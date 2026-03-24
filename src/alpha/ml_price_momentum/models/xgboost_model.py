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
        # Regularization tuned for ~1764 training samples x 28 features.
        # Prior settings (max_depth=5, n_estimators=500, subsample=0.8) produced
        # severe overfit: train acc 70-77% vs test acc 35-58% per walk-forward window.
        # Confident OOS predictions were LESS accurate than uncertain ones (49% vs 50%).
        # Changes:
        #   max_depth: 5 → 3          (shallower trees, less capacity to memorize noise)
        #   n_estimators: 500 → 300   (fewer trees reduces cumulative overfit)
        #   subsample: 0.8 → 0.6      (more variance injection per tree)
        #   colsample_bytree: 0.7 → 0.5  (force feature diversity per tree)
        #   min_child_weight: 100 → 200  (require more samples per leaf)
        #   reg_alpha: 0.1 → 1.0      (stronger L1 sparsity)
        #   reg_lambda: 1.0 → 5.0     (stronger L2 weight decay)
        #   early stopping: 50 → 30   (stop sooner when val loss plateaus)
        self._clf = xgb.XGBClassifier(
            n_estimators=300,
            max_depth=3,
            learning_rate=0.01,
            subsample=0.6,
            colsample_bytree=0.5,
            min_child_weight=200,
            reg_alpha=1.0,
            reg_lambda=5.0,
            eval_metric="logloss",
            callbacks=[xgb.callback.EarlyStopping(rounds=30, metric_name="logloss")],
            random_state=42,
        )

    def fit(
        self,
        x_train: np.ndarray,
        y_train: np.ndarray,
        x_val: np.ndarray,
        y_val: np.ndarray,
    ) -> None:
        """Fit the XGBoost classifier.

        NOTE: callbacks are NOT passed here — they live in the constructor.
        Passing callbacks to fit() raises TypeError in XGBoost 3.x.
        """
        self._clf.fit(x_train, y_train, eval_set=[(x_val, y_val)], verbose=False)

    def predict_proba(self, x: np.ndarray) -> np.ndarray:
        """Return probability of class 1 (upward momentum)."""
        return self._clf.predict_proba(x)[:, 1]

    @property
    def model(self) -> xgb.XGBClassifier:
        """Return the underlying XGBClassifier (for SHAP access)."""
        return self._clf
