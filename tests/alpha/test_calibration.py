"""Regime calibration tests — ALPH-03."""

from __future__ import annotations

import pytest


@pytest.mark.xfail(reason="Phase 3 not implemented", strict=False)
def test_weekly_recalibration_produces_valid_model(synthetic_returns: object) -> None:
    """ALPH-03: Weekly Baum-Welch recalibration produces stationarity-valid model."""
    raise AssertionError("Not yet implemented")
