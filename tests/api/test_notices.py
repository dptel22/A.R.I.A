"""Regression pins for GET /api/v1/notices/{inspection_id}.

Locks the current deterministic notice behaviour before any RAG work lands:
status codes, auth gating, eligibility rules, and the hard-coded legal text.
"""
from __future__ import annotations

import importlib
import sqlite3
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aria.db.connection import get_connection
from aria.db.schema import init_db


API_KEY = "test-api-key"


def _reload_app():
    for module_name in (
        "aria.api.app",
        "aria.api.dependencies",
        "aria.api.routes",
        "aria.api.routes.health",
        "aria.api.routes.inspections",
        "aria.api.routes.notices",
        "aria.services.inspection_service",
        "aria.services.notice_service",
    ):
        sys.modules.pop(module_name, None)
    importlib.invalidate_caches()
    return importlib.import_module("aria.api.app")


def _cleanup_sqlite_files(db_path: Path) -> None:
    db_path.unlink(missing_ok=True)
    db_path.with_suffix(".db-wal").unlink(missing_ok=True)
    db_path.with_suffix(".db-shm").unlink(missing_ok=True)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    unique_id = uuid.uuid4().hex
    base_dir = tmp_path
    db_path = base_dir / f"notice-test-{unique_id}.db"
    upload_dir = base_dir / f"notice-uploads-{unique_id}"
    upload_dir.mkdir(exist_ok=True)

    monkeypatch.setenv("ARIA_API_KEY", API_KEY)
    monkeypatch.setenv("ARIA_DB_PATH", str(db_path))
    monkeypatch.setenv("ARIA_UPLOAD_DIR", str(upload_dir))
    monkeypatch.setenv("ARIA_MODEL_PATH", str(base_dir / "missing-model.pt"))

    init_db(str(db_path))

    con = get_connection(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        with con:
            con.execute(
                """
                INSERT INTO road_segments (
                    name, ward_id, zone_id, gps_min_lat, gps_max_lat, gps_min_lon, gps_max_lon
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("Notice Test Segment", "W-150", "East", 12.90, 12.96, 77.60, 77.70),
            )
            segment_id = int(con.execute("SELECT last_insert_rowid()").fetchone()[0])
            con.execute(
                """
                INSERT INTO contracts (
                    road_segment_id, contractor_name, contractor_email, dlp_end_date, contract_value
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (segment_id, "Notice Infra Ltd", "ops@noticeinfra.test", "2027-12-31", 1500.0),
            )
            contract_id = int(con.execute("SELECT last_insert_rowid()").fetchone()[0])
            cur = con.execute(
                """
                INSERT INTO inspection_events (
                    segment_id, lat, lng, pipeline_status,
                    contract_id_snapshot, contractor_name_snapshot,
                    contractor_email_snapshot, dlp_end_date_snapshot,
                    is_dlp_active_snapshot
                ) VALUES (?, ?, ?, 'SUCCEEDED', ?, ?, ?, '2027-12-31', 1)
                """,
                (segment_id, 12.931, 77.645, contract_id, "Notice Infra Ltd", "ops@noticeinfra.test"),
            )
            inspection_id = int(cur.lastrowid)
            con.execute(
                """
                INSERT INTO detections (
                    inspection_event_id, class_name, confidence,
                    bbox_x, bbox_y, bbox_w, bbox_h, severity_score, severity_level
                ) VALUES (?, 'pothole', 0.9, 0.5, 0.5, 0.25, 0.25, 8.0, 'CRITICAL')
                """,
                (inspection_id,),
            )
    finally:
        con.close()

    app_module = _reload_app()
    with TestClient(app_module.app) as test_client:
        yield test_client, inspection_id
    _cleanup_sqlite_files(db_path)


def _auth_headers() -> dict[str, str]:
    return {"x-api-key": API_KEY}


def test_notice_requires_api_key(client):
    test_client, inspection_id = client
    assert test_client.get(f"/api/v1/notices/{inspection_id}").status_code == 401
    bad = test_client.get(
        f"/api/v1/notices/{inspection_id}", headers={"x-api-key": "wrong"}
    )
    assert bad.status_code == 403


def test_notice_unknown_inspection_is_404(client):
    test_client, _ = client
    response = test_client.get("/api/v1/notices/999999", headers=_auth_headers())
    assert response.status_code == 404


def test_notice_pdf_streams_with_pinned_content(client):
    test_client, inspection_id = client
    response = test_client.get(f"/api/v1/notices/{inspection_id}", headers=_auth_headers())

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")

    import fitz  # pymupdf

    with fitz.open(stream=response.content, filetype="pdf") as doc:
        text = "\n".join(page.get_text() for page in doc)

    # Hard-coded contractual/legal claims that must remain deterministic
    # (RAG must never silently alter these).
    assert "Clause 32.1" in text
    assert "48 hours" in text
    assert "7 days" in text
    assert "5% withheld security deposit" in text
    assert "blacklisting" in text
    # Snapshotted contract facts
    assert "Notice Infra Ltd" in text
    assert "ops@noticeinfra.test" in text
    assert "DLP End Date: 2027-12-31" in text
    # Authority framing
    assert "Greater Bengaluru Authority (GBA)" in text
    assert "Bengaluru South Corporation" in text
    assert "Digitally generated by A.R.I.A." in text


def test_notice_requires_enforceable_dlp_snapshot(client, monkeypatch, tmp_path):
    """An inspection without an enforceable DLP contract must not produce a PDF."""
    test_client, _ = client
    # Insert a no-contract inspection row and confirm 404.
    import aria.api.app as app_module  # noqa: F401  (ensures app module loaded)
    db_path = Path(__import__("os").environ["ARIA_DB_PATH"])
    con = get_connection(str(db_path))
    try:
        with con:
            cur = con.execute(
                "INSERT INTO inspection_events (segment_id, lat, lng, pipeline_status) "
                "VALUES ((SELECT id FROM road_segments LIMIT 1), 12.931, 77.645, 'SUCCEEDED')"
            )
            no_contract_id = int(cur.lastrowid)
    finally:
        con.close()

    response = test_client.get(f"/api/v1/notices/{no_contract_id}", headers=_auth_headers())
    assert response.status_code == 404
