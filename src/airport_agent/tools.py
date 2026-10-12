"""The agent's tools: thin, pure wrappers over the data layer and scoring (decision D2).

Each tool returns a small dict that can be turned into JSON. Every number in it carries its
source and as-of date, so the model can quote numbers but never has to compute them. A mistake
(an unknown airport, region or preset, an argument of the wrong type, missing data, or a tool that
breaks) comes back as {"error": "..."}: the model relays it, and no exception leaves `run_tool`.

`TOOL_DECLARATIONS` describes the tools to the model (JSON Schema); `run_tool` runs one by name.
No model and no network here: the tools read only a data snapshot (the latest unless `cache_dir`
is given) and the two settings files.
"""

import datetime
import logging
import math
import re
from pathlib import Path

from airport_agent.data.cache import BUILD_COMMAND, CacheMissingError, load_config
from airport_agent.data.metrics import (
    SIGNALS,
    UnknownAirportError,
    airport_metrics,
    all_airport_metrics,
)
from airport_agent.data.store import open_store, read_manifest, snapshot_problem
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


# In the source tree the notes sit at the repo root; installed as a package (the Docker image),
# they are found from the working folder (/app), like config/scoring.yaml in scoring.py.
_REPO = Path(__file__).resolve().parents[2]


def _notes_path(repo=_REPO):
    in_repo = repo / "docs" / "DOMAIN_NOTES.md"
    return in_repo if in_repo.exists() else Path("docs/DOMAIN_NOTES.md")


DOMAIN_NOTES_PATH = _notes_path()
DEFAULT_TOP = 10  # rows shown when a ranking asks for no region and no codes
FRACTIONS = {
    "cancellation_rate",
    "largest_carrier_share",
    "long_haul_share",
    "bad_weather_capacity_loss",
}
# One dated reading shared by every snapshot (D27): it has no change over time to compare.
NOT_COMPARED = {"bad_weather_capacity_loss"}
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
    airports = {}  # IATA code -> the codes asked for that name it ("BOS", "KBOS")
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


def _snapshot_folders(cache_dir):
    """{version: folder} of every complete snapshot, oldest name first, and the latest version.

    `cache_dir`, if given, is a data store folder (a folder of snapshots), not one snapshot as
    in the other tools; given one snapshot, it says so instead of finding no versions.
    """
    if cache_dir and any(Path(cache_dir).glob("*.json")):  # a store holds only folders
        raise ToolError(
            "compare_over_time needs a folder of data snapshots, not a single snapshot folder"
        )
    store = open_store(f"file://{cache_dir}") if cache_dir else open_store()
    root = store.root
    folders = sorted(p for p in root.iterdir() if p.is_dir()) if root.is_dir() else []
    return {p.name: p for p in folders if snapshot_problem(p) is None}, store.latest()


def _pick_version(version, folders, latest):
    """The version name asked for ("latest" = the newest refresh); ToolError lists the choices."""
    name = latest if version == "latest" else version
    if name in folders:
        return name
    choices = ", ".join([*folders, *(["latest"] if latest else [])]) or "none built"
    raise ToolError(f"no data version {version!r}; available versions: {choices}")


def _standing(m, metrics_list, preset, settings):
    """Score and rank of one airport among all ranked, or why it has none."""
    ranking = rank(metrics_list, preset, settings=settings)
    row = next((r for r in ranking if r.code == m.iata), None)
    if row is None:
        reason = m.scope_reason
        if m.in_scope:
            reason = next(n.reason for n in ranking.not_ranked if n.code == m.iata)
        return {"score": None, "rank": None, "not_ranked": reason}
    return {
        "score": round(row.score, 1),
        "rank": row.rank,
        "ranked_count": _ranked_count(metrics_list, settings),
    }


def _signal_change(name, m_before, m_after, versions):
    """One signal in both snapshots; a side with no value gets a note and no change."""
    old, new = getattr(m_before, name), getattr(m_after, name)
    result = {
        "from": _metric(old, name) if old else None,
        "to": _metric(new, name) if new else None,
    }
    if old is None or new is None:
        result["note"] = "not available for this date; no change computed"
        result["why"] = [
            f"{v}: {m.missing.get(name, 'no value')}"
            for v, m, x in zip(versions, (m_before, m_after), (old, new), strict=True)
            if x is None
        ]
    elif isinstance(old.value, str) or isinstance(new.value, str):  # the largest carrier's name
        result["changed"] = old.value != new.value
    else:
        result["change"] = round(new.value - old.value, 4)
        if name in FRACTIONS:
            result["change_pct_points"] = round((new.value - old.value) * 100, 1)
    return result


def compare_over_time(code, from_version, to_version, preset=None, cache_dir=None, settings=None):
    """One airport's signals, score and rank in two data snapshots, with each signal's change."""
    folders, latest = _snapshot_folders(cache_dir)
    versions = [_pick_version(v, folders, latest) for v in (from_version, to_version)]
    if versions[0] == versions[1]:
        raise ToolError(f"give two different versions to compare; both are {versions[0]!r}")
    settings = settings or load_settings()
    preset = preset or settings.scoring["default_preset"]
    found = {}
    for version in versions:
        try:
            found[version] = airport_metrics(code, folders[version])
        except UnknownAirportError as error:
            found[version] = error
    missing = [v for v in versions if isinstance(found[v], UnknownAirportError)]
    if len(missing) == 2:
        raise ToolError(f"{code!r} is in neither data version: {found[missing[0]]}")
    if missing:
        raise ToolError(f"{code!r} is not in the {missing[0]} data: {found[missing[0]]}")
    standing = [
        _standing(found[v], all_airport_metrics(folders[v]), preset, settings) for v in versions
    ]
    m_before, m_after = (found[v] for v in versions)
    sides = [
        {
            "version": v,
            "as_of": read_manifest(folders[v])["as_of"],
            **st,
        }
        for v, st in zip(versions, standing, strict=True)
    ]
    result = {
        "code": m_after.iata,
        "name": m_after.name,
        "preset": preset,
        "weights_pct": _weights_pct(settings, preset),
        "from": sides[0],
        "to": sides[1],
        "signals": {
            name: _signal_change(name, m_before, m_after, versions)
            for name in SIGNALS
            if name not in NOT_COMPARED
            and (getattr(m_before, name) is not None or getattr(m_after, name) is not None)
        },
        "note": (
            "score and rank use today's settings in both snapshots; rank is among the airports "
            "ranked in that snapshot; change = to minus from"
        ),
    }
    if standing[0]["score"] is not None and standing[1]["score"] is not None:
        result["score_change"] = round(standing[1]["score"] - standing[0]["score"], 1)
    return result


def _stale_note(review_by):
    return f"may be out of date: due for re-check on {review_by}"


def domain_facts(code, path=DOMAIN_NOTES_PATH, today=None):
    """Verified (✅) facts from docs/DOMAIN_NOTES.md whose claim names this airport code.

    Each fact carries `checked` and `review_by` (ISO dates). After `review_by` (`today` defaults
    to the real date) it is also marked `stale` with a note; it is still returned.
    """
    today = today or datetime.date.today()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    facts = []
    for cells, checked, review_by in verified_rows(text):
        # Drop the "(The ... is dropped)" asides: they name figures that failed the check.
        claim = re.sub(r"\s*\(The [^)]*dropped\)", "", cells[1].replace("**", ""))
        if re.search(rf"\b{re.escape(code)}\b", claim):
            fact = {
                "note": int(cells[0]),
                "fact": claim,
                "sources": re.findall(r"\]\((https?://[^)\s]+)\)", cells[4]),
                "checked": checked.isoformat(),
                "review_by": review_by.isoformat(),
            }
            if review_by < today:
                fact["stale"] = True
                fact["stale_note"] = _stale_note(review_by.isoformat())
            facts.append(fact)
    return facts


def verified_rows(text):
    """(cells, checked, review_by) for each verified (✅) row of the notes table.

    A verified row without both dates, or in the old six-column shape, raises ToolError naming
    the row, so a mistake in the notes shows up instead of the fact silently disappearing.
    """
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells[0].isdigit() or not any(c.startswith("✅") for c in cells[5:6]):
            continue
        where = f"docs/DOMAIN_NOTES.md note {cells[0]}"
        if len(cells) != 8:
            raise ToolError(f"{where}: needs the Checked and Review by columns")
        try:
            checked, review_by = (datetime.date.fromisoformat(c) for c in cells[6:8])
        except ValueError:
            raise ToolError(
                f"{where}: Checked and Review by must be dates like 2026-10-11, "
                f"found {cells[6]!r} and {cells[7]!r}"
            ) from None
        if review_by < checked:
            raise ToolError(f"{where}: Review by {review_by} is before Checked {checked}")
        yield cells, checked, review_by


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


# --- What the model sees, and the dispatcher ------------------------------------------------

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

TOOL_DECLARATIONS = [
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

TOOLS = {
    "rank_airports": rank_airports,
    "compare_airports": compare_airports,
    "airport_profile": airport_profile,
    "long_haul_share": long_haul_share,
    "compare_over_time": compare_over_time,
    "demand_pressure": demand_pressure,
}


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
