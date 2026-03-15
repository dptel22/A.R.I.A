"""
api/dependencies.py — FastAPI dependency injection for A.R.I.A.

Provides:
    get_api_key  — validates x-api-key header
    get_db       — yields a DB connection per request with guaranteed cleanup
"""
from __future__ import annotations

import logging
import os
import sqlite3
import sys
from collections.abc import Generator

from dotenv import load_dotenv
from fastapi import Header, HTTPException

from db.connection import get_connection

load_dotenv()

log: logging.Logger = logging.getLogger(__name__)

_API_KEY: str = os.environ.get("ARIA_API_KEY", "")
_DB_PATH: str = os.environ.get("ARIA_DB_PATH", "./aria.db")

# Fail-fast: refuse to start if API key is missing or empty
if not _API_KEY:
    log.critical(
        "ARIA_API_KEY is not set or is empty. "
        "Set it in .env or as an environment variable. Aborting."
    )
    sys.exit(1)


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------

def get_api_key(x_api_key: str = Header(default=None)) -> str:
    """
    Validate the ``x-api-key`` header on every protected endpoint.

    Returns the validated key on success.

    Raises:
        HTTPException 401: Missing or empty header.
        HTTPException 403: Invalid key.
    """
    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Include x-api-key header.",
        )
    if x_api_key != _API_KEY:
        raise HTTPException(
            status_code=403,
            detail="Invalid API key.",
        )
    return x_api_key


# ---------------------------------------------------------------------------
# DB dependency
# ---------------------------------------------------------------------------

def get_db() -> Generator[sqlite3.Connection, None, None]:
    """
    Yield a DB connection with WAL + FK pragmas via the centralised factory.

    Uses FastAPI's ``yield`` dependency pattern — the connection is
    guaranteed to close after the request completes, even on exception.
    """
    con = get_connection(_DB_PATH)
    con.row_factory = sqlite3.Row   # dict-like row access
    try:
        yield con
    finally:
        con.close()
