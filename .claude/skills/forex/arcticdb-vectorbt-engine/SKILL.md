---
name: arcticdb-vectorbt-engine
description: >
  Design and implement the data engineering layer for tick and bar storage using ArcticDB
  and vectorized backtesting using VectorBT Pro with Numba JIT compilation. This skill
  supports TWO data schemas — a Forex schema for Stage A (bid/ask/tick_volume/spread from
  MT5 brokers) and a CME MBO schema for Stage B (order_id/side/price/qty/action from FIX).
  Both schemas share the same ArcticDB library architecture, PiT compliance framework, and
  VectorBT backtesting harness. Covers ArcticDB library/symbol design, column-oriented
  storage, Point-in-Time data structuring with strict .shift(1), VectorBT Pro memory
  optimization (chunk caching, accumulators), and Numba JIT C-compilation. Use this skill
  whenever working on: tick data storage, ArcticDB configuration, backtesting, VectorBT Pro,
  look-ahead bias prevention, PiT data, Numba JIT, or chunk caching. Also trigger when the
  user mentions "ArcticDB", "VectorBT", "tick data", "MBO storage", "Forex ticks",
  "backtesting", "look-ahead bias", "PiT data", "Numba JIT", or "chunk caching".
---

# ArcticDB & VectorBT Pro Engine Skill

## Purpose

This skill governs the complete data engineering and backtesting pipeline across BOTH
stages of the trading system. Data flows from the execution adapter (MT5 in Stage A,
CME FIX in Stage B) into ArcticDB, gets structured for Point-in-Time correctness, and
feeds into VectorBT Pro for vectorized strategy backtesting.

## Two-Stage Schema Design

### Stage A: Forex Schema (from MT5/cTrader brokers)

```python
FOREX_TICK_SCHEMA = {
    'timestamp':    'datetime64[ns]',   # Broker timestamp (millisecond precision from MT5)
    'symbol':       'string',           # "EURUSD", "GBPUSD", etc.
    'bid':          'float64',          # Bid price
    'ask':          'float64',          # Ask price
    'spread':       'float64',          # ask - bid (stored for spread modeling)
    'tick_volume':  'float64',          # Number of price changes (NOT real volume)
    'source':       'string',           # "mt5", "ctrader"
}

FOREX_BAR_SCHEMA = {
    'timestamp':    'datetime64[ns]',
    'symbol':       'string',
    'open':         'float64',
    'high':         'float64',
    'low':          'float64',
    'close':        'float64',
    'tick_volume':  'float64',          # Count of price changes per bar
    'spread_avg':   'float64',          # Average spread during the bar
    'spread_max':   'float64',          # Maximum spread during the bar
    'session':      'int8',             # 0=Asian, 1=London, 2=NY, 3=Overlap
}

SWAP_RATE_SCHEMA = {
    'date':         'datetime64[ns]',   # Date of snapshot
    'symbol':       'string',
    'swap_long':    'float64',          # Points per lot for long positions
    'swap_short':   'float64',          # Points per lot for short positions
    'swap_annual_long_pct':  'float64', # Annualized percentage
    'swap_annual_short_pct': 'float64',
}
```

### Stage B: CME MBO Schema (from FIX/MDP 3.0)

```python
MBO_TICK_SCHEMA = {
    'timestamp':    'datetime64[ns]',   # Exchange timestamp (nanosecond precision)
    'recv_ts':      'datetime64[ns]',   # Local receive timestamp
    'order_id':     'int64',            # CME OrderID (Tag 37)
    'side':         'int8',             # 0=bid, 1=ask
    'price':        'float64',          # Limit price
    'qty':          'int32',            # Order quantity
    'action':       'int8',             # 0=new, 1=modify, 2=delete, 3=trade
    'rpt_seq':      'int64',            # Sequence number for gap detection
    'agg_qty':      'int32',            # Aggregated quantity at level
    'num_orders':   'int32',            # Orders at price level (Tag 346)
    'price_level':  'int8',             # 1-10 depth (Tag 1023)
}
```

### ArcticDB Library Architecture

```
Arctic Store (S3 for production, LMDB for local dev)
│
├── Library: "forex_ticks"            ← Stage A
│   ├── Symbol: "EURUSD"
│   ├── Symbol: "GBPUSD"
│   ├── Symbol: "AUDUSD"
│   ├── Symbol: "USDJPY"
│   ├── Symbol: "AUDJPY"
│   ├── Symbol: "EURGBP"
│   └── Symbol: "NZDUSD"
│
├── Library: "forex_bars"             ← Stage A
│   ├── Symbol: "EURUSD_1m"
│   ├── Symbol: "EURUSD_5m"
│   ├── Symbol: "EURUSD_1h"
│   └── Symbol: "EURUSD_1d"  (... per pair per timeframe)
│
├── Library: "swap_rates"             ← Stage A
│   └── Symbol: "daily_swaps"
│
├── Library: "mbo_ticks"              ← Stage B (created but empty during Stage A)
│   ├── Symbol: "6E_CME"
│   ├── Symbol: "6J_CME"
│   └── ...
│
├── Library: "signals"                ← Both stages
│   ├── Symbol: "regime_states"
│   ├── Symbol: "cointegration_scores"
│   ├── Symbol: "carry_signals"
│   └── Symbol: "ml_predictions"
│
└── Library: "portfolio"              ← Both stages
    ├── Symbol: "positions"
    ├── Symbol: "pnl_curve"
    └── Symbol: "risk_metrics"
```

### Write Path

```python
import arcticdb as adb

# Initialize store
store = adb.Arctic("lmdb://./arctic_data")  # Local dev
# store = adb.Arctic("s3://tick-data?region=us-east-1")  # Production

# Stage A: Write Forex ticks
forex_lib = store.get_library("forex_ticks", create_if_missing=True)

def write_forex_ticks(symbol: str, ticks: list[Tick]):
    df = pd.DataFrame([{
        'timestamp': t.timestamp, 'bid': t.bid, 'ask': t.ask,
        'spread': t.ask - t.bid, 'tick_volume': t.bid_volume,
        'source': t.source
    } for t in ticks])
    df.set_index('timestamp', inplace=True)
    forex_lib.append(symbol, df)

# Stage B: Write CME MBO ticks (same pattern, different schema)
mbo_lib = store.get_library("mbo_ticks", create_if_missing=True)
```

### Read Path (Identical for Both Stages)

```python
from arcticdb import QueryBuilder

def read_price_data(library_name: str, symbol: str,
                    start: np.datetime64, end: np.datetime64,
                    columns: list[str] | None = None) -> pd.DataFrame:
    """
    Unified read function. Works for both Forex and CME data.
    The alpha engines call this — they don't know which library it's reading from.
    """
    lib = store.get_library(library_name)
    qb = QueryBuilder()
    qb = qb[qb['timestamp'] >= start]
    qb = qb[qb['timestamp'] <= end]

    result = lib.read(symbol, query_builder=qb, columns=columns)
    return result.data
```

## Point-in-Time (PiT) Data Structuring

### The Iron Rule (Applies to BOTH Stages)

> **Every feature, signal, and derived value used at time T must be computed using ONLY
> data available at or before time T-1. No exceptions. This rule is identical whether
> the underlying data is Forex ticks or CME MBO ticks.**

### Implementation via Shift Operators

```python
# CORRECT: Signal at time T uses data from T-1
df['signal'] = compute_signal(df['close'].shift(1), df['volume'].shift(1))

# WRONG: Uses current bar data to generate current bar signal
# df['signal'] = compute_signal(df['close'], df['volume'])

# CORRECT: Rolling window with shift AFTER computation
df['rolling_vol'] = df['returns'].rolling(20).std().shift(1)

# WRONG: Rolling without shift — window includes current bar
# df['rolling_vol'] = df['returns'].rolling(20).std()
```

### PiT Validation Framework

```python
def validate_pit_compliance(signal_df: pd.DataFrame,
                            price_df: pd.DataFrame) -> bool:
    """
    Validates no signal at time T correlates with current price data.
    Uses information coefficient (IC) analysis.
    Works for BOTH Forex and futures signal data.
    """
    forward_ic = signal_df['signal'].corr(price_df['returns'].shift(-1))
    contemp_ic = signal_df['signal'].corr(price_df['returns'])

    if abs(contemp_ic) > abs(forward_ic) * 1.5:
        raise LookAheadBiasError(
            f"Contemporaneous IC ({contemp_ic:.4f}) exceeds forward IC "
            f"({forward_ic:.4f}). Probable look-ahead bias."
        )
    return True
```

## VectorBT Pro Optimization

### Numba JIT Compilation (Identical for Both Stages)

All custom indicators must be Numba-compilable:
- No Python objects on the hot path
- Use numpy arrays exclusively
- `@njit(cache=True)` for persistent compilation cache
- `parallel=True` only for embarrassingly parallel operations

```python
from numba import njit
import numpy as np

@njit(cache=True)
def single_pass_backtest(
    close: np.ndarray,
    signal: np.ndarray,
    risk_per_trade: float,
    atr: np.ndarray,
    spread_cost: np.ndarray  # Stage A: variable spread; Stage B: zeros
) -> tuple:
    """
    Single-pass backtest accumulator. No multi-pass loops.
    The spread_cost array makes this work for BOTH Forex and futures:
    - Forex: spread_cost[i] = median broker spread at bar i
    - Futures: spread_cost[i] = 0 (exchange fees handled separately)
    """
    n = len(close)
    equity = np.empty(n)
    position = np.empty(n, dtype=np.int8)
    pnl = np.empty(n)

    equity[0] = 100_000.0
    position[0] = 0
    pnl[0] = 0.0
    pos_size = 0.0

    for i in range(1, n):
        if signal[i-1] != 0 and position[i-1] == 0:
            pos_size = (equity[i-1] * risk_per_trade) / max(atr[i-1], 1e-10)
            position[i] = signal[i-1]
            # Deduct entry spread cost
            pnl[i] = -spread_cost[i] * pos_size
        elif signal[i-1] == 0 and position[i-1] != 0:
            position[i] = 0
            # Deduct exit spread cost
            pnl[i] = position[i-1] * (close[i] - close[i-1]) * pos_size \
                      - spread_cost[i] * pos_size
            pos_size = 0.0
        else:
            position[i] = position[i-1]
            pnl[i] = position[i] * (close[i] - close[i-1]) * pos_size \
                      if position[i] != 0 else 0.0

        equity[i] = equity[i-1] + pnl[i]

    return equity, position, pnl
```

### Chunk Caching to Disk

```python
import vectorbtpro as vbt

# Configure VectorBT Pro for chunked processing (same for both stages)
vbt.settings.chunking['n_chunks'] = 'auto'
vbt.settings.caching['register_lazily'] = True
vbt.settings.caching['use_disk'] = True
vbt.settings.caching['disk_path'] = '/tmp/vbt_cache'

import psutil
available_mb = psutil.virtual_memory().available // (1024 * 1024)
vbt.settings.chunking['chunk_size'] = int(available_mb * 0.8)
```

## Data Pipeline (Stage A vs Stage B)

```
STAGE A (Forex):
MT5 Broker ──[ZMQ Bridge]──► Linux Consumer ──► ArcticDB (forex_ticks, forex_bars)
                                                     │
                                                     ▼
                                              Signal Engines (Numba)
                                                     │
                                                     ▼
                                              VectorBT Accumulator
                                                     │
                                                     ▼
                                              Execution Adapter (MT5)

STAGE B (Futures):
CME MDP 3.0 ──[FIX Parser]──► Ring Buffer ──► ArcticDB (mbo_ticks)
                                                     │
                                                     ▼
                                              Signal Engines (Numba)
                                                     │
                                                     ▼
                                              VectorBT Accumulator
                                                     │
                                                     ▼
                                              Execution Adapter (CME)
```

## Implementation Structure

```
./src/data/
  arctic_store.py         (ArcticDB initialization, library management)
  schemas.py              (BOTH schemas: Forex + MBO)
  forex_writer.py         (Stage A: write Forex ticks/bars/swaps)
  mbo_writer.py           (Stage B: write CME MBO ticks — stub during Stage A)
  reader.py               (Unified read — works for both)
  pit_manager.py          (PiT validation framework — identical for both)
  snapshot_scheduler.py   (ArcticDB snapshot management)
./src/backtest/
  engine.py               (VectorBT backtest runner)
  accumulators.py         (Numba single-pass backtester with spread_cost param)
  numba_kernels.py        (Shared Numba-compiled indicators)
  warmup.py               (JIT compilation warmup service)
  config.py               (Chunk caching, memory settings)
./tests/data/
  test_arctic_store.py
  test_forex_writer.py
  test_pit_integrity.py
  test_backtest.py
```
