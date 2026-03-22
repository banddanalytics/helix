---
phase: 03-alpha-engines
plan: 01
subsystem: alpha
tags: [signal-schema, test-scaffold, shap, regime-detection]
dependency_graph:
  requires: []
  provides:
    - src/alpha/signal_types.py — SignalRow, RegimeState, SIGNAL_COLUMNS, REGIME_ACTIVATION
    - tests/alpha/ — 8 test files with 32 skip-marked stubs
    - tests/alpha/conftest.py — shared fixtures for all alpha engine tests
  affects:
    - All Phase 3 plans (03-02 through 03-08) depend on this scaffold
tech_stack:
  added: [shap==0.51.0]
  patterns:
    - SignalRow dataclass with typed fields per D-01 signal schema
    - pytest.mark.skip stubs with plan reference in reason string
    - Fixture-based test data (synthetic_returns, cointegrated_pair, sample_bar_data)
key_files:
  created:
    - src/alpha/signal_types.py
    - tests/alpha/conftest.py
    - tests/alpha/test_regime_detector.py
    - tests/alpha/test_calibration.py
    - tests/alpha/test_cointegration.py
    - tests/alpha/test_carry.py
    - tests/alpha/test_features.py
    - tests/alpha/test_walk_forward.py
    - tests/alpha/test_ensemble.py
    - tests/alpha/test_orchestrator.py
  modified:
    - src/alpha/__init__.py
decisions:
  - "Signal schema uses plain Python int/float types instead of np.int8/np.float32 in SignalRow fields — numpy scalar types are annotated but dataclass fields use stdlib types for broader compatibility"
  - "conftest.py synthetic_returns uses 2000 bars (666+666+668) to match plan spec for HMM training data requirements"
  - "Test stubs use pytest.mark.skip (not xfail) to make missing implementations immediately visible rather than silently passing"
metrics:
  duration: 193s
  completed_date: "2026-03-22"
  tasks_completed: 2
  files_created: 10
  files_modified: 1
---

# Phase 3 Plan 01: Alpha Engine Test Scaffold and Signal Schema

Signal schema contract and test scaffold for Phase 3 alpha engines — 32 skip-marked stubs across 8 files with shared fixtures and full REGIME_ACTIVATION mapping.

## What Was Built

### Task 1: Signal Schema Contract

`src/alpha/signal_types.py` defines the typed signal contract used by all 4 alpha engines:

- `RegimeState(IntEnum)`: TRENDING=0, MEAN_REVERTING=1, CRISIS=2
- `SignalRow`: 8-field dataclass (symbol, engine, direction, strength, regime, z_score, ml_prob, carry_rank)
- `SIGNAL_COLUMNS`: ordered list of all 8 column names
- `REGIME_ACTIVATION`: maps each regime to its active engines per D-05 (CRISIS → empty list)
- `CONFIGURED_PAIRS`: 3 cointegration pairs (AUDUSD/NZDUSD, EURUSD/GBPUSD, USDJPY/USDCHF)
- `CROSS_ASSET_SYMBOLS`: 6 tracked symbols

`src/alpha/__init__.py` re-exports all public symbols for clean imports.

### Task 2: Test Scaffold

`tests/alpha/conftest.py` provides:
- `synthetic_returns`: 2000-bar regime-switching returns (3 volatility segments)
- `cointegrated_pair`: paired (y1, y2) arrays with known hedge ratio 0.8
- `sample_bar_data`: 500-bar OHLCV dict as numpy arrays
- `sample_signal_df`: 10-row DataFrame matching SIGNAL_COLUMNS schema
- `synthetic_bars`: 2000-row pandas OHLCV DataFrame with DatetimeIndex
- `six_symbol_bars`, `mock_signal_df`: additional fixtures

8 test files with 32 total skip-marked stubs covering all 9 alpha engine requirements:

| File | Tests | Requirements |
|------|-------|-------------|
| test_regime_detector.py | 4 | ALPH-01, ALPH-02 |
| test_calibration.py | 5 | ALPH-03 |
| test_cointegration.py | 5 | ALPH-04, ALPH-05 |
| test_carry.py | 4 | ALPH-06 |
| test_features.py | 4 | ALPH-07 |
| test_walk_forward.py | 3 | ALPH-08 |
| test_ensemble.py | 3 | ALPH-08 |
| test_orchestrator.py | 4 | ALPH-09 |

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | f2f5e10 | feat(03-01): add signal schema contract |
| 2 | 6a8f233 | feat(03-01): scaffold all alpha engine test stubs |

## Verification Results

```
shap.__version__ == "0.51.0"           PASS
pyproject.toml contains "shap.*"       PASS
from src.alpha.signal_types import ... PASS (8 columns, 3 states, crisis=[], 3 pairs, 6 symbols)
pytest --collect-only tests/alpha/     32 tests collected
pytest tests/alpha/ -x -q --no-cov    32 skipped in 0.18s
grep pytest.mark.skip tests/alpha/    32 occurrences
```

## Deviations from Plan

### Pre-existing Work

**Quick task 260322-hyg (prior session):** Had already installed shap 0.51.0, added `"shap.*"` to mypy overrides, created a partial `signal_types.py` (missing REGIME_ACTIVATION, CONFIGURED_PAIRS, CROSS_ASSET_SYMBOLS), and scaffolded 11 xfail stubs.

**What this plan added:**
- Completed `signal_types.py` with the 3 missing constants
- Replaced xfail markers with skip markers (more explicit for stubs)
- Expanded from 11 to 32 stubs (2-5 per file vs 1 per file previously)
- Added 4 new fixtures (cointegrated_pair, sample_bar_data, sample_signal_df, mock_signal_df) to conftest.py
- Added RegimeState import to conftest.py

None of these constitute deviations from the plan — they are completions of the plan's required acceptance criteria.

## Known Stubs

All 32 test functions are intentional stubs. Each raises `AssertionError("Not yet implemented")` under a `pytest.mark.skip` decorator. They will be implemented in plans 03-02 through 03-07 as their respective alpha engines are built. No stub prevents the plan's goal (test scaffold setup) from being achieved.

## Self-Check: PASSED
