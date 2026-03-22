"""RegimeOrchestrator tests — ALPH-09."""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pandas as pd
import pytest

from src.alpha.signal_types import RegimeState, SignalRow


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_signal(symbol: str, engine: str, regime: RegimeState) -> SignalRow:
    return SignalRow(
        symbol=symbol,
        engine=engine,
        direction=1,
        strength=0.70,
        regime=regime.value,
    )


def _make_orchestrator(regime: RegimeState, confidence: float = 0.85) -> tuple:
    """Create a RegimeOrchestrator with mocked dependencies.

    The orchestrator is initialized with `initial_regime=regime` so it starts
    in the target regime without needing the hysteresis period to settle.
    """
    from src.alpha.orchestrator import RegimeOrchestrator

    mock_filter = MagicMock()
    mock_filter.update.return_value = (regime, confidence)

    mock_calibration = MagicMock()
    mock_calibration.has_pending = False
    mock_calibration.apply_pending.return_value = False

    ml_engine = MagicMock()
    ml_engine.generate_signals.return_value = [
        _make_signal("EURUSD", "ml_engine", regime)
    ]

    carry_engine = MagicMock()
    carry_engine.generate_signals.return_value = [
        _make_signal("EURUSD", "carry_engine", regime)
    ]

    coint_engine = MagicMock()
    coint_engine.generate_signals.return_value = [
        _make_signal("EURUSD", "cointegration_engine", regime)
    ]

    engines = {
        "ml_engine": ml_engine,
        "carry_engine": carry_engine,
        "cointegration_engine": coint_engine,
    }

    orchestrator = RegimeOrchestrator(
        regime_filter=mock_filter,
        calibration_service=mock_calibration,
        engines=engines,
        initial_regime=regime,
    )
    return orchestrator, engines, mock_filter, mock_calibration


def _run_bars(orchestrator, n: int = 25, symbol: str = "EURUSD") -> list:
    """Run n bars and return last result."""
    result = []
    for _ in range(n):
        result = orchestrator.on_bar(symbol, 0.0001)
    return result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_trending_activates_ml_and_carry() -> None:
    """ALPH-09: TRENDING regime activates ml_engine and carry_engine only (D-05)."""
    orchestrator, engines, _, _ = _make_orchestrator(RegimeState.TRENDING, 0.85)

    # Run 21 bars to surpass the 20-bar hysteresis dwell
    _run_bars(orchestrator, n=21)

    assert engines["ml_engine"].generate_signals.called, "ml_engine should be called in TRENDING"
    assert engines["carry_engine"].generate_signals.called, "carry_engine should be called in TRENDING"
    assert not engines["cointegration_engine"].generate_signals.called, (
        "cointegration_engine must NOT be called in TRENDING"
    )


def test_mean_reverting_activates_cointegration() -> None:
    """ALPH-09: MEAN_REVERTING regime activates cointegration_engine only (D-05)."""
    orchestrator, engines, _, _ = _make_orchestrator(RegimeState.MEAN_REVERTING, 0.75)

    # Run 21 bars to surpass hysteresis
    _run_bars(orchestrator, n=21)

    assert engines["cointegration_engine"].generate_signals.called, (
        "cointegration_engine should be called in MEAN_REVERTING"
    )
    assert not engines["ml_engine"].generate_signals.called, (
        "ml_engine must NOT be called in MEAN_REVERTING"
    )
    assert not engines["carry_engine"].generate_signals.called, (
        "carry_engine must NOT be called in MEAN_REVERTING"
    )


def test_crisis_activates_nothing() -> None:
    """ALPH-09: CRISIS regime activates no engines — all signals blocked (D-05)."""
    orchestrator, engines, _, _ = _make_orchestrator(RegimeState.CRISIS, 0.70)

    # Run 25 bars to ensure hysteresis is well past
    signals = []
    for _ in range(25):
        signals = orchestrator.on_bar("EURUSD", 0.0001)

    # No engines should be called in CRISIS
    assert not engines["ml_engine"].generate_signals.called, "ml_engine must NOT be called in CRISIS"
    assert not engines["carry_engine"].generate_signals.called, "carry_engine must NOT be called in CRISIS"
    assert not engines["cointegration_engine"].generate_signals.called, (
        "cointegration_engine must NOT be called in CRISIS"
    )
    # Returned signals list must be empty
    assert signals == [], f"CRISIS must return empty signals, got {signals}"


def test_hysteresis_20_bars() -> None:
    """ALPH-09: Hysteresis dwell of 20 bars prevents rapid regime oscillation."""
    from src.alpha.orchestrator import RegimeOrchestrator

    mock_filter = MagicMock()
    mock_calibration = MagicMock()
    mock_calibration.has_pending = False

    ml_engine = MagicMock()
    ml_engine.generate_signals.return_value = [_make_signal("EURUSD", "ml_engine", RegimeState.TRENDING)]
    carry_engine = MagicMock()
    carry_engine.generate_signals.return_value = [_make_signal("EURUSD", "carry_engine", RegimeState.TRENDING)]
    coint_engine = MagicMock()
    coint_engine.generate_signals.return_value = []

    engines = {
        "ml_engine": ml_engine,
        "carry_engine": carry_engine,
        "cointegration_engine": coint_engine,
    }

    orchestrator = RegimeOrchestrator(
        regime_filter=mock_filter,
        calibration_service=mock_calibration,
        engines=engines,
    )

    # Phase 1: start in TRENDING — run 20 bars to settle (initial dwell)
    mock_filter.update.return_value = (RegimeState.TRENDING, 0.85)
    for _ in range(20):
        orchestrator.on_bar("EURUSD", 0.0001)

    # After 20 bars we are at the hysteresis boundary — state allowed to flip now
    # Confirm still TRENDING at bar 20 (dwell just reached 20)
    assert orchestrator.current_regime == RegimeState.TRENDING

    # Phase 2: mock filter NOW starts returning MEAN_REVERTING with high confidence
    mock_filter.update.return_value = (RegimeState.MEAN_REVERTING, 0.80)

    # Bar 21: regime may switch here (dwell_counter == 20 at start of bar, which is >= 20)
    orchestrator.on_bar("EURUSD", 0.0)
    # At this point regime should have switched to MEAN_REVERTING
    assert orchestrator.current_regime == RegimeState.MEAN_REVERTING, (
        "Regime should switch to MEAN_REVERTING after hysteresis is satisfied"
    )

    # Dwell counter should have reset to 0 on regime change
    assert orchestrator.dwell_counter == 0, "dwell_counter must reset to 0 on regime change"

    # Phase 3: immediately try to switch back to TRENDING — must be blocked by hysteresis
    mock_filter.update.return_value = (RegimeState.TRENDING, 0.85)
    for bar_num in range(1, 20):
        orchestrator.on_bar("EURUSD", 0.0001)
        assert orchestrator.current_regime == RegimeState.MEAN_REVERTING, (
            f"Regime should stay MEAN_REVERTING at bar {bar_num} (hysteresis not satisfied)"
        )


def test_pending_model_applied_at_bar_start() -> None:
    """ALPH-09: Pending model swap occurs at bar start, before engine calls."""
    from src.alpha.orchestrator import RegimeOrchestrator

    call_order: list[str] = []

    mock_filter = MagicMock()
    mock_filter.update.side_effect = lambda r: (
        call_order.append("update") or (RegimeState.TRENDING, 0.85)
    )

    mock_calibration = MagicMock()
    mock_calibration.has_pending = True
    mock_calibration.apply_pending.side_effect = lambda: (
        call_order.append("apply_pending") or True
    )

    ml_engine = MagicMock()
    ml_engine.generate_signals.side_effect = lambda *a, **kw: (
        call_order.append("generate_signals") or [_make_signal("EURUSD", "ml_engine", RegimeState.TRENDING)]
    )
    carry_engine = MagicMock()
    carry_engine.generate_signals.side_effect = lambda *a, **kw: (
        call_order.append("generate_signals_carry") or []
    )

    engines = {
        "ml_engine": ml_engine,
        "carry_engine": carry_engine,
        "cointegration_engine": MagicMock(),
    }
    engines["cointegration_engine"].generate_signals.return_value = []

    orchestrator = RegimeOrchestrator(
        regime_filter=mock_filter,
        calibration_service=mock_calibration,
        engines=engines,
    )

    # Run 21 bars (needs to be past hysteresis to call engines)
    # Set has_pending True only on first bar
    for i in range(21):
        if i > 0:
            mock_calibration.has_pending = False
        orchestrator.on_bar("EURUSD", 0.0001)

    # apply_pending must have been called
    assert mock_calibration.apply_pending.called, "apply_pending() must be called when has_pending is True"

    # apply_pending must appear before any generate_signals call
    apply_idx = call_order.index("apply_pending")
    gen_idx = call_order.index("generate_signals")
    assert apply_idx < gen_idx, (
        f"apply_pending (idx={apply_idx}) must occur before generate_signals (idx={gen_idx})"
    )
