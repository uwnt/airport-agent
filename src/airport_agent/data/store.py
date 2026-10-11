"""Where data snapshots live, behind a tiny interface: latest(), get(version), publish(snapshot).

A snapshot is a folder of per-source summary JSONs plus `manifest.json`, whose `version` names it
(`2019-12`, `2021-12`, `latest-2026-10-11`) and whose `as_of` (YYYY-MM-DD) dates it.
`latest()` is the snapshot with the newest `as_of`; on a tie, the one built last.

The environment variable DATA_STORE picks the store. Only `file://<folder>` is built (default
`file://data/snapshots`, relative to the working directory; `file:///data` is absolute).
`s3://` and `github://` are described in the design doc, not built.
"""

import json
import os
import re
import shutil
from pathlib import Path

from airport_agent.data.cache import BUILD_COMMAND, CacheMissingError

DEFAULT_STORE = "file://data/snapshots"
_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _check_version(version):
    if not isinstance(version, str) or not _VERSION.match(version):
        raise ValueError(f"Not a snapshot version: {version!r}")
    return version


def read_manifest(snapshot_dir):
    return json.loads((Path(snapshot_dir) / "manifest.json").read_text(encoding="utf-8"))


class FileStore:
    """Snapshots as sub-folders of one local folder (or network share)."""

    def __init__(self, root):
        self.root = Path(root)

    def __repr__(self):
        return f"file://{self.root}"

    def latest(self):
        """The version with the newest as-of date, or None when the store is empty."""
        manifests = [read_manifest(path.parent) for path in self.root.glob("*/manifest.json")]
        if not manifests:
            return None
        return max(manifests, key=lambda m: (m["as_of"], m.get("built_at", "")))["version"]

    def get(self, version):
        """The local folder holding this version; raises CacheMissingError if it isn't there."""
        path = self.root / _check_version(version)
        if not (path / "manifest.json").exists():
            raise CacheMissingError(f"No data snapshot {version!r} in {self!r}.")
        return path

    def publish(self, snapshot_dir):
        """Copy a built snapshot folder in under its manifest's version; replaces that version.

        Copied under a temporary name and renamed when complete, so readers never see half of it.
        """
        version = _check_version(read_manifest(snapshot_dir)["version"])
        target = self.root / version
        partial, old = self.root / f".{version}.part", self.root / f".{version}.old"
        shutil.rmtree(partial, ignore_errors=True)
        shutil.copytree(snapshot_dir, partial)
        if target.exists():
            target.rename(old)
        partial.rename(target)
        shutil.rmtree(old, ignore_errors=True)
        return version


def open_store(url=None):
    """The store DATA_STORE names (or `url`). Raises ValueError for a scheme that isn't built."""
    url = url or os.environ.get("DATA_STORE") or DEFAULT_STORE
    if url.startswith("file://"):
        return FileStore(url.removeprefix("file://"))
    raise ValueError(
        f"DATA_STORE={url!r}: only file://<folder> is built. "
        "s3:// and github:// are described in the design doc, not built."
    )


def snapshot_dir(version=None, store=None):
    """The folder of `version`, or of the latest snapshot. Raises CacheMissingError if none."""
    store = store or open_store()
    version = version or store.latest()
    if version is None:
        raise CacheMissingError(f"No data snapshot in {store!r}. Build one first: {BUILD_COMMAND}")
    return store.get(version)
