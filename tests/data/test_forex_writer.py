"""Tests for Forex tick writer with batch flush and quality flagging (DATA-02)."""
import pytest


def test_batch_flush_at_10k_ticks() -> None:
    """DATA-02: Writer flushes buffer when 10,000 ticks accumulated for one symbol."""
    pytest.skip("Not implemented — Wave 2")


def test_timer_flush_at_1s() -> None:
    """DATA-02: Writer flushes buffer after 1 second even if < 10K ticks."""
    pytest.skip("Not implemented — Wave 2")


def test_quality_flags() -> None:
    """DATA-02: quality column is int8 with values 0=clean, 1=rollover_spike, 2=weekend_gap, 3=duplicate."""
    pytest.skip("Not implemented — Wave 2")


def test_duplicate_detection() -> None:
    """DATA-02: Ticks with same timestamp + bid + ask are flagged quality=3."""
    pytest.skip("Not implemented — Wave 2")


def test_rollover_spike_detection() -> None:
    """DATA-02: Spread > 5x median at 00:00 UTC flagged quality=1."""
    pytest.skip("Not implemented — Wave 2")


def test_weekend_gap_detection() -> None:
    """DATA-02: Ticks on Saturday/Sunday flagged quality=2."""
    pytest.skip("Not implemented — Wave 2")


def test_append_sorts_by_timestamp() -> None:
    """DATA-02: Buffer is sorted by timestamp before ArcticDB append (monotonic index requirement)."""
    pytest.skip("Not implemented — Wave 2")


def test_writer_does_not_block_caller() -> None:
    """DATA-02: write() returns immediately; flush happens on background thread."""
    pytest.skip("Not implemented — Wave 2")
