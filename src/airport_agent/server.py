"""Web server. For now it only answers /health; the chat endpoints arrive in Step 6.

Run: doppler run -- uv run uvicorn airport_agent.server:app --host 127.0.0.1 --port 8100
"""

import os
import subprocess
from pathlib import Path

from fastapi import FastAPI

app = FastAPI(title="Airport Investment Intelligence Agent")


def current_commit():
    """The deployed commit (RELEASE_SHA, set at image build), else the local git HEAD."""
    release_sha = os.environ.get("RELEASE_SHA", "").strip()
    if release_sha:
        return release_sha
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
            cwd=Path(__file__).resolve().parent,  # this package's repo, not the caller's directory
        )
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


@app.get("/health")
def health():
    """Says what this running copy is: its code version, data version and model."""
    return {
        "status": "ok",
        "commit": current_commit(),
        "snapshot_date": None,  # filled in once data snapshots exist (#14)
        "model": os.environ.get("GEMINI_MODEL"),
    }
