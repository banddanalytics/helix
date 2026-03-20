---
name: ast-tdd-validation
description: >
  Implement AST-based deterministic validation for LLM-generated code and the Testing
  Trophy CI/CD methodology. Stage-agnostic — code quality standards are identical whether
  trading Forex or futures. Covers AST parsing to verify code against library stubs,
  Knowledge Conflicting Hallucination (KCH) prevention, stub auto-generation from installed
  libraries, Testing Trophy test hierarchy (static > integration > unit > e2e), 80% coverage
  enforcement, pytest-cov configuration, mypy strict mode, Ruff linting, pre-commit hooks,
  GitHub Actions CI pipeline, and Hypothesis property-based tests. Use this skill for:
  code validation, AST analysis, LLM output verification, test strategy, CI/CD, coverage
  enforcement, or hallucination detection in generated code.
---

# AST TDD Validation Skill

## Purpose

When development relies on LLM-assisted coding (Cursor, Claude Code, Claude CLI),
Knowledge Conflicting Hallucinations (KCH) can produce code using non-existent functions,
wrong parameters, or deprecated APIs. This skill catches KCH before code enters the
test suite or production. Applies identically to both Stage A and Stage B code.

## KCH Taxonomy

| Type             | Example                                  | Detection       |
|------------------|------------------------------------------|-----------------|
| Phantom function | `arcticdb.Library.upsert()` (nonexistent)| AST + stubs     |
| Wrong parameter  | `zmq.Socket(zmq.DEALER)` vs `zmq.PAIR`  | Signature check  |
| Wrong return     | Assuming `lib.read()` → DataFrame        | Return type      |
| Deprecated API   | Using pandas `.append()` (removed 2.0)   | Deprecation list |
| Import phantom   | `from arcticdb import QueryBuilder`      | Import resolve   |

## AST Validation Pipeline

### Stage 1: Extract API Calls from Source

```python
import ast

class ASTExtractor(ast.NodeVisitor):
    def __init__(self):
        self.imports = []
        self.function_calls = []
        self.attribute_accesses = []
    
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
    
    def _extract_call(self, node):
        if isinstance(node.func, ast.Attribute):
            return {
                'func': node.func.attr,
                'kwargs': {kw.arg for kw in node.keywords},
                'lineno': node.lineno
            }
        return None
```

### Stage 2: Library Stubs (Ground Truth)

Auto-generated from installed libraries. Covers BOTH stage adapters:

```python
# stubs/arcticdb_stubs.py
ARCTICDB_STUBS = {
    'Library': {
        'write': {'params': ['symbol','data','metadata','prune_previous_versions']},
        'read': {'params': ['symbol','as_of','date_range','columns','query_builder']},
        'append': {'params': ['symbol','data','metadata','prune_previous_versions']},
        'list_symbols': {'params': []},
        'delete': {'params': ['symbol']},
        'snapshot': {'params': ['snap_name','metadata','skip_symbols','versions']},
        # NOTE: 'upsert' does NOT exist — common KCH
    }
}

# stubs/mt5_stubs.py (Stage A)
MT5_STUBS = {
    'copy_ticks_range': {'params': ['symbol','date_from','date_to','flags']},
    'copy_rates_from_pos': {'params': ['symbol','timeframe','start_pos','count']},
    'order_send': {'params': ['request']},
    'symbol_info': {'params': ['symbol']},
    'symbol_info_tick': {'params': ['symbol']},
    'positions_get': {'params': ['symbol','group','ticket']},
    'account_info': {'params': []},
}

# stubs/zmq_stubs.py, stubs/nats_stubs.py, stubs/xgboost_stubs.py, etc.
```

### Stage 3: Validate

```python
class KCHValidator:
    def __init__(self, stubs):
        self.stubs = stubs
    
    def validate(self, source_code: str) -> list[dict]:
        tree = ast.parse(source_code)
        extractor = ASTExtractor()
        extractor.visit(tree)
        violations = []
        
        for call in extractor.function_calls:
            result = self._check_call(call)
            if result:
                violations.append(result)
        
        return violations
    
    def _check_call(self, call):
        func = call['func']
        for cls, methods in self.stubs.items():
            if func in methods:
                stub = methods[func]
                for kwarg in call['kwargs']:
                    if kwarg not in stub['params']:
                        return {
                            'type': 'WRONG_PARAMETER',
                            'severity': 'CRITICAL',
                            'lineno': call['lineno'],
                            'detail': f"{cls}.{func}() has no param '{kwarg}'",
                            'valid': stub['params']
                        }
                return None
        return None  # Not in stubs — might be user-defined
```

### Stage 4: Stub Auto-Generation

```python
import importlib, inspect

def generate_stubs(module_name: str, classes: list[str]) -> dict:
    module = importlib.import_module(module_name)
    stubs = {}
    for cls_name in classes:
        cls = getattr(module, cls_name)
        methods = {}
        for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
            if name.startswith('_') and name != '__init__':
                continue
            sig = inspect.signature(method)
            params = [p.name for p in sig.parameters.values() if p.name != 'self']
            methods[name] = {'params': params}
        stubs[cls_name] = methods
    return stubs
```

## Testing Trophy Methodology

```
          ╱╲
         ╱E2E╲           (~20%: full pipeline smoke tests)
        ╱──────╲
       ╱ Integr. ╲       (~60%: cross-module, DB, network)
      ╱────────────╲
     ╱    Unit      ╲     (~20%: pure math, serialization)
    ╱────────────────╲
   ╱   Static/AST    ╲    (foundation: types, KCH, lint)
  ╱────────────────────╲
```

### Coverage Enforcement: 80% Minimum

```toml
# pyproject.toml
[tool.pytest.ini_options]
addopts = "--cov=src --cov-report=term-missing --cov-branch --cov-fail-under=80"

[tool.coverage.run]
branch = true
omit = ["tests/*", "stubs/*"]

[tool.coverage.report]
fail_under = 80
show_missing = true
```

### Type Checking: mypy Strict

```toml
[tool.mypy]
python_version = "3.12"
strict = true
warn_unreachable = true

[[tool.mypy.overrides]]
module = ["MetaTrader5.*", "hmmlearn.*", "arch.*", "vectorbt.*", "arcticdb.*"]
ignore_missing_imports = true
```

### Linting: Ruff

```toml
[tool.ruff]
target-version = "py312"
line-length = 88

[tool.ruff.lint]
select = ["E","W","F","I","N","UP","B","SIM","ANN","S","C4","DTZ","RUF"]
```

### Pre-Commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    hooks: [{id: ruff, args: [--fix]}, {id: ruff-format}]
  - repo: https://github.com/pre-commit/mirrors-mypy
    hooks: [{id: mypy}]
  - repo: local
    hooks:
      - id: ast-validation
        name: KCH Validator
        language: python
        entry: python scripts/ast_validator.py
        files: '\.py$'
      - id: pit-check
        name: PiT Compliance
        language: python
        entry: python scripts/pit_validator.py
        files: 'alpha/.*\.py$'
```

### GitHub Actions CI

```yaml
name: Trading System CI
on: [push, pull_request]
jobs:
  static:
    steps:
      - run: ruff check . && ruff format --check .
      - run: mypy src/ --strict
      - run: python -m ast_validator --stubs stubs/ --source src/
  
  tests:
    needs: static
    services:
      nats: {image: "nats:latest", ports: ["4222:4222"]}
    steps:
      - run: pytest --cov=src --cov-fail-under=80 --cov-branch -v
  
  e2e:
    needs: tests
    if: github.ref == 'refs/heads/main'
    steps:
      - run: pytest tests/e2e/ -v --timeout=300
```

### CI Gating Rules

| Gate             | Trigger                      | Blocks      |
|------------------|------------------------------|-------------|
| KCH CRITICAL     | Any phantom function/param   | Merge       |
| Coverage < 80%   | Combined unit+integration    | Merge       |
| PiT Violation    | Missing .shift() in signals  | Merge       |
| mypy Error       | Any type error               | Merge       |
| Integration Fail | Any integration test failure | Merge       |
| E2E Fail         | Shadow trading failure       | Deploy      |

## Implementation Structure

```
./src/quality/
  ast_validator/
    extractor.py, validator.py, stub_generator.py
  stubs/
    arcticdb_stubs.py, mt5_stubs.py, zmq_stubs.py
    nats_stubs.py, xgboost_stubs.py, hmmlearn_stubs.py
./tests/
  conftest.py             (Shared fixtures)
  unit/, integration/, e2e/, properties/
.pre-commit-config.yaml
.github/workflows/ci.yml
pyproject.toml            (pytest, coverage, mypy, ruff config)
```
