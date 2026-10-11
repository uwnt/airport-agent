"""Where data snapshots live, behind a tiny interface: latest(), get(version), publish(snapshot).

A snapshot is a folder of per-source summary JSONs plus `manifest.json`, whose `version` names it
(`2019-12`, `2021-12`, `latest-2026-10-11`) and whose `as_of` (YYYY-MM-DD) dates it.
`latest()` is the snapshot with the newest `as_of`; on a tie, the one built last.

The environment variable DATA_STORE picks the store. Only `file://<folder>` is built (default
`file://data/snapshots`, relative to the working directory; `file:///data` is absolute).
`s3://` and `github://` are described in the design doc, not built.
"""

import json
import logging
import os
import re
import shutil
from pathlib import Path

from airport_agent.data.cache import BUILD_COMMAND, CacheMissingError

DEFAULT_STORE = "file://data/snapshots"
log = logging.getLogger(__name__)
_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _check_version(version):
    if not isinstance(version, str) or not _VERSION.match(version):
        raise ValueError(f"Not a snapshot version: {version!r}")
    return version


def read_manifest(snapshot_dir):
    return json.loads((Path(snapshot_dir) / "manifest.json").read_text(encoding="utf-8"))


def snapshot_problem(folder):
    """Why `folder` is not a complete snapshot, in a few words; None when it is one.

    Complete: its name is a version name (so not a hidden `.part`/`.old` folder from `publish`),
    its manifest reads, names that same version, has an as-of date, and every file it lists exists.
    """
    folder = Path(folder)
    if not _VERSION.match(folder.name):
        return "not a snapshot version name"
    try:
        manifest = read_manifest(folder)
    except FileNotFoundError:
        return "no manifest.json"
    except (OSError, ValueError):
        return "manifest.json can't be read"
    if not isinstance(manifest, dict) or manifest.get("version") != folder.name:
        return "manifest.json doesn't name this version"
    if not isinstance(manifest.get("as_of"), str):
        return "manifest.json has no as_of date"
    missing = [name for name in manifest.get("files", []) if not (folder / name).is_file()]
    if missing:
        return f"missing {', '.join(missing)}"
    return None


class FileStore:
    """Snapshots as sub-folders of one local folder (or network share)."""

    def __init__(self, root):
        self.root = Path(root)

    def __repr__(self):
        return f"file://{self.root}"

    def latest(self):
        """The complete snapshot with the newest as-of date, or None when there is none.

        Other folders (a publish in progress or cut short, a broken manifest) are skipped; a
        broken one is logged in one line.
        """
        manifests = []
        folders = sorted(p for p in self.root.iterdir() if p.is_dir()) if self.root.is_dir() else []
        for folder in folders:
            problem = snapshot_problem(folder)
            if problem is None:
                manifests.append(read_manifest(folder))
            elif _VERSION.match(folder.name):
                log.warning("Skipping data snapshot %r in %r: %s", folder.name, self, problem)
        if not manifests:
            return None
        return max(manifests, key=lambda m: (m["as_of"], m.get("built_at", "")))["version"]

    def get(self, version):
        """The local folder holding this version; raises CacheMissingError if it isn't complete."""
        path = self.root / _check_version(version)
        if not path.is_dir():
            raise CacheMissingError(f"No data snapshot {version!r} in {self!r}.")
        problem = snapshot_problem(path)
        if problem:
            raise CacheMissingError(f"Data snapshot {version!r} in {self!r} is broken: {problem}.")
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
