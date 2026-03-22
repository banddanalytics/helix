"""Shared fixtures for Phase 3 alpha engine tests."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.alpha.signal_types import SIGNAL_COLUMNS


@pytest.fixture
def synthetic_returns() -> np.ndarray[tuple[int], np.dtype[np.float64]]:
    """1000-bar regime-switching return series with 3 distinct regimes.

    Regime 0 (Trending): low-vol, positive drift  — bars   0..332
    Regime 1 (Mean-Rev): moderate-vol, zero drift — bars 333..665
    Regime 2 (Crisis):   high-vol, negative drift  — bars 666..999
    Seeded with np.random.default_rng(42) for reproducibility.
    """
    rng = np.random.default_rng(42)
    trending = rng.normal(loc=0.0002, scale=0.005, size=333)
    mean_rev = rng.normal(loc=0.0000, scale=0.012, size=333)
    crisis = rng.normal(loc=-0.001, scale=0.025, size=334)
    return np.concatenate([trending, mean_rev, crisis])


@pytest.fixture
def synthetic_bars(
    synthetic_returns: np.ndarray[tuple[int], np.dtype[np.float64]],
) -> pd.DataFrame:
    """1000-row OHLCV DataFrame derived from synthetic_returns.

    Index: pd.DatetimeIndex at 4-hour frequency starting 2020-01-01.
    Columns: open, high, low, close, tick_volume, session (int8).
    session cycles 0-3 (Asian=0, London=1, Overlap=2, NY=3).
    """
    rng = np.random.default_rng(seed=99)
    n = len(synthetic_returns)

    close = 1.1000 * np.exp(np.cumsum(synthetic_returns))
    noise = rng.uniform(0.0001, 0.0010, size=n)
    open_ = close * (1 + rng.uniform(-0.0005, 0.0005, size=n))
    high = np.maximum(open_, close) + noise
    low = np.minimum(open_, close) - noise
    tick_volume = rng.integers(50, 500, size=n).astype(float)

    index = pd.date_range("2020-01-01", periods=n, freq="4h")
    session = (np.arange(n) % 4).astype("int8")

    return pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "tick_volume": tick_volume,
            "session": session,
        },
        index=index,
    )


_SYMBOLS = ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDJPY", "USDCHF"]


@pytest.fixture
def six_symbol_bars(synthetic_bars: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Dict mapping each of the 6 configured symbols to a OHLCV DataFrame.

    Each symbol gets a slightly different random seed to vary the data,
    while keeping the same regime structure as synthetic_bars.
    """
    result: dict[str, pd.DataFrame] = {}
    for i, symbol in enumerate(_SYMBOLS):
        rng = np.random.default_rng(seed=i + 10)
        n = len(synthetic_bars)
        offset = rng.uniform(-0.0002, 0.0002, size=n)
        copy = synthetic_bars.copy()
        for col in ("open", "high", "low", "close"):
            copy[col] = copy[col] + offset
        result[symbol] = copy
    return result


@pytest.fixture
def mock_signal_df() -> pd.DataFrame:
    """10-row DataFrame matching the SIGNAL_COLUMNS schema from signal_types.

    Contains realistic mixed-engine, mixed-direction test data.
    """
    rows = [
        ("EURUSD", "ml", 1, 0.72, 0, None, 0.61, None),
        ("GBPUSD", "ml", -1, 0.55, 0, None, 0.41, None),
        ("AUDUSD", "carry", 1, 0.80, 0, None, None, 0.85),
        ("NZDUSD", "carry", 0, 0.50, 1, None, None, 0.50),
        ("EURUSD", "cointegration", 1, 0.65, 1, -2.35, None, None),
        ("GBPUSD", "cointegration", -1, 0.70, 1, 2.60, None, None),
        ("USDJPY", "ml", 0, 0.50, 0, None, 0.50, None),
        ("USDCHF", "carry", -1, 0.60, 0, None, None, 0.20),
        ("AUDUSD", "cointegration", 1, 0.55, 1, -2.05, None, None),
        ("EURUSD", "ml", 1, 0.78, 0, None, 0.65, None),
    ]
    return pd.DataFrame(rows, columns=SIGNAL_COLUMNS)
