---
phase: 03-alpha-engines
plan: "02"
subsystem: alpha/regime
tags: [hmm-garch, regime-detection, emissions, viterbi, online-filter, tdd]
dependency_graph:
  requires: ["03-01"]
  provides: ["HMMGARCHRegimeDetector", "OnlineRegimeFilter", "GARCHParams", "viterbi_decode"]
  affects: ["03-03", "03-04", "03-05", "03-06", "03-07", "03-08"]
tech_stack:
  added: ["hmmlearn 0.3.3 (GaussianHMM)", "arch 8.0.0 (GARCH fitting)"]
  patterns: ["two-stage HMM-GARCH fit", "log-space Viterbi", "forward-only online filter", "TDD RED-GREEN"]
key_files:
  created:
    - src/alpha/regime/emissions.py
    - src/alpha/regime/viterbi.py
    - src/alpha/regime/hmm_garch.py
    - src/alpha/regime/online_filter.py
  modified:
    - src/alpha/regime/__init__.py
    - tests/alpha/test_regime_detector.py
decisions:
  - "Gaussian fallback for states with < 100 samples — GARCH needs sufficient data for convergence, stationary synthetic fallback with omega=var*0.05, alpha=0.05, beta=0.90 ensures alpha+beta<1"
  - "EM non-convergence does not hard-fail — last fit is used after max_retries seeds; stationarity check downstream still guards"
  - "Log-space fallback in OnlineRegimeFilter.update() handles numerical underflow for low-probability regimes"
metrics:
  duration: "273 seconds (~5 minutes)"
  completed: "2026-03-22T10:21:25Z"
  tasks_completed: 2
  files_created: 4
  files_modified: 2
---

# Phase 3 Plan 2: HMM-GARCH Regime Detector Core — Summary

HMM-GARCH regime detector with two-stage fitting (GaussianHMM + per-state GARCH), GARCH variance recursion emission computation, log-space offline Viterbi decoder, and forward-only online filter returning RegimeState enum values.

## What Was Built

### `src/alpha/regime/emissions.py` (97 lines)
- `GARCHParams` frozen dataclass with `mu`, `omega`, `alpha`, `beta` fields
- `unconditional_variance` property: `omega / (1 - alpha - beta)`
- `is_stationary` property: `alpha + beta < 1.0`
- `garch_emission_prob()`: GARCH(1,1) variance recursion initialized at unconditional variance, returns log emission log-probabilities shape `(T,)`

### `src/alpha/regime/viterbi.py` (60 lines)
- `viterbi_decode()`: log-space Viterbi with delta/psi matrices and backtracking
- Input: `log_emission_probs (T, n_states)`, `log_transmat (n_states, n_states)`, `log_startprob (n_states,)`
- Output: `states np.ndarray (T,)` — optimal state sequence

### `src/alpha/regime/hmm_garch.py` (253 lines)
- `HMMGARCHRegimeDetector` class with two-stage fitting
- Stage 1: `GaussianHMM(n_components=3, covariance_type='diag')` with retry loop (up to `max_retries` seeds)
- Convergence check via `model.monitor_.converged` (underscore — confirmed correct API)
- Stage 2: per-state `arch_model(..., vol='Garch', p=1, q=1).fit(disp='off')` using exact param keys `alpha[1]` and `beta[1]`
- Stationarity gate: rejects entire fit if `alpha + beta >= 1` for any state
- State sorting by ascending `unconditional_variance` — deterministic ordering across refits
- Transition matrix and startprob remapped to match new state ordering
- Gaussian fallback for states with `< min_state_samples (100)` samples
- `predict_viterbi()`: GARCH emission log-probs fed to `viterbi_decode()`
- `get_regime_label()`: maps 0→"TRENDING", 1→"MEAN_REVERTING", 2→"CRISIS"

### `src/alpha/regime/online_filter.py` (151 lines)
- `OnlineRegimeFilter` class — forward algorithm step, no backward pass
- Maintains `_alpha` (normalized forward variable) and `_sigma2` (per-state GARCH conditional variance)
- `update(return_value)`: emission probs → forward step → normalize → update sigma2 → return `(RegimeState, confidence)`
- Log-space fallback for numerical underflow
- `reset()`: re-initializes to startprob and unconditional variances
- `state_probs` property: returns current normalized forward variable

### `tests/alpha/test_regime_detector.py`
- 5 emission/Viterbi tests added (all pass)
- 4 previously-skipped stub tests unstubbed with real implementations (all pass)
- Total: 10 tests passing

## Verification Results

```
pytest tests/alpha/test_regime_detector.py -x -q --no-cov
10 passed, 8 warnings in 1.93s
```

Import check:
```
from src.alpha.regime import HMMGARCHRegimeDetector, OnlineRegimeFilter, GARCHParams, viterbi_decode
# All imports OK
```

## Deviations from Plan

None — plan executed exactly as written. TDD approach followed strictly (RED then GREEN for each task).

One test fix required: `test_garch_emission_prob_matches_scipy` originally asserted `log_probs < 0` but log-probabilities of a tight normal distribution can be positive when the PDF value > 1 (sub-unit sigma). Fixed assertion to check only `np.isfinite(log_probs)`. This was a test correctness fix, not an implementation fix.

## Known Stubs

None — all exported symbols are fully implemented.

## Self-Check: PASSED

Files exist:
- FOUND: src/alpha/regime/emissions.py
- FOUND: src/alpha/regime/viterbi.py
- FOUND: src/alpha/regime/hmm_garch.py
- FOUND: src/alpha/regime/online_filter.py

Commits exist:
- d6696d2 feat(03-02): implement GARCH emissions, Viterbi decoder, and failing tests
- f9a1bd1 feat(03-02): implement HMMGARCHRegimeDetector and OnlineRegimeFilter
