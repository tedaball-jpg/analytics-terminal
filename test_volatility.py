import numpy as np
import pandas as pd
import pytest

from volatility import (
    GARCH_SCALE,
    fit_garch,
    garch_variance_recursion,
    long_run_variance,
    scale_returns_for_garch,
    unscale_annualised_volatility,
)


def test_scale_returns_for_garch_multiplies_by_100():
    scaled = scale_returns_for_garch(pd.Series([0.01, -0.02, 0.0]))
    assert scaled.tolist() == pytest.approx([1.0, -2.0, 0.0])


def test_unscale_annualised_volatility_by_hand():
    # A scaled daily std of 1.5 (i.e. 1.5% before unscaling) over 252 days:
    # 1.5 / 100 * sqrt(252) = 0.015 * 15.8745... = 0.23811...
    result = unscale_annualised_volatility(1.5, periods_per_year=252)
    assert result == pytest.approx(0.015 * (252**0.5))


def test_unscale_annualised_volatility_with_a_different_periodicity():
    # Same scaled value, monthly data (12 periods a year) annualises to a smaller number.
    daily = unscale_annualised_volatility(1.5, periods_per_year=252)
    monthly = unscale_annualised_volatility(1.5, periods_per_year=12)
    assert monthly < daily
    assert monthly == pytest.approx(daily * (12 / 252) ** 0.5)


def test_garch_variance_recursion_by_hand():
    # sigma^2_t = omega + alpha * epsilon^2_(t-1) + beta * sigma^2_(t-1)
    #           = 0.1 + 0.2 * 4 + 0.7 * 9 = 0.1 + 0.8 + 6.3 = 7.2
    result = garch_variance_recursion(omega=0.1, alpha=0.2, beta=0.7, previous_squared_shock=4, previous_variance=9)
    assert result == pytest.approx(7.2)


def test_garch_variance_recursion_with_no_shock_and_no_prior_variance_is_just_omega():
    result = garch_variance_recursion(omega=0.05, alpha=0.2, beta=0.7, previous_squared_shock=0, previous_variance=0)
    assert result == pytest.approx(0.05)


def test_long_run_variance_by_hand():
    # omega / (1 - alpha - beta) = 0.1 / (1 - 0.2 - 0.7) = 0.1 / 0.1 = 1.0
    assert long_run_variance(omega=0.1, alpha=0.2, beta=0.7) == pytest.approx(1.0)


def test_long_run_variance_rejects_a_non_stationary_process():
    with pytest.raises(ValueError):
        long_run_variance(omega=0.1, alpha=0.5, beta=0.6)  # alpha + beta = 1.1


def test_long_run_variance_rejects_the_boundary_case_too():
    with pytest.raises(ValueError):
        long_run_variance(omega=0.1, alpha=0.5, beta=0.5)  # alpha + beta = 1.0 exactly


def test_recursion_applied_repeatedly_settles_near_the_long_run_variance():
    # With no further shocks, repeatedly applying the recursion should converge to
    # exactly the long-run variance formula predicts - an independent check that the
    # two formulas (the recursion and its closed-form steady state) agree.
    omega, alpha, beta = 0.1, 0.2, 0.7
    variance = 50.0  # start far from the steady state
    for _ in range(2000):
        variance = garch_variance_recursion(omega, alpha, beta, previous_squared_shock=variance, previous_variance=variance)
    assert variance == pytest.approx(long_run_variance(omega, alpha, beta), rel=1e-6)


@pytest.fixture(scope="module")
def synthetic_returns():
    # A fixed seed, so this is reproducible without needing network access.
    rng = np.random.default_rng(0)
    return pd.Series(rng.normal(0.0005, 0.015, 500))


@pytest.fixture(scope="module")
def garch_result(synthetic_returns):
    return fit_garch(synthetic_returns)


def test_fit_garch_returns_one_volatility_per_input_return(synthetic_returns, garch_result):
    assert len(garch_result.conditional_volatility) == len(synthetic_returns)


def test_fit_garch_conditional_volatility_is_always_positive(garch_result):
    assert (garch_result.conditional_volatility > 0).all()


def test_fit_garch_parameters_are_a_stationary_process(garch_result):
    assert garch_result.alpha + garch_result.beta < 1


def test_fit_garch_long_run_volatility_is_positive_and_reasonable(garch_result):
    # Daily vol of 1.5% annualises to roughly 24%; the long-run estimate should be
    # in the right order of magnitude for data simulated with that daily vol.
    assert 0.05 < garch_result.long_run_volatility < 1.0


def test_fit_garch_matches_its_own_recursion_independently(synthetic_returns, garch_result):
    # The strongest check: reimplement the GARCH(1,1) recursion by hand from the fitted
    # parameters and confirm it reproduces arch's own conditional_volatility series
    # exactly. This does not test arch's own initialisation (the recursion is seeded
    # from arch's first value), only whether garch_variance_recursion is the same
    # formula arch actually used to go from that point forward.
    scaled = scale_returns_for_garch(synthetic_returns)
    shocks = (scaled - garch_result.mu).values  # the demeaned "surprise" each day

    arch_annualised_vol = garch_result.conditional_volatility.values
    # Undo the annualising/unscaling this module's own conditional_volatility applied,
    # to work in the same scaled, non-annualised variance units the recursion uses.
    arch_scaled_vol = arch_annualised_vol / (252**0.5) * GARCH_SCALE

    variance = [arch_scaled_vol[0] ** 2]
    for t in range(1, len(shocks)):
        variance.append(
            garch_variance_recursion(
                garch_result.omega, garch_result.alpha, garch_result.beta,
                previous_squared_shock=shocks[t - 1] ** 2,
                previous_variance=variance[-1],
            )
        )
    reimplemented_vol = np.sqrt(variance)

    assert reimplemented_vol == pytest.approx(arch_scaled_vol, abs=1e-8)
