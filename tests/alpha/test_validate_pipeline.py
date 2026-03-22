"""Validation pipeline tests — cost sensitivity and SHAP stability contracts."""
from __future__ import annotations

import numpy as np
import pytest

from src.alpha.ml_price_momentum.evaluation.cost_adjusted_metrics import (
    cost_adjusted_sharpe,
)
from src.alpha.ml_price_momentum.evaluation.shap_analysis import SHAPAnalyzer
from src.backtest.accumulators import single_pass_backtest
from src.backtest.numba_kernels import rolling_atr


def _make_synthetic_backtest_data(
    n: int = 2000, seed: int = 42
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generate synthetic close prices, signals, and ATR for backtesting."""
    rng = np.random.default_rng(seed)
    close = 1.1000 + np.cumsum(rng.normal(0, 0.0003, n))
    close = np.maximum(close, 0.5)

    high = close + rng.uniform(0.0001, 0.0005, n)
    low = close - rng.uniform(0.0001, 0.0005, n)

    atr = rolling_atr(high, low, close, 14)
    first_valid = atr[~np.isnan(atr)]
    fill = float(first_valid[0]) if len(first_valid) > 0 else 0.001
    atr = np.where(np.isnan(atr), fill, atr)

    signal = rng.choice(np.array([-1, 0, 1], dtype=np.int8), size=n)
    return close, signal, atr


def test_cost_sensitivity_monotonic() -> None:
    """Higher spread costs must reduce net Sharpe (extremes check).

    Strict monotonicity per multiplier step isn't guaranteed with
    stochastic signals, but 5x spread must produce lower Sharpe
    than 0.5x spread.
    """
    close, signal, atr = _make_synthetic_backtest_data()
    base_spread = 0.00012
    bars_per_year = 6048

    sharpes = []
    for mult in [0.5, 1.0, 2.0, 5.0]:
        spread_cost = np.full(len(close), base_spread * mult)
        equity, _, pnl = single_pass_backtest(
            close, signal, 0.01, atr, spread_cost,
        )
        returns = pnl[1:] / np.maximum(equity[:-1], 1.0)
        costs = spread_cost[1:]
        sharpe = cost_adjusted_sharpe(returns, costs, bars_per_year=bars_per_year)
        sharpes.append(sharpe)

    assert sharpes[-1] < sharpes[0], (
        f"5x spread Sharpe ({sharpes[-1]:.4f}) should be less than "
        f"0.5x spread Sharpe ({sharpes[0]:.4f})"
    )


def test_shap_stability_structure() -> None:
    """SHAPAnalyzer.track_stability() returns correct structure.

    Features appearing in top_5 in >50% of windows are "stable".
    """
    feature_names = ["f0", "f1", "f2", "f3", "f4", "f5", "f6"]
    analyzer = SHAPAnalyzer(feature_names)

    window_results = [
        {"top_5": ["f0", "f1", "f2", "f3", "f4"]},
        {"top_5": ["f0", "f1", "f2", "f5", "f6"]},
        {"top_5": ["f0", "f1", "f3", "f4", "f5"]},
    ]

    stability = analyzer.track_stability(window_results)

    assert "stable_features" in stability
    assert "stability_scores" in stability

    assert set(stability["stability_scores"].keys()) == set(feature_names)

    # f0 and f1 appear in all 3 windows (100%) — must be stable
    assert "f0" in stability["stable_features"]
    assert "f1" in stability["stable_features"]

    # f6 appears in only 1/3 windows (33%) — must not be stable
    assert "f6" not in stability["stable_features"]

    assert stability["stability_scores"]["f0"] == pytest.approx(1.0)
    assert stability["stability_scores"]["f6"] == pytest.approx(1 / 3)


def test_single_pass_backtest_equity_nonnegative() -> None:
    """Equity curve must stay non-negative with reasonable risk."""
    close, signal, atr = _make_synthetic_backtest_data()
    spread_cost = np.full(len(close), 0.00012)

    equity, _, _ = single_pass_backtest(
        close, signal, 0.01, atr, spread_cost,
    )

    assert np.all(equity > 0), "Equity went negative"
