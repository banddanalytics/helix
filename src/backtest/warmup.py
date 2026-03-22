"""Numba JIT warmup service — compiles all @njit functions at startup.

Per D-17: Triggers compilation with tiny representative arrays so first
real call is fast. NUMBA_CACHE_DIR=./numba_cache for persistent cache.
"""
from __future__ import annotations

import logging
import os
import time

os.environ.setdefault("NUMBA_CACHE_DIR", "./numba_cache")

import numpy as np

logger = logging.getLogger("helix.backtest")


def warmup_numba() -> float:
    """Call every @njit function with tiny representative arrays.

    Returns elapsed seconds for warmup.
    """
    # Ensure cache dir exists
    cache_dir = os.environ.get("NUMBA_CACHE_DIR", "./numba_cache")
    os.makedirs(cache_dir, exist_ok=True)

    start = time.monotonic()

    # Import and warm up accumulators
    from src.backtest.accumulators import single_pass_backtest

    n = 10
    single_pass_backtest(
        close=np.linspace(1.0, 1.1, n),
        signal=np.array([0, 1, 1, 1, 0, -1, -1, -1, 0, 0], dtype=np.int8),
        risk_per_trade=0.01,
        atr=np.full(n, 0.001),
        spread_cost=np.full(n, 0.0001),
    )

    # Import and warm up numba_kernels
    from src.backtest.numba_kernels import rolling_atr

    rolling_atr(
        high=np.linspace(1.01, 1.11, n),
        low=np.linspace(0.99, 1.09, n),
        close=np.linspace(1.0, 1.1, n),
        period=3,
    )

    # Phase 3: Alpha feature warmup
    from src.alpha.ml_price_momentum.features.momentum import compute_momentum_features
    from src.alpha.ml_price_momentum.features.session import compute_session_features
    from src.alpha.ml_price_momentum.features.tick_volume import compute_tick_volume_features
    from src.alpha.ml_price_momentum.features.volatility import compute_volatility_features

    n_warm = 300  # > 253 required warmup
    close_w = np.linspace(1.0, 1.05, n_warm)
    high_w = close_w + 0.001
    low_w = close_w - 0.001
    open_w = close_w - 0.0005
    tv_w = np.full(n_warm, 500.0)
    hour_w = np.tile(np.arange(24), n_warm // 24 + 1)[:n_warm].astype(np.int64)
    dow_w = np.tile(np.arange(5), n_warm // 5 + 1)[:n_warm].astype(np.int64)

    compute_momentum_features(close_w, high_w, low_w)
    compute_volatility_features(close_w, high_w, low_w)
    compute_session_features(open_w, high_w, low_w, close_w, hour_w, dow_w)
    compute_tick_volume_features(close_w, tv_w)

    elapsed = time.monotonic() - start
    logger.info("Numba warmup completed in %.2fs", elapsed)
    return elapsed
