"""Cointegration engine tests — ALPH-04, ALPH-05."""

from __future__ import annotations

import pytest


@pytest.mark.xfail(reason="Phase 3 not implemented", strict=False)
def test_johansen_detects_cointegrated_pair() -> None:
    """ALPH-04: Johansen trace test identifies rank=1 on synthetic cointegrated data."""
    raise AssertionError("Not yet implemented")


@pytest.mark.xfail(reason="Phase 3 not implemented", strict=False)
def test_zscore_signals_at_thresholds() -> None:
    """ALPH-05: Z-score entry/exit signals fire at correct thresholds (2.0/0.5/4.0)."""
    raise AssertionError("Not yet implemented")
