"""OurAirports: airport codes, names, states and coordinates.

This is the code lookup between IATA (DOT and BTS use "SFO") and ICAO (OpenSky uses "KSFO").
Alaska ICAO codes start with P (Anchorage is PANC, IATA ANC), so "add a K" would be wrong: the
ICAO code always comes from the data. Some airports have no `icao_code`; then a four-letter
`gps_code` is used, and if there is none the airport has no ICAO code.
"""

import csv
import io
import math
from pathlib import Path

from airport_agent.data.cache import download

SOURCE = "OurAirports"
URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
RAW_NAME = "ourairports_airports.csv"
SUMMARY_NAME = "ourairports"

# When two US rows share an IATA code, prefer scheduled service, then the bigger airport type.
_TYPE_RANK = {"large_airport": 0, "medium_airport": 1, "small_airport": 2}
EARTH_RADIUS_MILES = 3958.8


def fetch_airports(cache_dir):
    """Download the worldwide airport list (about 12 MB) into the cache. Network."""
    return download(URL, Path(cache_dir) / RAW_NAME)


def _read_rows(source):
    """CSV rows from a path or from CSV text."""
    if isinstance(source, Path):
        source = source.read_text(encoding="utf-8")
    return list(csv.DictReader(io.StringIO(source)))


def _four_letter(code):
    code = (code or "").strip().upper()
    return code if len(code) == 4 and code.isalnum() else None


def icao_of(row):
    """ICAO code: `icao_code`, else a four-letter `gps_code`, else None."""
    return _four_letter(row.get("icao_code")) or _four_letter(row.get("gps_code"))


def parse_airports(source):
    """US airports with an IATA code, closed ones left out. Pure.

    `source` is a Path or CSV text, either the full OurAirports file or the trimmed sample (which
    has no country or scheduled-service columns: every row there is a US scheduled airport).
    Returns dicts with iata, icao, name, type, state, municipality, lat, lon, scheduled.
    """
    airports = []
    for row in _read_rows(source):
        if row.get("iso_country", "US") != "US" or not row.get("iata_code"):
            continue
        if row.get("type") == "closed":
            continue
        airports.append(
            {
                "iata": row["iata_code"].strip().upper(),
                "icao": icao_of(row),
                "name": row["name"],
                "type": row["type"],
                "state": row["iso_region"].removeprefix("US-"),
                "municipality": row.get("municipality") or None,
                "lat": float(row["latitude_deg"]),
                "lon": float(row["longitude_deg"]),
                "scheduled": row.get("scheduled_service", "yes") == "yes",
            }
        )
    return airports


def build_lookup(airports):
    """Map every IATA and ICAO code (upper case) to one airport record. Pure and deterministic.

    If two airports share a code, the one with scheduled service wins, then the bigger type
    (large, medium, small, other), then the IATA code alphabetically.
    """

    def preference(airport):
        return (
            not airport["scheduled"],
            _TYPE_RANK.get(airport["type"], 3),
            airport["iata"],
            airport["icao"] or "",
        )

    lookup = {}
    for airport in sorted(airports, key=preference):
        lookup.setdefault(airport["iata"], airport)
        if airport["icao"]:
            lookup.setdefault(airport["icao"], airport)
    return lookup


def find_airport(code, lookup):
    """The airport for an IATA or ICAO code (any case), or None."""
    return lookup.get((code or "").strip().upper())


def parse_coordinates(source):
    """Coordinates of every airport worldwide by code, for distances. Pure.

    Keys are the ICAO code (or four-letter GPS code) and the OurAirports `ident`, which is what
    OpenSky reports as a destination. Returns {code: (lat, lon)}.
    """
    coords = {}
    for row in _read_rows(source):
        point = (float(row["latitude_deg"]), float(row["longitude_deg"]))
        for code in (icao_of(row), (row.get("ident") or "").strip().upper()):
            if code:
                coords.setdefault(code, point)
    return coords


def great_circle_miles(a, b):
    """Great-circle distance in statute miles between two (lat, lon) points (haversine)."""
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(h))
