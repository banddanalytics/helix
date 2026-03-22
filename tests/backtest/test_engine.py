"""Tests for BacktestRunner and Numba warmup (DATA-05 reproducibility, DATA-07)."""
import pytest


def test_reproducibility() -> None:
    """DATA-05: BacktestRunner on same snapshot returns identical results across 2 runs."""
    pytest.skip("Not implemented — Wave 3")


def test_warmup_timing() -> None:
    """DATA-07: warmup_numba() completes in under 60 seconds on first run."""
    pytest.skip("Not implemented — Wave 3")


def test_cached_run_timing() -> None:
    """DATA-07: After warmup, single_pass_backtest on 1M bars completes in under 5 seconds."""
    pytest.skip("Not implemented — Wave 3")


def test_backtest_persists_to_portfolio_library() -> None:
    """DATA-06: BacktestRunner.run() writes results to ArcticDB portfolio library with strategy/date/snapshot tags."""
    pytest.skip("Not implemented — Wave 3")
