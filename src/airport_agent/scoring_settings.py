"""Scoring settings: read and check config/scoring.yaml and data/constraints.yaml.

Kept apart from the math in scoring.py so a mistake in either file is caught in one place and
said in one plain sentence naming the file and key. Reading the two files is the only I/O in
scoring; the checks are pure.
"""

import datetime
from dataclasses import dataclass
from pathlib import Path

import yaml

_REPO = Path(__file__).resolve().parents[2]


# In the source tree the files sit at the repo root; installed as a package (the Docker image),
# they are found from the working folder (/app), like config/sources.yaml in data/cache.py.
def _settings_root(repo):
    """`repo` when config/scoring.yaml is there (source tree), else the working folder."""
    return repo if (repo / "config" / "scoring.yaml").exists() else Path()


SCORING_PATH = _settings_root(_REPO) / "config" / "scoring.yaml"
CONSTRAINTS_PATH = _settings_root(_REPO) / "data" / "constraints.yaml"

STRAIN_SIGNALS = ("nas_delay_per_landed_flight", "cancellation_rate", "fare_premium")
GROWTH_SIGNAL = "growth_vs_2019"
SCORED_SIGNALS = (*STRAIN_SIGNALS, GROWTH_SIGNAL)
SCORING_FILE = "config/scoring.yaml"
CONSTRAINTS_FILE = "data/constraints.yaml"
SCORING_KEYS = (
    "default_preset",
    "presets",
    "strain_mix",
    "required_signals",
    "low_confidence_min_markets",
    "friction_points",
)
PRESET_KEYS = ("strain", "growth")
FRICTION_TIERS = ("minor", "major", "hard_cap")


class SettingsError(ValueError):
    """A mistake in config/scoring.yaml or data/constraints.yaml, said in one plain sentence."""


@dataclass(frozen=True)
class Settings:
    """What config/scoring.yaml and data/constraints.yaml say, read once."""

    scoring: dict
    constraints: dict


# --- Reading the two YAML files (the only I/O) ---------------------------------------------


def load_settings(scoring_path=SCORING_PATH, constraints_path=CONSTRAINTS_PATH):
    """Read config/scoring.yaml and data/constraints.yaml; a mistake raises SettingsError."""
    scoring = _read_yaml(scoring_path, SCORING_FILE)
    constraints = _read_yaml(constraints_path, CONSTRAINTS_FILE) or {}
    validate_settings(scoring, constraints)
    return Settings(scoring, constraints)


def _read_yaml(path, label):
    with open(path, encoding="utf-8") as f:
        try:
            return yaml.safe_load(f)
        except yaml.YAMLError as error:
            first_line = str(error).splitlines()[0]
            raise SettingsError(f"{label} is not valid YAML ({first_line})") from None


# --- Checking the settings (pure) -----------------------------------------------------------


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _check_keys(where, mapping, allowed):
    """`mapping` must be a mapping with exactly the `allowed` keys."""
    if not isinstance(mapping, dict):
        raise SettingsError(f"{where} must be a set of keys: {', '.join(allowed)}")
    unknown = sorted(str(key) for key in mapping if key not in allowed)
    if unknown:
        raise SettingsError(
            f"{where} has unknown key(s) {', '.join(unknown)}; allowed: {', '.join(allowed)}"
        )
    missing = [key for key in allowed if key not in mapping]
    if missing:
        raise SettingsError(
            f"{where} is missing {', '.join(missing)}; it needs: {', '.join(allowed)}"
        )


def _check_number(where, key, value):
    if not _is_number(value) or value < 0:
        raise SettingsError(f"{where}: {key} must be a number 0 or more, not {value!r}")


def _check_shares(where, mapping, allowed):
    """Exactly the `allowed` keys, each a number 0 or more, not all 0."""
    _check_keys(where, mapping, allowed)
    for key, value in mapping.items():
        _check_number(where, key, value)
    if sum(mapping.values()) <= 0:
        raise SettingsError(f"{where}: at least one of {', '.join(allowed)} must be more than 0")


def validate_settings(scoring, constraints):
    """Check both settings files; the first mistake raises SettingsError naming file and key.

    Airport codes in data/constraints.yaml are checked by `rank`, against the airports it gets.
    """
    _check_keys(SCORING_FILE, scoring, SCORING_KEYS)
    presets = scoring["presets"]
    if not isinstance(presets, dict) or not presets:
        raise SettingsError(f"{SCORING_FILE}: presets must list at least one preset")
    for name, split in presets.items():
        _check_shares(f"{SCORING_FILE}: presets: {name}", split, PRESET_KEYS)
    if scoring["default_preset"] not in presets:
        raise SettingsError(
            f"{SCORING_FILE}: default_preset {scoring['default_preset']!r} is not a preset; "
            f"choose one of: {', '.join(sorted(map(str, presets)))}"
        )
    _check_shares(f"{SCORING_FILE}: strain_mix", scoring["strain_mix"], STRAIN_SIGNALS)
    required = scoring["required_signals"]
    if not isinstance(required, list):
        raise SettingsError(
            f"{SCORING_FILE}: required_signals must be a list (one '- name' per line) of: "
            f"{', '.join(SCORED_SIGNALS)}; found {required!r}"
        )
    unknown = [str(name) for name in required if name not in SCORED_SIGNALS]
    if unknown:
        raise SettingsError(
            f"{SCORING_FILE}: required_signals has unknown signal(s) {', '.join(unknown)}; "
            f"allowed: {', '.join(SCORED_SIGNALS)}"
        )
    threshold = scoring["low_confidence_min_markets"]
    if not isinstance(threshold, int) or isinstance(threshold, bool) or threshold < 0:
        raise SettingsError(
            f"{SCORING_FILE}: low_confidence_min_markets must be a whole number 0 or more, "
            f"not {threshold!r}"
        )
    points = scoring["friction_points"]
    _check_keys(f"{SCORING_FILE}: friction_points", points, FRICTION_TIERS)
    for tier, value in points.items():
        _check_number(f"{SCORING_FILE}: friction_points", tier, value)
    _check_constraints(constraints)


def _check_constraints(constraints):
    if not isinstance(constraints, dict):
        raise SettingsError(f"{CONSTRAINTS_FILE} must list airport codes, each with constraints")
    for code, entries in constraints.items():
        where = f"{CONSTRAINTS_FILE}: {code}"
        if not isinstance(entries, list) or not entries:
            raise SettingsError(f"{where} must be a list of constraints (each starting with '- ')")
        for entry in entries:
            if not isinstance(entry, dict):
                raise SettingsError(
                    f"{where}: each constraint needs name, tier, description and sources"
                )
            name = entry.get("name")
            if not isinstance(name, str) or not name.strip():
                raise SettingsError(f"{where}: a constraint has no name")
            if entry.get("tier") not in FRICTION_TIERS:
                raise SettingsError(
                    f"{where}: {name}: tier {entry.get('tier')!r} is not one of: "
                    f"{', '.join(FRICTION_TIERS)}"
                )
            description = entry.get("description")
            if not isinstance(description, str) or not description.strip():
                raise SettingsError(f"{where}: {name}: description is missing")
            sources = entry.get("sources")
            if not isinstance(sources, list) or not sources:
                raise SettingsError(f"{where}: {name}: sources must list at least one link")
            if not all(isinstance(link, str) and link.strip() for link in sources):
                raise SettingsError(f"{where}: {name}: every source must be a link")
            notes = entry.get("domain_notes", [])
            if not isinstance(notes, list) or not all(_is_number(n) for n in notes):
                raise SettingsError(f"{where}: {name}: domain_notes must be a list of numbers")
            checked = _check_date(f"{where}: {name}", "checked", entry)
            review_by = _check_date(f"{where}: {name}", "review_by", entry)
            if review_by < checked:
                raise SettingsError(f"{where}: {name}: review_by is before checked")


def _check_date(where, key, entry):
    """A date written as YYYY-MM-DD (YAML may already have turned it into a date)."""
    value = entry.get(key)
    if isinstance(value, datetime.datetime):
        value = None
    elif isinstance(value, str):
        try:
            value = datetime.date.fromisoformat(value)
        except ValueError:
            value = None
    if not isinstance(value, datetime.date):
        raise SettingsError(f"{where}: {key} must be a date written like 2026-10-11")
    return value


def _constraints_by_code(metrics_list, constraints):
    """data/constraints.yaml keyed by IATA code.

    A key may be an IATA or ICAO code in any case ("sna", "KSNA"). One that names no airport in
    `metrics_list` raises SettingsError, so a typo never drops a penalty silently.
    """
    aliases = {}
    for m in metrics_list:
        aliases[m.iata.upper()] = m.iata
        if m.icao:
            aliases[m.icao.upper()] = m.iata
    result = {}
    for key, entries in constraints.items():
        code = aliases.get(str(key).strip().upper())
        if code is None:
            raise SettingsError(
                f"{CONSTRAINTS_FILE}: {key} is not the code of any airport being ranked; "
                "use the airport's IATA code, e.g. SNA"
            )
        if code in result:
            raise SettingsError(
                f"{CONSTRAINTS_FILE}: {key} is {code} again; list all of {code}'s constraints "
                "under one code"
            )
        result[code] = entries
    return result
