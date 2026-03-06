"""
db package — A.R.I.A. SQLite persistence layer.

Public surface (lazy-loaded to avoid -m module warnings):
    init_db(db_path)  — create schema, set pragmas
    seed_db(db_path)  — insert idempotent test data
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from db.schema import init_db as _init_db  # noqa: F401
    from db.seed import seed_db as _seed_db    # noqa: F401

__all__ = ["init_db", "seed_db"]


def __getattr__(name: str):  # PEP 562 lazy package attributes
    if name == "init_db":
        from db.schema import init_db
        return init_db
    if name == "seed_db":
        from db.seed import seed_db
        return seed_db
    raise AttributeError(f"module 'db' has no attribute {name!r}")
