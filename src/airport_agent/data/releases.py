"""Data releases: snapshots published as GitHub releases named `data-YYYY-MM-DD[-N]`.

The refresh workflow (.github/workflows/refresh.yml) builds a snapshot on GitHub's machine and
publishes it as a release: the snapshot folder as one `.tar.gz` archive plus its `manifest.json`,
with a comparison summary (`notes`) as the release text. Data versions are released apart from
code versions: a running server picks up new data without a new image.

The server (data_panel.py) asks the public GitHub API for the newest data release, with no token,
downloads the archive, checks it as a complete snapshot and places it in the local data store
under its version; the server's usual snapshot check then switches to it if it is the newest.

Workflow helpers (no network except `previous`):
  python -m airport_agent.data.releases check FOLDER       exit 1 with the reason if incomplete
  python -m airport_agent.data.releases previous DEST       the snapshot to compare against
  python -m airport_agent.data.releases notes NEW [OLD]     the release text, as Markdown
"""

import io
import json
import re
import sys
import tarfile
import tempfile
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path, PurePosixPath

from airport_agent.data.store import open_store, read_manifest, snapshot_problem, sort_key

API = "https://api.github.com"
DEFAULT_REPO = "uwnt/airport-agent"
TIMEOUT_SECONDS = 10
MAX_JSON_BYTES = 2_000_000
MAX_ARCHIVE_BYTES = 50_000_000  # snapshots are a few MB (scripts/check_snapshots.py budget)
MAX_UNPACKED_BYTES = 200_000_000  # a gzip bomb stops here, counted from the member headers
MAX_MEMBERS = 2_000
# The summaries the server's loader (metrics.load_cache) reads: a release must list them all.
SUMMARIES = ("ourairports", "dot_fares", "bts_ontime", "bts_enplanements", "opensky")
TAG = re.compile(r"^data-(\d{4}-\d{2}-\d{2})(?:-(\d+))?$")
PLAIN = re.compile(r"^latest-\d{4}-\d{2}-\d{2}(-\d+)?$")  # the versions store.latest() reads
ORIGIN_FILE = "release.json"  # who built it: written by the workflow, the tag added on install


class ReleaseError(Exception):
    """A data release that can't be used, in plain words."""


class SameHostRedirect(urllib.request.HTTPRedirectHandler):
    """Follows a redirect only to the same scheme, host and port.

    urllib copies every header, Authorization included, onto the redirected request, so a request
    carrying a token must never follow a redirect to another host.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        old, new = urllib.parse.urlsplit(req.full_url), urllib.parse.urlsplit(newurl)
        if (old.scheme, old.netloc) != (new.scheme, new.netloc):
            raise ReleaseError(f"refused a redirect to {new.netloc!r} for a request with a token")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def http(url, *, method="GET", headers=None, body=None, limit=MAX_JSON_BYTES):
    """The response body of one HTTPS request (bytes); refuses a body over `limit` bytes.

    Tests replace this function: they never use the network.
    """
    request = urllib.request.Request(url, data=body, method=method)
    request.add_header("User-Agent", "airport-agent")
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    authenticated = any(key.lower() == "authorization" for key in headers or {})
    opener = urllib.request.build_opener(*([SameHostRedirect] if authenticated else []))
    with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ReleaseError(f"the download from {url} is over {limit} bytes")
    return data


def get_json(url, headers=None):
    return json.loads(
        http(url, headers={"Accept": "application/vnd.github+json", **(headers or {})})
    )


def tag_order(tag):
    """Sort key of a data release tag: its date, then its same-day number; None if not one."""
    m = TAG.match(tag or "")
    return (m[1], int(m[2] or 1)) if m else None


def latest_release(repo):
    """The newest published data release of `repo` (by tag), or None when there is none."""
    releases = get_json(f"{API}/repos/{repo}/releases?per_page=100")
    data = [
        r
        for r in releases
        if tag_order(r.get("tag_name")) and not r.get("draft") and not r.get("prerelease")
    ]
    return max(data, key=lambda r: tag_order(r["tag_name"]), default=None)


def unpack(archive, dest):
    """Unpack a snapshot archive into `dest`; returns the one snapshot folder it holds.

    Refuses any member that would land outside `dest` (an absolute path or `..`), checked here by
    name and again by tarfile's "data" filter (which also refuses links out and device files), and
    an archive over MAX_MEMBERS members or MAX_UNPACKED_BYTES unpacked, counted from the member
    headers while reading them, before anything is written.
    """
    try:
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
            count, size = 0, 0
            for member in tar:  # one header at a time: stops at the first member over a cap
                count, size = count + 1, size + member.size
                if count > MAX_MEMBERS or size > MAX_UNPACKED_BYTES:
                    raise ReleaseError(
                        f"the archive is over {MAX_MEMBERS} files or {MAX_UNPACKED_BYTES} bytes"
                    )
                path = PurePosixPath(member.name)
                if path.is_absolute() or ".." in path.parts:
                    raise ReleaseError(f"unsafe path in the archive: {member.name!r}")
            tar.extractall(dest, filter="data")
    except tarfile.TarError as error:
        raise ReleaseError(f"the archive can't be unpacked: {error}") from error
    folders = list(Path(dest).iterdir())
    if len(folders) != 1 or not folders[0].is_dir():
        raise ReleaseError("the archive must hold exactly one snapshot folder")
    return folders[0]


def check(folder):
    """Raise ReleaseError unless `folder` is a plain snapshot (`latest-YYYY-MM-DD`) that loads.

    Complete: its manifest lists every summary the server reads and they all exist. Loads: the
    server's own loader reads it without an error, so a release that passes can be switched to.
    """
    name = Path(folder).name
    problem = snapshot_problem(folder)
    if problem:
        raise ReleaseError(f"snapshot {name!r} is incomplete: {problem}")
    if not PLAIN.match(name):
        raise ReleaseError(f"snapshot {name!r} is not a latest-YYYY-MM-DD snapshot")
    listed = read_manifest(folder).get("files")
    unlisted = [s for s in SUMMARIES if f"{s}.json" not in (listed or [])]
    if not isinstance(listed, list) or unlisted:
        raise ReleaseError(f"snapshot {name!r} doesn't list {', '.join(unlisted) or 'its files'}")
    manifest = read_manifest(folder)
    try:
        sort_key(manifest)  # what the store orders by
        date.fromisoformat(manifest["as_of"])
        if not manifest.get("built_at"):
            raise ValueError("no built_at")
        datetime.fromisoformat(manifest["built_at"])
    except (ValueError, KeyError, TypeError) as error:
        raise ReleaseError(
            f"snapshot {name!r} has a bad as_of or built_at in its manifest"
        ) from error
    from airport_agent.data.metrics import load_cache  # the loader the server uses

    try:
        load_cache(folder)
    except Exception as error:  # any error at all means the server couldn't use it either
        raise ReleaseError(f"snapshot {name!r} can't be loaded: {error!r}") from error


def install_latest(store, repo):
    """Put the newest data release of `repo` into `store`. Network.

    Returns {"tag", "version", "installed"}: installed is False when the store already has that
    version. Raises ReleaseError (or a network error) when there is none or it can't be used.
    """
    release = latest_release(repo)
    if release is None:
        raise ReleaseError(f"{repo} has no data releases yet")
    tag = release["tag_name"]
    asset = next((a for a in release.get("assets", []) if a["name"].endswith(".tar.gz")), None)
    if asset is None:
        raise ReleaseError(f"release {tag} has no .tar.gz snapshot")
    archive = http(asset["browser_download_url"], limit=MAX_ARCHIVE_BYTES)
    with tempfile.TemporaryDirectory(prefix="airport-agent-release-") as tmp:
        folder = unpack(archive, tmp)
        check(folder)
        version = folder.name
        if store.exists(version):
            return {"tag": tag, "version": version, "installed": False}
        origin_path = folder / ORIGIN_FILE
        try:
            origin = json.loads(origin_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            origin = {}
        origin = origin if isinstance(origin, dict) else {}
        origin_path.write_text(json.dumps({**origin, "tag": tag}), encoding="utf-8")
        store.publish(folder)
    return {"tag": tag, "version": version, "installed": True}


def origin(folder):
    """The release a snapshot folder came from ({"tag", "run_number", ...}), or None."""
    try:
        found = json.loads((Path(folder) / ORIGIN_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return found if isinstance(found, dict) and found.get("tag") else None


# --- The release text (run by the workflow) ------------------------------------------------------


def top_ten(folder):
    """[(code, score)] of the national top 10 under the default preset, from one snapshot."""
    from airport_agent import tools  # scoring is only needed by the workflow's summary

    result = tools.run_tool("rank_airports", {"top": 10}, folder)
    return [(row["code"], row["score"]) for row in result.get("rows", [])]


def notes(new, old=None):
    """A short Markdown comparison of snapshot `new` with `old` (sources' as-of dates, top 10)."""
    new_m = read_manifest(new)
    lines = [f"Snapshot `{new_m['version']}`, as of {new_m['as_of']}."]
    old_m = read_manifest(old) if old else None
    lines.append(f"Compared with `{old_m['version']}`." if old_m else "Nothing to compare with.")
    lines += ["", "| Source | As of | Before |", "|---|---|---|"]
    for key, source in sorted(new_m.get("sources", {}).items()):
        before = (old_m or {}).get("sources", {}).get(key, {}).get("as_of", "")
        lines.append(f"| {source.get('source', key)} | {source.get('as_of', '')} | {before} |")
    old_rank = {code: i for i, (code, _) in enumerate(top_ten(old), 1)} if old else {}
    lines += ["", "Top 10 nationally, default preset:", ""]
    for i, (code, score) in enumerate(top_ten(new), 1):
        was = old_rank.get(code)
        move = "" if not old else (" (new in the top 10)" if was is None else f" (was {was})")
        lines.append(f"{i}. {code} {score:g}{move}")
    return "\n".join(lines) + "\n"


def previous(dest, repo):
    """The snapshot to compare against: the newest data release, else the committed latest."""
    try:
        release = latest_release(repo)
        if release:
            asset = next(a for a in release["assets"] if a["name"].endswith(".tar.gz"))
            return unpack(http(asset["browser_download_url"], limit=MAX_ARCHIVE_BYTES), dest)
    except (OSError, ValueError, StopIteration, ReleaseError) as error:
        print(f"No previous data release to compare with: {error}", file=sys.stderr)
    store = open_store()
    version = store.latest()
    return store.get(version) if version else None


def main(argv):
    command, *args = argv
    if command == "check":
        try:
            check(args[0])
        except ReleaseError as error:
            print(f"::error::{error}")
            return 1
        print(f"{Path(args[0]).name}: complete")
    elif command == "previous":
        found = previous(args[0], args[1] if len(args) > 1 else DEFAULT_REPO)
        print(found or "")
    elif command == "notes":
        print(notes(args[0], args[1] if len(args) > 1 and args[1] else None), end="")
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
