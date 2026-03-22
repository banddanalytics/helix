"""SimAdapter: simulation adapter for backtesting and CI testing without Windows/MT5.

Provides the same interface as MT5Adapter but uses in-memory synthetic data
and stateful simulated execution.  No ArcticDB dependency in Phase 1 — data
reads return synthetic prices based on the current mid price registered via
``set_price()``.
"""

from __future__ import annotations

import random
import uuid
from collections.abc import Callable

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

# Standard Forex contract size (one lot = 100,000 units of base currency)
_CONTRACT_SIZE: float = 100_000.0

# Pip size for Forex pairs quoted in X.XXXX format
_PIP_SIZE: float = 0.0001


class SimAdapter(MarketDataProvider, OrderExecutor, PositionManager):
    """Stateful simulation adapter providing identical interface to MT5Adapter.

    Decision references:
        D-22: Instant fill at mid price ± half spread
        D-23: Spread cost on every fill (buy at ask, sell at bid)
        D-24: No slippage in Phase 1
        D-25: Stateful — _positions dict, _realized_pnl, _margin_used
        D-26: random.Random(seed) for deterministic behavior
        D-27: Rejection on insufficient margin or invalid lot size
    """

    def __init__(
        self,
        initial_equity: float = 100_000.0,
        spread_pips: float = 1.5,
        seed: int = 42,
    ) -> None:
        self._initial_equity: float = initial_equity
        self._spread_pips: float = spread_pips
        self._rng: random.Random = random.Random(seed)  # D-26: fixed seed
        self._positions: dict[str, Position] = {}
        self._realized_pnl: float = 0.0
        self._margin_used: float = 0.0
        self._current_prices: dict[str, float] = {}  # symbol -> mid price
        self._order_counter: int = 0

    # ------------------------------------------------------------------
    # Price injection (test helper)
    # ------------------------------------------------------------------

    def set_price(self, symbol: str, mid_price: float) -> None:
        """Inject a mid price for *symbol* so tests can control fill prices."""
        self._current_prices[symbol] = mid_price

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _half_spread(self) -> float:
        """Half-spread in price terms (pips * pip_size / 2)."""
        return self._spread_pips * _PIP_SIZE / 2.0

    def _ask(self, symbol: str) -> float:
        return self._current_prices[symbol] + self._half_spread()

    def _bid(self, symbol: str) -> float:
        return self._current_prices[symbol] - self._half_spread()

    def _required_margin(self, symbol: str, quantity: float) -> float:
        """Simple 2% margin requirement per unit of contract value."""
        mid = self._current_prices.get(symbol, 0.0)
        return quantity * _CONTRACT_SIZE * mid * 0.02

    def _current_equity(self) -> float:
        """Compute equity = initial + realized + unrealized PnL."""
        unrealized: float = sum(p.unrealized_pnl for p in self._positions.values())
        return self._initial_equity + self._realized_pnl + unrealized

    def _update_unrealized(self) -> None:
        """Refresh unrealized_pnl on all open positions from current prices."""
        for pos in self._positions.values():
            mid = self._current_prices.get(pos.symbol, pos.entry_price)
            pos.current_price = mid
            if pos.side == Side.BUY:
                pos.unrealized_pnl = (
                    (self._bid(pos.symbol) - pos.entry_price) * pos.quantity * _CONTRACT_SIZE
                )
            else:
                pos.unrealized_pnl = (
                    (pos.entry_price - self._ask(pos.symbol)) * pos.quantity * _CONTRACT_SIZE
                )

    def _gen_order_id(self) -> str:
        """Generate a deterministic order ID using the seeded RNG."""
        self._order_counter += 1
        return f"SIM-{self._order_counter:06d}-{self._rng.randint(10000, 99999)}"

    # ------------------------------------------------------------------
    # MarketDataProvider
    # ------------------------------------------------------------------

    async def get_ticks(
        self,
        symbol: str,
        start: np.datetime64,
        end: np.datetime64,
    ) -> list[Tick]:
        """Return synthetic ticks based on current mid price (Phase 1 in-memory)."""
        if symbol not in self._current_prices:
            return []
        mid = self._current_prices[symbol]
        hs = self._half_spread()
        return [
            Tick(
                timestamp=start,
                symbol=symbol,
                bid=mid - hs,
                ask=mid + hs,
                source="sim",
            )
        ]

    async def get_bars(self, symbol: str, timeframe: str, count: int) -> list[Bar]:
        """Return synthetic bars based on current mid price."""
        if symbol not in self._current_prices:
            return []
        mid = self._current_prices[symbol]
        hs = self._half_spread()
        ts = np.datetime64("now", "ns")
        return [
            Bar(
                timestamp=ts,
                symbol=symbol,
                open=mid,
                high=mid + hs,
                low=mid - hs,
                close=mid,
                spread=self._spread_pips * _PIP_SIZE,
            )
            for _ in range(count)
        ]

    async def subscribe_ticks(self, symbol: str, callback: Callable[[Tick], None]) -> None:
        """No-op in simulation — callbacks must be driven by test logic."""
        pass

    async def get_symbols(self) -> list[str]:
        """Return all symbols for which a price has been registered."""
        return list(self._current_prices.keys())

    # ------------------------------------------------------------------
    # OrderExecutor
    # ------------------------------------------------------------------

    async def submit_order(self, order: OrderRequest) -> OrderResult:
        """Fill order instantly at ask (BUY) or bid (SELL); enforce margin and lot checks."""
        # D-27: lot size validation
        if order.quantity <= 0:
            return OrderResult(
                order_id="",
                fill_price=0.0,
                fill_quantity=0.0,
                slippage=0.0,
                commission=0.0,
                success=False,
                error_message="Invalid lot size: quantity must be > 0",
            )

        # Unknown symbol
        if order.symbol not in self._current_prices:
            return OrderResult(
                order_id="",
                fill_price=0.0,
                fill_quantity=0.0,
                slippage=0.0,
                commission=0.0,
                success=False,
                error_message=f"Unknown symbol: {order.symbol}",
            )

        # D-27: margin check
        required = self._required_margin(order.symbol, order.quantity)
        available = self._current_equity() - self._margin_used
        if required > available:
            return OrderResult(
                order_id="",
                fill_price=0.0,
                fill_quantity=0.0,
                slippage=0.0,
                commission=0.0,
                success=False,
                error_message=(
                    f"Insufficient margin: required {required:.2f}, available {available:.2f}"
                ),
            )

        # D-22 / D-23: fill at ask (BUY) or bid (SELL)
        if order.side == Side.BUY:
            fill_price = self._ask(order.symbol)
        else:
            fill_price = self._bid(order.symbol)

        order_id = self._gen_order_id()
        self._margin_used += required

        # D-25: stateful position — update or open
        if order.symbol in self._positions:
            # Simple overwrite (single-position per symbol in Phase 1)
            pos = self._positions[order.symbol]
            pos.entry_price = fill_price
            pos.side = order.side
            pos.quantity = order.quantity
            pos.margin_used = required
            pos.unrealized_pnl = 0.0
        else:
            self._positions[order.symbol] = Position(
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                entry_price=fill_price,
                current_price=fill_price,
                unrealized_pnl=0.0,
                margin_used=required,
            )

        self._update_unrealized()

        return OrderResult(
            order_id=order_id,
            fill_price=fill_price,
            fill_quantity=order.quantity,
            slippage=0.0,  # D-24: no slippage in Phase 1
            commission=0.0,
            success=True,
        )

    async def cancel_order(self, order_id: str) -> bool:
        """Simulation has no pending orders — always returns False."""
        return False

    async def get_open_orders(self) -> list[OrderRequest]:
        """Simulation fills instantly — no pending orders."""
        return []

    # ------------------------------------------------------------------
    # PositionManager
    # ------------------------------------------------------------------

    async def get_positions(self) -> list[Position]:
        """Return all currently open positions."""
        self._update_unrealized()
        return list(self._positions.values())

    async def close_position(self, symbol: str) -> OrderResult:
        """Close an open position and realize PnL."""
        if symbol not in self._positions:
            return OrderResult(
                order_id="",
                fill_price=0.0,
                fill_quantity=0.0,
                slippage=0.0,
                commission=0.0,
                success=False,
                error_message=f"No open position for {symbol}",
            )

        if symbol not in self._current_prices:
            return OrderResult(
                order_id="",
                fill_price=0.0,
                fill_quantity=0.0,
                slippage=0.0,
                commission=0.0,
                success=False,
                error_message=f"No price available for {symbol}",
            )

        pos = self._positions[symbol]
        self._update_unrealized()

        # Close at bid (BUY → sell out) or ask (SELL → buy back)
        if pos.side == Side.BUY:
            exit_price = self._bid(symbol)
            pnl = (exit_price - pos.entry_price) * pos.quantity * _CONTRACT_SIZE
        else:
            exit_price = self._ask(symbol)
            pnl = (pos.entry_price - exit_price) * pos.quantity * _CONTRACT_SIZE

        self._realized_pnl += pnl
        self._margin_used -= pos.margin_used
        if self._margin_used < 0:
            self._margin_used = 0.0

        order_id = self._gen_order_id()
        del self._positions[symbol]

        return OrderResult(
            order_id=order_id,
            fill_price=exit_price,
            fill_quantity=pos.quantity,
            slippage=0.0,
            commission=0.0,
            success=True,
        )

    async def get_account_equity(self) -> float:
        """Return initial_equity + realized_pnl + unrealized_pnl."""
        self._update_unrealized()
        return self._current_equity()

    async def get_margin_level(self) -> float:
        """Return margin level as a percentage (equity / margin_used * 100)."""
        if self._margin_used <= 0:
            return 100.0
        equity = self._current_equity()
        return (equity / self._margin_used) * 100.0
