"""Walk-forward validation tests — ALPH-08."""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="Stub — implementation in plan 03-06")
def test_walk_forward_produces_30_windows(synthetic_bars: object) -> None:
    """ALPH-08: Walk-forward splitter produces >= 30 OOS windows on 5 years of data.

    Given 5 years of 4-hour bars (~10,950 bars), the walk-forward splitter
    with 4-week train / 1-week test windows must yield at least 30 folds.
    """
    raise AssertionError("Not yet implemented")


@pytest.mark.skip(reason="Stub — implementation in plan 03-06")
def test_no_data_leakage_purge(synthetic_bars: object) -> None:
    """ALPH-08: Purge gap ensures no test bar appears in the training set.

    The walk-forward splitter applies a purge gap (embargo) so that
    overlapping feature windows cannot leak test data into training data.
    """
    raise AssertionError("Not yet implemented")


@pytest.mark.skip(reason="Stub — implementation in plan 03-06")
def test_cost_adjusted_sharpe(synthetic_bars: object) -> None:
    """ALPH-08: Net Sharpe (after spread/commission costs) is less than gross Sharpe.

    After applying spread costs per bar, the net Sharpe ratio must be
    strictly lower than the gross Sharpe ratio for any strategy with
    non-zero turnover.
    """
    raise AssertionError("Not yet implemented")
