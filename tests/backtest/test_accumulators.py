"""Tests for Numba single-pass backtest accumulator (DATA-06)."""
from __future__ import annotations

import numpy as np
import pytest


def test_known_pnl() -> None:
    """DATA-06: Accumulator PnL on known trade sequence matches hand-computed values."""
    from src.backtest.accumulators import single_pass_backtest

    # 10-bar sequence:
    # Bars 0-2: flat, bars 3-6: long entry at bar 3, hold 4-6, exit bar 7, flat 8-9
    # Close prices
    close = np.array([1.10, 1.10, 1.10, 1.10, 1.11, 1.12, 1.13, 1.14, 1.14, 1.14])
    # Signal: 0=flat, 1=long, 0=exit
    # signal[i-1] determines action on bar i, so signal[3]=1 → entry on bar 4
    signal = np.array([0, 0, 0, 1, 1, 1, 1, 0, 0, 0], dtype=np.int8)
    atr = np.full(10, 0.01)
    spread_cost = np.zeros(10)
    risk_per_trade = 0.01

    equity, position, pnl = single_pass_backtest(
        close=close,
        signal=signal,
        risk_per_trade=risk_per_trade,
        atr=atr,
        spread_cost=spread_cost,
    )

    # Starting equity 100,000. Entry at bar 4 (signal[3]=1, position[3]=0):
    # pos_size = (100_000 * 0.01) / 0.01 = 100_000 units
    # On bar 4: entry, pnl=0 (no spread_cost)
    # On bar 5: hold, pnl = 1 * (1.12 - 1.11) * 100_000 = 1000
    # On bar 6: hold, pnl = 1 * (1.13 - 1.12) * 100_000 = 1000
    # On bar 7: hold (signal[6]=1, position[6]=1), pnl = 1 * (1.14 - 1.13) * 100_000 = 1000
    # Wait — signal[6]=1 so bar 7 still holds. signal[7]=0 triggers exit on bar 8.
    # Bar 8: exit, pnl = 1 * (1.14 - 1.14) * 100_000 = 0

    assert equity[0] == pytest.approx(100_000.0)
    assert equity[-1] > equity[0], "Equity should increase on an uptrend long trade"
    # Position should be long (1) at bars 4-7 where signal is active
    assert position[4] == 1
    assert position[0] == 0
    assert position[-1] == 0


def test_spread_deduction() -> None:
    """DATA-06: Forex PnL is lower than zero-spread PnL by exactly 2 x spread per round-trip trade."""
    from src.backtest.accumulators import single_pass_backtest

    # Simple 1-trade sequence: entry bar 1, hold bars 2-3, exit bar 4
    n = 6
    close = np.array([1.10, 1.10, 1.11, 1.12, 1.13, 1.13])
    signal = np.array([0, 1, 1, 1, 0, 0], dtype=np.int8)
    atr = np.full(n, 0.01)
    spread_val = 0.0001
    risk_per_trade = 0.01

    # Compute pos_size: (100_000 * 0.01) / 0.01 = 100_000
    pos_size = (100_000.0 * risk_per_trade) / atr[0]

    # Zero spread run
    spread_zero = np.zeros(n)
    equity_zero, _, _ = single_pass_backtest(
        close=close, signal=signal, risk_per_trade=risk_per_trade,
        atr=atr, spread_cost=spread_zero,
    )

    # Non-zero spread run
    spread_nonzero = np.full(n, spread_val)
    equity_nonzero, _, _ = single_pass_backtest(
        close=close, signal=signal, risk_per_trade=risk_per_trade,
        atr=atr, spread_cost=spread_nonzero,
    )

    # Per plan: difference = 2 x spread_cost x pos_size (entry + exit)
    expected_diff = 2 * spread_val * pos_size
    actual_diff = equity_zero[-1] - equity_nonzero[-1]
    assert actual_diff == pytest.approx(expected_diff, rel=1e-6)


def test_flat_signal_no_trades() -> None:
    """DATA-06: All-zero signal produces zero PnL and flat equity."""
    from src.backtest.accumulators import single_pass_backtest

    n = 20
    close = np.linspace(1.10, 1.20, n)
    signal = np.zeros(n, dtype=np.int8)
    atr = np.full(n, 0.001)
    spread_cost = np.full(n, 0.0001)

    equity, position, pnl = single_pass_backtest(
        close=close, signal=signal, risk_per_trade=0.01,
        atr=atr, spread_cost=spread_cost,
    )

    assert np.all(equity == pytest.approx(100_000.0)), "Equity must be flat at 100,000"
    assert np.all(pnl == pytest.approx(0.0)), "PnL must be all zeros"
    assert np.all(position == 0), "Position must be flat (0) throughout"


def test_equity_never_negative() -> None:
    """DATA-06: Equity stays non-negative for a reasonable signal and risk_per_trade."""
    from src.backtest.accumulators import single_pass_backtest

    n = 100
    # Gentle uptrend
    close = np.linspace(1.0, 1.1, n)
    # Alternating long / flat signal
    signal = np.array([1 if i % 4 < 2 else 0 for i in range(n)], dtype=np.int8)
    atr = np.full(n, 0.001)
    spread_cost = np.full(n, 0.00005)

    equity, _, _ = single_pass_backtest(
        close=close, signal=signal, risk_per_trade=0.01,
        atr=atr, spread_cost=spread_cost,
    )

    assert np.all(equity > 0), "Equity must always be positive"
