---
phase: 02-data-engineering
plan: 06
subsystem: backtest
tags: [numba, vectorbtpro, backtesting, pit-compliance, portfolio-persistence]
dependency_graph:
  requires: [02-03, 02-05]
  provides: [BacktestRunner, single_pass_backtest, warmup_numba, configure_vbt]
  affects: [phase-03-alpha-engines]
tech_stack:
  added: [numba, arcticdb-portfolio-library]
  patterns: [tdd-red-green, numba-njit-cache, pit-read-shift-accumulate]
key_files:
  created:
    - src/backtest/__init__.py
    - src/backtest/config.py
    - src/backtest/accumulators.py
    - src/backtest/numba_kernels.py
    - src/backtest/warmup.py
    - src/backtest/engine.py
    - scripts/warmup-numba-cache.sh
  modified:
    - tests/backtest/test_accumulators.py
    - tests/backtest/test_engine.py
decisions:
  - "spread_cost is a per-bar array (not scalar) enabling different values per bar — Stage A passes SpreadModel.median broadcast, Stage B passes zeros array"
  - "numba_kernels.py isolated from accumulators.py to prevent Numba cache invalidation when non-JIT code changes"
  - "BacktestRunner uses pit_read snapshot parameter for deterministic reproducibility across runs"
  - "portfolio library symbol format: bt_{strategy_name}_{symbol} — strategy name scopes the audit trail"
metrics:
  duration: "200s"
  completed: "2026-03-22"
  tasks_completed: 2
  files_created: 7
  files_modified: 2
---

# Phase 02 Plan 06: VectorBT Pro + Numba Backtesting Stack Summary

**One-liner:** Numba @njit single-pass accumulator with spread_cost dual-stage parameter wired into BacktestRunner via pit_read, rolling_atr, and ArcticDB portfolio persistence.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Numba accumulator, VBT config, warmup service, numba_kernels | 7c2af81 | src/backtest/__init__.py, config.py, accumulators.py, numba_kernels.py, warmup.py, scripts/warmup-numba-cache.sh, tests/backtest/test_accumulators.py |
| 2 | BacktestRunner with pit_read integration and portfolio persistence | ebf1239 | src/backtest/engine.py, tests/backtest/test_engine.py |

## What Was Built

### src/backtest/accumulators.py
Single-pass Numba accumulator `single_pass_backtest(close, signal, risk_per_trade, atr, spread_cost)` decorated with `@njit(cache=True)`. Implements the dual-stage spread_cost design (D-16): Stage A passes `SpreadModel.median` broadcast array, Stage B passes zeros. Equity starts at 100,000; positions are sized via ATR fraction of equity.

### src/backtest/numba_kernels.py
`rolling_atr(high, low, close, period)` using Wilder's smoothing isolated in a separate file to prevent Numba cache invalidation when other modules change (per RESEARCH Pitfall 4).

### src/backtest/warmup.py
`warmup_numba()` calls all `@njit` functions with tiny 10-element arrays at startup. `NUMBA_CACHE_DIR=./numba_cache` is set before numba import for persistent cross-restart cache (D-17). Returns elapsed seconds.

### src/backtest/config.py
`configure_vbt()` configures VectorBT Pro with chunking.n_chunks='auto', caching.register_lazily=True, caching.use_disk=True, disk_path='/tmp/vbt_cache', and memory-aware chunk_size (80% of available RAM via psutil). Gracefully handles missing vectorbtpro package.

### src/backtest/engine.py
`BacktestRunner` class (D-14): reads from ArcticDB via `pit_read()` → `shift_features()` to prevent look-ahead bias → `rolling_atr()` for position sizing → `single_pass_backtest()` for PnL → persists to portfolio library with full metadata (D-15). `BacktestResult` dataclass is frozen/immutable for reproducibility.

### scripts/warmup-numba-cache.sh
CLI script for one-shot Numba cache warmup. Executable, sets NUMBA_CACHE_DIR before invocation.

## Tests

| Test File | Tests | Result |
|-----------|-------|--------|
| tests/backtest/test_accumulators.py | 4 | PASS |
| tests/backtest/test_engine.py | 4 | PASS |
| **Total** | **8** | **8/8 PASS** |

### Key Test Coverage
- `test_known_pnl`: Known 10-bar sequence with hand-verifiable equity growth
- `test_spread_deduction`: Confirms 2x spread per round-trip to the penny
- `test_flat_signal_no_trades`: Zero-signal produces exactly flat equity at 100,000
- `test_equity_never_negative`: Alternating signal on uptrend stays positive
- `test_reproducibility`: Same snapshot → identical equity arrays across two runs
- `test_warmup_timing`: warmup_numba() < 60s
- `test_cached_run_timing`: 1M-bar run < 5s after warmup
- `test_backtest_persists_to_portfolio_library`: Portfolio library contains bt_test_strategy_EURUSD with strategy/start/end metadata

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all data paths are wired. spread_cost defaults to zeros array (futures mode) when not supplied, which is intentional (D-16 dual-stage design).

## Self-Check: PASSED

All 9 files found on disk. Both task commits (7c2af81, ebf1239) confirmed in git log.
