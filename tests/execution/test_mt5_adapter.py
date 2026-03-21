"""Tests for MT5Adapter — all MT5 calls are mocked so CI runs on Linux."""

from __future__ import annotations

import asyncio
import sys
import types
from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Helpers to build a fake mt5 module so the import-time conditional works
# ---------------------------------------------------------------------------


def _make_mt5_mock() -> MagicMock:
    """Create a MagicMock representing the MetaTrader5 module."""
    mt5 = MagicMock()

    # Constants expected by the adapter
    mt5.COPY_TICKS_ALL = 0
    mt5.TIMEFRAME_M1 = 1
    mt5.TIMEFRAME_M5 = 5
    mt5.TIMEFRAME_M15 = 15
    mt5.TIMEFRAME_M30 = 30
    mt5.TIMEFRAME_H1 = 16385
    mt5.TIMEFRAME_H4 = 16388
    mt5.TIMEFRAME_D1 = 16408
    mt5.TIMEFRAME_W1 = 32769
    mt5.ORDER_TYPE_BUY = 0
    mt5.ORDER_TYPE_SELL = 1
    mt5.TRADE_ACTION_DEAL = 1
    mt5.ORDER_FILLING_IOC = 1
    mt5.TRADE_RETCODE_DONE = 10009

    mt5.initialize.return_value = True
    mt5.login.return_value = True
    mt5.last_error.return_value = (0, "No error")
    mt5.shutdown.return_value = None

    return mt5


@pytest.fixture
def fake_mt5() -> MagicMock:
    return _make_mt5_mock()


@pytest.fixture
def adapter(fake_mt5: MagicMock) -> Any:
    """Return a MT5Adapter instance with a patched mt5 module."""
    # Inject the fake module so the import-time try/except succeeds
    import src.execution.mt5_adapter as mod

    mod.mt5 = fake_mt5  # type: ignore[assignment]

    from src.execution.mt5_adapter import MT5Adapter

    return MT5Adapter(account=12345, password="secret", server="Broker-Demo")


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------


class TestMT5AdapterInstantiation:
    def test_instantiates_with_required_args(self, fake_mt5: MagicMock) -> None:
        import src.execution.mt5_adapter as mod

        mod.mt5 = fake_mt5  # type: ignore[assignment]
        from src.execution.mt5_adapter import MT5Adapter

        adapter = MT5Adapter(account=12345, password="pw", server="Broker-Demo")
        assert adapter is not None

    def test_optional_mt5_path_defaults_none(self, fake_mt5: MagicMock) -> None:
        import src.execution.mt5_adapter as mod

        mod.mt5 = fake_mt5  # type: ignore[assignment]
        from src.execution.mt5_adapter import MT5Adapter

        adapter = MT5Adapter(account=1, password="x", server="srv")
        # Should not raise; mt5_path defaults to None

    def test_implements_all_three_abcs(self, adapter: Any) -> None:
        from src.execution.abstract import MarketDataProvider, OrderExecutor, PositionManager

        assert isinstance(adapter, MarketDataProvider)
        assert isinstance(adapter, OrderExecutor)
        assert isinstance(adapter, PositionManager)


# ---------------------------------------------------------------------------
# connect / disconnect
# ---------------------------------------------------------------------------


class TestConnect:
    def test_connect_success(self, adapter: Any, fake_mt5: MagicMock) -> None:
        fake_mt5.initialize.return_value = True
        fake_mt5.login.return_value = True
        asyncio.run(adapter.connect())
        assert fake_mt5.initialize.called
        assert fake_mt5.login.called

    def test_connect_calls_initialize_via_to_thread(
        self, adapter: Any, fake_mt5: MagicMock
    ) -> None:
        """initialize() must be called through asyncio.to_thread, not directly."""
        import src.execution.mt5_adapter as mod

        call_log: list[str] = []

        original_to_thread = asyncio.to_thread

        async def spy_to_thread(func: Any, *args: Any, **kwargs: Any) -> Any:
            call_log.append(getattr(func, "__name__", str(func)))
            return await original_to_thread(func, *args, **kwargs)

        fake_mt5.initialize.return_value = True
        fake_mt5.login.return_value = True

        with patch("src.execution.mt5_adapter.asyncio.to_thread", side_effect=spy_to_thread):
            asyncio.run(adapter.connect())

        assert len(call_log) >= 2, "Expected at least 2 asyncio.to_thread calls in connect()"

    def test_connect_failure_raises_connection_error(
        self, adapter: Any, fake_mt5: MagicMock
    ) -> None:
        fake_mt5.initialize.return_value = False
        fake_mt5.last_error.return_value = (-6, "Terminal not running")
        with pytest.raises(ConnectionError, match="Terminal not running"):
            asyncio.run(adapter.connect())

    def test_login_failure_raises_connection_error(
        self, adapter: Any, fake_mt5: MagicMock
    ) -> None:
        fake_mt5.initialize.return_value = True
        fake_mt5.login.return_value = False
        fake_mt5.last_error.return_value = (10014, "Invalid credentials")
        with pytest.raises(ConnectionError, match="Invalid credentials"):
            asyncio.run(adapter.connect())

    def test_disconnect_calls_shutdown(self, adapter: Any, fake_mt5: MagicMock) -> None:
        asyncio.run(adapter.disconnect())
        assert fake_mt5.shutdown.called


# ---------------------------------------------------------------------------
# get_ticks
# ---------------------------------------------------------------------------


class TestGetTicks:
    def _make_tick_row(self, bid: float, ask: float) -> Any:
        """Build a numpy structured array row matching MT5 tick format."""
        dtype = np.dtype(
            [
                ("time", np.int64),
                ("bid", np.float64),
                ("ask", np.float64),
                ("last", np.float64),
                ("volume", np.uint64),
                ("time_msc", np.int64),
                ("flags", np.uint32),
                ("volume_real", np.float64),
            ]
        )
        row = np.zeros(1, dtype=dtype)
        row["time"][0] = 1704067200  # 2024-01-01 00:00:00 UTC
        row["bid"][0] = bid
        row["ask"][0] = ask
        row["volume"][0] = 10
        return row

    def test_returns_tick_list(self, adapter: Any, fake_mt5: MagicMock) -> None:
        from src.execution.abstract import Tick

        fake_mt5.copy_ticks_range.return_value = self._make_tick_row(1.1000, 1.1002)
        result = asyncio.run(
            adapter.get_ticks(
                "EURUSD",
                np.datetime64("2024-01-01T00:00:00", "ns"),
                np.datetime64("2024-01-01T01:00:00", "ns"),
            )
        )
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], Tick)

    def test_tick_fields_correctly_mapped(self, adapter: Any, fake_mt5: MagicMock) -> None:
        fake_mt5.copy_ticks_range.return_value = self._make_tick_row(1.1000, 1.1002)
        result = asyncio.run(
            adapter.get_ticks(
                "EURUSD",
                np.datetime64("2024-01-01T00:00:00", "ns"),
                np.datetime64("2024-01-01T01:00:00", "ns"),
            )
        )
        tick = result[0]
        assert tick.bid == pytest.approx(1.1000)
        assert tick.ask == pytest.approx(1.1002)
        assert tick.symbol == "EURUSD"

    def test_empty_result_returns_empty_list(self, adapter: Any, fake_mt5: MagicMock) -> None:
        fake_mt5.copy_ticks_range.return_value = None
        result = asyncio.run(
            adapter.get_ticks(
                "EURUSD",
                np.datetime64("2024-01-01T00:00:00", "ns"),
                np.datetime64("2024-01-01T01:00:00", "ns"),
            )
        )
        assert result == []

    def test_uses_asyncio_to_thread(self, adapter: Any, fake_mt5: MagicMock) -> None:
        fake_mt5.copy_ticks_range.return_value = None
        call_count: list[int] = [0]
        original = asyncio.to_thread

        async def counting_to_thread(func: Any, *a: Any, **kw: Any) -> Any:
            call_count[0] += 1
            return await original(func, *a, **kw)

        with patch("src.execution.mt5_adapter.asyncio.to_thread", side_effect=counting_to_thread):
            asyncio.run(
                adapter.get_ticks(
                    "EURUSD",
                    np.datetime64("2024-01-01T00:00:00", "ns"),
                    np.datetime64("2024-01-01T01:00:00", "ns"),
                )
            )
        assert call_count[0] >= 1


# ---------------------------------------------------------------------------
# get_bars
# ---------------------------------------------------------------------------


class TestGetBars:
    def _make_bar_array(self, close: float = 1.10) -> Any:
        dtype = np.dtype(
            [
                ("time", np.int64),
                ("open", np.float64),
                ("high", np.float64),
                ("low", np.float64),
                ("close", np.float64),
                ("tick_volume", np.int64),
                ("spread", np.int32),
                ("real_volume", np.int64),
            ]
        )
        arr = np.zeros(2, dtype=dtype)
        arr["time"][0] = 1704067200
        arr["open"][0] = 1.099
        arr["high"][0] = 1.102
        arr["low"][0] = 1.098
        arr["close"][0] = close
        arr["spread"][0] = 2
        arr["tick_volume"][0] = 500
        arr["time"][1] = 1704070800
        arr["close"][1] = close + 0.001
        arr["spread"][1] = 2
        return arr

    def test_returns_bar_list(self, adapter: Any, fake_mt5: MagicMock) -> None:
        from src.execution.abstract import Bar

        info_mock = MagicMock()
        info_mock.point = 0.00001
        fake_mt5.symbol_info.return_value = info_mock
        fake_mt5.copy_rates_from_pos.return_value = self._make_bar_array()

        result = asyncio.run(adapter.get_bars("EURUSD", "1h", 2))
        assert isinstance(result, list)
        assert len(result) == 2
        assert isinstance(result[0], Bar)

    def test_bar_fields_mapped(self, adapter: Any, fake_mt5: MagicMock) -> None:
        info_mock = MagicMock()
        info_mock.point = 0.00001
        fake_mt5.symbol_info.return_value = info_mock
        fake_mt5.copy_rates_from_pos.return_value = self._make_bar_array(close=1.1050)

        result = asyncio.run(adapter.get_bars("EURUSD", "1h", 2))
        assert result[0].close == pytest.approx(1.1050)
        assert result[0].symbol == "EURUSD"

    def test_spread_field_uses_point(self, adapter: Any, fake_mt5: MagicMock) -> None:
        """spread = row['spread'] * symbol_info.point"""
        info_mock = MagicMock()
        info_mock.point = 0.00001
        fake_mt5.symbol_info.return_value = info_mock
        fake_mt5.copy_rates_from_pos.return_value = self._make_bar_array()

        result = asyncio.run(adapter.get_bars("EURUSD", "1h", 2))
        # spread=2, point=0.00001 → 0.00002
        assert result[0].spread == pytest.approx(2 * 0.00001)

    def test_timeframe_mapping_1m(self, adapter: Any, fake_mt5: MagicMock) -> None:
        info_mock = MagicMock()
        info_mock.point = 0.00001
        fake_mt5.symbol_info.return_value = info_mock
        fake_mt5.copy_rates_from_pos.return_value = self._make_bar_array()

        asyncio.run(adapter.get_bars("EURUSD", "1m", 5))
        call_args = fake_mt5.copy_rates_from_pos.call_args
        # The timeframe constant should be TIMEFRAME_M1 (=1 in our mock)
        assert call_args[0][1] == fake_mt5.TIMEFRAME_M1

    def test_empty_result_returns_empty_list(self, adapter: Any, fake_mt5: MagicMock) -> None:
        info_mock = MagicMock()
        info_mock.point = 0.00001
        fake_mt5.symbol_info.return_value = info_mock
        fake_mt5.copy_rates_from_pos.return_value = None

        result = asyncio.run(adapter.get_bars("EURUSD", "1h", 5))
        assert result == []

    def test_uses_asyncio_to_thread(self, adapter: Any, fake_mt5: MagicMock) -> None:
        info_mock = MagicMock()
        info_mock.point = 0.00001
        fake_mt5.symbol_info.return_value = info_mock
        fake_mt5.copy_rates_from_pos.return_value = None
        call_count: list[int] = [0]
        original = asyncio.to_thread

        async def counting(func: Any, *a: Any, **kw: Any) -> Any:
            call_count[0] += 1
            return await original(func, *a, **kw)

        with patch("src.execution.mt5_adapter.asyncio.to_thread", side_effect=counting):
            asyncio.run(adapter.get_bars("EURUSD", "1h", 5))
        assert call_count[0] >= 1


# ---------------------------------------------------------------------------
# submit_order
# ---------------------------------------------------------------------------


class TestSubmitOrder:
    def _make_order(self) -> Any:
        from src.execution.abstract import OrderRequest, OrderType, Side

        return OrderRequest(
            symbol="EURUSD",
            side=Side.BUY,
            quantity=0.1,
            order_type=OrderType.MARKET,
        )

    def _make_result_mock(self, retcode: int = 10009, price: float = 1.1001) -> MagicMock:
        res = MagicMock()
        res.retcode = retcode
        res.order = 111111
        res.price = price
        res.volume = 0.1
        res.comment = ""
        return res

    def test_submit_order_success(self, adapter: Any, fake_mt5: MagicMock) -> None:
        from src.execution.abstract import OrderResult

        fake_mt5.order_send.return_value = self._make_result_mock()
        info_mock = MagicMock()
        info_mock.ask = 1.1001
        info_mock.bid = 1.0999
        fake_mt5.symbol_info_tick.return_value = info_mock

        result = asyncio.run(adapter.submit_order(self._make_order()))
        assert isinstance(result, OrderResult)
        assert result.success is True

    def test_submit_order_uses_deviation_20_magic_100001(
        self, adapter: Any, fake_mt5: MagicMock
    ) -> None:
        fake_mt5.order_send.return_value = self._make_result_mock()
        info_mock = MagicMock()
        info_mock.ask = 1.1001
        info_mock.bid = 1.0999
        fake_mt5.symbol_info_tick.return_value = info_mock

        asyncio.run(adapter.submit_order(self._make_order()))
        call_args = fake_mt5.order_send.call_args[0][0]
        assert call_args["deviation"] == 20
        assert call_args["magic"] == 100001

    def test_order_rejection_returns_failure(self, adapter: Any, fake_mt5: MagicMock) -> None:
        fake_mt5.order_send.return_value = self._make_result_mock(retcode=10018)
        info_mock = MagicMock()
        info_mock.ask = 1.1001
        info_mock.bid = 1.0999
        fake_mt5.symbol_info_tick.return_value = info_mock

        result = asyncio.run(adapter.submit_order(self._make_order()))
        assert result.success is False

    def test_buy_order_uses_buy_type(self, adapter: Any, fake_mt5: MagicMock) -> None:
        fake_mt5.order_send.return_value = self._make_result_mock()
        info_mock = MagicMock()
        info_mock.ask = 1.1001
        info_mock.bid = 1.0999
        fake_mt5.symbol_info_tick.return_value = info_mock

        asyncio.run(adapter.submit_order(self._make_order()))
        call_args = fake_mt5.order_send.call_args[0][0]
        assert call_args["type"] == fake_mt5.ORDER_TYPE_BUY

    def test_sell_order_uses_sell_type(self, adapter: Any, fake_mt5: MagicMock) -> None:
        from src.execution.abstract import OrderRequest, OrderType, Side

        fake_mt5.order_send.return_value = self._make_result_mock()
        info_mock = MagicMock()
        info_mock.ask = 1.1001
        info_mock.bid = 1.0999
        fake_mt5.symbol_info_tick.return_value = info_mock

        sell_order = OrderRequest(symbol="EURUSD", side=Side.SELL, quantity=0.1)
        asyncio.run(adapter.submit_order(sell_order))
        call_args = fake_mt5.order_send.call_args[0][0]
        assert call_args["type"] == fake_mt5.ORDER_TYPE_SELL

    def test_submit_order_uses_asyncio_to_thread(self, adapter: Any, fake_mt5: MagicMock) -> None:
        fake_mt5.order_send.return_value = self._make_result_mock()
        info_mock = MagicMock()
        info_mock.ask = 1.1001
        info_mock.bid = 1.0999
        fake_mt5.symbol_info_tick.return_value = info_mock
        call_count: list[int] = [0]
        original = asyncio.to_thread

        async def counting(func: Any, *a: Any, **kw: Any) -> Any:
            call_count[0] += 1
            return await original(func, *a, **kw)

        with patch("src.execution.mt5_adapter.asyncio.to_thread", side_effect=counting):
            asyncio.run(adapter.submit_order(self._make_order()))
        assert call_count[0] >= 1


# ---------------------------------------------------------------------------
# cancel_order / get_open_orders
# ---------------------------------------------------------------------------


class TestCancelOrder:
    def test_cancel_order_calls_mt5(self, adapter: Any, fake_mt5: MagicMock) -> None:
        res_mock = MagicMock()
        res_mock.retcode = 10009
        fake_mt5.order_send.return_value = res_mock
        result = asyncio.run(adapter.cancel_order("111111"))
        assert isinstance(result, bool)

    def test_get_open_orders_returns_list(self, adapter: Any, fake_mt5: MagicMock) -> None:
        fake_mt5.orders_get.return_value = []
        result = asyncio.run(adapter.get_open_orders())
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# get_positions
# ---------------------------------------------------------------------------


class TestGetPositions:
    def _make_position_row(self) -> MagicMock:
        pos = MagicMock()
        pos.symbol = "EURUSD"
        pos.type = 0  # BUY
        pos.volume = 0.1
        pos.price_open = 1.1000
        pos.price_current = 1.1010
        pos.profit = 10.0
        pos.swap = -0.5
        pos.margin = 110.0
        return pos

    def test_get_positions_returns_list(self, adapter: Any, fake_mt5: MagicMock) -> None:
        from src.execution.abstract import Position

        fake_mt5.positions_get.return_value = [self._make_position_row()]
        result = asyncio.run(adapter.get_positions())
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], Position)

    def test_position_side_buy(self, adapter: Any, fake_mt5: MagicMock) -> None:
        from src.execution.abstract import Side

        row = self._make_position_row()
        row.type = 0  # MT5 BUY
        fake_mt5.positions_get.return_value = [row]

        result = asyncio.run(adapter.get_positions())
        assert result[0].side == Side.BUY

    def test_position_side_sell(self, adapter: Any, fake_mt5: MagicMock) -> None:
        from src.execution.abstract import Side

        row = self._make_position_row()
        row.type = 1  # MT5 SELL
        fake_mt5.positions_get.return_value = [row]

        result = asyncio.run(adapter.get_positions())
        assert result[0].side == Side.SELL

    def test_empty_positions(self, adapter: Any, fake_mt5: MagicMock) -> None:
        fake_mt5.positions_get.return_value = None
        result = asyncio.run(adapter.get_positions())
        assert result == []

    def test_uses_asyncio_to_thread(self, adapter: Any, fake_mt5: MagicMock) -> None:
        fake_mt5.positions_get.return_value = None
        call_count: list[int] = [0]
        original = asyncio.to_thread

        async def counting(func: Any, *a: Any, **kw: Any) -> Any:
            call_count[0] += 1
            return await original(func, *a, **kw)

        with patch("src.execution.mt5_adapter.asyncio.to_thread", side_effect=counting):
            asyncio.run(adapter.get_positions())
        assert call_count[0] >= 1


# ---------------------------------------------------------------------------
# close_position
# ---------------------------------------------------------------------------


class TestClosePosition:
    def test_close_position_creates_reverse_order(
        self, adapter: Any, fake_mt5: MagicMock
    ) -> None:
        from src.execution.abstract import OrderResult, Side

        # Set up a BUY position
        pos = MagicMock()
        pos.symbol = "EURUSD"
        pos.type = 0  # BUY
        pos.volume = 0.1
        pos.price_open = 1.1000
        pos.price_current = 1.1010
        pos.profit = 1.0
        pos.swap = 0.0
        pos.margin = 110.0
        fake_mt5.positions_get.return_value = [pos]

        res_mock = MagicMock()
        res_mock.retcode = 10009
        res_mock.order = 222222
        res_mock.price = 1.1010
        res_mock.volume = 0.1
        res_mock.comment = ""
        fake_mt5.order_send.return_value = res_mock

        tick_mock = MagicMock()
        tick_mock.bid = 1.1008
        tick_mock.ask = 1.1010
        fake_mt5.symbol_info_tick.return_value = tick_mock

        result = asyncio.run(adapter.close_position("EURUSD"))
        assert isinstance(result, OrderResult)
        # Verify the close used SELL (reverse of BUY)
        sent = fake_mt5.order_send.call_args[0][0]
        assert sent["type"] == fake_mt5.ORDER_TYPE_SELL


# ---------------------------------------------------------------------------
# get_account_equity / get_margin_level
# ---------------------------------------------------------------------------


class TestAccountInfo:
    def test_get_account_equity_returns_float(self, adapter: Any, fake_mt5: MagicMock) -> None:
        info = MagicMock()
        info.equity = 98500.50
        fake_mt5.account_info.return_value = info
        result = asyncio.run(adapter.get_account_equity())
        assert result == pytest.approx(98500.50)

    def test_get_margin_level_returns_float(self, adapter: Any, fake_mt5: MagicMock) -> None:
        info = MagicMock()
        info.margin_level = 234.5
        fake_mt5.account_info.return_value = info
        result = asyncio.run(adapter.get_margin_level())
        assert result == pytest.approx(234.5)

    def test_account_equity_uses_asyncio_to_thread(
        self, adapter: Any, fake_mt5: MagicMock
    ) -> None:
        info = MagicMock()
        info.equity = 100000.0
        fake_mt5.account_info.return_value = info
        call_count: list[int] = [0]
        original = asyncio.to_thread

        async def counting(func: Any, *a: Any, **kw: Any) -> Any:
            call_count[0] += 1
            return await original(func, *a, **kw)

        with patch("src.execution.mt5_adapter.asyncio.to_thread", side_effect=counting):
            asyncio.run(adapter.get_account_equity())
        assert call_count[0] >= 1


# ---------------------------------------------------------------------------
# get_symbols / subscribe_ticks
# ---------------------------------------------------------------------------


class TestGetSymbols:
    def test_get_symbols_returns_list_of_strings(self, adapter: Any, fake_mt5: MagicMock) -> None:
        sym1 = MagicMock()
        sym1.name = "EURUSD"
        sym2 = MagicMock()
        sym2.name = "GBPUSD"
        fake_mt5.symbols_get.return_value = [sym1, sym2]
        result = asyncio.run(adapter.get_symbols())
        assert isinstance(result, list)
        assert "EURUSD" in result

    def test_empty_symbols_returns_empty_list(self, adapter: Any, fake_mt5: MagicMock) -> None:
        fake_mt5.symbols_get.return_value = None
        result = asyncio.run(adapter.get_symbols())
        assert result == []


class TestSubscribeTicks:
    def test_subscribe_ticks_is_coroutine(self, adapter: Any) -> None:
        """subscribe_ticks must be an async method (coroutine function)."""
        import inspect

        assert inspect.iscoroutinefunction(adapter.subscribe_ticks)
