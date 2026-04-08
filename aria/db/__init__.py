"""
SQLite persistence layer for A.R.I.A.

Public surface (lazy-loaded to avoid -m module warnings):
    get_connection(db_path) - open connection with WAL + FK pragmas
    init_db(db_path)        - create schema, set pragmas
    seed_db(db_path)        - insert idempotent test data
"""
from __future__ import annotations

__all__ = ["get_connection", "init_db", "seed_db"]


def __getattr__(name: str):
    if name == "get_connection":
        from aria.db.connection import get_connection
        return get_connection
    if name == "init_db":
        from aria.db.schema import init_db
        return init_db
    if name == "seed_db":
        from aria.db.seed import seed_db
        return seed_db
    raise AttributeError(f"module 'aria.db' has no attribute {name!r}")
