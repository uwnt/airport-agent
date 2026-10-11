"""Named regions, and the rule for names that could mean an airport or a region.

Rule for ambiguous names: a name in REGIONS is the region; otherwise a name in ALIASES is that one
airport; otherwise it is read as an airport code. So "LA" means LAX, the airport, and "LA area"
means the five airports of the Los Angeles region.
"""

REGIONS = {
    # By state: every in-scope airport in these states.
    "new england": {"states": ["CT", "ME", "MA", "NH", "RI", "VT"]},
    # By list: these airports, whatever their state.
    "la area": {"airports": ["LAX", "SNA", "BUR", "LGB", "ONT"]},
}

ALIASES = {"la": "LAX"}


def resolve_place(name, airports):
    """The airport codes a place name means, sorted; [] if the name is not known.

    `airports` maps the IATA codes in scope to their state, e.g. {"BOS": "MA", ...}.
    """
    key = " ".join(name.lower().split())
    region = REGIONS.get(key)
    if region and "states" in region:
        return sorted(code for code, state in airports.items() if state in region["states"])
    if region:
        return sorted(region["airports"])
    code = ALIASES.get(key, key.upper())
    return [code] if code in airports else []
