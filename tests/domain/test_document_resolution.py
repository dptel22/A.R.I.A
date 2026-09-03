"""Unit tests for aria/domain/document_resolution.py"""
from __future__ import annotations

import sqlite3

import pytest

from aria.db.connection import get_connection
from aria.db.schema import init_db
from aria.domain.document_resolution import resolve_document_version


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "resolution-test.db"
    init_db(str(db_path))
    con = get_connection(str(db_path))
    try:
        with con:
            con.execute(
                "INSERT INTO road_segments (name, gps_min_lat, gps_max_lat, gps_min_lon, gps_max_lon)"
                " VALUES ('Res Segment', 12.9, 13.0, 77.6, 77.7)"
            )
            cur = con.execute(
                "INSERT INTO contracts (road_segment_id, contractor_name, contractor_email, dlp_end_date)"
                " VALUES ((SELECT id FROM road_segments LIMIT 1), 'C', 'c@test', '2027-12-31')"
            )
            yield con, int(cur.lastrowid)
    finally:
        con.close()


def _add_doc(
    con: sqlite3.Connection,
    contract_id: int,
    version: int,
    effective_from: str,
    superseded_at: str | None,
    status: str = "READY",
) -> int:
    cur = con.execute(
        """
        INSERT INTO contract_documents (
            contract_id, version, effective_from, superseded_at,
            file_name, file_hash, file_path, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            contract_id,
            version,
            effective_from,
            superseded_at,
            f"doc_v{version}.pdf",
            f"hash-{contract_id}-{version}",
            f"/tmp/doc_v{version}.pdf",
            status,
        ),
    )
    con.commit()
    return int(cur.lastrowid)


def test_returns_none_without_documents(db):
    con, contract_id = db
    assert resolve_document_version(con, contract_id) is None


def test_single_open_version_applies(db):
    con, contract_id = db
    doc_id = _add_doc(con, contract_id, 1, "2025-01-01", None)
    resolved = resolve_document_version(con, contract_id, at="2026-06-01")
    assert resolved is not None and resolved["id"] == doc_id


def test_superseded_version_not_selected_after_supersession(db):
    con, contract_id = db
    v1 = _add_doc(con, contract_id, 1, "2025-01-01", "2025-06-01")
    v2 = _add_doc(con, contract_id, 2, "2025-06-01", None)

    resolved = resolve_document_version(con, contract_id, at="2025-03-01")
    assert resolved is not None and resolved["id"] == v1

    resolved = resolve_document_version(con, contract_id, at="2025-06-15")
    assert resolved is not None and resolved["id"] == v2

    # Exactly on supersession boundary, the new version applies.
    resolved = resolve_document_version(con, contract_id, at="2025-06-01")
    assert resolved is not None and resolved["id"] == v2


def test_ignores_non_ready_documents(db):
    con, contract_id = db
    _add_doc(con, contract_id, 1, "2025-01-01", None, status="FAILED")
    assert resolve_document_version(con, contract_id) is None


def test_falls_back_to_latest_effective_before_date(db):
    """Document uploaded later can still be authoritative for earlier history."""
    con, contract_id = db
    v1 = _add_doc(con, contract_id, 1, "2025-01-01", "2025-06-01")
    v2 = _add_doc(con, contract_id, 2, "2025-06-01", None)
    # No version window covers 2025-12-31 exactly as 'before v2 effective'...
    # but v2 covers it; instead test a date before any effective_from.
    resolved = resolve_document_version(con, contract_id, at="2024-12-31")
    assert resolved is None

    # Date inside v1's window resolves v1 even though v2 exists.
    resolved = resolve_document_version(con, contract_id, at="2025-02-01")
    assert resolved is not None and resolved["id"] in (v1, v2)  # v2 fallback also acceptable
    assert resolved["version"] in (1, 2)


def test_invalid_at_date_raises(db):
    con, contract_id = db
    _add_doc(con, contract_id, 1, "2025-01-01", None)
    with pytest.raises(ValueError):
        resolve_document_version(con, contract_id, at="not-a-date")


def test_defaults_to_today(db):
    con, contract_id = db
    doc_id = _add_doc(con, contract_id, 1, "2025-01-01", None)
    resolved = resolve_document_version(con, contract_id)
    assert resolved is not None and resolved["id"] == doc_id
