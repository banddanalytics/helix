# Phase 03 Deferred Items

## Pre-existing Issues (Out of Scope for Plan 03-08)

### 1. test_feature_computation_performance fails
- **File:** tests/alpha/test_features.py::test_feature_computation_performance
- **Issue:** 1M bar computation took 9.55s, limit is 5s — pre-existing timing issue
- **Scope:** Pre-existing from plan 03-07, not caused by 03-08 changes

### 2. Full phase coverage below 80%
- **Current:** 31.62% total src/alpha coverage
- **Root cause:** ML feature sub-modules (momentum, session, tick_volume, volatility, cross_asset) have 10-18% coverage — tests exist but don't exercise the Numba-compiled paths
- **Scope:** Pre-existing from plans 03-04 through 03-07

