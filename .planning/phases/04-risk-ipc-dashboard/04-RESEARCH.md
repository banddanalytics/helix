# Phase 4: Risk, IPC & Dashboard — Research

**Researched:** 2026-03-22
**Domain:** CVaR risk engine (Python/CVXPY), NATS JetStream telemetry, Next.js App Router dashboard
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Dashboard Stack**
- D-01: Next.js App Router replaces Webpack 5 Module Federation. IPC-04 requirement updated: "6 route-based views with error boundaries in a Next.js app."
- D-02: Directory: `dashboard/` (existing repo location). Replace the existing Webpack scaffold with a Next.js app rooted there. The workspace `package.json` at `dashboard/package.json` becomes the Next.js root.
- D-03: Styling: Tailwind CSS + shadcn/ui + 21st.dev components. Dark trading terminal aesthetic throughout. No light mode.
- D-04: Charts: Recharts (already in shell package.json). Use for all time-series and gauge visualizations.
- D-05: 7 routes: `/` (overview/summary), `/regime`, `/cointegration`, `/momentum`, `/carry`, `/risk`, `/orders`. Each route has its own `<Suspense>` + `<ErrorBoundary>` — a loading or error in one section does not crash the app or other sections.
- D-06: Vercel deployment: `NEXT_PUBLIC_NATS_WS_URL` env var points to the Linux server's NATS WebSocket bridge (`wss://server:9222`). The Next.js app is statically deployable to Vercel; live data comes from the server at runtime.
- D-07: `tradingStage` context: a React context (not prop drilling) provides `'forex' | 'futures'` to all components. Controls unit labeling.

**Risk Engine Integration**
- D-08: `RegimeOrchestrator.on_bar()` generates raw signals → calls `risk_engine.size_signals(signals, regime, equity)` → returns sized, filtered signals → executor receives only pre-approved orders.
- D-09: Risk engine lives at `src/risk/engine.py`. Exposes a single `RiskEngine` class with: `size_signals()`, `on_bar_end()`, `sandbox_strategy()` / `restore_strategy()`.
- D-10: `size_signals()` applies checks in order: (1) circuit breaker state → reject if L3, scale if L1; (2) ECT sandbox check → route to virtual executor if sandboxed; (3) CVaR budget gate → reject if adding signal exceeds 5% CVaR budget; (4) Kelly fraction → scale position size.

**Telemetry Data Sourcing**
- D-11: `TelemetryState` is a dataclass holding current snapshot of all publishable fields.
- D-12: The orchestrator and risk engine push updates into a shared `TelemetryState` instance. `TelemetryPublisher` reads from it on its own asyncio timer.
- D-13: Seeding at startup: `TelemetryPublisher.__init__()` reads last known state from ArcticDB `portfolio` library for equity/PnL initialization.

**ECT Virtual Executor**
- D-14: Reuse `SimAdapter` from Phase 1 (`src/execution/sim_adapter.py`) as the virtual executor. Add `paper=True` flag — disables ArcticDB writes and order logging, accumulates PnL in-memory only.
- D-15: ECT monitors equity curve per strategy using in-process `TelemetryState`.

**CVaR + CVXPY**
- D-16: Three CVaR methods: historical simulation, parametric (GARCH σ from Phase 3), Cornish-Fisher. Plus spread-adjusted variant.
- D-17: CVXPY LP formulation: Rockafellar-Uryasev. ECOS solver primary, SCS fallback. Budget constraint 5%, per-strategy weight cap 25%.
- D-18: Kelly multipliers: Trending 0.5×, Mean-Reverting 0.4×, Crisis 0.1×. Max fraction 15%.

**Circuit Breakers**
- D-19: L1 at 2% daily drawdown → reduce all to 50% Kelly. L2 at 5% → flatten all, pause 1 hour. L3 at 10% → flatten all, disable strategies, require manual restart. L3 is idempotent.
- D-20: Daily drawdown resets at midnight UTC. L1 state automatically clears on reset.

### Claude's Discretion

- NATS server config file format and deployment method (Docker vs systemd)
- Exact asyncio timer implementation for telemetry publisher intervals
- Next.js App Router file structure within `dashboard/` (page.tsx layout, loading.tsx, error.tsx per route)
- shadcn/ui component selection for gauges, tables, and status indicators
- 21st.dev component choices for any specialized trading visualizations
- Test fixture approach for circuit breaker integration tests

### Deferred Ideas (OUT OF SCOPE)

- NATS hub+leaf cluster for Stage B (cross-continent) — Stage B only
- PREEMPT_RT kernel + OpenOnload for Stage B latency — out of scope for Phase 4
- Telegram/SMS alerting (PROD-06 alerting system) — Phase 5
- Automated pair discovery — v2 requirement
- Light mode for dashboard — out of scope, dark terminal only
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RISK-01 | CVaR computed by historical simulation, parametric (GARCH-informed), and Cornish-Fisher methods | Function signatures verified in SKILL.md and phase spec; CVXPY + scipy in venv |
| RISK-02 | Spread-adjusted CVaR uses p95 spread for worst-10% return periods | Implementation pattern from SKILL.md confirmed |
| RISK-03 | CVXPY portfolio optimizer minimizes CVaR with 25% weight cap and 5% budget constraint | CLARABEL solver confirmed working; ECOS NOT installed — use CLARABEL primary |
| RISK-04 | Kelly criterion applies regime multipliers (Trending 0.5×, MR 0.4×, Crisis 0.1×), capped at 15% | Formula verified in skill; multiplier dict pattern confirmed |
| RISK-05 | ECT sandboxes underperforming strategies; restores after 10 consecutive recovery bars at 50% Kelly, scales to 100% over 20 bars | `SimAdapter` reuse pattern confirmed; `paper=True` flag must be added |
| RISK-06 | Circuit breaker L1: 2% daily drawdown → 50% Kelly | Drawdown monitor + state machine pattern documented |
| RISK-07 | Circuit breaker L2: 5% daily drawdown → flatten all, pause 1 hour | asyncio.sleep or timestamp-based pause confirmed |
| RISK-08 | Circuit breaker L3: 10% daily drawdown → flatten all, disable, require manual restart; idempotent | Idempotent state flag pattern documented |
| IPC-01 | NATS JetStream single-node, TELEMETRY stream, 7 subjects, 7-day retention | NATS v2.12.5 confirmed; Docker deployment confirmed available |
| IPC-02 | Telemetry publisher emits PnL (100ms), positions (1s), risk (1s), regime (5s), orders (on-event) | asyncio timer pattern from Phase 2 precedent; nats-py 2.14.0 in venv |
| IPC-03 | WebSocket bridge relays NATS to browser with auto-reconnect | NATS native WebSocket (port 9222) pattern documented |
| IPC-04 | React host shell: 6 route-based views with error boundaries (NOT Module Federation — see D-01) | Next.js 16.2.1 App Router confirmed; error.tsx per-route isolation |
| IPC-05 | Dashboard displays regime state, z-scores, carry rankings, ML predictions, CVaR, drawdown, order blotter | Next.js routes mapped to 6 existing `dashboard/remotes/` directories |
| IPC-06 | `useNatsSubscription` buffers at 100ms intervals to prevent re-render thrash | `useRef` buffer + `setInterval` flush pattern documented |
</phase_requirements>

---

## Summary

Phase 4 has three well-separated subsystems: a Python risk engine, a NATS telemetry layer, and a Next.js dashboard. All function signatures and math formulations are locked in `_docs/Phase_4_Risk_IPC_Dashboard.md` and the skill files — implementation is transcription, not design work.

The most critical technical discovery is a **solver mismatch**: the spec says "ECOS primary, SCS fallback" but ECOS is not installed in the project `.venv`. CLARABEL is installed and verified to solve the Rockafellar-Uryasev LP correctly — it must replace ECOS as the primary solver. SCS remains available as fallback. The CVXPY LP is feasible with realistic return data when `max_weight=0.5` but can be infeasible with strict `max_weight=0.25` and random noise data — the infeasibility handler must return equal weights (not crash).

The dashboard decision (D-01) replaces Webpack Module Federation with Next.js App Router routes. The existing `dashboard/shell/package.json` has a Webpack scaffold that must be replaced. The 6 existing `dashboard/remotes/` directories become source material for the 6 Next.js route pages. NATS native WebSocket (`websocket { listen: "0.0.0.0:9222" }`) eliminates the need for a separate Python WebSocket bridge process — the browser connects directly to NATS.

The 04-UI-SPEC.md (already approved) provides a complete, binding visual and component contract that implementers must follow exactly.

**Primary recommendation:** Implement in dependency order: CVaR functions → CVXPY optimizer → Kelly + ECT + circuit breakers → `RiskEngine` orchestrator → `TelemetryState` + publisher → NATS config → `useNatsSubscription` hook → Next.js routes.

---

## Standard Stack

### Core Python (Risk Engine)

| Library | Version (verified) | Purpose | Why Standard |
|---------|--------------------|---------|--------------|
| cvxpy | 1.7.5 (in .venv) | Portfolio optimization LP | Rockafellar-Uryasev CVaR formulation; locked in spec |
| numpy | 1.26.3 (in .venv) | CVaR math, Kelly computation | Already in project; all numeric arrays |
| scipy | 1.15.3 (in .venv) | Cornish-Fisher (skew/kurtosis), parametric CVaR (norm.ppf, norm.pdf) | Already in project; no new dep |
| pandas | 2.2.0 (in .venv) | ECT rolling MA on equity curve | Already in project |
| nats-py | 2.14.0 (in .venv) | NATS JetStream publish/subscribe | Official async Python client |

### CVXPY Solvers (critical — see pitfall)

| Solver | Status | Role |
|--------|--------|------|
| CLARABEL | Installed, verified optimal | PRIMARY (replaces ECOS — ECOS not in .venv) |
| SCS | Installed | FALLBACK |
| OSQP | Installed | Not needed for LP |
| ECOS | NOT INSTALLED | Spec says primary — must update to CLARABEL |

### Core JavaScript (Dashboard)

| Library | Version (verified from npm registry) | Purpose | Why Standard |
|---------|--------------------------------------|---------|--------------|
| next | 16.2.1 | App Router, SSG for Vercel, per D-01 | Locked decision D-01 |
| react | 18.3.1 (in shell/package.json) | Component model | Already in repo |
| recharts | 2.13.3 (in shell/package.json) | All charts per D-04 | Already in repo, locked |
| @tanstack/react-query | 5.62.7 (in shell/package.json) | Server state, caching | Already in repo |
| tailwindcss | 4.2.2 | Styling per D-03 | Locked D-03 |
| shadcn | 4.1.0 | Component library per D-03 | Locked D-03 |
| lucide-react | 0.577.0 | Icons (bundled with shadcn) | Standard with shadcn |

### Infrastructure

| Component | Version | Deployment Method | Why |
|-----------|---------|-------------------|-----|
| nats-server | v2.12.5 (latest as of 2026-03-09) | Docker (`nats:latest` image) | Docker confirmed available; simplest for dev and prod |

**Installation — Python (already installed, no new deps required):**
```bash
# All Python deps already in .venv — no pip installs needed for risk engine
# Verify: .venv/bin/python -c "import cvxpy, nats, scipy, numpy, pandas"
```

**Installation — Next.js dashboard:**
```bash
cd dashboard
# Remove existing webpack shell, initialize Next.js
rm -rf shell/  # remove webpack scaffold
npx create-next-app@latest . --typescript --tailwind --app --no-src-dir --import-alias "@/*"
npx shadcn init  # select zinc/slate dark base — components.json does not yet exist
npx shadcn add badge card table skeleton alert progress sheet navigation-menu separator tooltip pagination
npm install recharts @tanstack/react-query lucide-react
```

---

## Architecture Patterns

### Recommended Project Structure

```
src/risk/
├── __init__.py
├── engine.py              # RiskEngine class (D-09) — single entry point
├── cvar/
│   ├── __init__.py
│   ├── historical.py      # compute_cvar_historical()
│   ├── parametric.py      # compute_cvar_parametric()
│   ├── cornish_fisher.py  # compute_cvar_cornish_fisher()
│   ├── spread_adjusted.py # compute_cvar_with_spread() — Stage A
│   └── portfolio_opt.py   # optimize_portfolio_cvar() — CVXPY
├── kelly/
│   ├── __init__.py
│   ├── criterion.py       # compute_kelly_fraction()
│   └── regime_adjusted.py # regime multiplier application
├── ect/
│   ├── __init__.py
│   ├── equity_curve.py    # EquityCurveTrader class
│   └── virtual_executor.py  # wraps SimAdapter with paper=True
└── circuit_breakers/
    ├── __init__.py
    ├── drawdown_monitor.py  # DrawdownMonitor tracks daily high-water mark
    └── kill_switch.py       # CircuitBreaker state machine (L0/L1/L2/L3)

src/ipc/
├── __init__.py
├── telemetry_state.py     # TelemetryState dataclass (D-11)
└── nats/
    ├── __init__.py
    ├── telemetry_pub.py   # TelemetryPublisher — asyncio timers + NATS publish
    └── ws_bridge.py       # OPTIONAL: only needed if NATS native WS not used

config/nats/
└── stage_a.conf           # JetStream + websocket config

dashboard/                 # Next.js app root (D-02)
├── package.json           # Next.js root (replaces workspace root)
├── next.config.ts
├── tailwind.config.ts
├── components.json        # shadcn config (created by `npx shadcn init`)
├── app/
│   ├── layout.tsx         # Root layout — sidebar nav, TradingStageProvider
│   ├── page.tsx           # / — Overview
│   ├── regime/page.tsx
│   ├── cointegration/page.tsx
│   ├── momentum/page.tsx
│   ├── carry/page.tsx
│   ├── risk/page.tsx
│   └── orders/page.tsx
├── components/
│   ├── ui/                # shadcn auto-generated
│   ├── providers/
│   │   └── trading-stage-provider.tsx   # D-07 context
│   ├── hooks/
│   │   └── use-nats-subscription.ts     # IPC-06 buffered hook
│   └── connection-status.tsx
└── tests/risk/            # Python tests
    ├── __init__.py
    ├── test_cvar.py
    ├── test_portfolio_opt.py
    ├── test_kelly.py
    ├── test_ect.py
    └── test_circuit_breakers.py
```

### Pattern 1: RiskEngine Call Chain (D-08 through D-10)

**What:** `RegimeOrchestrator.on_bar()` calls `RiskEngine.size_signals()` which applies a sequential gate chain.

**When to use:** All signal processing — every bar, every signal.

```python
# src/risk/engine.py — RiskEngine.size_signals() gate sequence (D-10)
def size_signals(
    self,
    signals: list[SignalRow],
    regime: RegimeState,
    equity: float,
) -> list[SignalRow]:
    """Apply gate chain: circuit breaker → ECT → CVaR → Kelly."""
    # Gate 1: circuit breaker
    cb_level = self._circuit_breaker.current_level
    if cb_level == CircuitBreakerLevel.L3:
        return []  # all signals rejected until manual restart

    # Gate 2: ECT sandbox routing (side-effects: routes to paper executor)
    live_signals = [s for s in signals if not self._ect.is_sandboxed(s.engine)]

    # Gate 3: CVaR budget gate
    approved = self._cvxpy_gate(live_signals, equity)

    # Gate 4: Kelly sizing
    kelly_scale = 0.5 if cb_level == CircuitBreakerLevel.L1 else 1.0
    return self._apply_kelly(approved, regime, equity, kelly_scale)
```

### Pattern 2: TelemetryState Shared Reference (D-11, D-12)

**What:** A single `TelemetryState` dataclass instance is passed by reference to both `RiskEngine` and `RegimeOrchestrator`. `TelemetryPublisher` reads from it on its own asyncio timer without blocking the trading path.

**When to use:** Any component that needs to report telemetry data.

```python
# src/ipc/telemetry_state.py
from dataclasses import dataclass, field

@dataclass
class TelemetryState:
    equity: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    positions: dict = field(default_factory=dict)
    cvar: dict = field(default_factory=dict)   # {'historical': x, 'parametric': y, 'cf': z}
    drawdown_pct: float = 0.0
    circuit_breaker_level: int = 0             # 0/1/2/3
    regime_state: str = "TRENDING"
    regime_probs: dict = field(default_factory=dict)
    sandboxed_strategies: list = field(default_factory=list)
```

### Pattern 3: TelemetryPublisher asyncio Timer (D-12, IPC-02)

**What:** Separate asyncio tasks per subject, each on its own interval. Uses `asyncio.create_task()` — no APScheduler, consistent with Phase 2 pattern.

```python
# src/ipc/nats/telemetry_pub.py
class TelemetryPublisher:
    async def start(self) -> None:
        self._nc = await nats.connect("nats://localhost:4222")
        self._js = self._nc.jetstream()
        asyncio.create_task(self._publish_loop("telemetry.pnl", 0.1))    # 100ms
        asyncio.create_task(self._publish_loop("telemetry.positions", 1.0))
        asyncio.create_task(self._publish_loop("telemetry.risk", 1.0))
        asyncio.create_task(self._publish_loop("telemetry.regime", 5.0))

    async def _publish_loop(self, subject: str, interval: float) -> None:
        while True:
            payload = self._build_payload(subject)
            await self._js.publish(subject, json.dumps(payload).encode())
            await asyncio.sleep(interval)
```

### Pattern 4: NATS Native WebSocket (IPC-03 simplified)

**What:** NATS server v2.2+ has built-in WebSocket support. Browser connects directly to NATS — no Python WebSocket bridge process needed.

**Server config:**
```
# config/nats/stage_a.conf
jetstream {
  store_dir: "/data/nats"
  max_mem: 1GB
  max_file: 10GB
}
websocket {
  listen: "0.0.0.0:9222"
  no_tls: true   # TLS at reverse proxy for prod; dev uses plaintext
}
```

**Browser connection (useNatsSubscription hook):**
```typescript
// The NATS.ws browser client connects directly to ws://host:9222
// No Python bridge process required
import { connect, StringCodec } from "nats.ws";
```

### Pattern 5: useNatsSubscription with 100ms Batching (IPC-06)

**What:** Messages accumulate in a `useRef` buffer; a `setInterval` flushes to React state every 100ms. This prevents re-render on every 100ms PnL message.

```typescript
// dashboard/components/hooks/use-nats-subscription.ts
export function useNatsSubscription(subject: string) {
  const [data, setData] = useState<unknown>(null);
  const bufferRef = useRef<unknown[]>([]);

  useEffect(() => {
    let nc: NatsConnection;
    const flush = setInterval(() => {
      if (bufferRef.current.length > 0) {
        setData(bufferRef.current[bufferRef.current.length - 1]); // latest wins
        bufferRef.current = [];
      }
    }, 100);

    (async () => {
      nc = await connect({ servers: process.env.NEXT_PUBLIC_NATS_WS_URL });
      const sub = nc.subscribe(subject);
      for await (const msg of sub) {
        bufferRef.current.push(JSON.parse(sc.decode(msg.data)));
      }
    })();

    return () => {
      clearInterval(flush);
      nc?.close();
    };
  }, [subject]);

  return data;
}
```

### Pattern 6: Next.js App Router Per-Route Error Isolation (IPC-04, D-05)

**What:** Each route gets its own `error.tsx` (must be `"use client"`) and `loading.tsx`. An unhandled error in `/risk` does not affect `/regime`.

```
app/
├── regime/
│   ├── page.tsx
│   ├── loading.tsx   # <Skeleton> while fetching
│   └── error.tsx     # "use client" — ErrorBoundary
```

### Anti-Patterns to Avoid

- **ECOS as primary solver:** ECOS is NOT in the `.venv`. Using `cp.ECOS` will raise `SolverError`. Use `cp.CLARABEL` as primary.
- **Direct ArcticDB reads on the telemetry hot path:** `TelemetryPublisher` reads from `TelemetryState` (in-memory), never ArcticDB. Only startup seeding uses ArcticDB (D-13).
- **`setState` on every NATS message:** Will thrash React rendering at 100ms PnL interval. Buffer in `useRef`, flush at 100ms (IPC-06).
- **Prop drilling `tradingStage`:** Must use React context (D-07), not props.
- **L3 circuit breaker double-execution:** L3 must be idempotent — check `self._level == L3` before executing flatten-all logic.
- **CVaR LP infeasibility crash:** When `max_weight=0.25` is too tight for poor return data, optimizer may be infeasible. Fallback must return equal weights and log a warning — never raise.
- **ModuleFederation references in code:** Spec was written with Module Federation; D-01 replaces it with Next.js. Do not reference `remoteEntry.js`, `ModuleFederationPlugin`, or multi-port remote servers.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CVaR LP formulation | Custom gradient descent | CVXPY (Rockafellar-Uryasev) | Solver handles corner cases, infeasibility, warm-starting |
| Cornish-Fisher skew/kurtosis | Custom moment estimators | `scipy.stats.skew`, `scipy.stats.kurtosis` | Already installed; numerically stable |
| Parametric normal quantile | Custom lookup table | `scipy.stats.norm.ppf`, `norm.pdf` | Already installed |
| Rolling MA for ECT | Custom loop | `pd.Series.rolling().mean()` | Handles edge cases, NaN propagation |
| NATS async client | Custom TCP socket | `nats-py` 2.14.0 | Official client; handles reconnect, JetStream ACK |
| Browser WebSocket with NATS | Custom relay server | `nats.ws` npm package + NATS native WS port 9222 | No extra process needed |
| React state batching | Custom debounce | `useRef` buffer + `setInterval` 100ms flush | Predictable interval; avoids stale closure issues |
| shadcn component variants | Custom CSS component library | `npx shadcn add` | Dark mode out-of-box; Radix accessibility included |

**Key insight:** CVXPY's CLARABEL solver handles numeric edge cases (near-infeasibility, ill-conditioned matrices) that hand-rolled QP solvers routinely fail on. The fallback to SCS is a solver swap, not algorithm re-implementation.

---

## Common Pitfalls

### Pitfall 1: ECOS Solver Not Available

**What goes wrong:** Code calls `problem.solve(solver=cp.ECOS)` → `cvxpy.error.SolverError: The solver ECOS is not installed.`

**Why it happens:** ECOS was removed from CVXPY default install in recent versions; the spec was written when ECOS was standard. The project `.venv` has CVXPY 1.7.5 with CLARABEL, OSQP, SCIPY, SCS — no ECOS.

**How to avoid:** Use `cp.CLARABEL` as primary. Update all references in spec that say "ECOS primary, SCS fallback" to "CLARABEL primary, SCS fallback."

**Warning signs:** `SolverError` at first LP solve in test.

### Pitfall 2: CVXPY LP Infeasibility with Tight Weight Caps

**What goes wrong:** `optimize_portfolio_cvar()` returns `w.value = None` and `problem.status = 'infeasible'` when `max_weight=0.25` is applied to returns data where the optimizer cannot simultaneously satisfy `sum(w)==1`, `w<=0.25`, and `CVaR<=0.05`.

**Why it happens:** With 3 strategies and `max_weight=0.25`, the maximum achievable allocation is 0.75 (not 1.0) — the constraint `sum(w)==1` cannot be satisfied. The `max_weight` in the Rockafellar-Uryasev formulation is a risk budget constraint, not a hard allocation cap; the correct interpretation for 3 strategies is `max_weight=0.5` or using a separate soft budget.

**How to avoid:** The SKILL.md and spec use `max_weight=0.25` (which works for N≥4 strategies). For N=3, implement a fallback: if `problem.status != 'optimal'`, relax `max_weight` to `1/N` and retry. Final fallback: equal weights `[1/N, 1/N, 1/N]`.

**Warning signs:** `w.value is None` after solve; `problem.status == 'infeasible'`.

### Pitfall 3: NATS JetStream Subject Mismatch

**What goes wrong:** `TelemetryPublisher` publishes to `telemetry.pnl` but the TELEMETRY stream is configured with subject filter `telemetry.>` — messages are captured. However, the `useNatsSubscription` hook subscribes to `telemetry.pnl` directly; if the browser connects before the stream is created, subscription silently returns nothing.

**Why it happens:** NATS core subscriptions and JetStream consumers are different. The browser client should use core NATS subscription (not JetStream pull), which works regardless of stream state.

**How to avoid:** Publisher uses JetStream `js.publish()` (durable, persistent). Browser uses core NATS subscribe (ephemeral, push-based). These are compatible — JetStream publish is also visible to core subscribers on the same subject.

**Warning signs:** Dashboard shows no data even though publisher logs "published"; check `nats sub 'telemetry.>'` from CLI to verify messages are flowing.

### Pitfall 4: asyncio Timer Drift in TelemetryPublisher

**What goes wrong:** Using `asyncio.sleep(0.1)` in a loop for 100ms PnL publishing results in wall-clock drift — each iteration takes `0.1s + processing_time`, so the actual interval is longer than 100ms under load.

**Why it happens:** `asyncio.sleep()` is a minimum delay, not a fixed-rate timer.

**How to avoid:** Use monotonic clock tracking: record `t0 = asyncio.get_event_loop().time()` before processing, sleep for `max(0, interval - (now - t0))`.

**Warning signs:** PnL messages arriving at 120ms instead of 100ms; dashboard "STALE" badge appearing at 200ms threshold.

### Pitfall 5: ECT Equity Curve Insufficient History

**What goes wrong:** `EquityCurveTrader.evaluate()` calls `pd.Series(equity_curve).rolling(50).mean()` — if the strategy has fewer than 50 bars of history, the MA is NaN for all values and sandbox trigger logic fails.

**Why it happens:** Rolling window requires `ma_window` observations before producing a value.

**How to avoid:** Guard with `if len(equity_curve) < self.ma_window: return {'action': 'HOLD'}`. Do not sandbox strategies without sufficient history.

**Warning signs:** All strategies immediately sandbox on startup.

### Pitfall 6: CircuitBreaker L2 One-Hour Pause — asyncio vs Wall Clock

**What goes wrong:** Using `asyncio.sleep(3600)` for L2 pause blocks the event loop or gets cancelled on process restart — the 1-hour pause is lost.

**Why it happens:** asyncio sleep is process-local and non-persistent.

**How to avoid:** Store `L2_pause_until = datetime.utcnow() + timedelta(hours=1)` in `CircuitBreaker` state. On every `size_signals()` call, check `if datetime.utcnow() < self.L2_pause_until: return []`. The pause survives asyncio task cancellation and is cleared by daily reset.

**Warning signs:** L2 pause not enforced after process restart.

### Pitfall 7: Next.js Error Boundary vs React Error Boundary

**What goes wrong:** Using a client-side class-based `ErrorBoundary` with `componentDidCatch` works in React, but Next.js App Router has a special `error.tsx` convention — if `error.tsx` is missing, errors propagate to the root layout and crash the whole app.

**Why it happens:** Next.js App Router segments each route; each segment needs its own `error.tsx` as the Error Boundary.

**How to avoid:** Create `error.tsx` (with `"use client"` directive) AND `loading.tsx` in every route directory per D-05.

**Warning signs:** Error in `/risk` route triggers full-page crash instead of isolated error card.

### Pitfall 8: Dashboard workspace.json Conflict

**What goes wrong:** `dashboard/package.json` is currently a workspace root (`"workspaces": ["shell", "remotes/*"]`). Replacing `dashboard/shell/package.json` with a Next.js app while keeping the workspace `package.json` causes npm to try to install Next.js as a workspace package, producing conflicts.

**Why it happens:** The existing `dashboard/` is structured as a monorepo for the webpack Module Federation setup being replaced.

**How to avoid:** Per D-02, the workspace `package.json` at `dashboard/package.json` becomes the Next.js root. This means: delete the workspace config entirely; `dashboard/package.json` becomes the Next.js `package.json`; the `dashboard/shell/` and `dashboard/remotes/` directories are replaced by `dashboard/app/` (Next.js routes).

**Warning signs:** `npm install` in `dashboard/` tries to resolve `shell` and `remotes/*` as sub-packages.

---

## Code Examples

### CVaR Historical Simulation

```python
# Source: _docs/Phase_4_Risk_IPC_Dashboard.md, Task 4A.1
def compute_cvar_historical(returns: np.ndarray, alpha: float = 0.95) -> tuple[float, float]:
    losses = -returns
    var = np.percentile(losses, alpha * 100)
    cvar = losses[losses >= var].mean()
    return var, cvar
```

### CVaR Parametric (GARCH-informed)

```python
# Source: _docs/Phase_4_Risk_IPC_Dashboard.md, Task 4A.1
from scipy.stats import norm

def compute_cvar_parametric(mu: float, sigma: float, alpha: float = 0.95) -> tuple[float, float]:
    z = norm.ppf(alpha)
    var = -(mu - z * sigma)
    cvar = -(mu - sigma * norm.pdf(z) / (1 - alpha))
    return var, cvar
```

### CVXPY LP — CLARABEL Primary (D-17, solver corrected)

```python
# Source: _docs/Phase_4_Risk_IPC_Dashboard.md Task 4A.2, SOLVER CORRECTED
import cvxpy as cp

def optimize_portfolio_cvar(
    returns: np.ndarray,
    alpha: float = 0.95,
    max_weight: float = 0.25,
    cvar_budget: float = 0.05,
) -> np.ndarray:
    T, N = returns.shape
    w = cp.Variable(N)
    zeta = cp.Variable()
    u = cp.Variable(T)

    losses = -returns @ w
    constraints = [
        u >= 0, u >= losses - zeta,
        cp.sum(w) == 1, w >= 0, w <= max_weight,
        zeta + (1 / (T * (1 - alpha))) * cp.sum(u) <= cvar_budget,
    ]
    objective = cp.Minimize(zeta + (1 / (T * (1 - alpha))) * cp.sum(u))
    problem = cp.Problem(objective, constraints)
    problem.solve(solver=cp.CLARABEL)   # ECOS not in .venv; use CLARABEL

    if problem.status != "optimal":
        problem.solve(solver=cp.SCS)    # SCS fallback

    if problem.status not in ("optimal", "optimal_inaccurate") or w.value is None:
        # Fallback: equal weights
        return np.full(N, 1.0 / N)

    return w.value
```

### Kelly Fraction with Regime Adjustment

```python
# Source: _docs/Phase_4_Risk_IPC_Dashboard.md Task 4A.3
def compute_kelly_fraction(
    returns: np.ndarray,
    regime: str,
    max_fraction: float = 0.15,
) -> float:
    mu = np.mean(returns)
    var = np.var(returns)
    if var == 0 or mu <= 0:
        return 0.0
    full_kelly = mu / var
    multiplier = {"trending": 0.5, "mean_reverting": 0.4, "crisis": 0.1}
    adjusted = full_kelly * multiplier.get(regime, 0.3)
    return min(adjusted, max_fraction)
```

### Circuit Breaker with Timestamp-Based L2 Pause

```python
# Source: Pattern documented in pitfall 6 above
from datetime import datetime, timezone, timedelta
import enum

class CBLevel(enum.IntEnum):
    L0 = 0; L1 = 1; L2 = 2; L3 = 3

class CircuitBreaker:
    def __init__(self) -> None:
        self._level: CBLevel = CBLevel.L0
        self._l2_resume_at: datetime | None = None

    def update(self, daily_drawdown_pct: float) -> CBLevel:
        now = datetime.now(tz=timezone.utc)
        if daily_drawdown_pct >= 10.0 and self._level != CBLevel.L3:
            self._level = CBLevel.L3  # idempotent: only set once
        elif daily_drawdown_pct >= 5.0 and self._level < CBLevel.L2:
            self._level = CBLevel.L2
            self._l2_resume_at = now + timedelta(hours=1)
        elif daily_drawdown_pct >= 2.0 and self._level < CBLevel.L1:
            self._level = CBLevel.L1
        return self._level

    def is_paused(self) -> bool:
        if self._level == CBLevel.L2 and self._l2_resume_at:
            return datetime.now(tz=timezone.utc) < self._l2_resume_at
        return False

    def daily_reset(self) -> None:
        """Called at midnight UTC. Clears L1; L2/L3 require manual or timeout."""
        if self._level == CBLevel.L1:
            self._level = CBLevel.L0
```

### NATS Config (Docker + native WebSocket)

```
# config/nats/stage_a.conf
jetstream {
  store_dir: "/data/nats"
  max_mem: 1GB
  max_file: 10GB
}
websocket {
  listen: "0.0.0.0:9222"
  no_tls: true
}
```

```yaml
# docker-compose.yml (NATS service)
services:
  nats:
    image: nats:latest
    ports:
      - "4222:4222"   # NATS client port (Python publisher)
      - "9222:9222"   # WebSocket port (browser)
      - "8222:8222"   # HTTP monitoring
    volumes:
      - ./config/nats/stage_a.conf:/etc/nats/nats.conf
      - nats_data:/data/nats
    command: ["-c", "/etc/nats/nats.conf"]
```

### NATS Stream Creation (Python startup)

```python
# Source: nats-py 2.14.0 JetStream API
async def ensure_telemetry_stream(nc: nats.aio.client.Client) -> None:
    js = nc.jetstream()
    try:
        await js.add_stream(
            name="TELEMETRY",
            subjects=["telemetry.>"],
            retention="limits",
            max_age=7 * 24 * 3600,  # 7 days in seconds
            storage="file",
        )
    except nats.js.errors.BadRequestError:
        pass  # Stream already exists
```

### Next.js Route with Suspense + ErrorBoundary (per D-05)

```typescript
// dashboard/app/risk/loading.tsx
import { Skeleton } from "@/components/ui/skeleton";
export default function Loading() {
  return <Skeleton className="h-full w-full" />;
}

// dashboard/app/risk/error.tsx
"use client";
export default function Error({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <div className="text-red-500">
      Connection lost. Dashboard cannot receive live data. Check NATS_WS_URL and server status, then reload.
      <button onClick={reset}>Retry connection</button>
    </div>
  );
}

// dashboard/app/risk/page.tsx
export default function RiskPage() {
  return <Suspense fallback={<Loading />}><RiskDashboard /></Suspense>;
}
```

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x (existing, per pyproject.toml) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/risk/ -x -m 'not slow'` |
| Full suite command | `pytest tests/risk/ tests/ipc/ --cov=src/risk --cov=src/ipc --cov-report=term-missing` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RISK-01 | All 3 CVaR methods produce CVaR ≥ VaR | unit | `pytest tests/risk/test_cvar.py -x` | Wave 0 |
| RISK-02 | Spread-adjusted CVaR > standard CVaR | unit | `pytest tests/risk/test_cvar.py::test_spread_adjusted -x` | Wave 0 |
| RISK-03 | CVXPY optimizer: weights sum=1, w≤0.25, CVaR≤0.05 | unit | `pytest tests/risk/test_portfolio_opt.py -x` | Wave 0 |
| RISK-04 | Kelly crisis=0.1×, trending=0.5×, never exceeds 15% | unit | `pytest tests/risk/test_kelly.py -x` | Wave 0 |
| RISK-05 | ECT sandbox trigger; restore after 10 consecutive bars at 50% Kelly | unit | `pytest tests/risk/test_ect.py -x` | Wave 0 |
| RISK-06 | L1 fires at 2% drawdown; scales Kelly to 50% | unit | `pytest tests/risk/test_circuit_breakers.py::test_l1 -x` | Wave 0 |
| RISK-07 | L2 fires at 5%; flattens positions; 1-hour pause | unit | `pytest tests/risk/test_circuit_breakers.py::test_l2 -x` | Wave 0 |
| RISK-08 | L3 fires at 10%; idempotent; blocks all orders until manual reset | unit | `pytest tests/risk/test_circuit_breakers.py::test_l3_idempotent -x` | Wave 0 |
| IPC-01 | NATS stream TELEMETRY exists with 7-day retention | integration | `pytest tests/ipc/test_nats_telemetry.py -x` | Wave 0 |
| IPC-02 | Publisher emits all 7 subjects at correct intervals | unit (mock NATS) | `pytest tests/ipc/test_telemetry_pub.py -x` | Wave 0 |
| IPC-03 | WebSocket bridge / NATS native WS delivers messages to browser | manual-only | NATS native WS tested via nats.ws client; no automated test | — |
| IPC-04 | All 7 Next.js routes render without crash; error in one does not affect others | manual-only | Visual verification in browser; no Python test | — |
| IPC-05 | Dashboard displays regime, z-scores, CVaR, drawdown, orders from live NATS feed | manual-only | Visual verification against live NATS publisher | — |
| IPC-06 | useNatsSubscription batches at 100ms; no re-render on every message | manual-only | React DevTools profiler; no automated test | — |

### Sampling Rate

- **Per task commit:** `pytest tests/risk/ -x -m 'not slow'`
- **Per wave merge:** `pytest tests/risk/ tests/ipc/ --cov=src/risk --cov=src/ipc --cov-fail-under=80`
- **Phase gate:** Full suite green (`make all`) before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/risk/__init__.py`
- [ ] `tests/risk/test_cvar.py` — RISK-01, RISK-02
- [ ] `tests/risk/test_portfolio_opt.py` — RISK-03
- [ ] `tests/risk/test_kelly.py` — RISK-04
- [ ] `tests/risk/test_ect.py` — RISK-05
- [ ] `tests/risk/test_circuit_breakers.py` — RISK-06, RISK-07, RISK-08
- [ ] `tests/ipc/__init__.py`
- [ ] `tests/ipc/test_nats_telemetry.py` — IPC-01, IPC-02 (requires running NATS; mark `@pytest.mark.slow` or mock `nats.connect`)

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| ECOS as CVXPY default solver | CLARABEL (cone LP, SOCP) | CVXPY ~1.4+ | Must use CLARABEL; ECOS not in .venv |
| Webpack 5 Module Federation | Next.js App Router routes | Phase 4 D-01 | Single `npm run build` → Vercel; no multi-port dev servers |
| Python WebSocket bridge process | NATS native WebSocket (port 9222) | NATS ~2.2+ | Eliminates ws_bridge.py process; browser connects directly |
| Module Federation remote entry | Next.js error.tsx + loading.tsx | Phase 4 D-01 | Per-route error isolation via Next.js convention |
| @tanstack/react-query v4 | v5 (in shell/package.json) | 2024 | Breaking API changes: `useQuery({queryKey, queryFn})`, no `onSuccess` callback |

**Deprecated/outdated in spec:**
- `ws_bridge.py` Python process: NATS native WebSocket makes this unnecessary (NATS server handles WS directly). The skill file shows a Python bridge; Phase 4 should use NATS native WS instead to reduce operational complexity.
- `ui/` path references in `_docs/Phase_4_Risk_IPC_Dashboard.md`: Per D-02, all `ui/` paths map to `dashboard/` in the actual repo.
- Webpack Module Federation config in skill file: Replaced by Next.js App Router per D-01. Ignore `webpack.config.js`, `remoteEntry.js`, `ModuleFederationPlugin` references in the skill file.

---

## Open Questions

1. **NATS server TLS for Vercel deployment**
   - What we know: Vercel serves pages over HTTPS; browser will refuse to connect to `ws://` (plaintext) from an `https://` page (mixed content block).
   - What's unclear: Whether a reverse proxy (nginx/Caddy) is already in place to terminate TLS for port 9222; if not, `wss://` requires TLS on the NATS WebSocket listener.
   - Recommendation: For local development, `NEXT_PUBLIC_NATS_WS_URL=ws://localhost:9222` works. For Vercel production, set `NEXT_PUBLIC_NATS_WS_URL=wss://yourserver.com:9222` and configure TLS in NATS config or via reverse proxy. Executor should add nginx/Caddy TLS termination as a Wave 0 config task.

2. **nats.ws browser package for Next.js**
   - What we know: The `nats.ws` npm package provides browser-compatible NATS client. The `nats` npm package (Node.js) is different.
   - What's unclear: Whether `nats.ws` works in Next.js client components without server-side import guards.
   - Recommendation: Import `nats.ws` only inside `useEffect()` (client-only hook). Add `if (typeof window === 'undefined') return` guard. Mark the hook file `"use client"` to prevent SSR execution.

3. **ECT virtual executor and `paper=True` SimAdapter**
   - What we know: D-14 says add `paper=True` to `SimAdapter` constructor; when True, skip ArcticDB writes.
   - What's unclear: Whether `paper=True` SimAdapter should also skip order logging to `helix.risk` logger, or just ArcticDB.
   - Recommendation: Skip both ArcticDB writes AND structured logging for paper trades. Log only to a lower-severity debug channel to avoid polluting production logs.

---

## Integration Points (Phase 3 → Phase 4)

| Phase 3 Asset | How Phase 4 Consumes It |
|---------------|-------------------------|
| `src/alpha/orchestrator.py` `RegimeOrchestrator.on_bar()` | Phase 4 hooks `risk_engine.size_signals()` call after signal generation (lines 219-243) — insert between signal collection and executor dispatch |
| `src/alpha/signal_types.py` `SignalRow` | `RiskEngine.size_signals()` receives `list[SignalRow]`, returns sized `list[SignalRow]` |
| `src/alpha/regime/online_filter.py` `OnlineRegimeFilter` | Provides GARCH σ for `compute_cvar_parametric()` — access via `filter._garch_sigma` or add a property |
| `src/data/arctic_store.py` `get_library("portfolio")` | `TelemetryPublisher.__init__()` reads initial equity curve at startup (D-13) |
| `src/data/pit_manager.py` `pit_read()` | Risk engine reads strategy return history for CVaR computation via `pit_read("signals", engine_symbol, as_of)` |
| `src/execution/sim_adapter.py` `SimAdapter` | Reused as virtual executor; add `paper: bool = False` constructor param; guard all `get_library` calls with `if not self._paper` |

---

## Sources

### Primary (HIGH confidence)

- `_docs/Phase_4_Risk_IPC_Dashboard.md` — Complete task breakdown with exact function signatures; all CVaR, CVXPY, Kelly, ECT, circuit breaker code verified against this document
- `.claude/skills/forex/cvar-risk-optimizer/SKILL.md` — CVaR math, CVXPY LP, Kelly, ECT, circuit breaker patterns; HIGH confidence
- `.claude/skills/forex/zeromq-nats-react-ui/SKILL.md` — NATS JetStream config, telemetry publisher, WebSocket bridge patterns; HIGH confidence (NOTE: Module Federation section superseded by D-01)
- `.planning/phases/04-risk-ipc-dashboard/04-CONTEXT.md` — Locked decisions D-01 through D-20; all implementation decisions
- `.planning/phases/04-risk-ipc-dashboard/04-UI-SPEC.md` — Complete visual and component contract; binding for dashboard implementation
- `src/execution/sim_adapter.py` — Read source directly; confirmed interface for `paper=True` extension
- `src/alpha/orchestrator.py` — Read source directly; confirmed hook point for `size_signals()` insertion
- CVXPY solver test — Executed in `.venv`; confirmed CLARABEL solves LP, ECOS NOT installed

### Secondary (MEDIUM confidence)

- npm registry: `npm view next version` → 16.2.1 (verified 2026-03-22)
- npm registry: `npm view tailwindcss version` → 4.2.2 (verified 2026-03-22)
- npm registry: `npm view shadcn version` → 4.1.0 (verified 2026-03-22)
- GitHub NATS releases API: v2.12.5 published 2026-03-09 (verified 2026-03-22)
- `pip show nats-py` in `.venv`: 2.14.0 confirmed installed

### Tertiary (LOW confidence)

- NATS native WebSocket behavior with `nats.ws` npm package in Next.js client components — not directly tested; based on NATS documentation patterns. Flag for validation in Wave 0.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions verified against live npm registry and installed `.venv`
- Architecture: HIGH — function signatures from spec; integration points from source code reads
- Pitfalls: HIGH — solver pitfall discovered by direct test execution; others from code structure analysis
- Dashboard patterns: MEDIUM — Next.js App Router patterns are well-established; `nats.ws` in Next.js is LOW for SSR edge cases

**Research date:** 2026-03-22
**Valid until:** 2026-04-22 (Next.js and NATS versions; Python deps are pinned)
