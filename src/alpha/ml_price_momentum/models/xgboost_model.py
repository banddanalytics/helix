"""XGBoost classifier wrapper — callbacks in constructor (XGBoost 3.x compatible)."""
from __future__ import annotations

import numpy as np
import xgboost as xgb


class XGBoostModel:
    """XGBoost binary classifier for ML price momentum.

    CRITICAL: callbacks are passed to the constructor, NOT to fit().
    XGBoost 3.x raises TypeError if callbacks are passed to fit().
    """

    def __init__(self) -> None:
        self._clf = xgb.XGBClassifier(
            n_estimators=500,
            max_depth=5,
            learning_rate=0.01,
            subsample=0.8,
            colsample_bytree=0.7,
            min_child_weight=100,
            reg_alpha=0.1,
            reg_lambda=1.0,
            eval_metric="logloss",
            callbacks=[xgb.callback.EarlyStopping(rounds=50, metric_name="logloss")],
            random_state=42,
        )

    def fit(self, X_train: np.ndarray, y_train: np.ndarray, X_val: np.ndarray, y_val: np.ndarray) -> None:
        """Fit the XGBoost classifier.

        NOTE: callbacks are NOT passed here — they live in the constructor.
        Passing callbacks to fit() raises TypeError in XGBoost 3.x.
        """
        self._clf.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Return probability of class 1 (upward momentum)."""
        return self._clf.predict_proba(X)[:, 1]

    @property
    def model(self) -> xgb.XGBClassifier:
        """Return the underlying XGBClassifier (for SHAP access)."""
        return self._clf
