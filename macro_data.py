import csv
from datetime import datetime

import requests
import yfinance as yf

from analytics import year_over_year_change

CPI_URL = "https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/d7g7/mm23/data"
GDP_URL = "https://www.ons.gov.uk/economy/grossdomesticproductgdp/timeseries/ihyq/qna/data"
BANK_RATE_URL = (
    "https://www.bankofengland.co.uk/boeapps/iadb/fromshowcolumns.asp"
    "?csv.x=yes&Datefrom=01/Jan/1980&Dateto=now&SeriesCodes=IUDBEDR"
    "&CSVF=TT&UsingCodes=Y&VPD=Y&VFD=N"
)
BROWSER_HEADERS = {"User-Agent": "Mozilla/5.0"}

# FRED (Federal Reserve Economic Data) publishes a plain CSV per series that needs no
# API key, unlike its JSON API. Used for data ONS/BoE don't have (US series) and for
# points Yahoo doesn't offer for free (the US 2-year Treasury).
FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"

US_CPI_SERIES = "CPIAUCSL"  # CPI index level, monthly - FRED has no ready-made US 12-month rate
US_GDP_SERIES = "A191RL1Q225SBEA"  # real GDP growth, already annualised quarter-on-quarter
US_FED_FUNDS_SERIES = "FEDFUNDS"  # effective federal funds rate, monthly
US_2Y_TREASURY_SERIES = "DGS2"

# Yahoo quotes these constant-maturity Treasury indices directly in percent
# (e.g. 4.25 means 4.25%), so no unit conversion is needed. The 2-year point comes from
# FRED instead, since Yahoo has no free US 2-year series.
US_YIELD_CURVE_TICKERS = {"3M": "^IRX", "5Y": "^FVX", "10Y": "^TNX", "30Y": "^TYX"}

# FRED mirrors OECD data for the UK, but only two points, both monthly (not daily like
# the US series). The "3M" point is an interbank rate (a proxy for a T-bill yield, not
# the same instrument), and there is no free UK 5-year or 30-year point.
UK_YIELD_CURVE_SERIES = {"3M": "IR3TIB01GBM156N", "10Y": "IRLTLT01GBM156N"}

# Years to maturity for each point, used to space the curve chart's x-axis realistically
# (the gap from 3M to 5Y is genuinely much smaller than 5Y to 30Y).
MATURITY_YEARS = {"3M": 0.25, "2Y": 2, "5Y": 5, "10Y": 10, "30Y": 30}

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


def fetch_fred_series(series_id, source_name):
    """A FRED series as [(date, value), ...], oldest first. Missing observations are
    skipped: FRED marks these as an empty string in most series, but '.' shows up too
    (its documented convention), so both are treated as missing."""
    try:
        response = requests.get(FRED_CSV_URL.format(series_id=series_id), timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise DataUnavailable(f"could not fetch {source_name} data ({e})") from e

    try:
        lines = response.text.strip().splitlines()
        reader = csv.reader(lines[1:])  # skip the "observation_date,<series>" header
        readings = [
            (datetime.strptime(date_str, "%Y-%m-%d").date(), float(value_str))
            for date_str, value_str in reader
            if value_str not in ("", ".")
        ]
        if not readings:
            raise DataUnavailable(f"no {source_name} data returned")
        return readings
    except (ValueError, csv.Error) as e:
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


def fetch_us_cpi_readings():
    """US CPI 12-month inflation rate, computed from FRED's CPI index level (FRED has no
    ready-made US 12-month rate series, unlike ONS's UK series). Rounded to 1 decimal
    place to match the precision ONS already publishes its UK rate at - the raw
    computation has far more (meaningless) precision than either source's real accuracy."""
    index_levels = fetch_fred_series(US_CPI_SERIES, "US CPI")
    return [(date, round(rate, 1)) for date, rate in year_over_year_change(index_levels)]


def fetch_us_gdp_readings():
    """US real GDP growth, annualised quarter-on-quarter (FRED's convention - not
    directly comparable to the UK's non-annualised quarterly rate from ONS)."""
    return fetch_fred_series(US_GDP_SERIES, "US GDP growth")


def fetch_us_fed_funds_readings():
    """US federal funds rate: the US analogue of the UK Bank Rate."""
    return fetch_fred_series(US_FED_FUNDS_SERIES, "US Fed Funds Rate")


def fetch_yield_curve(country):
    """{'3M': yield_pct, ...} for the given country ('US' or 'UK'); missing points are
    omitted. See US_YIELD_CURVE_TICKERS / UK_YIELD_CURVE_SERIES for what each covers."""
    if country == "US":
        return _fetch_us_yield_curve()
    if country == "UK":
        return _fetch_uk_yield_curve()
    raise ValueError(f"no yield curve data for {country!r}")


def _fetch_us_yield_curve():
    curve = {}
    for label, ticker in US_YIELD_CURVE_TICKERS.items():
        history = yf.Ticker(ticker).history(period="5d")
        if not history.empty:
            curve[label] = history["Close"].iloc[-1]

    try:
        two_year = fetch_fred_series(US_2Y_TREASURY_SERIES, "US 2-year Treasury")
        curve["2Y"] = two_year[-1][1]
    except DataUnavailable:
        pass  # the rest of the curve still renders without this one point

    return curve


def _fetch_uk_yield_curve():
    curve = {}
    for label, series_id in UK_YIELD_CURVE_SERIES.items():
        try:
            readings = fetch_fred_series(series_id, f"UK {label} rate")
            curve[label] = readings[-1][1]
        except DataUnavailable:
            continue
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
