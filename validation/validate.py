"""Record and report comparisons between this app's numbers and the real Bloomberg
terminal. Run as a module (not as a bare script), from the project root, so the
validation.* imports resolve:

    python -m validation.validate add       # interactively record one comparison
    python -m validation.validate report    # print a summary, update README.md

The raw comparisons (including every Bloomberg value) live only in
validation/comparisons.csv, which is gitignored. Only aggregated agreement counts,
never a value, ever reach README.md. See validation/README.md for the full explanation
and validation/common_mismatch_causes.md for how to diagnose a mismatch.
"""

import argparse
from datetime import date
from pathlib import Path

from validation.analysis import AGREEMENT_LABELS, categorize_agreement, compute_difference, compute_percent_difference
from validation.readme_sync import update_readme
from validation.storage import append_comparison, load_comparisons
from validation.summary import build_summary_markdown

CAUSES_DOC = Path(__file__).parent / "common_mismatch_causes.md"


def prompt(label, cast=str, default=None):
    suffix = f" [{default}]" if default is not None else ""
    while True:
        raw = input(f"{label}{suffix}: ").strip()
        if not raw and default is not None:
            return default
        if not raw:
            print("This field is required.")
            continue
        try:
            return cast(raw)
        except ValueError:
            print(f"Could not parse {raw!r} as {cast.__name__}; try again.")


def print_diagnostic_hint():
    print(
        "\nThat's outside a tight match. Usual causes, roughly most to least common here:\n"
        "  1. Price adjustment - split-only vs split+dividend (this app's Price basis toggle)\n"
        "  2. Date/window alignment - a different start/end date or 'as of' time\n"
        "  3. Day-count/annualisation convention - 252 vs 260 vs 365 days; sample vs population std\n"
        "  4. Log returns vs simple returns\n"
        "  5. Data source difference - Yahoo Finance vs Bloomberg's own pricing\n"
        f"See {CAUSES_DOC.relative_to(CAUSES_DOC.parent.parent)} for the full checklist."
    )


def cmd_add(_args):
    print("Recording a new comparison against the real Bloomberg terminal.")
    print("Stored only in validation/comparisons.csv (gitignored) - not printed to the README.\n")

    row = {
        "date_checked": prompt("Date checked (YYYY-MM-DD)", default=date.today().isoformat()),
        "function": prompt("Function (e.g. GP)").upper(),
        "ticker": prompt("Ticker as typed into the app (e.g. AAPL US)").upper(),
        "window": prompt("Window (e.g. '2y daily', '2026-01-01 to 2026-06-30')"),
        "metric": prompt("Metric (e.g. total_return, annualised_volatility, max_drawdown, 52w_high)"),
    }
    row["my_value"] = prompt("This app's value", cast=float)
    row["bloomberg_value"] = prompt("Bloomberg's value", cast=float)
    row["difference"] = compute_difference(row["my_value"], row["bloomberg_value"])
    row["explanation"] = prompt(
        "Explanation, if you already know one (blank is fine, especially if matched)", default=""
    )

    append_comparison(row)

    agreement = categorize_agreement(row["my_value"], row["bloomberg_value"])
    print(f"\nSaved. Agreement: {AGREEMENT_LABELS[agreement]}.")
    if agreement != "matched":
        print_diagnostic_hint()
    print("\nRun `python -m validation.validate report` to refresh the README summary.")


def cmd_report(_args):
    rows = load_comparisons()
    print(f"{len(rows)} comparison(s) recorded.\n")

    for row in rows:
        agreement = categorize_agreement(row["my_value"], row["bloomberg_value"])
        percent_difference = compute_percent_difference(row["my_value"], row["bloomberg_value"])
        percent_display = f"{percent_difference:.2f}%" if percent_difference is not None else "n/a"
        print(
            f"  {row['date_checked']}  {row['function']:<6} {row['metric']:<24} "
            f"{AGREEMENT_LABELS[agreement]:<24} (diff {percent_display})"
        )

    markdown = build_summary_markdown(rows)
    update_readme(markdown)
    print("\nREADME.md's 'Bloomberg validation' section updated (counts and labels only).")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("add", help="Record a new comparison (interactive)")
    subparsers.add_parser("report", help="Print a summary and update README.md")

    args = parser.parse_args()
    {"add": cmd_add, "report": cmd_report}[args.command](args)


if __name__ == "__main__":
    main()
