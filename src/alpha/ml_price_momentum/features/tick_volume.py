"""Tier 5: 4 tick volume proxy features via Numba @njit.

All features at index i use data from index i-1 or earlier (PiT compliant).
Warmup period: 20 bars.

NOTE: Tick volume is a proxy only — no genuine order book data in Stage A.
"""
from __future__ import annotations

import os

os.environ.setdefault("NUMBA_CACHE_DIR", "./numba_cache")

import numpy as np
from numba import njit


@njit(cache=True)
def compute_tick_volume_features(
    close: np.ndarray,
    tick_volume: np.ndarray,
) -> np.ndarray:
    """Compute 4 tick volume features for every bar.

    Parameters
    ----------
    close : np.ndarray
        Close price array of shape (n,).
    tick_volume : np.ndarray
        Tick volume array of shape (n,).

    Returns
    -------
    np.ndarray
        Shape (n, 4) — NaN for rows < 20 (warmup). PiT: feature[i] uses
        data up to tick_volume[i-1].

    Feature columns
    ---------------
    0: Relative tick volume — tick_volume[i-1] / mean(tick_volume[i-21:i-1])
    1: Volume trend — mean(tv[i-6:i-1]) / max(mean(tv[i-11:i-6]), 1e-10)
    2: Price-volume divergence — sign(Δclose) * sign(Δtick_volume)
    3: Volume spike — 1.0 if tick_volume[i-1] > 2 * mean(tv[i-21:i-1]) else 0.0
    """
    n = len(close)
    out = np.full((n, 4), np.nan)

    for i in range(20, n):
        # Mean of 20 prior bars (i-21 to i-2, exclusive of current)
        mean_20 = 0.0
        for j in range(i - 21, i - 1):
            mean_20 += tick_volume[j]
        mean_20 /= 20.0

        tv_prev = tick_volume[i - 1]

        # Relative tick volume
        out[i, 0] = tv_prev / max(mean_20, 1e-10)

        # Volume trend: recent 5-bar mean vs prior 5-bar mean
        recent_sum = 0.0
        for j in range(i - 6, i - 1):
            recent_sum += tick_volume[j]
        recent_mean = recent_sum / 5.0

        prior_sum = 0.0
        for j in range(i - 11, i - 6):
            prior_sum += tick_volume[j]
        prior_mean = prior_sum / 5.0

        out[i, 1] = recent_mean / max(prior_mean, 1e-10)

        # Price-volume divergence
        price_dir = 0.0
        if close[i - 1] > close[i - 2]:
            price_dir = 1.0
        elif close[i - 1] < close[i - 2]:
            price_dir = -1.0

        vol_dir = 0.0
        if tick_volume[i - 1] > tick_volume[i - 2]:
            vol_dir = 1.0
        elif tick_volume[i - 1] < tick_volume[i - 2]:
            vol_dir = -1.0

        out[i, 2] = price_dir * vol_dir

        # Volume spike flag
        out[i, 3] = 1.0 if tv_prev > 2.0 * mean_20 else 0.0

    return out
