# Quick Task 260322-vf9: Wire SHAP + Validation Script — Summary

**Completed:** 2026-03-22
**Commits:** 6d827db (SHAP wiring), c20af93 (validation script)

## Task 1: Wire SHAP into WalkForwardEngine.run()

### Changes
- **`src/alpha/ml_price_momentum/models/walk_forward.py`**: Added `SHAPAnalyzer` import. Instantiate analyzer once before the loop when `feature_names` is provided. Call `analyzer.analyze_window(ensemble.xgb_model.model, X_test)` per window. Populate `WindowResult.feature_importance` with mean |SHAP| per feature.
- **`tests/alpha/test_walk_forward.py`**: Added `test_shap_populates_feature_importance` (verifies all window results have importance dicts with correct keys and non-negative values) and `test_shap_none_without_feature_names` (verifies backward compat).

### Key Decisions
- SHAPAnalyzer instantiated once outside the loop (stateless except feature names)
- Uses small WalkForwardConfig (train=200, step=80) in tests to keep runtime ~60s
- No changes to WindowResult dataclass or run() signature — fully backward compatible
- Performance: ~50-200ms per window (TreeExplainer on 21 bars × 27 features), negligible

## Task 2: Validation Script + Tests

### `scripts/validate_pipeline.py`
End-to-end pipeline validation with no ArcticDB dependency:
1. **Data pull**: Yahoo Finance via VectorBT Pro (1h bars, configurable pairs/months)
2. **Regime detection**: HMM-GARCH fit + Viterbi decode, regime distribution printed
3. **Feature building**: All 27 features via FeatureBuilder with cross-asset data
4. **Walk-forward**: Default config (756 train, 21 test, 5 purge, 21 step) with SHAP
5. **SHAP stability**: Tracks which features stay in top-5 across >50% of windows
6. **Backtest**: single_pass_backtest with ATR sizing and pair-specific spreads
7. **Metrics**: Gross/Net Sharpe (6048 bars/year), max drawdown, win rate, profit factor
8. **Cost sensitivity**: Sweep at [0.5x, 1x, 1.5x, 2x, 3x, 5x] spread multipliers
9. **Cross-pair correlation**: Pairwise Pearson correlation of OOS predictions

Usage:
```bash
python scripts/validate_pipeline.py
python scripts/validate_pipeline.py --pairs EURUSD GBPUSD AUDUSD --months 24
```

### `tests/alpha/test_validate_pipeline.py`
- `test_cost_sensitivity_monotonic`: 5x spread Sharpe < 0.5x spread Sharpe on synthetic data
- `test_shap_stability_structure`: track_stability() returns correct stable_features and scores
- `test_single_pass_backtest_equity_nonnegative`: Equity stays positive with 1% risk

## Tests
- 10/10 passing in test_walk_forward.py (8 existing + 2 new SHAP)
- 3/3 passing in test_validate_pipeline.py (all new)
