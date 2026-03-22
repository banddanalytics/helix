"""Regime detector tests — ALPH-01, ALPH-02."""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="Stub — implementation in plan 03-02")
def test_hmm_garch_fits_three_states(synthetic_returns: object) -> None:
    """ALPH-01: HMMGARCHRegimeDetector.fit() identifies 3 distinct states on synthetic data.

    Verifies that fitting on regime-switching synthetic returns produces
    exactly 3 distinct state labels with no degenerate (zero-mass) states.
    """
    raise AssertionError("Not yet implemented")


@pytest.mark.skip(reason="Stub — implementation in plan 03-02")
def test_garch_stationarity_constraint(synthetic_returns: object) -> None:
    """ALPH-02: GARCH stationarity gate — alpha + beta < 1 for all states.

    For each fitted GARCH state, verifies the persistence constraint
    alpha_i + beta_i < 1 (i.e., unconditional variance is finite).
    """
    raise AssertionError("Not yet implemented")


@pytest.mark.skip(reason="Stub — implementation in plan 03-02")
def test_states_sorted_by_ascending_variance(synthetic_returns: object) -> None:
    """ALPH-02: States ordered by ascending unconditional variance omega/(1-alpha-beta).

    State 0 must have the lowest unconditional variance (trending/low-vol),
    state 2 the highest (crisis/high-vol).
    """
    raise AssertionError("Not yet implemented")


@pytest.mark.skip(reason="Stub — implementation in plan 03-02")
def test_online_prediction_matches_viterbi(synthetic_returns: object) -> None:
    """ALPH-01: Online forward-filter prediction agrees with Viterbi path >90% of bars.

    Online predictions (causal, uses only past data) should agree with
    the batch Viterbi decoded path on at least 90% of samples.
    """
    raise AssertionError("Not yet implemented")
