"""The agent's tools: thin, pure wrappers over the data layer and scoring (decision D2).

Each tool returns a small dict that can be turned into JSON. Every number in it carries its
source and as-of date, so the model can quote numbers but never has to compute them. A mistake
(an unknown airport, region or preset, an argument of the wrong type, missing data, or a tool that
breaks) comes back as {"error": "..."}: the model relays it, and no exception leaves `run_tool`.

`TOOL_DECLARATIONS` describes the tools to the model (JSON Schema, kept in
tools_declarations.py); `run_tool` runs one by name.
No model and no network here: the tools read only a data snapshot (the latest unless `cache_dir`
is given) and the two settings files.
"""

import logging
import re
from collections.abc import Callable
from typing import Any

from airport_agent.data.cache import BUILD_COMMAND, CacheMissingError, load_config
from airport_agent.data.metrics import SIGNALS, UnknownAirportError, airport_metrics
from airport_agent.scoring import STRAIN_SIGNALS, SettingsError, UnknownPlaceError, rank
from airport_agent.tools_declarations import (  # noqa: F401 (callers import it from here)
    TOOL_DECLARATIONS,
    _bad_argument,
)
from airport_agent.tools_domain_notes import (  # noqa: F401 (callers import them from here)
    DOMAIN_NOTES_PATH,
    domain_facts,
    verified_rows,
)
from airport_agent.tools_helpers import (
    ToolError,
    _context,
    _metric,
    _ranked_count,
    _row,
    _split_codes,
    _weights_pct,
)
from airport_agent.tools_over_time import compare_over_time

log = logging.getLogger(__name__)

DEFAULT_TOP = 10  # rows shown when a ranking asks for no region and no codes
TOP_QUARTILE = 75
BOTTOM_QUARTILE = 25


# --- The tools ------------------------------------------------------------------------------


def rank_airports(
    region=None, codes=None, preset=None, top=None, cache_dir=None, settings=None, today=None
):
    """Rank airports for terminal expansion, nationally, in a region, or among some codes."""
    if region and codes:
        raise ToolError("give a region or a list of airport codes, not both")
    if top is not None and top < 1:
        raise ToolError(f"top must be a positive whole number (or left out), not {top}")
    metrics_list, settings = _context(cache_dir, settings)
    preset = preset or settings.scoring["default_preset"]
    outside = []
    if codes is not None:
        codes, outside = _split_codes(codes, cache_dir)
        if not codes:
            return {
                "preset": preset,
                "rows": [],
                "not_ranked": outside,
                "note": "none of these airports is in the ranked scope",
            }
    ranking = rank(
        metrics_list,
        preset,
        region=region or None,
        codes=codes or None,
        settings=settings,
        today=today,
    )
    if top is None and not region and not codes:
        top = DEFAULT_TOP
    rows = [_row(r) for r in ranking]
    shown = rows[:top] if top else rows
    result = {
        "preset": preset,
        "weights_pct": _weights_pct(settings, preset),
        "ranked_count": _ranked_count(metrics_list, settings),
        "region": region,
        "rows": shown,
        "not_ranked": outside
        + [{"code": n.code, "name": n.name, "reason": n.reason} for n in ranking.not_ranked],
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
    airports: dict[
        str, list[str]
    ] = {}  # IATA code -> the codes asked for that name it ("BOS", "KBOS")
    for code in codes:
        if not str(code).strip():
            continue
        try:
            iata = airport_metrics(code, cache_dir).iata
        except UnknownAirportError as error:
            raise ToolError(str(error)) from None
        airports.setdefault(iata, []).append(str(code).strip())
    if len(airports) < 2:
        same = [
            f"{' and '.join(asked)} are the same airport ({iata})"
            for iata, asked in airports.items()
            if len(asked) > 1
        ]
        reason = f" ({'; '.join(same)})" if same else ""
        raise ToolError(f"compare_airports needs two or more different airports{reason}")
    return rank_airports(codes=codes, preset=preset, cache_dir=cache_dir, settings=settings)


def airport_profile(code, cache_dir=None, today=None):
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
        "scope": m.scope_reason,
        "metrics": {
            name: _metric(getattr(m, name), name)
            for name in SIGNALS
            if getattr(m, name) is not None
        },
        "missing": dict(m.missing),
        "verified_facts": domain_facts(m.iata, today=today),
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
        return {"code": n.code, "name": n.name, "ranked": False, "reason": n.reason}
    row = ranking[0]
    signals, high, low = {}, [], []
    for s in row.signals:
        group = "strain" if s.name in STRAIN_SIGNALS else "growth"
        if s.metric is None:
            signals[s.label] = {"group": group, "missing": s.missing or "no value"}
            continue
        percentile = round(s.percentile)  # as shown, so the summary agrees with it
        signals[s.label] = {"group": group, "percentile": percentile, **_metric(s.metric, s.name)}
        if percentile >= TOP_QUARTILE:
            high.append(s.label)
        elif percentile <= BOTTOM_QUARTILE:
            low.append(s.label)
    parts = [
        f"top quartile nationally: {', '.join(high) if high else 'none'}",
        f"bottom quartile: {', '.join(low) if low else 'none'}",
    ]
    return {
        "code": row.code,
        "name": row.name,
        "ranked": True,
        "ranked_count": _ranked_count(metrics_list, settings),
        "signals": signals,
        "friction": _row(row)["friction"],
        "confidence": row.confidence,
        "summary": f"{row.code}: " + "; ".join(parts) + ".",
        "percentile_note": (
            "percentile 100 = highest of the ranked_count airports ranked nationally; higher "
            "means more strain or more growth. ranked_count is how many airports are ranked, "
            "not this airport's rank: this tool gives no rank (rank_airports gives national_rank)"
        ),
    }


# --- The dispatcher -------------------------------------------------------------------------

TOOLS: dict[str, Callable[..., Any]] = {
    "rank_airports": rank_airports,
    "compare_airports": compare_airports,
    "airport_profile": airport_profile,
    "long_haul_share": long_haul_share,
    "compare_over_time": compare_over_time,
    "demand_pressure": demand_pressure,
}


def run_tool(name, args, cache_dir=None):
    """Run a tool by name; any mistake comes back as {"error": "..."}, never as an exception."""
    tool = TOOLS.get(name)
    if tool is None:
        return {"error": f"unknown tool {name!r}; tools: {', '.join(TOOLS)}"}
    args = {} if args is None else args
    problem = _bad_argument(name, args)
    if problem:
        return {"error": problem}
    if isinstance(args.get("top"), float):
        args = {**args, "top": int(args["top"])}
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
