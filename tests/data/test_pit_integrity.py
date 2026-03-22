"""Tests for PiT data manager and snapshot isolation (DATA-04, DATA-05)."""
import pytest


def test_pit_read_cutoff() -> None:
    """DATA-04: pit_read returns no data beyond as_of_timestamp."""
    pytest.skip("Not implemented — Wave 2")


def test_pit_read_inclusive() -> None:
    """DATA-04: pit_read includes the row at exactly as_of_timestamp."""
    pytest.skip("Not implemented — Wave 2")


def test_contemp_ic_violation() -> None:
    """DATA-04: validate_pit_compliance raises LookAheadBiasError when abs(contemp_ic) > abs(forward_ic) * 1.5."""
    pytest.skip("Not implemented — Wave 2")


def test_shift_features_applies_shift() -> None:
    """DATA-04: shift_features shifts specified columns by 1 period, NaN in first row."""
    pytest.skip("Not implemented — Wave 2")


def test_snapshot_isolation() -> None:
    """DATA-05: Snapshot at T, write after T, pit_read(as_of=snapshot) returns pre-T data only."""
    pytest.skip("Not implemented — Wave 3")


def test_eod_snapshot_naming() -> None:
    """DATA-05: Snapshot named eod_YYYYMMDD with metadata containing created_at."""
    pytest.skip("Not implemented — Wave 3")


def test_startup_backfill_missed_snapshots() -> None:
    """DATA-05: On startup, scheduler creates snapshots for missed days since last eod_YYYYMMDD."""
    pytest.skip("Not implemented — Wave 3")
