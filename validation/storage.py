"""CSV read/write for the private comparisons file. Not unit-tested (it's file I/O, not
maths), but kept small and separate from analysis.py so the maths stays easy to test."""

import csv
from pathlib import Path

FIELDS = [
    "date_checked",
    "function",
    "ticker",
    "window",
    "metric",
    "my_value",
    "bloomberg_value",
    "difference",
    "explanation",
]

COMPARISONS_PATH = Path(__file__).parent / "comparisons.csv"


def load_comparisons(path=COMPARISONS_PATH):
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        row["my_value"] = float(row["my_value"])
        row["bloomberg_value"] = float(row["bloomberg_value"])
        row["difference"] = float(row["difference"])
    return rows


def append_comparison(row, path=COMPARISONS_PATH):
    is_new_file = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if is_new_file:
            writer.writeheader()
        writer.writerow(row)
