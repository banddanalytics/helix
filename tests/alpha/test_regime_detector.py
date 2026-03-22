"""Regime detector tests — ALPH-01, ALPH-02."""

from __future__ import annotations

import pytest


@pytest.mark.xfail(reason="Phase 3 not implemented", strict=False)
def test_hmm_identifies_three_states(synthetic_returns: object) -> None:
    """ALPH-01: HMMGARCHRegimeDetector.fit() identifies 3 distinct states."""
    raise AssertionError("Not yet implemented")


@pytest.mark.xfail(reason="Phase 3 not implemented", strict=False)
def test_states_sorted_by_ascending_variance(synthetic_returns: object) -> None:
    """ALPH-02: States ordered by ascending unconditional variance omega/(1-a-b)."""
    raise AssertionError("Not yet implemented")
