"""The Data panel's endpoints (data_panel.py): options, guards, rate limits, jobs. No network."""

import io
import json
import threading
import time

import pytest
from fastapi.testclient import TestClient

from airport_agent import data_panel, server
from airport_agent.data import releases
from airport_agent.data.store import FileStore

ORIGIN = {"Origin": "http://testserver"}
TOKEN = "tok-never-shown-123"


@pytest.fixture
def web(monkeypatch, tmp_path, make_snapshot):
    root = tmp_path / "store"
    make_snapshot("latest-2026-10-11", root=root, built_at="2026-10-11T14:03:00+00:00")
    monkeypatch.setenv("DATA_STORE", f"file://{root}")
    for name in ("ALLOW_LOCAL_REFRESH", "GITHUB_TOKEN_REFRESH", "RELEASE_SHA", "GEMINI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(server, "data", server.DataVersion(FileStore(root), clock=lambda: 0.0))
    monkeypatch.setattr(data_panel, "jobs", data_panel.Jobs())
    monkeypatch.setattr(data_panel, "refresh_limit", data_panel.RateLimit(3600))
    monkeypatch.setattr(data_panel, "latest_limit", data_panel.RateLimit(60))
    monkeypatch.setattr(data_panel, "startup_versions", set())
    monkeypatch.setattr(data_panel, "sleep", lambda seconds: None)
    with TestClient(server.app) as client:  # DATA_RELEASES=off here (conftest): no startup check
        yield client


def wait_for(job):
    for _ in range(200):
        state = data_panel.jobs.snapshot()[job]
        if state["state"] != "running":
            return state
        time.sleep(0.02)
    raise AssertionError(f"job {job} still running")


def test_options_are_disabled_with_reasons_by_default(web):
    options = web.get("/data/status").json()["options"]
    assert options["latest"] == {"enabled": False, "reason": data_panel.RELEASES_OFF}
    assert options["local"] == {"enabled": False, "reason": "Disabled on this deployment"}
    assert options["github"] == {
        "enabled": False,
        "reason": "Needs a maintainer token; use Get latest data",
    }


def test_options_follow_the_environment(web, monkeypatch):
    monkeypatch.setenv("DATA_RELEASES", "on")
    monkeypatch.setenv("ALLOW_LOCAL_REFRESH", "true")
    monkeypatch.setenv("GITHUB_TOKEN_REFRESH", TOKEN)
    options = web.get("/data/status").json()["options"]
    assert all(option == {"enabled": True, "reason": None} for option in options.values())


def test_disabled_option_is_refused_with_its_reason(web):
    response = web.post("/data/refresh", json={"on": "local"}, headers=ORIGIN)
    assert response.status_code == 403
    assert response.json()["detail"] == "Disabled on this deployment"
    response = web.post("/data/refresh", json={"on": "github"}, headers=ORIGIN)
    assert response.json()["detail"] == "Needs a maintainer token; use Get latest data"


def test_triggers_need_this_sites_page(web, monkeypatch):
    monkeypatch.setenv("DATA_RELEASES", "on")
    assert web.post("/data/latest").status_code == 403
    response = web.post("/data/latest", headers={"Origin": "https://elsewhere.example"})
    assert response.status_code == 403
    assert web.get("/data/latest").status_code == 405


@pytest.mark.parametrize(
    ("release_sha", "origin", "expected"),
    [
        ("", None, "this machine, 2026-10-11 14:03 UTC"),
        ("abc123", None, "baked into the image"),
        (
            "abc123",
            {"tag": "data-2026-10-19", "run_number": 12},
            "GitHub release data-2026-10-19 (run #12)",
        ),
    ],
)
def test_status_says_who_built_the_data(web, monkeypatch, release_sha, origin, expected):
    monkeypatch.setenv("RELEASE_SHA", release_sha)
    data_panel.startup_versions.add("latest-2026-10-11")
    if origin:
        folder = server.data.store.get("latest-2026-10-11")
        (folder / "release.json").write_text(json.dumps(origin), encoding="utf-8")
    current = web.get("/data/status").json()["current"]
    assert current == {"version": "latest-2026-10-11", "as_of": "2026-10-11", "built_by": expected}


def test_get_latest_is_limited_to_once_a_minute(web, monkeypatch):
    monkeypatch.setenv("DATA_RELEASES", "on")
    calls = []
    monkeypatch.setattr(
        releases,
        "install_latest",
        lambda store, repo: (
            calls.append(repo)
            or {"tag": "data-2026-10-19", "version": "latest-2026-10-11", "installed": False}
        ),
    )
    assert web.post("/data/latest", headers=ORIGIN).status_code == 202
    assert wait_for("latest")["state"] == "done"
    second = web.post("/data/latest", headers=ORIGIN)
    assert second.status_code == 429
    assert "once per minute" in second.json()["detail"]
    assert int(second.headers["Retry-After"]) <= 60
    assert len(calls) == 1


class FakeProcess:
    """Stands in for the refresh child process; prints two lines, then waits for `release`."""

    started = []

    def __init__(self, args, **kwargs):
        FakeProcess.started.append((args, kwargs["env"]))
        self.release = threading.Event()
        FakeProcess.last = self
        self.stdout = io.StringIO("Downloading DOT fares\nPublished snapshot latest-x\n")

    def wait(self):
        self.release.wait(5)
        return 0


@pytest.fixture
def local(web, monkeypatch):
    monkeypatch.setenv("ALLOW_LOCAL_REFRESH", "true")
    monkeypatch.setenv("GITHUB_TOKEN_REFRESH", TOKEN)
    FakeProcess.started = []
    monkeypatch.setattr(data_panel.subprocess, "Popen", FakeProcess)
    return web


def test_one_local_refresh_at_a_time_then_once_an_hour(local):
    first = local.post("/data/refresh", json={"on": "local"}, headers=ORIGIN)
    assert first.status_code == 202
    for _ in range(100):  # the fake has started and is waiting
        if FakeProcess.started:
            break
        time.sleep(0.02)
    busy = local.post("/data/refresh", json={"on": "local"}, headers=ORIGIN)
    assert busy.status_code == 409
    FakeProcess.last.release.set()
    state = wait_for("local")
    assert state["state"] == "done"
    assert state["progress"] == "Publishing the snapshot"
    later = local.post("/data/refresh", json={"on": "local"}, headers=ORIGIN)
    assert later.status_code == 429
    assert "once per hour" in later.json()["detail"]
    assert len(FakeProcess.started) == 1
    args, env = FakeProcess.started[0]
    assert args[1:] == ["-m", "airport_agent.data"]
    assert "GITHUB_TOKEN_REFRESH" not in env


def test_github_refresh_follows_the_run_and_never_shows_the_token(web, monkeypatch):
    monkeypatch.setenv("DATA_RELEASES", "on")
    monkeypatch.setenv("GITHUB_TOKEN_REFRESH", TOKEN)
    requests = []
    run = {"id": 7, "run_number": 12, "html_url": "https://github.test/run/7"}

    def http(url, method="GET", headers=None, body=None, **kwargs):
        requests.append((method, url, headers or {}, body))
        path = url.removeprefix(f"{releases.API}/repos/{data_panel.repo()}")
        if path == "":
            return json.dumps({"default_branch": "dev"}).encode()
        if path.endswith("/dispatches"):
            return b""
        if "/runs?" in path:
            listing = [{**run, "status": "queued", "created_at": "2999-01-01T00:00:00Z"}]
            return json.dumps({"workflow_runs": listing}).encode()
        if path == "/actions/runs/7":
            return json.dumps({**run, "status": "completed", "conclusion": "success"}).encode()
        raise AssertionError(f"unexpected {url}")

    monkeypatch.setattr(releases, "http", http)
    monkeypatch.setattr(
        releases,
        "install_latest",
        lambda store, repo: {
            "tag": "data-2999-01-01",
            "version": "latest-2026-10-11",
            "installed": True,
        },
    )
    response = web.post("/data/refresh", json={"on": "github"}, headers=ORIGIN)
    assert response.status_code == 202
    state = wait_for("github")
    assert state["state"] == "done", state
    assert "data-2999-01-01" in state["message"]
    method, _, headers, body = requests[1]
    assert method == "POST" and json.loads(body) == {"ref": "dev"}
    assert headers["Authorization"] == f"Bearer {TOKEN}"
    for text in (response.text, web.get("/data/status").text, web.get("/health").text):
        assert TOKEN not in text


def test_failed_github_run_is_reported(web, monkeypatch):
    monkeypatch.setenv("DATA_RELEASES", "on")
    monkeypatch.setenv("GITHUB_TOKEN_REFRESH", TOKEN)

    def http(url, **kwargs):
        raise OSError("GitHub is down")

    monkeypatch.setattr(releases, "http", http)
    assert web.post("/data/refresh", json={"on": "github"}, headers=ORIGIN).status_code == 202
    state = wait_for("github")
    assert state["state"] == "failed" and "GitHub" in state["message"]
    assert TOKEN not in web.get("/data/status").text


def test_a_job_that_raises_anything_ends_failed(web, monkeypatch):
    """A snapshot that can't load (here a TypeError) must not leave the job running forever."""
    monkeypatch.setenv("DATA_RELEASES", "on")
    monkeypatch.setattr(
        releases,
        "install_latest",
        lambda store, repo: {"tag": "data-2026-10-19", "version": "x", "installed": True},
    )

    def broken_switch():
        raise TypeError("list indices must be integers or slices, not str")

    monkeypatch.setattr(data_panel, "switch", broken_switch)
    assert web.post("/data/latest", headers=ORIGIN).status_code == 202
    state = wait_for("latest")
    assert state["state"] == "failed"
    assert "unexpected error" in state["message"] and "data in use stays" in state["message"]
    assert not data_panel.jobs.busy()


class UndecodableProcess(FakeProcess):
    """A refresh whose output holds bytes that are not UTF-8, decoded the way Popen would."""

    def __init__(self, args, **kwargs):
        super().__init__(args, **kwargs)
        self.release.set()
        raw = b"OpenSky unavailable (\xff\xfe bad bytes)\nPublished snapshot latest-x\n"
        errors = kwargs.get("errors") or "strict"
        self.stdout = io.TextIOWrapper(io.BytesIO(raw), encoding="utf-8", errors=errors)


def test_local_refresh_survives_undecodable_output(local, monkeypatch):
    monkeypatch.setattr(data_panel.subprocess, "Popen", UndecodableProcess)
    assert local.post("/data/refresh", json={"on": "local"}, headers=ORIGIN).status_code == 202
    state = wait_for("local")
    assert state["state"] == "done", state
    assert state["progress"] == "Publishing the snapshot"


def test_refresh_child_gets_no_token_or_key(monkeypatch):
    secrets = {
        "GITHUB_TOKEN",
        "GH_TOKEN",
        "DOPPLER_TOKEN",
        "GEMINI_API_KEY",
        "GITHUB_TOKEN_REFRESH",
        "SOME_FUTURE_API_KEY",
    }
    for name in secrets:
        monkeypatch.setenv(name, "x-not-a-real-value")
    monkeypatch.setenv("OPENSKY_CLIENT_ID", "client")
    monkeypatch.setenv("DATA_STORE", "file:///store")
    monkeypatch.setenv("LC_ALL", "C.UTF-8")
    env = data_panel._child_env()
    assert not secrets & env.keys()  # names only: a failure must not print values
    assert env["OPENSKY_CLIENT_ID"] == "client" and env["DATA_STORE"] == "file:///store"
    assert env["LC_ALL"] == "C.UTF-8" and "PATH" in env


@pytest.mark.parametrize(
    ("line", "shown"),
    [
        ("OpenSky unavailable (401 for https://user:secret@example.test); using the sample",
         "Working on OpenSky"),
        ("DOT Table 1a: 2026 Q1 and 2019 Q1", "Working on DOT Table 1a"),
        ("Published snapshot latest-x to FileStore('/somewhere')", "Publishing the snapshot"),
        ("Traceback (most recent call last): token=abc", None),
    ],
)  # fmt: skip
def test_progress_shows_only_the_source_name(line, shown):
    assert data_panel._progress(line) == shown


LEAKY = "/secret/path https://example.invalid"


def assert_plain(web, job):
    """The job failed, and the public status shows neither the path nor the URL of the error."""
    state = wait_for(job)
    assert state["state"] == "failed", state
    text = web.get("/data/status").text
    assert "/secret/path" not in text and "example.invalid" not in text


def test_failure_messages_never_show_error_text(local, monkeypatch):
    monkeypatch.setenv("DATA_RELEASES", "on")

    def boom(*args, **kwargs):
        raise OSError(LEAKY)

    def refused(*args, **kwargs):
        raise releases.ReleaseError(LEAKY)

    def fire(path, job, body=None):
        data_panel.latest_limit.last = data_panel.refresh_limit.last = None
        assert local.post(path, json=body, headers=ORIGIN).status_code == 202
        assert_plain(local, job)

    monkeypatch.setattr(releases, "install_latest", boom)  # GitHub unreachable
    fire("/data/latest", "latest")
    monkeypatch.setattr(releases, "install_latest", refused)  # a release that fails the checks
    fire("/data/latest", "latest")
    monkeypatch.setattr(data_panel, "_get_latest", boom)  # the job boundary
    fire("/data/latest", "latest")
    monkeypatch.setattr(releases, "http", boom)  # the GitHub refresh
    fire("/data/refresh", "github", {"on": "github"})
    monkeypatch.setattr(data_panel.subprocess, "Popen", boom)  # the local process cannot start
    fire("/data/refresh", "local", {"on": "local"})


@pytest.mark.parametrize(
    ("error", "state", "message"),
    [
        (releases.ReleaseError(LEAKY, kind="none"), "done", "No data releases yet."),
        (OSError(LEAKY), "failed", "Could not reach GitHub. The data in use stays."),
        (
            releases.ReleaseError(LEAKY, kind="no_snapshot"),
            "failed",
            "The release has no snapshot file. The data in use stays.",
        ),
        (
            releases.ReleaseError(LEAKY, kind="too_large"),
            "failed",
            "The download was too large. The data in use stays.",
        ),
        (
            releases.ReleaseError(LEAKY),
            "failed",
            "The release failed the data checks. The data in use stays.",
        ),
    ],
)
def test_release_check_says_why_in_fixed_words(web, monkeypatch, error, state, message):
    monkeypatch.setenv("DATA_RELEASES", "on")

    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(releases, "install_latest", fail)
    assert web.post("/data/latest", headers=ORIGIN).status_code == 202
    assert wait_for("latest") == {"state": state, "message": message}
    assert web.get("/data/status").json()["current"]["version"] == "latest-2026-10-11"
