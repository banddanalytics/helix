# Phase 3: Alpha Engines - Research

**Researched:** 2026-03-22
**Domain:** Quantitative trading alpha engines — HMM-GARCH, cointegration, carry, ML momentum
**Confidence:** HIGH (all critical APIs verified against installed library versions in project venv)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Common signal schema: `timestamp` (index), `symbol`, `engine`, `direction` (int8: +1/0/-1), `strength` (float32 [0,1]), `regime` (int8 at signal time), plus nullable engine-specific columns: `z_score` (cointegration), `ml_prob` (ML), `carry_rank` (carry).
- **D-02:** Each engine writes to its own ArcticDB `signals` library symbol using pattern `{engine}_{symbol}` (e.g. `cointegration_EURUSD_NZDUSD`, `ml_EURUSD`). Engines are isolated — a failing engine never blocks others.
- **D-03:** Regime state is stored separately as `regime_{symbol}` in the `signals` library — it is state, not a trading signal. Risk engine reads it independently to apply Kelly multipliers.
- **D-04:** Central `RegimeOrchestrator` owns all strategy activation. On each bar it reads regime state and calls `engine.generate_signals()` only for active engines — inactive engines are never called.
- **D-05:** Activation map (locked per ALPH-09):
  - `TRENDING` → `[ml_engine, carry_engine]`
  - `MEAN_REVERTING` → `[cointegration_engine]`
  - `CRISIS` → `[]` (reduce-only, no new signals generated)
- **D-06:** The orchestrator owns the 20-bar hysteresis dwell logic for regime transitions. Individual engines have no awareness of hysteresis.
- **D-07:** `CrossAssetCache` pre-loads the last 252 bars for all 6 required symbols at startup via `pit_read()`. Updates incrementally on each new bar (append new, drop oldest — O(1) per bar).
- **D-08:** Required symbols: `EURUSD, GBPUSD, AUDUSD, NZDUSD, USDJPY, USDCHF` — identical to the pairs already used by cointegration and carry engines, no extra data cost.
- **D-09:** Cache lives on the orchestrator and is injected into `FeatureBuilder`. During backtests it is pre-populated from the ArcticDB snapshot and replayed bar-by-bar.
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

### Deferred Ideas (OUT OF SCOPE)

- MBO order flow features (OFI, VPIN, depth imbalance) — Stage B only, no genuine order book in Stage A (STAGEB-03)
- `ml_mbo_orderflow` module — stub exists at `src/alpha/ml_mbo_orderflow/`, activated in Stage B
- Automated pair discovery (test all XXXYYY combinations) — v2 requirement
- Telegram/SMS alerting for regime switches — Phase 4 NATS layer doesn't exist yet
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ALPH-01 | HMM-GARCH regime detector identifies 3 states (Trending/Mean-Reverting/Crisis) with GARCH stationarity constraint | hmmlearn 0.3.3 GaussianHMM + arch 8.0.0 GARCH APIs verified; `alpha + beta < 1` check implemented in per-state GARCH fits |
| ALPH-02 | Regime states sorted by ascending unconditional variance (deterministic across refits) | Sort key `ω/(1-α-β)` documented; verified in SKILL.md and spec |
| ALPH-03 | Weekly Baum-Welch recalibration + 1000-bar GARCH parameter updates | hmmlearn `fit()` is Baum-Welch EM; recalibration scheduler pattern documented |
| ALPH-04 | Johansen cointegration engine tests 3 Forex pairs with dynamic hedge ratio (504-bar rolling) | statsmodels 0.14.6 `coint_johansen` API verified; `evec[1,0]/evec[0,0]` hedge ratio indexing confirmed on live data |
| ALPH-05 | Z-score entry/exit signals fire at ±2.0 with hard stop at ±4.0; half-life monitoring | Z-score formula, AR(1) half-life, and threshold logic fully specified in spec and skills |
| ALPH-06 | Swap-based carry provider ranks symbols cross-sectionally, suppresses when spread > carry | `SwapRateCalculator.compute_annualized_carry()` API inspected; `CarryResult` dataclass confirmed |
| ALPH-07 | 27-feature Numba pipeline (5 tiers) with PiT compliance | All 4 Numba tiers verified compilable (np.std, np.sign, np.log, slicing all work in njit); cross-asset tier stays in pandas (multi-symbol alignment) |
| ALPH-08 | Walk-forward XGBoost+RF ensemble (756-bar train, 21-bar step, 30+ OOS windows) with SHAP | XGBoost 3.2.0: callbacks MUST go in constructor, NOT `fit()` — critical breaking change verified; shap not yet installed (0.51.0 available) |
| ALPH-09 | Regime gates strategy activation: Trending → ML+Carry, Mean-Reverting → Cointegration, Crisis → reduce only | `RegimeOrchestrator` pattern documented; hysteresis (20 bars) owned by orchestrator per D-06 |
</phase_requirements>

---

## Summary

Phase 3 builds four alpha generation engines on top of Phase 2's ArcticDB/PiT infrastructure. The regime detector (HMM-GARCH) is the master switch and must be built first. Cointegration pairs, carry, and ML momentum can be built in parallel after the regime detector is working. All four engines read data exclusively through `pit_read()` and write signals to the `signals` ArcticDB library.

The critical API pitfall for this phase is **XGBoost 3.x**: the `callbacks` parameter moved from `fit()` to the `XGBClassifier` constructor. The project is on XGBoost 3.2.0 and code written with the pre-3.0 pattern will raise a `TypeError`. This was verified directly against the installed library.

The cross-asset feature tier (Tier 4) cannot be Numba JIT compiled because it operates on a dict of symbol arrays requiring pandas alignment — it stays in pure Python/pandas while the other four tiers use `@njit(cache=True)`. SHAP is not currently installed and must be added to the project as a Wave 0 task. The `shap.Explainer(xgb_model)` auto-selects `TreeExplainer` for XGBoost models — no need to import `shap.TreeExplainer` directly.

**Primary recommendation:** Build Phase 3A (regime detector) first as a complete unit with its own test suite. Then build 3B (cointegration + carry) and 3C (ML pipeline) in parallel, using the regime detector's output contract as the integration seam.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| hmmlearn | 0.3.3 | GaussianHMM for regime detection (Stage 1 fit) | Only production-grade Python HMM library; Baum-Welch EM built in |
| arch | 8.0.0 | GARCH(1,1) per-state emission fitting | Industry standard for ARCH/GARCH; clean `arch_model().fit()` API |
| statsmodels | 0.14.6 | Johansen cointegration test, VECM | Only Python library with `coint_johansen` (no alternatives) |
| xgboost | 3.2.0 | Gradient boosting classifier in ensemble | Fast, regularized, supports early stopping; project already uses it |
| scikit-learn | 1.8.0 | RandomForestClassifier for ensemble second model | Standard; `class_weight='balanced'` for imbalanced signal labels |
| numba | (existing) | `@njit(cache=True)` for 5-tier feature pipeline | Project already uses it; 1M bar < 5s requirement met only with JIT |
| shap | 0.51.0 | TreeExplainer for XGBoost feature importance | Required by ALPH-08; not yet installed — Wave 0 task |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| numpy | (existing) | Array math throughout all engines | All numerical operations |
| pandas | (existing) | Rolling windows, cross-asset alignment, signal DataFrames | Tier 4 cross-asset features; signal output construction |
| asyncio.to_thread | stdlib | ArcticDB signal writes (non-blocking) | Per established Phase 2 pattern (SwapWriter) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| hmmlearn GaussianHMM | pomegranate | pomegranate has better GPU support but different API; hmmlearn is already in mypy overrides |
| statsmodels coint_johansen | manual OLS hedge ratio | Manual OLS misses rank determination; Johansen is required for ALPH-04 |
| shap.Explainer (auto) | shap.TreeExplainer (explicit) | `shap.Explainer(model)` auto-selects TreeExplainer for XGBoost — spec recommends auto form |

**Installation (Wave 0):**
```bash
.venv/bin/pip install shap==0.51.0
```

**Version verification (confirmed 2026-03-22 against project venv):**
- hmmlearn: 0.3.3
- arch: 8.0.0
- statsmodels: 0.14.6
- xgboost: 3.2.0
- scikit-learn: 1.8.0
- shap: 0.51.0 (available, not yet installed)

---

## Architecture Patterns

### Recommended Project Structure
```
src/alpha/
├── regime/                  # HMM-GARCH regime detector (Phase 3A)
│   ├── __init__.py
│   ├── hmm_garch.py         # HMMGARCHRegimeDetector class
│   ├── emissions.py         # GARCH emission PDF (omega/alpha/beta/mu)
│   ├── online_filter.py     # Forward-only real-time filter (no backward pass)
│   ├── viterbi.py           # Offline log-space Viterbi for backtests
│   └── calibration.py       # Weekly Baum-Welch + Dirichlet smoothing
├── cointegration/           # Johansen pairs engine (Phase 3B)
│   ├── __init__.py
│   ├── johansen.py          # Trace test, rank detection
│   ├── vecm.py              # VECM estimation
│   ├── hedge_ratio.py       # Dynamic 504-bar rolling hedge ratio
│   ├── spread_signals.py    # Z-score entry/exit/hard-stop logic
│   └── health_monitor.py   # Half-life AR(1), breakdown detection
├── carry/                   # Swap-based carry provider (Phase 3B)
│   ├── __init__.py
│   ├── carry_provider.py    # Abstract CarrySignalProvider ABC
│   ├── forex_carry.py       # Stage A: SwapRateCalculator wrapper
│   └── futures_carry.py     # Stage B: NotImplementedError stub
├── ml_price_momentum/       # 27-feature ML ensemble (Phase 3C)
│   ├── __init__.py
│   ├── features/
│   │   ├── momentum.py      # Tier 1: 8 momentum features (@njit)
│   │   ├── volatility.py    # Tier 2: 6 volatility features (@njit)
│   │   ├── session.py       # Tier 3: 5 session features (@njit)
│   │   ├── cross_asset.py   # Tier 4: 4 cross-asset features (pandas)
│   │   ├── tick_volume.py   # Tier 5: 4 tick volume features (@njit)
│   │   └── builder.py       # Assembles all 27 features, applies .shift(1)
│   ├── models/
│   │   ├── xgboost_model.py # XGBClassifier with callbacks in constructor
│   │   ├── rf_model.py      # RandomForestClassifier
│   │   ├── ensemble.py      # P = 0.5 * P_xgb + 0.5 * P_rf
│   │   └── walk_forward.py  # 756-train / 21-step / 5-purge framework
│   └── evaluation/
│       ├── shap_analysis.py # shap.Explainer(xgb_model) per window
│       └── cost_adjusted_metrics.py
├── orchestrator.py          # RegimeOrchestrator + CrossAssetCache
└── ml_mbo_orderflow/        # Stage B stub (already exists — __init__.py only)

config/
└── regime_calibration.yaml  # Recalibration schedule config

tests/alpha/
├── __init__.py
├── test_regime_detector.py
├── test_calibration.py
├── test_cointegration.py
├── test_carry.py
├── test_features.py
├── test_walk_forward.py
├── test_ensemble.py
└── test_orchestrator.py
```

### Pattern 1: Two-Stage HMM-GARCH Fit
**What:** Stage 1 uses hmmlearn GaussianHMM to assign initial state labels; Stage 2 fits a GARCH(1,1) per state on those subsets. The GARCH params replace Gaussian emissions.
**When to use:** Regime detector fit and weekly recalibration.
**Example:**
```python
# Source: .claude/skills/forex/hmm-garch-regime-detector/SKILL.md + verified against hmmlearn 0.3.3
from hmmlearn.hmm import GaussianHMM
from arch import arch_model

# Stage 1: initial Gaussian HMM
base = GaussianHMM(n_components=3, covariance_type='diag', n_iter=100, tol=0.01)
base.fit(returns.reshape(-1, 1))

# Convergence check — must happen AFTER fit()
if not base.monitor_.converged:
    # retry with different random_state
    pass

states = base.predict(returns.reshape(-1, 1))

# Stage 2: per-state GARCH(1,1)
for s in range(3):
    state_returns = returns[states == s]
    if len(state_returns) < 100:
        continue
    res = arch_model(state_returns, vol='Garch', p=1, q=1, dist='normal').fit(disp='off')
    params = {
        'mu':    res.params['mu'],       # verified key name
        'omega': res.params['omega'],    # verified key name
        'alpha': res.params['alpha[1]'], # verified key name
        'beta':  res.params['beta[1]'],  # verified key name
    }
    # Stationarity gate — hard reject
    assert params['alpha'] + params['beta'] < 1.0

# Sort states by ascending unconditional variance for determinism
# unconditional_var[s] = omega[s] / (1 - alpha[s] - beta[s])
```

### Pattern 2: Johansen Trace Test with Hedge Ratio
**What:** `coint_johansen(data, det_order=0, k_ar_diff=1)` — result.evec indexing for hedge ratio is `[1,0]/[0,0]` on the first eigenvector.
**When to use:** Initial pair test and rolling 504-bar hedge ratio update.
**Example:**
```python
# Source: statsmodels 0.14.6 — verified evec shape (2,2) for bivariate case
from statsmodels.tsa.vector_ar.vecm import coint_johansen
import numpy as np

data = np.column_stack([y1, y2])
result = coint_johansen(data, det_order=0, k_ar_diff=1)

trace_stat = result.trace_stat[0]           # scalar for H0: rank=0
crit_95   = result.trace_stat_crit_vals[0, 1]  # col 1 = 95% critical value

cointegrated = trace_stat > crit_95
# Hedge ratio: first eigenvector (column 0), ratio of row-1 to row-0
hedge_ratio = -result.evec[1, 0] / result.evec[0, 0]
```

### Pattern 3: XGBoost EarlyStopping — v3.x Breaking Change
**What:** In XGBoost 3.x, `callbacks` moved from `fit()` to the `XGBClassifier` constructor. Passing `callbacks` to `fit()` raises `TypeError: got an unexpected keyword argument 'callbacks'`.
**When to use:** Every XGBoost model instantiation in the walk-forward loop.
**Example:**
```python
# Source: verified against xgboost 3.2.0 in project venv
import xgboost as xgb

# CORRECT for XGBoost 3.x — callbacks in constructor
clf = xgb.XGBClassifier(
    n_estimators=500,
    max_depth=5,
    learning_rate=0.01,
    subsample=0.8,
    colsample_bytree=0.7,
    min_child_weight=100,
    reg_alpha=0.1,
    reg_lambda=1.0,
    eval_metric='logloss',
    callbacks=[xgb.callback.EarlyStopping(rounds=50, metric_name='logloss')]
)
clf.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
proba = clf.predict_proba(X_test)[:, 1]  # class 1 probability

# WRONG — raises TypeError in XGBoost 3.x
# clf.fit(X_train, y_train, callbacks=[...])  # DO NOT DO THIS
```

### Pattern 4: Numba @njit Feature Functions
**What:** Feature tier functions must be defined in `.py` module files (not inline strings). `cache=True` requires a filesystem-backed source file. `os.environ.setdefault("NUMBA_CACHE_DIR", "./numba_cache")` must appear before `from numba import njit`.
**When to use:** Tiers 1, 2, 3, 5 of the feature pipeline. Tier 4 (cross-asset) stays in pandas.
**Example:**
```python
# Source: src/backtest/numba_kernels.py + accumulators.py — established project pattern
from __future__ import annotations
import os
os.environ.setdefault("NUMBA_CACHE_DIR", "./numba_cache")
import numpy as np
from numba import njit

@njit(cache=True)
def compute_momentum_features(close: np.ndarray, high: np.ndarray, low: np.ndarray) -> np.ndarray:
    n = len(close)
    features = np.empty((n, 8))
    features[:] = np.nan
    for i in range(253, n):
        features[i, 0] = close[i-1] / close[i-2] - 1  # 1-bar return (PiT)
        # ... remaining 7 features
    return features
```

### Pattern 5: ArcticDB Signal Write (asyncio.to_thread)
**What:** Signal writes use `asyncio.to_thread` to keep the event loop non-blocking. First write uses `lib.write()`, subsequent updates on the same symbol use `lib.append()`.
**When to use:** Each engine's signal persistence after `generate_signals()` call.
**Example:**
```python
# Source: src/data/arctic_store.py pattern + Phase 2 SwapWriter pattern
import asyncio
from src.data.arctic_store import get_library

async def write_signal(engine: str, symbol: str, df: pd.DataFrame) -> None:
    lib = get_library("signals")
    arctic_symbol = f"{engine}_{symbol}"
    try:
        await asyncio.to_thread(lib.append, arctic_symbol, df)
    except Exception:
        # Symbol doesn't exist yet — first write
        await asyncio.to_thread(lib.write, arctic_symbol, df)
```

### Pattern 6: SHAP TreeExplainer for XGBoost
**What:** Use `shap.Explainer(xgb_model)` which auto-selects `TreeExplainer`. Compute per-window SHAP values.
**When to use:** After each walk-forward window fit to track feature stability.
**Example:**
```python
# Source: _docs/Phase_3_Alpha_Engines.md Task 3C.2
import shap

explainer = shap.Explainer(xgb_model)         # auto → TreeExplainer
shap_values = explainer(X_test)               # shape: (n_samples, n_features)
# SHAP identity: shap_values.values.sum(axis=1) + explainer.expected_value ≈ model output
```

### Pattern 7: Warmup Registration for Alpha Numba Functions
**What:** `src/backtest/warmup.py::warmup_numba()` must be extended to call each new `@njit` feature function with tiny representative arrays. Import the function in `warmup_numba()` body (lazy import pattern matches existing code).
**When to use:** Wave 0 of Phase 3C — register all 4 Numba tier functions.
**Example:**
```python
# Extend warmup_numba() in src/backtest/warmup.py
from src.alpha.ml_price_momentum.features.momentum import compute_momentum_features
n = 300  # min warmup size to satisfy warmup range (253 required)
compute_momentum_features(
    close=np.linspace(1.0, 1.05, n),
    high=np.linspace(1.01, 1.06, n),
    low=np.linspace(0.99, 1.04, n),
)
```

### Anti-Patterns to Avoid

- **Callbacks in XGBoost `fit()`:** `clf.fit(X, y, callbacks=[...])` raises `TypeError` in XGBoost 3.x. All callbacks (including `EarlyStopping`) go in the constructor.
- **Numba on cross-asset tier:** Tier 4 requires `pd.DataFrame.rolling().corr()` and `.std(axis=1)` across a dict of symbol arrays. These are not Numba-compatible. Keep Tier 4 in pandas.
- **Numba cache=True in interactive context:** `@njit(cache=True)` fails when the function is defined in a string (e.g., `python -c "..."`). All `@njit(cache=True)` functions must live in `.py` files.
- **Calling `predict()` before `fit()` on hmmlearn:** `monitor_` is created by `fit()` — checking `monitor_.converged` before fit raises `AttributeError`.
- **Looking up future data in rolling hedge ratio:** The rolling Johansen window `[t-504, t]` must use `[t-504, t-1]` (exclusive end) to be PiT compliant. Step through the spec's loop: `for t in range(window, T): data = ...[t-window:t]` — Python slice excludes `t`, so `t` itself is never included. Correct.
- **Importing SHAP before installation:** shap is not in the current venv — Wave 0 must install it before any shap import.
- **Mid-bar model swap:** The pending HMM model must only be activated at the START of `on_bar()`, never mid-computation.
- **State label aliasing across refits:** HMM state 0 in refit N may not be the same regime as state 0 in refit N-1. Always re-sort by unconditional variance after each fit.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Baum-Welch EM for HMM | Custom forward-backward loop | `hmmlearn.GaussianHMM.fit()` | Numerically stable log-space implementation; handles convergence monitoring |
| Johansen cointegration test | Custom trace statistic from scratch | `statsmodels.coint_johansen` | Critical value tables are hard to replicate; rank determination is non-trivial |
| Early stopping for XGBoost | Manual eval loop with patience counter | `xgb.callback.EarlyStopping` | Callbacks integrate with internal eval rounds; manual is fragile |
| Feature importance for XGBoost | `clf.feature_importances_` array | `shap.Explainer` | Split-based importances are biased toward high-cardinality features; SHAP is game-theoretically fair |
| Rolling z-score normalization | Per-row lambda | `pd.Series.rolling().mean()` + `std()` with `.shift(1)` | Vectorized, correct PiT |
| GARCH variance recursion from scratch | NumPy loop with manual MLE | `arch.arch_model().fit()` | arch handles MLE optimization, gradient computation, parameter constraints |

**Key insight:** All four engines rely on statistical models with well-known edge cases (degenerate states, near-unit-root processes, look-ahead in rolling windows). Use established libraries for the statistical core; implement only the integration glue (PiT enforcement, signal schema, regime gating).

---

## Common Pitfalls

### Pitfall 1: XGBoost 3.x EarlyStopping in `fit()` (CRITICAL)
**What goes wrong:** `TypeError: XGBClassifier.fit() got an unexpected keyword argument 'callbacks'`
**Why it happens:** XGBoost 3.0 moved `callbacks` from `fit()` to the constructor. All pre-3.0 examples and tutorials use `clf.fit(X, y, callbacks=[...])`.
**How to avoid:** Always pass `callbacks=[xgb.callback.EarlyStopping(...)]` to `XGBClassifier(...)` constructor, not to `fit()`.
**Warning signs:** `TypeError` on `clf.fit()` call.

### Pitfall 2: HMM State Index Instability Across Refits
**What goes wrong:** State 0 in week N is Crisis; state 0 in week N+1 is Trending. Regime gating breaks silently.
**Why it happens:** hmmlearn assigns state indices arbitrarily. Without re-sorting, the regime label mapping is meaningless after refit.
**How to avoid:** After every `fit()`, compute `ω/(1-α-β)` for each state and re-sort states by ascending unconditional variance. State 0 = lowest vol = Trending; State 2 = highest vol = Crisis.
**Warning signs:** Regime switches that seem random or correlated with recalibration timing.

### Pitfall 3: Look-Ahead Bias in Rolling Johansen Hedge Ratio
**What goes wrong:** Hedge ratio at bar T uses price data including bar T, biasing all subsequent z-score signals.
**Why it happens:** `data[t-window:t+1]` instead of `data[t-window:t]` — off-by-one in the window end.
**How to avoid:** Always use `data[t-window:t]` (Python exclusive end). The spec's loop `for t in range(window, T)` with `data[t-window:t]` is correct.
**Warning signs:** `validate_pit_compliance()` IC ratio > 1.5 threshold.

### Pitfall 4: Numba Tier 4 (Cross-Asset) Compilation Error
**What goes wrong:** `TypingError` when trying to `@njit` a function that uses `pd.DataFrame` or dict indexing.
**Why it happens:** Numba cannot compile pandas operations or Python dicts with heterogeneous values.
**How to avoid:** Tier 4 (`compute_cross_asset_features`) must be plain Python/pandas — no `@njit` decorator. Only Tiers 1, 2, 3, and 5 use Numba.
**Warning signs:** Numba compilation error mentioning `reflected dict` or `DataFrame`.

### Pitfall 5: GARCH Convergence Failure on Small State Subsets
**What goes wrong:** GARCH fit on a small state subset (< 100 returns) fails or produces degenerate parameters (alpha + beta ≥ 1).
**Why it happens:** GARCH MLE needs enough returns to estimate volatility persistence. Crisis state may have very few bars.
**How to avoid:** Skip GARCH fit for states with < 100 samples (use Gaussian emission fallback). Apply stationarity hard reject: if `alpha + beta >= 1`, reject entire refit and keep prior model.
**Warning signs:** `arch` optimizer warning about convergence; stationarity check fails.

### Pitfall 6: ArcticDB `append()` Before First `write()`
**What goes wrong:** `KeyError` or symbol not found when calling `lib.append()` on a symbol that doesn't exist yet.
**Why it happens:** ArcticDB `append()` requires the symbol to already exist; `write()` creates it.
**How to avoid:** Try `append()` first; catch the exception and fall back to `write()` for the first write. Or check symbol existence with `lib.has_symbol()` before deciding.
**Warning signs:** `KeyError` on first engine signal write.

### Pitfall 7: shap Not Installed
**What goes wrong:** `ModuleNotFoundError: No module named 'shap'` when running SHAP analysis.
**Why it happens:** shap is not in the current project venv (verified 2026-03-22).
**How to avoid:** Wave 0 of Phase 3C installs `shap==0.51.0`. Also add to mypy overrides in `pyproject.toml`.
**Warning signs:** Import error on any file that imports shap.

### Pitfall 8: Numba `cache=True` Runtime Error in Tests
**What goes wrong:** `RuntimeError: cannot cache function: no locator available for file '<string>'`
**Why it happens:** `cache=True` requires Numba to find the source `.py` file on disk. This fails for functions defined in eval strings (e.g., `python -c "..."`). In normal test runs this is not an issue.
**How to avoid:** All `@njit(cache=True)` functions must be defined in `.py` module files. Tests import from those files normally. Do not define JIT functions dynamically.
**Warning signs:** Error during warmup in test environments using tmpdir.

---

## Code Examples

Verified patterns from official sources and project venv:

### hmmlearn GaussianHMM with Convergence Check and Retry
```python
# Source: hmmlearn 0.3.3 — GaussianHMM.__init__ signature verified
from hmmlearn.hmm import GaussianHMM
import numpy as np

def fit_with_retry(returns: np.ndarray, n_states: int = 3, max_attempts: int = 5) -> GaussianHMM:
    returns_2d = returns.reshape(-1, 1)
    for seed in range(max_attempts):
        model = GaussianHMM(
            n_components=n_states,
            covariance_type='diag',
            n_iter=100,
            tol=0.01,
            random_state=seed,
        )
        model.fit(returns_2d)
        if model.monitor_.converged:  # monitor_.converged verified on hmmlearn 0.3.3
            return model
    return model  # return last attempt regardless
```

### arch GARCH(1,1) Parameter Extraction
```python
# Source: arch 8.0.0 — parameter names verified: ['mu', 'omega', 'alpha[1]', 'beta[1]']
from arch import arch_model

res = arch_model(state_returns, vol='Garch', p=1, q=1, dist='normal').fit(disp='off')
params = {
    'mu':    res.params['mu'],
    'omega': res.params['omega'],
    'alpha': res.params['alpha[1]'],   # NOT 'alpha' — verified key name
    'beta':  res.params['beta[1]'],    # NOT 'beta'  — verified key name
}
assert params['alpha'] + params['beta'] < 1.0, "GARCH non-stationary — reject fit"
```

### statsmodels coint_johansen — Verified Indexing
```python
# Source: statsmodels 0.14.6 — evec shape (2,2) verified; trace_stat_crit_vals shape (2,3)
from statsmodels.tsa.vector_ar.vecm import coint_johansen
import numpy as np

data = np.column_stack([y1, y2])
result = coint_johansen(data, det_order=0, k_ar_diff=1)

# result.trace_stat_crit_vals columns: [90%, 95%, 99%]
crit_95 = result.trace_stat_crit_vals[0, 1]  # row 0 = H0:rank=0, col 1 = 95%
cointegrated = result.trace_stat[0] > crit_95

# Hedge ratio: from first cointegrating vector (column 0 of evec)
hedge_ratio = -result.evec[1, 0] / result.evec[0, 0]
```

### XGBoost 3.2.0 Walk-Forward Fit
```python
# Source: xgboost 3.2.0 — callbacks in constructor verified; fit() signature confirmed
import xgboost as xgb

# Callbacks MUST go in constructor in XGBoost 3.x
xgb_model = xgb.XGBClassifier(
    n_estimators=500,
    max_depth=5,
    learning_rate=0.01,
    subsample=0.8,
    colsample_bytree=0.7,
    min_child_weight=100,
    reg_alpha=0.1,
    reg_lambda=1.0,
    eval_metric='logloss',
    callbacks=[xgb.callback.EarlyStopping(rounds=50, metric_name='logloss')],
)
xgb_model.fit(
    X_train, y_train,
    eval_set=[(X_val, y_val)],
    verbose=False,
)
proba_xgb = xgb_model.predict_proba(X_test)[:, 1]  # shape: (n_test,)
```

### SwapRateCalculator API for ForexCarryProvider
```python
# Source: src/execution/swap_rates.py — SwapRateCalculator.compute_annualized_carry() verified
from src.execution.swap_rates import SwapRateCalculator

result = SwapRateCalculator.compute_annualized_carry(
    swap_long=0.5,       # MT5 swap_long value
    swap_short=-0.7,     # MT5 swap_short value
    point=0.00001,       # instrument point size
    mid_price=1.0850,    # current mid price
)
# result.carry_long  — annualized % for long position
# result.carry_short — annualized % for short position
# result.net_carry   — carry_long + carry_short
```

### ArcticDB Signal Write Pattern
```python
# Source: arcticdb write/append signatures verified; asyncio.to_thread per Phase 2 pattern
import asyncio
from src.data.arctic_store import get_library

async def persist_signal(engine: str, symbol: str, df: pd.DataFrame) -> None:
    """Write signal DataFrame to signals library, appending if symbol exists."""
    lib = get_library("signals")
    arctic_symbol = f"{engine}_{symbol}"
    if lib.has_symbol(arctic_symbol):
        await asyncio.to_thread(lib.append, arctic_symbol, df)
    else:
        await asyncio.to_thread(lib.write, arctic_symbol, df)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `clf.fit(X, y, callbacks=[...])` | `XGBClassifier(callbacks=[...]); clf.fit(X, y)` | XGBoost 3.0 | Breaking — affects walk-forward code |
| `shap.TreeExplainer(model)` | `shap.Explainer(model)` (auto-selects) | shap 0.40+ | Spec recommends `shap.Explainer` for forward compatibility |
| `hmmlearn.hmm.GaussianHMM(n_iter=10)` default | `n_iter=100, tol=0.01` explicit | Always was default=10 | Must be explicit; default 10 is too few for regime detection |

**Deprecated/outdated:**
- `xgb.train()` with `evals_result` dict: The sklearn API (`XGBClassifier`) is used throughout this phase — consistent with how `predict_proba()` is needed for ensemble weighting.
- Manual `shap.TreeExplainer` import: Use `shap.Explainer(model)` which auto-selects the right backend.

---

## Open Questions

1. **Carry provider input source during backtests**
   - What we know: `SwapRateCalculator.compute_annualized_carry()` takes raw swap point floats; in live trading these come from MT5 API
   - What's unclear: During historical backtests, how are historical swap rates sourced? The `swap_rates` ArcticDB library exists (DATA-01) — is it populated with historical data or does carry engine use current rates only?
   - Recommendation: Use current swap rates from `swap_rates` library as a proxy for historical rates (carry strategies are relatively slow-moving). BacktestRunner can inject a fixed CarryResult for backtests.

2. **RegimeOrchestrator test isolation**
   - What we know: `RegimeOrchestrator` integrates all 4 engines; unit testing the orchestrator requires mocking engines
   - What's unclear: Whether to test orchestrator with real engine stubs or pure mock objects
   - Recommendation: Use `unittest.mock.MagicMock` for engine mocks in unit tests; create a separate integration test with real engines on synthetic data.

3. **tests/alpha/ directory placement**
   - What we know: The spec says `tests/alpha/test_*.py`; existing test structure has `tests/unit/`, `tests/integration/`, `tests/e2e/`
   - What's unclear: Whether alpha tests should go under `tests/unit/alpha/` or `tests/alpha/` at the top level
   - Recommendation: Use `tests/alpha/` as specified in the phase spec to match the skill SKILL.md directory structure. The pytest `testpaths = ["tests"]` in `pyproject.toml` will discover it automatically.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing, pyproject.toml configured) |
| Config file | `pyproject.toml` — `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/alpha/ -x -q --no-cov` |
| Full suite command | `pytest tests/alpha/ --cov=src/alpha --cov-fail-under=80` |
| Phase gate command | `pytest tests/alpha/ --cov=src --cov-fail-under=80 && make all` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ALPH-01 | HMM-GARCH fits 3 states, stationarity α+β<1 per state | unit | `pytest tests/alpha/test_regime_detector.py -x` | ❌ Wave 0 |
| ALPH-02 | States sorted by ascending unconditional variance | unit | `pytest tests/alpha/test_regime_detector.py::test_state_ordering -x` | ❌ Wave 0 |
| ALPH-03 | Weekly recalibration produces valid model; Dirichlet smoothing active | unit | `pytest tests/alpha/test_calibration.py -x` | ❌ Wave 0 |
| ALPH-04 | Johansen detects rank-1 on known cointegrated series; 504-bar rolling hedge ratio PiT compliant | unit | `pytest tests/alpha/test_cointegration.py -x` | ❌ Wave 0 |
| ALPH-05 | Z-score fires entry at ±2.0, hard stop at ±4.0; half-life AR(1) matches known coefficient | unit | `pytest tests/alpha/test_cointegration.py::test_zscore_signals -x` | ❌ Wave 0 |
| ALPH-06 | Carry ranking top/bottom quartile correct; spread-filter suppresses where carry < 2×spread | unit | `pytest tests/alpha/test_carry.py -x` | ❌ Wave 0 |
| ALPH-07 | All 27 features finite, PiT (shift verified), 1M bar < 5s | unit + perf | `pytest tests/alpha/test_features.py -x` | ❌ Wave 0 |
| ALPH-08 | Walk-forward 30+ windows; no data leakage; SHAP values sum to output | unit | `pytest tests/alpha/test_walk_forward.py tests/alpha/test_ensemble.py -x` | ❌ Wave 0 |
| ALPH-09 | Orchestrator activates correct engines per regime; Crisis → no signals; hysteresis 20 bars | unit + integration | `pytest tests/alpha/test_orchestrator.py -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/alpha/ -x -q --no-cov` (fast, stops on first failure)
- **Per wave merge:** `pytest tests/alpha/ --cov=src/alpha --cov-fail-under=80`
- **Phase gate:** `pytest tests/alpha/ --cov=src --cov-fail-under=80` + `make all` (ruff + mypy)

### Wave 0 Gaps
- [ ] `tests/alpha/__init__.py` — alpha test package
- [ ] `tests/alpha/test_regime_detector.py` — covers ALPH-01, ALPH-02
- [ ] `tests/alpha/test_calibration.py` — covers ALPH-03
- [ ] `tests/alpha/test_cointegration.py` — covers ALPH-04, ALPH-05
- [ ] `tests/alpha/test_carry.py` — covers ALPH-06
- [ ] `tests/alpha/test_features.py` — covers ALPH-07
- [ ] `tests/alpha/test_walk_forward.py` — covers ALPH-08 (walk-forward structure)
- [ ] `tests/alpha/test_ensemble.py` — covers ALPH-08 (SHAP, probability bounds)
- [ ] `tests/alpha/test_orchestrator.py` — covers ALPH-09
- [ ] shap install: `.venv/bin/pip install shap==0.51.0`
- [ ] Add `shap.*` to mypy overrides in `pyproject.toml`

---

## Sources

### Primary (HIGH confidence)
- Project venv — hmmlearn 0.3.3, arch 8.0.0, statsmodels 0.14.6, xgboost 3.2.0, sklearn 1.8.0 (all verified by import and API inspection)
- `src/backtest/numba_kernels.py` — established `@njit(cache=True)` pattern with `NUMBA_CACHE_DIR`
- `src/backtest/warmup.py` — warmup registration pattern
- `src/data/arctic_store.py` — singleton get_library, reset_store pattern
- `src/execution/swap_rates.py` — `SwapRateCalculator.compute_annualized_carry()` signature and `CarryResult` dataclass
- `.claude/skills/forex/hmm-garch-regime-detector/SKILL.md` — HMM-GARCH implementation reference
- `.claude/skills/forex/alpha-cointegration-carry/SKILL.md` — Johansen + carry implementation reference
- `.claude/skills/forex/ml-price-momentum/SKILL.md` — 27-feature + walk-forward reference
- `_docs/Phase_3_Alpha_Engines.md` — full phase spec with exact parameters

### Secondary (MEDIUM confidence)
- Direct API verification: `xgboost.XGBClassifier.fit()` signature inspected — callbacks not in fit() confirmed
- Direct API verification: `coint_johansen` result attributes and evec shape confirmed on live data
- Direct API verification: arch GARCH parameter names `['mu', 'omega', 'alpha[1]', 'beta[1]']` confirmed
- Direct API verification: `hmmlearn.monitor_.converged` attribute confirmed after `fit()`
- Direct API verification: Numba `np.std`, `np.sign`, `np.log`, array slicing — all compile in njit context

### Tertiary (LOW confidence)
- shap 0.51.0 `shap.Explainer` auto-selection behavior — confirmed by dry-run install metadata only; shap not yet installed in venv

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all library versions verified against project venv
- Architecture: HIGH — matches skill SKILL.md files, phase spec, and existing codebase patterns
- Pitfalls: HIGH — XGBoost breaking change verified by direct TypeError reproduction; all others verified via API inspection or existing code patterns
- SHAP API: MEDIUM — library not installed, behavior documented from shap changelog and spec guidance

**Research date:** 2026-03-22
**Valid until:** 2026-06-22 (stable libraries; XGBoost API stable since 3.0 release)
