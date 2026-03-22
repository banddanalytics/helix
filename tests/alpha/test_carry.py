"""Carry engine tests — ALPH-06."""

from __future__ import annotations

import pytest


@pytest.mark.xfail(reason="Phase 3 not implemented", strict=False)
def test_carry_ranking_and_spread_filter() -> None:
    """ALPH-06: Cross-sectional carry ranking assigns +1/-1/0, filters spread cost."""
    raise AssertionError("Not yet implemented")
