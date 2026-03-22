"""Linux-side ZMQ consumer for MT5 market data.

Connects to the Windows publisher over WireGuard VPN (default host 10.200.0.1)
and maintains four sockets per D-33:

  5556  SUB  — tick stream  (subscribe to specific symbol topics)
  5557  SUB  — bar stream   (subscribe to specific symbol topics)
  5558  PUSH — order requests to Windows
  5559  PULL — order results from Windows

Auto-reconnect:
  If the underlying connection drops (heartbeat times out), the consumer
  attempts to reconnect with exponential back-off per D-35:
  1s → 2s → 4s → 8s → 16s → 30s (capped).

Stale data detection:
  ``is_stale`` returns True if no heartbeat has been received within
  ``STALE_THRESHOLD`` seconds.  Alpha engines must check this flag before
  generating signals.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

import zmq  # type: ignore[import-untyped,unused-ignore]
import zmq.asyncio  # type: ignore[import-untyped,unused-ignore]

from src.execution.abstract import Bar, OrderRequest, Tick
from src.execution.bridge.message_schemas import (
    pack_order_request,
    unpack_bar,
    unpack_heartbeat,
    unpack_order_result,
    unpack_tick,
)


class LinuxConsumer:
    """ZMQ subscriber that runs on the Linux alpha-engine host.

    Attributes:
        RECONNECT_DELAYS: Exponential back-off schedule in seconds (max 30s).
        STALE_THRESHOLD: Seconds without heartbeat before data is considered stale.
    """

    RECONNECT_DELAYS: list[float] = [1.0, 2.0, 4.0, 8.0, 16.0, 30.0]
    STALE_THRESHOLD: float = 10.0

    def __init__(self, host: str = "10.200.0.1") -> None:
        self._host = host
        self._ctx: zmq.asyncio.Context | None = None
        self._tick_sub: Any = None
        self._bar_sub: Any = None
        self._order_push: Any = None
        self._order_pull: Any = None
        self._last_heartbeat: float = 0.0
        self._is_stale: bool = True
        self._reconnect_attempt: int = 0
        self._subscribed_symbols: set[str] = set()
        self._running: bool = False
        # ZMQ constant — stored as attribute to allow test injection
        self._zmq_subscribe_opt: int = zmq.SUBSCRIBE

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Connect all ZMQ sockets to the Windows publisher host."""
        self._ctx = zmq.asyncio.Context()

        self._tick_sub = self._ctx.socket(zmq.SUB)
        self._tick_sub.connect(f"tcp://{self._host}:5556")

        self._bar_sub = self._ctx.socket(zmq.SUB)
        self._bar_sub.connect(f"tcp://{self._host}:5557")

        self._order_push = self._ctx.socket(zmq.PUSH)
        self._order_push.connect(f"tcp://{self._host}:5558")

        self._order_pull = self._ctx.socket(zmq.PULL)
        self._order_pull.connect(f"tcp://{self._host}:5559")

        self._running = True
        self._reconnect_attempt = 0

    async def disconnect(self) -> None:
        """Close all sockets and terminate the ZMQ context."""
        self._running = False
        for sock in (self._tick_sub, self._bar_sub, self._order_push, self._order_pull):
            if sock is not None:
                sock.close()
        if self._ctx is not None:
            self._ctx.term()
        self._tick_sub = None
        self._bar_sub = None
        self._order_push = None
        self._order_pull = None
        self._ctx = None

    # ------------------------------------------------------------------
    # Subscription management
    # ------------------------------------------------------------------

    async def subscribe(self, symbol: str) -> None:
        """Subscribe to tick and bar data for the given symbol.

        Sets the ZMQ topic filter so only messages prefixed with the
        symbol bytes are delivered.
        """
        if self._tick_sub is not None:
            self._tick_sub.setsockopt(self._zmq_subscribe_opt, symbol.encode())
        if self._bar_sub is not None:
            self._bar_sub.setsockopt(self._zmq_subscribe_opt, symbol.encode())
        self._subscribed_symbols.add(symbol)

    # ------------------------------------------------------------------
    # Stale detection
    # ------------------------------------------------------------------

    @property
    def is_stale(self) -> bool:
        """True if no heartbeat received within STALE_THRESHOLD seconds."""
        return time.monotonic() - self._last_heartbeat > self.STALE_THRESHOLD

    # ------------------------------------------------------------------
    # Receive loop
    # ------------------------------------------------------------------

    async def _receive_loop(
        self,
        on_tick: Callable[[Tick], Awaitable[None]],
        on_bar: Callable[[Bar], Awaitable[None]],
    ) -> None:
        """Receive ticks, bars, and heartbeats; dispatch to callbacks.

        Heartbeats are intercepted on the tick socket — they carry no
        symbol prefix so they arrive as a single frame.  Multipart tick/bar
        messages carry [symbol, payload] frames.
        """
        while self._running:
            poller = zmq.asyncio.Poller()
            if self._tick_sub is not None:
                poller.register(self._tick_sub, zmq.POLLIN)
            if self._bar_sub is not None:
                poller.register(self._bar_sub, zmq.POLLIN)

            events = dict(await poller.poll(timeout=100))

            if self._tick_sub in events:
                frames = await self._tick_sub.recv_multipart()
                if len(frames) == 1:
                    # heartbeat (single-frame message)
                    try:
                        unpack_heartbeat(frames[0])
                        self._last_heartbeat = time.monotonic()
                    except Exception:
                        pass
                elif len(frames) == 2:
                    tick = unpack_tick(frames[1])
                    await on_tick(tick)

            if self._bar_sub in events:
                frames = await self._bar_sub.recv_multipart()
                if len(frames) == 2:
                    bar = unpack_bar(frames[1])
                    await on_bar(bar)

    # ------------------------------------------------------------------
    # Order sending
    # ------------------------------------------------------------------

    async def send_order(self, order: OrderRequest) -> None:
        """Push an OrderRequest to the Windows publisher."""
        if self._order_push is not None:
            await self._order_push.send(pack_order_request(order))

    # ------------------------------------------------------------------
    # Reconnect with exponential back-off
    # ------------------------------------------------------------------

    def _get_reconnect_delay(self) -> float:
        """Return the delay for the current reconnect attempt (capped at 30s)."""
        idx = min(self._reconnect_attempt, len(self.RECONNECT_DELAYS) - 1)
        return self.RECONNECT_DELAYS[idx]

    async def _reconnect(self) -> None:
        """Attempt to reconnect once with exponential back-off."""
        delay = self._get_reconnect_delay()
        self._reconnect_attempt += 1
        await asyncio.sleep(delay)
        if self._running:
            # Close existing sockets and reconnect
            for sock in (
                self._tick_sub,
                self._bar_sub,
                self._order_push,
                self._order_pull,
            ):
                if sock is not None:
                    try:
                        sock.close()
                    except Exception:
                        pass
            self._tick_sub = None
            self._bar_sub = None
            self._order_push = None
            self._order_pull = None
            if self._ctx is not None:
                await self.connect()
