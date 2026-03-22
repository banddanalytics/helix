"""Ground-truth numba API stub for KCH validator.

Covers the numba functions used in Helix backtest accumulators.
"""

from __future__ import annotations

STUB: dict[str, dict[str, set[str]]] = {
    "numba": {
        "njit": {"func_or_sig", "cache", "parallel", "fastmath", "nogil", "boundscheck", "error_model"},
        "jit": {"func_or_sig", "nopython", "cache", "parallel", "fastmath", "nogil"},
        "vectorize": {"signatures", "target", "cache", "nopython"},
        "guvectorize": {"signatures", "layout", "target", "cache", "nopython"},
        "typeof": {"val"},
        "typed": set(),
        "types": set(),
        "prange": {"start", "stop", "step"},
    }
}

SUBMODULES: list[str] = [
    "njit",
    "jit",
    "vectorize",
    "prange",
    "types",
    "typed",
]
