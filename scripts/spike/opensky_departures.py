"""Spike: fetch actual departures from one airport (Anchorage) from OpenSky and save a sample.

Needs OPENSKY_CLIENT_ID and OPENSKY_CLIENT_SECRET in the environment.
Run: doppler run -- uv run python scripts/spike/opensky_departures.py
"""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

TOKEN_URL = (
    "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
)
API_URL = "https://opensky-network.org/api/flights/departure"
AIRPORT = "PANC"  # OpenSky uses ICAO codes; Anchorage is PANC (Alaska codes start with P)
DAYS = 2
OUT = Path("data/samples/opensky_departures_panc.json")
KEEP = ("callsign", "estDepartureAirport", "estArrivalAirport", "firstSeen", "lastSeen")
# US private tail numbers: N, a digit, then up to four digits or letters (N269TD, N795J).
PRIVATE = re.compile(r"^N[0-9][0-9A-Z]{0,4}$")


def trim(flight):
    """Keep only the fields the project uses; mask private tail numbers (public repo)."""
    row = {key: flight.get(key) for key in KEEP}
    callsign = (row["callsign"] or "").strip()
    row["callsign"] = "PRIVATE" if PRIVATE.match(callsign) else callsign
    return row


def fetch(request):
    """Open the request; exit with a clear message on auth or rate-limit errors."""
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            sys.exit(
                f"OpenSky refused the credentials (HTTP {error.code}). "
                "Check OPENSKY_CLIENT_ID and OPENSKY_CLIENT_SECRET."
            )
        if error.code == 429:
            sys.exit("OpenSky rate limit reached (HTTP 429). Wait and try again later.")
        sys.exit(f"OpenSky request failed (HTTP {error.code}).")


def get_token():
    form = urllib.parse.urlencode(
        {
            "grant_type": "client_credentials",
            "client_id": os.environ["OPENSKY_CLIENT_ID"],
            "client_secret": os.environ["OPENSKY_CLIENT_SECRET"],
        }
    ).encode()
    return fetch(urllib.request.Request(TOKEN_URL, data=form))["access_token"]


# OpenSky processes flights overnight, so ask for whole days that have already ended.
end = int(time.time()) // 86400 * 86400  # midnight UTC today
begin = end - DAYS * 86400
query = urllib.parse.urlencode({"airport": AIRPORT, "begin": begin, "end": end})
request = urllib.request.Request(
    f"{API_URL}?{query}", headers={"Authorization": f"Bearer {get_token()}"}
)
flights = fetch(request)
if not isinstance(flights, list) or not flights:
    sys.exit(f"Unexpected or empty response; {OUT} left unchanged.")
flights = [trim(flight) for flight in flights]

destinations = {}
for flight in flights:
    dest = flight.get("estArrivalAirport") or "unknown"
    destinations[dest] = destinations.get(dest, 0) + 1
top = sorted(destinations.items(), key=lambda item: -item[1])[:8]
print(f"{len(flights)} departures from {AIRPORT} in {DAYS} days")
print("Top destinations:", ", ".join(f"{code} {count}" for code, count in top))
OUT.write_text(json.dumps(flights, indent=1) + "\n")
print(f"Saved to {OUT} ({OUT.stat().st_size // 1024} KB)")
