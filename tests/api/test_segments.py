"""Tests for the Road Segments read endpoints."""
from __future__ import annotations

import importlib
import shutil
import sqlite3
import sys
import uuid
from datetime import date, timedelta
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
        "aria.api.routes.intake",
        "aria.api.routes.segments",
        "aria.services.inspection_service",
        "aria.services.intake_service",
        "aria.services.segments_service",
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
    db_path = base_dir / f"segments-test-{unique_id}.db"
    upload_dir = base_dir / f"segments-test-uploads-{unique_id}"
    upload_dir.mkdir(exist_ok=True)

    monkeypatch.setenv("ARIA_API_KEY", API_KEY)
    monkeypatch.setenv("ARIA_DB_PATH", str(db_path))
    monkeypatch.setenv("ARIA_UPLOAD_DIR", str(upload_dir))
    monkeypatch.setenv("ARIA_MODEL_PATH", str(base_dir / "missing-model.pt"))

    init_db(str(db_path))

    app_module = _reload_app()
    with TestClient(app_module.app) as test_client:
        yield test_client, db_path, app_module
    shutil.rmtree(upload_dir, ignore_errors=True)
    _cleanup_sqlite_files(db_path)


def _auth_headers() -> dict[str, str]:
    return {"x-api-key": API_KEY}


def _insert_segment(
    db_path: Path,
    *,
    name: str,
    lat: tuple[float, float] = (12.90, 12.96),
    lng: tuple[float, float] = (77.60, 77.70),
) -> int:
    con = get_connection(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        with con:
            cur = con.execute(
                """
                INSERT INTO road_segments (name, ward_id, zone_id, gps_min_lat, gps_max_lat, gps_min_lon, gps_max_lon)
                VALUES (?, 'W-300', 'East', ?, ?, ?, ?)
                """,
                (name, lat[0], lat[1], lng[0], lng[1]),
            )
            return int(cur.lastrowid)
    finally:
        con.close()


def _insert_contract(
    db_path: Path,
    *,
    segment_id: int,
    contractor_name: str,
    contractor_email: str,
    dlp_end_date: str,
) -> int:
    con = get_connection(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        with con:
            cur = con.execute(
                """
                INSERT INTO contracts (road_segment_id, contractor_name, contractor_email, dlp_end_date, contract_value)
                VALUES (?, ?, ?, ?, 500.0)
                """,
                (segment_id, contractor_name, contractor_email, dlp_end_date),
            )
            return int(cur.lastrowid)
    finally:
        con.close()


def _insert_linked_inspection(db_path: Path, *, segment_id: int) -> int:
    con = get_connection(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        with con:
            cur = con.execute(
                """
                INSERT INTO inspection_events (segment_id, source_type, lat, lng, pipeline_status)
                VALUES (?, 'manual_upload', 12.93, 77.62, 'SUCCEEDED')
                """,
                (segment_id,),
            )
            inspection_id = int(cur.lastrowid)
            con.execute(
                """
                INSERT INTO detections (inspection_event_id, class_name, confidence, bbox_x, bbox_y, bbox_w, bbox_h, severity_score, severity_level)
                VALUES (?, 'pothole', 0.9, 0.5, 0.5, 0.2, 0.2, 8.0, 'CRITICAL')
                """,
                (inspection_id,),
            )
        return inspection_id
    finally:
        con.close()


def _insert_no_segment_inspection(db_path: Path) -> int:
    con = get_connection(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        with con:
            cur = con.execute(
                """
                INSERT INTO inspection_events (segment_id, source_type, lat, lng, pipeline_status)
                VALUES (NULL, 'citizen_submission', 13.5, 78.2, 'SUCCEEDED')
                """,
            )
            return int(cur.lastrowid)
    finally:
        con.close()


# ---------------------------------------------------------------------------
# List tests
# ---------------------------------------------------------------------------

def test_segments_requires_api_key(client):
    test_client, _, _ = client
    assert test_client.get("/segments").status_code == 401


def test_segments_list_returns_bbox_active_contract_history_and_case_count(client):
    test_client, db_path, _ = client
    active_end = (date.today() + timedelta(days=365)).isoformat()
    expired_end = (date.today() - timedelta(days=1)).isoformat()

    active_segment = _insert_segment(db_path, name="Active Road")
    expired_segment = _insert_segment(db_path, name="Expired Road", lat=(13.0, 13.1), lng=(78.0, 78.1))
    _insert_contract(db_path, segment_id=active_segment, contractor_name="Active Infra", contractor_email="active@test.example", dlp_end_date=active_end)
    _insert_contract(db_path, segment_id=active_segment, contractor_name="Old Infra", contractor_email="old@test.example", dlp_end_date=expired_end)
    _insert_contract(db_path, segment_id=expired_segment, contractor_name="Expired Infra", contractor_email="expired@test.example", dlp_end_date=expired_end)
    _insert_linked_inspection(db_path, segment_id=active_segment)
    _insert_linked_inspection(db_path, segment_id=active_segment)

    response = test_client.get("/segments", headers=_auth_headers())
    assert response.status_code == 200
    segments = {s["name"]: s for s in response.json()}

    active = segments["Active Road"]
    assert active["bbox"] == {"min_lat": 12.90, "max_lat": 12.96, "min_lng": 77.60, "max_lng": 77.70}
    assert active["case_count"] == 2
    assert active["active_contract"] is not None
    assert active["active_contract"]["contractor_name"] == "Active Infra"
    assert active["active_contract"]["is_dlp_active"] is True
    assert len(active["contract_history"]) == 2
    # Newest first.
    assert active["contract_history"][0]["id"] > active["contract_history"][1]["id"]


def test_expired_only_segment_has_null_active_contract_but_history(client):
    test_client, db_path, _ = client
    expired_end = (date.today() - timedelta(days=1)).isoformat()
    segment_id = _insert_segment(db_path, name="Expired Only Road")
    _insert_contract(db_path, segment_id=segment_id, contractor_name="Gone Infra", contractor_email="gone@test.example", dlp_end_date=expired_end)

    segments = test_client.get("/segments", headers=_auth_headers()).json()
    segment = next(s for s in segments if s["name"] == "Expired Only Road")

    assert segment["active_contract"] is None
    assert len(segment["contract_history"]) == 1
    assert segment["contract_history"][0]["is_dlp_active"] is False


# ---------------------------------------------------------------------------
# Detail tests
# ---------------------------------------------------------------------------

def test_segment_detail_returns_partial_case_fields_only(client):
    test_client, db_path, _ = client
    segment_id = _insert_segment(db_path, name="Detail Road")
    inspection_id = _insert_linked_inspection(db_path, segment_id=segment_id)

    response = test_client.get(f"/segments/{segment_id}", headers=_auth_headers())
    assert response.status_code == 200
    payload = response.json()
    assert payload["segment"]["id"] == segment_id

    case = payload["cases"][0]
    # Partial fields only.
    assert case["inspection_id"] == inspection_id
    assert set(case.keys()) == {
        "id", "inspection_id", "road_segment", "severity", "status", "created",
        "recommendation", "image_url",
    }
    assert "detections" not in case


def test_segment_detail_unknown_returns_404(client):
    test_client, _, _ = client
    response = test_client.get("/segments/9999", headers=_auth_headers())
    assert response.status_code == 404


def test_no_segment_intake_case_does_not_appear_under_any_segment(client):
    test_client, db_path, _ = client
    segment_id = _insert_segment(db_path, name="Lonely Road")
    _insert_no_segment_inspection(db_path)

    segments = test_client.get("/segments", headers=_auth_headers()).json()
    lonely = next(s for s in segments if s["name"] == "Lonely Road")
    assert lonely["case_count"] == 0

    detail = test_client.get(f"/segments/{segment_id}", headers=_auth_headers()).json()
    assert detail["cases"] == []
