"""Feature pipeline tests — ALPH-07."""

from __future__ import annotations

import pytest


@pytest.mark.xfail(reason="Phase 3 not implemented", strict=False)
def test_27_features_compile_and_pit_compliant(synthetic_bars: object) -> None:
    """ALPH-07: All 27 Numba-JIT features compile, return finite values, PiT valid."""
    raise AssertionError("Not yet implemented")
