#!/usr/bin/env bash
# Warmup Numba JIT cache for all @njit functions
set -euo pipefail
cd "$(dirname "$0")/.."
export NUMBA_CACHE_DIR=./numba_cache
.venv/bin/python -c "from src.backtest.warmup import warmup_numba; warmup_numba()"
echo "Numba cache warmed up at $NUMBA_CACHE_DIR"
