"""Spike: fetch DOT Airfare Report (Table 1a) rows for New England airports and save a sample.

Each row is one airport pair in one quarter: passengers per day, average fare, distance.
Run: uv run python scripts/spike/dot_fares.py
"""

import json
import urllib.parse
import urllib.request
from pathlib import Path

URL = "https://datahub.transportation.gov/resource/tfrh-tu9e.json"
AIRPORTS = ["BOS", "BDL", "PVD", "MHT", "PWM", "BTV"]  # New England, question 1
QUARTERS = [(2019, 1), (2026, 1)]  # same season: pre-pandemic Q1 vs the latest Q1
OUT = Path("data/samples/dot_fares_new_england.json")


def fetch(year, quarter):
    codes = ", ".join(f"'{code}'" for code in AIRPORTS)
    where = (
        f"(airport_1 in ({codes}) OR airport_2 in ({codes})) AND year={year} AND quarter={quarter}"
    )
    query = urllib.parse.urlencode({"$where": where, "$limit": 5000})
    with urllib.request.urlopen(f"{URL}?{query}", timeout=60) as response:
        return json.load(response)


rows = []
for year, quarter in QUARTERS:
    batch = fetch(year, quarter)
    print(f"{year} Q{quarter}: {len(batch)} airport pairs")
    rows.extend(batch)

OUT.write_text(json.dumps(rows, indent=1))
print(f"Saved {len(rows)} rows to {OUT} ({OUT.stat().st_size // 1024} KB)")
