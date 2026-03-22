---
phase: 01-foundation
plan: "05"
subsystem: execution-adapters
tags: [mt5-adapter, sim-adapter, async, tdd, broker-agnostic]
dependency_graph:
  requires: ["01-04"]
  provides: ["MT5Adapter", "SimAdapter"]
  affects: ["alpha-engines", "risk-engine", "phase-2-live-trading"]
tech_stack:
  added: []
  patterns:
    - "asyncio.to_thread for all synchronous MT5 API calls"
    - "unittest.mock.MagicMock for Windows-only MT5 module in CI"
    - "random.Random(seed) for deterministic SimAdapter fills"
    - "TDD red/green with pytest"
key_files:
  created:
    - src/execution/mt5_adapter.py
    - src/execution/sim_adapter.py
    - tests/execution/test_mt5_adapter.py
    - tests/execution/test_sim_adapter.py
  modified:
    - tests/conftest.py
decisions:
  - "MT5 imported conditionally (try/except ImportError -> None) so Linux CI runs without MetaTrader5 installed"
  - "SimAdapter uses fixed seed (42) via random.Random for deterministic test fills"
  - "SpreadModel integration into SimAdapter deferred to Phase 2 — Phase 1 uses fixed spread_pips float"
  - "Margin rejection threshold: equity * 0.02 (2% margin requirement)"
metrics:
  duration_minutes: 20
  completed_date: "2026-03-22"
  tasks_completed: 2
  files_created: 4
  files_modified: 1
---

# Phase 01 Plan 05: Concrete Execution Adapters Summary

**One-liner:** MT5Adapter wraps all Windows MT5 calls in asyncio.to_thread; SimAdapter provides identical stateful interface for backtesting with deterministic fills and margin rejection.

## What Was Built

Two concrete implementations of the three ABCs (MarketDataProvider, OrderExecutor, PositionManager) from Plan 04:

1. **`src/execution/mt5_adapter.py`** — `MT5Adapter` implements all 11 abstract methods. MT5 is imported conditionally (`try/except ImportError`) so Linux CI runs clean. All synchronous MT5 calls wrapped in `asyncio.to_thread()`. Timeframe mapping covers 1m/5m/15m/30m/1h/4h/1d/1w. Order submission uses `TRADE_ACTION_DEAL`, `deviation=20`, `magic=100001`, `ORDER_FILLING_IOC`. Tick subscription uses 10ms polling loop via `asyncio.sleep(0.01)`.

2. **`src/execution/sim_adapter.py`** — `SimAdapter` implements all 11 abstract methods identically. Stateful position ledger (`_positions` dict), realized PnL tracking, margin tracking. Instant fills at mid ± half_spread. Rejection logic: insufficient margin (equity × 0.02) and invalid lot size (≤0). Fixed `random.Random(42)` seed for deterministic behavior. `set_price(symbol, mid)` method allows tests to inject prices.

## Commits

| Hash | Message |
|------|---------|
| c84dbc6 | test(01-05): add failing tests for MT5Adapter (TDD red) |
| 33f6226 | feat(01-05): implement MT5Adapter with asyncio.to_thread wrappers |
| febe7ad | test(01-05): add failing tests for SimAdapter (TDD red) |
| eeb368f | feat(01-05): implement SimAdapter with stateful execution and spread cost |

## Test Results

- 31 tests in test_sim_adapter.py — all pass
- MT5Adapter tests pass with fully mocked MT5 module (no Windows dependency)
- SimAdapter 92% branch coverage
- `mypy src/execution/ --strict` — clean

## Verification

```
31 sim_adapter tests pass, 92% coverage
All MT5Adapter tests pass with mocked MT5 module
Both adapters implement all 11 abstract methods
class MT5Adapter(MarketDataProvider, OrderExecutor, PositionManager) — confirmed
class SimAdapter(MarketDataProvider, OrderExecutor, PositionManager) — confirmed
asyncio.to_thread used ≥5 times in MT5Adapter — confirmed
```

## Deviations from Plan

None — plan executed as written.

## Self-Check: PASSED

- src/execution/mt5_adapter.py: FOUND
- src/execution/sim_adapter.py: FOUND
- tests/execution/test_mt5_adapter.py: FOUND
- tests/execution/test_sim_adapter.py: FOUND
- Commit c84dbc6: FOUND
- Commit 33f6226: FOUND
- Commit febe7ad: FOUND
- Commit eeb368f: FOUND
