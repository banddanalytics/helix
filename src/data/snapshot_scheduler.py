"""EOD snapshot scheduler with startup backfill.

Per D-09: Daily snapshots at 22:00 UTC named eod_YYYYMMDD.
Per D-10: On startup, checks last snapshot date and backfills missed days.
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING

from src.data.pit_manager import create_snapshot
from src.data.schemas import LIBRARY_NAMES

if TYPE_CHECKING:
    pass

logger = logging.getLogger("helix.data")

SNAPSHOT_PREFIX = "eod_"
SNAPSHOT_TIME_UTC = 22  # 22:00 UTC = market close


class SnapshotScheduler:
    """Daily EOD snapshot scheduler with backfill on startup.

    Usage:
        scheduler = SnapshotScheduler(store_uri="lmdb://./arctic_data")
        await scheduler.backfill_missed()
        await scheduler.run()  # blocks, runs daily at 22:00 UTC
    """

    def __init__(
        self,
        store_uri: str = "lmdb://./arctic_data",
        libraries: list[str] | None = None,
    ) -> None:
        self._store_uri = store_uri
        self._libraries = libraries or [
            lib for lib in LIBRARY_NAMES if lib != "mbo_ticks"
        ]
        self._stop = asyncio.Event()

    def _get_last_snapshot_date(self, library_name: str) -> date | None:
        """Find the most recent eod_YYYYMMDD snapshot date for a library."""
        import arcticdb as adb

        store = adb.Arctic(self._store_uri)
        lib = store.get_library(library_name)
        snapshots = lib.list_snapshots()

        eod_dates: list[date] = []
        for name in snapshots:
            match = re.match(r"eod_(\d{8})", name)
            if match:
                try:
                    eod_dates.append(
                        datetime.strptime(match.group(1), "%Y%m%d").replace(  # noqa: DTZ007
                            tzinfo=timezone.utc
                        ).date()
                    )
                except ValueError:
                    continue

        return max(eod_dates) if eod_dates else None

    async def backfill_missed(self) -> int:
        """Create snapshots for any missed days since the last eod snapshot.

        Per D-10: On startup, if gap exists, backfills retroactive snapshots.
        Note (per RESEARCH Pitfall 5): Backfill snapshots capture current library
        state, not historical state. This is acceptable for normal operation.

        Returns number of backfill snapshots created.
        """
        today = datetime.now(tz=timezone.utc).date()
        count = 0

        for library_name in self._libraries:
            last_date = await asyncio.to_thread(
                self._get_last_snapshot_date, library_name
            )

            if last_date is None:
                # No snapshots yet — create one for yesterday
                start = today - timedelta(days=1)
            else:
                start = last_date + timedelta(days=1)

            current = start
            while current < today:
                snap_name = f"{SNAPSHOT_PREFIX}{current.strftime('%Y%m%d')}"
                try:
                    await asyncio.to_thread(
                        create_snapshot,
                        library_name,
                        snap_name,
                        store_uri=self._store_uri,
                    )
                    count += 1
                    logger.info(
                        "Backfilled snapshot %s for %s", snap_name, library_name
                    )
                except Exception:
                    logger.exception(
                        "Failed to backfill snapshot %s for %s",
                        snap_name, library_name,
                    )
                current += timedelta(days=1)

        return count

    async def create_eod_snapshot(self) -> None:
        """Create today's EOD snapshot for all managed libraries."""
        today = datetime.now(tz=timezone.utc).date()
        snap_name = f"{SNAPSHOT_PREFIX}{today.strftime('%Y%m%d')}"

        for library_name in self._libraries:
            await asyncio.to_thread(
                create_snapshot,
                library_name,
                snap_name,
                store_uri=self._store_uri,
            )

    async def run(self) -> None:
        """Run the scheduler loop. Blocks until stop() is called."""
        while not self._stop.is_set():
            now = datetime.now(tz=timezone.utc)
            target = now.replace(
                hour=SNAPSHOT_TIME_UTC, minute=0, second=0, microsecond=0
            )
            if now >= target:
                target += timedelta(days=1)

            wait_seconds = (target - now).total_seconds()
            logger.info("Next EOD snapshot in %.0f seconds", wait_seconds)

            try:
                await asyncio.wait_for(self._stop.wait(), timeout=wait_seconds)
                break  # stop was called
            except asyncio.TimeoutError:
                await self.create_eod_snapshot()

    def stop(self) -> None:
        """Signal the scheduler to stop."""
        self._stop.set()
