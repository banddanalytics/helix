---
phase: 03-alpha-engines
plan: 05
subsystem: alpha
tags: [carry-engine, swap-rates, cross-sectional-ranking, spread-filter, stage-b-stub]
dependency_graph:
  requires:
    - 03-01 (signal_types.py, CROSS_ASSET_SYMBOLS)
    - src/execution/swap_rates.py (SwapRateCalculator, CarryResult)
  provides:
    - src/alpha/carry/carry_provider.py — CarrySignalProvider ABC
    - src/alpha/carry/forex_carry.py — ForexCarryProvider with ranking + spread filter
    - src/alpha/carry/futures_carry.py — FuturesCarryProvider Stage B stub
    - src/alpha/carry/__init__.py — package exports
  affects:
    - 03-08 (alpha ensemble — carry_engine activation in TRENDING regime)
tech_stack:
  added: []
  patterns:
    - ABC pattern for broker-agnostic carry providers (Stage A / Stage B)
    - Ordinal percentile ranking normalized to (0, 1] for cross-sectional signals
    - Spread filter: |net_carry| < 2 * median_spread -> signal override to 0
    - SwapRateCalculator.compute_annualized_carry() as the canonical carry computation
key_files:
  created:
    - src/alpha/carry/carry_provider.py
    - src/alpha/carry/forex_carry.py
    - src/alpha/carry/futures_carry.py
  modified:
    - src/alpha/carry/__init__.py
    - tests/alpha/test_carry.py
decisions:
  - "ForexCarryProvider uses ordinal ranking / n to produce (0, 1] percentile ranks — no scipy dependency"
  - "Spread filter applied after quartile assignment: only active symbols (signal != 0) checked against spread_data"
  - "FuturesCarryProvider raises NotImplementedError on both get_carry_signals and get_carry_ranks — full Stage B gate"
metrics:
  duration: 136s
  completed: "2026-03-22"
  tasks_completed: 2
  files_changed: 5
---

# Phase 3 Plan 5: Carry Signal Provider Summary

**One-liner:** Swap-based ForexCarryProvider with ordinal cross-sectional ranking and 2x-spread suppression filter, plus NotImplementedError FuturesCarryProvider Stage B stub.

## What Was Built

The carry alpha engine for Stage A Forex trading: an abstract `CarrySignalProvider` ABC, a concrete `ForexCarryProvider` that converts MT5 swap rates to annualized carry via `SwapRateCalculator`, ranks symbols cross-sectionally, and assigns +1/-1 to top/bottom quartiles with a spread-cost filter that suppresses signals where carry benefit is less than 2x the median spread. A `FuturesCarryProvider` stub enforces the Stage B boundary with `NotImplementedError`.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | CarrySignalProvider ABC, ForexCarryProvider, FuturesCarryProvider | 749c993 | carry_provider.py, forex_carry.py, futures_carry.py, __init__.py |
| 2 | Unstub and implement carry tests | 4025f44 | tests/alpha/test_carry.py |

## Decisions Made

1. **Ordinal ranking without scipy:** `sorted_symbols` ascending by `net_carry`, rank = `(idx+1)/n` — avoids a scipy dependency for a simple percentile.
2. **Spread filter placement:** Applied after quartile assignment so neutral signals (0.0) are not needlessly checked; only +1/-1 signals can be suppressed.
3. **FuturesCarryProvider gates both methods:** Both `get_carry_signals` and `get_carry_ranks` raise `NotImplementedError` to prevent partial Stage B use.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — `FuturesCarryProvider` is an intentional Stage B stub (documented in the plan). All Stage A carry functionality is fully wired.

## Self-Check: PASSED

Files exist:
- src/alpha/carry/carry_provider.py — FOUND
- src/alpha/carry/forex_carry.py — FOUND
- src/alpha/carry/futures_carry.py — FOUND
- tests/alpha/test_carry.py — FOUND

Commits exist:
- 749c993 — FOUND
- 4025f44 — FOUND

Tests: 4 passed, 0 failed, 0 skipped.
