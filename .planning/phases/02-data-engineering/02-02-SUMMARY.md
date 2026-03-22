---
phase: 02-data-engineering
plan: 02
subsystem: database
tags: [arcticdb, lmdb, python, pandas, numpy, schema, forex, mbo]

# Dependency graph
requires:
  - phase: 02-01
    provides: ArcticDB installed, numba/psutil deps, Makefile validate target
  - phase: 01-foundation
    provides: Tick/Bar dataclasses from src/execution/abstract.py, arcticdb stubs

provides:
  - ArcticDB store singleton (get_store, initialize_store, get_library, reset_store)
  - All 6 libraries initialized on first call (forex_ticks, forex_bars, swap_rates, mbo_ticks, signals, portfolio)
  - Schema constants for Forex (FOREX_TICK_COLUMNS, FOREX_BAR_COLUMNS, SWAP_RATE_COLUMNS) and MBO (MBO_TICK_COLUMNS)
  - Quality flag constants (QUALITY_CLEAN, QUALITY_ROLLOVER_SPIKE, QUALITY_WEEKEND_GAP, QUALITY_DUPLICATE)
  - Admin CLI with list-libraries, list-symbols, schema, compact commands
  - 7 passing tests with tmp_path LMDB isolation

affects:
  - 02-03 (Forex writer needs get_library)
  - 02-04 (PiT manager needs get_library and LIBRARY_NAMES)
  - 02-05 (VectorBT backtesting needs ArcticDB round-trip verified)
  - 02-06 (Ingestion pipeline uses initialize_store)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Module-level singleton with reset_store() for test isolation — avoids lru_cache which can't be cleared per-test
    - LMDB backend at ./arctic_data — same path in dev/staging/production per D-01/D-02
    - Schema constants as plain dicts (column -> dtype string) — documentation only, ArcticDB infers from first write
    - Quality int8 flags for tick data annotation

key-files:
  created:
    - src/data/schemas.py
    - src/data/arctic_store.py
    - src/data/admin_cli.py
    - tests/data/__init__.py
    - tests/data/test_arctic_store.py
  modified:
    - src/data/__init__.py

key-decisions:
  - "Module-level singleton pattern (not lru_cache) for ArcticDB store — allows reset_store() in tests to inject tmp paths"
  - "LMDB backend at ./arctic_data, no env-var switching in Phase 2 — same path dev/staging/production per D-01/D-02"
  - "Schema constants are documentation only (dict[str, str]) — ArcticDB infers schema from first DataFrame written"
  - "MBO tick schema stubbed but fully defined — Stage B ready without blocking Stage A"

patterns-established:
  - "Pattern 1: Store singleton with reset_store() for test isolation — use tmp_path fixture + reset_store() in autouse fixture"
  - "Pattern 2: URI-parametric functions — all store functions accept uri kwarg defaulting to lmdb://./arctic_data"
  - "Pattern 3: Idempotent initialization — has_library check before create_library prevents errors on re-init"

requirements-completed: [DATA-01]

# Metrics
duration: 3min
completed: 2026-03-22
---

# Phase 02 Plan 02: ArcticDB Store Initialization Summary

**ArcticDB LMDB store with 6 libraries, Forex/MBO schema constants, quality flags, and admin CLI — all backed by 7 round-trip tests**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-22T07:32:13Z
- **Completed:** 2026-03-22T07:35:17Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- ArcticDB store singleton initializes all 6 libraries (forex_ticks, forex_bars, swap_rates, mbo_ticks, signals, portfolio) idempotently via `initialize_store()`
- Schema constants defined for Forex ticks/bars, swap rates, MBO ticks, and quality flag int8 constants — exported from `src/data/__init__.py`
- Admin CLI (argparse) provides list-libraries, list-symbols, schema, compact commands using only valid KCH-approved ArcticDB API calls
- 7 passing tests with tmp_path LMDB isolation and autouse reset_store() fixture

## Task Commits

Each task was committed atomically:

1. **Task 1: Create schema definitions and ArcticDB store initialization** - `77039d8` (feat)
2. **Task 2: Create admin CLI tool** - `fc31431` (feat)

## Files Created/Modified

- `src/data/schemas.py` - LIBRARY_NAMES (6), FOREX_TICK_COLUMNS, FOREX_BAR_COLUMNS, SWAP_RATE_COLUMNS, MBO_TICK_COLUMNS, QUALITY_* constants
- `src/data/arctic_store.py` - get_store singleton, reset_store, initialize_store (idempotent), get_library
- `src/data/admin_cli.py` - argparse CLI: list-libraries, list-symbols, schema, compact
- `src/data/__init__.py` - Updated to export all public symbols from schemas and arctic_store
- `tests/data/__init__.py` - Package init (empty)
- `tests/data/test_arctic_store.py` - 7 tests: store init, idempotency, Forex round-trip, MBO round-trip, get_library, LIBRARY_NAMES count, admin CLI

## Decisions Made

- Module-level singleton (not `lru_cache`) for `_STORE` — `reset_store()` allows test injection of tmp paths. `lru_cache` cannot be cleared per-test without monkey-patching.
- LMDB backend fixed at `./arctic_data`, no env-var switching per D-01/D-02 — simplicity over configurability in Phase 2.
- Schema constants are plain `dict[str, str]` — documentation intent, not runtime enforcement. ArcticDB infers schema from first DataFrame written.
- MBO tick schema fully defined as Stage B stub — all columns present, library created, empty on Stage A.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- A pre-commit hook temporarily replaced the test file with `pytest.skip` stubs mid-execution. Detected and restored from the Write tool. No functional impact; final commit state is correct.

## Known Stubs

- `mbo_ticks` library is created and schema-defined but will remain empty through Stage A. This is intentional per plan spec ("Stage B stub"). The `test_mbo_tick_schema_roundtrip` test verifies the library accepts the schema, satisfying the must_have truth "MBO tick schema is created but empty".

## Next Phase Readiness

- `get_library("forex_ticks")`, `get_library("forex_bars")`, etc. are ready for 02-03 Forex writer
- `initialize_store()` can be called from any Phase 2 plan — idempotent and safe to call multiple times
- Admin CLI ready for manual inspection of store state during development

---
*Phase: 02-data-engineering*
*Completed: 2026-03-22*
