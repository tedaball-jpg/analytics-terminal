import math

import pandas as pd
import pytest

from analytics import (
    TRADING_DAYS_PER_YEAR,
    annualised_volatility,
    build_cross_matrix,
    buy_and_hold_returns,
    correlation_matrix,
    cumulative_return,
    curve_spread,
    drawdown_series,
    is_curve_inverted,
    latest_reading,
    max_drawdown,
    normalize_weights,
    portfolio_returns,
    rebase,
    sharpe_ratio,
    simple_returns,
    total_return,
    trailing_range,
    trailing_return,
    year_over_year_change,
)

DATES = pd.date_range("2026-01-05", periods=4, freq="B")

# 100 -> 110 (+10%) -> 99 (-10%) -> 108.9 (+10%). Every answer below can be worked out by hand.
PRICES = pd.Series([100.0, 110.0, 99.0, 108.9], index=DATES)


def test_simple_returns_by_hand():
    returns = simple_returns(PRICES)
    assert returns.tolist() == pytest.approx([0.10, -0.10, 0.10])
    assert len(returns) == len(PRICES) - 1


def test_total_return_by_hand():
    # 108.9 / 100 - 1
    assert total_return(PRICES) == pytest.approx(0.089)


def test_returns_compound_rather_than_add():
    # +10%, -10%, +10% adds up to +10% but compounds to +8.9%.
    assert simple_returns(PRICES).sum() == pytest.approx(0.10)
    assert cumulative_return(simple_returns(PRICES)).iloc[-1] == pytest.approx(0.089)


def test_compounded_returns_equal_price_ratio():
    # Two independent routes to the same number.
    compounded = cumulative_return(simple_returns(PRICES)).iloc[-1]
    assert compounded == pytest.approx(total_return(PRICES))


def test_annualised_volatility_by_hand():
    # Returns are +a, -a, +a with a = 0.1. Mean = a/3, squared deviations sum to 8a^2/3,
    # sample variance = (8a^2/3) / (n - 1 = 2) = 4a^2/3, so the daily std is 2a / sqrt(3).
    daily_std = 2 * 0.1 / math.sqrt(3)
    expected = daily_std * math.sqrt(252)
    assert annualised_volatility(simple_returns(PRICES)) == pytest.approx(expected)


def test_annualisation_factor_depends_on_periodicity():
    returns = simple_returns(PRICES)
    daily = annualised_volatility(returns, 252)
    weekly = annualised_volatility(returns, 52)
    monthly = annualised_volatility(returns, 12)
    assert weekly / daily == pytest.approx(math.sqrt(52 / 252))
    assert monthly / daily == pytest.approx(math.sqrt(12 / 252))


def test_default_annualisation_is_252_trading_days():
    assert TRADING_DAYS_PER_YEAR == 252
    returns = simple_returns(PRICES)
    assert annualised_volatility(returns) == annualised_volatility(returns, 252)


def test_volatility_is_zero_for_a_steady_climb():
    steady = pd.Series([100 * 1.01**i for i in range(10)])
    assert annualised_volatility(simple_returns(steady)) == pytest.approx(0, abs=1e-12)


def test_volatility_is_undefined_with_one_return():
    assert math.isnan(annualised_volatility(simple_returns(PRICES.iloc[:2])))


def test_trailing_return_uses_the_last_n_steps():
    # Last price 108.9 against the price 2 steps earlier (110).
    assert trailing_return(PRICES, 2) == pytest.approx(108.9 / 110 - 1)
    assert trailing_return(PRICES, 3) == pytest.approx(0.089)


def test_trailing_return_is_nan_without_enough_history():
    assert math.isnan(trailing_return(PRICES, 4))


# 100, 120, 90, 110, 130, 104: peak 120 falls to 90 (-25%); later peak 130 falls to 104 (-20%).
DRAWDOWN_PRICES = pd.Series([100.0, 120.0, 90.0, 110.0, 130.0, 104.0], index=pd.date_range("2026-01-05", periods=6, freq="B"))


def test_drawdown_series_by_hand():
    assert drawdown_series(DRAWDOWN_PRICES).tolist() == pytest.approx([0, 0, -0.25, -1 / 12, 0, -0.20])


def test_max_drawdown_finds_depth_and_dates():
    result = max_drawdown(DRAWDOWN_PRICES)
    assert result.depth == pytest.approx(-0.25)
    assert result.peak_date == DRAWDOWN_PRICES.index[1]  # the 120
    assert result.trough_date == DRAWDOWN_PRICES.index[2]  # the 90


def test_max_drawdown_is_zero_when_prices_only_rise():
    rising = pd.Series([1.0, 2.0, 3.0], index=pd.date_range("2026-01-05", periods=3, freq="B"))
    assert max_drawdown(rising).depth == 0


def test_drawdown_is_never_positive_and_never_below_minus_100_percent():
    drawdown = drawdown_series(DRAWDOWN_PRICES)
    assert (drawdown <= 0).all()
    assert (drawdown >= -1).all()


def test_scaling_all_prices_changes_no_return_statistic():
    # Whether a stock is quoted in pounds or pence must not change any of these.
    scaled = DRAWDOWN_PRICES * 100
    assert total_return(scaled) == pytest.approx(total_return(DRAWDOWN_PRICES))
    assert max_drawdown(scaled).depth == pytest.approx(max_drawdown(DRAWDOWN_PRICES).depth)
    assert annualised_volatility(simple_returns(scaled)) == pytest.approx(
        annualised_volatility(simple_returns(DRAWDOWN_PRICES))
    )


def test_trailing_range_uses_only_the_window():
    index = pd.date_range("2026-01-05", periods=5, freq="B")
    ohlcv = pd.DataFrame(
        {
            "Open": [1, 1, 1, 1, 1],
            "High": [500, 12, 14, 13, 15],  # the 500 is outside the last-4 window
            "Low": [0.5, 9, 8, 10, 11],
            "Close": [1, 10, 12, 11, 12],
            "Volume": [1, 1, 1, 1, 1],
        },
        index=index,
    )
    result = trailing_range(ohlcv, window=4)

    assert result.high == 15
    assert result.low == 8
    assert result.last_close == 12
    assert result.below_high == pytest.approx(12 / 15 - 1)


# --- latest_reading: used by ECO for CPI, GDP and Bank Rate ------------------------------------

READINGS = [
    (pd.Timestamp("2026-06-01"), 2.0),
    (pd.Timestamp("2026-07-01"), 2.3),
    (pd.Timestamp("2026-08-01"), 2.1),
]


def test_latest_reading_by_hand():
    result = latest_reading(READINGS)
    assert result.date == pd.Timestamp("2026-08-01")
    assert result.value == 2.1
    assert result.previous_value == 2.3
    assert result.change == pytest.approx(2.1 - 2.3)  # a level change (percentage points), not a ratio


def test_latest_reading_change_is_a_difference_not_a_ratio():
    # A 2.3 -> 2.1 move is -0.2 percentage points, not -8.7% (which would be a return-style calculation).
    assert latest_reading(READINGS).change == pytest.approx(-0.2)


def test_latest_reading_with_a_single_entry_has_no_previous_value():
    result = latest_reading(READINGS[:1])
    assert result.value == 2.0
    assert result.previous_value is None
    assert result.change is None


def test_latest_reading_rejects_an_empty_series():
    with pytest.raises(ValueError):
        latest_reading([])


# --- curve_spread / is_curve_inverted: used by GC -----------------------------------------------


def test_curve_spread_by_hand():
    yields = {"3M": 4.0, "5Y": 4.8, "10Y": 4.9, "30Y": 5.2}
    assert curve_spread(yields, "3M", "10Y") == pytest.approx(0.9)


def test_curve_spread_is_negative_and_flagged_inverted_when_short_exceeds_long():
    yields = {"3M": 5.5, "10Y": 4.2}
    spread = curve_spread(yields, "3M", "10Y")
    assert spread == pytest.approx(-1.3)
    assert is_curve_inverted(spread)


def test_normal_curve_is_not_flagged_inverted():
    assert not is_curve_inverted(curve_spread({"3M": 4.0, "10Y": 4.9}, "3M", "10Y"))


def test_flat_curve_is_not_flagged_inverted():
    # A spread of exactly zero is flat, not inverted.
    assert not is_curve_inverted(curve_spread({"3M": 4.0, "10Y": 4.0}, "3M", "10Y"))


# --- build_cross_matrix: used by FXC, triangulating every pair through USD -----------------------

UNITS_PER_USD = {"USD": 1.0, "GBP": 0.75, "EUR": 0.85, "JPY": 150.0}


def test_cross_matrix_by_hand():
    matrix = build_cross_matrix(UNITS_PER_USD)
    # 1 GBP = 1 / 0.75 USD = 150 / 0.75 JPY = 200 JPY.
    assert matrix.loc["GBP", "JPY"] == pytest.approx(200.0)
    # 1 USD = 0.75 GBP, directly from the input.
    assert matrix.loc["USD", "GBP"] == pytest.approx(0.75)


def test_cross_matrix_diagonal_is_one():
    matrix = build_cross_matrix(UNITS_PER_USD)
    for currency in UNITS_PER_USD:
        assert matrix.loc[currency, currency] == pytest.approx(1.0)


def test_cross_matrix_is_reciprocal():
    # The rate from A to B must be the reciprocal of B to A.
    matrix = build_cross_matrix(UNITS_PER_USD)
    for base in UNITS_PER_USD:
        for quote in UNITS_PER_USD:
            assert matrix.loc[base, quote] == pytest.approx(1 / matrix.loc[quote, base])


def test_cross_matrix_triangulates_consistently():
    # Going A -> B -> C must equal going A -> C directly, for any third currency.
    matrix = build_cross_matrix(UNITS_PER_USD)
    for a in UNITS_PER_USD:
        for b in UNITS_PER_USD:
            for c in UNITS_PER_USD:
                assert matrix.loc[a, b] * matrix.loc[b, c] == pytest.approx(matrix.loc[a, c])


def test_cross_matrix_unaffected_by_which_currency_is_the_usd_anchor():
    # The USD values are just a computational anchor; rescaling them all (e.g. quoting
    # everything against a different base) must not change any cross rate.
    rescaled = {k: v / UNITS_PER_USD["GBP"] for k, v in UNITS_PER_USD.items()}
    original = build_cross_matrix(UNITS_PER_USD)
    rescaled_matrix = build_cross_matrix(rescaled)
    pd.testing.assert_frame_equal(original, rescaled_matrix)


# --- normalize_weights / portfolio_returns / correlation_matrix: used by PORT ------------------


def test_normalize_weights_of_fractions_already_summing_to_one():
    assert normalize_weights([0.6, 0.4]) == pytest.approx([0.6, 0.4])


def test_normalize_weights_of_raw_ratios():
    # A 2:1 ratio is 2/3, 1/3, whatever units the raw numbers were in.
    assert normalize_weights([2, 1]) == pytest.approx([2 / 3, 1 / 3])


def test_normalize_weights_of_three_equal_amounts():
    assert normalize_weights([1, 1, 1]) == pytest.approx([1 / 3, 1 / 3, 1 / 3])


def test_normalize_weights_always_sums_to_one():
    assert sum(normalize_weights([5, 3, 17.5])) == pytest.approx(1.0)


def test_normalize_weights_rejects_a_non_positive_total():
    with pytest.raises(ValueError):
        normalize_weights([0, 0])


PORTFOLIO_RETURNS_INPUT = pd.DataFrame(
    {
        # Day 1: A +10%, B -10%. Day 2: A -10%, B +10%.
        "A": [0.10, -0.10],
        "B": [-0.10, 0.10],
    }
)


def test_portfolio_returns_equal_weight_by_hand():
    # Equal-weighted, the opposite moves cancel out to exactly 0 both days.
    result = portfolio_returns(PORTFOLIO_RETURNS_INPUT, [0.5, 0.5])
    assert result.tolist() == pytest.approx([0.0, 0.0])


def test_portfolio_returns_uneven_weight_by_hand():
    # 70% A, 30% B on day 1: 0.7*0.10 + 0.3*(-0.10) = 0.04.
    result = portfolio_returns(PORTFOLIO_RETURNS_INPUT, [0.7, 0.3])
    assert result.tolist() == pytest.approx([0.04, -0.04])


def test_portfolio_returns_single_asset_at_full_weight_matches_that_asset():
    result = portfolio_returns(PORTFOLIO_RETURNS_INPUT, [1.0, 0.0])
    assert result.tolist() == pytest.approx(PORTFOLIO_RETURNS_INPUT["A"].tolist())


def test_correlation_matrix_of_identical_series_is_one():
    returns = pd.DataFrame({"A": [0.01, -0.02, 0.03, 0.01], "B": [0.01, -0.02, 0.03, 0.01]})
    corr = correlation_matrix(returns)
    assert corr.loc["A", "B"] == pytest.approx(1.0)


def test_correlation_matrix_of_perfectly_opposite_series_is_minus_one():
    returns = pd.DataFrame({"A": [0.01, -0.02, 0.03, 0.01], "B": [-0.01, 0.02, -0.03, -0.01]})
    corr = correlation_matrix(returns)
    assert corr.loc["A", "B"] == pytest.approx(-1.0)


def test_correlation_matrix_diagonal_is_one():
    returns = pd.DataFrame({"A": [0.01, -0.02, 0.03], "B": [0.02, 0.01, -0.01]})
    corr = correlation_matrix(returns)
    assert corr.loc["A", "A"] == pytest.approx(1.0)
    assert corr.loc["B", "B"] == pytest.approx(1.0)


# --- rebase: used by GP's rebased two-security comparison --------------------------------------


def test_rebase_starts_at_100():
    prices = pd.Series([50.0, 55.0, 45.0])
    assert rebase(prices).iloc[0] == pytest.approx(100.0)


def test_rebase_by_hand():
    # A 10% rise from the start should read as 110, whatever the starting price was.
    prices = pd.Series([200.0, 220.0, 180.0])
    result = rebase(prices)
    assert result.tolist() == pytest.approx([100.0, 110.0, 90.0])


def test_rebase_makes_two_different_price_levels_comparable():
    cheap = pd.Series([10.0, 11.0, 9.0])
    expensive = pd.Series([1000.0, 1100.0, 900.0])
    # Same percentage moves, wildly different price levels -> identical rebased series.
    assert rebase(cheap).tolist() == pytest.approx(rebase(expensive).tolist())


# --- sharpe_ratio: used by PORT -----------------------------------------------------------------


def test_sharpe_ratio_by_hand():
    # Constant +0.1% daily return has zero volatility, so a naive Sharpe would divide by
    # zero; use a return series with real dispersion instead, matching GP's daily std = 2a/sqrt(3).
    returns = pd.Series([0.10, -0.10, 0.10])
    annualised_return = returns.mean() * 252  # (0.10 - 0.10 + 0.10) / 3 * 252
    vol = annualised_volatility(returns)
    risk_free_rate = 0.04
    assert sharpe_ratio(returns, risk_free_rate) == pytest.approx((annualised_return - risk_free_rate) / vol)


def test_sharpe_ratio_is_higher_with_a_lower_risk_free_rate():
    returns = pd.Series([0.01, -0.02, 0.03, 0.01, -0.01])
    assert sharpe_ratio(returns, 0.01) > sharpe_ratio(returns, 0.05)


def test_sharpe_ratio_respects_periods_per_year():
    returns = pd.Series([0.01, -0.02, 0.03, 0.01, -0.01])
    daily_convention = sharpe_ratio(returns, 0.02, periods_per_year=252)
    monthly_convention = sharpe_ratio(returns, 0.02, periods_per_year=12)
    assert daily_convention != pytest.approx(monthly_convention)


# --- buy_and_hold_returns: used by PORT's buy-and-hold mode -------------------------------------

# Day 1: A +20%, B +0%. Day 2: A +10%, B +0%. Worked by hand in the module's docstring
# derivation: day 1 return matches fixed-weight exactly (no drift has happened yet), day 2
# does not, because A is now a bigger share of the portfolio after day 1's outperformance.
DRIFT_RETURNS = pd.DataFrame({"A": [0.20, 0.10], "B": [0.0, 0.0]})
DRIFT_WEIGHTS = [0.5, 0.5]


def test_buy_and_hold_first_day_matches_fixed_weight():
    # Before any drift, day 1 is identical under both methods.
    bh = buy_and_hold_returns(DRIFT_RETURNS, DRIFT_WEIGHTS)
    fixed = portfolio_returns(DRIFT_RETURNS, DRIFT_WEIGHTS)
    assert bh.iloc[0] == pytest.approx(fixed.iloc[0])
    assert bh.iloc[0] == pytest.approx(0.10)  # 0.5 * 0.20 + 0.5 * 0.0


def test_buy_and_hold_second_day_diverges_from_fixed_weight_by_hand():
    # After day 1, A's weight has drifted to 1.2*0.5 / 1.1 = 0.5454..., B's to 0.4545...
    # Day 2 return = 0.5454... * 0.10 + 0.4545... * 0.0 = 0.054545...
    bh = buy_and_hold_returns(DRIFT_RETURNS, DRIFT_WEIGHTS)
    assert bh.iloc[1] == pytest.approx(0.0545454545, rel=1e-6)

    fixed = portfolio_returns(DRIFT_RETURNS, DRIFT_WEIGHTS)
    assert fixed.iloc[1] == pytest.approx(0.05)  # unaffected by drift, always uses 0.5/0.5
    assert bh.iloc[1] != pytest.approx(fixed.iloc[1])


def test_buy_and_hold_equals_fixed_weight_with_only_one_period():
    # With a single day of returns there has been no time to drift.
    returns = pd.DataFrame({"A": [0.05], "B": [-0.03]})
    weights = [0.7, 0.3]
    assert buy_and_hold_returns(returns, weights).tolist() == pytest.approx(
        portfolio_returns(returns, weights).tolist()
    )


def test_buy_and_hold_cumulative_value_matches_each_holdings_own_compounding():
    # The portfolio's total cumulative return must equal the weighted sum of each
    # holding's own (independently compounded) cumulative return - the defining property
    # of buy-and-hold, checked independently of the day-by-day return formula above.
    returns = pd.DataFrame({"A": [0.10, -0.05, 0.20], "B": [-0.02, 0.03, 0.01]})
    weights = [0.6, 0.4]
    bh = buy_and_hold_returns(returns, weights)
    portfolio_cumulative = (1 + bh).prod() - 1

    holding_a_cumulative = (1 + returns["A"]).prod() - 1
    holding_b_cumulative = (1 + returns["B"]).prod() - 1
    expected = 0.6 * (1 + holding_a_cumulative) + 0.4 * (1 + holding_b_cumulative) - 1

    assert portfolio_cumulative == pytest.approx(expected)


# --- year_over_year_change: used by ECO's US CPI (a raw index level, not a rate) ----------------


def test_year_over_year_change_by_hand():
    # 13 monthly index points: 100, 100.1, ..., up to a 13th point at 105. The 12-months-
    # back comparison for the 13th point is 105 / 100 - 1 = 5%.
    dates = pd.date_range("2025-01-01", periods=13, freq="MS")
    values = [100.0] * 12 + [105.0]
    readings = list(zip(dates, values))
    result = year_over_year_change(readings)
    assert len(result) == 1
    assert result[0][0] == dates[12]
    assert result[0][1] == pytest.approx(5.0)


def test_year_over_year_change_needs_at_least_13_readings():
    dates = pd.date_range("2025-01-01", periods=12, freq="MS")
    readings = list(zip(dates, [100.0] * 12))
    assert year_over_year_change(readings) == []


def test_year_over_year_change_returns_one_point_per_reading_past_the_first_12():
    dates = pd.date_range("2025-01-01", periods=15, freq="MS")
    readings = list(zip(dates, range(100, 115)))
    result = year_over_year_change(readings)
    assert len(result) == 3  # 15 readings - 12 = 3 with a year-ago comparison
    assert [d for d, _ in result] == list(dates[12:])


def test_year_over_year_change_of_a_falling_index_is_negative():
    dates = pd.date_range("2025-01-01", periods=13, freq="MS")
    values = [100.0] * 12 + [95.0]
    result = year_over_year_change(list(zip(dates, values)))
    assert result[0][1] == pytest.approx(-5.0)
