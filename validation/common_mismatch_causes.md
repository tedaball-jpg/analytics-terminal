# Diagnosing a mismatch against Bloomberg

Check these roughly in order — the first three explain most real mismatches in this app.

## 1. Price adjustment

**What it is:** whether prices are adjusted for stock splits only, or for splits and dividends.

**How it shows up:** returns and volatility differ, usually by more the further back the window goes; price *levels* (a specific day's close) can be off by a large, obvious factor if a split happened in the window.

**Check here:** GP and HP have a **Price basis** toggle (`Dividend-adjusted (total return)` vs `Split-adjusted only (price return)`). Make sure you compared against the matching Bloomberg setting — on the terminal this is usually a "Corporate Actions" / adjustment setting on the pricing function, not the default. See `README.md`'s "Price basis" note and each function's learn file.

## 2. Date/window alignment

**What it is:** a different start date, end date, or "as of" cut-off time than you think you're comparing.

**How it shows up:** returns and volatility both differ, often by a similar-looking amount, because the two windows overlap but aren't identical.

**Check here:** this app's price window is a fixed rolling 2 years ending at the last available close (see "Known weaknesses" in the README — there's no date-range picker). Bloomberg lets you set exact start/end dates. Match the end date first, then count back the same number of calendar days or trading days, not "2 years" loosely.

## 3. Day-count / annualisation convention

**What it is:** how many trading days a year is assumed to have, and whether volatility uses the sample (n-1) or population (n) standard deviation.

**How it shows up:** volatility (and anything derived from it) is off by a small, fairly consistent percentage, not wildly different.

**Check here:** this app always annualises with **252 trading days** and the **sample** standard deviation (`analytics.annualised_volatility`, `TRADING_DAYS_PER_YEAR = 252`). Bloomberg functions can differ (260 or 365 are also used elsewhere in finance for other conventions). If a volatility mismatch is small and roughly proportional to `sqrt(252/N)` for some other N, this is very likely it.

## 4. Log returns vs simple returns

**What it is:** this app uses **simple** returns everywhere (`P_t / P_(t-1) - 1`), never log returns (`ln(P_t / P_(t-1))`). The two are close for small daily moves but diverge for large ones or over long compounding windows.

**How it shows up:** cumulative/total return differs more than volatility does, especially over a volatile window; the gap grows with the size of individual day-to-day moves.

**Check here:** every return in `analytics.py` (`simple_returns`, `total_return`, `cumulative_return`) is a simple return. If Bloomberg's number came from a log-return-based calculation, expect a small, direction-dependent gap.

## 5. Data source

**What it is:** this app always uses **Yahoo Finance**. Bloomberg's own prices can differ slightly from Yahoo's, especially around dividends, corporate actions, or for less liquid instruments.

**How it shows up:** small, otherwise unexplained differences that don't match any of the above, most often in the last few decimal places of a price level.

**Check here:** not fixable from this app's side; it's a real difference in the underlying data, not a bug. Worth noting in the `explanation` column so it isn't re-investigated later.

## 6. Currency and units

**What it is:** London-listed stocks are quoted in pence on this app (and on Yahoo). Reading a price as pounds instead of pence is a factor-of-100 error that looks like a huge mismatch but isn't one.

**Check here:** every equity function's learn file and caption calls this out. If a "mismatch" is suspiciously close to a factor of 100, this is almost certainly it.

## 7. Rounding and display precision

**What it is:** Bloomberg may round or truncate a displayed figure differently than this app does.

**How it shows up:** a mismatch under about 0.1%, especially on a manually typed-in value — check you didn't drop a digit when reading the screen.
