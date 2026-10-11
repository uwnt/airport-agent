"""airport_metrics on a cache built from data/samples/ (see conftest.sample_cache)."""

import pytest

from airport_agent.data.cache import CacheMissingError
from airport_agent.data.metrics import SIGNALS, airport_metrics, all_airport_metrics


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


def test_all_airport_metrics_is_the_lower_48_in_table_1a(sample_cache):
    codes = [m.iata for m in all_airport_metrics(sample_cache)]
    assert {"BOS", "BDL", "PVD", "MHT", "PWM", "BTV"} <= set(codes)
    assert "ANC" not in codes
    assert codes == sorted(codes)


def test_unknown_code(sample_cache):
    with pytest.raises(KeyError):
        airport_metrics("ZZZZ", sample_cache)


def test_missing_cache_says_how_to_build_it(tmp_path):
    with pytest.raises(CacheMissingError, match="python -m airport_agent.data"):
        airport_metrics("BOS", tmp_path / "empty")
