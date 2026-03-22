---
phase: 02-data-engineering
plan: 04
subsystem: data
tags: [bar-aggregation, session-tagging, ohlcv, swap-rates, arcticdb, pandas]
dependency_graph:
  requires: [02-02]
  provides: [forex_bars library data, swap_rates library data, BarAggregator, SwapWriter]
  affects: [02-05, phase-03-alpha-engines]
tech_stack:
  added: []
  patterns: [pandas-resample-ohlc, arcticdb-append, asyncio-to-thread]
key_files:
  created:
    - src/data/bar_aggregator.py
    - src/data/swap_writer.py
  modified:
    - tests/data/test_bar_aggregator.py
decisions:
  - "aggregate_bars() uses pandas mid-price resample().ohlc() — single pass, vectorized, no custom loops"
  - "session column stored as np.int8 via pd.Int8Dtype() intermediate — avoids nullable integer in final DataFrame"
  - "BarAggregator takes store_uri in constructor — enables test injection with tmp_path LMDB stores"
  - "SwapWriter uses asyncio.to_thread for ArcticDB I/O — keeps event loop non-blocking without APScheduler dependency"
metrics:
  duration: 110s
  completed_date: "2026-03-22"
  tasks_completed: 2
  files_created: 3
---

# Phase 02 Plan 04: Bar Aggregator and Swap Writer Summary

**One-liner:** Tick-to-OHLCV aggregation with 6 pandas resample timeframes, 4-session UTC tagging (int8), and spread stats written to ArcticDB forex_bars; SwapWriter snapshots daily rates to swap_rates via asyncio.to_thread.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Failing tests for BarAggregator | 78e25fc | tests/data/test_bar_aggregator.py |
| 1 (GREEN) | BarAggregator with 6 timeframes and session tagging | 6346f94 | src/data/bar_aggregator.py |
| 2 | SwapWriter for daily swap rate snapshots | 7515c1b | src/data/swap_writer.py |

## What Was Built

### BarAggregator (`src/data/bar_aggregator.py`)

- `TIMEFRAMES` dict maps 6 labels (1m, 5m, 15m, 1h, 4h, 1d) to pandas resample rules
- `hour_to_session(hour)` maps UTC hour to int session tag: 0=Asian(00-08), 1=London(08-13), 2=Overlap(13-16), 3=NY(16-21), 0=Asian(21-23)
- `aggregate_bars(ticks_df, rule)` computes mid-price, resamples to OHLCV, adds tick_volume sum, spread_avg, spread_max, session tag; drops empty bars
- `BarAggregator.process_ticks(symbol, ticks_df)` iterates all 6 timeframes, writes to forex_bars library with `{SYMBOL}_{tf}` naming using `lib.append()`

### SwapWriter (`src/data/swap_writer.py`)

- `SwapWriter.write_daily(symbols)` fetches swap rates per symbol via injected callable, builds DataFrame with DatetimeIndex, appends to swap_rates library
- Non-blocking via `asyncio.to_thread(lib.append, ...)` — keeps event loop free
- Injectable `get_swap_rates_fn` parameter for broker-agnostic integration (MT5, SimAdapter, CMEAdapter)
- Logs to `helix.data` per D-08; gracefully skips if no function configured

### Tests (`tests/data/test_bar_aggregator.py`)

5 tests replacing skip stubs:
- `test_1m_bar_ohlcv_from_known_ticks`: Verifies open/high/low/close/tick_volume from hand-computed tick sequence
- `test_all_six_timeframes_produced`: 25h synthetic tick stream — all 6 timeframe symbols present in forex_bars
- `test_session_tags`: Ticks at hours 3, 10, 14, 18, 22 map to sessions 0, 1, 2, 3, 0 respectively; dtype is np.int8
- `test_spread_avg_and_max_per_bar`: Spreads [0.0001, 0.0002, 0.0003] → avg=0.0002, max=0.0003
- `test_bar_symbol_naming`: `process_ticks("EURUSD", ...)` → "EURUSD_1m" in lib.list_symbols()

## Verification

- All 5 bar aggregator tests pass: `pytest tests/data/test_bar_aggregator.py -x --no-cov` → 5 passed
- `grep "TIMEFRAMES" src/data/bar_aggregator.py` shows dict with keys 1m, 5m, 15m, 1h, 4h, 1d
- `grep "lib.append" src/data/bar_aggregator.py` confirmed (not write)
- `grep "asyncio.to_thread" src/data/swap_writer.py` confirmed
- `python -c "from src.data.swap_writer import SwapWriter"` exits 0

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None - all data paths are wired. SwapWriter's `get_swap_rates_fn` is intentionally injectable (not a stub) — caller provides broker adapter function.

## Self-Check: PASSED

Files exist:
- src/data/bar_aggregator.py: FOUND
- src/data/swap_writer.py: FOUND
- tests/data/test_bar_aggregator.py: FOUND

Commits:
- 78e25fc: test(02-04) RED phase
- 6346f94: feat(02-04) bar aggregator implementation
- 7515c1b: feat(02-04) swap writer implementation
