"""Web server. For now it only answers /health; the chat endpoints arrive in Step 6.

Run: doppler run -- uv run uvicorn airport_agent.server:app --host 127.0.0.1 --port 8100

Data: the server answers from one snapshot of the data store (DATA_STORE, see data/store.py),
read fully into memory: the latest at startup. On use, once DATA_CHECK_MINUTES (default 5) have
passed, it asks the store for its latest again and, if that is a new one, loads it and switches to
it in one step, so a new snapshot from `airport-agent refresh` is picked up without a restart.
/health reports the version of that same loaded snapshot.
"""

import logging
import os
import subprocess
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI

from airport_agent.data.metrics import load_cache
from airport_agent.data.store import open_store, read_manifest

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Snapshot:
    """One data snapshot, fully loaded: its version, its as-of date and every summary (`cache`).

    Answers pass `cache` to the metrics functions (`airport_metrics(code, cache=...)`), so they
    never read the store themselves.
    """

    version: str
    as_of: str
    cache: dict


class DataVersion:
    """The snapshot the server answers from, re-checked every DATA_CHECK_MINUTES.

    `store` and `clock` can be replaced in tests (a fake store, a fake clock: no sleeping).
    """

    def __init__(self, store=None, clock=time.monotonic):
        self.store, self.clock = store, clock
        self.snapshot, self.checked_at = None, None
        self.minutes = 5.0
        text = os.environ.get("DATA_CHECK_MINUTES", "5")
        try:
            minutes = float(text)
            if not minutes >= 0:
                raise ValueError("must not be negative")
            self.minutes = minutes
        except ValueError:
            log.warning("DATA_CHECK_MINUTES=%r is not a number of minutes, using 5", text)

    def current(self):
        """The Snapshot in use (None while the store has none); checks the store first if due.

        A newer snapshot is loaded completely before it replaces the one in use, in a single
        assignment: a caller gets the old snapshot or the new one, never a mix. If it can't be
        loaded, the old one stays in use and the next check tries again.
        """
        now = self.clock()
        if self.checked_at is None or now - self.checked_at >= self.minutes * 60:
            self.checked_at = now
            store = self.store or open_store()
            try:
                latest = store.latest()
            except OSError as error:
                log.warning("Can't reach the data store, keeping the snapshot in use: %s", error)
                return self.snapshot
            if latest and (self.snapshot is None or latest != self.snapshot.version):
                try:
                    folder = store.get(latest)
                    loaded = Snapshot(latest, read_manifest(folder)["as_of"], load_cache(folder))
                except (OSError, ValueError, KeyError) as error:
                    log.warning(
                        "Can't load data snapshot %r, keeping the one in use: %s", latest, error
                    )
                else:
                    self.snapshot = loaded
        return self.snapshot


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
    snapshot = data.current()
    return {
        "status": "ok",
        "commit": current_commit(),
        "data_version": snapshot.version if snapshot else None,
        "snapshot_date": snapshot.as_of if snapshot else None,
        "model": os.environ.get("GEMINI_MODEL"),
    }
