# Bloomberg validation

A tool for cross-checking this app's numbers against the real Bloomberg terminal by
hand, and keeping a record of how well they agree, **without ever putting a Bloomberg
value in the repo**.

## Why this is split the way it is

Bloomberg terminal data is licensed, not public. Even a handful of manually copied
numbers ("AAPL's 2-year total return was 50.08%") could be a problem to publish. So:

- **`validation/comparisons.csv`** holds every real number: your app's value, the
  Bloomberg value, the difference, an explanation. It is **gitignored**
  (`.gitignore` at the project root) and must never be committed.
- **`validation/comparisons.example.csv`** is checked into the repo instead, with
  fabricated numbers clearly labelled as fabricated, so the file format is documented
  without any real data.
- **`README.md`** (the project's main one) gets an auto-generated section with only
  *counts* — "3 of 4 GP comparisons matched within 0.5%" — never a value, a ticker, or
  a date beyond "most recent". `validation/summary.py` builds that section and is
  tested to guarantee it (`test_build_summary_markdown_never_contains_a_bloomberg_or_my_value`
  and `..._never_contains_a_ticker` in `test_validation.py`).

## Recording a comparison

1. Look a number up in this app (e.g. `AAPL US GP`'s total return).
2. Look up the equivalent number on the real Bloomberg terminal, matching the window
   and settings as closely as you can (see "getting a fair comparison" below).
3. From the project root (not from inside `validation/` — it must run as a module so
   its own imports resolve):
   ```bash
   python -m validation.validate add
   ```
   and answer the prompts. It computes the difference for you and tells you the
   agreement level immediately.
4. Run:
   ```bash
   python -m validation.validate report
   ```
   to print every recorded comparison and refresh the "Bloomberg validation" section
   in the project's `README.md`.

## Getting a fair comparison

Match these before you conclude the numbers disagree:

- **Price basis**: this app's dividend-adjusted vs split-adjusted toggle (GP, HP) —
  make sure Bloomberg's adjustment setting matches.
- **Window**: this app uses a fixed rolling 2 years ending at the latest close; set
  Bloomberg to the same start and end date, not just "2 years".
- **Units**: London-listed prices are in pence here (and on Yahoo); Bloomberg may
  default to pounds. A "mismatch" that's suspiciously close to a factor of 100 is
  almost always this.

If a comparison still doesn't match, see
[common_mismatch_causes.md](common_mismatch_causes.md) for the full, ranked checklist,
or `validate.py add` will print a short version of it automatically for anything that
isn't a tight match.

## Files

| File | Job |
|---|---|
| [analysis.py](analysis.py) | Pure maths: difference, percentage difference, and the matched/close/mismatch thresholds. No file I/O. Tested in `../test_validation.py`. |
| [summary.py](summary.py) | Builds the README's markdown block from a list of comparisons. Pure string building, tested for containing no Bloomberg data. |
| [storage.py](storage.py) | Reads and writes `comparisons.csv`. |
| [readme_sync.py](readme_sync.py) | Splices `summary.py`'s output into the project's `README.md` between marker comments. |
| [validate.py](validate.py) | The CLI: `add` (record one comparison) and `report` (print + update the README). |
| [common_mismatch_causes.md](common_mismatch_causes.md) | The ranked diagnostic checklist. |
| [comparisons.example.csv](comparisons.example.csv) | The file format, with fabricated numbers. Never edit `comparisons.csv` directly by hand except to match this shape. |

## Schema

| Column | Meaning |
|---|---|
| `date_checked` | When you compared it, `YYYY-MM-DD`. |
| `function` | The terminal function, e.g. `GP`. |
| `ticker` | Exactly as typed into this app, e.g. `AAPL US`. |
| `window` | The window/settings used, e.g. `2y daily dividend-adjusted`. Free text — precise enough that you could reproduce it later. |
| `metric` | Which specific number within that function's output, e.g. `total_return`, `annualised_volatility`, `max_drawdown`, `52w_high`. Functions like GP report several numbers at once, so this says which one. |
| `my_value` / `bloomberg_value` | Plain numbers, in the units you'd read off the screen (e.g. `28.8` for 28.8%, not `0.288`) — agreement is a *relative* percentage, so the units just need to match between the two columns. |
| `difference` | `my_value - bloomberg_value`, computed for you by `validate.py add`. |
| `explanation` | Optional. A cause from `common_mismatch_causes.md`, or your own note. |

`metric` isn't part of what was originally asked for; I added it because `function`
alone doesn't say which of a function's several numbers (e.g. GP's return, volatility
*and* drawdown) a row is about. Say if you'd rather drop it.
