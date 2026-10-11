"""Spike: fetch BTS yearly boarded passengers (top 50 US airports) and save a sample.

Run: uv run python scripts/spike/bts_enplanements.py
"""

import json
import urllib.parse
import urllib.request
from pathlib import Path

URL = "https://data.bts.gov/resource/2ydv-qfge.json"
OUT = Path("data/samples/bts_enplanements_top50.json")

query = urllib.parse.urlencode({"$limit": 5000, "$order": "year DESC, rank"})
with urllib.request.urlopen(f"{URL}?{query}", timeout=60) as response:
    rows = json.load(response)

years = sorted({row["year"] for row in rows})
print(f"{len(rows)} rows, years {years[0]}-{years[-1]}")
OUT.write_text(json.dumps(rows, indent=1))
print(f"Saved to {OUT} ({OUT.stat().st_size // 1024} KB)")
