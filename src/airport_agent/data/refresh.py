"""`airport-agent refresh [--as-of YYYY-MM]`: build a dated data snapshot and publish it.

Wraps the Step 3 build (`build.build_cache`): it writes the per-source summaries into a staging
folder under the cache, adds `manifest.json` (version, as-of date, the point-in-time rule, every
source with its URL, as-of, fetch time, gaps and unresolved codes, and the code's commit), then
publishes the folder to the data store chosen by DATA_STORE (store.py).

- `--as-of 2019-12` -> version `2019-12`: only data published by 31 Dec 2019 (see asof.py).
- no `--as-of` -> version `latest-YYYY-MM-DD` (today): the newest data each source has; a second
  plain refresh on the same day is `latest-YYYY-MM-DD-2`, then `-3`, and so on.

Published snapshots never change (store.py): `--as-of` for a version already in the store is
refused before anything is downloaded.

Raw BTS ZIPs are deleted once their month is summarised (`--keep-raw` keeps them); the small
per-month summaries stay in the cache, so a later refresh does not download those months again.
"""

import shutil
from datetime import date
from pathlib import Path

from airport_agent.data import (
    asof,
    bts_enplanements,
    bts_ontime,
    build,
    dot_fares,
    opensky,
    ourairports,
)
from airport_agent.data.cache import (
    DEFAULT_CACHE_DIR,
    load_config,
    now_utc,
    read_summary,
    write_json,
)
from airport_agent.data.store import open_store

SUMMARIES = (ourairports, dot_fares, bts_ontime, bts_enplanements, opensky)


def rule_text(as_of, lags):
    """The point-in-time rule in words, for the manifest."""
    if as_of is None:
        return "latest: the newest data each source serves on the build date"
    return (
        f"only data published by {as_of.isoformat()}: BTS on-time months that ended at least "
        f"{lags['bts_ontime_lag_days']} days before; DOT Table 1a quarters that ended at least "
        f"{lags['dot_fares_lag_months']} months before (an assumed lag); BTS boardings for years "
        f"up to {as_of.year - lags['bts_enplanements_lag_years']}; OurAirports keeps no history, "
        "so its current file is used; OpenSky only in the latest snapshot"
    )


def write_manifest(folder, version, as_of_date, rule, commit, built_at=None):
    """Write `manifest.json` for the summaries in `folder`; every path in it is relative."""
    sources = {m.SUMMARY_NAME: read_summary(folder, m.SUMMARY_NAME)["manifest"] for m in SUMMARIES}
    sources[ourairports.SUMMARY_NAME]["note"] = "current file: OurAirports keeps no history"
    return write_json(
        Path(folder) / "manifest.json",
        {
            "version": version,
            "as_of": as_of_date.isoformat(),
            "built_at": built_at or now_utc(),
            "commit": commit,
            "point_in_time_rule": rule,
            "files": sorted(f"{m.SUMMARY_NAME}.json" for m in SUMMARIES),
            "sources": sources,
        },
    )


def next_latest_version(store, today):
    """`latest-YYYY-MM-DD` for today, or `-2`, `-3`, ... if that name is taken."""
    version, n = f"latest-{today.isoformat()}", 1
    while store.exists(version if n == 1 else f"{version}-{n}"):
        n += 1
    return version if n == 1 else f"{version}-{n}"


def refresh(as_of=None, cache_dir=DEFAULT_CACHE_DIR, store=None, keep_raw=False, today=None):
    """Build and publish one snapshot; returns its version. Network.

    `as_of` is a "YYYY-MM" string or None (latest).
    """
    from airport_agent.server import current_commit  # the same commit /health reports

    today = today or date.today()
    as_of_date = asof.parse_as_of(as_of) if as_of else None
    if as_of_date and as_of_date.replace(day=1) > today:
        raise ValueError(f"--as-of {as_of} is in the future")
    store = store or open_store()
    version = as_of or next_latest_version(store, today)
    if store.exists(version):
        raise ValueError(
            f"Data snapshot {version!r} is already in {store!r}; published snapshots never change."
        )
    staging = Path(cache_dir) / "staging" / version
    shutil.rmtree(staging, ignore_errors=True)
    build.build_cache(cache_dir, delete_raw=not keep_raw, out_dir=staging, as_of=as_of_date)
    rule = rule_text(as_of_date, load_config()["point_in_time"])
    write_manifest(staging, version, as_of_date or today, rule, current_commit())
    store.publish(staging)
    shutil.rmtree(staging)
    print(f"Published snapshot {version} to {store!r}", flush=True)
    return version
