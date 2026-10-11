"""Scoring on small hand-made airports, plus one run on the cache built from data/samples/."""

import dataclasses
import random

import pytest
import yaml

from airport_agent import scoring
from airport_agent.data.metrics import Metric, Metrics, all_airport_metrics
from airport_agent.scoring import (
    CONSTRAINTS_PATH,
    SCORED_SIGNALS,
    SCORING_PATH,
    Settings,
    SettingsError,
    UnknownPlaceError,
    load_settings,
    percentiles,
    rank,
    signal_weights,
)

SCORING = {
    "default_preset": "balanced",
    "presets": {
        "balanced": {"strain": 50, "growth": 50},
        "growth-focused": {"strain": 30, "growth": 70},
        "congestion-focused": {"strain": 70, "growth": 30},
    },
    "strain_mix": {"nas_delay_per_landed_flight": 50, "cancellation_rate": 25, "fare_premium": 25},
    "required_signals": ["nas_delay_per_landed_flight"],
    "low_confidence_min_markets": 10,
    "friction_points": {"minor": 10, "major": 20, "hard_cap": 30},
}


def settings(constraints=None, **changes):
    return Settings({**SCORING, **changes}, constraints or {})


def without_constraints(real):
    """Real scoring settings with no constraints, for the hand-made airports (no SNA or SFO)."""
    return dataclasses.replace(real, constraints={})


def friction(name, tier):
    return {"name": name, "tier": tier, "description": name, "sources": ["s"], "domain_notes": [1]}


def airport(
    code, delay=None, cancel=None, fare=None, growth=None, markets=50, state="MA", icao=None
):
    """A ranked airport with the given signal values; None = missing (with a reason)."""
    values = {
        "nas_delay_per_landed_flight": delay,
        "cancellation_rate": cancel,
        "fare_premium": fare,
        "growth_vs_2019": growth,
    }
    signals = {name: Metric(v, "u", "test", "2026") for name, v in values.items() if v is not None}
    missing = {name: "not in the test data" for name, v in values.items() if v is None}
    return Metrics(
        iata=code,
        icao=icao,
        name=f"{code} Airport",
        state=state,
        in_scope=True,
        scope_reason="test",
        market_count=Metric(markets, "markets", "test", "2026"),
        missing=missing,
        **signals,
    )


# Four complete airports. Percentiles (4 airports, top = 100):
#   delay   A 1 -> 25, B 2 -> 50, C 3 -> 75, D 4 -> 100
#   cancel  D 25, C 50, B 75, A 100
#   fare    all equal 1.0 -> each gets average rank 2.5 -> 62.5
#   growth  A 25, B 50, C 75, D 100
FOUR = [
    airport("AAA", delay=1, cancel=0.04, fare=1.0, growth=-10),
    airport("BBB", delay=2, cancel=0.03, fare=1.0, growth=0),
    airport("CCC", delay=3, cancel=0.02, fare=1.0, growth=10),
    airport("DDD", delay=4, cancel=0.01, fare=1.0, growth=20),
]


def by_code(results):
    return {r.code: r for r in results}


def test_percentiles_top_is_100_and_ties_share_the_average_rank():
    assert percentiles({"A": 5, "B": 1, "C": 3}) == pytest.approx(
        {"A": 100, "B": 100 / 3, "C": 200 / 3}
    )
    # B and C tie for ranks 2 and 3 -> both 2.5 of 4.
    assert percentiles({"A": 1, "B": 2, "C": 2, "D": 9}) == pytest.approx(
        {"A": 25, "B": 62.5, "C": 62.5, "D": 100}
    )
    assert percentiles({"A": 7}) == {"A": 100}
    assert percentiles({}) == {}


def test_contributions_sum_to_the_score_before_friction():
    for r in rank(FOUR, settings=settings()):
        assert sum(r.contributions.values()) == pytest.approx(r.pre_friction_score)
        assert r.score == pytest.approx(r.pre_friction_score)  # no friction on file


def test_hand_checked_balanced_scores():
    # Balanced weights: delay .25, cancel .125, fare .125, growth .5.
    # DDD = .25*100 + .125*25 + .125*62.5 + .5*100 = 25 + 3.125 + 7.8125 + 50 = 85.9375
    # AAA = .25*25 + .125*100 + .125*62.5 + .5*25 = 6.25 + 12.5 + 7.8125 + 12.5 = 39.0625
    results = by_code(rank(FOUR, settings=settings()))
    assert results["DDD"].score == pytest.approx(85.9375)
    assert results["AAA"].score == pytest.approx(39.0625)
    assert [r.code for r in rank(FOUR, settings=settings())] == ["DDD", "CCC", "BBB", "AAA"]


def test_missing_signal_spreads_its_weight_and_lowers_confidence():
    # EEE has no growth. Its strain weights .25/.125/.125 are divided by their sum .5, so become
    # delay .5, cancel .25, fare .25. Percentiles among 5 airports: delay 5 -> 100, cancel 0.05
    # -> 100, fare 1.0 ties with 4 others for ranks 1-5 -> 60.
    # Score = .5*100 + .25*100 + .25*60 = 90.
    five = [*FOUR, airport("EEE", delay=5, cancel=0.05, fare=1.0)]
    eee = by_code(rank(five, settings=settings()))["EEE"]
    assert eee.score == pytest.approx(90)
    weights = {s.name: s.weight for s in eee.signals}
    assert weights == pytest.approx(
        {
            "nas_delay_per_landed_flight": 0.5,
            "cancellation_rate": 0.25,
            "fare_premium": 0.25,
            "growth_vs_2019": 0,
        }
    )
    assert eee.confidence == "Low"
    assert eee.confidence_reasons == ("growth missing: not in the test data",)
    # Growth percentiles are still over the four airports that have it.
    assert by_code(rank(five, settings=settings()))["DDD"].percentiles["growth_vs_2019"] == 100


def test_all_signals_missing_scores_zero_without_crashing():
    # With nothing required, an airport with no signals at all is still ranked, at 0.
    empty = airport("ZZZ")
    zzz = by_code(rank([*FOUR, empty], settings=settings(required_signals=[])))["ZZZ"]
    assert (zzz.score, zzz.confidence) == (0, "Low")
    assert len(zzz.confidence_reasons) == 4


# FFF has only a fare premium, the highest of all: no measured delay, so it is not ranked.
FARE_ONLY = airport("FFF", fare=9.0)


def test_airport_without_a_required_signal_is_not_ranked():
    results = rank([*FOUR, FARE_ONLY], settings=settings())
    assert [r.code for r in results] == ["DDD", "CCC", "BBB", "AAA"]
    [fff] = results.not_ranked
    assert (fff.code, fff.missing) == ("FFF", ("nas_delay_per_landed_flight",))
    assert fff.reason == "no measured delay data"
    # The real config requires measured delay.
    assert load_settings().scoring["required_signals"] == ["nas_delay_per_landed_flight"]
    with pytest.raises(ValueError, match="unknown signal"):
        rank(FOUR, settings=settings(required_signals=["delay"]))


def test_unranked_airport_does_not_move_anyone_elses_percentiles():
    # FFF's fare premium tops everyone's; if it were counted, every ranked fare percentile
    # would fall from 62.5 to 50. The ranked results must be identical with and without it.
    with_fff = rank([*FOUR, FARE_ONLY], settings=settings())
    assert with_fff == rank(FOUR, settings=settings())
    assert all(r.percentiles["fare_premium"] == 62.5 for r in with_fff)


def test_region_and_codes_list_not_ranked_airports_with_the_reason(monkeypatch, capsys):
    places = [*FOUR, FARE_ONLY, airport("GGG", fare=2.0, state="CA")]
    new_england = rank(places, region="New England", settings=settings())
    assert [r.code for r in new_england] == ["DDD", "CCC", "BBB", "AAA"]
    assert [(n.code, n.reason) for n in new_england.not_ranked] == [
        ("FFF", "no measured delay data")
    ]
    picked = rank(places, codes=["FFF", "AAA"], settings=settings())
    assert [r.code for r in picked] == ["AAA"]
    assert [n.code for n in picked.not_ranked] == ["FFF"]
    # The command line prints them under the table; the national count leaves them out.
    monkeypatch.setattr(scoring, "all_airport_metrics", lambda: places)
    monkeypatch.setattr(scoring, "load_settings", lambda: without_constraints(load_settings()))
    assert scoring.main(["--region", "New England"]) == 0
    out = capsys.readouterr().out
    assert "out of 4 ranked airports" in out
    assert "Not ranked: FFF (no measured delay data)." in out
    assert "GGG" not in out


def test_required_signals_come_from_the_yaml(tmp_path):
    # EEE has no growth: ranked (Low confidence) under the real file ...
    eee = airport("EEE", delay=5, cancel=0.05, fare=1.0)
    assert "EEE" in by_code(rank([*FOUR, eee], settings=without_constraints(load_settings())))
    # ... but not ranked once a temporary copy also requires growth.
    text = SCORING_PATH.read_text(encoding="utf-8").replace(
        "  - nas_delay_per_landed_flight\n", "  - nas_delay_per_landed_flight\n  - growth_vs_2019\n"
    )
    path = tmp_path / "scoring.yaml"
    path.write_text(text, encoding="utf-8")
    stricter = without_constraints(load_settings(path, CONSTRAINTS_PATH))
    results = rank([*FOUR, eee, airport("HHH", fare=1.0)], settings=stricter)
    assert "EEE" not in by_code(results)
    assert [(n.code, n.reason) for n in results.not_ranked] == [
        ("EEE", "no measured growth data"),
        ("HHH", "no measured delay or growth data"),
    ]


def test_few_markets_lowers_confidence():
    thin = [*FOUR[:3], airport("DDD", 4, 0.01, 1.0, 20, markets=9)]
    ddd = by_code(rank(thin, settings=settings()))["DDD"]
    assert ddd.confidence == "Low"
    assert ddd.confidence_reasons == ("only 9 market(s) in DOT Table 1a (fewer than 10)",)
    assert by_code(rank(thin, settings=settings()))["CCC"].confidence == "High"
    # The threshold comes from the settings.
    looser = settings(low_confidence_min_markets=9)
    assert by_code(rank(thin, settings=looser))["DDD"].confidence == "High"


def test_only_the_largest_friction_counts():
    constraints = {"DDD": [friction("curfew", "minor"), friction("cap", "hard_cap")]}
    ddd = by_code(rank(FOUR, settings=settings(constraints)))["DDD"]
    assert ddd.friction.name == "cap" and ddd.friction.points == 30
    assert [f.name for f in ddd.friction_not_counted] == ["curfew"]
    assert ddd.score == pytest.approx(85.9375 - 30)
    assert by_code(rank(FOUR, settings=settings(constraints)))["AAA"].friction.points == 0


def test_friction_never_takes_the_score_below_zero():
    constraints = {"AAA": [friction("cap", "hard_cap")]}
    low = settings(constraints, friction_points={"minor": 10, "major": 20, "hard_cap": 50})
    aaa = by_code(rank(FOUR, settings=low))["AAA"]  # 39.0625 - 50 -> 0
    assert aaa.score == 0
    assert aaa.pre_friction_score == pytest.approx(39.0625)


@pytest.mark.parametrize("code", ["AAA", "BBB", "CCC", "DDD"])
def test_raising_growth_never_lowers_the_score(code):
    before = by_code(rank(FOUR, settings=settings()))[code].score
    for step in (0.1, 5, 15, 100):
        raised = [
            airport(
                m.iata,
                m.nas_delay_per_landed_flight.value,
                m.cancellation_rate.value,
                m.fare_premium.value,
                m.growth_vs_2019.value + (step if m.iata == code else 0),
            )
            for m in FOUR
        ]
        after = by_code(rank(raised, settings=settings()))[code].score
        assert after >= before


def test_same_input_any_order_gives_the_same_result():
    # Two identical airports too, so the order of tied airports is checked as well.
    airports = [*FOUR, airport("YYY", 2, 0.02, 1.0, 5), airport("XXX", 2, 0.02, 1.0, 5)]
    first = rank(airports, settings=settings())
    assert rank(airports, settings=settings()) == first
    shuffled = list(airports)
    for seed in range(5):
        random.Random(seed).shuffle(shuffled)
        assert rank(shuffled, settings=settings()) == first


def test_ties_go_to_the_higher_pre_friction_score_then_the_code():
    # Two identical airports tie on everything: alphabetical code decides.
    twins = [airport("YYY", 2, 0.02, 1.0, 5), airport("XXX", 2, 0.02, 1.0, 5)]
    assert [r.code for r in rank(twins, settings=settings())] == ["XXX", "YYY"]
    # Friction brings both to 0: the one with the higher score before friction ranks first.
    constraints = {c: [friction("cap", "hard_cap")] for c in ("AAA", "BBB")}
    big = settings(constraints, friction_points={"minor": 10, "major": 20, "hard_cap": 100})
    ranked = rank(FOUR, settings=big)
    assert [(r.code, r.score) for r in ranked[-2:]] == [("BBB", 0), ("AAA", 0)]


def test_presets_change_only_the_strain_growth_split():
    s = settings()
    for preset, (strain, growth) in {
        "balanced": (0.5, 0.5),
        "growth-focused": (0.3, 0.7),
        "congestion-focused": (0.7, 0.3),
    }.items():
        w = signal_weights(s, preset)
        assert sum(w.values()) == pytest.approx(1)
        assert w["growth_vs_2019"] == pytest.approx(growth)
        # Inside strain: delay 50%, cancellations 25%, fare premium 25%, in every preset.
        assert w["nas_delay_per_landed_flight"] == pytest.approx(strain * 0.5)
        assert w["cancellation_rate"] == pytest.approx(strain * 0.25)
        assert w["fare_premium"] == pytest.approx(strain * 0.25)
    with pytest.raises(UnknownPlaceError, match="balanced"):
        signal_weights(s, "nope")


def test_yaml_weights_drive_the_result(tmp_path):
    # Real files first: the defaults are the D9 numbers.
    real = load_settings()
    assert signal_weights(real, "balanced") == pytest.approx(signal_weights(settings(), "balanced"))
    # All weight on growth in a temporary copy -> the score equals the growth percentile,
    # so AAA (lowest growth) drops to 25 and the order follows growth alone.
    text = SCORING_PATH.read_text(encoding="utf-8").replace(
        "    strain: 50\n    growth: 50", "    strain: 0\n    growth: 50"
    )
    path = tmp_path / "scoring.yaml"
    path.write_text(text, encoding="utf-8")
    growth_only = without_constraints(load_settings(path, CONSTRAINTS_PATH))
    results = by_code(rank(FOUR, settings=growth_only))
    assert results["AAA"].score == pytest.approx(25)
    assert results["CCC"].score == pytest.approx(75)


def test_constraints_file_has_the_owner_tiers():
    real = load_settings()
    assert set(real.constraints) == {"SNA", "SFO"}
    for entries in real.constraints.values():
        for entry in entries:
            assert entry["tier"] in real.scoring["friction_points"]
            assert entry["sources"] and entry["domain_notes"]
    tiers = {(code, e["name"]): e["tier"] for code, es in real.constraints.items() for e in es}
    assert tiers == {
        ("SNA", "Passenger cap"): "hard_cap",
        ("SNA", "Curfew"): "minor",
        ("SFO", "Runway spacing and Bay fill"): "major",
    }


def test_region_and_codes_filter_but_keep_the_national_rank():
    places = [*FOUR[:2], airport("CCC", 3, 0.02, 1.0, 10, state="CA"), FOUR[3]]
    everyone = by_code(rank(places, settings=settings()))
    new_england = rank(places, region="New England", settings=settings())
    assert [r.code for r in new_england] == ["DDD", "BBB", "AAA"]
    assert [r.rank for r in new_england] == [1, 2, 3]
    assert [r.national_rank for r in new_england] == [1, 3, 4]
    assert all(r.score == everyone[r.code].score for r in new_england)
    picked = rank(places, codes=["ccc", "AAA"], settings=settings())
    assert [(r.code, r.rank, r.national_rank) for r in picked] == [("CCC", 1, 2), ("AAA", 2, 4)]
    with pytest.raises(UnknownPlaceError, match="Not ranked: ZZZ"):
        rank(places, codes=["ZZZ"], settings=settings())
    with pytest.raises(UnknownPlaceError, match="new england"):
        rank(places, region="Atlantis", settings=settings())


def test_sample_cache_ranks_every_airport_with_real_settings(sample_cache):
    metrics = all_airport_metrics(sample_cache)
    results = rank(metrics, region="New England")
    assert results and [r.rank for r in results] == list(range(1, len(results) + 1))
    for r in results:
        assert 0 <= r.score <= 100
        assert r.confidence in ("High", "Low")
        for s in r.signals:
            assert s.name in SCORED_SIGNALS
            assert (s.metric is None) == (s.percentile is None)
    sfo = rank(metrics, codes=["SFO"])[0]
    assert sfo.friction.points == 20 and sfo.friction.domain_notes == (6, 7)


def test_cli_prints_the_new_england_table(sample_cache, monkeypatch, capsys):
    monkeypatch.setattr(scoring, "all_airport_metrics", lambda: all_airport_metrics(sample_cache))
    assert scoring.main(["--region", "New England"]) == 0
    out = capsys.readouterr().out
    assert "Preset: balanced" in out and "BOS " in out and "SFO" not in out
    assert scoring.main(["--codes", "SFO", "--preset", "growth-focused"]) == 0
    assert "-20 Runway spacing" in capsys.readouterr().out


def test_cli_says_how_to_build_missing_data(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)  # no data/cache here
    assert scoring.main([]) == 1
    assert "python -m airport_agent.data" in capsys.readouterr().err


# --- Settings mistakes fail loudly: one plain sentence naming the file and the key ----------


def _scoring_with(**changes):
    """A deep enough copy of SCORING with some keys replaced (None = key removed)."""
    result = {key: (dict(v) if isinstance(v, dict) else v) for key, v in SCORING.items()}
    result["presets"] = {name: dict(split) for name, split in SCORING["presets"].items()}
    for key, value in changes.items():
        if value is None:
            del result[key]
        else:
            result[key] = value
    return result


BALANCED = SCORING["presets"]["balanced"]
MIX = SCORING["strain_mix"]


@pytest.mark.parametrize(
    "scoring_settings, constraints, named",
    [
        (_scoring_with(colour="red"), {}, "colour"),
        (_scoring_with(strain_mix=None), {}, "strain_mix"),
        (_scoring_with(presets={"balanced": {"strian": 50, "growth": 50}}), {}, "strian"),
        (_scoring_with(presets={"balanced": {"growth": 50}}), {}, "strain"),
        (_scoring_with(presets={"balanced": {"strain": 0, "growth": 0}}), {}, "balanced"),
        (_scoring_with(presets={"balanced": {"strain": -5, "growth": 50}}), {}, "strain"),
        (_scoring_with(presets={"balanced": {"strain": "50", "growth": 50}}), {}, "strain"),
        (_scoring_with(default_preset="balnced"), {}, "default_preset"),
        (_scoring_with(strain_mix={**MIX, "delay": 100}), {}, "delay"),
        (_scoring_with(strain_mix={"nas_delay_per_landed_flight": 50}), {}, "cancellation_rate"),
        (_scoring_with(strain_mix=dict.fromkeys(MIX, 0)), {}, "strain_mix"),
        (_scoring_with(strain_mix={**MIX, "fare_premium": -1}), {}, "fare_premium"),
        (_scoring_with(friction_points={"minr": 10, "major": 20, "hard_cap": 30}), {}, "minr"),
        (
            _scoring_with(friction_points={"minor": 10, "major": 20, "hard_cap": "30"}),
            {},
            "hard_cap",
        ),
        (_scoring_with(friction_points={"minor": 10, "major": -20, "hard_cap": 30}), {}, "major"),
        (_scoring_with(required_signals="nas_delay_per_landed_flight"), {}, "required_signals"),
        (_scoring_with(required_signals=["delay"]), {}, "delay"),
        (_scoring_with(low_confidence_min_markets=-1), {}, "low_confidence_min_markets"),
        (_scoring_with(low_confidence_min_markets="10"), {}, "low_confidence_min_markets"),
        (SCORING, {"AAA": [{**friction("cap", "hard_cap"), "tier": "minr"}]}, "minr"),
        (SCORING, {"AAA": [{**friction("cap", "hard_cap"), "description": ""}]}, "description"),
        (SCORING, {"AAA": [{**friction("cap", "hard_cap"), "sources": []}]}, "sources"),
        (SCORING, {"AAA": [{**friction("cap", "hard_cap"), "sources": "s"}]}, "sources"),
        (SCORING, {"AAA": "cap"}, "AAA"),
    ],
)
def test_a_settings_mistake_raises_a_plain_error_naming_the_key(
    tmp_path, scoring_settings, constraints, named
):
    # Straight from dicts, through rank ...
    with pytest.raises(SettingsError, match=named):
        rank(FOUR, settings=Settings(scoring_settings, constraints))
    # ... and from the YAML files, through load_settings.
    scoring_path, constraints_path = tmp_path / "scoring.yaml", tmp_path / "constraints.yaml"
    scoring_path.write_text(yaml.safe_dump(scoring_settings), encoding="utf-8")
    constraints_path.write_text(yaml.safe_dump(constraints), encoding="utf-8")
    with pytest.raises(SettingsError, match=named) as error:
        load_settings(scoring_path, constraints_path)
    assert "\n" not in str(error.value)


SNA_PLACES = [*FOUR, airport("SNA", 1, 0.01, 1.0, 0, state="CA", icao="KSNA")]


@pytest.mark.parametrize("key", ["SAN", "SNX", "KSAN"])
def test_a_constraints_code_that_names_no_airport_fails(key):
    # Before, a typo dropped the penalty silently: SNA went from last to 2nd in the LA area.
    with pytest.raises(SettingsError, match=f"data/constraints.yaml: {key} is not the code"):
        rank(SNA_PLACES, settings=settings({key: [friction("cap", "hard_cap")]}))


@pytest.mark.parametrize("key", ["SNA", "sna", "KSNA", "ksna"])
def test_a_constraints_code_may_be_lower_case_or_icao(key):
    ranked = by_code(rank(SNA_PLACES, settings=settings({key: [friction("cap", "hard_cap")]})))
    assert ranked["SNA"].friction.points == 30


def test_a_constraints_code_given_twice_fails():
    twice = {"SNA": [friction("a", "minor")], "sna": [friction("b", "minor")]}
    with pytest.raises(SettingsError, match="sna is SNA again"):
        rank(SNA_PLACES, settings=settings(twice))


def test_cli_prints_a_settings_mistake_plainly_and_exits_2(tmp_path, monkeypatch, capsys):
    path = tmp_path / "scoring.yaml"
    path.write_text(
        SCORING_PATH.read_text(encoding="utf-8").replace("strain: 50", "strian: 50"),
        encoding="utf-8",
    )
    monkeypatch.setattr(scoring, "all_airport_metrics", lambda: FOUR)
    monkeypatch.setattr(scoring, "load_settings", lambda: load_settings(path, CONSTRAINTS_PATH))
    assert scoring.main([]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        "config/scoring.yaml: presets: balanced has unknown key(s) strian; "
        "allowed: strain, growth\n"
    )
