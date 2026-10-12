"""The "Data" panel: who built the data in use, and three ways to get newer data.

- **Get latest data** (POST /data/latest): download the newest GitHub data release (releases.py)
  into the local data store and switch to it. The same check runs once in the background at
  startup, so startup and /health never wait on GitHub; any failure logs one line and the data
  already in use (the snapshot baked into the image) stays. DATA_RELEASES=off switches it off.
- **Refresh on this machine** (POST /data/refresh {"on": "local"}): runs `airport-agent refresh`
  as a background process inside this server's machine or container, then switches to the new
  snapshot. Only when ALLOW_LOCAL_REFRESH=true: it downloads a lot and needs memory, so it is off
  by default and must stay off on a public site.
- **Refresh on GitHub Actions** (POST /data/refresh {"on": "github"}): starts the refresh
  workflow through GitHub's API, follows the run, then gets the release it published. Only when
  GITHUB_TOKEN_REFRESH is set (a fine-grained token with Actions: write on this one repository).
  The token stays on the server: no response ever contains it.

Guards: POST only, from pages served by this host (the same check as /talk); one job at a time;
at most one refresh per hour and one "get latest" per minute per server process.
GET /data/status says what is in use, which options are allowed (with the reason when not), and
how each job is going; the page polls it while a job runs.
"""

import json
import logging
import os
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from airport_agent import talk
from airport_agent.data import releases
from airport_agent.data.store import read_manifest

log = logging.getLogger(__name__)
router = APIRouter()

WORKFLOW = "refresh.yml"
POLL_SECONDS = 20
MAX_WAIT_SECONDS = 90 * 60  # the workflow's own timeout is 60 minutes, plus time in the queue
sleep = time.sleep  # tests replace it: no waiting
OFF_HERE = "Disabled on this deployment"
NEEDS_TOKEN = "Needs a maintainer token; use Get latest data"
RELEASES_OFF = "Data releases are off on this deployment"
# What the panel says when the release check stops, by ReleaseError kind: fixed words only,
# never the error's own text (it can hold a path or an address).
CANNOT_REACH = "Could not reach GitHub."
RELEASE_MESSAGES = {
    releases.NONE: "No data releases yet.",
    releases.NO_SNAPSHOT: "The release has no snapshot file.",
    releases.TOO_LARGE: "The download was too large.",
    releases.CHECKS: releases.CHECKS_FAILED,
    releases.REDIRECT: CANNOT_REACH,
}


def _server():
    from airport_agent import server  # imported here: server.py imports this module

    return server


def repo():
    return os.environ.get("GITHUB_REPOSITORY", "").strip() or releases.DEFAULT_REPO


def options():
    """Each way to get newer data: {"enabled": bool, "reason": why not, or None}."""
    releases_on = os.environ.get("DATA_RELEASES", "on").strip().lower() != "off"
    local_on = os.environ.get("ALLOW_LOCAL_REFRESH", "").strip().lower() == "true"
    token = bool(os.environ.get("GITHUB_TOKEN_REFRESH", "").strip())

    def option(enabled, reason):
        return {"enabled": enabled, "reason": None if enabled else reason}

    return {
        "latest": option(releases_on, RELEASES_OFF),
        "local": option(local_on, OFF_HERE),
        "github": option(token and releases_on, NEEDS_TOKEN if not token else RELEASES_OFF),
    }


class RateLimit:
    """At most one use per `seconds` in this process; take() returns seconds to wait, 0 if taken."""

    def __init__(self, seconds, clock=time.monotonic):
        self.seconds, self.clock = seconds, clock
        self.lock = threading.Lock()
        self.last = None

    def take(self):
        with self.lock:
            now = self.clock()
            if self.last is not None and now - self.last < self.seconds:
                return int(self.seconds - (now - self.last)) + 1
            self.last = now
            return 0


class Jobs:
    """How each job is going: {"state": idle|running|done|failed, "message": ..., ...}."""

    def __init__(self):
        self.lock = threading.Lock()
        self.state = {
            name: {"state": "idle", "message": ""} for name in ("latest", "local", "github")
        }

    def busy(self):
        return any(job["state"] == "running" for job in self.state.values())

    def start(self, name, message):
        """Mark `name` running; False if any job already runs (one at a time)."""
        with self.lock:
            if self.busy():
                return False
            self.state[name] = {"state": "running", "message": message}
            return True

    def update(self, name, state=None, **fields):
        with self.lock:
            job = dict(self.state[name], **fields)
            if state:
                job["state"] = state
            self.state[name] = job

    def snapshot(self):
        with self.lock:
            return {name: dict(job) for name, job in self.state.items()}


jobs = Jobs()
refresh_limit = RateLimit(60 * 60)
latest_limit = RateLimit(60)
startup_versions = set()  # snapshots in the store when the server started (see built_by)


def _finish(name, target, *args):
    """Run job `name`; whatever it raises, it ends "done" or "failed", never stuck "running"."""
    try:
        target(*args)
    except Exception as error:  # the job boundary: a stuck job would refuse every later one
        log.warning("Data job %r stopped with an error: %r", name, error)
        jobs.update(
            name,
            "failed",
            message="The job stopped with an unexpected error; the data in use stays.",
        )
    if jobs.snapshot()[name]["state"] == "running":
        jobs.update(
            name, "failed", message="The job ended without a result; the data in use stays."
        )


def _run(name, target, *args):
    threading.Thread(target=_finish, args=(name, target, *args), daemon=True).start()


def switch():
    """Look at the store now (not at the next interval) and use its newest snapshot."""
    data = _server().data
    data.checked_at = None
    snapshot = data.current()
    return snapshot.version if snapshot else None


def _get_latest(job):
    """The release check, as job `job`; never raises (a failure keeps the data in use)."""
    try:
        result = releases.install_latest(_server()._store(), repo())
    except Exception as error:  # network, GitHub, a bad archive: report it, keep serving
        kind = getattr(error, "kind", None)  # only a ReleaseError has one
        if kind == releases.NONE:  # a normal state, not a failure
            jobs.update(job, "done", message=RELEASE_MESSAGES[kind])
            return False
        log.warning("Data release check failed, keeping the data in use: %s", error)
        why = RELEASE_MESSAGES.get(kind, CANNOT_REACH)
        jobs.update(job, "failed", message=f"{why} The data in use stays.")
        return False
    in_use = switch()
    got = "Downloaded" if result["installed"] else "Already had"
    jobs.update(
        job,
        "done",
        message=f"{got} data release {result['tag']}; answering from {in_use}.",
    )
    return True


def start_release_check():
    """At startup: remember the snapshots already here, then check releases in the background."""
    root = getattr(_server()._store(), "root", None)  # a test's fake store has no folder
    if root is not None and root.is_dir():
        startup_versions.update(p.name for p in root.iterdir() if p.is_dir())
    if options()["latest"]["enabled"] and jobs.start("latest", "Checking for a data release"):
        _run("latest", _get_latest, "latest")


# What `airport-agent refresh` reads from the environment, and nothing else: an allowlist, so a
# token added to the server later (GitHub, Doppler, the model's key) never reaches the child.
CHILD_ENV = {
    "PATH", "HOME", "LANG", "TZ", "PYTHONPATH", "PYTHONHOME", "PYTHONUTF8", "PYTHONIOENCODING",
    "VIRTUAL_ENV", "SSL_CERT_FILE", "SSL_CERT_DIR",
    "DATA_STORE", "OPENSKY_CLIENT_ID", "OPENSKY_CLIENT_SECRET",
}  # fmt: skip
# The sources refresh names at the start of its progress lines (build.py's _log).
SOURCES = ("OurAirports", "DOT Table 1a", "BTS on-time", "BTS boardings", "OpenSky")


def _child_env():
    return {k: v for k, v in os.environ.items() if k in CHILD_ENV or k.startswith("LC_")}


def _progress(line):
    """The public progress for one refresh output line: a source name only, never the raw text.

    Raw lines can hold a download error or a store address; a fixed set of names can't leak.
    None when the line names no step (the progress shown stays as it was).
    """
    if line.startswith("Published snapshot"):
        return "Publishing the snapshot"
    source = next((s for s in SOURCES if line.startswith(s)), None)
    return f"Working on {source}" if source else None


def _local_refresh():
    """`airport-agent refresh` in a child process; the source it is on is the progress."""
    try:
        process = subprocess.Popen(
            [sys.executable, "-m", "airport_agent.data"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",  # a stray byte in a download error must not stop the reading
            env=_child_env(),
        )
        for line in process.stdout:
            progress = _progress(line.strip())
            if progress:
                jobs.update("local", progress=progress)
        code = process.wait()
    except OSError as error:
        log.warning("Local refresh could not start: %s", error)
        jobs.update("local", "failed", message="The refresh could not start.")
        return
    if code != 0:
        jobs.update("local", "failed", message=f"The refresh failed (exit code {code}).")
        return
    jobs.update("local", "done", message=f"Refreshed on this machine; answering from {switch()}.")


def _github(path, token, method="GET", body=None):
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    data = releases.http(
        f"{releases.API}/repos/{repo()}{path}", method=method, headers=headers, body=body
    )
    return json.loads(data) if data else None


def _find_run(token, since):
    """The workflow_dispatch run of the refresh workflow created at or after `since`, or None."""
    for _ in range(6):  # GitHub lists a new run within a few seconds
        found = _github(
            f"/actions/workflows/{WORKFLOW}/runs?event=workflow_dispatch&per_page=5", token
        )
        runs = [r for r in found.get("workflow_runs", []) if r.get("created_at", "") >= since]
        if runs:
            return min(runs, key=lambda r: r["created_at"])
        sleep(5)
    return None


def _github_refresh(token):
    """Start the refresh workflow, follow its run, then get the release it published."""
    try:
        branch = _github("", token)["default_branch"]
        since = datetime.now(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
        body = json.dumps({"ref": branch}).encode()
        _github(f"/actions/workflows/{WORKFLOW}/dispatches", token, method="POST", body=body)
        run = _find_run(token, since)
        if run is None:
            raise releases.ReleaseError("the workflow run did not appear on GitHub")
        waited = 0
        while run["status"] != "completed" and waited < MAX_WAIT_SECONDS:
            jobs.update(
                "github", progress=f"Run #{run['run_number']}: {run['status']}", url=run["html_url"]
            )
            sleep(POLL_SECONDS)
            waited += POLL_SECONDS
            run = _github(f"/actions/runs/{run['id']}", token)
    except Exception as error:  # report it in the panel; the data in use stays
        log.warning("GitHub refresh failed: %s", error)
        jobs.update("github", "failed", message="Could not run the refresh on GitHub.")
        return
    if run.get("conclusion") != "success":
        state = run.get("conclusion") or "still running"
        jobs.update("github", "failed", message=f"Run #{run['run_number']} ended: {state}.")
        return
    jobs.update("github", progress=f"Run #{run['run_number']} succeeded; downloading its release")
    _get_latest("github")


def built_by(folder, version):
    """Who built a snapshot, in words: a GitHub release, the image, or this machine."""
    found = releases.origin(folder)
    if found:
        run = f" (run #{found['run_number']})" if found.get("run_number") else ""
        return f"GitHub release {found['tag']}{run}"
    if os.environ.get("RELEASE_SHA", "").strip() and version in startup_versions:
        return "baked into the image"
    built = read_manifest(folder).get("built_at", "")
    return f"this machine, {built[:16].replace('T', ' ')} UTC" if built else "this machine"


def _same_origin(request):
    if not talk.same_origin(request.headers):
        raise HTTPException(status_code=403, detail="Only this site's own page can do that.")


def _limited(limit, what):
    wait = limit.take()
    if wait:
        minutes = (wait + 59) // 60
        raise HTTPException(
            status_code=429,
            detail=f"{what} at most once per {'hour' if limit.seconds >= 3600 else 'minute'}; "
            f"try again in {minutes} minute{'s' if minutes != 1 else ''}.",
            headers={"Retry-After": str(wait)},
        )


@router.get("/data/status")
def status():
    snapshot = _server().data.current()
    current = None
    if snapshot:
        folder = _server()._store().get(snapshot.version)
        current = {
            "version": snapshot.version,
            "as_of": snapshot.as_of,
            "built_by": built_by(folder, snapshot.version),
        }
    return {"current": current, "options": options(), "jobs": jobs.snapshot(), "repo": repo()}


@router.post("/data/latest", status_code=202)
def get_latest(request: Request):
    _same_origin(request)
    option = options()["latest"]
    if not option["enabled"]:
        raise HTTPException(status_code=403, detail=option["reason"])
    if jobs.busy():
        raise HTTPException(status_code=409, detail="A data job is already running.")
    _limited(latest_limit, "Get latest data runs")
    if not jobs.start("latest", "Checking for a data release"):
        raise HTTPException(status_code=409, detail="A data job is already running.")
    _run("latest", _get_latest, "latest")
    return status()


class RefreshRequest(BaseModel):
    on: Literal["local", "github"]


@router.post("/data/refresh", status_code=202)
def refresh(body: RefreshRequest, request: Request):
    _same_origin(request)
    option = options()[body.on]
    if not option["enabled"]:
        raise HTTPException(status_code=403, detail=option["reason"])
    if jobs.busy():
        raise HTTPException(status_code=409, detail="A data job is already running.")
    _limited(refresh_limit, "A refresh runs")
    where = "this machine" if body.on == "local" else "GitHub Actions"
    if not jobs.start(body.on, f"Refreshing on {where}"):
        raise HTTPException(status_code=409, detail="A data job is already running.")
    if body.on == "local":
        _run("local", _local_refresh)
    else:
        _run("github", _github_refresh, os.environ["GITHUB_TOKEN_REFRESH"].strip())
    return status()
