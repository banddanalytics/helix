"""Stage B futures carry provider — placeholder stub.

FuturesCarryProvider requires CME term structure data (front/back
contract prices) which is only available in Stage B co-located execution.
This stub exists to satisfy the CarrySignalProvider interface contract
while making it impossible to accidentally use in Stage A.

Design reference: ALPH-06
"""

from __future__ import annotations

from src.alpha.carry.carry_provider import CarrySignalProvider


class FuturesCarryProvider(CarrySignalProvider):
    """Stage B carry provider based on CME futures term structure.

    NOT for use in Stage A. Raises NotImplementedError on all calls.
    """

    def get_carry_signals(self, symbols: list[str]) -> dict[str, float]:
        """Stage B stub — raises NotImplementedError."""
        raise NotImplementedError(
            "FuturesCarryProvider is a Stage B stub — requires CME term structure data"
        )

    def get_carry_ranks(self, symbols: list[str]) -> dict[str, float]:
        """Stage B stub — raises NotImplementedError."""
        raise NotImplementedError("FuturesCarryProvider is a Stage B stub")


__all__ = ["FuturesCarryProvider"]
