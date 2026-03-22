# PHASE 4: Risk Management, IPC, and Dashboard

**Duration:** 3-4 weeks
**Dependencies:** Phase 3 (alpha engines produce strategy returns for CVaR and Kelly)
**Skills Used:** `cvar-risk-optimizer`, `zeromq-nats-react-ui`

Phase 4 builds the risk engine that governs all position sizing and the IPC/dashboard layer that connects everything for monitoring. The risk engine must be complete before the dashboard because the dashboard displays risk metrics.

---

## Phase 4A: CVaR Risk Engine

**Read:** `SKILL.md: cvar-risk-optimizer`, all sections.

---

### Task 4A.1 — Implement CVaR Computation (All Three Methods)

**Tool:** Cursor
**Skill Reference:** `cvar-risk-optimizer > CVaR Computation`

Implement three CVaR computation methods plus the Forex-specific spread-adjusted variant.

**Method 1 — Historical Simulation:**

```python
def compute_cvar_historical(returns: np.ndarray, alpha: float = 0.95) -> tuple[float, float]:
    losses = -returns
    var = np.percentile(losses, alpha * 100)
    cvar = losses[losses >= var].mean()
    return var, cvar
```

**Method 2 — Parametric (GARCH-informed):**

```python
def compute_cvar_parametric(mu: float, sigma: float, alpha: float = 0.95) -> tuple[float, float]:
    z = norm.ppf(alpha)
    var = -(mu - z * sigma)
    cvar = -(mu - sigma * norm.pdf(z) / (1 - alpha))
    return var, cvar
```

Uses σ from the GARCH conditional variance computed by the regime detector in Phase 3A.

**Method 3 — Cornish-Fisher (fat tails):**

```python
def compute_cvar_cornish_fisher(returns: np.ndarray, alpha: float = 0.95) -> tuple[float, float]:
    mu, sigma = np.mean(returns), np.std(returns)
    skew = scipy.stats.skew(returns)
    kurt = scipy.stats.kurtosis(returns)  # excess kurtosis
    z = norm.ppf(alpha)
    z_cf = z + (z**2-1)*skew/6 + (z**3-3*z)*kurt/24 - (2*z**3-5*z)*skew**2/36
    var = -(mu + z_cf * sigma)
    tail = returns[returns <= -(mu + z_cf * sigma)]
    cvar = -tail.mean() if len(tail) > 0 else var * 1.2
    return var, cvar
```

Better for CME futures and Forex data which exhibit fat tails (positive excess kurtosis).

**Forex-Specific: Spread-Adjusted CVaR (Stage A only):**

```python
def compute_cvar_with_spread(returns: np.ndarray, spread_history: np.ndarray,
                              alpha: float = 0.95) -> tuple[float, float]:
    """
    During crisis periods, retail Forex spreads widen dramatically.
    This correlates with the worst return periods, making the tail fatter.
    Use p95 spread during stress, median spread otherwise.
    """
    spread_cost = np.where(
        returns < np.percentile(returns, 10),      # Worst 10% of returns
        np.percentile(spread_history, 95) * 2,      # p95 spread, round-trip
        np.median(spread_history) * 2                # Median spread, round-trip
    )
    adjusted_returns = returns - spread_cost
    return compute_cvar_historical(adjusted_returns, alpha)
```

**Output Files:**

```
src/risk/__init__.py
src/risk/cvar/__init__.py
src/risk/cvar/historical.py
src/risk/cvar/parametric.py
src/risk/cvar/cornish_fisher.py
src/risk/cvar/spread_adjusted.py
tests/risk/test_cvar.py
```

**Validation:**

- [ ] Historical CVaR on normal distribution matches parametric result (within 2%)
- [ ] `CVaR >= VaR` always (sanity check on all methods)
- [ ] Cornish-Fisher: CVaR increases for fat-tailed distribution vs Gaussian
- [ ] Spread-adjusted CVaR > standard CVaR (spread cost makes the tail worse)
- [ ] Edge case: all returns positive → VaR and CVaR are both negative (no loss)

---

### Task 4A.2 — Implement CVXPY Portfolio Optimizer

**Tool:** Claude Code
**Skill Reference:** `cvar-risk-optimizer > CVXPY Portfolio Optimization`

Implement the Rockafellar-Uryasev LP reformulation:

```python
import cvxpy as cp

def optimize_portfolio_cvar(
    returns: np.ndarray,       # (T, N) matrix of strategy returns
    alpha: float = 0.95,
    max_weight: float = 0.25,  # No strategy > 25% of portfolio
    cvar_budget: float = 0.05  # 5% maximum CVaR
) -> np.ndarray:
    T, N = returns.shape
    w = cp.Variable(N)
    zeta = cp.Variable()
    u = cp.Variable(T)

    losses = -returns @ w
    constraints = [
        u >= 0,
        u >= losses - zeta,
        cp.sum(w) == 1,
        w >= 0,
        w <= max_weight,
        zeta + (1 / (T * (1 - alpha))) * cp.sum(u) <= cvar_budget
    ]

    objective = cp.Minimize(zeta + (1 / (T * (1 - alpha))) * cp.sum(u))
    problem = cp.Problem(objective, constraints)
    problem.solve(solver=cp.ECOS)

    if problem.status != 'optimal':
        # Fallback to SCS solver
        problem.solve(solver=cp.SCS)

    return w.value
```

**Risk budget allocation for Stage A:**

| Strategy | CVaR Budget Share |
|----------|------------------|
| Cointegration | 35% |
| Carry | 25% |
| ML Momentum | 30% |
| Reserve (unallocated) | 10% |

**Output Files:**

```
src/risk/cvar/portfolio_opt.py
tests/risk/test_portfolio_opt.py
```

**Validation:**

- [ ] Optimizer finds feasible solution with realistic 3-strategy returns
- [ ] Weights sum to 1.0 (within solver tolerance 1e-6)
- [ ] No weight exceeds `max_weight` constraint (0.25)
- [ ] CVaR of optimized portfolio ≤ `cvar_budget` (0.05)
- [ ] Handles infeasible case gracefully (returns error, not crash)

---

### Task 4A.3 — Implement Kelly Criterion, ECT, and Circuit Breakers

**Tool:** Cursor
**Skill Reference:** `cvar-risk-optimizer > Kelly Criterion, Equity Curve Trading, Circuit Breakers`

**Kelly Criterion with regime adjustment:**

```python
def compute_kelly_fraction(returns: np.ndarray, regime: str,
                            max_fraction: float = 0.15) -> float:
    mu = np.mean(returns)
    var = np.var(returns)
    if var == 0 or mu <= 0:
        return 0.0

    full_kelly = mu / var
    multiplier = {'trending': 0.5, 'mean_reverting': 0.4, 'crisis': 0.1}
    adjusted = full_kelly * multiplier.get(regime, 0.3)
    return min(adjusted, max_fraction)
```

For Stage A, the Kelly fraction feeds into `kelly_to_lots()` from the `forex-broker-adapter` skill. For Stage B, it converts to CME contracts: `contracts = int(equity × kelly_fraction / margin_per_contract)`.

**Equity Curve Trading (ECT):**

```python
class EquityCurveTrader:
    """
    Monitors cumulative PnL per strategy.
    Sandboxes strategies with deteriorating equity curves.
    """
    def __init__(self, ma_window=50, deriv_window=20, recovery_bars=10):
        self.ma_window = ma_window       # MA on equity curve
        self.deriv_window = deriv_window  # MA on PnL derivative
        self.recovery_bars = recovery_bars
        self.sandboxed = {}  # {strategy_name: state_dict}
```

**Sandbox trigger:**
- `equity < MA(equity, 50)` AND `dE/dt < MA(dE/dt, 20)`
- Strategy moves to paper trading via virtual executor

**Recovery trigger:**
- `equity_virtual > MA(equity_virtual, 50)` AND `dE_virtual/dt > 0`
- For 10 consecutive bars
- Restore at 50% Kelly, scale to 100% over 20 bars

**Circuit Breakers (identical both stages):**

| Level | Trigger | Action |
|-------|---------|--------|
| L1 WARNING | Daily drawdown > 2% | Reduce all positions to 50% Kelly |
| L2 HALT | Daily drawdown > 5% | Flatten all positions, pause 1 hour |
| L3 SHUTDOWN | Daily drawdown > 10% | Flatten all, disable strategies, require manual restart |

L3 must be idempotent — calling twice does not double-flatten or cause errors.

**Output Files:**

```
src/risk/kelly/__init__.py
src/risk/kelly/criterion.py
src/risk/kelly/regime_adjusted.py
src/risk/ect/__init__.py
src/risk/ect/equity_curve.py
src/risk/ect/virtual_executor.py
src/risk/circuit_breakers/__init__.py
src/risk/circuit_breakers/drawdown_monitor.py
src/risk/circuit_breakers/kill_switch.py
tests/risk/test_kelly.py
tests/risk/test_ect.py
tests/risk/test_circuit_breakers.py
```

**Validation:**

- [ ] Kelly returns 0 when expected return ≤ 0
- [ ] Regime adjustment: crisis = 0.1 × full Kelly
- [ ] Kelly fraction never exceeds `max_fraction` (0.15)
- [ ] ECT sandboxes strategy on synthetic drawdown data
- [ ] ECT restores after 10 consecutive recovery bars
- [ ] Restored strategy starts at 50% Kelly, reaches 100% after 20 bars
- [ ] Circuit breaker L1 fires at 2% daily drawdown
- [ ] Circuit breaker L2 fires at 5%, flattens all positions
- [ ] Circuit breaker L3 fires at 10%, prevents any new orders until manual reset
- [ ] L3 is idempotent (calling twice doesn't cause errors)

---

### Phase 4A Completion Gate

- [ ] CVaR computed correctly by all three methods with spread adjustment for Stage A
- [ ] CVXPY optimizer produces feasible portfolio with CVaR ≤ budget
- [ ] Kelly + ECT + circuit breakers tested on synthetic equity curves
- [ ] `pytest tests/risk/ --cov=src/risk --cov-fail-under=85` passes

---

## Phase 4B: IPC and Dashboard

**Read:** `SKILL.md: zeromq-nats-react-ui`, all sections. Focus on Stage A topology.

---

### Task 4B.1 — Configure NATS Single-Node Telemetry

**Tool:** Claude Code
**Skill Reference:** `zeromq-nats-react-ui > Part 2: NATS Telemetry > Stage A: Single Node`

Deploy NATS server with JetStream enabled on the Linux server.

**Stream configuration:**
- Stream name: `TELEMETRY`
- Subjects: `telemetry.>` (wildcard)
- Storage: File-backed
- Retention: 7 days
- Max bytes: 10 GB
- Consumer: `nairobi-dashboard` (pull-based, durable, explicit ack)

**Telemetry subjects and intervals:**

| Subject | Data | Interval |
|---------|------|----------|
| `telemetry.pnl` | Equity, unrealized PnL, realized PnL | 100ms |
| `telemetry.positions` | Per-symbol position inventory | 1s |
| `telemetry.risk` | CVaR, drawdown %, circuit breaker level | 1s |
| `telemetry.regime` | State probabilities, current regime label | 5s |
| `telemetry.orders` | Fill events, rejects, cancels | On-event |
| `telemetry.latency` | Bridge latency, signal computation time | 10s |
| `telemetry.system` | CPU, memory, disk usage | 30s |

**Telemetry publisher:** Converts alpha engine outputs (regime state, z-scores, carry signals, ML predictions, risk metrics, PnL) into JSON messages and publishes to appropriate subjects.

**WebSocket bridge:** Subscribes to `telemetry.>`, relays messages to connected browser clients over WebSocket. Uses NATS native WebSocket support (server config: `websocket { listen: "0.0.0.0:9222" }`).

**Output Files:**

```
config/nats/stage_a_single.conf
src/ipc/__init__.py
src/ipc/nats/__init__.py
src/ipc/nats/telemetry_pub.py
src/ipc/nats/ws_bridge.py
tests/ipc/test_nats_telemetry.py
```

**Validation:**

- [ ] NATS server starts with JetStream enabled
- [ ] TELEMETRY stream created with correct retention (7 days)
- [ ] Publish → subscribe round-trip delivers message within 50ms on localhost
- [ ] WebSocket bridge relays NATS messages to connected browser client
- [ ] Old messages pruned after 7 days

---

### Task 4B.2 — Build React Module Federation Dashboard

**Tool:** Cursor
**Skill Reference:** `zeromq-nats-react-ui > Part 3: React Module Federation Dashboard`

**Host Shell (`tradingShell`):**
- Sidebar navigation between strategy views
- Header with connection status indicator (green/yellow/red)
- Main content area with `React.lazy()` + `<Suspense>` loading
- `<RemoteErrorBoundary>` fallback for each remote module

**6 Remote Modules:**

| Remote | Port | Key Components |
|--------|------|---------------|
| `regime-monitor` | 3001 | Price chart with regime-colored background bands, state probability bar chart |
| `coint-dashboard` | 3002 | Spread chart, z-score with threshold lines, half-life indicator, hedge ratio |
| `momentum-monitor` | 3003 | ML prediction confidence, feature importance heatmap, SHAP waterfall |
| `carry-monitor` | 3004 | Swap rates table, carry ranking, spread-cost filter status |
| `risk-dashboard` | 3005 | CVaR gauge, drawdown chart, ECT sandbox status, circuit breaker indicators |
| `order-blotter` | 3006 | Trade history table with filters, fill rate, slippage analysis |

**Webpack 5 Module Federation shared dependencies:**

```javascript
shared: {
  react: { singleton: true, requiredVersion: '^18.0.0', strictVersion: true },
  'react-dom': { singleton: true, requiredVersion: '^18.0.0' },
  recharts: { singleton: true },
  '@tanstack/react-query': { singleton: true },
}
```

**Bootstrap pattern** (required for Module Federation):
- `index.js` dynamically imports `./bootstrap`
- `bootstrap.tsx` contains `createRoot()` call

**`useNatsSubscription` React hook:**
- Connects to NATS WebSocket bridge (`wss://server:9222`)
- Buffers messages in `useRef`
- Flushes to state at 100ms intervals (prevents excessive re-renders)
- Auto-reconnect with exponential backoff (1s, 2s, 4s, 8s, max 30s)
- `reconnectJitter: 1000` to prevent thundering herd

**`tradingStage` prop:** Each remote component accepts a `tradingStage: 'forex' | 'futures'` prop that controls unit labeling:

| Stage A (Forex) | Stage B (Futures) |
|-----------------|-------------------|
| "lots" | "contracts" |
| "pips" | "ticks" |
| "swap rate" | "term structure carry" |
| "spread cost" | "exchange fee" |

**Output Files:**

```
ui/shell/package.json
ui/shell/webpack.config.js
ui/shell/src/index.js
ui/shell/src/bootstrap.tsx
ui/shell/src/App.tsx
ui/shell/src/hooks/useNats.ts
ui/shell/src/components/ConnectionStatus.tsx
ui/shell/src/components/RemoteErrorBoundary.tsx
ui/remotes/regime-monitor/         (webpack.config.js, src/, package.json)
ui/remotes/coint-dashboard/
ui/remotes/momentum-monitor/
ui/remotes/carry-monitor/
ui/remotes/risk-dashboard/
ui/remotes/order-blotter/
docker-compose.yml                 (runs all remotes in dev mode)
```

**Validation:**

- [ ] Host shell loads without errors
- [ ] Each remote loads via Module Federation with Suspense fallback
- [ ] Error boundary shows "Module unavailable" when remote is down
- [ ] `useNatsSubscription` hook receives messages from NATS bridge
- [ ] Dashboard displays real-time PnL, regime state, and risk metrics
- [ ] `tradingStage='forex'` renders lots/pips labels correctly

---

## PHASE 4 COMPLETE

**Phase 4 Completion Gate — all must pass before proceeding to Phase 5:**

- [ ] CVaR computed correctly by all three methods plus spread-adjusted variant
- [ ] CVXPY optimizer produces feasible portfolio with CVaR ≤ budget
- [ ] Kelly + ECT + circuit breakers all tested on synthetic data
- [ ] NATS telemetry delivers messages from alpha engines to dashboard
- [ ] React dashboard renders live data from all 6 remote modules
- [ ] **End-to-end test:** signal generation → risk check → simulated execution → PnL → dashboard display
- [ ] `pytest tests/risk/ tests/ipc/ --cov --cov-fail-under=80` passes
- [ ] All pre-commit hooks pass
- [ ] `make all` passes

**Phase 4 delivers:** A complete risk management engine (CVaR, Kelly, ECT, circuit breakers) governing all position sizing, plus a real-time monitoring dashboard connected via NATS telemetry that displays all strategy and risk metrics.
