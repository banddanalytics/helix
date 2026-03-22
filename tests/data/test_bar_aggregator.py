"""Tests for bar aggregation from ticks with session tagging (DATA-03)."""
import pytest


def test_1m_bar_ohlcv_from_known_ticks() -> None:
    """DATA-03: 1-minute bar OHLCV matches hand-computed values from tick sequence."""
    pytest.skip("Not implemented — Wave 2")


def test_all_six_timeframes_produced() -> None:
    """DATA-03: aggregate produces bars for 1m, 5m, 15m, 1h, 4h, 1d."""
    pytest.skip("Not implemented — Wave 2")


def test_session_tags() -> None:
    """DATA-03: session column is int8 — 0=Asian(00-08), 1=London(08-13), 2=Overlap(13-16), 3=NY(16-21)."""
    pytest.skip("Not implemented — Wave 2")


def test_spread_avg_and_max_per_bar() -> None:
    """DATA-03: spread_avg and spread_max computed correctly per bar."""
    pytest.skip("Not implemented — Wave 2")


def test_bar_symbol_naming() -> None:
    """DATA-03: Bars written to forex_bars with symbol format EURUSD_1m, EURUSD_5m, etc."""
    pytest.skip("Not implemented — Wave 2")
