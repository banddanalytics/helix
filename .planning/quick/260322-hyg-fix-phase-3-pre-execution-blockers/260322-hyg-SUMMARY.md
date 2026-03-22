---
phase: quick
plan: 260322-hyg
subsystem: alpha
tags: [phase3, signal-types, test-scaffold, shap, pre-execution]
dependency_graph:
  requires: [phase-02-complete]
  provides: [signal-schema-contract, tests-alpha-scaffold, shap-dependency]
  affects: [phase-03-alpha-engines]
tech_stack:
  added: [shap==0.51.0]
  patterns: [xfail-stubs, signal-schema-dataclass, pytest-fixtures-regime-data]
key_files:
  created:
    - src/alpha/signal_types.py
    - tests/alpha/__init__.py
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
    - pyproject.toml
    - src/data/bar_aggregator.py
    - tests/data/test_bar_aggregator.py
    - src/data/arctic_store.py
decisions:
  - "Use raise AssertionError() instead of assert False in xfail stubs (ruff B011 requirement)"
  - "np.ndarray[tuple[int], np.dtype[np.float64]] for fully generic-typed fixture return types (mypy strict)"
  - "Remove unused type: ignore[return-value] from arctic_store.py — arcticdb stubs now typed correctly"
metrics:
  duration: "~15 minutes"
  completed: "2026-03-22"
  tasks_completed: 2
  files_created: 11
  files_modified: 4
---

# Quick Task 260322-hyg: Fix Phase 3 Pre-Execution Blockers Summary

**One-liner:** Committed ruff formatting, installed shap 0.51.0, defined SignalRow/RegimeState/SIGNAL_COLUMNS signal schema, and scaffolded 11 xfail test stubs covering ALPH-01 through ALPH-09.

## Tasks Completed

| Task | Description | Commit | Status |
|------|-------------|--------|--------|
| 1 | Commit formatting, install shap, update pyproject.toml | 6a173ab, d908ffa | Done |
| 2 | Create signal_types.py and tests/alpha/ xfail scaffold | f0d63d6 | Done |

## Verification Results

1. `git log --oneline -1` — confirmed formatting commit `6a173ab`
2. `.venv/bin/python -c "import shap; print(shap.__version__)"` — prints `0.51.0`
3. `grep '"shap\.\*"' pyproject.toml` — matches (single overrides block, not duplicated)
4. `.venv/bin/python -c "from src.alpha.signal_types import SignalRow, RegimeState, SIGNAL_COLUMNS; print(len(SIGNAL_COLUMNS))"` — prints `8`
5. `.venv/bin/pytest tests/alpha/ --collect-only -q --no-cov` — 11 tests collected, 0 errors

## Key Artifacts

### `src/alpha/signal_types.py`

Implements the D-01/D-02/D-03 signal schema contract:
- `RegimeState(IntEnum)` — TRENDING=0, MEAN_REVERTING=1, CRISIS=2 (ordered by ascending variance)
- `SignalRow` — dataclass with symbol, engine, direction (int8), strength (float32), regime (int8), plus nullable z_score, ml_prob, carry_rank
- `SIGNAL_COLUMNS` — 8-element list for DataFrame column validation
- `ENGINE_SYMBOL_PATTERN` and `REGIME_SYMBOL_PATTERN` — ArcticDB naming constants per D-02/D-03

### `tests/alpha/conftest.py`

Four shared fixtures:
- `synthetic_returns` — 1000-bar regime-switching array (trending/mean-rev/crisis blocks), seeded rng(42)
- `synthetic_bars` — 1000-row OHLCV DataFrame, 4h frequency, session column cycling 0-3
- `six_symbol_bars` — dict[symbol, DataFrame] for 6 configured Forex symbols with varied seeds
- `mock_signal_df` — 10-row DataFrame matching SIGNAL_COLUMNS for unit testing signal consumers

### Test Stubs (11 tests)

| File | Tests | Requirements |
|------|-------|-------------|
| test_regime_detector.py | 2 | ALPH-01, ALPH-02 |
| test_calibration.py | 1 | ALPH-03 |
| test_cointegration.py | 2 | ALPH-04, ALPH-05 |
| test_carry.py | 1 | ALPH-06 |
| test_features.py | 1 | ALPH-07 |
| test_walk_forward.py | 1 | ALPH-08 |
| test_ensemble.py | 2 | ALPH-08 |
| test_orchestrator.py | 1 | ALPH-09 |

All stubs use `@pytest.mark.xfail(reason="Phase 3 not implemented", strict=False)` and `raise AssertionError("Not yet implemented")`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Pre-commit hook failures during Task 1 commit**
- **Found during:** Task 1 (first commit attempt)
- **Issue:** ruff E501 (line too long) in test_bar_aggregator.py docstring, and mypy `unused-ignore` on arctic_store.py line 53 — the arcticdb stubs were updated so the `type: ignore[return-value]` was no longer needed
- **Fix:** Shortened docstring to fit 88-char limit; removed unused `type: ignore[return-value]` from `get_library()`
- **Files modified:** `tests/data/test_bar_aggregator.py`, `src/data/arctic_store.py`
- **Commit:** 6a173ab

**2. [Rule 1 - Bug] Ruff B011 (assert False) and E501 in test stub files**
- **Found during:** Task 2 pre-commit check
- **Issue:** ruff B011 requires `raise AssertionError()` instead of `assert False`; several docstrings exceeded 88 chars; RUF002 flagged Greek letters (α, ω, β) in docstrings
- **Fix:** Changed all `assert False` to `raise AssertionError()`, shortened docstrings, replaced Greek letters with ASCII equivalents
- **Files modified:** All 9 test stub files
- **Commit:** f0d63d6

**3. [Rule 1 - Bug] mypy strict ndarray missing type parameters in conftest.py**
- **Found during:** Task 2 commit (pre-commit mypy hook)
- **Issue:** `np.ndarray` without type parameters violates mypy strict `[type-arg]`
- **Fix:** Changed return type to `np.ndarray[tuple[int], np.dtype[np.float64]]` and fixture parameter type accordingly
- **Files modified:** `tests/alpha/conftest.py`
- **Commit:** f0d63d6

## Known Stubs

The 11 test functions in `tests/alpha/` are intentional stubs — they exist to define the test contract for Phase 3 plans. Each Phase 3 plan will replace the stub body with real implementation and remove the `xfail` decorator when the feature is complete.

## Self-Check: PASSED

- FOUND: src/alpha/signal_types.py
- FOUND: tests/alpha/conftest.py
- FOUND: tests/alpha/__init__.py
- FOUND: commit 6a173ab (formatting fix)
- FOUND: commit d908ffa (shap install + pyproject.toml)
- FOUND: commit f0d63d6 (signal_types + test scaffold)
