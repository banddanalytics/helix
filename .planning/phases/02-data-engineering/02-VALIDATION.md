---
phase: 02
slug: data-engineering
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-22
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (installed in venv) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `.venv/bin/pytest tests/data/ tests/backtest/ -x --no-cov` |
| **Full suite command** | `.venv/bin/pytest tests/data/ tests/backtest/ --cov=src --cov-fail-under=85 --cov-branch -v` |
| **Estimated runtime** | ~30s quick / ~90s full |

Note: Phase 2 spec sets **85% coverage threshold** (stricter than project 80% baseline).

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/data/ tests/backtest/ -x --no-cov`
- **After every plan wave:** Run `.venv/bin/pytest tests/data/ tests/backtest/ --cov=src --cov-fail-under=85 --cov-branch -v`
- **Before `/gsd:verify-work`:** Full suite must be green + `make all` passes
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | DATA-01 | unit | `.venv/bin/pytest tests/data/test_arctic_store.py -x` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 1 | DATA-01 | unit | `.venv/bin/pytest tests/data/test_arctic_store.py -x` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 2 | DATA-02 | unit | `.venv/bin/pytest tests/data/test_forex_writer.py -x` | ❌ W0 | ⬜ pending |
| 02-02-02 | 02 | 2 | DATA-02 | unit | `.venv/bin/pytest tests/data/test_forex_writer.py::test_quality_flags -x` | ❌ W0 | ⬜ pending |
| 02-03-01 | 03 | 2 | DATA-03 | unit | `.venv/bin/pytest tests/data/test_bar_aggregator.py -x` | ❌ W0 | ⬜ pending |
| 02-03-02 | 03 | 2 | DATA-03 | unit | `.venv/bin/pytest tests/data/test_bar_aggregator.py::test_session_tags -x` | ❌ W0 | ⬜ pending |
| 02-04-01 | 04 | 2 | DATA-04 | unit | `.venv/bin/pytest tests/data/test_pit_integrity.py::test_pit_read_cutoff -x` | ❌ W0 | ⬜ pending |
| 02-04-02 | 04 | 2 | DATA-04 | unit | `.venv/bin/pytest tests/data/test_pit_integrity.py::test_contemp_ic_violation -x` | ❌ W0 | ⬜ pending |
| 02-05-01 | 05 | 3 | DATA-05 | unit | `.venv/bin/pytest tests/data/test_pit_integrity.py::test_snapshot_isolation -x` | ❌ W0 | ⬜ pending |
| 02-05-02 | 05 | 3 | DATA-05 | unit | `.venv/bin/pytest tests/backtest/test_engine.py::test_reproducibility -x` | ❌ W0 | ⬜ pending |
| 02-06-01 | 06 | 3 | DATA-06 | unit | `.venv/bin/pytest tests/backtest/test_accumulators.py::test_known_pnl -x` | ❌ W0 | ⬜ pending |
| 02-06-02 | 06 | 3 | DATA-06 | unit | `.venv/bin/pytest tests/backtest/test_accumulators.py::test_spread_deduction -x` | ❌ W0 | ⬜ pending |
| 02-07-01 | 07 | 3 | DATA-07 | smoke | `.venv/bin/pytest tests/backtest/test_engine.py::test_warmup_timing -x` | ❌ W0 | ⬜ pending |
| 02-07-02 | 07 | 3 | DATA-07 | smoke | `.venv/bin/pytest tests/backtest/test_engine.py::test_cached_run_timing -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

All test files must be created as stubs (failing tests) before implementation begins:

- [ ] `tests/data/__init__.py` — package init
- [ ] `tests/data/test_arctic_store.py` — covers DATA-01 (6 libraries, round-trip dtypes)
- [ ] `tests/data/test_forex_writer.py` — covers DATA-02 (batch flush, quality flags)
- [ ] `tests/data/test_bar_aggregator.py` — covers DATA-03 (OHLCV, session tags)
- [ ] `tests/data/test_pit_integrity.py` — covers DATA-04, DATA-05 (pit_read cutoff, snapshot isolation)
- [ ] `tests/backtest/__init__.py` — package init
- [ ] `tests/backtest/test_accumulators.py` — covers DATA-06 (known PnL, spread deduction)
- [ ] `tests/backtest/test_engine.py` — covers DATA-05 reproducibility, DATA-07 warmup/cached timing
- [ ] `stubs/numba_stubs.py` — KCH validator will flag `@njit` calls without this stub
- [ ] Install packages: `numba==0.60.0 psutil` + VectorBT Pro wheel (user has license)
- [ ] Extend `Makefile validate` target to scan `src/data/` and `src/backtest/` via pit_validator

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| ArcticDB LMDB creates valid files at ./arctic_data | DATA-01 | Filesystem artifact, not easily asserted in CI | `ls -la arctic_data/` after init |
| Tick writer non-blocking under load | DATA-02 | Requires real async load test | Run MT5 sim at 1000 ticks/s, measure event loop latency |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
