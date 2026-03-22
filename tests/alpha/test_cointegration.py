"""Cointegration engine tests — ALPH-04, ALPH-05."""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="Stub — implementation in plan 03-03")
def test_johansen_detects_cointegrated_pair(cointegrated_pair: object) -> None:
    """ALPH-04: Johansen trace test identifies rank=1 on synthetic cointegrated data.

    Uses a known cointegrated pair (hedge ratio ~0.8) and verifies the
    Johansen trace statistic exceeds the 5% critical value for rank=1.
    """
    raise AssertionError("Not yet implemented")


@pytest.mark.skip(reason="Stub — implementation in plan 03-03")
def test_hedge_ratio_converges(cointegrated_pair: object) -> None:
    """ALPH-04: Estimated hedge ratio is within 5% of the known true value (0.8).

    OLS or Johansen eigenvector estimation on 1000 bars of synthetic data
    must recover the true hedge ratio 0.8 within ±0.04.
    """
    raise AssertionError("Not yet implemented")


@pytest.mark.skip(reason="Stub — implementation in plan 03-03")
def test_zscore_entry_signals(cointegrated_pair: object) -> None:
    """ALPH-05: Z-score entry signals fire at +/-2.0 threshold.

    When the spread z-score crosses ±2.0, direction +1 or -1 must be
    emitted. No signal should be emitted when |z| < 2.0.
    """
    raise AssertionError("Not yet implemented")


@pytest.mark.skip(reason="Stub — implementation in plan 03-03")
def test_zscore_hard_stop(cointegrated_pair: object) -> None:
    """ALPH-05: Z-score hard stop fires at +/-4.0 (widening spread protection).

    When |z| >= 4.0, a hard stop signal with direction=0 must be emitted
    regardless of current position, indicating spread divergence.
    """
    raise AssertionError("Not yet implemented")


@pytest.mark.skip(reason="Stub — implementation in plan 03-03")
def test_half_life_computation(cointegrated_pair: object) -> None:
    """ALPH-04: Half-life computation matches known AR(1) coefficient.

    For spread s_t = beta * s_{t-1} + epsilon, half-life = -log(2)/log(beta).
    Estimated half-life must match the analytical value within 10%.
    """
    raise AssertionError("Not yet implemented")
