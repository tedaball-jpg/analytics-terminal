import pytest

from validation.analysis import (
    LOOSE_THRESHOLD_PCT,
    TIGHT_THRESHOLD_PCT,
    ZERO_VALUE_ABSOLUTE_TOLERANCE,
    categorize_agreement,
    compute_difference,
    compute_percent_difference,
)
from validation.summary import build_summary_markdown, summarize_by_function


def test_compute_difference_by_hand():
    assert compute_difference(28.9, 28.8) == pytest.approx(0.1)


def test_compute_difference_can_be_negative():
    assert compute_difference(28.8, 28.9) == pytest.approx(-0.1)


def test_compute_percent_difference_by_hand():
    # |100.5 - 100| / |100| * 100 = 0.5%
    assert compute_percent_difference(100.5, 100) == pytest.approx(0.5)


def test_compute_percent_difference_is_relative_to_bloomberg_value():
    # Same absolute gap (1.0), different Bloomberg values, so different percentages.
    assert compute_percent_difference(101, 100) == pytest.approx(1.0)
    assert compute_percent_difference(1001, 1000) == pytest.approx(0.1)


def test_compute_percent_difference_is_symmetric_in_sign():
    # A value that is too high and one that is too low by the same relative amount
    # should read as the same percentage difference.
    assert compute_percent_difference(105, 100) == pytest.approx(compute_percent_difference(95, 100))


def test_compute_percent_difference_is_none_when_bloomberg_value_is_zero():
    assert compute_percent_difference(0.01, 0) is None


def test_categorize_agreement_exact_match():
    assert categorize_agreement(28.8, 28.8) == "matched"


def test_categorize_agreement_matched_by_hand():
    # 0.4% difference, under the 0.5% tight threshold.
    assert categorize_agreement(100.4, 100.0) == "matched"


def test_categorize_agreement_at_the_tight_boundary_is_matched():
    # Exactly TIGHT_THRESHOLD_PCT should count as matched (<=, not <).
    bloomberg_value = 100.0
    my_value = bloomberg_value * (1 + TIGHT_THRESHOLD_PCT / 100)
    assert categorize_agreement(my_value, bloomberg_value) == "matched"


def test_categorize_agreement_just_past_the_tight_boundary_is_close():
    bloomberg_value = 100.0
    my_value = bloomberg_value * (1 + TIGHT_THRESHOLD_PCT / 100) + 0.001
    assert categorize_agreement(my_value, bloomberg_value) == "close"


def test_categorize_agreement_close_by_hand():
    # 1% difference: past the 0.5% tight threshold, within the 2% loose threshold.
    assert categorize_agreement(101.0, 100.0) == "close"


def test_categorize_agreement_at_the_loose_boundary_is_close():
    bloomberg_value = 100.0
    my_value = bloomberg_value * (1 + LOOSE_THRESHOLD_PCT / 100)
    assert categorize_agreement(my_value, bloomberg_value) == "close"


def test_categorize_agreement_just_past_the_loose_boundary_is_mismatch():
    bloomberg_value = 100.0
    my_value = bloomberg_value * (1 + LOOSE_THRESHOLD_PCT / 100) + 0.001
    assert categorize_agreement(my_value, bloomberg_value) == "mismatch"


def test_categorize_agreement_mismatch_by_hand():
    # 10% difference: well past both thresholds.
    assert categorize_agreement(110.0, 100.0) == "mismatch"


def test_categorize_agreement_does_not_depend_on_the_sign_of_the_error():
    assert categorize_agreement(105, 100) == categorize_agreement(95, 100)


def test_categorize_agreement_zero_bloomberg_value_within_absolute_tolerance_is_matched():
    assert categorize_agreement(ZERO_VALUE_ABSOLUTE_TOLERANCE / 2, 0) == "matched"


def test_categorize_agreement_zero_bloomberg_value_past_absolute_tolerance_is_mismatch():
    assert categorize_agreement(ZERO_VALUE_ABSOLUTE_TOLERANCE * 2, 0) == "mismatch"


def test_categorize_agreement_zero_bloomberg_value_exact_zero_match_is_matched():
    assert categorize_agreement(0, 0) == "matched"


def test_categorize_agreement_respects_custom_thresholds():
    # With a much looser tight threshold, a 1% difference now counts as matched.
    assert categorize_agreement(101.0, 100.0, tight=1.5) == "matched"


# --- summarize_by_function / build_summary_markdown ---------------------------------------------

ROWS = [
    # GP: one matched (0.1% off), one close (1% off), one mismatch (10% off).
    {"function": "GP", "ticker": "AAPL", "my_value": 28.9, "bloomberg_value": 28.9 * (1 - 0.001), "date_checked": "2026-01-05"},
    {"function": "GP", "ticker": "MSFT", "my_value": 101.0, "bloomberg_value": 100.0, "date_checked": "2026-01-06"},
    {"function": "GP", "ticker": "GOOG", "my_value": 110.0, "bloomberg_value": 100.0, "date_checked": "2026-01-04"},
    # HP: one matched.
    {"function": "HP", "ticker": "AAPL", "my_value": 50.0, "bloomberg_value": 50.0, "date_checked": "2026-01-07"},
]


def test_summarize_by_function_counts_by_hand():
    counts = summarize_by_function(ROWS)
    assert counts["GP"] == {"matched": 1, "close": 1, "mismatch": 1}
    assert counts["HP"] == {"matched": 1, "close": 0, "mismatch": 0}


def test_summarize_by_function_recomputes_agreement_rather_than_trusting_a_stored_value():
    # No "agreement" or "difference" field is passed in; it must be derived from the
    # two raw values every time, so a stale or hand-edited difference can't mislead it.
    rows = [{"function": "GP", "ticker": "AAPL", "my_value": 100.0, "bloomberg_value": 100.0}]
    assert summarize_by_function(rows)["GP"]["matched"] == 1


def test_build_summary_markdown_has_no_rows_message_when_empty():
    markdown = build_summary_markdown([])
    assert "No comparisons recorded" in markdown


def test_build_summary_markdown_contains_the_markers():
    markdown = build_summary_markdown(ROWS)
    assert markdown.startswith("<!-- VALIDATION:START")
    assert markdown.rstrip().endswith("<!-- VALIDATION:END -->")


def test_build_summary_markdown_totals_add_up():
    markdown = build_summary_markdown(ROWS)
    assert "| **All** | **4** |" in markdown


def test_build_summary_markdown_never_contains_a_bloomberg_or_my_value():
    # The whole point: only counts and labels, never a number from the CSV's value columns.
    markdown = build_summary_markdown(ROWS)
    for row in ROWS:
        assert str(row["my_value"]) not in markdown
        assert str(row["bloomberg_value"]) not in markdown


def test_build_summary_markdown_never_contains_a_ticker():
    markdown = build_summary_markdown(ROWS)
    for row in ROWS:
        assert row["ticker"] not in markdown


def test_build_summary_markdown_reports_the_most_recent_date():
    markdown = build_summary_markdown(ROWS)
    assert "2026-01-07" in markdown
