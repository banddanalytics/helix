"""MT5Adapter: concrete implementation of MarketDataProvider, OrderExecutor, PositionManager.

All synchronous MetaTrader5 API calls are wrapped in asyncio.to_thread() so
they do not block the event loop.  MetaTrader5 is imported conditionally so
this module can be imported on Linux in CI without the Windows-only package.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

import numpy as np

from src.execution.abstract import (
    Bar,
    MarketDataProvider,
    OrderExecutor,
    OrderRequest,
    OrderResult,
    OrderType,
    Position,
    PositionManager,
    Side,
    Tick,
)

# MT5 imported conditionally to allow Linux CI to run
try:
    import MetaTrader5 as mt5  # type: ignore[import-untyped,unused-ignore]
except ImportError:
    mt5 = None  # type: ignore[assignment,unused-ignore]


TIMEFRAME_MAP: dict[str, Any] = {
    "1m": "TIMEFRAME_M1",
    "5m": "TIMEFRAME_M5",
    "15m": "TIMEFRAME_M15",
    "30m": "TIMEFRAME_M30",
    "1h": "TIMEFRAME_H1",
    "4h": "TIMEFRAME_H4",
    "1d": "TIMEFRAME_D1",
    "1w": "TIMEFRAME_W1",
}


class MT5Adapter(MarketDataProvider, OrderExecutor, PositionManager):
    """Concrete broker adapter wrapping the MetaTrader5 Python API.

    All MT5 calls are wrapped in ``asyncio.to_thread`` to prevent blocking
    the event loop.  Designed to run on Windows where MT5 is available; in
    CI on Linux the ``mt5`` module-level name is replaced by a ``MagicMock``.
    """

    def __init__(
        self,
        account: int,
        password: str,
        server: str,
        mt5_path: str | None = None,
    ) -> None:
        self._account = account
        self._password = password
        self._server = server
        self._mt5_path = mt5_path

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Initialize the MT5 terminal and login to the trading account."""
        if self._mt5_path is not None:
            ok: bool = await asyncio.to_thread(mt5.initialize, self._mt5_path)
        else:
            ok = await asyncio.to_thread(mt5.initialize)
        if not ok:
            err = await asyncio.to_thread(mt5.last_error)
            raise ConnectionError(f"MT5 initialize failed: {err}")

        logged_in: bool = await asyncio.to_thread(
            mt5.login,
            self._account,
            password=self._password,
            server=self._server,
        )
        if not logged_in:
            err = await asyncio.to_thread(mt5.last_error)
            raise ConnectionError(f"MT5 login failed: {err}")

    async def disconnect(self) -> None:
        """Shut down the MT5 terminal connection."""
        await asyncio.to_thread(mt5.shutdown)

    # ------------------------------------------------------------------
    # MarketDataProvider
    # ------------------------------------------------------------------

    async def get_ticks(
        self,
        symbol: str,
        start: np.datetime64,
        end: np.datetime64,
    ) -> list[Tick]:
        """Retrieve tick data for *symbol* between *start* and *end*."""
        start_ts = int(start.astype("datetime64[s]").astype(np.int64))
        end_ts = int(end.astype("datetime64[s]").astype(np.int64))

        raw = await asyncio.to_thread(
            mt5.copy_ticks_range,
            symbol,
            start_ts,
            end_ts,
            mt5.COPY_TICKS_ALL,
        )
        if raw is None or len(raw) == 0:
            return []

        ticks: list[Tick] = []
        for row in raw:
            ticks.append(
                Tick(
                    timestamp=np.datetime64(int(row["time"]), "s").astype("datetime64[ns]"),
                    symbol=symbol,
                    bid=float(row["bid"]),
                    ask=float(row["ask"]),
                    bid_volume=float(row["volume"]),
                    ask_volume=float(row["volume"]),
                    source="mt5",
                )
            )
        return ticks

    async def get_bars(self, symbol: str, timeframe: str, count: int) -> list[Bar]:
        """Retrieve the most recent *count* bars for *symbol* at *timeframe*."""
        tf_attr = TIMEFRAME_MAP.get(timeframe, "TIMEFRAME_H1")
        tf_const: Any = getattr(mt5, tf_attr)

        info = await asyncio.to_thread(mt5.symbol_info, symbol)
        point: float = float(info.point) if info is not None else 0.00001

        raw = await asyncio.to_thread(
            mt5.copy_rates_from_pos,
            symbol,
            tf_const,
            0,
            count,
        )
        if raw is None or len(raw) == 0:
            return []

        bars: list[Bar] = []
        for row in raw:
            bars.append(
                Bar(
                    timestamp=np.datetime64(int(row["time"]), "s").astype("datetime64[ns]"),
                    symbol=symbol,
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["tick_volume"]),
                    spread=float(row["spread"]) * point,
                )
            )
        return bars

    async def subscribe_ticks(self, symbol: str, callback: Callable[[Tick], None]) -> None:
        """Poll MT5 at 10 ms intervals and invoke *callback* with each new tick."""
        last_time: int = 0
        while True:
            tick_info = await asyncio.to_thread(mt5.symbol_info_tick, symbol)
            if tick_info is not None and tick_info.time != last_time:
                last_time = tick_info.time
                callback(
                    Tick(
                        timestamp=np.datetime64(int(tick_info.time), "s").astype(
                            "datetime64[ns]"
                        ),
                        symbol=symbol,
                        bid=float(tick_info.bid),
                        ask=float(tick_info.ask),
                        source="mt5",
                    )
                )
            await asyncio.sleep(0.01)

    async def get_symbols(self) -> list[str]:
        """Return all available instrument identifiers."""
        raw = await asyncio.to_thread(mt5.symbols_get)
        if raw is None:
            return []
        return [sym.name for sym in raw]

    # ------------------------------------------------------------------
    # OrderExecutor
    # ------------------------------------------------------------------

    async def submit_order(self, order: OrderRequest) -> OrderResult:
        """Build and send an MT5 market order request."""
        tick_info = await asyncio.to_thread(mt5.symbol_info_tick, order.symbol)
        if order.side == Side.BUY:
            price: float = float(tick_info.ask)
            order_type = mt5.ORDER_TYPE_BUY
        else:
            price = float(tick_info.bid)
            order_type = mt5.ORDER_TYPE_SELL

        request: dict[str, Any] = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": order.symbol,
            "volume": order.quantity,
            "type": order_type,
            "price": order.price if order.price is not None else price,
            "deviation": 20,
            "magic": 100001,
            "type_filling": mt5.ORDER_FILLING_IOC,
            "comment": order.comment,
        }
        if order.sl is not None:
            request["sl"] = order.sl
        if order.tp is not None:
            request["tp"] = order.tp

        result = await asyncio.to_thread(mt5.order_send, request)

        success = result.retcode == mt5.TRADE_RETCODE_DONE
        error_msg = "" if success else f"retcode={result.retcode}: {result.comment}"
        return OrderResult(
            order_id=str(result.order),
            fill_price=float(result.price),
            fill_quantity=float(result.volume),
            slippage=abs(float(result.price) - price),
            commission=0.0,
            success=success,
            error_message=error_msg,
        )

    async def cancel_order(self, order_id: str) -> bool:
        """Send a cancel request for the given order ID."""
        request: dict[str, Any] = {
            "action": 2,  # TRADE_ACTION_REMOVE
            "order": int(order_id),
        }
        result = await asyncio.to_thread(mt5.order_send, request)
        return bool(result.retcode == mt5.TRADE_RETCODE_DONE)

    async def get_open_orders(self) -> list[OrderRequest]:
        """Return all pending (unfilled) orders."""
        raw = await asyncio.to_thread(mt5.orders_get)
        if not raw:
            return []
        orders: list[OrderRequest] = []
        for o in raw:
            side = Side.BUY if o.type == mt5.ORDER_TYPE_BUY else Side.SELL
            orders.append(
                OrderRequest(
                    symbol=o.symbol,
                    side=side,
                    quantity=float(o.volume_current),
                    price=float(o.price_open),
                    comment=o.comment,
                )
            )
        return orders

    # ------------------------------------------------------------------
    # PositionManager
    # ------------------------------------------------------------------

    async def get_positions(self) -> list[Position]:
        """Return all currently open positions."""
        raw = await asyncio.to_thread(mt5.positions_get)
        if not raw:
            return []
        positions: list[Position] = []
        for p in raw:
            side = Side.BUY if p.type == 0 else Side.SELL
            positions.append(
                Position(
                    symbol=p.symbol,
                    side=side,
                    quantity=float(p.volume),
                    entry_price=float(p.price_open),
                    current_price=float(p.price_current),
                    unrealized_pnl=float(p.profit),
                    swap_accumulated=float(p.swap),
                    margin_used=float(p.margin),
                )
            )
        return positions

    async def close_position(self, symbol: str) -> OrderResult:
        """Close an open position by submitting a reverse market order."""
        raw = await asyncio.to_thread(mt5.positions_get)
        position: Any = None
        if raw:
            for p in raw:
                if p.symbol == symbol:
                    position = p
                    break

        if position is None:
            return OrderResult(
                order_id="",
                fill_price=0.0,
                fill_quantity=0.0,
                slippage=0.0,
                commission=0.0,
                success=False,
                error_message=f"No open position for {symbol}",
            )

        tick_info = await asyncio.to_thread(mt5.symbol_info_tick, symbol)

        # Reverse: BUY position → SELL to close, SELL position → BUY to close
        if position.type == 0:  # BUY
            close_type = mt5.ORDER_TYPE_SELL
            close_price = float(tick_info.bid)
        else:
            close_type = mt5.ORDER_TYPE_BUY
            close_price = float(tick_info.ask)

        request: dict[str, Any] = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(position.volume),
            "type": close_type,
            "price": close_price,
            "deviation": 20,
            "magic": 100001,
            "type_filling": mt5.ORDER_FILLING_IOC,
            "comment": "close",
        }
        result = await asyncio.to_thread(mt5.order_send, request)
        success = result.retcode == mt5.TRADE_RETCODE_DONE
        return OrderResult(
            order_id=str(result.order),
            fill_price=float(result.price),
            fill_quantity=float(result.volume),
            slippage=abs(float(result.price) - close_price),
            commission=0.0,
            success=success,
            error_message="" if success else f"retcode={result.retcode}: {result.comment}",
        )

    async def get_account_equity(self) -> float:
        """Return current account equity."""
        info = await asyncio.to_thread(mt5.account_info)
        return float(info.equity)

    async def get_margin_level(self) -> float:
        """Return current margin level as a percentage."""
        info = await asyncio.to_thread(mt5.account_info)
        return float(info.margin_level)
