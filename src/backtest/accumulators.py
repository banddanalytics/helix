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
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute equity curve, position array, and PnL in one forward pass.

    Args:
        close: Price array (n,).
        signal: Signal array (n,) — 1=long, -1=short, 0=flat.
        risk_per_trade: Fraction of equity risked per trade.
        atr: ATR array (n,) for position sizing.
        spread_cost: Spread cost array (n,) — Stage A: variable, Stage B: zeros.

    Returns:
        (equity, position, pnl) — all arrays of shape (n,).
    """
    n = len(close)
    equity = np.empty(n)
    position = np.empty(n, dtype=np.int8)
    pnl = np.empty(n)

    equity[0] = 100_000.0
    position[0] = 0
    pnl[0] = 0.0
    pos_size = 0.0

    for i in range(1, n):
        if signal[i - 1] != 0 and position[i - 1] == 0:
            # Entry
            pos_size = (equity[i - 1] * risk_per_trade) / max(atr[i - 1], 1e-10)
            position[i] = signal[i - 1]
            pnl[i] = -spread_cost[i] * pos_size
        elif signal[i - 1] == 0 and position[i - 1] != 0:
            # Exit
            position[i] = 0
            pnl[i] = (
                position[i - 1] * (close[i] - close[i - 1]) * pos_size
                - spread_cost[i] * pos_size
            )
            pos_size = 0.0
        else:
            # Hold or flat
            position[i] = position[i - 1]
            if position[i] != 0:
                pnl[i] = position[i] * (close[i] - close[i - 1]) * pos_size
            else:
                pnl[i] = 0.0

        equity[i] = equity[i - 1] + pnl[i]

    return equity, position, pnl
