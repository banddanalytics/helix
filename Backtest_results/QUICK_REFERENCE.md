# Backtest Results — Quick Reference

**Location:** `/Backtest_results/`

---

## What's In This Directory?

| File | Purpose |
|------|---------|
| `backtest_log.csv` | **Master journal** — append a row each time you run a backtest |
| `VALIDATION_REPORT_*.md` | **Detailed analysis** — diagnostics, cost sensitivity, feature importance |
| `README.md` | **How-to guide** — interpretation, iteration protocol, integration with Phase 4 |

---

## Quick Start: Adding a New Backtest

1. **Run the validation script:**
   ```bash
   cd /home/user/Desktop/Projects/BANDD/helix
   PYTHONPATH=. .venv/bin/python scripts/validate_pipeline.py --pairs EURUSD GBPUSD --months 24
   ```

2. **Extract the metrics** from the output tables

3. **Add a row to `backtest_log.csv`** with the results

4. **Create a new `VALIDATION_REPORT_YYYY-MM-DD.md`** with detailed findings (optional but recommended)

5. **Compare this row to the previous row** — did the change improve or hurt performance?

---

## Reading the Journal: Key Columns

### Performance (what matters most)
- **Net_Sharpe** — Sharpe ratio AFTER spread costs (PRIMARY METRIC)
  - ✅ > 0.5 = viable alpha
  - ⚠️ 0.0 to 0.5 = marginal
  - ❌ < 0.0 = capital destruction

- **Max_Drawdown_Pct** — worst-case peak-to-trough loss
  - ✅ < 20% = acceptable
  - ⚠️ 20-50% = risky
  - ❌ > 50% = catastrophic

- **Win_Rate_Pct** — % of trades that are profitable
  - ✅ > 55% = good
  - ⚠️ 45-55% = marginal
  - ❌ < 45% = signal may be inverted

- **Profit_Factor** — gross wins / |gross losses|
  - ✅ > 1.5 = strong
  - ⚠️ 1.0-1.5 = acceptable
  - ❌ < 1.0 = more losses than wins

### Diagnostics (why performance is what it is)
- **Trades_Per_Bar_Pct** — how often the model generates signals
  - < 5% = high-quality signals
  - 5-20% = normal
  - \> 20% = overtrading (too many low-confidence signals)

- **Stable_Features** — which features matter (from SHAP)
  - If only "mom_*" features: volatility/session/cross-asset features are noise
  - If diverse features: signal is capturing multiple market factors

- **Regime_*_Pct** — market composition during backtest
  - Trending-heavy (>70%): ensure strategy works in trends
  - Balanced: strategy needs to adapt to all regimes

---

## Interpreting Changes

### Scenario 1: You widen signal thresholds (0.53/0.47 → 0.60/0.40)
- ✅ Expected: Fewer trades, higher quality signals
- 📊 Check: Trades_Per_Bar_Pct should ↓, Win_Rate_Pct should ↑
- ⚠️ Risk: May filter out too much, reducing total profit

### Scenario 2: You lengthen training window (756 → 4032 bars)
- ✅ Expected: Model sees more market cycles, better generalization
- 📊 Check: Sharpe should improve, feature stability should increase
- ⚠️ Risk: May overfit to older market regime, fail on new data

### Scenario 3: You activate regime gating (only trade in Trending)
- ✅ Expected: Fewer trades, but higher quality (filtered by regime)
- 📊 Check: Win_Rate_Pct and Profit_Factor should improve
- ⚠️ Risk: May miss profitable signals in other regimes

---

## Example Iteration Log

```
2026-03-22 | Initial (0.53/0.47) | Sharpe: -5.58 | DD: -86% | Trades: 1790 | ❌ FAIL
2026-03-23 | Threshold (0.60/0.40) | Sharpe: -4.20 | DD: -75% | Trades: 800 | ⚠️ IMPROVING
2026-03-24 | Training (4032 bars) | Sharpe: -1.85 | DD: -45% | Trades: 600 | ⚠️ GOOD PROGRESS
2026-03-25 | Multi-bar label (5-bar) | Sharpe: +0.32 | DD: -22% | Trades: 450 | ✅ EDGE!
2026-03-26 | Regime gating + polish | Sharpe: +0.68 | DD: -18% | Trades: 380 | ✅ READY FOR PHASE 4
```

---

## Integration Checkpoints

### Ready for Phase 4 (CVaR, Kelly, Circuit Breakers)?
- [ ] Net_Sharpe > 0.5
- [ ] Max_Drawdown_Pct < 25%
- [ ] Profit_Factor > 1.2
- [ ] Win_Rate_Pct > 50%
- [ ] At least 2 pairs showing consistent edge

### Ready for Shadow Trading (Phase 5)?
- [ ] Phase 4 risk infrastructure deployed
- [ ] CVaR optimization complete
- [ ] Kelly fractional sizing calibrated
- [ ] Circuit breakers tested
- [ ] 3+ pairs showing edge > 1.0 Sharpe
- [ ] Same-month backtest reproduced live

### Ready for Live Trading?
- [ ] 6+ months shadow trading with >80% correlation to backtest
- [ ] All 4 alpha engines contributing positively
- [ ] Maximum drawdown circuit triggered but never exceeded (stress-tested)
- [ ] Regulatory compliance verified (if applicable)
- [ ] Capital requirements met (typically $50K minimum)

---

## Python API: Programmatic Logging

```python
from src.backtest.result_logger import BacktestLogger, BacktestMetrics

logger = BacktestLogger()

# Log a result
metrics = BacktestMetrics(
    pair="EURUSD",
    timeframe="1H",
    data_period_months=18,
    bars_available=9095,
    bars_oos=8064,
    config_train_window=756,
    config_test_window=21,
    config_purge_gap=5,
    config_step=21,
    num_wf_windows=384,
    num_trades=1790,
    trades_per_bar_pct=22.2,
    gross_sharpe=-3.637,
    net_sharpe=-5.581,
    max_drawdown_pct=-86.4,
    win_rate_pct=35.4,
    profit_factor=0.805,
    total_return_pct=-85.1,
    base_spread_pips=0.00012,
    stable_features="mom_1bar,mom_5bar,mom_10bar,mom_22bar,mom_63bar",
    regime_trending_pct=80.3,
    regime_meanrev_pct=12.9,
    regime_volatile_pct=6.8,
    notes="Initial validation run; signal thresholds too tight"
)

logger.log_result(metrics)
```

---

## Troubleshooting

**Q: CSV not formatting correctly in Excel?**
A: Open `backtest_log.csv` in Excel and use Data → Text to Columns to auto-detect delimiter.

**Q: Need to edit an existing row?**
A: Edit `backtest_log.csv` directly. One row per backtest (Date + Pair combo should be unique).

**Q: Where are the Sharpe calculations?**
A: See `src/alpha/ml_price_momentum/evaluation/cost_adjusted_metrics.py` (annualization is configurable by timeframe).

**Q: How do I compare two backtest versions?**
A: Add a `config_version` or `git_hash` note in the Notes column so you can git checkout and reproduce.

---

## Files You'll Modify

- `backtest_log.csv` — append rows here after each run
- `scripts/validate_pipeline.py` — modify signal parameters, features, labels, training windows here
- `src/alpha/ml_price_momentum/models/ensemble.py` — tweak thresholds (0.53/0.47), model params

---

**Last Updated:** 2026-03-23
**Current Status:** Phase 3 Complete — Phase 4 Ready (signal tuning in progress)
