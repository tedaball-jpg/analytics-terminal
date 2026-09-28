import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from analytics import (
    annualised_volatility,
    build_cross_matrix,
    correlation_matrix,
    curve_spread,
    is_curve_inverted,
    latest_reading,
    max_drawdown,
    normalize_weights,
    portfolio_returns,
    simple_returns,
    total_return,
    trailing_range,
)
from command_parser import FUNCTION_CODES
from macro_data import (
    MATURITY_YEARS,
    DataUnavailable,
    fetch_bank_rate_readings,
    fetch_cpi_readings,
    fetch_gdp_readings,
    fetch_units_per_usd,
    fetch_yield_curve,
)
from market_data import (
    PERIOD_RULES,
    PERIODS_PER_YEAR,
    company_name,
    company_rows,
    fetch_company_info,
    fetch_price_history,
    format_percent,
    resample_prices,
)
from markets import to_yfinance_ticker
from portfolio import fetch_prices as fetch_portfolio_prices
from portfolio import plot_correlation_heatmap, plot_garch_vs_flat, plot_price_history
from volatility import fit_garch

# Label shown to the user -> the `adjusted` flag passed to the data layer.
PRICE_BASES = {
    "Dividend-adjusted (total return)": True,
    "Split-adjusted only (price return)": False,
}


# Streamlit reruns the script on every click (including the Learn panel toggle),
# so each download is cached instead of hitting Yahoo Finance each time.
@st.cache_data(ttl=600, show_spinner="Fetching prices...")
def fetch_ohlcv(yf_ticker, adjusted):
    return fetch_price_history(yf_ticker, adjusted=adjusted)


@st.cache_data(ttl=3600, show_spinner="Fetching company info...")
def fetch_company(yf_ticker):
    return fetch_company_info(yf_ticker)


def choose_price_basis(key):
    label = st.radio("Price basis", list(PRICE_BASES), horizontal=True, key=key)
    return PRICE_BASES[label]


def price_graph(command):
    yf_ticker = to_yfinance_ticker(command.ticker, command.market)
    adjusted = choose_price_basis("gp_price_basis")
    prices = fetch_ohlcv(yf_ticker, adjusted)["Close"]

    if prices.empty:
        st.error(f"No price data found for {command.ticker} {command.market} ({yf_ticker})")
        return

    fig = plot_price_history(prices, command.ticker)
    st.pyplot(fig)
    plt.close(fig)  # otherwise matplotlib keeps every rerun's figure in memory

    drawdown = max_drawdown(prices)
    first, second, third = st.columns(3)
    first.metric("Total return" if adjusted else "Price return", format_percent(total_return(prices)))
    second.metric("Annualised volatility", format_percent(annualised_volatility(simple_returns(prices))))
    third.metric("Max drawdown", format_percent(drawdown.depth))
    st.caption(
        f"{prices.index[0]:%d %b %Y} to {prices.index[-1]:%d %b %Y}. "
        "Volatility is the standard deviation of daily returns times the square root of 252. "
        f"Worst fall: peak {drawdown.peak_date:%d %b %Y} to trough {drawdown.trough_date:%d %b %Y}. "
        "London stocks are quoted in pence."
    )


def description(command):
    yf_ticker = to_yfinance_ticker(command.ticker, command.market)

    try:
        info = fetch_company(yf_ticker)
    except Exception as error:  # yfinance raises many different network and parsing errors
        st.error(f"Could not fetch company info for {command.ticker} {command.market}: {error}")
        return

    name = company_name(info)
    if name is None:
        st.error(f"No company data found for {command.ticker} {command.market} ({yf_ticker})")
        return

    st.subheader(name)
    rows = pd.DataFrame(company_rows(info), columns=["Field", "Value"]).set_index("Field")
    st.table(rows)
    st.caption(
        "Data from Yahoo Finance. Yahoo does not state the currency of the market cap "
        "(for London stocks the quote currency is pence), so check it against the real terminal."
    )

    # Price levels (last close, 52-week range) use split-adjusted prices: dividend-adjusting
    # would shift old prices away from what the stock actually traded at.
    ohlcv = fetch_ohlcv(yf_ticker, False)
    if not ohlcv.empty:
        stats = trailing_range(ohlcv)
        st.markdown("**Price snapshot** (split-adjusted, about 52 weeks of daily data)")
        snapshot = pd.DataFrame(
            [
                ("Last close", f"{stats.last_close:,.2f}"),
                ("52-week high", f"{stats.high:,.2f}"),
                ("52-week low", f"{stats.low:,.2f}"),
                ("Last close vs 52-week high", format_percent(stats.below_high)),
            ],
            columns=["Field", "Value"],
        ).set_index("Field")
        st.table(snapshot)

    st.markdown("**Business description**")
    st.write(info.get("longBusinessSummary") or "n/a")


def historical_prices(command):
    yf_ticker = to_yfinance_ticker(command.ticker, command.market)
    adjusted = choose_price_basis("hp_price_basis")
    prices = fetch_ohlcv(yf_ticker, adjusted)

    if prices.empty:
        st.error(f"No price data found for {command.ticker} {command.market} ({yf_ticker})")
        return

    periodicity = st.radio("Periodicity", list(PERIOD_RULES), horizontal=True, key="hp_periodicity")

    table = resample_prices(prices, periodicity)
    returns = simple_returns(table["Close"])
    table["Change %"] = returns.reindex(table.index) * 100  # the first row has no previous close
    # Annualise with the factor that matches the row frequency (252, 52 or 12).
    volatility = annualised_volatility(returns, PERIODS_PER_YEAR[periodicity])

    table = table.sort_index(ascending=False)  # newest first
    table.index = table.index.strftime("%Y-%m-%d")

    st.metric(f"Annualised volatility ({periodicity.lower()} returns)", format_percent(volatility))
    st.dataframe(
        table,
        height=420,
        column_config={
            "Open": st.column_config.NumberColumn(format="%.2f"),
            "High": st.column_config.NumberColumn(format="%.2f"),
            "Low": st.column_config.NumberColumn(format="%.2f"),
            "Close": st.column_config.NumberColumn(format="%.2f"),
            "Volume": st.column_config.NumberColumn(format="localized"),
            "Change %": st.column_config.NumberColumn(format="%.2f%%"),
        },
    )
    st.caption(
        "Last 2 years from Yahoo Finance. London stocks are quoted in pence. "
        "Weekly and monthly rows: open is the first day's, high the highest, low the lowest, "
        "close the last day's, volume the total. Each row is dated by its last trading day. "
        "Change % is the close against the previous row's close."
    )


@st.cache_data(ttl=3600, show_spinner="Fetching UK economic data...")
def fetch_cpi():
    return fetch_cpi_readings()


@st.cache_data(ttl=3600, show_spinner="Fetching UK economic data...")
def fetch_gdp():
    return fetch_gdp_readings()


@st.cache_data(ttl=3600, show_spinner="Fetching UK economic data...")
def fetch_bank_rate():
    return fetch_bank_rate_readings()


@st.cache_data(ttl=600, show_spinner="Fetching yield curve...")
def fetch_curve():
    return fetch_yield_curve()


@st.cache_data(ttl=600, show_spinner="Fetching FX rates...")
def fetch_fx():
    return fetch_units_per_usd()


def render_indicator(title, fetch, unit, window):
    """One economic indicator's metric and trend, or a clean warning if its source failed.
    Failures are per indicator, so one broken source does not blank the whole ECO page."""
    try:
        readings = fetch()
    except DataUnavailable as error:
        st.warning(f"{title}: {error}")
        return

    st.markdown(f"**{title}**")
    reading = latest_reading(readings)
    delta = None if reading.change is None else f"{reading.change:+.2f}{unit}"
    st.metric(f"{reading.date:%b %Y}", f"{reading.value:g}{unit}", delta=delta, delta_color="off")

    recent = pd.Series(
        [value for _, value in readings[-window:]],
        index=[pd.Timestamp(date) for date, _ in readings[-window:]],
    )
    st.line_chart(recent, height=160)


def economic_calendar(command):
    # command.ticker is always "UK" (the only subject command_parser.MACRO_SUBJECTS["ECO"]
    # allows), since ONS and the Bank of England only give this app UK data for free.
    first, second, third = st.columns(3)
    with first:
        render_indicator("CPI inflation (12-month rate)", fetch_cpi, "%", window=24)
    with second:
        render_indicator("GDP growth (quarter-on-quarter)", fetch_gdp, "%", window=12)
    with third:
        render_indicator("Bank Rate", fetch_bank_rate, "%", window=24)
    st.caption(
        "CPI and GDP from the Office for National Statistics; Bank Rate from the Bank of "
        "England. The change shown is in percentage points against the previous reading, "
        "not a percentage change."
    )


def yield_curve(command):
    try:
        curve = fetch_curve()
    except Exception as error:  # yfinance raises many different network and parsing errors
        st.error(f"Could not fetch the yield curve: {error}")
        return

    if not curve:
        st.error("No yield curve data available.")
        return

    labels = [label for label in MATURITY_YEARS if label in curve]
    maturities = [MATURITY_YEARS[label] for label in labels]
    values = [curve[label] for label in labels]

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(maturities, values, marker="o")
    ax.set_xticks(maturities, labels)
    ax.set_xlabel("Maturity")
    ax.set_ylabel("Yield (%)")
    ax.set_title("US Treasury yield curve")
    fig.tight_layout()
    st.pyplot(fig)
    plt.close(fig)

    if "3M" in curve and "10Y" in curve:
        spread = curve_spread(curve, "3M", "10Y")
        inverted = is_curve_inverted(spread)
        st.metric("10-year minus 3-month spread", f"{spread:+.2f} pp", delta="Inverted" if inverted else "Normal", delta_color="inverse")
        st.caption(
            "A negative spread (short-term yields above long-term yields) is called an "
            "inversion, and has preceded most US recessions historically, though the lead "
            "time varies widely and not every inversion is followed by one. "
            "Yahoo has no free 2-year Treasury series, so the curve has a gap between 3 "
            "months and 5 years, and the spread uses 3-month rather than the also common "
            "10-year-minus-2-year measure."
        )


def fx_cross_rates(command):
    try:
        rates = fetch_fx()
    except Exception as error:  # yfinance raises many different network and parsing errors
        st.error(f"Could not fetch FX rates: {error}")
        return

    if command.ticker not in rates:
        st.error(f"No FX data available for {command.ticker}.")
        return

    matrix = build_cross_matrix(rates)
    base = command.ticker

    st.markdown(f"**1 {base} buys**")
    columns = st.columns(len(matrix.columns) - 1)
    for column, other in zip(columns, [c for c in matrix.columns if c != base]):
        column.metric(other, f"{matrix.loc[base, other]:,.4f}")

    st.markdown("**Full cross-rate matrix**")
    st.caption("Row = 1 unit of the row currency; columns = how many units of that currency it buys.")
    st.dataframe(matrix.style.format("{:.4f}"))
    st.caption(
        "Rates from Yahoo Finance, triangulated through USD (every pair is computed from "
        "each currency's rate against USD, not fetched directly), so a small triangulation "
        "gap against a directly-quoted pair is possible. Real FX screens usually quote JPY "
        "pairs to 2 decimal places and others to 4; this table uses 4 throughout."
    )


MIN_PORTFOLIO_HISTORY = 30  # rows; below this, correlation and GARCH stop being meaningful


@st.cache_data(ttl=600, show_spinner="Fetching prices and fitting the portfolio...")
def compute_portfolio(tickers, weights):
    """Fetch, then run every portfolio calculation, in one cached call. Raises ValueError
    (a clean message) for bad input data, so the handler doesn't need to inspect the
    result to find out whether it worked."""
    prices = fetch_portfolio_prices(list(tickers))

    missing = [t for t in tickers if t not in prices.columns or prices[t].isna().all()]
    if missing:
        raise ValueError(f"No price data found for: {', '.join(missing)}")

    prices = prices[list(tickers)].dropna()  # align to the trading days every ticker has
    if len(prices) < MIN_PORTFOLIO_HISTORY:
        raise ValueError(
            f"Only {len(prices)} overlapping trading days for this basket "
            f"(need at least {MIN_PORTFOLIO_HISTORY}); check the tickers have similar listing histories."
        )

    normalised = normalize_weights(list(weights))
    returns = simple_returns(prices)
    port_returns = portfolio_returns(returns, normalised)
    value_index = (1 + port_returns).cumprod()  # a "price" series starting at 1, for max_drawdown

    return {
        "weights": normalised,
        "value_index": value_index,
        "correlation": correlation_matrix(returns),
        "drawdown": max_drawdown(value_index),
        "flat_volatility": annualised_volatility(port_returns),
        "garch": fit_garch(port_returns),
    }


def portfolio_analytics(command):
    tickers = tuple(holding.ticker for holding in command.holdings)
    weights = tuple(holding.weight for holding in command.holdings)

    try:
        result = compute_portfolio(tickers, weights)
    except ValueError as error:
        st.error(str(error))
        return
    except Exception as error:  # yfinance and arch can both raise a variety of errors
        st.error(f"Could not build the portfolio: {error}")
        return

    st.markdown("**Weights**")
    weights_table = pd.DataFrame(
        {"Ticker": tickers, "Weight": [format_percent(w) for w in result["weights"]]}
    ).set_index("Ticker")
    st.table(weights_table)

    st.markdown("**Cumulative return**")
    st.line_chart(result["value_index"] * 100 - 100, height=300)

    drawdown = result["drawdown"]
    first, second, third = st.columns(3)
    first.metric("Total return", format_percent(total_return(result["value_index"])))
    second.metric("Annualised volatility", format_percent(result["flat_volatility"]))
    third.metric("Max drawdown", format_percent(drawdown.depth))
    st.caption(
        "Fixed weights, rebalanced daily (not buy-and-hold, whose weights would drift as "
        f"prices move). Worst fall: peak {drawdown.peak_date:%d %b %Y} to trough {drawdown.trough_date:%d %b %Y}."
    )

    st.markdown("**Correlation matrix** (daily returns)")
    heatmap = plot_correlation_heatmap(result["correlation"])
    st.pyplot(heatmap)
    plt.close(heatmap)
    st.dataframe(result["correlation"].style.format("{:.2f}"))

    st.markdown("**Volatility: GARCH(1,1) vs flat historical**")
    garch = result["garch"]
    garch_fig = plot_garch_vs_flat(garch.conditional_volatility, result["flat_volatility"])
    st.pyplot(garch_fig)
    plt.close(garch_fig)

    g1, g2, g3 = st.columns(3)
    g1.metric("Flat historical volatility", format_percent(result["flat_volatility"]))
    g2.metric("GARCH long-run volatility", format_percent(garch.long_run_volatility))
    g3.metric("GARCH latest estimate", format_percent(garch.conditional_volatility.iloc[-1]))
    st.caption(
        f"alpha={garch.alpha:.3f} (how much a shock feeds into tomorrow's variance), "
        f"beta={garch.beta:.3f} (how much of today's variance persists), "
        f"alpha+beta={garch.alpha + garch.beta:.3f} (must be under 1, or variance would never settle). "
        "Fitted on the portfolio's own daily returns, not on each stock separately."
    )


# Function code -> handler. Each handler takes a parsed Command and renders
# into the Streamlit page. Adding a function means writing a handler here and
# adding its code to command_parser.FUNCTION_CODES.
FUNCTIONS = {
    "GP": price_graph,
    "DES": description,
    "HP": historical_prices,
    "ECO": economic_calendar,
    "GC": yield_curve,
    "FXC": fx_cross_rates,
    "PORT": portfolio_analytics,
}

assert FUNCTIONS.keys() == FUNCTION_CODES, "FUNCTIONS must match command_parser.FUNCTION_CODES"
