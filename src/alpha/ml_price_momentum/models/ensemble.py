"""50/50 XGBoost + Random Forest ensemble for ML price momentum."""
from __future__ import annotations

import numpy as np

from src.alpha.ml_price_momentum.models.rf_model import RFModel
from src.alpha.ml_price_momentum.models.xgboost_model import XGBoostModel


class EnsembleModel:
    """50/50 blended XGBoost + Random Forest ensemble.

    Ensemble probability: P = xgb_weight * P_xgb + rf_weight * P_rf
    Signal thresholds:
      - P > 0.53 → long (1)
      - P < 0.47 → short (-1)
      - else     → flat (0)
    """

    def __init__(self, xgb_weight: float = 0.5, rf_weight: float = 0.5) -> None:
        self._xgb = XGBoostModel()
        self._rf = RFModel()
        self._xgb_weight = xgb_weight
        self._rf_weight = rf_weight

    def fit(self, X_train: np.ndarray, y_train: np.ndarray, X_val: np.ndarray, y_val: np.ndarray) -> None:
        """Fit both XGBoost (with validation set) and Random Forest."""
        self._xgb.fit(X_train, y_train, X_val, y_val)
        self._rf.fit(X_train, y_train)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Return blended ensemble probability bounded in [0, 1]."""
        return self._xgb_weight * self._xgb.predict_proba(X) + self._rf_weight * self._rf.predict_proba(X)

    def generate_signal(self, proba: float) -> int:
        """Convert ensemble probability to directional signal.

        Returns:
            1  if proba > 0.53  (long)
            -1 if proba < 0.47  (short)
            0  otherwise        (flat)
        """
        if proba > 0.53:
            return 1
        if proba < 0.47:
            return -1
        return 0

    @property
    def xgb_model(self) -> XGBoostModel:
        """Return the XGBoost model wrapper (for SHAP access)."""
        return self._xgb
