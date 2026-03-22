"""Tests for RegimeOrchestrator.persist_signals() and persist_regime_state() — Plan 03-10."""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pandas as pd
import pytest

from src.alpha.signal_types import RegimeState, SignalRow


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_signal(
    engine: str,
    symbol: str = "EURUSD",
    direction: int = 1,
    strength: float = 0.70,
    ml_prob: float | None = 0.61,
    z_score: float | None = None,
    carry_rank: float | None = None,
) -> SignalRow:
    return SignalRow(
        symbol=symbol,
        engine=engine,
        direction=direction,
        strength=strength,
        regime=int(RegimeState.TRENDING),
        z_score=z_score,
        ml_prob=ml_prob,
        carry_rank=carry_rank,
    )


def _make_orchestrator(regime: RegimeState = RegimeState.TRENDING) -> "RegimeOrchestrator":
    """Create a RegimeOrchestrator with mocked filter/calibration/engines."""
    from src.alpha.orchestrator import RegimeOrchestrator

    mock_filter = MagicMock()
    mock_filter.update.return_value = (regime, 0.85)

    mock_calibration = MagicMock()
    mock_calibration.has_pending = False

    orchestrator = RegimeOrchestrator(
        regime_filter=mock_filter,
        calibration_service=mock_calibration,
        engines={},
        initial_regime=regime,
    )
    # Manually set confidence for persist_regime_state to have something to write
    orchestrator._regime_confidence = 0.85
    return orchestrator


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persist_signals_writes_to_arctic() -> None:
    """persist_signals() must call append/write with arctic_symbol='ml_engine_EURUSD'."""
    orch = _make_orchestrator()

    signals = [
        _make_signal("ml_engine", "EURUSD"),
        _make_signal("ml_engine", "EURUSD"),
    ]

    mock_lib = MagicMock()

    with patch("src.data.arctic_store.get_library", return_value=mock_lib):
        await orch.persist_signals(signals, "EURUSD")

    # _write_or_append is called; it tries append first; mock doesn't raise so append wins
    mock_lib.append.assert_called_once()
    call_args = mock_lib.append.call_args
    arctic_symbol = call_args[0][0]
    df_written: pd.DataFrame = call_args[0][1]

    assert arctic_symbol == "ml_engine_EURUSD", (
        f"Expected arctic_symbol 'ml_engine_EURUSD', got '{arctic_symbol}'"
    )

    expected_cols = {"symbol", "engine", "direction", "strength", "regime", "z_score", "ml_prob", "carry_rank"}
    assert expected_cols.issubset(set(df_written.columns)), (
        f"DataFrame missing expected columns. Got: {list(df_written.columns)}"
    )
    assert len(df_written) == 2, f"Expected 2 rows, got {len(df_written)}"


@pytest.mark.asyncio
async def test_persist_signals_groups_by_engine() -> None:
    """persist_signals() must make a separate write per engine."""
    orch = _make_orchestrator()

    signals = [
        _make_signal("ml_engine", "EURUSD"),
        _make_signal("carry_engine", "EURUSD", ml_prob=None, carry_rank=0.85),
    ]

    mock_lib = MagicMock()

    with patch("src.data.arctic_store.get_library", return_value=mock_lib):
        await orch.persist_signals(signals, "EURUSD")

    # Two engines → two append calls
    assert mock_lib.append.call_count == 2, (
        f"Expected 2 append calls (one per engine), got {mock_lib.append.call_count}"
    )

    called_symbols = {c[0][0] for c in mock_lib.append.call_args_list}
    assert called_symbols == {"ml_engine_EURUSD", "carry_engine_EURUSD"}, (
        f"Expected arctic symbols 'ml_engine_EURUSD' and 'carry_engine_EURUSD', got {called_symbols}"
    )


@pytest.mark.asyncio
async def test_persist_signals_empty_list_noop() -> None:
    """persist_signals() with empty list must not call the library at all."""
    orch = _make_orchestrator()

    mock_lib = MagicMock()

    with patch("src.data.arctic_store.get_library", return_value=mock_lib):
        await orch.persist_signals([], "EURUSD")

    mock_lib.append.assert_not_called()
    mock_lib.write.assert_not_called()


@pytest.mark.asyncio
async def test_persist_regime_state_writes_regime() -> None:
    """persist_regime_state() must write arctic_symbol='regime_EURUSD' with required columns."""
    orch = _make_orchestrator(RegimeState.TRENDING)

    mock_lib = MagicMock()
    ts = pd.Timestamp.utcnow()

    with patch("src.data.arctic_store.get_library", return_value=mock_lib):
        await orch.persist_regime_state("EURUSD", ts)

    mock_lib.append.assert_called_once()
    call_args = mock_lib.append.call_args
    arctic_symbol = call_args[0][0]
    df_written: pd.DataFrame = call_args[0][1]

    assert arctic_symbol == "regime_EURUSD", (
        f"Expected arctic_symbol 'regime_EURUSD', got '{arctic_symbol}'"
    )

    expected_cols = {"regime", "regime_name", "confidence"}
    assert expected_cols.issubset(set(df_written.columns)), (
        f"DataFrame missing expected columns. Got: {list(df_written.columns)}"
    )
    assert len(df_written) == 1, f"Expected 1 row for regime state, got {len(df_written)}"


def test_write_or_append_falls_back_to_write() -> None:
    """_write_or_append must call lib.write() when lib.append() raises an Exception."""
    from src.alpha.orchestrator import RegimeOrchestrator

    mock_lib = MagicMock()
    mock_lib.append.side_effect = Exception("ArcticDB: symbol not found")

    df = pd.DataFrame(
        [{"regime": 0, "regime_name": "TRENDING", "confidence": 0.85}],
        index=pd.DatetimeIndex([pd.Timestamp.utcnow()], name="timestamp"),
    )

    RegimeOrchestrator._write_or_append(mock_lib, "test_sym", df)

    mock_lib.write.assert_called_once_with("test_sym", df)
