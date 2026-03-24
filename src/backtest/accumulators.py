"""Numba JIT single-pass backtest accumulator.

Per D-16: single_pass_backtest(close, signal, risk_per_trade, atr, spread_cost).
spread_cost is the dual-stage parameter: Stage A = SpreadModel.median, Stage B = zeros.
"""

from __future__ import annotations

import os

# Set Numba cache dir before importing numba (per D-17)
os.environ.setdefault("NUMBA_CACHE_DIR", "./numba_cache")

import numpy as np
from numba import njit


@njit(cache=True)
def single_pass_backtest(
    close: np.ndarray,
    signal: np.ndarray,
    risk_per_trade: float,
    atr: np.ndarray,
    spread_cost: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Compute equity curve, position array, PnL, and gross PnL in one forward pass.

    Args:
        close: Price array (n,).
        signal: Signal array (n,) — 1=long, -1=short, 0=flat.
        risk_per_trade: Fraction of equity risked per trade.
        atr: ATR array (n,) for position sizing.
        spread_cost: Spread cost array (n,) — Stage A: variable, Stage B: zeros.

    Returns:
        (equity, position, pnl, gross_pnl) — all arrays of shape (n,).
        pnl includes spread cost deductions; gross_pnl is raw directional PnL only.
    """
    n = len(close)
    equity = np.empty(n)
    position = np.empty(n, dtype=np.int8)
    pnl = np.empty(n)
    gross_pnl = np.empty(n)

    equity[0] = 100_000.0
    position[0] = 0
    pnl[0] = 0.0
    gross_pnl[0] = 0.0
    pos_size = 0.0

    for i in range(1, n):
        if signal[i - 1] != 0 and position[i - 1] == 0:
            # Entry — spread charged, no directional PnL on entry bar
            pos_size = (equity[i - 1] * risk_per_trade) / max(atr[i - 1], 1e-10)
            position[i] = signal[i - 1]
            pnl[i] = -spread_cost[i] * pos_size
            gross_pnl[i] = 0.0
        elif signal[i - 1] == 0 and position[i - 1] != 0:
            # Exit — directional PnL plus spread charged
            position[i] = 0
            dir_pnl = position[i - 1] * (close[i] - close[i - 1]) * pos_size
            pnl[i] = dir_pnl - spread_cost[i] * pos_size
            gross_pnl[i] = dir_pnl
            pos_size = 0.0
        else:
            # Hold or flat
            position[i] = position[i - 1]
            if position[i] != 0:
                dir_pnl = position[i] * (close[i] - close[i - 1]) * pos_size
                pnl[i] = dir_pnl
                gross_pnl[i] = dir_pnl
            else:
                pnl[i] = 0.0
                gross_pnl[i] = 0.0

        equity[i] = equity[i - 1] + pnl[i]

    return equity, position, pnl, gross_pnl
