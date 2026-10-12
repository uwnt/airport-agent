"""FAA runway capacity in bad weather, from Table 1 of "Airport Capacity Profiles" (2014).

Unlike the other sources this is a committed reference table (data/faa_capacity_profiles.yaml,
typed in by hand from the report): nothing is fetched and it is not part of a snapshot. It is valid
for every snapshot, since it was published before the oldest one. Shown only, never scored (D27).
"""

from pathlib import Path

import yaml

SOURCE = "FAA, Airport Capacity Profiles (2014), Table 1"
URL = "https://www.faa.gov/sites/faa.gov/files/airports/planning_capacity/profiles/Airport-Capacity-Profiles-2014.pdf"
# In the source tree the file sits at the repo root; installed as a package (the Docker image),
# it is found from the working folder (/app), like config/sources.yaml in cache.py.
_IN_REPO = Path(__file__).resolve().parents[3] / "data" / "faa_capacity_profiles.yaml"
PATH = _IN_REPO if _IN_REPO.exists() else Path("data/faa_capacity_profiles.yaml")
WEATHER = ("visual", "marginal", "instrument")


def _range(ranges, iata, weather):
    """The overall (low, high) of one weather condition's [low, high] ranges."""
    try:
        if not ranges or any(len(r) != 2 or r[0] > r[1] or r[0] <= 0 for r in ranges):
            raise ValueError("expected a list of [low, high] ranges")
        return min(r[0] for r in ranges), max(r[1] for r in ranges)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{iata}: bad {weather} ranges: {error}") from None


def summarise(table):
    """{iata: {"visual": (low, high), "instrument": (low, high), "loss": share lost}}.

    The loss is 1 - instrument midpoint / visual midpoint, where a midpoint is halfway between the
    lowest and highest rate listed for that weather. Raises ValueError naming the airport.
    """
    result = {}
    for iata, entry in table.items():
        if not isinstance(entry, dict) or not all(w in entry for w in WEATHER):
            raise ValueError(f"{iata}: needs visual, marginal and instrument ranges")
        found = {w: _range(entry[w], iata, w) for w in WEATHER}
        visual, instrument = found["visual"], found["instrument"]
        result[iata] = {
            "visual": visual,
            "instrument": instrument,
            "loss": 1 - sum(instrument) / sum(visual),
        }
    return result


def load(path=PATH):
    """Read the reference file and summarise it."""
    with open(path, encoding="utf-8") as f:
        return summarise(yaml.safe_load(f))
