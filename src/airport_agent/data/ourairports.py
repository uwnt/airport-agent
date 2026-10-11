"""OurAirports: airport codes, names, states and coordinates.

This is the code lookup between IATA (DOT and BTS use "SFO") and ICAO (OpenSky uses "KSFO").
Alaska ICAO codes start with P (Anchorage is PANC, IATA ANC), so "add a K" would be wrong: the
ICAO code always comes from the data. Some airports have no `icao_code`; then a four-letter
`gps_code` is used, and if there is none the airport has no ICAO code.

A code DOT or BTS still uses may no longer be an OurAirports `iata_code`: Palm Beach is PBI in DOT
and BTS but DJT in OurAirports, which keeps "PBI" in the airport's `keywords`. `build_lookup`
matches such a code to the scheduled airport whose keywords contain exactly that code; a code
that still matches nothing is listed by the build in the airports manifest (`unresolved_codes`).
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


def _keyword_codes(row):
    """Three-letter codes in the `keywords` column (other airport codes it is known by)."""
    words = (word.strip().upper() for word in (row.get("keywords") or "").split(","))
    return [word for word in words if len(word) == 3 and word.isalnum()]


def parse_airports(source):
    """US airports with an IATA code, closed ones left out. Pure.

    `source` is a Path or CSV text, either the full OurAirports file or the trimmed sample (which
    has no country or scheduled-service columns: every row there is a US scheduled airport).
    Returns dicts with iata, icao, name, type, state, municipality, lat, lon, scheduled, keywords.
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
                "keywords": _keyword_codes(row),
            }
        )
    return airports


def _preference(airport):
    """Sort key when two airports share a code: scheduled, bigger type, then codes A-Z."""
    return (
        not airport["scheduled"],
        _TYPE_RANK.get(airport["type"], 3),
        airport["iata"],
        airport["icao"] or "",
    )


def build_lookup(airports, source_codes=()):
    """Map every IATA and ICAO code (upper case) to one airport record. Pure and deterministic.

    If two airports share a code, the one with scheduled service wins, then the bigger type
    (large, medium, small, other), then the IATA code alphabetically.

    `source_codes` are the codes DOT and BTS use. One that is no airport's IATA or ICAO code is
    matched to the preferred scheduled airport listing exactly that code in its keywords (PBI).
    Each record gets `data_code`: the code the sources use for it (its IATA code unless matched).
    """
    ordered = [
        {**airport, "data_code": airport["iata"]} for airport in sorted(airports, key=_preference)
    ]
    lookup = {}
    for airport in ordered:
        lookup.setdefault(airport["iata"], airport)
        if airport["icao"]:
            lookup.setdefault(airport["icao"], airport)
    codes = set(source_codes)
    for code in sorted(codes - lookup.keys()):
        match = next((a for a in ordered if a["scheduled"] and code in a.get("keywords", ())), None)
        # One source code per airport: skip one already matched or whose own IATA code is used.
        if match is None or match["data_code"] != match["iata"] or match["iata"] in codes:
            continue
        match["data_code"] = code
        lookup[code] = match
    return lookup


def unresolved_codes(source_codes, lookup):
    """Source codes no airport in the lookup answers to, sorted. Pure."""
    return sorted(set(source_codes) - lookup.keys())


def countries_by_iata(source):
    """{IATA code: country} for airports outside the US, to explain unresolved codes. Pure.

    OurAirports lists US territories under their own country (SJU is PR, GUM is GU).
    """
    return {
        row["iata_code"].strip().upper(): row["iso_country"]
        for row in _read_rows(source)
        if row.get("iata_code") and row.get("iso_country", "US") != "US"
    }


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
