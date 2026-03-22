---
phase: 03-alpha-engines
plan: 07
subsystem: alpha
tags: [xgboost, random-forest, ensemble, walk-forward, shap, cost-adjusted-metrics, ml, momentum]

# Dependency graph
requires:
  - phase: 03-06
    provides: FeatureBuilder.build() producing the 27-feature X matrix for the ensemble

provides:
  - WalkForwardEngine (756-train/21-step/5-purge, 59 windows on 2000 bars)
  - EnsembleModel (0.5*XGB + 0.5*RF, thresholds 0.53/0.47)
  - XGBoostModel (callbacks in constructor, XGBoost 3.x compatible)
  - RFModel (class_weight='balanced')
  - SHAPAnalyzer (TreeExplainer auto-select, per-window importance + stability)
  - cost_adjusted_sharpe / gross_sharpe

affects:
  - phase: 03-08
    note: ML momentum engine is now complete — Phase 08 orchestrator can wire all alpha engines

# Tech stack
tech-stack:
  added:
    - xgboost 3.2.0 (XGBClassifier with EarlyStopping callbacks in constructor)
    - shap 0.51.0 (Explainer auto-selects TreeExplainer for XGBoost)
    - sklearn RandomForestClassifier (class_weight='balanced', n_estimators=1000)
  patterns:
    - Walk-forward cross-validation with embargo (purge gap) to prevent label leakage
    - SHAP identity: shap_values.sum(axis=1) + expected_value == model raw output (logit)
    - 50/50 ensemble blend with directional signal thresholds (0.53 long / 0.47 short)
    - Cost-adjusted Sharpe: sqrt(252) annualisation on net returns after spread deduction

# Key files
key-files:
  created:
    - src/alpha/ml_price_momentum/models/__init__.py
    - src/alpha/ml_price_momentum/models/xgboost_model.py
    - src/alpha/ml_price_momentum/models/rf_model.py
    - src/alpha/ml_price_momentum/models/ensemble.py
    - src/alpha/ml_price_momentum/models/walk_forward.py
    - src/alpha/ml_price_momentum/evaluation/__init__.py
    - src/alpha/ml_price_momentum/evaluation/shap_analysis.py
    - src/alpha/ml_price_momentum/evaluation/cost_adjusted_metrics.py
    - tests/alpha/test_walk_forward.py
    - tests/alpha/test_ensemble.py
  modified: []

# Decisions
decisions:
  - "XGBoost callbacks in constructor (not fit()) — XGBoost 3.x raises TypeError if callbacks passed to fit(); regression-tested in test_xgboost_callbacks_in_constructor"
  - "SHAP identity verified against raw model output (output_margin=True) not probability output — probability output passes through sigmoid making direct SHAP sum comparison invalid"
  - "WalkForwardEngine.n_windows() is a pure function so test_walk_forward_produces_30_windows tests the config math without fitting models (fast)"
  - "SHAPAnalyzer.expected_value normalised from array to scalar via hasattr(__len__) check — shap.Explainer returns array for binary classifiers"

# Metrics
metrics:
  duration_minutes: 91
  completed_date: "2026-03-22"
  tasks_completed: 2
  files_created: 10
  tests_added: 6
  tests_passing: 6
---

# Phase 03 Plan 07: Walk-Forward XGBoost/RF Ensemble Summary

**One-liner:** XGBoost/RF 50/50 ensemble with 756-bar walk-forward (59 windows), SHAP TreeExplainer identity test, and cost-adjusted Sharpe metrics

## What Was Built

The complete ML price momentum model layer:

**Task 1 (committed prior as a2dbf45):** Model wrappers
- `XGBoostModel`: XGBClassifier with `callbacks=[EarlyStopping(rounds=50)]` in the constructor — XGBoost 3.x compatibility constraint enforced and regression-tested
- `RFModel`: RandomForestClassifier with `class_weight='balanced'`, 1000 trees, `max_depth=7`
- `EnsembleModel`: `P = 0.5*P_xgb + 0.5*P_rf`, `generate_signal()` returns 1/−1/0 at 0.53/0.47 thresholds

**Task 2 (committed as 3b1a850):** Walk-forward + evaluation
- `WalkForwardEngine`: 756-bar training window, 63-bar validation tail, 21-bar OOS test, 5-bar purge gap, 21-bar step. Produces 59 windows on 2000 samples (30+ requirement satisfied).
- `SHAPAnalyzer`: `shap.Explainer(xgb_model)` auto-selects TreeExplainer; `analyze_window()` returns `{feature_importance, top_5, expected_value}`; `track_stability()` flags features in top-5 >50% of windows.
- `cost_adjusted_sharpe` / `gross_sharpe`: `sqrt(252)` annualisation; net < gross is mathematically guaranteed when costs > 0.
- Unstubbed `test_walk_forward.py` (3 tests) and `test_ensemble.py` (3 tests) — all 6 passing.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 | a2dbf45 | XGBoost/RF model wrappers and 50/50 ensemble |
| Task 2 | 3b1a850 | Walk-forward engine, SHAP analysis, cost-adjusted metrics, unstub tests |

## Test Results

```
tests/alpha/test_walk_forward.py::test_walk_forward_produces_30_windows  PASSED
tests/alpha/test_walk_forward.py::test_no_data_leakage_purge              PASSED
tests/alpha/test_walk_forward.py::test_cost_adjusted_sharpe               PASSED
tests/alpha/test_ensemble.py::test_ensemble_probability_bounded           PASSED
tests/alpha/test_ensemble.py::test_xgboost_callbacks_in_constructor       PASSED
tests/alpha/test_ensemble.py::test_shap_values_sum_to_output              PASSED

6 passed in 2.92s
```

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written.

**Note:** `test_walk_forward.py` was already fully implemented (no `@pytest.mark.skip`) when Task 2 began — the prior agent completed the test file but left `test_ensemble.py` stubbed. The walk-forward implementation files (`walk_forward.py`, `evaluation/`) were also created but left untracked. Task 2 committed all remaining files and unstubbed `test_ensemble.py`.

## Known Stubs

None — all plan objectives are wired and verified.

## Self-Check: PASSED

Files verified present:
- `src/alpha/ml_price_momentum/models/walk_forward.py` — FOUND
- `src/alpha/ml_price_momentum/evaluation/shap_analysis.py` — FOUND
- `src/alpha/ml_price_momentum/evaluation/cost_adjusted_metrics.py` — FOUND
- `tests/alpha/test_walk_forward.py` — FOUND
- `tests/alpha/test_ensemble.py` — FOUND (0 skips)

Commits verified:
- a2dbf45 — FOUND (Task 1)
- 3b1a850 — FOUND (Task 2)
