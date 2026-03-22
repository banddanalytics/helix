"""Tests for PiT data manager and snapshot isolation (DATA-04, DATA-05)."""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import pytest

import arcticdb as adb


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_store(tmp_path):
    """Return an ArcticDB store backed by a tmp LMDB path."""
    uri = f"lmdb://{tmp_path}/arctic_test"
    store = adb.Arctic(uri)
    return store, uri


def _write_bars(lib, symbol: str, n: int, start: str = "2024-01-01") -> pd.DataFrame:
    """Write `n` daily OHLCV rows to lib[symbol] and return the DataFrame."""
    idx = pd.date_range(start, periods=n, freq="D", tz="UTC")
    df = pd.DataFrame(
        {
            "close": [1.10 + i * 0.001 for i in range(n)],
            "volume": [1000.0 + i for i in range(n)],
        },
        index=idx,
    )
    lib.write(symbol, df)
    return df


# ---------------------------------------------------------------------------
# Task 1: pit_read tests (DATA-04)
# ---------------------------------------------------------------------------

def test_pit_read_cutoff(tmp_path) -> None:
    """DATA-04: pit_read returns no data beyond as_of_timestamp."""
    from src.data.pit_manager import pit_read

    store, uri = _make_store(tmp_path)
    store.create_library("forex_bars")
    lib = store.get_library("forex_bars")
    _write_bars(lib, "EURUSD", 5)  # 2024-01-01 .. 2024-01-05

    as_of = pd.Timestamp("2024-01-03", tz="UTC")
    df = pit_read("forex_bars", "EURUSD", as_of, store_uri=f"lmdb://{tmp_path}/arctic_test")

    assert len(df) == 3, f"Expected 3 rows, got {len(df)}"
    assert df.index.max() <= as_of, "Last row exceeds as_of cutoff"


def test_pit_read_inclusive(tmp_path) -> None:
    """DATA-04: pit_read includes the row at exactly as_of_timestamp."""
    from src.data.pit_manager import pit_read

    store, uri = _make_store(tmp_path)
    store.create_library("forex_bars")
    lib = store.get_library("forex_bars")
    _write_bars(lib, "EURUSD", 5)

    as_of = pd.Timestamp("2024-01-03", tz="UTC")
    df = pit_read("forex_bars", "EURUSD", as_of, store_uri=f"lmdb://{tmp_path}/arctic_test")

    assert as_of in df.index, "Row at as_of_timestamp must be included"


def test_contemp_ic_violation() -> None:
    """DATA-04: validate_pit_compliance raises LookAheadBiasError when abs(contemp_ic) > abs(forward_ic) * 1.5."""
    from src.data.pit_manager import LookAheadBiasError, validate_pit_compliance

    n = 100
    idx = pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC")

    # Build returns series with a clear trend
    returns = pd.Series([0.001 * (i % 5 - 2) for i in range(n)], index=idx)

    # Signal = contemporaneous returns (perfect look-ahead bias)
    signal_df = pd.DataFrame({"signal": returns}, index=idx)
    price_df = pd.DataFrame({"returns": returns}, index=idx)

    with pytest.raises(LookAheadBiasError):
        validate_pit_compliance(signal_df, price_df)


def test_contemp_ic_compliant() -> None:
    """DATA-04: validate_pit_compliance passes for a legitimately shifted signal."""
    from src.data.pit_manager import validate_pit_compliance

    import numpy as np

    rng = np.random.default_rng(42)
    n = 200
    idx = pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC")

    # Returns: random walk increments
    returns = pd.Series(rng.normal(0, 0.001, n), index=idx)

    # Signal: lagged returns (forward-looking relative to price, not look-ahead)
    # Use returns.shift(1) as signal so contemp_ic is near zero
    signal = returns.shift(1).fillna(0)
    signal_df = pd.DataFrame({"signal": signal}, index=idx)
    price_df = pd.DataFrame({"returns": returns}, index=idx)

    # Should NOT raise (low contemp_ic, some forward_ic)
    result = validate_pit_compliance(signal_df, price_df)
    assert result is True


def test_shift_features_applies_shift() -> None:
    """DATA-04: shift_features shifts specified columns by 1 period, NaN in first row."""
    from src.data.pit_manager import shift_features

    idx = pd.date_range("2024-01-01", periods=5, freq="D", tz="UTC")
    df = pd.DataFrame(
        {"close": [1.1, 1.2, 1.3, 1.4, 1.5], "volume": [100.0, 200.0, 300.0, 400.0, 500.0]},
        index=idx,
    )

    shifted = shift_features(df, ["close", "volume"])

    assert pd.isna(shifted["close"].iloc[0]), "First row 'close' must be NaN after shift"
    assert pd.isna(shifted["volume"].iloc[0]), "First row 'volume' must be NaN after shift"
    assert shifted["close"].iloc[1] == pytest.approx(1.1), "Row 1 should equal original row 0"
    assert shifted["volume"].iloc[1] == pytest.approx(100.0), "Row 1 should equal original row 0"
    # Original df unchanged
    assert df["close"].iloc[0] == pytest.approx(1.1), "Original DataFrame must not be mutated"


# ---------------------------------------------------------------------------
# Task 1: Snapshot isolation tests (DATA-05)
# ---------------------------------------------------------------------------

def test_snapshot_isolation(tmp_path) -> None:
    """DATA-05: Snapshot at T, write after T, pit_read(snapshot=snap) returns pre-T data only."""
    from src.data.pit_manager import create_snapshot, pit_read

    store, uri = _make_store(tmp_path)
    store.create_library("forex_bars")
    lib = store.get_library("forex_bars")

    # Write 3 rows
    _write_bars(lib, "EURUSD", 3)

    # Create snapshot
    snap_name = "eod_test"
    create_snapshot("forex_bars", snap_name, store_uri=uri)

    # Write 2 more rows (should not be visible in snapshot read)
    extra_idx = pd.date_range("2024-01-04", periods=2, freq="D", tz="UTC")
    extra_df = pd.DataFrame(
        {"close": [1.103, 1.104], "volume": [1003.0, 1004.0]},
        index=extra_idx,
    )
    lib.append("EURUSD", extra_df)

    # Read at snapshot — should see only 3 rows
    # Use a far-future as_of so date_range doesn't filter
    far_future = pd.Timestamp("2099-12-31", tz="UTC")
    snap_df = pit_read(
        "forex_bars", "EURUSD", far_future, snapshot=snap_name, store_uri=uri
    )
    assert len(snap_df) == 3, f"Expected 3 rows at snapshot, got {len(snap_df)}"

    # Read without snapshot — should see 5 rows
    full_df = pit_read("forex_bars", "EURUSD", far_future, store_uri=uri)
    assert len(full_df) == 5, f"Expected 5 rows without snapshot, got {len(full_df)}"


def test_eod_snapshot_naming(tmp_path) -> None:
    """DATA-05: Snapshot named eod_YYYYMMDD with metadata containing created_at."""
    from src.data.pit_manager import create_snapshot

    store, uri = _make_store(tmp_path)
    store.create_library("forex_bars")
    lib = store.get_library("forex_bars")
    _write_bars(lib, "EURUSD", 2)

    snap_name = "eod_20240101"
    create_snapshot("forex_bars", snap_name, store_uri=uri)

    snapshots = lib.list_snapshots(load_metadata=True)
    assert snap_name in snapshots, f"Snapshot '{snap_name}' not found in list_snapshots()"
    metadata = snapshots[snap_name]
    assert "created_at" in metadata, f"Snapshot metadata missing 'created_at': {metadata}"


# ---------------------------------------------------------------------------
# Task 2: Snapshot scheduler backfill test (DATA-05)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_startup_backfill_missed_snapshots(tmp_path) -> None:
    """DATA-05: On startup, scheduler creates snapshots for missed days since last eod_YYYYMMDD."""
    from src.data.snapshot_scheduler import SnapshotScheduler

    store, uri = _make_store(tmp_path)
    store.create_library("forex_bars")
    lib = store.get_library("forex_bars")
    _write_bars(lib, "EURUSD", 5)

    # Create a snapshot for 3 days ago
    three_days_ago = (datetime.now(tz=timezone.utc).date() - timedelta(days=3))
    snap_name = f"eod_{three_days_ago.strftime('%Y%m%d')}"
    from src.data.pit_manager import create_snapshot
    create_snapshot("forex_bars", snap_name, store_uri=uri)

    # Run backfill — should create snapshots for 2 missed days (day-2 and day-1)
    scheduler = SnapshotScheduler(store_uri=uri, libraries=["forex_bars"])
    count = await scheduler.backfill_missed()

    assert count >= 2, f"Expected at least 2 backfill snapshots, got {count}"

    # Verify expected snapshot names exist
    snapshots = lib.list_snapshots()
    yesterday = datetime.now(tz=timezone.utc).date() - timedelta(days=1)
    two_days_ago = datetime.now(tz=timezone.utc).date() - timedelta(days=2)

    assert f"eod_{yesterday.strftime('%Y%m%d')}" in snapshots
    assert f"eod_{two_days_ago.strftime('%Y%m%d')}" in snapshots
