# Requirements: Helix Algorithmic Trading Suite

**Defined:** 2026-03-20
**Core Value:** A broker-agnostic trading system where every signal passes through rigorous quality gates before reaching live markets

---

## v1 Requirements (Stage A — Forex Production)

### Quality Infrastructure

- [x] **QUAL-01**: CI/CD pipeline runs AST/KCH hallucination detection on every commit
- [x] **QUAL-02**: Point-in-Time compliance validator catches look-ahead bias in alpha code
- [x] **QUAL-03**: mypy strict + ruff linting pass on all source code
- [x] **QUAL-04**: Test coverage ≥ 80% enforced as a merge gate
- [x] **QUAL-05**: Pre-commit hooks run all quality gates locally before push
- [x] **QUAL-06**: GitHub Actions CI runs static analysis → unit tests → e2e in sequence

### Execution Abstraction

- [x] **EXEC-01**: Abstract interfaces (MarketDataProvider, OrderExecutor, PositionManager) define broker-agnostic contract
- [ ] **EXEC-02**: MT5Adapter implements all three interfaces with async wrappers
- [ ] **EXEC-03**: SimAdapter provides identical interface for backtesting without Windows dependency
- [ ] **EXEC-04**: SpreadModel tracks empirical spread distribution and suppresses signals where spread > 50% of expected profit
- [ ] **EXEC-05**: Swap rate extraction computes annualized carry for all configured symbols
- [ ] **EXEC-06**: Lot sizing converts Kelly fraction to MT5 lots respecting volume_min/max/step
- [ ] **EXEC-07**: ZeroMQ bridge streams ticks/bars from Windows MT5 to Linux engines over WireGuard

### Data Engineering

- [ ] **DATA-01**: ArcticDB initialized with 6 libraries (forex_ticks, forex_bars, swap_rates, mbo_ticks stub, signals, portfolio)
- [ ] **DATA-02**: Forex tick writer batches 10K ticks, flushes every 1s, never blocks execution adapter
- [ ] **DATA-03**: Bar aggregator produces 6 timeframes (1m/5m/15m/1h/4h/1d) with session tagging
- [ ] **DATA-04**: PiT manager prevents all 5 look-ahead bias vectors; pit_read returns only data ≤ as_of_timestamp
- [ ] **DATA-05**: ArcticDB snapshots enable reproducible backtests at any historical date
- [ ] **DATA-06**: VectorBT Pro + Numba single-pass backtester with spread cost parameter
- [ ] **DATA-07**: Numba warmup service compiles all JIT functions at startup; cached run < 5s

### Alpha Engines

- [ ] **ALPH-01**: HMM-GARCH regime detector identifies 3 states (Trending/Mean-Reverting/Crisis) with GARCH stationarity constraint
- [ ] **ALPH-02**: Regime states sorted by ascending unconditional variance (deterministic across refits)
- [ ] **ALPH-03**: Weekly Baum-Welch recalibration + 1000-bar GARCH parameter updates
- [ ] **ALPH-04**: Johansen cointegration engine tests 3 Forex pairs with dynamic hedge ratio (504-bar rolling)
- [ ] **ALPH-05**: Z-score entry/exit signals fire at ±2.0 with hard stop at ±4.0; half-life monitoring
- [ ] **ALPH-06**: Swap-based carry provider ranks symbols cross-sectionally, suppresses when spread > carry
- [ ] **ALPH-07**: 27-feature Numba pipeline (5 tiers: momentum, volatility, session, cross-asset, tick volume) with PiT compliance
- [ ] **ALPH-08**: Walk-forward XGBoost+RF ensemble (756-bar train, 21-bar step, 30+ OOS windows) with SHAP analysis
- [ ] **ALPH-09**: Regime gates strategy activation: Trending → ML+Carry, Mean-Reverting → Cointegration, Crisis → reduce only

### Risk Management

- [ ] **RISK-01**: CVaR computed by historical simulation, parametric (GARCH-informed), and Cornish-Fisher methods
- [ ] **RISK-02**: Spread-adjusted CVaR uses p95 spread for worst-10% return periods
- [ ] **RISK-03**: CVXPY portfolio optimizer minimizes CVaR with per-strategy weight cap (25%) and budget constraint (5%)
- [ ] **RISK-04**: Kelly criterion applies regime multipliers (Trending 0.5×, Mean-Reverting 0.4×, Crisis 0.1×), capped at 15%
- [ ] **RISK-05**: ECT sandboxes underperforming strategies to virtual executor; restores after 10 consecutive recovery bars at 50% Kelly scaling to 100% over 20 bars
- [ ] **RISK-06**: Circuit breaker L1 fires at 2% daily drawdown (reduce to 50% Kelly)
- [ ] **RISK-07**: Circuit breaker L2 fires at 5% daily drawdown (flatten all positions, pause 1 hour)
- [ ] **RISK-08**: Circuit breaker L3 fires at 10% daily drawdown (flatten all, disable strategies, require manual restart; idempotent)

### IPC & Dashboard

- [ ] **IPC-01**: NATS JetStream single-node with TELEMETRY stream (7 subjects, 7-day retention)
- [ ] **IPC-02**: Telemetry publisher emits PnL (100ms), positions (1s), risk metrics (1s), regime state (5s), orders (on-event)
- [ ] **IPC-03**: WebSocket bridge relays NATS messages to browser clients with auto-reconnect
- [ ] **IPC-04**: React host shell loads 6 remote modules via Module Federation with error boundaries
- [ ] **IPC-05**: Dashboard displays regime state, cointegration z-scores, carry rankings, ML predictions, CVaR, drawdown, order blotter
- [ ] **IPC-06**: useNatsSubscription hook buffers messages at 100ms intervals to prevent re-render thrash

### Integration & Production

- [ ] **PROD-01**: End-to-end pipeline test: SimAdapter → ArcticDB → regime → signals → risk → execution → NATS → dashboard
- [ ] **PROD-02**: Circuit breaker L3 integration test halts all orders at 10% simulated drawdown
- [ ] **PROD-03**: Shadow trading deployment runs 2+ weeks on live MT5 data with SimAdapter execution
- [ ] **PROD-04**: Production deployment switches to MT5Adapter with graduated Kelly (25% → 50% → 100%)
- [ ] **PROD-05**: Daily reconciliation validates ArcticDB positions match MT5 broker report
- [ ] **PROD-06**: Alerting delivers notifications within 10s for L2/L3 circuit breakers and bridge disconnects

### Stage B Preparation

- [ ] **STAGEB-01**: CMEAdapter implements identical abstract interfaces as MT5Adapter and SimAdapter
- [ ] **STAGEB-02**: FuturesCarryProvider replaces stub with term structure carry formula
- [ ] **STAGEB-03**: MBO feature pipeline: OFI, VPIN, depth imbalance, microprice, Kyle's lambda, iceberg detection (all Numba JIT)
- [ ] **STAGEB-04**: NY4/LD4 infrastructure: Ansible playbooks, WireGuard 3-site mesh, NATS hub+leaf, Terraform
- [ ] **STAGEB-05**: CME iLink 3.0 sandbox certification (Negotiate → Establish → Order → Fill cycle)
- [ ] **STAGEB-06**: Migration runbook documents Stage A → Stage B switch with tested rollback procedure

---

## v2 Requirements (Post-Stage A validation)

### Stage B Live Trading
- Live CME futures execution at NY4/LD4 co-location
- PREEMPT_RT kernel + OpenOnload kernel bypass networking
- MBO feature integration into ML ensemble (supplements 27 Forex features)
- CME FIX Drop Copy for position reconciliation

### Advanced Features
- Multi-broker support (cTrader adapter alongside MT5)
- Automated hyperparameter tuning for walk-forward ensemble
- Automated pair discovery (test all EURUSD/XXXYYY combinations)
- Telegram/SMS/email alerting system

---

## Out of Scope

| Feature | Reason |
|---------|--------|
| OFI/VPIN/order book features in Stage A | No genuine order book data from retail brokers |
| Mobile app | Web dashboard sufficient for monitoring |
| Social/sharing features | Not relevant to trading system |
| Automated news/sentiment analysis | Out of scope for quantitative strategy |
| High-frequency tick-level ML in Stage A | Tick volume is proxy only; signals operate on bars |

---

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| QUAL-01 | Phase 1 | Complete |
| QUAL-02 | Phase 1 | Complete |
| QUAL-03 | Phase 1 | Complete |
| QUAL-04 | Phase 1 | Complete |
| QUAL-05 | Phase 1 | Complete |
| QUAL-06 | Phase 1 | Complete |
| EXEC-01 | Phase 1 | Complete |
| EXEC-02 | Phase 1 | Pending |
| EXEC-03 | Phase 1 | Pending |
| EXEC-04 | Phase 1 | Pending |
| EXEC-05 | Phase 1 | Pending |
| EXEC-06 | Phase 1 | Pending |
| EXEC-07 | Phase 1 | Pending |
| DATA-01 | Phase 2 | Pending |
| DATA-02 | Phase 2 | Pending |
| DATA-03 | Phase 2 | Pending |
| DATA-04 | Phase 2 | Pending |
| DATA-05 | Phase 2 | Pending |
| DATA-06 | Phase 2 | Pending |
| DATA-07 | Phase 2 | Pending |
| ALPH-01 | Phase 3 | Pending |
| ALPH-02 | Phase 3 | Pending |
| ALPH-03 | Phase 3 | Pending |
| ALPH-04 | Phase 3 | Pending |
| ALPH-05 | Phase 3 | Pending |
| ALPH-06 | Phase 3 | Pending |
| ALPH-07 | Phase 3 | Pending |
| ALPH-08 | Phase 3 | Pending |
| ALPH-09 | Phase 3 | Pending |
| RISK-01 | Phase 4 | Pending |
| RISK-02 | Phase 4 | Pending |
| RISK-03 | Phase 4 | Pending |
| RISK-04 | Phase 4 | Pending |
| RISK-05 | Phase 4 | Pending |
| RISK-06 | Phase 4 | Pending |
| RISK-07 | Phase 4 | Pending |
| RISK-08 | Phase 4 | Pending |
| IPC-01 | Phase 4 | Pending |
| IPC-02 | Phase 4 | Pending |
| IPC-03 | Phase 4 | Pending |
| IPC-04 | Phase 4 | Pending |
| IPC-05 | Phase 4 | Pending |
| IPC-06 | Phase 4 | Pending |
| PROD-01 | Phase 5 | Pending |
| PROD-02 | Phase 5 | Pending |
| PROD-03 | Phase 5 | Pending |
| PROD-04 | Phase 5 | Pending |
| PROD-05 | Phase 5 | Pending |
| PROD-06 | Phase 5 | Pending |
| STAGEB-01 | Phase 5 | Pending |
| STAGEB-02 | Phase 5 | Pending |
| STAGEB-03 | Phase 5 | Pending |
| STAGEB-04 | Phase 5 | Pending |
| STAGEB-05 | Phase 5 | Pending |
| STAGEB-06 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 47 total
- Mapped to phases: 47
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-20*
*Last updated: 2026-03-20 after roadmap creation*
