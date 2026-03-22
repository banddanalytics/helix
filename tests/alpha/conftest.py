"""Shared fixtures for Phase 3 alpha engine tests."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.alpha.signal_types import SIGNAL_COLUMNS, RegimeState


@pytest.fixture
def synthetic_returns() -> np.ndarray[tuple[int], np.dtype[np.float64]]:
    """2000-bar regime-switching return series with 3 distinct regimes.

    Regime 0 (Trending):   low-vol, positive drift  — bars    0..665
    Regime 1 (Mean-Rev):  moderate-vol, zero drift  — bars  666..1331
    Regime 2 (Crisis):     high-vol, negative drift — bars 1332..1999
    Seeded with np.random.default_rng(42) for reproducibility.
    """
    rng = np.random.default_rng(42)
    trending = rng.normal(loc=0.0002, scale=0.005, size=666)
    mean_rev = rng.normal(loc=0.0000, scale=0.010, size=666)
    crisis = rng.normal(loc=-0.001, scale=0.030, size=668)
    return np.concatenate([trending, mean_rev, crisis])


@pytest.fixture
def cointegrated_pair() -> tuple[np.ndarray[tuple[int], np.dtype[np.float64]], np.ndarray[tuple[int], np.dtype[np.float64]]]:
    """Pair of 1000-bar price series with known cointegration (hedge ratio ~0.8).

    y1 is a random walk; y2 = 0.8 * y1 + stationary noise.
    The true hedge ratio is exactly 0.8 for regression-based methods.
    """
    rng = np.random.default_rng(123)
    n = 1000
    innovations = rng.normal(0, 1, size=n)
    y1 = np.cumsum(innovations)
    noise = rng.normal(0, 0.5, size=n)
    y2 = 0.8 * y1 + noise
    return y1, y2


@pytest.fixture
def sample_bar_data() -> dict[str, np.ndarray[tuple[int], np.dtype[np.float64]]]:
    """500-bar OHLCV dict with keys: open, high, low, close, tick_volume.

    All values are np.ndarrays of float64. close follows a random walk
    seeded for reproducibility.
    """
    rng = np.random.default_rng(77)
    n = 500
    returns = rng.normal(0, 0.001, size=n)
    close = 1.1000 * np.exp(np.cumsum(returns))
    noise = rng.uniform(0.0001, 0.0010, size=n)
    open_ = close * (1 + rng.uniform(-0.0005, 0.0005, size=n))
    high = np.maximum(open_, close) + noise
    low = np.minimum(open_, close) - noise
    tick_volume = rng.integers(50, 500, size=n).astype(float)
    return {
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "tick_volume": tick_volume,
    }


@pytest.fixture
def sample_signal_df() -> pd.DataFrame:
    """10-row DataFrame matching the SIGNAL_COLUMNS schema from signal_types.

    Contains realistic mixed-engine, mixed-direction test data spanning
    all 3 regimes and all 3 engine types.
    """
    rows = [
        ("EURUSD", "ml_engine", 1, 0.72, RegimeState.TRENDING, None, 0.61, None),
        ("GBPUSD", "ml_engine", -1, 0.55, RegimeState.TRENDING, None, 0.41, None),
        ("AUDUSD", "carry_engine", 1, 0.80, RegimeState.TRENDING, None, None, 0.85),
        ("NZDUSD", "carry_engine", 0, 0.50, RegimeState.MEAN_REVERTING, None, None, 0.50),
        ("EURUSD", "cointegration_engine", 1, 0.65, RegimeState.MEAN_REVERTING, -2.35, None, None),
        ("GBPUSD", "cointegration_engine", -1, 0.70, RegimeState.MEAN_REVERTING, 2.60, None, None),
        ("USDJPY", "ml_engine", 0, 0.50, RegimeState.TRENDING, None, 0.50, None),
        ("USDCHF", "carry_engine", -1, 0.60, RegimeState.TRENDING, None, None, 0.20),
        ("AUDUSD", "cointegration_engine", 1, 0.55, RegimeState.MEAN_REVERTING, -2.05, None, None),
        ("EURUSD", "ml_engine", 1, 0.78, RegimeState.CRISIS, None, 0.65, None),
    ]
    return pd.DataFrame(rows, columns=SIGNAL_COLUMNS)


@pytest.fixture
def synthetic_bars(
    synthetic_returns: np.ndarray[tuple[int], np.dtype[np.float64]],
) -> pd.DataFrame:
    """2000-row OHLCV DataFrame derived from synthetic_returns.

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
    """Dict mapping each of the 6 configured symbols to an OHLCV DataFrame.

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

    Alias for sample_signal_df, kept for backward compatibility with
    existing test stubs that reference mock_signal_df.
    """
    rows = [
        ("EURUSD", "ml_engine", 1, 0.72, int(RegimeState.TRENDING), None, 0.61, None),
        ("GBPUSD", "ml_engine", -1, 0.55, int(RegimeState.TRENDING), None, 0.41, None),
        ("AUDUSD", "carry_engine", 1, 0.80, int(RegimeState.TRENDING), None, None, 0.85),
        ("NZDUSD", "carry_engine", 0, 0.50, int(RegimeState.MEAN_REVERTING), None, None, 0.50),
        ("EURUSD", "cointegration_engine", 1, 0.65, int(RegimeState.MEAN_REVERTING), -2.35, None, None),
        ("GBPUSD", "cointegration_engine", -1, 0.70, int(RegimeState.MEAN_REVERTING), 2.60, None, None),
        ("USDJPY", "ml_engine", 0, 0.50, int(RegimeState.TRENDING), None, 0.50, None),
        ("USDCHF", "carry_engine", -1, 0.60, int(RegimeState.TRENDING), None, None, 0.20),
        ("AUDUSD", "cointegration_engine", 1, 0.55, int(RegimeState.MEAN_REVERTING), -2.05, None, None),
        ("EURUSD", "ml_engine", 1, 0.78, int(RegimeState.CRISIS), None, 0.65, None),
    ]
    return pd.DataFrame(rows, columns=SIGNAL_COLUMNS)
