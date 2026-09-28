from datetime import date, timedelta

import matplotlib.pyplot as plt

from macro_data import (
    CPI_URL,
    GDP_URL,
    DataUnavailable,
    bank_rate_changes,
    fetch_bank_rate_readings,
    fetch_json_series,
    parse_month,
    parse_quarter,
)

TEN_YEARS_AGO = date.today() - timedelta(days=365 * 10)


def print_table(title, entries, value_label):
    print(title)
    print(f"{'Date':<10} {value_label:>22}")
    print("-" * 33)
    for entry in entries:
        print(f"{entry['date']:<10} {entry['value']:>22}")
    print()


def annotate_latest(ax, x, y):
    ax.scatter([x], [y], color="black", zorder=5, s=20)
    ax.annotate(
        f"{y:g}%",
        xy=(x, y),
        xytext=(8, 8),
        textcoords="offset points",
        fontweight="bold",
    )


def plot_series(ax, title, dates, values, color):
    if not dates:
        ax.set_title(title)
        ax.text(0.5, 0.5, "Data unavailable", ha="center", va="center", transform=ax.transAxes)
        return
    ax.plot(dates, values, color=color)
    ax.set_title(title)
    ax.set_ylabel("%")
    annotate_latest(ax, dates[-1], values[-1])


def plot_dashboard(cpi_months, gdp_quarters, bank_rate_series):
    cpi_dates = [parse_month(m["date"]) for m in cpi_months] if cpi_months is not None else []
    cpi_values = [float(m["value"]) for m in cpi_months] if cpi_months is not None else []

    gdp_dates = [parse_quarter(q["date"]) for q in gdp_quarters] if gdp_quarters is not None else []
    gdp_values = [float(q["value"]) for q in gdp_quarters] if gdp_quarters is not None else []

    bank_dates = [d for d, _ in bank_rate_series] if bank_rate_series is not None else []
    bank_values = [r for _, r in bank_rate_series] if bank_rate_series is not None else []

    fig, axes = plt.subplots(3, 1, figsize=(10, 11), constrained_layout=True)

    plot_series(axes[0], "CPI inflation (12-month rate)", cpi_dates, cpi_values, "tab:blue")
    plot_series(axes[1], "GDP quarter-on-quarter growth", gdp_dates, gdp_values, "tab:green")
    plot_series(axes[2], "Bank Rate", bank_dates, bank_values, "tab:red")

    fig.suptitle(f"UK Macro Dashboard — {date.today().strftime('%d %B %Y')}", fontsize=14, fontweight="bold")
    fig.savefig("dashboard.png", dpi=150)


def try_fetch(fetch, source_name):
    """Run a fetch that raises DataUnavailable on failure; print and return None instead."""
    try:
        return fetch()
    except DataUnavailable as e:
        print(f"Error: {e}")
        return None


def main():
    months = try_fetch(lambda: fetch_json_series(CPI_URL, "months", "CPI inflation"), "CPI inflation")
    if months is not None:
        print_table("CPI inflation (12-month rate)", months[-12:], "CPI 12-month rate (%)")

    quarters = try_fetch(lambda: fetch_json_series(GDP_URL, "quarters", "GDP growth"), "GDP growth")
    if quarters is not None:
        print_table("GDP quarter-on-quarter growth", quarters[-8:], "GDP QoQ growth (%)")

    bank_series = try_fetch(fetch_bank_rate_readings, "Bank Rate")
    if bank_series is not None:
        changes = bank_rate_changes(bank_series)[-12:]
        print("Bank Rate (last 12 changes)")
        print(f"{'Effective date':<16} {'Bank Rate (%)':>16}")
        print("-" * 33)
        for entry_date, rate in changes:
            print(f"{entry_date.strftime('%d %b %Y'):<16} {rate:>16g}")

    cpi_last_10y = [m for m in months if parse_month(m["date"]) >= TEN_YEARS_AGO] if months is not None else None
    gdp_last_10y = [q for q in quarters if parse_quarter(q["date"]) >= TEN_YEARS_AGO] if quarters is not None else None
    bank_last_10y = [entry for entry in bank_series if entry[0] >= TEN_YEARS_AGO] if bank_series is not None else None

    plot_dashboard(cpi_last_10y, gdp_last_10y, bank_last_10y)
    print("Saved chart to dashboard.png")


if __name__ == "__main__":
    main()
