---
phase: 3
slug: alpha-engines
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-22
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `pytest tests/alpha/ -x -q` |
| **Full suite command** | `pytest tests/alpha/ --cov=src/alpha --cov-fail-under=80` |
| **Estimated runtime** | ~30 seconds (synthetic data; ML walk-forward uses small windows in tests) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/alpha/ -x -q`
- **After every plan wave:** Run `pytest tests/alpha/ --cov=src/alpha --cov-fail-under=80`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 3-W0-01 | Wave0 | 0 | ALPH-01..09 | setup | `pytest tests/alpha/ --collect-only` | ❌ W0 | ⬜ pending |
| 3-01-01 | 01 | 1 | ALPH-01,02 | unit | `pytest tests/alpha/test_regime_detector.py -x -q` | ❌ W0 | ⬜ pending |
| 3-01-02 | 01 | 1 | ALPH-01,02 | unit | `pytest tests/alpha/test_regime_detector.py::test_state_ordering -x` | ❌ W0 | ⬜ pending |
| 3-01-03 | 01 | 1 | ALPH-01 | unit | `pytest tests/alpha/test_regime_detector.py::test_garch_stationarity -x` | ❌ W0 | ⬜ pending |
| 3-02-01 | 02 | 1 | ALPH-03 | unit | `pytest tests/alpha/test_calibration.py -x -q` | ❌ W0 | ⬜ pending |
| 3-03-01 | 03 | 2 | ALPH-04,05 | unit | `pytest tests/alpha/test_cointegration.py -x -q` | ❌ W0 | ⬜ pending |
| 3-03-02 | 03 | 2 | ALPH-05 | unit | `pytest tests/alpha/test_cointegration.py::test_zscore_thresholds -x` | ❌ W0 | ⬜ pending |
| 3-04-01 | 04 | 2 | ALPH-06 | unit | `pytest tests/alpha/test_carry.py -x -q` | ❌ W0 | ⬜ pending |
| 3-05-01 | 05 | 2 | ALPH-07 | unit | `pytest tests/alpha/test_features.py -x -q` | ❌ W0 | ⬜ pending |
| 3-05-02 | 05 | 2 | ALPH-07 | perf | `pytest tests/alpha/test_features.py::test_1m_bar_perf -x` | ❌ W0 | ⬜ pending |
| 3-06-01 | 06 | 2 | ALPH-08 | unit | `pytest tests/alpha/test_walk_forward.py -x -q` | ❌ W0 | ⬜ pending |
| 3-06-02 | 06 | 2 | ALPH-08 | unit | `pytest tests/alpha/test_ensemble.py -x -q` | ❌ W0 | ⬜ pending |
| 3-07-01 | 07 | 3 | ALPH-09 | integration | `pytest tests/alpha/test_orchestrator.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/alpha/__init__.py` — create tests/alpha/ package
- [ ] `tests/alpha/conftest.py` — shared fixtures: synthetic regime-switching data, synthetic cointegrated series, mock ArcticDB store, bar DataFrames for 6 symbols
- [ ] `tests/alpha/test_regime_detector.py` — stubs for ALPH-01, ALPH-02
- [ ] `tests/alpha/test_calibration.py` — stubs for ALPH-03
- [ ] `tests/alpha/test_cointegration.py` — stubs for ALPH-04, ALPH-05
- [ ] `tests/alpha/test_carry.py` — stubs for ALPH-06
- [ ] `tests/alpha/test_features.py` — stubs for ALPH-07 (includes 1M bar perf test)
- [ ] `tests/alpha/test_walk_forward.py` — stubs for ALPH-08 walk-forward
- [ ] `tests/alpha/test_ensemble.py` — stubs for ALPH-08 ensemble + SHAP
- [ ] `tests/alpha/test_orchestrator.py` — stubs for ALPH-09 regime gating integration
- [ ] `pip install shap==0.51.0` + add to `pyproject.toml` dependencies
- [ ] Add `shap.*` to mypy `[[tool.mypy.overrides]]` with `ignore_missing_imports = true`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| HMM converges on real EURUSD 5yr data | ALPH-01 | Requires real ArcticDB data; synthetic only in CI | Run `python -m src.alpha.regime.hmm_garch` with EURUSD bars loaded; inspect `monitor_.converged` |
| Weekly recalibration produces valid model | ALPH-03 | Scheduler runs on Sunday 00:00 UTC wall clock | Manually trigger `RecalibrationService.run_calibration()` and verify ArcticDB write to `signals` library |
| Cointegration detects AUDUSD/NZDUSD on real data | ALPH-04 | Requires real 5yr data in ArcticDB | Run `python -m src.alpha.cointegration.johansen` on live ArcticDB; verify trace_stat > crit_95 |
| ML walk-forward produces 30+ windows on 5yr data | ALPH-08 | Full run ~minutes; CI uses small synthetic window | Run `BacktestRunner` with 5yr EURUSD snapshot; count OOS windows in output |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
