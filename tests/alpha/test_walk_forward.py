"""Walk-forward validation tests — ALPH-08."""

from __future__ import annotations

import pytest


@pytest.mark.xfail(reason="Phase 3 not implemented", strict=False)
def test_walk_forward_produces_oos_windows(synthetic_bars: object) -> None:
    """ALPH-08: Walk-forward splitter produces 30+ OOS windows on 5 years of data."""
    raise AssertionError("Not yet implemented")
