"""50/50 XGBoost + Random Forest ensemble for ML price momentum."""

from __future__ import annotations

import numpy as np

from src.alpha.ml_price_momentum.models.rf_model import RFModel
from src.alpha.ml_price_momentum.models.xgboost_model import XGBoostModel


class EnsembleModel:
    """50/50 blended XGBoost + Random Forest ensemble.

    Ensemble probability: P = xgb_weight * P_xgb + rf_weight * P_rf
    Signal thresholds:
      - P > 0.51 → long (1)
      - P < 0.49 → short (-1)
      - else     → flat (0)

    Threshold choice rationale (2026-03-24):
    The original ±0.03 dead zone (0.47-0.53) produced 99% long / 1% short signal splits
    on both EURUSD and GBPUSD.  The regularized model outputs probabilities clustered in
    the 0.50-0.52 range due to the bullish training period (Sept 2024 EUR/GBP rally).
    With a ±0.03 band, probabilities at 0.51 trigger long but 0.49 is still flat — the
    band is geometrically symmetric but practically asymmetric when the distribution of
    raw probabilities is shifted above 0.50.  Narrowing to ±0.01 allows the model to
    generate short signals when proba falls slightly below 0.50, restoring
    long/short balance and enabling capture of downside moves (e.g. GBPUSD).
    """

    def __init__(self, xgb_weight: float = 0.5, rf_weight: float = 0.5) -> None:
        self._xgb = XGBoostModel()
        self._rf = RFModel()
        self._xgb_weight = xgb_weight
        self._rf_weight = rf_weight

    def fit(
        self,
        x_train: np.ndarray,
        y_train: np.ndarray,
        x_val: np.ndarray,
        y_val: np.ndarray,
    ) -> None:
        """Fit both XGBoost (with validation set) and Random Forest."""
        self._xgb.fit(x_train, y_train, x_val, y_val)
        self._rf.fit(x_train, y_train)

    def predict_proba(self, x: np.ndarray) -> np.ndarray:
        """Return blended ensemble probability bounded in [0, 1]."""
        return self._xgb_weight * self._xgb.predict_proba(
            x
        ) + self._rf_weight * self._rf.predict_proba(x)

    def generate_signal(self, proba: float) -> int:
        """Convert ensemble probability to directional signal.

        Returns:
            1  if proba > 0.51  (long)
            -1 if proba < 0.49  (short)
            0  otherwise        (flat)

        Note: Dead zone narrowed from ±0.03 to ±0.01 on 2026-03-24 to fix long bias.
        See class docstring for full rationale.
        """
        if proba > 0.51:
            return 1
        if proba < 0.49:
            return -1
        return 0

    @property
    def xgb_model(self) -> XGBoostModel:
        """Return the XGBoost model wrapper (for SHAP access)."""
        return self._xgb
