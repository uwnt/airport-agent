"""Spike: download OurAirports and keep only US airports with scheduled passenger service.

This is our code lookup: IATA (DOT uses "SFO") <-> ICAO (OpenSky uses "KSFO"), plus coordinates.
Run: uv run python scripts/spike/ourairports.py
"""

import csv
import io
import urllib.request
from pathlib import Path

URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
OUT = Path("data/samples/ourairports_us_scheduled.csv")
KEEP = [
    "iata_code",
    "icao_code",
    "name",
    "type",
    "iso_region",
    "municipality",
    "latitude_deg",
    "longitude_deg",
]

with urllib.request.urlopen(URL, timeout=120) as response:
    text = response.read().decode("utf-8")

all_rows = list(csv.DictReader(io.StringIO(text)))
us = [
    r
    for r in all_rows
    if r["iso_country"] == "US" and r["scheduled_service"] == "yes" and r["iata_code"]
]
print(f"{len(all_rows)} airports worldwide, {len(us)} US with scheduled service and an IATA code")

with OUT.open("w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=KEEP, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(us)
print(f"Saved to {OUT} ({OUT.stat().st_size // 1024} KB)")
