"""
db package — A.R.I.A. SQLite persistence layer.

Public surface (lazy-loaded to avoid -m module warnings):
    get_connection(db_path) — open connection with WAL + FK pragmas
    init_db(db_path)        — create schema, set pragmas
    seed_db(db_path)        — insert idempotent test data
"""
from __future__ import annotations

__all__ = ["get_connection", "init_db", "seed_db"]


def __getattr__(name: str):  # PEP 562 lazy package attributes
    if name == "get_connection":
        from db.connection import get_connection
        return get_connection
    if name == "init_db":
        from db.schema import init_db
        return init_db
    if name == "seed_db":
        from db.seed import seed_db
        return seed_db
    raise AttributeError(f"module 'db' has no attribute {name!r}")
