"""Kelly fraction to MT5 lot conversion with broker volume constraints.

LotSizer translates the Kelly criterion output (a fraction of equity to risk)
into a concrete MT5 lot size that respects the broker's volume_min, volume_max,
and volume_step constraints.  Lots are always rounded DOWN to the nearest step
to avoid over-sizing positions.

Design reference: D-29
"""

from __future__ import annotations

import math


class LotSizer:
    """Converts Kelly risk fractions to valid MT5 lot sizes.

    All methods are static — LotSizer carries no state; it is a collection of
    pure calculation utilities used by alpha engines and the risk module.
    """

    @staticmethod
    def kelly_to_lots(
        equity: float,
        kelly_fraction: float,
        stop_loss_pips: float,
        pip_value: float,
        volume_min: float = 0.01,
        volume_max: float = 100.0,
        volume_step: float = 0.01,
    ) -> float:
        """Convert a Kelly risk fraction to MT5-compatible lot size.

        Formula:
            risk_amount = equity * kelly_fraction
            raw_lots    = risk_amount / (stop_loss_pips * pip_value)
            stepped     = floor(raw_lots / volume_step) * volume_step
            lots        = clamp(stepped, volume_min, volume_max)

        If the stepped value is below volume_min but the Kelly fraction is
        positive, the function still returns volume_min (minimum tradeable
        size rather than skipping the trade entirely).

        Args:
            equity: Current account equity in account currency.
            kelly_fraction: Fraction of equity to risk (0 < f <= 1).
                Returns 0.0 when <= 0.
            stop_loss_pips: Distance to stop loss in pips.
                Returns 0.0 when <= 0.
            pip_value: Value of one pip per lot in account currency.
                Returns 0.0 when <= 0.
            volume_min: Broker minimum lot size (default 0.01).
            volume_max: Broker maximum lot size (default 100.0).
            volume_step: Broker lot increment (default 0.01).

        Returns:
            Lot size rounded down to volume_step and clamped to
            [volume_min, volume_max], or 0.0 for invalid inputs.
        """
        if kelly_fraction <= 0 or stop_loss_pips <= 0 or pip_value <= 0:
            return 0.0
        risk_amount = equity * kelly_fraction
        raw_lots = risk_amount / (stop_loss_pips * pip_value)
        # Round DOWN to nearest volume_step (never over-size)
        stepped = math.floor(raw_lots / volume_step) * volume_step
        # Clamp to broker limits
        stepped = max(volume_min, min(volume_max, stepped))
        return round(stepped, 8)  # suppress floating-point noise

    @staticmethod
    def compute_pip_value(
        contract_size: float,
        pip_size: float,
        exchange_rate: float = 1.0,
    ) -> float:
        """Compute the pip value per lot in account currency.

        For accounts denominated in USD trading a USD-quoted instrument
        (e.g. EURUSD), ``exchange_rate`` is 1.0.  For instruments where the
        profit currency differs from the account currency (e.g. a USD account
        trading GBPJPY whose profit currency is JPY), pass the USDJPY rate to
        convert JPY profit to USD.

        Formula:
            pip_value = (contract_size * pip_size) / exchange_rate

        Args:
            contract_size: Standard lot size in base-currency units
                (e.g. 100,000 for Forex majors).
            pip_size: Minimum price increment (e.g. 0.0001 for 4-digit EURUSD,
                0.01 for USDJPY).
            exchange_rate: Rate to convert profit currency to account currency.
                Default is 1.0 (no conversion needed).

        Returns:
            Pip value per lot in account currency, or 0.0 if exchange_rate
            is zero.
        """
        if exchange_rate == 0.0:
            return 0.0
        return (contract_size * pip_size) / exchange_rate
