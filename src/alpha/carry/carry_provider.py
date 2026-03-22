"""Abstract base class for carry signal providers.

Design reference: ALPH-06 — Stage A swap-based carry, Stage B futures carry.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class CarrySignalProvider(ABC):
    """Abstract base for carry signal computation.

    Subclasses implement carry computation via swap rates (Stage A)
    or futures term structure (Stage B).
    """

    @abstractmethod
    def get_carry_signals(self, symbols: list[str]) -> dict[str, float]:
        """Return carry signal for each symbol.

        Args:
            symbols: Instrument symbols to compute signals for.

        Returns:
            Mapping of symbol -> signal float: +1.0 (long), -1.0 (short), 0.0 (neutral).
        """

    @abstractmethod
    def get_carry_ranks(self, symbols: list[str]) -> dict[str, float]:
        """Return cross-sectional percentile rank for each symbol.

        Args:
            symbols: Instrument symbols to rank.

        Returns:
            Mapping of symbol -> percentile rank in [0.0, 1.0].
            Rank 1.0 means highest carry.
        """


__all__ = ["CarrySignalProvider"]
