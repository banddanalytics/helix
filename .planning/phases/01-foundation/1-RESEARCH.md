# Phase 1: Foundation - Research

**Researched:** 2026-03-21
**Domain:** CI/CD quality pipeline + broker-agnostic execution abstraction (Python 3.12, pytest, mypy, ruff, ZeroMQ, pre-commit, GitHub Actions)
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Python 3.12 via deadsnakes PPA (`/usr/bin/python3.12`) — already installed on the Linux machine
- **D-02:** All project venvs use Python 3.12. System Python (3.10) stays untouched
- **D-03:** pyproject.toml is the single source of truth for all tool configuration (pytest, mypy, ruff, coverage)
- **D-04:** Full `src/` tree scaffolded in Phase 1 — all directories created with `__init__.py` stubs and `# TODO: Phase N` placeholders
- **D-05:** Directory layout: `src/execution/`, `src/data/`, `src/alpha/`, `src/risk/`, `src/ipc/` — matches phase boundaries exactly
- **D-06:** `src/bridge/` created for ZeroMQ bridge code (Windows publisher + Linux consumer)
- **D-07:** Pre-commit runs ruff (lint + format) and mypy only — target under 10 seconds total
- **D-08:** pytest and coverage do NOT run in pre-commit — CI only
- **D-09:** AST/KCH hallucination detector does NOT run in pre-commit — CI only (needs full codebase scan)
- **D-10:** `--no-verify` is a documented escape hatch; commits using it are flagged visibly in git log
- **D-11:** CI gate order: static analysis (ruff + mypy) → AST/KCH hallucination detection → PiT compliance check → unit tests → coverage enforcement
- **D-12:** Coverage enforced at 80% as a merge gate — CI fails below this threshold
- **D-13:** Linux-only CI runner (no Windows runner needed — MT5 tested via mocks and SimAdapter)
- **D-14:** GitHub Actions workflow file at `.github/workflows/ci.yml`
- **D-15:** Custom AST validator scans for phantom API calls against a whitelist of known-valid MT5 API methods
- **D-16:** Runs on full codebase in CI, not on partial staged files
- **D-17:** PiT compliance checker is a separate validator — scans alpha code for look-ahead bias patterns
- **D-18:** Three abstract base classes: `MarketDataProvider`, `OrderExecutor`, `PositionManager` — defined in `src/execution/abstract.py`
- **D-19:** `MT5Adapter` implements all three interfaces with async wrappers (`asyncio.to_thread()` around MT5's synchronous API)
- **D-20:** `SimAdapter` implements all three interfaces — no Windows dependency, safe for CI and backtesting
- **D-21:** Calling code throughout the project NEVER imports from `mt5_adapter.py` directly — always typed against the ABCs
- **D-22:** Instant fill — orders are accepted immediately at the requested price
- **D-23:** Spread cost IS applied on every fill using `SpreadModel` — backtests are honest from day one
- **D-24:** No slippage simulation in Phase 1 — realistic slippage requires tick data (Phase 2)
- **D-25:** SimAdapter is stateful — maintains virtual account balance and open position ledger
- **D-26:** SimAdapter uses a fixed random seed — deterministic fills, reproducible CI runs
- **D-27:** Basic rejection logic included: insufficient margin, invalid lot size (matches real broker behaviour)
- **D-28:** `SpreadModel` tracks empirical spread distribution per symbol and suppresses signals where spread > 50% of expected profit
- **D-29:** `LotSizer` converts Kelly fraction to MT5 lots respecting `volume_min`, `volume_max`, `volume_step`
- **D-30:** `SwapRates` module extracts annualized carry for all configured symbols — used by Phase 3 carry engine
- **D-31:** Bridge code is written and unit tested in Phase 1 (mocked sockets)
- **D-32:** Live end-to-end bridge testing (real MT5 → real tick stream) is DEFERRED to go-live
- **D-33:** Windows side: ZMQ PUB on port 5556 (ticks), 5557 (bars); PULL on 5558 (order requests); PUSH on 5559 (order results)
- **D-34:** Message serialization: MessagePack (faster than JSON, schema-flexible)
- **D-35:** Linux consumer reconnects automatically on disconnection and stops signal generation on stale data
- **D-36:** WireGuard VPN setup between Linux laptop and Windows MT5 node is DEFERRED to go-live
- **D-37:** MT5 node decision (Beelink mini PC vs Windows VM on laptop) is DEFERRED to go-live

### Claude's Discretion

- Exact pre-commit hook configuration syntax
- mypy ignore list for third-party stubs (MetaTrader5, hmmlearn, arch, vectorbt, arcticdb)
- Compression and temp file handling in bridge
- Progress reporting format in CI logs

### Deferred Ideas (OUT OF SCOPE)

- WireGuard VPN setup — deferred to go-live; bridge code written in Phase 1 but not live-tested
- MT5 node decision (Beelink vs VM) — deferred to go-live; doesn't affect Phase 1 code
- Live end-to-end bridge testing — deferred to go-live; Phase 1 exit criterion is unit tests passing with mocked sockets
- Slippage simulation in SimAdapter — Phase 2, when ArcticDB tick data is available
- Windows CI runner — not needed; MT5 always mocked in CI via SimAdapter
- Stage B infrastructure (CMEAdapter, iLink 3.0) — Phase 5 only
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| QUAL-01 | CI/CD pipeline runs AST/KCH hallucination detection on every commit | Custom AST validator in `src/quality/ast_validator/`; runs in GitHub Actions static-analysis job |
| QUAL-02 | Point-in-Time compliance validator catches look-ahead bias in alpha code | `src/quality/pit_validator.py`; AST + IC + temporal-shuffle detection; runs in CI static-analysis job |
| QUAL-03 | mypy strict + ruff linting pass on all source code | `pyproject.toml` configures both; ruff-pre-commit + mirrors-mypy hooks for local; CI runs on ubuntu-latest |
| QUAL-04 | Test coverage ≥ 80% enforced as a merge gate | `--cov-fail-under=80` in pytest addopts; CI `tests` job blocks merge below threshold |
| QUAL-05 | Pre-commit hooks run all quality gates locally before push | `.pre-commit-config.yaml` with ruff + mypy only (fast gates); AST/KCH/PiT in CI only per D-08/D-09 |
| QUAL-06 | GitHub Actions CI runs static analysis → unit tests → e2e in sequence | Three-job pipeline: `static-analysis` → `tests` → `e2e`; NATS service container for tests job |
| EXEC-01 | Abstract interfaces (MarketDataProvider, OrderExecutor, PositionManager) define broker-agnostic contract | `src/execution/abstract.py`; all methods `@abstractmethod`; no broker-specific concepts in ABCs |
| EXEC-02 | MT5Adapter implements all three interfaces with async wrappers | `src/execution/mt5_adapter.py`; `asyncio.to_thread()` wraps synchronous MT5 API; mocked in CI |
| EXEC-03 | SimAdapter provides identical interface for backtesting without Windows dependency | `src/execution/sim_adapter.py`; stateful, fixed-seed, instant-fill with spread cost; Phase 1 has no ArcticDB yet — uses in-memory price data |
| EXEC-04 | SpreadModel tracks empirical spread distribution and suppresses signals where spread > 50% expected profit | `src/execution/spread_model.py`; `cost_adjusted_signal()` method; `median`, `p95`, `volatility` properties |
| EXEC-05 | Swap rate extraction computes annualized carry for all configured symbols | `src/execution/swap_rates.py`; formula: `(swap_points × point × 365) / mid_price × 100`; normalized carry_signal |
| EXEC-06 | Lot sizing converts Kelly fraction to MT5 lots respecting volume_min/max/step | `src/execution/lot_sizing.py`; handles currency conversion when profit_currency ≠ account_currency |
| EXEC-07 | ZeroMQ bridge streams ticks/bars from Windows MT5 to Linux engines over WireGuard | `src/execution/bridge/`; PUB/SUB + PUSH/PULL; MessagePack; auto-reconnect; tested with mocked sockets in Phase 1 |
</phase_requirements>

---

## Summary

Phase 1 builds two independent but mutually reinforcing systems. Phase 1A creates the CI/CD quality pipeline — the AST/KCH hallucination detector, PiT compliance validator, mypy/ruff linting, coverage enforcement, pre-commit hooks, and GitHub Actions workflow. Phase 1B creates the broker-agnostic execution abstraction layer — three ABCs, MT5Adapter, SimAdapter, SpreadModel, lot sizing, swap rate extraction, and the ZeroMQ bridge.

The critical environment fact discovered during research: the tools documented as "already installed" (pytest 9.0.2, mypy 1.19.1, ruff 0.15.7, pyzmq 27.1.0, arcticdb 6.10.2, nats-py 2.14.0, coverage 7.13.5, msgpack 1.1.2, hmmlearn 0.3.3, arch 8.0.0, xgboost 3.2.0, statsmodels 0.14.6, cvxpy 1.7.5, numpy 1.26.3, pandas 2.2.0) are installed for **Python 3.10** (`pip3`), not Python 3.12. The project must create a Python 3.12 virtualenv and reinstall or pip-install these packages into it. `hypothesis` and `pre-commit` are not installed at all. `ruff` is available as a system binary at version 0.15.7.

The SimAdapter in Phase 1 has a subtle design constraint: it is specified to read from ArcticDB (D-25), but ArcticDB setup is Phase 2. The planner must decide whether SimAdapter Phase 1 implementation uses in-memory synthetic price data or a minimal ArcticDB stub. Based on the skill reference, the constructor takes an `arctic_store` parameter — the Phase 1 implementation should accept `None` or a mock store and use synthetic in-memory data for Phase 1 tests, with full ArcticDB integration wired in Phase 2.

**Primary recommendation:** Create the Python 3.12 venv first (Task 1A.1), install all tools into it, then proceed with quality infrastructure and execution abstraction. Every file must pass mypy strict from the moment it is created.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.12.13 | Runtime | Already at `/usr/bin/python3.12`; matches project decision D-01 |
| pytest | 9.0.2 | Test runner | Installed for Python 3.10; must reinstall in Python 3.12 venv |
| pytest-cov | 7.0.0 | Coverage plugin | Already installed for Python 3.10 |
| pytest-asyncio | 1.3.0 | Async test support | Required for testing async ABC methods; installed for Python 3.10 |
| pytest-mock | 3.15.1 | Mock fixtures | Cleaner mock API than unittest.mock; installed for Python 3.10 |
| mypy | 1.19.1 | Static type checking | Installed for Python 3.10; strict mode mandated by D-03 |
| ruff | 0.15.7 | Linting + formatting | System binary available; also installed for Python 3.10 |
| coverage | 7.13.5 | Branch coverage | `branch = true` in config; installed for Python 3.10 |
| pyzmq | 27.1.0 | ZeroMQ messaging | Bridge PUB/SUB/PUSH/PULL; installed for Python 3.10 |
| msgpack | 1.1.2 | Message serialization | Bridge serialization (D-34); installed for Python 3.10 |
| arcticdb | 6.10.2 | Time-series DB | Phase 2 primary; imported as stub in Phase 1; installed for Python 3.10 |
| nats-py | 2.14.0 | NATS messaging | Phase 4 primary; stub in Phase 1; installed for Python 3.10 |
| numpy | 1.26.3 | Array types | datetime64 used in all dataclasses; installed for Python 3.10 |
| pandas | 2.2.0 | DataFrames | Used in PiT validator IC analysis; installed for Python 3.10 |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| hypothesis | NOT INSTALLED | Property-based testing | `tests/properties/` directory; install in venv setup |
| pre-commit | NOT INSTALLED | Local git hook runner | `.pre-commit-config.yaml` execution; install via pip in venv |
| pandas-stubs | NOT INSTALLED | mypy pandas type stubs | Required for `mypy --strict` on pandas code; install in venv |
| types-requests | NOT INSTALLED | mypy requests stubs | Needed if any HTTP in bridge; install in venv |
| hmmlearn | 0.3.3 | HMM models | Phase 3; stub in Phase 1 AST stubs |
| arch | 8.0.0 | GARCH models | Phase 3; stub in Phase 1 AST stubs |
| xgboost | 3.2.0 | ML ensemble | Phase 3; stub in Phase 1 AST stubs |
| statsmodels | 0.14.6 | Johansen cointegration | Phase 3; stub in Phase 1 AST stubs |
| cvxpy | 1.7.5 | Convex optimization | Phase 4; stub in Phase 1 AST stubs |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| ruff | flake8 + isort + black | ruff replaces all three in one tool; 10-100x faster |
| msgpack | JSON, protobuf | msgpack is faster than JSON; simpler than protobuf for this use case |
| pytest-asyncio | anyio + pytest-anyio | pytest-asyncio is simpler for asyncio-only code |

**Installation (into Python 3.12 venv):**
```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install pytest==9.0.2 pytest-cov==7.0.0 pytest-asyncio==1.3.0 pytest-mock==3.15.1
pip install mypy==1.19.1 ruff==0.15.7 coverage==7.13.5
pip install pyzmq==27.1.0 msgpack==1.1.2 numpy==1.26.3 pandas==2.2.0
pip install arcticdb==6.10.2 nats-py==2.14.0
pip install hypothesis pre-commit pandas-stubs
pip install hmmlearn==0.3.3 arch==8.0.0 xgboost==3.2.0 statsmodels==0.14.6 cvxpy==1.7.5
```

**Version note:** All versions verified against `pip3 list` output (Python 3.10 system install reflects what was tested). The Python 3.12 venv should pin these same versions for reproducibility.

---

## Architecture Patterns

### Recommended Project Structure

```
helix/
├── src/
│   ├── execution/          # Phase 1B: abstraction layer
│   │   ├── __init__.py
│   │   ├── abstract.py     # ABCs + dataclasses
│   │   ├── mt5_adapter.py  # MT5 concrete implementation
│   │   ├── sim_adapter.py  # Simulation adapter
│   │   ├── spread_model.py # Variable spread tracking
│   │   ├── swap_rates.py   # Carry signal from swaps
│   │   ├── lot_sizing.py   # Kelly → MT5 lots
│   │   └── bridge/
│   │       ├── __init__.py
│   │       ├── windows_publisher.py
│   │       ├── linux_consumer.py
│   │       └── message_schemas.py
│   ├── data/               # Phase 2: __init__.py stub only
│   ├── alpha/              # Phase 3: __init__.py stub only
│   │   ├── regime/
│   │   ├── cointegration/
│   │   ├── carry/
│   │   ├── ml_price_momentum/
│   │   └── ml_mbo_orderflow/   # Stage B only
│   ├── risk/               # Phase 4: __init__.py stub only
│   ├── ipc/                # Phase 4: __init__.py stub only
│   └── quality/            # Phase 1A: validators
│       ├── __init__.py
│       ├── pit_validator.py
│       └── ast_validator/
│           ├── __init__.py
│           ├── extractor.py
│           ├── validator.py
│           └── stub_generator.py
├── tests/
│   ├── conftest.py         # Shared fixtures + pit_check marker
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   ├── properties/         # Hypothesis property-based tests
│   ├── execution/          # test_abstract.py, test_mt5_adapter.py, etc.
│   │   └── bridge/
│   └── quality/            # test_ast_extractor.py, etc.
├── stubs/                  # KCH validation ground-truth stubs
│   ├── mt5_stubs.py
│   ├── arcticdb_stubs.py
│   ├── zmq_stubs.py
│   ├── nats_stubs.py
│   ├── xgboost_stubs.py
│   ├── hmmlearn_stubs.py
│   ├── arch_stubs.py
│   └── statsmodels_stubs.py
├── scripts/
│   ├── ast_validator.py    # CLI entry point
│   └── pit_validator.py    # CLI entry point
├── config/
├── infra/
├── .venv/                  # Python 3.12 virtualenv
├── .pre-commit-config.yaml
├── .github/
│   └── workflows/
│       └── ci.yml
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── .python-version         # "3.12"
└── Makefile
```

### Pattern 1: Abstract Base Class Hierarchy

**What:** Three separate ABCs (`MarketDataProvider`, `OrderExecutor`, `PositionManager`). Concrete adapters inherit all three. Calling code type-hints against individual ABCs.

**When to use:** All execution-touching code — alpha engines, risk engine, dashboard.

**Example:**
```python
# Source: .claude/skills/forex/forex-broker-adapter/SKILL.md
from abc import ABC, abstractmethod
import numpy as np

class MarketDataProvider(ABC):
    @abstractmethod
    async def get_ticks(self, symbol: str, start: np.datetime64,
                        end: np.datetime64) -> list[Tick]: ...
    @abstractmethod
    async def get_bars(self, symbol: str, timeframe: str,
                       count: int) -> list[Bar]: ...
    @abstractmethod
    async def subscribe_ticks(self, symbol: str,
                              callback: callable) -> None: ...
    @abstractmethod
    async def get_symbols(self) -> list[str]: ...

class MT5Adapter(MarketDataProvider, OrderExecutor, PositionManager):
    # All MT5 synchronous calls wrapped in asyncio.to_thread()
    async def get_account_equity(self) -> float:
        return await asyncio.to_thread(lambda: mt5.account_info().equity)
```

### Pattern 2: AST Validation Pipeline

**What:** Four-stage pipeline: extract API calls from source → compare against ground-truth stubs → report violations → auto-generate stubs from installed libraries.

**When to use:** CI gate for all Python files; run against full `src/` not staged files.

**Example:**
```python
# Source: .claude/skills/forex/ast-tdd-validation/SKILL.md
class ASTExtractor(ast.NodeVisitor):
    def visit_Call(self, node):
        if isinstance(node.func, ast.Attribute):
            self.function_calls.append({
                'func': node.func.attr,
                'kwargs': {kw.arg for kw in node.keywords},
                'lineno': node.lineno
            })
        self.generic_visit(node)

# KCH example: arcticdb.Library.upsert() does NOT exist
# validator catches this as PHANTOM_FUNCTION → CRITICAL → blocks merge
```

### Pattern 3: ZeroMQ PUB/SUB + PUSH/PULL Bridge

**What:** Four sockets — two PUB sockets (ticks/bars out), one PULL (orders in), one PUSH (results out). MessagePack serialization. Topic prefix for symbol filtering.

**When to use:** All tick/bar data from Windows MT5 to Linux engines.

**Example:**
```python
# Source: _docs/Phase_1_Foundation.md §Task 1B.6
# Windows publisher
ctx = zmq.Context()
tick_pub = ctx.socket(zmq.PUB)
tick_pub.bind("tcp://*:5556")
# Topic-prefix filtering: "EURUSD " + msgpack.packb(tick_dict)
tick_pub.send_multipart([b"EURUSD", msgpack.packb(tick_dict)])

# Linux consumer
sub = ctx.socket(zmq.SUB)
sub.connect("tcp://10.200.0.1:5556")
sub.setsockopt(zmq.SUBSCRIBE, b"EURUSD")
```

### Pattern 4: SpreadModel Signal Suppression

**What:** Track rolling spread distribution. Suppress signal if round-trip spread > 50% of expected profit. Attenuate if < 50%.

**Example:**
```python
# Source: .claude/skills/forex/forex-broker-adapter/SKILL.md
def cost_adjusted_signal(self, raw_signal: float,
                          expected_holding_bars: int,
                          avg_bar_range: float) -> float:
    expected_move = abs(raw_signal) * avg_bar_range * expected_holding_bars
    round_trip_cost = 2 * self.median
    if expected_move == 0:
        return 0.0
    cost_ratio = round_trip_cost / expected_move
    if cost_ratio > 0.5:
        return 0.0  # Suppressed
    return raw_signal * (1 - cost_ratio)  # Attenuated
```

### Pattern 5: pyproject.toml Single Source of Truth

**What:** All tool configuration lives in `pyproject.toml`. No separate `setup.cfg`, `tox.ini`, `.mypy.ini`, or `.ruff.toml`.

```toml
[tool.pytest.ini_options]
addopts = "--cov=src --cov-report=term-missing --cov-branch --cov-fail-under=80"

[tool.coverage.run]
branch = true
omit = ["tests/*", "stubs/*"]

[tool.coverage.report]
fail_under = 80
show_missing = true

[tool.mypy]
python_version = "3.12"
strict = true
warn_unreachable = true

[[tool.mypy.overrides]]
module = ["MetaTrader5.*", "hmmlearn.*", "arch.*", "vectorbt.*", "arcticdb.*", "nats.*"]
ignore_missing_imports = true

[tool.ruff]
target-version = "py312"
line-length = 88

[tool.ruff.lint]
select = ["E","W","F","I","N","UP","B","SIM","ANN","S","C4","DTZ","RUF"]
```

### Anti-Patterns to Avoid

- **Direct mt5 imports in alpha/risk code:** Any `import MetaTrader5` or `import mt5` outside `src/execution/mt5_adapter.py` is a violation. KCH validator should flag it.
- **Synchronous MT5 calls without `asyncio.to_thread()`:** MT5 API is blocking; calling directly from async code deadlocks the event loop.
- **Running coverage in pre-commit:** Coverage requires full test execution — too slow for pre-commit (D-08). CI only.
- **Mutable default arguments in dataclasses:** Use `field(default_factory=list)`, not `history: list[float] = []`, in `SpreadModel`.
- **Missing `@abstractmethod` decorator:** Python allows instantiation of ABCs with only some methods implemented if decorator is missing — all methods must have it.
- **Hard-coded port numbers in bridge tests:** Use `zmq.Context().socket(zmq.PUSH)` with ephemeral ports (e.g., `bind_to_random_port()`) in tests to avoid port conflicts in CI.
- **ArcticDB `upsert()` call:** Does not exist. Use `write()` or `append()`. Classic KCH — the stub validator specifically tests for this.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| AST parsing | Custom regex/string parsing | Python `ast` module | Regex misses nested calls, multi-line, string literals; `ast` is exact |
| Levenshtein suggestions | Custom edit distance | `difflib.get_close_matches()` | Already in stdlib; handles transpositions correctly |
| Library stub introspection | Manual stub files only | `importlib` + `inspect.signature()` | Auto-generated stubs always match installed version; manual stubs drift |
| Async MT5 wrapper | Custom thread pool | `asyncio.to_thread()` | Standard library; avoids executor management boilerplate |
| ZMQ reconnect logic | Custom socket polling loop | ZMQ `RECONNECT_IVL` socket option + exponential backoff in consumer | ZMQ handles TCP reconnect at socket level; application layer adds heartbeat timeout |
| Coverage report | Custom test counter | `pytest-cov` + `coverage` | Branch coverage, XML output for CI, HTML for local — handles all edge cases |
| Property-based tests | Manual parameterized tests | `hypothesis` | Hypothesis finds edge cases humans miss; required for lot sizing (volume_step rounding) |
| MessagePack schema validation | Custom deserializer | `msgpack.unpackb()` with strict_map_key=False + dataclass conversion | msgpack handles encoding; dataclass conversion gives type safety |

**Key insight:** The AST validator and PiT checker ARE custom hand-rolled tools — but they operate on Python code using Python's built-in `ast` module, not on network protocols or math. Everything else uses existing libraries.

---

## Common Pitfalls

### Pitfall 1: Python 3.12 Venv Not Activated in CI

**What goes wrong:** GitHub Actions `setup-python` installs Python 3.12 but `pip install` goes into the wrong location if the venv is not explicitly activated or `pip` is not from the venv.

**Why it happens:** `actions/setup-python@v5` sets PATH for the selected Python but does not create a venv automatically.

**How to avoid:** In CI, use `pip install -r requirements.txt` directly after `setup-python` (no venv needed in CI containers). Locally, use `.venv/` and `source .venv/bin/activate`.

**Warning signs:** `ModuleNotFoundError` for packages that were installed; `pip list` shows packages but `python -c "import X"` fails.

### Pitfall 2: pytest-asyncio Mode Not Configured

**What goes wrong:** async test functions are collected but not awaited — they pass vacuously, or are silently skipped.

**Why it happens:** pytest-asyncio 0.21+ changed the default mode from `auto` to `strict`. Tests need either `@pytest.mark.asyncio` or `asyncio_mode = "auto"` in config.

**How to avoid:** Add to `pyproject.toml`:
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```
Or decorate every async test with `@pytest.mark.asyncio`.

**Warning signs:** async tests show 0 assertions and pass; `RuntimeWarning: coroutine 'test_foo' was never awaited`.

### Pitfall 3: mypy Strict Fails on `asyncio.to_thread()` with Lambda

**What goes wrong:** `asyncio.to_thread(lambda: mt5.account_info().equity)` fails mypy strict because the lambda return type is inferred as `Any` when MT5 has `ignore_missing_imports = true`.

**Why it happens:** mypy strict enables `--disallow-any-generics` and related checks. Lambda returning `Any` propagates `Any` through `to_thread()`.

**How to avoid:** Type the lambda explicitly or extract to a typed helper:
```python
def _get_equity() -> float:
    info = mt5.account_info()
    return float(info.equity)  # type: ignore[attr-defined]

async def get_account_equity(self) -> float:
    return await asyncio.to_thread(_get_equity)
```

**Warning signs:** `error: Returning Any from function declared to return "float"` in mypy output.

### Pitfall 4: SimAdapter Circular Dependency with ArcticDB

**What goes wrong:** SimAdapter constructor takes `arctic_store` parameter, but ArcticDB is not wired up until Phase 2. If SimAdapter imports ArcticDB types concretely, Phase 1 tests fail when ArcticDB store is unavailable.

**Why it happens:** Phase 1 and Phase 2 are sequential; SimAdapter is built in Phase 1 but uses ArcticDB data in Phase 2.

**How to avoid:** Use `Protocol` typing or `Any` type hint for `arctic_store` in Phase 1. Accept `None` as default and use in-memory data arrays for Phase 1 tests. Document the Phase 2 wiring point with a `# TODO: Phase 2 — wire ArcticDB store` comment.

**Warning signs:** `ImportError: cannot import name 'Arctic' from 'arcticdb'` in tests.

### Pitfall 5: ZMQ Socket Cleanup in Tests

**What goes wrong:** Test processes hold open ZMQ sockets, causing `Address already in use` errors on subsequent test runs or port conflicts between parallel tests.

**Why it happens:** ZMQ contexts and sockets are not automatically closed when test functions exit.

**How to avoid:** Use `pytest` fixtures with `yield` to guarantee cleanup:
```python
@pytest.fixture
def zmq_pair():
    ctx = zmq.Context()
    push = ctx.socket(zmq.PUSH)
    pull = ctx.socket(zmq.PULL)
    port = push.bind_to_random_port("tcp://127.0.0.1")
    pull.connect(f"tcp://127.0.0.1:{port}")
    yield push, pull
    push.close()
    pull.close()
    ctx.term()
```

**Warning signs:** `zmq.error.ZMQError: Address already in use`; tests pass in isolation but fail when run as a suite.

### Pitfall 6: coverage 80% Gate With Stub `__init__.py` Files

**What goes wrong:** Phase 1 creates `__init__.py` files with `# TODO: Phase N` stubs for `src/data/`, `src/alpha/`, etc. These count toward coverage denominator — 0% covered lines lower total coverage below 80%.

**Why it happens:** `--cov=src` instruments all files under `src/`, including empty stubs.

**How to avoid:** Either (a) exclude stub `__init__.py` files from coverage using `omit` in `pyproject.toml`, or (b) ensure every stub `__init__.py` contains only comments and type annotations (zero executable lines = not counted). Option (b) is cleaner.

**Warning signs:** Coverage drops unexpectedly when new `__init__.py` files are added.

### Pitfall 7: KCH Validator False Negatives on Chained Calls

**What goes wrong:** The AST extractor captures method names but not the object they're called on. `lib.write()` and `other_lib.write()` both appear as `{'func': 'write', ...}`. If `write` is in stubs for Library but called wrong on another object, no violation fires.

**Why it happens:** The current ASTExtractor only captures `node.func.attr` (method name), not the full dotted path.

**How to avoid:** Extend ASTExtractor to walk the full attribute chain. For `lib.write(symbol=x)`, capture `('lib', 'write')` not just `('write')`. The stub lookup then checks `(object_name, method_name)` pairs. For Phase 1, document this limitation — the validator catches wrong parameters and phantom functions, not object-type mismatches.

**Warning signs:** `arcticdb.Library.upsert()` phantom call passes validation when the variable is named something other than `lib`.

### Pitfall 8: Pre-commit `mirrors-mypy` Additional Dependencies

**What goes wrong:** Pre-commit runs mypy in an isolated environment — it does not have access to the project's venv. Without `additional_dependencies`, mypy cannot find `pandas-stubs`, `numpy`, or `types-requests`, causing spurious errors.

**Why it happens:** pre-commit hook environments are sandboxed; `additional_dependencies` must explicitly list all mypy stub packages.

**How to avoid:**
```yaml
- repo: https://github.com/pre-commit/mirrors-mypy
  rev: v1.19.1
  hooks:
    - id: mypy
      additional_dependencies:
        - pandas-stubs
        - numpy
        - types-requests
      args: [--strict]
```

**Warning signs:** `Cannot find implementation or library stub for module named "pandas"` in pre-commit output despite pandas-stubs being in the venv.

---

## Code Examples

Verified patterns from skill files and phase documentation:

### Swap Rate Annualization
```python
# Source: .claude/skills/forex/forex-broker-adapter/SKILL.md §Swap Rate Extraction
def compute_annualized_carry(symbol: str) -> dict[str, float]:
    info = mt5.symbol_info(symbol)
    tick = mt5.symbol_info_tick(symbol)
    mid = (tick.bid + tick.ask) / 2
    swap_long_annual = (info.swap_long * info.point * 365) / mid * 100
    swap_short_annual = (info.swap_short * info.point * 365) / mid * 100
    return {
        'swap_long_annual_pct': swap_long_annual,
        'swap_short_annual_pct': swap_short_annual,
        'net_carry_signal': swap_long_annual - abs(swap_short_annual),
    }
```

### Lot Sizing with Volume Constraints
```python
# Source: .claude/skills/forex/forex-broker-adapter/SKILL.md §Forex Lot Sizing
def kelly_to_lots(equity: float, kelly_fraction: float,
                  stop_loss_pips: float, symbol: str,
                  account_currency: str = "USD") -> float:
    info = mt5.symbol_info(symbol)
    pip_size = info.point * 10  # 5-digit broker: 1 pip = 10 points
    pip_value = info.trade_contract_size * pip_size
    if info.currency_profit != account_currency:
        conv = f"{info.currency_profit}{account_currency}"
        conv_tick = mt5.symbol_info_tick(conv)
        if conv_tick:
            pip_value *= conv_tick.bid
    risk_amount = equity * kelly_fraction
    lots = risk_amount / (stop_loss_pips * pip_value)
    step = info.volume_step
    lots = max(info.volume_min,
               min(info.volume_max, round(lots / step) * step))
    return lots
```

### ArcticDB Stub (CRITICAL — upsert does not exist)
```python
# Source: .claude/skills/forex/ast-tdd-validation/SKILL.md §Library Stubs
ARCTICDB_STUBS = {
    'Library': {
        'write': {'params': ['symbol', 'data', 'metadata', 'prune_previous_versions']},
        'read': {'params': ['symbol', 'as_of', 'date_range', 'columns', 'query_builder']},
        'append': {'params': ['symbol', 'data', 'metadata', 'prune_previous_versions']},
        'list_symbols': {'params': []},
        'delete': {'params': ['symbol']},
        'snapshot': {'params': ['snap_name', 'metadata', 'skip_symbols', 'versions']},
        # NOTE: 'upsert' does NOT exist — common KCH
    }
}
```

### MT5 Stub (Phase 1A validation ground truth)
```python
# Source: .claude/skills/forex/ast-tdd-validation/SKILL.md §Library Stubs
MT5_STUBS = {
    'copy_ticks_range': {'params': ['symbol', 'date_from', 'date_to', 'flags']},
    'copy_rates_from_pos': {'params': ['symbol', 'timeframe', 'start_pos', 'count']},
    'order_send': {'params': ['request']},
    'symbol_info': {'params': ['symbol']},
    'symbol_info_tick': {'params': ['symbol']},
    'positions_get': {'params': ['symbol', 'group', 'ticket']},
    'account_info': {'params': []},
    'initialize': {'params': ['path', 'login', 'password', 'server', 'timeout', 'portable']},
    'login': {'params': ['login', 'password', 'server', 'timeout']},
    'last_error': {'params': []},
    'symbols_get': {'params': ['group']},
    'shutdown': {'params': []},
}
```

### GitHub Actions CI Workflow
```yaml
# Source: _docs/Phase_1_Foundation.md §Task 1A.4
name: Trading System CI
on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  static-analysis:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'
      - run: pip install -r requirements-dev.txt
      - run: ruff check . && ruff format --check .
      - run: mypy src/ --strict
      - run: python scripts/ast_validator.py --stubs stubs/ --source src/
      - run: python scripts/pit_validator.py --source src/alpha/

  tests:
    needs: static-analysis
    runs-on: ubuntu-latest
    services:
      nats:
        image: nats:latest
        ports: ['4222:4222']
        options: --health-cmd "nats-server --help" --health-interval 10s
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - run: pytest tests/ --cov=src --cov-report=xml --cov-fail-under=80 --cov-branch -v
      - uses: codecov/codecov-action@v4
        with:
          file: coverage.xml

  e2e:
    needs: tests
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    services:
      nats:
        image: nats:latest
        ports: ['4222:4222']
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - run: pytest tests/e2e/ -v --timeout=300
```

### Pre-commit Configuration
```yaml
# Source: _docs/Phase_1_Foundation.md §Task 1A.4 + D-07/D-08/D-09
# Pre-commit: ruff + mypy ONLY (fast). No pytest/coverage/AST in pre-commit.
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: no-commit-to-branch
        args: ['--branch', 'main']

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.15.7
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.19.1
    hooks:
      - id: mypy
        additional_dependencies: [pandas-stubs, numpy, types-requests]
        args: [--strict]
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| flake8 + black + isort | ruff (single tool) | 2022-2023 | 10-100x faster; one config section |
| `asyncio.get_event_loop().run_in_executor()` | `asyncio.to_thread()` | Python 3.9 | Simpler; no executor management |
| `pytest.ini` + `setup.cfg` | `pyproject.toml` | PEP 518/621, ~2021 | Single source of truth |
| pandas `.append()` | `pd.concat()` | pandas 2.0 (2023) | `.append()` removed — KCH validator must catch it |
| `dataclasses.dataclass` with mutable defaults | `field(default_factory=...)` | Python 3.7+ | Required for list/dict defaults; mypy strict enforces |
| pytest-asyncio `auto` mode default | `strict` mode default (0.21+) | 2023 | Must explicitly set `asyncio_mode = "auto"` or decorate tests |

**Deprecated/outdated:**
- `arcticdb.Library.upsert()`: Does not exist. Use `write()` or `append()`.
- `pandas.DataFrame.append()`: Removed in pandas 2.0. Use `pd.concat()`.
- `mt5.order_check()` without `order_send()`: Does not execute — only validates. KCH risk if confused.
- `zmq.NOBLOCK` (old constant): Still works but prefer `zmq.DONTWAIT` in modern pyzmq.

---

## Open Questions

1. **SimAdapter data source in Phase 1**
   - What we know: SimAdapter constructor takes `arctic_store` per the skill reference; ArcticDB is Phase 2
   - What's unclear: Should Phase 1 SimAdapter use synthetic numpy arrays or accept `None` store?
   - Recommendation: Accept `arctic_store: Any = None` in Phase 1. When `None`, generate synthetic price series with fixed seed (D-26). Document with `# TODO: Phase 2 — pass ArcticDB library handle`. This avoids circular dependency and keeps tests deterministic.

2. **`src/bridge/` vs `src/execution/bridge/` placement**
   - What we know: CONTEXT.md D-06 says `src/bridge/`; Phase_1_Foundation.md Task 1B.6 says `src/execution/bridge/`; claude-code-prompts-fxadapter.md says `./src/bridge/`
   - What's unclear: Which is canonical?
   - Recommendation: Use `src/execution/bridge/` — it matches the execution layer ownership and the skill's Implementation Structure section. The skill file takes precedence over the prompt doc.

3. **Coverage exclusion for stub `__init__.py` files**
   - What we know: Phase 1 creates empty `__init__.py` stubs for Phases 2-4 modules; coverage counts them
   - What's unclear: Will empty files (comments only, no executable lines) count against coverage?
   - Recommendation: Keep all Phase 2-4 stubs as comment-only files — Python `coverage.py` only counts executable lines. A file with only comments and docstrings has 0 executable lines and does not affect percentage. Verify after `pytest --cov` first run.

4. **`no-commit-to-branch` pre-commit hook version**
   - What we know: Phase_1_Foundation.md shows `pre-commit-hooks rev: v6.0.0`; as of research date this is reasonable
   - What's unclear: Is v6.0.0 released?
   - Recommendation: Use `v5.0.0` (confirmed released). The planner should verify latest tag at implementation time via `https://github.com/pre-commit/pre-commit-hooks/tags`.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | `pyproject.toml` (to be created in Wave 1) |
| Quick run command | `pytest tests/quality/ tests/execution/ -x -q` |
| Full suite command | `pytest tests/ --cov=src --cov-fail-under=80 --cov-branch -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| QUAL-01 | AST validator detects phantom function (e.g., `arcticdb.Library.upsert()`) | unit | `pytest tests/quality/test_kch_validator.py -x` | ❌ Wave 0 |
| QUAL-01 | AST validator detects wrong parameter name | unit | `pytest tests/quality/test_kch_validator.py -x` | ❌ Wave 0 |
| QUAL-01 | AST validator passes clean code with 0 violations | unit | `pytest tests/quality/test_kch_validator.py -x` | ❌ Wave 0 |
| QUAL-02 | PiT validator flags `df['signal'] = f(df['price'])` (no `.shift()`) | unit | `pytest tests/quality/test_pit_validator.py -x` | ❌ Wave 0 |
| QUAL-02 | PiT validator passes `df['signal'] = f(df['price'].shift(1))` | unit | `pytest tests/quality/test_pit_validator.py -x` | ❌ Wave 0 |
| QUAL-03 | mypy strict passes on all `src/` files | static | `mypy src/ --strict` | ❌ Wave 0 |
| QUAL-03 | ruff check passes on all files | static | `ruff check .` | ❌ Wave 0 |
| QUAL-04 | coverage gate at 80% enforced | integration | `pytest tests/ --cov-fail-under=80` | ❌ Wave 0 |
| QUAL-05 | pre-commit run passes on clean repo | integration | `pre-commit run --all-files` | ❌ Wave 0 |
| QUAL-06 | CI workflow YAML is syntactically valid | static | `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"` | ❌ Wave 0 |
| EXEC-01 | Incomplete ABC implementation raises `TypeError` | unit | `pytest tests/execution/test_abstract.py -x` | ❌ Wave 0 |
| EXEC-02 | MT5Adapter connects with mocked mt5 module | unit | `pytest tests/execution/test_mt5_adapter.py -x` | ❌ Wave 0 |
| EXEC-02 | MT5Adapter submit_order handles retcode != DONE | unit | `pytest tests/execution/test_mt5_adapter.py -x` | ❌ Wave 0 |
| EXEC-02 | MT5Adapter timeframe mapping covers all 8 timeframes | unit | `pytest tests/execution/test_mt5_adapter.py -x` | ❌ Wave 0 |
| EXEC-03 | SimAdapter buy→hold→sell PnL = (exit-entry)*qty - spread | unit | `pytest tests/execution/test_sim_adapter.py -x` | ❌ Wave 0 |
| EXEC-03 | SimAdapter equity = initial + realized + unrealized | unit | `pytest tests/execution/test_sim_adapter.py -x` | ❌ Wave 0 |
| EXEC-03 | SimAdapter rejects order with insufficient margin | unit | `pytest tests/execution/test_sim_adapter.py -x` | ❌ Wave 0 |
| EXEC-04 | SpreadModel suppresses signal when cost_ratio > 0.5 | unit | `pytest tests/execution/test_spread_model.py -x` | ❌ Wave 0 |
| EXEC-04 | SpreadModel p95 matches `np.percentile(history, 95)` | unit | `pytest tests/execution/test_spread_model.py -x` | ❌ Wave 0 |
| EXEC-05 | Swap rate formula matches hand-calculated result for EURUSD | unit | `pytest tests/execution/test_swap_rates.py -x` | ❌ Wave 0 |
| EXEC-06 | Lot size respects volume_min/max/step constraints | unit | `pytest tests/execution/test_lot_sizing.py -x` | ❌ Wave 0 |
| EXEC-06 | Currency conversion correct for GBPUSD lot sizing | unit | `pytest tests/execution/test_lot_sizing.py -x` | ❌ Wave 0 |
| EXEC-07 | MessagePack round-trip preserves all Tick/Bar fields | unit | `pytest tests/execution/bridge/test_bridge.py -x` | ❌ Wave 0 |
| EXEC-07 | ZMQ SUB topic filtering receives only matching symbol ticks | unit | `pytest tests/execution/bridge/test_bridge.py -x` | ❌ Wave 0 |
| EXEC-07 | Consumer detects publisher disconnect via heartbeat within 10s | unit | `pytest tests/execution/bridge/test_bridge.py -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/quality/ tests/execution/ -x -q` (unit tests only, ~10-30 seconds)
- **Per wave merge:** `pytest tests/ --cov=src --cov-fail-under=80 --cov-branch -v`
- **Phase gate:** Full suite green + `pre-commit run --all-files` passes + `make all` passes before `/gsd:verify-work`

### Wave 0 Gaps

All test files are missing — this is a greenfield phase:

- [ ] `tests/conftest.py` — shared fixtures, `pit_check` marker registration, async mode config
- [ ] `tests/quality/test_ast_extractor.py` — covers QUAL-01 extraction stage
- [ ] `tests/quality/test_kch_validator.py` — covers QUAL-01 validation + violation reporting
- [ ] `tests/quality/test_stub_generator.py` — covers QUAL-01 auto-generation
- [ ] `tests/quality/test_pit_validator.py` — covers QUAL-02 all three detection methods
- [ ] `tests/execution/test_abstract.py` — covers EXEC-01 interface contracts
- [ ] `tests/execution/test_mt5_adapter.py` — covers EXEC-02 with mocked mt5
- [ ] `tests/execution/test_sim_adapter.py` — covers EXEC-03 deterministic fills
- [ ] `tests/execution/test_spread_model.py` — covers EXEC-04 signal suppression/attenuation
- [ ] `tests/execution/test_swap_rates.py` — covers EXEC-05 annualization formula
- [ ] `tests/execution/test_lot_sizing.py` — covers EXEC-06 all constraints
- [ ] `tests/execution/bridge/test_bridge.py` — covers EXEC-07 with mocked ZMQ sockets
- [ ] `pyproject.toml` — all tool configurations (pytest, mypy, ruff, coverage)
- [ ] Framework install: `python3.12 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt -r requirements-dev.txt`

---

## Sources

### Primary (HIGH confidence)
- `.claude/skills/forex/ast-tdd-validation/SKILL.md` — AST extractor code, KCH validator, stub format, pytest/mypy/ruff config, CI/CD pipeline pattern
- `.claude/skills/forex/forex-broker-adapter/SKILL.md` — Abstract interfaces, MT5Adapter implementation, SimAdapter pattern, SpreadModel, swap rates, lot sizing, ZMQ bridge topology
- `_docs/Phase_1_Foundation.md` — Complete task breakdown, output file lists, validation checklists, exact pyproject.toml config values
- `_docs/claude-code-prompts-fxadapter.md` — Implementation prompts with ZMQ port assignments and serialization specs

### Secondary (MEDIUM confidence)
- Direct system inspection: `pip3 list` output confirming installed package versions for Python 3.10 system install — packages need reinstalling in Python 3.12 venv
- `python3.12 --version` output confirming Python 3.12.13 at `/usr/bin/python3.12`
- `ruff --version` confirming ruff 0.15.7 available as system binary

### Tertiary (LOW confidence)
- pre-commit-hooks v6.0.0 referenced in Phase_1_Foundation.md — unverified against current GitHub tags; use v5.0.0 as safe fallback (LOW: requires internet verification at implementation time)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions confirmed via `pip3 list` and system inspection
- Architecture: HIGH — drawn directly from project skill files and Phase_1_Foundation.md
- Pitfalls: HIGH for Python/pytest/ZMQ items (based on known ecosystem behavior); MEDIUM for KCH false-negative analysis (based on AST pattern analysis)

**Research date:** 2026-03-21
**Valid until:** 2026-06-21 (stable ecosystem; ruff and pytest release frequently but patch versions don't affect architecture)

---

## Critical Implementation Note: Python 3.10 vs 3.12

The most important finding from environment inspection:

All documented "already installed" packages (pytest 9.0.2, mypy 1.19.1, ruff 0.15.7, pyzmq 27.1.0, arcticdb 6.10.2, nats-py 2.14.0, coverage 7.13.5, msgpack 1.1.2) are installed for **Python 3.10** (`/usr/bin/python3`), NOT Python 3.12.

`/usr/bin/python3.12` has **no packages installed beyond the standard library**.

Task 1A.1 MUST create a Python 3.12 venv and reinstall all packages. The `requirements.txt` and `requirements-dev.txt` files pin the same versions already tested on this machine (Python 3.10 packages are a known-working baseline). The `ruff` binary (0.15.7) is usable system-wide without the venv.

The following packages are NOT installed anywhere and must be added to `requirements-dev.txt`:
- `hypothesis` (property-based testing — `tests/properties/` directory)
- `pre-commit` (local git hook runner)
- `pandas-stubs` (mypy strict type stubs for pandas)
