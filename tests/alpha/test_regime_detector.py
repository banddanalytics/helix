"""Regime detector tests — ALPH-01, ALPH-02."""

from __future__ import annotations

import math

import numpy as np
import pytest
import scipy.stats


# ---------------------------------------------------------------------------
# Task 1 tests: GARCH emissions and Viterbi decoder
# ---------------------------------------------------------------------------


def test_garch_params_unconditional_variance() -> None:
    """GARCHParams.unconditional_variance = omega / (1 - alpha - beta)."""
    from src.alpha.regime.emissions import GARCHParams

    params = GARCHParams(mu=0.0, omega=0.0001, alpha=0.1, beta=0.8)
    expected = 0.0001 / (1 - 0.1 - 0.8)
    assert math.isclose(params.unconditional_variance, expected, rel_tol=1e-9)


def test_garch_params_is_stationary() -> None:
    """GARCHParams.is_stationary returns True iff alpha + beta < 1."""
    from src.alpha.regime.emissions import GARCHParams

    stationary = GARCHParams(mu=0.0, omega=0.0001, alpha=0.1, beta=0.8)
    non_stationary = GARCHParams(mu=0.0, omega=0.0001, alpha=0.6, beta=0.5)
    assert stationary.is_stationary is True
    assert non_stationary.is_stationary is False


def test_garch_emission_prob_matches_scipy() -> None:
    """garch_emission_prob log-probs match scipy.stats.norm at t=0."""
    from src.alpha.regime.emissions import GARCHParams, garch_emission_prob

    rng = np.random.default_rng(0)
    returns = rng.normal(0.0, 0.01, size=50)
    params = GARCHParams(mu=0.0, omega=0.0001, alpha=0.05, beta=0.90)

    log_probs = garch_emission_prob(returns, params)

    # t=0: sigma2 = unconditional variance
    sigma2_0 = params.unconditional_variance
    expected_lp_0 = scipy.stats.norm.logpdf(returns[0], loc=0.0, scale=math.sqrt(sigma2_0))
    assert math.isclose(log_probs[0], expected_lp_0, rel_tol=1e-6)
    assert len(log_probs) == len(returns)
    # All log-probs must be finite
    assert np.all(np.isfinite(log_probs))


def test_garch_variance_recursion_finite_positive() -> None:
    """GARCH variance recursion produces finite positive sigma^2 values."""
    from src.alpha.regime.emissions import GARCHParams, garch_emission_prob

    rng = np.random.default_rng(1)
    returns = rng.normal(0.0, 0.02, size=200)
    params = GARCHParams(mu=0.0, omega=5e-5, alpha=0.08, beta=0.87)

    log_probs = garch_emission_prob(returns, params)

    assert np.all(np.isfinite(log_probs)), "All log-probs must be finite"
    assert len(log_probs) == 200


def test_viterbi_decode_toy_example() -> None:
    """viterbi_decode returns correct optimal path on 3-state toy HMM."""
    from src.alpha.regime.viterbi import viterbi_decode

    # 3 states, T=5: deterministic toy HMM
    # State 0 → stay in 0; emission only good in state 0 for obs 0, state 1 for obs 1
    n_states = 3
    T = 5

    # Transition: strong self-loops
    transmat = np.array([
        [0.9, 0.05, 0.05],
        [0.05, 0.9, 0.05],
        [0.05, 0.05, 0.9],
    ])
    log_transmat = np.log(transmat)

    startprob = np.array([0.8, 0.1, 0.1])
    log_startprob = np.log(startprob)

    # Emission log-probs: each observation strongly favors state 0
    log_emission_probs = np.full((T, n_states), -10.0)
    log_emission_probs[:, 0] = 0.0  # state 0 always very likely

    states = viterbi_decode(log_emission_probs, log_transmat, log_startprob)

    assert len(states) == T
    assert np.all(states == 0), f"Expected all-zero path, got {states}"


def test_viterbi_decode_output_length() -> None:
    """viterbi_decode output length equals input T."""
    from src.alpha.regime.viterbi import viterbi_decode

    T = 100
    n_states = 3
    rng = np.random.default_rng(42)

    log_emission_probs = rng.normal(-5, 1, size=(T, n_states))
    transmat = np.full((n_states, n_states), 1.0 / n_states)
    log_transmat = np.log(transmat)
    startprob = np.full(n_states, 1.0 / n_states)
    log_startprob = np.log(startprob)

    states = viterbi_decode(log_emission_probs, log_transmat, log_startprob)

    assert len(states) == T
    assert states.dtype in (np.int32, np.int64, int)
    assert np.all((states >= 0) & (states < n_states))


# ---------------------------------------------------------------------------
# Task 2 tests: HMMGARCHRegimeDetector and OnlineRegimeFilter
# ---------------------------------------------------------------------------


def test_hmm_garch_fits_three_states(synthetic_returns: np.ndarray) -> None:
    """ALPH-01: HMMGARCHRegimeDetector.fit() identifies 3 distinct states on synthetic data.

    Verifies that fitting on regime-switching synthetic returns produces
    exactly 3 distinct state labels with no degenerate (zero-mass) states.
    """
    from src.alpha.regime.hmm_garch import HMMGARCHRegimeDetector

    detector = HMMGARCHRegimeDetector(n_states=3, random_state=0)
    success = detector.fit(synthetic_returns)
    assert success is True, "fit() should return True on convergence"
    assert detector.is_fitted
    assert len(detector.garch_params) == 3


def test_garch_stationarity_constraint(synthetic_returns: np.ndarray) -> None:
    """ALPH-02: GARCH stationarity gate — alpha + beta < 1 for all states.

    For each fitted GARCH state, verifies the persistence constraint
    alpha_i + beta_i < 1 (i.e., unconditional variance is finite).
    """
    from src.alpha.regime.hmm_garch import HMMGARCHRegimeDetector

    detector = HMMGARCHRegimeDetector(n_states=3, random_state=0)
    detector.fit(synthetic_returns)
    assert all(p.is_stationary for p in detector.garch_params), (
        "All GARCH states must satisfy alpha + beta < 1"
    )


def test_states_sorted_by_ascending_variance(synthetic_returns: np.ndarray) -> None:
    """ALPH-02: States ordered by ascending unconditional variance omega/(1-alpha-beta).

    State 0 must have the lowest unconditional variance (trending/low-vol),
    state 2 the highest (crisis/high-vol).
    """
    from src.alpha.regime.hmm_garch import HMMGARCHRegimeDetector

    detector = HMMGARCHRegimeDetector(n_states=3, random_state=0)
    detector.fit(synthetic_returns)
    variances = [p.unconditional_variance for p in detector.garch_params]
    assert variances[0] < variances[1] < variances[2], (
        f"States must be sorted by ascending variance, got {variances}"
    )


def test_online_prediction_matches_viterbi(synthetic_returns: np.ndarray) -> None:
    """ALPH-01: Online forward-filter prediction agrees with Viterbi path >90% of bars.

    Online predictions (causal, uses only past data) should agree with
    the batch Viterbi decoded path on at least 90% of samples.
    """
    from src.alpha.regime.hmm_garch import HMMGARCHRegimeDetector
    from src.alpha.regime.online_filter import OnlineRegimeFilter

    detector = HMMGARCHRegimeDetector(n_states=3, random_state=0)
    detector.fit(synthetic_returns)

    # Offline Viterbi reference
    viterbi_states = detector.predict_viterbi(synthetic_returns)

    # Online forward filter
    filt = OnlineRegimeFilter(detector)
    online_states = np.array(
        [int(filt.update(r)[0]) for r in synthetic_returns]
    )

    agreement = np.mean(online_states == viterbi_states)
    assert agreement > 0.90, f"Online vs Viterbi agreement {agreement:.2%} < 90%"
