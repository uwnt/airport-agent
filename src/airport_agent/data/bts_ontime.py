"""BTS On-Time Performance: delay and cancellations on flights arriving at each airport.

Each month is a ~32 MB ZIP with one row per scheduled flight. We reduce a month to a small
per-airport summary (counts and minutes, so months can be added up), cache that, and the raw ZIP
can then be deleted.

Grouped by `Dest`: BTS files delay at the arrival airport, wherever it was caused, so the numbers
mean "delay on flights into X". Over the latest 12 months (decision D7):

    nas_delay_per_landed_flight = NAS delay minutes ÷ landed flights
    cancellation_rate           = cancelled ÷ (scheduled arrivals − diverted)
    landed                      = scheduled arrivals − cancelled − diverted

A diverted flight landed somewhere else, so it is neither "landed at X" nor a cancellation at X:
it is left out of both denominators.
"""

import json
import urllib.error
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd

from airport_agent.data.cache import download, write_json

SOURCE = "BTS On-Time Performance (Reporting Carrier)"
URL_TEMPLATE = (
    "https://transtats.bts.gov/PREZIP/"
    "On_Time_Reporting_Carrier_On_Time_Performance_1987_present_{year}_{month}.zip"
)
SOURCE_URL = "https://transtats.bts.gov/PREZIP/"
SUMMARY_NAME = "bts_ontime"
_COLUMNS = ["Dest", "Cancelled", "Diverted", "NASDelay"]
_MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def month_url(year, month):
    return URL_TEMPLATE.format(year=year, month=month)


def raw_name(year, month):
    return Path(month_url(year, month)).name


def month_summary_name(year, month):
    return f"bts_ontime_{year}_{month:02d}.json"


def months_back(year, month, count):
    """`count` (year, month) pairs ending at the given month, oldest first. Pure."""
    index = year * 12 + month - 1
    return [(i // 12, i % 12 + 1) for i in range(index - count + 1, index + 1)]


def month_label(year, month):
    return f"{_MONTHS[month - 1]} {year}"


def latest_available_month(exists, today=None, look_back=12):
    """The newest (year, month) for which `exists(year, month)` is true, from this month back.

    `exists` does the network check (see `month_exists`); kept separate so this is testable.
    """
    today = today or date.today()
    for year, month in reversed(months_back(today.year, today.month, look_back)):
        if exists(year, month):
            return year, month
    raise LookupError(f"No BTS on-time month found in the {look_back} months before {today}.")


def month_exists(year, month):
    """True if BTS has published this month's ZIP. Network (HEAD request).

    Only a 404 means "not published"; any other error is raised, so an outage can't quietly
    make an older month look like the newest.
    """
    request = urllib.request.Request(month_url(year, month), method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status == 200
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return False
        raise


def fetch_month(year, month, cache_dir):
    """Download one month's ZIP into the cache unless it is already there. Network."""
    target = Path(cache_dir) / raw_name(year, month)
    return target if target.exists() else download(month_url(year, month), target, timeout=600)


def summarise_flights(flights):
    """Per-airport monthly counts from flight rows (Dest, Cancelled, Diverted, NASDelay). Pure.

    Returns {airport: {scheduled, cancelled, diverted, landed, nas_delay_minutes}}.
    """
    frame = pd.DataFrame(flights, columns=_COLUMNS)
    for column in ("Cancelled", "Diverted", "NASDelay"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0)
    grouped = frame.groupby("Dest").agg(
        scheduled=("Dest", "size"),
        cancelled=("Cancelled", "sum"),
        diverted=("Diverted", "sum"),
        nas_delay_minutes=("NASDelay", "sum"),
    )
    summary = {}
    for airport, row in grouped.iterrows():
        scheduled, cancelled, diverted = int(row.scheduled), int(row.cancelled), int(row.diverted)
        summary[str(airport)] = {
            "scheduled": scheduled,
            "cancelled": cancelled,
            "diverted": diverted,
            "landed": scheduled - cancelled - diverted,
            "nas_delay_minutes": float(row.nas_delay_minutes),
        }
    return summary


def summarise_zip(path):
    """Read one month's raw ZIP (only the columns we need) and summarise it. No network."""
    with zipfile.ZipFile(path) as archive:
        csv_name = next(name for name in archive.namelist() if name.endswith(".csv"))
        with archive.open(csv_name) as raw:
            flights = pd.read_csv(raw, usecols=_COLUMNS, dtype={"Dest": str})
    return summarise_flights(flights)


def write_month_summary(cache_dir, year, month, summary):
    return write_json(Path(cache_dir) / month_summary_name(year, month), summary)


def read_month_summary(cache_dir, year, month):
    path = Path(cache_dir) / month_summary_name(year, month)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def aggregate(monthly):
    """Add up monthly summaries and compute the two signals per airport. Pure.

    `monthly` is a list of {airport: counts} from `summarise_flights`. Airports with no landed
    flights get no delay figure; airports with nothing left after diversions get no rate.
    """
    totals = {}
    for month in monthly:
        for airport, counts in month.items():
            total = totals.setdefault(
                airport,
                {"scheduled": 0, "cancelled": 0, "diverted": 0, "landed": 0, "months": 0},
            )
            total.setdefault("nas_delay_minutes", 0.0)
            for key in ("scheduled", "cancelled", "diverted", "landed", "nas_delay_minutes"):
                total[key] += counts[key]
            total["months"] += 1
    for total in totals.values():
        not_diverted = total["scheduled"] - total["diverted"]
        total["nas_delay_minutes"] = round(total["nas_delay_minutes"], 1)
        total["nas_delay_per_landed_flight"] = (
            round(total["nas_delay_minutes"] / total["landed"], 2) if total["landed"] else None
        )
        total["cancellation_rate"] = (
            round(total["cancelled"] / not_diverted, 4) if not_diverted else None
        )
    return totals
