---
name: forex-broker-adapter
description: >
  Implement the retail Forex broker connectivity layer for the pre-futures capital building
  phase (Stage A, months 1-12). Covers MetaTrader 5 Python API integration, cTrader Open API
  as alternative, the execution abstraction layer that enables clean Forex→Futures migration,
  broker data normalization into ArcticDB schema, swap rate extraction for carry signals,
  variable spread modeling for CVaR adjustment, Forex lot sizing from Kelly fractions, and
  the ZeroMQ bridge pattern for running MT5 on Windows while alpha engines run on Linux.
  Use this skill whenever working on: MT5 Python connectivity, cTrader integration, retail
  Forex execution, broker data ingestion, swap rate analysis, spread cost modeling, lot sizing,
  pip value calculation, or any task involving the retail Forex execution layer. Also trigger
  when the user mentions "MT5", "MetaTrader", "cTrader", "Forex broker", "swap rates",
  "spread cost", "retail execution", "pip value", "lot sizing", or "broker API".
---

# Forex Broker Adapter Skill

## Purpose

This skill defines the connectivity, data ingestion, and execution layer for trading
against a retail Forex broker (MT5 or cTrader) during Stage A (6-12 months of capital
building before transitioning to CME futures). The architecture centers on a clean
abstraction boundary so the broker-specific layer can be swapped for the CME FIX adapter
(Stage B) without modifying any alpha engine, risk engine, or dashboard code.

## Two-Stage System Context

```
STAGE A (Months 1-12): Retail Forex
  - Execution via MT5 broker on Windows VPS
  - Data from MT5 tick/bar API (no genuine order book)
  - Alpha: regime detection, cointegration, carry (from swaps), price momentum ML
  - Infrastructure: single VPS + Nairobi dashboard
  - Goal: validate strategies, build capital

STAGE B (Month 12+): CME Currency Futures
  - Execution via FIX iLink 3.0 at NY4/LD4 co-location
  - Data from CME MDP 3.0 MBO multicast (genuine order book)
  - Alpha: all Stage A strategies + MBO orderflow features (OFI, VPIN, iceberg)
  - Infrastructure: NY4/LD4 co-lo + Nairobi dashboard
  - Goal: institutional-grade execution, lower costs
```

## Architecture: The Execution Abstraction Layer

Alpha engines, risk management, and the dashboard NEVER know whether they are trading
Forex or futures. They interact only with abstract interfaces:

```
┌───────────────────────────────────────────────────────────┐
│  Alpha Engines (regime, cointegration, carry, momentum)   │
│  Risk Engine (CVaR, Kelly, ECT)                           │
│  Dashboard (React Module Federation)                      │
└──────────────────────┬────────────────────────────────────┘
                       │  Uses abstract interfaces only
                       ▼
┌───────────────────────────────────────────────────────────┐
│              Execution Abstraction Layer                   │
│  MarketDataProvider  │  OrderExecutor  │  PositionManager  │
└──────────┬───────────┴────────┬────────┴──────────┬───────┘
           │                    │                    │
    ┌──────▼──────┐      ┌─────▼──────┐      ┌─────▼──────┐
    │  MT5Adapter  │      │ CMEAdapter │      │ SimAdapter │
    │  (Stage A)   │      │ (Stage B)  │      │ (Testing)  │
    └─────────────┘      └────────────┘      └────────────┘
```

### Abstract Interfaces (Market-Agnostic)

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
import numpy as np

class Side(Enum):
    BUY = 1
    SELL = -1

class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"

@dataclass
class Tick:
    """Universal tick representation. Works for Forex and futures."""
    timestamp: np.datetime64   # Nanosecond precision
    symbol: str                # "EURUSD" (Forex) or "6E" (futures)
    bid: float
    ask: float
    bid_volume: float          # Indicative in Forex; real in futures
    ask_volume: float          # 0 in MT5; real in futures
    source: str                # "mt5", "cme_mdp", "ctrader", "sim"

@dataclass
class Bar:
    """Universal OHLCV bar. Works for Forex and futures."""
    timestamp: np.datetime64
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float              # Tick volume in Forex; real volume in futures
    spread: float              # Average spread during bar (Forex); 0 for futures

@dataclass
class OrderRequest:
    symbol: str
    side: Side
    quantity: float            # Lots for Forex; contracts for futures
    order_type: OrderType
    price: float | None        # None for market orders
    stop_loss: float | None
    take_profit: float | None
    comment: str

@dataclass
class OrderResult:
    order_id: str
    fill_price: float
    fill_quantity: float
    slippage: float            # Actual fill vs requested price
    commission: float
    timestamp: np.datetime64
    success: bool
    error_message: str | None

@dataclass
class Position:
    symbol: str
    side: Side
    quantity: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    swap_accumulated: float    # Forex: overnight rollover; Futures: 0
    margin_used: float

class MarketDataProvider(ABC):
    """Abstract interface for market data — broker agnostic."""
    @abstractmethod
    async def get_ticks(self, symbol: str, start: np.datetime64,
                        end: np.datetime64) -> list[Tick]: ...
    @abstractmethod
    async def get_bars(self, symbol: str, timeframe: str,
                       count: int) -> list[Bar]: ...
    @abstractmethod
    async def subscribe_ticks(self, symbol: str,
                              callback: callable) -> None: ...
    @abstractmethod
    async def get_symbols(self) -> list[str]: ...

class OrderExecutor(ABC):
    """Abstract interface for order execution — broker agnostic."""
    @abstractmethod
    async def submit_order(self, order: OrderRequest) -> OrderResult: ...
    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool: ...
    @abstractmethod
    async def get_open_orders(self) -> list[OrderRequest]: ...

class PositionManager(ABC):
    """Abstract interface for position management — broker agnostic."""
    @abstractmethod
    async def get_positions(self) -> list[Position]: ...
    @abstractmethod
    async def close_position(self, symbol: str) -> OrderResult: ...
    @abstractmethod
    async def get_account_equity(self) -> float: ...
    @abstractmethod
    async def get_margin_level(self) -> float: ...
```

### MT5 Adapter Implementation

```python
import MetaTrader5 as mt5

class MT5Adapter(MarketDataProvider, OrderExecutor, PositionManager):
    """
    MetaTrader 5 concrete implementation.
    
    Platform constraint: MT5 Python API uses COM interop — Windows only.
    For Linux alpha engines, use the ZeroMQ bridge pattern (see below).
    """
    
    def __init__(self, account: int, password: str, server: str,
                 mt5_path: str | None = None):
        self.account = account
        self.password = password
        self.server = server
        self.mt5_path = mt5_path
    
    def connect(self) -> bool:
        if not mt5.initialize(path=self.mt5_path):
            raise ConnectionError(f"MT5 init failed: {mt5.last_error()}")
        if not mt5.login(self.account, self.password, self.server):
            raise ConnectionError(f"MT5 login failed: {mt5.last_error()}")
        return True
    
    async def get_ticks(self, symbol, start, end):
        ticks = mt5.copy_ticks_range(
            symbol,
            start.astype('datetime64[s]').astype('int'),
            end.astype('datetime64[s]').astype('int'),
            mt5.COPY_TICKS_ALL
        )
        if ticks is None:
            return []
        return [
            Tick(
                timestamp=np.datetime64(int(t['time_msc']), 'ms'),
                symbol=symbol, bid=t['bid'], ask=t['ask'],
                bid_volume=t.get('volume_real', 0.0),
                ask_volume=0.0,  # MT5 does not provide separate ask volume
                source="mt5"
            ) for t in ticks
        ]
    
    async def get_bars(self, symbol, timeframe, count):
        tf_map = {
            "1m": mt5.TIMEFRAME_M1, "5m": mt5.TIMEFRAME_M5,
            "15m": mt5.TIMEFRAME_M15, "30m": mt5.TIMEFRAME_M30,
            "1h": mt5.TIMEFRAME_H1, "4h": mt5.TIMEFRAME_H4,
            "1d": mt5.TIMEFRAME_D1, "1w": mt5.TIMEFRAME_W1,
        }
        rates = mt5.copy_rates_from_pos(symbol, tf_map[timeframe], 0, count)
        if rates is None:
            return []
        info = mt5.symbol_info(symbol)
        return [
            Bar(
                timestamp=np.datetime64(int(r['time']), 's'),
                symbol=symbol, open=r['open'], high=r['high'],
                low=r['low'], close=r['close'],
                volume=r['tick_volume'],
                spread=r['spread'] * info.point
            ) for r in rates
        ]
    
    async def submit_order(self, order):
        info = mt5.symbol_info(order.symbol)
        if info is None:
            return OrderResult("", 0, 0, 0, 0, np.datetime64('now'),
                               False, f"Symbol {order.symbol} not found")
        tick = mt5.symbol_info_tick(order.symbol)
        price = tick.ask if order.side == Side.BUY else tick.bid
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": order.symbol,
            "volume": order.quantity,
            "type": mt5.ORDER_TYPE_BUY if order.side == Side.BUY
                    else mt5.ORDER_TYPE_SELL,
            "price": order.price or price,
            "deviation": 20,
            "magic": 100001,
            "comment": order.comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        if order.stop_loss:
            request["sl"] = order.stop_loss
        if order.take_profit:
            request["tp"] = order.take_profit
        
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return OrderResult("", 0, 0, 0, 0, np.datetime64('now'),
                               False, f"Failed: {result.comment}")
        return OrderResult(
            str(result.order), result.price, result.volume,
            abs(result.price - request["price"]), result.commission,
            np.datetime64('now'), True, None
        )
    
    async def get_positions(self):
        positions = mt5.positions_get()
        if not positions:
            return []
        return [
            Position(
                symbol=p.symbol,
                side=Side.BUY if p.type == 0 else Side.SELL,
                quantity=p.volume,
                entry_price=p.price_open,
                current_price=p.price_current,
                unrealized_pnl=p.profit,
                swap_accumulated=p.swap,
                margin_used=p.volume * mt5.symbol_info(p.symbol).margin_initial
            ) for p in positions
        ]
    
    async def close_position(self, symbol):
        positions = mt5.positions_get(symbol=symbol)
        if not positions:
            return OrderResult("", 0, 0, 0, 0, np.datetime64('now'),
                               False, "No position found")
        p = positions[0]
        close_side = Side.SELL if p.type == 0 else Side.BUY
        return await self.submit_order(OrderRequest(
            symbol=symbol, side=close_side, quantity=p.volume,
            order_type=OrderType.MARKET, price=None,
            stop_loss=None, take_profit=None, comment="close"
        ))
    
    async def get_account_equity(self):
        return mt5.account_info().equity
    
    async def get_margin_level(self):
        info = mt5.account_info()
        return info.margin_level if info.margin_level else 0.0
    
    async def get_symbols(self):
        symbols = mt5.symbols_get()
        return [s.name for s in symbols if s.visible]
    
    async def subscribe_ticks(self, symbol, callback):
        # MT5 does not have native streaming — poll at 10ms intervals
        import asyncio
        while True:
            tick = mt5.symbol_info_tick(symbol)
            if tick:
                await callback(Tick(
                    timestamp=np.datetime64(int(tick.time_msc), 'ms'),
                    symbol=symbol, bid=tick.bid, ask=tick.ask,
                    bid_volume=tick.volume_real, ask_volume=0.0, source="mt5"
                ))
            await asyncio.sleep(0.01)  # 10ms poll
```

### Simulation Adapter (for backtesting without MT5)

```python
class SimAdapter(MarketDataProvider, OrderExecutor, PositionManager):
    """
    Simulation adapter for backtesting and testing on any platform.
    Reads data from ArcticDB, simulates execution with configurable
    spread and slippage models.
    """
    def __init__(self, arctic_store, spread_model, slippage_bps=1.0):
        self.store = arctic_store
        self.spread_model = spread_model
        self.slippage_bps = slippage_bps
        self.positions = {}
        self.equity = 100_000.0
    
    # ... implements all abstract methods using ArcticDB data
    # Used for: backtesting, CI testing, strategy development on Linux/Mac
```

## Forex-Specific Components

### Variable Spread Model

```python
@dataclass
class SpreadModel:
    """
    Track and model variable broker spreads.
    
    Retail Forex spreads are NOT fixed — they widen during:
    - News events (NFP, FOMC, ECB)
    - Low liquidity (Asian session for EUR pairs)
    - Market stress (risk-off events)
    
    This model tracks empirical spread distribution and adjusts signal
    evaluation and CVaR computation accordingly.
    """
    history: list[float]
    lookback: int = 5000
    
    def update(self, bid: float, ask: float):
        self.history.append(ask - bid)
        if len(self.history) > self.lookback:
            self.history.pop(0)
    
    @property
    def median(self) -> float:
        return float(np.median(self.history)) if self.history else 0.0
    
    @property
    def p95(self) -> float:
        """95th percentile — worst-case cost for risk calculations."""
        return float(np.percentile(self.history, 95)) if self.history else 0.0
    
    @property
    def volatility(self) -> float:
        """Spread variability — high = unreliable execution environment."""
        return float(np.std(self.history)) if self.history else 0.0
    
    def cost_adjusted_signal(self, raw_signal: float,
                              expected_holding_bars: int,
                              avg_bar_range: float) -> float:
        """
        Attenuate signal by expected spread cost.
        
        A signal must overcome round-trip spread to be profitable.
        If cost exceeds 50% of expected profit, suppress the signal.
        """
        expected_move = abs(raw_signal) * avg_bar_range * expected_holding_bars
        round_trip_cost = 2 * self.median
        if expected_move == 0:
            return 0.0
        cost_ratio = round_trip_cost / expected_move
        if cost_ratio > 0.5:
            return 0.0
        return raw_signal * (1 - cost_ratio)
```

### Swap Rate Extraction (Carry Signal Source)

```python
def get_swap_rates(symbol: str) -> dict:
    """
    Extract overnight swap rates from MT5 for carry signal.
    
    In Stage A (Forex), the carry signal comes from broker swap rates.
    In Stage B (Futures), it comes from futures term structure.
    The alpha engine receives a normalized carry_signal float either way.
    """
    info = mt5.symbol_info(symbol)
    tick = mt5.symbol_info_tick(symbol)
    mid = (tick.bid + tick.ask) / 2
    
    swap_long_annual = (info.swap_long * info.point * 365) / mid * 100
    swap_short_annual = (info.swap_short * info.point * 365) / mid * 100
    
    return {
        'symbol': symbol,
        'swap_long_annual_pct': swap_long_annual,
        'swap_short_annual_pct': swap_short_annual,
        'net_carry_signal': swap_long_annual - abs(swap_short_annual),
        'swap_mode': info.swap_mode,
        'triple_swap_day': 3,  # Wednesday for most brokers
    }
```

### Forex Lot Sizing (Kelly → Lots)

```python
def kelly_to_lots(equity: float, kelly_fraction: float,
                  stop_loss_pips: float, symbol: str,
                  account_currency: str = "USD") -> float:
    """
    Convert Kelly Criterion fraction to MT5 lot size.
    
    risk_amount = equity × kelly_fraction
    lot_size = risk_amount / (stop_loss_pips × pip_value_per_lot)
    
    Then round to broker's volume_step and clamp to min/max.
    """
    info = mt5.symbol_info(symbol)
    pip_size = info.point * 10  # 5-digit broker: 1 pip = 10 points
    pip_value = info.trade_contract_size * pip_size
    
    # Currency conversion if profit currency ≠ account currency
    if info.currency_profit != account_currency:
        conv = f"{info.currency_profit}{account_currency}"
        conv_tick = mt5.symbol_info_tick(conv)
        if conv_tick:
            pip_value *= conv_tick.bid
    
    risk_amount = equity * kelly_fraction
    lots = risk_amount / (stop_loss_pips * pip_value)
    
    # Round to broker constraints
    step = info.volume_step
    lots = max(info.volume_min, min(info.volume_max,
               round(lots / step) * step))
    return lots
```

### ZeroMQ Bridge (Windows MT5 ↔ Linux Alpha Engines)

```
MT5 Python API is Windows-only (COM interop). The bridge pattern:

[Windows VPS near broker]                 [Linux server / Nairobi]
MT5 Terminal + Python script              Alpha engines + ArcticDB + Dashboard
  │                                         │
  ├── ZMQ PUB (tcp://*:5556) ──ticks──►    ZMQ SUB
  ├── ZMQ PUB (tcp://*:5557) ──bars───►    ZMQ SUB  
  ├── ZMQ PULL (tcp://*:5558) ◄─orders──   ZMQ PUSH
  └── ZMQ PUSH (tcp://*:5559) ──fills──►   ZMQ PULL
  
  Connected via WireGuard VPN tunnel
  MessagePack serialization for efficiency
```

## Data Considerations for Forex

### Tick Volume vs Real Volume

MT5 provides `tick_volume` (count of price changes per bar), NOT real traded volume.
- Correlation with real volume: ~0.85 (usable as activity proxy)
- CANNOT be used for: VPIN, volume-weighted anything assuming real flow
- CAN be used for: relative volume spikes, session activity profiling

### No Genuine Order Book

What MT5 shows as "market depth" is the broker's internal aggregated liquidity.
There is no queue priority, no individual order identification, no MBO data.
- Do NOT implement: OFI, VPIN, iceberg detection, depth imbalance
- Do implement: price-based momentum, volatility features, session structure

### Broker Data Quality Issues

- Weekend gaps (Friday close → Sunday open)
- Inconsistent timestamps across brokers
- Spread spikes during rollover (00:00 UTC)
- Missing ticks during server restarts
- Different number of decimal places (4-digit vs 5-digit brokers)

## Migration Checklist: Stage A → Stage B

When transitioning to CME futures (after 6-12 months):

1. ☐ Replace `MT5Adapter` with `CMEAdapter` (same abstract interfaces)
2. ☐ Switch ArcticDB data source from Forex ticks to CME MBO ticks
3. ☐ Replace swap-based carry with futures term structure carry
4. ☐ Enable MBO features (OFI, VPIN) in ML momentum engine
5. ☐ Replace lot sizing with contract sizing
6. ☐ Remove spread cost model (exchange fees are deterministic)
7. ☐ Deploy to NY4/LD4 co-location
8. ☐ Switch NATS from VPS→Nairobi to NY4→Nairobi
9. ☐ All alpha/risk/dashboard code: ZERO changes required

## Implementation Structure

```
./src/execution/
  abstract.py           (ABC interfaces, dataclasses — NEVER changes)
  mt5_adapter.py        (Stage A: MetaTrader 5 implementation)
  cme_adapter.py        (Stage B: CME iLink 3.0 — stub during Stage A)
  sim_adapter.py        (Testing: simulation from ArcticDB data)
  spread_model.py       (Forex spread tracking and cost adjustment)
  swap_rates.py         (Carry signal from broker swaps)
  lot_sizing.py         (Kelly fraction → Forex lots)
  bridge/
    windows_publisher.py (Windows-side ZMQ tick/bar publisher)
    linux_consumer.py    (Linux-side ZMQ subscriber)
    message_schemas.py   (MessagePack schemas)
  tests/
    test_abstract.py     (interface contract tests)
    test_mt5_adapter.py  (mocked MT5 API tests)
    test_sim_adapter.py  (simulation round-trip tests)
    test_spread_model.py
    test_lot_sizing.py
```
