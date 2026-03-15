"""
db/connection.py — Centralised SQLite connection factory for A.R.I.A.

Every module that needs a database connection MUST use ``get_connection``
instead of raw ``sqlite3.connect()``.  This guarantees WAL journal mode
and foreign-key enforcement on every connection, every time.
"""
from __future__ import annotations

import logging
import sqlite3

log: logging.Logger = logging.getLogger(__name__)


def get_connection(db_path: str) -> sqlite3.Connection:
    """
    Open (or create) the SQLite database at *db_path* and return a
    connection with production-safe pragmas already applied.

    Pragmas set per connection:
        PRAGMA journal_mode = WAL      — concurrent readers, single writer
        PRAGMA foreign_keys = ON       — enforce FK constraints (off by default!)

    The caller is responsible for closing the connection, typically via::

        con = get_connection("aria.db")
        try:
            ...
        finally:
            con.close()

    If either PRAGMA fails, the connection is closed before the
    exception propagates — no leaked file descriptors.
    """
    con: sqlite3.Connection = sqlite3.connect(db_path)
    try:
        con.execute("PRAGMA journal_mode = WAL")
        con.execute("PRAGMA foreign_keys = ON")
    except Exception:
        con.close()
        raise
    log.debug("Opened connection to %s (WAL, FK=ON)", db_path)
    return con
