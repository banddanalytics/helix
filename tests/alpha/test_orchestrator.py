"""RegimeOrchestrator tests — ALPH-09."""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="Stub — implementation in plan 03-07")
def test_trending_activates_ml_and_carry(mock_signal_df: object) -> None:
    """ALPH-09: TRENDING regime activates ml_engine and carry_engine only (D-05).

    When the detector emits RegimeState.TRENDING, the orchestrator must
    activate exactly ["ml_engine", "carry_engine"] and suppress cointegration.
    """
    raise AssertionError("Not yet implemented")


@pytest.mark.skip(reason="Stub — implementation in plan 03-07")
def test_mean_reverting_activates_cointegration(mock_signal_df: object) -> None:
    """ALPH-09: MEAN_REVERTING regime activates cointegration_engine only (D-05).

    When the detector emits RegimeState.MEAN_REVERTING, the orchestrator
    must activate exactly ["cointegration_engine"] and suppress ml and carry.
    """
    raise AssertionError("Not yet implemented")


@pytest.mark.skip(reason="Stub — implementation in plan 03-07")
def test_crisis_activates_nothing(mock_signal_df: object) -> None:
    """ALPH-09: CRISIS regime activates no engines — all signals blocked (D-05).

    When the detector emits RegimeState.CRISIS, the orchestrator must
    return an empty active engine list, blocking all signal generation.
    """
    raise AssertionError("Not yet implemented")


@pytest.mark.skip(reason="Stub — implementation in plan 03-07")
def test_hysteresis_20_bars(synthetic_returns: object) -> None:
    """ALPH-09: Hysteresis dwell of 20 bars prevents rapid regime oscillation.

    After a regime transition, the orchestrator must not allow another
    transition for at least 20 bars, even if the detector emits a new state.
    """
    raise AssertionError("Not yet implemented")
