"""Ground-truth arcticdb API stub — auto-verified against arcticdb 6.10.2.

IMPORTANT: 'upsert' is intentionally absent — it does NOT exist in arcticdb.
This is the canonical phantom function test case for the KCH validator.
"""

from __future__ import annotations

STUB: dict[str, dict[str, set[str]]] = {
    "arcticdb": {
        # Arctic top-level constructor and library accessor
        "Arctic": {"uri", "encoding_version"},
        "get_library": {"library", "create_if_missing", "library_options"},
        # Library methods (via Library object)
        "write": {"symbol", "data", "metadata", "prune_previous_version"},
        "write_batch": {"payloads", "prune_previous_version"},
        "read": {"symbol", "as_of", "date_range", "columns", "query_builder"},
        "read_batch": {"symbols", "query_builder"},
        "append": {"symbol", "data", "metadata", "incomplete"},
        "update": {"symbol", "data", "metadata", "upsert", "date_range"},
        "delete": {"symbol", "versions", "date_range"},
        "delete_version": {"symbol", "version"},
        "delete_range": {"symbol", "date_range", "truncate"},
        "list_symbols": {"regex", "snapshot"},
        "has_symbol": {"symbol", "as_of"},
        "snapshot": {"snapshot_name", "metadata", "skip_symbols", "versions"},
        "delete_snapshot": {"snapshot_name"},
        "list_snapshots": {"load_metadata"},
        "list_versions": {"symbol", "snapshot", "latest_only", "skip_snapshots"},
        "get_description": {"symbol", "as_of"},
        "tail": {"symbol", "n", "as_of", "columns"},
        "head": {"symbol", "n", "as_of", "columns"},
        "is_symbol_fragmented": {"symbol", "config"},
        "defragment_symbol_data": {"symbol", "config"},
        "compact_incomplete": {"symbol", "convert_int_to_float", "sparsify_floats"},
        "sort_and_finalize_staged_data": {"symbol", "delete_staged_data_on_failure"},
        "get_library": {"library", "create_if_missing", "library_options"},
        "create_library": {"library", "library_options"},
        "delete_library": {"library"},
        "list_libraries": set(),
        "has_library": {"library"},
    }
}

SUBMODULES: list[str] = [
    "Arctic",
    "QueryBuilder",
    "LibraryOptions",
    "EncodingVersion",
    "WritePayload",
]
