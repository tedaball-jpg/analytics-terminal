from datetime import timedelta

import pandas as pd
import yfinance as yf

OHLCV = ["Open", "High", "Low", "Close", "Volume"]

# Periodicity shown in the HP table -> pandas resample rule (None = keep daily rows).
# "W-FRI" groups days into weeks ending Friday; "ME" groups them into calendar months.
PERIOD_RULES = {"Daily": None, "Weekly": "W-FRI", "Monthly": "ME"}

# How many rows of each periodicity make a year; needed to annualise volatility correctly.
PERIODS_PER_YEAR = {"Daily": 252, "Weekly": 52, "Monthly": 12}

# The only fields we read from Yahoo's large `info` record.
COMPANY_FIELDS = [
    "longName",
    "shortName",
    "exchange",
    "fullExchangeName",
    "currency",
    "country",
    "sector",
    "industry",
    "marketCap",
    "fullTimeEmployees",
    "website",
    "longBusinessSummary",
]


def fetch_price_history(yf_ticker, period="2y", interval="1d", adjusted=True, start=None, end=None):
    """Daily OHLCV. adjusted=True is adjusted for splits and dividends (use it for returns);
    adjusted=False is adjusted for splits only (use it for price levels). Yahoo does not
    provide raw, never-adjusted quotes.

    Pass start/end (dates) for an explicit window; otherwise `period` (e.g. "2y") is
    used, ending at the latest available close. start/end take priority if both are given.
    `end` is treated as inclusive (a user picking "to today" expects today's close if it
    exists); yfinance's own `end` is exclusive, so it is pushed forward a day internally."""
    if start is not None:
        yf_end = end + timedelta(days=1) if end is not None else None
        data = yf.download(yf_ticker, start=start, end=yf_end, interval=interval, auto_adjust=adjusted, progress=False)
    else:
        data = yf.download(yf_ticker, period=period, interval=interval, auto_adjust=adjusted, progress=False)
    if data.empty:
        return pd.DataFrame(columns=OHLCV)
    # yfinance labels columns (field, ticker); with one ticker we only need the field.
    # With adjusted=False there is also an "Adj Close" column, which OHLCV selection drops.
    return data.droplevel("Ticker", axis=1)[OHLCV].dropna(subset=["Close"])


def resample_prices(prices, periodicity):
    """Collapse daily OHLCV rows into weekly or monthly rows."""
    rule = PERIOD_RULES[periodicity]
    if rule is None:
        return prices

    # A week's open is its first day's open, its high is the highest high, and so on.
    # Date is carried along as a column so each row can be labelled with its last trading
    # day, rather than a calendar period end that may lie in the future.
    aggregated = (
        prices.assign(Date=prices.index)
        .resample(rule)
        .agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum", "Date": "last"})
    )
    # Periods with no trading days (a holiday week) come out empty, so drop them.
    return aggregated.dropna(subset=["Close"]).set_index("Date")


def fetch_company_info(yf_ticker):
    info = yf.Ticker(yf_ticker).info
    return {field: info.get(field) for field in COMPANY_FIELDS}


def company_name(info):
    # Yahoo returns a nearly empty record for unknown tickers, so "no name" means "not found".
    return info.get("longName") or info.get("shortName")


def format_market_cap(value):
    if not isinstance(value, (int, float)) or value <= 0:
        return "n/a"
    for size, suffix in [(1e12, "T"), (1e9, "B"), (1e6, "M")]:
        if value >= size:
            return f"{value / size:.2f}{suffix}"
    return f"{value:,.0f}"


def format_percent(value, digits=1):
    """0.089 -> '8.9%'; NaN or missing -> 'n/a' (for statistics that cannot be computed)."""
    if value is None or pd.isna(value):
        return "n/a"
    return f"{value:.{digits}%}"


def company_rows(info):
    """Label/value pairs for the DES table, with 'n/a' wherever Yahoo has no data."""

    def text(value):
        return str(value) if value not in (None, "") else "n/a"

    employees = info.get("fullTimeEmployees")
    return [
        ("Name", text(company_name(info))),
        ("Exchange", text(info.get("fullExchangeName") or info.get("exchange"))),
        ("Quote currency", text(info.get("currency"))),
        ("Country", text(info.get("country"))),
        ("Sector", text(info.get("sector"))),
        ("Industry", text(info.get("industry"))),
        ("Market cap", format_market_cap(info.get("marketCap"))),
        ("Employees", f"{employees:,}" if isinstance(employees, int) else "n/a"),
        ("Website", text(info.get("website"))),
    ]
