"""Schema definitions for Forex (Stage A) and CME MBO (Stage B) data.

These constants define the column names and dtypes for each ArcticDB library.
They are used for documentation and validation — ArcticDB infers schemas from
the first DataFrame written to a symbol.
"""
from __future__ import annotations

LIBRARY_NAMES: list[str] = [
    "forex_ticks",
    "forex_bars",
    "swap_rates",
    "mbo_ticks",
    "signals",
    "portfolio",
]

FOREX_TICK_COLUMNS: dict[str, str] = {
    "bid": "float64",
    "ask": "float64",
    "spread": "float64",
    "tick_volume": "float64",
    "source": "object",
    "quality": "int8",
}
# Index: timestamp datetime64[ns]
# Symbol: stored as ArcticDB symbol key, not a column

FOREX_BAR_COLUMNS: dict[str, str] = {
    "open": "float64",
    "high": "float64",
    "low": "float64",
    "close": "float64",
    "tick_volume": "float64",
    "spread_avg": "float64",
    "spread_max": "float64",
    "session": "int8",
}

SWAP_RATE_COLUMNS: dict[str, str] = {
    "symbol": "object",
    "swap_long": "float64",
    "swap_short": "float64",
    "swap_annual_long_pct": "float64",
    "swap_annual_short_pct": "float64",
}

MBO_TICK_COLUMNS: dict[str, str] = {
    "recv_ts": "datetime64[ns]",
    "order_id": "int64",
    "side": "int8",
    "price": "float64",
    "qty": "int32",
    "action": "int8",
    "rpt_seq": "int64",
    "agg_qty": "int32",
    "num_orders": "int32",
    "price_level": "int8",
}

# Quality flag constants (int8 values for quality column on tick writes)
QUALITY_CLEAN: int = 0
QUALITY_ROLLOVER_SPIKE: int = 1
QUALITY_WEEKEND_GAP: int = 2
QUALITY_DUPLICATE: int = 3
