"""The number check: numbers stated in an answer, and which of them no tool result gave."""

from airport_agent.number_check import numbers_in, unsupported_numbers


def texts(found):
    return [n.text for n in found]


def test_finds_whole_numbers_decimals_commas_percents_and_points():
    found = numbers_in("BOS scores 72.4 with 1,234 flights; cancellations 2.1% (up 0.4 pp).")
    assert texts(found) == ["72.4", "1,234", "2.1%", "0.4 pp"]
    assert [(n.value, n.decimals, n.unit) for n in found] == [
        (72.4, 1, ""),
        (1234.0, 0, ""),
        (2.1, 1, "%"),
        (0.4, 1, "pp"),
    ]


def test_skips_dates_years_list_markers_and_digits_inside_codes():
    answer = (
        "1. BOS leads (as of 2026-07, checked 2026-10-11).\n"
        "2) Since 2019 KSFO and A320 traffic grew 5 points."
    )
    assert texts(numbers_in(answer)) == ["5"]


def test_a_year_with_a_unit_or_out_of_range_is_a_number():
    assert texts(numbers_in("2019% and 2050 and 1,999")) == ["2019%", "2050", "1,999"]


def test_minus_signs_and_runway_letters():
    found = numbers_in("change −1.2 pp; runway 28L; delay -3.5 min")
    assert [n.value for n in found] == [1.2, 28.0, 3.5]


def test_rounded_numbers_match_the_tool_number():
    result = {"score": 12.83, "rank": 3}
    assert unsupported_numbers("Score 12.8, about 13, rank 3.", result) == []
    assert texts(unsupported_numbers("Score 12.9.", result)) == ["12.9"]


def test_a_percent_matches_a_share_given_as_a_fraction():
    share = {"value": 0.1283, "unit": "share"}
    assert unsupported_numbers("12.8% of departures", share) == []
    # A plain number does not get the times-100 allowance.
    assert texts(unsupported_numbers("12.8 of departures", share)) == ["12.8"]


def test_a_signed_change_matches_a_stated_size():
    change = {"change_pct_points": -1.2, "change": -0.012}
    assert unsupported_numbers("Cancellations fell 1.2 pp.", change) == []


def test_numbers_inside_tool_text_count():
    results = [
        {"definition": "departures flying over 1,400 miles"},
        {"verified_facts": [{"note": 6, "fact": "runways 750 ft apart"}]},
    ]
    assert unsupported_numbers("Over 1,400 miles; 750 ft apart (note 6).", results) == []


def test_invented_numbers_are_flagged_once_each_in_order():
    results = [{"score": 55.0}]
    answer = "ROI of 14% and $250 million; again 14%; score 55."
    assert texts(unsupported_numbers(answer, results)) == ["14%", "250"]


def test_booleans_and_missing_values_are_not_numbers():
    assert texts(unsupported_numbers("1 airport", {"ranked": True, "x": None})) == ["1"]
