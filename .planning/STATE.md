---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: unknown
stopped_at: Completed 03-06-PLAN.md — 5-tier 27-feature Numba pipeline for ML price momentum
last_updated: "2026-03-22T10:48:55.228Z"
progress:
  total_phases: 5
  completed_phases: 2
  total_plans: 21
  completed_plans: 19
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-20)

**Core value:** A broker-agnostic trading system where every signal passes through rigorous quality gates (AST validation, PiT compliance, 80%+ test coverage) before reaching live markets
**Current focus:** Phase 03 — alpha-engines

## Current Position

Phase: 03 (alpha-engines) — EXECUTING
Plan: 7 of 8

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: -
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**

- Last 5 plans: none yet
- Trend: -

*Updated after each plan completion*
| Phase 01-foundation P01 | 23 | 2 tasks | 32 files |
| Phase 01-foundation P04 | 30 | 2 tasks | 3 files |
| Phase 01-foundation P02 | 8 | 2 tasks | 16 files |
| Phase 01 P02 | 14 | 2 tasks | 18 files |
| Phase 01-foundation P03 | 20 | 2 tasks | 13 files |
| Phase 01-foundation P06 | 3 | 2 tasks | 6 files |
| Phase 02-data-engineering P02 | 3 | 2 tasks | 6 files |
| Phase 02-data-engineering P01 | 10 | 2 tasks | 10 files |
| Phase 02-data-engineering P04 | 110s | 2 tasks | 3 files |
| Phase 02-data-engineering P03 | 2 | 1 tasks | 2 files |
| Phase 02-data-engineering P05 | 3 | 2 tasks | 3 files |
| Phase 02-data-engineering P06 | 200 | 2 tasks | 9 files |
| Phase 03-alpha-engines P01 | 193 | 2 tasks | 11 files |
| Phase 03-alpha-engines P02 | 273 | 2 tasks | 6 files |
| Phase 03-alpha-engines P03 | 182 | 2 tasks | 5 files |
| Phase 03-alpha-engines P04 | 233 | 2 tasks | 6 files |
| Phase 03-alpha-engines P05 | 136 | 2 tasks | 5 files |
| Phase 03-alpha-engines P06 | 533 | 2 tasks | 10 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- All phases: Broker-agnostic abstraction layer — every component codes against ABCs, never MT5 directly
- All phases: ZeroMQ bridge over REST/gRPC — low latency, MessagePack, PUB/SUB topology match
- Phase 2: ArcticDB over InfluxDB/TimescaleDB — native Python, columnar, version snapshots for PiT
- Phase 3: Numba JIT — 27 features × 1M bars < 5s requirement
- Phase 4: NATS JetStream — single-node Stage A, hub+leaf scales to Stage B without code changes
- Phase 4: Module Federation dashboard — one crashing remote does not break others
- [Phase 01-foundation]: pyproject.toml is the single source of truth for all tool config (D-03) — no setup.cfg or tox.ini
- [Phase 01-foundation]: Python 3.12 venv at .venv/ using /usr/bin/python3.12 — system Python 3.10 stays untouched (D-01, D-02)
- [Phase 01-foundation]: Coverage gate at 80% branch coverage enforced in pytest addopts and tool.coverage.report (QUAL-04)
- [Phase 01-foundation]: Three ABCs (MarketDataProvider, OrderExecutor, PositionManager) define broker-agnostic execution contract — all downstream code types against these, never MT5 directly (D-18, D-21)
- [Phase 01-foundation]: Position dataclass is mutable (not frozen) — current_price and unrealized_pnl must update continuously during live trading
- [Phase 01-foundation]: Stubs use flat dict {lib -> {func -> set_of_kwargs}} — simple to load and compare against extracted calls
- [Phase 01-foundation]: arcticdb stub intentionally excludes upsert as the canonical phantom-function test case (QUAL-01)
- [Phase 01-foundation]: Pre-commit uses local mypy with system language to access project venv deps (avoids duplicating additional_dependencies)
- [Phase 01-foundation]: pytest and validators excluded from pre-commit per D-07/D-08/D-09 — CI only gates
- [Phase 01-foundation]: SpreadModel wiring into SimAdapter deferred to Phase 2 — Phase 1 uses fixed spread_pips float; Phase 2 replaces with SpreadModel.median after ArcticDB tick history available
- [Phase 01-foundation]: LotSizer floor-rounds to volume_step via math.floor to prevent position over-sizing
- [Phase 02-data-engineering]: Module-level singleton (not lru_cache) for ArcticDB store — reset_store() allows test injection of tmp paths
- [Phase 02-data-engineering]: LMDB backend fixed at ./arctic_data, no env-var switching per D-01/D-02
- [Phase 02-data-engineering]: Schema constants are plain dict[str, str] — documentation only, ArcticDB infers schema from first DataFrame write
- [Phase 02-01]: numba_stubs.py uses same flat dict {lib -> {func -> set_of_kwargs}} format as arcticdb_stubs.py — consistent pattern across all KCH stubs
- [Phase 02-data-engineering]: aggregate_bars() uses pandas mid-price resample().ohlc() — single pass, vectorized, no custom loops
- [Phase 02-data-engineering]: SwapWriter uses asyncio.to_thread for ArcticDB I/O — keeps event loop non-blocking without APScheduler dependency
- [Phase 02-data-engineering]: TickWriter caches single ArcticDB store instance per object to avoid LMDB multi-open warning
- [Phase 02-data-engineering]: Duplicate detection requires both index.duplicated AND df.duplicated(subset=bid/ask) — timestamp alone is insufficient since legitimate ticks can share a timestamp
- [Phase 02-data-engineering]: pit_read uses ArcticDB native date_range=(None, as_of_timestamp) for PiT cutoff per D-11
- [Phase 02-data-engineering]: validate_pit_compliance uses IC analysis with 1.5x threshold — contemp_ic > forward_ic * 1.5 signals look-ahead bias per D-13
- [Phase 02-data-engineering]: spread_cost is a per-bar array (not scalar) enabling different values per bar — Stage A passes SpreadModel.median broadcast, Stage B passes zeros array
- [Phase 02-data-engineering]: numba_kernels.py isolated from accumulators.py to prevent Numba cache invalidation when non-JIT code changes
- [Phase 02-data-engineering]: BacktestRunner uses pit_read snapshot parameter for deterministic reproducibility across runs
- [Phase 03-alpha-engines]: Signal schema uses plain Python int/float types in SignalRow fields for broader compatibility; numpy types annotated but not enforced in dataclass
- [Phase 03-alpha-engines]: Test stubs use pytest.mark.skip (not xfail) — missing implementations are immediately visible rather than silently passing as expected failures
- [Phase 03-alpha-engines]: Gaussian fallback for states with fewer than 100 GARCH samples uses stationary synthetic params (omega=var*0.05, alpha=0.05, beta=0.90)
- [Phase 03-alpha-engines]: OnlineRegimeFilter uses log-space fallback for numerical underflow when forward variable underflows to zero
- [Phase 03-alpha-engines]: RecalibrationService holds reference to active detector and swaps atomically via apply_pending() — pending model never active until explicitly applied
- [Phase 03-alpha-engines]: Dirichlet smoothing applied post-fit by adding concentration scalar then row-normalizing — no zero transition probabilities without modifying HMMGARCHRegimeDetector.fit()
- [Phase 03-alpha-engines]: Johansen eigenvector hedge ratio uses -evec[0,0]/evec[1,0]: plan spec had [1,0]/[0,0] which produced ~1.25 instead of ~0.8 — corrected via empirical verification
- [Phase 03-alpha-engines]: test_cointegration() imported as johansen_test alias in test file to prevent pytest collecting the re-exported function as a test item
- [Phase 03-alpha-engines]: ForexCarryProvider uses ordinal ranking / n to produce (0, 1] percentile ranks — no scipy dependency
- [Phase 03-alpha-engines]: Spread filter applied after quartile assignment: only active signals (signal != 0) checked against spread_data
- [Phase 03-alpha-engines]: FuturesCarryProvider raises NotImplementedError on both get_carry_signals and get_carry_ranks — full Stage B gate
- [Phase 03-alpha-engines]: vol_zscore replaces vol_63bar — z-score of vol_22 vs 63-bar baseline avoids corr>0.95 with vol_22bar
- [Phase 03-alpha-engines]: range_expansion uses 5-bar/50-bar ratio (not 1-bar/20-bar) to differentiate from session.relative_bar_size
- [Phase 03-alpha-engines]: FeatureBuilder outer .shift(1) is belt-and-suspenders PiT layer on top of Numba function PiT alignment

### Pending Todos

None yet.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260322-g0v | Fix Phase 02 verification pending items | 2026-03-22 | c18399f | [260322-g0v](./quick/260322-g0v-fix-phase-02-verification-pending-items/) |
| 260322-hyg | Fix Phase 3 pre-execution blockers: shap install, signal_types, test scaffold | 2026-03-22 | f0d63d6 | [260322-hyg](./quick/260322-hyg-fix-phase-3-pre-execution-blockers/) |

### Blockers/Concerns

- MT5 Python API is Windows-only; alpha engine code must run on Linux via ZMQ bridge — affects Phase 1 ZMQ setup and all CI testing strategies
- Stage B trigger requires $50K+ equity AND 6+ months positive expectancy AND iLink 3.0 certification — Phase 5 Stage B work is prep only, not activation

## Session Continuity

Last session: 2026-03-22T10:48:55.224Z
Stopped at: Completed 03-06-PLAN.md — 5-tier 27-feature Numba pipeline for ML price momentum
Resume file: None
