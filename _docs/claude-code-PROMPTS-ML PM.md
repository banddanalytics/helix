# Implementation Prompts — ML Price Momentum (Non-MBO)

## Claude Code Prompts

### Prompt 1: Forex Feature Engineering Pipeline
```
Build the complete feature engineering pipeline for ML momentum using price/volume
data available from retail Forex brokers.

Requirements:
- 5 feature tiers, all Numba @njit(cache=True) compiled:
  1. Momentum: 1/5/10/22/63/252 bar returns, momentum acceleration, range expansion
  2. Volatility: 5/22/63 bar realized vol, vol ratio, Parkinson vol, vol skew
  3. Session: Asian/London/NY classification, session-relative position, day-of-week
  4. Cross-asset: USD strength, risk appetite proxy, EUR-GBP correlation
  5. Tick volume: relative volume ratio, volume trend, price-volume divergence, spikes
- Feature builder class that assembles all tiers into a single DataFrame
- PiT enforcement: ALL features use .shift(1) — validated by PiT checker
- NaN handling: forward-fill warmup period, drop rows with any NaN before model training
- Feature normalization: rolling z-score with 252-bar lookback (PiT compliant)
- Feature correlation matrix: flag any pair with |corr| > 0.9 for removal

Output: ./alpha-engine/ml_price_momentum/features/ with all modules
Tests:
  - Each feature function compiles under Numba without errors
  - Feature values are finite (no inf, no extreme outliers > 10σ)
  - PiT compliance: feature at time T has no information from T or later
  - 1M bar feature computation completes in < 5 seconds
```

### Prompt 2: Walk-Forward Ensemble (Same Framework, Different Features)
```
Adapt the walk-forward XGBoost/RF ensemble for the Forex feature set.

Requirements:
- Import WalkForwardSplitter, XGBoostModel, RFModel, Ensemble from ml-momentum-orderflow
- Configure for Forex-specific parameters:
  - Longer holding period targets: predict 4h/1d return (not tick-level)
  - Wider train window: 756 bars (3 years) due to weaker signal
  - Monthly retraining step: 22 bars
  - Purge gap: 5 bars (same as futures)
  - Lower signal threshold: Long if P>0.53, Short if P<0.47 (weaker signals)
- Spread-cost-adjusted performance metrics:
  - Sharpe ratio after subtracting median spread per round trip
  - Cost-adjusted IC: multiply signal by (1 - cost_ratio)
- SHAP analysis to identify which of the 5 feature tiers contributes most

Output: ./alpha-engine/ml_price_momentum/models/ with adapted configs
Tests:
  - Walk-forward produces 30+ out-of-sample evaluation windows on 5 years of data
  - Cost-adjusted Sharpe > 0 on at least 60% of windows
  - Feature stability: top 5 SHAP features consistent across >50% of windows
```

## Cursor Prompts

### .cursorrules addition for ML price momentum
```
When working on the ML price momentum engine (non-MBO):
- NEVER implement OFI, VPIN, or any feature requiring Market-by-Order data
- Tick volume is a PROXY — use only for relative comparisons, never absolute
- Session features: use UTC hours, handle DST transitions (US/EU clock changes)
- Cross-asset features: handle missing pairs gracefully (not all brokers offer all pairs)
- Walk-forward windows must be longer than futures (756 bars vs 504) — weaker signals need more data
- Signal thresholds are asymmetric around 0.5 (0.53/0.47) — don't use 0.55/0.45 from futures skill
- Always subtract spread cost before computing Sharpe/IC
- Parkinson volatility: validate high > low (data quality check on broker feed)
```

## Claude CLI Prompts

```bash
# Compare feature quality: Forex vs simulated futures
claude -p "Generate a script that:
1. Loads 5 years of EURUSD data from ArcticDB
2. Computes ALL Forex features (Tiers 1-5 from ml-price-momentum skill)
3. Computes individual feature IC (correlation with next-bar return)
4. Ranks features by |IC| and stability (rolling IC)
5. Identifies the minimum feature set that captures 80% of total ensemble IC
6. Estimates IC improvement if MBO features were added (using literature benchmarks)
Output as markdown table with recommendations." > feature_quality_audit.py
```

```bash
# Backtest Forex ML momentum strategy with realistic costs
claude -p "Generate a full backtest script:
1. Load EURUSD, GBPUSD, AUDUSD, USDJPY, AUDJPY, EURGBP (3 years)
2. Compute all Tier 1-5 features per pair
3. Run walk-forward XGBoost+RF ensemble per pair
4. Apply spread cost model (use 1.5 pip median, 3.0 pip p95 for majors)
5. Apply Kelly sizing with half-Kelly regime adjustment
6. Aggregate portfolio: equal risk contribution across pairs
7. Output: cumulative PnL, Sharpe (gross vs net), max drawdown, cost ratio
8. Compare: strategy with vs without spread adjustment
Save results to ./alpha-engine/ml_price_momentum/backtest_results/" > run_forex_ml_backtest.py
```
