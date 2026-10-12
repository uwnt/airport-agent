"""Data releases (data/releases.py): lookup, download and checks, with a fake HTTP layer."""

import email.message
import gzip
import io
import json
import re
import tarfile
import time
import urllib.error
import urllib.request
import urllib.response
from pathlib import Path

import pytest
import yaml
from conftest import tar_gz
from fastapi.testclient import TestClient

from airport_agent import data_panel, server
from airport_agent.data import releases
from airport_agent.data.store import FileStore

REPO = "owner/repo"
ASSET_URL = "https://example.test/snapshot.tar.gz"


def release(tag, **fields):
    asset = {"name": "snapshot.tar.gz", "browser_download_url": f"{ASSET_URL}?{tag}"}
    return {"tag_name": tag, "draft": False, "prerelease": False, "assets": [asset], **fields}


def fake_http(monkeypatch, listing, archive=b""):
    """GitHub answers with `listing` (a list of releases) and every asset is `archive`."""
    seen = []

    def http(url, **kwargs):
        seen.append(url)
        if url.startswith(f"{releases.API}/repos/{REPO}/releases"):
            return json.dumps(listing).encode()
        if url.startswith(ASSET_URL):
            return archive
        raise AssertionError(f"unexpected request {url}")

    monkeypatch.setattr(releases, "http", http)
    return seen


@pytest.fixture
def release_archive(make_snapshot, tmp_path):
    folder = make_snapshot("latest-2026-10-19", "2026-10-19")
    (folder / "release.json").write_text(json.dumps({"run_number": 12}), encoding="utf-8")
    return tar_gz((folder.name, folder))


def test_latest_release_is_picked_by_tag(monkeypatch):
    listing = [
        release("data-2026-10-05"),
        release("data-2026-10-19"),
        release("data-2026-10-19-2"),
        release("data-2026-10-12"),
        release("v1.0.0"),
        release("data-2026-10-30", draft=True),
        release("data-2026-10-31", prerelease=True),
    ]
    fake_http(monkeypatch, listing)
    assert releases.latest_release(REPO)["tag_name"] == "data-2026-10-19-2"


def test_no_data_release_is_reported(monkeypatch, tmp_path):
    fake_http(monkeypatch, [release("v1.0.0")])
    with pytest.raises(releases.ReleaseError, match="no data releases"):
        releases.install_latest(FileStore(tmp_path), REPO)


def test_release_is_installed_with_its_origin(monkeypatch, tmp_path, release_archive):
    fake_http(monkeypatch, [release("data-2026-10-19")], release_archive)
    store = FileStore(tmp_path)
    result = releases.install_latest(store, REPO)
    assert result == {"tag": "data-2026-10-19", "version": "latest-2026-10-19", "installed": True}
    assert store.latest() == "latest-2026-10-19"
    origin = releases.origin(store.get("latest-2026-10-19"))
    assert origin == {"run_number": 12, "tag": "data-2026-10-19"}
    # A second check finds the version already there and changes nothing.
    assert releases.install_latest(store, REPO)["installed"] is False


def test_bad_archive_is_refused(monkeypatch, tmp_path):
    fake_http(monkeypatch, [release("data-2026-10-19")], b"not a gzip file")
    with pytest.raises(releases.ReleaseError, match="can't be unpacked"):
        releases.install_latest(FileStore(tmp_path / "store"), REPO)
    assert not (tmp_path / "store").exists()


def test_incomplete_snapshot_is_refused(monkeypatch, tmp_path, make_snapshot):
    folder = make_snapshot("latest-2026-10-19", "2026-10-19")
    (folder / "manifest.json").unlink()
    fake_http(monkeypatch, [release("data-2026-10-19")], tar_gz((folder.name, folder)))
    with pytest.raises(releases.ReleaseError, match="no manifest.json"):
        releases.install_latest(FileStore(tmp_path / "store"), REPO)
    assert not (tmp_path / "store").exists()


def test_point_in_time_snapshot_is_refused(monkeypatch, tmp_path, make_snapshot):
    folder = make_snapshot("2019-12", "2019-12-31")
    fake_http(monkeypatch, [release("data-2026-10-19")], tar_gz((folder.name, folder)))
    with pytest.raises(releases.ReleaseError, match="not a latest-YYYY-MM-DD"):
        releases.install_latest(FileStore(tmp_path), REPO)


@pytest.mark.parametrize("name", ["../escape.json", "/abs/escape.json"])
def test_member_outside_the_folder_is_refused(monkeypatch, tmp_path, make_snapshot, name):
    folder = make_snapshot("latest-2026-10-19", "2026-10-19")
    archive = with_member(tar_gz((folder.name, folder)), name)
    fake_http(monkeypatch, [release("data-2026-10-19")], archive)
    store_root = tmp_path / "store"
    with pytest.raises(releases.ReleaseError, match="unsafe path"):
        releases.install_latest(FileStore(store_root), REPO)
    assert not store_root.exists()
    assert not (tmp_path / "escape.json").exists()


def with_member(archive, name):
    """The archive plus one small file stored under exactly `name` (tarfile.add strips a "/")."""
    buffer = io.BytesIO()
    with (
        tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as source,
        tarfile.open(fileobj=buffer, mode="w:gz") as tar,
    ):
        for member in source.getmembers():
            tar.addfile(member, source.extractfile(member) if member.isfile() else None)
        extra = tarfile.TarInfo(name)
        extra.size = 2
        tar.addfile(extra, io.BytesIO(b"{}"))
    return buffer.getvalue()


def test_release_listing_no_files_is_refused(monkeypatch, tmp_path, make_snapshot):
    folder = make_snapshot("latest-2026-10-19", "2026-10-19", files=[])
    fake_http(monkeypatch, [release("data-2026-10-19")], tar_gz((folder.name, folder)))
    store_root = tmp_path / "store"
    with pytest.raises(releases.ReleaseError, match="doesn't list ourairports"):
        releases.install_latest(FileStore(store_root), REPO)
    assert not store_root.exists()


def test_release_that_does_not_load_is_refused(monkeypatch, tmp_path, make_snapshot):
    """A summary the loader can't use (here `[]`) is caught by a trial load, not by the server."""
    folder = make_snapshot("latest-2026-10-19", "2026-10-19")
    (folder / "ourairports.json").write_text("[]", encoding="utf-8")
    fake_http(monkeypatch, [release("data-2026-10-19")], tar_gz((folder.name, folder)))
    store = FileStore(tmp_path / "store")
    make_snapshot("latest-2026-10-11", root=store.root)
    with pytest.raises(releases.ReleaseError, match="can't be loaded"):
        releases.install_latest(store, REPO)
    assert sorted(p.name for p in store.root.iterdir()) == ["latest-2026-10-11"]


def archive_of(*members):
    """A .tar.gz of TarInfo members with no file bodies (only their headers are read)."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for member in members:
            tar.addfile(member)
    return buffer.getvalue()


def link(name, target, kind):
    member = tarfile.TarInfo(name)
    member.type, member.linkname = kind, target
    return member


@pytest.mark.parametrize(
    "member",
    [
        link("latest-2026-10-19/passwd", "/etc/passwd", tarfile.SYMTYPE),
        link("latest-2026-10-19/up", "../../outside", tarfile.SYMTYPE),
        link("latest-2026-10-19/hard", "/etc/passwd", tarfile.LNKTYPE),
        link("latest-2026-10-19/hard", "../outside", tarfile.LNKTYPE),
    ],
)
def test_links_out_of_the_archive_are_refused(tmp_path, member):
    folder = tarfile.TarInfo("latest-2026-10-19")
    folder.type = tarfile.DIRTYPE
    with pytest.raises(releases.ReleaseError, match="can't be unpacked"):
        releases.unpack(archive_of(folder, member), tmp_path)
    assert not (tmp_path / "latest-2026-10-19" / member.name.split("/")[-1]).exists()


def test_archive_over_the_size_cap_is_refused(tmp_path):
    """A header declaring 300 MB is refused at that header: the body is never read."""
    huge = tarfile.TarInfo("latest-2026-10-19/huge.json")
    huge.size = 300_000_000
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb") as gz:
        gz.write(huge.tobuf())  # the header only: the archive is a few hundred bytes
    with pytest.raises(releases.ReleaseError, match="over 2000 files or 200000000 bytes"):
        releases.unpack(buffer.getvalue(), tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_archive_over_the_member_cap_is_refused(tmp_path):
    members = [tarfile.TarInfo(f"latest-2026-10-19/{i}.json") for i in range(2_001)]
    with pytest.raises(releases.ReleaseError, match="over 2000 files"):
        releases.unpack(archive_of(*members), tmp_path)
    assert list(tmp_path.iterdir()) == []


class FakeHTTPS(urllib.request.HTTPSHandler):
    """Stands in for HTTPS: /start redirects to `FakeHTTPS.to`, anything else answers "{}"."""

    to, seen = "", []

    def https_open(self, req):
        FakeHTTPS.seen.append((req.full_url, req.get_header("Authorization")))
        headers = email.message.Message()
        moved = req.full_url.endswith("/start")
        if moved:
            headers["Location"] = FakeHTTPS.to
        response = urllib.response.addinfourl(
            io.BytesIO(b"" if moved else b"{}"), headers, req.full_url, 302 if moved else 200
        )
        response.msg = "Found" if moved else "OK"
        return response


@pytest.fixture
def redirecting(monkeypatch):
    monkeypatch.setattr(urllib.request, "HTTPSHandler", FakeHTTPS)
    FakeHTTPS.seen = []
    return FakeHTTPS


def test_token_is_not_sent_to_another_host_on_redirect(redirecting):
    redirecting.to = "https://elsewhere.test/collect"
    with pytest.raises(releases.ReleaseError, match="refused a redirect"):
        releases.http("https://api.github.test/start", headers={"Authorization": "Bearer t"})
    assert redirecting.seen == [("https://api.github.test/start", "Bearer t")]
    # Without a token the same redirect is followed (release downloads redirect to a CDN).
    assert releases.http("https://api.github.test/start") == b"{}"
    assert redirecting.seen[-1] == ("https://elsewhere.test/collect", None)


def test_token_follows_a_redirect_on_the_same_host(redirecting):
    redirecting.to = "https://api.github.test/moved"
    headers = {"Authorization": "Bearer t"}
    assert releases.http("https://api.github.test/start", headers=headers) == b"{}"
    assert redirecting.seen[-1] == ("https://api.github.test/moved", "Bearer t")


def test_notes_compare_sources_and_top_ten(make_snapshot):
    new = make_snapshot("latest-2026-10-19", "2026-10-19", sources={"x": {"as_of": "2026"}})
    old = make_snapshot("latest-2026-10-11", "2026-10-11", sources={"x": {"as_of": "2025"}})
    text = releases.notes(new, old)
    assert "Compared with `latest-2026-10-11`" in text
    assert "| x | 2026 | 2025 |" in text
    assert "1. " in text and "(was 1)" in text


# --- The server at startup ---------------------------------------------------------------------


@pytest.fixture
def served(monkeypatch, tmp_path, make_snapshot):
    """A server whose store holds the baked-in snapshot latest-2026-10-11."""
    root = tmp_path / "store"
    make_snapshot("latest-2026-10-11", root=root)
    monkeypatch.setenv("DATA_STORE", f"file://{root}")
    monkeypatch.setenv("DATA_RELEASES", "on")
    monkeypatch.setenv("GITHUB_REPOSITORY", REPO)
    monkeypatch.setattr(server, "data", server.DataVersion(FileStore(root), clock=lambda: 0.0))
    monkeypatch.setattr(data_panel, "jobs", data_panel.Jobs())
    return root


def wait_for(job):
    for _ in range(200):
        state = data_panel.jobs.snapshot()[job]
        if state["state"] != "running":
            return state
        time.sleep(0.02)
    raise AssertionError(f"job {job} still running")


def test_startup_switches_to_the_latest_release(monkeypatch, served, release_archive):
    fake_http(monkeypatch, [release("data-2026-10-19")], release_archive)
    with TestClient(server.app) as web:
        assert wait_for("latest")["state"] == "done"
        assert web.get("/health").json()["data_version"] == "latest-2026-10-19"


def test_github_down_keeps_the_baked_in_snapshot(monkeypatch, served, caplog):
    def down(url, **kwargs):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(releases, "http", down)
    with TestClient(server.app) as web:
        assert web.get("/health").json()["data_version"] == "latest-2026-10-11"
        assert wait_for("latest")["state"] == "failed"
        assert web.get("/health").json()["data_version"] == "latest-2026-10-11"
    lines = [r for r in caplog.records if "Data release check failed" in r.getMessage()]
    assert len(lines) == 1


def test_release_check_is_off_with_data_releases_off(monkeypatch, served):
    monkeypatch.setenv("DATA_RELEASES", "off")
    monkeypatch.setattr(releases, "http", lambda url, **kw: pytest.fail("no request expected"))
    with TestClient(server.app) as web:
        assert web.get("/health").json()["data_version"] == "latest-2026-10-11"
    assert data_panel.jobs.snapshot()["latest"]["state"] == "idle"


def test_refresh_workflow_writes_only_in_the_publish_job():
    """A syntax and permissions check of the workflow (actionlint is not a project tool)."""
    path = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "refresh.yml"
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    triggers = workflow[True]  # YAML 1.1 reads the key `on` as true
    assert set(triggers) == {"workflow_dispatch", "schedule"}
    assert workflow["concurrency"]["cancel-in-progress"] is False
    assert workflow["permissions"] == {"contents": "read"}
    assert "permissions" not in workflow["jobs"]["build"]
    publish = workflow["jobs"]["publish"]
    assert publish["permissions"] == {"contents": "write", "actions": "read"}
    assert all("uses" not in step for step in publish["steps"])  # no action holds the write
    assert publish["if"] == (
        "github.ref == format('refs/heads/{0}', github.event.repository.default_branch)"
    )
    for step in workflow["jobs"]["build"]["steps"]:  # every action pinned to a full commit
        if "uses" in step:
            assert re.fullmatch(r"[\w./-]+@[0-9a-f]{40}", step["uses"]), step["uses"]
