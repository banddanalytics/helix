---
phase: 02-data-engineering
plan: "03"
subsystem: data
tags: [arcticdb, tick-writer, quality-flagging, threading, forex]
dependency_graph:
  requires: [02-02]
  provides: [TickWriter class, quality-flagged tick storage in forex_ticks library]
  affects: [02-04-bar-aggregator, pit-manager]
tech_stack:
  added: []
  patterns:
    - Non-blocking write() with Lock-protected defaultdict buffer per symbol
    - Background daemon thread flush loop with threading.Event for shutdown
    - Lazy-initialized ArcticDB store instance per TickWriter (avoids LMDB multi-open)
    - int8 quality flags — stored with ticks, never discarded (D-07)
    - sort_index() before append for ArcticDB monotonic index requirement
key_files:
  created:
    - src/data/forex_writer.py
  modified:
    - tests/data/test_forex_writer.py
decisions:
  - Single ArcticDB store instance per TickWriter instance (not module-level singleton) prevents LMDB multi-open warning across tests
  - write_if_missing kwarg removed — ArcticDB append() creates symbol automatically on first call
  - Duplicate detection uses combined mask of index.duplicated AND df.duplicated(subset=bid/ask) — both conditions required
metrics:
  duration_minutes: 2
  completed_date: "2026-03-22"
  tasks_completed: 1
  files_created: 1
  files_modified: 1
---

# Phase 2 Plan 3: Forex Tick Writer Summary

**One-liner:** TickWriter with per-symbol Lock buffer, 10K/1s dual-trigger flush, and int8 quality flagging (clean/rollover_spike/weekend_gap/duplicate) via ArcticDB append.

## What Was Built

`src/data/forex_writer.py` — `TickWriter` class that:

- Buffers incoming `Tick` dataclasses per symbol in a thread-safe `defaultdict` protected by `threading.Lock`
- Triggers flush when a symbol's buffer reaches `FLUSH_TICKS = 10_000` (inline, during `write()`)
- Background daemon thread flushes all symbols every `FLUSH_SECONDS = 1.0` second
- Converts buffers to pandas DataFrames and applies `_flag_quality()` before `lib.append()`
- Sorts DataFrame index before append to satisfy ArcticDB's monotonic index requirement
- Logs flush events and quality flags to `helix.data` logger per D-08

Quality flags applied as `int8` column (D-07 — stored, not discarded):
- `0` = clean (default)
- `1` = rollover_spike (spread > 5x median at 00:00 UTC hour)
- `2` = weekend_gap (Saturday or Sunday, dayofweek >= 5)
- `3` = duplicate (same timestamp + bid + ask, first occurrence kept clean)

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 (RED) | Failing tests for TickWriter behavior | 09a3606 |
| 1 (GREEN) | TickWriter implementation making all 8 tests pass | 5f2fda5 |

## Tests

All 8 tests in `tests/data/test_forex_writer.py` pass:

- `test_batch_flush_at_10k_ticks` — 10K ticks trigger flush without background thread
- `test_timer_flush_at_1s` — 100 ticks flushed after 1.5s with background thread running
- `test_quality_flags` — quality column dtype is int8; clean and weekend_gap values verified
- `test_duplicate_detection` — first of 3 identical ticks stays clean, others flagged 3
- `test_rollover_spike_detection` — tick at 00:00 UTC with 100x spread flagged quality=1
- `test_weekend_gap_detection` — Saturday and Sunday ticks flagged quality=2
- `test_append_sorts_by_timestamp` — reverse-chronological writes produce monotonic index
- `test_writer_does_not_block_caller` — 1000 write() calls average < 1ms each

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed invalid `write_if_missing` kwarg from `lib.append()`**
- **Found during:** Task 1 GREEN phase, first test run
- **Issue:** Plan code snippet used `lib.append(symbol, df, write_if_missing=True)` but ArcticDB 6.10.2 does not support this kwarg
- **Fix:** Removed the kwarg — verified that `lib.append()` creates the symbol automatically on first call
- **Files modified:** `src/data/forex_writer.py`
- **Commit:** 5f2fda5

**2. [Rule 1 - Bug] Fixed LMDB multiple-open by caching store instance in TickWriter**
- **Found during:** Task 1 GREEN phase
- **Issue:** Plan code created a new `adb.Arctic(uri)` on every `_flush_symbol()` call, triggering LMDB multi-open warnings
- **Fix:** Added `self._store` lazy-initialized instance so each TickWriter opens LMDB once
- **Files modified:** `src/data/forex_writer.py`
- **Commit:** 5f2fda5

**3. [Rule 1 - Bug] Fixed invalid timestamp string in `test_timer_flush_at_1s`**
- **Found during:** Task 1 GREEN phase, second test run
- **Issue:** Loop used `f"2024-01-03T10:00:{i:02d}"` which generated "2024-01-03T10:00:60" (seconds=60) for i=60
- **Fix:** Changed to `f"2024-01-03T10:{i // 60:02d}:{i % 60:02d}"` to correctly roll over into minutes
- **Files modified:** `tests/data/test_forex_writer.py`
- **Commit:** 5f2fda5

## Known Stubs

None. TickWriter is fully wired to ArcticDB — no placeholder data or mock returns.

## Self-Check

Files exist:
- `src/data/forex_writer.py`: FOUND
- `tests/data/test_forex_writer.py`: FOUND

Commits exist:
- `09a3606`: test(02-03) RED phase — FOUND
- `5f2fda5`: feat(02-03) GREEN implementation — FOUND

## Self-Check: PASSED
