"""Contract tests for src/execution/abstract.py — enums, dataclasses, and ABCs."""
from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestSideEnum:
    def test_buy_value(self) -> None:
        from src.execution.abstract import Side

        assert Side.BUY.value == 1

    def test_sell_value(self) -> None:
        from src.execution.abstract import Side

        assert Side.SELL.value == -1

    def test_only_two_members(self) -> None:
        from src.execution.abstract import Side

        assert len(Side) == 2


class TestOrderTypeEnum:
    def test_market_value(self) -> None:
        from src.execution.abstract import OrderType

        assert OrderType.MARKET.value == "market"

    def test_limit_value(self) -> None:
        from src.execution.abstract import OrderType

        assert OrderType.LIMIT.value == "limit"

    def test_stop_value(self) -> None:
        from src.execution.abstract import OrderType

        assert OrderType.STOP.value == "stop"

    def test_only_three_members(self) -> None:
        from src.execution.abstract import OrderType

        assert len(OrderType) == 3


# ---------------------------------------------------------------------------
# Dataclass tests
# ---------------------------------------------------------------------------


class TestTickDataclass:
    def _make_tick(self) -> Any:
        from src.execution.abstract import Tick

        return Tick(
            timestamp=np.datetime64("2024-01-01T00:00:00", "ns"),
            symbol="EURUSD",
            bid=1.1000,
            ask=1.1002,
            bid_volume=10.0,
            ask_volume=10.0,
            source="mt5",
        )

    def test_fields_accessible(self) -> None:
        tick = self._make_tick()
        assert tick.symbol == "EURUSD"
        assert tick.bid == pytest.approx(1.1000)
        assert tick.ask == pytest.approx(1.1002)

    def test_timestamp_type(self) -> None:
        tick = self._make_tick()
        assert isinstance(tick.timestamp, np.datetime64)

    def test_frozen_immutable(self) -> None:
        from dataclasses import FrozenInstanceError

        tick = self._make_tick()
        with pytest.raises(FrozenInstanceError):
            tick.bid = 1.2  # type: ignore[misc]

    def test_default_volumes(self) -> None:
        from src.execution.abstract import Tick

        tick = Tick(
            timestamp=np.datetime64("2024-01-01", "D"),
            symbol="EURUSD",
            bid=1.1,
            ask=1.1002,
        )
        assert tick.bid_volume == 0.0
        assert tick.ask_volume == 0.0
        assert tick.source == ""

    def test_no_broker_references_in_module(self) -> None:
        import src.execution.abstract as mod

        src_text = inspect.getsource(mod)
        for term in ("mt5", "cme", "forex", "futures", "metatrader"):
            assert term not in src_text.lower(), (
                f"Broker-specific term '{term}' found in abstract.py"
            )


class TestBarDataclass:
    def _make_bar(self) -> Any:
        from src.execution.abstract import Bar

        return Bar(
            timestamp=np.datetime64("2024-01-01T01:00:00", "ns"),
            symbol="GBPUSD",
            open=1.2700,
            high=1.2720,
            low=1.2690,
            close=1.2710,
            volume=500.0,
            spread=0.0002,
        )

    def test_fields_accessible(self) -> None:
        bar = self._make_bar()
        assert bar.symbol == "GBPUSD"
        assert bar.open == pytest.approx(1.2700)
        assert bar.close == pytest.approx(1.2710)

    def test_frozen_immutable(self) -> None:
        from dataclasses import FrozenInstanceError

        bar = self._make_bar()
        with pytest.raises(FrozenInstanceError):
            bar.close = 1.3  # type: ignore[misc]

    def test_default_volume_and_spread(self) -> None:
        from src.execution.abstract import Bar

        bar = Bar(
            timestamp=np.datetime64("2024-01-01", "D"),
            symbol="EURUSD",
            open=1.1,
            high=1.11,
            low=1.09,
            close=1.105,
        )
        assert bar.volume == 0.0
        assert bar.spread == 0.0


class TestOrderRequestDataclass:
    def _make_order(self) -> Any:
        from src.execution.abstract import OrderRequest, OrderType, Side

        return OrderRequest(
            symbol="EURUSD",
            side=Side.BUY,
            quantity=0.1,
            order_type=OrderType.MARKET,
            price=None,
            sl=1.0900,
            tp=1.1200,
            comment="test",
        )

    def test_fields_accessible(self) -> None:
        req = self._make_order()
        from src.execution.abstract import Side

        assert req.symbol == "EURUSD"
        assert req.side == Side.BUY
        assert req.quantity == pytest.approx(0.1)

    def test_frozen_immutable(self) -> None:
        from dataclasses import FrozenInstanceError

        req = self._make_order()
        with pytest.raises(FrozenInstanceError):
            req.quantity = 1.0  # type: ignore[misc]

    def test_defaults(self) -> None:
        from src.execution.abstract import OrderRequest, OrderType, Side

        req = OrderRequest(symbol="EURUSD", side=Side.SELL, quantity=0.2)
        assert req.order_type == OrderType.MARKET
        assert req.price is None
        assert req.sl is None
        assert req.tp is None
        assert req.comment == ""


class TestOrderResultDataclass:
    def _make_result(self) -> Any:
        from src.execution.abstract import OrderResult

        return OrderResult(
            order_id="ORD-001",
            fill_price=1.1001,
            fill_quantity=0.1,
            slippage=0.0001,
            commission=0.0007,
            success=True,
        )

    def test_fields_accessible(self) -> None:
        res = self._make_result()
        assert res.order_id == "ORD-001"
        assert res.success is True

    def test_frozen_immutable(self) -> None:
        from dataclasses import FrozenInstanceError

        res = self._make_result()
        with pytest.raises(FrozenInstanceError):
            res.success = False  # type: ignore[misc]

    def test_default_error_message(self) -> None:
        res = self._make_result()
        assert res.error_message == ""


class TestPositionDataclass:
    def _make_position(self) -> Any:
        from src.execution.abstract import Position, Side

        return Position(
            symbol="USDJPY",
            side=Side.BUY,
            quantity=1.0,
            entry_price=150.00,
            current_price=150.50,
            unrealized_pnl=500.0,
            swap_accumulated=-5.0,
            margin_used=1500.0,
        )

    def test_fields_accessible(self) -> None:
        pos = self._make_position()
        assert pos.symbol == "USDJPY"
        assert pos.unrealized_pnl == pytest.approx(500.0)

    def test_mutable(self) -> None:
        """Position is NOT frozen — current_price updates during live trading."""
        pos = self._make_position()
        pos.current_price = 151.00
        assert pos.current_price == pytest.approx(151.00)

    def test_defaults(self) -> None:
        from src.execution.abstract import Position, Side

        pos = Position(
            symbol="EURUSD",
            side=Side.SELL,
            quantity=0.1,
            entry_price=1.1,
            current_price=1.09,
            unrealized_pnl=100.0,
        )
        assert pos.swap_accumulated == 0.0
        assert pos.margin_used == 0.0


# ---------------------------------------------------------------------------
# ABC contract tests (Task 2)
# ---------------------------------------------------------------------------


class TestMarketDataProviderABC:
    def test_incomplete_impl_raises_type_error(self) -> None:
        from src.execution.abstract import MarketDataProvider

        class BadProvider(MarketDataProvider):
            pass  # missing all abstract methods

        with pytest.raises(TypeError):
            BadProvider()  # type: ignore[abstract]

    def test_partial_impl_raises_type_error(self) -> None:
        from src.execution.abstract import Bar, MarketDataProvider, Tick

        class PartialProvider(MarketDataProvider):
            async def get_ticks(
                self, symbol: str, start: np.datetime64, end: np.datetime64
            ) -> list[Tick]:
                return []

            # missing get_bars, subscribe_ticks, get_symbols

        with pytest.raises(TypeError):
            PartialProvider()  # type: ignore[abstract]

    def test_complete_impl_can_instantiate(self) -> None:
        from src.execution.abstract import Bar, MarketDataProvider, Tick

        class GoodProvider(MarketDataProvider):
            async def get_ticks(
                self, symbol: str, start: np.datetime64, end: np.datetime64
            ) -> list[Tick]:
                return []

            async def get_bars(
                self, symbol: str, timeframe: str, count: int
            ) -> list[Bar]:
                return []

            async def subscribe_ticks(
                self, symbol: str, callback: Callable[[Tick], None]
            ) -> None:
                pass

            async def get_symbols(self) -> list[str]:
                return []

        provider = GoodProvider()
        assert provider is not None

    def test_get_ticks_signature(self) -> None:
        from src.execution.abstract import MarketDataProvider

        sig = inspect.signature(MarketDataProvider.get_ticks)
        params = list(sig.parameters.keys())
        assert "symbol" in params
        assert "start" in params
        assert "end" in params


class TestOrderExecutorABC:
    def test_incomplete_impl_raises_type_error(self) -> None:
        from src.execution.abstract import OrderExecutor

        class BadExecutor(OrderExecutor):
            pass

        with pytest.raises(TypeError):
            BadExecutor()  # type: ignore[abstract]

    def test_partial_impl_raises_type_error(self) -> None:
        from src.execution.abstract import OrderExecutor, OrderRequest, OrderResult

        class PartialExecutor(OrderExecutor):
            async def submit_order(self, order: OrderRequest) -> OrderResult:
                raise NotImplementedError

            # missing cancel_order, get_open_orders

        with pytest.raises(TypeError):
            PartialExecutor()  # type: ignore[abstract]

    def test_complete_impl_can_instantiate(self) -> None:
        from src.execution.abstract import OrderExecutor, OrderRequest, OrderResult

        class GoodExecutor(OrderExecutor):
            async def submit_order(self, order: OrderRequest) -> OrderResult:
                raise NotImplementedError

            async def cancel_order(self, order_id: str) -> bool:
                return False

            async def get_open_orders(self) -> list[OrderRequest]:
                return []

        executor = GoodExecutor()
        assert executor is not None

    def test_submit_order_signature(self) -> None:
        from src.execution.abstract import OrderExecutor

        sig = inspect.signature(OrderExecutor.submit_order)
        params = list(sig.parameters.keys())
        assert "order" in params


class TestPositionManagerABC:
    def test_incomplete_impl_raises_type_error(self) -> None:
        from src.execution.abstract import PositionManager

        class BadManager(PositionManager):
            pass

        with pytest.raises(TypeError):
            BadManager()  # type: ignore[abstract]

    def test_partial_impl_raises_type_error(self) -> None:
        from src.execution.abstract import OrderResult, Position, PositionManager

        class PartialManager(PositionManager):
            async def get_positions(self) -> list[Position]:
                return []

            # missing close_position, get_account_equity, get_margin_level

        with pytest.raises(TypeError):
            PartialManager()  # type: ignore[abstract]

    def test_complete_impl_can_instantiate(self) -> None:
        from src.execution.abstract import OrderResult, Position, PositionManager

        class GoodManager(PositionManager):
            async def get_positions(self) -> list[Position]:
                return []

            async def close_position(self, symbol: str) -> OrderResult:
                raise NotImplementedError

            async def get_account_equity(self) -> float:
                return 0.0

            async def get_margin_level(self) -> float:
                return 0.0

        manager = GoodManager()
        assert manager is not None

    def test_get_account_equity_signature(self) -> None:
        from src.execution.abstract import PositionManager

        sig = inspect.signature(PositionManager.get_account_equity)
        # only 'self' — no additional parameters
        params = [p for p in sig.parameters.keys() if p != "self"]
        assert params == []


class TestFullImplementation:
    """A class that implements all three ABCs can be instantiated."""

    def test_combined_adapter_instantiates(self) -> None:
        from src.execution.abstract import (
            Bar,
            MarketDataProvider,
            OrderExecutor,
            OrderRequest,
            OrderResult,
            Position,
            PositionManager,
            Tick,
        )

        class MinimalAdapter(
            MarketDataProvider, OrderExecutor, PositionManager
        ):
            async def get_ticks(
                self, symbol: str, start: np.datetime64, end: np.datetime64
            ) -> list[Tick]:
                return []

            async def get_bars(
                self, symbol: str, timeframe: str, count: int
            ) -> list[Bar]:
                return []

            async def subscribe_ticks(
                self, symbol: str, callback: Callable[[Tick], None]
            ) -> None:
                pass

            async def get_symbols(self) -> list[str]:
                return []

            async def submit_order(self, order: OrderRequest) -> OrderResult:
                raise NotImplementedError

            async def cancel_order(self, order_id: str) -> bool:
                return False

            async def get_open_orders(self) -> list[OrderRequest]:
                return []

            async def get_positions(self) -> list[Position]:
                return []

            async def close_position(self, symbol: str) -> OrderResult:
                raise NotImplementedError

            async def get_account_equity(self) -> float:
                return 100000.0

            async def get_margin_level(self) -> float:
                return 100.0

        adapter = MinimalAdapter()
        assert isinstance(adapter, MarketDataProvider)
        assert isinstance(adapter, OrderExecutor)
        assert isinstance(adapter, PositionManager)


class TestAbstractMethodCount:
    def test_eleven_abstract_methods_total(self) -> None:
        """Verify 4 + 3 + 4 = 11 abstract methods across the three ABCs."""
        import src.execution.abstract as mod

        src_text = inspect.getsource(mod)
        count = src_text.count("@abstractmethod")
        assert count == 11, f"Expected 11 @abstractmethod decorators, found {count}"
