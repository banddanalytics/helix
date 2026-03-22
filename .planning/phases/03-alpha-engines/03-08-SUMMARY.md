---
phase: 03-alpha-engines
plan: 08
subsystem: alpha
tags: [regime-orchestrator, hmm-garch, hysteresis, arcticdb, cross-asset-cache, signal-persistence]

# Dependency graph
requires:
  - phase: 03-02
    provides: OnlineRegimeFilter for real-time regime update
  - phase: 03-03
    provides: RecalibrationService for pending model swap
  - phase: 03-04
    provides: signal_types (RegimeState, REGIME_ACTIVATION, CROSS_ASSET_SYMBOLS, SignalRow)
  - phase: 03-05
    provides: ForexCarryProvider (carry_engine)
  - phase: 03-07
    provides: WalkForwardEngine (ml_engine)
provides:
  - RegimeOrchestrator class: central coordinator gating all 4 engines by regime state
  - CrossAssetCache class: pre-loads 252-bar window for all 6 symbols, O(1) incremental update
  - src/alpha/__init__.py exports RegimeOrchestrator, CrossAssetCache
affects: [04-risk-engine, integration-tests, live-trading]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Hysteresis dwell: 20-bar counter resets on regime change; new regime only accepted when dwell_counter >= 20"
    - "Atomic model swap: apply_pending() called at bar start before any computation (D-12)"
    - "CRISIS reduce-only: REGIME_ACTIVATION map returns [] for CRISIS — no engine calls"
    - "ArcticDB append-then-write: lib.append() tried first, lib.write() as fallback (Research Pitfall 6)"

key-files:
  created:
    - src/alpha/orchestrator.py
  modified:
    - src/alpha/__init__.py
    - tests/alpha/test_orchestrator.py

key-decisions:
  - "initial_regime parameter added to RegimeOrchestrator constructor to support testing without hysteresis settling period"
  - "exit_threshold (0.30) AND enter_threshold checked on dwell expiry — regime switch on either condition"
  - "CrossAssetCache.update() uses pd.concat + iloc[-lookback:] for O(1) window maintenance"

patterns-established:
  - "Pattern 1: All engine calls go through RegimeOrchestrator.on_bar() — engines have no regime awareness"
  - "Pattern 2: Pending model applied atomically at bar boundary — no mid-bar model changes"
  - "Pattern 3: TDD with initial_regime injection for unit testing regime-specific behavior without hysteresis settling"

requirements-completed: [ALPH-09]

# Metrics
duration: 4min
completed: 2026-03-22
---

# Phase 3 Plan 08: RegimeOrchestrator Summary

**RegimeOrchestrator with 20-bar hysteresis dwell, CRISIS reduce-only gating, and ArcticDB signal/regime persistence via CrossAssetCache**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-03-22T15:23:12Z
- **Completed:** 2026-03-22T15:27:00Z
- **Tasks:** 2 (TDD: RED → GREEN)
- **Files modified:** 3

## Accomplishments
- CrossAssetCache: pre-loads 252 bars via `pit_read()` for all 6 cross-asset symbols; O(1) incremental bar append with `pd.concat + iloc[-lookback:]`
- RegimeOrchestrator gates strategy activation via `REGIME_ACTIVATION` map; CRISIS returns empty list (reduce-only)
- 20-bar hysteresis dwell logic: `_dwell_counter` resets on regime change; new regime accepted only after 20+ bars with sufficient confidence
- Atomic pending model swap: `apply_pending()` called at bar start before any computation (D-12)
- Async `persist_signals()` and `persist_regime_state()` write to ArcticDB `signals` library with `{engine}_{symbol}` and `regime_{symbol}` patterns
- All 5 orchestrator tests pass; exports added to `src/alpha/__init__.py`

## Task Commits

Each task was committed atomically:

1. **TDD RED (failing tests)** - `1c617e0` (test)
2. **Task 1+2: RegimeOrchestrator + tests GREEN** - `acb3066` (feat)

## Files Created/Modified
- `src/alpha/orchestrator.py` — CrossAssetCache and RegimeOrchestrator implementation (260 lines)
- `src/alpha/__init__.py` — added RegimeOrchestrator, CrossAssetCache exports
- `tests/alpha/test_orchestrator.py` — 5 tests: trending/mean-reverting/crisis activation, 20-bar hysteresis, pending model swap order

## Decisions Made

- Added `initial_regime` parameter to `RegimeOrchestrator.__init__()` to enable clean unit testing without a 20-bar settling period. Tests for MEAN_REVERTING/CRISIS use `initial_regime=` to start directly in the target regime.
- `exit_threshold` (0.30) check in hysteresis: a regime switch occurs when dwell >= 20 AND either `confidence >= enter_threshold[new_regime]` OR `current_confidence <= exit_threshold`. This matches the spec's entry + exit threshold design.
- CrossAssetCache uses `pd.concat + iloc[-lookback:]` for incremental updates — simple and correct for moderate bar rates.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test isolation: initial regime parameter**
- **Found during:** Task 2 (test_mean_reverting_activates_cointegration)
- **Issue:** Default `initial_regime=TRENDING` caused ml+carry engines to be called during the first 20 bars of any test starting in MEAN_REVERTING, making the `.called` assertion fail despite correct behavior after dwell
- **Fix:** Added `initial_regime: RegimeState = RegimeState.TRENDING` parameter to `RegimeOrchestrator.__init__()`. Tests for non-TRENDING regimes pass `initial_regime=regime` to skip the settling period
- **Files modified:** `src/alpha/orchestrator.py`, `tests/alpha/test_orchestrator.py`
- **Verification:** All 5 tests pass
- **Committed in:** `acb3066` (Task 1+2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug in test isolation)
**Impact on plan:** The `initial_regime` parameter is a pure testing affordance; it does not change production behavior (default is still TRENDING). No scope creep.

## Issues Encountered

- Pre-existing coverage failure: `pytest tests/alpha/ --cov=src/alpha --cov-fail-under=80` reports 31.62% due to Numba feature sub-modules with minimal test coverage (10-18%). This is a pre-existing issue from plans 03-04 through 03-07 and is out of scope for 03-08.
- Pre-existing performance failure: `test_feature_computation_performance` fails (9.55s > 5s limit). Pre-existing from 03-07.
- Both issues logged to `.planning/phases/03-alpha-engines/deferred-items.md`.

## Next Phase Readiness
- RegimeOrchestrator is the central integration seam for Phase 4 risk engine — it provides the `current_regime` property needed for Kelly regime multipliers
- `persist_signals()` / `persist_regime_state()` are async and ready for NATS JetStream integration (Phase 4)
- `CrossAssetCache` provides the ML feature window data; `cache.get_data()` returns dict for injection into `FeatureBuilder`

---
*Phase: 03-alpha-engines*
*Completed: 2026-03-22*
