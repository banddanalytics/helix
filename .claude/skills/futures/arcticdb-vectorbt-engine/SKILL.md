---
name: arcticdb-vectorbt-engine
description: >
  Design and implement the data engineering layer for MBO tick data storage using ArcticDB
  and vectorized backtesting using VectorBT Pro with Numba JIT compilation. Covers ArcticDB
  library/symbol schema design, column-oriented tick storage, Point-in-Time (PiT) data
  structuring with strict .shift(1) operators to eliminate look-ahead bias, VectorBT Pro
  memory optimization (chunk caching, accumulators, multi-pass loop elimination), and Numba
  JIT C-compilation for signal generation. Use this skill whenever working on: tick data
  storage schemas, ArcticDB configuration, backtesting engine design, VectorBT Pro optimization,
  look-ahead bias prevention, PiT data pipelines, or any task involving the data/backtesting
  layer. Also trigger when the user mentions "ArcticDB", "VectorBT", "tick data", "MBO storage",
  "backtesting", "look-ahead bias", "PiT data", "Numba JIT", or "chunk caching".
---

# ArcticDB & VectorBT Pro Engine Skill

## Purpose

This skill governs the complete data engineering and backtesting pipeline: how MBO tick data
flows from the FIX ingestion layer into ArcticDB, how it's structured for Point-in-Time
correctness, and how VectorBT Pro consumes it for vectorized strategy backtesting at maximum
throughput with zero look-ahead bias.

## ArcticDB Schema Design

### Library Architecture

ArcticDB organizes data as Libraries → Symbols → Versions. The schema maps directly to
the trading system's data hierarchy:

```
Arctic Store (S3-backed or LMDB local)
│
├── Library: "mbo_ticks"
│   ├── Symbol: "6E_CME"  (EUR/USD futures)
│   │   Columns: timestamp(ns), order_id, side, price, qty, action, rpt_seq
│   ├── Symbol: "6J_CME"  (JPY/USD futures)
│   ├── Symbol: "6A_CME"  (AUD/USD futures)
│   └── Symbol: "6N_CME"  (NZD/USD futures)
│
├── Library: "ohlcv_bars"
│   ├── Symbol: "6E_CME_1s"   (1-second bars, derived)
│   ├── Symbol: "6E_CME_1m"   (1-minute bars, derived)
│   └── Symbol: "6E_CME_1h"   (1-hour bars, derived)
│
├── Library: "signals"
│   ├── Symbol: "regime_states"       (HMM regime classifications)
│   ├── Symbol: "cointegration_scores" (VECM z-scores)
│   └── Symbol: "ml_predictions"      (XGBoost/RF outputs)
│
└── Library: "portfolio"
    ├── Symbol: "positions"
    ├── Symbol: "pnl_curve"
    └── Symbol: "risk_metrics"
```

### MBO Tick Schema (Columnar)

```python
import numpy as np

MBO_TICK_DTYPE = {
    'timestamp':   'datetime64[ns]',  # Exchange timestamp, nanosecond precision
    'recv_ts':     'datetime64[ns]',  # Local receive timestamp (for latency measurement)
    'order_id':    'int64',           # CME OrderID (Tag 37)
    'side':        'int8',            # 0=bid, 1=ask
    'price':       'float64',         # Limit price (tick-adjusted)
    'qty':         'int32',           # Order quantity
    'action':      'int8',            # 0=new, 1=modify, 2=delete, 3=trade
    'rpt_seq':     'int64',           # Sequence number for gap detection
    'agg_qty':     'int32',           # Aggregated quantity at level (for MBP reconstruction)
    'num_orders':  'int32',           # Tag 346: number of orders at level
    'price_level': 'int8',            # Tag 1023: 1-10 price level depth
}
```

### Write Path (Tick Ingestion)

```python
import arcticdb as adb

# Initialize Arctic store backed by S3 (production) or LMDB (local dev)
store = adb.Arctic("s3://tick-data-ny4?region=us-east-1")
lib = store.get_library("mbo_ticks", create_if_missing=True)

# Batch write: accumulate ticks in a pre-allocated numpy buffer, flush every N ticks
BATCH_SIZE = 10_000  # Flush threshold

def flush_tick_buffer(symbol: str, buffer: np.ndarray, count: int):
    """Write accumulated ticks to ArcticDB. Uses append mode for time-series."""
    df = pd.DataFrame(buffer[:count])
    df.set_index('timestamp', inplace=True)
    lib.append(symbol, df)  # append, not write — preserves existing data
```

### Read Path (Vectorized Queries)

```python
# Date-range filtered read — ArcticDB uses column pruning + predicate pushdown
from arcticdb import QueryBuilder

qb = QueryBuilder()
qb = qb[qb['timestamp'] >= start_ts]
qb = qb[qb['timestamp'] <= end_ts]

# Read only the columns needed for the specific strategy
df = lib.read(
    "6E_CME",
    query_builder=qb,
    columns=['timestamp', 'price', 'qty', 'side', 'action']
).data
```

## Point-in-Time (PiT) Data Structuring

This is the single most critical data integrity constraint in the entire system. Look-ahead
bias will silently destroy backtest validity and produce unreplicable live results.

### The Iron Rule

> **Every feature, signal, and derived value used at time T must be computed using ONLY
> data available at or before time T-1. No exceptions.**

### Implementation via Shift Operators

```python
# CORRECT: Signal at time T uses data available at T-1
df['signal'] = compute_signal(df['price'].shift(1), df['volume'].shift(1))

# WRONG: This uses data at time T to generate signal at time T (look-ahead)
# df['signal'] = compute_signal(df['price'], df['volume'])

# CORRECT: Rolling statistics use .shift(1) AFTER computation
df['rolling_vol'] = df['returns'].rolling(20).std().shift(1)

# WRONG: Rolling without shift means the window includes the current bar
# df['rolling_vol'] = df['returns'].rolling(20).std()
```

### PiT Validation Framework

```python
def validate_pit_compliance(signal_df: pd.DataFrame, price_df: pd.DataFrame) -> bool:
    """
    Validates that no signal at time T correlates with future price data.
    Uses information coefficient (IC) analysis with temporal offsets.
    """
    # Forward IC should be significant (signal predicts future)
    forward_ic = signal_df['signal'].corr(price_df['returns'].shift(-1))
    
    # Contemporaneous IC should be near-zero if PiT is correct
    contemp_ic = signal_df['signal'].corr(price_df['returns'])
    
    # If contemporaneous IC >> forward IC, look-ahead bias is present
    if abs(contemp_ic) > abs(forward_ic) * 1.5:
        raise LookAheadBiasError(
            f"Contemporaneous IC ({contemp_ic:.4f}) exceeds forward IC ({forward_ic:.4f}). "
            f"Probable look-ahead bias detected."
        )
    return True
```

### PiT for Regime Labels

When the HMM/GARCH pipeline produces regime labels, they must be aligned PiT:

```python
# Regime detection runs on data up to T-1, label is applied at T
regimes = hmm_model.predict(features.shift(1))  # shift input features
df['regime'] = regimes  # This label is now PiT-correct at each row
```

## VectorBT Pro Optimization

### Numba JIT Compilation Strategy

All custom indicators and signal generators must be Numba-compilable. This means:
- No Python objects on the hot path (no dicts, no classes, no string operations)
- Use numpy arrays exclusively
- Decorate with `@njit(cache=True)` for persistent compilation cache
- Use `parallel=True` only for embarrassingly parallel operations (no shared state)

```python
from numba import njit
import numpy as np

@njit(cache=True)
def compute_ema_crossover_signal(close: np.ndarray, fast: int, slow: int) -> np.ndarray:
    """Numba-JIT compiled EMA crossover. No Python overhead."""
    n = len(close)
    fast_ema = np.empty(n)
    slow_ema = np.empty(n)
    signal = np.empty(n, dtype=np.int8)
    
    fast_alpha = 2.0 / (fast + 1)
    slow_alpha = 2.0 / (slow + 1)
    
    fast_ema[0] = close[0]
    slow_ema[0] = close[0]
    signal[0] = 0
    
    for i in range(1, n):
        fast_ema[i] = fast_alpha * close[i] + (1 - fast_alpha) * fast_ema[i - 1]
        slow_ema[i] = slow_alpha * close[i] + (1 - slow_alpha) * slow_ema[i - 1]
        
        # PiT: compare EMAs computed up to i (using close[i]), assign signal at i
        # In live trading, this signal would be acted upon at i+1
        if fast_ema[i] > slow_ema[i]:
            signal[i] = 1  # Long
        elif fast_ema[i] < slow_ema[i]:
            signal[i] = -1  # Short
        else:
            signal[i] = 0  # Flat
    
    return signal
```

### Chunk Caching to Disk

For backtests spanning years of tick data (100GB+), VectorBT Pro's chunk caching prevents
OOM conditions:

```python
import vectorbtpro as vbt

# Configure VectorBT Pro for chunked processing
vbt.settings.chunking['n_chunks'] = 'auto'  # Auto-determine based on available RAM
vbt.settings.caching['register_lazily'] = True
vbt.settings.caching['use_disk'] = True
vbt.settings.caching['disk_path'] = '/tmp/vbt_cache'  # NVMe-backed tmpfs for speed

# Memory budget: leave 20% for OS, allocate 80% to VectorBT
import psutil
available_mb = psutil.virtual_memory().available // (1024 * 1024)
vbt.settings.chunking['chunk_size'] = int(available_mb * 0.8)
```

### Accumulator Pattern (Eliminate Multi-Pass Loops)

Instead of running multiple passes over data (once for signals, once for position sizing,
once for PnL), use VectorBT Pro accumulators that compute everything in a single forward pass:

```python
@njit(cache=True)
def single_pass_backtest(
    close: np.ndarray,
    signal: np.ndarray,
    risk_per_trade: float,
    atr: np.ndarray
) -> tuple:
    """Single-pass backtest accumulator. No multi-pass loops."""
    n = len(close)
    equity = np.empty(n)
    position = np.empty(n, dtype=np.int8)
    pnl = np.empty(n)
    
    equity[0] = 100_000.0  # Initial capital
    position[0] = 0
    pnl[0] = 0.0
    
    for i in range(1, n):
        # Position sizing via ATR (uses shift-1 ATR for PiT)
        if signal[i - 1] != 0 and position[i - 1] == 0:  # Entry signal from T-1
            pos_size = (equity[i - 1] * risk_per_trade) / atr[i - 1]
            position[i] = signal[i - 1]
        elif signal[i - 1] == 0 and position[i - 1] != 0:  # Exit signal
            position[i] = 0
        else:
            position[i] = position[i - 1]
        
        # PnL calculation
        price_change = close[i] - close[i - 1]
        pnl[i] = position[i] * price_change * pos_size if position[i] != 0 else 0.0
        equity[i] = equity[i - 1] + pnl[i]
    
    return equity, position, pnl
```

## Data Pipeline Architecture

```
CME MDP 3.0 (Multicast)
       │
       ▼
[FIX Parser / MBO Decoder]  ←── Solarflare ef_vi zero-copy
       │
       ▼
[Ring Buffer (lock-free)]  ←── Pre-allocated 64K entries
       │
       ├──► [ArcticDB Writer Thread]  ←── Batch flush every 10K ticks
       │
       └──► [Signal Engine (Numba)]  ←── Real-time signal computation
              │
              ▼
       [VectorBT Accumulator]  ←── Single-pass position/PnL tracking
              │
              ▼
       [ZeroMQ → Order Router]  ←── Execution decisions
```

## Key Constraints

- ArcticDB write path must never block the FIX parser — use a separate writer thread
- VectorBT Pro backtest results must be reproducible to the tick level
- All `.shift(1)` operations must be validated by the PiT compliance framework
- Chunk cache directory must be on NVMe (not spinning disk) for acceptable I/O
- Numba compilation cache must persist across restarts (`cache=True`)

Read `prompts/` for tool-specific implementation prompts.
