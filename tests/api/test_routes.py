from __future__ import annotations

import importlib
import sqlite3
import sys
import shutil
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aria.db.connection import get_connection
from aria.db.schema import init_db
from aria.inference.pipeline import PipelineResult


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
    for module_name in (
        "aria.api.app",
        "aria.api.dependencies",
        "aria.api.routes",
        "aria.api.routes.health",
        "aria.api.routes.inspections",
        "aria.api.routes.notices",
        "aria.services.inspection_service",
    ):
        sys.modules.pop(module_name, None)
    importlib.invalidate_caches()
    return importlib.import_module("aria.api.app")


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


def _cleanup_sqlite_files(db_path: Path) -> None:
    db_path.unlink(missing_ok=True)
    db_path.with_suffix(".db-wal").unlink(missing_ok=True)
    db_path.with_suffix(".db-shm").unlink(missing_ok=True)


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
    _cleanup_sqlite_files(db_path)


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


def _insert_legacy_inspection_with_detection(db_path: Path, *, pipeline_status: str) -> int:
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
                    pipeline_status,
                    contract_id,
                    "Legacy Infra",
                    "legacy@infra.test",
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
                (inspection_id, "pothole", 0.95, 0.5, 0.5, 0.25, 0.25, 8.0, "CRITICAL"),
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


def test_detect_with_missing_model_returns_503_and_logs_failed_inspection(client):
    test_client, db_path, _ = client

    response = test_client.post(
        "/api/v1/detect",
        headers=_auth_headers(),
        data={"lat": "12.931", "lng": "77.645"},
        files={"file": ("good.png", _png_bytes(), "image/png")},
    )

    assert response.status_code == 503
    rows = _load_inspection_rows(db_path)
    assert len(rows) == 1
    assert rows[0]["pipeline_status"] == "FAILED"
    assert rows[0]["failure_reason"] == "YOLO model not loaded."


def test_detect_rejects_unsupported_file_type_without_logging_inspection(client):
    test_client, db_path, _ = client

    response = test_client.post(
        "/api/v1/detect",
        headers=_auth_headers(),
        data={"lat": "12.931", "lng": "77.645"},
        files={"file": ("bad.txt", b"plain-text", "text/plain")},
    )

    assert response.status_code == 400
    assert _load_inspection_rows(db_path) == []


def test_detect_rejects_invalid_latitude_without_logging_inspection(client):
    test_client, db_path, _ = client

    response = test_client.post(
        "/api/v1/detect",
        headers=_auth_headers(),
        data={"lat": "120.0", "lng": "77.645"},
        files={"file": ("good.png", _png_bytes(), "image/png")},
    )

    assert response.status_code == 422
    assert _load_inspection_rows(db_path) == []


def test_detect_zero_detections_logs_auditable_no_defect_event(client, monkeypatch):
    test_client, db_path, _ = client
    routes_module = sys.modules["aria.services.inspection_service"]
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
    routes_module = sys.modules["aria.services.inspection_service"]
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
    assert payload["recommendation"] == "Block Payment"

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


def test_contracts_allow_repeat_awards_for_same_contractor_on_same_segment(client):
    _, db_path, _ = client
    con = get_connection(str(db_path))
    try:
        segment_id = int(con.execute("SELECT id FROM road_segments LIMIT 1").fetchone()[0])
        with con:
            con.execute(
                """
                INSERT INTO contracts (
                    road_segment_id,
                    contractor_name,
                    contractor_email,
                    dlp_end_date,
                    contract_value,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (segment_id, "Legacy Infra", "legacy@infra.test", "2028-01-01", 2400.0, "2028-01-01T00:00:00Z"),
            )
        count = int(
            con.execute(
                """
                SELECT COUNT(*)
                FROM contracts
                WHERE road_segment_id = ? AND contractor_name = ?
                """,
                (segment_id, "Legacy Infra"),
            ).fetchone()[0]
        )
    finally:
        con.close()

    assert count == 2


def test_init_db_migrates_legacy_contract_uniqueness_and_preserves_rows():
    unique_id = uuid.uuid4().hex
    db_path = Path.cwd() / f"legacy-contracts-{unique_id}.db"
    con = sqlite3.connect(str(db_path))
    try:
        with con:
            con.execute("PRAGMA foreign_keys = ON")
            con.execute(
                """
                CREATE TABLE road_segments (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    ward_id TEXT NOT NULL DEFAULT 'UNKNOWN',
                    zone_id TEXT NOT NULL DEFAULT 'UNKNOWN',
                    gps_min_lat REAL NOT NULL,
                    gps_max_lat REAL NOT NULL,
                    gps_min_lon REAL NOT NULL,
                    gps_max_lon REAL NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
                )
                """
            )
            con.execute(
                """
                CREATE TABLE contracts (
                    id INTEGER PRIMARY KEY,
                    road_segment_id INTEGER NOT NULL REFERENCES road_segments(id) ON DELETE CASCADE,
                    contractor_name TEXT NOT NULL,
                    contractor_email TEXT NOT NULL,
                    dlp_end_date TEXT NOT NULL,
                    contract_value REAL,
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                    UNIQUE (road_segment_id, contractor_name)
                )
                """
            )
            con.execute(
                """
                CREATE TABLE inspection_events (
                    id INTEGER PRIMARY KEY,
                    segment_id INTEGER NOT NULL REFERENCES road_segments(id) ON DELETE CASCADE,
                    lat REAL NOT NULL,
                    lng REAL NOT NULL,
                    contract_id_snapshot INTEGER REFERENCES contracts(id) ON DELETE SET NULL,
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
                )
                """
            )
            con.execute(
                """
                INSERT INTO road_segments (
                    id, name, ward_id, zone_id, gps_min_lat, gps_max_lat, gps_min_lon, gps_max_lon
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (1, "Legacy Segment", "W-001", "Test", 12.0, 13.0, 77.0, 78.0),
            )
            con.execute(
                """
                INSERT INTO contracts (
                    id, road_segment_id, contractor_name, contractor_email, dlp_end_date, contract_value, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (7, 1, "Repeat Builder", "repeat@infra.test", "2027-01-01", 5000.0, "2024-01-01T00:00:00Z"),
            )
            con.execute(
                """
                INSERT INTO inspection_events (segment_id, lat, lng, contract_id_snapshot)
                VALUES (?, ?, ?, ?)
                """,
                (1, 12.5, 77.5, 7),
            )
    finally:
        con.close()

    init_db(str(db_path))

    migrated = get_connection(str(db_path))
    migrated.row_factory = sqlite3.Row
    try:
        contract_row = migrated.execute(
            "SELECT * FROM contracts WHERE id = ?",
            (7,),
        ).fetchone()
        inspection_row = migrated.execute(
            "SELECT contract_id_snapshot, pipeline_status FROM inspection_events LIMIT 1"
        ).fetchone()
        with migrated:
            migrated.execute(
                """
                INSERT INTO contracts (
                    road_segment_id,
                    contractor_name,
                    contractor_email,
                    dlp_end_date,
                    contract_value,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (1, "Repeat Builder", "repeat-v2@infra.test", "2028-01-01", 7500.0, "2025-01-01T00:00:00Z"),
            )
        repeat_count = int(
            migrated.execute(
                """
                SELECT COUNT(*)
                FROM contracts
                WHERE road_segment_id = ? AND contractor_name = ?
                """,
                (1, "Repeat Builder"),
            ).fetchone()[0]
        )
    finally:
        migrated.close()
        _cleanup_sqlite_files(db_path)

    assert contract_row is not None
    assert contract_row["contractor_email"] == "repeat@infra.test"
    assert inspection_row is not None
    assert inspection_row["contract_id_snapshot"] == 7
    assert inspection_row["pipeline_status"] == "NO_DETECTIONS"
    assert repeat_count == 2


def test_find_contract_returns_latest_repeat_award(client):
    _, db_path, _ = client
    routes_module = sys.modules["aria.services.inspection_service"]
    con = get_connection(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        segment_id = int(con.execute("SELECT id FROM road_segments LIMIT 1").fetchone()[0])
        with con:
            con.execute(
                """
                INSERT INTO contracts (
                    road_segment_id,
                    contractor_name,
                    contractor_email,
                    dlp_end_date,
                    contract_value,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (segment_id, "Legacy Infra", "legacy-v2@infra.test", "2028-01-01", 2400.0, "2028-01-01T00:00:00Z"),
            )
        contract = routes_module._find_contract(con, segment_id)
    finally:
        con.close()

    assert contract is not None
    assert contract["contractor_email"] == "legacy-v2@infra.test"


def test_init_db_normalizes_legacy_seed_status_when_detections_exist(client):
    _, db_path, _ = client
    inspection_id = _insert_legacy_inspection_with_detection(db_path, pipeline_status="NO_DETECTIONS")

    init_db(str(db_path))

    con = get_connection(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            "SELECT pipeline_status FROM inspection_events WHERE id = ?",
            (inspection_id,),
        ).fetchone()
    finally:
        con.close()

    assert row is not None
    assert row["pipeline_status"] == "SUCCEEDED"


def test_detection_detail_hides_notice_for_non_succeeded_legacy_rows(client):
    test_client, db_path, _ = client
    inspection_id = _insert_legacy_inspection_with_detection(db_path, pipeline_status="FAILED")

    response = test_client.get(f"/api/v1/detections/{inspection_id}", headers=_auth_headers())

    assert response.status_code == 200
    payload = response.json()
    assert payload["pipeline_status"] == "FAILED"
    assert payload["total_detections"] == 0
    assert payload["detections"] == []
    assert payload["notice_url"] is None


@pytest.mark.parametrize(
    ("severity_level", "is_dlp_active", "pipeline_status", "expected"),
    [
        ("LOW", True, "SUCCEEDED", "No Action"),
        ("MEDIUM", True, "SUCCEEDED", "Issue Notice"),
        ("HIGH", True, "SUCCEEDED", "Issue Notice"),
        ("CRITICAL", True, "SUCCEEDED", "Block Payment"),
        ("CRITICAL", False, "SUCCEEDED", "No Action"),
        ("CRITICAL", True, "FAILED", "Escalate Manual Inspection"),
        ("CRITICAL", True, "NO_DETECTIONS", "No Action"),
        ("NONE", True, "SUCCEEDED", "No Action"),
    ],
)
def test_recommended_action_uses_shared_runtime_policy(client, severity_level, is_dlp_active, pipeline_status, expected):
    _, _, _ = client
    routes_module = sys.modules["aria.services.inspection_service"]

    assert routes_module._recommended_action(severity_level, is_dlp_active, pipeline_status) == expected


def test_list_and_detail_share_recommendation_for_same_inspection(client):
    test_client, db_path, _ = client
    inspection_id = _insert_inspection_with_detection(
        db_path,
        contractor_name="Legacy Infra",
        contractor_email="legacy@infra.test",
    )

    list_response = test_client.get("/api/v1/detections", headers=_auth_headers())
    detail_response = test_client.get(f"/api/v1/detections/{inspection_id}", headers=_auth_headers())

    assert list_response.status_code == 200
    assert detail_response.status_code == 200

    list_item = next(
        item for item in list_response.json()["results"]
        if item["inspection_id"] == inspection_id
    )
    detail_payload = detail_response.json()

    assert list_item["recommendation"] == "Block Payment"
    assert detail_payload["recommendation"] == "Block Payment"
    assert list_item["recommendation"] == detail_payload["recommendation"]


def _png_bytes() -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT\x08\x99c``\x00\x00"
        b"\x00\x04\x00\x01\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
    )
