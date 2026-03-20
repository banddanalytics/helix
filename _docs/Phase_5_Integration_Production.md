# PHASE 5: Integration, Shadow Trading, Production Deployment, and Stage B Preparation

**Duration:** 3-4 weeks
**Dependencies:** All previous phases (1-4)
**Skills Used:** All 10 skills

Phase 5 connects all components into a running system, validates through shadow trading (paper trading with live market data), deploys to production with live capital, and prepares the Stage B migration to CME futures.

---

## Task 5.1 — End-to-End Integration Testing

**Tool:** Claude Code
**Skill Reference:** All skills, `ast-tdd-validation > Testing Trophy > E2E Tests`

Build comprehensive end-to-end tests that exercise the complete pipeline. These are the highest tier of the Testing Trophy — fewer in number but validating the entire signal-to-execution chain.

**Test 1: Full Pipeline (Happy Path)**

```
Market data (SimAdapter)
  → ArcticDB storage (forex_writer)
    → PiT read
      → Regime detection (HMM-GARCH)
        → Strategy signal generation:
            - Cointegration z-score
            - Carry ranking
            - ML momentum prediction
          → Risk check:
              - CVaR constraint
              - Kelly sizing
              - ECT filter
            → Order submission (SimAdapter)
              → Fill processing
                → PnL computation
                  → ArcticDB portfolio write
                    → NATS telemetry publish
                      → Dashboard WebSocket delivery
```

Run on 1 year of simulated Forex data. Verify each stage produces expected output.

**Test 2: Circuit Breaker Level 3 (Negative Path)**

Simulate a 10% daily drawdown and verify:
- L1 fires at 2% and reduces sizing to 50%
- L2 fires at 5% and flattens all positions
- L3 fires at 10% and prevents ALL new orders until manual reset
- After L3, `submit_order()` returns error without executing

**Test 3: ECT Sandbox/Restore Cycle**

Create a strategy with deliberately poor performance:
- Verify ECT detects equity < MA with negative PnL derivative
- Verify strategy is sandboxed (orders routed to virtual executor)
- Simulate recovery (equity > MA for 10 bars)
- Verify strategy is restored at 50% Kelly
- Verify scaling to 100% Kelly over 20 bars

**Test 4: PiT Integration**

Inject a deliberately contaminated signal (using current bar data without `.shift(1)`):
- Verify PiT validator catches the contamination
- Verify AST validator flags the source code
- Verify the contaminated signal produces suspiciously high contemporaneous IC

**Test 5: Full Coverage Report**

Run the complete test suite:

```bash
pytest tests/ --cov=src --cov-fail-under=80 --cov-branch -v
```

Verify all quality gates from Phase 1 pass on the full codebase:

```bash
make all  # lint + typecheck + validate + test
```

**Output Files:**

```
tests/e2e/test_full_pipeline.py
tests/e2e/test_circuit_breakers_live.py
tests/e2e/test_ect_sandbox.py
tests/e2e/test_pit_integration.py
tests/e2e/conftest.py             # E2E-specific fixtures (SimAdapter, test data)
```

**Validation:**

- [ ] Full pipeline test completes without errors on 1 year of simulated Forex data
- [ ] Circuit breaker L3 correctly halts all trading at 10% drawdown
- [ ] ECT correctly sandboxes and restores strategy over full cycle
- [ ] PiT integration test catches deliberate look-ahead bias injection
- [ ] `pytest --cov=src --cov-fail-under=80 --cov-branch` passes on entire codebase
- [ ] `make all` passes (lint + typecheck + validate + test)

---

## Task 5.2 — Shadow Trading Deployment (Paper Trading with Live Data)

**Tool:** Claude Code
**Skill Reference:** `forex-broker-adapter > MT5 Adapter`, `zeromq-nats-react-ui > Stage A topology`, `hft-network-topology > Stage A Topology`

Deploy the complete system in shadow trading mode: connected to a live MT5 broker feed receiving real market data, running all alpha engines and risk management in real-time, but routing all orders to the `SimAdapter` instead of the `MT5Adapter`.

**Infrastructure setup:**

```
[Windows VPS near broker]                   [Linux server]                    [Nairobi]
─────────────────────────                   ──────────────                    ─────────
MT5 Terminal (logged in)                    Alpha engines                     React dashboard
windows_publisher.py                        Risk engine
  ├─ ZMQ PUB :5556 (ticks) ──WireGuard──►  linux_consumer.py
  ├─ ZMQ PUB :5557 (bars)  ──WireGuard──►  ArcticDB writer
  ├─ ZMQ PULL :5558 ◄────────────────────  (orders to SimAdapter,
  └─ ZMQ PUSH :5559 ────────────────────►   NOT MT5Adapter)
                                            NATS single node
                                              └─ WS bridge ──WireGuard──►  Dashboard
```

**Windows VPS provisioning:**
- Provider: Vultr or Hetzner Windows Server (closest to broker's servers)
- Install MT5 terminal, login to broker account
- Install Python 3.12 + MetaTrader5 package
- Deploy `windows_publisher.py` as a Windows service
- Configure WireGuard tunnel to Linux server

**Linux server configuration:**
- Deploy `linux_consumer.py` → ArcticDB writer → alpha engines → risk engine
- Configure order routing to `SimAdapter` (NOT `MT5Adapter`) for shadow mode
- Deploy NATS server with JetStream
- Deploy WebSocket bridge
- Configure WireGuard tunnel to both Windows VPS and Nairobi

**Nairobi dashboard:**
- Deploy React dashboard (host shell + all 6 remotes)
- Connect to NATS WebSocket bridge via WireGuard
- Verify live data renders in all dashboard modules

**Shadow trading monitoring (minimum 2 weeks):**

| Metric | Expected Range | Action if Violated |
|--------|---------------|-------------------|
| Signal generation frequency | 1-10 signals/day per strategy | Debug if 0 or >50/day |
| Regime transitions | 2-8 per month | Investigate if >20/month (whipsaw) |
| Cointegration z-scores | Mostly within [-3, +3] | Check half-life if >50% outside range |
| Carry rankings | Stable within week, shift monthly | Normal — swap rates change slowly |
| ML prediction distribution | Centered around 0.5 | Investigate if strongly biased to one side |
| CVaR levels | Below 5% budget | Reduce exposure if consistently at limit |
| Simulated PnL | Positive over 2 weeks | Re-examine strategies if consistently negative |
| Bridge latency | <500ms tick-to-signal | Check WireGuard tunnel if >1000ms |
| Memory RSS | Stable over 48 hours | Fix leak if growing >10% per day |

**Deployment configuration:**

```yaml
# config/deployment/shadow_trading.yaml
mode: shadow  # Routes orders to SimAdapter
broker:
  type: mt5
  account: 12345678
  server: "ICMarkets-Demo"  # Use demo account first
  symbols: [EURUSD, GBPUSD, AUDUSD, NZDUSD, USDJPY, AUDJPY, EURGBP]
execution:
  adapter: sim  # SimAdapter for shadow trading
  slippage_bps: 1.0
  initial_equity: 100000
nats:
  url: "nats://localhost:4222"
dashboard:
  ws_url: "wss://server:9222"
  trading_stage: forex
```

**Output Files:**

```
config/deployment/shadow_trading.yaml
scripts/deploy_shadow.sh            # Automated deployment script
scripts/monitor_shadow.py           # Shadow trading health monitor
docs/shadow_trading_runbook.md      # Step-by-step deployment guide
```

**Validation:**

- [ ] Shadow system receives live ticks with < 500ms latency from broker
- [ ] All alpha engines produce signals in real-time without errors for 48+ hours
- [ ] Regime transitions occur at reasonable frequency (not every bar, not stuck in one state)
- [ ] Simulated PnL is realistic (not suspiciously good or catastrophically bad)
- [ ] Dashboard displays live data from all 6 modules via Nairobi connection
- [ ] No memory leaks over 48-hour continuous operation (RSS stable ± 5%)
- [ ] WireGuard tunnel survives daily ISP reconnections (auto-reconnect works)
- [ ] Shadow trading runs for minimum 2 weeks before proceeding to live

---

## Task 5.3 — Production Deployment with Live Capital

**Tool:** Cursor
**Skill Reference:** `forex-broker-adapter > MT5 Adapter`, `cvar-risk-optimizer > Circuit Breakers`

Transition from shadow trading to live execution by switching the order routing from `SimAdapter` to `MT5Adapter`.

**Graduated position sizing (capital preservation first):**

| Period | Kelly Multiplier | Condition to Advance |
|--------|-----------------|---------------------|
| Weeks 1-2 | 25% of calculated Kelly | No L2+ circuit breaker events |
| Weeks 3-4 | 50% of calculated Kelly | Positive cumulative PnL |
| Month 2+ | 100% of calculated Kelly | Continued positive expectancy |

**Configuration change:**

```yaml
# config/deployment/production.yaml
mode: production
execution:
  adapter: mt5           # ← Changed from 'sim' to 'mt5'
  kelly_scale: 0.25      # ← Start at 25%, increase manually
```

**Circuit breaker verification (do this on day 1):**
- Intentionally trigger L1 by opening a position that creates >2% paper drawdown
- Verify L1 fires and reduces sizing to 50%
- Close the position to reset
- Document the circuit breaker response time

**Daily reconciliation process:**

```python
# scripts/daily_reconciliation.py
"""
Compares ArcticDB position records with MT5 broker position report.
Runs daily at market close (22:00 UTC Friday, or 21:00 UTC weekdays).
Flags any discrepancy in: symbol, side, quantity, or entry price.
"""
```

**Alerting configuration:**

| Event | Channel | Response |
|-------|---------|----------|
| Circuit breaker L1 | Telegram + email | Monitor, no action needed |
| Circuit breaker L2 | Telegram + email + SMS | Review within 1 hour |
| Circuit breaker L3 | Telegram + email + SMS + phone call | Immediate investigation |
| Strategy sandboxed (ECT) | Telegram | Review at next daily check |
| Bridge connection lost | Telegram | Check VPS within 15 minutes |
| Reconciliation mismatch | Email | Investigate before next trading session |

**Output Files:**

```
config/deployment/production.yaml
scripts/deploy_production.sh
scripts/daily_reconciliation.py
config/alerting/webhooks.yaml
docs/production_runbook.md
```

**Validation:**

- [ ] First live trade executes successfully on MT5 broker
- [ ] Position reconciliation matches between ArcticDB and MT5 broker report
- [ ] Circuit breaker L1 fires and reduces sizing (intentionally tested on day 1)
- [ ] Alert webhook delivers notification within 10 seconds of triggering event
- [ ] Daily PnL report generated and stored in ArcticDB `portfolio` library
- [ ] Graduated sizing: 25% → 50% → 100% progression documented
- [ ] No L3 circuit breaker events in first month of live trading

---

## Task 5.4 — Stage B Migration Preparation (CME Futures Readiness)

**Tool:** Claude Code
**Skill Reference:** `hft-network-topology > Stage B`, `ml-momentum-orderflow`, `alpha-cointegration-carry > Stage B`

While Stage A runs in production, prepare Stage B infrastructure in parallel. This task does not interrupt live trading.

**5.4.1 — Implement CMEAdapter:**

Implement `CMEAdapter` inheriting from the same abstract interfaces as `MT5Adapter`:
- `MarketDataProvider`: reads from CME MDP 3.0 multicast via ArcticDB `mbo_ticks` library
- `OrderExecutor`: wraps CME iLink 3.0 FIX session (Negotiate → Establish → Order)
- `PositionManager`: tracks positions from FIX Drop Copy confirmations
- Contract sizing instead of lot sizing

This adapter must pass the identical interface contract tests as MT5Adapter and SimAdapter.

**5.4.2 — Implement FuturesCarryProvider:**

Replace the stub from Phase 3B.2 with full implementation:

```python
def compute_futures_carry(front_price, back_price,
                           front_expiry_days, back_expiry_days):
    """
    carry = (F1/F2 - 1) × 365/(D2 - D1)
    Returns the same normalized float as ForexCarryProvider.
    """
```

**5.4.3 — Implement MBO Feature Pipeline:**

From `ml-momentum-orderflow` skill — the features that only work with genuine order book data:
- OFI (Order Flow Imbalance) — Cont, Kukanov, Stoikov (2014)
- VPIN (Volume-Synchronized Probability of Informed Trading)
- Depth imbalance at L1-L5
- Microprice
- Kyle's lambda
- Iceberg order detection

All functions `@njit(cache=True)` compiled. These supplement (not replace) the 27 features from `ml-price-momentum`.

**5.4.4 — Prepare NY4/LD4 infrastructure:**

From `hft-network-topology > Stage B`:
- Ansible playbooks for bare-metal provisioning (PREEMPT_RT kernel, OpenOnload, core affinity)
- WireGuard 3-site mesh configuration (NY4, LD4, Nairobi)
- NATS hub+leaf cluster configuration
- Terraform for Equinix Fabric interconnection

**5.4.5 — CME sandbox certification:**

Complete CME iLink 3.0 certification in their New Release environment:
- Session establishment (Negotiate → Establish with HMAC)
- Order entry and fill confirmation
- Market data recovery protocol (snapshot + incremental replay)
- Sequence number gap handling

**5.4.6 — Migration runbook:**

Document the exact sequence of changes for migration day:

```markdown
## Migration Runbook: Stage A → Stage B

### Pre-Migration (Week Before)
1. ☐ CME sandbox certification completed
2. ☐ NY4/LD4 servers provisioned and configured
3. ☐ WireGuard 3-site mesh tested (ping all sites)
4. ☐ NATS cluster operational (hub at NY4, leaves at LD4 + Nairobi)
5. ☐ CMEAdapter passes all interface contract tests
6. ☐ FuturesCarryProvider produces correct values on test data
7. ☐ MBO features compile and produce valid outputs on synthetic data

### Migration Day
1. ☐ Flatten all Forex positions at market close
2. ☐ Switch config: adapter = cme, kelly_scale = 0.25
3. ☐ Deploy CMEAdapter to NY4 execution server
4. ☐ Verify CME FIX session connects and authenticates
5. ☐ Verify MDP 3.0 market data flowing into ArcticDB mbo_ticks
6. ☐ Enable MBO features in ML momentum pipeline
7. ☐ Switch carry provider from ForexCarryProvider to FuturesCarryProvider
8. ☐ Start shadow trading on CME for 1 week
9. ☐ After successful shadow week: enable live trading at 25% Kelly

### Rollback Plan
If any step fails:
1. ☐ Switch config back: adapter = mt5
2. ☐ Resume Forex trading within 1 hour
3. ☐ Investigate failure, schedule retry
```

**Output Files:**

```
src/execution/cme_adapter.py            # Full CME iLink 3.0 implementation
src/alpha/carry/futures_carry.py         # Full term structure carry
src/alpha/ml_mbo_orderflow/__init__.py
src/alpha/ml_mbo_orderflow/features/
  ofi.py, vpin.py, depth.py, microprice.py, iceberg.py, kyle_lambda.py
  builder.py
infra/stage_b/
  ansible/                               # Bare-metal provisioning playbooks
  terraform/                             # Equinix Fabric configs
  wireguard/                             # 3-site mesh configs
  nats/                                  # Hub + leaf cluster configs
  kernel/                                # PREEMPT_RT build script
  onload/                                # Solarflare OpenOnload installation
docs/migration_runbook.md
tests/execution/test_cme_adapter.py
tests/alpha/test_mbo_features.py
```

**Validation:**

- [ ] CMEAdapter passes identical interface contract tests as MT5Adapter and SimAdapter
- [ ] FuturesCarryProvider produces correct carry on known term structure data
- [ ] OFI/VPIN features compile under Numba and produce valid values on synthetic MBO data
- [ ] NY4/LD4 Ansible playbooks execute without errors on test servers
- [ ] WireGuard 3-site mesh: all sites can ping each other
- [ ] NATS hub+leaf topology: telemetry flows NY4 → Nairobi via leaf
- [ ] CME sandbox: successful Negotiate → Establish → Order → Fill cycle
- [ ] Migration runbook reviewed by all team members
- [ ] Rollback procedure tested: switch from CME back to MT5 in < 1 hour

---

## PHASE 5 COMPLETE

**Phase 5 Completion Gate:**

- [ ] End-to-end tests pass on full codebase with 80%+ coverage
- [ ] Shadow trading runs 2+ weeks without critical errors
- [ ] Live trading executes successfully with circuit breakers validated
- [ ] Daily reconciliation produces zero discrepancies for 5+ consecutive days
- [ ] Stage B components (CMEAdapter, FuturesCarryProvider, MBO features) implemented and tested
- [ ] Migration runbook documented and rehearsed
- [ ] **SYSTEM OPERATIONAL IN PRODUCTION**

---

## Implementation Summary

| Phase | Duration | Key Deliverables | Skills Used |
|-------|----------|-----------------|-------------|
| Phase 1 | 2-3 weeks | CI/CD pipeline, execution abstraction, MT5 adapter | ast-tdd-validation, forex-broker-adapter |
| Phase 2 | 2-3 weeks | ArcticDB storage, PiT compliance, VectorBT backtesting | arcticdb-vectorbt-engine |
| Phase 3 | 4-6 weeks | Regime detector, cointegration, carry, ML momentum | hmm-garch, alpha-coint-carry, ml-price-momentum |
| Phase 4 | 3-4 weeks | CVaR/Kelly/ECT risk engine, NATS telemetry, React dashboard | cvar-risk-optimizer, zeromq-nats-react-ui |
| Phase 5 | 3-4 weeks | Integration testing, shadow/live trading, Stage B prep | All 10 skills |

**Total: 14-20 weeks (3.5-5 months) to Stage A production deployment.**

Stage B migration executes 6-12 months after Stage A goes live, depending on:
- Capital accumulation (need $50K+ for CME margin requirements)
- Strategy validation (6+ months consistent positive expectancy net of spreads)
- Spread cost analysis (if >30% of gross alpha is lost to spreads, futures will help)
- CME certification completion
