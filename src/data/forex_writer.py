"""Forex tick writer with batched ArcticDB appends and quality flagging.

Per D-04: Flushes at 10,000 ticks OR 1 second, whichever comes first.
Uses lib.append() exclusively — never lib.write().
Per D-07: Bad ticks stored with quality:int8 column, not discarded.
Per D-08: Quality events logged to helix.data logger.
"""
from __future__ import annotations

import logging
import threading
from collections import defaultdict
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from src.data.schemas import (
    QUALITY_CLEAN,
    QUALITY_DUPLICATE,
    QUALITY_ROLLOVER_SPIKE,
    QUALITY_WEEKEND_GAP,
)

if TYPE_CHECKING:
    from src.execution.abstract import Tick

logger = logging.getLogger("helix.data")

FLUSH_TICKS: int = 10_000
FLUSH_SECONDS: float = 1.0


class TickWriter:
    """Non-blocking tick writer with background flush thread.

    Call write(tick) from any thread — it appends to a thread-safe buffer.
    A dedicated background thread flushes to ArcticDB at FLUSH_TICKS or
    FLUSH_SECONDS, whichever comes first.

    Usage::

        writer = TickWriter(store_uri="lmdb://./arctic_data")
        writer.start()
        writer.write(tick)
        writer.stop()  # flushes remaining ticks and joins background thread
    """

    def __init__(self, store_uri: str = "lmdb://./arctic_data") -> None:
        self._buffer: defaultdict[str, list[Tick]] = defaultdict(list)
        self._lock = threading.Lock()
        self._store_uri = store_uri
        self._stop = threading.Event()
        self._flush_count: int = 0
        self._thread: threading.Thread | None = None
        # Lazy-initialized ArcticDB store — one connection per TickWriter instance
        self._store: object | None = None

    def start(self) -> None:
        """Start the background flush thread."""
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._flush_loop,
            daemon=True,
            name="tick-writer-flush",
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop background flush thread and flush remaining ticks."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        # Final flush of any remaining buffered ticks
        self._flush_all()

    @property
    def flush_count(self) -> int:
        """Number of flush operations completed (one per symbol batch)."""
        return self._flush_count

    def write(self, tick: Tick) -> None:
        """Buffer a tick. Non-blocking — returns immediately.

        Triggers a flush for the symbol if its buffer reaches FLUSH_TICKS.
        """
        with self._lock:
            self._buffer[tick.symbol].append(tick)
            if len(self._buffer[tick.symbol]) >= FLUSH_TICKS:
                self._flush_symbol(tick.symbol)

    def _flush_loop(self) -> None:
        """Background thread: flush all symbols every FLUSH_SECONDS."""
        while not self._stop.wait(timeout=FLUSH_SECONDS):
            self._flush_all()

    def _flush_all(self) -> None:
        """Flush all symbols that have buffered ticks."""
        with self._lock:
            for symbol in list(self._buffer.keys()):
                if self._buffer[symbol]:
                    self._flush_symbol(symbol)

    def _flush_symbol(self, symbol: str) -> None:
        """Flush buffered ticks for one symbol to ArcticDB.

        Must be called with self._lock held.
        """
        ticks = self._buffer.pop(symbol, [])
        if not ticks:
            return

        df = _ticks_to_dataframe(ticks)
        df = _flag_quality(df)
        # Sort by timestamp — ArcticDB append requires monotonically increasing index
        df = df.sort_index()

        import arcticdb as adb  # deferred import — avoids cost when not flushing

        if self._store is None:
            self._store = adb.Arctic(self._store_uri)
        lib = self._store.get_library("forex_ticks")  # type: ignore[union-attr]
        lib.append(symbol, df)
        self._flush_count += 1
        logger.info(
            "Flushed %d ticks for %s",
            len(ticks),
            symbol,
            extra={"symbol": symbol, "tick_count": len(ticks)},
        )


def _ticks_to_dataframe(ticks: list[Tick]) -> pd.DataFrame:
    """Convert Tick dataclasses to a DataFrame with DatetimeIndex."""
    records = []
    for t in ticks:
        records.append(
            {
                "bid": t.bid,
                "ask": t.ask,
                "spread": t.ask - t.bid,
                "tick_volume": t.bid_volume,
                "source": t.source,
            }
        )
    df = pd.DataFrame(records)
    df.index = pd.DatetimeIndex(
        [pd.Timestamp(t.timestamp) for t in ticks],
        name="timestamp",
    )
    return df


def _flag_quality(df: pd.DataFrame) -> pd.DataFrame:
    """Add int8 quality column to tick DataFrame.

    Per D-07: ticks are stored with quality flag, not discarded.
    Priority (lowest wins, first applied overwrites): clean -> weekend -> rollover -> duplicate.
    Duplicate check is final so it always overwrites any other flag.
    """
    df = df.copy()
    df["quality"] = np.int8(QUALITY_CLEAN)

    # Weekend gap: Saturday=5, Sunday=6 (dayofweek is 0-based Monday=0)
    weekend_mask = df.index.dayofweek >= 5
    if weekend_mask.any():
        df.loc[weekend_mask, "quality"] = np.int8(QUALITY_WEEKEND_GAP)
        logger.debug(
            "Weekend gap: %d ticks flagged",
            weekend_mask.sum(),
            extra={"quality_flag": "weekend_gap", "count": int(weekend_mask.sum())},
        )

    # Rollover spike: spread > 5x median spread AND tick is at 00:00 UTC hour
    if len(df) > 1:
        median_spread = df["spread"].median()
        if median_spread > 0:
            rollover_mask = (df.index.hour == 0) & (df["spread"] > median_spread * 5)
            if rollover_mask.any():
                df.loc[rollover_mask, "quality"] = np.int8(QUALITY_ROLLOVER_SPIKE)
                logger.debug(
                    "Rollover spike: %d ticks flagged",
                    rollover_mask.sum(),
                    extra={
                        "quality_flag": "rollover_spike",
                        "count": int(rollover_mask.sum()),
                    },
                )

    # Duplicate: same timestamp AND same bid AND same ask (keep first as clean)
    # Detect duplicated timestamps first, then filter to same bid+ask
    ts_dup_mask = df.index.duplicated(keep="first")
    if ts_dup_mask.any():
        # Among rows with duplicate timestamps, flag those with same bid+ask
        bid_ask_dup_mask = df.duplicated(subset=["bid", "ask"], keep="first")
        dup_mask = ts_dup_mask & bid_ask_dup_mask
        if dup_mask.any():
            df.loc[dup_mask, "quality"] = np.int8(QUALITY_DUPLICATE)
            logger.debug(
                "Duplicate ticks: %d ticks flagged",
                dup_mask.sum(),
                extra={"quality_flag": "duplicate", "count": int(dup_mask.sum())},
            )

    return df
