"""SHAP TreeExplainer analysis per walk-forward window.

Uses shap.Explainer which auto-selects TreeExplainer for XGBoost models.
Provides per-window feature importance and cross-window stability tracking.
"""
from __future__ import annotations

import numpy as np
import shap
import xgboost as xgb


class SHAPAnalyzer:
    """SHAP analysis for XGBoost models within walk-forward windows.

    Parameters
    ----------
    feature_names : list[str]
        Names corresponding to the columns of X_test passed to analyze_window.
    """

    def __init__(self, feature_names: list[str]) -> None:
        self._feature_names = feature_names

    def analyze_window(self, xgb_model: xgb.XGBClassifier, X_test: np.ndarray) -> dict:
        """Compute SHAP values for one walk-forward window.

        Parameters
        ----------
        xgb_model : xgb.XGBClassifier
            Fitted XGBoost classifier.
        X_test : np.ndarray, shape (n_samples, n_features)
            Test data for this window.

        Returns
        -------
        dict with keys:
            feature_importance : dict[str, float]  — mean |SHAP| per feature
            top_5              : list[str]          — top 5 feature names by importance
            expected_value     : float              — SHAP baseline (model output for empty input)
        """
        # Use get_booster() for XGBoost 3.x / shap 0.49.x compatibility.
        # shap.Explainer auto-detection and TreeExplainer(classifier) both fail
        # when XGBoost 3.x serialises base_score as '[5E-1]' instead of '0.5'.
        explainer = shap.TreeExplainer(xgb_model.get_booster())
        shap_values = explainer.shap_values(X_test)

        mean_abs_shap = np.abs(shap_values).mean(axis=0)

        feature_importance: dict[str, float] = {
            name: float(mean_abs_shap[i])
            for i, name in enumerate(self._feature_names)
        }

        sorted_features = sorted(feature_importance, key=lambda k: feature_importance[k], reverse=True)
        top_5 = sorted_features[:5]

        ev = explainer.expected_value
        expected_value = float(ev[0] if hasattr(ev, "__len__") else ev)

        return {
            "feature_importance": feature_importance,
            "top_5": top_5,
            "expected_value": expected_value,
        }

    def track_stability(self, window_results: list[dict]) -> dict:
        """Track feature stability across walk-forward windows.

        Parameters
        ----------
        window_results : list[dict]
            List of dicts from analyze_window() calls, one per window.

        Returns
        -------
        dict with keys:
            stable_features   : list[str]         — features in top 5 in >50% of windows
            stability_scores  : dict[str, float]  — frequency of each feature in top 5
        """
        feature_counts: dict[str, int] = {name: 0 for name in self._feature_names}
        n_windows = len(window_results)

        for result in window_results:
            for feature in result.get("top_5", []):
                if feature in feature_counts:
                    feature_counts[feature] += 1

        stability_scores: dict[str, float] = {
            name: count / n_windows if n_windows > 0 else 0.0
            for name, count in feature_counts.items()
        }

        stable_features = [
            name for name, score in stability_scores.items() if score > 0.5
        ]

        return {
            "stable_features": stable_features,
            "stability_scores": stability_scores,
        }
