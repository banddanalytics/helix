# Helix — Algorithmic Trading Suite

## What This Is

Helix is a two-stage algorithmic trading system for currency markets. Stage A trades retail Forex via MT5/cTrader with 4 alpha engines, a CVaR risk engine, and a real-time React dashboard. Stage B migrates to CME currency futures via co-located iLink 3.0 execution once sufficient capital and strategy validation are achieved.

## Core Value

A fully automated, broker-agnostic trading system where every signal passes through rigorous quality gates (AST validation, PiT compliance, 80%+ test coverage) before reaching live markets — eliminating hallucinated API calls and look-ahead bias from the execution path.

## Requirements

### Validated

(None yet — ship to validate)

### Active

**Infrastructure & Quality**
- [ ] CI/CD pipeline with AST/KCH hallucination detection, PiT compliance checker, mypy strict, ruff, 80%+ coverage
- [ ] Broker-agnostic execution abstraction (MarketDataProvider, OrderExecutor, PositionManager ABCs)
- [ ] MT5 concrete adapter with async wrappers, spread model, lot sizing, swap rate extraction
- [ ] SimAdapter for backtesting and CI without Windows MT5 dependency
- [ ] ZeroMQ bridge: Windows MT5 ↔ Linux alpha engines over WireGuard VPN

**Data Engineering**
- [ ] ArcticDB dual-schema storage (Forex tick/bar + MBO stub for Stage B)
- [ ] Point-in-Time data manager preventing all 5 look-ahead bias vectors
- [ ] VectorBT Pro + Numba JIT backtesting with spread cost parameter
- [ ] Forex tick ingestion, bar aggregation (6 timeframes), session tagging, swap snapshots

**Alpha Engines**
- [ ] HMM-GARCH regime detector (3 states: Trending, Mean-Reverting, Crisis)
- [ ] Johansen cointegration engine for 3 Forex pairs (AUDUSD/NZDUSD, EURUSD/GBPUSD, USDJPY/USDCHF)
- [ ] Swap-based carry signal provider with spread-cost filter
- [ ] ML price momentum: 27-feature Numba pipeline + XGBoost/RF walk-forward ensemble

**Risk Management**
- [ ] CVaR computation (historical, parametric, Cornish-Fisher, spread-adjusted)
- [ ] CVXPY portfolio optimizer with CVaR budget constraints
- [ ] Kelly criterion with regime adjustment, ECT sandbox/restore, circuit breakers (L1/L2/L3)

**IPC & Dashboard**
- [ ] NATS JetStream single-node telemetry (7 subjects, WebSocket bridge)
- [ ] React Module Federation dashboard (host shell + 6 remotes) with live NATS feed

**Integration & Production**
- [ ] End-to-end integration tests across full pipeline
- [ ] Shadow trading deployment (live data, simulated orders, 2-week validation)
- [ ] Production deployment with graduated Kelly scaling (25% → 50% → 100%)
- [ ] Stage B preparation: CMEAdapter, FuturesCarryProvider, MBO features, NY4/LD4 infra

### Out of Scope

- MBO/order book features in Stage A — no genuine order book data from retail brokers
- OFI, VPIN, depth imbalance — Stage B only features
- Mobile app — web dashboard only
- Real-time chat or social features
- Stage B live trading — only infrastructure preparation in Phase 5

## Context

- **Architecture:** Windows VPS (MT5 terminal + ZMQ publisher) → WireGuard → Linux server (alpha engines, ArcticDB, NATS) → WireGuard → Nairobi (React dashboard)
- **Language:** Python 3.12 for all backend components; TypeScript/React for dashboard
- **Key libraries:** MetaTrader5, arcticdb, vectorbtpro, hmmlearn, arch, statsmodels, xgboost, cvxpy, pyzmq, nats-py, numba
- **Stage A target pairs:** EURUSD, GBPUSD, AUDUSD, NZDUSD, USDJPY, AUDJPY, EURGBP
- **Stage A cointegration pairs:** AUDUSD/NZDUSD, EURUSD/GBPUSD, USDJPY/USDCHF

## Constraints

- **Platform:** MT5 Python API is Windows-only — all alpha engine code runs on Linux via ZMQ bridge
- **Data:** No genuine order book data in Stage A — tick volume is a proxy only
- **Quality:** All code must pass AST/KCH validation (no phantom APIs), PiT compliance, mypy strict, 80%+ coverage
- **Capital:** Stage B requires $50K+ equity and 6+ months consistent positive expectancy
- **Stage B trigger:** Equity > $50K AND strategy profitable 6+ months AND spreads > 30% gross alpha AND iLink 3.0 certification complete

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Broker-agnostic abstraction layer | Every downstream component codes against ABCs, never MT5 directly — enables SimAdapter for CI and CMEAdapter for Stage B | — Pending |
| ZeroMQ bridge (not REST/gRPC) | Low latency, MessagePack serialization, PUB/SUB matches market data topology | — Pending |
| ArcticDB over InfluxDB/TimescaleDB | Native Python, columnar storage, version snapshots for PiT compliance | — Pending |
| Numba JIT for feature computation | 27 features × 1M bars < 5 seconds — Python loops would be 100× slower | — Pending |
| Module Federation dashboard | 6 remote modules load independently — one crashing doesn't break others | — Pending |
| NATS JetStream over Kafka | Single-node simplicity for Stage A, hub+leaf scales to Stage B without code changes | — Pending |

---
*Last updated: 2026-03-20 after initialization*

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state
