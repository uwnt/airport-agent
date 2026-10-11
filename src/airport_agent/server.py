"""Web server. For now it only answers /health; the chat endpoints arrive in Step 6.

Run: doppler run -- uv run uvicorn airport_agent.server:app --host 127.0.0.1 --port 8100

Data: the server answers from the latest snapshot in the data store (DATA_STORE, see
data/store.py). It looks at startup, then again on use once DATA_CHECK_MINUTES (default 5) have
passed, so a new snapshot from `airport-agent refresh` is picked up without a restart.
"""

import os
import subprocess
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from airport_agent.data.store import open_store, read_manifest


class DataVersion:
    """The snapshot version the app answers from, re-checked every DATA_CHECK_MINUTES.

    `store` and `clock` can be replaced in tests (a fake store, a fake clock: no sleeping).
    """

    def __init__(self, store=None, clock=time.monotonic):
        self.store, self.clock = store, clock
        self.version, self.as_of, self.checked_at = None, None, None

    def current(self):
        """The version in use; asks the store for its latest first if the check is due."""
        minutes = float(os.environ.get("DATA_CHECK_MINUTES", "5"))
        now = self.clock()
        if self.checked_at is None or now - self.checked_at >= minutes * 60:
            self.checked_at = now
            store = self.store or open_store()
            latest = store.latest()
            if latest and latest != self.version:
                self.version, self.as_of = latest, read_manifest(store.get(latest))["as_of"]
        return self.version


data = DataVersion()


@asynccontextmanager
async def lifespan(app):
    data.current()  # load the latest snapshot at startup
    yield


app = FastAPI(title="Airport Investment Intelligence Agent", lifespan=lifespan)


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
    version = data.current()
    return {
        "status": "ok",
        "commit": current_commit(),
        "data_version": version,
        "snapshot_date": data.as_of,
        "model": os.environ.get("GEMINI_MODEL"),
    }
