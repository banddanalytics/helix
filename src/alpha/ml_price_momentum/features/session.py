"""Tier 3: 5 session structure features via Numba @njit.

All features at index i use data from index i-1 or earlier (PiT compliant).
No warmup requirement beyond 20 bars for relative bar size.
"""
from __future__ import annotations

import os

os.environ.setdefault("NUMBA_CACHE_DIR", "./numba_cache")

import numpy as np
from numba import njit


@njit(cache=True)
def compute_session_features(
    open_arr: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    hour: np.ndarray,
    dow: np.ndarray,
) -> np.ndarray:
    """Compute 5 session structure features for every bar.

    Parameters
    ----------
    open_arr : np.ndarray
        Open price array of shape (n,).
    high : np.ndarray
        High price array of shape (n,).
    low : np.ndarray
        Low price array of shape (n,).
    close : np.ndarray
        Close price array of shape (n,).
    hour : np.ndarray
        Hour-of-day integer array (0-23) of shape (n,).
    dow : np.ndarray
        Day-of-week integer array (0=Mon..4=Fri) of shape (n,).

    Returns
    -------
    np.ndarray
        Shape (n, 5). PiT: feature[i] uses data from index i-1.

    Feature columns
    ---------------
    0: Session ID   — 0=Asian(0-7 UTC), 1=London(8-11), 2=Overlap(12-16), 3=NY(17-23)
    1: Bar position — (close - low) / max(high - low, 1e-10)
    2: Relative bar size — (high - low) / avg_range of 20 prior bars
    3: Day of week  — integer 0-4
    4: Distance from daily open — (close - open) / max(open, 1e-10)
    """
    n = len(close)
    out = np.full((n, 5), np.nan)

    for i in range(1, n):
        h = hour[i - 1]

        # Session ID based on hour of previous bar (PiT)
        if h <= 7:
            session_id = 0  # Asian
        elif h <= 11:
            session_id = 1  # London
        elif h <= 16:
            session_id = 2  # Overlap
        else:
            session_id = 3  # NY
        out[i, 0] = float(session_id)

        # Bar position: where close sits within the bar range
        hl = high[i - 1] - low[i - 1]
        out[i, 1] = (close[i - 1] - low[i - 1]) / max(hl, 1e-10)

        # Relative bar size: recent range vs 20-bar avg range
        if i >= 21:
            range_sum = 0.0
            for j in range(i - 21, i - 1):
                range_sum += high[j] - low[j]
            avg_range = range_sum / 20.0
            out[i, 2] = (high[i - 1] - low[i - 1]) / max(avg_range, 1e-10)
        else:
            out[i, 2] = 1.0

        # Day of week (from previous bar)
        out[i, 3] = float(dow[i - 1])

        # Distance from daily open
        out[i, 4] = (close[i - 1] - open_arr[i - 1]) / max(open_arr[i - 1], 1e-10)

    return out
