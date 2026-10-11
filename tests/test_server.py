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
