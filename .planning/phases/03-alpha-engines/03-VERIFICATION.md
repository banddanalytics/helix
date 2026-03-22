---
phase: 03-alpha-engines
verified: 2026-03-22T15:36:19Z
status: gaps_found
score: 8/10 must-haves verified
re_verification: null
gaps:
  - truth: "Full phase test coverage >= 80% (pytest tests/alpha/ --cov=src/alpha --cov-fail-under=80)"
    status: failed
    reason: >
      Total measurable coverage is 64% (excluding slow test). The 80% gate
      fails. Primary cause: Numba-compiled functions in momentum.py (18%),
      volatility.py (10%), session.py (16%), tick_volume.py (13%) are not
      traced by coverage.py. Additionally, orchestrator.py (61%),
      walk_forward.py (46%), and online_filter.py (64%) lack sufficient
      Python-traceable test paths. The phase itself documented this as a
      known issue in deferred-items.md but did not resolve it.
    artifacts:
      - path: "src/alpha/ml_price_momentum/features/momentum.py"
        issue: "18% coverage — Numba JIT body not traced by coverage.py"
      - path: "src/alpha/ml_price_momentum/features/volatility.py"
        issue: "10% coverage — Numba JIT body not traced"
      - path: "src/alpha/ml_price_momentum/features/session.py"
        issue: "16% coverage — Numba JIT body not traced"
      - path: "src/alpha/ml_price_momentum/features/tick_volume.py"
        issue: "13% coverage — Numba JIT body not traced"
      - path: "src/alpha/ml_price_momentum/models/walk_forward.py"
        issue: "46% coverage — WalkForwardEngine.run() inner loop not fully covered"
      - path: "src/alpha/orchestrator.py"
        issue: "61% coverage — async persist methods and full hysteresis path not covered"
      - path: "src/alpha/regime/online_filter.py"
        issue: "64% coverage — update() paths not fully covered"
    missing:
      - "Add --no-cov-on-fail or configure [tool.coverage.run] omit for Numba source files OR add pragma: no cover comments to @njit decorated functions"
      - "Add direct unit tests for OnlineRegimeFilter.update() (without going through HMM fit)"
      - "Add tests exercising WalkForwardEngine.run() with a small dataset directly"
      - "Add tests for orchestrator async persist paths (can mock ArcticDB lib)"
  - truth: "1M bar feature computation completes in < 5 seconds (test_feature_computation_performance)"
    status: failed
    reason: >
      test_feature_computation_performance fails: 8.81s measured vs 5s limit.
      The @pytest.mark.slow marker is on the test but the default pytest addopts
      in pyproject.toml does NOT exclude slow tests, so this test runs and fails
      in the standard suite. The phase documented this as pre-existing in
      deferred-items.md without resolution.
    artifacts:
      - path: "tests/alpha/test_features.py"
        issue: "test_feature_computation_performance asserts < 5s but takes ~8.8s"
    missing:
      - "Either exclude 'slow' tests from default addopts (addopts = ... -m 'not slow') OR optimize the Numba pipeline to meet the 5s threshold OR relax the limit to match actual CI performance"
human_verification: null
---

# Phase 3: Alpha Engines Verification Report

**Phase Goal:** Implement all four alpha engines (HMM-GARCH regime detector, Johansen cointegration, carry signal provider, ML price momentum) with full test coverage and signal schema contract.
**Verified:** 2026-03-22T15:36:19Z
**Status:** gaps_found
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | shap 0.51.0 installed and importable | VERIFIED | `shap.__version__ == '0.51.0'`; `"shap.*"` in pyproject.toml mypy overrides |
| 2 | Signal schema types defined and importable | VERIFIED | `signal_types.py` exports SignalRow, RegimeState, SIGNAL_COLUMNS, REGIME_ACTIVATION, CONFIGURED_PAIRS, CROSS_ASSET_SYMBOLS — all importable |
| 3 | HMM-GARCH regime detector produces 3 states with stationarity constraint | VERIFIED | `hmm_garch.py` 253 lines; `monitor_.converged` correct; `alpha[1]`/`beta[1]` arch params correct; 4 tests pass |
| 4 | Weekly recalibration with 2-gate validation and atomic swap | VERIFIED | `calibration.py` 194 lines; Dirichlet smoothing, stationarity gate, state_agreement gate, `_pending` atomic swap; 5 tests pass |
| 5 | Johansen cointegration engine with rolling hedge ratio and z-score signals | VERIFIED | All 4 cointegration modules exist; z-score thresholds 2.0/4.0 correct; half-life uses `np.log(2)`; hedge ratio converges to 0.8006 (true=0.8, within 5%); 8 tests pass |
| 6 | Carry provider with cross-sectional ranking and spread filter | VERIFIED | `forex_carry.py` uses SwapRateCalculator; spread filter `carry < 2*spread` logic present; `FuturesCarryProvider` raises NotImplementedError; 4 tests pass |
| 7 | 27-feature Numba pipeline with PiT compliance | VERIFIED | All 5 tier modules exist; tiers 1/2/3/5 have `@njit(cache=True)`; tier 4 cross_asset explicitly no @njit; FeatureBuilder assembles with `.shift(1)`; warmup.py registers all 4 Numba functions; 6 tests pass |
| 8 | Walk-forward XGBoost+RF ensemble with SHAP and cost-adjusted metrics | VERIFIED | XGBoost callbacks in constructor (not fit); RF class_weight='balanced'; ensemble thresholds 0.53/0.47; SHAP uses `shap.Explainer`; walk_forward 756/5/21 config; cost_adjusted_sharpe annualized; 6 tests pass |
| 9 | Regime orchestrator gates ML+Carry/Cointegration/nothing by regime | VERIFIED | `orchestrator.py` uses REGIME_ACTIVATION map; 20-bar hysteresis; atomic pending model swap at bar start; ArcticDB signal writes with `{engine}_{symbol}` and `regime_{symbol}` patterns; 5 tests pass |
| 10 | Full phase coverage >= 80% | FAILED | Measured 64% (src/alpha only, excluding slow test); Numba coverage not traceable; orchestrator 61%, walk_forward 46%, online_filter 64% are primary gaps |
| 11 | 1M bar feature computation < 5s | FAILED | Takes 8.81s on CI; test_feature_computation_performance marked @pytest.mark.slow but addopts does not exclude it |

**Score:** 9/11 truths verified (2 failed)

---

## Required Artifacts

| Artifact | Min Lines | Actual | Status | Details |
|----------|-----------|--------|--------|---------|
| `tests/alpha/conftest.py` | 20 | 168 | VERIFIED | synthetic_returns, cointegrated_pair, sample_bar_data, sample_signal_df fixtures present |
| `src/alpha/signal_types.py` | — | 81 | VERIFIED | All required exports: SignalRow, SIGNAL_COLUMNS, RegimeState, REGIME_ACTIVATION, CONFIGURED_PAIRS, CROSS_ASSET_SYMBOLS |
| `pyproject.toml` | — | — | VERIFIED | `"shap.*"` in mypy overrides (line 38) |
| `src/alpha/regime/hmm_garch.py` | 100 | 253 | VERIFIED | HMMGARCHRegimeDetector with fit(), predict_viterbi(), is_fitted property |
| `src/alpha/regime/emissions.py` | 40 | 97 | VERIFIED | GARCHParams dataclass, unconditional_variance property, garch_emission_prob function |
| `src/alpha/regime/online_filter.py` | 50 | 151 | VERIFIED | OnlineRegimeFilter with update(), reset(), state_probs property |
| `src/alpha/regime/viterbi.py` | 30 | 60 | VERIFIED | viterbi_decode in log-space |
| `src/alpha/regime/calibration.py` | 80 | 194 | VERIFIED | RecalibrationService with 2 gates and atomic swap |
| `config/regime_calibration.yaml` | 10 | 15 | VERIFIED | dirichlet_concentration: 0.01 present |
| `src/alpha/cointegration/johansen.py` | 30 | 55 | VERIFIED | test_cointegration, JohansenResult exported |
| `src/alpha/cointegration/hedge_ratio.py` | 40 | 59 | VERIFIED | RollingHedgeRatio with PiT slicing |
| `src/alpha/cointegration/spread_signals.py` | 60 | 129 | VERIFIED | SpreadSignalGenerator with entry/exit/hard-stop thresholds |
| `src/alpha/cointegration/health_monitor.py` | 40 | 114 | VERIFIED | CointegrationHealthMonitor with half-life and breakdown detection |
| `src/alpha/carry/carry_provider.py` | 15 | 42 | VERIFIED | CarrySignalProvider ABC |
| `src/alpha/carry/forex_carry.py` | 60 | 134 | VERIFIED | ForexCarryProvider with SwapRateCalculator and spread filter |
| `src/alpha/carry/futures_carry.py` | 10 | 33 | VERIFIED | FuturesCarryProvider raises NotImplementedError |
| `src/alpha/ml_price_momentum/features/momentum.py` | 40 | 85 | VERIFIED | @njit(cache=True), 8 momentum features |
| `src/alpha/ml_price_momentum/features/volatility.py` | 40 | 131 | VERIFIED | @njit(cache=True), 6 volatility features |
| `src/alpha/ml_price_momentum/features/session.py` | 30 | 92 | VERIFIED | @njit(cache=True), 5 session features |
| `src/alpha/ml_price_momentum/features/cross_asset.py` | 30 | 110 | VERIFIED | No @njit (pandas only), 4 cross-asset features |
| `src/alpha/ml_price_momentum/features/tick_volume.py` | 25 | 91 | VERIFIED | @njit(cache=True), 4 tick volume features |
| `src/alpha/ml_price_momentum/features/builder.py` | 60 | 185 | VERIFIED | FeatureBuilder with 27 columns, .shift(1) applied |
| `src/alpha/ml_price_momentum/models/xgboost_model.py` | 40 | 45 | VERIFIED | callbacks=[EarlyStopping] in XGBClassifier constructor, NOT in fit() |
| `src/alpha/ml_price_momentum/models/walk_forward.py` | 80 | 139 | VERIFIED | WalkForwardConfig: train=756, purge=5, step=21 |
| `src/alpha/ml_price_momentum/models/ensemble.py` | 30 | 52 | VERIFIED | EnsembleModel with 0.53/0.47 signal thresholds |
| `src/alpha/ml_price_momentum/evaluation/shap_analysis.py` | 30 | 101 | VERIFIED | SHAPAnalyzer uses shap.Explainer auto-select |
| `src/alpha/orchestrator.py` | 120 | 349 | VERIFIED | RegimeOrchestrator + CrossAssetCache; hysteresis_bars=20; apply_pending at bar start |

All 27 required artifacts exist and meet minimum line counts.

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `tests/alpha/conftest.py` | `src/alpha/signal_types.py` | `from src.alpha.signal_types import` | WIRED | Line 9: `from src.alpha.signal_types import SIGNAL_COLUMNS, RegimeState` |
| `src/alpha/regime/hmm_garch.py` | `src/alpha/regime/emissions.py` | `from src.alpha.regime.emissions import` | WIRED | Line 12: `from src.alpha.regime.emissions import GARCHParams, garch_emission_prob` |
| `src/alpha/regime/hmm_garch.py` | `hmmlearn.hmm.GaussianHMM` | Stage 1 base HMM fit | WIRED | Line 10: `from hmmlearn.hmm import GaussianHMM`; used in fit() |
| `src/alpha/regime/online_filter.py` | `src/alpha/regime/emissions.py` | `garch_emission_prob` | WIRED | Line 9: `from src.alpha.regime.emissions import garch_emission_prob` |
| `src/alpha/regime/calibration.py` | `src/alpha/regime/hmm_garch.py` | `HMMGARCHRegimeDetector.fit()` | WIRED | Line 13: `from src.alpha.regime.hmm_garch import HMMGARCHRegimeDetector`; used in recalibrate() |
| `src/alpha/regime/calibration.py` | `src/data/pit_manager.py` | `pit_read` for fetching bar data | NOT WIRED | calibration.py does not import pit_read. RecalibrationService.recalibrate() takes `returns: np.ndarray` directly — caller must supply data. Design deviation from plan 03-03 key_link. Functional tests pass; the interface is cleaner but the plan contract is broken. |
| `src/alpha/cointegration/johansen.py` | `statsmodels.tsa.vector_ar.vecm.coint_johansen` | Johansen trace test | WIRED | Line 8: `from statsmodels.tsa.vector_ar.vecm import coint_johansen`; called in test_cointegration() |
| `src/alpha/cointegration/spread_signals.py` | `src/alpha/cointegration/hedge_ratio.py` | `RollingHedgeRatio` via parameter | PARTIAL | SpreadSignalGenerator accepts hedge_ratio as np.ndarray parameter — no hard import. Loose coupling is deliberate. Not a bug but the key_link is not a static import dependency. |
| `src/alpha/carry/forex_carry.py` | `src/execution/swap_rates.py` | `SwapRateCalculator.compute_annualized_carry()` | WIRED | Line 14: import; `SwapRateCalculator.compute_annualized_carry()` called in `_compute_carries()` |
| `src/alpha/carry/forex_carry.py` | `src/alpha/signal_types.py` | `SignalRow` for output | WIRED | Line 13: `from src.alpha.signal_types import CROSS_ASSET_SYMBOLS, SignalRow` |
| `src/alpha/ml_price_momentum/features/builder.py` | `src/alpha/ml_price_momentum/features/momentum.py` | `compute_momentum_features` | WIRED | Imported and called in build() |
| `src/backtest/warmup.py` | `src/alpha/ml_price_momentum/features/momentum.py` | warmup registration | WIRED | Lines 53-70: all 4 Numba feature functions imported and called |
| `src/alpha/ml_price_momentum/models/walk_forward.py` | `src/alpha/ml_price_momentum/features/builder.py` | `FeatureBuilder.build()` | NOT WIRED | WalkForwardEngine takes pre-built X: np.ndarray as input — it does not import or call FeatureBuilder. Design deviation from plan 07 key_link. The engine operates on features already assembled by the caller. |
| `src/alpha/ml_price_momentum/models/xgboost_model.py` | `xgboost.XGBClassifier` | `callbacks=[EarlyStopping]` in constructor | WIRED | Line 26: callbacks in XGBClassifier constructor; line 36: fit() has NO callbacks parameter |
| `src/alpha/ml_price_momentum/evaluation/shap_analysis.py` | `shap.Explainer` | auto-selects TreeExplainer | WIRED | Line 42: `explainer = shap.Explainer(xgb_model)` |
| `src/alpha/orchestrator.py` | `src/alpha/regime/hmm_garch.py` | `OnlineRegimeFilter` | WIRED | Lines 28-29: conditional import `from src.alpha.regime.online_filter import OnlineRegimeFilter` |
| `src/alpha/orchestrator.py` | `src/alpha/regime/calibration.py` | `RecalibrationService` | WIRED | Lines 28-29: conditional import `from src.alpha.regime.calibration import RecalibrationService` |
| `src/alpha/orchestrator.py` | `src/alpha/signal_types.py` | `REGIME_ACTIVATION` | WIRED | Line 20: `from src.alpha.signal_types import ... REGIME_ACTIVATION`; used in on_bar() |
| `src/alpha/orchestrator.py` | `src/data/arctic_store.py` | `get_library('signals')` | WIRED | Line 261: `from src.data.arctic_store import get_library`; used in persist_signals() |

**Key link summary:** 17 WIRED, 1 NOT WIRED (calibration pit_read), 1 NOT WIRED (walk_forward FeatureBuilder), 1 PARTIAL (spread_signals hedge_ratio via parameter).

The two NOT WIRED cases represent intentional design decisions with cleaner interfaces. Both are documented in summaries. Neither blocks functional correctness as confirmed by passing tests.

---

## Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|---------------|-------------|--------|----------|
| ALPH-01 | 03-01, 03-02 | HMM-GARCH 3-state detector with GARCH stationarity | SATISFIED | hmm_garch.py: HMMGARCHRegimeDetector; stationarity enforced; 4 tests pass |
| ALPH-02 | 03-01, 03-02 | States sorted by ascending unconditional variance | SATISFIED | sort by unconditional_variance in fit(); test_states_sorted_by_ascending_variance passes |
| ALPH-03 | 03-01, 03-03 | Weekly Baum-Welch + 1000-bar GARCH updates with gates | SATISFIED | calibration.py RecalibrationService; 2 gates; atomic swap; config yaml; 5 tests pass |
| ALPH-04 | 03-01, 03-04 | Johansen cointegration on 3 pairs, 504-bar rolling hedge | SATISFIED | johansen.py + hedge_ratio.py; RollingHedgeRatio(window=504); hedge converges to within 0.001 of true 0.8 |
| ALPH-05 | 03-01, 03-04 | Z-score ±2.0 entry/exit ±0.5, hard stop ±4.0, half-life | SATISFIED | spread_signals.py entry_z=2.0, hard_stop_z=4.0; health_monitor.py half-life via `np.log(2)` |
| ALPH-06 | 03-01, 03-05 | Carry provider, cross-sectional ranking, spread filter | SATISFIED | forex_carry.py uses SwapRateCalculator; ranking; spread filter 2x; futures stub NotImplementedError |
| ALPH-07 | 03-01, 03-06 | 27-feature Numba pipeline (5 tiers), PiT compliance | SATISFIED (partial) | All 5 tier modules with correct decorators; FeatureBuilder.shift(1); warmup registered. Performance <5s target not met (8.81s) |
| ALPH-08 | 03-01, 03-07 | Walk-forward 756-bar, 21-step, 30+ OOS windows, SHAP | SATISFIED | WalkForwardConfig correct; EnsembleModel 50/50; SHAPAnalyzer; cost_adjusted_metrics; 6 tests pass |
| ALPH-09 | 03-01, 03-08 | Regime gates: Trending→ML+Carry, MR→Coint, Crisis→none | SATISFIED | orchestrator.py REGIME_ACTIVATION map; 20-bar hysteresis; atomic swap; ArcticDB writes; 5 tests pass |

All 9 requirements have implementation evidence. No orphaned requirements. All 9 listed as Complete in REQUIREMENTS.md.

---

## Test Suite Summary

| Test File | Tests | Result | Skip Markers |
|-----------|-------|--------|--------------|
| test_regime_detector.py | 4 | 4 passed | 0 remaining |
| test_calibration.py | 5 | 5 passed | 0 remaining |
| test_calibration_tdd.py | 7 | 7 passed | 0 remaining |
| test_cointegration.py | 8 | 8 passed | 0 remaining |
| test_carry.py | 4 | 4 passed | 0 remaining |
| test_features.py | 7 | 6 passed, 1 FAILED | 0 remaining |
| test_features_tdd.py | (see above) | — | — |
| test_walk_forward.py | 3 | 3 passed | 0 remaining |
| test_ensemble.py | 3 | 3 passed | 0 remaining |
| test_orchestrator.py | 5 | 5 passed | 0 remaining |

**Total:** 59 collected, 58 passed, 1 failed (`test_feature_computation_performance`: 8.81s > 5s)

---

## Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `tests/alpha/test_features.py` line 86-136 | `@pytest.mark.slow` test runs by default (addopts does not exclude slow markers) | BLOCKER | Causes test suite to fail every run; cannot meet CI gate |
| `src/alpha/ml_price_momentum/features/momentum.py` | Numba @njit body not covered by Python coverage (18%) | WARNING | Coverage gate fails; Numba code IS executed — this is a tooling gap, not untested logic |
| `src/alpha/ml_price_momentum/features/volatility.py` | Same Numba coverage issue (10%) | WARNING | Same as above |
| `src/alpha/ml_price_momentum/features/session.py` | Same Numba coverage issue (16%) | WARNING | Same as above |
| `src/alpha/ml_price_momentum/features/tick_volume.py` | Same Numba coverage issue (13%) | WARNING | Same as above |
| `src/alpha/orchestrator.py` lines 258-290, 304-320 | `persist_signals()` and `persist_regime_state()` async methods not tested (61% coverage) | WARNING | ArcticDB write paths untested without mocked library |

---

## Hedge Ratio Indexing Note

The PLAN spec (03-04) documented the hedge ratio formula as `hedge_ratio = -result.evec[1, 0] / result.evec[0, 0]`. The actual implementation uses `hedge_ratio = -result.evec[0, 0] / result.evec[1, 0]` with a detailed derivation comment showing this is mathematically equivalent given statsmodels' column ordering convention. The implementation is correct — convergence to 0.8006 (true=0.8) confirmed by direct test. This is NOT a bug.

---

## Human Verification Required

### 1. Numba Coverage Exclusion Decision

**Test:** Determine whether coverage exclusion for Numba @njit functions is the right fix, or whether the 80% gate should be measured differently.
**Expected:** Either (a) pyproject.toml `[tool.coverage.run]` omits Numba source files, or (b) `# pragma: no cover` on @njit decorated functions, or (c) the project accepts that Numba code is verified by functional tests not line coverage.
**Why human:** Policy decision about how coverage applies to JIT-compiled code.

### 2. Performance Benchmark Environment

**Test:** Run `pytest tests/alpha/test_features.py::test_feature_computation_performance -v` after Numba warmup on the target hardware.
**Expected:** Execution completes in < 5 seconds on production-equivalent hardware (not CI).
**Why human:** The 8.81s figure may be CI-specific (shared vCPUs). The limit may be appropriate on dedicated hardware with Numba cache pre-populated.

---

## Gaps Summary

Two gaps block full phase goal achievement:

**Gap 1 — Coverage gate failure (64% vs 80%):** The coverage shortfall has two components. First, Numba JIT functions are not traced by coverage.py despite being functionally tested — this requires either a coverage configuration fix or a policy decision. Second, `orchestrator.py` (61%), `walk_forward.py` (46%), and `online_filter.py` (64%) need more direct Python-level test paths. The phase acknowledged this in `deferred-items.md` but deferred without resolution.

**Gap 2 — Performance test failure (8.81s vs 5s):** `test_feature_computation_performance` fails every run because `@pytest.mark.slow` does not exclude it from the default `addopts`. This means the standard test suite always fails. Fix is either to add `-m "not slow"` to `addopts` in pyproject.toml, or relax the performance threshold to match CI hardware capability.

Both gaps were explicitly logged as deferred items by the executing agent. The core functional goal — four working alpha engines with signal schema, tests, and regime orchestration — is achieved. All 9 requirements have verified implementation evidence and 58/59 tests pass.

---

_Verified: 2026-03-22T15:36:19Z_
_Verifier: Claude (gsd-verifier)_
