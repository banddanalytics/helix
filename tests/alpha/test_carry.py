"""Carry engine tests — ALPH-06."""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="Stub — implementation in plan 03-04")
def test_forex_carry_annualized_values(sample_signal_df: object) -> None:
    """ALPH-06: Annualized carry computed correctly on known swap rates.

    Given known swap_long, swap_short, point, and mid_price values,
    verifies that SwapRateCalculator.compute_annualized_carry() returns
    the expected net_carry within floating point tolerance.
    """
    raise AssertionError("Not yet implemented")


@pytest.mark.skip(reason="Stub — implementation in plan 03-04")
def test_cross_sectional_ranking(sample_signal_df: object) -> None:
    """ALPH-06: Cross-sectional carry ranking assigns +1 to top quartile, -1 to bottom.

    Ranks 6 symbols by net carry, assigns direction=+1 to top 25%,
    direction=-1 to bottom 25%, direction=0 to the middle 50%.
    """
    raise AssertionError("Not yet implemented")


@pytest.mark.skip(reason="Stub — implementation in plan 03-04")
def test_spread_filter_suppresses(sample_signal_df: object) -> None:
    """ALPH-06: Carry signal suppressed when net carry < 2x average spread.

    When the annualized carry is less than 2 times the current average
    spread cost, the signal direction must be forced to 0.
    """
    raise AssertionError("Not yet implemented")


@pytest.mark.skip(reason="Stub — implementation in plan 03-04")
def test_futures_carry_stub_raises() -> None:
    """ALPH-06: FuturesCarryProvider.compute() raises NotImplementedError (Stage B stub).

    The futures carry provider is a Stage B placeholder and must raise
    NotImplementedError when called in the current Stage A implementation.
    """
    raise AssertionError("Not yet implemented")
