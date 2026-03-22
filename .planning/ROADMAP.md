# Roadmap: Helix Algorithmic Trading Suite

## Overview

Helix is built in five phases: Foundation establishes quality gates and the broker-agnostic execution abstraction that every other component depends on. Data Engineering wires in ArcticDB storage and VectorBT backtesting with strict Point-in-Time compliance. Alpha Engines delivers the four trading strategies (regime detection, cointegration, carry, and ML momentum) gated by the regime state machine. Risk, IPC & Dashboard adds the CVaR/Kelly risk engine, NATS telemetry, and React monitoring dashboard. Integration & Production validates the full pipeline via shadow trading and deploys to live markets with graduated sizing, plus lays Stage B infrastructure groundwork.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Foundation** - CI/CD quality pipeline and broker-agnostic execution abstraction layer
- [x] **Phase 2: Data Engineering** - ArcticDB storage, PiT compliance, and VectorBT backtesting infrastructure (completed 2026-03-22)
- [x] **Phase 3: Alpha Engines** - Regime detection, cointegration, carry, and ML momentum strategy engines (completed 2026-03-22)
- [ ] **Phase 4: Risk, IPC & Dashboard** - CVaR/Kelly risk engine, NATS telemetry, and React monitoring dashboard
- [ ] **Phase 5: Integration & Production** - E2E validation, shadow trading, live deployment, and Stage B preparation

## Phase Details

### Phase 1: Foundation
**Goal**: Every commit passes automated quality gates and all trading components code against broker-agnostic abstractions, not MT5 directly
**Depends on**: Nothing (first phase)
**Requirements**: QUAL-01, QUAL-02, QUAL-03, QUAL-04, QUAL-05, QUAL-06, EXEC-01, EXEC-02, EXEC-03, EXEC-04, EXEC-05, EXEC-06, EXEC-07
**Success Criteria** (what must be TRUE):
  1. A commit containing a phantom API call or look-ahead bias pattern is automatically rejected by CI before merge
  2. All source code passes mypy strict and ruff with zero errors, and test coverage is enforced at 80% as a merge gate
  3. The SimAdapter and MT5Adapter are interchangeable behind the three abstract interfaces — calling code never references MT5 directly
  4. The ZeroMQ bridge streams live ticks from a Windows MT5 terminal to a Linux process over WireGuard without data loss
  5. SpreadModel suppresses a signal when the spread exceeds 50% of expected profit, and lot sizing correctly converts a Kelly fraction to valid MT5 volume increments
**Plans:** 3/7 plans executed

Plans:
- [x] 01-01-PLAN.md — Project scaffold: venv, pyproject.toml, directory tree, Makefile
- [x] 01-02-PLAN.md — AST/KCH hallucination detection pipeline and library stubs
- [x] 01-03-PLAN.md — PiT compliance validator, pre-commit hooks, GitHub Actions CI
- [x] 01-04-PLAN.md — Abstract execution interfaces (ABCs) and dataclasses
- [ ] 01-05-PLAN.md — MT5Adapter and SimAdapter concrete implementations
- [x] 01-06-PLAN.md — SpreadModel, SwapRates, and LotSizer utilities
- [ ] 01-07-PLAN.md — ZeroMQ bridge: MessagePack schemas, publisher, consumer

### Phase 2: Data Engineering
**Goal**: All market data is stored with verifiable Point-in-Time isolation, and backtests can be reproduced exactly at any historical snapshot
**Depends on**: Phase 1
**Requirements**: DATA-01, DATA-02, DATA-03, DATA-04, DATA-05, DATA-06, DATA-07
**Success Criteria** (what must be TRUE):
  1. ArcticDB is initialized with all 6 libraries and tick writes batch at 10K records, flushing every 1s without blocking the execution adapter
  2. Bar aggregation produces all 6 timeframes with correct session tags, and pit_read returns strictly no data beyond the requested as_of timestamp
  3. A VectorBT backtest run on a named ArcticDB snapshot returns identical results across repeated executions
  4. The Numba warmup service compiles all JIT functions at startup and subsequent cached runs complete in under 5 seconds
**Plans:** 6/6 plans complete

Plans:
- [x] 02-01-PLAN.md — Wave 0 setup: install packages, numba stub, Makefile extension, test scaffolds
- [x] 02-02-PLAN.md — ArcticDB store initialization with 6 libraries and schema definitions
- [x] 02-03-PLAN.md — Forex tick writer with batch flush and quality flagging
- [x] 02-04-PLAN.md — Bar aggregator with 6 timeframes, session tagging, and swap writer
- [x] 02-05-PLAN.md — PiT data manager and EOD snapshot scheduler
- [x] 02-06-PLAN.md — VectorBT Pro + Numba backtesting stack and BacktestRunner

### Phase 3: Alpha Engines
**Goal**: Four trading strategies produce regime-gated signals that fire on correct market conditions and are suppressed in others
**Depends on**: Phase 2
**Requirements**: ALPH-01, ALPH-02, ALPH-03, ALPH-04, ALPH-05, ALPH-06, ALPH-07, ALPH-08, ALPH-09
**Success Criteria** (what must be TRUE):
  1. The HMM-GARCH detector classifies bar sequences into Trending, Mean-Reverting, or Crisis states, with state ordering deterministic across refits and weekly Baum-Welch recalibration running without intervention
  2. The cointegration engine fires entry signals at z-score ±2.0, hard stops at ±4.0, and correctly tracks the 504-bar rolling hedge ratio for all three configured pairs
  3. The carry provider suppresses signals on symbols where spread cost exceeds the carry differential, and the ML ensemble completes a walk-forward run (756-bar train, 21-bar step) with SHAP output
  4. Regime gates activate the correct strategy set: ML and carry in Trending, cointegration in Mean-Reverting, and reduce-only in Crisis
**Plans:** 8/8 plans complete

Plans:
- [x] 03-01-PLAN.md — Wave 0 setup: install shap, signal types contract, test scaffolds
- [x] 03-02-PLAN.md — HMM-GARCH regime detector: emissions, Viterbi, online filter
- [x] 03-03-PLAN.md — Regime recalibration scheduler with two-gate validation
- [x] 03-04-PLAN.md — Johansen cointegration engine: trace test, hedge ratio, z-score signals
- [x] 03-05-PLAN.md — Carry signal provider: swap-based ranking with spread filter
- [x] 03-06-PLAN.md — ML 27-feature Numba pipeline and FeatureBuilder
- [x] 03-07-PLAN.md — Walk-forward XGBoost+RF ensemble with SHAP analysis
- [x] 03-08-PLAN.md — RegimeOrchestrator: strategy gating, hysteresis, signal persistence

### Phase 4: Risk, IPC & Dashboard
**Goal**: All open positions are subject to live CVaR and Kelly sizing constraints, telemetry flows end-to-end from engine to browser, and the dashboard displays real-time system state
**Depends on**: Phase 3
**Requirements**: RISK-01, RISK-02, RISK-03, RISK-04, RISK-05, RISK-06, RISK-07, RISK-08, IPC-01, IPC-02, IPC-03, IPC-04, IPC-05, IPC-06
**Success Criteria** (what must be TRUE):
  1. CVaR is computed by all three methods (historical, parametric, Cornish-Fisher) with spread adjustment, and the CVXPY optimizer enforces per-strategy weight caps and the 5% budget constraint
  2. Circuit breakers fire at correct thresholds: L1 at 2% daily drawdown reduces Kelly to 50%, L2 at 5% flattens positions and pauses for 1 hour, L3 at 10% disables all strategies and requires manual restart
  3. An underperforming strategy is sandboxed to the virtual executor by ECT and restores to live at 50% Kelly after 10 consecutive recovery bars, scaling to 100% over 20 bars
  4. NATS JetStream publishes all 7 subjects at the specified intervals (PnL at 100ms, positions at 1s, risk at 1s, regime at 5s, orders on-event), and the React dashboard receives and displays them with no re-render thrash
  5. The React host shell loads all 6 remote modules via Module Federation; an error in one remote does not crash the shell or other remotes
**Plans**: TBD

### Phase 5: Integration & Production
**Goal**: The complete pipeline is validated end-to-end in shadow mode, deployed to live markets with graduated sizing, and Stage B infrastructure is ready to activate when trigger conditions are met
**Depends on**: Phase 4
**Requirements**: PROD-01, PROD-02, PROD-03, PROD-04, PROD-05, PROD-06, STAGEB-01, STAGEB-02, STAGEB-03, STAGEB-04, STAGEB-05, STAGEB-06
**Success Criteria** (what must be TRUE):
  1. The E2E integration test exercises SimAdapter through ArcticDB, regime detection, signal generation, risk sizing, NATS emission, and dashboard display in a single automated run; the L3 circuit breaker integration test halts all simulated orders at 10% drawdown
  2. Shadow trading runs for 2+ weeks on live MT5 data with SimAdapter execution, producing a reconciled position log with zero discrepancies against the MT5 broker report
  3. Production deployment switches to MT5Adapter and completes all three Kelly graduation steps (25% → 50% → 100%) with alerting delivering L2/L3 notifications within 10 seconds
  4. CMEAdapter, FuturesCarryProvider, and MBO feature pipeline pass their own test suites; the CME iLink 3.0 sandbox Negotiate → Establish → Order → Fill cycle completes certification; the Stage A → Stage B migration runbook includes a tested rollback procedure
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 3/7 | In Progress|  |
| 2. Data Engineering | 6/6 | Complete   | 2026-03-22 |
| 3. Alpha Engines | 8/8 | Complete   | 2026-03-22 |
| 4. Risk, IPC & Dashboard | 0/TBD | Not started | - |
| 5. Integration & Production | 0/TBD | Not started | - |
