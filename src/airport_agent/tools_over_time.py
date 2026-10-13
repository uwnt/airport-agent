"""The compare_over_time tool: one airport in two data snapshots, signal by signal.

Apart from the other tools because it alone reads several snapshots from a data store folder;
the others read one snapshot.
"""

from pathlib import Path

from airport_agent.data.metrics import (
    SIGNALS,
    UnknownAirportError,
    airport_metrics,
    all_airport_metrics,
)
from airport_agent.data.store import open_store, read_manifest, snapshot_problem
from airport_agent.scoring import (
    load_settings,
    rank,
)
from airport_agent.tools_helpers import (
    FRACTIONS,
    ToolError,
    _metric,
    _ranked_count,
    _weights_pct,
)

# One dated reading shared by every snapshot (D27): it has no change over time to compare.
NOT_COMPARED = {"bad_weather_capacity_loss"}


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
