"""Region names and the rule for ambiguous names."""

from airport_agent.data.regions import resolve_place

IN_SCOPE = {
    "BOS": "MA",
    "BDL": "CT",
    "PVD": "RI",
    "BTV": "VT",
    "LAX": "CA",
    "SNA": "CA",
    "JFK": "NY",
}


def test_new_england_is_every_in_scope_airport_in_its_states():
    assert resolve_place("New England", IN_SCOPE) == ["BDL", "BOS", "BTV", "PVD"]


def test_la_is_the_airport_and_la_area_is_the_region():
    assert resolve_place("LA", IN_SCOPE) == ["LAX"]
    assert resolve_place("la  Area", IN_SCOPE) == ["BUR", "LAX", "LGB", "ONT", "SNA"]


def test_airport_codes_and_unknown_names():
    assert resolve_place("jfk", IN_SCOPE) == ["JFK"]
    assert resolve_place("Atlantis", IN_SCOPE) == []
