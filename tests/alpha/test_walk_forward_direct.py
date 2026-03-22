"""Direct unit tests for WalkForwardEngine.run() with small synthetic dataset — Plan 03-10."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.alpha.ml_price_momentum.models.walk_forward import (
    WalkForwardConfig,
    WalkForwardEngine,
    WindowResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SMALL_CONFIG = WalkForwardConfig(
    train_window=50,
    val_size=10,
    test_window=5,
    purge_gap=2,
    step=5,
)
# min_length = 50 + 2 + 5 = 57; 100 bars gives multiple windows


def _make_data(n_samples: int = 100, n_features: int = 5, seed: int = 42) -> tuple[np.ndarray, np.ndarray]:
    """Generate small synthetic dataset."""
    rng = np.random.RandomState(seed)
    X = rng.randn(n_samples, n_features)
    y = (X[:, 0] > 0).astype(int)
    return X, y


def _mock_ensemble_cls(n_test: int = 5) -> MagicMock:
    """Return a MagicMock that stands in for EnsembleModel instances."""
    instance = MagicMock()
    instance.fit.return_value = None
    instance.predict_proba.side_effect = lambda X: np.random.rand(len(X))
    return instance


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_run_produces_window_results() -> None:
    """run() must return a non-empty list of WindowResult with correct array lengths."""
    X, y = _make_data(100)
    engine = WalkForwardEngine(_SMALL_CONFIG)

    mock_instance = MagicMock()
    mock_instance.fit.return_value = None
    mock_instance.predict_proba.side_effect = lambda X_t: np.random.rand(len(X_t))

    with patch(
        "src.alpha.ml_price_momentum.models.walk_forward.EnsembleModel",
        return_value=mock_instance,
    ):
        results = engine.run(X, y)

    assert len(results) > 0, "run() returned empty list for 100 samples with small config"
    for res in results:
        assert isinstance(res, WindowResult), f"Expected WindowResult, got {type(res)}"
        assert len(res.predictions) == _SMALL_CONFIG.test_window, (
            f"predictions length {len(res.predictions)} != test_window {_SMALL_CONFIG.test_window}"
        )
        assert len(res.actuals) == _SMALL_CONFIG.test_window, (
            f"actuals length {len(res.actuals)} != test_window {_SMALL_CONFIG.test_window}"
        )


def test_run_insufficient_data_returns_empty() -> None:
    """run() must return empty list when n_samples < train_window + purge_gap + test_window."""
    X, y = _make_data(30)  # 30 < 57 (minimum for small_config)
    engine = WalkForwardEngine(_SMALL_CONFIG)

    with patch("src.alpha.ml_price_momentum.models.walk_forward.EnsembleModel"):
        results = engine.run(X, y)

    assert results == [], f"Expected empty list for insufficient data, got {results}"


def test_run_window_count_matches_n_windows() -> None:
    """len(run()) must equal engine.n_windows(n_samples)."""
    X, y = _make_data(100)
    engine = WalkForwardEngine(_SMALL_CONFIG)
    expected_count = engine.n_windows(100)

    mock_instance = MagicMock()
    mock_instance.fit.return_value = None
    mock_instance.predict_proba.side_effect = lambda X_t: np.random.rand(len(X_t))

    with patch(
        "src.alpha.ml_price_momentum.models.walk_forward.EnsembleModel",
        return_value=mock_instance,
    ):
        results = engine.run(X, y)

    assert len(results) == expected_count, (
        f"n_windows({100}) = {expected_count}, but run() returned {len(results)} windows"
    )


def test_run_purge_gap_respected() -> None:
    """test_start must be >= train_end + purge_gap for every WindowResult.

    This verifies no label leakage from training set into test set.
    """
    X, y = _make_data(100)
    engine = WalkForwardEngine(_SMALL_CONFIG)

    mock_instance = MagicMock()
    mock_instance.fit.return_value = None
    mock_instance.predict_proba.side_effect = lambda X_t: np.random.rand(len(X_t))

    with patch(
        "src.alpha.ml_price_momentum.models.walk_forward.EnsembleModel",
        return_value=mock_instance,
    ):
        results = engine.run(X, y)

    assert len(results) > 0, "No results to check purge gap"
    cfg = _SMALL_CONFIG
    for w_idx, res in enumerate(results):
        # train_end for window w = train_window + w * step
        train_end = cfg.train_window + w_idx * cfg.step
        min_test_start = train_end + cfg.purge_gap
        assert res.test_start >= min_test_start, (
            f"Window {w_idx}: test_start={res.test_start} < train_end + purge_gap = {min_test_start}. "
            "Label leakage detected!"
        )
