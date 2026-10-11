"""Scoring: rank airports for terminal expansion from the measured signals (decisions D7 to D12).

Which airports are ranked: every in-scope airport (D11) that has each signal listed under
`required_signals` in config/scoring.yaml (now: measured delay). The others are not ranked: they
get no score, are left out of every percentile below, and are listed apart with the reason.

How a score is made, for one ranked airport:
1. Each of the four scored signals becomes a percentile from 0 to 100 across every ranked airport
   that has it: rank ÷ count × 100, so the top airport gets 100 and tied airports share the
   average of their ranks. Higher always means more promising (more delay, more cancellations,
   higher fares, more growth).
2. The percentiles are added up with the preset's weights. If a signal is missing, its weight is
   spread over the airport's other signals in proportion to their weights, and the airport is
   flagged Low confidence.
3. The largest friction penalty on file (data/constraints.yaml) is taken off; the score never
   goes below 0.

Weights, presets and penalties come from config/scoring.yaml. Everything here is pure (no network,
no model) except `load_settings`, which only reads the two YAML files.

Run `uv run python -m airport_agent.scoring --region "New England"` for a table.
"""

import argparse
import dataclasses
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

from airport_agent.data.cache import BUILD_COMMAND, CacheMissingError
from airport_agent.data.metrics import Metric, all_airport_metrics
from airport_agent.data.regions import REGIONS, resolve_place

_REPO = Path(__file__).resolve().parents[2]
SCORING_PATH = _REPO / "config" / "scoring.yaml"
CONSTRAINTS_PATH = _REPO / "data" / "constraints.yaml"

STRAIN_SIGNALS = ("nas_delay_per_landed_flight", "cancellation_rate", "fare_premium")
GROWTH_SIGNAL = "growth_vs_2019"
SCORED_SIGNALS = (*STRAIN_SIGNALS, GROWTH_SIGNAL)
LABELS = {
    "nas_delay_per_landed_flight": "delay",
    "cancellation_rate": "cancellations",
    "fare_premium": "fare premium",
    "growth_vs_2019": "growth",
}
NONE_ON_FILE = "none on file"


class UnknownPlaceError(ValueError):
    """A region, airport code or preset that scoring doesn't know."""


@dataclass(frozen=True)
class Settings:
    """What config/scoring.yaml and data/constraints.yaml say, read once."""

    scoring: dict
    constraints: dict


@dataclass(frozen=True)
class SignalScore:
    """One signal for one airport: its measured value, percentile and points added.

    `weight` is the share of the score this signal carries for this airport (after a missing
    signal's weight was spread out), from 0 to 1. A missing signal has metric, percentile and
    weight None/0 and `missing` says why.
    """

    name: str
    label: str
    metric: Metric | None
    percentile: float | None
    weight: float
    contribution: float
    missing: str | None = None


@dataclass(frozen=True)
class Friction:
    """One constraint from data/constraints.yaml, with its penalty in points."""

    name: str
    tier: str
    points: float
    description: str
    sources: tuple[str, ...]
    domain_notes: tuple[int, ...]


NO_FRICTION = Friction(NONE_ON_FILE, "none", 0, NONE_ON_FILE, (), ())


@dataclass(frozen=True)
class NotRanked:
    """An in-scope airport left out of the ranking because it lacks a required signal.

    `missing` names the required signals it lacks; `reason` says so in words, e.g.
    "no measured delay data".
    """

    code: str
    name: str
    state: str
    missing: tuple[str, ...]
    reason: str


class Ranking(list):
    """What `rank` returns: the ranked airports, best first, as a plain list of AirportScore.

    `not_ranked` lists, as NotRanked, the airports asked for that lack a required signal (A to Z
    by code); they come after the ranked ones and have no score or rank.
    """

    def __init__(self, ranked=(), not_ranked=()):
        super().__init__(ranked)
        self.not_ranked = list(not_ranked)


@dataclass(frozen=True)
class AirportScore:
    """An airport's score, how it was built, and how far to trust it.

    `national_rank` is the rank among every ranked airport in the US (1 = most promising).
    `rank` is the position in the list that was asked for (a region or a set of codes); with no
    filter the two are equal. `pre_friction_score` is the sum of the signals' contributions;
    `score` is that minus `friction.points`, floored at 0.
    """

    code: str
    name: str
    state: str
    preset: str
    score: float
    pre_friction_score: float
    national_rank: int
    rank: int
    signals: tuple[SignalScore, ...]
    friction: Friction
    friction_not_counted: tuple[Friction, ...]
    confidence: str
    confidence_reasons: tuple[str, ...]

    @property
    def contributions(self):
        """Points each signal added, by signal name (missing signals add 0)."""
        return {s.name: s.contribution for s in self.signals}

    @property
    def percentiles(self):
        """Percentile of each signal, by signal name (None when missing)."""
        return {s.name: s.percentile for s in self.signals}


# --- Reading the two YAML files (the only I/O) ---------------------------------------------


def load_settings(scoring_path=SCORING_PATH, constraints_path=CONSTRAINTS_PATH):
    """Read config/scoring.yaml and data/constraints.yaml."""
    with open(scoring_path, encoding="utf-8") as f:
        scoring = yaml.safe_load(f)
    with open(constraints_path, encoding="utf-8") as f:
        constraints = yaml.safe_load(f) or {}
    return Settings(scoring, constraints)


# --- The math (pure) ------------------------------------------------------------------------


def percentiles(values):
    """Percentile rank of each value: rank ÷ count × 100, highest value = 100.

    `values` maps an airport code to a number. Ties share the average of the ranks they cover,
    e.g. two airports tied for 2nd and 3rd of 4 both get rank 2.5, so 62.5.
    """
    ordered = sorted(values.values())
    count = len(ordered)
    result = {}
    for code, value in values.items():
        below = sum(1 for v in ordered if v < value)  # ranks 1..below are taken by lower values
        tied = sum(1 for v in ordered if v == value)
        average_rank = below + (tied + 1) / 2  # mean of ranks below+1 .. below+tied
        result[code] = average_rank / count * 100
    return result


def preset_names(settings):
    return sorted(settings.scoring["presets"])


def signal_weights(settings, preset):
    """Each scored signal's share of the score under a preset, from 0 to 1, summing to 1.

    Example, balanced (strain 50 / growth 50, strain mix 50/25/25): delay 0.25, cancellations
    0.125, fare premium 0.125, growth 0.5.
    """
    presets = settings.scoring["presets"]
    if preset not in presets:
        raise UnknownPlaceError(
            f"Unknown preset {preset!r}; choose one of: {', '.join(preset_names(settings))}"
        )
    split = presets[preset]
    strain_share = split["strain"] / (split["strain"] + split["growth"])
    mix = settings.scoring["strain_mix"]
    mix_total = sum(mix[name] for name in STRAIN_SIGNALS)
    weights = {name: strain_share * mix[name] / mix_total for name in STRAIN_SIGNALS}
    weights[GROWTH_SIGNAL] = 1 - strain_share
    return weights


def frictions(code, settings):
    """Every constraint on file for an airport, largest penalty first (file order breaks ties)."""
    points = settings.scoring["friction_points"]
    found = [
        Friction(
            name=c["name"],
            tier=c["tier"],
            points=points[c["tier"]],
            description=" ".join(c["description"].split()),
            sources=tuple(c["sources"]),
            domain_notes=tuple(c["domain_notes"]),
        )
        for c in settings.constraints.get(code) or []
    ]
    return sorted(found, key=lambda f: -f.points)  # sorted() keeps file order for equal points


def missing_required(metrics, settings):
    """The required signals (config `required_signals`) this airport lacks; empty = ranked."""
    required = settings.scoring["required_signals"]
    unknown = sorted(set(required) - set(SCORED_SIGNALS))
    if unknown:
        raise ValueError(f"required_signals has unknown signal(s): {', '.join(unknown)}")
    return tuple(name for name in required if getattr(metrics, name) is None)


def _not_ranked(metrics, missing):
    reason = "no measured " + " or ".join(LABELS[name] for name in missing) + " data"
    return NotRanked(metrics.iata, metrics.name, metrics.state, missing, reason)


def _confidence(metrics, settings):
    """("High" or "Low", reasons). Low if a scored signal is missing or markets are few (D12)."""
    reasons = [
        f"{LABELS[name]} missing: {metrics.missing.get(name, 'no value')}"
        for name in SCORED_SIGNALS
        if getattr(metrics, name) is None
    ]
    threshold = settings.scoring["low_confidence_min_markets"]
    if metrics.market_count is None:
        reasons.append("market count missing")
    elif metrics.market_count.value < threshold:
        reasons.append(
            f"only {metrics.market_count.value} market(s) in DOT Table 1a (fewer than {threshold})"
        )
    return ("Low" if reasons else "High"), tuple(reasons)


def score_airport(metrics, signal_percentiles, weights, settings, preset):
    """One airport's score from its percentiles; ranks are filled in by `rank`.

    `signal_percentiles` maps each signal name to {code: percentile} over all ranked airports.
    """
    code = metrics.iata
    present = [name for name in SCORED_SIGNALS if getattr(metrics, name) is not None]
    present_weight = sum(weights[name] for name in present)
    signals = []
    for name in SCORED_SIGNALS:
        metric = getattr(metrics, name)
        if metric is None:
            signals.append(
                SignalScore(name, LABELS[name], None, None, 0.0, 0.0, metrics.missing.get(name))
            )
            continue
        weight = weights[name] / present_weight  # a missing signal's weight is spread out here
        percentile = signal_percentiles[name][code]
        signals.append(
            SignalScore(name, LABELS[name], metric, percentile, weight, weight * percentile)
        )

    pre_friction = sum(s.contribution for s in signals)
    on_file = frictions(code, settings)
    friction = on_file[0] if on_file else NO_FRICTION
    confidence, reasons = _confidence(metrics, settings)
    return AirportScore(
        code=code,
        name=metrics.name,
        state=metrics.state,
        preset=preset,
        score=max(0.0, pre_friction - friction.points),
        pre_friction_score=pre_friction,
        national_rank=0,
        rank=0,
        signals=tuple(signals),
        friction=friction,
        friction_not_counted=tuple(on_file[1:]),
        confidence=confidence,
        confidence_reasons=reasons,
    )


def _order(result):
    """Sort key: higher score first; tie -> higher pre-friction score; tie -> code A to Z.

    Rounded to 9 decimals so two scores equal on paper are not split by float noise.
    """
    return (-round(result.score, 9), -round(result.pre_friction_score, 9), result.code)


def rank(metrics_list, preset=None, region=None, codes=None, settings=None):
    """Score and rank airports; returns a Ranking: AirportScore objects, best first.

    Airports missing a required signal are not scored: they go to `.not_ranked` with the reason,
    and are left out of the percentiles. Percentiles are always computed across every ranked
    airport in `metrics_list` (from `all_airport_metrics()`), so `national_rank` is the national
    rank. `region` (e.g.
    "New England", "LA area") or `codes` (e.g. ["BOS", "SFO"]) then pick which airports to
    return; `rank` is the position within that list. Give at most one of the two.
    """
    settings = settings or load_settings()
    preset = preset or settings.scoring["default_preset"]
    weights = signal_weights(settings, preset)
    in_scope = {m.iata: m for m in metrics_list if m.in_scope}
    ranked, not_ranked = {}, []
    for code, m in sorted(in_scope.items()):
        missing = missing_required(m, settings)
        if missing:
            not_ranked.append(_not_ranked(m, missing))
        else:
            ranked[code] = m

    signal_percentiles = {
        name: percentiles(
            {
                code: getattr(m, name).value
                for code, m in ranked.items()
                if getattr(m, name) is not None
            }
        )
        for name in SCORED_SIGNALS
    }
    results = sorted(
        (score_airport(m, signal_percentiles, weights, settings, preset) for m in ranked.values()),
        key=_order,
    )
    results = [dataclasses.replace(r, national_rank=i) for i, r in enumerate(results, 1)]

    wanted = _wanted_codes(in_scope, region, codes)
    if wanted is not None:
        results = [r for r in results if r.code in wanted]
        not_ranked = [n for n in not_ranked if n.code in wanted]
    return Ranking([dataclasses.replace(r, rank=i) for i, r in enumerate(results, 1)], not_ranked)


def _wanted_codes(in_scope, region, codes):
    """The codes a region or code list asks for (None = all). Raises UnknownPlaceError."""
    if region is not None and codes is not None:
        raise ValueError("give a region or a list of codes, not both")
    if region is not None:
        found = resolve_place(region, {code: m.state for code, m in in_scope.items()})
        if not found:
            raise UnknownPlaceError(
                f"Unknown region {region!r}; known regions: {', '.join(sorted(REGIONS))}"
            )
        return set(found)
    if codes is not None:
        wanted = {code.strip().upper() for code in codes if code.strip()}
        unknown = sorted(wanted - set(in_scope))
        if unknown:
            raise UnknownPlaceError(
                f"Not ranked: {', '.join(unknown)} (not a lower-48 airport in DOT Table 1a, D11)"
            )
        return wanted
    return None


# --- Command line ---------------------------------------------------------------------------


def format_table(results, settings, preset, total, not_ranked=()):
    """A plain-text table: rank, airport, score, each signal's points, friction, confidence.

    `not_ranked` (NotRanked objects) are listed below the table with their reasons.
    """
    weights = signal_weights(settings, preset)
    lines = [
        f"Preset: {preset} ("
        + ", ".join(f"{LABELS[n]} {weights[n] * 100:g}%" for n in SCORED_SIGNALS)
        + f"). National rank is out of {total} ranked airports.",
        "",
        f"{'#':>3} {'Natl':>4}  {'Airport':<34} {'Score':>5}  "
        + "  ".join(f"{LABELS[n][:6]:>6}" for n in SCORED_SIGNALS)
        + f"  {'Friction':<20} Confidence",
    ]
    notes = []
    for r in results:
        points = "  ".join(
            f"{s.contribution:6.1f}" if s.metric is not None else f"{'-':>6}" for s in r.signals
        )
        friction = (
            "none" if r.friction is NO_FRICTION else f"-{r.friction.points:g} {r.friction.name}"
        )
        lines.append(
            f"{r.rank:>3} {r.national_rank:>4}  {(r.code + ' ' + r.name)[:34]:<34} "
            f"{r.score:5.1f}  {points}  {friction[:20]:<20} {r.confidence}"
        )
        if r.confidence_reasons:
            notes.append(f"  {r.code}: " + "; ".join(r.confidence_reasons))
    lines.append("")
    lines.append(
        "Signal columns: points each signal added (percentile × weight); score = their sum "
        "minus friction, never below 0. '-' = missing."
    )
    if notes:
        lines.append("Low confidence:")
        lines.extend(notes)
    if not_ranked:
        lines.append("Not ranked: " + ", ".join(f"{n.code} ({n.reason})" for n in not_ranked) + ".")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m airport_agent.scoring",
        description="Rank airports for terminal expansion from the local data cache.",
    )
    parser.add_argument("--preset", help="balanced (default), growth-focused, congestion-focused")
    place = parser.add_mutually_exclusive_group()
    place.add_argument("--region", help='a named region, e.g. "New England" or "LA area"')
    place.add_argument("--codes", help="airport codes separated by commas, e.g. BOS,SFO")
    parser.add_argument("--top", type=int, help="show only the first N rows")
    args = parser.parse_args(argv)

    try:
        metrics_list = all_airport_metrics()
    except CacheMissingError as error:
        print(f"No data built yet ({error}). Build it with: {BUILD_COMMAND}", file=sys.stderr)
        return 1
    settings = load_settings()
    preset = args.preset or settings.scoring["default_preset"]
    codes = args.codes.split(",") if args.codes else None
    try:
        results = rank(metrics_list, preset, region=args.region, codes=codes, settings=settings)
    except UnknownPlaceError as error:
        print(error, file=sys.stderr)
        return 2
    total = sum(1 for m in metrics_list if m.in_scope and not missing_required(m, settings))
    shown = results[: args.top] if args.top else results
    print(format_table(shown, settings, preset, total, results.not_ranked))
    return 0


if __name__ == "__main__":
    sys.exit(main())
