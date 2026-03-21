"""Ground-truth MT5 API whitelist — hand-written because MetaTrader5 is Windows-only.

MT5 Python API cannot be introspected on Linux (Wine does not support the named-pipe IPC).
This stub reflects the real MetaTrader5 package as of version 5.0.45.
"""

from __future__ import annotations

STUB: dict[str, dict[str, set[str]]] = {
    "MetaTrader5": {
        "initialize": {"path", "login", "password", "server", "timeout", "portable"},
        "login": {"login", "password", "server", "timeout"},
        "shutdown": set(),
        "version": set(),
        "last_error": set(),
        "account_info": set(),
        "terminal_info": set(),
        "symbols_total": set(),
        "symbols_get": {"group"},
        "symbol_info": {"symbol"},
        "symbol_info_tick": {"symbol"},
        "symbol_select": {"symbol", "enable"},
        "market_book_add": {"symbol"},
        "market_book_release": {"symbol"},
        "market_book_get": {"symbol"},
        "copy_ticks_from": {"symbol", "date_from", "count", "flags"},
        "copy_ticks_range": {"symbol", "date_from", "date_to", "flags"},
        "copy_rates_from": {"symbol", "timeframe", "date_from", "count"},
        "copy_rates_from_pos": {"symbol", "timeframe", "start_pos", "count"},
        "copy_rates_range": {"symbol", "timeframe", "date_from", "date_to"},
        "orders_total": set(),
        "orders_get": {"symbol", "group", "ticket"},
        "order_calc_margin": {"action", "symbol", "volume", "price"},
        "order_calc_profit": {
            "action",
            "symbol",
            "volume",
            "price_open",
            "price_close",
        },
        "order_check": {"request"},
        "order_send": {"request"},
        "positions_total": set(),
        "positions_get": {"symbol", "group", "ticket"},
        "history_orders_total": {"date_from", "date_to"},
        "history_orders_get": {"date_from", "date_to", "group", "ticket", "position"},
        "history_deals_total": {"date_from", "date_to"},
        "history_deals_get": {"date_from", "date_to", "group", "ticket", "position"},
    }
}
