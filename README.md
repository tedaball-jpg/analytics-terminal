# Analytics Terminal

A Bloomberg-style terminal built with Python and Streamlit. Type a command like `AAPL US GP` into the command bar; the app parses it into a subject and a function code, then routes it to the matching module. It has the command bar, parser, router, seven working functions (equity: **GP**, **DES**, **HP**, live from Yahoo Finance; macro: **ECO**, **GC**, **FXC**, from ONS, the Bank of England and Yahoo; portfolio: **PORT**, a weighted basket with a GARCH(1,1) volatility fit) and a Learn panel that teaches each one.

## Run it

```bash
pip install streamlit pytest pyyaml yfinance pandas matplotlib arch
python -m streamlit run app.py
python -m pytest -v
```

## Commands

There are two command grammars, because an equity ticker needs an exchange to disambiguate it (AAPL could be listed in several places) and a macro subject (a country or currency) does not.

**Equity functions:** `TICKER MARKET FUNCTION` (case-insensitive, extra spaces ignored). The Bloomberg form with the security type, `TICKER MARKET Equity FUNCTION`, also works; `Equity` is checked and then dropped, and it is the only security type accepted.

| Function | Name | Output |
|---|---|---|
| `GP` | Graph Price | Line chart of 2 years of daily closes, plus total (or price) return, annualised volatility and maximum drawdown with its peak and trough dates |
| `DES` | Description | Company table (name, exchange, quote currency, country, sector, industry, market cap, employees, website), a price snapshot (last close, 52-week high and low, distance below the high) and the business summary; `n/a` where Yahoo has no data |
| `HP` | Historical Price Table | 2 years of open/high/low/close/volume and a Change % column, newest first, switchable between Daily, Weekly and Monthly rows, with volatility annualised by the matching factor (252, 52 or 12) |

GP and HP have a **price basis** switch: *dividend-adjusted (total return)*, for returns, or *split-adjusted only (price return)*, for price levels. Yahoo does not provide raw, never-adjusted quotes.

| Market | Meaning |
|---|---|
| `US` | US-listed (no suffix) |
| `LN` | London (`.L` suffix; prices are in pence) |

Examples: `AAPL US GP`, `AZN LN Equity DES`, `AAPL US HP`.

**Macro functions:** `SUBJECT FUNCTION`, no market, no `Equity` word.

| Function | Name | Subject | Output |
|---|---|---|---|
| `ECO` | Economic Calendar | `UK` only | Latest CPI, GDP and Bank Rate readings with the change from the previous reading and a trend chart, from ONS and the Bank of England |
| `GC` | Government Curve | `US` only | The US Treasury yield curve (3-month, 5-year, 10-year, 30-year) and the 10-year-minus-3-month spread, flagged Inverted or Normal |
| `FXC` | FX Cross Rates | `USD`, `GBP`, `EUR` or `JPY` | The subject's rate against the other three, plus the full 4x4 cross-rate matrix, all from Yahoo Finance |

The subject universes are small on purpose: ONS and the Bank of England only give this app UK data, and Yahoo has no free UK gilt yield series, so GC is US-only. `command_parser.MACRO_SUBJECTS` is the single place that lists what each macro function accepts.

Examples: `UK ECO`, `US GC`, `GBP FXC`.

**Portfolio functions:** `TICKER:WEIGHT,TICKER:WEIGHT,... FUNCTION` (the whole ticker:weight list is one word, no spaces in it; at least 2 holdings; weights must be positive but don't need to sum to 1 — they're normalised).

| Function | Name | Output |
|---|---|---|
| `PORT` | Portfolio & Risk Analytics | Weights table, cumulative return chart, total return/annualised volatility/max drawdown, a correlation matrix (chart and table), and a volatility section: GARCH(1,1) conditional volatility plotted against flat historical volatility, with the fitted alpha/beta |

Tickers are typed as raw Yahoo tickers (e.g. `AZN.L` for London), unlike the equity grammar, which hides that suffix — a basket can mix markets, and there is nowhere to put a market code once you have several tickers in one word.

Examples: `AAPL:0.6,MSFT:0.4 PORT`, `AAPL:2,MSFT:1 PORT` (a 2:1 ratio, normalised the same way).

Do not type `<GO>` in any grammar; it is a key press on the real terminal, not a word in the command.

## Design: layers

| File | Job |
|---|---|
| [command_parser.py](command_parser.py) | Turns text into a `Command(ticker, market, function, holdings)` or a `ParseError`. Three grammars (equity, macro, portfolio), one function each, picked by which set the function code (always the last word) belongs to. Plain Python, no Streamlit. |
| [market_data.py](market_data.py) | The equity **data layer**: fetching prices (adjusted or split-adjusted) and company info from yfinance, resampling daily rows into weekly/monthly, formatting. No Streamlit. |
| [macro_data.py](macro_data.py) | The macro **data layer**: UK CPI/GDP/Bank Rate from ONS and the Bank of England (moved and refactored from `macro_dashboard.py`), the US Treasury curve and FX rates from yfinance. Raises `DataUnavailable` on failure instead of returning `None`; no Streamlit. |
| [analytics.py](analytics.py) | The **calculations**: returns, total return, annualised volatility, drawdown, trailing 52-week range, latest-reading deltas, curve spread/inversion, FX cross-matrix triangulation, weight normalisation, portfolio returns, correlation matrix. Pure functions on pandas data, no Streamlit or yfinance. |
| [volatility.py](volatility.py) | The **GARCH(1,1) module**: scaling returns for `arch`, the recursion formula, its long-run (steady-state) variance, and `fit_garch()`, which wraps `arch_model(...).fit()`. No Streamlit. |
| [functions.py](functions.py) | Router: a dict mapping function codes to Streamlit handlers (GP, DES, HP, ECO, GC, FXC, PORT), plus the cached download wrappers. Handlers only call the data layer and the calculations, then display, and catch failures into a clean `st.error`/`st.warning`. |
| [app.py](app.py) | Streamlit UI: command bar, calls the parser, shows the error or calls the routed handler. |
| [markets.py](markets.py) | Market code to yfinance suffix (`US` -> `""`, `LN` -> `.L`); equity functions only. |
| [portfolio.py](portfolio.py) | Earlier portfolio/volatility script. It now imports `simple_returns`, `annualised_volatility` and `cumulative_return` from `analytics.py`, `fit_garch` from `volatility.py`, and `bank_rate_changes`/`fetch_bank_rate_readings` from `macro_data.py` (all used to be untested copies, some via `macro_dashboard.py`). `plot_price_history()`, `plot_correlation_heatmap()` and `plot_garch_vs_flat()` are reused live by GP and PORT; `main()` still saves them as PNGs for the standalone script. |
| [macro_dashboard.py](macro_dashboard.py) | Earlier standalone UK macro script. Now imports its fetch and parse functions from `macro_data.py` instead of defining its own; its own plotting and `main()` are unchanged. |
| [verify_calculations.py](verify_calculations.py) | Independent checks of the equity calculations against live data (see below). |
| [validation/](validation/README.md) | Compares this app's numbers against the real Bloomberg terminal by hand and tracks agreement over time, without ever storing a Bloomberg value in the repo (see below). |

**Why split it:** the parser, both data layers and the calculations have no Streamlit dependency, so they are unit-tested without a browser. Streamlit code (handlers, caching, layout, error display) stays in `functions.py` and `app.py`. Each layer has one job, so changing one doesn't break the others. Numbers are never computed inside a handler, so every number on screen comes from a tested function. Two standalone scripts (`portfolio.py`, `macro_dashboard.py`) now import from the shared data/calculation layers instead of each other or duplicating logic, so there is one definition of each formula. GARCH got its own module rather than living in `analytics.py`: it is a different kind of maths (a numerical fit, not a closed-form formula), and it was asked for as "a volatility module" specifically.

## How to verify the calculations

Run `python verify_calculations.py` (needs internet). It compares the app's numbers, computed with pandas, against numbers produced a different way:

| Section | What it does |
|---|---|
| A. Hand-worked example | A 4-price series whose return, volatility and drawdown can be worked out on paper. |
| B. Plain-Python re-implementation | Recomputes total return, compounded return, volatility, max drawdown and the 52-week range with loops and the `math` module only, and rebuilds the weekly table by grouping on ISO weeks (a different rule from pandas' week-ending-Friday). |
| C. Dividend reconciliation | Rebuilds total return from split-adjusted closes plus the dividends actually paid, without touching Yahoo's adjusted series, and compares it with the dividend-adjusted return. |
| D. Properties | Changing units (pounds to pence) must not change any return statistic; drawdown must lie between -100% and 0%. |

It exits with status 1 if any check fails. Latest run: 24 of 24 pass. The dividend check matched Yahoo to 5e-8 once the reinvestment convention was matched. My first version compared against a different convention (dividend added to the ex-date close instead of scaling the previous close down) and differed by about 0.01 percentage points (0.014 in one run, 0.007 in another, as live data moved). That was a convention difference, not an error, and the script now tests both, one tightly and one loosely.

What this cannot prove: that Yahoo's prices are correct, or that the conventions (252 trading days, sample standard deviation, simple returns) are the ones you want. Two manual checks cover that:

1. **Excel:** use the table's built-in "Download as CSV" on `HP`, recompute a return (`=C3/C2-1`) and a volatility (`=STDEV.S(range)*SQRT(252)`), and compare with the app.
2. **Real terminal:** set the same dates and price basis on Bloomberg and compare prices, the 52-week range, and a historical volatility figure. The Learn panel's "Try it on the terminal" checklist lists these steps.

The section below this paragraph is generated by [validation/validate.py](validation/validate.py) (`python -m validation.validate report`) and only ever contains counts and agreement labels, never a value: the real comparisons, including every Bloomberg number, live in `validation/comparisons.csv`, which is gitignored and never committed. See [validation/README.md](validation/README.md) for why it's split this way, how to record a comparison, and [validation/common_mismatch_causes.md](validation/common_mismatch_causes.md) for a ranked checklist (price adjustment, date/window alignment, day-count convention, log vs simple returns, data source, currency/units, rounding) if a number doesn't match.

<!-- VALIDATION:START (generated by validation/validate.py report - do not edit by hand) -->

## Bloomberg validation

No comparisons recorded yet. See [validation/README.md](validation/README.md) to add one after checking a number against the real Bloomberg terminal.

<!-- VALIDATION:END -->

## Learn panel

A toggleable panel beside every function's output that teaches the function: what it does on the real Bloomberg terminal, why analysts use it, key concepts, how to read the output, common mistakes, interview questions with model answers, a checklist to try on the real terminal, and related functions.

The content is **data, not UI code**: one YAML file per function in [learn/](learn/) (`GP.yaml`, `HP.yaml`, `DES.yaml`, `ECO.yaml`, `GC.yaml`, `FXC.yaml`, `PORT.yaml`). Adding a function's panel means adding a file; `app.py` never changes.

| File | Job |
|---|---|
| [learn/*.yaml](learn/GP.yaml) | The content. GP explains adjusted prices, returns, volatility and drawdown; GC explains yield curve shape before the function is described further, since that concept has to be understood before the chart makes sense. |
| [learn_loader.py](learn_loader.py) | Loads a file and validates it (all fields required and non-empty, unknown keys rejected, mnemonic must match the filename). No Streamlit. |
| [learn_panel.py](learn_panel.py) | Renders a loaded file: a scrollable container with expanders for interview questions and checkboxes for the checklist. |
| [test_learn_loader.py](test_learn_loader.py) | Fails if any function in the router has no learn file, or a file is missing or has a blank field. |

Schema (every field required; `related_functions` may be an empty list):

```yaml
mnemonic: GP                 # must equal the filename and the function code
full_name: Graph Price
what_it_does: ...            # text, markdown allowed
why_analysts_use_it: ...
key_concepts: [{term, explanation}, ...]
how_to_read_the_output: [...]
common_mistakes: [...]
interview_questions: [{question, model_answer}, ...]
terminal_checklist: [...]
related_functions: [HP, DES, GIP]   # any well-formed mnemonic; the panel marks which exist here
```

Trade-offs: YAML reads well for prose but is whitespace-sensitive and turns unquoted `NO`/`ON` into booleans (the validator checks types); strict validation catches typos but means no stub files; the validator is hand-written to avoid a schema dependency; `related_functions` isn't checked against built functions so it can point at real Bloomberg functions not built here.

The Bloomberg content was written from general knowledge, not from a terminal. Verify each claim with the `terminal_checklist` before relying on it.

## Design choices

- **Parser returns a result, not exceptions.** Bad input is normal for a command bar, not exceptional.
- **`FUNCTION_CODES` (in the parser) is the single source of truth for valid codes.** `functions.py` asserts its handler dict has exactly those keys, so the two can't silently drift. (I first had the parser import the handlers, which pulled Streamlit into it, so I flipped the dependency.)
- **Market suffixes are hidden from the user.** Yahoo uses `AAPL` for US stocks but `AZN.L` for London; the terminal takes care of that.
- **GP, DES and HP all fetch through `market_data.py`.** `portfolio.fetch_prices()` (generalised to take `tickers`, `period`, `interval` with defaults) remains for the portfolio script only.
- **Calculations live in `analytics.py`, never in a handler.** Each statistic is a small pure function with hand-worked tests, and `portfolio.py` imports them instead of keeping its own copies.
- **Price basis is an explicit choice.** Returns use dividend-adjusted prices (they include dividends). Price levels (last close, 52-week range) use split-adjusted prices, which are closest to what actually traded. DES uses split-adjusted for its snapshot for that reason.
- **Volatility is annualised by periodicity.** `PERIODS_PER_YEAR` maps Daily/Weekly/Monthly to 252/52/12, and a test fails if a periodicity is added without a factor.
- **`plot_price_history` returns a figure instead of saving a PNG.** Older plot functions save report images; the terminal renders live via `st.pyplot()`, and GP closes each figure so reruns don't accumulate them in memory.
- **HP resampling follows the OHLCV rules.** A week or month's open is its first day's open, high is the highest high, low the lowest low, close the last close, volume the sum. Rows are dated by the last trading day in the period, not the calendar period end, so the current unfinished week or month never shows a future date.
- **DES treats "no company name" as "not found".** For an unknown ticker Yahoo returns a nearly empty record instead of an error, so the app checks for a name.
- **DES does not label market cap with a currency.** Yahoo does not state it (for London stocks the quote currency is pence, but the market cap is clearly not in pence), so guessing would be wrong by a factor of 100. The page says so and points you at the real terminal.
- **Only the fields DES uses are kept from Yahoo's large `info` record**, which keeps the cached data small and the code's dependence on Yahoo's field names explicit.
- **Macro functions use a different grammar (`SUBJECT FUNCTION`) instead of reusing `TICKER MARKET`.** A market code disambiguates an exchange; a country or currency code needs no exchange, so forcing one in would be meaningless (`UK US ECO`?) rather than just unused. The function code is found as the *last* word of any command, which is what lets one parser support both grammars without the caller declaring which one it means.
- **Each macro function has its own subject universe (`MACRO_SUBJECTS`), not a shared one.** `GBP` is valid for FXC but not GC; `US` is valid for GC but not ECO. This is realistic (Bloomberg functions vary in what they cover) and it means adding a country later is a one-line change to a dict, not a new code path.
- **`macro_data.py` raises `DataUnavailable` instead of returning `None`.** The functions it replaced (moved from `macro_dashboard.py`) caught exceptions internally and printed to the console, which is invisible in a web app. Handlers now catch the exception and show `st.error`/`st.warning`, the same pattern DES already used for yfinance failures, so all data-source failures in the app are handled the same way.
- **ECO fetches CPI, GDP and Bank Rate independently, each in its own try/except.** One source being down (ONS, say) shows a warning only for that indicator; the other two still render. This mirrors `macro_dashboard.py`'s original per-series resilience, expressed as exceptions instead of `None`-checking.
- **GC's chart spaces maturities by actual years, not evenly.** The gap from 3 months to 5 years is genuinely much bigger than 5 to 10 years; spacing the four points evenly would flatten the short end of the curve, which is often where the interesting shape is.
- **FXC triangulates every rate through USD rather than fetching each pair directly.** One consistent data source (`USD<code>=X` for every currency) is simpler to reason about and test than mixing direct-quote conventions (`GBPUSD=X` vs `USDJPY=X`), at the cost of a small, expected gap against a directly-quoted pair.
- **PORT is a third grammar (`TICKER:WEIGHT,... FUNCTION`), not a variant of the other two.** A basket is a list of an unknown length, which doesn't fit a fixed number of positional words; encoding it in one comma-separated token keeps the "function is always the last word" rule intact for every grammar.
- **Weights are normalised, not required to sum to 1.** Requiring an exact sum (even to 1.00 with a tolerance) is a common source of a frustrating, avoidable error; dividing by the sum accepts both raw ratios (`2,1`) and pre-normalised fractions (`0.667,0.333`) without the user having to get the arithmetic exactly right themselves.
- **PORT assumes fixed weights, rebalanced daily.** A true buy-and-hold portfolio's weights drift as prices move, which needs tracking each holding's position size over time, not just applying one set of weights to every day's returns. I built the simpler, more common textbook version and said so in the learn file rather than silently overclaiming what the number means.
- **PORT tickers are raw Yahoo tickers, not the equity grammar's hidden-suffix convention.** A basket can mix US and London stocks in one comma-separated word; there's nowhere to attach a market code per ticker without a much more complex spec syntax, so this app trades that convenience away for the multi-asset case and documents it.
- **`compute_portfolio` is one cached function that fetches and computes, not several small cached steps.** Streamlit's cache can hash a tuple of tickers and weights (the function's actual arguments) without needing to decide whether it can also hash a pandas Series or DataFrame as a cache key; the individual calculations inside it are still the same independently tested functions from `analytics.py` and `volatility.py`.
- **GARCH parameters (omega, alpha, beta) are extracted by name from `arch`'s fitted result (`result.params["alpha[1]"]`), not by position.** `arch`'s parameter order isn't part of any promise it makes; the names are.
- **`fit_garch` also returns `mu`, the fitted mean return**, even though no handler currently displays it, because it's needed to demean returns correctly when reproducing the recursion independently (see verification, below) — a byproduct of testing the formula properly, not speculative future-proofing.

## Testing

- 38 pytest cases on the parser: valid input, lowercase, messy whitespace, the `Equity` form, wrong word counts, unknown market/function, valid and invalid macro commands, each macro function's own subject universe, valid and malformed portfolio commands (bad ratios, non-numeric weights, non-positive weights, duplicate tickers, too few holdings), and each grammar rejecting the other two's style of command.
- 41 pytest cases on the Learn loader: every function must have a valid learn file, and each kind of problem (missing field, blank field, empty list, unknown key, wrong mnemonic, malformed record, bad related mnemonic, missing file, broken YAML) is reported. (Caught two real bugs of exactly this kind while writing GC/FXC/PORT's own learn files — an unquoted colon in a bullet point silently turned it into a one-key mapping instead of text.)
- 27 pytest cases on `market_data.py`: weekly/monthly aggregation checked by hand against known numbers (open first, high max, low min, close last, volume sum), holiday weeks dropped, rows dated by last trading day, annualisation factors, percent and market cap formatting, and the company table with missing fields.
- 41 pytest cases on `analytics.py`: returns, total return, volatility (worked out on paper: daily std = 2a/sqrt(3)), compounding vs adding, annualisation factors, drawdown depth and dates, unit-change invariance, trailing range, latest-reading deltas, curve spread/inversion, FX cross-matrix triangulation (checked by hand, reciprocal, transitive A->B->C = A->C, and unaffected by rescaling the anchor currency), weight normalisation (raw ratios and pre-normalised fractions), portfolio returns (hand-computed: opposite $\pm$10% moves cancel to 0% equal-weighted, to $\pm$4% at 70/30), and correlation (identical series = 1, opposite series = -1, diagonal = 1).
- 14 pytest cases on `volatility.py`: the scaling arithmetic by hand, the GARCH(1,1) recursion by hand (`sigma^2_t = omega + alpha*epsilon^2_(t-1) + beta*sigma^2_(t-1)`, e.g. `0.1 + 0.2*4 + 0.7*9 = 7.2`), the long-run variance formula by hand and its boundary case (`alpha + beta >= 1` must raise), the recursion converging to the long-run formula under 2000 iterations with no new shocks, and — the strongest check — refitting on a fixed-seed synthetic series and reimplementing the recursion from the fitted parameters, reproducing `arch`'s own conditional volatility to within `1e-8`.
- 8 pytest cases on `macro_data.py`: `parse_month`/`parse_quarter` by hand, `bank_rate_changes` collapsing a flat run, and `fetch_json_series` raising `DataUnavailable` (not returning `None`) on a network error or a malformed response.
- 169 tests in total, all passing, plus the 24 live checks in `verify_calculations.py` (equity functions only).
- Checked by hand in the browser: `AAPL US GP` (chart, three statistics, price-basis switch changes the label and value), `AZN LN GP` (chart in pence), `AAPL US DES` and `AZN LN Equity DES` (company tables and price snapshot; the 52-week high/low matched the independent script exactly), `AAPL US HP` (500 daily rows, 105 weekly, 25 monthly; volatility label and value change with periodicity), `AZN LN HP` (prices in pence), `ZZZZZZ US GP/DES/HP` (clean errors), `UK ECO` (three metrics and trend charts), `US GC` (curve chart with realistic maturity spacing, +0.95pp spread flagged Normal), `GBP FXC` (cross-rate matrix, diagonal 1.0000, reciprocal and consistent), and `AAPL:0.6,MSFT:0.4 PORT` (weights table showing 60.0%/40.0%, cumulative return chart, three metrics, a correlation heatmap and table showing 0.32, and a GARCH-vs-flat chart whose volatility spike visibly lined up with the reported max-drawdown trough date). `AAPL:0.5,ZZZZZZ:0.5 PORT` gave a clean "No price data found for: ZZZZZZ" instead of a stack trace.
- Graceful-failure requirement verified directly, not just by code review: I monkeypatched each data-layer fetch to raise (simulating ONS, the Bank of England and yfinance being down) and called the handlers standalone; all three (`render_indicator`, `yield_curve`, `fx_cross_rates`) caught the failure and returned without raising.
- Only pure logic (parser, Learn loader, `market_data.py`, `macro_data.py`, `analytics.py`, `volatility.py`) has automated tests; the Streamlit handlers and the panel UI were checked by hand.

## Known weaknesses

- Downloads are cached (`st.cache_data`): prices for 10 minutes, company info for an hour, so data can be that stale.
- DES depends on Yahoo's `info` endpoint, which is less reliable than the price download: fields can be missing (shown as `n/a`) and it can be rate-limited (shown as an error). yfinance also prints a 404 to the server console for unknown tickers.
- GP and HP are a fixed 2-year window; there is no date-range picker. A monthly volatility from two years rests on only about 24 returns, so it is noisy (for Apple: about 29% from daily returns, about 22% from monthly).
- The latest daily bar is live, so figures can change in the last decimal between refreshes.
- Streamlit does not hot-reload changed modules reliably here; restart `streamlit run` after editing `command_parser.py`, `functions.py`, `market_data.py` or `analytics.py`.
- Learn checklist ticks are lost when the panel is hidden or you switch function (Streamlit drops the state of widgets that aren't rendered).
- The `assert` crashes the app at import time if the code lists drift; fine for a solo project, not for production.
- Only 2 markets and 6 function codes, hardcoded.
- Macro subject coverage is narrow by necessity: ECO is UK-only, GC is US-only, FXC covers 4 currencies. Widening any of them means finding a free data source, not just a config change.
- GC is missing the 2-year Treasury point (no free source found), so it uses the 10-year-minus-3-month spread rather than the also-common 10-year-minus-2-year one.
- FXC's cross rates are triangulated through USD, not fetched directly, so a rate can differ very slightly from a directly-quoted pair for the same two currencies.
- Cached macro/yield/FX data is 10-40 minutes old depending on the source (prices and FX 10 minutes, company info and UK economic data an hour).
- PORT assumes daily rebalancing to fixed weights, not buy-and-hold; the two give different numbers, especially over longer windows or after one holding has moved a lot relative to the others.
- PORT needs at least `MIN_PORTFOLIO_HISTORY` (30) overlapping trading days to run at all, and a GARCH fit on a short or unusual history can be unstable even above that floor; there's no minimum-quality check on the fit itself, only a stationarity check (`alpha + beta < 1`).
- PORT's tickers are raw Yahoo tickers, so a basket of `.L` and bare US tickers mixes two different currencies' prices into one correlation matrix without converting them, which is fine for correlation (a ratio-based measure) but would be wrong if the app ever reported currency-mixed portfolio value in one number.
- GARCH fitting is the slowest thing in the app (typically 1-3 seconds for 2 years of daily data); it's cached, but the first PORT command for a given basket and weights pays that cost.

## Concepts worth being able to explain

- **Session state:** Streamlit reruns the whole script on every interaction; `st.session_state` remembers the last command.
- **Dataclass:** a lightweight structured record (`Command`) without boilerplate.
- **yfinance MultiIndex columns:** data comes back with columns like `('Close', 'AAPL')`, hence `["Close"]` then the ticker.
- **Invalid tickers:** yfinance returns an empty DataFrame for prices and a nearly empty record for company info, rather than raising, so the app checks `.empty` (prices) and for a missing name (DES).
- **Resampling:** `DataFrame.resample("W-FRI")` groups daily rows into weeks ending Friday and `"ME"` into calendar months; `.agg({...})` then applies a different rule to each column, which is how OHLCV rows are collapsed correctly.
- **Adjusted prices:** `auto_adjust=True` rescales history for splits and dividends (use it for returns); `auto_adjust=False` adjusts for splits only (use it for price levels). Yahoo has no raw, never-adjusted option, so old prices are not the prices actually quoted at the time.
- **Total vs price return:** total return includes dividends. On Yahoo's convention the ex-dividend day's growth is `C_t / (C_(t-1) - D_t)`; adding the dividend to the day's close gives a slightly different number (about 0.01 percentage points over two years for Apple).
- **Annualising volatility:** the daily sample standard deviation times the square root of 252, because variance grows in proportion to time if returns are independent. Weekly data uses 52 and monthly 12.
- **Maximum drawdown:** the worst fall from a previous peak, `price / running_max - 1`; it captures the worst episode, which volatility does not.
- **Yield curve inversion:** when a shorter maturity yields more than a longer one (a negative long-minus-short spread). It has preceded most US recessions historically, with a lead time that varies widely, which is why it is a warning sign and not a countdown.
- **Currency triangulation:** deriving a cross rate (GBP/JPY) from two rates against a common anchor currency (GBP/USD and USD/JPY) rather than fetching it directly; this is also the mechanism behind triangular arbitrage.
- **Level change vs percentage change:** for a series that is already a percentage (CPI, GDP growth, Bank Rate), a change is reported in percentage points (2.3% to 2.1% is -0.2 points), not as a percentage of the previous value (which would misleadingly say -8.7%).
- **Weight normalisation:** dividing each weight by their sum, so `2,1` and `0.667,0.333` give the same portfolio; the underlying formula is `w_i = weight_i / sum(weights)`.
- **Correlation vs diversification:** correlation (-1 to +1) measures how two return series move together; combining assets that are not perfectly correlated can make a portfolio less volatile than the weighted average of its parts, because their moves partly offset — the lower the correlation, the bigger the effect.
- **GARCH(1,1):** models variance as `sigma^2_t = omega + alpha*epsilon^2_(t-1) + beta*sigma^2_(t-1)` — a constant floor, plus a share (alpha) of yesterday's squared shock, plus a share (beta) of yesterday's variance. `alpha + beta < 1` is required for the process to be stationary (mean-reverting); the level it reverts to is `omega / (1 - alpha - beta)`.
- **Why GARCH beats a single "flat" volatility number:** markets have calm and turbulent periods (volatility clustering); GARCH reacts to recent shocks and fades back toward a long-run average, instead of treating volatility as constant.

## Next steps

Add a date-range picker for GP and HP, and a rebased comparison of two securities. For the macro functions: widen ECO beyond the UK and GC beyond the US if a free data source turns up, and add the 2-year Treasury point to GC if one does. For PORT: a Sharpe ratio (the formula already exists, untested, in `portfolio.py`), a buy-and-hold mode alongside the current fixed-weight one, and a per-holding volatility breakdown next to the portfolio-level GARCH fit.
