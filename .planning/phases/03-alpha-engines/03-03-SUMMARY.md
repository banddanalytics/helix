---
phase: 03-alpha-engines
plan: "03"
subsystem: regime-calibration
tags: [hmm-garch, recalibration, dirichlet-smoothing, stationarity-gate, state-agreement-gate, atomic-swap]
dependency_graph:
  requires: ["03-02"]
  provides: ["RecalibrationService", "config/regime_calibration.yaml"]
  affects: ["regime-detector", "alpha-engine-pipeline"]
tech_stack:
  added: ["pyyaml (yaml.safe_load)"]
  patterns:
    - "TDD RED-GREEN cycle for RecalibrationService"
    - "Dirichlet smoothing via transmat + concentration then row-normalize"
    - "Two-gate validation (stationarity + state agreement) before model swap"
    - "Atomic pending model pattern — apply_pending() at bar boundary"
key_files:
  created:
    - src/alpha/regime/calibration.py
    - config/regime_calibration.yaml
    - tests/alpha/test_calibration_tdd.py
  modified:
    - src/alpha/regime/__init__.py
    - tests/alpha/test_calibration.py
decisions:
  - "RecalibrationService holds reference to active detector and swaps atomically via apply_pending() — pending model is never active until explicitly applied"
  - "Dirichlet smoothing applied post-fit by adding concentration scalar then row-normalizing — ensures no zero transition probabilities without modifying HMMGARCHRegimeDetector.fit()"
  - "Gate 1 uses stationarity_threshold=1.0 from YAML config — alpha+beta must be strictly less than 1.0"
  - "Gate 2 only runs when current detector is already fitted — avoids comparison against unfitted initial state"
  - "Drift warning logs once per recalibration call (early return after first drift) — prevents log flooding"
metrics:
  duration: "182 seconds"
  completed_date: "2026-03-22"
  tasks_completed: 2
  files_changed: 5
---

# Phase 03 Plan 03: Regime Recalibration Service Summary

**One-liner:** Weekly Baum-Welch HMM-GARCH recalibration with Dirichlet smoothing, stationarity gate, 90% state-agreement gate, and atomic pending-model swap.

## What Was Built

`RecalibrationService` (`src/alpha/regime/calibration.py`) — wraps an `HMMGARCHRegimeDetector` and manages weekly refitting with safe validation before model hot-swap.

Key behaviors:
- `recalibrate(returns)` creates a fresh detector, fits it, applies Dirichlet smoothing (`concentration=0.01`), validates through two gates, then stores as `_pending`.
- `apply_pending()` atomically promotes `_pending` to the active detector — called at the next bar boundary to prevent mid-bar state transitions.
- Gate 1 (Stationarity): rejects refits where `alpha + beta >= 1.0` for any GARCH state.
- Gate 2 (State Agreement): rejects refits with `< 90%` agreement on last 100 bars vs. the current detector.
- Drift warning: logs `WARNING` when any GARCH parameter drifts `> 50%` from last fitted values; does not block the swap.

Config (`config/regime_calibration.yaml`) specifies schedule, thresholds, lookback, and Dirichlet concentration.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Implement RecalibrationService with two-gate validation | 34abfa6 | calibration.py, regime_calibration.yaml, __init__.py, test_calibration_tdd.py |
| 2 | Unstub and implement calibration tests | 3885ee2 | test_calibration.py |

## Test Results

```
tests/alpha/test_calibration.py .....   5 passed
```

- `test_weekly_recalibration_produces_valid_model` — end-to-end refit + apply_pending
- `test_dirichlet_smoothing_no_zero_transitions` — `np.all(transmat > 0)` after smoothing
- `test_parameter_drift_warning` — omega patched 100x, WARNING with "drift" logged
- `test_stationarity_gate_rejects_invalid` — alpha+beta=1.1 patched, returns False
- `test_state_agreement_gate` — predict_viterbi flipped, returns False

## Deviations from Plan

### Auto-added Items

**1. [Rule 2 - Missing functionality] TDD Red test file `test_calibration_tdd.py`**
- **Found during:** Task 1 (TDD protocol)
- **Issue:** Plan specified TDD with RED phase but test stubs were in `test_calibration.py` with `@pytest.mark.skip`. A separate TDD RED file was needed to prove tests fail before implementation.
- **Fix:** Created `tests/alpha/test_calibration_tdd.py` with 7 failing tests (ImportError at collection), then implemented calibration.py to make them pass.
- **Files modified:** tests/alpha/test_calibration_tdd.py (new)
- **Commit:** 34abfa6

None of the plan's core specifications were deviated from. Implementation matched the spec exactly.

## Known Stubs

None — all behaviors are fully implemented with real logic.

## Self-Check: PASSED

- src/alpha/regime/calibration.py: FOUND
- config/regime_calibration.yaml: FOUND
- tests/alpha/test_calibration.py: FOUND
- Commit 34abfa6: FOUND
- Commit 3885ee2: FOUND
