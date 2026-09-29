from dataclasses import dataclass

import pandas as pd

TRADING_DAYS_PER_YEAR = 252


@dataclass
class MaxDrawdown:
    depth: float  # negative fraction, e.g. -0.25 means a 25% fall from the peak
    peak_date: pd.Timestamp
    trough_date: pd.Timestamp


@dataclass
class TrailingRange:
    high: float
    low: float
    last_close: float
    below_high: float  # negative fraction: how far the last close is under the high


@dataclass
class LatestReading:
    date: object
    value: float
    previous_value: float | None  # None if this is the only reading available
    change: float | None  # value - previous_value (a level change, not a percentage)


def simple_returns(prices):
    """Period-to-period percentage change: P_t / P_(t-1) - 1."""
    return prices.pct_change().dropna()


def total_return(prices):
    """Return over the whole window: last price / first price - 1."""
    return prices.iloc[-1] / prices.iloc[0] - 1


def trailing_return(prices, periods):
    """Return over the last `periods` steps, or NaN if there is not enough history."""
    if len(prices) <= periods:
        return float("nan")
    return prices.iloc[-1] / prices.iloc[-1 - periods] - 1


def cumulative_return(returns):
    """Compound a series of returns: (1 + r1)(1 + r2)... - 1 at each step."""
    return (1 + returns).cumprod() - 1


def annualised_volatility(returns, periods_per_year=TRADING_DAYS_PER_YEAR):
    """Sample standard deviation of returns (n - 1) scaled by sqrt(periods per year)."""
    return returns.std() * (periods_per_year**0.5)


def drawdown_series(prices):
    """How far each price is below the highest price seen so far (0 at a new high)."""
    return prices / prices.cummax() - 1


def max_drawdown(prices):
    drawdown = drawdown_series(prices)
    trough_date = drawdown.idxmin()
    # The peak is the highest price on or before the trough.
    peak_date = prices.loc[:trough_date].idxmax()
    return MaxDrawdown(depth=drawdown.min(), peak_date=peak_date, trough_date=trough_date)


def trailing_range(ohlcv, window=TRADING_DAYS_PER_YEAR):
    """Highest high and lowest low over the last `window` rows (about 52 weeks of daily data)."""
    recent = ohlcv.tail(window)
    high = recent["High"].max()
    low = recent["Low"].min()
    last_close = ohlcv["Close"].iloc[-1]
    return TrailingRange(high=high, low=low, last_close=last_close, below_high=last_close / high - 1)


def latest_reading(series):
    """The most recent (date, value) in a [(date, value), ...] series, oldest first, and
    its change from the reading before it. Used for economic indicators (CPI, GDP, Bank
    Rate), where the level change (not a percentage) is what is usually quoted."""
    if not series:
        raise ValueError("series is empty")

    date, value = series[-1]
    if len(series) == 1:
        return LatestReading(date=date, value=value, previous_value=None, change=None)

    previous_value = series[-2][1]
    return LatestReading(date=date, value=value, previous_value=previous_value, change=value - previous_value)


def curve_spread(yields, short_label, long_label):
    """Long-maturity yield minus short-maturity yield, in percentage points. Positive is a
    normal (upward-sloping) curve; negative is an inverted curve."""
    return yields[long_label] - yields[short_label]


def is_curve_inverted(spread):
    return spread < 0


def normalize_weights(weights):
    """Rescale a list of weights so they sum to 1, whatever scale they were typed in
    (raw amounts like [2, 1] or fractions like [0.6, 0.4] both work)."""
    total = sum(weights)
    if total <= 0:
        raise ValueError(f"weights must sum to a positive number, got {total}")
    return [w / total for w in weights]


def portfolio_returns(returns, weights):
    """The weighted daily return of a fixed-weight (rebalanced daily) portfolio: on each
    day, sum each asset's return times its weight. `returns` has one column per asset;
    `weights` is in the same order as `returns.columns`, already normalised (sums to 1)."""
    return (returns * weights).sum(axis=1)


def correlation_matrix(returns):
    """Pearson correlation between every pair of assets' daily returns."""
    return returns.corr()


def rebase(prices):
    """Rescale a price series to start at 100: rebased_t = price_t / price_0 * 100. Lets
    two securities on different price levels (or in different currencies) be compared
    on one chart, since both start from the same point."""
    return prices / prices.iloc[0] * 100


def sharpe_ratio(returns, risk_free_rate, periods_per_year=TRADING_DAYS_PER_YEAR):
    """Excess return per unit of risk: (annualised return - risk-free rate) / annualised
    volatility. risk_free_rate must already be annualised, in the same decimal units as
    returns (0.04 for 4%), not a daily rate."""
    annualised_return = returns.mean() * periods_per_year
    return (annualised_return - risk_free_rate) / annualised_volatility(returns, periods_per_year)


def buy_and_hold_returns(returns, weights):
    """The daily return of a buy-and-hold portfolio: weights are set once, at the start,
    then left to drift as each holding's own value compounds (yesterday's winner is a
    bigger slice today). Contrast with portfolio_returns, which reapplies the same
    weights every day (rebalancing). `weights` must already be normalised (sum to 1)."""
    value_path = ((1 + returns).cumprod() * weights).sum(axis=1)
    initial_value = sum(weights)  # the portfolio's value the moment before the first return
    previous_value = [initial_value] + value_path.iloc[:-1].tolist()
    return pd.Series(value_path.values / previous_value - 1, index=value_path.index)


def year_over_year_change(readings):
    """Convert a monthly index-level series (e.g. a CPI index, not already a rate) into
    a 12-month percentage change: rate_i = readings[i] / readings[i-12] - 1, as a
    percentage (matching how a 12-month inflation rate is normally quoted). Needs at
    least 13 monthly readings; the first 12 have no year-ago comparison and are dropped."""
    return [
        (readings[i][0], (readings[i][1] / readings[i - 12][1] - 1) * 100)
        for i in range(12, len(readings))
    ]


def build_cross_matrix(units_per_usd):
    """A full currency cross-rate matrix by triangulating through USD.

    units_per_usd maps a currency code to how many units of it 1 USD buys (Yahoo's
    'USD<code>=X' quote). The rate from currency A to currency B (units of B per 1 unit
    of A) is (units of B per USD) / (units of A per USD), since both sides cancel the
    USD: A -> USD -> B. The matrix's diagonal is always 1.0 (a currency against itself).
    """
    currencies = list(units_per_usd)
    matrix = pd.DataFrame(index=currencies, columns=currencies, dtype=float)
    for base in currencies:
        for quote in currencies:
            matrix.loc[base, quote] = units_per_usd[quote] / units_per_usd[base]
    return matrix
