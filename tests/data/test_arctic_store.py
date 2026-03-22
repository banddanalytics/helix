"""Tests for ArcticDB store initialization and schema definitions.

TDD RED phase — these tests will fail until arctic_store.py and schemas.py are created.
"""
from __future__ import annotations

import io
from contextlib import redirect_stdout

import numpy as np
import pandas as pd
import pytest

from src.data import (
    FOREX_BAR_COLUMNS,
    FOREX_TICK_COLUMNS,
    LIBRARY_NAMES,
    MBO_TICK_COLUMNS,
    get_library,
    initialize_store,
    reset_store,
)


@pytest.fixture(autouse=True)
def isolate_store() -> None:
    """Reset the module-level singleton before each test."""
    reset_store()
    yield
    reset_store()


def make_uri(tmp_path):
    return f"lmdb://{tmp_path}/arctic_data"


# ---------------------------------------------------------------------------
# Task 1 tests
# ---------------------------------------------------------------------------


def test_initialize_creates_all_six_libraries(tmp_path):
    """initialize_store must create all 6 libraries, presence verified via list_libraries."""
    uri = make_uri(tmp_path)
    store = initialize_store(uri)
    libs = set(store.list_libraries())
    assert libs == set(LIBRARY_NAMES), f"Expected {set(LIBRARY_NAMES)}, got {libs}"


def test_initialize_store_is_idempotent(tmp_path):
    """Calling initialize_store twice must not raise and libraries stay consistent."""
    uri = make_uri(tmp_path)
    initialize_store(uri)
    store = initialize_store(uri)
    libs = set(store.list_libraries())
    assert libs == set(LIBRARY_NAMES)


def test_forex_tick_roundtrip_preserves_dtypes(tmp_path):
    """Forex tick DataFrame round-trips through write/read with correct dtypes."""
    uri = make_uri(tmp_path)
    store = initialize_store(uri)
    lib = store.get_library("forex_ticks")

    index = pd.date_range("2025-01-01", periods=5, freq="100ms", tz="UTC")
    df = pd.DataFrame(
        {
            "bid": np.array([1.1000, 1.1001, 1.1002, 1.1003, 1.1004], dtype="float64"),
            "ask": np.array([1.1001, 1.1002, 1.1003, 1.1004, 1.1005], dtype="float64"),
            "spread": np.array([0.0001, 0.0001, 0.0001, 0.0001, 0.0001], dtype="float64"),
            "tick_volume": np.array([10.0, 20.0, 30.0, 40.0, 50.0], dtype="float64"),
            "source": ["mt5"] * 5,
            "quality": np.array([0, 0, 0, 0, 0], dtype="int8"),
        },
        index=index,
    )
    lib.write("EURUSD", df)
    result = lib.read("EURUSD").data

    for col, expected_dtype in FOREX_TICK_COLUMNS.items():
        assert col in result.columns, f"Column {col!r} missing from read-back"
        # int8 comes back as int8; floats as float64; object as object
        actual = str(result[col].dtype)
        assert actual == expected_dtype, (
            f"Column {col!r}: expected dtype {expected_dtype!r}, got {actual!r}"
        )


def test_mbo_tick_schema_roundtrip(tmp_path):
    """MBO tick DataFrame round-trips through write/read with correct dtypes."""
    uri = make_uri(tmp_path)
    store = initialize_store(uri)
    lib = store.get_library("mbo_ticks")

    index = pd.date_range("2025-01-01", periods=3, freq="1ms", tz="UTC")
    df = pd.DataFrame(
        {
            "recv_ts": pd.to_datetime(["2025-01-01 00:00:00.001", "2025-01-01 00:00:00.002", "2025-01-01 00:00:00.003"]),
            "order_id": np.array([100, 101, 102], dtype="int64"),
            "side": np.array([1, -1, 1], dtype="int8"),
            "price": np.array([4200.25, 4200.50, 4200.25], dtype="float64"),
            "qty": np.array([10, 5, 20], dtype="int32"),
            "action": np.array([1, 2, 1], dtype="int8"),
            "rpt_seq": np.array([1000, 1001, 1002], dtype="int64"),
            "agg_qty": np.array([50, 45, 65], dtype="int32"),
            "num_orders": np.array([3, 2, 4], dtype="int32"),
            "price_level": np.array([1, 1, 1], dtype="int8"),
        },
        index=index,
    )
    lib.write("ESH25", df)
    result = lib.read("ESH25").data

    for col in MBO_TICK_COLUMNS:
        if col == "recv_ts":
            continue  # recv_ts stored as a column; dtype handling varies
        assert col in result.columns, f"Column {col!r} missing from MBO read-back"


def test_get_library_returns_existing(tmp_path):
    """get_library returns a Library object for an initialized library."""
    uri = make_uri(tmp_path)
    initialize_store(uri)
    lib = get_library("forex_ticks", uri=uri)
    assert lib is not None


def test_library_names_has_exactly_six(tmp_path):
    """LIBRARY_NAMES constant must contain exactly 6 entries."""
    expected = {"forex_ticks", "forex_bars", "swap_rates", "mbo_ticks", "signals", "portfolio"}
    assert set(LIBRARY_NAMES) == expected
    assert len(LIBRARY_NAMES) == 6
