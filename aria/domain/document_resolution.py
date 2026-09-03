"""Authoritative contract-document version resolution.

Given a contract and a point in time, decide which uploaded contract document
version is the authoritative one. This mirrors ``contract_lookup`` but operates
on documents instead of contracts, and is deliberately pure/SQLite-based so it
can be unit-tested without the Gemini stack.

Rules
-----
* Only documents with ``status = 'READY'`` are ever resolvable.
* A version applies when ``effective_from <= at_date`` AND
  (``superseded_at IS NULL`` OR ``at_date < superseded_at``).
* ``at_date`` defaults to "now".
* If several versions satisfy the window (should not happen — the ingest
  service supersedes prior versions), the highest ``version`` wins.
* If no version covers ``at_date`` exactly, fall back to the latest version
  whose ``effective_from <= at_date`` (documents uploaded after the fact can
  still be authoritative for history they claim to cover — the resolution
  caller surfaces which version was used).
"""
from __future__ import annotations

import datetime
import sqlite3
from typing import Any


def _as_date(value: str | None) -> datetime.date | None:
    if not value:
        return None
    text = str(value).strip()
    try:
        return datetime.date.fromisoformat(text[:10])
    except ValueError:
        return None


def resolve_document_version(
    db: sqlite3.Connection,
    contract_id: int,
    at: str | None = None,
) -> dict[str, Any] | None:
    """Resolve the applicable READY document version for *contract_id*.

    Parameters
    ----------
    db:
        Open SQLite connection.
    contract_id:
        The contract (prefer the inspection-time snapshot id).
    at:
        ISO date (or ISO datetime — only the date part is used) the version
        must be applicable at. Defaults to today (UTC).

    Returns a dict with the document row, or ``None`` when no READY version
    covers the requested date.
    """
    if at:
        at_date = _as_date(at)
        if at_date is None:
            raise ValueError(f"Invalid 'at' date: {at!r}")
    else:
        at_date = datetime.datetime.now(datetime.timezone.utc).date()

    cur = db.cursor()
    cur.row_factory = sqlite3.Row
    rows = cur.execute(
        """
        SELECT id, contract_id, version, effective_from, superseded_at,
               file_name, file_hash, file_path, status, page_count, created_at
        FROM contract_documents
        WHERE contract_id = ? AND status = 'READY'
        ORDER BY version ASC
        """,
        (contract_id,),
    ).fetchall()
    if not rows:
        return None

    documents = [dict(row) for row in rows]

    applicable = [
        doc
        for doc in documents
        if (_as_date(doc["effective_from"]) or datetime.date.min) <= at_date
        and (
            doc["superseded_at"] is None
            or at_date < (_as_date(doc["superseded_at"]) or datetime.date.min)
        )
    ]
    if applicable:
        return max(applicable, key=lambda doc: doc["version"])

    # Fall back to the latest version effective at or before the date.
    covering = [
        doc
        for doc in documents
        if (_as_date(doc["effective_from"]) or datetime.date.min) <= at_date
    ]
    if covering:
        return max(covering, key=lambda doc: doc["version"])

    return None
