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
        self._clf = RandomForestClassifier(
            n_estimators=1000,
            max_depth=7,
            min_samples_leaf=50,
            max_features="sqrt",
            class_weight="balanced",
            n_jobs=-1,
            random_state=42,
        )

    def fit(self, X_train: np.ndarray, y_train: np.ndarray) -> None:
        """Fit the Random Forest classifier."""
        self._clf.fit(X_train, y_train)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Return probability of class 1 (upward momentum)."""
        return self._clf.predict_proba(X)[:, 1]
