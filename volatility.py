from dataclasses import dataclass

from arch import arch_model

from analytics import TRADING_DAYS_PER_YEAR

# arch's optimiser converges more reliably on returns rescaled to roughly unit variance.
# Daily returns are fractions like 0.01, so *100 puts them on a percent-like scale.
GARCH_SCALE = 100


@dataclass
class GarchFit:
    mu: float  # fitted mean daily return, in scaled units (see GARCH_SCALE)
    omega: float
    alpha: float
    beta: float
    conditional_volatility: object  # pandas Series, annualised, same units as the input returns
    long_run_volatility: float  # annualised


def scale_returns_for_garch(returns):
    return returns * GARCH_SCALE


def unscale_annualised_volatility(scaled_volatility, periods_per_year=TRADING_DAYS_PER_YEAR):
    """Undo scale_returns_for_garch and annualise: a scaled daily std -> an annualised
    fraction, e.g. 0.0288 (2.88% daily, scaled) -> roughly 0.288 (28.8% annualised)."""
    return scaled_volatility / GARCH_SCALE * (periods_per_year**0.5)


def garch_variance_recursion(omega, alpha, beta, previous_squared_shock, previous_variance):
    """The GARCH(1,1) formula: today's variance is a constant (omega), plus a share
    (alpha) of yesterday's squared shock, plus a share (beta) of yesterday's variance.
    Working in the same scaled units fit_garch fits in, not annualised, not unscaled."""
    return omega + alpha * previous_squared_shock + beta * previous_variance


def long_run_variance(omega, alpha, beta):
    """The variance GARCH reverts to when there are no new shocks: omega / (1 - alpha - beta).
    Requires alpha + beta < 1 (the process must be stationary), otherwise shocks would
    never fade and variance could grow without bound."""
    persistence = alpha + beta
    if persistence >= 1:
        raise ValueError(f"alpha + beta must be < 1 for a stationary GARCH process, got {persistence}")
    return omega / (1 - persistence)


def fit_garch(returns, periods_per_year=TRADING_DAYS_PER_YEAR):
    """Fit a GARCH(1,1) model to a daily return series and return its parameters plus its
    day-by-day annualised conditional volatility (the model's time-varying estimate)."""
    scaled_returns = scale_returns_for_garch(returns)
    result = arch_model(scaled_returns, vol="Garch", p=1, q=1, dist="normal").fit(disp="off")

    mu = result.params["mu"]
    omega = result.params["omega"]
    alpha = result.params["alpha[1]"]
    beta = result.params["beta[1]"]

    conditional_volatility = unscale_annualised_volatility(result.conditional_volatility, periods_per_year)
    long_run_std_scaled = long_run_variance(omega, alpha, beta) ** 0.5
    long_run_volatility = unscale_annualised_volatility(long_run_std_scaled, periods_per_year)

    return GarchFit(
        mu=mu,
        omega=omega,
        alpha=alpha,
        beta=beta,
        conditional_volatility=conditional_volatility,
        long_run_volatility=long_run_volatility,
    )
