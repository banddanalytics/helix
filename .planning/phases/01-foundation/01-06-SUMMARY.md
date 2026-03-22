---
phase: 01-foundation
plan: "06"
subsystem: execution-utilities
tags: [spread-model, swap-rates, lot-sizing, kelly, tdd]
dependency_graph:
  requires: ["01-04"]
  provides: ["SpreadModel", "SwapRateCalculator", "LotSizer"]
  affects: ["alpha-engines", "risk-sizing", "phase-2-sim-adapter"]
tech_stack:
  added: []
  patterns:
    - "TDD red/green with pytest"
    - "Static-method utility classes (no state in SwapRateCalculator, LotSizer)"
    - "Rolling deque for fixed-window statistics (SpreadModel)"
    - "math.floor for deterministic floor-rounding to volume_step"
key_files:
  created:
    - src/execution/spread_model.py
    - src/execution/swap_rates.py
    - src/execution/lot_sizing.py
    - tests/execution/test_spread_model.py
    - tests/execution/test_swap_rates.py
    - tests/execution/test_lot_sizing.py
  modified: []
decisions:
  - "SpreadModel wiring into SimAdapter deferred to Phase 2 — Phase 1 SimAdapter uses fixed spread_pips float; Phase 2 replaces with SpreadModel.median after ArcticDB tick history is available"
  - "LotSizer floor-rounds to volume_step via math.floor (never over-sizes positions)"
  - "SwapRateCalculator uses frozen dataclass CarryResult to prevent accidental mutation"
metrics:
  duration_minutes: 3
  completed_date: "2026-03-21"
  tasks_completed: 2
  files_created: 6
  files_modified: 0
---

# Phase 01 Plan 06: Execution Utility Modules Summary

**One-liner:** Variable spread tracking, annualized carry from broker swap points, and Kelly-to-lot sizing with floor rounding and broker volume constraints.

## What Was Built

Three execution utility modules implementing requirements EXEC-04, EXEC-05, and EXEC-06:

1. **`src/execution/spread_model.py`** — `SpreadModel` maintains a rolling deque of observed spread values (default 10,000 entries). Provides `median`, `p95`, and `volatility` properties backed by numpy. `cost_adjusted_signal` suppresses signals when round-trip spread cost exceeds 50% of expected profit, attenuates otherwise. Wiring into `SimAdapter` is deferred to Phase 2 (per plan frontmatter key_links).

2. **`src/execution/swap_rates.py`** — `SwapRateCalculator` with `compute_annualized_carry` static method. Converts MT5 daily swap points to annualized percentage carry using `(swap_points * point * 365) / mid_price * 100`. Returns frozen `CarryResult` dataclass. Guards against zero mid_price.

3. **`src/execution/lot_sizing.py`** — `LotSizer` with `kelly_to_lots` and `compute_pip_value` static methods. `kelly_to_lots` computes `(equity * kelly_fraction) / (stop_loss_pips * pip_value)`, floor-rounds to `volume_step` via `math.floor`, then clamps to `[volume_min, volume_max]`. Returns 0.0 for non-positive kelly fraction, stop-loss, or pip value.

## Commits

| Hash | Message |
|------|---------|
| 0cfb518 | test(01-06): add failing tests for SpreadModel (TDD red) |
| ca80bd7 | feat(01-06): implement SpreadModel with cost-adjusted signal suppression |
| 74aecd4 | test(01-06): add failing tests for SwapRateCalculator and LotSizer (TDD red) |
| c6f6655 | feat(01-06): implement SwapRateCalculator and LotSizer |

## Test Results

- 32 tests across 3 files — all pass
- Coverage: spread_model.py 100%, swap_rates.py 100%, lot_sizing.py 100%
- `mypy src/execution/ --strict` — clean (10 source files)

## Verification

```
.venv/bin/mypy src/execution/ --strict   -> Success: no issues found in 10 source files
32 tests pass, 100% coverage on all three new modules
```

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None. All three modules are fully wired with real logic. SpreadModel-SimAdapter integration is intentionally deferred (documented in plan frontmatter) pending ArcticDB tick history in Phase 2.

## Self-Check: PASSED

- src/execution/spread_model.py: FOUND
- src/execution/swap_rates.py: FOUND
- src/execution/lot_sizing.py: FOUND
- tests/execution/test_spread_model.py: FOUND
- tests/execution/test_swap_rates.py: FOUND
- tests/execution/test_lot_sizing.py: FOUND
- .planning/phases/01-foundation/01-06-SUMMARY.md: FOUND
- Commit 0cfb518: FOUND
- Commit ca80bd7: FOUND
- Commit 74aecd4: FOUND
- Commit c6f6655: FOUND
