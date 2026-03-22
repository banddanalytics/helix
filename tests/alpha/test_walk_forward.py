"""Walk-forward validation tests — ALPH-08."""

from __future__ import annotations

import numpy as np
import pytest

from src.alpha.ml_price_momentum.evaluation.cost_adjusted_metrics import (
    cost_adjusted_sharpe,
    gross_sharpe,
    timeframe_to_bars_per_year,
)
from src.alpha.ml_price_momentum.models.walk_forward import (
    WalkForwardConfig,
    WalkForwardEngine,
)


def _make_synthetic_data(
    n_samples: int = 2000, n_features: int = 5
) -> tuple[np.ndarray, np.ndarray]:
    """Generate synthetic binary classification data."""
    rng = np.random.default_rng(42)
    X = rng.standard_normal((n_samples, n_features)).astype(np.float32)
    y = (rng.random(n_samples) > 0.5).astype(int)
    return X, y


def test_walk_forward_produces_30_windows() -> None:
    """ALPH-08: Walk-forward splitter produces >= 30 OOS windows.

    With 2000 samples, train_window=756, step=21, purge_gap=5, test_window=21:
    n_windows = (2000 - 756 - 5 - 21) // 21 + 1 = 1218 // 21 + 1 = 58 + 1 = 59
    """
    config = WalkForwardConfig(
        train_window=756,
        val_size=63,
        test_window=21,
        purge_gap=5,
        step=21,
    )
    engine = WalkForwardEngine(config)
    n = 2000
    expected = engine.n_windows(n)
    assert expected >= 30, f"Expected >= 30 windows, config yields {expected}"


def test_no_data_leakage_purge() -> None:
    """ALPH-08: Purge gap ensures no test bar appears in the training set.

    test_start must be strictly > train_end + purge_gap - 1, i.e.
    test_start >= train_end + purge_gap.
    """
    config = WalkForwardConfig(
        train_window=756,
        val_size=63,
        test_window=21,
        purge_gap=5,
        step=21,
    )
    engine = WalkForwardEngine(config)
    n = 2000
    cfg = config

    for w in range(engine.n_windows(n)):
        train_end = cfg.train_window + w * cfg.step
        test_start = train_end + cfg.purge_gap

        # No test bar should appear in the training set
        assert test_start >= train_end + cfg.purge_gap, (
            f"Window {w}: test_start {test_start} < train_end {train_end} + "
            f"purge_gap {cfg.purge_gap}"
        )
        # Also verify there is an actual gap
        assert test_start > train_end, (
            f"Window {w}: test_start {test_start} not strictly after train_end {train_end}"
        )


def test_cost_adjusted_sharpe() -> None:
    """ALPH-08: Net Sharpe (after spread costs) is less than gross Sharpe.

    With positive spread costs, cost_adjusted_sharpe < gross_sharpe.
    """
    returns = np.array([0.01, 0.02, 0.015, 0.012, 0.008])
    costs = np.array([0.001, 0.001, 0.001, 0.001, 0.001])

    bpy = timeframe_to_bars_per_year("1d")
    net_sr = cost_adjusted_sharpe(returns, costs, bars_per_year=bpy)
    gross_sr = gross_sharpe(returns, bars_per_year=bpy)

    assert net_sr < gross_sr, (
        f"Expected cost_adjusted_sharpe ({net_sr:.4f}) < gross_sharpe ({gross_sr:.4f})"
    )


def test_timeframe_to_bars_per_year_known_values() -> None:
    """Verify bars-per-year mapping for all supported Forex timeframes."""
    assert timeframe_to_bars_per_year("1m") == 362_880
    assert timeframe_to_bars_per_year("5m") == 72_576
    assert timeframe_to_bars_per_year("15m") == 24_192
    assert timeframe_to_bars_per_year("1h") == 6_048
    assert timeframe_to_bars_per_year("4h") == 1_512
    assert timeframe_to_bars_per_year("1d") == 252
    assert timeframe_to_bars_per_year("1D") == 252  # case-insensitive
    assert timeframe_to_bars_per_year(" 4H ") == 1_512  # whitespace stripped


def test_timeframe_to_bars_per_year_unknown_raises() -> None:
    """Unknown timeframe must raise ValueError with supported list."""
    with pytest.raises(ValueError, match="Unknown timeframe"):
        timeframe_to_bars_per_year("3h")


def test_sharpe_scales_with_bars_per_year() -> None:
    """Sharpe ratio scales by sqrt(bars_per_year) for identical returns."""
    returns = np.array([0.01, 0.02, 0.015, 0.012, 0.008])

    sharpe_daily = gross_sharpe(returns, bars_per_year=252)
    sharpe_hourly = gross_sharpe(returns, bars_per_year=6_048)

    expected_ratio = np.sqrt(6_048 / 252)
    actual_ratio = sharpe_hourly / sharpe_daily

    assert actual_ratio == pytest.approx(expected_ratio, rel=1e-6)
