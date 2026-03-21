"""Tests for SpreadModel — variable spread tracking and cost-adjusted signal suppression."""

from __future__ import annotations

import numpy as np
import pytest

from src.execution.spread_model import SpreadModel


class TestSpreadModelProperties:
    """Tests for statistical properties of spread history."""

    def test_median_known_data(self) -> None:
        """Median of [1.0, 2.0, 3.0] is 2.0."""
        model = SpreadModel()
        for v in [1.0, 2.0, 3.0]:
            model.update(v)
        assert model.median == pytest.approx(2.0)

    def test_p95_known_data(self) -> None:
        """p95 of 100 values from 0 to 99 is near 94.05."""
        model = SpreadModel()
        for v in range(100):
            model.update(float(v))
        assert model.p95 == pytest.approx(np.percentile(list(range(100)), 95))

    def test_volatility_matches_numpy_std(self) -> None:
        """Volatility must match np.std of the same values."""
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        model = SpreadModel()
        for v in data:
            model.update(v)
        assert model.volatility == pytest.approx(float(np.std(data)))

    def test_empty_history_median_returns_zero(self) -> None:
        """Empty history: median returns 0.0."""
        assert SpreadModel().median == 0.0

    def test_empty_history_p95_returns_zero(self) -> None:
        """Empty history: p95 returns 0.0."""
        assert SpreadModel().p95 == 0.0

    def test_empty_history_volatility_returns_zero(self) -> None:
        """Empty history: volatility returns 0.0."""
        assert SpreadModel().volatility == 0.0


class TestCostAdjustedSignal:
    """Tests for cost_adjusted_signal."""

    def test_suppression_when_cost_ratio_exceeds_50_percent(self) -> None:
        """Returns 0.0 when spread eats >50% of expected profit."""
        model = SpreadModel()
        # median spread = 5.0
        for _ in range(10):
            model.update(5.0)
        # expected_move = |1.0| * 10.0 * 1 = 10.0
        # cost_ratio = (2 * 5.0) / 10.0 = 1.0  >0.5 -> suppress
        result = model.cost_adjusted_signal(
            raw_signal=1.0,
            expected_holding_bars=1,
            avg_bar_range=10.0,
        )
        assert result == 0.0

    def test_attenuation_when_cost_ratio_is_0_25(self) -> None:
        """Returns raw_signal * (1 - cost_ratio) when cost_ratio = 0.25."""
        model = SpreadModel()
        # median spread = 1.0
        for _ in range(10):
            model.update(1.0)
        # expected_move = |1.0| * 8.0 * 1 = 8.0
        # cost_ratio = (2 * 1.0) / 8.0 = 0.25  <= 0.5 -> attenuate
        result = model.cost_adjusted_signal(
            raw_signal=1.0,
            expected_holding_bars=1,
            avg_bar_range=8.0,
        )
        assert result == pytest.approx(1.0 * (1.0 - 0.25))

    def test_zero_expected_move_returns_zero(self) -> None:
        """Returns 0.0 when expected_move is zero (raw_signal=0)."""
        model = SpreadModel()
        for _ in range(10):
            model.update(1.0)
        result = model.cost_adjusted_signal(
            raw_signal=0.0,
            expected_holding_bars=5,
            avg_bar_range=10.0,
        )
        assert result == 0.0

    def test_zero_avg_bar_range_returns_zero(self) -> None:
        """Returns 0.0 when avg_bar_range is zero (expected_move=0)."""
        model = SpreadModel()
        for _ in range(10):
            model.update(1.0)
        result = model.cost_adjusted_signal(
            raw_signal=1.0,
            expected_holding_bars=5,
            avg_bar_range=0.0,
        )
        assert result == 0.0

    def test_negative_raw_signal_suppressed(self) -> None:
        """Suppression logic works for negative signals."""
        model = SpreadModel()
        # median spread = 5.0; expected_move = |-1| * 10 * 1 = 10; ratio = 1.0 > 0.5
        for _ in range(10):
            model.update(5.0)
        result = model.cost_adjusted_signal(
            raw_signal=-1.0,
            expected_holding_bars=1,
            avg_bar_range=10.0,
        )
        assert result == 0.0

    def test_negative_raw_signal_attenuated(self) -> None:
        """Attenuation preserves sign for negative signals."""
        model = SpreadModel()
        # median spread = 1.0; expected_move = 1 * 8 * 1 = 8; ratio = 0.25
        for _ in range(10):
            model.update(1.0)
        result = model.cost_adjusted_signal(
            raw_signal=-1.0,
            expected_holding_bars=1,
            avg_bar_range=8.0,
        )
        assert result == pytest.approx(-1.0 * (1.0 - 0.25))


class TestMaxHistoryEviction:
    """Tests for rolling window eviction."""

    def test_max_history_evicts_oldest_entries(self) -> None:
        """Adding 10001 items to a 10000-item window keeps exactly 10000."""
        model = SpreadModel(max_history=10_000)
        for i in range(10_001):
            model.update(float(i))
        # Internal deque should hold exactly 10000 items
        assert len(model._history) == 10_000

    def test_custom_max_history(self) -> None:
        """Custom max_history limits window size."""
        model = SpreadModel(max_history=5)
        for i in range(10):
            model.update(float(i))
        assert len(model._history) == 5
