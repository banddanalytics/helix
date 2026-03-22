"""Regime calibration tests — ALPH-03."""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="Stub — implementation in plan 03-02")
def test_weekly_recalibration_produces_valid_model(synthetic_returns: object) -> None:
    """ALPH-03: Weekly Baum-Welch recalibration produces a stationarity-valid model.

    Fits the HMM-GARCH on the most recent rolling window and verifies
    the resulting model passes all stationarity gates.
    """
    raise AssertionError("Not yet implemented")


@pytest.mark.skip(reason="Stub — implementation in plan 03-02")
def test_dirichlet_smoothing_no_zero_transitions(synthetic_returns: object) -> None:
    """ALPH-03: Dirichlet smoothing ensures no transition probability is exactly 0.

    After applying concentration parameter alpha=0.1, all entries in the
    3x3 transition matrix must be > 0 to avoid absorbing states.
    """
    raise AssertionError("Not yet implemented")


@pytest.mark.skip(reason="Stub — implementation in plan 03-02")
def test_parameter_drift_warning(synthetic_returns: object) -> None:
    """ALPH-03: >50% parameter drift triggers a WARNING log entry.

    When recalibrated parameters differ from previous fit by more than 50%
    (KL divergence threshold), a WARNING-level message must be emitted.
    """
    raise AssertionError("Not yet implemented")


@pytest.mark.skip(reason="Stub — implementation in plan 03-02")
def test_stationarity_gate_rejects_invalid(synthetic_returns: object) -> None:
    """ALPH-03: Stationarity gate rejects model where alpha + beta >= 1.

    A model with at least one state violating alpha_i + beta_i < 1
    must be rejected (raises ValueError or returns None).
    """
    raise AssertionError("Not yet implemented")


@pytest.mark.skip(reason="Stub — implementation in plan 03-02")
def test_state_agreement_gate(synthetic_returns: object) -> None:
    """ALPH-03: State agreement gate rejects recalibration with <90% agreement.

    If online predictions agree with the new model's Viterbi path on fewer
    than 90% of the validation window bars, recalibration is rejected.
    """
    raise AssertionError("Not yet implemented")
