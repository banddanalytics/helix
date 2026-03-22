# Phase 3: Alpha Engines - Context

**Gathered:** 2026-03-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Build all four alpha generation engines: HMM-GARCH regime detector, Johansen cointegration pairs engine, swap-based carry provider, and 27-feature ML momentum ensemble. The regime detector gates which strategies are active. Cointegration, carry, and ML momentum can be developed in parallel after the regime detector is complete. Every engine reads data exclusively through Phase 2's `pit_read()` interface. Phase 4 (risk engine) consumes the signals this phase produces.

</domain>

<decisions>
## Implementation Decisions

### Signal Output Contract
- **D-01:** Common signal schema: `timestamp` (index), `symbol`, `engine`, `direction` (int8: +1/0/-1), `strength` (float32 [0,1]), `regime` (int8 at signal time), plus nullable engine-specific columns: `z_score` (cointegration), `ml_prob` (ML), `carry_rank` (carry).
- **D-02:** Each engine writes to its own ArcticDB `signals` library symbol using pattern `{engine}_{symbol}` (e.g. `cointegration_EURUSD_NZDUSD`, `ml_EURUSD`). Engines are isolated — a failing engine never blocks others.
- **D-03:** Regime state is stored separately as `regime_{symbol}` in the `signals` library — it is state, not a trading signal. Risk engine reads it independently to apply Kelly multipliers.

### Regime Orchestrator Architecture
- **D-04:** Central `RegimeOrchestrator` owns all strategy activation. On each bar it reads regime state and calls `engine.generate_signals()` only for active engines — inactive engines are never called.
- **D-05:** Activation map (locked per ALPH-09):
  - `TRENDING` → `[ml_engine, carry_engine]`
  - `MEAN_REVERTING` → `[cointegration_engine]`
  - `CRISIS` → `[]` (reduce-only, no new signals generated)
- **D-06:** The orchestrator owns the 20-bar hysteresis dwell logic for regime transitions. Individual engines have no awareness of hysteresis.

### ML Cross-Asset Data Sourcing
- **D-07:** `CrossAssetCache` pre-loads the last 252 bars for all 6 required symbols at startup via `pit_read()`. Updates incrementally on each new bar (append new, drop oldest — O(1) per bar).
- **D-08:** Required symbols: `EURUSD, GBPUSD, AUDUSD, NZDUSD, USDJPY, USDCHF` — identical to the pairs already used by cointegration and carry engines, no extra data cost.
- **D-09:** Cache lives on the orchestrator and is injected into `FeatureBuilder`. During backtests it is pre-populated from the ArcticDB snapshot and replayed bar-by-bar.

### Model Hot-Swap During Recalibration
- **D-10:** New weekly refit must pass two gates before swap:
  1. Stationarity: `α + β < 1` for all states (hard reject if violated)
  2. State agreement: new model must agree with old model on ≥90% of last 100 bars (hard reject if violated)
- **D-11:** Parameter drift >50% from prior week triggers a WARNING log but does NOT block the swap — the new fit used more recent data and should be preferred.
- **D-12:** Swap happens at next bar boundary (atomic reference swap). The orchestrator picks up `self._pending` model on the next `on_bar()` call — no mid-bar model change.

### Claude's Discretion
- Internal Numba cache warming strategy for the 27-feature pipeline
- Exact ArcticDB append pattern for signal writes (batch vs per-bar)
- Config file format for regime calibration schedule (`config/regime_calibration.yaml`)
- Test fixture strategy for synthetic regime-switching data generation

</decisions>

<specifics>
## Specific Ideas

- No specific UX or interaction requirements — this phase is pure computation
- The spec in `_docs/Phase_3_Alpha_Engines.md` is unusually detailed: exact HMM params, GARCH config, all 27 feature formulas, walk-forward splits, and ML hyperparameters are all locked there

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Full Phase 3 Spec
- `_docs/Phase_3_Alpha_Engines.md` — Complete task breakdown for all four engines: HMM params, GARCH config, regime thresholds, hysteresis rules, recalibration schedule, Johansen test code, z-score entry/exit/hard-stop thresholds, hedge ratio window, target Forex pairs, all 27 feature formulas with PiT notes, walk-forward config, XGBoost/RF hyperparameters, ensemble weighting, SHAP requirements, signal thresholds, and completion gates

### Phase 2 Data Layer (what Phase 3 reads through)
- `src/data/pit_manager.py` — `pit_read()` and `validate_pit_compliance()` — all data access must go through this
- `src/data/arctic_store.py` — ArcticDB store singleton, `signals` library write patterns
- `src/backtest/engine.py` — `BacktestRunner.run()` API that alpha engines call for strategy validation

### Phase 1 Interfaces (what Phase 3 codes against)
- `src/execution/abstract.py` — `Tick`, `Bar`, `MarketDataProvider` ABCs — engines receive `Bar` objects
- `src/execution/spread_model.py` — `SpreadModel.median` used by carry engine spread filter and ML cost-adjusted Sharpe
- `src/execution/swap_rates.py` — `compute_annualized_carry()` consumed by `ForexCarryProvider`

### Project Constraints
- `CLAUDE.md` — Quality gates: mypy strict, ruff, 80%+ coverage, PiT compliance on all data access code

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/data/pit_manager.py` `pit_read()`: all rolling window computations (hedge ratio, feature lookbacks) must use this — not raw ArcticDB reads
- `src/execution/swap_rates.py` `compute_annualized_carry()`: ForexCarryProvider wraps this directly, no reimplementation
- `src/backtest/numba_kernels.py` + `src/backtest/accumulators.py`: established `@njit(cache=True)` pattern — ML feature functions follow the same pattern
- `src/backtest/warmup.py`: Numba warmup service already exists — Phase 3 must register its `@njit` feature functions here

### Established Patterns
- All Phase 1/2 code was TDD (red/green) — Phase 3 follows same pattern
- `asyncio.to_thread` for ArcticDB I/O (established in Phase 2 SwapWriter)
- Module-level singleton store pattern (`arctic_store.py`) — signal writes use same pattern
- Structured JSON logging to `helix.data` logger — alpha engines log to `helix.alpha`

### Integration Points
- `pit_read("forex_bars", symbol, as_of)` → bar data into all 4 engines
- `RegimeOrchestrator.on_bar()` → `signals` library → Phase 4 risk engine reads
- `BacktestRunner.run(strategy_fn, symbol, date_range)` → `portfolio` library → Phase 4 dashboard PnL curve
- `CrossAssetCache` → `FeatureBuilder` → 27 features → XGBoost/RF ensemble

</code_context>

<deferred>
## Deferred Ideas

- MBO order flow features (OFI, VPIN, depth imbalance) — Stage B only, no genuine order book in Stage A (STAGEB-03)
- `ml_mbo_orderflow` module — stub exists at `src/alpha/ml_mbo_orderflow/`, activated in Stage B
- Automated pair discovery (test all XXXYYY combinations) — v2 requirement
- Telegram/SMS alerting for regime switches — Phase 4 NATS layer doesn't exist yet

</deferred>

---

*Phase: 03-alpha-engines*
*Context gathered: 2026-03-22*
