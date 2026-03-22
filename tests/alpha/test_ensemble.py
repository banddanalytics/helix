"""Ensemble model tests — ALPH-08."""

from __future__ import annotations

import numpy as np
import pytest

from src.alpha.ml_price_momentum.evaluation.shap_analysis import SHAPAnalyzer
from src.alpha.ml_price_momentum.models.ensemble import EnsembleModel
from src.alpha.ml_price_momentum.models.xgboost_model import XGBoostModel


def _make_synthetic_data(
    n_samples: int = 300, n_features: int = 5
) -> tuple[np.ndarray, np.ndarray]:
    """Generate synthetic binary classification data for fast fitting."""
    rng = np.random.default_rng(42)
    X = rng.standard_normal((n_samples, n_features)).astype(np.float32)
    y = (rng.random(n_samples) > 0.5).astype(int)
    return X, y


def test_ensemble_probability_bounded() -> None:
    """ALPH-08: Ensemble probability P = 0.5*P_xgb + 0.5*P_rf is bounded in [0, 1].

    For all input samples, the blended ensemble probability must be
    a valid probability (0.0 <= P <= 1.0) with no clamping required.
    """
    X, y = _make_synthetic_data(n_samples=300)
    split = 200
    val_split = 240
    X_train = X[:split]
    y_train = y[:split]
    X_val = X[split:val_split]
    y_val = y[split:val_split]
    X_test = X[val_split:]

    model = EnsembleModel()
    model.fit(X_train, y_train, X_val, y_val)
    probas = model.predict_proba(X_test)

    assert probas.shape == (len(X_test),), f"Expected 1-D array, got shape {probas.shape}"
    assert np.all(probas >= 0.0), f"Probabilities below 0: {probas[probas < 0.0]}"
    assert np.all(probas <= 1.0), f"Probabilities above 1: {probas[probas > 1.0]}"


def test_xgboost_callbacks_in_constructor() -> None:
    """ALPH-08: XGBoost callbacks are in constructor — no TypeError on fit().

    Verifies that constructing XGBoostModel with EarlyStopping callbacks
    in the constructor and calling fit() raises no TypeError.
    This is the XGBoost 3.x regression test — callbacks passed to fit()
    would raise TypeError in XGBoost 3.x.
    """
    X, y = _make_synthetic_data(n_samples=200)
    split = 160
    X_train, y_train = X[:split], y[:split]
    X_val, y_val = X[split:], y[split:]

    # Must not raise TypeError
    model = XGBoostModel()
    model.fit(X_train, y_train, X_val, y_val)

    # Confirm EarlyStopping is in the constructor params, not in fit signature
    import inspect

    fit_params = inspect.signature(model._clf.fit).parameters
    assert "callbacks" not in fit_params, (
        "XGBoost 3.x removed 'callbacks' from fit() — callbacks must be in constructor"
    )

    # Confirm predict works after fit
    probas = model.predict_proba(X_val)
    assert probas.shape == (len(X_val),)


def test_shap_values_sum_to_output() -> None:
    """ALPH-08: SHAP values (TreeExplainer) sum to model output per prediction.

    For each prediction, sum(shap_values[i]) + expected_value must equal
    the raw model logit output within floating point tolerance (SHAP identity).
    """
    import shap

    n_features = 5
    feature_names = [f"feat_{i}" for i in range(n_features)]

    X, y = _make_synthetic_data(n_samples=200, n_features=n_features)
    split = 160
    X_train, y_train = X[:split], y[:split]
    X_val, y_val = X[split:], y[split:]

    xgb_model = XGBoostModel()
    xgb_model.fit(X_train, y_train, X_val, y_val)

    analyzer = SHAPAnalyzer(feature_names=feature_names)
    result = analyzer.analyze_window(xgb_model.model, X_val)

    assert "feature_importance" in result
    assert "top_5" in result
    assert "expected_value" in result
    assert len(result["top_5"]) <= 5

    # Verify SHAP identity: shap_values.sum(axis=1) + expected_value ≈ model raw output
    # Use get_booster() for XGBoost 3.x / shap 0.49.x compatibility.
    explainer = shap.TreeExplainer(xgb_model.model.get_booster())
    shap_values = explainer.shap_values(X_val)

    ev = explainer.expected_value
    expected_value = float(ev[0] if hasattr(ev, "__len__") else ev)

    shap_sums = shap_values.sum(axis=1) + expected_value
    raw_output = xgb_model.model.get_booster().predict(
        __import__("xgboost").DMatrix(X_val), output_margin=True
    )

    np.testing.assert_allclose(
        shap_sums,
        raw_output,
        atol=1e-4,
        err_msg="SHAP identity violation: shap_values.sum + expected_value != model output",
    )
