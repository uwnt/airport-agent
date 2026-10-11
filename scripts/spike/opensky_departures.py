"""Spike: fetch actual departures from one airport (Anchorage) from OpenSky and save a sample.

Needs OPENSKY_CLIENT_ID and OPENSKY_CLIENT_SECRET in the environment.
Run: doppler run -- uv run python scripts/spike/opensky_departures.py
"""

import json
import os
import time
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


def get_token():
    form = urllib.parse.urlencode(
        {
            "grant_type": "client_credentials",
            "client_id": os.environ["OPENSKY_CLIENT_ID"],
            "client_secret": os.environ["OPENSKY_CLIENT_SECRET"],
        }
    ).encode()
    with urllib.request.urlopen(TOKEN_URL, data=form, timeout=30) as response:
        return json.load(response)["access_token"]


# OpenSky processes flights overnight, so ask for whole days that have already ended.
end = int(time.time()) // 86400 * 86400  # midnight UTC today
begin = end - DAYS * 86400
query = urllib.parse.urlencode({"airport": AIRPORT, "begin": begin, "end": end})
request = urllib.request.Request(
    f"{API_URL}?{query}", headers={"Authorization": f"Bearer {get_token()}"}
)
with urllib.request.urlopen(request, timeout=120) as response:
    flights = json.load(response)

destinations = {}
for flight in flights:
    dest = flight.get("estArrivalAirport") or "unknown"
    destinations[dest] = destinations.get(dest, 0) + 1
top = sorted(destinations.items(), key=lambda item: -item[1])[:8]
print(f"{len(flights)} departures from {AIRPORT} in {DAYS} days")
print("Top destinations:", ", ".join(f"{code} {count}" for code, count in top))
OUT.write_text(json.dumps(flights, indent=1))
print(f"Saved to {OUT} ({OUT.stat().st_size // 1024} KB)")
