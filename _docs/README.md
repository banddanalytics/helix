# Algorithmic Trading Suite — Skills Collection v2

## Two-Stage Architecture: Forex → CME Futures

```
STAGE A (Months 1-12): Retail Forex via MT5/cTrader
  Build capital, validate strategies, develop infrastructure

STAGE B (Month 12+): CME Currency Futures via iLink 3.0
  Co-located execution, genuine order book data, lower costs
```

## Skill Map

```
┌──────────────────────────────────────────────────────────────────────┐
│                         EXECUTION LAYER                              │
│                                                                      │
│  [1] forex-broker-adapter (Stage A)    [8] hft-network-topology      │
│      MT5/cTrader, abstraction layer        (Stage B: NY4/LD4 co-lo)  │
│      spread model, swap rates, lots        FIX iLink 3.0, PREEMPT_RT│
│                                                                      │
├──────────────────────────────────────────────────────────────────────┤
│                         DATA LAYER                                   │
│                                                                      │
│  [2] arcticdb-vectorbt-engine (Both Stages)                          │
│      Forex schema (A) + MBO schema (B), PiT compliance,             │
│      Numba JIT, VectorBT Pro backtesting                             │
│                                                                      │
├──────────────────────────────────────────────────────────────────────┤
│                         ALPHA GENERATION LAYER                       │
│                                                                      │
│  [3] hmm-garch-regime-detector    [4] alpha-cointegration-carry      │
│      (Both Stages)                    (Both: swap carry A,           │
│      HMM/GARCH on returns             term structure carry B)        │
│                                                                      │
│  [5] ml-price-momentum            [6] ml-momentum-orderflow          │
│      (Both: price/vol features)       (Stage B ONLY: OFI, VPIN,     │
│      Active from day 1                iceberg — supplements [5])     │
│                                                                      │
├──────────────────────────────────────────────────────────────────────┤
│                         RISK LAYER                                   │
│                                                                      │
│  [7] cvar-risk-optimizer (Both Stages)                               │
│      CVaR + spread cost (A), CVaR (B), Kelly, ECT, circuit breakers  │
│                                                                      │
├──────────────────────────────────────────────────────────────────────┤
│                         IPC / UI LAYER                               │
│                                                                      │
│  [9] zeromq-nats-react-ui (Both Stages)                              │
│      ZMQ bridge (A), ZMQ IPC (B), NATS telemetry, React dashboard    │
│                                                                      │
├──────────────────────────────────────────────────────────────────────┤
│                         QUALITY LAYER                                │
│                                                                      │
│  [10] ast-tdd-validation (Both Stages)                               │
│       AST/KCH validation, Testing Trophy, 80% coverage, CI/CD       │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

## Stage A Active Skills (Forex Phase)

| # | Skill                      | Stage A Role                                       |
|---|----------------------------|----------------------------------------------------|
| 1 | forex-broker-adapter       | MT5 connectivity, execution abstraction, swap rates |
| 2 | arcticdb-vectorbt-engine   | Forex tick/bar storage, PiT, backtesting            |
| 3 | hmm-garch-regime-detector  | Regime detection on Forex returns                   |
| 4 | alpha-cointegration-carry  | Pairs trading + swap-based carry                    |
| 5 | ml-price-momentum          | ML from price/volume (no order book needed)         |
| 7 | cvar-risk-optimizer        | CVaR with spread cost adjustment                    |
| 9 | zeromq-nats-react-ui       | ZMQ bridge + single NATS + React dashboard          |
| 10| ast-tdd-validation         | Code quality, testing, CI/CD                        |

## Skills Added at Stage B (CME Futures Transition)

| # | Skill                      | Stage B Addition                                    |
|---|----------------------------|----------------------------------------------------|
| 6 | ml-momentum-orderflow      | OFI, VPIN, iceberg detection from CME MBO data      |
| 8 | hft-network-topology       | NY4/LD4 co-location, PREEMPT_RT, OpenOnload         |

## Build Order

```
Phase 1 (Foundation — start here):
  [10] ast-tdd-validation      ← Set up CI/CD first
  [1]  forex-broker-adapter    ← Execution abstraction + MT5

Phase 2 (Data):
  [2]  arcticdb-vectorbt-engine ← Storage + backtesting

Phase 3 (Alpha — can be parallel):
  [3]  hmm-garch-regime-detector
  [4]  alpha-cointegration-carry
  [5]  ml-price-momentum

Phase 4 (Risk + IPC):
  [7]  cvar-risk-optimizer
  [9]  zeromq-nats-react-ui

Phase 5 (Stage B Migration — when ready):
  [8]  hft-network-topology
  [6]  ml-momentum-orderflow
```

## Migration Triggers (Stage A → Stage B)

Move to CME futures when ALL of these are met:
- Account equity > $50,000 (CME margin requirements)
- Strategies profitable net of spreads for 6+ consecutive months
- Spread costs eroding >30% of gross alpha
- CME iLink 3.0 sandbox certification completed
