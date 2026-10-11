"""Build the data cache: fetch every source and write one small summary JSON per source.

Run: doppler run -- uv run python -m airport_agent.data [--cache-dir data/cache] [--delete-raw]

The `write_*` functions turn already-parsed data into a summary file; they don't touch the
network, so tests use them to build a cache from data/samples/. `build_cache` does the fetching.
The BTS step downloads about 12 × 32 MB; months already summarised are not downloaded again.
"""

import argparse
import sys
from pathlib import Path

from airport_agent.data import (
    bts_enplanements,
    bts_ontime,
    dot_fares,
    opensky,
    ourairports,
)
from airport_agent.data.cache import (
    DEFAULT_CACHE_DIR,
    load_config,
    now_utc,
    read_summary,
    write_summary,
)

SAMPLES_DIR = Path("data/samples")
OPENSKY_SAMPLE = "opensky_departures_panc.json"


# Sources whose airport codes must each match an OurAirports airport.
CODE_SOURCES = (dot_fares, bts_ontime, bts_enplanements)


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
    """`latest` and `baseline` are (year, quarter); the baseline is the same quarter of 2019."""
    edges = config["dot_fares"]["distance_band_edges_miles"]
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
    )


def write_ontime(cache_dir, monthly, fetched_at=None):
    """`monthly` maps (year, month) to that month's per-airport summary."""
    months = sorted(monthly)
    return write_summary(
        cache_dir,
        bts_ontime.SUMMARY_NAME,
        bts_ontime.aggregate([monthly[key] for key in months]),
        source=bts_ontime.SOURCE,
        source_url=bts_ontime.SOURCE_URL,
        as_of=" to ".join(
            dict.fromkeys(bts_ontime.month_label(*m) for m in (months[0], months[-1]))
        ),
        months=[f"{year}-{month:02d}" for year, month in months],
        fetched_at=fetched_at,
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


def write_opensky(cache_dir, flights, coords, config, note=None, fetched_at=None):
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
        as_of=opensky.date_range(flights) or "no flights",
        fetched_at=fetched_at,
        **extra,
    )


def _log(message):
    print(message, flush=True)


def build_cache(cache_dir=DEFAULT_CACHE_DIR, delete_raw=False):
    """Fetch every source and write its summary into `cache_dir`. Network."""
    cache_dir = Path(cache_dir)
    config = load_config()

    _log("OurAirports: downloading the airport list")
    airports_csv = ourairports.fetch_airports(cache_dir)
    coords = ourairports.parse_coordinates(airports_csv)

    latest = dot_fares.fetch_latest_quarter()
    baseline = (config["dot_fares"]["baseline_year"], latest[1])
    _log(f"DOT Table 1a: {latest[0]} Q{latest[1]} and {baseline[0]} Q{baseline[1]}")
    rows = {
        q: dot_fares.load_rows(dot_fares.fetch_quarter(*q, cache_dir)) for q in (latest, baseline)
    }
    write_fares(cache_dir, rows[latest], rows[baseline], latest, baseline, config)

    newest = bts_ontime.latest_available_month(bts_ontime.month_exists)
    monthly = {}
    for year, month in bts_ontime.months_back(*newest, config["bts_ontime"]["months"]):
        summary = bts_ontime.read_month_summary(cache_dir, year, month)
        if summary is None:
            _log(f"BTS on-time: {bts_ontime.month_label(year, month)} (download and summarise)")
            zip_path = bts_ontime.fetch_month(year, month, cache_dir)
            summary = bts_ontime.summarise_zip(zip_path)
            bts_ontime.write_month_summary(cache_dir, year, month, summary)
        if delete_raw:
            (cache_dir / bts_ontime.raw_name(year, month)).unlink(missing_ok=True)
        monthly[(year, month)] = summary
    write_ontime(cache_dir, monthly)

    _log("BTS boardings: downloading the top-50 list")
    raw = bts_enplanements.fetch_enplanements(cache_dir)
    write_enplanements(cache_dir, dot_fares.load_rows(raw))

    write_airports(
        cache_dir,
        ourairports.parse_airports(airports_csv),
        ourairports.countries_by_iata(airports_csv),
    )
    unresolved = read_summary(cache_dir, ourairports.SUMMARY_NAME)["manifest"]["unresolved_codes"]
    for code, reason in unresolved.items():
        _log(f"OurAirports: {code} matches no airport ({reason})")

    settings = config["opensky"]
    try:
        _log(f"OpenSky: {settings['days']} days of departures from {settings['airport']}")
        paths = opensky.fetch_departures(settings["airport"], settings["days"], cache_dir)
        write_opensky(cache_dir, opensky.load_flights(paths), coords, config)
    except opensky.OpenSkyUnavailable as error:
        _log(f"OpenSky unavailable ({error}); using the committed sample instead")
        flights = opensky.load_flights([SAMPLES_DIR / OPENSKY_SAMPLE])
        note = f"from the committed sample, because OpenSky was unavailable: {error}"
        write_opensky(cache_dir, flights, coords, config, note=note)
    _log(f"Done: summaries in {cache_dir}")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m airport_agent.data", description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument(
        "--delete-raw", action="store_true", help="delete each BTS ZIP once it is summarised"
    )
    args = parser.parse_args(argv)
    build_cache(args.cache_dir, delete_raw=args.delete_raw)
    return 0


if __name__ == "__main__":
    sys.exit(main())
