"""Parsing and summarising each source, offline, on data/samples/."""

import http.client
import json
import urllib.error
from datetime import date
from pathlib import Path

import pytest
from conftest import SAMPLES, load_sample_json, ontime_sample_as_month

from airport_agent.data import (
    bts_enplanements,
    bts_ontime,
    build,
    dot_fares,
    faa_nas_status,
    opensky,
    ourairports,
)
from airport_agent.data.cache import load_config
from airport_agent.data.metrics import airport_metrics

AIRPORTS_CSV = SAMPLES / "ourairports_us_scheduled.csv"
BANDS = [500, 1000, 1500]


# --- OurAirports -------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def lookup():
    return ourairports.build_lookup(ourairports.parse_airports(AIRPORTS_CSV))


@pytest.mark.parametrize("code", ["ANC", "PANC", "panc", " anc "])
def test_anchorage_by_either_code(lookup, code):
    airport = ourairports.find_airport(code, lookup)
    assert (airport["iata"], airport["icao"], airport["state"]) == ("ANC", "PANC", "AK")


def test_icao_comes_from_the_data_not_a_k_prefix(lookup):
    assert ourairports.find_airport("KANC", lookup) is None
    assert ourairports.find_airport("SFO", lookup)["icao"] == "KSFO"
    assert ourairports.find_airport("KBOS", lookup)["iata"] == "BOS"


def test_icao_falls_back_to_a_four_letter_gps_code():
    assert ourairports.icao_of({"icao_code": "", "gps_code": "POKA"}) == "POKA"
    assert ourairports.icao_of({"icao_code": "", "gps_code": "4K0"}) is None
    assert ourairports.icao_of({"icao_code": "KSFO", "gps_code": "XXXX"}) == "KSFO"


def test_source_code_found_by_keyword_only_when_needed():
    base = {"state": "FL", "lat": 0.0, "lon": 0.0, "name": "", "municipality": None}
    djt = {**base, "iata": "DJT", "icao": "KDJT", "type": "large_airport", "scheduled": True}
    djt["keywords"] = ["PBI", "MFW"]
    closed_field = {**djt, "iata": "AAA", "icao": "KAAA", "scheduled": False, "keywords": ["QQQ"]}
    airports = [djt, closed_field]

    assert "PBI" not in ourairports.build_lookup(airports)  # only codes the sources use
    lookup = ourairports.build_lookup(airports, {"PBI", "QQQ", "SJU"})
    assert lookup["PBI"] is lookup["DJT"] is lookup["KDJT"]
    assert lookup["PBI"]["data_code"] == "PBI"
    assert "MFW" not in lookup  # keywords the sources don't use are not codes
    assert "QQQ" not in lookup  # only airports with scheduled service are matched
    assert ourairports.unresolved_codes({"PBI", "QQQ", "SJU"}, lookup) == ["QQQ", "SJU"]
    # A real IATA code always wins over a keyword, and DJT itself keeps its own code.
    assert ourairports.build_lookup(airports, {"DJT", "PBI"})["DJT"]["data_code"] == "DJT"


def test_duplicate_iata_prefers_scheduled_then_bigger_airport():
    base = {"state": "XX", "lat": 0.0, "lon": 0.0, "name": "", "municipality": None}
    small = {**base, "iata": "ABC", "icao": "KAAA", "type": "small_airport", "scheduled": True}
    large = {**base, "iata": "ABC", "icao": "KBBB", "type": "large_airport", "scheduled": True}
    unscheduled = {
        **base,
        "iata": "ABC",
        "icao": "KCCC",
        "type": "large_airport",
        "scheduled": False,
    }
    for order in ([small, large, unscheduled], [unscheduled, large, small]):
        assert ourairports.build_lookup(order)["ABC"]["icao"] == "KBBB"


def test_great_circle_anchorage_to_seattle():
    coords = ourairports.parse_coordinates(AIRPORTS_CSV)
    # D13: Seattle is about 1,445 miles from Anchorage, just over the 1,400-mile line.
    assert ourairports.great_circle_miles(coords["PANC"], coords["KSEA"]) == pytest.approx(
        1445, abs=5
    )


# --- DOT Table 1a ------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def fares():
    rows = load_sample_json("dot_fares_new_england.json")
    latest = [row for row in rows if row["year"] == "2026"]
    baseline = [row for row in rows if row["year"] == "2019"]
    return latest, dot_fares.summarise(latest, baseline, BANDS)


def test_growth_compares_the_same_quarter(fares):
    _, summary = fares
    # DATA_SOURCES.md: BOS down 10.2% from Q1 2019 to Q1 2026.
    assert summary["BOS"]["growth_pct"] == -10.2
    assert summary["BOS"]["passengers_per_day"] == pytest.approx(51380.9)
    assert summary["BTV"]["passengers_per_day"] == pytest.approx(253.0)  # DATA_SOURCES.md


def test_fare_ratio_by_hand(fares):
    latest, _ = fares
    frame = dot_fares.add_fare_ratio(dot_fares.to_frame(latest), BANDS)
    btv_dca = frame[(frame["airport_1"] == "BTV") & (frame["airport_2"] == "DCA")].iloc[0]
    # Hand check: BTV-DCA is 441 miles (band 0-500) at $255.36, so 255.36 / 441 = 0.5790 $/mile.
    # The passenger-weighted 0-500 average over this sample's markets is 0.6445 $/mile, so the
    # ratio is 0.5790 / 0.6445 = 0.898: fares about 10% below normal for that distance.
    assert btv_dca["band"] == "0-500"
    assert btv_dca["band_fare_per_mile"] == pytest.approx(0.6445, abs=1e-4)
    assert btv_dca["fare_ratio"] == pytest.approx(0.898, abs=1e-3)


def test_fare_premium_is_passenger_weighted(fares):
    latest, summary = fares
    frame = dot_fares.add_fare_ratio(dot_fares.to_frame(latest), BANDS)
    btv = frame[(frame["airport_1"] == "BTV") | (frame["airport_2"] == "BTV")]
    expected = (btv["fare_ratio"] * btv["passengers"]).sum() / btv["passengers"].sum()
    assert summary["BTV"]["fare_premium"] == pytest.approx(expected, abs=1e-3)
    assert summary["BTV"]["fare_premium"] == pytest.approx(0.923, abs=1e-3)


def test_market_count_and_largest_carrier(fares):
    _, summary = fares
    assert summary["BTV"]["market_count"] == 3
    assert summary["PWM"]["market_count"] == 8  # under D12's 10, so Low confidence later
    assert summary["BTV"]["largest_carrier"] == "AA"
    assert 0 < summary["BOS"]["largest_carrier_share"] <= 1


def test_band_edges_belong_to_the_lower_band():
    rows = [
        {"airport_1": "AAA", "airport_2": "BBB", "nsmiles": "500", "passengers": "1", "fare": "1"},
        {"airport_1": "AAA", "airport_2": "CCC", "nsmiles": "501", "passengers": "1", "fare": "1"},
    ]
    frame = dot_fares.add_fare_ratio(dot_fares.to_frame(rows), BANDS)
    assert list(frame["band"]) == ["0-500", "500-1000"]


def test_airport_missing_from_the_baseline_has_no_growth():
    row = {"airport_1": "AAA", "airport_2": "BBB", "nsmiles": "800", "passengers": "10"}
    latest = [{**row, "fare": "200", "carrier_lg": "XX", "large_ms": "1"}]
    summary = dot_fares.summarise(latest, [], BANDS)
    assert summary["AAA"]["growth_pct"] is None
    assert summary["AAA"]["fare_premium"] == pytest.approx(1.0)


# --- BTS on-time -------------------------------------------------------------------------------


def test_month_summary_and_aggregate_formulas():
    flights = [
        # Dest, Cancelled, Diverted, NASDelay
        ("SFO", 0, 0, 30),
        ("SFO", 0, 0, 0),
        ("SFO", 1, 0, None),
        ("SFO", 0, 1, None),
        ("BOS", 0, 0, 12),
    ]
    month = bts_ontime.summarise_flights(flights)
    assert month["SFO"] == {
        "scheduled": 4,
        "cancelled": 1,
        "diverted": 1,
        "landed": 2,
        "nas_delay_minutes": 30.0,
    }
    total = bts_ontime.aggregate([month, month])["SFO"]
    assert total["months"] == 2
    assert total["nas_delay_per_landed_flight"] == 15.0  # 60 minutes / 4 landed
    assert total["cancellation_rate"] == pytest.approx(
        2 / 6, abs=1e-4
    )  # cancelled / (8 - 2 diverted)


def test_july_sample_matches_data_sources_table():
    totals = bts_ontime.aggregate([ontime_sample_as_month()])
    # DATA_SOURCES.md, July 2026: SFO 15.2 NAS minutes per landed flight, EWR 8.0% cancelled.
    assert totals["SFO"]["nas_delay_per_landed_flight"] == pytest.approx(15.21, abs=0.01)
    assert round(totals["EWR"]["cancellation_rate"], 3) == 0.080
    assert totals["SNA"]["nas_delay_per_landed_flight"] == pytest.approx(2.21, abs=0.01)


def test_diverted_flights_leave_the_cancel_denominator_on_real_ewr_counts():
    # EWR, July 2026, from the built cache (bts_ontime_2026_07.json). DATA_SOURCES.md: D7 moves
    # EWR from 8.0% (802 / 10074 = 0.0796) to 8.2% (802 / (10074 - 239) = 0.0815).
    ewr = {"scheduled": 10074, "cancelled": 802, "diverted": 239, "landed": 9033}
    total = bts_ontime.aggregate([{"EWR": {**ewr, "nas_delay_minutes": 119296.0}}])["EWR"]
    assert total["cancellation_rate"] == 0.0815
    assert round(total["cancellation_rate"], 3) == 0.082 != round(802 / 10074, 3)


def test_latest_twelve_months():
    assert bts_ontime.months_back(2026, 7, 12)[0] == (2025, 8)
    assert bts_ontime.months_back(2026, 7, 12)[-1] == (2026, 7)
    published = {(2026, 7), (2026, 6)}
    newest = bts_ontime.latest_available_month(
        lambda y, m: (y, m) in published, today=date(2026, 10, 11)
    )
    assert newest == (2026, 7)


def _cached_months(cache_dir, months):
    counts = {"scheduled": 10, "cancelled": 1, "diverted": 1, "landed": 8, "nas_delay_minutes": 8}
    for year, month in months:
        bts_ontime.write_month_summary(cache_dir, year, month, {"BOS": counts})


def test_missing_month_in_the_window_is_a_gap_not_filled(tmp_path):
    window = bts_ontime.months_back(2026, 7, 12)
    _cached_months(tmp_path, [m for m in window if m != (2026, 1)])

    def fetch(year, month, cache_dir):  # only the uncached middle month is downloaded
        assert (year, month) == (2026, 1)
        raise urllib.error.HTTPError(bts_ontime.month_url(year, month), 404, "Not Found", {}, None)

    build.build_ontime(
        tmp_path,
        load_config(),
        exists=lambda y, m: (y, m) <= (2026, 7),
        fetch=fetch,
        today=date(2026, 10, 11),
    )
    summary = json.loads((tmp_path / "bts_ontime.json").read_text(encoding="utf-8"))
    manifest = summary["manifest"]
    assert manifest["as_of"] == "Aug 2025 to Jul 2026"  # the whole window, stated
    assert len(manifest["months"]) == 11 and "2026-01" not in manifest["months"]
    assert manifest["gaps"] == {"2026-01": "BTS answered HTTP 404"}
    assert manifest["note"] == "11 of 12 months; missing: Jan 2026 (BTS answered HTTP 404)"
    assert summary["data"]["BOS"]["months"] == 11 and summary["data"]["BOS"]["scheduled"] == 110


def test_dropped_connection_mid_download_is_a_gap(tmp_path):
    # A server hanging up is not a URLError, so it needs its own test (review round 2).
    window = bts_ontime.months_back(2026, 7, 12)
    _cached_months(tmp_path, [m for m in window if m != (2026, 1)])

    def fetch(year, month, cache_dir):
        raise http.client.RemoteDisconnected("Remote end closed connection without response")

    build.build_ontime(
        tmp_path,
        load_config(),
        exists=lambda y, m: (y, m) <= (2026, 7),
        fetch=fetch,
        today=date(2026, 10, 11),
    )
    manifest = json.loads((tmp_path / "bts_ontime.json").read_text(encoding="utf-8"))["manifest"]
    assert manifest["gaps"] == {
        "2026-01": "download failed: Remote end closed connection without response"
    }


@pytest.mark.parametrize(
    "error",
    [
        urllib.error.URLError("timed out"),
        ConnectionResetError("reset by peer"),
        http.client.IncompleteRead(b""),
    ],
)
def test_unreachable_bts_stops_the_build_with_a_reason(tmp_path, error):
    def exists(year, month):
        raise error

    with pytest.raises(build.BuildError, match="can't reach BTS"):
        build.build_ontime(tmp_path, load_config(), exists=exists, today=date(2026, 10, 11))


def test_month_note_reaches_the_metrics(sample_cache):
    gaps = {(2026, 6): "BTS answered HTTP 404"}
    build.write_ontime(sample_cache, {(2026, 7): ontime_sample_as_month()}, gaps=gaps)
    bos = airport_metrics("BOS", sample_cache)
    assert bos.cancellation_rate.as_of == "Jun 2026 to Jul 2026"
    assert "1 of 2 months; missing: Jun 2026" in bos.cancellation_rate.note
    assert "missing: Jun 2026" in bos.nas_delay_per_landed_flight.note


# --- OpenSky -----------------------------------------------------------------------------------


def test_anchorage_long_haul_share_on_the_sample():
    settings = load_config()["opensky"]
    counts = opensky.long_haul_share(
        load_sample_json("opensky_departures_panc.json"),
        "PANC",
        ourairports.parse_coordinates(AIRPORTS_CSV),
        settings["passenger_callsign_prefixes"],
        settings["min_distance_miles"],
        settings["long_haul_miles"],
    )
    assert counts["departures"] == 552
    assert counts["passenger"] == 113
    assert counts["unknown_destination"] == 17  # reported separately, never guessed
    assert counts["same_airport"] == 1
    assert (counts["long_haul"], counts["known_destination"]) == (58, 95)
    assert counts["share"] == pytest.approx(58 / 95, abs=1e-3)


def test_long_haul_rules():
    coords = {"PANC": (61.17, -150.0), "PAFA": (64.8, -147.9), "KSEA": (47.45, -122.31)}
    flights = [
        {"callsign": "ASA1", "estArrivalAirport": "KSEA"},  # ~1,445 miles: long-haul
        {"callsign": "ASA2", "estArrivalAirport": "PAFA"},  # ~260 miles: known, not long-haul
        {"callsign": "ASA3", "estArrivalAirport": "PANC"},  # same airport: dropped
        {"callsign": "ASA4", "estArrivalAirport": None},  # unknown: reported separately
        {"callsign": "ASA5", "estArrivalAirport": "RJAA"},  # no coordinates: reported separately
        {"callsign": "FDX6", "estArrivalAirport": "KSEA"},  # cargo: not counted at all
        {"callsign": "PRIVATE", "estArrivalAirport": "KSEA"},  # private: not counted at all
    ]
    counts = opensky.long_haul_share(flights, "PANC", coords, ["ASA"], 100, 1400)
    assert counts["passenger"] == 5
    assert (counts["long_haul"], counts["known_destination"], counts["share"]) == (1, 2, 0.5)
    assert (counts["same_airport"], counts["unknown_destination"], counts["no_coordinates"]) == (
        1,
        1,
        1,
    )


def test_long_haul_means_strictly_over_the_line():
    coords = {"PANC": (61.17, -150.0), "KSEA": (47.45, -122.31)}
    miles = ourairports.great_circle_miles(coords["PANC"], coords["KSEA"])
    flights = [{"callsign": "ASA1", "estArrivalAirport": "KSEA"}]
    at_the_line = opensky.long_haul_share(flights, "PANC", coords, ["ASA"], 100, miles)
    just_over = opensky.long_haul_share(flights, "PANC", coords, ["ASA"], 100, miles - 1)
    assert (at_the_line["long_haul"], just_over["long_haul"]) == (0, 1)


def test_missing_credentials_raise_unavailable(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENSKY_CLIENT_ID", raising=False)
    monkeypatch.delenv("OPENSKY_CLIENT_SECRET", raising=False)
    with pytest.raises(opensky.OpenSkyUnavailable):
        opensky.fetch_departures("PANC", 1, tmp_path)


def test_private_tail_numbers_are_masked():
    assert opensky.trim({"callsign": "N269TD  "})["callsign"] == "PRIVATE"
    assert opensky.trim({"callsign": "NAC123"})["callsign"] == "NAC123"


# --- BTS boardings and FAA status --------------------------------------------------------------


def test_enplanements_latest_year():
    year, summary = bts_enplanements.summarise(load_sample_json("bts_enplanements_top50.json"))
    assert year == 2023
    assert summary["ATL"] == {"enplanements": 50925180, "rank": 1}
    assert "ANC" not in summary


def test_nas_status_sample():
    status = faa_nas_status.parse_status(Path(SAMPLES / "faa_nas_status.xml").read_bytes())
    assert status["updated"] == "Sun Oct 11 10:55:13 2026 GMT"
    san = faa_nas_status.airport_status(status, "san")
    assert len(san) == 2
    assert san[0]["type"] == "Airport Closures"
    assert san[0]["reopen"] == "Oct 11 at 13:00 UTC."
    assert faa_nas_status.airport_status(status, "BOS") == []
