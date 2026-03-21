---
phase: 01-foundation
plan: 02
subsystem: quality
tags: [ast-validation, kch, phantom-api, stubs, tdd]
dependency_graph:
  requires: [01-01]
  provides: [AST validator CLI, KCHValidator, ASTExtractor, Violation, StubGenerator, 8 library stubs]
  affects: [CI pipeline, all future phases — code must pass KCH validation]
tech_stack:
  added: []
  patterns:
    - TDD red/green/refactor with pytest
    - ast.NodeVisitor for Python AST walking
    - importlib + inspect.signature() for library introspection
    - difflib.get_close_matches() for Levenshtein parameter suggestions
    - dataclasses for typed violation reports
key_files:
  created:
    - src/quality/ast_validator/extractor.py
    - src/quality/ast_validator/validator.py
    - src/quality/ast_validator/stub_generator.py
    - scripts/ast_validator.py
    - stubs/mt5_stubs.py
    - stubs/arcticdb_stubs.py
    - stubs/zmq_stubs.py
    - stubs/nats_stubs.py
    - stubs/xgboost_stubs.py
    - stubs/hmmlearn_stubs.py
    - stubs/arch_stubs.py
    - stubs/statsmodels_stubs.py
    - tests/quality/test_ast_extractor.py
    - tests/quality/test_kch_validator.py
    - tests/quality/test_stub_generator.py
  modified:
    - src/quality/ast_validator/__init__.py
decisions:
  - Stubs use flat dict format {lib -> {func -> set_of_kwargs}} — simple to load and compare
  - arcticdb stub intentionally excludes 'upsert' as the canonical phantom-function test case
  - Validator flags PHANTOM_FUNCTION for any call not in the imported library's stub
  - MT5 stub is hand-written (Windows-only library not importable on Linux)
  - StubGenerator uses importlib + inspect.signature() for auto-generation of real library stubs
  - CLI outputs JSON array to stdout for machine-parseable violation reports
metrics:
  duration: 14 minutes
  completed: 2026-03-21T22:24:00Z
  tasks_completed: 2
  files_created: 15
  files_modified: 3
---

# Phase 01 Plan 02: AST/KCH Hallucination Detection Pipeline Summary

**One-liner:** AST-based phantom API detector with difflib parameter suggestions, 8 hand-crafted library stubs, and a JSON CLI — 94% branch coverage on src/quality/ast_validator/.

## What Was Built

Two tasks completed via TDD (red → green → refactor):

**Task 1 — ASTExtractor + KCHValidator:**
- `ASTExtractor` walks Python ASTs using `ast.NodeVisitor`, extracting imports, function calls (with kwargs set and lineno), and attribute accesses.
- `KCHValidator` loads `*_stubs.py` files from a directory and validates source files against them. Detects PHANTOM_FUNCTION (CRITICAL), WRONG_PARAMETER (WARNING, with difflib suggestion), and PHANTOM_IMPORT (CRITICAL).
- `Violation` dataclass carries file, line, severity, violation_type, message, suggestion.
- 60 tests pass, 94% branch coverage on the module.

**Task 2 — StubGenerator + 8 stubs + CLI:**
- `StubGenerator.introspect_module()` uses `importlib` and `inspect.signature()` to extract real API surfaces from installed libraries.
- `StubGenerator.generate_stub_file()` serializes stubs to valid Python files loadable by KCHValidator.
- 8 stub files created: MT5 (hand-written), arcticdb (upsert intentionally absent), zmq, nats, xgboost, hmmlearn, arch, statsmodels.
- `scripts/ast_validator.py`: CLI with `--stubs`/`--source` flags, JSON output, exit 0 (clean) or 1 (CRITICAL violations).

## Verification Results

```
60 passed, 1 warning
Coverage: 94% on src/quality/ast_validator/ (target: 85%)
mypy --strict: Success: no issues found in 4 source files
python scripts/ast_validator.py --stubs stubs/ --source src/ → [] exit 0
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] arcticdb stub missing Arctic() and get_library() methods**
- **Found during:** Task 1 GREEN phase — test_valid_function_no_violation failed
- **Issue:** The KCH validator flagged `arcticdb.Arctic(...)` and `store.get_library(...)` as PHANTOM_FUNCTION because these names were absent from the initial arcticdb stub
- **Fix:** Added `Arctic` and `get_library` to `stubs/arcticdb_stubs.py`; updated test fixture to match
- **Files modified:** `stubs/arcticdb_stubs.py`, `tests/quality/test_kch_validator.py`
- **Commit:** 3f43549, 700f080

**2. [Rule 1 - Bug] Unused type: ignore comment in validator.py**
- **Found during:** mypy --strict verification
- **Issue:** `spec.loader.exec_module(module)  # type: ignore[union-attr]` was flagged as unused-ignore by mypy strict
- **Fix:** Removed the type: ignore comment (mypy no longer reports union-attr here)
- **Files modified:** `src/quality/ast_validator/validator.py`
- **Commit:** 700f080

**3. [Rule 2 - Cleanup] Lint and stub improvements**
- **Found during:** Post-implementation cleanup
- **Issue:** scripts/ast_validator.py had an E402 linting issue; nats_stubs.py was missing publish params
- **Fix:** Added `# noqa: E402` to sys.path insert; added `timeout` and `stream` kwargs to nats publish stub
- **Files modified:** `scripts/ast_validator.py`, `stubs/nats_stubs.py`, `stubs/mt5_stubs.py`
- **Commit:** 86304db

## Known Stubs

None — all stub files contain real API data. `upsert` is intentionally absent from `stubs/arcticdb_stubs.py` as the canonical phantom-function test case (per plan specification).

## Self-Check

Checking created files exist:
- src/quality/ast_validator/extractor.py — FOUND
- src/quality/ast_validator/validator.py — FOUND
- src/quality/ast_validator/stub_generator.py — FOUND
- scripts/ast_validator.py — FOUND
- stubs/mt5_stubs.py — FOUND (contains copy_ticks_range)
- stubs/arcticdb_stubs.py — FOUND (write present, upsert absent)

## Self-Check: PASSED
