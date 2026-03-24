"""Random Forest classifier wrapper for ML price momentum ensemble."""

from __future__ import annotations

import numpy as np
from sklearn.ensemble import RandomForestClassifier


class RFModel:
    """Random Forest binary classifier for ML price momentum.

    Uses class_weight='balanced' to handle class imbalance in directional
    momentum classification.
    """

    def __init__(self) -> None:
        # Regularization tuned for ~1764 training samples x 28 features.
        # Prior settings (n_estimators=1000, max_depth=7, min_samples_leaf=50)
        # produced severe overfit alongside XGBoost: train acc 70-77% vs test
        # acc 35-58% per window. Changes:
        #   n_estimators: 1000 → 300   (fewer trees, faster + less overfit)
        #   max_depth: 7 → 3           (shallower trees cannot memorize noise)
        #   min_samples_leaf: 50 → 200 (require more support per leaf, ~11% of train)
        self._clf = RandomForestClassifier(
            n_estimators=300,
            max_depth=3,
            min_samples_leaf=200,
            max_features="sqrt",
            class_weight="balanced",
            n_jobs=-1,
            random_state=42,
        )

    def fit(self, x_train: np.ndarray, y_train: np.ndarray) -> None:
        """Fit the Random Forest classifier."""
        self._clf.fit(x_train, y_train)

    def predict_proba(self, x: np.ndarray) -> np.ndarray:
        """Return probability of class 1 (upward momentum)."""
        return self._clf.predict_proba(x)[:, 1]
