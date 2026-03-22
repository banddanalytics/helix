"""ArcticDB store initialization and library management.

Per D-01: LMDB backend at ./arctic_data for both dev and production.
Per D-02: Same path in dev, staging, production — no env var switching in Phase 2.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import arcticdb as adb

from src.data.schemas import LIBRARY_NAMES

if TYPE_CHECKING:
    pass

_STORE: adb.Arctic | None = None


def get_store(uri: str = "lmdb://./arctic_data") -> adb.Arctic:
    """Return cached ArcticDB store instance.

    Uses module-level singleton (not lru_cache) so tests can override via
    reset_store() with a tmp path.
    """
    global _STORE
    if _STORE is None:
        _STORE = adb.Arctic(uri)
    return _STORE


def reset_store() -> None:
    """Clear cached store instance. Used by tests to inject tmp paths."""
    global _STORE
    _STORE = None


def initialize_store(uri: str = "lmdb://./arctic_data") -> adb.Arctic:
    """Initialize ArcticDB with all 6 libraries. Idempotent.

    Returns the Arctic store instance.
    """
    store = get_store(uri)
    for name in LIBRARY_NAMES:
        if not store.has_library(name):
            store.create_library(name)
    return store


def get_library(name: str, *, uri: str = "lmdb://./arctic_data") -> adb.Library:
    """Get a library by name. Raises KeyError if library does not exist."""
    store = get_store(uri)
    return store.get_library(name)
