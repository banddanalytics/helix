"""Tests for BacktestRunner and Numba warmup (DATA-05 reproducibility, DATA-07)."""
from __future__ import annotations

import time

import numpy as np
import pandas as pd
import pytest


def _make_synthetic_store(store_uri: str) -> None:
    """Write synthetic EURUSD_1h bar data to a tmp ArcticDB store."""
    import arcticdb as adb

    store = adb.Arctic(store_uri)
    if not store.has_library("forex_bars"):
        store.create_library("forex_bars")
    if not store.has_library("portfolio"):
        store.create_library("portfolio")

    lib = store.get_library("forex_bars")

    n = 200
    dates = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    rng = np.random.default_rng(42)
    close = 1.10 + np.cumsum(rng.normal(0, 0.0005, n))
    df = pd.DataFrame(
        {
            "open": close - 0.0001,
            "high": close + 0.001,
            "low": close - 0.001,
            "close": close,
            "volume": rng.integers(100, 1000, n).astype(float),
        },
        index=dates,
    )

    lib.write("EURUSD_1h", df)
    lib.snapshot("test_snap_v1", metadata={"created_at": "2024-06-30T22:00:00Z"})


def _simple_strategy(df: pd.DataFrame) -> np.ndarray:
    """Simple momentum strategy: buy when close is above 5-bar shifted close."""
    close = df["close"].to_numpy()
    signal = np.zeros(len(close), dtype=np.int8)
    for i in range(5, len(close)):
        if close[i] > close[i - 5]:
            signal[i] = 1
    return signal


def test_reproducibility(tmp_path: pytest.TempPathFactory) -> None:
    """DATA-05: BacktestRunner on same snapshot returns identical results across 2 runs."""
    from src.backtest.engine import BacktestRunner

    store_uri = f"lmdb://{tmp_path}/arctic_data"
    _make_synthetic_store(store_uri)

    runner = BacktestRunner(store_uri=store_uri)
    result1 = runner.run(
        strategy_fn=_simple_strategy,
        symbol="EURUSD",
        start=pd.Timestamp("2024-01-01", tz="UTC"),
        end=pd.Timestamp("2024-06-30", tz="UTC"),
        snapshot="test_snap_v1",
        strategy_name="test_strategy",
        persist=False,
    )
    result2 = runner.run(
        strategy_fn=_simple_strategy,
        symbol="EURUSD",
        start=pd.Timestamp("2024-01-01", tz="UTC"),
        end=pd.Timestamp("2024-06-30", tz="UTC"),
        snapshot="test_snap_v1",
        strategy_name="test_strategy",
        persist=False,
    )

    assert result1.final_equity == pytest.approx(result2.final_equity)
    assert np.array_equal(result1.equity, result2.equity)
    assert np.array_equal(result1.position, result2.position)


def test_warmup_timing() -> None:
    """DATA-07: warmup_numba() completes in under 60 seconds on first run."""
    from src.backtest.warmup import warmup_numba

    start = time.monotonic()
    elapsed = warmup_numba()
    wall = time.monotonic() - start

    assert elapsed < 60, f"Warmup took {elapsed:.1f}s — must be under 60s"
    assert wall < 65, f"Wall clock time {wall:.1f}s too long"


def test_cached_run_timing() -> None:
    """DATA-07: After warmup, single_pass_backtest on 1M bars completes in under 5 seconds."""
    from src.backtest.accumulators import single_pass_backtest
    from src.backtest.warmup import warmup_numba

    # Ensure Numba is compiled
    warmup_numba()

    n = 1_000_000
    close = np.linspace(1.0, 1.1, n)
    signal = np.array([1 if i % 20 < 10 else 0 for i in range(n)], dtype=np.int8)
    atr = np.full(n, 0.001)
    spread_cost = np.full(n, 0.00005)

    start = time.monotonic()
    single_pass_backtest(
        close=close,
        signal=signal,
        risk_per_trade=0.01,
        atr=atr,
        spread_cost=spread_cost,
    )
    elapsed = time.monotonic() - start

    assert elapsed < 5.0, f"Cached run took {elapsed:.2f}s — must be under 5s"


def test_backtest_persists_to_portfolio_library(tmp_path: pytest.TempPathFactory) -> None:
    """DATA-06: BacktestRunner.run() writes results to ArcticDB portfolio library with strategy/date/snapshot tags."""
    import arcticdb as adb

    from src.backtest.engine import BacktestRunner

    store_uri = f"lmdb://{tmp_path}/arctic_data"
    _make_synthetic_store(store_uri)

    runner = BacktestRunner(store_uri=store_uri)
    runner.run(
        strategy_fn=_simple_strategy,
        symbol="EURUSD",
        start=pd.Timestamp("2024-01-01", tz="UTC"),
        end=pd.Timestamp("2024-06-30", tz="UTC"),
        snapshot="test_snap_v1",
        strategy_name="test_strategy",
        persist=True,
    )

    store = adb.Arctic(store_uri)
    lib = store.get_library("portfolio")
    symbols = lib.list_symbols()
    assert "bt_test_strategy_EURUSD" in symbols

    result = lib.read("bt_test_strategy_EURUSD")
    meta = result.metadata
    assert meta is not None
    assert "strategy" in meta
    assert "start" in meta
    assert "end" in meta
    assert meta["strategy"] == "test_strategy"
