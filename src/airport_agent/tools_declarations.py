"""What the model sees: each tool's declaration (JSON Schema), and the check of what it sends.

`run_tool` in tools.py checks every call against these declarations before running a tool, so
an argument the model was not told about, or one of the wrong type, comes back as a plain error.
"""

import math
from typing import Any

_PRESET = {
    "type": "string",
    "enum": ["balanced", "growth-focused", "congestion-focused"],
    "description": "Weighting preset; balanced unless the user asks for another.",
}
_CODE = {"type": "string", "description": "IATA or ICAO airport code, e.g. SFO or KSFO."}
_VERSION = {
    "type": "string",
    "description": "Data snapshot version, e.g. 2019-12, 2021-12, or latest.",
}
_CODES = {"type": "array", "items": {"type": "string"}, "description": "IATA airport codes."}

TOOL_DECLARATIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "rank_airports",
        "description": (
            "Rank US airports for terminal expansion: score 0-100, national_rank (out of "
            "ranked_count airports ranked nationally), each "
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
                "top": {"type": "integer", "description": "Show only the first N rows (N >= 1)."},
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
        "name": "compare_over_time",
        "description": (
            "How one airport changed between two data snapshots: each signal's value in both "
            "(with source and date) and its change, plus score and rank in each. Versions are "
            "'2019-12', '2021-12' or 'latest'; an unknown version returns the list available. "
            "A signal not measured in one snapshot is flagged, with no change."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "code": _CODE,
                "from_version": _VERSION,
                "to_version": _VERSION,
                "preset": _PRESET,
            },
            "required": ["code", "from_version", "to_version"],
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


def _is_text(value):
    return isinstance(value, str)


def _is_codes(value):
    return isinstance(value, str) or (
        isinstance(value, list) and all(isinstance(c, str) for c in value)
    )


def _is_whole(value):
    # The model may send a whole number as 5.0; that counts (run_tool passes it on as 5).
    if isinstance(value, float):
        return value.is_integer()
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value):
    ok = isinstance(value, (int, float)) and not isinstance(value, bool)
    return ok and math.isfinite(value)  # NaN or infinity is not a distance


# What each argument the model may send must be; None (left out) is always allowed.
_ARG_TYPES = {
    "region": (_is_text, "a region name as text"),
    "codes": (_is_codes, "a list of airport codes as text"),
    "code": (_is_text, "an airport code as text"),
    "preset": (_is_text, "a preset name as text"),
    "top": (_is_whole, "a whole number"),
    "from_version": (_is_text, "a data version as text"),
    "to_version": (_is_text, "a data version as text"),
    "threshold_miles": (_is_number, "a number"),
}


_DECLARED = {d["name"]: set(d["parameters"]["properties"]) for d in TOOL_DECLARATIONS}


def _bad_argument(name, args):
    """A plain message for the first argument of the wrong type, or None if all are fine."""
    if not isinstance(args, dict):
        return f"bad arguments for {name}: expected named arguments, got {type(args).__name__}"
    declared = _DECLARED.get(name, set())  # what the model was told it may send
    unknown = sorted(set(args) - declared)
    if unknown:
        allowed = ", ".join(sorted(declared))
        return f"bad arguments for {name}: unknown {', '.join(unknown)}; allowed: {allowed}"
    for arg, value in args.items():
        check = _ARG_TYPES.get(arg)
        if value is None or check is None:
            continue
        is_ok, wanted = check
        if not is_ok(value):
            return f"bad arguments for {name}: {arg} must be {wanted}, got {value!r}"
    return None
