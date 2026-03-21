.PHONY: lint typecheck test test-integration validate all

lint:
	.venv/bin/ruff check . && .venv/bin/ruff format --check .

typecheck:
	.venv/bin/mypy src/ --strict

test:
	.venv/bin/pytest tests/ --cov=src --cov-fail-under=80 --cov-branch -v

test-integration:
	.venv/bin/pytest tests/integration/ -v --timeout=60

validate:
	.venv/bin/python scripts/ast_validator.py --stubs stubs/ --source src/
	.venv/bin/python scripts/pit_validator.py --source src/alpha/

all: lint typecheck validate test
