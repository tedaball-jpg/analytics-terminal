import matplotlib.pyplot as plt
import yfinance as yf

from analytics import annualised_volatility, cumulative_return, simple_returns
from macro_data import bank_rate_changes, fetch_bank_rate_readings
from volatility import fit_garch

TICKERS = ["AZN.L", "HSBA.L", "SHEL.L", "TSCO.L", "RR.L", "^FTSE"]
STOCKS = ["AZN.L", "HSBA.L", "SHEL.L", "TSCO.L", "RR.L"]


def fetch_prices(tickers=TICKERS, period="2y", interval="1d"):
    data = yf.download(tickers, period=period, interval=interval, auto_adjust=True)
    return data["Close"]


def plot_price_history(prices, ticker):
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(prices.index, prices)

    ax.set_title(f"{ticker}: price history")
    ax.set_ylabel("Price")
    fig.tight_layout()
    return fig


def plot_correlation_heatmap(corr):
    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(corr, cmap="coolwarm", vmin=-1, vmax=1)

    ax.set_xticks(range(len(corr.columns)))
    ax.set_yticks(range(len(corr.columns)))
    ax.set_xticklabels(corr.columns, rotation=45, ha="right")
    ax.set_yticklabels(corr.columns)

    for i in range(len(corr.columns)):
        for j in range(len(corr.columns)):
            ax.text(j, i, f"{corr.iloc[i, j]:.2f}", ha="center", va="center")

    fig.colorbar(im, ax=ax, label="Correlation")
    ax.set_title("Correlation of daily returns")
    fig.tight_layout()
    return fig


def plot_portfolio_vs_ftse(portfolio_cum_return, ftse_cum_return):
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(portfolio_cum_return.index, portfolio_cum_return * 100, label="Equal-weighted portfolio")
    ax.plot(ftse_cum_return.index, ftse_cum_return * 100, label="FTSE 100")

    ax.set_title("Portfolio vs FTSE 100: cumulative return")
    ax.set_ylabel("Cumulative return (%)")
    ax.axhline(0, color="black", linewidth=0.5)
    ax.legend()
    fig.tight_layout()
    return fig


def sharpe_ratio(returns, risk_free_rate):
    annualised_return = returns.mean() * 252
    return (annualised_return - risk_free_rate) / annualised_volatility(returns)


def plot_garch_vs_flat(garch_vol, flat_vol):
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(garch_vol.index, garch_vol * 100, label="GARCH(1,1) volatility (time-varying)")
    ax.axhline(flat_vol * 100, color="black", linestyle="--", label="Flat historical volatility")

    ax.set_title("Portfolio volatility: GARCH(1,1) vs flat historical estimate")
    ax.set_ylabel("Annualised volatility (%)")
    ax.legend()
    fig.tight_layout()
    return fig


def plot_volatility_difference(garch_vol, flat_vol):
    difference = (garch_vol - flat_vol) * 100

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(difference.index, difference, color="tab:purple")
    ax.axhline(0, color="black", linewidth=0.5)

    ax.set_title("GARCH(1,1) volatility minus flat historical estimate")
    ax.set_ylabel("Difference (percentage points)")
    fig.tight_layout()
    return fig


def main():
    prices = fetch_prices()
    print(prices.tail())
    print(f"\n{len(prices)} trading days from {prices.index[0].date()} to {prices.index[-1].date()}")

    returns = simple_returns(prices)

    volatility = annualised_volatility(returns)
    print("\nAnnualised volatility")
    print(f"{'Ticker':<10} {'Volatility':>12}")
    print("-" * 23)
    for ticker, vol in volatility.items():
        print(f"{ticker:<10} {vol:>11.2%}")

    corr = returns[STOCKS].corr()
    print("\nCorrelation matrix (daily returns)")
    print(corr.round(2))

    plot_correlation_heatmap(corr).savefig("correlation_heatmap.png", dpi=150)
    print("\nSaved heatmap to correlation_heatmap.png")

    portfolio_returns = returns[STOCKS].mean(axis=1)
    portfolio_cum_return = cumulative_return(portfolio_returns)
    ftse_cum_return = cumulative_return(returns["^FTSE"])

    print(f"\nPortfolio cumulative return: {portfolio_cum_return.iloc[-1]:.2%}")
    print(f"FTSE 100 cumulative return: {ftse_cum_return.iloc[-1]:.2%}")

    plot_portfolio_vs_ftse(portfolio_cum_return, ftse_cum_return).savefig("portfolio_vs_ftse.png", dpi=150)
    print("Saved chart to portfolio_vs_ftse.png")

    risk_free_rate = bank_rate_changes(fetch_bank_rate_readings())[-1][1] / 100
    sharpe = sharpe_ratio(portfolio_returns, risk_free_rate)
    print(f"\nRisk-free rate (Bank Rate): {risk_free_rate:.2%}")
    print(f"Portfolio Sharpe ratio: {sharpe:.2f}")

    flat_vol = annualised_volatility(portfolio_returns)
    garch = fit_garch(portfolio_returns)

    plot_garch_vs_flat(garch.conditional_volatility, flat_vol).savefig("garch_vs_historical_volatility.png", dpi=150)
    print("Saved chart to garch_vs_historical_volatility.png")

    plot_volatility_difference(garch.conditional_volatility, flat_vol).savefig("volatility_forecast_difference.png", dpi=150)
    print("Saved chart to volatility_forecast_difference.png")


if __name__ == "__main__":
    main()
