---
phase: 01-foundation
plan: 04
subsystem: execution
tags: [abstractions, ABCs, dataclasses, broker-agnostic, interfaces]
dependency_graph:
  requires: [01-01]
  provides: [src/execution/abstract.py, src/execution/__init__.py]
  affects: [01-05, 01-06, 01-07, all downstream phases]
tech_stack:
  added: [abc.ABC, abc.abstractmethod, numpy.datetime64, dataclasses.dataclass, enum.Enum]
  patterns: [ABC contract tests, TDD red-green, frozen dataclasses, async abstract methods]
key_files:
  created:
    - src/execution/abstract.py
    - tests/execution/test_abstract.py
  modified:
    - src/execution/__init__.py
key_decisions:
  - "Three ABCs (MarketDataProvider, OrderExecutor, PositionManager) define the complete broker-agnostic execution contract — all downstream code types against these, never MT5 directly (D-18, D-21)"
  - "Position dataclass is intentionally mutable (not frozen) because current_price and unrealized_pnl are updated continuously during live trading"
  - "All ABC methods are async — synchronous MT5 calls will be wrapped in asyncio.to_thread() in MT5Adapter (D-19)"
metrics:
  duration_minutes: ~30
  completed: "2026-03-21"
  tasks_completed: 2
  files_created: 2
  files_modified: 1
---

# Phase 1 Plan 4: Abstract Execution Interfaces Summary

Broker-agnostic execution ABCs (MarketDataProvider, OrderExecutor, PositionManager) and dataclasses (Tick, Bar, OrderRequest, OrderResult, Position) with 11 async abstract methods and 100% contract test coverage.

## Objective

Define the broker-agnostic execution interfaces (three ABCs) and all shared dataclasses that every downstream component depends on. EXEC-01 requires that all trading components code against abstract interfaces, never MT5 directly.

## Tasks Completed

### Task 1: Define enums and dataclasses (TDD)
**Commit:** 89646d9

**Files Created/Modified:**
- `src/execution/abstract.py` — Side enum (BUY=1, SELL=-1), OrderType enum (MARKET/LIMIT/STOP), and five frozen dataclasses: Tick, Bar, OrderRequest, OrderResult, Position
- `tests/execution/test_abstract.py` — Dataclass tests written first (TDD red), then implementation added (green)

**Key implementation details:**
- All dataclasses use `@dataclass(frozen=True, slots=True)` except Position (mutable for live mark-to-market updates)
- Tick and Bar use `np.datetime64` for nanosecond-resolution timestamps
- OrderRequest defaults: `order_type=OrderType.MARKET`, `price=None`, `sl=None`, `tp=None`, `comment=""`
- Zero broker-specific references (no MT5, CME, Forex, futures, or MetaTrader anywhere in file)

### Task 2: Define three abstract base classes with contract tests (TDD)
**Commit:** 89646d9

**Files Created/Modified:**
- `src/execution/abstract.py` — Three ABCs appended after dataclasses: MarketDataProvider (4 methods), OrderExecutor (3 methods), PositionManager (4 methods) = 11 total `@abstractmethod` decorators
- `src/execution/__init__.py` — Updated to export all 10 public names
- `tests/execution/test_abstract.py` — Contract tests written first (TDD red): incomplete implementations raise TypeError, complete implementations instantiate successfully, signatures verified via inspect module

**ABCs defined:**

| ABC | Async Methods |
|-----|--------------|
| MarketDataProvider | get_ticks(symbol, start, end), get_bars(symbol, timeframe, count), subscribe_ticks(symbol, callback), get_symbols() |
| OrderExecutor | submit_order(order), cancel_order(order_id), get_open_orders() |
| PositionManager | get_positions(), close_position(symbol), get_account_equity(), get_margin_level() |

## Verification Results

- `.venv/bin/python -m pytest tests/execution/test_abstract.py -x -v`: **38 passed**
- `src/execution/abstract.py` coverage: **100%** (64 statements, 0 missed)
- `.venv/bin/mypy src/execution/abstract.py --strict`: **Success: no issues found in 1 source file**
- Broker reference scan (`grep -qi "mt5|cme|forex|futures|metatrader"`): **0 matches**
- `@abstractmethod` count: **11** (4 + 3 + 4 matches plan spec)

## Deviations from Plan

None — plan executed exactly as written.

The TDD cycle was completed: contract tests were written first (red), then implementation added to make them pass (green). Both tasks were committed together in a single atomic commit `89646d9` since they represent one logical unit (the complete abstract.py file with its tests).

## Known Stubs

None — all exported names are fully implemented. The ABCs use `...` (Ellipsis) as method bodies, which is the correct pattern for abstract methods.

## Self-Check: PASSED

- `src/execution/abstract.py`: FOUND
- `tests/execution/test_abstract.py`: FOUND
- `src/execution/__init__.py`: FOUND (exports all 10 names)
- Commit `89646d9`: FOUND in git log
- 38 tests passing: VERIFIED
- mypy strict: VERIFIED
- No broker references: VERIFIED
- 11 abstractmethod decorators: VERIFIED
