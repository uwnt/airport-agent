"""BTS enplanements: passengers boarding at each of the top 50 US airports, per year.

A size number for context only (not scored). The list ends at 2023 and covers the top 50
airports only, so most small airports and Anchorage have no figure.
"""

from pathlib import Path

from airport_agent.data.cache import get_json, write_json

SOURCE = "BTS passenger boardings (top 50 airports)"
URL = "https://data.bts.gov/resource/2ydv-qfge.json"
RAW_NAME = "bts_enplanements.json"
SUMMARY_NAME = "bts_enplanements"


def fetch_enplanements(cache_dir):
    """Download every year of the top-50 list into the cache. Network."""
    rows = get_json(URL, {"$limit": 50000, "$order": "year DESC, rank"})
    return write_json(Path(cache_dir) / RAW_NAME, rows)


def summarise(rows):
    """The latest year's boardings per airport. Pure.

    Returns (year, {airport: {"enplanements": int, "rank": int}}).
    """
    year = max(int(row["year"]) for row in rows)
    latest = {
        row["airport"]: {
            "enplanements": int(float(row["enplaned_passengers"])),
            "rank": int(row["rank"]),
        }
        for row in rows
        if int(row["year"]) == year
    }
    return year, latest
