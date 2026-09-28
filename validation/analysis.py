"""Pure comparison logic: no file I/O, no CSV, no network. Kept separate so it can be
unit-tested with small hand-checkable numbers, the same pattern as analytics.py."""

# Agreement buckets, as a percentage of the Bloomberg value (relative error). Using a
# relative threshold means a volatility of 28.8 and a price of 337.28 sit on the same
# scale: "matched within 0.5%" means the same thing whatever the number represents.
TIGHT_THRESHOLD_PCT = 0.5
LOOSE_THRESHOLD_PCT = 2.0

# When the Bloomberg value is exactly zero, a relative (percentage) error is undefined
# (division by zero), so agreement falls back to this absolute tolerance instead.
ZERO_VALUE_ABSOLUTE_TOLERANCE = 0.01

AGREEMENT_LABELS = {
    "matched": f"Matched within {TIGHT_THRESHOLD_PCT:g}%",
    "close": f"Within {LOOSE_THRESHOLD_PCT:g}%",
    "mismatch": f"Mismatch (over {LOOSE_THRESHOLD_PCT:g}%)",
}
# The order results should be reported in (tightest agreement first).
AGREEMENT_ORDER = ["matched", "close", "mismatch"]


def compute_difference(my_value, bloomberg_value):
    """my_value minus bloomberg_value, in whatever units the two values are in."""
    return my_value - bloomberg_value


def compute_percent_difference(my_value, bloomberg_value):
    """abs(difference) as a percentage of abs(bloomberg_value). None if bloomberg_value
    is exactly zero, where a relative error cannot be computed."""
    if bloomberg_value == 0:
        return None
    return abs(my_value - bloomberg_value) / abs(bloomberg_value) * 100


def categorize_agreement(my_value, bloomberg_value, tight=TIGHT_THRESHOLD_PCT, loose=LOOSE_THRESHOLD_PCT):
    """'matched', 'close' or 'mismatch', per the thresholds above."""
    percent_difference = compute_percent_difference(my_value, bloomberg_value)

    if percent_difference is None:
        difference = compute_difference(my_value, bloomberg_value)
        return "matched" if abs(difference) < ZERO_VALUE_ABSOLUTE_TOLERANCE else "mismatch"

    if percent_difference <= tight:
        return "matched"
    if percent_difference <= loose:
        return "close"
    return "mismatch"
