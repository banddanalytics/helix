"""Tier 2: 6 volatility features via Numba @njit.

All features at index i use data from close[i-1] or earlier (PiT compliant).
Warmup period: 63 bars.

NOTE: std computation uses manual loop — pandas/numpy std are not Numba-compatible.
"""
from __future__ import annotations

import os

os.environ.setdefault("NUMBA_CACHE_DIR", "./numba_cache")

import numpy as np
from numba import njit


@njit(cache=True)
def _std(arr: np.ndarray) -> float:
    """Sample standard deviation (ddof=1) for a 1-D array."""
    n = len(arr)
    if n < 2:
        return 0.0
    mean = 0.0
    for v in arr:
        mean += v
    mean /= n
    var = 0.0
    for v in arr:
        diff = v - mean
        var += diff * diff
    return (var / (n - 1)) ** 0.5


@njit(cache=True)
def compute_volatility_features(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
) -> np.ndarray:
    """Compute 6 volatility features for every bar.

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
        Shape (n, 6) — NaN for rows < 63 (warmup). PiT: feature[i] uses
        log returns computed from data up to close[i-1].

    Feature columns
    ---------------
    0: 5-bar realized vol
    1: 22-bar realized vol
    2: 63-bar realized vol
    3: Vol ratio (vol_5 / vol_63)
    4: Parkinson vol (22-bar)
    5: Vol of vol (std of 5-bar vol over 22 bars)
    """
    n = len(close)
    out = np.full((n, 6), np.nan)

    # Pre-compute log returns: lr[i] = log(close[i] / close[i-1])
    # lr[0] is undefined; start from index 1
    lr = np.full(n, np.nan)
    for i in range(1, n):
        lr[i] = np.log(close[i] / close[i - 1])

    for i in range(64, n):
        # Realized vol uses lr up through lr[i-1] (PiT: excludes lr[i])
        # 5-bar: lr[i-5 .. i-1] (5 values)
        vol5 = _std(lr[i - 5: i])
        # 22-bar: lr[i-22 .. i-1] (22 values)
        vol22 = _std(lr[i - 22: i])
        # 63-bar: lr[i-63 .. i-1] (63 values)
        vol63 = _std(lr[i - 63: i])

        out[i, 0] = vol5
        out[i, 1] = vol22
        out[i, 2] = vol63
        out[i, 3] = vol5 / max(vol63, 1e-10)

        # Parkinson vol (22-bar): sqrt(sum(ln(H/L)^2) / (22 * 4 * ln(2)))
        park_sum = 0.0
        for j in range(i - 22, i):
            ratio = high[j] / max(low[j], 1e-10)
            log_hl = np.log(ratio)
            park_sum += log_hl * log_hl
        out[i, 4] = (park_sum / (22.0 * 4.0 * np.log(2.0))) ** 0.5

        # Vol of vol: std of rolling 5-bar vols over last 22 positions
        volvol_arr = np.empty(22)
        for k in range(22):
            j = i - 22 + k
            # 5-bar vol ending at j (i.e., lr[j-4 .. j])
            if j >= 5:
                volvol_arr[k] = _std(lr[j - 4: j + 1])
            else:
                volvol_arr[k] = 0.0
        out[i, 5] = _std(volvol_arr)

    return out
