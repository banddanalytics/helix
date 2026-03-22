---
phase: 4
slug: risk-ipc-dashboard
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-22
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (Python risk engine) + vitest (Next.js dashboard) |
| **Config file** | `pytest.ini` / `dashboard/vitest.config.ts` |
| **Quick run command** | `pytest tests/risk/ tests/ipc/ -x -q` |
| **Full suite command** | `pytest tests/ -q && cd dashboard && npm test -- --run` |
| **Estimated runtime** | ~45 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/risk/ tests/ipc/ -x -q`
- **After every plan wave:** Run `pytest tests/ -q && cd dashboard && npm test -- --run`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 45 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 4-01-01 | 01 | 1 | RISK-01 | unit | `pytest tests/risk/test_cvar.py -x -q` | ❌ W0 | ⬜ pending |
| 4-01-02 | 01 | 1 | RISK-01 | unit | `pytest tests/risk/test_cvar.py::test_historical -x -q` | ❌ W0 | ⬜ pending |
| 4-01-03 | 01 | 1 | RISK-01 | unit | `pytest tests/risk/test_cvar.py::test_parametric -x -q` | ❌ W0 | ⬜ pending |
| 4-01-04 | 01 | 1 | RISK-01 | unit | `pytest tests/risk/test_cvar.py::test_cornish_fisher -x -q` | ❌ W0 | ⬜ pending |
| 4-02-01 | 02 | 1 | RISK-02 | unit | `pytest tests/risk/test_kelly.py -x -q` | ❌ W0 | ⬜ pending |
| 4-02-02 | 02 | 1 | RISK-03 | unit | `pytest tests/risk/test_optimizer.py -x -q` | ❌ W0 | ⬜ pending |
| 4-03-01 | 03 | 1 | RISK-04 | unit | `pytest tests/risk/test_circuit_breakers.py -x -q` | ❌ W0 | ⬜ pending |
| 4-03-02 | 03 | 1 | RISK-05 | unit | `pytest tests/risk/test_ect.py -x -q` | ❌ W0 | ⬜ pending |
| 4-04-01 | 04 | 2 | IPC-01 | integration | `pytest tests/ipc/test_nats_publisher.py -x -q` | ❌ W0 | ⬜ pending |
| 4-04-02 | 04 | 2 | IPC-02 | integration | `pytest tests/ipc/test_subjects.py -x -q` | ❌ W0 | ⬜ pending |
| 4-04-03 | 04 | 2 | IPC-03 | integration | `pytest tests/ipc/test_intervals.py -x -q` | ❌ W0 | ⬜ pending |
| 4-05-01 | 05 | 2 | IPC-04 | unit | `cd dashboard && npm test -- --run src/hooks/useNats.test.ts` | ❌ W0 | ⬜ pending |
| 4-05-02 | 05 | 2 | IPC-05 | unit | `cd dashboard && npm test -- --run src/components/ErrorBoundary.test.tsx` | ❌ W0 | ⬜ pending |
| 4-05-03 | 05 | 2 | IPC-06 | unit | `cd dashboard && npm test -- --run src/hooks/useThrottle.test.ts` | ❌ W0 | ⬜ pending |
| 4-06-01 | 06 | 3 | RISK-06 | manual | See Manual-Only Verifications | n/a | ⬜ pending |
| 4-06-02 | 06 | 3 | RISK-07 | unit | `pytest tests/risk/test_circuit_breakers.py::test_l1_l2_l3 -x -q` | ❌ W0 | ⬜ pending |
| 4-06-03 | 06 | 3 | RISK-08 | unit | `pytest tests/risk/test_ect.py::test_recovery_scaling -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/risk/__init__.py` — package init
- [ ] `tests/risk/test_cvar.py` — stubs for RISK-01 (historical, parametric, Cornish-Fisher, spread-adjusted)
- [ ] `tests/risk/test_kelly.py` — stubs for RISK-02 (Kelly fraction computation)
- [ ] `tests/risk/test_optimizer.py` — stubs for RISK-03 (CVXPY weight optimizer, infeasibility fallback)
- [ ] `tests/risk/test_circuit_breakers.py` — stubs for RISK-04, RISK-07 (L1/L2/L3 thresholds)
- [ ] `tests/risk/test_ect.py` — stubs for RISK-05, RISK-08 (ECT sandbox + recovery scaling)
- [ ] `tests/ipc/__init__.py` — package init
- [ ] `tests/ipc/test_nats_publisher.py` — stubs for IPC-01 (NATS JetStream publisher)
- [ ] `tests/ipc/test_subjects.py` — stubs for IPC-02 (7 subjects enumerated)
- [ ] `tests/ipc/test_intervals.py` — stubs for IPC-03 (publish intervals per subject)
- [ ] `dashboard/vitest.config.ts` — vitest config for Next.js (if not present)
- [ ] `dashboard/src/hooks/useNats.test.ts` — stubs for IPC-04 (NATS WebSocket hook)
- [ ] `dashboard/src/components/ErrorBoundary.test.tsx` — stubs for IPC-05 (Module Federation error isolation)
- [ ] `dashboard/src/hooks/useThrottle.test.ts` — stubs for IPC-06 (100ms throttle)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| End-to-end NATS → browser data flow | IPC-01/IPC-04 | Requires live NATS server + browser | Start NATS with WS enabled, run engine, open dashboard, confirm PnL tile updates at ~100ms, positions at ~1s |
| Module Federation: remote crash isolation | IPC-05 | Requires multiple remotes loaded | Load dashboard, use DevTools to block one remote module network request, confirm shell and other remotes remain functional |
| L3 circuit breaker manual restart gate | RISK-06 | Requires UI interaction + state persistence | Trigger 10% drawdown in paper mode, confirm all strategies disabled, confirm "Restart Trading" button appears, confirm restart re-enables strategies |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 45s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
