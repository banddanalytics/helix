"""Tier 1: 8 momentum features via Numba @njit.

All features at index i use data from close[i-1] or earlier (PiT compliant).
Warmup period: 253 bars (required for 252-bar return).
"""
from __future__ import annotations

import os

os.environ.setdefault("NUMBA_CACHE_DIR", "./numba_cache")

import numpy as np
from numba import njit


@njit(cache=True)
def compute_momentum_features(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
) -> np.ndarray:
    """Compute 8 momentum features for every bar.

    Parameters
    ----------
    close : np.ndarray
        Close price array of shape (n,).
    high : np.ndarray
        High price array of shape (n,).
    low : np.ndarray
        Low price array of shape (n,).

    Returns
    -------
    np.ndarray
        Shape (n, 8) — NaN for rows < 253 (warmup). PiT: feature[i] uses
        data up to close[i-1].

    Feature columns
    ---------------
    0: 1-bar return
    1: 5-bar return
    2: 10-bar return
    3: 22-bar return
    4: 63-bar return
    5: 252-bar return
    6: Momentum acceleration (5-bar mom difference)
    7: Range expansion (recent range / 20-bar avg range)
    """
    n = len(close)
    out = np.full((n, 8), np.nan)

    for i in range(253, n):
        # Returns — all use close[i-1] as the most recent observation (PiT)
        out[i, 0] = close[i - 1] / close[i - 2] - 1.0          # 1-bar
        out[i, 1] = close[i - 1] / close[i - 6] - 1.0          # 5-bar
        out[i, 2] = close[i - 1] / close[i - 11] - 1.0         # 10-bar
        out[i, 3] = close[i - 1] / close[i - 23] - 1.0         # 22-bar
        out[i, 4] = close[i - 1] / close[i - 64] - 1.0         # 63-bar
        out[i, 5] = close[i - 1] / close[i - 253] - 1.0        # 252-bar

        # Momentum acceleration: difference of consecutive 5-bar momenta
        mom5_current = close[i - 1] / close[i - 6] - 1.0
        mom5_previous = close[i - 2] / close[i - 7] - 1.0
        out[i, 6] = mom5_current - mom5_previous

        # Range expansion: (recent range) / (mean range of 20 prior bars)
        recent_range = high[i - 1] - low[i - 1]
        range_sum = 0.0
        for j in range(i - 21, i - 1):
            range_sum += high[j] - low[j]
        avg_range = range_sum / 20.0
        if avg_range > 0.0:
            out[i, 7] = recent_range / avg_range
        else:
            out[i, 7] = 1.0

    return out
