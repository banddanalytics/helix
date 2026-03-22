"""VectorBT Pro configuration with memory-aware chunk sizing.

Per D-18: chunking.n_chunks='auto', caching.register_lazily=True,
caching.use_disk=True, caching.disk_path='/tmp/vbt_cache'.
"""
from __future__ import annotations

import logging

logger = logging.getLogger("helix.backtest")


def configure_vbt() -> None:
    """Configure VectorBT Pro settings. Call once at startup.

    Gracefully handles missing vectorbtpro package (not yet installed).
    """
    try:
        import psutil
        import vectorbtpro as vbt

        vbt.settings.chunking["n_chunks"] = "auto"
        vbt.settings.caching["register_lazily"] = True

        available_mb = psutil.virtual_memory().available // (1024 * 1024)
        vbt.settings.chunking["size"] = int(available_mb * 0.8)

        logger.info(
            "VectorBT Pro configured: chunk_size=%d MB",
            int(available_mb * 0.8),
        )
    except ImportError:
        logger.warning(
            "vectorbtpro not installed — BacktestRunner will use raw accumulator output only"
        )
