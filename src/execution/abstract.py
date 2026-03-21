"""Broker-agnostic execution interfaces and shared dataclasses.

This module defines the abstract contracts that every downstream component
codes against. No reference to any specific broker, exchange, or instrument
type exists here — those belong in concrete adapters.
"""
from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Side(enum.Enum):
    """Direction of a trade."""

    BUY = 1
    SELL = -1


class OrderType(enum.Enum):
    """Execution instruction type."""

    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Tick:
    """A single best-bid/ask quote snapshot.

    Attributes:
        timestamp: Nanosecond-resolution event time.
        symbol: Instrument identifier (e.g. "EURUSD").
        bid: Best bid price.
        ask: Best ask price.
        bid_volume: Quoted bid volume (proxy only for retail feeds).
        ask_volume: Quoted ask volume (proxy only for retail feeds).
        source: Originating feed identifier (empty string if unknown).
    """

    timestamp: np.datetime64
    symbol: str
    bid: float
    ask: float
    bid_volume: float = 0.0
    ask_volume: float = 0.0
    source: str = ""


@dataclass(frozen=True, slots=True)
class Bar:
    """An OHLCV aggregate bar for a given timeframe.

    Attributes:
        timestamp: Bar open time (nanosecond resolution).
        symbol: Instrument identifier.
        open: Opening price.
        high: Session high price.
        low: Session low price.
        close: Closing price.
        volume: Tick/trade volume (proxy for retail feeds; real for exchange feeds).
        spread: Representative bid-ask spread for the bar (0.0 if not available).
    """

    timestamp: np.datetime64
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    spread: float = 0.0


@dataclass(frozen=True, slots=True)
class OrderRequest:
    """Instruction to open or modify a position.

    Attributes:
        symbol: Target instrument identifier.
        side: Trade direction.
        quantity: Trade size in broker-native volume units.
        order_type: Execution type — market, limit, or stop.
        price: Limit or stop trigger price; None for market orders.
        sl: Stop-loss price; None if not required.
        tp: Take-profit price; None if not required.
        comment: Arbitrary annotation attached to the order.
    """

    symbol: str
    side: Side
    quantity: float
    order_type: OrderType = OrderType.MARKET
    price: float | None = None
    sl: float | None = None
    tp: float | None = None
    comment: str = ""


@dataclass(frozen=True, slots=True)
class OrderResult:
    """Outcome of a submitted order.

    Attributes:
        order_id: Broker-assigned order identifier.
        fill_price: Actual execution price.
        fill_quantity: Quantity actually filled.
        slippage: Absolute price deviation from requested price.
        commission: Total commission charged.
        success: True if order was fully accepted and filled.
        error_message: Human-readable rejection reason; empty on success.
    """

    order_id: str
    fill_price: float
    fill_quantity: float
    slippage: float
    commission: float
    success: bool
    error_message: str = ""


@dataclass(slots=True)
class Position:
    """Current state of an open position.

    Position is intentionally *mutable* because current_price and
    unrealized_pnl are updated continuously during live trading.

    Attributes:
        symbol: Instrument identifier.
        side: Direction of the position.
        quantity: Position size (lots or contracts).
        entry_price: Average fill price when position was opened.
        current_price: Latest market price for mark-to-market.
        unrealized_pnl: Mark-to-market profit/loss in account currency.
        swap_accumulated: Accumulated overnight financing costs (0 for non-swap instruments).
        margin_used: Collateral reserved for this position.
    """

    symbol: str
    side: Side
    quantity: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    swap_accumulated: float = 0.0
    margin_used: float = 0.0


# ---------------------------------------------------------------------------
# Abstract Base Classes
# ---------------------------------------------------------------------------


class MarketDataProvider(ABC):
    """Source of market data — historical and streaming."""

    @abstractmethod
    async def get_ticks(
        self, symbol: str, start: np.datetime64, end: np.datetime64
    ) -> list[Tick]:
        """Retrieve tick data for a symbol within a time range."""
        ...

    @abstractmethod
    async def get_bars(
        self, symbol: str, timeframe: str, count: int
    ) -> list[Bar]:
        """Retrieve the most recent *count* bars for a symbol at *timeframe*."""
        ...

    @abstractmethod
    async def subscribe_ticks(
        self, symbol: str, callback: Callable[[Tick], None]
    ) -> None:
        """Register *callback* to receive live ticks for *symbol*."""
        ...

    @abstractmethod
    async def get_symbols(self) -> list[str]:
        """Return all available instrument identifiers."""
        ...


class OrderExecutor(ABC):
    """Submits and manages orders with the execution venue."""

    @abstractmethod
    async def submit_order(self, order: OrderRequest) -> OrderResult:
        """Send an order to the venue and return the fill result."""
        ...

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order; returns True if cancellation succeeded."""
        ...

    @abstractmethod
    async def get_open_orders(self) -> list[OrderRequest]:
        """Return all currently pending (unfilled) orders."""
        ...


class PositionManager(ABC):
    """Queries and manages the account's open positions."""

    @abstractmethod
    async def get_positions(self) -> list[Position]:
        """Return all currently open positions."""
        ...

    @abstractmethod
    async def close_position(self, symbol: str) -> OrderResult:
        """Submit a market order to close the position in *symbol*."""
        ...

    @abstractmethod
    async def get_account_equity(self) -> float:
        """Return current account equity in account base currency."""
        ...

    @abstractmethod
    async def get_margin_level(self) -> float:
        """Return current margin level as a percentage."""
        ...
