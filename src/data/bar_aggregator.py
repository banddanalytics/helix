"""Bar aggregation from tick data with session tagging.

Per D-05: 6 timeframes: 1m, 5m, 15m, 1h, 4h, 1d.
Per D-06: Session tags: 0=Asian(00-08), 1=London(08-13), 2=Overlap(13-16), 3=NY(16-21).
Bars written to forex_bars library with symbol format {SYMBOL}_{timeframe}.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from src.data.schemas import FOREX_BAR_COLUMNS

if TYPE_CHECKING:
    pass

logger = logging.getLogger("helix.data")

# Per D-05: All 6 timeframes computed from tick stream
TIMEFRAMES: dict[str, str] = {
    "1m": "1min",
    "5m": "5min",
    "15m": "15min",
    "1h": "1h",
    "4h": "4h",
    "1d": "1D",
}


# Per D-06: Session tag boundaries (UTC hours)
def hour_to_session(hour: int) -> int:
    """Map UTC hour to session tag.

    0=Asian (00:00-08:00), 1=London (08:00-13:00),
    2=Overlap (13:00-16:00), 3=New York (16:00-21:00).
    Hours 21-24 map to Asian (pre-open).
    """
    if 0 <= hour < 8:
        return 0   # Asian
    if 8 <= hour < 13:
        return 1   # London
    if 13 <= hour < 16:
        return 2   # Overlap
    if 16 <= hour < 21:
        return 3   # New York
    return 0       # Asian (21:00-00:00)


def aggregate_bars(ticks_df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Aggregate tick DataFrame into OHLCV bars at given pandas resample rule.

    Args:
        ticks_df: DataFrame with DatetimeIndex and columns: bid, ask, spread, tick_volume.
        rule: Pandas resample rule string (e.g., '1min', '5min', '1h', '1D').

    Returns:
        DataFrame with columns: open, high, low, close, tick_volume, spread_avg, spread_max, session.
    """
    mid = (ticks_df["bid"] + ticks_df["ask"]) / 2.0
    bars = mid.resample(rule).ohlc()
    bars["tick_volume"] = ticks_df["tick_volume"].resample(rule).sum()
    bars["spread_avg"] = ticks_df["spread"].resample(rule).mean()
    bars["spread_max"] = ticks_df["spread"].resample(rule).max()
    bars["session"] = pd.array(
        [hour_to_session(h) for h in bars.index.hour],
        dtype=pd.Int8Dtype(),
    ).astype(np.int8)
    # Drop bars with no trades (NaN open)
    bars = bars.dropna(subset=["open"])
    expected_cols = set(FOREX_BAR_COLUMNS.keys())
    actual_cols = set(bars.columns)
    if actual_cols != expected_cols:
        raise ValueError(
            f"Bar schema drift: expected {sorted(expected_cols)}, got {sorted(actual_cols)}"
        )
    return bars


class BarAggregator:
    """Aggregates ticks into bars across all timeframes and writes to ArcticDB.

    Usage:
        agg = BarAggregator(store_uri="lmdb://./arctic_data")
        agg.process_ticks("EURUSD", ticks_df)
    """

    def __init__(self, store_uri: str = "lmdb://./arctic_data") -> None:
        self._store_uri = store_uri

    def process_ticks(self, symbol: str, ticks_df: pd.DataFrame) -> dict[str, int]:
        """Aggregate ticks into all 6 timeframes and append to forex_bars library.

        Returns dict of {timeframe: bar_count} for logging.
        """
        import arcticdb as adb

        store = adb.Arctic(self._store_uri)
        lib = store.get_library("forex_bars")
        result: dict[str, int] = {}

        for tf_label, resample_rule in TIMEFRAMES.items():
            bars = aggregate_bars(ticks_df, resample_rule)
            if not bars.empty:
                arc_symbol = f"{symbol}_{tf_label}"
                lib.append(arc_symbol, bars)
                result[tf_label] = len(bars)
                logger.info(
                    "Aggregated %d %s bars for %s",
                    len(bars), tf_label, symbol,
                    extra={"symbol": symbol, "timeframe": tf_label, "bar_count": len(bars)},
                )

        return result
