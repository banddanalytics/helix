---
phase: 01-foundation
plan: 03
subsystem: quality
tags: [pit-validator, pre-commit, ci-cd, github-actions, look-ahead-bias]
dependency_graph:
  requires: [01-01]
  provides: [pit-compliance-checker, pre-commit-hooks, github-actions-ci]
  affects: [all-plans]
tech_stack:
  added: []
  patterns:
    - AST-based look-ahead bias detection using ast.NodeVisitor
    - Pre-commit hooks: ruff lint+format + mypy strict (CI-only for validators)
    - GitHub Actions 3-job pipeline: static-analysis -> tests -> e2e
key_files:
  created:
    - src/quality/pit_validator.py
    - scripts/pit_validator.py
    - tests/quality/test_pit_validator.py
    - .pre-commit-config.yaml
    - .github/workflows/ci.yml
  modified:
    - stubs/arcticdb_stubs.py
    - stubs/nats_stubs.py
    - stubs/mt5_stubs.py
    - src/quality/ast_validator/validator.py
    - scripts/ast_validator.py
    - src/execution/abstract.py
    - tests/execution/test_abstract.py
    - tests/quality/test_kch_validator.py
decisions:
  - Pre-commit uses local mypy with system language to access project venv deps (avoids duplicating additional_dependencies)
  - pytest and validators excluded from pre-commit per D-07/D-08/D-09 — CI only
  - PiT validation detects look-ahead bias at whole-RHS level (not per-access chain) — simpler and catches all cases
metrics:
  duration_minutes: 20
  completed_date: "2026-03-21"
  tasks_completed: 2
  files_created: 5
  files_modified: 8
---

# Phase 01 Plan 03: PiT Compliance Validator and CI/CD Integration Summary

**One-liner:** PiT validator using AST inspection for look-ahead bias in DataFrame assignments, plus ruff+mypy pre-commit hooks and 3-job GitHub Actions CI pipeline with 80% coverage gate.

## Tasks Completed

| Task | Description | Commit | Status |
|------|-------------|--------|--------|
| 1 | Implement PiT compliance validator (TDD) | ce2fa11 | Done |
| 2 | Configure pre-commit hooks and GitHub Actions CI | 11c1eff | Done |

## What Was Built

### Task 1: PiT Compliance Validator

`src/quality/pit_validator.py` implements `PiTValidator(ast.NodeVisitor)` that detects look-ahead bias in alpha engine code:

- `PRICE_COLUMNS` frozenset covers: price, volume, bid, ask, close, high, low, open, returns, spread, tick_volume
- `PiTViolation` dataclass captures: file, line, column_accessed, expression, message
- Detection logic: for each `ast.Assign` / `ast.AugAssign`, walks the full RHS subtree with `ast.walk()` to find `df['column']` subscript accesses. If any price column is accessed and no `.shift()` call appears anywhere in the RHS, a violation is recorded.
- Rolling patterns (`.rolling().std()`, `.rolling().mean()`) without a trailing `.shift(1)` are flagged identically.
- `validate_file(Path)` and `validate_directory(Path, pattern)` public API.

`scripts/pit_validator.py` CLI accepts `--source` (directory) and `--json` flags. Exits 0 if clean, 1 if any violation found.

All 14 tests pass covering: direct access without shift (violation), direct access with shift (compliant), rolling without shift (violation), rolling with shift (compliant), directory scanning, violation dataclass fields, and line number accuracy.

### Task 2: Pre-commit Hooks and GitHub Actions CI

`.pre-commit-config.yaml` runs on every commit attempt:
- `pre-commit-hooks` v5.0.0: trailing-whitespace, end-of-file-fixer, check-yaml, check-toml
- `ruff-pre-commit` v0.15.7: ruff lint (--fix) and ruff-format
- Local mypy hook using `.venv/bin/mypy --strict` (system language to use project venv)
- No pytest, no AST validator, no PiT validator in pre-commit (CI-only per D-07/D-08/D-09)

`.github/workflows/ci.yml` with 3 sequential jobs:
1. `static-analysis`: ruff check/format + mypy strict + AST/KCH validator + PiT validator
2. `tests` (needs: static-analysis): pytest with `--cov-fail-under=80`, coverage upload to codecov
3. `e2e` (needs: tests, main only): pytest tests/e2e/ with 300s timeout
- Linux-only (`ubuntu-latest`), no Windows runner (D-13)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed missing sys.path setup in scripts/pit_validator.py**
- **Found during:** Task 1 verification
- **Issue:** The CLI script imported `from src.quality.pit_validator import PiTValidator` inside `main()` without adding project root to `sys.path`, causing `ModuleNotFoundError` when run directly.
- **Fix:** Added `_PROJECT_ROOT` detection and `sys.path.insert()` pattern (matching `scripts/ast_validator.py`), moved import to module level.
- **Files modified:** `scripts/pit_validator.py`
- **Commit:** ce2fa11

**2. [Rule 3 - Blocking] Fixed pre-existing lint/type errors blocking clean pre-commit run**
- **Found during:** Task 2 verification (pre-commit run --all-files)
- **Issue:** Pre-commit found 12+ ruff errors and 4 mypy unused-ignore errors across files from Plans 01-02 and 01-04, causing the acceptance criterion `pre-commit run --all-files exits 0` to fail.
- **Fixes applied:**
  - `stubs/arcticdb_stubs.py`: removed duplicate `get_library` dict key (F601)
  - `stubs/nats_stubs.py`: merged duplicate `publish` and `subscribe` dict keys (F601)
  - `stubs/mt5_stubs.py`: wrapped long docstring line (E501)
  - `src/quality/ast_validator/validator.py`: fixed long comment (E501), replaced `Any` return type with `ModuleType` (ANN401), combined nested if into single if with `and` (SIM102)
  - `scripts/ast_validator.py`: added `# noqa: E402` on path-dependent import (E402)
  - `src/execution/abstract.py`: wrapped long docstring line (E501)
  - `tests/execution/test_abstract.py`: removed unused `# type: ignore[misc]` comments (4 instances) + fixed `.keys()` dict iteration (SIM118)
  - `tests/quality/test_kch_validator.py`: wrapped long string literals in test fixture (E501)
- **Files modified:** 8 files from prior plans
- **Commit:** 11c1eff

## Known Stubs

None — all data flows in this plan are via AST inspection of Python source files, not DataFrame operations. No stub data paths exist.

## Self-Check

Checking created files and commits exist...

## Self-Check: PASSED

- src/quality/pit_validator.py: FOUND
- scripts/pit_validator.py: FOUND
- tests/quality/test_pit_validator.py: FOUND
- .pre-commit-config.yaml: FOUND
- .github/workflows/ci.yml: FOUND
- commit ce2fa11: FOUND
- commit 11c1eff: FOUND
