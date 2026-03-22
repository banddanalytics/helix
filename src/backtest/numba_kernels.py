"""Shared Numba-compiled indicators used by multiple strategies.

Isolated in a separate file to avoid cache invalidation when
non-JIT code changes (per RESEARCH Pitfall 4).
"""
from __future__ import annotations

import os

os.environ.setdefault("NUMBA_CACHE_DIR", "./numba_cache")

import numpy as np
from numba import njit


@njit(cache=True)
def rolling_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> np.ndarray:
    """Compute Average True Range using Wilder's smoothing.

    Returns array of shape (n,) with NaN for first `period` values.
    """
    n = len(close)
    atr = np.full(n, np.nan)
    tr = np.empty(n)
    tr[0] = high[0] - low[0]

    for i in range(1, n):
        hl = high[i] - low[i]
        hc = abs(high[i] - close[i - 1])
        lc = abs(low[i] - close[i - 1])
        tr[i] = max(hl, hc, lc)

    # Initial ATR: simple average of first `period` true ranges
    if n >= period:
        atr[period - 1] = np.mean(tr[:period])
        for i in range(period, n):
            atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period

    return atr
