import pytest

from command_parser import Command, Holding, ParseError, parse_command


def test_parses_valid_command():
    result = parse_command("AAPL US GP")
    assert result == Command(ticker="AAPL", market="US", function="GP")


def test_normalises_lowercase_input():
    result = parse_command("aapl us gp")
    assert result == Command(ticker="AAPL", market="US", function="GP")


def test_normalises_mixed_case_and_whitespace():
    result = parse_command("  AzN  ln  des  ")
    assert result == Command(ticker="AZN", market="LN", function="DES")


def test_accepts_bloomberg_style_security_type():
    result = parse_command("AAPL US Equity DES")
    assert result == Command(ticker="AAPL", market="US", function="DES")


def test_security_type_is_case_insensitive_and_whitespace_tolerant():
    result = parse_command("  aapl  us  EQUITY  gp ")
    assert result == Command(ticker="AAPL", market="US", function="GP")


def test_security_type_form_still_validates_market_and_function():
    assert isinstance(parse_command("AAPL XX Equity GP"), ParseError)
    assert isinstance(parse_command("AAPL US Equity ZZ"), ParseError)


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "AAPL",
        "AAPL US",
        "AAPL US GP EXTRA",  # 4 words, but the third is not a security type
        "AAPL US Equity",  # security type but no function
        "AAPL US Equity GP EXTRA",  # too many words
        "AAPL US Equity Equity GP",  # security type twice
    ],
)
def test_rejects_wrong_token_count(raw):
    result = parse_command(raw)
    assert isinstance(result, ParseError)


def test_rejects_unknown_market():
    result = parse_command("AAPL XX GP")
    assert isinstance(result, ParseError)
    assert "market" in result.message.lower()


def test_rejects_unknown_function():
    result = parse_command("AAPL US ZZ")
    assert isinstance(result, ParseError)
    assert "function" in result.message.lower()


# --- Macro functions: SUBJECT FUNCTION, no market (a country/currency needs no exchange) ---


def test_parses_valid_macro_commands():
    assert parse_command("UK ECO") == Command(ticker="UK", market=None, function="ECO")
    assert parse_command("US GC") == Command(ticker="US", market=None, function="GC")
    assert parse_command("GBP FXC") == Command(ticker="GBP", market=None, function="FXC")


def test_macro_commands_are_case_insensitive_and_whitespace_tolerant():
    assert parse_command("  uk   eco  ") == Command(ticker="UK", market=None, function="ECO")


@pytest.mark.parametrize("raw", ["ECO", "UK LN ECO", "UK Equity ECO", "UK ECO EXTRA"])
def test_rejects_wrong_word_count_for_macro_commands(raw):
    assert isinstance(parse_command(raw), ParseError)


def test_rejects_unknown_subject_for_a_macro_function():
    result = parse_command("FR ECO")  # only UK is supported for ECO
    assert isinstance(result, ParseError)
    assert "subject" in result.message.lower()


def test_each_macro_function_has_its_own_subject_universe():
    # GBP is a valid FXC subject but not a valid GC subject.
    assert isinstance(parse_command("GBP GC"), ParseError)
    assert not isinstance(parse_command("GBP FXC"), ParseError)


def test_gc_accepts_both_us_and_uk():
    assert parse_command("US GC") == Command(ticker="US", market=None, function="GC")
    assert parse_command("UK GC") == Command(ticker="UK", market=None, function="GC")


def test_eco_accepts_both_uk_and_us():
    assert parse_command("UK ECO") == Command(ticker="UK", market=None, function="ECO")
    assert parse_command("US ECO") == Command(ticker="US", market=None, function="ECO")


def test_widened_macro_subjects_still_reject_everything_else():
    assert isinstance(parse_command("FR GC"), ParseError)
    assert isinstance(parse_command("FR ECO"), ParseError)


def test_equity_functions_still_reject_a_macro_style_command():
    result = parse_command("UK GP")
    assert isinstance(result, ParseError)


# --- Portfolio functions: TICKER:WEIGHT,TICKER:WEIGHT,... FUNCTION -----------------------------


def test_parses_a_valid_portfolio_command():
    result = parse_command("AAPL:0.6,MSFT:0.4 PORT")
    assert result == Command(
        ticker=None,
        market=None,
        function="PORT",
        holdings=[Holding(ticker="AAPL", weight=0.6), Holding(ticker="MSFT", weight=0.4)],
    )


def test_portfolio_weights_are_kept_as_typed_not_normalised_by_the_parser():
    # AAPL:2,MSFT:1 is a valid 2:1 ratio; normalising is analytics.normalize_weights's job.
    result = parse_command("AAPL:2,MSFT:1 PORT")
    assert result.holdings == [Holding(ticker="AAPL", weight=2.0), Holding(ticker="MSFT", weight=1.0)]


def test_portfolio_command_is_case_insensitive_and_tolerates_outer_whitespace():
    # The spec itself has no internal spaces (it is one token); only the whitespace
    # around it and before the function code is flexible, same as every other grammar.
    result = parse_command("   aapl:0.6,msft:0.4    PORT  ")
    assert result == Command(
        ticker=None,
        market=None,
        function="PORT",
        holdings=[Holding(ticker="AAPL", weight=0.6), Holding(ticker="MSFT", weight=0.4)],
    )


@pytest.mark.parametrize(
    "raw",
    [
        "PORT",  # no holdings at all
        "AAPL:0.6 PORT",  # only 1 holding
        "AAPL:0.5 MSFT:0.5 PORT",  # space instead of comma splits into 2 remainder tokens
    ],
)
def test_rejects_wrong_shape_portfolio_commands(raw):
    assert isinstance(parse_command(raw), ParseError)


@pytest.mark.parametrize(
    "raw",
    [
        "AAPL MSFT PORT",  # no ':' at all
        "AAPL:0.5,MSFT PORT",  # second piece has no ':'
        ":0.5,MSFT:0.5 PORT",  # missing ticker
        "AAPL:oops,MSFT:0.5 PORT",  # weight is not a number
        "AAPL:0,MSFT:0.5 PORT",  # weight is not positive
        "AAPL:-0.1,MSFT:0.5 PORT",  # weight is negative
        "AAPL:0.5,AAPL:0.5 PORT",  # duplicate ticker
    ],
)
def test_rejects_malformed_portfolio_specs(raw):
    assert isinstance(parse_command(raw), ParseError)


def test_macro_functions_still_reject_a_portfolio_style_command():
    assert isinstance(parse_command("AAPL:0.5,MSFT:0.5 ECO"), ParseError)
