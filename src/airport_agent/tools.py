"""The agent's tools: thin, pure wrappers over the data layer and scoring (decision D2).

Each tool returns a small dict that can be turned into JSON. Every number in it carries its
source and as-of date, so the model can quote numbers but never has to compute them. A mistake
(an unknown airport, region or preset, an argument of the wrong type, missing data, or a tool that
breaks) comes back as {"error": "..."}: the model relays it, and no exception leaves `run_tool`.

`TOOL_DECLARATIONS` describes the tools to the model (JSON Schema); `run_tool` runs one by name.
No model and no network here: the tools read only a data snapshot (the latest unless `cache_dir`
is given) and the two settings files.
"""

import logging
import re
from pathlib import Path

from airport_agent.data.cache import BUILD_COMMAND, CacheMissingError, load_config
from airport_agent.data.metrics import (
    SIGNALS,
    UnknownAirportError,
    airport_metrics,
    all_airport_metrics,
)
from airport_agent.scoring import (
    LABELS,
    NO_FRICTION,
    SCORED_SIGNALS,
    STRAIN_SIGNALS,
    SettingsError,
    UnknownPlaceError,
    load_settings,
    missing_required,
    rank,
    signal_weights,
)

log = logging.getLogger(__name__)

DOMAIN_NOTES_PATH = Path(__file__).resolve().parents[2] / "docs" / "DOMAIN_NOTES.md"
DEFAULT_TOP = 10  # rows shown when a ranking asks for no region and no codes
FRACTIONS = {"cancellation_rate", "largest_carrier_share", "long_haul_share"}
TOP_QUARTILE = 75
BOTTOM_QUARTILE = 25


class ToolError(ValueError):
    """A request a tool can't answer, said in one plain sentence."""


# --- Small helpers --------------------------------------------------------------------------


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


def _plain(text):
    """Text without internal decision labels: "(AK, D11)" -> "(AK)"; the model would copy them."""
    if not text:
        return text
    return re.sub(r"\s*\(D\d+\)", "", re.sub(r",\s*D\d+\b", "", text))


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
                "percentile": round(s.percentile, 1),
                "weight_pct": round(s.weight * 100, 1),
                **_metric(s.metric, s.name),
            }
    friction = {"name": result.friction.name, "points": result.friction.points}
    if result.friction is not NO_FRICTION:
        friction |= {
            "tier": result.friction.tier,
            "description": result.friction.description,
            "sources": list(result.friction.sources),
        }
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
            not_ranked.append({"code": m.iata, "name": m.name, "reason": _plain(m.scope_reason)})
    return wanted, not_ranked


# --- The tools ------------------------------------------------------------------------------


def rank_airports(region=None, codes=None, preset=None, top=None, cache_dir=None, settings=None):
    """Rank airports for terminal expansion, nationally, in a region, or among some codes."""
    if region and codes:
        raise ToolError("give a region or a list of airport codes, not both")
    metrics_list, settings = _context(cache_dir, settings)
    preset = preset or settings.scoring["default_preset"]
    outside = []
    if codes:
        codes, outside = _split_codes(codes, cache_dir)
        if not codes:
            return {
                "preset": preset,
                "rows": [],
                "not_ranked": outside,
                "note": "none of these airports is in the ranked scope",
            }
    ranking = rank(
        metrics_list, preset, region=region or None, codes=codes or None, settings=settings
    )
    if top is None and not region and not codes:
        top = DEFAULT_TOP
    rows = [_row(r) for r in ranking]
    shown = rows[: int(top)] if top else rows
    result = {
        "preset": preset,
        "weights_pct": _weights_pct(settings, preset),
        "ranked_nationally": _ranked_count(metrics_list, settings),
        "region": region,
        "rows": shown,
        "not_ranked": outside
        + [
            {"code": n.code, "name": n.name, "reason": _plain(n.reason)} for n in ranking.not_ranked
        ],
        "method": (
            "score = sum of each signal's percentile (0-100, across all airports ranked "
            "nationally) times its weight, minus the largest friction penalty, never below 0; "
            "settings from config/scoring.yaml"
        ),
    }
    if len(shown) < len(rows):
        result["note"] = f"showing the top {len(shown)} of {len(rows)}"
    return result


def compare_airports(codes, preset=None, cache_dir=None, settings=None):
    """The ranking rows for two or more airports, side by side."""
    if isinstance(codes, str):
        codes = re.split(r"[,\s]+", codes)
    if len([c for c in codes if str(c).strip()]) < 2:
        raise ToolError("compare_airports needs two or more airport codes")
    return rank_airports(codes=codes, preset=preset, cache_dir=cache_dir, settings=settings)


def domain_facts(code, path=DOMAIN_NOTES_PATH):
    """Verified (✅) facts from docs/DOMAIN_NOTES.md whose claim names this airport code."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    facts = []
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 6 or not cells[0].isdigit() or not cells[5].startswith("✅"):
            continue
        # Drop the "(The ... is dropped)" asides: they name figures that failed the check.
        claim = re.sub(r"\s*\(The [^)]*dropped\)", "", cells[1].replace("**", ""))
        if re.search(rf"\b{re.escape(code)}\b", claim):
            facts.append(
                {
                    "note": int(cells[0]),
                    "fact": claim,
                    "sources": re.findall(r"\]\((https?://[^)\s]+)\)", cells[4]),
                }
            )
    return facts


def airport_profile(code, cache_dir=None):
    """Every measured value for one airport, why any is missing, and its verified facts."""
    try:
        m = airport_metrics(code, cache_dir)
    except UnknownAirportError as error:
        raise ToolError(str(error)) from None
    result = {
        "code": m.iata,
        "icao": m.icao,
        "name": m.name,
        "state": m.state,
        "ranked": m.in_scope,
        "scope": _plain(m.scope_reason),
        "metrics": {
            name: _metric(getattr(m, name), name)
            for name in SIGNALS
            if getattr(m, name) is not None
        },
        "missing": dict(m.missing),
        "verified_facts": domain_facts(m.iata),
    }
    if m.code_note:
        result["code_note"] = m.code_note
    return result


def long_haul_share(code, threshold_miles=None, cache_dir=None):
    """Share of passenger departures flying over the configured distance (Anchorage only, D13)."""
    try:
        m = airport_metrics(code, cache_dir)
    except UnknownAirportError as error:
        raise ToolError(str(error)) from None
    configured = load_config()["opensky"]["long_haul_miles"]
    if m.long_haul_share is None:
        return {
            "code": m.iata,
            "name": m.name,
            "available": False,
            "reason": "not available: " + m.missing.get("long_haul_share", "no value"),
        }
    result = {
        "code": m.iata,
        "name": m.name,
        "available": True,
        "threshold_miles": configured,
        "definition": (
            f"passenger-airline departures flying over {configured:,} miles great-circle, "
            "divided by those with a known destination; destinations 100 miles or closer and "
            "same-airport returns dropped"
        ),
        "long_haul_share": _metric(m.long_haul_share, "long_haul_share"),
    }
    if threshold_miles is not None and float(threshold_miles) != configured:
        result["threshold_note"] = (
            f"only the {configured:,}-mile threshold is computed; the stored summary keeps "
            f"counts, not distances, so {float(threshold_miles):,.0f} miles can't be answered "
            "without rebuilding the data"
        )
    return result


def demand_pressure(code, cache_dir=None, settings=None):
    """The strain and growth signals with their national percentiles, and a one-line summary."""
    metrics_list, settings = _context(cache_dir, settings)
    codes, outside = _split_codes([code], cache_dir)
    if outside:
        return {**outside[0], "ranked": False}
    ranking = rank(metrics_list, codes=codes, settings=settings)
    if not ranking:
        n = ranking.not_ranked[0]
        return {"code": n.code, "name": n.name, "ranked": False, "reason": _plain(n.reason)}
    row = ranking[0]
    signals, high, low = {}, [], []
    for s in row.signals:
        group = "strain" if s.name in STRAIN_SIGNALS else "growth"
        if s.metric is None:
            signals[s.label] = {"group": group, "missing": s.missing or "no value"}
            continue
        signals[s.label] = {
            "group": group,
            "percentile": round(s.percentile, 1),
            **_metric(s.metric, s.name),
        }
        if s.percentile >= TOP_QUARTILE:
            high.append(s.label)
        elif s.percentile <= BOTTOM_QUARTILE:
            low.append(s.label)
    parts = [
        f"top quartile nationally: {', '.join(high) if high else 'none'}",
        f"bottom quartile: {', '.join(low) if low else 'none'}",
    ]
    return {
        "code": row.code,
        "name": row.name,
        "ranked": True,
        "ranked_nationally": _ranked_count(metrics_list, settings),
        "signals": signals,
        "friction": _row(row)["friction"],
        "confidence": row.confidence,
        "summary": f"{row.code}: " + "; ".join(parts) + ".",
        "percentile_note": (
            "percentile 100 = highest of all airports ranked nationally; higher means more "
            "strain or more growth"
        ),
    }


# --- What the model sees, and the dispatcher ------------------------------------------------

_PRESET = {
    "type": "string",
    "enum": ["balanced", "growth-focused", "congestion-focused"],
    "description": "Weighting preset; balanced unless the user asks for another.",
}
_CODE = {"type": "string", "description": "IATA or ICAO airport code, e.g. SFO or KSFO."}
_CODES = {"type": "array", "items": {"type": "string"}, "description": "IATA airport codes."}

TOOL_DECLARATIONS = [
    {
        "type": "function",
        "name": "rank_airports",
        "description": (
            "Rank US airports for terminal expansion: score 0-100, national rank, each "
            "signal's points, percentile and measured value with source and date, friction "
            "penalty, confidence. Give a region (e.g. 'New England', 'LA area') or codes, or "
            "neither for the national top list."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "region": {"type": "string", "description": "Named region, e.g. New England."},
                "codes": _CODES,
                "preset": _PRESET,
                "top": {"type": "integer", "description": "Show only the first N rows."},
            },
        },
    },
    {
        "type": "function",
        "name": "compare_airports",
        "description": (
            "Score and compare two or more airports side by side (same fields as rank_airports)."
        ),
        "parameters": {
            "type": "object",
            "properties": {"codes": _CODES, "preset": _PRESET},
            "required": ["codes"],
        },
    },
    {
        "type": "function",
        "name": "airport_profile",
        "description": (
            "Everything measured about one airport (each value with source and date), why "
            "anything is missing, whether it is ranked, and verified domain facts with sources."
        ),
        "parameters": {"type": "object", "properties": {"code": _CODE}, "required": ["code"]},
    },
    {
        "type": "function",
        "name": "long_haul_share",
        "description": (
            "Share of passenger departures that are long-haul (over 1,400 miles). Computed only "
            "for Anchorage (ANC), from a week of OpenSky flights."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "code": _CODE,
                "threshold_miles": {"type": "number", "description": "Only 1400 is computed."},
            },
            "required": ["code"],
        },
    },
    {
        "type": "function",
        "name": "demand_pressure",
        "description": (
            "Signs of unmet demand at one airport: strain (delay, cancellations, fare premium) "
            "and growth since 2019, each with its national percentile, plus a one-line summary."
        ),
        "parameters": {"type": "object", "properties": {"code": _CODE}, "required": ["code"]},
    },
]

TOOLS = {
    "rank_airports": rank_airports,
    "compare_airports": compare_airports,
    "airport_profile": airport_profile,
    "long_haul_share": long_haul_share,
    "demand_pressure": demand_pressure,
}


def _is_text(value):
    return isinstance(value, str)


def _is_codes(value):
    return isinstance(value, str) or (
        isinstance(value, list) and all(isinstance(c, str) for c in value)
    )


def _is_whole(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


# What each argument the model may send must be; None (left out) is always allowed.
_ARG_TYPES = {
    "region": (_is_text, "a region name as text"),
    "codes": (_is_codes, "a list of airport codes as text"),
    "code": (_is_text, "an airport code as text"),
    "preset": (_is_text, "a preset name as text"),
    "top": (_is_whole, "a whole number"),
    "threshold_miles": (_is_number, "a number"),
}


def _bad_argument(name, args):
    """A plain message for the first argument of the wrong type, or None if all are fine."""
    if not isinstance(args, dict):
        return f"bad arguments for {name}: expected named arguments, got {type(args).__name__}"
    for arg, value in args.items():
        check = _ARG_TYPES.get(arg)
        if value is None or check is None:
            continue
        is_ok, wanted = check
        if not is_ok(value):
            return f"bad arguments for {name}: {arg} must be {wanted}, got {value!r}"
    return None


def run_tool(name, args, cache_dir=None):
    """Run a tool by name; any mistake comes back as {"error": "..."}, never as an exception."""
    tool = TOOLS.get(name)
    if tool is None:
        return {"error": f"unknown tool {name!r}; tools: {', '.join(TOOLS)}"}
    args = {} if args is None else args
    problem = _bad_argument(name, args)
    if problem:
        return {"error": problem}
    try:
        return tool(**args, cache_dir=cache_dir)
    except CacheMissingError as error:
        return {"error": f"no data built yet ({error}); build it with: {BUILD_COMMAND}"}
    except (ToolError, UnknownPlaceError, SettingsError, UnknownAirportError) as error:
        return {"error": str(error)}
    except (TypeError, ValueError) as error:
        return {"error": f"bad arguments for {name}: {error}"}
    except Exception as error:  # last line of defence: the model should say the tool failed
        log.exception("tool %s failed", name)
        return {"error": f"the tool {name} failed: {type(error).__name__}: {error}"}
