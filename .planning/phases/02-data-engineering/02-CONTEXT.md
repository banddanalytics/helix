# Phase 2: Data Engineering - Context

**Gathered:** 2026-03-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the data layer that all alpha engines consume: ArcticDB dual-schema storage (Forex + MBO stub), Forex tick ingestion with bar aggregation and session tagging, Point-in-Time data manager preventing all 5 look-ahead bias vectors, daily EOD snapshot scheduling, and a full VectorBT Pro + Numba single-pass backtesting stack. Every alpha engine in Phase 3 reads data exclusively through this layer.

</domain>

<decisions>
## Implementation Decisions

### ArcticDB Storage Backend
- **D-01:** Production backend is LMDB on local disk — NOT S3. `adb.Arctic("lmdb://./arctic_data")` for both dev and production. S3 migration deferred to later milestone if needed.
- **D-02:** Dev/CI path: `./arctic_data` (relative to project root, gitignored). Same path in dev, staging, and production — no env var switching required in Phase 2.
- **D-03:** 6 libraries with fixed schemas per `_docs/Phase_2_Data_Engineering.md`: `forex_ticks`, `forex_bars`, `swap_rates`, `mbo_ticks` (stub, empty in Stage A), `signals`, `portfolio`.

### Tick Writer & Bar Aggregation
- **D-04:** Batch flush: 10,000 ticks OR 1 second, whichever comes first. Uses `lib.append()` never `lib.write()`.
- **D-05:** Bar timeframes: 1m, 5m, 15m, 1h, 4h, 1d — all 6 computed from tick stream.
- **D-06:** Session tags: `0`=Asian (00:00-08:00 UTC), `1`=London (08:00-13:00 UTC), `2`=Overlap (13:00-16:00 UTC), `3`=New York (16:00-21:00 UTC).
- **D-07:** Bad ticks are stored with a `quality: int8` column — NOT discarded. Values: `0`=clean, `1`=rollover_spike, `2`=weekend_gap, `3`=duplicate. Consumers filter by quality column.
- **D-08:** Data quality events reported via Python logging to `helix.data` logger (structured JSON). NATS alerting deferred to Phase 4.

### Snapshot Scheduling
- **D-09:** Daily EOD automated snapshots at 22:00 UTC (market close). Named `eod_YYYYMMDD`.
- **D-10:** On startup, scheduler checks last snapshot date. If gap exists, backfills retroactive snapshots for missed days using data already in ArcticDB (e.g., server was down 2 days → creates 2 missed snapshots on next start).

### PiT Data Manager
- **D-11:** `pit_read(library, symbol, as_of_timestamp)` uses ArcticDB native date range filtering — no data beyond `as_of_timestamp` ever returned.
- **D-12:** Five look-ahead bias vectors prevented per `_docs/Phase_2_Data_Engineering.md` § Task 2.3.
- **D-13:** `validate_pit_compliance(signal_df, price_df)` uses IC analysis: if `abs(contemp_ic) > abs(forward_ic) * 1.5` → raises `LookAheadBiasError`.

### BacktestRunner & Numba
- **D-14:** Full BacktestRunner delivered in Phase 2 — not deferred. Alpha engines in Phase 3 call `BacktestRunner.run(strategy_fn, symbol, date_range)` directly.
- **D-15:** BacktestRunner persists results to ArcticDB `portfolio` library, tagged by strategy name + date range + snapshot name. Every run creates an audit trail entry.
- **D-16:** Single-pass Numba accumulator signature (from `_docs`): `single_pass_backtest(close, signal, risk_per_trade, atr, spread_cost)` — `spread_cost` parameter is the dual-stage design element (Stage A: variable spread from SpreadModel, Stage B: zeros).
- **D-17:** Numba warmup service compiles all `@njit` functions at startup. `NUMBA_CACHE_DIR` set to `./numba_cache` for persistent cache across restarts.
- **D-18:** VectorBT Pro settings: `chunking.n_chunks='auto'`, `caching.register_lazily=True`, `caching.use_disk=True`, `caching.disk_path='/tmp/vbt_cache'`.

### Claude's Discretion
- Exact deduplication algorithm for duplicate tick detection (timestamp + bid/ask equality check is sufficient)
- Swap writer scheduler implementation (APScheduler or asyncio-based)
- Admin CLI framework (argparse or click)
- Numba cache directory creation and cleanup strategy

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 2 Full Spec
- `_docs/Phase_2_Data_Engineering.md` — Complete task breakdown, all schemas, flush thresholds, session tag values, PiT bias table, VectorBT config, Numba accumulator signature, validation criteria

### Phase 1 Interfaces (what Phase 2 integrates with)
- `src/execution/abstract.py` — Tick, Bar, OrderRequest, OrderResult dataclasses; MarketDataProvider/OrderExecutor/PositionManager ABCs that Phase 2 data writers consume
- `src/execution/sim_adapter.py` — SimAdapter.set_price() and submit_order() used to generate synthetic tick streams for data layer tests
- `src/execution/spread_model.py` — SpreadModel.median property used as `spread_cost` input to Numba accumulator
- `src/quality/pit_validator.py` — PiTValidator AST checker; Phase 2 PiT manager must pass its own validation

### ArcticDB Skill Reference
- `.claude/skills/forex/arcticdb-vectorbt-engine/SKILL.md` — Write path patterns, PiT structuring, VectorBT Pro optimization, Numba JIT compilation strategy (READ THIS BEFORE PLANNING)

### Project Constraints
- `CLAUDE.md` — Quality gates: mypy strict, ruff, 80%+ coverage, PiT compliance on all data access code

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/execution/abstract.py` Tick + Bar dataclasses: Phase 2 tick writer accepts these directly — no conversion needed
- `src/quality/pit_validator.py` PiTValidator: run against Phase 2 data access code to catch look-ahead patterns during development
- `src/execution/sim_adapter.py` SimAdapter: inject synthetic ticks into forex_writer for testing without MT5

### Established Patterns
- TDD red/green: all Phase 1 code was TDD — Phase 2 follows same pattern (write failing tests first)
- `asyncio.to_thread` for blocking I/O: ArcticDB writes should follow this pattern to avoid blocking async event loop
- `--no-verify` commits during parallel execution: already established in Phase 1 CI config

### Integration Points
- Bar aggregator output → `src/data/arctic_store.py` forex_bars library → Phase 3 alpha engines read via `pit_read()`
- BacktestRunner results → `portfolio` library → Phase 4 dashboard reads PnL curve
- SpreadModel (Phase 1) → `spread_cost` array fed into Numba accumulator (Phase 2)

</code_context>

<deferred>
## Deferred Ideas

- S3 / S3-compatible production backend — deferred to later milestone, LMDB sufficient for Stage A
- NATS alerting for data quality events — Phase 4 (IPC layer doesn't exist yet)
- Real-time data quality dashboard — Phase 4 dashboard
- Automated pair discovery / tick data for all XXXYYY combinations — v2 requirement

</deferred>

---

*Phase: 02-data-engineering*
*Context gathered: 2026-03-22*
