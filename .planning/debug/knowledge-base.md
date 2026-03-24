# GSD Debug Knowledge Base

Resolved debug sessions. Used by `gsd-debugger` to surface known-pattern hypotheses at the start of new investigations.

---

## ml-momentum-inverted-win-rate — ML pipeline producing inverted win rate (~35%) due to 6 interacting bugs
- **Date:** 2026-03-24
- **Error patterns:** win rate, inverted signal, 35% win rate, gross sharpe negative, double spread, look-ahead, feature staleness, train window, regime state, class imbalance, long bias, overfit noise, xgboost, random forest, walk forward, validate_pipeline
- **Root cause:** Three interacting issues: (A) Long bias from bullish training period causing 99% long signals during OOS downtrend — threshold dead zone was too wide (±0.03) for probability clusters near 0.50; (B) 27 features with only 1764 training samples — 22 of 27 features were noise dimensions per SHAP, causing spurious confident predictions that were systematically wrong; (C) Metrics were broken — win_rate counted per-bar PnL including guaranteed-loss entry bars, spread was double-counted in cost_adjusted_metrics, and no classification accuracy diagnostic existed. Earlier bugs: double-shift in FeatureBuilder made features 2-bar stale; binary 1-bar label had 50% class noise; train_window=756 only covered 31 days; regime_state (HMM-GARCH) injected non-deterministic noise.
- **Fix:** BUG1: Remove df.shift(1) from FeatureBuilder.build(). BUG2: Replace binary 1-bar label with 5-bar threshold label. BUG3: Expand train_window to 2016 bars. BUG4: Remove non-deterministic regime_state feature. BUG5: Fix win_rate to trade-level PnL. BUG6: Separate gross_pnl accumulator from net pnl; remove double-counting in cost_adjusted_metrics. BUG7: Add accuracy_score, class balance, and confident-prediction accuracy diagnostics. Round2: Narrow threshold ±0.03→±0.01; subset features to top-5 SHAP-stable momentum; add MIN_HOLD_BARS=5 to match label horizon; regularize XGBoost (max_depth 5→3) and RF (max_depth 7→3, min_samples_leaf 50→200).
- **Files changed:** scripts/validate_pipeline.py, src/backtest/accumulators.py, src/backtest/result_logger.py, src/backtest/engine.py, src/alpha/ml_price_momentum/models/xgboost_model.py, src/alpha/ml_price_momentum/models/rf_model.py, src/alpha/ml_price_momentum/models/ensemble.py, src/alpha/ml_price_momentum/features/builder.py, src/alpha/ml_price_momentum/models/walk_forward.py, tests/backtest/test_accumulators.py, tests/alpha/test_validate_pipeline.py
---
