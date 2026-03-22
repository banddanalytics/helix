# Quick Task 260322-uov: Configurable annualization factor — Summary

**Completed:** 2026-03-22
**Commit:** 58536ac

## What Changed

### `src/alpha/ml_price_momentum/evaluation/cost_adjusted_metrics.py`

- Added `_TIMEFRAME_BARS_PER_YEAR` mapping with 10 supported timeframes (1m, 5m, 15m, 30m, 1h, 60m, 4h, 1d, daily, 1w, weekly)
- Added `SUPPORTED_TIMEFRAMES` frozenset for public API
- Added `timeframe_to_bars_per_year(timeframe: str) -> int` helper — case-insensitive, whitespace-stripped, raises `ValueError` on unknown timeframes
- Added `bars_per_year: int = 252` keyword argument to `gross_sharpe()` and `cost_adjusted_sharpe()`
- Replaced all `np.sqrt(252)` with `np.sqrt(bars_per_year)`
- Default remains 252 (daily bars) for backward compatibility

### `src/alpha/ml_price_momentum/evaluation/__init__.py`

- Re-exported `timeframe_to_bars_per_year`, `SUPPORTED_TIMEFRAMES`, `gross_sharpe`, `cost_adjusted_sharpe`

### `tests/alpha/test_walk_forward.py`

- Updated `test_cost_adjusted_sharpe` to use explicit `bars_per_year` via helper
- Added `test_timeframe_to_bars_per_year_known_values` — verifies all Forex timeframe mappings
- Added `test_timeframe_to_bars_per_year_unknown_raises` — verifies ValueError on bad input
- Added `test_sharpe_scales_with_bars_per_year` — verifies Sharpe scales by sqrt(bars2/bars1)

## Bars-Per-Year Schedule (Forex 24h × 252d)

| Timeframe | Bars/Year |
|-----------|-----------|
| 1m | 362,880 |
| 5m | 72,576 |
| 15m | 24,192 |
| 30m | 12,096 |
| 1h | 6,048 |
| 4h | 1,512 |
| 1d | 252 |
| 1w | 52 |

## Tests

6/6 passing in `test_walk_forward.py` (3 existing + 3 new).
