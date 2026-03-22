---
phase: quick
plan: 260322-hyg
type: execute
wave: 1
depends_on: []
files_modified:
  - src/data/bar_aggregator.py
  - tests/data/test_bar_aggregator.py
  - pyproject.toml
  - src/alpha/signal_types.py
  - tests/alpha/__init__.py
  - tests/alpha/conftest.py
  - tests/alpha/test_regime_detector.py
  - tests/alpha/test_calibration.py
  - tests/alpha/test_cointegration.py
  - tests/alpha/test_carry.py
  - tests/alpha/test_features.py
  - tests/alpha/test_walk_forward.py
  - tests/alpha/test_ensemble.py
  - tests/alpha/test_orchestrator.py
autonomous: true
requirements: [ALPH-01, ALPH-02, ALPH-03, ALPH-04, ALPH-05, ALPH-06, ALPH-07, ALPH-08, ALPH-09]
must_haves:
  truths:
    - "shap 0.51.0 is installed and importable in the project venv"
    - "pyproject.toml has shap in mypy overrides"
    - "src/alpha/signal_types.py defines SignalRow, RegimeState, SIGNAL_COLUMNS matching D-01/D-02/D-03"
    - "tests/alpha/ contains 9 test files with xfail stubs covering all ALPH requirements"
    - "pytest tests/alpha/ --collect-only succeeds"
  artifacts:
    - path: "src/alpha/signal_types.py"
      provides: "Signal schema contract for all Phase 3 engines"
      contains: "SignalRow"
    - path: "tests/alpha/conftest.py"
      provides: "Shared fixtures for all alpha engine tests"
      contains: "synthetic_returns"
    - path: "tests/alpha/test_regime_detector.py"
      provides: "ALPH-01, ALPH-02 test stubs"
      contains: "xfail"
  key_links:
    - from: "tests/alpha/conftest.py"
      to: "src/alpha/signal_types.py"
      via: "import for mock_signal_df fixture"
      pattern: "from src.alpha.signal_types import"
---

<objective>
Fix Phase 3 pre-execution blockers: commit pending formatting changes, install shap dependency, create the signal types contract module, and scaffold the entire tests/alpha/ package with xfail stubs for all 9 ALPH requirements.

Purpose: Unblock Phase 3 plan execution by resolving dependency gaps and establishing the test scaffold that all Phase 3 plans will write against.
Output: Committed formatting fixes, shap installed, signal_types.py with SignalRow/RegimeState/SIGNAL_COLUMNS, tests/alpha/ with 9 stub files and conftest.py.
</objective>

<execution_context>
@~/.claude/get-shit-done/workflows/execute-plan.md
@~/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
@.planning/phases/03-alpha-engines/03-CONTEXT.md
@pyproject.toml
@src/alpha/__init__.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Commit formatting changes, install shap, update pyproject.toml</name>
  <files>src/data/bar_aggregator.py, tests/data/test_bar_aggregator.py, pyproject.toml</files>
  <action>
1. Stage and commit the two files with pending ruff formatting changes:
   ```
   git add src/data/bar_aggregator.py tests/data/test_bar_aggregator.py
   git commit -m "style: apply ruff formatting to bar_aggregator and tests"
   ```

2. Install shap 0.51.0 in the project venv:
   ```
   .venv/bin/pip install shap==0.51.0
   ```

3. Add `"shap.*"` to the existing mypy overrides in pyproject.toml. The file already has a `[[tool.mypy.overrides]]` block with a module list — add `"shap.*"` to that list (after `"statsmodels.*"` or at the end). Do NOT create a second overrides block.

4. Verify shap imports:
   ```
   .venv/bin/python -c "import shap; print(shap.__version__)"
   ```
   Expected output: `0.51.0`
  </action>
  <verify>
    <automated>.venv/bin/python -c "import shap; print(shap.__version__)" && grep -q '"shap\.\*"' pyproject.toml && echo "OK"</automated>
  </verify>
  <done>bar_aggregator formatting committed, shap 0.51.0 installed and importable, pyproject.toml updated with shap mypy override</done>
</task>

<task type="auto">
  <name>Task 2: Create signal_types.py and tests/alpha/ scaffold with xfail stubs</name>
  <files>src/alpha/signal_types.py, tests/alpha/__init__.py, tests/alpha/conftest.py, tests/alpha/test_regime_detector.py, tests/alpha/test_calibration.py, tests/alpha/test_cointegration.py, tests/alpha/test_carry.py, tests/alpha/test_features.py, tests/alpha/test_walk_forward.py, tests/alpha/test_ensemble.py, tests/alpha/test_orchestrator.py</files>
  <action>
**Create `src/alpha/signal_types.py`** (per D-01, D-02, D-03 from 03-CONTEXT.md):

```python
"""Signal schema types for Phase 3 alpha engines."""
from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Optional

import numpy as np


class RegimeState(enum.IntEnum):
    """HMM regime states, ordered by ascending unconditional variance."""
    TRENDING = 0
    MEAN_REVERTING = 1
    CRISIS = 2


@dataclass
class SignalRow:
    """Single signal output from any alpha engine (per D-01)."""
    symbol: str
    engine: str
    direction: np.int8          # +1 / 0 / -1
    strength: np.float32        # [0, 1]
    regime: np.int8             # RegimeState value at signal time
    z_score: Optional[np.float32] = None      # cointegration engine
    ml_prob: Optional[np.float32] = None      # ML engine
    carry_rank: Optional[np.float32] = None   # carry engine


SIGNAL_COLUMNS: list[str] = [
    "symbol", "engine", "direction", "strength",
    "regime", "z_score", "ml_prob", "carry_rank",
]

# ArcticDB symbol naming patterns
ENGINE_SYMBOL_PATTERN: str = "{engine}_{symbol}"     # D-02
REGIME_SYMBOL_PATTERN: str = "regime_{symbol}"        # D-03
```

**Create `tests/alpha/__init__.py`** — empty file.

**Create `tests/alpha/conftest.py`** with four fixtures:

- `synthetic_returns`: numpy array of 1000 returns generated from 3 regime-switching normal distributions (low-vol trending: mu=0.0002 sigma=0.005, moderate-vol mean-reverting: mu=0 sigma=0.012, high-vol crisis: mu=-0.001 sigma=0.025). Use np.random.default_rng(42) for reproducibility. Create regime blocks of ~333 bars each by concatenating samples from each distribution.

- `synthetic_bars`: pandas DataFrame with 1000 rows, columns: open, high, low, close, tick_volume, session (int). Use cumulative sum of synthetic_returns for close, derive OHLC from close with random noise. Set index to pd.date_range("2020-01-01", periods=1000, freq="4h"). session cycles 0-3 (Asian/London/Overlap/NY).

- `six_symbol_bars`: dict mapping each of the 6 symbols (EURUSD, GBPUSD, AUDUSD, NZDUSD, USDJPY, USDCHF) to a copy of `synthetic_bars` with slightly different random seeds for each.

- `mock_signal_df`: pandas DataFrame with 10 rows matching SIGNAL_COLUMNS schema from `src.alpha.signal_types`. Import SIGNAL_COLUMNS and use it as column list. Fill with realistic test data (mixed engines, directions, strengths).

**Create 9 test stub files.** Each file should import pytest and contain `@pytest.mark.xfail(reason="Phase 3 not implemented")` decorated test functions. Minimum one test per ALPH requirement the file covers:

1. `test_regime_detector.py`:
   - `test_hmm_identifies_three_states` (ALPH-01)
   - `test_states_sorted_by_ascending_variance` (ALPH-02)

2. `test_calibration.py`:
   - `test_weekly_recalibration_produces_valid_model` (ALPH-03)

3. `test_cointegration.py`:
   - `test_johansen_detects_cointegrated_pair` (ALPH-04)
   - `test_zscore_signals_at_thresholds` (ALPH-05)

4. `test_carry.py`:
   - `test_carry_ranking_and_spread_filter` (ALPH-06)

5. `test_features.py`:
   - `test_27_features_compile_and_pit_compliant` (ALPH-07)

6. `test_walk_forward.py`:
   - `test_walk_forward_produces_oos_windows` (ALPH-08)

7. `test_ensemble.py`:
   - `test_ensemble_probability_bounded` (ALPH-08)
   - `test_shap_values_sum_to_output` (ALPH-08)

8. `test_orchestrator.py`:
   - `test_regime_gates_strategy_activation` (ALPH-09)

Each xfail test body should be a single `assert False, "Not yet implemented"` line. Tests must NOT import any not-yet-existing modules — only pytest and standard library.

**Verify collection:**
```
.venv/bin/pytest tests/alpha/ --collect-only -q
```
Expected: all tests collected, 0 errors.
  </action>
  <verify>
    <automated>.venv/bin/pytest tests/alpha/ --collect-only -q 2>&1 | tail -5</automated>
  </verify>
  <done>signal_types.py exports SignalRow, RegimeState, SIGNAL_COLUMNS, ENGINE_SYMBOL_PATTERN, REGIME_SYMBOL_PATTERN. tests/alpha/ has __init__.py, conftest.py with 4 fixtures, and 9 test files with xfail stubs covering ALPH-01 through ALPH-09. pytest --collect-only passes with 0 errors.</done>
</task>

</tasks>

<verification>
1. `git log --oneline -1` shows formatting commit
2. `.venv/bin/python -c "import shap; print(shap.__version__)"` prints `0.51.0`
3. `grep '"shap\.\*"' pyproject.toml` matches
4. `.venv/bin/python -c "from src.alpha.signal_types import SignalRow, RegimeState, SIGNAL_COLUMNS; print(len(SIGNAL_COLUMNS))"` prints `8`
5. `.venv/bin/pytest tests/alpha/ --collect-only -q` exits 0 with 12+ tests collected
</verification>

<success_criteria>
- Formatting changes committed (clean git status for those 2 files)
- shap 0.51.0 installed and importable
- pyproject.toml has shap in mypy overrides (single overrides block, not duplicated)
- signal_types.py defines SignalRow, RegimeState, SIGNAL_COLUMNS per D-01/D-02/D-03
- tests/alpha/ contains conftest.py + 9 test files, all collectible by pytest
- All xfail stubs reference the correct ALPH requirement IDs
</success_criteria>

<output>
After completion, create `.planning/quick/260322-hyg-fix-phase-3-pre-execution-blockers/260322-hyg-SUMMARY.md`
</output>
