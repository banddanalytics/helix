"""RegimeOrchestrator tests — ALPH-09."""

from __future__ import annotations

import pytest


@pytest.mark.xfail(reason="Phase 3 not implemented", strict=False)
def test_regime_gates_strategy_activation() -> None:
    """ALPH-09: RegimeOrchestrator activates only engines matching regime map (D-05)."""
    raise AssertionError("Not yet implemented")
