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
        "2) Since 2019 KSFO, A320 and lower-48 traffic grew 5 points."
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
        {"sources": ["https://example.gov/JO_7110.308B_Approaches.pdf"]},
    ]
    answer = "Over 1,400 miles; 750 ft apart (note 6; FAA Order JO 7110.308B)."
    assert unsupported_numbers(answer, results) == []


def test_invented_numbers_are_flagged_once_each_in_order():
    results = [{"score": 55.0}]
    answer = "ROI of 14% and $250 million; again 14%; score 55."
    assert texts(unsupported_numbers(answer, results)) == ["14%", "250"]


def test_booleans_and_missing_values_are_not_numbers():
    assert texts(unsupported_numbers("1 airport", {"ranked": True, "x": None})) == ["1"]


PROBE = {
    "score": 48.2,
    "checked": "2026-10-11",
    "source": "https://x/tfrh-tu9e.json",
    "as_of": "2026 Q1 vs 2019 Q1",
}


def test_dates_in_tool_text_do_not_support_a_number():
    assert texts(unsupported_numbers("demand grew 11%", PROBE)) == ["11%"]


def test_digits_inside_a_link_id_do_not_support_a_number():
    assert texts(unsupported_numbers("ranked 9th", PROBE)) == ["9"]


def test_a_four_digit_count_is_a_number_unless_it_reads_as_a_year():
    assert texts(numbers_in("BOS handles 2000 departures a day")) == ["2000"]
    assert texts(numbers_in("up since 2019 or 2021, in 2024, 2019 Q1 vs 2026 Q1 (2019)")) == []


def test_a_leading_decimal_is_a_number():
    found = numbers_in("a share of .75")
    assert [(n.text, n.value, n.decimals) for n in found] == [(".75", 0.75, 2)]
