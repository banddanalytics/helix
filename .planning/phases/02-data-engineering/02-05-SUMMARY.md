---
phase: 02-data-engineering
plan: "05"
subsystem: data
tags: [pit-compliance, arcticdb, snapshots, look-ahead-bias, scheduler]
dependency_graph:
  requires: [02-02]
  provides: [pit_read, validate_pit_compliance, shift_features, create_snapshot, SnapshotScheduler]
  affects: [03-alpha-engines, backtesting]
tech_stack:
  added: []
  patterns:
    - ArcticDB date_range=(None, as_of_timestamp) for native temporal cutoff
    - IC analysis for look-ahead bias detection (contemp vs forward IC with 1.5x threshold)
    - asyncio.to_thread for non-blocking ArcticDB calls in async scheduler
    - eod_YYYYMMDD snapshot naming convention with created_at metadata
key_files:
  created:
    - src/data/pit_manager.py
    - src/data/snapshot_scheduler.py
  modified:
    - tests/data/test_pit_integrity.py
decisions:
  - "pit_read uses ArcticDB native date_range=(None, as_of_timestamp) rather than post-filtering — per D-11, database-level filtering is more efficient and correct"
  - "validate_pit_compliance uses IC analysis with 1.5x threshold (D-13) — contemporaneous IC exceeding 1.5x forward IC is the look-ahead bias signal"
  - "SnapshotScheduler.backfill_missed() creates snapshots reflecting current library state, not historical — this is a known limitation documented in RESEARCH Pitfall 5"
metrics:
  duration: "3 minutes"
  completed: "2026-03-22"
  tasks: 2
  files_created: 3
  files_modified: 1
---

# Phase 2 Plan 05: PiT Data Manager and Snapshot Scheduler Summary

**One-liner:** ArcticDB date_range PiT read with IC-based look-ahead bias detection, shift_features helper, and async EOD snapshot scheduler with startup backfill.

## What Was Built

### Task 1: PiT Data Manager (`src/data/pit_manager.py`)

Implements four core functions:

- **`pit_read()`** — reads ArcticDB library with `date_range=(None, as_of_timestamp)` for native temporal cutoff. Supports optional snapshot version via `as_of` parameter.
- **`validate_pit_compliance()`** — computes contemporaneous IC and forward IC; raises `LookAheadBiasError` if `abs(contemp_ic) > abs(forward_ic) * 1.5` per D-13.
- **`shift_features()`** — applies `.shift(periods)` to specified DataFrame columns, resulting in NaN in the first row, preventing same-bar signal execution.
- **`create_snapshot()`** — creates named ArcticDB snapshot with `created_at` metadata in ISO 8601 UTC format per D-09.

### Task 2: Snapshot Scheduler (`src/data/snapshot_scheduler.py`)

Implements `SnapshotScheduler` class:

- **`backfill_missed()`** — async method that detects the most recent `eod_YYYYMMDD` snapshot, then creates snapshots for each missed day up to yesterday. Returns count of snapshots created.
- **`create_eod_snapshot()`** — creates today's `eod_YYYYMMDD` snapshot for all managed libraries.
- **`run()`** — async scheduler loop that waits until 22:00 UTC daily, creates EOD snapshots, repeats.
- **`stop()`** — signals the scheduler to exit cleanly.

### Tests (`tests/data/test_pit_integrity.py`)

8 tests covering all plan requirements:

1. `test_pit_read_cutoff` — verifies no rows beyond `as_of_timestamp`
2. `test_pit_read_inclusive` — verifies row at exactly `as_of_timestamp` is included
3. `test_contemp_ic_violation` — verifies `LookAheadBiasError` raised for contemporaneous signal
4. `test_contemp_ic_compliant` — verifies no error for legitimately shifted signal
5. `test_shift_features_applies_shift` — verifies first row NaN, row 1 equals original row 0
6. `test_snapshot_isolation` — write after snapshot not visible; write before visible
7. `test_eod_snapshot_naming` — `eod_YYYYMMDD` key present with `created_at` metadata
8. `test_startup_backfill_missed_snapshots` — scheduler creates 2 missing days correctly

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test_contemp_ic_compliant signal construction**

- **Found during:** Task 1 TDD GREEN phase
- **Issue:** Initial test used `returns.shift(1).fillna(0)` as signal, but this produces a lagged version of IID noise, which has near-zero forward IC AND near-zero contemporaneous IC — making the IC ratio undefined/unpredictable. The test was randomly failing because random IID noise can produce any IC ratio.
- **Fix:** Redesigned test construction: `returns[t] = signal[t-1] + small_noise`. This guarantees `forward_ic = corr(signal[t], returns[t+1]) = corr(signal[t], signal[t] + noise) ≈ 1.0` and `contemp_ic = corr(signal[t], returns[t]) = corr(signal[t], signal[t-1] + noise) ≈ 0`, which deterministically satisfies the 1.5x threshold.
- **Files modified:** `tests/data/test_pit_integrity.py`
- **Commit:** fb75614

## Known Stubs

None — all functions are fully implemented with real ArcticDB integration.

## Self-Check: PASSED

- src/data/pit_manager.py: FOUND
- src/data/snapshot_scheduler.py: FOUND
- tests/data/test_pit_integrity.py: FOUND
- Commit dbd786c (test RED): FOUND
- Commit fb75614 (feat Task 1): FOUND
- Commit 36ad032 (feat Task 2): FOUND
