# Backtest Report Template

Use this template for detailed analysis after each backtest iteration. Copy to `VALIDATION_REPORT_YYYY-MM-DD.md` and fill in.

---

## Executive Summary

**Date:** YYYY-MM-DD
**Pairs Tested:** (e.g., EURUSD, GBPUSD)
**Timeframe:** (e.g., 1H)
**Data Period:** X months (YYYY-MM-DD to YYYY-MM-DD)
**Configuration Changes:** (what changed from last iteration)

**Key Finding:**
- [Brief 1-2 sentence summary of performance]
- [Did Sharpe improve/regress?]
- [Is strategy closer to viability?]

---

## Performance Metrics

### EURUSD (1H, 18 months)

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Net Sharpe | X.XXX | > 0.5 | ❌ / ⚠️ / ✅ |
| Max Drawdown | -XX% | < 25% | ❌ / ⚠️ / ✅ |
| Win Rate | XX% | > 50% | ❌ / ⚠️ / ✅ |
| Profit Factor | X.XXX | > 1.2 | ❌ / ⚠️ / ✅ |
| Total Trades | X | <500 ideal | ❌ / ⚠️ / ✅ |
| Gross Sharpe | X.XXX | — | — |
| Total Return | +X% / -X% | — | — |

### GBPUSD (1H, 18 months)

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Net Sharpe | X.XXX | > 0.5 | ❌ / ⚠️ / ✅ |
| Max Drawdown | -XX% | < 25% | ❌ / ⚠️ / ✅ |
| Win Rate | XX% | > 50% | ❌ / ⚠️ / ✅ |
| Profit Factor | X.XXX | > 1.2 | ❌ / ⚠️ / ✅ |
| Total Trades | X | <500 ideal | ❌ / ⚠️ / ✅ |
| Gross Sharpe | X.XXX | — | — |
| Total Return | +X% / -X% | — | — |

---

## What Changed?

### Configuration Modifications

| Parameter | Previous | New | Expected Impact |
|-----------|----------|-----|-----------------|
| Signal threshold (long) | 0.XX | 0.XX | Higher quality signals |
| Training window (bars) | X | X | Better generalization |
| Feature set | X features | X features | Reduced noise / increased signal |
| Label definition | Next-bar direction | X-bar forward | Cleaner target |
| Regime gating | Off | On (Trending only) | Conditional alpha |

### Code Changes

- Modified file A: [brief description]
- Added file B: [brief description]
- Deleted file C: [brief description]

Git commit: `[hash]`

---

## Analysis

### What Worked?

1. [Finding 1 + supporting evidence]
2. [Finding 2 + supporting evidence]

### What Didn't Work?

1. [Finding 1 + supporting evidence]
2. [Finding 2 + supporting evidence]

### SHAP Feature Importance

**Stable features** (present in >50% of walk-forward windows):
- `mom_1bar` — [why it matters]
- `mom_5bar` — [why it matters]
- ...

**Dropped features** (appeared in <25% of windows):
- `vol_*` — Likely noise or redundant
- `session_*` — May not capture true session effects
- `cross_*` — Correlation not predictive

---

## Regime Analysis

### Distribution

| Regime | % of Data | Avg Return | Win Rate | Best For |
|--------|-----------|-----------|----------|----------|
| Trending | XX% | X% | XX% | XGBoost momentum |
| Mean-Reverting | XX% | X% | XX% | Johansen cointegration |
| Volatile | XX% | X% | XX% | None (flat position) |

### Observations

- [Observation 1 about regime classification accuracy]
- [Observation 2 about regime-conditional performance]

---

## Cost Sensitivity

| Spread Mult | 0.5x | 1.0x (base) | 1.5x | 2.0x |
|-------------|------|-----------|------|------|
| Net Sharpe | X.XXX | X.XXX | X.XXX | X.XXX |
| Max DD | -XX% | -XX% | -XX% | -XX% |
| Profit Factor | X.XXX | X.XXX | X.XXX | X.XXX |

**Breakeven Spread:** Strategy breaks even at roughly X.XXX pips (X% of EURUSD typical spread)

---

## Comparison to Previous Iteration

### Previous Run (YYYY-MM-DD)
- Net Sharpe: X.XXX
- Max DD: -XX%
- Win Rate: XX%

### This Run (YYYY-MM-DD)
- Net Sharpe: X.XXX
- Max DD: -XX%
- Win Rate: XX%

### Improvement/Regression
- Sharpe: [+X.XXX ✅ / -X.XXX ❌]
- Drawdown: [+X% better ✅ / -X% worse ❌]
- Win Rate: [+X% ✅ / -X% ❌]

---

## Diagnosis & Root Causes

### If Performance Regressed:

1. **Root Cause 1:** [Analysis]
   - Evidence: [quantitative data]
   - Impact: [effect on overall Sharpe]
   - Fix: [recommendation for next iteration]

2. **Root Cause 2:** [Analysis]
   - Evidence: [quantitative data]
   - Impact: [effect on overall Sharpe]
   - Fix: [recommendation for next iteration]

### If Performance Improved:

1. **Positive Factor 1:** [What worked]
   - Magnitude: [how much it helped]
   - Why: [mechanism]
   - Exploit: [how to maximize this in future]

2. **Positive Factor 2:** [What worked]
   - Magnitude: [how much it helped]
   - Why: [mechanism]
   - Exploit: [how to maximize this in future]

---

## Next Steps

### Immediate (before next run)

- [ ] [Action 1]
- [ ] [Action 2]

### Recommended for Iteration N+1

**Option A:** [Parameter change] — Expected to [improve/test] [metric] by [X%]
**Option B:** [Different parameter change] — Expected to [improve/test] [metric] by [X%]
**Option C:** [Feature modification] — Expected to [improve/test] [metric] by [X%]

**Recommendation:** Try **Option [A/B/C]** first

---

## Phase 4 Readiness Checklist

| Criterion | Status | Notes |
|-----------|--------|-------|
| Net Sharpe > 0.5 | ❌ / ⚠️ / ✅ | Currently X.XXX |
| Max Drawdown < 25% | ❌ / ⚠️ / ✅ | Currently -XX% |
| Profit Factor > 1.2 | ❌ / ⚠️ / ✅ | Currently X.XXX |
| Win Rate > 50% | ❌ / ⚠️ / ✅ | Currently XX% |
| 2+ pairs with edge | ❌ / ⚠️ / ✅ | [Pairs listed] |
| Cost sensitivity < -20% | ❌ / ⚠️ / ✅ | Breakeven at X pips |

**Overall Readiness:** Strategy is [months away / close / ready] for Phase 4 risk infrastructure.

---

## Notes & Observations

- [Any qualitative observations about market regime, data quality, model behavior]
- [Surprises or unexpected findings]
- [Risk factors to watch]

---

**Report Prepared By:** [Name/AI Assistant]
**Date:** YYYY-MM-DD
**Data Source:** Yahoo Finance via VectorBT Pro
**Backtest Engine:** Numba JIT + VectorBT Pro (PiT-compliant)
**Quality Checks:** ✅ Look-ahead bias: None | ✅ Purge gaps: 5 bars | ✅ Coverage: 84%
