"""Walk-forward validation engine for ML price momentum ensemble.

Configuration:
  train_window : 756 bars  (3 years of daily bars)
  val_size     : 63 bars   (last 63 bars of train for XGBoost early stopping)
  test_window  : 21 bars   (1 month OOS)
  purge_gap    : 5 bars    (prevents label leakage between train and test)
  step         : 21 bars   (monthly retraining cadence)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np

from src.alpha.ml_price_momentum.evaluation.shap_analysis import SHAPAnalyzer
from src.alpha.ml_price_momentum.models.ensemble import EnsembleModel

logger = logging.getLogger("helix.alpha")


@dataclass
class WalkForwardConfig:
    """Walk-forward splitter configuration."""

    train_window: int = 756  # 3 years of ~daily bars
    val_size: int = 63  # last portion of train used for XGBoost eval_set
    test_window: int = 21  # 1 month OOS
    purge_gap: int = 5  # bars between train end and test start (embargo)
    step: int = 21  # monthly retraining cadence


@dataclass
class WindowResult:
    """Results from a single walk-forward window."""

    window_idx: int
    test_start: int
    test_end: int
    predictions: np.ndarray
    actuals: np.ndarray
    feature_importance: dict[str, float] | None = field(default=None)


class WalkForwardEngine:
    """Walk-forward cross-validation engine.

    Trains an EnsembleModel on successive rolling windows, evaluates on
    out-of-sample test bars, and enforces a purge gap to prevent label
    leakage between the train and test sets.
    """

    def __init__(self, config: WalkForwardConfig | None = None) -> None:
        self._config = config if config is not None else WalkForwardConfig()

    def n_windows(self, n_samples: int) -> int:
        """Compute the expected number of walk-forward windows for n_samples bars."""
        cfg = self._config
        min_length = cfg.train_window + cfg.purge_gap + cfg.test_window
        if n_samples < min_length:
            return 0
        return (n_samples - min_length) // cfg.step + 1

    def run(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: list[str] | None = None,
    ) -> list[WindowResult]:
        """Execute walk-forward validation.

        Parameters
        ----------
        X : np.ndarray, shape (n_samples, n_features)
        y : np.ndarray, shape (n_samples,)
        feature_names : list[str] | None
            Optional feature names for importance reporting.

        Returns
        -------
        list[WindowResult]
            One result per OOS window.
        """
        cfg = self._config
        n = len(X)
        results: list[WindowResult] = []

        n_wins = self.n_windows(n)
        if n_wins <= 0:
            logger.warning(
                "walk_forward.run: not enough samples (%d) for config %s", n, cfg
            )
            return results

        analyzer = SHAPAnalyzer(feature_names) if feature_names is not None else None

        for w in range(n_wins):
            train_end = cfg.train_window + w * cfg.step
            train_start = train_end - cfg.train_window
            val_start = train_end - cfg.val_size
            test_start = train_end + cfg.purge_gap
            test_end = test_start + cfg.test_window

            if test_end > n:
                break

            X_train = X[train_start:val_start]
            y_train = y[train_start:val_start]
            X_val = X[val_start:train_end]
            y_val = y[val_start:train_end]
            X_test = X[test_start:test_end]
            y_test = y[test_start:test_end]

            logger.debug(
                "Window %d: train=[%d,%d), val=[%d,%d), test=[%d,%d)",
                w,
                train_start,
                val_start,
                val_start,
                train_end,
                test_start,
                test_end,
            )

            ensemble = EnsembleModel()
            ensemble.fit(X_train, y_train, X_val, y_val)
            predictions = ensemble.predict_proba(X_test)

            feature_importance = None
            if analyzer is not None:
                shap_result = analyzer.analyze_window(
                    ensemble.xgb_model.model, X_test
                )
                feature_importance = shap_result["feature_importance"]

            results.append(
                WindowResult(
                    window_idx=w,
                    test_start=test_start,
                    test_end=test_end,
                    predictions=predictions,
                    actuals=y_test,
                    feature_importance=feature_importance,
                )
            )

        logger.info("walk_forward.run: completed %d windows", len(results))
        return results
