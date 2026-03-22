"""BacktestRunner — pit_read → shift(1) → Numba accumulator → VBT Portfolio.

Per D-14: Full BacktestRunner delivered in Phase 2.
Per D-15: Persists results to ArcticDB portfolio library.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from src.backtest.accumulators import single_pass_backtest
from src.backtest.numba_kernels import rolling_atr
from src.data.pit_manager import pit_read, shift_features

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger("helix.backtest")


@dataclass(frozen=True)
class BacktestResult:
    """Immutable result of a backtest run."""

    equity: np.ndarray
    position: np.ndarray
    pnl: np.ndarray
    dates: pd.DatetimeIndex
    strategy_name: str
    symbol: str
    snapshot: str | None
    final_equity: float
    total_return: float
    num_trades: int


class BacktestRunner:
    """Runs backtests via pit_read → shift → Numba accumulator.

    Usage:
        runner = BacktestRunner(store_uri="lmdb://./arctic_data")
        result = runner.run(
            strategy_fn=my_signal_fn,
            symbol="EURUSD",
            start=pd.Timestamp("2024-01-01"),
            end=pd.Timestamp("2024-06-30"),
        )
    """

    def __init__(
        self,
        store_uri: str = "lmdb://./arctic_data",
        risk_per_trade: float = 0.01,
        atr_period: int = 14,
    ) -> None:
        self._store_uri = store_uri
        self._risk_per_trade = risk_per_trade
        self._atr_period = atr_period

    def run(
        self,
        strategy_fn: Callable[[pd.DataFrame], np.ndarray],
        symbol: str,
        start: pd.Timestamp,
        end: pd.Timestamp,
        *,
        timeframe: str = "1h",
        snapshot: str | None = None,
        spread_cost_array: np.ndarray | None = None,
        strategy_name: str = "unnamed",
        persist: bool = True,
    ) -> BacktestResult:
        """Execute a backtest.

        Args:
            strategy_fn: Function that takes a shifted DataFrame and returns a signal array
                         (1=long, -1=short, 0=flat).
            symbol: Forex pair (e.g., "EURUSD").
            start: Start date.
            end: End date (as_of for pit_read).
            timeframe: Bar timeframe (default "1h").
            snapshot: Optional ArcticDB snapshot name for reproducibility.
            spread_cost_array: Spread cost per bar. If None, uses zeros (futures mode).
            strategy_name: Name for audit trail.
            persist: Write results to portfolio library.

        Returns:
            BacktestResult with equity curve, positions, PnL.
        """
        # 1. Read data via pit_read (per D-14)
        arc_symbol = f"{symbol}_{timeframe}"
        df = pit_read(
            library="forex_bars",
            symbol=arc_symbol,
            as_of_timestamp=end,
            store_uri=self._store_uri,
            snapshot=snapshot,
        )

        # Filter to start date
        df = df[df.index >= start]

        if len(df) < self._atr_period + 1:
            msg = f"Insufficient data: {len(df)} bars (need {self._atr_period + 1}+)"
            raise ValueError(msg)

        # 2. Shift features to prevent look-ahead bias
        df_shifted = shift_features(df, columns=["open", "high", "low", "close"], periods=1)
        df_shifted = df_shifted.iloc[1:]  # Drop first row (NaN from shift)

        # 3. Compute ATR from shifted data
        atr = rolling_atr(
            df_shifted["high"].to_numpy(),
            df_shifted["low"].to_numpy(),
            df_shifted["close"].to_numpy(),
            self._atr_period,
        )
        # Fill NaN ATR values with first valid value
        first_valid = atr[~np.isnan(atr)][0] if np.any(~np.isnan(atr)) else 0.001
        atr = np.where(np.isnan(atr), first_valid, atr)

        # 4. Generate signals from strategy function
        signal = strategy_fn(df_shifted)
        if len(signal) != len(df_shifted):
            msg = f"Signal length {len(signal)} != data length {len(df_shifted)}"
            raise ValueError(msg)

        # 5. Prepare spread cost (per D-16: Stage A = variable, Stage B = zeros)
        if spread_cost_array is None:
            spread_cost = np.zeros(len(df_shifted))
        else:
            spread_cost = spread_cost_array

        # 6. Run Numba accumulator
        equity, position, pnl = single_pass_backtest(
            close=df_shifted["close"].to_numpy(),
            signal=signal.astype(np.int8) if signal.dtype != np.int8 else signal,
            risk_per_trade=self._risk_per_trade,
            atr=atr,
            spread_cost=spread_cost,
        )

        # 7. Build result
        num_trades = int(np.sum(np.diff(position.astype(np.int16)) != 0))
        result = BacktestResult(
            equity=equity,
            position=position,
            pnl=pnl,
            dates=df_shifted.index,
            strategy_name=strategy_name,
            symbol=symbol,
            snapshot=snapshot,
            final_equity=float(equity[-1]),
            total_return=float((equity[-1] / equity[0]) - 1.0),
            num_trades=num_trades,
        )

        # 8. Persist to portfolio library (per D-15)
        if persist:
            self._persist_result(result, start, end)

        return result

    def _persist_result(
        self,
        result: BacktestResult,
        start: pd.Timestamp,
        end: pd.Timestamp,
    ) -> None:
        """Write backtest results to ArcticDB portfolio library."""
        import arcticdb as adb

        df = pd.DataFrame(
            {
                "equity": result.equity,
                "position": result.position,
                "pnl": result.pnl,
            },
            index=result.dates,
        )

        store = adb.Arctic(self._store_uri)
        lib = store.get_library("portfolio")

        # Symbol format: strategy_name (per D-15: tagged by strategy + date + snapshot)
        portfolio_symbol = f"bt_{result.strategy_name}_{result.symbol}"

        metadata = {
            "strategy": result.strategy_name,
            "symbol": result.symbol,
            "start": str(start),
            "end": str(end),
            "snapshot": result.snapshot or "latest",
            "final_equity": result.final_equity,
            "total_return": result.total_return,
            "num_trades": result.num_trades,
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
        }

        lib.write(portfolio_symbol, df, metadata=metadata)
        logger.info(
            "Persisted backtest: %s (return=%.4f, trades=%d)",
            portfolio_symbol,
            result.total_return,
            result.num_trades,
        )
