"""CI budget for committed data snapshots: each under 5 MB, and only the three named versions.

Allowed: `2019-12`, `2021-12` and one `latest-YYYY-MM-DD`. Counts files git tracks under
data/snapshots/ (so local, uncommitted refresh output doesn't fail the check).
Run: uv run python scripts/check_snapshots.py      (exit 1 with the reasons if over budget)
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path("data/snapshots")
LIMIT_BYTES = 5 * 1024 * 1024
ALLOWED = re.compile(r"^(2019-12|2021-12|latest-\d{4}-\d{2}-\d{2})$")


def problems(root, files):
    """Reasons the snapshots break the budget (empty if fine). `files` lie under `root`."""
    sizes = {}
    for path in files:
        version = Path(path).relative_to(root).parts[0]
        sizes[version] = sizes.get(version, 0) + Path(path).stat().st_size
    found = []
    for version, size in sorted(sizes.items()):
        if not ALLOWED.match(version):
            found.append(f"{version}: not one of 2019-12, 2021-12, latest-YYYY-MM-DD")
        if size > LIMIT_BYTES:
            found.append(f"{version}: {size / 1e6:.1f} MB, over the 5 MB budget")
    latest = [v for v in sizes if v.startswith("latest-")]
    if len(latest) > 1:
        found.append(f"more than one latest snapshot committed: {', '.join(sorted(latest))}")
    return found


def main():
    listed = subprocess.run(
        ["git", "ls-files", "-z", "--", str(ROOT)], capture_output=True, text=True, check=True
    ).stdout
    found = problems(ROOT, [f for f in listed.split("\0") if f])
    for problem in found:
        print(f"snapshot budget: {problem}", file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
