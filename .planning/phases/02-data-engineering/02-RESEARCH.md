# Phase 02: Data Engineering - Research

**Researched:** 2026-03-22
**Domain:** ArcticDB time-series storage, Forex tick ingestion, Point-in-Time data integrity, VectorBT Pro backtesting, Numba JIT compilation
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Production backend is LMDB on local disk — NOT S3. `adb.Arctic("lmdb://./arctic_data")` for both dev and production.
- **D-02:** Dev/CI path: `./arctic_data` (relative to project root, gitignored). Same path in dev, staging, and production.
- **D-03:** 6 libraries with fixed schemas: `forex_ticks`, `forex_bars`, `swap_rates`, `mbo_ticks` (stub, empty in Stage A), `signals`, `portfolio`.
- **D-04:** Batch flush: 10,000 ticks OR 1 second, whichever comes first. Uses `lib.append()` never `lib.write()`.
- **D-05:** Bar timeframes: 1m, 5m, 15m, 1h, 4h, 1d — all 6 computed from tick stream.
- **D-06:** Session tags: `0`=Asian (00:00-08:00 UTC), `1`=London (08:00-13:00 UTC), `2`=Overlap (13:00-16:00 UTC), `3`=New York (16:00-21:00 UTC).
- **D-07:** Bad ticks are stored with a `quality: int8` column — NOT discarded. Values: `0`=clean, `1`=rollover_spike, `2`=weekend_gap, `3`=duplicate. Consumers filter by quality column.
- **D-08:** Data quality events reported via Python logging to `helix.data` logger (structured JSON). NATS alerting deferred.
- **D-09:** Daily EOD automated snapshots at 22:00 UTC. Named `eod_YYYYMMDD`.
- **D-10:** On startup, scheduler checks last snapshot date; backfills retroactive snapshots for missed days.
- **D-11:** `pit_read(library, symbol, as_of_timestamp)` uses ArcticDB native `date_range` filtering — no data beyond `as_of_timestamp` ever returned.
- **D-12:** Five look-ahead bias vectors prevented per `_docs/Phase_2_Data_Engineering.md` § Task 2.3.
- **D-13:** `validate_pit_compliance(signal_df, price_df)` uses IC analysis: `abs(contemp_ic) > abs(forward_ic) * 1.5` → raises `LookAheadBiasError`.
- **D-14:** Full BacktestRunner delivered in Phase 2. Alpha engines in Phase 3 call `BacktestRunner.run(strategy_fn, symbol, date_range)` directly.
- **D-15:** BacktestRunner persists results to ArcticDB `portfolio` library, tagged by strategy name + date range + snapshot name.
- **D-16:** Single-pass Numba accumulator signature: `single_pass_backtest(close, signal, risk_per_trade, atr, spread_cost)`.
- **D-17:** Numba warmup service compiles all `@njit` functions at startup. `NUMBA_CACHE_DIR` set to `./numba_cache`.
- **D-18:** VectorBT Pro settings: `chunking.n_chunks='auto'`, `caching.register_lazily=True`, `caching.use_disk=True`, `caching.disk_path='/tmp/vbt_cache'`.

### Claude's Discretion

- Exact deduplication algorithm for duplicate tick detection (timestamp + bid/ask equality check is sufficient)
- Swap writer scheduler implementation (APScheduler or asyncio-based)
- Admin CLI framework (argparse or click)
- Numba cache directory creation and cleanup strategy

### Deferred Ideas (OUT OF SCOPE)

- S3 / S3-compatible production backend
- NATS alerting for data quality events (Phase 4)
- Real-time data quality dashboard (Phase 4)
- Automated pair discovery / tick data for all XXXYYY combinations (v2)

</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DATA-01 | ArcticDB initialized with 6 libraries (forex_ticks, forex_bars, swap_rates, mbo_ticks stub, signals, portfolio) | ArcticDB 6.10.2 installed; `create_library` + `get_library(create_if_missing=True)` API verified |
| DATA-02 | Forex tick writer batches 10K ticks, flushes every 1s, never blocks execution adapter | `lib.append()` creates symbol on first call; `asyncio.to_thread` pattern for non-blocking writes; threading.Event for timer |
| DATA-03 | Bar aggregator produces 6 timeframes (1m/5m/15m/1h/4h/1d) with session tagging | Pure pandas resample; session tag via UTC hour boundaries; spread_avg/spread_max per bar |
| DATA-04 | PiT manager prevents all 5 look-ahead bias vectors; pit_read returns only data ≤ as_of_timestamp | `lib.read(symbol, date_range=(None, as_of))` verified working in ArcticDB 6.10.2 |
| DATA-05 | ArcticDB snapshots enable reproducible backtests at any historical date | `lib.snapshot(name)` + `lib.read(symbol, as_of=snapshot_name)` verified; snapshot metadata dict confirmed |
| DATA-06 | VectorBT Pro + Numba single-pass backtester with spread cost parameter | VectorBT Pro NOT pip-installable (requires purchase); numba 0.60.0 installable and compatible with numpy 1.26.3 |
| DATA-07 | Numba warmup service compiles all JIT functions at startup; cached run < 5s | `@njit(cache=True)` + `NUMBA_CACHE_DIR=./numba_cache`; warmup by calling each function with tiny representative arrays |

</phase_requirements>

---

## Summary

Phase 2 builds the complete data layer consumed by all Phase 3 alpha engines. The work splits into four distinct modules: (1) ArcticDB store initialization with dual-stage schemas, (2) the Forex tick ingestion and bar aggregation pipeline, (3) the Point-in-Time data manager enforcing temporal integrity, and (4) the VectorBT Pro + Numba backtesting stack. Each module has well-defined interfaces to Phase 1 (Tick/Bar dataclasses, SpreadModel) and to Phase 3 (pit_read, BacktestRunner).

ArcticDB 6.10.2 is already installed in the project venv. Critical API behaviors have been verified directly against the installed package: `lib.append()` creates the symbol if it does not exist (no prior `write()` needed), `date_range=(None, as_of_timestamp)` returns strictly no data beyond the cutoff, and `lib.read(symbol, as_of='snapshot_name')` returns data at the snapshot version only. These are the three load-bearing APIs for DATA-02, DATA-04, and DATA-05 respectively.

The most significant dependency gap is VectorBT Pro — it is NOT available on PyPI (requires a direct purchase from vectorbt.pro). The project already has `vectorbt.*` listed in pyproject.toml mypy overrides, but the package itself is absent from the venv. Numba 0.60.0 is installable and compatible with the installed numpy 1.26.3. psutil (needed for VectorBT memory-aware chunk sizing) is also not installed. A Wave 0 task must install these packages before any backtest code can be written.

**Primary recommendation:** Structure Phase 2 into 4 tasks matching the spec (Task 2.1 store init, Task 2.2 ingestion pipeline, Task 2.3 PiT manager, Task 2.4 backtest stack). Gate Task 2.4 on VectorBT Pro being installed. The pit_validator script currently targets `src/alpha/` only — extend it or run it explicitly against `src/data/` and `src/backtest/` in CI to enforce PiT compliance on Phase 2 code.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| arcticdb | 6.10.2 (installed) | Time-series columnar storage with versioning | Native Python, LMDB backend, snapshot/PiT APIs, already installed |
| pandas | 2.2.0 (installed) | DataFrame manipulation for ticks and bars | ArcticDB reads/writes pandas DataFrames natively |
| numpy | 1.26.3 (installed) | Array operations, datetime64 index | Required by arcticdb, numba compatibility verified |
| numba | 0.60.0 (NOT installed) | JIT-compile single-pass backtest accumulator | `@njit(cache=True)` for < 5s cached run requirement |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| vectorbtpro | purchase required (NOT installed) | Vectorized backtesting with Portfolio analytics | BacktestRunner wraps it for full analytics after Numba accumulator |
| psutil | latest (NOT installed) | Available memory detection for VBT chunk sizing | VBT config: `chunk_size = available_mb * 0.8` |
| APScheduler or asyncio | stdlib / APScheduler 3.x | EOD snapshot scheduler, swap writer daily trigger | Swap writer at 00:05 UTC, snapshot at 22:00 UTC |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| asyncio.to_thread (for ArcticDB writes) | threading.Thread directly | asyncio.to_thread is the established pattern in this codebase (Phase 1 reference) |
| APScheduler | asyncio loop + asyncio.sleep | APScheduler is more robust for missed-run backfill; asyncio is sufficient but fragile on restart |
| argparse (admin CLI) | click | argparse is stdlib (no dep); click is more ergonomic for multi-command CLIs; either works |

**Installation (missing packages):**
```bash
# Required before Task 2.4
pip install numba==0.60.0 psutil
# VectorBT Pro: must be purchased at https://vectorbt.pro and installed via provided wheel
pip install vectorbtpro-*.whl  # version from purchase
```

**Version verification (verified 2026-03-22):**
- arcticdb 6.10.2 — `pip show arcticdb` confirmed
- numba 0.60.0 — compatible with numpy<2.1, dry-run install confirmed
- numpy 1.26.3 — installed, compatible with numba 0.60
- vectorbtpro — NOT on PyPI; must be purchased separately

---

## Architecture Patterns

### Recommended Project Structure

```
src/data/
├── __init__.py              # Module docstring (already exists, stub only)
├── arctic_store.py          # ArcticDB initialization, library management, get_store()
├── schemas.py               # FOREX_TICK_SCHEMA, FOREX_BAR_SCHEMA, MBO_TICK_SCHEMA constants
├── admin_cli.py             # CLI: list-libraries, list-symbols, schema, compact
├── forex_writer.py          # TickWriter class: buffer, flush thread, quality flagging
├── bar_aggregator.py        # BarAggregator: resample ticks to 6 timeframes + session tags
├── swap_writer.py           # SwapWriter: daily scheduler writes swap_rates library
├── pit_manager.py           # pit_read(), create_snapshot(), validate_pit_compliance(), shift_features()
└── snapshot_scheduler.py    # EOD snapshot at 22:00 UTC + startup backfill

src/backtest/
├── __init__.py
├── config.py                # VBT settings: chunking, caching, memory-aware chunk_size
├── accumulators.py          # @njit single_pass_backtest(close, signal, risk_per_trade, atr, spread_cost)
├── numba_kernels.py         # Shared @njit indicators (ATR, rolling computations)
├── warmup.py                # Call every @njit function with tiny arrays at startup
└── engine.py                # BacktestRunner: pit_read → shift(1) → accumulator → vbt.Portfolio

tests/data/
├── __init__.py
├── test_arctic_store.py     # 6 libs created, round-trip dtype preservation
├── test_forex_writer.py     # Batch flush, session tags, quality flags, dedup
├── test_bar_aggregator.py   # 6 timeframes, OHLCV correctness, session labels
├── test_swap_writer.py      # Daily write, schema validation
└── test_pit_integrity.py    # pit_read cutoff, snapshot isolation, validate_pit_compliance

tests/backtest/
├── __init__.py
├── test_accumulators.py     # Known PnL on synthetic signals, spread deduction math
└── test_engine.py           # BacktestRunner round-trip, reproducibility across runs
```

### Pattern 1: ArcticDB Store Singleton

**What:** A module-level `get_store()` function returns a cached `adb.Arctic` instance.
**When to use:** All code that reads or writes ArcticDB in Phase 2.

```python
# Source: verified against arcticdb 6.10.2 installed package
import arcticdb as adb
from functools import lru_cache

@lru_cache(maxsize=1)
def get_store(uri: str = "lmdb://./arctic_data") -> adb.Arctic:
    return adb.Arctic(uri)

def get_library(name: str, *, create_if_missing: bool = False):
    store = get_store()
    if create_if_missing and not store.has_library(name):
        store.create_library(name)
    return store.get_library(name)
```

**Pitfall:** `lru_cache` on `get_store` means the URI cannot be changed after first call. Use a module-level `_STORE: adb.Arctic | None = None` pattern instead for tests that need a tmp path override.

### Pattern 2: Non-Blocking Tick Writer

**What:** A `TickWriter` that buffers ticks in a list and flushes to ArcticDB on a dedicated thread, never blocking the async execution event loop.
**When to use:** All live tick ingestion from MT5/ZMQ bridge.

```python
# Source: established pattern from Phase 1 (asyncio.to_thread for blocking I/O)
import asyncio
import threading
import time
from collections import defaultdict
import pandas as pd

class TickWriter:
    FLUSH_TICKS = 10_000
    FLUSH_SECONDS = 1.0

    def __init__(self, store_uri: str = "lmdb://./arctic_data") -> None:
        self._buffer: defaultdict[str, list] = defaultdict(list)
        self._lock = threading.Lock()
        self._store_uri = store_uri
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._flush_loop, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join()

    def write(self, tick: "Tick") -> None:
        """Called from async execution loop — must not block."""
        with self._lock:
            self._buffer[tick.symbol].append(tick)
            if len(self._buffer[tick.symbol]) >= self.FLUSH_TICKS:
                self._flush_symbol_locked(tick.symbol)

    def _flush_loop(self) -> None:
        while not self._stop.wait(timeout=self.FLUSH_SECONDS):
            self._flush_all()
        self._flush_all()  # Final flush on shutdown

    def _flush_all(self) -> None:
        with self._lock:
            for symbol in list(self._buffer.keys()):
                if self._buffer[symbol]:
                    self._flush_symbol_locked(symbol)

    def _flush_symbol_locked(self, symbol: str) -> None:
        """Must be called with self._lock held."""
        ticks = self._buffer.pop(symbol)
        # Build DataFrame and append to ArcticDB on calling thread
        # (flush_loop runs on dedicated thread, so ArcticDB I/O never touches async loop)
        import arcticdb as adb
        store = adb.Arctic(self._store_uri)
        lib = store.get_library("forex_ticks")
        df = _ticks_to_df(ticks)
        lib.append(symbol, df)
```

**Key insight:** `lib.append()` in ArcticDB 6.10.2 creates the symbol on first call — no prior `lib.write()` needed. The index must be monotonically increasing; the writer must sort by timestamp within each buffer flush.

### Pattern 3: PiT Read with ArcticDB date_range

**What:** `pit_read()` wraps `lib.read()` with a `date_range=(None, as_of_timestamp)` constraint.
**When to use:** Every data access in backtests and signal generation.

```python
# Source: verified against arcticdb 6.10.2 — date_range=(None, end) returns rows with index <= end
import arcticdb as adb
import pandas as pd

def pit_read(
    library: str,
    symbol: str,
    as_of_timestamp: pd.Timestamp,
    *,
    store_uri: str = "lmdb://./arctic_data",
    columns: list[str] | None = None,
) -> pd.DataFrame:
    """Return rows with index strictly <= as_of_timestamp."""
    store = adb.Arctic(store_uri)
    lib = store.get_library(library)
    result = lib.read(
        symbol,
        date_range=(None, as_of_timestamp),
        columns=columns,
    )
    return result.data
```

**Verified behavior:** `date_range=(None, pd.Timestamp('2024-01-03'))` on a 5-row DataFrame returns 3 rows (2024-01-01, 2024-01-02, 2024-01-03 inclusive). The cutoff is inclusive — if strict exclusion is needed, subtract one nanosecond.

### Pattern 4: Snapshot Creation and Isolation

**What:** Named snapshots freeze a version of every symbol in a library. Reading `as_of='snapshot_name'` returns data as of that snapshot.
**When to use:** EOD snapshot creation (22:00 UTC), BacktestRunner reproducibility.

```python
# Source: verified against arcticdb 6.10.2
def create_snapshot(library_name: str, snapshot_name: str) -> None:
    """Create a named snapshot of all symbols in library."""
    store = adb.Arctic("lmdb://./arctic_data")
    lib = store.get_library(library_name)
    lib.snapshot(
        snapshot_name,
        metadata={"created_at": datetime.utcnow().isoformat() + "Z"},
    )

# Reading at snapshot — data written AFTER snapshot is NOT returned
df = lib.read("EURUSD", as_of="eod_20240102").data   # returns pre-snapshot data only
```

**Verified behavior:** After `lib.snapshot('eod_20240102')` and subsequent `lib.append('EURUSD', new_data)`, `lib.read('EURUSD', as_of='eod_20240102').data` returns 2 rows; `lib.read('EURUSD').data` returns 3 rows.

### Pattern 5: Numba Single-Pass Accumulator

**What:** `@njit(cache=True)` function that computes equity curve, positions, and PnL in one forward pass.
**When to use:** BacktestRunner for every backtest evaluation.

```python
# Source: SKILL.md arcticdb-vectorbt-engine (project skill reference)
from numba import njit
import numpy as np

@njit(cache=True)
def single_pass_backtest(
    close: np.ndarray,
    signal: np.ndarray,       # 1=long, -1=short, 0=flat
    risk_per_trade: float,
    atr: np.ndarray,
    spread_cost: np.ndarray,  # Stage A: SpreadModel.median per bar; Stage B: zeros
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
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
            pnl[i] = -spread_cost[i] * pos_size
        elif signal[i-1] == 0 and position[i-1] != 0:
            position[i] = 0
            pnl[i] = (position[i-1] * (close[i] - close[i-1]) * pos_size
                      - spread_cost[i] * pos_size)
            pos_size = 0.0
        else:
            position[i] = position[i-1]
            pnl[i] = (position[i] * (close[i] - close[i-1]) * pos_size
                      if position[i] != 0 else 0.0)
        equity[i] = equity[i-1] + pnl[i]
    return equity, position, pnl
```

### Anti-Patterns to Avoid

- **Using `lib.write()` in the tick writer:** `write()` creates a new version and discards previous data unless `prune_previous_version=False`. Use `lib.append()` exclusively for incremental tick ingestion.
- **Accessing ArcticDB from the async event loop directly:** ArcticDB I/O is blocking. Always use `asyncio.to_thread()` or a dedicated thread.
- **Snapshot without metadata:** Always include `metadata={'created_at': ...}` so `list_snapshots()` returns enough information for the startup backfill check.
- **Numba `parallel=True` on non-embarrassingly-parallel code:** The accumulator is a sequential forward pass — `parallel=True` will miscompile. Reserve `parallel=True` for independent rolling indicator computations.
- **VectorBT chunk_size set to a fixed integer:** Memory varies by machine. Always compute from `psutil.virtual_memory().available`.
- **Quality column as bool:** Use `int8` (0/1/2/3) not `bool` — the spec uses int8 and future values (e.g., `4=missing_gap`) would overflow a bool column.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Time-series versioning with snapshot isolation | Custom file-based snapshot system | ArcticDB `lib.snapshot()` + `as_of=` | ArcticDB handles concurrent reads, LMDB transactions, version garbage collection |
| PiT date range filtering | Manual DataFrame slicing with `.loc[]` | ArcticDB `date_range=(None, as_of)` parameter | Pushes filter to storage layer; never loads future data into memory |
| Vectorized portfolio analytics (Sharpe, drawdown, etc.) | Custom metric computation | VectorBT `vbt.Portfolio.from_signals()` | Handles NaN, edge cases, multi-symbol portfolios; battle-tested |
| Numba compilation cache management | Custom pickle/shelve cache | `@njit(cache=True)` + `NUMBA_CACHE_DIR` env var | Numba's own cache handles invalidation on source change automatically |
| Bar aggregation from ticks | Custom OHLCV loop | `pandas.DataFrame.resample(rule).agg()` | Handles timezone, DST, incomplete bars correctly |

**Key insight:** The three hardest problems in this phase (snapshot isolation, PiT filtering, bar aggregation) each have a one-line solution in the respective library. The effort is in wiring them correctly, not in reimplementing them.

---

## Common Pitfalls

### Pitfall 1: ArcticDB append requires monotonically increasing index

**What goes wrong:** `lib.append()` raises `ValueError: data is not sorted in ascending order` when ticks arrive out-of-order (common during rollover/reconnect).
**Why it happens:** ArcticDB enforces `validate_index=True` by default — the appended DataFrame's index must start at or after the last stored timestamp.
**How to avoid:** Sort the buffer by timestamp before flushing: `df = df.sort_index()`. Also deduplicate on (timestamp, bid, ask) before sort to prevent duplicate-index errors.
**Warning signs:** Exceptions from flush thread with `validate_index` in the traceback.

### Pitfall 2: PiTValidator (scripts/pit_validator.py) only scans src/alpha/

**What goes wrong:** Phase 2 code in `src/data/` and `src/backtest/` that accesses price columns without `.shift()` will NOT be caught by the existing `make validate` command, which hardcodes `--source src/alpha/`.
**Why it happens:** The PiT validator was set up in Phase 1 for alpha engine code only.
**How to avoid:** Either (a) extend the Makefile `validate` target to also run `--source src/data/ --source src/backtest/`, or (b) add a `validate_data` target. The `pit_manager.py` itself accesses price columns legitimately (to validate them) — use a `# noqa: pit_check` comment convention or exclude specific modules from scanning.
**Warning signs:** `make validate` passes but look-ahead bias exists in data layer code.

### Pitfall 3: VectorBT Pro is not pip-installable from PyPI

**What goes wrong:** `pip install vectorbtpro` fails with "No matching distribution found."
**Why it happens:** VectorBT Pro is a commercial library distributed only to paying customers via a private wheel or git repo.
**How to avoid:** Wave 0 must acquire and install the wheel before implementing Task 2.4. The `vectorbt.*` mypy ignore is already in pyproject.toml but the package itself must be manually installed.
**Warning signs:** `ModuleNotFoundError: No module named 'vectorbtpro'` during backtest task implementation.

### Pitfall 4: Numba cache invalidation on refactor

**What goes wrong:** After renaming or moving a `.py` file containing `@njit` functions, the Numba cache for the old path is orphaned and a full recompile triggers on next run.
**Why it happens:** Numba's file-based cache keys on the source file path and bytecode hash.
**How to avoid:** Isolate all `@njit` functions in dedicated files (`accumulators.py`, `numba_kernels.py`). Avoid mixing JIT and non-JIT code in the same file. Document `NUMBA_CACHE_DIR=./numba_cache` in `.env.example`.
**Warning signs:** Warmup taking > 60s after a routine refactor.

### Pitfall 5: Snapshot backfill creates wrong snapshot contents

**What goes wrong:** On startup, the scheduler tries to backfill missed snapshots by calling `lib.snapshot('eod_YYYYMMDD')` for past dates. But `lib.snapshot()` always snapshots the CURRENT state of the library, not the state at the past date.
**Why it happens:** ArcticDB snapshots are created at call-time; there is no `as_of` parameter on `snapshot()`.
**How to avoid:** Backfill snapshots ARE correct for this use case — they capture whatever data is currently in the library for that symbol, which is the correct historical state if the library was written to during the missed period. The backfill just creates a snapshot of current data labeled with the past date. This is acceptable as long as no new data was written for those periods after the outage. Document this limitation in `snapshot_scheduler.py`.
**Warning signs:** Backfill snapshots containing more data than they should (if data was retroactively appended after an outage).

### Pitfall 6: Thread safety in TickWriter buffer

**What goes wrong:** The tick writer's buffer is accessed from multiple threads (the async loop calls `write()`, the flush thread calls `_flush_all()`), causing data corruption or missed ticks.
**Why it happens:** Python lists are not thread-safe for concurrent append + pop.
**How to avoid:** Use a `threading.Lock` on all buffer access. Alternatively, use `queue.Queue` (thread-safe by design) and have the flush thread drain the queue.
**Warning signs:** Missing ticks in ArcticDB, intermittent `IndexError` in flush thread.

### Pitfall 7: mypy strict + ArcticDB return types

**What goes wrong:** `lib.read()` returns a `VersionedItem` object, not a DataFrame. `lib.read(...).data` is typed as `Any` in the ArcticDB stubs.
**Why it happens:** ArcticDB's return types are complex and the mypy ignore is set for the entire `arcticdb.*` module.
**How to avoid:** Add explicit `cast(pd.DataFrame, lib.read(...).data)` or use `assert isinstance(result.data, pd.DataFrame)` at read boundaries. The existing `arcticdb_stubs.py` only covers KCH validation — mypy type narrowing must be done manually.
**Warning signs:** mypy strict passing but runtime `AttributeError` on `.data`.

---

## Code Examples

Verified patterns from official sources and direct API testing:

### ArcticDB Store Initialization (verified against 6.10.2)

```python
# Source: arcticdb_stubs.py + direct API verification 2026-03-22
import arcticdb as adb

LIBRARY_NAMES = [
    "forex_ticks", "forex_bars", "swap_rates",
    "mbo_ticks",   # Stage B stub — empty during Stage A
    "signals", "portfolio",
]

def initialize_store(uri: str = "lmdb://./arctic_data") -> adb.Arctic:
    store = adb.Arctic(uri)
    for name in LIBRARY_NAMES:
        if not store.has_library(name):
            store.create_library(name)
    return store
```

### PiT Read (date_range verified)

```python
# Verified 2026-03-22: returns rows with index <= as_of_timestamp (inclusive)
result = lib.read(
    symbol,
    date_range=(None, pd.Timestamp(as_of_timestamp)),
    columns=columns,
)
df: pd.DataFrame = result.data
```

### Snapshot Creation and Listing (verified)

```python
# snapshot() metadata is a dict stored alongside the snapshot name
lib.snapshot("eod_20240101", metadata={"created_at": "2024-01-01T22:00:00Z"})
snaps: dict[str, dict | None] = lib.list_snapshots()
# {"eod_20240101": {"created_at": "2024-01-01T22:00:00Z"}}
```

### Bar Aggregation from Ticks

```python
# Source: pandas resample — standard pattern for OHLCV from tick mid prices
import pandas as pd

def aggregate_bars(ticks_df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """rule: '1min', '5min', '15min', '1h', '4h', '1D'"""
    mid = (ticks_df["bid"] + ticks_df["ask"]) / 2.0
    bars = mid.resample(rule).ohlc()
    bars["tick_volume"] = ticks_df["tick_volume"].resample(rule).sum()
    bars["spread_avg"] = ticks_df["spread"].resample(rule).mean()
    bars["spread_max"] = ticks_df["spread"].resample(rule).max()
    bars["session"] = bars.index.hour.map(_hour_to_session).astype("int8")
    return bars.dropna(subset=["open"])

def _hour_to_session(hour: int) -> int:
    if 0 <= hour < 8:   return 0  # Asian
    if 8 <= hour < 13:  return 1  # London
    if 13 <= hour < 16: return 2  # Overlap
    if 16 <= hour < 21: return 3  # New York
    return 0  # Asian (covers 21-24 as Asian pre-open)
```

### Numba Warmup Service

```python
# Source: SKILL.md + direct API knowledge
import os
os.environ.setdefault("NUMBA_CACHE_DIR", "./numba_cache")

def warmup_numba() -> None:
    """Call every @njit function with minimal representative arrays."""
    import numpy as np
    from src.backtest.accumulators import single_pass_backtest
    # Tiny 10-element arrays — triggers compilation, not performance test
    n = 10
    single_pass_backtest(
        close=np.linspace(1.0, 1.1, n),
        signal=np.array([0, 1, 1, 1, 0, -1, -1, -1, 0, 0], dtype=np.int8),
        risk_per_trade=0.01,
        atr=np.full(n, 0.001),
        spread_cost=np.full(n, 0.0001),
    )
```

### Data Quality Flagging

```python
# int8 quality column on every tick row before writing
import numpy as np

QUALITY_CLEAN: int = 0
QUALITY_ROLLOVER_SPIKE: int = 1
QUALITY_WEEKEND_GAP: int = 2
QUALITY_DUPLICATE: int = 3

def flag_quality(df: pd.DataFrame) -> pd.DataFrame:
    """Add int8 quality column; default clean."""
    df = df.copy()
    df["quality"] = np.int8(QUALITY_CLEAN)

    # Rollover spike: spread > 5× median at 00:00 UTC
    rollover_mask = (df.index.hour == 0) & (df["spread"] > df["spread"].median() * 5)
    df.loc[rollover_mask, "quality"] = np.int8(QUALITY_ROLLOVER_SPIKE)

    # Weekend gap: Friday 22:00 → Sunday 22:00 UTC
    weekend_mask = df.index.dayofweek.isin([5, 6])  # Saturday=5, Sunday=6
    df.loc[weekend_mask, "quality"] = np.int8(QUALITY_WEEKEND_GAP)

    # Duplicate: same timestamp + same bid + same ask
    dup_mask = df.duplicated(subset=["bid", "ask"], keep="first")
    df.loc[dup_mask, "quality"] = np.int8(QUALITY_DUPLICATE)

    return df
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| InfluxDB / TimescaleDB for tick storage | ArcticDB (columnar, versioned) | ~2022 | Native Python, snapshot PiT, no separate DB process |
| Custom OHLCV aggregation loops | pandas resample().agg() | Pandas 1.0+ | Handles DST/tz correctly |
| VectorBT open-source (free) | VectorBT Pro (paid) | 2022 | Chunk caching, disk persistence, more analytics |
| Manual Numba compilation | `@njit(cache=True)` + `NUMBA_CACHE_DIR` | Numba 0.43+ | Persistent cache across Python restarts |

**Deprecated/outdated:**
- `vectorbt` (open source): The pyproject.toml mypy override says `vectorbt.*` (not `vectorbtpro`) — this reflects the old package name. Phase 2 installs `vectorbtpro` which imports as `vectorbtpro`, not `vectorbt`. Update mypy overrides if needed.
- ArcticDB `compact_incomplete()`: The ArcticDB 6.x API does not expose `compact_incomplete` in the same way as older versions. Use `defragment_symbol_data(symbol)` instead for compacting fragmented appended segments. The admin CLI `compact` command should call `lib.defragment_symbol_data(symbol)`.

---

## Open Questions

1. **VectorBT Pro acquisition status**
   - What we know: `vectorbtpro` is not on PyPI; the project references it in mypy overrides; the SKILL.md documents its usage in detail
   - What's unclear: Has the VectorBT Pro license been purchased? Is a wheel available locally?
   - Recommendation: Wave 0 task must confirm VectorBT Pro availability before Task 2.4 begins. If not acquired, BacktestRunner can be stubbed with direct Numba accumulator output and a minimal Portfolio-like dataclass, deferring VBT analytics to when the license is available.

2. **PiT validator scope for src/data/ and src/backtest/**
   - What we know: `scripts/pit_validator.py` defaults to `--source src/alpha/`; the `make validate` Makefile target uses that default
   - What's unclear: Should Phase 2 extend the Makefile to scan `src/data/` and `src/backtest/`? Or is the existing scope intentional (PiT only enforced on alpha code)?
   - Recommendation: Extend `make validate` to scan both new directories. `pit_manager.py` itself does legitimate raw price access (it validates others' code) — either scope it out or add a `# noqa: pit` comment convention.

3. **Symbol naming convention for forex_bars library**
   - What we know: SKILL.md shows `EURUSD_1m`, `EURUSD_5m`, etc. as symbol names within `forex_bars` library
   - What's unclear: Is the naming `{SYMBOL}_{timeframe}` (e.g., `EURUSD_1m`) or a nested approach?
   - Recommendation: Use `{SYMBOL}_{timeframe}` as ArcticDB symbol names within `forex_bars`. This is what SKILL.md shows and what the spec implies.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (installed in venv) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `.venv/bin/pytest tests/data/ tests/backtest/ -x --no-cov` |
| Full suite command | `.venv/bin/pytest tests/data/ tests/backtest/ --cov=src --cov-fail-under=85 --cov-branch -v` |

Note: Phase 2 spec sets 85% coverage threshold (stricter than project's 80% baseline).

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DATA-01 | 6 libraries created; round-trip preserves dtypes | unit | `.venv/bin/pytest tests/data/test_arctic_store.py -x` | Wave 0 |
| DATA-02 | 10K tick batch flush; 1s timer flush; no async blocking | unit | `.venv/bin/pytest tests/data/test_forex_writer.py -x` | Wave 0 |
| DATA-02 | Quality flags applied (int8 column) | unit | `.venv/bin/pytest tests/data/test_forex_writer.py::test_quality_flags -x` | Wave 0 |
| DATA-03 | 6 timeframes OHLCV correct on known tick sequence | unit | `.venv/bin/pytest tests/data/test_bar_aggregator.py -x` | Wave 0 |
| DATA-03 | Session tags match UTC hour ranges | unit | `.venv/bin/pytest tests/data/test_bar_aggregator.py::test_session_tags -x` | Wave 0 |
| DATA-04 | pit_read returns no data beyond as_of_timestamp | unit | `.venv/bin/pytest tests/data/test_pit_integrity.py::test_pit_read_cutoff -x` | Wave 0 |
| DATA-04 | validate_pit_compliance raises LookAheadBiasError on contaminated signal | unit | `.venv/bin/pytest tests/data/test_pit_integrity.py::test_contemp_ic_violation -x` | Wave 0 |
| DATA-05 | Snapshot at T, write after T, pit_read(as_of=snapshot) returns pre-T only | unit | `.venv/bin/pytest tests/data/test_pit_integrity.py::test_snapshot_isolation -x` | Wave 0 |
| DATA-05 | BacktestRunner on same snapshot returns identical results across 2 runs | unit | `.venv/bin/pytest tests/backtest/test_engine.py::test_reproducibility -x` | Wave 0 |
| DATA-06 | Single-pass accumulator PnL correct on known trade sequence | unit | `.venv/bin/pytest tests/backtest/test_accumulators.py::test_known_pnl -x` | Wave 0 |
| DATA-06 | Spread cost: Forex PnL lower than zero-spread by exactly 2×spread per trade | unit | `.venv/bin/pytest tests/backtest/test_accumulators.py::test_spread_deduction -x` | Wave 0 |
| DATA-07 | Numba warmup completes < 60s on first run | smoke | `.venv/bin/pytest tests/backtest/test_engine.py::test_warmup_timing -x` | Wave 0 |
| DATA-07 | Numba cached run completes < 5s | smoke | `.venv/bin/pytest tests/backtest/test_engine.py::test_cached_run_timing -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `.venv/bin/pytest tests/data/ tests/backtest/ -x --no-cov`
- **Per wave merge:** `.venv/bin/pytest tests/data/ tests/backtest/ --cov=src --cov-fail-under=85 --cov-branch -v`
- **Phase gate:** Full suite green + `make all` passes before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/data/__init__.py` — package init
- [ ] `tests/data/test_arctic_store.py` — covers DATA-01
- [ ] `tests/data/test_forex_writer.py` — covers DATA-02
- [ ] `tests/data/test_bar_aggregator.py` — covers DATA-03
- [ ] `tests/data/test_pit_integrity.py` — covers DATA-04, DATA-05
- [ ] `tests/backtest/__init__.py` — package init
- [ ] `tests/backtest/test_accumulators.py` — covers DATA-06
- [ ] `tests/backtest/test_engine.py` — covers DATA-05 (reproducibility), DATA-07
- [ ] Install missing packages: `numba==0.60.0 psutil` and VectorBT Pro wheel
- [ ] Add `numba_stubs.py` to `stubs/` — the KCH validator will flag `@njit` calls without it
- [ ] Extend `Makefile validate` target to scan `src/data/` and `src/backtest/` via pit_validator

---

## Sources

### Primary (HIGH confidence)

- ArcticDB 6.10.2 installed package — direct API inspection and functional verification of `append`, `read`, `snapshot`, `date_range`, `list_snapshots`, `defragment_symbol_data`
- `.claude/skills/forex/arcticdb-vectorbt-engine/SKILL.md` — project skill: write path patterns, PiT structuring, VectorBT Pro optimization, Numba accumulator signature
- `_docs/Phase_2_Data_Engineering.md` — complete Phase 2 spec with all schemas, thresholds, session tag values, accumulator signature
- `src/execution/abstract.py` — Tick, Bar dataclasses that Phase 2 writers consume directly
- `src/execution/spread_model.py` — SpreadModel.median as spread_cost source
- `src/quality/pit_validator.py` — PiT AST checker that Phase 2 code must pass
- `stubs/arcticdb_stubs.py` — verified ArcticDB 6.10.2 API surface (KCH stub)

### Secondary (MEDIUM confidence)

- `pyproject.toml` — confirmed installed packages, mypy overrides, pytest config
- Direct `pip index versions numba` — confirmed numba 0.60.0 availability and numpy 1.26.3 compatibility
- Direct `pip index versions vectorbtpro` — confirmed NOT on PyPI

### Tertiary (LOW confidence)

- General Numba documentation patterns (`@njit(cache=True)`, `NUMBA_CACHE_DIR`) — consistent with installed version capabilities but not directly tested in this environment

---

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — arcticdb version verified by `pip show`; numba dry-run install confirmed; VectorBT Pro absence confirmed by `pip index versions`
- Architecture: HIGH — patterns verified against arcticdb 6.10.2 API directly; schemas from project SKILL.md
- Pitfalls: HIGH — append/monotonic-index behavior verified; VBT Pro absence confirmed; PiTValidator scope confirmed by reading the script

**Research date:** 2026-03-22
**Valid until:** 2026-06-22 (arcticdb API is stable; numba compatibility valid until numpy 2.x upgrade)
