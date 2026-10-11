"""OpenSky Network: actual departures from Anchorage and the long-haul share (decision D13).

OpenSky needs a free API client. Credentials are read only from the environment variables
OPENSKY_CLIENT_ID and OPENSKY_CLIENT_SECRET (in Doppler); they are never written anywhere.

Long-haul share, counting passenger airlines only (callsign prefixes in config/sources.yaml):

    share = long-haul departures ÷ departures with a known destination

- Same-airport flights and destinations at or under 100 miles are dropped.
- Long-haul = over 1,400 miles great-circle distance, from OurAirports coordinates.
- Flights with no destination, or with a destination we have no coordinates for, are counted and
  reported separately; their distance is never guessed.
"""

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from airport_agent.data.cache import get_json, write_json
from airport_agent.data.ourairports import great_circle_miles

SOURCE = "OpenSky Network (estimated destinations)"
SOURCE_URL = "https://opensky-network.org/api/flights/departure"
TOKEN_URL = (
    "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
)
SUMMARY_NAME = "opensky"
_KEEP = ("callsign", "estDepartureAirport", "estArrivalAirport", "firstSeen", "lastSeen")
# US private tail numbers: N, a digit, then up to four digits or letters (N269TD, N795J).
_PRIVATE = re.compile(r"^N[0-9][0-9A-Z]{0,4}$")


class OpenSkyUnavailable(RuntimeError):
    """OpenSky can't be reached with what we have (no credentials, refused, rate-limited)."""


def trim(flight):
    """Keep only the fields we use; mask US private tail numbers as PRIVATE."""
    row = {key: flight.get(key) for key in _KEEP}
    callsign = (row["callsign"] or "").strip()
    row["callsign"] = "PRIVATE" if _PRIVATE.match(callsign) else callsign
    return row


def _token():
    client_id = os.environ.get("OPENSKY_CLIENT_ID")
    secret = os.environ.get("OPENSKY_CLIENT_SECRET")
    if not client_id or not secret:
        raise OpenSkyUnavailable("OPENSKY_CLIENT_ID / OPENSKY_CLIENT_SECRET are not set.")
    form = urllib.parse.urlencode(
        {"grant_type": "client_credentials", "client_id": client_id, "client_secret": secret}
    ).encode()
    with urllib.request.urlopen(urllib.request.Request(TOKEN_URL, data=form), timeout=60) as r:
        return json.load(r)["access_token"]


def fetch_departures(airport, days, cache_dir, now=None):
    """Download `days` whole UTC days of departures from `airport` (ICAO), one file per day.

    OpenSky processes flights overnight, so only days that have already ended are requested.
    Returns the cached file paths, oldest first. Network; raises OpenSkyUnavailable.
    """
    try:
        headers = {"Authorization": f"Bearer {_token()}"}
        end_of_today = int(now if now is not None else time.time()) // 86400 * 86400
        paths = []
        for back in range(days, 0, -1):
            begin = end_of_today - back * 86400
            day = datetime.fromtimestamp(begin, UTC).date().isoformat()
            target = Path(cache_dir) / f"opensky_{airport.lower()}_{day}.json"
            if not target.exists():
                params = {"airport": airport, "begin": begin, "end": begin + 86400}
                flights = get_json(SOURCE_URL, params, headers=headers, timeout=120)
                write_json(target, [trim(flight) for flight in flights or []])
            paths.append(target)
        return paths
    except urllib.error.HTTPError as error:
        raise OpenSkyUnavailable(f"OpenSky request failed (HTTP {error.code}).") from error
    except urllib.error.URLError as error:
        raise OpenSkyUnavailable(f"OpenSky could not be reached ({error.reason}).") from error


def load_flights(paths):
    flights = []
    for path in paths:
        flights.extend(json.loads(Path(path).read_text(encoding="utf-8")))
    return flights


def date_range(flights):
    """'YYYY-MM-DD to YYYY-MM-DD' (UTC) covered by the flights' first-seen times."""
    seen = [flight["firstSeen"] for flight in flights if flight.get("firstSeen")]
    if not seen:
        return None
    first, last = (
        datetime.fromtimestamp(t, UTC).date().isoformat() for t in (min(seen), max(seen))
    )
    return f"{first} to {last}"


def long_haul_share(flights, airport, coords, prefixes, min_miles, long_haul_miles):
    """Long-haul share of passenger departures from `airport` (ICAO), with every count. Pure.

    `coords` maps airport codes to (lat, lon). Returns a dict of counts and `share` (None when no
    passenger flight has a usable destination).
    """
    prefixes = {prefix.upper() for prefix in prefixes}
    origin = coords.get(airport)
    counts = {
        "departures": len(flights),
        "passenger": 0,
        "unknown_destination": 0,
        "no_coordinates": 0,
        "same_airport": 0,
        "short_hop": 0,
        "known_destination": 0,
        "long_haul": 0,
    }
    for flight in flights:
        callsign = (flight.get("callsign") or "").strip().upper()
        if len(callsign) <= 3 or callsign[:3] not in prefixes:
            continue
        counts["passenger"] += 1
        destination = (flight.get("estArrivalAirport") or "").strip().upper()
        if not destination:
            counts["unknown_destination"] += 1
        elif destination == airport:
            counts["same_airport"] += 1
        elif destination not in coords or origin is None:
            counts["no_coordinates"] += 1
        else:
            miles = great_circle_miles(origin, coords[destination])
            if miles <= min_miles:
                counts["short_hop"] += 1
            else:
                counts["known_destination"] += 1
                counts["long_haul"] += miles > long_haul_miles
    known = counts["known_destination"]
    counts["share"] = round(counts["long_haul"] / known, 3) if known else None
    return counts
