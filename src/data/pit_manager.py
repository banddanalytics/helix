"""Point-in-Time data manager enforcing temporal integrity.

Per D-11: pit_read uses ArcticDB native date_range filtering.
Per D-12: Prevents all 5 look-ahead bias vectors.
Per D-13: validate_pit_compliance uses IC analysis with 1.5x threshold.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    pass

logger = logging.getLogger("helix.data")


class LookAheadBiasError(Exception):
    """Raised when signal exhibits look-ahead bias per IC analysis."""


def pit_read(
    library: str,
    symbol: str,
    as_of_timestamp: pd.Timestamp,
    *,
    store_uri: str = "lmdb://./arctic_data",
    columns: list[str] | None = None,
    snapshot: str | None = None,
) -> pd.DataFrame:
    """Read data from ArcticDB with strict temporal cutoff.

    Returns rows with index <= as_of_timestamp. If snapshot is provided,
    reads from that snapshot version (data written after snapshot is excluded).

    Per D-11: Uses ArcticDB native date_range=(None, as_of_timestamp).
    """
    import arcticdb as adb

    store = adb.Arctic(store_uri)
    lib = store.get_library(library)

    read_kwargs: dict = {
        "date_range": (None, as_of_timestamp),
    }
    if columns is not None:
        read_kwargs["columns"] = columns
    if snapshot is not None:
        read_kwargs["as_of"] = snapshot

    result = lib.read(symbol, **read_kwargs)
    df: pd.DataFrame = result.data
    return df


def validate_pit_compliance(
    signal_df: pd.DataFrame,
    price_df: pd.DataFrame,
    *,
    threshold: float = 1.5,
) -> bool:
    """Validate that signal does not exhibit look-ahead bias.

    Per D-13: If abs(contemp_ic) > abs(forward_ic) * threshold, raises LookAheadBiasError.

    Args:
        signal_df: DataFrame with 'signal' column.
        price_df: DataFrame with 'returns' column (or computes from 'close').
        threshold: IC ratio threshold (default 1.5 per D-13).

    Returns:
        True if compliant.

    Raises:
        LookAheadBiasError: If contemporaneous IC is suspiciously high.
    """
    if "returns" not in price_df.columns:
        if "close" in price_df.columns:
            returns = price_df["close"].pct_change()
        else:
            msg = "price_df must have 'returns' or 'close' column"
            raise ValueError(msg)
    else:
        returns = price_df["returns"]

    signal = signal_df["signal"]

    # Forward IC: signal at T correlates with returns at T+1 (should be significant)
    forward_ic = signal.corr(returns.shift(-1))
    # Contemporaneous IC: signal at T correlates with returns at T (should be near zero)
    contemp_ic = signal.corr(returns)

    if abs(contemp_ic) > abs(forward_ic) * threshold:
        raise LookAheadBiasError(
            f"Contemporaneous IC ({contemp_ic:.4f}) exceeds forward IC "
            f"({forward_ic:.4f}) * {threshold}. Probable look-ahead bias."
        )

    logger.info(
        "PiT compliance passed: forward_ic=%.4f, contemp_ic=%.4f",
        forward_ic, contemp_ic,
    )
    return True


def shift_features(
    df: pd.DataFrame,
    columns: list[str],
    periods: int = 1,
) -> pd.DataFrame:
    """Apply .shift(periods) to specified columns to prevent look-ahead bias.

    Args:
        df: Input DataFrame.
        columns: Column names to shift.
        periods: Number of periods to shift (default 1).

    Returns:
        DataFrame with shifted columns (first `periods` rows have NaN in shifted columns).
    """
    df = df.copy()
    for col in columns:
        if col not in df.columns:
            msg = f"Column '{col}' not found in DataFrame"
            raise KeyError(msg)
        df[col] = df[col].shift(periods)
    return df


def create_snapshot(
    library_name: str,
    snapshot_name: str,
    *,
    store_uri: str = "lmdb://./arctic_data",
) -> None:
    """Create a named snapshot of all symbols in a library.

    Per D-09: EOD snapshots named eod_YYYYMMDD with metadata.
    """
    import arcticdb as adb

    store = adb.Arctic(store_uri)
    lib = store.get_library(library_name)
    lib.snapshot(
        snapshot_name,
        metadata={"created_at": datetime.now(tz=timezone.utc).isoformat()},
    )
    logger.info("Created snapshot '%s' for library '%s'", snapshot_name, library_name)
