---
name: ast-tdd-validation
description: >
  Implement the AST-based deterministic validation pipeline for LLM-generated code and the
  Testing Trophy CI/CD methodology. Covers Abstract Syntax Tree parsing to verify generated
  code against real library schemas (ArcticDB, VectorBT Pro, ZeroMQ, NATS APIs), Knowledge
  Conflicting Hallucination (KCH) prevention by validating function signatures, parameter
  types, and return types against ground-truth library stubs, the Testing Trophy test
  hierarchy (unit < integration < e2e), 80% coverage enforcement, and CI gating triggers
  for the Cursor/Claude Code development workflow. Use this skill whenever working on:
  code validation, AST analysis, LLM output verification, test strategy, CI/CD pipelines,
  code quality enforcement, hallucination detection in generated code, Testing Trophy
  methodology, or any task involving code integrity. Also trigger when the user mentions
  "AST validation", "code verification", "KCH", "hallucination prevention", "Testing Trophy",
  "test coverage", "CI gating", "library schema validation", "Cursor validation", or
  "Claude Code testing".
---

# AST TDD Validation Skill

## Purpose

When development relies on LLM-assisted coding (Cursor, Claude Code, Claude CLI), there is
a measurable risk of Knowledge Conflicting Hallucinations (KCH) — where the LLM generates
code that uses non-existent functions, incorrect parameter names, wrong return types, or
deprecated API patterns. This skill defines a deterministic validation pipeline that catches
KCH before code enters the test suite or production.

## Knowledge Conflicting Hallucination (KCH) Taxonomy

| KCH Type          | Example                                           | Detection Method     |
|-------------------|---------------------------------------------------|----------------------|
| Phantom function  | `arcticdb.Library.upsert()` (doesn't exist)       | AST + stub matching  |
| Wrong parameters  | `zmq.Socket(zmq.DEALER)` instead of `zmq.PAIR`    | Signature validation |
| Wrong return type | Assuming `lib.read()` returns DataFrame directly   | Return type checking |
| Deprecated API    | Using `vbt.Portfolio.from_signals()` (old API)     | Version-pinned stubs |
| Import phantom    | `from arcticdb import QueryBuilder` (wrong path)   | Import resolution    |
| Method confusion  | Mixing pandas `.append()` (removed in 2.0) usage   | Deprecation registry |

## AST Validation Pipeline

### Stage 1: Parse and Extract

```python
import ast
import inspect
from typing import Dict, List, Set, Tuple

class ASTExtractor(ast.NodeVisitor):
    """
    Walk the AST of generated code and extract all external API calls,
    imports, and attribute accesses.
    """
    def __init__(self):
        self.imports: List[str] = []              # import statements
        self.function_calls: List[dict] = []      # {module, func, args, kwargs, lineno}
        self.attribute_accesses: List[dict] = []  # {object, attr, lineno}
    
    def visit_Import(self, node):
        for alias in node.names:
            self.imports.append(alias.name)
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node):
        for alias in node.names:
            self.imports.append(f"{node.module}.{alias.name}")
        self.generic_visit(node)
    
    def visit_Call(self, node):
        call_info = self._extract_call_info(node)
        if call_info:
            self.function_calls.append(call_info)
        self.generic_visit(node)
    
    def visit_Attribute(self, node):
        self.attribute_accesses.append({
            'object': ast.dump(node.value),
            'attr': node.attr,
            'lineno': node.lineno
        })
        self.generic_visit(node)
    
    def _extract_call_info(self, node) -> dict:
        """Extract function name, arguments, and keyword arguments from a Call node."""
        if isinstance(node.func, ast.Attribute):
            return {
                'func': node.func.attr,
                'args': [ast.dump(a) for a in node.args],
                'kwargs': {kw.arg: ast.dump(kw.value) for kw in node.keywords},
                'lineno': node.lineno
            }
        elif isinstance(node.func, ast.Name):
            return {
                'func': node.func.id,
                'args': [ast.dump(a) for a in node.args],
                'kwargs': {kw.arg: ast.dump(kw.value) for kw in node.keywords},
                'lineno': node.lineno
            }
        return None
```

### Stage 2: Ground-Truth Library Stubs

Maintain version-pinned stub definitions for every external library the system uses.
These stubs are the single source of truth — NOT the LLM's training data.

```python
# stubs/arcticdb_stubs.py — generated from actual library introspection
ARCTICDB_STUBS = {
    'Arctic': {
        '__init__': {'params': ['uri'], 'return': 'Arctic'},
        'get_library': {'params': ['name', 'create_if_missing'], 'return': 'Library'},
        'list_libraries': {'params': [], 'return': 'List[str]'},
    },
    'Library': {
        'write': {'params': ['symbol', 'data', 'metadata', 'prune_previous_versions'], 'return': 'VersionedItem'},
        'read': {'params': ['symbol', 'as_of', 'date_range', 'columns', 'query_builder'], 'return': 'VersionedItem'},
        'append': {'params': ['symbol', 'data', 'metadata', 'prune_previous_versions'], 'return': 'VersionedItem'},
        'list_symbols': {'params': [], 'return': 'List[str]'},
        'delete': {'params': ['symbol'], 'return': 'None'},
        'snapshot': {'params': ['snap_name', 'metadata', 'skip_symbols', 'versions'], 'return': 'None'},
        # NOTE: 'upsert' does NOT exist — this is a common KCH
    },
    'QueryBuilder': {
        '__init__': {'params': [], 'return': 'QueryBuilder'},
        # Accessed via indexing syntax, not method calls
    }
}

# stubs/zmq_stubs.py
ZMQ_STUBS = {
    'Context': {
        '__init__': {'params': ['io_threads'], 'return': 'Context'},
        'socket': {'params': ['socket_type'], 'return': 'Socket'},
        'term': {'params': [], 'return': 'None'},
    },
    'Socket': {
        'bind': {'params': ['addr'], 'return': 'None'},
        'connect': {'params': ['addr'], 'return': 'None'},
        'send': {'params': ['data', 'flags'], 'return': 'None'},
        'recv': {'params': ['flags'], 'return': 'bytes'},
        'send_multipart': {'params': ['msg_parts', 'flags'], 'return': 'None'},
        'setsockopt': {'params': ['option', 'value'], 'return': 'None'},
        'setsockopt_string': {'params': ['option', 'value', 'encoding'], 'return': 'None'},
        'close': {'params': [], 'return': 'None'},
    },
    'SOCKET_TYPES': ['PAIR', 'PUB', 'SUB', 'REQ', 'REP', 'DEALER', 'ROUTER', 'PULL', 'PUSH', 'XPUB', 'XSUB'],
}
```

### Stage 3: Validation Engine

```python
class KCHValidator:
    """
    Validates LLM-generated code against ground-truth library stubs.
    Returns a list of KCH violations with severity and fix suggestions.
    """
    def __init__(self, stubs: Dict[str, dict]):
        self.stubs = stubs
    
    def validate(self, source_code: str) -> List[dict]:
        """Parse source code and check all API calls against stubs."""
        tree = ast.parse(source_code)
        extractor = ASTExtractor()
        extractor.visit(tree)
        
        violations = []
        
        # Check imports
        for imp in extractor.imports:
            if not self._validate_import(imp):
                violations.append({
                    'type': 'PHANTOM_IMPORT',
                    'severity': 'CRITICAL',
                    'detail': f"Import '{imp}' not found in library stubs",
                    'suggestion': self._suggest_import(imp)
                })
        
        # Check function calls
        for call in extractor.function_calls:
            result = self._validate_call(call)
            if result:
                violations.append(result)
        
        return violations
    
    def _validate_call(self, call: dict) -> dict | None:
        """Check if a function call matches the stub definition."""
        func_name = call['func']
        
        # Search for this function across all stub classes
        for class_name, methods in self.stubs.items():
            if func_name in methods:
                stub = methods[func_name]
                
                # Check parameter names
                for kwarg in call['kwargs']:
                    if kwarg not in stub['params']:
                        return {
                            'type': 'WRONG_PARAMETER',
                            'severity': 'CRITICAL',
                            'lineno': call['lineno'],
                            'detail': f"{class_name}.{func_name}() has no parameter '{kwarg}'",
                            'valid_params': stub['params'],
                            'suggestion': self._suggest_param(kwarg, stub['params'])
                        }
                
                return None  # Valid call
        
        # Function not found in any stub — potential phantom
        return {
            'type': 'PHANTOM_FUNCTION',
            'severity': 'WARNING',  # WARNING because it might be user-defined
            'lineno': call['lineno'],
            'detail': f"Function '{func_name}' not found in library stubs",
            'suggestion': 'Verify this function exists in the target library version'
        }
    
    def _suggest_param(self, wrong_param: str, valid_params: list) -> str:
        """Suggest the closest valid parameter name (Levenshtein distance)."""
        from difflib import get_close_matches
        matches = get_close_matches(wrong_param, valid_params, n=1, cutoff=0.6)
        return f"Did you mean '{matches[0]}'?" if matches else "No close match found"
```

### Stage 4: Stub Auto-Generation

Stubs should be auto-generated from installed libraries, not hand-written:

```python
import importlib
import inspect

def generate_stubs(module_name: str, classes: List[str]) -> dict:
    """
    Introspect an installed library and generate ground-truth stubs.
    Run this once per library version update to refresh stubs.
    """
    module = importlib.import_module(module_name)
    stubs = {}
    
    for class_name in classes:
        cls = getattr(module, class_name)
        methods = {}
        
        for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
            if name.startswith('_') and name != '__init__':
                continue
            sig = inspect.signature(method)
            params = [p.name for p in sig.parameters.values() if p.name != 'self']
            return_annotation = sig.return_annotation
            
            methods[name] = {
                'params': params,
                'return': str(return_annotation) if return_annotation != inspect.Parameter.empty else 'Unknown'
            }
        
        stubs[class_name] = methods
    
    return stubs

# Usage: generate stubs from installed arcticdb
# arcticdb_stubs = generate_stubs('arcticdb', ['Arctic', 'Library', 'QueryBuilder'])
```

## Testing Trophy Methodology

The Testing Trophy inverts the traditional testing pyramid — more integration tests,
fewer unit tests, because integration tests catch more real bugs in trading systems.

```
          ╱╲
         ╱E2E╲         (few: full system smoke tests)
        ╱──────╲
       ╱ Integr. ╲     (many: cross-module, DB, network)
      ╱────────────╲
     ╱    Unit      ╲   (moderate: pure functions, math)
    ╱────────────────╲
   ╱   Static/AST    ╲  (foundation: type checks, KCH validation)
  ╱────────────────────╲
```

### Test Distribution Target

| Layer        | Coverage Target | Description                                        |
|--------------|----------------|----------------------------------------------------|
| Static/AST   | 100% of files  | Every file passes KCH validation + mypy             |
| Unit          | 80% lines      | Math functions, Numba kernels, serialization         |
| Integration   | 60% paths      | ArcticDB read/write, ZMQ roundtrip, NATS delivery   |
| E2E           | Critical paths  | Signal → Order → Fill → PnL (shadow mode)           |

### 80% Coverage Enforcement

```yaml
# pytest.ini / pyproject.toml
[tool.pytest.ini_options]
addopts = "--cov=. --cov-report=html --cov-fail-under=80"
testpaths = ["tests"]

[tool.coverage.run]
branch = true
omit = ["tests/*", "stubs/*", "scripts/*"]

[tool.coverage.report]
fail_under = 80
show_missing = true
```

## CI/CD Pipeline (Gating Triggers)

```yaml
# .github/workflows/ci.yml
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
      - name: AST/KCH Validation
        run: python -m ast_validator --stubs ./stubs/ --source ./
      - name: MyPy Type Check
        run: mypy . --strict
      - name: Ruff Lint
        run: ruff check .

  unit-tests:
    needs: static-analysis
    runs-on: ubuntu-latest
    steps:
      - name: Run Unit Tests
        run: pytest tests/unit/ -v --cov --cov-fail-under=80
      - name: PiT Compliance Check
        run: pytest tests/ -m pit_check -v

  integration-tests:
    needs: unit-tests
    runs-on: ubuntu-latest
    services:
      nats:
        image: nats:latest
        ports: ["4222:4222"]
    steps:
      - name: Run Integration Tests
        run: pytest tests/integration/ -v --timeout=60
      - name: ZMQ Roundtrip Test
        run: pytest tests/integration/test_zmq_routing.py -v
      - name: ArcticDB Read/Write Test
        run: pytest tests/integration/test_arcticdb.py -v

  e2e-tests:
    needs: integration-tests
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - name: Shadow Trading E2E
        run: pytest tests/e2e/test_shadow_trading.py -v --timeout=300

  coverage-gate:
    needs: [unit-tests, integration-tests]
    runs-on: ubuntu-latest
    steps:
      - name: Enforce 80% Coverage
        run: |
          coverage combine
          coverage report --fail-under=80
```

### Gating Rules

| Gate             | Trigger                           | Block Level |
|------------------|-----------------------------------|-------------|
| KCH Found        | Any CRITICAL KCH violation        | Block merge  |
| Coverage < 80%   | Combined unit+integration         | Block merge  |
| PiT Violation    | Any .shift() missing in signals   | Block merge  |
| MyPy Error       | Any type error in strict mode     | Block merge  |
| Integration Fail | Any integration test failure      | Block merge  |
| E2E Fail         | Shadow trading test failure       | Block deploy |

## Implementation Structure

```
./quality/
  ast_validator/
    __init__.py
    extractor.py       (ASTExtractor)
    validator.py        (KCHValidator)
    stub_generator.py   (auto-generate stubs from libraries)
  stubs/
    arcticdb_stubs.py
    zmq_stubs.py
    nats_stubs.py
    vectorbt_stubs.py
    xgboost_stubs.py
  testing/
    conftest.py         (shared fixtures)
    pit_plugin.py       (pytest plugin for PiT checks)
    coverage_config.py
  ci/
    ci.yml              (GitHub Actions workflow)
    pre-commit-config.yaml
```

Read `prompts/` for tool-specific implementation prompts.
