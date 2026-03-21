"""MessagePack serialization schemas for the ZeroMQ bridge.

Provides pack/unpack functions for every message type crossing the
Windows MT5 ↔ Linux alpha engine bridge:

  Tick          — real-time best-bid/ask snapshots
  Bar           — OHLCV aggregates
  OrderRequest  — trade instructions (Linux → Windows)
  OrderResult   — fill confirmations  (Windows → Linux)
  Heartbeat     — keep-alive with timestamp

All timestamps are transmitted as int64 nanoseconds-since-epoch so that
the round-trip preserves nanosecond precision without floating-point loss.

Enums are transmitted as their `.value` (int/str) to remain
forward-compatible with schema evolution.
"""

from __future__ import annotations

import time
from typing import Any

import msgpack  # type: ignore[import-untyped,unused-ignore]
import numpy as np

from src.execution.abstract import (
    Bar,
    OrderRequest,
    OrderResult,
    OrderType,
    Side,
    Tick,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _dt64_to_ns(dt: np.datetime64) -> int:
    """Convert numpy datetime64 to nanoseconds since epoch (int64)."""
    return int(dt.astype("datetime64[ns]").astype(np.int64))


def _ns_to_dt64(ns: int) -> np.datetime64:
    """Convert nanoseconds since epoch to numpy datetime64[ns]."""
    return np.datetime64(ns, "ns")


# ---------------------------------------------------------------------------
# Tick
# ---------------------------------------------------------------------------


def pack_tick(tick: Tick) -> bytes:
    """Serialize a Tick to MessagePack bytes."""
    return msgpack.packb(  # type: ignore[no-any-return]
        {
            "ts": _dt64_to_ns(tick.timestamp),
            "sym": tick.symbol,
            "bid": tick.bid,
            "ask": tick.ask,
            "bv": tick.bid_volume,
            "av": tick.ask_volume,
            "src": tick.source,
        }
    )


def unpack_tick(data: bytes) -> Tick:
    """Deserialize MessagePack bytes to a Tick."""
    d: dict[str, Any] = msgpack.unpackb(data)
    return Tick(
        timestamp=_ns_to_dt64(d["ts"]),
        symbol=d["sym"],
        bid=d["bid"],
        ask=d["ask"],
        bid_volume=d["bv"],
        ask_volume=d["av"],
        source=d["src"],
    )


# ---------------------------------------------------------------------------
# Bar
# ---------------------------------------------------------------------------


def pack_bar(bar: Bar) -> bytes:
    """Serialize a Bar to MessagePack bytes."""
    return msgpack.packb(  # type: ignore[no-any-return]
        {
            "ts": _dt64_to_ns(bar.timestamp),
            "sym": bar.symbol,
            "o": bar.open,
            "h": bar.high,
            "l": bar.low,
            "c": bar.close,
            "v": bar.volume,
            "sp": bar.spread,
        }
    )


def unpack_bar(data: bytes) -> Bar:
    """Deserialize MessagePack bytes to a Bar."""
    d: dict[str, Any] = msgpack.unpackb(data)
    return Bar(
        timestamp=_ns_to_dt64(d["ts"]),
        symbol=d["sym"],
        open=d["o"],
        high=d["h"],
        low=d["l"],
        close=d["c"],
        volume=d["v"],
        spread=d["sp"],
    )


# ---------------------------------------------------------------------------
# OrderRequest
# ---------------------------------------------------------------------------


def pack_order_request(order: OrderRequest) -> bytes:
    """Serialize an OrderRequest to MessagePack bytes.

    ``side`` is stored as its int value; ``order_type`` as its str value.
    Optional price/sl/tp fields are stored as-is (None → msgpack nil).
    """
    return msgpack.packb(  # type: ignore[no-any-return]
        {
            "sym": order.symbol,
            "side": order.side.value,
            "qty": order.quantity,
            "ot": order.order_type.value,
            "px": order.price,
            "sl": order.sl,
            "tp": order.tp,
            "cmt": order.comment,
        }
    )


def unpack_order_request(data: bytes) -> OrderRequest:
    """Deserialize MessagePack bytes to an OrderRequest."""
    d: dict[str, Any] = msgpack.unpackb(data)
    return OrderRequest(
        symbol=d["sym"],
        side=Side(d["side"]),
        quantity=d["qty"],
        order_type=OrderType(d["ot"]),
        price=d["px"],
        sl=d["sl"],
        tp=d["tp"],
        comment=d["cmt"],
    )


# ---------------------------------------------------------------------------
# OrderResult
# ---------------------------------------------------------------------------


def pack_order_result(result: OrderResult) -> bytes:
    """Serialize an OrderResult to MessagePack bytes."""
    return msgpack.packb(  # type: ignore[no-any-return]
        {
            "oid": result.order_id,
            "fp": result.fill_price,
            "fq": result.fill_quantity,
            "slip": result.slippage,
            "comm": result.commission,
            "ok": result.success,
            "err": result.error_message,
        }
    )


def unpack_order_result(data: bytes) -> OrderResult:
    """Deserialize MessagePack bytes to an OrderResult."""
    d: dict[str, Any] = msgpack.unpackb(data)
    return OrderResult(
        order_id=d["oid"],
        fill_price=d["fp"],
        fill_quantity=d["fq"],
        slippage=d["slip"],
        commission=d["comm"],
        success=d["ok"],
        error_message=d["err"],
    )


# ---------------------------------------------------------------------------
# Heartbeat
# ---------------------------------------------------------------------------


def pack_heartbeat() -> bytes:
    """Serialize a heartbeat with the current wall-clock time."""
    ns = int(time.time_ns())
    return msgpack.packb({"type": "heartbeat", "ts": ns})  # type: ignore[no-any-return]


def unpack_heartbeat(data: bytes) -> np.datetime64:
    """Deserialize a heartbeat and return its timestamp as numpy datetime64."""
    d: dict[str, Any] = msgpack.unpackb(data)
    return _ns_to_dt64(d["ts"])
