"""Tests for SimAdapter — stateful simulation adapter for backtesting and CI testing."""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def adapter() -> Any:
    """Return a fresh SimAdapter with well-known prices set."""
    from src.execution.sim_adapter import SimAdapter

    sim = SimAdapter(initial_equity=100_000.0, spread_pips=1.5, seed=42)
    sim.set_price("EURUSD", 1.1000)
    sim.set_price("GBPUSD", 1.2500)
    return sim


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------


class TestSimAdapterInstantiation:
    def test_instantiates_with_defaults(self) -> None:
        from src.execution.sim_adapter import SimAdapter

        sim = SimAdapter()
        assert sim is not None

    def test_initial_equity_stored(self) -> None:
        from src.execution.sim_adapter import SimAdapter

        sim = SimAdapter(initial_equity=50_000.0)
        result = asyncio.run(sim.get_account_equity())
        assert result == pytest.approx(50_000.0)

    def test_implements_all_three_abcs(self, adapter: Any) -> None:
        from src.execution.abstract import MarketDataProvider, OrderExecutor, PositionManager

        assert isinstance(adapter, MarketDataProvider)
        assert isinstance(adapter, OrderExecutor)
        assert isinstance(adapter, PositionManager)

    def test_set_price_method_exists(self, adapter: Any) -> None:
        adapter.set_price("USDJPY", 150.0)  # should not raise


# ---------------------------------------------------------------------------
# submit_order: basic fill behavior
# ---------------------------------------------------------------------------


class TestSubmitOrderFill:
    def test_buy_order_fills_at_ask(self, adapter: Any) -> None:
        """BUY fills at mid + half_spread."""
        from src.execution.abstract import OrderRequest, Side

        order = OrderRequest(symbol="EURUSD", side=Side.BUY, quantity=0.1)
        result = asyncio.run(adapter.submit_order(order))
        assert result.success is True
        # ask = mid + half_spread
        half_spread = 1.5 * 0.0001 / 2
        assert result.fill_price == pytest.approx(1.1000 + half_spread, abs=1e-6)

    def test_sell_order_fills_at_bid(self, adapter: Any) -> None:
        """SELL fills at mid - half_spread."""
        from src.execution.abstract import OrderRequest, Side

        order = OrderRequest(symbol="EURUSD", side=Side.SELL, quantity=0.1)
        result = asyncio.run(adapter.submit_order(order))
        assert result.success is True
        half_spread = 1.5 * 0.0001 / 2
        assert result.fill_price == pytest.approx(1.1000 - half_spread, abs=1e-6)

    def test_order_result_has_order_id(self, adapter: Any) -> None:
        from src.execution.abstract import OrderRequest, Side

        order = OrderRequest(symbol="EURUSD", side=Side.BUY, quantity=0.1)
        result = asyncio.run(adapter.submit_order(order))
        assert result.order_id != ""

    def test_order_fills_immediately(self, adapter: Any) -> None:
        from src.execution.abstract import OrderRequest, Side

        order = OrderRequest(symbol="EURUSD", side=Side.BUY, quantity=0.1)
        result = asyncio.run(adapter.submit_order(order))
        assert result.fill_quantity == pytest.approx(0.1)


# ---------------------------------------------------------------------------
# submit_order: rejection logic
# ---------------------------------------------------------------------------


class TestSubmitOrderRejection:
    def test_invalid_lot_size_rejected(self, adapter: Any) -> None:
        from src.execution.abstract import OrderRequest, Side

        order = OrderRequest(symbol="EURUSD", side=Side.BUY, quantity=0.0)
        result = asyncio.run(adapter.submit_order(order))
        assert result.success is False
        assert "lot" in result.error_message.lower() or "quantity" in result.error_message.lower()

    def test_negative_quantity_rejected(self, adapter: Any) -> None:
        from src.execution.abstract import OrderRequest, Side

        order = OrderRequest(symbol="EURUSD", side=Side.BUY, quantity=-1.0)
        result = asyncio.run(adapter.submit_order(order))
        assert result.success is False

    def test_insufficient_margin_rejected(self) -> None:
        """A very large position should be rejected when margin is insufficient."""
        from src.execution.abstract import OrderRequest, Side
        from src.execution.sim_adapter import SimAdapter

        # tiny equity, huge position
        sim = SimAdapter(initial_equity=100.0, spread_pips=1.5, seed=42)
        sim.set_price("EURUSD", 1.1000)
        order = OrderRequest(symbol="EURUSD", side=Side.BUY, quantity=1000.0)
        result = asyncio.run(sim.submit_order(order))
        assert result.success is False
        assert "margin" in result.error_message.lower()

    def test_unknown_symbol_returns_failure(self, adapter: Any) -> None:
        from src.execution.abstract import OrderRequest, Side

        order = OrderRequest(symbol="ZZZZZZ", side=Side.BUY, quantity=0.1)
        result = asyncio.run(adapter.submit_order(order))
        assert result.success is False


# ---------------------------------------------------------------------------
# Position tracking
# ---------------------------------------------------------------------------


class TestPositionTracking:
    def test_position_appears_after_buy(self, adapter: Any) -> None:
        from src.execution.abstract import OrderRequest, Side

        order = OrderRequest(symbol="EURUSD", side=Side.BUY, quantity=0.1)
        asyncio.run(adapter.submit_order(order))

        positions = asyncio.run(adapter.get_positions())
        assert len(positions) == 1
        assert positions[0].symbol == "EURUSD"

    def test_position_side_correct(self, adapter: Any) -> None:
        from src.execution.abstract import OrderRequest, Side

        order = OrderRequest(symbol="EURUSD", side=Side.BUY, quantity=0.1)
        asyncio.run(adapter.submit_order(order))

        positions = asyncio.run(adapter.get_positions())
        assert positions[0].side == Side.BUY

    def test_multiple_symbols_tracked(self, adapter: Any) -> None:
        from src.execution.abstract import OrderRequest, Side

        asyncio.run(adapter.submit_order(OrderRequest(symbol="EURUSD", side=Side.BUY, quantity=0.1)))
        asyncio.run(adapter.submit_order(OrderRequest(symbol="GBPUSD", side=Side.SELL, quantity=0.2)))

        positions = asyncio.run(adapter.get_positions())
        symbols = {p.symbol for p in positions}
        assert "EURUSD" in symbols
        assert "GBPUSD" in symbols

    def test_no_positions_initially(self, adapter: Any) -> None:
        positions = asyncio.run(adapter.get_positions())
        assert positions == []


# ---------------------------------------------------------------------------
# close_position and round-trip PnL
# ---------------------------------------------------------------------------


class TestClosePositionAndPnL:
    def test_close_removes_position(self, adapter: Any) -> None:
        from src.execution.abstract import OrderRequest, Side

        asyncio.run(adapter.submit_order(OrderRequest(symbol="EURUSD", side=Side.BUY, quantity=0.1)))
        asyncio.run(adapter.close_position("EURUSD"))

        positions = asyncio.run(adapter.get_positions())
        assert len(positions) == 0

    def test_close_nonexistent_returns_failure(self, adapter: Any) -> None:
        result = asyncio.run(adapter.close_position("ZZZZZZ"))
        assert result.success is False

    def test_round_trip_pnl_buy_then_sell(self) -> None:
        """Buy at ask, sell at bid → PnL = (bid_exit - ask_entry) * qty * contract_size."""
        from src.execution.abstract import OrderRequest, Side
        from src.execution.sim_adapter import SimAdapter

        sim = SimAdapter(initial_equity=100_000.0, spread_pips=2.0, seed=42)
        sim.set_price("EURUSD", 1.1000)

        # Open BUY
        buy_result = asyncio.run(
            sim.submit_order(OrderRequest(symbol="EURUSD", side=Side.BUY, quantity=0.1))
        )
        entry_ask = buy_result.fill_price

        # Price moves up
        sim.set_price("EURUSD", 1.1020)

        # Close SELL
        close_result = asyncio.run(sim.close_position("EURUSD"))
        exit_bid = close_result.fill_price

        # Equity should reflect realized PnL
        equity = asyncio.run(sim.get_account_equity())

        # Expected: initial + (exit_bid - entry_ask) * qty * 100_000
        contract_size = 100_000.0
        expected_pnl = (exit_bid - entry_ask) * 0.1 * contract_size
        assert equity == pytest.approx(100_000.0 + expected_pnl, rel=1e-4)

    def test_round_trip_pnl_sell_then_buy(self) -> None:
        """Sell at bid, buy to close at ask → PnL = (bid_entry - ask_exit) * qty * cs."""
        from src.execution.abstract import OrderRequest, Side
        from src.execution.sim_adapter import SimAdapter

        sim = SimAdapter(initial_equity=100_000.0, spread_pips=2.0, seed=42)
        sim.set_price("EURUSD", 1.1000)

        sell_result = asyncio.run(
            sim.submit_order(OrderRequest(symbol="EURUSD", side=Side.SELL, quantity=0.1))
        )
        entry_bid = sell_result.fill_price

        sim.set_price("EURUSD", 1.0980)

        close_result = asyncio.run(sim.close_position("EURUSD"))
        exit_ask = close_result.fill_price

        equity = asyncio.run(sim.get_account_equity())
        contract_size = 100_000.0
        expected_pnl = (entry_bid - exit_ask) * 0.1 * contract_size
        assert equity == pytest.approx(100_000.0 + expected_pnl, rel=1e-4)


# ---------------------------------------------------------------------------
# Equity tracking
# ---------------------------------------------------------------------------


class TestEquityTracking:
    def test_initial_equity(self, adapter: Any) -> None:
        equity = asyncio.run(adapter.get_account_equity())
        assert equity == pytest.approx(100_000.0)

    def test_equity_decreases_after_spread_cost(self) -> None:
        from src.execution.abstract import OrderRequest, Side
        from src.execution.sim_adapter import SimAdapter

        sim = SimAdapter(initial_equity=100_000.0, spread_pips=10.0, seed=42)
        sim.set_price("EURUSD", 1.1000)

        # Open and immediately close — spread cost is realized
        asyncio.run(sim.submit_order(OrderRequest(symbol="EURUSD", side=Side.BUY, quantity=1.0)))
        asyncio.run(sim.close_position("EURUSD"))
        equity = asyncio.run(sim.get_account_equity())
        # After a round-trip with spread, equity should be less than initial
        assert equity < 100_000.0

    def test_get_margin_level_returns_float(self, adapter: Any) -> None:
        result = asyncio.run(adapter.get_margin_level())
        assert isinstance(result, float)
        assert result >= 0.0


# ---------------------------------------------------------------------------
# Determinism: same seed produces same order IDs
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_same_seed_produces_same_order_ids(self) -> None:
        from src.execution.abstract import OrderRequest, Side
        from src.execution.sim_adapter import SimAdapter

        def run_once(seed: int) -> list[str]:
            sim = SimAdapter(initial_equity=100_000.0, seed=seed)
            sim.set_price("EURUSD", 1.1000)
            ids: list[str] = []
            for _ in range(3):
                r = asyncio.run(
                    sim.submit_order(OrderRequest(symbol="EURUSD", side=Side.BUY, quantity=0.1))
                )
                ids.append(r.order_id)
            return ids

        ids1 = run_once(42)
        ids2 = run_once(42)
        assert ids1 == ids2

    def test_different_seeds_produce_different_ids(self) -> None:
        from src.execution.abstract import OrderRequest, Side
        from src.execution.sim_adapter import SimAdapter

        def run_once(seed: int) -> str:
            sim = SimAdapter(initial_equity=100_000.0, seed=seed)
            sim.set_price("EURUSD", 1.1000)
            r = asyncio.run(
                sim.submit_order(OrderRequest(symbol="EURUSD", side=Side.BUY, quantity=0.1))
            )
            return r.order_id

        id1 = run_once(42)
        id2 = run_once(99)
        assert id1 != id2


# ---------------------------------------------------------------------------
# cancel_order / get_open_orders (interface compliance)
# ---------------------------------------------------------------------------


class TestCancelAndOpenOrders:
    def test_cancel_order_returns_bool(self, adapter: Any) -> None:
        result = asyncio.run(adapter.cancel_order("nonexistent"))
        assert isinstance(result, bool)

    def test_get_open_orders_returns_list(self, adapter: Any) -> None:
        result = asyncio.run(adapter.get_open_orders())
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Market data methods (synthetic data)
# ---------------------------------------------------------------------------


class TestMarketData:
    def test_get_ticks_returns_list(self, adapter: Any) -> None:
        from src.execution.abstract import Tick

        result = asyncio.run(
            adapter.get_ticks(
                "EURUSD",
                np.datetime64("2024-01-01T00:00:00", "ns"),
                np.datetime64("2024-01-01T01:00:00", "ns"),
            )
        )
        assert isinstance(result, list)

    def test_get_bars_returns_list(self, adapter: Any) -> None:
        from src.execution.abstract import Bar

        result = asyncio.run(adapter.get_bars("EURUSD", "1h", 5))
        assert isinstance(result, list)

    def test_subscribe_ticks_is_coroutine(self, adapter: Any) -> None:
        import inspect

        assert inspect.iscoroutinefunction(adapter.subscribe_ticks)

    def test_get_symbols_returns_list(self, adapter: Any) -> None:
        result = asyncio.run(adapter.get_symbols())
        assert isinstance(result, list)
        assert "EURUSD" in result
        assert "GBPUSD" in result
