"""Spike: summarise one month of BTS On-Time Performance per arrival airport and save the summary.

The raw month (~32 MB ZIP) is cached in data/cache/ and never committed; only the per-airport
summary goes to data/samples/. Delay causes are recorded on the arriving flight, so we group by
Dest: this is "delay on flights into X", whatever the cause's location. Cancelled flights have no
delay minutes, so delay averages divide by flights that landed; cancellations are a separate rate.
Run: uv run python scripts/spike/bts_ontime.py
"""

import csv
import io
import urllib.request
import zipfile
from pathlib import Path

YEAR, MONTH = 2026, 7
NAME = f"On_Time_Reporting_Carrier_On_Time_Performance_1987_present_{YEAR}_{MONTH}.zip"
URL = f"https://transtats.bts.gov/PREZIP/{NAME}"
CACHE = Path("data/cache") / NAME
OUT = Path(f"data/samples/bts_ontime_by_airport_{YEAR}_{MONTH:02d}.csv")


def number(text):
    return float(text) if text else 0.0


if not CACHE.exists():
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(URL, CACHE)

totals = {}  # airport code -> running sums
with zipfile.ZipFile(CACHE) as archive:
    csv_name = next(name for name in archive.namelist() if name.endswith(".csv"))
    with archive.open(csv_name) as raw:
        for row in csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8")):
            t = totals.setdefault(
                row["Dest"], {"arrivals": 0, "cancelled": 0, "nas_min": 0.0, "weather_min": 0.0}
            )
            t["arrivals"] += 1
            t["cancelled"] += int(number(row["Cancelled"]))
            t["nas_min"] += number(row["NASDelay"])
            t["weather_min"] += number(row["WeatherDelay"])

with OUT.open("w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(
        [
            "airport",
            "arrivals",
            "cancel_rate",
            "nas_delay_min_per_landed",
            "weather_delay_min_per_landed",
        ]
    )
    for code, t in sorted(totals.items(), key=lambda item: -item[1]["arrivals"]):
        landed = t["arrivals"] - t["cancelled"]
        if landed == 0:
            continue
        writer.writerow(
            [
                code,
                t["arrivals"],
                round(t["cancelled"] / t["arrivals"], 3),
                round(t["nas_min"] / landed, 2),
                round(t["weather_min"] / landed, 2),
            ]
        )

print(f"{sum(t['arrivals'] for t in totals.values()):,} flights, {len(totals)} airports")
print(f"Saved to {OUT} ({OUT.stat().st_size // 1024} KB)")
