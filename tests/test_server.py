import json
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from airport_agent import server
from airport_agent.data.metrics import airport_metrics

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
    """A store whose latest version the test sets; counts how often it is asked.

    Each snapshot is a copy of the sample summaries (`sample_cache`) with BOS's fare premium set
    to a number of the test's choosing, so the test can tell which snapshot an answer came from.
    """

    def __init__(self, root, sample_cache):
        self.root, self.sample_cache, self.newest, self.asked = root, sample_cache, None, 0

    def add(self, version, as_of, bos_fare_premium=0.1):
        folder = self.root / version
        shutil.copytree(self.sample_cache, folder)
        fares = json.loads((folder / "dot_fares.json").read_text(encoding="utf-8"))
        fares["data"]["BOS"]["fare_premium"] = bos_fare_premium
        (folder / "dot_fares.json").write_text(json.dumps(fares), encoding="utf-8")
        manifest = {"version": version, "as_of": as_of}
        (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        self.newest = version

    def latest(self):
        self.asked += 1
        return self.newest

    def get(self, version):
        return self.root / version


@pytest.fixture
def store(tmp_path_factory, sample_cache):
    return FakeStore(tmp_path_factory.mktemp("store"), sample_cache)


def answered(data):
    """What the server would answer from right now: (data version, BOS fare premium)."""
    snapshot = data.current()
    return snapshot.version, airport_metrics("BOS", cache=snapshot.cache).fare_premium.value


def test_server_switches_to_a_new_snapshot_after_the_check_interval(monkeypatch, store):
    monkeypatch.setenv("DATA_CHECK_MINUTES", "5")
    now = [1000.0]
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


def test_answers_stay_on_the_loaded_snapshot_until_the_check(monkeypatch, store):
    """The numbers the server answers from and /health's data_version always agree."""
    monkeypatch.setenv("DATA_CHECK_MINUTES", "5")
    now = [1000.0]
    store.add("2021-12", "2021-12-31", bos_fare_premium=0.1)
    data = server.DataVersion(store, clock=lambda: now[0])
    monkeypatch.setattr(server, "data", data)

    with TestClient(server.app) as started:
        assert answered(data) == ("2021-12", 0.1)
        store.add("latest-2026-10-11", "2026-10-11", bos_fare_premium=0.9)
        now[0] += 5 * 60 - 1  # a newer snapshot exists, but the check isn't due
        assert answered(data) == ("2021-12", 0.1)
        assert started.get("/health").json()["data_version"] == "2021-12"
        now[0] += 1
        assert started.get("/health").json()["data_version"] == "latest-2026-10-11"
        assert answered(data) == ("latest-2026-10-11", 0.9)


def test_server_keeps_its_snapshot_when_the_new_one_cannot_load(monkeypatch, store, caplog):
    store.add("2021-12", "2021-12-31")
    data = server.DataVersion(store, clock=lambda: 0.0)
    assert data.current().version == "2021-12"
    store.add("latest-2026-10-11", "2026-10-11")
    (store.get("latest-2026-10-11") / "bts_ontime.json").unlink()
    data.checked_at = -10_000
    assert data.current().version == "2021-12"
    assert "latest-2026-10-11" in caplog.text


def test_server_keeps_its_snapshot_when_the_store_is_empty(store):
    data = server.DataVersion(store, clock=lambda: 0.0)
    assert data.current() is None
    store.add("2019-12", "2019-12-31")
    data.checked_at = -10_000
    assert data.current().version == "2019-12"
    store.newest = None
    data.checked_at = -20_000
    assert data.current().version == "2019-12"


def test_server_keeps_its_snapshot_when_the_store_cannot_be_reached(store, caplog):
    now = [0.0]
    store.add("2021-12", "2021-12-31")
    data = server.DataVersion(store, clock=lambda: now[0])
    assert data.current().version == "2021-12"

    def unreachable():
        raise OSError("share is down")

    store.latest = unreachable
    now[0] += 10 * 60
    assert data.current().version == "2021-12"
    assert "share is down" in caplog.text


def test_unreachable_store_at_startup_gives_no_snapshot(store):
    def unreachable():
        raise OSError("share is down")

    store.latest = unreachable
    assert server.DataVersion(store, clock=lambda: 0.0).current() is None
