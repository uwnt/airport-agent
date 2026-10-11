"""The agent's tools on a cache built from data/samples/ (New England fares, Anchorage flights)."""

import json
import re

import pytest

from airport_agent import tools
from airport_agent.tools import run_tool


@pytest.fixture
def run(sample_cache):
    def call(name, **args):
        result = run_tool(name, args, cache_dir=sample_cache)
        json.dumps(result)  # every result must be JSON-able
        return result

    return call


def has_source_and_date(signal):
    return signal["source"].strip() and signal["as_of"].strip()


def test_rank_region_rows_have_points_percentiles_sources_and_dates(run):
    result = run("rank_airports", region="New England")
    assert result["preset"] == "balanced"
    assert result["weights_pct"] == {
        "delay": 25.0,
        "cancellations": 12.5,
        "fare premium": 12.5,
        "growth": 50.0,
    }
    assert [r["rank"] for r in result["rows"]] == list(range(1, len(result["rows"]) + 1))
    assert {"BOS", "BDL"} <= {r["code"] for r in result["rows"]}
    for row in result["rows"]:
        assert 0 <= row["score"] <= 100
        assert row["national_rank"] >= row["rank"]
        assert row["confidence"] in ("High", "Low")
        for signal in row["signals"].values():
            if "missing" not in signal:
                assert {"points", "percentile", "weight_pct", "value", "unit"} <= set(signal)
                assert has_source_and_date(signal)


def test_rank_shares_also_come_as_percentages(run):
    bos = next(r for r in run("rank_airports", region="New England")["rows"] if r["code"] == "BOS")
    cancel = bos["signals"]["cancellations"]
    assert cancel["value_pct"] == round(cancel["value"] * 100, 1)


def test_rank_top_and_preset(run):
    result = run("rank_airports", region="New England", preset="growth-focused", top=2)
    assert len(result["rows"]) == 2
    assert result["weights_pct"]["growth"] == 70.0
    assert result["note"].startswith("showing the top 2")


def test_compare_lists_airports_outside_the_ranked_scope_with_the_reason(run):
    result = run("compare_airports", codes=["BOS", "BDL", "PANC"])
    assert [r["code"] for r in result["rows"]] == sorted(
        ["BOS", "BDL"], key=lambda c: next(r["rank"] for r in result["rows"] if r["code"] == c)
    )
    assert result["not_ranked"][0]["code"] == "ANC"
    assert "lower-48" in result["not_ranked"][0]["reason"]


def test_compare_needs_two_codes(run):
    assert "two or more" in run("compare_airports", codes=["BOS"])["error"]


def test_profile_has_every_metric_with_source_and_missing_reasons(run):
    result = run("airport_profile", code="KBOS")
    assert result["code"] == "BOS" and result["ranked"] is True
    assert result["metrics"] and all(has_source_and_date(m) for m in result["metrics"].values())
    assert result["missing"]["long_haul_share"] == "computed only for Anchorage (OpenSky)"


def test_verified_facts_are_only_checked_rows_naming_the_airport():
    sna = tools.domain_facts("SNA")
    assert [f["note"] for f in sna] == [2, 3, 5]
    assert all(f["sources"] and f["sources"][0].startswith("https://") for f in sna)
    assert "**" not in sna[0]["fact"]
    assert "9.9M" not in sna[2]["fact"]  # a figure the check dropped is not passed on
    assert [f["note"] for f in tools.domain_facts("LAX")] == [5]  # note 4 is unverified
    assert tools.domain_facts("BOS") == []


def test_long_haul_share_for_anchorage(run):
    result = run("long_haul_share", code="ANC")
    assert result["available"] is True and result["threshold_miles"] == 1400
    share = result["long_haul_share"]
    assert 0 <= share["value"] <= 1 and has_source_and_date(share)
    assert "threshold_note" not in result


def test_long_haul_share_other_threshold_says_only_1400_is_computed(run):
    result = run("long_haul_share", code="ANC", threshold_miles=1500)
    assert "only the 1,400-mile threshold is computed" in result["threshold_note"]


def test_long_haul_share_elsewhere_is_not_available(run):
    result = run("long_haul_share", code="BOS")
    assert result["available"] is False
    assert result["reason"].startswith("not available: computed only for Anchorage")


def test_demand_pressure_has_percentiles_and_a_summary_built_in_code(run):
    result = run("demand_pressure", code="BOS")
    assert result["ranked"] is True
    assert set(result["signals"]) == {"delay", "cancellations", "fare premium", "growth"}
    high = [k for k, s in result["signals"].items() if s.get("percentile", 0) >= 75]
    assert result["summary"].startswith("BOS: top quartile nationally: ")
    assert ", ".join(high) in result["summary"]


def test_demand_pressure_outside_scope(run):
    result = run("demand_pressure", code="ANC")
    assert result["ranked"] is False and "lower-48" in result["reason"]


@pytest.mark.parametrize(
    ("name", "args", "expected"),
    [
        ("airport_profile", {"code": "ZZZ"}, "No airport for code"),
        ("rank_airports", {"region": "Atlantis"}, "Unknown region"),
        ("rank_airports", {"preset": "aggressive"}, "Unknown preset"),
        ("rank_airports", {"region": "New England", "codes": ["BOS"]}, "not both"),
        ("rank_airports", {"colour": "red"}, "bad arguments"),
        ("compare_airports", {"codes": ["BOS", "ZZZ"]}, "No airport for code"),
        ("no_such_tool", {}, "unknown tool"),
    ],
)
def test_mistakes_come_back_as_structured_errors(run, name, args, expected):
    result = run(name, **args)
    assert set(result) == {"error"} and expected in result["error"]


def test_missing_cache_is_an_error_not_an_exception(tmp_path):
    result = run_tool("rank_airports", {}, cache_dir=tmp_path)
    assert "no data built yet" in result["error"]


def test_every_tool_is_declared_once():
    names = [d["name"] for d in tools.TOOL_DECLARATIONS]
    assert sorted(names) == sorted(tools.TOOLS)


def test_results_carry_no_internal_decision_labels(run):
    # The model copies wording from tool results into answers; "(D13)" means nothing to a user.
    results = [
        run("rank_airports", region="New England"),
        run("compare_airports", codes=["BOS", "ANC"]),
        run("airport_profile", code="ANC"),
        run("long_haul_share", code="ANC", threshold_miles=1500),
        run("demand_pressure", code="BDL"),
    ]
    text = json.dumps(results)
    assert not [text[max(m.start() - 60, 0) : m.end() + 5] for m in re.finditer(r"\bD\d+\b", text)]


def test_tools_read_the_latest_snapshot_by_default(sample_cache, tmp_path, monkeypatch):
    # No cache_dir: the tools must leave the choice to the data layer (latest snapshot), not
    # fall back to an old local build folder.
    monkeypatch.chdir(tmp_path)  # no data/cache folder here
    latest = lambda version=None: sample_cache  # noqa: E731
    monkeypatch.setattr("airport_agent.data.metrics.snapshot_dir", latest)
    for name, args in [
        ("rank_airports", {"region": "New England"}),
        ("airport_profile", {"code": "BOS"}),
        ("long_haul_share", {"code": "ANC"}),
        ("demand_pressure", {"code": "BOS"}),
    ]:
        assert "error" not in run_tool(name, args), name


@pytest.mark.parametrize(
    ("name", "args", "expected"),
    [
        ("rank_airports", {"codes": [123]}, "codes must be a list of airport codes"),
        ("rank_airports", {"codes": {"BOS": 1}}, "codes must be a list of airport codes"),
        ("rank_airports", {"region": 5}, "region must be a region name"),
        ("rank_airports", {"preset": ["balanced"]}, "preset must be a preset name"),
        ("rank_airports", {"top": "3"}, "top must be a whole number"),
        ("rank_airports", {"top": True}, "top must be a whole number"),
        ("compare_airports", {"codes": ["BOS", None]}, "codes must be a list of airport codes"),
        ("airport_profile", {"code": 7}, "code must be an airport code"),
        ("long_haul_share", {"code": "ANC", "threshold_miles": "far"}, "must be a number"),
    ],
)
def test_arguments_of_the_wrong_type_come_back_as_errors(run, name, args, expected):
    result = run(name, **args)
    assert set(result) == {"error"} and expected in result["error"]


def test_a_tool_that_breaks_unexpectedly_comes_back_as_an_error(run, monkeypatch, caplog):
    def broken(**_):
        raise KeyError("delay")

    monkeypatch.setitem(tools.TOOLS, "airport_profile", broken)
    result = run("airport_profile", code="BOS")
    assert result == {"error": "the tool airport_profile failed: KeyError: 'delay'"}
    assert "tool airport_profile failed" in caplog.text
