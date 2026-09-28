import csv
from datetime import datetime

import requests
import yfinance as yf

CPI_URL = "https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/d7g7/mm23/data"
GDP_URL = "https://www.ons.gov.uk/economy/grossdomesticproductgdp/timeseries/ihyq/qna/data"
BANK_RATE_URL = (
    "https://www.bankofengland.co.uk/boeapps/iadb/fromshowcolumns.asp"
    "?csv.x=yes&Datefrom=01/Jan/1980&Dateto=now&SeriesCodes=IUDBEDR"
    "&CSVF=TT&UsingCodes=Y&VPD=Y&VFD=N"
)
BROWSER_HEADERS = {"User-Agent": "Mozilla/5.0"}

# Yahoo quotes these constant-maturity Treasury indices directly in percent
# (e.g. 4.25 means 4.25%), so no unit conversion is needed. Yahoo has no free 2-year
# series, so the curve has a gap between 3 months and 5 years.
YIELD_CURVE_TICKERS = {"3M": "^IRX", "5Y": "^FVX", "10Y": "^TNX", "30Y": "^TYX"}
# Years to maturity for each point, used to space the curve chart's x-axis realistically
# (the gap from 3M to 5Y is genuinely much smaller than 5Y to 30Y).
MATURITY_YEARS = {"3M": 0.25, "5Y": 5, "10Y": 10, "30Y": 30}

# FXC's currency basket. USD is the anchor: Yahoo has a "USD<code>=X" ticker (units of
# <code> per 1 USD) for every one of these, which is not true of every currency pair.
FX_CURRENCIES = ["USD", "GBP", "EUR", "JPY"]


class DataUnavailable(Exception):
    """Raised when a source could not be reached or returned something we can't parse."""


def fetch_json_series(url, key, source_name):
    """A named series from an ONS "generator" JSON endpoint, e.g. months of CPI."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()[key]
    except requests.exceptions.RequestException as e:
        raise DataUnavailable(f"could not fetch {source_name} data ({e})") from e
    except (KeyError, ValueError) as e:
        raise DataUnavailable(f"unexpected {source_name} response format ({e})") from e


def parse_month(date_str):
    """ONS month labels look like '2026 AUG'."""
    return datetime.strptime(date_str.title(), "%Y %b").date()


def parse_quarter(date_str):
    """ONS quarter labels look like '2026 Q2'; quarter n starts in month 3n - 2."""
    year_str, quarter_str = date_str.split()
    month = (int(quarter_str[1]) - 1) * 3 + 1
    return datetime(int(year_str), month, 1).date()


def fetch_cpi_readings():
    """UK CPI 12-month inflation rate as [(date, value), ...], oldest first."""
    months = fetch_json_series(CPI_URL, "months", "CPI inflation")
    return [(parse_month(m["date"]), float(m["value"])) for m in months]


def fetch_gdp_readings():
    """UK GDP quarter-on-quarter growth as [(date, value), ...], oldest first."""
    quarters = fetch_json_series(GDP_URL, "quarters", "GDP growth")
    return [(parse_quarter(q["date"]), float(q["value"])) for q in quarters]


def fetch_bank_rate_readings():
    """Bank of England Bank Rate as [(date, value), ...], one row per day, oldest first."""
    try:
        response = requests.get(BANK_RATE_URL, timeout=10, headers=BROWSER_HEADERS)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise DataUnavailable(f"could not fetch Bank Rate data ({e})") from e

    try:
        lines = response.text.splitlines()
        start = next(i for i, line in enumerate(lines) if line.startswith("DATE,"))
        reader = csv.reader(lines[start + 1 :])
        return [(datetime.strptime(d, "%d %b %Y").date(), float(r)) for d, r in reader]
    except (StopIteration, ValueError) as e:
        raise DataUnavailable(f"unexpected Bank Rate response format ({e})") from e


def bank_rate_changes(series):
    """Collapse a daily Bank Rate series to just the dates it changed (it is flat between
    the Monetary Policy Committee's roughly 8 decisions a year)."""
    changes = []
    previous_rate = None
    for entry_date, rate in series:
        if rate != previous_rate:
            changes.append((entry_date, rate))
            previous_rate = rate
    return changes


def fetch_yield_curve():
    """{'3M': yield_pct, '5Y': ..., '10Y': ..., '30Y': ...}; missing points are omitted."""
    curve = {}
    for label, ticker in YIELD_CURVE_TICKERS.items():
        history = yf.Ticker(ticker).history(period="5d")
        if not history.empty:
            curve[label] = history["Close"].iloc[-1]
    return curve


def fetch_units_per_usd():
    """{'USD': 1.0, 'GBP': ..., ...}: units of each currency that 1 USD buys, from
    Yahoo's 'USD<code>=X' tickers. Missing currencies are omitted."""
    rates = {}
    for code in FX_CURRENCIES:
        history = yf.download(f"USD{code}=X", period="5d", progress=False)
        if not history.empty:
            rates[code] = history["Close"].iloc[-1].item()
    return rates
