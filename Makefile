.PHONY: lint typecheck test test-integration validate install-vbt all

install-vbt:
	@[ -n "$$VBT_TOKEN" ] || (echo "ERROR: VBT_TOKEN is not set. Copy .env.example to .env and set your token." && exit 1)
	.venv/bin/pip install vectorbtpro==2026.3.1 \
		--extra-index-url "https://$$VBT_TOKEN@packages.vectorbt.pro/simple/"

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
	.venv/bin/python scripts/pit_validator.py --source src/alpha/ --source src/data/ --source src/backtest/

all: lint typecheck validate test
