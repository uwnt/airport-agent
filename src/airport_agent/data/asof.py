"""Point-in-time rule: which months, quarters and years a snapshot dated YYYY-MM may use. Pure.

A snapshot `--as-of 2019-12` uses only data published by the end of December 2019. The publication
lags live in config/sources.yaml (`point_in_time`), each with the evidence or assumption behind it.
"""

import calendar
from datetime import date, timedelta


def month_end(year, month):
    return date(year, month, calendar.monthrange(year, month)[1])


def parse_as_of(text):
    """'2019-12' -> the last day of that month (2019-12-31). Raises ValueError otherwise."""
    try:
        year, month = (int(part) for part in text.split("-"))
        if len(text) != 7:
            raise ValueError
        return month_end(year, month)
    except ValueError:
        raise ValueError(f"--as-of must look like YYYY-MM, got {text!r}") from None


def newest_ontime_month(as_of, lag_days):
    """The newest BTS on-time (year, month) published by `as_of`: its month ended `lag_days` ago."""
    year, month = as_of.year, as_of.month
    while month_end(year, month) + timedelta(days=lag_days) > as_of:
        year, month = (year, month - 1) if month > 1 else (year - 1, 12)
    return year, month


def newest_fare_quarter(as_of, lag_months):
    """The newest DOT Table 1a (year, quarter) whose end is at least `lag_months` before `as_of`.

    Months are counted whole: a quarter ending in June with a 6-month lag is usable from the end of
    December.
    """
    limit = as_of.year * 12 + as_of.month - 1 - lag_months  # month index, January = 0
    end = limit - (limit - 2) % 3  # the last quarter-end month (Mar, Jun, Sep, Dec) not after it
    return end // 12, end % 12 // 3 + 1


def usable_enplanement_rows(rows, as_of, lag_years):
    """BTS boardings rows for years published by `as_of`: up to as-of year − `lag_years`."""
    return [row for row in rows if int(row["year"]) <= as_of.year - lag_years]
