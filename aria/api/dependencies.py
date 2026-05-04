"""
FastAPI dependency injection for A.R.I.A.

Provides:
    get_api_key  â€” validates x-api-key header
    get_db       â€” yields a DB connection per request with guaranteed cleanup
"""
from __future__ import annotations

import logging
import os
import secrets
import sqlite3
from collections.abc import Generator

from dotenv import load_dotenv
from fastapi import Header, HTTPException

from aria.db.connection import get_connection

load_dotenv()

log: logging.Logger = logging.getLogger(__name__)

_API_KEY: str = os.environ.get("ARIA_API_KEY", "")
_DB_PATH: str = os.environ.get("ARIA_DB_PATH", "./runtime/db/aria.db")


def get_api_key(x_api_key: str | None = Header(default=None)) -> str:
    if not _API_KEY:
        raise HTTPException(503, "API key not configured on this server.")
    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Include x-api-key header.",
        )
    if not secrets.compare_digest(x_api_key, _API_KEY):
        raise HTTPException(
            status_code=403,
            detail="Invalid API key.",
        )
    return x_api_key


def get_db() -> Generator[sqlite3.Connection, None, None]:
    con = get_connection(_DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
    finally:
        con.close()
