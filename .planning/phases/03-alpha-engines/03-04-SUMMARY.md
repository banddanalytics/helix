---
phase: 03-alpha-engines
plan: 04
subsystem: alpha/cointegration
tags: [cointegration, johansen, hedge-ratio, z-score, half-life, mean-reverting]
dependency_graph:
  requires:
    - 03-01 — SignalRow, signal_types, test scaffold and conftest fixtures
  provides:
    - src/alpha/cointegration/johansen.py — JohansenResult, test_cointegration()
    - src/alpha/cointegration/hedge_ratio.py — RollingHedgeRatio (504-bar PiT)
    - src/alpha/cointegration/spread_signals.py — SpreadSignalGenerator (entry/exit/hard-stop)
    - src/alpha/cointegration/health_monitor.py — CointegrationHealthMonitor (half-life, breakdown)
    - src/alpha/cointegration/__init__.py — all public exports
  affects:
    - 03-07/03-08 (integration and walk-forward may consume cointegration signals)
    - CVaR engine (spread signals feed portfolio optimizer)
tech_stack:
  added: []
  patterns:
    - Johansen eigenvector normalization: beta = -evec[0,0] / evec[1,0] (y1-first ordering)
    - PiT rolling window: y1[t-window:t] Python exclusive-end slice guarantees no future data
    - Hard stop urgency: strength=1.0 when |z| > 4.0 for immediate position close
    - AR(1) half-life: -ln(2)/ln(|delta|) where delta is OLS coefficient
    - Dirichlet smoothing not needed here — all stats are rolling with explicit windows
key_files:
  created:
    - src/alpha/cointegration/johansen.py
    - src/alpha/cointegration/hedge_ratio.py
    - src/alpha/cointegration/spread_signals.py
    - src/alpha/cointegration/health_monitor.py
  modified:
    - src/alpha/cointegration/__init__.py
    - tests/alpha/test_cointegration.py
decisions:
  - "Johansen eigenvector hedge ratio uses -evec[0,0]/evec[1,0]: the plan spec had [1,0]/[0,0] which produced ~1.25 instead of ~0.8 on test fixture with true beta=0.8. Corrected via empirical verification against statsmodels output."
  - "test_cointegration() imported as johansen_test alias in test file: pytest collects any function named test_* in module namespace including re-exports, causing false fixture injection errors. Alias avoids collection without renaming the public API."
metrics:
  duration: 233
  completed_date: "2026-03-22"
  tasks_completed: 2
  files_changed: 6
---

# Phase 3 Plan 4: Johansen Cointegration Engine Summary

**One-liner:** Johansen trace test + 504-bar rolling hedge ratio + z-score entry/exit/hard-stop signals + AR(1) half-life health monitor, all PiT compliant.

## What Was Built

Complete cointegration pipeline for Mean-Reverting regime trading:

1. **`johansen.py`** — `test_cointegration(y1, y2)` wraps `statsmodels.coint_johansen` with correct eigenvector normalization. Returns `JohansenResult(cointegrated, trace_stat, crit_95, hedge_ratio)`. Uses `det_order=0, k_ar_diff=1` per research spec.

2. **`hedge_ratio.py`** — `RollingHedgeRatio(window=504, step=21)` computes Johansen hedge ratio on rolling 504-bar windows. Every 21 bars recomputes; carries forward between recomputes. The slice `y1[t-window:t]` is Python exclusive-end — bar t is never in the estimation window (PiT compliant).

3. **`spread_signals.py`** — `SpreadSignalGenerator(entry_z=2.0, exit_z=0.5, hard_stop_z=4.0, lookback=252)` generates `(direction, strength)` tuples per bar. Hard stop at |z|>4.0 sets strength=1.0 for urgency. Entry signals strength = min(|z|/entry_z, 1.0).

4. **`health_monitor.py`** — `CointegrationHealthMonitor` computes AR(1) half-life via OLS (`-ln(2)/ln(|delta|)`), and `assess_health()` returns `{half_life, reduce_position, close_all, suspend}` flags.

## Test Results

All 8 tests pass with no skips:
- `test_johansen_detects_cointegrated_pair` — trace_stat > crit_95 on seeded pair
- `test_johansen_rejects_independent_walks` — trace_stat < crit_95 on two independent RWs
- `test_hedge_ratio_converges` — |estimated_beta - 0.8| < 0.05 on 1000-bar fixture
- `test_rolling_hedge_ratio_pit_compliant` — first 200 bars NaN, finite thereafter
- `test_zscore_entry_signals` — z=-2.5 -> direction=+1; z=+2.5 -> direction=-1
- `test_zscore_hard_stop` — z=±4.5 -> direction=0, strength=1.0
- `test_half_life_computation` — delta=0.95 process: |hl - 13.5| < 1.0
- `test_health_monitor_flags` — delta=0.995 process: reduce_position=True, close_all=True

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected Johansen eigenvector indexing**
- **Found during:** Task 1 GREEN phase (test_hedge_ratio_converges failed with ~1.25 vs 0.8)
- **Issue:** Plan spec stated `hedge_ratio = -result.evec[1, 0] / result.evec[0, 0]`. For data stacked as `[y1, y2]`, this produces the inverse of the true hedge ratio.
- **Fix:** Changed to `hedge_ratio = -result.evec[0, 0] / result.evec[1, 0]`. Verified empirically: returns 0.8 for the `cointegrated_pair` fixture (y2 = 0.8*y1 + noise).
- **Files modified:** `src/alpha/cointegration/johansen.py`
- **Commit:** 58cdf8c

**2. [Rule 1 - Bug] Import alias for test_cointegration in test file**
- **Found during:** Task 1 RED phase (pytest collected `test_cointegration` as a test fixture)
- **Issue:** `from src.alpha.cointegration import test_cointegration` puts the function in the test module namespace. pytest collects any `test_*` symbol as a test item, triggering fixture injection errors for `y1`, `y2`.
- **Fix:** Imported as `test_cointegration as johansen_test` in `test_cointegration.py`. The public API name remains unchanged; only the test file import alias differs.
- **Files modified:** `tests/alpha/test_cointegration.py`
- **Commit:** 58cdf8c

## Known Stubs

None — all five test functions that were previously `pytest.mark.skip`-marked are now implemented and passing.

## Self-Check: PASSED
