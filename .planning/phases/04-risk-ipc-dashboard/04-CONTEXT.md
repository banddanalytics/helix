# Phase 4: Risk, IPC & Dashboard - Context

**Gathered:** 2026-03-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the risk engine (CVaR computation, CVXPY portfolio optimization, Kelly sizing, ECT strategy sandboxing, and circuit breakers), the IPC layer (NATS JetStream telemetry publisher + WebSocket bridge), and the React dashboard (Next.js App Router, deployable to Vercel). Risk engine governs all position sizing; telemetry flows from alpha engines through NATS to the browser; the dashboard displays real-time system state.

</domain>

<decisions>
## Implementation Decisions

### Dashboard Stack (replaces Module Federation from original spec)
- **D-01:** Next.js App Router replaces Webpack 5 Module Federation. IPC-04 requirement updated: "6 remote modules via Module Federation" → "6 route-based views with error boundaries in a Next.js app."
- **D-02:** Directory: `dashboard/` (existing repo location). Replace the existing Webpack scaffold with a Next.js app rooted there. The workspace `package.json` at `dashboard/package.json` becomes the Next.js root.
- **D-03:** Styling: Tailwind CSS + shadcn/ui + 21st.dev components. Dark trading terminal aesthetic throughout. No light mode.
- **D-04:** Charts: Recharts (already in shell package.json). Use for all time-series and gauge visualizations.
- **D-05:** 7 routes: `/` (overview/summary), `/regime`, `/cointegration`, `/momentum`, `/carry`, `/risk`, `/orders`. Each route has its own `<Suspense>` + `<ErrorBoundary>` — a loading or error in one section does not crash the app or other sections.
- **D-06:** Vercel deployment: `NEXT_PUBLIC_NATS_WS_URL` env var points to the Linux server's NATS WebSocket bridge (`wss://server:9222`). The Next.js app is statically deployable to Vercel; live data comes from the server at runtime.
- **D-07:** `tradingStage` context: a React context (not prop drilling) provides `'forex' | 'futures'` to all components. Controls unit labeling (lots/pips/swap rate vs contracts/ticks/term structure carry).

### Risk Engine Integration (Orchestrator → Risk → Executor)
- **D-08:** `RegimeOrchestrator.on_bar()` generates raw signals → calls `risk_engine.size_signals(signals, regime, equity)` → returns sized, filtered signals → executor receives only pre-approved orders. The risk engine does NOT call back into the orchestrator (no circular imports).
- **D-09:** Risk engine lives at `src/risk/engine.py`. Exposes a single `RiskEngine` class with: `size_signals()` (Kelly + CVaR gate), `on_bar_end()` (circuit breaker drawdown update), `sandbox_strategy()` / `restore_strategy()` (ECT delegation).
- **D-10:** `size_signals()` applies checks in order: (1) circuit breaker state → reject if L3, scale if L1; (2) ECT sandbox check → route to virtual executor if sandboxed; (3) CVaR budget gate → reject if adding signal exceeds 5% CVaR budget; (4) Kelly fraction → scale position size.

### Telemetry Data Sourcing
- **D-11:** `TelemetryState` is a dataclass holding current snapshot of all publishable fields: `equity`, `unrealized_pnl`, `realized_pnl`, `positions` (dict), `cvar` (per-method), `drawdown_pct`, `circuit_breaker_level`, `regime_state`, `regime_probs`, `sandboxed_strategies`.
- **D-12:** The orchestrator and risk engine push updates into a shared `TelemetryState` instance (passed by reference). `TelemetryPublisher` reads from it on its own asyncio timer — no ArcticDB reads on the hot path.
- **D-13:** Seeding at startup: `TelemetryPublisher.__init__()` reads last known state from ArcticDB `portfolio` library for equity/PnL initialization, then live updates are in-process only.

### ECT Virtual Executor
- **D-14:** Reuse `SimAdapter` from Phase 1 (`src/execution/sim_adapter.py`) as the virtual executor. `EquityCurveTrader` injects a second `SimAdapter(paper=True)` instance when sandboxing a strategy. The `paper=True` flag (to be added to SimAdapter) disables ArcticDB writes and order logging — accumulates PnL in-memory only.
- **D-15:** ECT monitors equity curve per strategy using the in-process `TelemetryState` (not ArcticDB reads). Sandbox trigger and recovery trigger both operate on in-memory equity accumulator updated each bar.

### CVaR + CVXPY (all locked from spec, no changes)
- **D-16:** Three CVaR methods as exact code in spec: historical simulation, parametric (GARCH σ from Phase 3 regime detector), Cornish-Fisher. Plus spread-adjusted variant using p95 spread during worst-10% return periods.
- **D-17:** CVXPY LP formulation: Rockafellar-Uryasev. ECOS solver primary, SCS fallback. Budget constraint 5%, per-strategy weight cap 25%.
- **D-18:** Kelly multipliers: Trending 0.5×, Mean-Reverting 0.4×, Crisis 0.1×. Max fraction 15%. Cap enforced after regime adjustment.

### Circuit Breakers (locked from RISK-06/07/08)
- **D-19:** L1 at 2% daily drawdown → reduce all to 50% Kelly (state persists until EOD reset). L2 at 5% → flatten all positions, pause 1 hour. L3 at 10% → flatten all, disable strategies, require manual restart. L3 is idempotent.
- **D-20:** Daily drawdown resets at midnight UTC (new trading day). L1 state automatically clears on reset.

### Claude's Discretion
- NATS server config file format and deployment method (Docker vs systemd)
- Exact asyncio timer implementation for telemetry publisher intervals
- Next.js App Router file structure within `dashboard/` (page.tsx layout, loading.tsx, error.tsx per route)
- shadcn/ui component selection for gauges, tables, and status indicators
- 21st.dev component choices for any specialized trading visualizations
- Test fixture approach for circuit breaker integration tests

</decisions>

<specifics>
## Specific Ideas

- Dashboard should feel like a dark trading terminal — think Bloomberg/TradingView aesthetic not a generic SaaS dashboard
- Vercel deployment means the user can view the dashboard from any browser without being on the same network as the trading server — the NATS WebSocket URL is the only runtime dependency on the server
- The 21st.dev registry should be used for any components where a purpose-built trading/data visualization component exists (gauges, sparklines, data tables with sorting)

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Full Phase 4 Spec (primary reference)
- `_docs/Phase_4_Risk_IPC_Dashboard.md` — Complete task breakdown: exact CVaR function signatures, CVXPY LP formulation, Kelly formula, ECT sandbox/restore protocol, circuit breaker thresholds, NATS stream config, telemetry subjects + intervals, all output file paths (note: `ui/` paths in spec → use `dashboard/` instead per D-02)

### Phase 4 Skills (must read before implementing each subsystem)
- `.claude/skills/forex/cvar-risk-optimizer/SKILL.md` — CVaR math, CVXPY optimizer, Kelly criterion, ECT sandbox/restore, circuit breaker implementation patterns
- `.claude/skills/forex/zeromq-nats-react-ui/SKILL.md` — NATS JetStream config, telemetry publisher patterns, WebSocket bridge, React dashboard patterns (use Next.js routes instead of Module Federation per D-01)

### Phase 3 Integration Points (what Phase 4 consumes)
- `src/alpha/orchestrator.py` — `RegimeOrchestrator.on_bar()` — Phase 4 risk engine hooks in here
- `src/alpha/signal_types.py` — `SignalRow` schema — risk engine receives and returns these
- `src/data/arctic_store.py` — `portfolio` library — TelemetryPublisher reads initial equity from here

### Phase 1 Reuse
- `src/execution/sim_adapter.py` — `SimAdapter` — ECT virtual executor (add `paper=True` flag per D-14)
- `src/execution/abstract.py` — `OrderExecutor` ABC — `RiskEngine` and `VirtualExecutor` must implement or wrap this

### Existing Dashboard Scaffold
- `dashboard/shell/package.json` — Existing deps (react 18, recharts, @tanstack/react-query) — Next.js replaces webpack config, keep these deps
- `dashboard/remotes/` — 6 remote dirs already exist (carry-monitor, coint-dashboard, ml-momentum, order-blotter, regime-monitor, risk-dashboard) — replace with Next.js route pages

### Project Constraints
- `CLAUDE.md` — Quality gates: mypy strict, ruff, 80%+ coverage, PiT compliance (risk engine reads strategy returns — must use pit_read)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/execution/sim_adapter.py` `SimAdapter`: add `paper: bool = False` constructor param; when True, skip ArcticDB writes, accumulate PnL in-memory — reuse as ECT virtual executor (D-14)
- `src/alpha/orchestrator.py` `RegimeOrchestrator.on_bar()`: risk engine hooks in here after signal generation, before execution delegation
- `src/data/arctic_store.py` `get_library("portfolio")`: TelemetryPublisher reads initial equity curve at startup (D-13)
- `src/data/pit_manager.py` `pit_read()`: risk engine reads strategy return history for CVaR computation — must use this, not raw ArcticDB reads

### Established Patterns
- `asyncio.to_thread` for ArcticDB I/O (Phase 2 pattern) — TelemetryPublisher startup read uses same pattern
- Module-level singleton store (`arctic_store.py`) — risk engine uses same pattern for `get_library("portfolio")`
- Structured JSON logging to `helix.*` logger — risk engine logs to `helix.risk`, IPC to `helix.ipc`
- All Phase 1/2/3 code is TDD — Phase 4 follows: write test first, then implementation

### Integration Points
- `RegimeOrchestrator.on_bar()` → `RiskEngine.size_signals()` → `OrderExecutor.submit_order()` (new call chain)
- `RiskEngine` → `TelemetryState` (push updates on every sizing decision)
- `TelemetryPublisher` → NATS JetStream → WebSocket bridge → Next.js `useNatsSubscription` hook → React state

</code_context>

<deferred>
## Deferred Ideas

- NATS hub+leaf cluster for Stage B (cross-continent) — Stage B only, current phase is single-node
- PREEMPT_RT kernel + OpenOnload for Stage B latency — out of scope for Phase 4
- Telegram/SMS alerting (PROD-06 alerting system) — Phase 5
- Automated pair discovery — v2 requirement
- Light mode for dashboard — out of scope, dark terminal only for now

</deferred>

---

*Phase: 04-risk-ipc-dashboard*
*Context gathered: 2026-03-22*
