"""Stage A swap-based carry signal provider.

ForexCarryProvider wraps SwapRateCalculator to produce cross-sectional
carry signals with a spread-cost filter.

Design reference: ALPH-06
"""

from __future__ import annotations

import logging

from src.alpha.carry.carry_provider import CarrySignalProvider
from src.execution.swap_rates import CarryResult, SwapRateCalculator

logger = logging.getLogger("helix.alpha")


class ForexCarryProvider(CarrySignalProvider):
    """Carry signal provider for Stage A Forex instruments.

    Uses MT5 swap rates converted to annualized carry via SwapRateCalculator.
    Produces cross-sectional rank signals (+1 / 0 / -1) and suppresses
    symbols where carry benefit is less than 2x the median spread cost.

    Args:
        swap_data: Mapping of symbol ->
            {"swap_long": float, "swap_short": float,
             "point": float, "mid_price": float}.
        spread_data: Optional mapping of symbol -> median spread (float).
            When provided, signals are suppressed when
            |net_carry| < 2 * spread.
    """

    def __init__(
        self,
        swap_data: dict[str, dict[str, float]],
        spread_data: dict[str, float] | None = None,
    ) -> None:
        self._swap_data = swap_data
        self._spread_data = spread_data or {}

    def _compute_carries(self, symbols: list[str]) -> dict[str, CarryResult]:
        """Compute annualized carry for each symbol via SwapRateCalculator.

        Args:
            symbols: Symbols to compute carry for.

        Returns:
            Mapping of symbol -> CarryResult.
        """
        results: dict[str, CarryResult] = {}
        for symbol in symbols:
            data = self._swap_data.get(symbol)
            if data is None:
                logger.warning("No swap data for %s — defaulting carry to zero", symbol)
                results[symbol] = CarryResult(carry_long=0.0, carry_short=0.0, net_carry=0.0)
                continue
            results[symbol] = SwapRateCalculator.compute_annualized_carry(
                swap_long=data["swap_long"],
                swap_short=data["swap_short"],
                point=data["point"],
                mid_price=data["mid_price"],
            )
        return results

    def get_carry_ranks(self, symbols: list[str]) -> dict[str, float]:
        """Compute cross-sectional percentile rank for each symbol.

        Ranks by net_carry using ordinal ranking normalised to [0, 1].
        Rank 1.0 = highest carry, approaching 0.0 = lowest.

        Args:
            symbols: Symbols to rank.

        Returns:
            Mapping of symbol -> percentile rank in (0, 1].
        """
        carries = self._compute_carries(symbols)
        n = len(symbols)
        if n == 0:
            return {}

        # Sort symbols by net_carry ascending, assign ordinal rank normalised to (0, 1]
        sorted_symbols = sorted(symbols, key=lambda s: carries[s].net_carry)
        return {symbol: (rank_idx + 1) / n for rank_idx, symbol in enumerate(sorted_symbols)}

    def get_carry_signals(self, symbols: list[str]) -> dict[str, float]:
        """Compute carry direction signals with cross-sectional ranking and spread filter.

        Algorithm:
        1. Compute annualized carry for each symbol.
        2. Rank cross-sectionally; top quartile (rank >= 0.75) -> +1,
           bottom quartile (rank <= 0.25) -> -1, middle -> 0.
        3. Apply spread filter: if |net_carry| < 2 * spread, override to 0.

        Args:
            symbols: Symbols to generate signals for.

        Returns:
            Mapping of symbol -> signal: +1.0, -1.0, or 0.0.
        """
        carries = self._compute_carries(symbols)
        ranks = self.get_carry_ranks(symbols)

        signals: dict[str, float] = {}
        for symbol in symbols:
            rank = ranks[symbol]
            if rank >= 0.75:
                signal = 1.0
            elif rank <= 0.25:
                signal = -1.0
            else:
                signal = 0.0

            # Spread filter: suppress signal if carry benefit < 2x spread cost
            if signal != 0.0 and symbol in self._spread_data:
                carry_benefit = abs(carries[symbol].net_carry)
                spread_cost = 2.0 * self._spread_data[symbol]
                if carry_benefit < spread_cost:
                    logger.warning(
                        "Carry signal suppressed for %s: carry_benefit=%.6f < spread_cost=%.6f",
                        symbol,
                        carry_benefit,
                        spread_cost,
                    )
                    signal = 0.0

            signals[symbol] = signal

        return signals


__all__ = ["ForexCarryProvider"]
