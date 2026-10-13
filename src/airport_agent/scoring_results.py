"""What scoring returns: an airport's score, its signals and frictions, and the not-ranked.

Plain frozen dataclasses, apart from the math in scoring.py, so a reader of a result (the tools,
the command line) sees every field in one place.
"""

import datetime
from dataclasses import dataclass

from airport_agent.data.metrics import Metric

NONE_ON_FILE = "none on file"


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
    checked: datetime.date | None = None  # when the fact was verified against its source
    review_by: datetime.date | None = None  # when it must be re-checked
    stale: bool = False  # review_by has passed; the penalty still applies


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
