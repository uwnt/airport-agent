"""airport_metrics on a cache built from data/samples/ (see conftest.sample_cache)."""

import pytest
from conftest import FETCHED_AT, SAMPLES

from airport_agent.data import build, faa_capacity, ourairports
from airport_agent.data.cache import CacheMissingError, read_summary
from airport_agent.data.metrics import (
    SIGNALS,
    UnknownAirportError,
    airport_metrics,
    all_airport_metrics,
    load_cache,
)


def test_every_signal_has_a_value_or_a_reason(sample_cache):
    for code in ("BOS", "SFO", "PANC"):
        metrics = airport_metrics(code, sample_cache)
        for name in SIGNALS:
            metric = getattr(metrics, name)
            if metric is None:
                assert metrics.missing[name], f"{code} {name} missing with no reason"
            else:
                assert name not in metrics.missing
                assert metric.source and metric.as_of


def test_boston(sample_cache):
    bos = airport_metrics("KBOS", sample_cache)
    assert (bos.iata, bos.icao, bos.state, bos.in_scope) == ("BOS", "KBOS", "MA", True)
    assert bos.growth_vs_2019.value == -10.2
    assert bos.growth_vs_2019.as_of == "2026 Q1 vs 2019 Q1"
    assert bos.fare_premium.as_of == "2026 Q1"
    assert "DOT" in bos.fare_premium.source
    # Dates are kept per number: on-time is a month range, boardings a year.
    assert bos.nas_delay_per_landed_flight.as_of == "Jul 2026"
    assert bos.nas_delay_per_landed_flight.value == pytest.approx(9.71, abs=0.01)
    assert bos.enplanements.as_of == "2023"
    assert bos.long_haul_share is None
    assert "Anchorage" in bos.missing["long_haul_share"]


def test_sfo(sample_cache):
    sfo = airport_metrics("sfo", sample_cache)
    assert sfo.nas_delay_per_landed_flight.value == pytest.approx(15.21, abs=0.01)
    # The fare sample holds only New England markets, so SFO has just its markets to them.
    assert sfo.fare_premium is not None and sfo.in_scope


def test_bad_weather_capacity_loss_is_shown_for_the_30_airports(sample_cache):
    sfo = airport_metrics("SFO", sample_cache).bad_weather_capacity_loss
    assert sfo.value == pytest.approx(0.324, abs=1e-3)
    assert sfo.as_of == "2014" and faa_capacity.URL in sfo.source
    assert "visual 100–110, instrument 70–72" in sfo.note
    oma = airport_metrics("OMA", sample_cache)  # not one of the 30
    assert oma.bad_weather_capacity_loss is None
    assert "not one of the 30 airports" in oma.missing["bad_weather_capacity_loss"]


def test_airport_missing_from_table_1a(sample_cache):
    oma = airport_metrics("OMA", sample_cache)  # in the on-time sample, not the fare sample
    assert oma.fare_premium is None
    assert oma.missing["fare_premium"] == "not in DOT Table 1a for 2026 Q1"
    assert not oma.in_scope and "no DOT Table 1a rows" in oma.scope_reason
    assert oma.cancellation_rate is not None


def test_anchorage(sample_cache):
    anc = airport_metrics("PANC", sample_cache)
    assert (anc.iata, anc.icao, anc.state) == ("ANC", "PANC", "AK")
    assert not anc.in_scope and "lower-48" in anc.scope_reason
    assert anc.missing["fare_premium"] == "DOT Table 1a has no Alaska rows"
    assert anc.long_haul_share.value == pytest.approx(0.611, abs=1e-3)
    assert anc.long_haul_share.as_of == "2026-10-09 to 2026-10-10"
    assert "17 with no destination" in anc.long_haul_share.note
    assert anc.cancellation_rate is not None  # BTS on-time covers Anchorage


def test_anchorage_without_usable_flights_says_why(sample_cache):
    # Review round 3: Anchorage must not get the "only for Anchorage" reason.
    cache = load_cache(sample_cache)
    cache["opensky"]["data"]["PANC"]["share"] = None
    anc = airport_metrics("PANC", cache=cache)
    assert anc.long_haul_share is None
    assert anc.missing["long_haul_share"].startswith("no passenger departures with a known")


def test_all_airport_metrics_is_the_lower_48_in_table_1a(sample_cache):
    codes = [m.iata for m in all_airport_metrics(sample_cache)]
    assert {"BOS", "BDL", "PVD", "MHT", "PWM", "BTV"} <= set(codes)
    assert "ANC" not in codes
    assert codes == sorted(codes)


def test_unknown_code(sample_cache):
    with pytest.raises(UnknownAirportError, match="not an IATA or ICAO code"):
        airport_metrics("ZZZZ", sample_cache)


def test_unresolved_source_codes_are_reported(sample_cache):
    # The OurAirports sample lists Palm Beach only as DJT (no keywords column) and has no SJU,
    # but the on-time sample has both: the build must say so instead of dropping them.
    manifest = read_summary(sample_cache, ourairports.SUMMARY_NAME)["manifest"]
    assert "PBI" in manifest["unresolved_codes"]
    assert "BTS On-Time" in manifest["unresolved_codes"]["PBI"]
    assert manifest["matched_by_keyword"] == {}
    with pytest.raises(UnknownAirportError, match="no US airport in OurAirports"):
        airport_metrics("PBI", sample_cache)


def test_territory_code_names_its_country(sample_cache):
    airports = ourairports.parse_airports(SAMPLES / "ourairports_us_scheduled.csv")
    build.write_airports(sample_cache, airports, {"SJU": "PR"}, FETCHED_AT)
    with pytest.raises(UnknownAirportError, match="OurAirports lists it in PR, not the US"):
        airport_metrics("sju", sample_cache)


def test_code_matched_by_keyword_is_ranked(sample_cache):
    # Real data: DOT and BTS list Palm Beach as PBI (3 markets in the fare sample); OurAirports
    # has it as DJT with "PBI" in its keywords, which the trimmed sample left out.
    airports = ourairports.parse_airports(SAMPLES / "ourairports_us_scheduled.csv")
    for airport in airports:
        if airport["iata"] == "DJT":
            airport["keywords"] = ["PBI", "MFW"]
    build.write_airports(sample_cache, airports, fetched_at=FETCHED_AT)

    manifest = read_summary(sample_cache, ourairports.SUMMARY_NAME)["manifest"]
    assert manifest["matched_by_keyword"] == {"PBI": "DJT"}
    assert "PBI" not in manifest["unresolved_codes"]
    for code in ("PBI", "pbi", "DJT", "KDJT"):
        pbi = airport_metrics(code, sample_cache)
        assert (pbi.iata, pbi.icao, pbi.state, pbi.in_scope) == ("PBI", "KDJT", "FL", True)
        assert pbi.cancellation_rate is not None and pbi.market_count.value == 3
        assert pbi.code_note == "OurAirports lists this airport as DJT; DOT and BTS use PBI"
    assert "PBI" in [m.iata for m in all_airport_metrics(sample_cache)]


def test_missing_cache_says_how_to_build_it(tmp_path):
    with pytest.raises(CacheMissingError, match="airport-agent refresh"):
        airport_metrics("BOS", tmp_path / "empty")
