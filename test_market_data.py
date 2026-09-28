import pandas as pd
import pytest

from market_data import (
    OHLCV,
    PERIOD_RULES,
    PERIODS_PER_YEAR,
    company_name,
    company_rows,
    format_market_cap,
    format_percent,
    resample_prices,
)


def make_prices(rows):
    """rows: (date, open, high, low, close, volume) tuples -> a daily OHLCV DataFrame."""
    index = pd.DatetimeIndex([row[0] for row in rows], name="Date")
    return pd.DataFrame([row[1:] for row in rows], index=index, columns=OHLCV)


# Week of Mon 5 Jan - Fri 9 Jan 2026, a whole holiday week with no trading, then a partial
# week Mon 19 - Wed 21 Jan. Values are chosen so every aggregate can be checked by hand.
JANUARY = make_prices(
    [
        ("2026-01-05", 10, 12, 9, 11, 100),
        ("2026-01-06", 11, 15, 10, 14, 200),
        ("2026-01-07", 14, 16, 13, 13, 300),
        ("2026-01-08", 13, 14, 8, 9, 400),
        ("2026-01-09", 9, 11, 7, 10, 500),
        ("2026-01-19", 20, 22, 19, 21, 50),
        ("2026-01-20", 21, 25, 20, 24, 60),
        ("2026-01-21", 24, 26, 23, 25, 70),
    ]
)


def test_daily_periodicity_returns_rows_unchanged():
    pd.testing.assert_frame_equal(resample_prices(JANUARY, "Daily"), JANUARY)


def test_weekly_aggregates_follow_ohlcv_rules():
    weekly = resample_prices(JANUARY, "Weekly")
    first_week = weekly.loc["2026-01-09"]

    assert first_week["Open"] == 10  # first day's open
    assert first_week["High"] == 16  # highest high of the week
    assert first_week["Low"] == 7  # lowest low of the week
    assert first_week["Close"] == 10  # last day's close
    assert first_week["Volume"] == 1500  # volumes add up


def test_weekly_drops_periods_with_no_trading_days():
    weekly = resample_prices(JANUARY, "Weekly")
    assert len(weekly) == 2


def test_rows_are_labelled_with_last_trading_day_not_period_end():
    weekly = resample_prices(JANUARY, "Weekly")
    # The second week ends Friday 23 Jan but the data stops on Wednesday 21 Jan.
    assert weekly.index.tolist() == [pd.Timestamp("2026-01-09"), pd.Timestamp("2026-01-21")]


def test_monthly_groups_by_calendar_month():
    prices = make_prices(
        [
            ("2026-01-29", 10, 11, 9, 10, 100),
            ("2026-01-30", 10, 14, 8, 12, 200),
            ("2026-02-02", 12, 13, 11, 13, 300),
            ("2026-02-03", 13, 20, 12, 18, 400),
        ]
    )
    monthly = resample_prices(prices, "Monthly")

    assert monthly.index.tolist() == [pd.Timestamp("2026-01-30"), pd.Timestamp("2026-02-03")]
    assert monthly.loc["2026-01-30"].tolist() == [10, 14, 8, 12, 300]
    assert monthly.loc["2026-02-03"].tolist() == [12, 20, 11, 18, 700]


def test_unknown_periodicity_is_rejected():
    with pytest.raises(KeyError):
        resample_prices(JANUARY, "Yearly")


@pytest.mark.parametrize(
    "value, expected",
    [
        (4_922_178_797_568, "4.92T"),
        (195_102_703_616, "195.10B"),
        (5_500_000, "5.50M"),
        (12_345, "12,345"),
        (None, "n/a"),
        (0, "n/a"),
        (-5, "n/a"),
        ("lots", "n/a"),
    ],
)
def test_format_market_cap(value, expected):
    assert format_market_cap(value) == expected


def test_every_periodicity_has_an_annualisation_factor():
    # Guards against adding a periodicity and forgetting how many of its rows make a year.
    assert PERIODS_PER_YEAR.keys() == PERIOD_RULES.keys()


def test_annualisation_factors_match_the_calendar():
    assert PERIODS_PER_YEAR == {"Daily": 252, "Weekly": 52, "Monthly": 12}


@pytest.mark.parametrize(
    "value, digits, expected",
    [
        (0.089, 1, "8.9%"),
        (-0.25, 1, "-25.0%"),
        (1.8330, 1, "183.3%"),
        (0.12345, 2, "12.35%"),
        (0, 1, "0.0%"),
        (float("nan"), 1, "n/a"),
        (None, 1, "n/a"),
    ],
)
def test_format_percent(value, digits, expected):
    assert format_percent(value, digits) == expected


def test_company_rows_formats_a_full_record():
    info = {
        "longName": "Apple Inc.",
        "fullExchangeName": "NasdaqGS",
        "exchange": "NMS",
        "currency": "USD",
        "country": "United States",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "marketCap": 4_922_178_797_568,
        "fullTimeEmployees": 150000,
        "website": "https://www.apple.com",
    }
    rows = dict(company_rows(info))

    assert rows["Name"] == "Apple Inc."
    assert rows["Exchange"] == "NasdaqGS"  # the readable name wins over the code
    assert rows["Market cap"] == "4.92T"
    assert rows["Employees"] == "150,000"


def test_company_rows_shows_na_for_missing_fields():
    rows = dict(company_rows({"longName": "Tiny Co"}))

    assert rows["Name"] == "Tiny Co"
    assert rows["Sector"] == "n/a"
    assert rows["Market cap"] == "n/a"
    assert rows["Employees"] == "n/a"


def test_exchange_falls_back_to_code_and_name_to_short_name():
    info = {"shortName": "ASTRAZENECA PLC ORD", "exchange": "LSE"}

    assert company_name(info) == "ASTRAZENECA PLC ORD"
    assert dict(company_rows(info))["Exchange"] == "LSE"


def test_unknown_ticker_record_has_no_name():
    # Yahoo returns a record with no name for a ticker that does not exist.
    assert company_name({"longName": None, "shortName": None}) is None
    assert company_name({}) is None
