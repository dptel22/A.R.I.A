from __future__ import annotations

import importlib
import sqlite3
import sys
import shutil
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from db.connection import get_connection
from db.schema import init_db
from inference.pipeline import PipelineResult


API_KEY = "test-api-key"


class DummyModel:
    names = {
        0: "longitudinal_crack",
        1: "transverse_crack",
        2: "alligator_crack",
        3: "pothole",
    }

    def predict(self, **kwargs):  # pragma: no cover - detect tests use stubs instead
        return []


def _reload_app():
    for module_name in ("api.app", "api.routes", "api.dependencies"):
        sys.modules.pop(module_name, None)
    importlib.invalidate_caches()
    return importlib.import_module("api.app")


def _seed_base_data(db_path: Path) -> sqlite3.Row:
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
                ("Outer Ring Road Test Segment", "W-150", "East", 12.90, 12.96, 77.60, 77.70),
            )
            segment_id = int(con.execute("SELECT last_insert_rowid()").fetchone()[0])
            con.execute(
                """
                INSERT INTO contracts (
                    road_segment_id, contractor_name, contractor_email, dlp_end_date, contract_value
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (segment_id, "Legacy Infra", "legacy@infra.test", "2027-12-31", 1200.0),
            )
        contract_row = con.execute(
            "SELECT * FROM contracts WHERE road_segment_id = ? ORDER BY created_at DESC LIMIT 1",
            (segment_id,),
        ).fetchone()
        assert contract_row is not None
        return contract_row
    finally:
        con.close()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    unique_id = uuid.uuid4().hex
    base_dir = Path.cwd()
    db_path = base_dir / f"api-test-{unique_id}.db"
    upload_dir = base_dir / f"api-test-uploads-{unique_id}"
    upload_dir.mkdir(exist_ok=True)

    monkeypatch.setenv("ARIA_API_KEY", API_KEY)
    monkeypatch.setenv("ARIA_DB_PATH", str(db_path))
    monkeypatch.setenv("ARIA_UPLOAD_DIR", str(upload_dir))
    monkeypatch.setenv("ARIA_MODEL_PATH", str(base_dir / "missing-model.pt"))

    init_db(str(db_path))
    _seed_base_data(db_path)

    app_module = _reload_app()
    with TestClient(app_module.app) as test_client:
        yield test_client, db_path, app_module
    shutil.rmtree(upload_dir, ignore_errors=True)
    db_path.unlink(missing_ok=True)
    wal_path = db_path.with_suffix(".db-wal")
    shm_path = db_path.with_suffix(".db-shm")
    wal_path.unlink(missing_ok=True)
    shm_path.unlink(missing_ok=True)


def _auth_headers() -> dict[str, str]:
    return {"x-api-key": API_KEY}


def _load_inspection_rows(db_path: Path):
    con = get_connection(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        return con.execute(
            """
            SELECT *
            FROM inspection_events
            ORDER BY id ASC
            """
        ).fetchall()
    finally:
        con.close()


def _insert_inspection_with_detection(db_path: Path, *, contractor_name: str, contractor_email: str) -> int:
    con = get_connection(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        segment_id = int(con.execute("SELECT id FROM road_segments LIMIT 1").fetchone()[0])
        contract_id = int(con.execute("SELECT id FROM contracts WHERE road_segment_id = ? LIMIT 1", (segment_id,)).fetchone()[0])
        with con:
            cur = con.execute(
                """
                INSERT INTO inspection_events (
                    segment_id,
                    lat,
                    lng,
                    pipeline_status,
                    contract_id_snapshot,
                    contractor_name_snapshot,
                    contractor_email_snapshot,
                    dlp_end_date_snapshot,
                    is_dlp_active_snapshot
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    segment_id,
                    12.931,
                    77.645,
                    "SUCCEEDED",
                    contract_id,
                    contractor_name,
                    contractor_email,
                    "2027-12-31",
                    1,
                ),
            )
            inspection_id = int(cur.lastrowid)
            con.execute(
                """
                INSERT INTO detections (
                    inspection_event_id, class_name, confidence,
                    bbox_x, bbox_y, bbox_w, bbox_h, severity_score, severity_level
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (inspection_id, "pothole", 0.9, 0.5, 0.5, 0.25, 0.25, 8.0, "CRITICAL"),
            )
        return inspection_id
    finally:
        con.close()


def test_detect_invalid_image_logs_failed_inspection(client):
    test_client, db_path, _ = client
    test_client.app.state.model = DummyModel()

    response = test_client.post(
        "/api/v1/detect",
        headers=_auth_headers(),
        data={"lat": "12.931", "lng": "77.645"},
        files={"file": ("bad.png", b"not-an-image", "image/png")},
    )

    assert response.status_code == 422
    rows = _load_inspection_rows(db_path)
    assert len(rows) == 1
    assert rows[0]["pipeline_status"] == "FAILED"
    assert "decoded as a valid image" in rows[0]["failure_reason"]


def test_detect_zero_detections_logs_auditable_no_defect_event(client, monkeypatch):
    test_client, db_path, _ = client
    routes_module = sys.modules["api.routes"]
    test_client.app.state.model = DummyModel()
    monkeypatch.setattr(routes_module, "run_pipeline", lambda img_bytes, model: PipelineResult(status="NO_DETECTIONS", detections=[]))

    response = test_client.post(
        "/api/v1/detect",
        headers=_auth_headers(),
        data={"lat": "12.931", "lng": "77.645"},
        files={"file": ("good.png", _png_bytes(), "image/png")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["pipeline_status"] == "NO_DETECTIONS"
    rows = _load_inspection_rows(db_path)
    assert rows[0]["pipeline_status"] == "NO_DETECTIONS"


def test_detect_success_masks_response_and_snapshots_raw_contract(client, monkeypatch):
    test_client, db_path, _ = client
    routes_module = sys.modules["api.routes"]
    test_client.app.state.model = DummyModel()
    monkeypatch.setattr(
        routes_module,
        "run_pipeline",
        lambda img_bytes, model: PipelineResult(
            status="SUCCEEDED",
            detections=[
                {
                    "class_name": "pothole",
                    "confidence": 0.92,
                    "bbox_x": 0.5,
                    "bbox_y": 0.5,
                    "bbox_w": 0.2,
                    "bbox_h": 0.2,
                    "severity_score": 8.0,
                    "severity_level": "CRITICAL",
                }
            ],
        ),
    )

    response = test_client.post(
        "/api/v1/detect",
        headers=_auth_headers(),
        data={"lat": "12.931", "lng": "77.645"},
        files={"file": ("good.png", _png_bytes(), "image/png")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["contract"]["contractor_email"] == "l***@infra.test"

    rows = _load_inspection_rows(db_path)
    assert rows[0]["pipeline_status"] == "SUCCEEDED"
    assert rows[0]["contractor_email_snapshot"] == "legacy@infra.test"
    assert rows[0]["contractor_name_snapshot"] == "Legacy Infra"


def test_detections_reports_total_matching_separately_from_page_size(client):
    test_client, db_path, _ = client
    _insert_inspection_with_detection(db_path, contractor_name="Legacy Infra", contractor_email="legacy@infra.test")
    _insert_inspection_with_detection(db_path, contractor_name="Legacy Infra", contractor_email="legacy@infra.test")

    response = test_client.get("/api/v1/detections?limit=1&offset=0", headers=_auth_headers())

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_matching"] == 2
    assert payload["returned_count"] == 1


def test_detection_detail_uses_historical_snapshot_even_after_contract_changes(client):
    test_client, db_path, _ = client
    inspection_id = _insert_inspection_with_detection(
        db_path,
        contractor_name="Legacy Infra",
        contractor_email="legacy@infra.test",
    )

    con = get_connection(str(db_path))
    try:
        with con:
            con.execute(
                """
                INSERT INTO contracts (
                    road_segment_id, contractor_name, contractor_email, dlp_end_date, contract_value
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (1, "Replacement Infra", "replacement@infra.test", "2028-01-01", 2400.0),
            )
    finally:
        con.close()

    response = test_client.get(f"/api/v1/detections/{inspection_id}", headers=_auth_headers())

    assert response.status_code == 200
    payload = response.json()
    assert payload["contract"]["contractor_name"] == "Legacy Infra"
    assert payload["contract"]["contractor_email"] == "l***@infra.test"


def _png_bytes() -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT\x08\x99c``\x00\x00"
        b"\x00\x04\x00\x01\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
    )
