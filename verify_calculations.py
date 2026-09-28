"""Independent checks of the terminal's calculations. Run: python verify_calculations.py

Each check compares the app's number (analytics.py / market_data.py, which use pandas)
against a number produced a different way:
  A. a tiny series whose answers you can work out by hand
  B. plain-Python re-implementations that use only loops and the math module
  C. a dividend reconciliation: rebuild total return from raw closes plus dividends paid
  D. mathematical properties that must hold whatever the data is
Exits with status 1 if any check fails.
"""

import math
import sys

import pandas as pd
import yfinance as yf

from analytics import (
    annualised_volatility,
    cumulative_return,
    max_drawdown,
    simple_returns,
    total_return,
    trailing_range,
)
from market_data import fetch_price_history, resample_prices

TICKER = "AAPL"
results = []


def check(name, ours, independent, tolerance=1e-9):
    difference = abs(ours - independent)
    results.append((name, ours, independent, difference, tolerance, difference <= tolerance))


# ---- Independent implementations: loops and math only, no pandas ----------------------------


def py_returns(closes):
    return [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes))]


def py_compound(returns):
    growth = 1.0
    for r in returns:
        growth *= 1 + r
    return growth - 1


def py_volatility(returns, periods_per_year):
    n = len(returns)
    mean = sum(returns) / n
    variance = sum((r - mean) ** 2 for r in returns) / (n - 1)  # sample variance: divide by n - 1
    return math.sqrt(variance) * math.sqrt(periods_per_year)


def py_max_drawdown(closes):
    peak, worst = closes[0], 0.0
    for close in closes:
        peak = max(peak, close)
        worst = min(worst, close / peak - 1)
    return worst


def py_weekly(frame):
    """Group by ISO calendar week (Monday to Sunday), a different rule from pandas' 'W-FRI'."""
    weeks = {}
    for date, row in frame.iterrows():
        weeks.setdefault(date.isocalendar()[:2], []).append((date, row))
    rows = []
    for week in sorted(weeks):
        days = weeks[week]
        rows.append(
            (
                days[-1][0],  # last trading day
                days[0][1]["Open"],
                max(r["High"] for _, r in days),
                min(r["Low"] for _, r in days),
                days[-1][1]["Close"],
                sum(r["Volume"] for _, r in days),
            )
        )
    return rows


# ---- A. Hand-worked example ------------------------------------------------------------------
print("A. Hand-worked example: prices 100, 110, 99, 108.9")
hand = pd.Series([100.0, 110.0, 99.0, 108.9])
print("   returns are +10%, -10%, +10%. They compound to 1.1 x 0.9 x 1.1 = 1.089, so total return is 8.9%")
print("   volatility: returns +a, -a, +a with a = 0.1 give a daily std of 2a/sqrt(3) = 0.11547")
check("A1 total return (8.9%)", total_return(hand), 0.089)
check("A2 daily volatility x sqrt(252)", annualised_volatility(simple_returns(hand)), 2 * 0.1 / math.sqrt(3) * math.sqrt(252))
check("A3 max drawdown (110 -> 99 = -10%)", max_drawdown(hand).depth, -0.10)

# ---- Live data through the app's own data layer ---------------------------------------------
print(f"\nFetching {TICKER} through market_data.fetch_price_history ...")
split_adjusted = fetch_price_history(TICKER, adjusted=False)
adjusted = fetch_price_history(TICKER, adjusted=True)
if split_adjusted.empty or adjusted.empty:
    print("Could not download data; skipping sections B to D.")
    sys.exit(1)
print(f"{len(adjusted)} daily rows, {adjusted.index[0]:%Y-%m-%d} to {adjusted.index[-1]:%Y-%m-%d}")

# ---- B. Plain-Python re-implementation on the real series ----------------------------------
print("\nB. Plain-Python re-implementation on real data")
for label, frame in [("dividend-adjusted", adjusted), ("split-adjusted", split_adjusted)]:
    closes = frame["Close"].tolist()
    returns = py_returns(closes)
    check(f"B1 total return, {label}", total_return(frame["Close"]), closes[-1] / closes[0] - 1)
    check(f"B2 compounded daily returns, {label}", cumulative_return(simple_returns(frame["Close"])).iloc[-1], py_compound(returns))
    check(f"B3 annualised volatility, {label}", annualised_volatility(simple_returns(frame["Close"])), py_volatility(returns, 252))
    check(f"B4 max drawdown, {label}", max_drawdown(frame["Close"]).depth, py_max_drawdown(closes))

weekly_ours = resample_prices(adjusted, "Weekly")
weekly_theirs = py_weekly(adjusted)
check("B5 weekly row count", len(weekly_ours), len(weekly_theirs), tolerance=0)
worst_gap = 0.0
dates_match = True
for (date, o, h, l, c, v), (our_date, our_row) in zip(weekly_theirs, weekly_ours.iterrows()):
    dates_match &= date == our_date
    worst_gap = max(worst_gap, abs(o - our_row["Open"]), abs(h - our_row["High"]), abs(l - our_row["Low"]), abs(c - our_row["Close"]), abs(v - our_row["Volume"]))
check("B6 weekly row dates all match", float(dates_match), 1.0, tolerance=0)
check("B7 weekly OHLCV, largest difference in any cell", worst_gap, 0.0, tolerance=1e-6)

recent = split_adjusted.tail(252)
range_stats = trailing_range(split_adjusted)
check("B8 52-week high", range_stats.high, max(recent["High"].tolist()))
check("B9 52-week low", range_stats.low, min(recent["Low"].tolist()))

# ---- C. Dividend reconciliation -------------------------------------------------------------
# Rebuild total return from split-adjusted closes plus the dividends paid, without touching
# Yahoo's own dividend-adjusted series. There are two standard conventions for the ex-dividend day:
#   Yahoo:      previous close is scaled down by the dividend, so the day's growth is C_t / (C_(t-1) - D_t)
#   Reinvested: the dividend is added to that day's close,       so the day's growth is (C_t + D_t) / C_(t-1)
# They differ by about (that day's price move x dividend yield) per dividend, so the first must
# match Yahoo almost exactly and the second only approximately.
print("\nC. Dividend reconciliation: dividend-adjusted return vs rebuilt from closes + dividends")
dividends = yf.Ticker(TICKER).dividends
dividends.index = dividends.index.tz_localize(None).normalize()
dividends = dividends.groupby(level=0).sum().reindex(split_adjusted.index, fill_value=0.0)
closes = split_adjusted["Close"].tolist()
paid = dividends.tolist()
growth_yahoo = growth_reinvested = 1.0
for i in range(1, len(closes)):
    growth_yahoo *= closes[i] / (closes[i - 1] - paid[i])
    growth_reinvested *= (closes[i] + paid[i]) / closes[i - 1]
price_only = closes[-1] / closes[0] - 1
print(f"   dividends in window: {int((dividends > 0).sum())}, total {dividends.sum():.2f} per share")
print(f"   price return {price_only:.4%}, total return rebuilt (Yahoo convention) {growth_yahoo - 1:.4%}, (reinvested) {growth_reinvested - 1:.4%}")
check("C1 same dates in both series", float((adjusted.index == split_adjusted.index).all()), 1.0, tolerance=0)
check("C2 adjusted total return vs rebuilt, Yahoo convention", total_return(adjusted["Close"]), growth_yahoo - 1, tolerance=1e-6)
check("C3 adjusted total return vs rebuilt, reinvested convention", total_return(adjusted["Close"]), growth_reinvested - 1, tolerance=1e-3)
check("C4 total return is at least price return (stock pays dividends)", float(growth_yahoo - 1 >= price_only), 1.0, tolerance=0)

# ---- D. Properties that must hold whatever the data is --------------------------------------
print("\nD. Properties")
scaled = adjusted["Close"] * 100  # pounds vs pence, or any unit change
check("D1 unit change leaves total return unchanged", total_return(scaled), total_return(adjusted["Close"]))
check("D2 unit change leaves volatility unchanged", annualised_volatility(simple_returns(scaled)), annualised_volatility(simple_returns(adjusted["Close"])))
check("D3 unit change leaves max drawdown unchanged", max_drawdown(scaled).depth, max_drawdown(adjusted["Close"]).depth)
check("D4 drawdown depth is between -100% and 0%", float(-1 <= max_drawdown(adjusted["Close"]).depth <= 0), 1.0, tolerance=0)

# ---- Report --------------------------------------------------------------------------------
print("\n" + "=" * 100)
print(f"{'Check':<58}{'App':>14}{'Independent':>14}{'Diff':>11}  Result")
print("-" * 100)
for name, ours, independent, difference, tolerance, ok in results:
    print(f"{name:<58}{ours:>14.6f}{independent:>14.6f}{difference:>11.2e}  {'PASS' if ok else 'FAIL'}")
failed = [r for r in results if not r[5]]
print("=" * 100)
print(f"{len(results) - len(failed)} of {len(results)} checks passed")
print(
    "\nWhat this does NOT prove: that Yahoo's prices are right (compare with the real terminal),\n"
    "or that the conventions are the ones you want (252 days, sample std, simple returns)."
)
sys.exit(1 if failed else 0)
