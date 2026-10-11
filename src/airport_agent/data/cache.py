"""Shared helpers for the data layer: settings, downloads and the small per-source summary files.

Every source writes one summary JSON into the cache directory (default `data/cache/`):

    {"manifest": {"source": ..., "source_url": ..., "as_of": ..., "fetched_at": ..., ...},
     "data": {...}}

The manifest says where the numbers came from and how current they are; `data` holds the numbers.
Raw downloads sit next to the summaries and can be deleted once the summaries exist.
"""

import json
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import yaml

DEFAULT_CACHE_DIR = Path("data/cache")
_REPO_CONFIG = Path(__file__).resolve().parents[3] / "config" / "sources.yaml"
CONFIG_PATH = _REPO_CONFIG if _REPO_CONFIG.exists() else Path("config/sources.yaml")
BUILD_COMMAND = "doppler run -- uv run python -m airport_agent.data"


class CacheMissingError(FileNotFoundError):
    """A summary the caller needs has not been built yet."""


def load_config(path=CONFIG_PATH):
    """Read config/sources.yaml (distance bands, thresholds, airline prefixes)."""
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def now_utc():
    """The current time as an ISO 8601 string in UTC, to the second."""
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def get_json(url, params=None, headers=None, timeout=120):
    """GET a URL (with optional query parameters) and decode the JSON answer."""
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def download(url, target, timeout=300):
    """Download `url` to `target`, through a temporary name renamed only when complete.

    A dropped download then can't leave a truncated file that later runs would trust.
    """
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    with urllib.request.urlopen(url, timeout=timeout) as response, open(partial, "wb") as out:
        while chunk := response.read(1 << 20):
            out.write(chunk)
    partial.replace(target)
    return target


def write_json(path, payload):
    """Write JSON through a temporary name, so readers never see a half-written file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".part")
    partial.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    partial.replace(path)
    return path


def write_summary(cache_dir, name, data, *, source, source_url, as_of, fetched_at=None, **extra):
    """Write one source's summary as `<cache_dir>/<name>.json` with its manifest."""
    manifest = {
        "source": source,
        "source_url": source_url,
        "as_of": as_of,
        "fetched_at": fetched_at or now_utc(),
        **extra,
    }
    return write_json(Path(cache_dir) / f"{name}.json", {"manifest": manifest, "data": data})


def read_summary(cache_dir, name):
    """Read `<cache_dir>/<name>.json`; raise CacheMissingError with the build command if absent."""
    path = Path(cache_dir) / f"{name}.json"
    if not path.exists():
        raise CacheMissingError(
            f"The data cache has no '{name}' summary ({path}). Build the cache first: "
            f"{BUILD_COMMAND}"
        )
    return json.loads(path.read_text(encoding="utf-8"))
