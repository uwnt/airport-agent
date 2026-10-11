"""Fetch every source and write one small summary JSON per source into a snapshot folder.

Run through `airport-agent refresh [--as-of YYYY-MM]` (refresh.py), which wraps `build_cache`.

The `write_*` functions turn already-parsed data into a summary file; they don't touch the
network, so tests use them to build a cache from data/samples/. `build_cache` does the fetching:
raw downloads and per-month BTS summaries go to `cache_dir`, the summaries to `out_dir`.
The BTS step downloads about 12 × 32 MB; months already summarised are not downloaded again.
"""

from pathlib import Path

from airport_agent.data import (
    asof,
    bts_enplanements,
    bts_ontime,
    dot_fares,
    opensky,
    ourairports,
)
from airport_agent.data.cache import (
    DEFAULT_CACHE_DIR,
    NETWORK_ERRORS,
    load_config,
    now_utc,
    read_summary,
    write_summary,
)

SAMPLES_DIR = Path("data/samples")
OPENSKY_SAMPLE = "opensky_departures_panc.json"
# Sources whose airport codes must each match an OurAirports airport.
CODE_SOURCES = (dot_fares, bts_ontime, bts_enplanements)


class BuildError(Exception):
    """A step can't finish (for example, BTS can't be reached); the message says why."""


def source_codes(cache_dir):
    """{code: [source names]} for every airport code in the DOT and BTS summaries."""
    codes = {}
    for module in CODE_SOURCES:
        for code in read_summary(cache_dir, module.SUMMARY_NAME)["data"]:
            codes.setdefault(code, []).append(module.SOURCE)
    return codes


def write_airports(cache_dir, airports, countries=None, fetched_at=None):
    """Write the airport list; run after the DOT and BTS summaries, whose codes it checks.

    The manifest lists codes matched by keyword (PBI) and, with a reason, every code that
    matches no airport, so nothing drops out of the ranking unseen. `countries` comes from
    `ourairports.countries_by_iata` and explains codes in US territories.
    """
    fetched_at = fetched_at or now_utc()
    codes = source_codes(cache_dir)
    lookup = ourairports.build_lookup(airports, codes)
    countries = countries or {}
    unresolved = {}
    for code in ourairports.unresolved_codes(codes, lookup):
        where = (
            f"OurAirports lists it in {countries[code]}, not the US"
            if code in countries
            else "no US airport in OurAirports has it as IATA, ICAO or keyword code"
        )
        unresolved[code] = f"in {', '.join(codes[code])}; {where}"
    matched = {
        code: airport["iata"]
        for code, airport in lookup.items()
        if airport["data_code"] == code != airport["iata"]
    }
    return write_summary(
        cache_dir,
        ourairports.SUMMARY_NAME,
        {"airports": airports},
        source=ourairports.SOURCE,
        source_url=ourairports.URL,
        as_of=fetched_at[:10],
        fetched_at=fetched_at,
        matched_by_keyword=matched,
        unresolved_codes=unresolved,
    )


def write_fares(cache_dir, latest_rows, baseline_rows, latest, baseline, config, fetched_at=None):
    """`latest` and `baseline` are (year, quarter); the baseline is the same quarter of 2019.

    When the latest quarter is itself in (or before) the baseline year, growth is meaningless:
    every growth value is None and the manifest's `no_growth_reason` says why.
    """
    edges = config["dot_fares"]["distance_band_edges_miles"]
    extra = {}
    if latest[0] <= baseline[0]:
        baseline_rows = []
        extra["no_growth_reason"] = (
            f"this snapshot is the {baseline[0]} baseline"
            if latest[0] == baseline[0]
            else f"this snapshot is older than the {baseline[0]} baseline"
        )
    summary = dot_fares.summarise(latest_rows, baseline_rows, edges)
    return write_summary(
        cache_dir,
        dot_fares.SUMMARY_NAME,
        summary,
        source=dot_fares.SOURCE,
        source_url=dot_fares.URL,
        as_of=f"{latest[0]} Q{latest[1]}",
        baseline=f"{baseline[0]} Q{baseline[1]}",
        distance_band_edges_miles=edges,
        fetched_at=fetched_at,
        **extra,
    )


def _month_range(months):
    return " to ".join(dict.fromkeys(bts_ontime.month_label(*m) for m in (months[0], months[-1])))


def write_ontime(cache_dir, monthly, fetched_at=None, gaps=None):
    """`monthly` maps (year, month) to that month's per-airport summary.

    `gaps` maps a (year, month) inside the window that has no data to the reason. A gap is
    never filled: the as-of states the whole window and the note says which months are missing.
    """
    gaps = gaps or {}
    months = sorted(monthly)
    window = sorted([*monthly, *gaps])
    extra = {}
    if gaps:
        missing = ", ".join(f"{bts_ontime.month_label(*m)} ({gaps[m]})" for m in sorted(gaps))
        extra["gaps"] = {f"{y}-{m:02d}": reason for (y, m), reason in sorted(gaps.items())}
        extra["note"] = f"{len(months)} of {len(window)} months; missing: {missing}"
    return write_summary(
        cache_dir,
        bts_ontime.SUMMARY_NAME,
        bts_ontime.aggregate([monthly[key] for key in months]),
        source=bts_ontime.SOURCE,
        source_url=bts_ontime.SOURCE_URL,
        as_of=_month_range(window),
        months=[f"{year}-{month:02d}" for year, month in months],
        fetched_at=fetched_at,
        **extra,
    )


def write_enplanements(cache_dir, rows, fetched_at=None):
    year, summary = bts_enplanements.summarise(rows)
    return write_summary(
        cache_dir,
        bts_enplanements.SUMMARY_NAME,
        summary,
        source=bts_enplanements.SOURCE,
        source_url=bts_enplanements.URL,
        as_of=str(year),
        fetched_at=fetched_at,
    )


def write_opensky(cache_dir, flights, coords, config, note=None, fetched_at=None, window=None):
    """`window` is the date range requested ("2026-10-04 to 2026-10-10"); it stays the as-of even
    when no flight came back. Without it, the as-of is the range the flights cover."""
    settings = config["opensky"]
    counts = opensky.long_haul_share(
        flights,
        settings["airport"],
        coords,
        settings["passenger_callsign_prefixes"],
        settings["min_distance_miles"],
        settings["long_haul_miles"],
    )
    extra = {"note": note} if note else {}
    return write_summary(
        cache_dir,
        opensky.SUMMARY_NAME,
        {settings["airport"]: counts},
        source=opensky.SOURCE,
        source_url=opensky.SOURCE_URL,
        as_of=window or opensky.date_range(flights),
        fetched_at=fetched_at,
        **extra,
    )


def write_opensky_unavailable(cache_dir, config, as_of, fetched_at=None):
    """An older snapshot: OpenSky's free history is short, so no long-haul share for that date."""
    return write_summary(
        cache_dir,
        opensky.SUMMARY_NAME,
        {config["opensky"]["airport"]: None},
        source=opensky.SOURCE,
        source_url=opensky.SOURCE_URL,
        as_of=as_of,
        fetched_at=fetched_at,
        note=opensky.NOT_AVAILABLE,
    )


def _log(message):
    print(message, flush=True)


def build_ontime(
    cache_dir,
    config,
    exists=bts_ontime.month_exists,
    fetch=bts_ontime.fetch_month,
    delete_raw=False,
    today=None,
    out_dir=None,
    newest=None,
):
    """Summarise 12 BTS on-time months ending at `newest` (default: the newest BTS serves).

    Network (through `exists`, `fetch`). Month summaries are cached in `cache_dir`; the 12-month
    summary goes to `out_dir` (default `cache_dir`). A month in the window that BTS doesn't serve
    (404) or that fails to download is recorded as a gap, not filled. If BTS can't be reached to
    find the newest month, raises BuildError.
    """
    if newest is None:
        try:
            newest = bts_ontime.latest_available_month(exists, today=today)
        except NETWORK_ERRORS as error:
            raise BuildError(
                f"BTS on-time: can't reach BTS to find the newest month: {error}"
            ) from error
    monthly, gaps = {}, {}
    for year, month in bts_ontime.months_back(*newest, config["bts_ontime"]["months"]):
        summary = bts_ontime.read_month_summary(cache_dir, year, month)
        if summary is None:
            label = bts_ontime.month_label(year, month)
            _log(f"BTS on-time: {label} (download and summarise)")
            try:
                zip_path = fetch(year, month, cache_dir)
            except NETWORK_ERRORS as error:  # HTTPError included: it is a URLError, an OSError
                code = getattr(error, "code", None)
                gaps[(year, month)] = (
                    f"BTS answered HTTP {code}" if code else f"download failed: {error}"
                )
                _log(f"BTS on-time: {label} left out, {gaps[(year, month)]}")
                continue
            summary = bts_ontime.summarise_zip(zip_path)
            bts_ontime.write_month_summary(cache_dir, year, month, summary)
        if delete_raw:
            (cache_dir / bts_ontime.raw_name(year, month)).unlink(missing_ok=True)
        monthly[(year, month)] = summary
    if not monthly:
        raise BuildError(f"BTS on-time: no month in the window could be read: {gaps}")
    return write_ontime(out_dir or cache_dir, monthly, gaps=gaps)


def build_cache(cache_dir=DEFAULT_CACHE_DIR, delete_raw=False, out_dir=None, as_of=None):
    """Fetch every source and write its summary into `out_dir` (default `cache_dir`). Network.

    `as_of` (a date, the end of the --as-of month) keeps to data published by then, by the lags
    in config/sources.yaml `point_in_time`; None means the latest each source has.
    """
    cache_dir = Path(cache_dir)
    out_dir = Path(out_dir or cache_dir)
    config = load_config()
    lags = config["point_in_time"]

    _log("OurAirports: downloading the airport list")
    airports_csv = ourairports.fetch_airports(cache_dir)
    coords = ourairports.parse_coordinates(airports_csv)

    latest = dot_fares.fetch_latest_quarter()
    if as_of:
        latest = min(latest, asof.newest_fare_quarter(as_of, lags["dot_fares_lag_months"]))
    baseline = (config["dot_fares"]["baseline_year"], latest[1])
    _log(f"DOT Table 1a: {latest[0]} Q{latest[1]} and {baseline[0]} Q{baseline[1]}")
    rows = {
        q: dot_fares.load_rows(dot_fares.fetch_quarter(*q, cache_dir)) for q in (latest, baseline)
    }
    write_fares(out_dir, rows[latest], rows[baseline], latest, baseline, config)

    newest = asof.newest_ontime_month(as_of, lags["bts_ontime_lag_days"]) if as_of else None
    build_ontime(cache_dir, config, delete_raw=delete_raw, out_dir=out_dir, newest=newest)

    _log("BTS boardings: downloading the top-50 list")
    rows = dot_fares.load_rows(bts_enplanements.fetch_enplanements(cache_dir))
    if as_of:
        rows = asof.usable_enplanement_rows(rows, as_of, lags["bts_enplanements_lag_years"])
    write_enplanements(out_dir, rows)

    write_airports(
        out_dir,
        ourairports.parse_airports(airports_csv),
        ourairports.countries_by_iata(airports_csv),
    )
    unresolved = read_summary(out_dir, ourairports.SUMMARY_NAME)["manifest"]["unresolved_codes"]
    for code, reason in unresolved.items():
        _log(f"OurAirports: {code} matches no airport ({reason})")

    settings = config["opensky"]
    if as_of:
        _log("OpenSky: not available for this date (free history is short)")
        write_opensky_unavailable(out_dir, config, as_of.isoformat())
        return
    try:
        _log(f"OpenSky: {settings['days']} days of departures from {settings['airport']}")
        paths = opensky.fetch_departures(settings["airport"], settings["days"], cache_dir)
        window = f"{opensky.day_of(paths[0])} to {opensky.day_of(paths[-1])}"
        write_opensky(out_dir, opensky.load_flights(paths), coords, config, window=window)
    except opensky.OpenSkyUnavailable as error:
        _log(f"OpenSky unavailable ({error}); using the committed sample instead")
        flights = opensky.load_flights([SAMPLES_DIR / OPENSKY_SAMPLE])
        note = f"from the committed sample, because OpenSky was unavailable: {error}"
        write_opensky(out_dir, flights, coords, config, note=note)
