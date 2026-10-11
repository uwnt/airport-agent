import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from airport_agent import server

client = TestClient(server.app)
SHA = "0123456789abcdef0123456789abcdef01234567"


def test_health_reports_release_commit(monkeypatch):
    monkeypatch.setenv("RELEASE_SHA", "abc123")
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["commit"] == "abc123"


@pytest.mark.parametrize("value", ["", "   "])
def test_blank_release_sha_is_treated_as_unset(monkeypatch, value):
    monkeypatch.setenv("RELEASE_SHA", value)
    monkeypatch.setattr(
        server.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, stdout=SHA + "\n"),
    )
    assert client.get("/health").json()["commit"] == SHA


def test_health_falls_back_to_git_head(monkeypatch):
    monkeypatch.delenv("RELEASE_SHA", raising=False)
    calls = []

    def fake_run(*args, **kwargs):
        calls.append(kwargs)
        return subprocess.CompletedProcess(args, 0, stdout=SHA + "\n")

    monkeypatch.setattr(server.subprocess, "run", fake_run)
    assert client.get("/health").json()["commit"] == SHA
    assert calls[0]["cwd"] == Path(server.__file__).resolve().parent


@pytest.mark.parametrize(
    "error",
    [
        FileNotFoundError("git"),
        subprocess.CalledProcessError(128, "git"),
        subprocess.TimeoutExpired("git", 5),
    ],
)
def test_health_reports_unknown_when_git_fails(monkeypatch, error):
    monkeypatch.delenv("RELEASE_SHA", raising=False)

    def fake_run(*args, **kwargs):
        raise error

    monkeypatch.setattr(server.subprocess, "run", fake_run)
    assert client.get("/health").json()["commit"] == "unknown"


class FakeStore:
    """A store whose latest version the test sets; counts how often it is asked."""

    def __init__(self, tmp_path):
        self.tmp_path, self.newest, self.asked = tmp_path, None, 0

    def add(self, version, as_of):
        folder = self.tmp_path / version
        folder.mkdir()
        (folder / "manifest.json").write_text(f'{{"as_of": "{as_of}"}}', encoding="utf-8")
        self.newest = version

    def latest(self):
        self.asked += 1
        return self.newest

    def get(self, version):
        return self.tmp_path / version


def test_server_switches_to_a_new_snapshot_after_the_check_interval(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_CHECK_MINUTES", "5")
    now = [1000.0]
    store = FakeStore(tmp_path)
    store.add("2021-12", "2021-12-31")
    data = server.DataVersion(store, clock=lambda: now[0])
    monkeypatch.setattr(server, "data", data)

    with TestClient(server.app) as started:  # startup loads the latest
        assert store.asked == 1
        assert started.get("/health").json()["data_version"] == "2021-12"
        store.add("latest-2026-10-11", "2026-10-11")
        now[0] += 5 * 60 - 1  # not due yet: keeps the version in use, doesn't ask the store
        assert started.get("/health").json()["data_version"] == "2021-12"
        assert store.asked == 1
        now[0] += 1  # five minutes since the last check
        body = started.get("/health").json()
    assert (body["data_version"], body["snapshot_date"]) == ("latest-2026-10-11", "2026-10-11")
    assert store.asked == 2


def test_server_keeps_its_snapshot_when_the_store_is_empty(monkeypatch, tmp_path):
    store = FakeStore(tmp_path)
    data = server.DataVersion(store, clock=lambda: 0.0)
    assert data.current() is None
    store.add("2019-12", "2019-12-31")
    data.checked_at = -10_000
    assert data.current() == "2019-12"
    store.newest = None
    data.checked_at = -20_000
    assert data.current() == "2019-12"
