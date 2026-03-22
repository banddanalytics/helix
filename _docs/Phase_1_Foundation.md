# PHASE 1: Foundation — Code Quality Infrastructure and Execution Abstraction

**Duration:** 2-3 weeks
**Dependencies:** None — this is the foundation phase
**Skills Used:** `ast-tdd-validation`, `forex-broker-adapter`

Phase 1 establishes two foundational layers that every subsequent phase depends on: the CI/CD quality pipeline that validates all generated code, and the execution abstraction layer that makes all downstream code broker-agnostic. These two layers must be complete and tested before any alpha engine, data pipeline, or dashboard work begins.

---

## Phase 1A: CI/CD Quality Pipeline

**Read:** `SKILL.md: ast-tdd-validation`, all sections

This sub-phase builds the automated quality gates that every line of code must pass through before it can be committed. The gates include AST-based hallucination detection, Point-in-Time compliance checking, type checking, linting, and coverage enforcement.

---

### Task 1A.1 — Initialize Project Repository and Python Environment

**Tool:** Claude Code
**Skill Reference:** `ast-tdd-validation > Implementation Structure`

Create the project repository with the complete directory structure specified across all 10 skills. Initialize a Python 3.12 virtual environment. Install core dependencies: pytest, pytest-cov, mypy, ruff, pre-commit, hypothesis.

Create `pyproject.toml` with all tool configurations as specified in the `ast-tdd-validation` skill:

- **pytest:** `addopts = "--cov=src --cov-report=term-missing --cov-branch --cov-fail-under=80"`
- **mypy:** `strict = true` with `ignore_missing_imports` for MetaTrader5, hmmlearn, arch, vectorbt, arcticdb
- **ruff:** Full rule set `select = ["E","W","F","I","N","UP","B","SIM","ANN","S","C4","DTZ","RUF"]`, target Python 3.12, line length 88
- **coverage:** `branch = true`, `fail_under = 80`, `show_missing = true`

Create the directory tree:

```
project-root/
├── src/
│   ├── execution/       # Phase 1B: abstraction layer, MT5 adapter, bridge
│   ├── data/            # Phase 2: ArcticDB, schemas, PiT manager
│   ├── alpha/           # Phase 3: regime, cointegration, carry, ML
│   │   ├── regime/
│   │   ├── cointegration/
│   │   ├── carry/
│   │   ├── ml_price_momentum/
│   │   └── ml_mbo_orderflow/   # Stage B only
│   ├── risk/            # Phase 4: CVaR, Kelly, ECT
│   ├── ipc/             # Phase 4: ZeroMQ, NATS
│   └── quality/         # Phase 1A: AST validator, PiT checker
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   ├── properties/      # Hypothesis property-based tests
│   ├── execution/
│   ├── data/
│   ├── alpha/
│   ├── risk/
│   ├── ipc/
│   └── quality/
├── scripts/
├── config/
├── infra/
├── ui/
├── stubs/               # Library stubs for KCH validation
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
└── Makefile
```

**Output Files:**

```
pyproject.toml
requirements.txt
requirements-dev.txt
.python-version
Makefile
src/__init__.py (and all subpackage __init__.py files)
tests/conftest.py
```

**Validation:**

- [ ] `python -m pytest --collect-only` returns 0 (no tests yet, but collection works)
- [ ] `mypy src/ --strict` returns 0 errors (empty modules pass)
- [ ] `ruff check . && ruff format --check .` returns 0

**Makefile Targets:**

```makefile
.PHONY: lint typecheck test test-integration validate all

lint:
	ruff check . && ruff format --check .

typecheck:
	mypy src/ --strict

test:
	pytest tests/ --cov=src --cov-fail-under=80 --cov-branch -v

test-integration:
	pytest tests/integration/ -v --timeout=60

validate:
	python scripts/ast_validator.py --stubs stubs/ --source src/
	python scripts/pit_validator.py --source src/alpha/

all: lint typecheck validate test
```

---

### Task 1A.2 — Build AST/KCH Validation Framework

**Tool:** Claude Code
**Skill Reference:** `ast-tdd-validation > AST Validation Pipeline (Stages 1-4)`

Implement the complete Knowledge Conflicting Hallucination (KCH) detection pipeline:

**ASTExtractor class** (`src/quality/ast_validator/extractor.py`):

Uses `ast.NodeVisitor` to walk Python ASTs and extract:
- All `import` and `from...import` statements
- All function/method calls with function name, keyword arguments, and line numbers
- All attribute accesses with object, attribute name, and line number

```python
import ast

class ASTExtractor(ast.NodeVisitor):
    def __init__(self):
        self.imports: list[str] = []
        self.function_calls: list[dict] = []
        self.attribute_accesses: list[dict] = []

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.append(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        for alias in node.names:
            self.imports.append(f"{node.module}.{alias.name}")
        self.generic_visit(node)

    def visit_Call(self, node):
        info = self._extract_call(node)
        if info:
            self.function_calls.append(info)
        self.generic_visit(node)

    def _extract_call(self, node) -> dict | None:
        if isinstance(node.func, ast.Attribute):
            return {
                'func': node.func.attr,
                'kwargs': {kw.arg for kw in node.keywords},
                'lineno': node.lineno
            }
        elif isinstance(node.func, ast.Name):
            return {
                'func': node.func.id,
                'kwargs': {kw.arg for kw in node.keywords},
                'lineno': node.lineno
            }
        return None
```

**KCHValidator class** (`src/quality/ast_validator/validator.py`):

Compares extracted API calls against ground-truth library stubs. Produces violation reports with:
- Severity levels: CRITICAL (blocks merge), WARNING (review required), INFO (suggestion)
- Levenshtein-based parameter name suggestions using `difflib.get_close_matches()`
- Violation types: PHANTOM_FUNCTION, WRONG_PARAMETER, PHANTOM_IMPORT, DEPRECATED_API

**Stub auto-generator** (`src/quality/ast_validator/stub_generator.py`):

Introspects installed libraries using `importlib` and `inspect.signature()` to create stub definitions. This ensures stubs always match the actual installed library version rather than relying on LLM training data.

**Generate initial stubs for:**

| Library | Stub File | Key Classes/Functions |
|---------|-----------|----------------------|
| MetaTrader5 | `stubs/mt5_stubs.py` | copy_ticks_range, copy_rates_from_pos, order_send, symbol_info, positions_get |
| arcticdb | `stubs/arcticdb_stubs.py` | Arctic, Library (write, read, append, list_symbols, snapshot — NOT upsert) |
| pyzmq | `stubs/zmq_stubs.py` | Context, Socket (bind, connect, send, recv, setsockopt) |
| nats-py | `stubs/nats_stubs.py` | connect, JetStream, PullSubscription |
| xgboost | `stubs/xgboost_stubs.py` | XGBClassifier, XGBRegressor, DMatrix |
| hmmlearn | `stubs/hmmlearn_stubs.py` | GaussianHMM (fit, predict, decode) |
| arch | `stubs/arch_stubs.py` | arch_model (fit, forecast, params) |
| statsmodels | `stubs/statsmodels_stubs.py` | coint_johansen, VECM, select_coint_rank |

**CLI entry point** (`scripts/ast_validator.py`):

```bash
python scripts/ast_validator.py --stubs stubs/ --source src/
# Outputs JSON violation report
# Exit code: 0 = clean, 1 = CRITICAL violations found
```

**Output Files:**

```
src/quality/ast_validator/__init__.py
src/quality/ast_validator/extractor.py
src/quality/ast_validator/validator.py
src/quality/ast_validator/stub_generator.py
stubs/mt5_stubs.py
stubs/arcticdb_stubs.py
stubs/zmq_stubs.py
stubs/nats_stubs.py
stubs/xgboost_stubs.py
stubs/hmmlearn_stubs.py
stubs/arch_stubs.py
stubs/statsmodels_stubs.py
scripts/ast_validator.py
tests/quality/test_ast_extractor.py
tests/quality/test_kch_validator.py
tests/quality/test_stub_generator.py
```

**Validation:**

- [ ] Validator detects `arcticdb.Library.upsert()` as PHANTOM_FUNCTION (upsert does not exist)
- [ ] Validator detects wrong parameter name and suggests closest match via Levenshtein
- [ ] Validator passes clean code with zero violations
- [ ] Stub generator produces valid stubs from installed arcticdb library
- [ ] `pytest tests/quality/ --cov=src/quality --cov-fail-under=90` passes

---

### Task 1A.3 — Build PiT Compliance Validator

**Tool:** Claude Code
**Skill Reference:** `arcticdb-vectorbt-engine > PiT Validation Framework`

Implement a Point-in-Time compliance checker that runs as both a pytest plugin and a standalone pre-commit hook.

**Three detection methods:**

1. **Information Coefficient (IC) analysis:** Compares contemporaneous IC vs forward IC on signal DataFrames. If `abs(contemp_ic) > abs(forward_ic) * 1.5`, look-ahead bias is probable.

2. **AST inspection:** Parses signal generation code and flags any column access without `.shift()` in assignment expressions involving price, volume, bid, ask, close, high, low, or open data.

3. **Temporal shuffle test:** Permutes timestamps randomly, re-runs signal generation, and verifies that performance does not persist (a PiT-correct signal's alpha should disappear when temporal order is destroyed).

**pytest plugin** (`tests/conftest.py`):

Register the `pit_check` marker so tests can be tagged `@pytest.mark.pit_check` and collected with `pytest -m pit_check`.

**Pre-commit hook** (`scripts/pit_validator.py`):

Scans all files matching `src/alpha/**/*.py` for PiT violations. Returns non-zero exit code if any violation found.

**Output Files:**

```
src/quality/pit_validator.py
scripts/pit_validator.py
tests/quality/test_pit_validator.py
```

**Validation:**

- [ ] Flags `df['signal'] = f(df['price'])` as VIOLATION (missing `.shift(1)`)
- [ ] Passes `df['signal'] = f(df['price'].shift(1))` as COMPLIANT
- [ ] Flags `df['rolling_vol'] = df['returns'].rolling(20).std()` as VIOLATION (missing shift after rolling)
- [ ] Passes `df['rolling_vol'] = df['returns'].rolling(20).std().shift(1)` as COMPLIANT
- [ ] `pytest -m pit_check` collects and runs PiT-tagged tests

---

### Task 1A.4 — Configure Pre-Commit Hooks and GitHub Actions CI

**Tool:** Claude Code
**Skill Reference:** `ast-tdd-validation > Pre-Commit Hooks, GitHub Actions CI`

**Pre-commit configuration** (`.pre-commit-config.yaml`):

Hooks execute in this order on every commit:

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v6.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: no-commit-to-branch
        args: ['--branch', 'main']

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.15.6
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

  - repo: local
    hooks:
      - id: ast-validation
        name: KCH Validator
        language: python
        entry: python scripts/ast_validator.py --stubs stubs/ --source
        files: '\.py$'
        pass_filenames: false
      - id: pit-check
        name: PiT Compliance
        language: python
        entry: python scripts/pit_validator.py --source
        files: 'alpha/.*\.py$'
        pass_filenames: false
```

**GitHub Actions CI** (`.github/workflows/ci.yml`):

Three jobs in sequence:

1. **static-analysis:** ruff check + ruff format --check + mypy strict + AST validator + PiT validator
2. **tests:** pytest with `--cov-fail-under=80`, NATS service container on port 4222
3. **e2e:** (only on main branch pushes) pytest tests/e2e/ with 300s timeout

```yaml
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

**Install and verify:**

```bash
pre-commit install
pre-commit install --hook-type pre-push
pre-commit run --all-files  # Should pass on clean codebase
```

**Output Files:**

```
.pre-commit-config.yaml
.github/workflows/ci.yml
Makefile (updated with targets: lint, typecheck, test, test-integration, validate, all)
```

**Validation:**

- [ ] `pre-commit run --all-files` exits 0
- [ ] `make lint` passes (ruff check + format)
- [ ] `make typecheck` passes (mypy strict)
- [ ] `make validate` passes (AST + PiT validators)
- [ ] GitHub Actions CI workflow YAML is valid (tested via `act` or pushed to repo)

---

### Phase 1A Completion Gate

**All of the following must pass before proceeding to Phase 1B:**

- [ ] `pre-commit run --all-files` exits 0
- [ ] `make lint && make typecheck && make validate` all exit 0
- [ ] `pytest tests/quality/ --cov=src/quality --cov-fail-under=90` passes
- [ ] GitHub Actions CI workflow runs green on a test push
- [ ] AST validator catches at least 5 known KCH patterns in test fixtures
- [ ] PiT validator catches all 3 look-ahead bias patterns in test fixtures

---

## Phase 1B: Execution Abstraction Layer

**Read:** `SKILL.md: forex-broker-adapter`, all sections

This sub-phase builds the broker-agnostic execution layer. The abstract interfaces defined here are the most critical code in the entire system — every alpha engine, risk engine, and dashboard component codes against them, never directly against MT5 or any broker API.

---

### Task 1B.1 — Implement Abstract Execution Interfaces and Dataclasses

**Tool:** Cursor
**Skill Reference:** `forex-broker-adapter > Execution Abstraction Layer > Abstract Interfaces`

Create the abstract base classes and dataclasses that define the market-agnostic execution contract. These interfaces must NEVER reference MT5, CME, Forex, or futures concepts directly.

**Enums:**

```python
class Side(Enum):
    BUY = 1
    SELL = -1

class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
```

**Dataclasses (all using numpy datetime64 and float64):**

| Dataclass | Key Fields | Notes |
|-----------|-----------|-------|
| `Tick` | timestamp, symbol, bid, ask, bid_volume, ask_volume, source | Universal tick — works for Forex and futures |
| `Bar` | timestamp, symbol, OHLCV, volume, spread | spread=0 for futures, >0 for Forex |
| `OrderRequest` | symbol, side, quantity, order_type, price, sl, tp, comment | quantity = lots (Forex) or contracts (futures) |
| `OrderResult` | order_id, fill_price, fill_quantity, slippage, commission, success, error_message | |
| `Position` | symbol, side, quantity, entry_price, current_price, unrealized_pnl, swap_accumulated, margin_used | swap_accumulated for Forex rollover; 0 for futures |

**Abstract Base Classes (all methods async):**

| ABC | Methods |
|-----|---------|
| `MarketDataProvider` | `get_ticks()`, `get_bars()`, `subscribe_ticks()`, `get_symbols()` |
| `OrderExecutor` | `submit_order()`, `cancel_order()`, `get_open_orders()` |
| `PositionManager` | `get_positions()`, `close_position()`, `get_account_equity()`, `get_margin_level()` |

**Output Files:**

```
src/execution/__init__.py
src/execution/abstract.py
tests/execution/test_abstract.py
```

**Validation:**

- [ ] `mypy src/execution/abstract.py --strict` passes with 0 errors
- [ ] All ABCs have `@abstractmethod` on every method
- [ ] No reference to MT5, CME, or any broker-specific concept in `abstract.py`
- [ ] Interface contract tests verify that incomplete implementations raise `TypeError`

---

### Task 1B.2 — Implement MT5 Concrete Adapter

**Tool:** Cursor
**Skill Reference:** `forex-broker-adapter > MT5 Adapter Implementation`

Implement `MT5Adapter` class inheriting from all three abstract interfaces.

**Connection management:**
- `__init__` stores account, password, server, optional mt5_path
- `connect()` calls `mt5.initialize()` then `mt5.login()` with error handling via `mt5.last_error()`

**Data methods:**
- `get_ticks()` → `mt5.copy_ticks_range()` with `COPY_TICKS_ALL`, converts to `Tick` dataclass list
- `get_bars()` → `mt5.copy_rates_from_pos()` with timeframe mapping dict (`"1m"` → `mt5.TIMEFRAME_M1` through `"1w"` → `mt5.TIMEFRAME_W1`), populates spread field from `r['spread'] * info.point`
- `subscribe_ticks()` → 10ms polling loop via `asyncio.sleep(0.01)` since MT5 has no native streaming

**Order methods:**
- `submit_order()` → builds MT5 request dict with `TRADE_ACTION_DEAL`, `deviation=20`, `magic=100001`, `type_filling=ORDER_FILLING_IOC`, checks `result.retcode != mt5.TRADE_RETCODE_DONE`

**Position methods:**
- `get_positions()` → `mt5.positions_get()` converted to `Position` dataclass
- `close_position()` → creates reverse market order
- `get_account_equity()` / `get_margin_level()` → wraps `mt5.account_info()`

**Critical:** All synchronous MT5 calls wrapped in `asyncio.to_thread()` to avoid blocking.

**Output Files:**

```
src/execution/mt5_adapter.py
tests/execution/test_mt5_adapter.py
```

**Validation:**

- [ ] All abstract methods implemented (no `NotImplementedError` remaining)
- [ ] Tests mock the `mt5` module and verify: connect, get_ticks, get_bars, submit_order, get_positions, close_position
- [ ] Error handling tested: connection failure, order rejection (retcode != DONE), symbol not found
- [ ] MT5 timeframe mapping covers all 8 timeframes (`1m` through `1w`)
- [ ] Async wrappers verified with `asyncio.run()`

---

### Task 1B.3 — Implement Simulation Adapter for Backtesting and Testing

**Tool:** Cursor
**Skill Reference:** `forex-broker-adapter > Simulation Adapter`

Implement `SimAdapter` that provides the same interface as `MT5Adapter` but reads from ArcticDB data and simulates execution with configurable spread and slippage.

**Constructor parameters:**
- `arctic_store`: ArcticDB library handle
- `spread_model`: SpreadModel instance
- `slippage_bps`: basis points of adverse slippage per trade (default 1.0)
- `initial_equity`: starting capital (default 100,000)

**Behavior:**
- Data methods read directly from ArcticDB using date range queries
- Order methods simulate fills at current price ± slippage, deducting spread cost
- Position management tracks open positions in an internal dict
- `get_account_equity()` returns initial capital + realized + unrealized PnL

This adapter enables backtesting and CI testing on Linux/Mac without Windows MT5 terminal.

**Output Files:**

```
src/execution/sim_adapter.py
tests/execution/test_sim_adapter.py
```

**Validation:**

- [ ] SimAdapter passes the same interface contract tests as MT5Adapter
- [ ] Buy→hold→sell round-trip PnL = (exit-entry) × qty - spread - slippage
- [ ] `initial_equity + Σ(realized_pnl) + Σ(unrealized_pnl) = get_account_equity()`
- [ ] Slippage model: fills are always worse than requested by exactly `slippage_bps`

---

### Task 1B.4 — Implement Spread Cost Model

**Tool:** Cursor
**Skill Reference:** `forex-broker-adapter > Variable Spread Model`

Implement `SpreadModel` class that tracks empirical spread distribution from the broker feed.

**Properties:**
- `median`: 50th percentile spread for typical cost estimation
- `p95`: 95th percentile for worst-case cost in risk calculations
- `volatility`: standard deviation of spread — high values indicate unreliable execution

**Key method — `cost_adjusted_signal()`:**

```python
def cost_adjusted_signal(self, raw_signal: float,
                          expected_holding_bars: int,
                          avg_bar_range: float) -> float:
    expected_move = abs(raw_signal) * avg_bar_range * expected_holding_bars
    round_trip_cost = 2 * self.median
    if expected_move == 0:
        return 0.0
    cost_ratio = round_trip_cost / expected_move
    if cost_ratio > 0.5:
        return 0.0  # Signal suppressed — spread eats >50% of expected profit
    return raw_signal * (1 - cost_ratio)  # Attenuate by cost
```

This model feeds directly into the CVaR risk optimizer in Phase 4.

**Output Files:**

```
src/execution/spread_model.py
tests/execution/test_spread_model.py
```

**Validation:**

- [ ] Median spread on synthetic data matches `np.median()`
- [ ] p95 spread on synthetic data matches `np.percentile(history, 95)`
- [ ] Signal suppressed when `cost_ratio > 0.5` (returns 0.0)
- [ ] Signal attenuated by `(1 - cost_ratio)` when `cost_ratio <= 0.5`
- [ ] Empty history returns 0.0 for all properties (no crashes)

---

### Task 1B.5 — Implement Swap Rate Extraction and Forex Lot Sizing

**Tool:** Cursor
**Skill Reference:** `forex-broker-adapter > Swap Rate Extraction, Forex Lot Sizing`

**swap_rates.py:**

```python
def compute_annualized_carry(symbol: str) -> dict:
    """
    Converts MT5 swap points to annualized percentage.
    Formula: annual_swap = (swap_points × point × 365) / mid_price × 100

    Returns normalized carry_signal float consumed identically by alpha engine
    regardless of source (swaps in Stage A, term structure in Stage B).
    """
```

**lot_sizing.py:**

```python
def kelly_to_lots(equity: float, kelly_fraction: float,
                  stop_loss_pips: float, symbol: str,
                  account_currency: str = "USD") -> float:
    """
    Converts Kelly Criterion fraction to MT5 lot size.

    risk_amount = equity × kelly_fraction
    pip_value = contract_size × pip_size
    lots = risk_amount / (stop_loss_pips × pip_value)

    Handles: currency conversion when profit_currency ≠ account_currency,
    rounding to volume_step, clamping to volume_min/volume_max.
    """
```

**Output Files:**

```
src/execution/swap_rates.py
src/execution/lot_sizing.py
tests/execution/test_swap_rates.py
tests/execution/test_lot_sizing.py
```

**Validation:**

- [ ] Annualized carry for EURUSD with known swap values matches hand-calculated result
- [ ] 100K equity, 2% Kelly, 50 pip SL on EURUSD → correct lot size
- [ ] Lot size respects `volume_min` (never below minimum)
- [ ] Lot size respects `volume_max` (never above maximum)
- [ ] Lot size rounds to `volume_step` (e.g., 0.01 step rounds 0.137 → 0.14)
- [ ] Currency conversion: GBPUSD lot sizing with USD account correctly converts pip value

---

### Task 1B.6 — Implement ZeroMQ Bridge for Windows MT5 ↔ Linux Alpha Engines

**Tool:** Claude Code
**Skill Reference:** `forex-broker-adapter > ZeroMQ Bridge`, `zeromq-nats-react-ui > Stage A: Cross-Host Bridge`

Build the two-component bridge connecting Windows MT5 to Linux alpha engines over WireGuard VPN.

**Windows side (`windows_publisher.py`):**
- Connects to MT5 terminal
- Polls `symbol_info_tick()` at 10ms intervals per configured symbol
- Publishes ticks on ZMQ PUB `tcp://*:5556` with symbol as topic prefix
- Publishes completed bars on ZMQ PUB `tcp://*:5557`
- Accepts order requests on ZMQ PULL `tcp://*:5558`
- Returns order results on ZMQ PUSH `tcp://*:5559`
- Heartbeat messages every 5 seconds for connection health

**Linux side (`linux_consumer.py`):**
- Connects to Windows VPS via WireGuard: `tcp://10.200.0.1:555x`
- Subscribes to configured symbols on SUB sockets
- Converts received MessagePack messages to Tick/Bar dataclasses
- Feeds into ArcticDB writer and signal engines
- Auto-reconnect on disconnect (exponential backoff: 1s, 2s, 4s, max 30s)

**Message format:** MessagePack serialization for cross-platform compatibility.

**Output Files:**

```
src/execution/bridge/__init__.py
src/execution/bridge/windows_publisher.py
src/execution/bridge/linux_consumer.py
src/execution/bridge/message_schemas.py
tests/execution/bridge/test_bridge.py
```

**Validation:**

- [ ] MessagePack round-trip: pack→send→recv→unpack preserves all fields for Tick and Bar
- [ ] ZMQ PUB/SUB topic filtering: subscribing to "EURUSD" only receives EURUSD ticks
- [ ] Heartbeat: consumer detects publisher disconnect within 10 seconds
- [ ] Order round-trip: PUSH order request → PULL on Windows → execute → PUSH result → PULL on Linux
- [ ] Auto-reconnect: consumer recovers within 30 seconds after publisher restart

---

## Phase 1B Completion Gate

**All of the following must pass before proceeding to Phase 2:**

- [ ] All abstract interfaces have 100% method coverage in contract tests
- [ ] MT5Adapter tests pass with mocked `mt5` module (no Windows dependency in CI)
- [ ] SimAdapter passes identical interface contract tests as MT5Adapter
- [ ] SpreadModel `cost_adjusted_signal` correctly suppresses and attenuates signals
- [ ] Swap rate and lot sizing produce correct values on known test inputs
- [ ] ZMQ bridge MessagePack round-trip preserves all data fields
- [ ] `pytest tests/execution/ --cov=src/execution --cov-fail-under=85` passes
- [ ] All pre-commit hooks pass on the new code
- [ ] `make all` (lint + typecheck + validate + test) passes

---

## PHASE 1 COMPLETE

Phase 1 delivers:

1. **A validated CI/CD pipeline** — every line of code passes through AST validation, PiT compliance checking, type checking, linting, and coverage enforcement before it can be committed.

2. **A complete, broker-agnostic execution layer** — abstract interfaces (`MarketDataProvider`, `OrderExecutor`, `PositionManager`) that all downstream code uses, with concrete implementations for MT5 (production), simulation (backtesting/testing), and stubs for CME (Stage B).

Every subsequent phase writes code that passes through these quality gates. Every alpha engine, risk engine, and dashboard component codes against `abstract.py`, never directly against MT5 or any broker API.
