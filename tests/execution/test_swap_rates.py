"""Tests for SwapRateCalculator — annualized carry from broker swap rates."""

from __future__ import annotations

import pytest

from src.execution.swap_rates import CarryResult, SwapRateCalculator


class TestSwapRateCalculatorKnownValues:
    """Verify annualized carry formula with known inputs."""

    def test_eurusd_known_swaps(self) -> None:
        """EURUSD with known swap values produces correct annualized carry.

        Hand calculation:
          swap_long = -6.5, point = 0.00001, mid_price = 1.1000
          carry_long = (-6.5 * 0.00001 * 365) / 1.1000 * 100
                     = -0.023725 / 1.1 * 100
                     = -0.02156... * 100
                     ≈ -2.1568...
          swap_short = 1.2, same formula:
          carry_short = (1.2 * 0.00001 * 365) / 1.1 * 100 ≈ 0.3981...
        """
        result = SwapRateCalculator.compute_annualized_carry(
            swap_long=-6.5,
            swap_short=1.2,
            point=0.00001,
            mid_price=1.1000,
        )
        expected_carry_long = (-6.5 * 0.00001 * 365) / 1.1000 * 100
        expected_carry_short = (1.2 * 0.00001 * 365) / 1.1000 * 100
        assert result.carry_long == pytest.approx(expected_carry_long)
        assert result.carry_short == pytest.approx(expected_carry_short)
        assert result.net_carry == pytest.approx(expected_carry_long + expected_carry_short)

    def test_zero_mid_price_returns_all_zeros(self) -> None:
        """Zero mid_price returns a CarryResult with all fields 0.0."""
        result = SwapRateCalculator.compute_annualized_carry(
            swap_long=-6.5,
            swap_short=1.2,
            point=0.00001,
            mid_price=0.0,
        )
        assert result.carry_long == 0.0
        assert result.carry_short == 0.0
        assert result.net_carry == 0.0

    def test_positive_and_negative_swaps_produce_correct_signs(self) -> None:
        """Positive swap_long yields positive carry_long; negative yields negative."""
        result_pos = SwapRateCalculator.compute_annualized_carry(
            swap_long=5.0,
            swap_short=-3.0,
            point=0.0001,
            mid_price=1.25,
        )
        assert result_pos.carry_long > 0.0
        assert result_pos.carry_short < 0.0

    def test_net_carry_is_sum_of_long_and_short(self) -> None:
        """net_carry = carry_long + carry_short always."""
        result = SwapRateCalculator.compute_annualized_carry(
            swap_long=3.0,
            swap_short=-2.0,
            point=0.0001,
            mid_price=1.5,
        )
        assert result.net_carry == pytest.approx(result.carry_long + result.carry_short)

    def test_carry_result_is_frozen_dataclass(self) -> None:
        """CarryResult must be immutable."""
        result = SwapRateCalculator.compute_annualized_carry(
            swap_long=1.0, swap_short=-1.0, point=0.0001, mid_price=1.0
        )
        assert isinstance(result, CarryResult)
        with pytest.raises((AttributeError, TypeError)):
            result.carry_long = 999.0  # type: ignore[misc]

    def test_annualization_uses_365_days(self) -> None:
        """Formula must include 365 as annualization factor."""
        result1 = SwapRateCalculator.compute_annualized_carry(
            swap_long=1.0, swap_short=0.0, point=1.0, mid_price=1.0
        )
        # carry_long = 1.0 * 1.0 * 365 / 1.0 * 100 = 36500
        assert result1.carry_long == pytest.approx(36500.0)
