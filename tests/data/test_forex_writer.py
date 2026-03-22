"""Tests for Forex tick writer with batch flush and quality flagging (DATA-02)."""
from __future__ import annotations

import time

import numpy as np
import pandas as pd
import pytest

from src.data.arctic_store import initialize_store, reset_store
from src.data.forex_writer import FLUSH_SECONDS, FLUSH_TICKS, TickWriter
from src.execution.abstract import Tick


def make_tick(
    symbol: str = "EURUSD",
    bid: float = 1.1000,
    ask: float = 1.1001,
    *,
    ts: str = "2024-01-03T10:00:00",  # Wednesday — not weekend
    source: str = "mt5",
) -> Tick:
    """Helper: create a Tick dataclass with sane defaults."""
    return Tick(
        timestamp=np.datetime64(ts, "ns"),
        symbol=symbol,
        bid=bid,
        ask=ask,
        bid_volume=0.0,
        ask_volume=0.0,
        source=source,
    )


@pytest.fixture()
def arctic_uri(tmp_path: "pytest.TempPathFactory") -> str:  # type: ignore[type-arg]
    """Provide an isolated LMDB URI for each test."""
    reset_store()
    uri = f"lmdb://{tmp_path}/arctic_test"
    initialize_store(uri)
    yield uri
    reset_store()


# ---------------------------------------------------------------------------
# Task 1: batch flush at 10K ticks
# ---------------------------------------------------------------------------


def test_batch_flush_at_10k_ticks(arctic_uri: str) -> None:
    """DATA-02: Writer flushes buffer when 10,000 ticks accumulated for one symbol."""
    writer = TickWriter(store_uri=arctic_uri)
    # Write 10K ticks without starting the background flush thread
    for i in range(FLUSH_TICKS):
        writer.write(make_tick(bid=1.1000 + i * 0.00001))

    # Buffer flush should have triggered during the writes
    assert writer.flush_count >= 1

    # Verify ticks are stored in ArcticDB
    import arcticdb as adb

    store = adb.Arctic(arctic_uri)
    lib = store.get_library("forex_ticks")
    df = lib.read("EURUSD").data
    assert len(df) == FLUSH_TICKS


# ---------------------------------------------------------------------------
# Task 2: timer flush at 1 second
# ---------------------------------------------------------------------------


def test_timer_flush_at_1s(arctic_uri: str) -> None:
    """DATA-02: Writer flushes buffer after 1 second even if < 10K ticks."""
    writer = TickWriter(store_uri=arctic_uri)
    writer.start()
    try:
        for i in range(100):
            writer.write(make_tick(bid=1.1000 + i * 0.00001, ts=f"2024-01-03T10:00:{i:02d}"))

        # Wait for timer flush (FLUSH_SECONDS + buffer)
        time.sleep(FLUSH_SECONDS + 0.5)
        assert writer.flush_count >= 1
    finally:
        writer.stop()


# ---------------------------------------------------------------------------
# Task 3: quality flags — dtype and values
# ---------------------------------------------------------------------------


def test_quality_flags(arctic_uri: str) -> None:
    """DATA-02: quality column is int8 with values 0=clean, 1=rollover_spike, 2=weekend_gap, 3=duplicate."""
    writer = TickWriter(store_uri=arctic_uri)

    # Clean tick (Wednesday)
    writer.write(make_tick(ts="2024-01-03T10:00:00"))
    # Weekend tick (Saturday 2024-01-06)
    writer.write(make_tick(ts="2024-01-06T12:00:00"))

    writer._flush_all()  # Force flush without timer

    import arcticdb as adb

    store = adb.Arctic(arctic_uri)
    lib = store.get_library("forex_ticks")
    df = lib.read("EURUSD").data

    assert df["quality"].dtype == np.int8
    assert 0 in df["quality"].values  # clean
    assert 2 in df["quality"].values  # weekend_gap


# ---------------------------------------------------------------------------
# Task 4: duplicate detection
# ---------------------------------------------------------------------------


def test_duplicate_detection(arctic_uri: str) -> None:
    """DATA-02: Ticks with same timestamp + bid + ask are flagged quality=3."""
    writer = TickWriter(store_uri=arctic_uri)
    ts = "2024-01-03T10:00:00"

    writer.write(make_tick(bid=1.1000, ask=1.1001, ts=ts))
    writer.write(make_tick(bid=1.1000, ask=1.1001, ts=ts))  # duplicate
    writer.write(make_tick(bid=1.1000, ask=1.1001, ts=ts))  # duplicate

    writer._flush_all()

    import arcticdb as adb

    store = adb.Arctic(arctic_uri)
    lib = store.get_library("forex_ticks")
    df = lib.read("EURUSD").data

    assert len(df) == 3
    quality_vals = df["quality"].values
    # First occurrence stays clean (0), duplicates flagged as 3
    assert quality_vals[0] == 0
    assert quality_vals[1] == 3
    assert quality_vals[2] == 3


# ---------------------------------------------------------------------------
# Task 5: rollover spike detection
# ---------------------------------------------------------------------------


def test_rollover_spike_detection(arctic_uri: str) -> None:
    """DATA-02: Spread > 5x median at 00:00 UTC flagged quality=1."""
    writer = TickWriter(store_uri=arctic_uri)

    # Normal ticks with spread ~0.0001 (10 pips EURUSD-like)
    for i in range(10):
        writer.write(make_tick(bid=1.1000, ask=1.1001, ts=f"2024-01-03T10:{i:02d}:00"))

    # Rollover spike at 00:00 UTC: spread = 0.0100 (100x median)
    writer.write(
        Tick(
            timestamp=np.datetime64("2024-01-03T00:00:00", "ns"),
            symbol="EURUSD",
            bid=1.1000,
            ask=1.1100,  # spread = 0.0100 — far above 5x median
            bid_volume=0.0,
            ask_volume=0.0,
            source="mt5",
        )
    )

    writer._flush_all()

    import arcticdb as adb

    store = adb.Arctic(arctic_uri)
    lib = store.get_library("forex_ticks")
    df = lib.read("EURUSD").data

    # The tick at 00:00 UTC with massive spread should be quality=1
    midnight_rows = df[df.index.hour == 0]
    assert len(midnight_rows) == 1
    assert int(midnight_rows["quality"].iloc[0]) == 1


# ---------------------------------------------------------------------------
# Task 6: weekend gap detection
# ---------------------------------------------------------------------------


def test_weekend_gap_detection(arctic_uri: str) -> None:
    """DATA-02: Ticks on Saturday/Sunday flagged quality=2."""
    writer = TickWriter(store_uri=arctic_uri)

    # Saturday 2024-01-06
    writer.write(make_tick(ts="2024-01-06T12:00:00"))
    # Sunday 2024-01-07
    writer.write(make_tick(bid=1.1002, ts="2024-01-07T12:00:00"))

    writer._flush_all()

    import arcticdb as adb

    store = adb.Arctic(arctic_uri)
    lib = store.get_library("forex_ticks")
    df = lib.read("EURUSD").data

    assert len(df) == 2
    assert all(df["quality"].values == 2)


# ---------------------------------------------------------------------------
# Task 7: buffer sorted by timestamp before append
# ---------------------------------------------------------------------------


def test_append_sorts_by_timestamp(arctic_uri: str) -> None:
    """DATA-02: Buffer is sorted by timestamp before ArcticDB append (monotonic index requirement)."""
    writer = TickWriter(store_uri=arctic_uri)

    # Write ticks in REVERSE chronological order
    for i in range(5, 0, -1):
        writer.write(make_tick(bid=1.1000 + i * 0.00001, ts=f"2024-01-03T10:00:{i:02d}"))

    writer._flush_all()

    import arcticdb as adb

    store = adb.Arctic(arctic_uri)
    lib = store.get_library("forex_ticks")
    df = lib.read("EURUSD").data

    # Index must be monotonically increasing
    assert df.index.is_monotonic_increasing


# ---------------------------------------------------------------------------
# Task 8: write() does not block the caller
# ---------------------------------------------------------------------------


def test_writer_does_not_block_caller(arctic_uri: str) -> None:
    """DATA-02: write() returns immediately; flush happens on background thread."""
    writer = TickWriter(store_uri=arctic_uri)
    # Do not start background thread — just test that write() itself is fast

    n = 1000
    start = time.perf_counter()
    for i in range(n):
        writer.write(make_tick(bid=1.1000 + i * 0.000001))
    elapsed = time.perf_counter() - start

    avg_ms = (elapsed / n) * 1000
    assert avg_ms < 1.0, f"write() averaged {avg_ms:.3f}ms — expected < 1ms"
