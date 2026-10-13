"""DOT Consumer Airfare Report, Table 1a: passengers, fares and distance per airport pair.

Each row is one airport pair (a "market") in one quarter, listed once in either direction. An
airport's numbers sum over every row where it is either end of the pair. Table 1a has no Alaska
rows and covers domestic markets only.

Signals (decision D7), all per airport:
- passengers_per_day: sum of `passengers` (already per day) over the airport's markets.
- growth_pct: percent change in that total, latest quarter vs the SAME quarter of 2019 (comparing
  different quarters mixes seasons and gave a false 24% drop for Boston in the spike).
- fare_premium: for each market, fare per mile ÷ the passenger-weighted national fare per mile of
  markets in the same distance band; then the passenger-weighted average of those ratios over the
  airport's markets. 1.0 = normal fares for those distances, 1.2 = 20% above.
- market_count: distinct airport pairs in the latest quarter (decision D12 uses it).
- largest_carrier / largest_carrier_share: shown, not scored (see `summarise`).
"""

import json
import math
from pathlib import Path

import pandas as pd

from airport_agent.data.cache import get_json, write_json

SOURCE = "DOT Consumer Airfare Report, Table 1a"
URL = "https://datahub.transportation.gov/resource/tfrh-tu9e.json"
SUMMARY_NAME = "dot_fares"
_PAGE = 50000
_COLUMNS = ["airport_1", "airport_2", "nsmiles", "passengers", "fare", "carrier_lg", "large_ms"]


def raw_name(year, quarter):
    return f"dot_fares_{year}_q{quarter}.json"


def fetch_latest_quarter():
    """The latest (year, quarter) the dataset has. Network."""
    rows = get_json(
        URL,
        {
            "$select": "year, quarter",
            "$group": "year, quarter",
            "$order": "year DESC, quarter DESC",
            "$limit": 1,
        },
    )
    return int(rows[0]["year"]), int(rows[0]["quarter"])


def fetch_quarter(year, quarter, cache_dir):
    """Download every Table 1a row of one quarter into the cache (paged). Network."""
    rows: list[dict] = []
    while True:
        page = get_json(
            URL,
            {
                "$where": f"year={int(year)} AND quarter={int(quarter)}",
                "$order": "tbl1apk",
                "$limit": _PAGE,
                "$offset": len(rows),
            },
        )
        rows.extend(page)
        if len(page) < _PAGE:
            break
    return write_json(Path(cache_dir) / raw_name(year, quarter), rows)


def load_rows(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def to_frame(rows):
    """Table 1a rows (dicts of strings) as a DataFrame with numeric columns. Pure.

    Rows missing a distance, passenger count or fare are dropped: they can't enter any signal.
    """
    frame = pd.DataFrame(list(rows), columns=_COLUMNS)
    for column in ("nsmiles", "passengers", "fare", "large_ms"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["airport_1", "airport_2", "nsmiles", "passengers", "fare"])
    return frame[(frame["nsmiles"] > 0) & (frame["passengers"] > 0)].reset_index(drop=True)


def band_labels(edges):
    """Readable labels for the distance bands, e.g. [500, 1000] -> 0-500, 500-1000, >1000."""
    lows = [0, *edges]
    return [f"{lo}-{hi}" for lo, hi in zip(lows, edges, strict=False)] + [f">{edges[-1]}"]


def add_fare_ratio(frame, band_edges):
    """Add `band`, `fare_per_mile` and `fare_ratio` (vs the national band average). Pure.

    The national average uses every market in `frame` once, weighted by passengers. A band's
    upper edge belongs to that band (a 500-mile market is in 0-500).
    """
    frame = frame.copy()
    frame["band"] = pd.cut(
        frame["nsmiles"],
        bins=[0, *band_edges, math.inf],
        labels=band_labels(band_edges),
        right=True,
    )
    frame["fare_per_mile"] = frame["fare"] / frame["nsmiles"]
    weighted = (frame["fare_per_mile"] * frame["passengers"]).groupby(
        frame["band"], observed=True
    ).sum() / frame.groupby("band", observed=True)["passengers"].sum()
    frame["band_fare_per_mile"] = frame["band"].map(weighted).astype(float)
    frame["fare_ratio"] = frame["fare_per_mile"] / frame["band_fare_per_mile"]
    return frame


def by_airport(frame):
    """One row per (airport, market): every market listed under both of its airports. Pure."""
    first = frame.assign(airport=frame["airport_1"])
    second = frame.assign(airport=frame["airport_2"])
    return pd.concat([first, second], ignore_index=True)


def summarise(latest_rows, baseline_rows, band_edges):
    """Per-airport signals from the latest quarter's rows and the same quarter of 2019. Pure.

    Returns {iata: {passengers_per_day, baseline_passengers_per_day, growth_pct, fare_premium,
    market_count, largest_carrier, largest_carrier_share}}. growth_pct and the baseline are None
    when the airport has no rows in the baseline quarter.

    Largest carrier: Table 1a names only the largest carrier of each market and its share there.
    For each carrier we add up passengers × its share over the markets it leads, and report the
    carrier with the biggest total and that total ÷ the airport's passengers. It is a lower bound
    of that carrier's real share (its passengers in markets it doesn't lead are not in the table).
    """
    latest = by_airport(add_fare_ratio(to_frame(latest_rows), band_edges))
    baseline = by_airport(to_frame(baseline_rows))
    baseline_pax = baseline.groupby("airport")["passengers"].sum()

    latest["weighted_ratio"] = latest["fare_ratio"] * latest["passengers"]
    latest["carrier_pax"] = latest["passengers"] * latest["large_ms"].fillna(0)
    carriers = latest.groupby(["airport", "carrier_lg"])["carrier_pax"].sum()

    summary = {}
    for airport, markets in latest.groupby("airport"):
        pax = float(markets["passengers"].sum())
        base = float(baseline_pax[airport]) if airport in baseline_pax.index else None
        pairs = {
            frozenset(pair) for pair in zip(markets["airport_1"], markets["airport_2"], strict=True)
        }
        if airport in carriers.index.get_level_values(0):
            leaders = carriers[airport].sort_values(ascending=False, kind="stable")
            leader, leader_pax = str(leaders.index[0]), float(leaders.iloc[0])
        else:
            leader, leader_pax = None, 0.0
        summary[str(airport)] = {
            "passengers_per_day": round(pax, 1),
            "baseline_passengers_per_day": round(base, 1) if base else None,
            "growth_pct": round((pax / base - 1) * 100, 1) if base else None,
            "fare_premium": round(float(markets["weighted_ratio"].sum()) / pax, 3),
            "market_count": len(pairs),
            "largest_carrier": leader,
            "largest_carrier_share": round(leader_pax / pax, 3) if leader else None,
        }
    return summary
