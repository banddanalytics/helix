"""Signal schema types for Phase 3 alpha engines."""

from __future__ import annotations

import enum
from dataclasses import dataclass

import numpy as np


class RegimeState(enum.IntEnum):
    """HMM regime states, ordered by ascending unconditional variance."""

    TRENDING = 0
    MEAN_REVERTING = 1
    CRISIS = 2


@dataclass
class SignalRow:
    """Single signal output from any alpha engine (per D-01)."""

    symbol: str
    engine: str
    direction: np.int8  # +1 / 0 / -1
    strength: np.float32  # [0, 1]
    regime: np.int8  # RegimeState value at signal time
    z_score: np.float32 | None = None  # cointegration engine
    ml_prob: np.float32 | None = None  # ML engine
    carry_rank: np.float32 | None = None  # carry engine


SIGNAL_COLUMNS: list[str] = [
    "symbol",
    "engine",
    "direction",
    "strength",
    "regime",
    "z_score",
    "ml_prob",
    "carry_rank",
]

# ArcticDB symbol naming patterns
ENGINE_SYMBOL_PATTERN: str = "{engine}_{symbol}"  # D-02
REGIME_SYMBOL_PATTERN: str = "regime_{symbol}"  # D-03
