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
    direction: int  # int8: +1 / 0 / -1
    strength: float  # float32 [0, 1]
    regime: int  # int8, current RegimeState value at signal time
    z_score: float | None = None  # cointegration engine
    ml_prob: float | None = None  # ML engine
    carry_rank: float | None = None  # carry engine


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

# Engine activation per regime (D-05)
REGIME_ACTIVATION: dict[RegimeState, list[str]] = {
    RegimeState.TRENDING: ["ml_engine", "carry_engine"],
    RegimeState.MEAN_REVERTING: ["cointegration_engine"],
    RegimeState.CRISIS: [],
}

# Configured cointegration pairs (D-04)
CONFIGURED_PAIRS: list[tuple[str, str]] = [
    ("AUDUSD", "NZDUSD"),
    ("EURUSD", "GBPUSD"),
    ("USDJPY", "USDCHF"),
]

# All cross-asset symbols tracked by the system
CROSS_ASSET_SYMBOLS: list[str] = [
    "EURUSD",
    "GBPUSD",
    "AUDUSD",
    "NZDUSD",
    "USDJPY",
    "USDCHF",
]

# ArcticDB symbol naming patterns
ENGINE_SYMBOL_PATTERN: str = "{engine}_{symbol}"  # D-02
REGIME_SYMBOL_PATTERN: str = "regime_{symbol}"  # D-03

__all__ = [
    "RegimeState",
    "SignalRow",
    "SIGNAL_COLUMNS",
    "REGIME_ACTIVATION",
    "CONFIGURED_PAIRS",
    "CROSS_ASSET_SYMBOLS",
    "ENGINE_SYMBOL_PATTERN",
    "REGIME_SYMBOL_PATTERN",
]
