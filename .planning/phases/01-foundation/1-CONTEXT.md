# Phase 1: Foundation - Context

**Gathered:** 2026-03-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Establish two foundational layers that every subsequent phase depends on:
1. CI/CD quality pipeline — automated gates that reject bad code before merge
2. Execution abstraction layer — broker-agnostic interfaces so no downstream code ever references MT5 directly

This phase does NOT include live trading, real broker connectivity, or any alpha/data/risk logic. Those belong to Phases 2–5.

</domain>

<decisions>
## Implementation Decisions

### Python Environment
- **D-01:** Python 3.12 via deadsnakes PPA (`/usr/bin/python3.12`) — already installed on the Linux machine
- **D-02:** All project venvs use Python 3.12. System Python (3.10) stays untouched
- **D-03:** pyproject.toml is the single source of truth for all tool configuration (pytest, mypy, ruff, coverage)

### Repository Structure
- **D-04:** Full `src/` tree scaffolded in Phase 1 — all directories created with `__init__.py` stubs and `# TODO: Phase N` placeholders
- **D-05:** Directory layout: `src/execution/`, `src/data/`, `src/alpha/`, `src/risk/`, `src/ipc/` — matches phase boundaries exactly
- **D-06:** `src/execution/bridge/` created for ZeroMQ bridge code (Windows publisher + Linux consumer) — under execution layer ownership per skill architecture

### Pre-commit Gates (Local)
- **D-07:** Pre-commit runs ruff (lint + format) and mypy only — target under 10 seconds total
- **D-08:** pytest and coverage do NOT run in pre-commit — CI only
- **D-09:** AST/KCH hallucination detector does NOT run in pre-commit — CI only (needs full codebase scan)
- **D-10:** `--no-verify` is a documented escape hatch; commits using it are flagged visibly in git log

### CI/CD Pipeline (GitHub Actions)
- **D-11:** CI gate order: static analysis (ruff + mypy) → AST/KCH hallucination detection → PiT compliance check → unit tests → coverage enforcement
- **D-12:** Coverage enforced at 80% as a merge gate — CI fails below this threshold
- **D-13:** Linux-only CI runner (no Windows runner needed — MT5 tested via mocks and SimAdapter)
- **D-14:** GitHub Actions workflow file at `.github/workflows/ci.yml`

### AST/KCH Hallucination Detector
- **D-15:** Custom AST validator scans for phantom API calls (e.g. `mt5.nonexistent_function()`) against a whitelist of known-valid MT5 API methods
- **D-16:** Runs on full codebase in CI, not on partial staged files
- **D-17:** PiT compliance checker is a separate validator — scans alpha code for look-ahead bias patterns (accessing future data)

### Execution Abstraction Layer
- **D-18:** Three abstract base classes: `MarketDataProvider`, `OrderExecutor`, `PositionManager` — defined in `src/execution/abstract.py`
- **D-19:** `MT5Adapter` implements all three interfaces with async wrappers (`asyncio.to_thread()` around MT5's synchronous API)
- **D-20:** `SimAdapter` implements all three interfaces — no Windows dependency, safe for CI and backtesting
- **D-21:** Calling code throughout the project NEVER imports from `mt5_adapter.py` directly — always typed against the ABCs

### SimAdapter Fill Model
- **D-22:** Instant fill — orders are accepted immediately at the requested price
- **D-23:** Spread cost IS applied on every fill using `SpreadModel` — backtests are honest from day one
- **D-24:** No slippage simulation in Phase 1 — realistic slippage requires tick data (Phase 2)
- **D-25:** SimAdapter is stateful — maintains virtual account balance and open position ledger
- **D-26:** SimAdapter uses a fixed random seed — deterministic fills, reproducible CI runs
- **D-27:** Basic rejection logic included: insufficient margin, invalid lot size (matches real broker behaviour)

### SpreadModel & Lot Sizing
- **D-28:** `SpreadModel` tracks empirical spread distribution per symbol and suppresses signals where spread > 50% of expected profit
- **D-29:** `LotSizer` converts Kelly fraction to MT5 lots respecting `volume_min`, `volume_max`, `volume_step`

### Swap Rates
- **D-30:** `SwapRates` module extracts annualized carry for all configured symbols — used by Phase 3 carry engine

### ZeroMQ Bridge
- **D-31:** Bridge code is written and unit tested in Phase 1 (mocked sockets)
- **D-32:** Live end-to-end bridge testing (real MT5 → real tick stream) is DEFERRED to go-live — not a Phase 1 exit criterion
- **D-33:** Windows side: ZMQ PUB on port 5556 (ticks), 5557 (bars); PULL on 5558 (order requests); PUSH on 5559 (order results)
- **D-34:** Message serialization: MessagePack (faster than JSON, schema-flexible)
- **D-35:** Linux consumer reconnects automatically on disconnection and stops signal generation on stale data

### Infrastructure (Deferred)
- **D-36:** WireGuard VPN setup between Linux laptop and Windows MT5 node is DEFERRED to go-live
- **D-37:** MT5 node decision (Beelink mini PC vs Windows VM on laptop) is DEFERRED to go-live — does not affect Phase 1 code

### Claude's Discretion
- Exact pre-commit hook configuration syntax
- mypy ignore list for third-party stubs (MetaTrader5, hmmlearn, arch, vectorbt, arcticdb)
- Compression and temp file handling in bridge
- Progress reporting format in CI logs

</decisions>

<specifics>
## Specific Ideas

- MT5 is installed on this Linux machine via Wine (`~/.mt5/`) but the MT5 Python API cannot connect to it from Linux Python — Wine does not support the Windows named pipe IPC that the API requires. The ZeroMQ bridge exists to solve this.
- The machine running Linux is a Lenovo IdeaPad (Ubuntu 22.04, i7-8550U, 11GB RAM, 735GB free) — this is the alpha engine node
- Python 3.12.13 is already installed at `/usr/bin/python3.12`
- pyzmq 27.1.0, arcticdb 6.10.2, nats-py 2.14.0 are already installed system-wide
- pytest 9.0.2, mypy 1.19.1, ruff 0.15.7 are already installed

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Quality Infrastructure
- `_docs/Phase_1_Foundation.md` — Full task breakdown for Phase 1A (CI/CD pipeline) and Phase 1B (execution abstraction), includes pyproject.toml config specs and directory tree
- `_docs/claude-code-prompts-fxadapter.md` — Detailed implementation prompts for execution abstraction layer, MT5 adapter, ZeroMQ bridge

### Execution Abstraction
- `_docs/claude-code-prompts-fxadapter.md` §Prompt 1 — Abstract interfaces spec (MarketDataProvider, OrderExecutor, PositionManager), MT5Adapter requirements
- `_docs/claude-code-prompts-fxadapter.md` §Prompt 2 — ZeroMQ bridge spec (Windows publisher, Linux consumer, MessagePack schemas, port assignments)

### Requirements
- `.planning/REQUIREMENTS.md` §QUAL-01–QUAL-06 — Quality infrastructure requirements
- `.planning/REQUIREMENTS.md` §EXEC-01–EXEC-07 — Execution abstraction requirements
- `.planning/PROJECT.md` §Key Decisions — Architecture decisions already locked (ZMQ over REST, broker-agnostic ABCs)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `dashboard/` — React dashboard already partially scaffolded (shell + remotes structure exists). Phase 1 does not touch this.
- `pyzmq 27.1.0` — Already installed, no version conflict expected
- `arcticdb 6.10.2` — Already installed, Phase 1 can import it in stubs without reinstalling

### Established Patterns
- No Python source code exists yet — Phase 1 creates the project from scratch
- `dashboard/` uses Node v24.13.0 via nvm — Python tooling should not interfere

### Integration Points
- `src/execution/abstract.py` → imported by every subsequent phase (data, alpha, risk, ipc)
- `src/bridge/` → connects to MT5 node at go-live; during Phase 1, tested via mocked ZMQ sockets

</code_context>

<deferred>
## Deferred Ideas

- **WireGuard VPN setup** — deferred to go-live; bridge code written in Phase 1 but not live-tested
- **MT5 node decision (Beelink vs VM)** — deferred to go-live; doesn't affect Phase 1 code
- **Live end-to-end bridge testing** — deferred to go-live; Phase 1 exit criterion is unit tests passing with mocked sockets
- **Slippage simulation in SimAdapter** — Phase 2, when ArcticDB tick data is available
- **Windows CI runner** — not needed; MT5 always mocked in CI via SimAdapter
- **Stage B infrastructure** (CMEAdapter, iLink 3.0) — Phase 5 only

</deferred>

---

*Phase: 01-foundation*
*Context gathered: 2026-03-21*
