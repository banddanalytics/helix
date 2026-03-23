# Backtest Results Library — Index

**Location:** `/Backtest_results/`
**Purpose:** Complete trading journal and audit trail for Helix algorithmic trading system
**Initialized:** 2026-03-22
**Status:** Active — Ready for iterative backtesting and strategy tuning

---

## 📑 Files at a Glance

| File | Purpose | Audience | When to Use |
|------|---------|----------|------------|
| **backtest_log.csv** | Master trading journal | Traders, analysts | Every backtest run — append a row |
| **README.md** | How-to guide & interpretation | New users | First time setup & methodology |
| **QUICK_REFERENCE.md** | Trader's cheat sheet | Active traders | Daily reference during iterations |
| **VALIDATION_REPORT_2026-03-22.md** | Detailed analysis (initial) | Researchers | Understanding first backtest failure modes |
| **REPORT_TEMPLATE.md** | Template for future reports | Report writers | Creating detailed analysis for each iteration |

---

## 🎯 Quick Navigation

### I Want To...

**...run my first backtest after a code change**
→ Read: `README.md` (Section: "How to Add a New Backtest Row")

**...understand if my changes improved the strategy**
→ Read: `QUICK_REFERENCE.md` (Section: "Reading the Journal: Key Columns")

**...interpret a backtest result**
→ Read: `QUICK_REFERENCE.md` (Section: "Interpreting Changes")

**...see what went wrong with the initial backtest**
→ Read: `VALIDATION_REPORT_2026-03-22.md` (Section: "IV. Diagnosis")

**...log my backtest results programmatically**
→ Use: `src.backtest.result_logger.BacktestLogger` (Python API)

**...create a detailed report for my latest backtest**
→ Use: `REPORT_TEMPLATE.md` as a template, save as `VALIDATION_REPORT_YYYY-MM-DD.md`

**...check if my strategy is ready for Phase 4 (CVaR, Kelly, etc.)**
→ Read: `QUICK_REFERENCE.md` (Section: "Integration Checkpoints")

**...understand the current strategy status**
→ Read: `VALIDATION_REPORT_2026-03-22.md` (Section: "I. Executive Summary")

---

## 📊 Current Status

### Latest Backtest Runs (2026-03-22)

**EURUSD (1H, 18 months)**
- Net Sharpe: **-5.581** ❌
- Max Drawdown: **-86.4%** ❌
- Win Rate: **35.4%** ❌
- Status: **FAILING** — Signal quality needs improvement

**GBPUSD (1H, 18 months)**
- Net Sharpe: **-6.363** ❌
- Max Drawdown: **-75.3%** ❌
- Win Rate: **31.9%** ❌
- Status: **FAILING** — Signal quality needs improvement

### Key Finding
The infrastructure is sound (PiT-compliant backtester, SHAP explainability, cost sensitivity analysis). The strategy fails because:
1. Signals are predictive noise (not genuine market edges)
2. Overtrading (1,790 trades in 8,064 bars)
3. Only momentum features matter; other 22 features are noise
4. Training window too short (756 bars = 1 month for hourly data)

---

## 🔄 Iteration Protocol

For each strategy modification:

1. **Modify** parameters in `scripts/validate_pipeline.py`
2. **Run** backtest: `PYTHONPATH=. .venv/bin/python scripts/validate_pipeline.py --pairs EURUSD GBPUSD --months 24`
3. **Extract** metrics from output
4. **Log** new row in `backtest_log.csv`
5. **Compare** to previous row — improved or regressed?
6. **If improved:** Commit change, repeat step 1
7. **If regressed:** Revert change, try different approach

---

## 📈 Success Criteria for Phase 4 Readiness

| Criterion | Target | Current | Status |
|-----------|--------|---------|--------|
| Net Sharpe | > 0.5 | -5.581 to -6.363 | ❌ FAILING |
| Max Drawdown | < 25% | -75% to -86% | ❌ FAILING |
| Win Rate | > 50% | 32-35% | ❌ FAILING |
| Profit Factor | > 1.2 | 0.76-0.81 | ❌ FAILING |
| 2+ pairs | Viable | 2 pairs failing | ❌ FAILING |

**Verdict:** Strategy requires immediate tuning before Phase 4 development.

---

## 🛠️ Recommended Next Iterations

### Iteration 1: Fix Overtrading
- Widen signal thresholds from 0.53/0.47 to 0.60/0.40
- Expected impact: 60% fewer trades, higher quality signals
- Estimated Sharpe improvement: +1.0 to +2.0

### Iteration 2: Longer Training Window
- Increase training window from 756 to 4,032 bars (1 month → 7 months)
- Expected impact: Better model generalization, capture multiple regimes
- Estimated Sharpe improvement: +0.5 to +1.5

### Iteration 3: Multi-Bar Labels
- Change target from next-bar direction to 5-bar forward return threshold
- Expected impact: Filter noise, capture meaningful moves
- Estimated Sharpe improvement: +0.5 to +1.0

### Iteration 4: Feature Pruning
- Drop 22 non-informative features, keep only 5 momentum features
- Expected impact: Reduced noise, faster training
- Estimated Sharpe improvement: +0.3 to +0.8

### Iteration 5: Regime Gating
- Only trade ML signals in Trending regime (80% of time for EURUSD)
- Expected impact: Conditional alpha, avoid mean-reversion noise in trending market
- Estimated Sharpe improvement: +0.2 to +0.6

---

## 📚 Documentation Index

### Getting Started
- `README.md` — Complete guide to methodology, interpretation, and iteration
- `QUICK_REFERENCE.md` — Cheat sheet for traders and analysts

### Technical Details
- `VALIDATION_REPORT_2026-03-22.md` — Full analysis of initial backtest
- `REPORT_TEMPLATE.md` — Template for creating detailed reports for future iterations

### Data & Results
- `backtest_log.csv` — Master trading journal (25 columns, append-only)

### Python API
- `src/backtest/result_logger.py` — Programmatic backtest logging
- `src/backtest/__init__.py` — Module exports (BacktestLogger, BacktestMetrics)

---

## 🔗 Related Documentation in Project

- `.planning/PROJECT.md` — Project overview and core value proposition
- `.planning/ROADMAP.md` — Phase structure (Phase 3 complete, Phase 4 planned)
- `.planning/phases/03-alpha-engines/03-VERIFICATION.md` — Phase 3 completion verification
- `scripts/validate_pipeline.py` — The backtest runner you'll be modifying
- `src/alpha/ml_price_momentum/models/ensemble.py` — Signal threshold definitions (0.53/0.47)
- `src/alpha/ml_price_momentum/evaluation/cost_adjusted_metrics.py` — Sharpe calculation with configurable timeframe

---

## ✅ Quality Assurance

This backtest library provides:

✅ **Look-ahead bias prevention** — PiT-compliant backtest with purge gaps (5 bars)
✅ **Cost inclusion** — Pair-specific spread costs per bar
✅ **Explainability** — SHAP feature importance per window
✅ **Reproducibility** — Deterministic seed (42), version tracking
✅ **Audit trail** — CSV logging of all runs with configuration
✅ **Cost sensitivity** — Sweep at 6 spread multipliers
✅ **Regime analysis** — Classification and performance breakdown
✅ **Cross-pair correlation** — Diversification assessment

---

## 🚀 Integration with Phase 4

Once strategy achieves **Net Sharpe > 0.5** and **Profit Factor > 1.2**, Phase 4 will add:

- **CVaR risk optimization** — Tail-event quantification
- **Kelly Criterion position sizing** — Dynamic stake adjustment
- **Circuit breakers** — Automated drawdown limits
- **NATS telemetry** — Real-time monitoring dashboard
- **React frontend** — Backtest result visualization

See `README.md` (Section: "Integration with Phase 4") for readiness checklist.

---

## 📞 Support & Questions

**Q: How do I add a new backtest result?**
A: See `README.md` → "How to Add a New Backtest Row"

**Q: What's the difference between Gross and Net Sharpe?**
A: Gross = before spread costs | Net = after spread costs (Net is the realistic metric)

**Q: Can I modify existing rows?**
A: Yes, edit `backtest_log.csv` directly. Keep one row per (Date, Pair) combination.

**Q: Where's the Python logging API?**
A: `src/backtest/result_logger.py` — import `BacktestLogger` and `BacktestMetrics`

**Q: Is this a trading backtest, or something else?**
A: This is a quantitative backtest of the Helix algorithmic trading system. Metrics include Sharpe ratio, drawdown, win rate, and profit factor.

---

## 📝 Version History

| Date | Event |
|------|-------|
| 2026-03-23 | Library initialized with 2 initial backtest runs |
| 2026-03-22 | First backtest runs (EURUSD, GBPUSD) completed |

---

**Owner:** Helix Trading System
**Status:** Active Development
**Managed Since:** 2026-03-22
**Next Review:** After Iteration 1 (signal threshold tuning)
