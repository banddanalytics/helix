# Quick Task 260322-uov: Configurable annualization factor

## Task 1: Add timeframe helper, `bars_per_year` parameter, and align tests

**Files:**

- `src/alpha/ml_price_momentum/evaluation/cost_adjusted_metrics.py` (edit)
- `tests/alpha/test_walk_forward.py` (edit)

**Action:**

1. **Helper:** Add `timeframe_to_bars_per_year(timeframe: str) -> int` that normalizes the input (strip, case-fold or map common aliases like `"1D"` / `"1d"` / `"D"`) and returns bars per year for **Forex-style 24h trading days, 5 days/week, ~252 days/year**:
   - `1m` → 252 × 24 × 60 = 362_880  
   - `5m` → 252 × 24 × 12 = 72_576  
   - `15m` → 252 × 24 × 4 = 24_192  
   - `1h` / `60m` → 252 × 24 = 6_048  
   - `4h` → 252 × 6 = 1_512  
   - `1d` / daily → 252  
   Raise a clear `ValueError` (or use a small public `frozenset` of supported keys) for unknown timeframes so misconfiguration fails fast.

2. **Metrics:** Add `bars_per_year: int = 252` to both `gross_sharpe()` and `cost_adjusted_sharpe()`, replacing `np.sqrt(252)` with `np.sqrt(bars_per_year)`. Update module and docstrings to state that annualization is `sqrt(bars_per_year)` and that 252 is the default for **daily** bars.

3. **Tests:** In `test_cost_adjusted_sharpe`, pass an explicit `bars_per_year` (e.g. `252` to preserve current numeric expectations, or derive via `timeframe_to_bars_per_year("1d")`) so the test documents the contract. Optionally add a tiny test that two calls with different `bars_per_year` scale the ratio of Sharpes by `sqrt(bars2/bars1)` for identical returns (optional if timeboxed).

4. **Callers:** Repo search shows **no** `BacktestRunner` or other `src/` usage of these functions today—only `tests/alpha/test_walk_forward.py`. If future walk-forward or runner code is added, it should pass `bars_per_year=timeframe_to_bars_per_year(bar_timeframe)` (or thread a config value). No other files required for this quick task unless new call sites appear.

**Verify:**

- `uv run pytest tests/alpha/test_walk_forward.py::test_cost_adjusted_sharpe -q` (or project’s equivalent test command) passes.
- `uv run ruff check` / `uv run mypy` on touched modules if that is the local gate.
- `grep "np.sqrt(252)" src/alpha/ml_price_momentum/evaluation/cost_adjusted_metrics.py` returns no matches (only `sqrt(bars_per_year)`).

**Done:**

- Sharpe annualization is parameterized; default remains daily-equivalent (252) for backward compatibility.
- Supported timeframe strings map to the agreed Forex 24×252 bars-per-year schedule via `timeframe_to_bars_per_year`.
- Tests exercise the new parameter; documented caller guidance matches actual codebase (tests only for now).
