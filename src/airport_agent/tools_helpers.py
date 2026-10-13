"""Helpers the tools share: their error, and turning metrics and scores into plain dicts.

Every number a tool returns goes through `_metric`, so each one carries its source and as-of
date the same way, whichever tool returned it.
"""

import re

from airport_agent.data.metrics import (
    UnknownAirportError,
    airport_metrics,
    all_airport_metrics,
)
from airport_agent.scoring import (
    LABELS,
    NO_FRICTION,
    SCORED_SIGNALS,
    load_settings,
    missing_required,
    signal_weights,
)

FRACTIONS = {
    "cancellation_rate",
    "largest_carrier_share",
    "long_haul_share",
    "bad_weather_capacity_loss",
}


class ToolError(ValueError):
    """A request a tool can't answer, said in one plain sentence."""


def _metric(metric, name=None):
    """A Metric as a dict; a share also gets `value_pct`, worked out here so the model needn't."""
    result = {
        "value": metric.value,
        "unit": metric.unit,
        "source": metric.source,
        "as_of": metric.as_of,
    }
    if name in FRACTIONS:
        result["value_pct"] = round(metric.value * 100, 1)
    if metric.note:
        result["note"] = metric.note
    return result


def _context(cache_dir, settings):
    settings = settings or load_settings()
    return all_airport_metrics(cache_dir), settings


def _ranked_count(metrics_list, settings):
    return sum(1 for m in metrics_list if m.in_scope and not missing_required(m, settings))


def _weights_pct(settings, preset):
    weights = signal_weights(settings, preset)
    return {LABELS[name]: round(weights[name] * 100, 1) for name in SCORED_SIGNALS}


def _row(result):
    signals = {}
    for s in result.signals:
        if s.metric is None:
            signals[s.label] = {"missing": s.missing or "no value"}
        else:
            signals[s.label] = {
                "points": round(s.contribution, 1),
                # Whole numbers read naturally ("61st"); "61.2th" did not. Points use the exact one.
                "percentile": round(s.percentile),
                "weight_pct": round(s.weight * 100, 1),
                **_metric(s.metric, s.name),
            }
    friction = {"name": result.friction.name, "points": result.friction.points}
    if result.friction is not NO_FRICTION:
        friction |= {
            "tier": result.friction.tier,
            "description": result.friction.description,
            "sources": list(result.friction.sources),
            "checked": result.friction.checked.isoformat(),
            "review_by": result.friction.review_by.isoformat(),
        }
        if result.friction.stale:
            friction["stale"] = True
            friction["stale_note"] = _stale_note(result.friction.review_by.isoformat())
    row = {
        "code": result.code,
        "name": result.name,
        "state": result.state,
        "rank": result.rank,
        "national_rank": result.national_rank,
        "score": round(result.score, 1),
        "score_before_friction": round(result.pre_friction_score, 1),
        "signals": signals,
        "friction": friction,
        "confidence": result.confidence,
    }
    if result.friction_not_counted:
        row["friction_not_counted"] = [
            f"{f.name} ({f.tier}, {f.points:g} points; only the largest penalty counts)"
            + (f"; {_stale_note(f.review_by.isoformat())}" if f.stale else "")
            for f in result.friction_not_counted
        ]
    if result.confidence_reasons:
        row["confidence_reasons"] = list(result.confidence_reasons)
    return row


def _split_codes(codes, cache_dir):
    """(in-scope IATA codes, not-ranked entries) for the codes asked for.

    An ICAO code ("KSFO") becomes its IATA code. An airport outside the ranked scope (D11), such
    as Anchorage, goes to not-ranked with the reason. An unknown code raises ToolError.
    """
    if isinstance(codes, str):
        codes = re.split(r"[,\s]+", codes)
    wanted, not_ranked = [], []
    for code in codes:
        if not str(code).strip():
            continue
        try:
            m = airport_metrics(code, cache_dir)
        except UnknownAirportError as error:
            raise ToolError(str(error)) from None
        if m.in_scope:
            if m.iata not in wanted:
                wanted.append(m.iata)
        else:
            not_ranked.append({"code": m.iata, "name": m.name, "reason": m.scope_reason})
    if not wanted and not not_ranked:
        raise ToolError("no airport code given; give one or more codes such as BOS or KSFO")
    return wanted, not_ranked


def _stale_note(review_by):
    return f"may be out of date: due for re-check on {review_by}"
