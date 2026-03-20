# PHASE 2: Data Engineering — ArcticDB Storage and VectorBT Backtesting

**Duration:** 2-3 weeks
**Dependencies:** Phase 1 (execution abstraction for SimAdapter data feed, CI/CD pipeline)
**Skills Used:** `arcticdb-vectorbt-engine`

Phase 2 builds the data layer that all alpha engines consume. It establishes ArcticDB as the tick and bar data store with both Forex and (stubbed) MBO schemas, implements Point-in-Time data integrity, and configures VectorBT Pro for vectorized backtesting with Numba JIT compilation.

**Read:** `SKILL.md: arcticdb-vectorbt-engine`, all sections.

---

## Task 2.1 — Initialize ArcticDB Store with Dual Schemas

**Tool:** Claude Code
**Skill Reference:** `arcticdb-vectorbt-engine > Two-Stage Schema Design, ArcticDB Library Architecture`

Initialize the ArcticDB store with the complete library structure for both stages.

**Stage A libraries (active now):**

| Library | Schema | Purpose |
|---------|--------|---------|
| `forex_ticks` | timestamp(ns), symbol, bid, ask, spread, tick_volume, source | Raw tick storage |
| `forex_bars` | timestamp(ns), symbol, OHLCV, tick_volume, spread_avg, spread_max, session | Aggregated bars |
| `swap_rates` | date, symbol, swap_long, swap_short, annual_long_pct, annual_short_pct | Daily swap snapshots |

**Stage B libraries (created but empty during Stage A):**

| Library | Schema | Purpose |
|---------|--------|---------|
| `mbo_ticks` | timestamp(ns), recv_ts, order_id, side, price, qty, action, rpt_seq, agg_qty, num_orders, price_level | CME MBO tick data |

**Shared libraries (both stages):**

| Library | Symbols | Purpose |
|---------|---------|---------|
| `signals` | regime_states, cointegration_scores, carry_signals, ml_predictions | Alpha engine outputs |
| `portfolio` | positions, pnl_curve, risk_metrics | Portfolio tracking |

**Backend configuration:**

```python
import arcticdb as adb

# Local development (LMDB)
store = adb.Arctic("lmdb://./arctic_data")

# Production (S3)
# store = adb.Arctic("s3s://s3.us-east-1.amazonaws.com:tick-data-bucket?aws_auth=true")
```

**Admin CLI tool:**

```bash
python -m src.data.admin_cli list-libraries
python -m src.data.admin_cli list-symbols forex_ticks
python -m src.data.admin_cli schema forex_ticks EURUSD
python -m src.data.admin_cli compact forex_ticks  # Merge small appended chunks
```

**Output Files:**

```
src/data/__init__.py
src/data/arctic_store.py      # Store initialization, library management
src/data/schemas.py            # Both Forex and MBO schema definitions
src/data/admin_cli.py          # Administrative CLI tool
tests/data/test_arctic_store.py
```

**Validation:**

- [ ] ArcticDB initializes with all 6 libraries (forex_ticks, forex_bars, swap_rates, mbo_ticks, signals, portfolio)
- [ ] Write→read round-trip preserves all columns and dtypes for Forex tick schema
- [ ] Write→read round-trip preserves all columns and dtypes for MBO tick schema
- [ ] Admin CLI `list-libraries` returns all 6 libraries
- [ ] LMDB backend creates valid database files in `./arctic_data/`

---

## Task 2.2 — Build Forex Data Ingestion Pipeline

**Tool:** Cursor
**Skill Reference:** `arcticdb-vectorbt-engine > Write Path`, `forex-broker-adapter > Forex-Specific Data Considerations`

Build the data writer that consumes Tick and Bar dataclasses from the execution abstraction layer and writes them to ArcticDB.

**Tick writer (`forex_writer.py`):**
- Batches incoming ticks in a pre-allocated buffer
- Flushes every 10,000 ticks OR every 1 second, whichever comes first
- Uses `lib.append(symbol, df)` — never `write()` which overwrites
- Runs on a dedicated thread to never block the execution adapter

**Bar aggregator (`bar_aggregator.py`):**
- Aggregates ticks into configurable timeframes: 1m, 5m, 15m, 1h, 4h, 1d
- Computes OHLCV from tick stream
- Tags each bar with session label:
  - `0` = Asian (00:00-08:00 UTC)
  - `1` = London (08:00-13:00 UTC)
  - `2` = Overlap (13:00-16:00 UTC)
  - `3` = New York (16:00-21:00 UTC)
- Computes `spread_avg` and `spread_max` per bar

**Swap writer (`swap_writer.py`):**
- Runs daily at 00:05 UTC via scheduler
- Calls `get_swap_rates()` for all configured symbols
- Appends to `swap_rates` library

**Data quality handling:**
- Weekend gap detection (Friday 22:00 → Sunday 22:00 UTC) — flag, do not fill
- Spread spike filtering during rollover (00:00 UTC) — log but do not discard
- Duplicate tick detection via timestamp deduplication
- Missing data flagging (gap > 2× expected tick interval)

**Output Files:**

```
src/data/forex_writer.py
src/data/bar_aggregator.py
src/data/swap_writer.py
tests/data/test_forex_writer.py
tests/data/test_bar_aggregator.py
tests/data/test_swap_writer.py
```

**Validation:**

- [ ] 10,000 ticks written in batch mode match individual reads
- [ ] 1-minute bars computed from ticks match expected OHLCV values
- [ ] Session tagging correctly labels bars by UTC hour ranges
- [ ] Weekend gaps detected and flagged in data quality report
- [ ] Duplicate ticks filtered (same timestamp + same bid/ask = deduplicated)
- [ ] Spread spike at 00:00 UTC logged but retained in data

---

## Task 2.3 — Implement Point-in-Time Data Manager

**Tool:** Cursor
**Skill Reference:** `arcticdb-vectorbt-engine > Point-in-Time (PiT) Data Structuring`

Build the PiT manager that enforces temporal integrity across all data access.

**Module provides:**

1. **`pit_read(library, symbol, as_of_timestamp)`** — Reads data up to and including `as_of_timestamp` using ArcticDB's native date range filtering. Ensures no future data leaks through.

2. **`create_snapshot(name)`** — Freezes the entire data universe with `lib.snapshot('eod_YYYYMMDD')` for reproducible backtests. Every backtest evaluation date should have a corresponding snapshot.

3. **`validate_pit_compliance(signal_df, price_df)`** — Checks signals for look-ahead bias using IC analysis:
   ```
   forward_ic = signal.corr(returns.shift(-1))      # Should be significant
   contemp_ic = signal.corr(returns)                  # Should be near zero
   if abs(contemp_ic) > abs(forward_ic) * 1.5 → VIOLATION
   ```

4. **`shift_features(df, columns, periods=1)`** — Applies `.shift(1)` to specified columns with validation that no unshifted price/volume columns remain in signal generation code.

**The five look-ahead bias vectors to prevent:**

| Bias Type | Prevention Method |
|-----------|------------------|
| Reporting lag | Index by `report_date` not `reference_date` |
| Data revision overwriting | Store all revisions via ArcticDB versioning |
| Survivorship bias | Maintain PiT index composition snapshots |
| Backfill contamination | Filter by `knowledge_time <= as_of_date` |
| Same-bar execution | Enforce T+1 execution delay minimum |

**Output Files:**

```
src/data/pit_manager.py
src/data/snapshot_scheduler.py
tests/data/test_pit_integrity.py
```

**Validation:**

- [ ] `pit_read` returns data only up to `as_of_timestamp` (no future data)
- [ ] Snapshot at T, write new data after T, `pit_read(as_of=snapshot)` returns pre-T data only
- [ ] `validate_pit_compliance` raises `LookAheadBiasError` on contaminated signals
- [ ] `shift_features` correctly shifts all specified columns by 1 period
- [ ] Integration test: signal generated with `.shift(1)` passes PiT validation; signal without `.shift(1)` fails

---

## Task 2.4 — Configure VectorBT Pro and Numba JIT Pipeline

**Tool:** Claude Code
**Skill Reference:** `arcticdb-vectorbt-engine > VectorBT Pro Optimization, Numba JIT Compilation Strategy`

**VectorBT Pro configuration:**

```python
import vectorbtpro as vbt
import psutil

vbt.settings.chunking['n_chunks'] = 'auto'
vbt.settings.caching['register_lazily'] = True
vbt.settings.caching['use_disk'] = True
vbt.settings.caching['disk_path'] = '/tmp/vbt_cache'

available_mb = psutil.virtual_memory().available // (1024 * 1024)
vbt.settings.chunking['chunk_size'] = int(available_mb * 0.8)
```

**Single-pass backtest accumulator with spread_cost parameter:**

```python
@njit(cache=True)
def single_pass_backtest(
    close: np.ndarray,
    signal: np.ndarray,      # 1=long, -1=short, 0=flat
    risk_per_trade: float,
    atr: np.ndarray,
    spread_cost: np.ndarray  # Stage A: variable spread; Stage B: zeros
) -> tuple:
    """
    Computes equity curve, position array, and PnL in one forward pass.
    No multi-pass loops. spread_cost makes this work for BOTH stages.
    """
```

The `spread_cost` parameter is the key dual-stage design element:
- **Stage A (Forex):** `spread_cost[i] = median_broker_spread_at_bar_i` from SpreadModel
- **Stage B (Futures):** `spread_cost[i] = 0.0` (exchange fees handled separately as fixed commission)

**BacktestRunner class:**
1. Reads data from ArcticDB via `pit_read()`
2. Applies PiT `.shift(1)` before passing to signal function
3. Runs single-pass Numba accumulator
4. Produces VectorBT Portfolio object with full analytics

**Numba warmup service (`warmup.py`):**
- Imports and calls every `@njit` function with representative argument types at startup
- Triggers JIT compilation so first real call is fast
- Configure `NUMBA_CACHE_DIR` for persistent cache across restarts
- Isolate Numba functions in separate files (cache invalidation is per-file)

**Output Files:**

```
src/backtest/__init__.py
src/backtest/engine.py           # BacktestRunner class
src/backtest/accumulators.py     # Numba single-pass backtester
src/backtest/numba_kernels.py    # Shared compiled indicators
src/backtest/warmup.py           # JIT warmup service
src/backtest/config.py           # VectorBT settings
scripts/warmup-numba-cache.sh
tests/backtest/test_engine.py
tests/backtest/test_accumulators.py
```

**Validation:**

- [ ] Single-pass accumulator produces correct PnL on known trade sequence
- [ ] Spread cost deduction: Forex backtest PnL lower than zero-spread by exactly `2 × spread per trade`
- [ ] Numba warmup completes in <60s on first run
- [ ] Numba cached run completes in <5s (compilation skipped)
- [ ] VectorBT chunk caching handles 10M+ row dataset without OOM
- [ ] BacktestRunner round-trip: ArcticDB read → PiT shift → accumulator → equity curve matches expected values

---

## PHASE 2 COMPLETE

**Phase 2 Completion Gate — all must pass before proceeding to Phase 3:**

- [ ] ArcticDB stores and retrieves both Forex and MBO schemas correctly
- [ ] Forex writer ingests ticks, aggregates bars, and tags sessions
- [ ] PiT manager prevents all forms of look-ahead bias
- [ ] VectorBT backtest with spread cost produces correct results on known data
- [ ] Numba warmup + cached run performance meets targets
- [ ] `pytest tests/data/ tests/backtest/ --cov --cov-fail-under=85` passes
- [ ] All pre-commit hooks pass on the new code
- [ ] `make all` passes

**Phase 2 delivers:** A complete data engineering layer with dual-schema storage, temporal integrity enforcement, and high-performance vectorized backtesting that accounts for Forex spread costs. Every alpha engine in Phase 3 reads data exclusively through this layer.
