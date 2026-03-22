"""Tests for bar aggregation from ticks with session tagging (DATA-03)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def _make_ticks(
    timestamps: list[str],
    bids: list[float],
    asks: list[float],
    spreads: list[float],
    tick_volumes: list[float],
) -> pd.DataFrame:
    """Helper to create a tick DataFrame with DatetimeIndex."""
    index = pd.DatetimeIndex(timestamps, tz="UTC")
    return pd.DataFrame(
        {
            "bid": bids,
            "ask": asks,
            "spread": spreads,
            "tick_volume": tick_volumes,
        },
        index=index,
    )


def test_1m_bar_ohlcv_from_known_ticks() -> None:
    """DATA-03: 1-minute bar OHLCV matches hand-computed values from tick sequence."""
    from src.data.bar_aggregator import aggregate_bars

    # Minute 1: 1.1000, 1.1005, 1.0995, 1.1003
    # Minute 2: 1.1010, 1.1020
    ticks = _make_ticks(
        timestamps=[
            "2024-01-02 10:00:00",
            "2024-01-02 10:00:15",
            "2024-01-02 10:00:30",
            "2024-01-02 10:00:45",
            "2024-01-02 10:01:00",
            "2024-01-02 10:01:30",
        ],
        bids=[1.0999, 1.1004, 1.0994, 1.1002, 1.1009, 1.1019],
        asks=[1.1001, 1.1006, 1.0996, 1.1004, 1.1011, 1.1021],
        spreads=[0.0002, 0.0002, 0.0002, 0.0002, 0.0002, 0.0002],
        tick_volumes=[1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
    )

    bars = aggregate_bars(ticks, "1min")

    # Mid prices minute 1: 1.1000, 1.1005, 1.0995, 1.1003
    # open=first mid, high=max mid, low=min mid, close=last mid
    bar0 = bars.iloc[0]
    assert bar0["open"] == pytest.approx(1.1000, abs=1e-5)
    assert bar0["high"] == pytest.approx(1.1005, abs=1e-5)
    assert bar0["low"] == pytest.approx(1.0995, abs=1e-5)
    assert bar0["close"] == pytest.approx(1.1003, abs=1e-5)
    assert bar0["tick_volume"] == 4.0


def test_all_six_timeframes_produced() -> None:
    """DATA-03: aggregate produces bars for 1m, 5m, 15m, 1h, 4h, 1d."""
    from src.data.bar_aggregator import BarAggregator

    # 25 hours of ticks, one per minute — ensures 1d, 4h, 1h, 15m, 5m, 1m bars
    n = 25 * 60
    start = pd.Timestamp("2024-01-02 00:00:00", tz="UTC")
    index = pd.date_range(start=start, periods=n, freq="1min", tz="UTC")
    ticks = pd.DataFrame(
        {
            "bid": np.random.uniform(1.09, 1.10, size=n),
            "ask": np.random.uniform(1.10, 1.11, size=n),
            "spread": np.full(n, 0.0001),
            "tick_volume": np.ones(n),
        },
        index=index,
    )
    ticks["ask"] = ticks["bid"] + ticks["spread"]

    import arcticdb as adb

    import tempfile, os

    with tempfile.TemporaryDirectory() as tmp:
        store_uri = f"lmdb://{tmp}/arctic_data"
        store = adb.Arctic(store_uri)
        store.create_library("forex_bars")

        agg = BarAggregator(store_uri=store_uri)
        result = agg.process_ticks("EURUSD", ticks)

        assert set(result.keys()) == {"1m", "5m", "15m", "1h", "4h", "1d"}
        for tf in ("1m", "5m", "15m", "1h", "4h", "1d"):
            assert result[tf] > 0

        lib = store.get_library("forex_bars")
        symbols = lib.list_symbols()
        for tf in ("1m", "5m", "15m", "1h", "4h", "1d"):
            assert f"EURUSD_{tf}" in symbols


def test_session_tags() -> None:
    """DATA-03: session column is int8 — 0=Asian(00-08), 1=London(08-13), 2=Overlap(13-16), 3=NY(16-21)."""
    from src.data.bar_aggregator import aggregate_bars

    # Ticks at representative hours: 3=Asian, 10=London, 14=Overlap, 18=NY, 22=Asian
    hour_expected = [
        (3, 0),   # Asian
        (10, 1),  # London
        (14, 2),  # Overlap
        (18, 3),  # New York
        (22, 0),  # Asian (21-23)
    ]
    timestamps = [f"2024-01-02 {h:02d}:30:00" for h, _ in hour_expected]
    n = len(timestamps)
    ticks = _make_ticks(
        timestamps=timestamps,
        bids=[1.1000] * n,
        asks=[1.1002] * n,
        spreads=[0.0002] * n,
        tick_volumes=[1.0] * n,
    )

    bars = aggregate_bars(ticks, "1h")

    for bar_time, (hour, expected_session) in zip(bars.index, hour_expected):
        actual = int(bars.loc[bar_time, "session"])
        assert actual == expected_session, (
            f"Hour {hour}: expected session {expected_session}, got {actual}"
        )

    # Check dtype is int8
    assert bars["session"].dtype == np.int8


def test_spread_avg_and_max_per_bar() -> None:
    """DATA-03: spread_avg and spread_max computed correctly per bar."""
    from src.data.bar_aggregator import aggregate_bars

    spreads = [0.0001, 0.0002, 0.0003]
    ticks = _make_ticks(
        timestamps=[
            "2024-01-02 10:00:00",
            "2024-01-02 10:00:20",
            "2024-01-02 10:00:40",
        ],
        bids=[1.1000, 1.1001, 1.1002],
        asks=[1.1001, 1.1003, 1.1005],
        spreads=spreads,
        tick_volumes=[1.0, 1.0, 1.0],
    )

    bars = aggregate_bars(ticks, "1min")

    assert len(bars) == 1
    assert bars.iloc[0]["spread_avg"] == pytest.approx(0.0002, abs=1e-7)
    assert bars.iloc[0]["spread_max"] == pytest.approx(0.0003, abs=1e-7)


def test_bar_symbol_naming() -> None:
    """DATA-03: Bars written to forex_bars with symbol format EURUSD_1m, EURUSD_5m, etc."""
    from src.data.bar_aggregator import BarAggregator

    import arcticdb as adb
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        store_uri = f"lmdb://{tmp}/arctic_data"
        store = adb.Arctic(store_uri)
        store.create_library("forex_bars")

        # 2 hours of ticks to produce meaningful bars
        n = 120
        start = pd.Timestamp("2024-01-02 10:00:00", tz="UTC")
        index = pd.date_range(start=start, periods=n, freq="1min", tz="UTC")
        ticks = pd.DataFrame(
            {
                "bid": np.full(n, 1.1000),
                "ask": np.full(n, 1.1001),
                "spread": np.full(n, 0.0001),
                "tick_volume": np.ones(n),
            },
            index=index,
        )

        agg = BarAggregator(store_uri=store_uri)
        agg.process_ticks("EURUSD", ticks)

        lib = store.get_library("forex_bars")
        symbols = lib.list_symbols()

        assert "EURUSD_1m" in symbols


def test_bar_columns_match_schema() -> None:
    """DATA-03: aggregate_bars output columns match FOREX_BAR_COLUMNS from schemas.py."""
    from src.data.bar_aggregator import aggregate_bars
    from src.data.schemas import FOREX_BAR_COLUMNS

    ticks = _make_ticks(
        timestamps=["2024-01-02 10:00:00", "2024-01-02 10:00:30"],
        bids=[1.1000, 1.1001],
        asks=[1.1002, 1.1003],
        spreads=[0.0002, 0.0002],
        tick_volumes=[1.0, 1.0],
    )
    bars = aggregate_bars(ticks, "1min")
    assert set(bars.columns) == set(FOREX_BAR_COLUMNS.keys())
