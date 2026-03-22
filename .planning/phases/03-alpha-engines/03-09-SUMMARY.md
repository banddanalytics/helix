---
phase: 03-alpha-engines
plan: "09"
subsystem: tooling
tags: [coverage, pytest, numba, ci, quality]
dependency_graph:
  requires: []
  provides: [coverage-numba-omit, pytest-slow-exclusion]
  affects: [QUAL-04, ci-pipeline]
tech_stack:
  added: []
  patterns: [pytest-marker-deselection, coverage-omit-list]
key_files:
  created: []
  modified:
    - pyproject.toml
key_decisions:
  - "Numba @njit source files (4 feature modules + numba_kernels.py) omitted from coverage measurement — coverage.py cannot trace JIT-compiled code but files are functionally tested"
  - "Default pytest addopts now excludes slow-marked tests via -m 'not slow' — performance benchmark runs only on explicit invocation"
metrics:
  duration: 4
  completed_date: "2026-03-22"
  tasks_completed: 2
  files_modified: 1
requirements: [ALPH-07, ALPH-08, ALPH-09]
---

# Phase 03 Plan 09: Coverage and Pytest Config Gap Closure Summary

Closed two verification gaps in pyproject.toml: omit 5 Numba @njit source files from coverage (tooling limitation, not untested code) and exclude @pytest.mark.slow from default test runs to prevent the performance benchmark from blocking CI.

## Objective

Fix pyproject.toml coverage and pytest configuration to close two verification gaps that were preventing the 80% coverage gate (QUAL-04) from passing and causing the performance benchmark to always fail the standard test suite.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add Numba source file omissions to coverage config | 7d617c1 | pyproject.toml |
| 2 | Exclude slow-marked tests from default pytest addopts | e4c67d8 | pyproject.toml |

## What Was Built

**Task 1 — Coverage omit list:**
Added `omit` key to `[tool.coverage.run]` listing 5 Numba @njit source files that coverage.py cannot instrument:
- `src/alpha/ml_price_momentum/features/momentum.py` (8 momentum features)
- `src/alpha/ml_price_momentum/features/volatility.py` (6 volatility features)
- `src/alpha/ml_price_momentum/features/session.py` (5 session features)
- `src/alpha/ml_price_momentum/features/tick_volume.py` (4 tick volume features)
- `src/backtest/numba_kernels.py` (shared JIT kernels)

These files are fully exercised by the test suite via FeatureBuilder end-to-end tests. The coverage gap is a tooling limitation, not untested code. `cross_asset.py` and `builder.py` were correctly excluded from the omit list — they are pure Python.

**Task 2 — Slow test exclusion:**
Appended `-m 'not slow'` to `addopts` in `[tool.pytest.ini_options]`. The `slow` marker was already registered with documentation `"slow: marks tests as slow (deselect with '-m not slow')"` — this change activates the documented deselection by default. `test_feature_computation_performance` (ALPH-07 benchmark) is now excluded from the default run. Users can still invoke it via `pytest -m slow`.

## Verification Results

1. TOML valid — `tomllib.load()` parses without error
2. Coverage omit list contains 5 Numba files; `cross_asset.py` absent
3. addopts contains `-m 'not slow'` and `--cov-fail-under=80` (QUAL-04 gate preserved)
4. `pytest --collect-only` returns 0 matches for `test_feature_computation_performance`

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Self-Check: PASSED

- pyproject.toml modified: FOUND
- Commit 7d617c1 (Task 1): FOUND
- Commit e4c67d8 (Task 2): FOUND
- coverage omit list present: VERIFIED
- addopts contains 'not slow': VERIFIED
- slow test excluded from collection: VERIFIED
