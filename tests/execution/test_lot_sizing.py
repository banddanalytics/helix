"""Tests for LotSizer — Kelly fraction to MT5 lot conversion."""

from __future__ import annotations

import pytest

from src.execution.lot_sizing import LotSizer


class TestLotSizerKellyToLots:
    """Verify Kelly-to-lots conversion logic."""

    def test_basic_calculation(self) -> None:
        """100K equity, 2% kelly, 50 pip SL, pip_value=10 -> 4.0 lots.

        lots = (100000 * 0.02) / (50 * 10) = 2000 / 500 = 4.0
        """
        result = LotSizer.kelly_to_lots(
            equity=100_000.0,
            kelly_fraction=0.02,
            stop_loss_pips=50.0,
            pip_value=10.0,
        )
        assert result == pytest.approx(4.0)

    def test_volume_step_floor_rounding(self) -> None:
        """Raw 0.137 with step 0.01 rounds DOWN to 0.13."""
        # Need to produce raw = 0.137
        # lots = equity * kelly / (sl * pv) = 0.137
        # Choose: equity=1370, kelly=1, sl=1, pv=10000/1370 to get 0.137
        # Simpler: equity=1370, kelly=0.001, sl=1, pv=10 -> 1370*0.001/10 = 0.137
        result = LotSizer.kelly_to_lots(
            equity=1370.0,
            kelly_fraction=0.001,
            stop_loss_pips=1.0,
            pip_value=10.0,
            volume_min=0.01,
            volume_max=100.0,
            volume_step=0.01,
        )
        assert result == pytest.approx(0.13)

    def test_volume_min_clamping(self) -> None:
        """Calculated lots below volume_min returns volume_min."""
        # Produce raw lots = 0.005 < 0.01
        # equity=0.5, kelly=0.001, sl=1, pv=100 -> 0.5*0.001/100 = 0.000005
        # Or simpler: produce something very small
        result = LotSizer.kelly_to_lots(
            equity=1.0,
            kelly_fraction=0.001,
            stop_loss_pips=100.0,
            pip_value=10.0,
            volume_min=0.01,
            volume_max=100.0,
            volume_step=0.01,
        )
        # raw = 1 * 0.001 / (100 * 10) = 0.000001 < volume_min
        assert result == pytest.approx(0.01)

    def test_volume_max_clamping(self) -> None:
        """Calculated lots above volume_max is clamped to volume_max."""
        result = LotSizer.kelly_to_lots(
            equity=1_000_000.0,
            kelly_fraction=0.5,
            stop_loss_pips=1.0,
            pip_value=1.0,
            volume_min=0.01,
            volume_max=100.0,
            volume_step=0.01,
        )
        # raw = 1M * 0.5 / (1 * 1) = 500000 > 100 -> clamp
        assert result == pytest.approx(100.0)

    def test_zero_kelly_fraction_returns_zero(self) -> None:
        """Zero kelly_fraction returns 0.0."""
        result = LotSizer.kelly_to_lots(
            equity=100_000.0,
            kelly_fraction=0.0,
            stop_loss_pips=50.0,
            pip_value=10.0,
        )
        assert result == 0.0

    def test_negative_kelly_fraction_returns_zero(self) -> None:
        """Negative kelly_fraction returns 0.0."""
        result = LotSizer.kelly_to_lots(
            equity=100_000.0,
            kelly_fraction=-0.02,
            stop_loss_pips=50.0,
            pip_value=10.0,
        )
        assert result == 0.0

    def test_zero_stop_loss_pips_returns_zero(self) -> None:
        """Zero stop_loss_pips returns 0.0 (avoids division by zero)."""
        result = LotSizer.kelly_to_lots(
            equity=100_000.0,
            kelly_fraction=0.02,
            stop_loss_pips=0.0,
            pip_value=10.0,
        )
        assert result == 0.0

    def test_zero_pip_value_returns_zero(self) -> None:
        """Zero pip_value returns 0.0 (avoids division by zero)."""
        result = LotSizer.kelly_to_lots(
            equity=100_000.0,
            kelly_fraction=0.02,
            stop_loss_pips=50.0,
            pip_value=0.0,
        )
        assert result == 0.0


class TestComputePipValue:
    """Verify pip value calculation with optional currency conversion."""

    def test_eurusd_standard(self) -> None:
        """EURUSD: 100000 * 0.0001 / 1.0 = 10.0 USD per pip."""
        result = LotSizer.compute_pip_value(
            contract_size=100_000.0,
            pip_size=0.0001,
            exchange_rate=1.0,
        )
        assert result == pytest.approx(10.0)

    def test_usdjpy_conversion(self) -> None:
        """USDJPY: 100000 * 0.01 / 150.0 = 6.667 USD per pip."""
        result = LotSizer.compute_pip_value(
            contract_size=100_000.0,
            pip_size=0.01,
            exchange_rate=150.0,
        )
        assert result == pytest.approx(100_000.0 * 0.01 / 150.0)

    def test_zero_exchange_rate_returns_zero(self) -> None:
        """Zero exchange_rate returns 0.0 (avoids division by zero)."""
        result = LotSizer.compute_pip_value(
            contract_size=100_000.0,
            pip_size=0.0001,
            exchange_rate=0.0,
        )
        assert result == 0.0

    def test_default_exchange_rate_is_one(self) -> None:
        """Default exchange_rate=1.0 matches explicit 1.0."""
        r1 = LotSizer.compute_pip_value(100_000.0, 0.0001)
        r2 = LotSizer.compute_pip_value(100_000.0, 0.0001, exchange_rate=1.0)
        assert r1 == pytest.approx(r2)
