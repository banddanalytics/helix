"""Tests for Numba single-pass backtest accumulator (DATA-06)."""
import pytest


def test_known_pnl() -> None:
    """DATA-06: Accumulator PnL on known trade sequence matches hand-computed values."""
    pytest.skip("Not implemented — Wave 3")


def test_spread_deduction() -> None:
    """DATA-06: Forex PnL is lower than zero-spread PnL by exactly 2 x spread per round-trip trade."""
    pytest.skip("Not implemented — Wave 3")


def test_flat_signal_no_trades() -> None:
    """DATA-06: All-zero signal produces zero PnL and flat equity."""
    pytest.skip("Not implemented — Wave 3")


def test_equity_never_negative() -> None:
    """DATA-06: Equity stays non-negative for a reasonable signal and risk_per_trade."""
    pytest.skip("Not implemented — Wave 3")
