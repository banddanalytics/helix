"""ArcticDB administrative CLI tool.

Usage:
    python -m src.data.admin_cli list-libraries
    python -m src.data.admin_cli list-symbols forex_ticks
    python -m src.data.admin_cli schema forex_ticks EURUSD
    python -m src.data.admin_cli compact forex_ticks
"""
from __future__ import annotations

import argparse
import sys

from src.data.arctic_store import get_store, initialize_store


def cmd_list_libraries(args: argparse.Namespace) -> None:
    store = get_store(args.uri)
    for lib_name in sorted(store.list_libraries()):
        print(lib_name)


def cmd_list_symbols(args: argparse.Namespace) -> None:
    store = get_store(args.uri)
    lib = store.get_library(args.library)
    for symbol in sorted(lib.list_symbols()):
        print(symbol)


def cmd_schema(args: argparse.Namespace) -> None:
    store = get_store(args.uri)
    lib = store.get_library(args.library)
    info = lib.get_description(args.symbol)
    print(info)


def cmd_compact(args: argparse.Namespace) -> None:
    store = get_store(args.uri)
    lib = store.get_library(args.library)
    for symbol in lib.list_symbols():
        if lib.is_symbol_fragmented(symbol):
            lib.defragment_symbol_data(symbol)
            print(f"Compacted: {symbol}")
        else:
            print(f"Not fragmented: {symbol}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ArcticDB admin CLI")
    parser.add_argument("--uri", default="lmdb://./arctic_data", help="ArcticDB URI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list-libraries", help="List all libraries")

    p_ls = sub.add_parser("list-symbols", help="List symbols in a library")
    p_ls.add_argument("library", help="Library name")

    p_schema = sub.add_parser("schema", help="Show symbol schema/description")
    p_schema.add_argument("library", help="Library name")
    p_schema.add_argument("symbol", help="Symbol name")

    p_compact = sub.add_parser("compact", help="Compact fragmented symbols")
    p_compact.add_argument("library", help="Library name")

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    commands = {
        "list-libraries": cmd_list_libraries,
        "list-symbols": cmd_list_symbols,
        "schema": cmd_schema,
        "compact": cmd_compact,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
