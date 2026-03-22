"""Ensemble model tests — ALPH-08."""

from __future__ import annotations

import pytest


@pytest.mark.xfail(reason="Phase 3 not implemented", strict=False)
def test_ensemble_probability_bounded(synthetic_bars: object) -> None:
    """ALPH-08: Ensemble P = 0.5*P_xgb + 0.5*P_rf is bounded in [0, 1]."""
    raise AssertionError("Not yet implemented")


@pytest.mark.xfail(reason="Phase 3 not implemented", strict=False)
def test_shap_values_sum_to_output(synthetic_bars: object) -> None:
    """ALPH-08: SHAP values (TreeExplainer) sum to model output per prediction."""
    raise AssertionError("Not yet implemented")
