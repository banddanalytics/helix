"""Windows-side ZMQ publisher for MT5 market data.

Binds four ZMQ sockets per D-33:
  5556  PUB  — tick stream  (topic = symbol bytes)
  5557  PUB  — bar stream   (topic = symbol bytes)
  5558  PULL — order requests from Linux engines
  5559  PUSH — order results back to Linux engines

The heartbeat is sent on the tick PUB socket every
``HEARTBEAT_INTERVAL`` seconds so Linux consumers can detect stale feeds.

This module is designed for the Windows side of the bridge.  It imports
pyzmq with asyncio support and uses multipart sends for PUB sockets so
that ZMQ topic filtering works correctly on the subscriber side.

Usage::

    publisher = WindowsPublisher()
    await publisher.start()
    await publisher.publish_tick(tick)
    await publisher.stop()
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import zmq  # type: ignore[import-untyped,unused-ignore]
import zmq.asyncio  # type: ignore[import-untyped,unused-ignore]

from src.execution.abstract import Bar, OrderRequest, Tick
from src.execution.bridge.message_schemas import (
    pack_bar,
    pack_heartbeat,
    pack_order_result,
    pack_tick,
    unpack_order_request,
)


class WindowsPublisher:
    """ZMQ publisher that runs on the Windows MT5 host.

    Attributes:
        TICK_PORT: PUB socket port for tick data.
        BAR_PORT: PUB socket port for bar data.
        ORDER_REQ_PORT: PULL socket port for incoming order requests.
        ORDER_RES_PORT: PUSH socket port for outgoing order results.
        HEARTBEAT_INTERVAL: Seconds between heartbeat messages.
    """

    TICK_PORT: int = 5556
    BAR_PORT: int = 5557
    ORDER_REQ_PORT: int = 5558
    ORDER_RES_PORT: int = 5559
    HEARTBEAT_INTERVAL: float = 5.0  # seconds

    def __init__(self, bind_address: str = "tcp://*") -> None:
        self._bind_address = bind_address
        self._ctx: zmq.asyncio.Context | None = None
        self._tick_pub: Any = None
        self._bar_pub: Any = None
        self._order_pull: Any = None
        self._order_push: Any = None
        self._running: bool = False
        # Allow tests to override heartbeat interval without patching asyncio.sleep
        self._heartbeat_interval_seconds: float = self.HEARTBEAT_INTERVAL

    async def start(self) -> None:
        """Bind all sockets and start background loops."""
        self._ctx = zmq.asyncio.Context()
        self._tick_pub = self._ctx.socket(zmq.PUB)
        self._tick_pub.bind(f"{self._bind_address}:{self.TICK_PORT}")
        self._bar_pub = self._ctx.socket(zmq.PUB)
        self._bar_pub.bind(f"{self._bind_address}:{self.BAR_PORT}")
        self._order_pull = self._ctx.socket(zmq.PULL)
        self._order_pull.bind(f"{self._bind_address}:{self.ORDER_REQ_PORT}")
        self._order_push = self._ctx.socket(zmq.PUSH)
        self._order_push.bind(f"{self._bind_address}:{self.ORDER_RES_PORT}")
        self._running = True

    async def stop(self) -> None:
        """Close all sockets and terminate the context."""
        self._running = False
        for sock in (self._tick_pub, self._bar_pub, self._order_pull, self._order_push):
            if sock is not None:
                sock.close()
        if self._ctx is not None:
            self._ctx.term()
        self._tick_pub = None
        self._bar_pub = None
        self._order_pull = None
        self._order_push = None
        self._ctx = None

    async def publish_tick(self, tick: Tick) -> None:
        """Publish a Tick as a multipart ZMQ message.

        Topic frame is the symbol encoded as UTF-8 bytes so that subscribers
        using ``setsockopt(zmq.SUBSCRIBE, b"EURUSD")`` receive only their
        requested symbols.
        """
        if self._tick_pub is None:
            return
        await self._tick_pub.send_multipart([tick.symbol.encode(), pack_tick(tick)])

    async def publish_bar(self, bar: Bar) -> None:
        """Publish a Bar as a multipart ZMQ message."""
        if self._bar_pub is None:
            return
        await self._bar_pub.send_multipart([bar.symbol.encode(), pack_bar(bar)])

    async def _heartbeat_loop(self) -> None:
        """Send a heartbeat message periodically while running."""
        while self._running:
            if self._tick_pub is not None:
                await self._tick_pub.send(pack_heartbeat())
            await asyncio.sleep(self._heartbeat_interval_seconds)

    async def _order_loop(
        self,
        handler: Callable[[OrderRequest], Awaitable[None]],
    ) -> None:
        """Receive order requests and pass them to the handler.

        The handler is expected to execute the order via MT5 and call
        ``send_order_result`` with the outcome.
        """
        while self._running:
            if self._order_pull is None:
                await asyncio.sleep(0.01)
                continue
            raw = await self._order_pull.recv()
            order = unpack_order_request(raw)
            await handler(order)

    async def send_order_result_bytes(self, data: bytes) -> None:
        """Push pre-packed order result bytes to Linux consumers."""
        if self._order_push is not None:
            await self._order_push.send(data)
