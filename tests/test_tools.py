"""The agent's tools on a cache built from data/samples/ (New England fares, Anchorage flights)."""

import copy
import dataclasses
import datetime
import json
import re
import shutil
from pathlib import Path

import pytest

from airport_agent import tools
from airport_agent.data.metrics import all_airport_metrics
from airport_agent.scoring import load_settings
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


@pytest.mark.parametrize("top", [0, -1])
def test_rank_top_must_be_positive(run, top):
    result = run("rank_airports", region="New England", top=top)
    assert set(result) == {"error"} and "top must be a positive whole number" in result["error"]


def test_compare_lists_airports_outside_the_ranked_scope_with_the_reason(run):
    result = run("compare_airports", codes=["BOS", "BDL", "PANC"])
    assert [r["code"] for r in result["rows"]] == sorted(
        ["BOS", "BDL"], key=lambda c: next(r["rank"] for r in result["rows"] if r["code"] == c)
    )
    assert result["not_ranked"][0]["code"] == "ANC"
    assert "lower-48" in result["not_ranked"][0]["reason"]


def test_compare_needs_two_codes(run):
    assert "two or more" in run("compare_airports", codes=["BOS"])["error"]


def test_compare_counts_airports_not_codes(run):
    result = run("compare_airports", codes=["BOS", "KBOS"])
    assert set(result) == {"error"}
    assert "two or more different airports" in result["error"]
    assert "BOS and KBOS are the same airport (BOS)" in result["error"]


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


def test_rank_count_is_named_apart_from_a_rank(run):
    # The evaluation run: a count named ranked_nationally was read as "ranked 138 nationally".
    ranking = run("rank_airports", region="New England")
    pressure = run("demand_pressure", code="SFO")
    for result in (ranking, pressure):
        assert "ranked_nationally" not in result
        assert result["ranked_count"] >= 2
    assert all(1 <= r["national_rank"] <= ranking["ranked_count"] for r in ranking["rows"])
    assert "national_rank" not in pressure
    assert "not this airport's rank" in pressure["percentile_note"]


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


def test_q4_sfo_tool_path_gives_the_model_the_verified_runway_facts_and_friction():
    # Offline stand-in for the Q4 run ("why is SFO constrained?"): the two tools the system
    # prompt sends a "why" question to, on the latest committed data snapshot. Whatever the
    # model writes, these facts and the 20-point penalty with sources are what it receives.
    profile = run_tool("airport_profile", {"code": "SFO"})
    facts = {f["note"]: f for f in profile["verified_facts"]}
    assert set(facts) == {6, 7}
    for phrase in ("28L/28R", "750 ft", "104–107", "71–78"):
        assert phrase in facts[6]["fact"], phrase
    for phrase in ("Bay fill", "Proposition D", "100 acres"):
        assert phrase in facts[7]["fact"], phrase
    assert all(
        f["sources"] and all(s.startswith("https://") for s in f["sources"]) for f in facts.values()
    )

    pressure = run_tool("demand_pressure", {"code": "SFO"})
    assert pressure["ranked"] is True
    friction = pressure["friction"]
    assert (friction["name"], friction["points"], friction["tier"]) == (
        "Runway spacing and Bay fill",
        20,
        "major",
    )
    assert "750 ft" in friction["description"]
    assert friction["sources"] and all(s.startswith("https://") for s in friction["sources"])
    for signal in pressure["signals"].values():
        assert "missing" in signal or has_source_and_date(signal)


@pytest.mark.parametrize(
    ("tool", "args"),
    [
        ("demand_pressure", {"code": ""}),
        ("demand_pressure", {"code": " "}),
        ("rank_airports", {"codes": ""}),
        ("rank_airports", {"codes": []}),
    ],
)
def test_a_blank_code_is_a_plain_error_not_a_national_ranking(tool, args):
    # Review round 2: blank codes failed with an IndexError or fell back to the national top 10.
    result = run_tool(tool, args)
    assert "no airport code given" in result["error"]


def test_top_sent_as_a_whole_float_works():
    # Review round 2: the model may send 5.0 for 5.
    result = run_tool("rank_airports", {"top": 5.0})
    assert "error" not in result and len(result["rows"]) == 5
    assert "error" in run_tool("rank_airports", {"top": 5.5})


def test_arguments_no_tool_declares_are_refused():
    # Review round 3: the model could pass internal arguments such as settings.
    result = run_tool("compare_airports", {"codes": ["LAX", "SNA"], "settings": {"x": 1}})
    assert "unknown settings" in result["error"]


@pytest.mark.parametrize("miles", [float("nan"), float("inf")])
def test_a_threshold_that_is_not_a_distance_is_refused(miles):
    result = run_tool("long_haul_share", {"code": "ANC", "threshold_miles": miles})
    assert "threshold_miles must be a number" in result["error"]


# --- compare_over_time, on the committed data snapshots ---------------------------------------


def over_time(**args):
    result = run_tool("compare_over_time", {"preset": None, **args})
    json.dumps(result)
    return result


def test_compare_over_time_gives_each_signal_in_both_snapshots_with_its_change():
    result = over_time(code="SFO", from_version="2019-12", to_version="latest")
    assert result["from"]["version"] == "2019-12"
    assert result["to"]["version"].startswith("latest-")
    for side in (result["from"], result["to"]):
        assert 0 <= side["score"] <= 100
        assert 1 <= side["rank"] <= side["ranked_count"]
    assert result["score_change"] == round(result["to"]["score"] - result["from"]["score"], 1)
    delay = result["signals"]["nas_delay_per_landed_flight"]
    assert has_source_and_date(delay["from"]) and has_source_and_date(delay["to"])
    assert delay["change"] == round(delay["to"]["value"] - delay["from"]["value"], 4)
    cancel = result["signals"]["cancellation_rate"]
    assert cancel["change_pct_points"] == round(cancel["change"] * 100, 1)
    assert "change_pct_points" not in delay


def test_compare_over_time_flags_a_signal_missing_on_one_side_and_computes_no_change():
    # The Anchorage long-haul share is measured only in the latest snapshot
    result = over_time(code="ANC", from_version="2019-12", to_version="latest")
    long_haul = result["signals"]["long_haul_share"]
    assert long_haul["from"] is None and long_haul["to"]["value_pct"] > 0
    assert "not available for this date" in long_haul["note"]
    assert "change" not in long_haul and "change_pct_points" not in long_haul
    assert long_haul["why"] and long_haul["why"][0].startswith("2019-12")
    assert result["from"]["score"] is None and "not ranked" in result["from"]["not_ranked"]
    assert "score_change" not in result


def test_compare_over_time_accepts_a_full_latest_name_and_orders_as_asked():
    latest = over_time(code="BOS", from_version="2021-12", to_version="latest")["to"]["version"]
    back = over_time(code="KBOS", from_version=latest, to_version="2021-12")
    assert (back["code"], back["from"]["version"], back["to"]["version"]) == (
        "BOS",
        latest,
        "2021-12",
    )


def test_compare_over_time_unknown_version_lists_the_available_ones():
    result = over_time(code="SFO", from_version="2020-06", to_version="latest")
    assert "no data version '2020-06'" in result["error"]
    for version in ("2019-12", "2021-12", "latest-", "latest"):
        assert version in result["error"]
    path_like = over_time(code="SFO", from_version="../etc", to_version="latest")
    assert "available versions" in path_like["error"]


def test_compare_over_time_needs_two_different_versions():
    result = over_time(code="SFO", from_version="2019-12", to_version="2019-12")
    assert "two different versions" in result["error"]


def test_compare_over_time_unknown_airport_names_the_snapshot():
    result = over_time(code="ZZZ", from_version="2019-12", to_version="latest")
    assert "'ZZZ' is in neither data version" in result["error"]


def test_compare_over_time_airport_absent_from_one_snapshot(tmp_path):
    # A store whose old snapshot lacks the airport: the message names that snapshot.
    store = tmp_path / "store"
    for version in ("2019-12", "2021-12"):
        shutil.copytree(Path("data/snapshots") / version, store / version)
    summary = store / "2019-12" / "ourairports.json"
    text = summary.read_text(encoding="utf-8")
    data = json.loads(text)
    data["data"]["airports"] = [a for a in data["data"]["airports"] if a.get("iata") != "SFO"]
    summary.write_text(json.dumps(data), encoding="utf-8")
    result = run_tool(
        "compare_over_time",
        {"code": "SFO", "from_version": "2019-12", "to_version": "2021-12"},
        cache_dir=store,
    )
    assert "is not in the 2019-12 data" in result["error"]


def test_compare_over_time_arguments_are_checked():
    missing = run_tool("compare_over_time", {"code": "SFO", "from_version": "2019-12"})
    assert "error" in missing
    wrong = run_tool(
        "compare_over_time", {"code": "SFO", "from_version": 2019, "to_version": "latest"}
    )
    assert "from_version must be a data version as text" in wrong["error"]


def test_compare_over_time_gives_the_asked_airports_own_reason_when_unranked():
    # In the latest snapshot other airports are unranked for another reason (APA, first A to Z:
    # no delay data); the side must carry SFO's own reason, not the first in the not-ranked list.
    settings = copy.deepcopy(load_settings())
    settings.scoring["required_signals"] = [
        *settings.scoring["required_signals"],
        "cancellation_rate",
    ]
    metrics_list = [
        dataclasses.replace(m, cancellation_rate=None) if m.iata == "SFO" else m
        for m in all_airport_metrics()
    ]
    sfo = next(m for m in metrics_list if m.iata == "SFO")
    standing = tools._standing(sfo, metrics_list, None, settings)
    assert standing["score"] is None
    assert standing["not_ranked"] == "no measured cancellations data"


def test_compare_over_time_carries_no_internal_decision_labels():
    results = [
        over_time(code="SFO", from_version="2019-12", to_version="latest"),
        over_time(code="ANC", from_version="2019-12", to_version="latest"),
    ]
    text = json.dumps(results)
    assert not [text[max(m.start() - 60, 0) : m.end() + 5] for m in re.finditer(r"\bD\d+\b", text)]


def test_compare_over_time_says_so_when_given_one_snapshot_folder(run):
    result = run("compare_over_time", code="SFO", from_version="2019-12", to_version="latest")
    assert "folder of data snapshots, not a single snapshot" in result["error"]


def test_compare_over_time_offers_latest_only_when_a_latest_snapshot_exists(tmp_path):
    store = tmp_path / "store"
    for version in ("2019-12", "2021-12"):
        shutil.copytree(Path("data/snapshots") / version, store / version)
    result = run_tool(
        "compare_over_time",
        {"code": "SFO", "from_version": "2019-12", "to_version": "latest"},
        cache_dir=store,
    )
    assert result["error"].endswith("available versions: 2019-12, 2021-12")


def test_out_of_scope_and_unmeasured_reasons_carry_no_decision_labels(run):
    # The two scope messages the label removal touched: an airport not in DOT Table 1a for the
    # data's date (the sample fares cover New England only) and a code outside the lower 48.
    results = [
        run("airport_profile", code="ABQ"),
        run("rank_airports", codes=["BOS", "ABQ"]),
        run("rank_airports", codes=["BOS", "HNL"]),
    ]
    text = json.dumps(results)
    assert "no DOT Table 1a rows" in text and "lower-48" in text
    assert not [text[max(m.start() - 60, 0) : m.end() + 5] for m in re.finditer(r"\bD\d+\b", text)]


def test_domain_notes_are_found_from_the_working_folder_when_installed(tmp_path, monkeypatch):
    # Installed as a package (the Docker image), there is no repo around the code: the notes
    # are read from docs/ under the working folder, where the Dockerfile copies them (/app).
    assert tools._notes_path(tmp_path / "venv") == Path("docs/DOMAIN_NOTES.md")
    (tmp_path / "docs").mkdir()
    shutil.copy(tools.DOMAIN_NOTES_PATH, tmp_path / "docs" / "DOMAIN_NOTES.md")
    monkeypatch.chdir(tmp_path)
    assert tools.domain_facts("SFO", path=tools._notes_path(tmp_path / "venv"))


def test_verified_facts_carry_dates_and_are_flagged_stale_after_review_by():
    sna = {f["note"]: f for f in tools.domain_facts("SNA", today=datetime.date(2026, 10, 12))}
    assert all(f["checked"] == "2026-10-11" for f in sna.values())
    assert sna[2]["review_by"] == "2030-12-31"
    assert sna[5]["review_by"] == "2027-10-11"
    assert not any(f.get("stale") for f in sna.values())
    later = {f["note"]: f for f in tools.domain_facts("SNA", today=datetime.date(2028, 1, 1))}
    assert later[5]["stale"] is True  # still returned, but flagged
    assert later[5]["stale_note"] == "may be out of date: due for re-check on 2027-10-11"
    assert "stale" not in later[2]
    assert tools.domain_facts("SNA", today=datetime.date(2031, 1, 1))[0]["stale"] is True


def test_airport_profile_for_sfo_returns_checked_dates():
    profile = tools.airport_profile("SFO", today=datetime.date(2026, 10, 12))
    facts = profile["verified_facts"]
    assert [(f["note"], f["checked"], f["review_by"]) for f in facts] == [
        (6, "2026-10-11", "2027-10-11"),
        (7, "2026-10-11", "2027-10-11"),
    ]
    assert not any("stale" in f for f in facts)
    stale = tools.airport_profile("SFO", today=datetime.date(2028, 1, 1))["verified_facts"]
    assert all(f["stale"] for f in stale)


def test_a_stale_friction_is_flagged_in_the_tool_row_and_still_costs_points():
    fresh = tools.rank_airports(codes=["SFO", "BOS"], today=datetime.date(2026, 10, 12))
    stale = tools.rank_airports(codes=["SFO", "BOS"], today=datetime.date(2028, 1, 1))
    fresh_sfo = next(r for r in fresh["rows"] if r["code"] == "SFO")
    stale_sfo = next(r for r in stale["rows"] if r["code"] == "SFO")
    assert fresh_sfo["friction"]["checked"] == "2026-10-11"
    assert fresh_sfo["friction"]["review_by"] == "2027-10-11"
    assert "stale" not in fresh_sfo["friction"]
    assert stale_sfo["friction"]["stale"] is True
    assert "may be out of date" in stale_sfo["friction"]["stale_note"]
    assert stale_sfo["score"] == fresh_sfo["score"]


def test_every_verified_note_has_valid_dates():
    text = tools.DOMAIN_NOTES_PATH.read_text(encoding="utf-8")
    verified = [line for line in text.splitlines() if re.match(r"\|\s*\d+\s*\|.*\|\s*✅", line)]
    rows = list(tools.verified_rows(text))
    assert len(rows) == len(verified) > 0


@pytest.mark.parametrize(
    ("row", "message"),
    [
        ("| 9 | SFO fact | x | x | src | ✅ | 2026-10-11 |  |", "must be dates"),
        ("| 9 | SFO fact | x | x | src | ✅ | 2026-10-11 | 11 Oct 2027 |", "must be dates"),
        ("| 9 | SFO fact | x | x | src | ✅ | 2026-10-11 | 2026-01-01 |", "is before Checked"),
        ("| 9 | SFO fact | x | x | src checked 2026-10-11 | ✅ |", "needs the Checked"),
    ],
)
def test_a_verified_note_with_bad_dates_is_reported_not_dropped(tmp_path, row, message):
    notes = tmp_path / "notes.md"
    notes.write_text(row + "\n", encoding="utf-8")
    with pytest.raises(tools.ToolError, match=message):
        tools.domain_facts("SFO", path=notes)


def test_a_fact_is_not_stale_on_its_review_by_day_only_after():
    def stale(day):
        facts = tools.domain_facts("SFO", today=day)
        return [f.get("stale", False) for f in facts]

    assert stale(datetime.date(2027, 10, 11)) == [False, False]
    assert stale(datetime.date(2027, 10, 12)) == [True, True]


def test_each_penalty_is_due_when_its_earliest_note_is():
    text = tools.DOMAIN_NOTES_PATH.read_text(encoding="utf-8")
    due = {int(cells[0]): review_by for cells, _, review_by in tools.verified_rows(text)}
    for code, entries in load_settings().constraints.items():
        for entry in entries:
            expected = min(due[n] for n in entry["domain_notes"])
            assert str(entry["review_by"]) == expected.isoformat(), (code, entry["name"])


def test_a_stale_penalty_that_does_not_count_is_still_flagged():
    sna = tools.rank_airports(codes=["SNA"], today=datetime.date(2031, 1, 1))["rows"][0]
    assert sna["friction_not_counted"]
    assert all("may be out of date" in text for text in sna["friction_not_counted"])


# --- Determinism: the same question gives the same numbers -----------------------------------

SAME_TWICE = {
    "rank_airports": {"region": "New England"},
    "compare_airports": {"codes": ["BOS", "BDL"]},
    "airport_profile": {"code": "BOS"},
    "long_haul_share": {"code": "ANC"},
    "compare_over_time": {"code": "SFO", "from_version": "2019-12", "to_version": "latest"},
    "demand_pressure": {"code": "BOS"},
}


def test_every_tool_has_a_determinism_case():
    assert set(SAME_TWICE) == {d["name"] for d in tools.TOOL_DECLARATIONS}


@pytest.mark.parametrize("name", sorted(SAME_TWICE))
def test_each_tool_gives_identical_results_when_run_twice(sample_cache, name):
    # compare_over_time reads a folder of snapshots, so it runs on the committed ones.
    cache_dir = None if name == "compare_over_time" else sample_cache
    first = run_tool(name, copy.deepcopy(SAME_TWICE[name]), cache_dir=cache_dir)
    second = run_tool(name, copy.deepcopy(SAME_TWICE[name]), cache_dir=cache_dir)
    assert "error" not in first, first
    assert json.dumps(first, sort_keys=False) == json.dumps(second, sort_keys=False)
