"""RegimeOrchestrator — central coordinator for all four alpha engines.

Per D-04: The orchestrator owns all strategy activation. On each bar it reads
regime state and calls engine.generate_signals() only for active engines.
Per D-06: The orchestrator owns the 20-bar hysteresis dwell logic.
Per D-07: CrossAssetCache pre-loads 252 bars for all 6 symbols at startup.
Per D-12: Pending model swap is atomic at bar boundary.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

import pandas as pd

from src.alpha.signal_types import (
    CROSS_ASSET_SYMBOLS,
    REGIME_ACTIVATION,
    REGIME_SYMBOL_PATTERN,
    ENGINE_SYMBOL_PATTERN,
    RegimeState,
    SignalRow,
)

if TYPE_CHECKING:
    from src.alpha.regime.calibration import RecalibrationService
    from src.alpha.regime.online_filter import OnlineRegimeFilter

logger = logging.getLogger("helix.alpha")


class CrossAssetCache:
    """Pre-loaded rolling window of OHLCV bars for all 6 cross-asset symbols.

    Per D-07: Loads 252 bars at startup via pit_read(). Updates incrementally
    on each new bar: append new bar, drop oldest (O(1) per update).
    """

    def __init__(
        self,
        symbols: list[str] | None = None,
        lookback: int = 252,
    ) -> None:
        self._symbols: list[str] = symbols if symbols is not None else CROSS_ASSET_SYMBOLS
        self._lookback: int = lookback
        self._data: dict[str, pd.DataFrame] = {}

    def load(self, as_of: pd.Timestamp) -> None:
        """Pre-load the last `lookback` bars for all symbols.

        Per D-07: Uses pit_read() to avoid look-ahead bias.

        Parameters
        ----------
        as_of:
            PiT cutoff — only data on or before this timestamp is loaded.
        """
        from src.data.pit_manager import pit_read

        for symbol in self._symbols:
            try:
                df = pit_read("forex_bars", symbol, as_of)
                self._data[symbol] = df.iloc[-self._lookback :]
            except Exception:
                logger.warning(
                    "CrossAssetCache.load(): failed to load %s — empty DataFrame",
                    symbol,
                )
                self._data[symbol] = pd.DataFrame()

    def update(self, symbol: str, new_bar: pd.Series) -> None:
        """Append new bar and drop oldest to maintain fixed-size window.

        O(1) operation — slices to keep last `lookback` rows.

        Parameters
        ----------
        symbol:
            Symbol to update.
        new_bar:
            New OHLCV bar as a Series.
        """
        if symbol not in self._data or self._data[symbol].empty:
            self._data[symbol] = new_bar.to_frame().T
        else:
            self._data[symbol] = pd.concat(
                [self._data[symbol], new_bar.to_frame().T]
            ).iloc[-self._lookback :]

    def get_data(self) -> dict[str, pd.DataFrame]:
        """Return a copy of the full cross-asset data dict."""
        return dict(self._data)

    @property
    def is_loaded(self) -> bool:
        """True if all symbols have at least one bar of data."""
        return all(
            symbol in self._data and not self._data[symbol].empty
            for symbol in self._symbols
        )


class RegimeOrchestrator:
    """Central coordinator for strategy activation based on regime state.

    Per D-04: Owns all strategy activation logic.
    Per D-05: Activation map — TRENDING→[ml,carry], MEAN_REVERTING→[cointegration], CRISIS→[]
    Per D-06: Owns 20-bar hysteresis dwell logic.
    Per D-12: Applies pending model swap at bar boundary (before any computation).
    """

    def __init__(
        self,
        regime_filter: "OnlineRegimeFilter",
        calibration_service: "RecalibrationService",
        engines: dict[str, Any],
        cache: CrossAssetCache | None = None,
        initial_regime: RegimeState = RegimeState.TRENDING,
    ) -> None:
        self._regime_filter = regime_filter
        self._calibration = calibration_service
        self._engines = engines
        self._cache = cache

        # Regime state
        self._current_regime: RegimeState = initial_regime
        self._regime_confidence: float = 0.0

        # Hysteresis dwell logic (D-06)
        self._dwell_counter: int = 0
        self._hysteresis_bars: int = 20

        # Regime switch confidence thresholds (per spec)
        self._enter_thresholds: dict[RegimeState, float] = {
            RegimeState.TRENDING: 0.70,
            RegimeState.MEAN_REVERTING: 0.65,
            RegimeState.CRISIS: 0.60,
        }
        self._exit_threshold: float = 0.30

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def on_bar(
        self,
        symbol: str,
        bar_return: float,
        bar_data: dict | None = None,
    ) -> list[SignalRow]:
        """Process a new bar and return signals from active engines.

        Steps:
          0. Apply pending model swap (atomic, before computation)
          1. Update regime filter
          2. Apply hysteresis dwell logic
          3. Get active engines for current regime
          4. Call active engines to generate signals
          5. Return collected signals (empty list in CRISIS)

        Parameters
        ----------
        symbol:
            The incoming bar's symbol.
        bar_return:
            Log-return of the current bar.
        bar_data:
            Optional OHLCV dict passed to engines.

        Returns
        -------
        list[SignalRow]
            Signals from active engines, or empty list in CRISIS.
        """
        # Step 0: apply pending model at bar boundary (D-12)
        if self._calibration.has_pending:
            applied = self._calibration.apply_pending()
            if applied:
                self._regime_filter.reset()
                logger.info(
                    "RegimeOrchestrator: pending model applied and filter reset at bar start"
                )

        # Step 1: update regime filter
        new_regime, confidence = self._regime_filter.update(bar_return)

        # Step 2: hysteresis dwell logic (D-06)
        self._dwell_counter += 1
        if self._dwell_counter >= self._hysteresis_bars:
            # Candidate for regime change — check entry/exit thresholds
            if new_regime != self._current_regime:
                enter_ok = confidence >= self._enter_thresholds[new_regime]
                exit_ok = self._regime_confidence <= self._exit_threshold
                if enter_ok or exit_ok:
                    logger.info(
                        "RegimeOrchestrator: regime %s -> %s (confidence=%.3f, dwell=%d)",
                        self._current_regime.name,
                        new_regime.name,
                        confidence,
                        self._dwell_counter,
                    )
                    self._current_regime = new_regime
                    self._dwell_counter = 0

        self._regime_confidence = confidence

        # Step 3: get active engines for current regime (D-05)
        active_engine_names = REGIME_ACTIVATION[self._current_regime]

        # Step 4: CRISIS regime — return immediately with no signals (reduce-only)
        if not active_engine_names:
            logger.debug(
                "RegimeOrchestrator: CRISIS regime — no signals generated for %s", symbol
            )
            return []

        # Step 5: call active engines and collect signals
        signals: list[SignalRow] = []
        for engine_name in active_engine_names:
            engine = self._engines.get(engine_name)
            if engine is None:
                logger.warning(
                    "RegimeOrchestrator: engine '%s' not found in engines dict", engine_name
                )
                continue
            try:
                engine_signals = engine.generate_signals(symbol, bar_data)
                if engine_signals:
                    # Tag signals with current regime
                    for sig in engine_signals:
                        if hasattr(sig, "regime"):
                            sig.regime = self._current_regime.value
                    signals.extend(engine_signals)
            except Exception:
                logger.exception(
                    "RegimeOrchestrator: engine '%s' raised exception for symbol %s",
                    engine_name,
                    symbol,
                )

        return signals

    async def persist_signals(self, signals: list[SignalRow], symbol: str) -> None:
        """Persist signals to ArcticDB with {engine}_{symbol} pattern.

        Per D-02: Each engine writes to its own signals library symbol.
        Uses append-first, fall-back-to-write pattern (per Research Pitfall 6).

        Parameters
        ----------
        signals:
            Signals to persist.
        symbol:
            The bar symbol (used to construct ArcticDB key).
        """
        if not signals:
            return

        from src.data.arctic_store import get_library

        lib = get_library("signals")

        # Group signals by engine
        by_engine: dict[str, list[SignalRow]] = {}
        for sig in signals:
            by_engine.setdefault(sig.engine, []).append(sig)

        for engine_name, engine_signals in by_engine.items():
            arctic_symbol = ENGINE_SYMBOL_PATTERN.format(engine=engine_name, symbol=symbol)
            rows = [
                {
                    "symbol": s.symbol,
                    "engine": s.engine,
                    "direction": s.direction,
                    "strength": s.strength,
                    "regime": s.regime,
                    "z_score": s.z_score,
                    "ml_prob": s.ml_prob,
                    "carry_rank": s.carry_rank,
                }
                for s in engine_signals
            ]
            df = pd.DataFrame(rows)
            df.index = pd.DatetimeIndex(
                [pd.Timestamp.utcnow()] * len(df), name="timestamp"
            )

            await asyncio.to_thread(self._write_or_append, lib, arctic_symbol, df)

    async def persist_regime_state(self, symbol: str, timestamp: pd.Timestamp) -> None:
        """Persist current regime state to ArcticDB regime_{symbol}.

        Per D-03: Regime state is stored separately from trading signals.

        Parameters
        ----------
        symbol:
            The bar symbol.
        timestamp:
            Bar timestamp for the regime state record.
        """
        from src.data.arctic_store import get_library

        lib = get_library("signals")
        arctic_symbol = REGIME_SYMBOL_PATTERN.format(symbol=symbol)

        regime_df = pd.DataFrame(
            [
                {
                    "regime": int(self._current_regime),
                    "regime_name": self._current_regime.name,
                    "confidence": self._regime_confidence,
                }
            ],
            index=pd.DatetimeIndex([timestamp], name="timestamp"),
        )

        await asyncio.to_thread(self._write_or_append, lib, arctic_symbol, regime_df)

    @property
    def current_regime(self) -> RegimeState:
        """Current active regime state."""
        return self._current_regime

    @property
    def dwell_counter(self) -> int:
        """Number of bars elapsed since last regime change (or since init)."""
        return self._dwell_counter

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _write_or_append(
        lib: Any,
        arctic_symbol: str,
        df: pd.DataFrame,
    ) -> None:
        """Append to existing ArcticDB symbol or write new (per Research Pitfall 6)."""
        try:
            lib.append(arctic_symbol, df)
        except Exception:
            lib.write(arctic_symbol, df)


__all__ = ["CrossAssetCache", "RegimeOrchestrator"]
