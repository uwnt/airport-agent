"""Every signal for one airport, each with its source and as-of date, read from a data snapshot.

No network: this reads only the summaries `airport-agent refresh` writes into a snapshot. By default
that is the latest snapshot in the data store (store.py); pass `version` for another one, or
`cache_dir` for a folder of summaries (tests do).
Sources have different dates (a DOT quarter, 12 BTS months, a 2023 boardings figure, a few days
of OpenSky flights), so each number carries its own `as_of`; dates are never merged.

A signal that is missing is None, and `Metrics.missing` says why
(for example "DOT Table 1a has no Alaska rows").
"""

from dataclasses import dataclass, field

from airport_agent.data import (
    bts_enplanements,
    bts_ontime,
    dot_fares,
    faa_capacity,
    opensky,
    ourairports,
)
from airport_agent.data.cache import load_config, read_summary
from airport_agent.data.store import snapshot_dir

SIGNALS = (
    "nas_delay_per_landed_flight",
    "cancellation_rate",
    "fare_premium",
    "growth_vs_2019",
    "passengers_per_day",
    "market_count",
    "largest_carrier",
    "largest_carrier_share",
    "enplanements",
    "long_haul_share",
    "bad_weather_capacity_loss",
)


class UnknownAirportError(LookupError):
    """No airport in the cache answers to this code; the message says why if the build knows."""


@dataclass(frozen=True)
class Metric:
    """One number (or carrier code) with where it came from and how current it is."""

    value: float | int | str
    unit: str
    source: str
    as_of: str
    note: str | None = None


@dataclass(frozen=True)
class Metrics:
    """An airport's identity, scope and signals. A None signal has its reason in `missing`.

    `iata` is the code DOT and BTS use; `code_note` says when OurAirports lists another (PBI).
    """

    iata: str
    icao: str | None
    name: str
    state: str
    in_scope: bool
    scope_reason: str
    nas_delay_per_landed_flight: Metric | None = None
    cancellation_rate: Metric | None = None
    fare_premium: Metric | None = None
    growth_vs_2019: Metric | None = None
    passengers_per_day: Metric | None = None
    market_count: Metric | None = None
    largest_carrier: Metric | None = None
    largest_carrier_share: Metric | None = None
    enplanements: Metric | None = None
    long_haul_share: Metric | None = None
    bad_weather_capacity_loss: Metric | None = None
    missing: dict[str, str] = field(default_factory=dict)
    code_note: str | None = None


def _source(manifest):
    return f"{manifest['source']} ({manifest['source_url']})"


def load_cache(cache_dir=None, version=None):
    """Every source summary, plus the code lookup. Raises CacheMissingError.

    Reads `cache_dir` if given, else snapshot `version` from the store, else the latest snapshot.
    """
    cache_dir = cache_dir or snapshot_dir(version)
    summaries = {
        name: read_summary(cache_dir, name)
        for name in (
            ourairports.SUMMARY_NAME,
            dot_fares.SUMMARY_NAME,
            bts_ontime.SUMMARY_NAME,
            bts_enplanements.SUMMARY_NAME,
            opensky.SUMMARY_NAME,
        )
    }
    airports = summaries[ourairports.SUMMARY_NAME]["data"]["airports"]
    codes = set().union(
        *(summaries[m.SUMMARY_NAME]["data"] for m in (dot_fares, bts_ontime, bts_enplanements))
    )
    summaries["lookup"] = ourairports.build_lookup(airports, codes)
    summaries["config"] = load_config()
    summaries["faa_capacity"] = faa_capacity.load()
    return summaries


def _scope(airport, cache):
    manifest = cache[dot_fares.SUMMARY_NAME]["manifest"]
    if airport["state"] in cache["config"]["scope"]["excluded_states"]:
        return False, f"not ranked: only lower-48 airports are ranked ({airport['state']})"
    if airport["data_code"] not in cache[dot_fares.SUMMARY_NAME]["data"]:
        return False, f"not ranked: no DOT Table 1a rows for {manifest['as_of']}"
    return True, f"ranked: lower 48 and in DOT Table 1a for {manifest['as_of']}"


def _add_dot_fares(airport, iata, cache, signals, missing):
    """DOT Table 1a: fares, growth, volume, markets, largest carrier."""
    fares = cache[dot_fares.SUMMARY_NAME]
    source, as_of = _source(fares["manifest"]), fares["manifest"]["as_of"]
    row = fares["data"].get(iata)
    if row is None:
        reason = (
            "DOT Table 1a has no Alaska rows"
            if airport["state"] == "AK"
            else f"not in DOT Table 1a for {as_of}"
        )
        for name in (
            "fare_premium",
            "growth_vs_2019",
            "passengers_per_day",
            "market_count",
            "largest_carrier",
            "largest_carrier_share",
        ):
            missing[name] = reason
    else:
        baseline = fares["manifest"]["baseline"]
        signals["passengers_per_day"] = Metric(
            row["passengers_per_day"],
            "passengers per day",
            source,
            as_of,
            "sum over the airport's listed markets; domestic only",
        )
        signals["fare_premium"] = Metric(
            row["fare_premium"],
            "ratio to national fare per mile",
            source,
            as_of,
            "1.0 = normal fares for those distances",
        )
        signals["market_count"] = Metric(row["market_count"], "markets", source, as_of)
        if row["growth_pct"] is None:
            missing["growth_vs_2019"] = (
                fares["manifest"].get("no_growth_reason") or f"no DOT Table 1a rows for {baseline}"
            )
        else:
            signals["growth_vs_2019"] = Metric(
                row["growth_pct"],
                "% change in passengers per day",
                source,
                f"{as_of} vs {baseline}",
                f"{row['baseline_passengers_per_day']} per day in {baseline}",
            )
        if row["largest_carrier"] is None:
            missing["largest_carrier"] = missing["largest_carrier_share"] = "no carrier listed"
        else:
            signals["largest_carrier"] = Metric(
                row["largest_carrier"], "carrier code", source, as_of
            )
            signals["largest_carrier_share"] = Metric(
                row["largest_carrier_share"],
                "share of passengers",
                source,
                as_of,
                "lower bound: counts only markets this carrier leads; shown, not scored",
            )


def _add_ontime(airport, iata, cache, signals, missing):
    """BTS on-time: delay and cancellations over 12 months."""
    ontime = cache[bts_ontime.SUMMARY_NAME]
    source, as_of = _source(ontime["manifest"]), ontime["manifest"]["as_of"]
    row = ontime["data"].get(iata)
    if row is None:
        missing["nas_delay_per_landed_flight"] = missing["cancellation_rate"] = (
            f"no BTS on-time arrivals for {as_of}"
        )
    else:
        note = f"{row['landed']} landed of {row['scheduled']} scheduled in {row['months']} months"
        if ontime["manifest"].get("note"):
            note += f"; {ontime['manifest']['note']}"
        if row["nas_delay_per_landed_flight"] is None:
            missing["nas_delay_per_landed_flight"] = "no landed flights"
        else:
            signals["nas_delay_per_landed_flight"] = Metric(
                row["nas_delay_per_landed_flight"],
                "NAS delay minutes per landed flight",
                source,
                as_of,
                note,
            )
        if row["cancellation_rate"] is None:
            missing["cancellation_rate"] = "no flights left after diversions"
        else:
            signals["cancellation_rate"] = Metric(
                row["cancellation_rate"],
                "cancelled ÷ (scheduled − diverted)",
                source,
                as_of,
                f"{row['cancelled']} cancelled, {row['diverted']} diverted"
                + (f"; {ontime['manifest']['note']}" if ontime["manifest"].get("note") else ""),
            )


def _add_boardings(airport, iata, cache, signals, missing):
    """BTS boardings (context size only)."""
    boardings = cache[bts_enplanements.SUMMARY_NAME]
    as_of = boardings["manifest"]["as_of"]
    row = boardings["data"].get(iata)
    if row is None:
        missing["enplanements"] = f"not in the BTS top-50 boardings list for {as_of}"
    else:
        signals["enplanements"] = Metric(
            row["enplanements"],
            "passengers boarded per year",
            _source(boardings["manifest"]),
            as_of,
            f"rank {row['rank']} of the top 50",
        )


def _add_long_haul(airport, iata, cache, signals, missing):
    """OpenSky long-haul share (Anchorage only)."""
    sky = cache[opensky.SUMMARY_NAME]
    icao = airport["icao"] or ""
    row = sky["data"].get(icao)
    if icao not in sky["data"]:
        missing["long_haul_share"] = "computed only for Anchorage (OpenSky)"
    elif row is None:  # an older snapshot: OpenSky has no data for its date
        missing["long_haul_share"] = sky["manifest"]["note"]
    elif row["share"] is None:
        missing["long_haul_share"] = (
            f"no passenger departures with a known destination in {sky['manifest']['as_of']}"
        )
    else:
        signals["long_haul_share"] = Metric(
            row["share"],
            "share of passenger departures",
            _source(sky["manifest"]),
            sky["manifest"]["as_of"],
            f"{row['long_haul']} of {row['known_destination']} with a known destination; "
            f"{row['unknown_destination']} with no destination and {row['no_coordinates']} "
            "with no coordinates not counted"
            + (f"; {sky['manifest']['note']}" if sky["manifest"].get("note") else ""),
        )


def _add_capacity_loss(airport, iata, cache, signals, missing):
    """FAA Table 1 (2014): runway capacity lost in bad weather, 30 airports (shown, not scored)."""
    row = cache["faa_capacity"].get(iata)
    if row is None:
        missing["bad_weather_capacity_loss"] = (
            "not one of the 30 airports in the FAA's 2014 capacity profiles"
        )
    else:
        (v_low, v_high), (i_low, i_high) = row["visual"], row["instrument"]
        signals["bad_weather_capacity_loss"] = Metric(
            row["loss"],
            "share of hourly runway capacity lost in instrument weather vs visual",
            f"{faa_capacity.SOURCE} ({faa_capacity.URL})",
            "2014",
            f"visual {v_low}–{v_high}, instrument {i_low}–{i_high} operations an hour; "
            "runway capacity only, not terminal space; shown, not scored",
        )


def _build(airport, cache):
    signals: dict = {}
    missing: dict = {}
    in_scope, scope_reason = _scope(airport, cache)
    iata = airport["data_code"]  # the code DOT and BTS use for this airport

    _add_dot_fares(airport, iata, cache, signals, missing)
    _add_ontime(airport, iata, cache, signals, missing)
    _add_boardings(airport, iata, cache, signals, missing)
    _add_long_haul(airport, iata, cache, signals, missing)
    _add_capacity_loss(airport, iata, cache, signals, missing)

    return Metrics(
        iata=iata,
        icao=airport["icao"],
        name=airport["name"],
        state=airport["state"],
        in_scope=in_scope,
        scope_reason=scope_reason,
        missing=missing,
        code_note=(
            f"OurAirports lists this airport as {airport['iata']}; DOT and BTS use {iata}"
            if iata != airport["iata"]
            else None
        ),
        **signals,
    )


def airport_metrics(code, cache_dir=None, cache=None, version=None):
    """Every signal for one airport, by IATA or ICAO code ("BOS", "KBOS", "PANC", "anc").

    Reads only the snapshot (see `load_cache` for which one). Raises CacheMissingError if it
    hasn't been built, UnknownAirportError for an unknown code. Pass `cache` (from `load_cache`)
    to avoid re-reading it for many airports.
    """
    cache = cache or load_cache(cache_dir, version)
    airport = ourairports.find_airport(code, cache["lookup"])
    if airport is None:
        key = (code or "").strip().upper()
        unresolved = cache[ourairports.SUMMARY_NAME]["manifest"].get("unresolved_codes", {})
        reason = unresolved.get(key, "not an IATA or ICAO code of a US airport in OurAirports")
        raise UnknownAirportError(f"No airport for code {code!r}: {reason}")
    return _build(airport, cache)


def all_airport_metrics(cache_dir=None, version=None):
    """Metrics for every airport in scope, sorted by IATA code; scoring ranks them all.

    A DOT code with no OurAirports airport can't be placed in a state, so it is left out here;
    the build lists every such code with its reason in the airports manifest (`unresolved_codes`).
    """
    cache = load_cache(cache_dir, version)
    result = []
    for code in sorted(cache[dot_fares.SUMMARY_NAME]["data"]):
        airport = ourairports.find_airport(code, cache["lookup"])
        if airport is not None:
            metrics = _build(airport, cache)
            if metrics.in_scope:
                result.append(metrics)
    return result
