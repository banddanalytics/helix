"""Annualized carry computation from broker swap rates.

SwapRateCalculator converts raw MT5 swap point values into annualized
percentage carry figures, consistent with industry conventions for overnight
financing costs.

Design reference: D-30
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CarryResult:
    """Annualized carry figures for a single instrument.

    Attributes:
        carry_long: Annualized carry (%) for a long position.  Negative means
            the trader pays to hold; positive means the trader earns.
        carry_short: Annualized carry (%) for a short position.
        net_carry: carry_long + carry_short.  One value will typically be
            negative because brokers charge more than they pay.
    """

    carry_long: float
    carry_short: float
    net_carry: float


class SwapRateCalculator:
    """Converts broker swap points to annualized percentage carry.

    MT5 swap points represent the daily financing cost/credit in price-point
    units per lot.  This class converts them to an annualized percentage so
    they can be compared against other alpha signals on a common scale.
    """

    @staticmethod
    def compute_annualized_carry(
        swap_long: float,
        swap_short: float,
        point: float,
        mid_price: float,
    ) -> CarryResult:
        """Convert daily swap points to annualized carry percentages.

        Formula:
            annual_carry = (swap_points * point * 365) / mid_price * 100

        Args:
            swap_long: MT5 swap_long value for one standard lot
                (daily points credited/charged for a long position).
            swap_short: MT5 swap_short value for one standard lot.
            point: Instrument point size (e.g. 0.00001 for EURUSD 5-digit).
            mid_price: Current mid-price used to normalise the carry.

        Returns:
            CarryResult with annualized long/short/net carry percentages.
            All fields are 0.0 when mid_price is zero.
        """
        if mid_price == 0.0:
            return CarryResult(carry_long=0.0, carry_short=0.0, net_carry=0.0)
        carry_long = (swap_long * point * 365) / mid_price * 100
        carry_short = (swap_short * point * 365) / mid_price * 100
        return CarryResult(
            carry_long=carry_long,
            carry_short=carry_short,
            net_carry=carry_long + carry_short,
        )
