# PHASE 3: Alpha Engine — Regime Detection, Cointegration, Carry, and ML Momentum

**Duration:** 4-6 weeks
**Dependencies:** Phase 2 (ArcticDB data access and PiT framework)
**Skills Used:** `hmm-garch-regime-detector`, `alpha-cointegration-carry`, `ml-price-momentum`

Phase 3 builds all four alpha generation engines. The regime detector must be built first as it governs which strategies are active. Cointegration, carry, and ML momentum can be developed in parallel after the regime detector is complete, since they share only the data layer (Phase 2) and regime output.

---

## Phase 3A: HMM-GARCH Regime Detector

**Read:** `SKILL.md: hmm-garch-regime-detector`, all sections.
This skill is stage-agnostic — it operates on 1D return arrays from any data source.

---

### Task 3A.1 — Implement HMM-GARCH Regime Detector

**Tool:** Cursor
**Skill Reference:** `hmm-garch-regime-detector > Mathematical Framework, Implementation`

Implement the `HMMGARCHRegimeDetector` class with the two-stage fitting procedure.

**Stage 1 — Base Gaussian HMM:**
- Use `hmmlearn.hmm.GaussianHMM` with `n_components=3`, `covariance_type='diag'`, `n_iter=100`, `tol=0.01`
- Fit on returns reshaped as `(n_samples, 1)` — `model.fit(returns.reshape(-1, 1))`
- Extract initial state assignments via `model.predict()`
- Check convergence via `model.monitor_.converged`
- Retry logic: if EM fails to converge, try up to 5 different `random_state` values

**Stage 2 — Per-state GARCH(1,1):**
- For each state j, extract `returns[states == j]`
- Fit with `arch_model(state_returns, vol='Garch', p=1, q=1, dist='normal').fit(disp='off')`
- Store parameters: `omega = res.params['omega']`, `alpha = res.params['alpha[1]']`, `beta = res.params['beta[1]']`, `mu = res.params['mu']`
- Stationarity check: `alpha + beta < 1` for each state (reject fit if violated)

**GARCH emission probability:**

```
σ²ₜ|ⱼ = ωⱼ + αⱼ · ε²ₜ₋₁ + βⱼ · σ²ₜ₋₁|ⱼ
bⱼ(rₜ) = (1 / √(2π · σ²ₜ|ⱼ)) · exp(-(rₜ - μⱼ)² / (2 · σ²ₜ|ⱼ))
```

**Online prediction (forward algorithm only):**
- No backward pass — suitable for real-time use
- Forward recursion with normalized alpha values to prevent underflow
- Returns: `state_probs[3]`, `current_regime` (int), `label` (string), `confidence` (float)

**Offline Viterbi decoding:**
- Log-space computation throughout
- Returns optimal state sequence for backtest regime labeling

**Regime state definitions:**

| State | Label | Characteristics | Active Strategies (Stage A) |
|-------|-------|-----------------|---------------------------|
| S₀ | Trending | Low vol, persistent direction | ML Price Momentum, Carry |
| S₁ | Mean-Reverting | Moderate vol, oscillation | Cointegration Pairs |
| S₂ | Crisis/Volatile | High vol, fat tails | Reduce exposure only |

**Critical:** Sort states by ascending unconditional variance `ω/(1-α-β)` so state ordering is deterministic across refits.

**Regime switch thresholds:**
- Enter Trending: `P(S₀) > 0.70`
- Enter Mean-Reverting: `P(S₁) > 0.65`
- Enter Crisis: `P(S₂) > 0.60` (lower threshold for faster detection)
- Exit any state: `P(Sᵢ) < 0.30`
- Hysteresis: minimum 20 bars in any state before transition allowed

**Output Files:**

```
src/alpha/regime/__init__.py
src/alpha/regime/hmm_garch.py       # HMMGARCHRegimeDetector class
src/alpha/regime/emissions.py       # GARCH emission PDF computation
src/alpha/regime/online_filter.py   # Forward-only real-time filter
src/alpha/regime/viterbi.py         # Offline log-space Viterbi decoding
tests/alpha/test_regime_detector.py
```

**Validation:**

- [ ] Fitted model identifies 3 distinct states on 5 years of synthetic regime-switching data
- [ ] GARCH stationarity: `α + β < 1` for all states
- [ ] States ordered by ascending unconditional variance (state 0 = lowest vol)
- [ ] Forward-only prediction matches full Viterbi on >90% of data points
- [ ] PiT compliance: `predict_online` uses `.shift(1)` returns as input
- [ ] Convergence retry succeeds on noisy data where first attempt fails
- [ ] Regime switch hysteresis: no state changes within 20-bar dwell period

---

### Task 3A.2 — Regime Recalibration Scheduler

**Tool:** Claude Code
**Skill Reference:** `hmm-garch-regime-detector > Recalibration Schedule`

Implement the recalibration service:

- **Full Baum-Welch:** Weekly (Sunday 00:00 UTC) — complete model re-estimation
- **GARCH update:** Every 1000 bars — exponentially weighted recursive MLE per state
- **Transition matrix smoothing:** Dirichlet prior (concentration=0.01) prevents zero-probability transitions

**Calibration workflow:**
1. Read latest data from ArcticDB `forex_bars` library
2. Fit model using `HMMGARCHRegimeDetector.fit()`
3. Validate stationarity and state ordering
4. Compare new parameters to previous calibration
5. If parameter drift > 50% from previous week → flag WARNING for manual review
6. Save fitted model to ArcticDB `signals` library as `regime_states`

**Output Files:**

```
src/alpha/regime/calibration.py
config/regime_calibration.yaml
tests/alpha/test_calibration.py
```

**Validation:**

- [ ] Weekly recalibration produces valid model on fresh data
- [ ] Dirichlet smoothing: no transition probability is exactly 0
- [ ] Parameter drift > 50% triggers WARNING flag
- [ ] Calibrated model persists to ArcticDB and reloads correctly

---

### Phase 3A Completion Gate

- [ ] Regime detector identifies 3 states on real Forex data (EURUSD 5 years)
- [ ] All GARCH parameters satisfy stationarity constraint
- [ ] Recalibration runs without errors
- [ ] `pytest tests/alpha/test_regime*.py --cov --cov-fail-under=85` passes

---

## Phase 3B: Cointegration and Carry Engines

**Read:** `SKILL.md: alpha-cointegration-carry`, all sections. Pay attention to the dual carry implementation: swap-based (Stage A) and term structure (Stage B).

---

### Task 3B.1 — Implement Johansen Cointegration Engine

**Tool:** Cursor
**Skill Reference:** `alpha-cointegration-carry > Part 1: Cointegration Engine`

**Johansen trace test:**

```python
from statsmodels.tsa.vector_ar.vecm import coint_johansen

def test_cointegration(y1: np.ndarray, y2: np.ndarray) -> dict:
    data = np.column_stack([y1, y2])
    result = coint_johansen(data, det_order=0, k_ar_diff=1)
    
    trace_stat = result.trace_stat[0]
    crit_95 = result.trace_stat_crit_vals[0, 1]
    
    return {
        'cointegrated': trace_stat > crit_95,
        'trace_stat': trace_stat,
        'crit_95': crit_95,
        'hedge_ratio': -result.evec[1, 0] / result.evec[0, 0],
    }
```

**Dynamic hedge ratio (rolling, PiT compliant):**
- Window: 504 bars (2 years), step: 21 bars (monthly)
- Hedge ratio at time T uses data `[T-504, T-1]` only (`.shift(1)` equivalent)

**Spread z-score trading signals:**
- Spread: `z_t = y1_t - β_t × y2_t`
- Z-score: `Z_t = (z_t - μ_z) / σ_z` where μ and σ are rolling on `.shift(1)` data
- Entry: Long spread at `Z < -2.0`, Short spread at `Z > +2.0`
- Exit: Close long at `Z > -0.5`, Close short at `Z < +0.5`
- Hard stop: `|Z| > 4.0` — cointegration breakdown, liquidate immediately

**Half-life monitoring:**
- `HL = -ln(2) / ln(δ)` where δ is AR(1) coefficient: `z_t = δ·z_{t-1} + ε`
- HL > 60 days → reduce position size 50%
- HL > 120 days → close all, re-test Johansen
- Trace stat drops below 10% critical value → suspend pair entirely

**Target Forex pairs for Stage A:**

| Pair | Rationale |
|------|-----------|
| AUDUSD / NZDUSD | Geographic proximity, commodity-export structure, RBNZ/RBA policy divergence |
| EURUSD / GBPUSD | European economic linkage, Brexit-era divergence opportunities |
| USDJPY / USDCHF | Safe-haven pair, risk-on/off correlation |

**Stage A execution note:** These trade as two separate positions (buy one pair, sell the other), so account for two separate spread costs per round trip.

**Output Files:**

```
src/alpha/cointegration/__init__.py
src/alpha/cointegration/johansen.py          # Trace test, rank detection
src/alpha/cointegration/vecm.py              # VECM estimation
src/alpha/cointegration/hedge_ratio.py       # Dynamic rolling hedge ratio
src/alpha/cointegration/spread_signals.py    # Z-score entry/exit logic
src/alpha/cointegration/health_monitor.py    # Half-life, breakdown detection
tests/alpha/test_cointegration.py
```

**Validation:**

- [ ] Johansen test correctly identifies rank=1 on synthetic cointegrated series
- [ ] Hedge ratio converges to true value (within 5%) on synthetic data
- [ ] Z-score entry/exit signals fire at correct thresholds
- [ ] Half-life computation matches known AR(1) coefficient
- [ ] PiT compliance: all rolling computations use `.shift(1)`
- [ ] Hard stop fires at `|Z| > 4.0`

---

### Task 3B.2 — Implement Dual Carry Signal Provider

**Tool:** Cursor
**Skill Reference:** `alpha-cointegration-carry > Part 2: Carry Engine`

**Abstract interface:**

```python
class CarrySignalProvider(ABC):
    @abstractmethod
    def get_carry_signals(self, symbols: list[str]) -> dict[str, float]:
        """Returns {symbol: carry_signal_float}."""
        ...
```

**ForexCarryProvider (Stage A):**
- Calls `compute_annualized_carry(symbol)` from `forex-broker-adapter` skill
- Computes cross-sectional rank across all configured symbols
- Assigns: `+1` for top quartile carry, `-1` for bottom quartile, `0` otherwise
- Filters: suppress symbols where `2 × median_spread > carry_benefit` (spread eats carry)

**FuturesCarryProvider (Stage B — stub):**
- Formula: `carry = (F1/F2 - 1) × 365/(D2 - D1)`
- Stub raises `NotImplementedError` during Stage A

**Output Files:**

```
src/alpha/carry/__init__.py
src/alpha/carry/carry_provider.py     # Abstract CarrySignalProvider
src/alpha/carry/forex_carry.py        # Stage A: swap rate implementation
src/alpha/carry/futures_carry.py      # Stage B: term structure (stub)
tests/alpha/test_carry.py
```

**Validation:**

- [ ] ForexCarryProvider produces correct annualized carry on known swap values
- [ ] Cross-sectional ranking correctly assigns +1/-1/0 positions
- [ ] Spread-cost filter suppresses symbols where carry < 2 × median spread
- [ ] FuturesCarryProvider stub raises `NotImplementedError`

---

### Phase 3B Completion Gate

- [ ] Cointegration engine detects known pairs (AUDUSD/NZDUSD) on real data
- [ ] Carry provider produces valid signals for all configured Forex symbols
- [ ] `pytest tests/alpha/test_cointegration.py tests/alpha/test_carry.py --cov --cov-fail-under=80` passes

---

## Phase 3C: ML Price Momentum Engine

**Read:** `SKILL.md: ml-price-momentum`, all sections. This is the Forex-phase ML engine using 27 features available without order book data.

---

### Task 3C.1 — Build 5-Tier Feature Engineering Pipeline

**Tool:** Cursor
**Skill Reference:** `ml-price-momentum > Feature Tiers 1-5`

All feature functions must be `@njit(cache=True)` compiled. No Python objects on the hot path.

**Tier 1 — Multi-Horizon Return Momentum (8 features):**

| Feature | Formula | PiT |
|---------|---------|-----|
| 1-bar return | `close[i-1] / close[i-2] - 1` | ✅ |
| 5-bar return | `close[i-1] / close[i-6] - 1` | ✅ |
| 10-bar return | `close[i-1] / close[i-11] - 1` | ✅ |
| 22-bar return | `close[i-1] / close[i-23] - 1` | ✅ |
| 63-bar return | `close[i-1] / close[i-64] - 1` | ✅ |
| 252-bar return | `close[i-1] / close[i-253] - 1` | ✅ |
| Momentum acceleration | `mom5 - mom5_prev` | ✅ |
| Range expansion | `recent_range / older_range` | ✅ |

**Tier 2 — Volatility Features (6 features):**

| Feature | Formula | PiT |
|---------|---------|-----|
| 5-bar realized vol | `std(log_returns[i-5:i])` | ✅ (.shift(1) applied in builder) |
| 22-bar realized vol | `std(log_returns[i-22:i])` | ✅ |
| 63-bar realized vol | `std(log_returns[i-63:i])` | ✅ |
| Vol ratio (short/long) | `vol_5 / vol_63` | ✅ |
| Parkinson vol | `sqrt(Σ(ln(H/L))² / (n×4×ln2))` | ✅ |
| Vol of vol | `std(rolling_vol_5_series)` | ✅ |

**Tier 3 — Session Structure (5 features):**

| Feature | Description | PiT |
|---------|-------------|-----|
| Session ID | 0=Asian, 1=London, 2=Overlap, 3=NY | ✅ |
| Bar position | `(close-low)/(high-low)` | ✅ |
| Relative bar size | `bar_range / avg_range_20` | ✅ |
| Day of week | 0=Mon through 4=Fri | ✅ |
| Distance from daily open | `(close - daily_open) / daily_open` | ✅ |

**Tier 4 — Cross-Asset (4 features):**

| Feature | Description | PiT |
|---------|-------------|-----|
| USD strength | Mean return of inverted USD pairs, 5-bar MA | ✅ |
| Risk appetite | `AUD_return + JPY_return`, 10-bar MA | ✅ |
| EUR-GBP correlation | Rolling 20-bar correlation | ✅ |
| Momentum dispersion | Std of 20-bar momentum across pairs | ✅ |

**Tier 5 — Tick Volume (4 features):**

| Feature | Description | PiT |
|---------|-------------|-----|
| Relative tick volume | `current / 20-bar avg` | ✅ |
| Volume trend | `recent_5_avg / older_5_avg` | ✅ |
| Price-volume divergence | `sign(price_change) × sign(vol_change)` | ✅ |
| Volume spike | `1.0 if vol > 2× avg, else 0.0` | ✅ |

**FeatureBuilder class:**
- Assembles all 27 features into single DataFrame
- Applies `.shift(1)` to EVERY feature (PiT compliance)
- Forward-fills NaN for warmup period
- Normalizes via rolling 252-bar z-score (PiT compliant)
- Checks for high correlation: flag pairs with `|corr| > 0.95`

**Output Files:**

```
src/alpha/ml_price_momentum/__init__.py
src/alpha/ml_price_momentum/features/__init__.py
src/alpha/ml_price_momentum/features/momentum.py
src/alpha/ml_price_momentum/features/volatility.py
src/alpha/ml_price_momentum/features/session.py
src/alpha/ml_price_momentum/features/cross_asset.py
src/alpha/ml_price_momentum/features/tick_volume.py
src/alpha/ml_price_momentum/features/builder.py
tests/alpha/test_features.py
```

**Validation:**

- [ ] All 27 features compile under Numba without errors
- [ ] Feature values are finite (no inf, no NaN after warmup period, no extreme outliers > 10σ)
- [ ] PiT: feature at time T computed from data at T-1 or earlier
- [ ] 1M bar feature computation completes in < 5 seconds
- [ ] Feature correlation matrix: no pair with `|corr| > 0.95`

---

### Task 3C.2 — Build Walk-Forward XGBoost/RF Ensemble

**Tool:** Cursor
**Skill Reference:** `ml-price-momentum > Model Architecture, Walk-Forward`

**Walk-forward configuration (adjusted for Forex weaker signals):**

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Train window | 756 bars (3 years) | Longer than futures — weaker signal needs more data |
| Validation | Last 63 bars of train | Early stopping reference |
| Test window | 21 bars (1 month) | Out-of-sample evaluation |
| Purge gap | 5 bars | Prevents label leakage |
| Step | 21 bars | Monthly retraining |

**XGBoost configuration:**

```python
xgb_params = {
    'n_estimators': 500,
    'max_depth': 5,
    'learning_rate': 0.01,
    'subsample': 0.8,
    'colsample_bytree': 0.7,
    'min_child_weight': 100,
    'reg_alpha': 0.1,
    'reg_lambda': 1.0,
    'callbacks': [xgb.callback.EarlyStopping(rounds=50, metric_name='logloss')]
}
```

**Random Forest configuration:**

```python
rf_params = {
    'n_estimators': 1000,
    'max_depth': 7,
    'min_samples_leaf': 50,
    'max_features': 'sqrt',
    'class_weight': 'balanced',
    'n_jobs': -1
}
```

**Ensemble:** `P = 0.5 × P_xgb + 0.5 × P_rf`

**Signal thresholds (wider than futures due to weaker signal):**
- Long: `P > 0.53`
- Short: `P < 0.47`
- Flat: `0.47 ≤ P ≤ 0.53`

**Cost-adjusted metrics per window:**

```python
def cost_adjusted_sharpe(returns, spread_costs):
    net_returns = returns - spread_costs
    return np.mean(net_returns) / max(np.std(net_returns), 1e-10) * np.sqrt(252)
```

**SHAP analysis:**
- Use `shap.Explainer(xgb_model)` — auto-selects `TreeExplainer`
- Compute per-window feature importance
- Track: top 5 features stability across windows (should be consistent >50%)
- Flag: if top features change between windows → possible regime shift

**Output Files:**

```
src/alpha/ml_price_momentum/models/__init__.py
src/alpha/ml_price_momentum/models/xgboost_model.py
src/alpha/ml_price_momentum/models/rf_model.py
src/alpha/ml_price_momentum/models/ensemble.py
src/alpha/ml_price_momentum/models/walk_forward.py
src/alpha/ml_price_momentum/evaluation/__init__.py
src/alpha/ml_price_momentum/evaluation/shap_analysis.py
src/alpha/ml_price_momentum/evaluation/cost_adjusted_metrics.py
tests/alpha/test_walk_forward.py
tests/alpha/test_ensemble.py
```

**Validation:**

- [ ] Walk-forward produces 30+ evaluation windows on 5 years of data
- [ ] No data leakage: test features never appear in train window (purge verified)
- [ ] Ensemble probability bounded in `[0, 1]`
- [ ] Cost-adjusted Sharpe computed correctly (gross Sharpe > net Sharpe)
- [ ] SHAP values sum to model output for each prediction (TreeExplainer identity)
- [ ] Feature stability: top 5 features consistent across >50% of windows

---

## PHASE 3 COMPLETE

**Phase 3 Completion Gate — all must pass before proceeding to Phase 4:**

- [ ] Regime detector identifies 3 states on Forex data with converged EM
- [ ] Cointegration engine detects known cointegrated Forex pairs
- [ ] Carry provider produces correct swap-based carry signals
- [ ] All 27 ML features compile under Numba and pass PiT validation
- [ ] Walk-forward backtest produces out-of-sample results on 5 years of data
- [ ] **Integration test:** regime → strategy selection → signal generation → backtest PnL
- [ ] `pytest tests/alpha/ --cov=src/alpha --cov-fail-under=80` passes
- [ ] All pre-commit hooks pass
- [ ] `make all` passes

**Phase 3 delivers:** Four alpha engines (regime detection, cointegration pairs, carry, ML momentum) all operating on Forex data, reading from ArcticDB through the PiT manager, and producing normalized signals that the risk engine in Phase 4 will consume for position sizing.
