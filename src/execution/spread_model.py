"""Variable spread tracking and cost-adjusted signal suppression.

SpreadModel maintains a rolling window of observed spreads and provides
statistical properties (median, p95, volatility) used to suppress or
attenuate trading signals when the spread cost exceeds a configurable
fraction of expected profit.

Design reference: D-28
"""

from __future__ import annotations

from collections import deque

import numpy as np


class SpreadModel:
    """Rolling spread distribution model with cost-adjusted signal filtering.

    Args:
        max_history: Maximum number of spread observations to retain.
            Oldest observations are evicted when the window is full.
            Default is 10,000.
    """

    def __init__(self, max_history: int = 10_000) -> None:
        self._history: deque[float] = deque(maxlen=max_history)

    def update(self, spread: float) -> None:
        """Record a new spread observation.

        Args:
            spread: Current bid-ask spread in price units (e.g. pips or points).
        """
        self._history.append(spread)

    @property
    def median(self) -> float:
        """Median of the spread history.

        Returns:
            Median spread, or 0.0 if no observations recorded.
        """
        if not self._history:
            return 0.0
        return float(np.median(list(self._history)))

    @property
    def p95(self) -> float:
        """95th-percentile of the spread history.

        Returns:
            p95 spread, or 0.0 if no observations recorded.
        """
        if not self._history:
            return 0.0
        return float(np.percentile(list(self._history), 95))

    @property
    def volatility(self) -> float:
        """Standard deviation of the spread history.

        Returns:
            Spread volatility, or 0.0 if no observations recorded.
        """
        if not self._history:
            return 0.0
        return float(np.std(list(self._history)))

    def cost_adjusted_signal(
        self,
        raw_signal: float,
        expected_holding_bars: int,
        avg_bar_range: float,
    ) -> float:
        """Return a spread-adjusted signal, suppressing when cost is too high.

        Computes the expected round-trip cost as a fraction of expected profit.
        If the cost ratio exceeds 50%, the signal is suppressed to 0.0.
        Otherwise the signal is attenuated by (1 - cost_ratio).

        Formula:
            expected_move = abs(raw_signal) * avg_bar_range * expected_holding_bars
            cost_ratio    = (2 * median_spread) / expected_move

        Args:
            raw_signal: Unscaled alpha signal (any non-zero float).
            expected_holding_bars: Anticipated trade duration in bars.
            avg_bar_range: Average price range per bar (e.g. ATR in price units).

        Returns:
            Attenuated signal, or 0.0 if spread eats more than 50% of expected
            profit or if the expected move is zero.
        """
        expected_move = abs(raw_signal) * avg_bar_range * expected_holding_bars
        if expected_move == 0.0:
            return 0.0
        round_trip_cost = 2.0 * self.median
        cost_ratio = round_trip_cost / expected_move
        if cost_ratio > 0.5:
            return 0.0  # Suppressed: spread consumes >50% of expected profit
        return raw_signal * (1.0 - cost_ratio)
