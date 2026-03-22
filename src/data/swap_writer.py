"""Daily swap rate writer for ArcticDB swap_rates library.

Runs daily at 00:05 UTC via an asyncio scheduler.
Per Claude's Discretion: uses asyncio-based scheduling (no APScheduler dep).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger("helix.data")


class SwapWriter:
    """Writes daily swap rate snapshots to ArcticDB.

    Usage:
        writer = SwapWriter(store_uri="lmdb://./arctic_data",
                            get_swap_rates_fn=my_get_swap_rates)
        await writer.write_daily(symbols=["EURUSD", "GBPUSD"])
    """

    def __init__(
        self,
        store_uri: str = "lmdb://./arctic_data",
        get_swap_rates_fn: Callable[[str], dict[str, float]] | None = None,
    ) -> None:
        self._store_uri = store_uri
        self._get_swap_rates = get_swap_rates_fn

    async def write_daily(self, symbols: list[str]) -> int:
        """Fetch swap rates for all symbols and append to swap_rates library.

        Returns number of symbols written.
        """
        import arcticdb as adb

        if self._get_swap_rates is None:
            logger.warning("No get_swap_rates_fn configured; skipping swap write")
            return 0

        records = []
        today = datetime.now(tz=timezone.utc).date()

        for symbol in symbols:
            try:
                rates = self._get_swap_rates(symbol)
                records.append({
                    "symbol": symbol,
                    "swap_long": rates.get("swap_long", 0.0),
                    "swap_short": rates.get("swap_short", 0.0),
                    "swap_annual_long_pct": rates.get("swap_annual_long_pct", 0.0),
                    "swap_annual_short_pct": rates.get("swap_annual_short_pct", 0.0),
                })
            except Exception:
                logger.exception("Failed to get swap rates for %s", symbol)

        if not records:
            return 0

        df = pd.DataFrame(records)
        df.index = pd.DatetimeIndex([pd.Timestamp(today)] * len(df), name="date")

        store = adb.Arctic(self._store_uri)
        lib = store.get_library("swap_rates")
        await asyncio.to_thread(lib.append, "daily_swaps", df)

        logger.info("Wrote swap rates for %d symbols", len(records))
        return len(records)
