from fastapi.testclient import TestClient

from airport_agent.server import app

client = TestClient(app)


def test_health_reports_release_commit(monkeypatch):
    monkeypatch.setenv("RELEASE_SHA", "abc123")
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["commit"] == "abc123"


def test_health_falls_back_to_git_head(monkeypatch):
    monkeypatch.delenv("RELEASE_SHA", raising=False)
    commit = client.get("/health").json()["commit"]
    assert len(commit) == 40  # a full git SHA in a checkout
