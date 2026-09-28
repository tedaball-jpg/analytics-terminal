# Market code -> yfinance ticker suffix. "US" has no suffix because
# yfinance uses bare tickers (AAPL) for US-listed stocks.
MARKET_SUFFIXES = {
    "US": "",
    "LN": ".L",
}


def to_yfinance_ticker(ticker: str, market: str) -> str:
    return ticker + MARKET_SUFFIXES[market]
