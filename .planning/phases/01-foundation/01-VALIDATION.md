---
phase: 1
slug: foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-21
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | `pyproject.toml` — Wave 0 installs |
| **Quick run command** | `python3.12 -m pytest tests/ -x -q --no-header` |
| **Full suite command** | `python3.12 -m pytest tests/ --cov=src --cov-report=term-missing --cov-branch --cov-fail-under=80` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python3.12 -m pytest tests/ -x -q --no-header`
- **After every plan wave:** Run `python3.12 -m pytest tests/ --cov=src --cov-report=term-missing --cov-branch --cov-fail-under=80`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 0 | QUAL-01–06 | scaffold | `python3.12 -m pytest tests/ -x -q` | ❌ W0 | ⬜ pending |
| 1-01-02 | 01 | 1 | QUAL-03 | unit | `python3.12 -m pytest tests/test_quality.py -x -q` | ❌ W0 | ⬜ pending |
| 1-01-03 | 01 | 1 | QUAL-04 | unit | `python3.12 -m pytest --cov=src --cov-fail-under=80` | ❌ W0 | ⬜ pending |
| 1-01-04 | 01 | 1 | QUAL-05 | integration | `pre-commit run --all-files` | ❌ W0 | ⬜ pending |
| 1-01-05 | 01 | 1 | QUAL-06 | integration | `cat .github/workflows/ci.yml` | ❌ W0 | ⬜ pending |
| 1-02-01 | 02 | 2 | EXEC-01 | unit | `python3.12 -m pytest tests/test_abstract.py -x -q` | ❌ W0 | ⬜ pending |
| 1-02-02 | 02 | 2 | EXEC-02 | unit | `python3.12 -m pytest tests/test_mt5_adapter.py -x -q` | ❌ W0 | ⬜ pending |
| 1-02-03 | 02 | 2 | EXEC-03 | unit | `python3.12 -m pytest tests/test_sim_adapter.py -x -q` | ❌ W0 | ⬜ pending |
| 1-02-04 | 02 | 2 | EXEC-04 | unit | `python3.12 -m pytest tests/test_spread_model.py -x -q` | ❌ W0 | ⬜ pending |
| 1-02-05 | 02 | 2 | EXEC-05 | unit | `python3.12 -m pytest tests/test_swap_rates.py -x -q` | ❌ W0 | ⬜ pending |
| 1-02-06 | 02 | 2 | EXEC-06 | unit | `python3.12 -m pytest tests/test_lot_sizing.py -x -q` | ❌ W0 | ⬜ pending |
| 1-02-07 | 02 | 3 | EXEC-07 | unit | `python3.12 -m pytest tests/test_bridge.py -x -q` | ❌ W0 | ⬜ pending |
| 1-03-01 | 03 | 1 | QUAL-01 | unit | `python3.12 -m pytest tests/test_ast_validator.py -x -q` | ❌ W0 | ⬜ pending |
| 1-03-02 | 03 | 1 | QUAL-02 | unit | `python3.12 -m pytest tests/test_pit_checker.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/__init__.py` — test package init
- [ ] `tests/conftest.py` — shared fixtures (SimAdapter, mock MT5, ZMQ contexts)
- [ ] `tests/test_abstract.py` — stubs for EXEC-01 abstract interface tests
- [ ] `tests/test_mt5_adapter.py` — stubs for EXEC-02 MT5Adapter tests (mocked MT5)
- [ ] `tests/test_sim_adapter.py` — stubs for EXEC-03 SimAdapter tests
- [ ] `tests/test_spread_model.py` — stubs for EXEC-04 SpreadModel tests
- [ ] `tests/test_swap_rates.py` — stubs for EXEC-05 swap rate tests
- [ ] `tests/test_lot_sizing.py` — stubs for EXEC-06 lot sizing tests
- [ ] `tests/test_bridge.py` — stubs for EXEC-07 ZMQ bridge tests (mocked sockets)
- [ ] `tests/test_ast_validator.py` — stubs for QUAL-01 AST validator tests
- [ ] `tests/test_pit_checker.py` — stubs for QUAL-02 PiT compliance tests
- [ ] `tests/test_quality.py` — stubs for QUAL-03/04 mypy/ruff/coverage tests
- [ ] `pyproject.toml` — pytest, mypy, ruff, coverage config (Wave 0 installs this)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Pre-commit hooks block phantom API call locally | QUAL-05 | Requires git commit attempt with bad code | Stage a file with `mt5.phantom_call()`, run `git commit`, verify hook rejects |
| GitHub Actions CI runs on push | QUAL-06 | Requires GitHub remote push | Push a branch, verify CI workflow triggers and passes in GitHub Actions UI |
| ZMQ bridge live tick stream (deferred) | EXEC-07 | Requires live MT5 node — deferred to go-live | Deferred: test via mocked sockets in Phase 1 |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
