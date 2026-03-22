"""TDD tests for 5-tier 27-feature Numba pipeline — RED phase for Task 1.

These tests verify Tiers 1, 2, 3, and 5 (Numba @njit) feature functions.
"""
from __future__ import annotations

import numpy as np
import pytest


@pytest.fixture
def bar_arrays() -> dict[str, np.ndarray]:
    """500-bar OHLCV arrays seeded for reproducibility."""
    rng = np.random.default_rng(42)
    n = 500
    returns = rng.normal(0, 0.001, size=n)
    close = 1.1000 * np.exp(np.cumsum(returns))
    noise = rng.uniform(0.0001, 0.0010, size=n)
    open_ = close * (1 + rng.uniform(-0.0005, 0.0005, size=n))
    high = np.maximum(open_, close) + noise
    low = np.minimum(open_, close) - noise
    tick_volume = rng.integers(50, 500, size=n).astype(np.float64)
    hour = np.tile(np.arange(24), n // 24 + 1)[:n].astype(np.int64)
    dow = np.tile(np.arange(5), n // 5 + 1)[:n].astype(np.int64)
    return {
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "tick_volume": tick_volume,
        "hour": hour,
        "dow": dow,
    }


# ---------------------------------------------------------------------------
# Task 1 — Tiers 1, 2, 3, 5 (Numba @njit) tests
# ---------------------------------------------------------------------------


def test_momentum_shape_and_finite(bar_arrays: dict[str, np.ndarray]) -> None:
    """Test 1: compute_momentum_features returns (n, 8) with finite values after warmup 253."""
    from src.alpha.ml_price_momentum.features.momentum import compute_momentum_features

    c = bar_arrays["close"]
    h = bar_arrays["high"]
    lo = bar_arrays["low"]
    result = compute_momentum_features(c, h, lo)

    assert result.shape == (len(c), 8), f"Expected ({len(c)}, 8), got {result.shape}"
    assert np.all(np.isfinite(result[253:])), "Non-finite values found after warmup at index 253"


def test_volatility_shape_and_finite(bar_arrays: dict[str, np.ndarray]) -> None:
    """Test 2: compute_volatility_features returns (n, 6) with positive vol values after warmup.

    Warmup notes:
    - Cols 0,1,3,4,5: warmup=64 (lr[0] undefined, first full window at index 64)
    - Col 2 (vol_zscore): warmup=86 (needs 63 rolling 22-bar vols, each needing >= 22 bars)
    """
    from src.alpha.ml_price_momentum.features.volatility import compute_volatility_features

    c = bar_arrays["close"]
    h = bar_arrays["high"]
    lo = bar_arrays["low"]
    result = compute_volatility_features(c, h, lo)

    assert result.shape == (len(c), 6), f"Expected ({len(c)}, 6), got {result.shape}"

    # Check all cols after the longest warmup (86)
    assert np.all(np.isfinite(result[86:])), "Non-finite values found after warmup at index 86"

    # Spot-check simpler cols after their own warmup (64)
    for col in [0, 1, 3, 4, 5]:
        assert np.all(np.isfinite(result[64:, col])), f"Non-finite in vol col {col} after row 64"

    # Vol values (cols 0, 1) should be non-negative
    assert np.all(result[64:, 0] >= 0), "Negative realized vol (5-bar) found"
    assert np.all(result[64:, 1] >= 0), "Negative realized vol (22-bar) found"


def test_session_shape_and_session_ids(bar_arrays: dict[str, np.ndarray]) -> None:
    """Test 3: compute_session_features returns (n, 5) with session_id in {0, 1, 2, 3}."""
    from src.alpha.ml_price_momentum.features.session import compute_session_features

    n = len(bar_arrays["close"])
    result = compute_session_features(
        bar_arrays["open"],
        bar_arrays["high"],
        bar_arrays["low"],
        bar_arrays["close"],
        bar_arrays["hour"],
        bar_arrays["dow"],
    )

    assert result.shape == (n, 5), f"Expected ({n}, 5), got {result.shape}"
    # session_id column (col 0) must be in {0, 1, 2, 3} for valid rows (index >= 1)
    # Row 0 is NaN (no prior bar to look back to — this is correct PiT behavior)
    session_ids = result[1:, 0].astype(np.int64)
    assert np.all((session_ids >= 0) & (session_ids <= 3)), (
        f"session_id out of range [0,3]: {np.unique(session_ids)}"
    )


def test_tick_volume_shape_and_finite(bar_arrays: dict[str, np.ndarray]) -> None:
    """Test 4: compute_tick_volume_features returns (n, 4) with finite values after warmup 20."""
    from src.alpha.ml_price_momentum.features.tick_volume import compute_tick_volume_features

    c = bar_arrays["close"]
    tv = bar_arrays["tick_volume"]
    result = compute_tick_volume_features(c, tv)

    assert result.shape == (len(c), 4), f"Expected ({len(c)}, 4), got {result.shape}"
    assert np.all(np.isfinite(result[20:])), "Non-finite values found after warmup at index 20"


def test_momentum_pit_compliance(bar_arrays: dict[str, np.ndarray]) -> None:
    """Test 5a: Momentum feature at index i uses only data from indices <= i-1."""
    from src.alpha.ml_price_momentum.features.momentum import compute_momentum_features

    c = bar_arrays["close"]
    h = bar_arrays["high"]
    lo = bar_arrays["low"]
    # Full result
    full = compute_momentum_features(c, h, lo)
    # Truncated to first 300 bars — feature at index 299 should match full[299]
    trunc = compute_momentum_features(c[:300], h[:300], lo[:300])
    np.testing.assert_array_almost_equal(
        full[299],
        trunc[299],
        decimal=10,
        err_msg="PiT violation: full[299] != trunc[299] (momentum)",
    )


def test_tick_volume_pit_compliance(bar_arrays: dict[str, np.ndarray]) -> None:
    """Test 5b: Tick volume feature at index i uses only data from indices <= i-1."""
    from src.alpha.ml_price_momentum.features.tick_volume import compute_tick_volume_features

    c = bar_arrays["close"]
    tv = bar_arrays["tick_volume"]
    full = compute_tick_volume_features(c, tv)
    trunc = compute_tick_volume_features(c[:100], tv[:100])
    np.testing.assert_array_almost_equal(
        full[99],
        trunc[99],
        decimal=10,
        err_msg="PiT violation: full[99] != trunc[99] (tick_volume)",
    )


def test_numba_decorators_present() -> None:
    """Test 6: All 4 Numba functions compile under @njit without error."""
    from src.alpha.ml_price_momentum.features.momentum import compute_momentum_features
    from src.alpha.ml_price_momentum.features.session import compute_session_features
    from src.alpha.ml_price_momentum.features.tick_volume import compute_tick_volume_features
    from src.alpha.ml_price_momentum.features.volatility import compute_volatility_features

    # Verify they are numba-compiled by checking they have py_func attribute
    for fn in [
        compute_momentum_features,
        compute_volatility_features,
        compute_session_features,
        compute_tick_volume_features,
    ]:
        assert hasattr(fn, "py_func"), (
            f"{fn.__name__} is not a Numba @njit function (missing .py_func attribute)"
        )
