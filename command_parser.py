from dataclasses import dataclass

from markets import MARKET_SUFFIXES

# Equity functions price a specific listing, so they need a ticker AND a market to
# disambiguate it (AAPL could be listed in several places). Macro functions operate on
# a country or currency, which is already unambiguous on its own, so they take only
# a subject: no market. Portfolio functions take a weighted list of tickers instead of
# either. FUNCTION_CODES is the single source of truth for valid codes; functions.py
# asserts its handler registry has exactly these keys, so it can't drift.
EQUITY_FUNCTIONS = {"GP", "DES", "HP"}
MACRO_FUNCTIONS = {"ECO", "GC", "FXC"}
PORTFOLIO_FUNCTIONS = {"PORT"}
FUNCTION_CODES = EQUITY_FUNCTIONS | MACRO_FUNCTIONS | PORTFOLIO_FUNCTIONS

MIN_HOLDINGS = 2

# Optional Bloomberg-style word between market and function (AAPL US Equity GP).
# Only equities can be priced here, and the word is dropped once it has been checked.
SECURITY_TYPES = {"EQUITY"}

# The subjects each macro function understands, given what free data is actually
# available: UK and US economic releases (ECO), the US and UK yield curves (GC), and a
# small basket of major currencies (FXC).
MACRO_SUBJECTS = {
    "ECO": {"UK", "US"},
    "GC": {"US", "UK"},
    "FXC": {"USD", "GBP", "EUR", "JPY"},
}


@dataclass
class Holding:
    ticker: str
    weight: float  # as typed, not normalised; analytics.normalize_weights does that


@dataclass
class Command:
    ticker: str | None
    market: str | None
    function: str
    holdings: list[Holding] | None = None  # only set for PORTFOLIO_FUNCTIONS


@dataclass
class ParseError:
    message: str


def parse_command(raw: str) -> Command | ParseError:
    tokens = raw.split()

    if not tokens:
        return ParseError("Expected a command, got nothing.")

    function = tokens[-1].upper()
    if function not in FUNCTION_CODES:
        known = ", ".join(sorted(FUNCTION_CODES))
        return ParseError(f"Unknown function {function!r}. Known functions: {known}")

    remainder = tokens[:-1]
    if function in EQUITY_FUNCTIONS:
        return _parse_equity_command(remainder, function, raw)
    if function in MACRO_FUNCTIONS:
        return _parse_macro_command(remainder, function, raw)
    return _parse_portfolio_command(remainder, function, raw)


def _parse_equity_command(remainder, function, raw):
    tokens = list(remainder)

    # A 3-word remainder is only valid if the third word is a known security type.
    if len(tokens) == 3 and tokens[2].upper() in SECURITY_TYPES:
        del tokens[2]

    if len(tokens) != 2:
        return ParseError(
            f"Expected TICKER MARKET {function} (e.g. AAPL US {function}) or "
            f"TICKER MARKET Equity {function}, got {len(remainder) + 1} parts: {raw!r}"
        )

    ticker, market = (token.upper() for token in tokens)

    if market not in MARKET_SUFFIXES:
        known = ", ".join(sorted(MARKET_SUFFIXES))
        return ParseError(f"Unknown market {market!r}. Known markets: {known}")

    return Command(ticker=ticker, market=market, function=function)


def _parse_macro_command(remainder, function, raw):
    if len(remainder) != 1:
        return ParseError(
            f"Expected SUBJECT {function} (e.g. {sorted(MACRO_SUBJECTS[function])[0]} {function}), "
            f"got {len(remainder) + 1} parts: {raw!r}"
        )

    subject = remainder[0].upper()
    allowed = MACRO_SUBJECTS[function]
    if subject not in allowed:
        known = ", ".join(sorted(allowed))
        return ParseError(f"Unknown subject {subject!r} for {function}. Known: {known}")

    return Command(ticker=subject, market=None, function=function)


def _parse_portfolio_command(remainder, function, raw):
    if len(remainder) != 1:
        return ParseError(
            f"Expected TICKER:WEIGHT,TICKER:WEIGHT,... {function} "
            f"(e.g. AAPL:0.5,MSFT:0.5 {function}), got {len(remainder) + 1} parts: {raw!r}"
        )

    holdings = []
    seen_tickers = set()
    for piece in remainder[0].split(","):
        if ":" not in piece:
            return ParseError(f"Expected TICKER:WEIGHT (e.g. AAPL:0.5), got {piece!r} in {raw!r}")

        ticker_part, _, weight_part = piece.partition(":")
        ticker = ticker_part.strip().upper()
        if not ticker:
            return ParseError(f"Missing ticker before ':' in {piece!r}")

        try:
            weight = float(weight_part.strip())
        except ValueError:
            return ParseError(f"Weight {weight_part.strip()!r} for {ticker} is not a number")
        if weight <= 0:
            return ParseError(f"Weight for {ticker} must be positive, got {weight}")

        if ticker in seen_tickers:
            return ParseError(f"{ticker} is listed more than once in {raw!r}")
        seen_tickers.add(ticker)
        holdings.append(Holding(ticker=ticker, weight=weight))

    if len(holdings) < MIN_HOLDINGS:
        return ParseError(f"{function} needs at least {MIN_HOLDINGS} holdings, got {len(holdings)}: {raw!r}")

    return Command(ticker=None, market=None, function=function, holdings=holdings)
