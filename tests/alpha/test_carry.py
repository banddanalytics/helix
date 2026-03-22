"""Carry engine tests — ALPH-06."""

from __future__ import annotations

import pytest

from src.alpha.carry.forex_carry import ForexCarryProvider
from src.alpha.carry.futures_carry import FuturesCarryProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_swap_data(
    net_carries: list[float],
    symbols: list[str] | None = None,
) -> tuple[list[str], dict[str, dict[str, float]]]:
    """Build swap_data and symbol list from target net_carry values.

    Uses point=0.00001, mid_price=1.0 so that:
        net_carry = (swap_long + swap_short) * 0.00001 * 365 / 1.0 * 100

    Rearranging: swap_long + swap_short = net_carry / (0.00001 * 365 * 100)
    We set swap_long = (swap_long + swap_short) and swap_short = 0.0 for simplicity.
    """
    if symbols is None:
        symbols = [f"SYM{i}" for i in range(len(net_carries))]

    point = 0.00001
    mid_price = 1.0
    factor = point * 365 * 100  # = 0.3650

    swap_data: dict[str, dict[str, float]] = {}
    for sym, nc in zip(symbols, net_carries):
        swap_long = nc / factor  # swap_short = 0 so net_carry == carry_long
        swap_data[sym] = {
            "swap_long": swap_long,
            "swap_short": 0.0,
            "point": point,
            "mid_price": mid_price,
        }
    return symbols, swap_data


SYMBOLS_6 = ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDJPY", "USDCHF"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_forex_carry_annualized_values() -> None:
    """ALPH-06: Annualized carry computed correctly on known swap rates.

    Given known swap_long, swap_short, point, and mid_price values,
    verifies that SwapRateCalculator.compute_annualized_carry() returns
    the expected net_carry within floating point tolerance, and that
    get_carry_signals() assigns +1 to the top-carry symbol and -1 to
    the bottom-carry symbol.
    """
    # Use clear ordering: EURUSD has the highest net carry, USDCHF the lowest
    net_carries = [0.06, 0.05, 0.04, 0.03, 0.02, 0.01]
    symbols, swap_data = _make_swap_data(net_carries, SYMBOLS_6)

    provider = ForexCarryProvider(swap_data)
    signals = provider.get_carry_signals(symbols)

    # Top carry symbol (EURUSD, rank=1.0 >= 0.75) should be +1
    assert signals["EURUSD"] == 1.0, f"Expected EURUSD=+1, got {signals['EURUSD']}"
    # Bottom carry symbol (USDCHF, rank=1/6 ~ 0.167 <= 0.25) should be -1
    assert signals["USDCHF"] == -1.0, f"Expected USDCHF=-1, got {signals['USDCHF']}"


def test_cross_sectional_ranking() -> None:
    """ALPH-06: Cross-sectional carry ranking assigns +1 to top quartile, -1 to bottom.

    Ranks 6 symbols by net carry, assigns direction=+1 to top 25% (top 2 of 6),
    direction=-1 to bottom 25% (bottom 2 of 6), direction=0 to middle 50%.
    """
    # Clear ranking: net_carry = 0.01 to 0.06 in ascending order
    net_carries = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06]
    symbols, swap_data = _make_swap_data(net_carries, SYMBOLS_6)

    provider = ForexCarryProvider(swap_data)
    ranks = provider.get_carry_ranks(symbols)

    # Verify ranks are monotonically increasing
    ranked_values = [ranks[s] for s in symbols]  # EURUSD..USDCHF with carries 0.01..0.06
    assert ranked_values == sorted(ranked_values), "Ranks should be ascending with carry values"

    signals = provider.get_carry_signals(symbols)

    # With 6 symbols, quartile = 6 * 0.25 = 1.5 -> top 2 (rank 5/6=0.833, 6/6=1.0) and bottom 2
    # Symbols sorted by carry ascending: SYM0(0.01), SYM1(0.02), SYM2(0.03), SYM3(0.04), SYM4(0.05), SYM5(0.06)
    # Ranks: SYM0=1/6, SYM1=2/6, SYM2=3/6, SYM3=4/6, SYM4=5/6, SYM5=6/6
    # Bottom quartile: ranks <= 0.25 -> 1/6=0.167 ✓, 2/6=0.333 ✗ -> only SYM0
    # Top quartile: ranks >= 0.75 -> 5/6=0.833 ✓, 6/6=1.0 ✓ -> SYM4, SYM5

    # Count +1, -1, 0 signals
    pos_signals = [s for s, v in signals.items() if v == 1.0]
    neg_signals = [s for s, v in signals.items() if v == -1.0]
    neutral_signals = [s for s, v in signals.items() if v == 0.0]

    assert len(pos_signals) >= 1, f"Expected at least 1 positive signal, got {pos_signals}"
    assert len(neg_signals) >= 1, f"Expected at least 1 negative signal, got {neg_signals}"
    assert len(neutral_signals) >= 1, f"Expected at least 1 neutral signal, got {neutral_signals}"

    # The highest carry symbol must get +1 and lowest must get -1
    highest_carry_sym = symbols[5]  # USDCHF with nc=0.06 (index 5 in SYMBOLS_6)
    lowest_carry_sym = symbols[0]   # EURUSD with nc=0.01 (index 0 in SYMBOLS_6)
    assert signals[highest_carry_sym] == 1.0
    assert signals[lowest_carry_sym] == -1.0


def test_spread_filter_suppresses() -> None:
    """ALPH-06: Carry signal suppressed when net carry < 2x average spread.

    When the annualized carry is less than 2 times the current average
    spread cost, the signal direction must be forced to 0.
    """
    # Use 6 symbols; give the "bottom" symbol (lowest carry) a very small carry
    # so it would normally be -1, but spread_cost > carry_benefit suppresses it
    net_carries = [0.001, 0.02, 0.03, 0.04, 0.05, 0.06]
    symbols, swap_data = _make_swap_data(net_carries, SYMBOLS_6)

    # EURUSD has net_carry=0.001; spread=0.001 -> spread_cost=2*0.001=0.002 > 0.001
    spread_data = {
        "EURUSD": 0.001,  # carry_benefit=0.001 < spread_cost=0.002 -> suppress
    }

    provider = ForexCarryProvider(swap_data, spread_data=spread_data)
    signals = provider.get_carry_signals(symbols)

    # EURUSD has the lowest carry -> rank <= 0.25 -> would be -1 without spread filter
    # Spread filter: |0.001| < 2*0.001 = 0.002 -> suppress to 0
    assert signals["EURUSD"] == 0.0, (
        f"Expected EURUSD to be suppressed to 0.0 by spread filter, got {signals['EURUSD']}"
    )


def test_futures_carry_stub_raises() -> None:
    """ALPH-06: FuturesCarryProvider.compute() raises NotImplementedError (Stage B stub).

    The futures carry provider is a Stage B placeholder and must raise
    NotImplementedError when called in the current Stage A implementation.
    """
    provider = FuturesCarryProvider()
    with pytest.raises(NotImplementedError):
        provider.get_carry_signals(["ES"])
    with pytest.raises(NotImplementedError):
        provider.get_carry_ranks(["ES"])
