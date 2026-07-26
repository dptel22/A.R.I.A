"""Tests for the Intake clustering, promotion, dismissal, and schema migration."""
from __future__ import annotations

import importlib
import os
import shutil
import sqlite3
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aria.db.connection import get_connection
from aria.db.schema import init_db
from aria.inference.pipeline import PipelineResult


API_KEY = "test-api-key"

# 12.93, 77.62 is inside the seeded segment (12.90-12.96 lat, 77.60-77.70 lng).
_SEGMENT_LAT = 12.93
_SEGMENT_LNG = 77.62
# ~5 m north of the segment centroid — still within the 10 m cluster threshold but
# outside the segment bbox, so it yields zero segment matches.
_NO_MATCH_LAT = 13.50
_NO_MATCH_LNG = 78.20


class _Png:
    """Small distinct PNG byte payloads so per-submission inference results differ."""

    LOW = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT\x08\x99c``\x00\x00"
        b"\x00\x04\x00\x01\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    HIGH = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x02\x00\x00\x00\x02"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT\x08\x99c``\x00\x00"
        b"\x00\x04\x00\x01\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
    )


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
    db_path = base_dir / f"intake-test-{unique_id}.db"
    upload_dir = base_dir / f"intake-test-uploads-{unique_id}"
    upload_dir.mkdir(exist_ok=True)

    monkeypatch.setenv("ARIA_API_KEY", API_KEY)
    monkeypatch.setenv("ARIA_DB_PATH", str(db_path))
    monkeypatch.setenv("ARIA_UPLOAD_DIR", str(upload_dir))
    monkeypatch.setenv("ARIA_MODEL_PATH", str(base_dir / "missing-model.pt"))

    init_db(str(db_path))
    _seed_base_segment(db_path)

    app_module = _reload_app()
    with TestClient(app_module.app) as test_client:
        yield test_client, db_path, upload_dir, app_module
    shutil.rmtree(upload_dir, ignore_errors=True)
    _cleanup_sqlite_files(db_path)


def _seed_base_segment(db_path: Path) -> None:
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
                ("Intake Test Segment", "W-200", "North", 12.90, 12.96, 77.60, 77.70),
            )
            segment_id = int(con.execute("SELECT last_insert_rowid()").fetchone()[0])
            con.execute(
                """
                INSERT INTO contracts (
                    road_segment_id, contractor_name, contractor_email, dlp_end_date, contract_value
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (segment_id, "Test Infra", "infra@test.example", "2027-12-31", 1000.0),
            )
    finally:
        con.close()


def _auth_headers() -> dict[str, str]:
    return {"x-api-key": API_KEY}


def _seed_submission(
    db_path: Path,
    upload_dir: Path,
    *,
    lat: float,
    lng: float,
    source_type: str,
    image_bytes: bytes,
    submitted_at: str | None = None,
    batch_id: int | None = None,
) -> int:
    """Insert a raw submission whose image_url points at a real file in upload_dir."""
    con = get_connection(str(db_path))
    con.row_factory = sqlite3.Row
    fname = f"sub_{uuid.uuid4().hex}.png"
    (upload_dir / fname).write_bytes(image_bytes)
    try:
        with con:
            if batch_id is None:
                cur = con.execute(
                    "INSERT INTO submission_batches (source_type) VALUES (?)",
                    (source_type,),
                )
                batch_id = int(cur.lastrowid)
            cur = con.execute(
                """
                INSERT INTO raw_submissions (
                    batch_id, image_url, lat, lng, status, submitted_at
                ) VALUES (?, ?, ?, ?, 'unreviewed', COALESCE(?, strftime('%Y-%m-%dT%H:%M:%SZ', 'now')))
                """,
                (batch_id, f"/uploads/{fname}", lat, lng, submitted_at),
            )
            return int(cur.lastrowid)
    finally:
        con.close()


def _pipeline_for(image_bytes: bytes) -> PipelineResult:
    """Map distinct image bytes to a deterministic pipeline outcome for monkeypatching."""
    if image_bytes == _Png.LOW:
        detection = {
            "class_name": "longitudinal_crack",
            "confidence": 0.7,
            "bbox_x": 0.4, "bbox_y": 0.4, "bbox_w": 0.2, "bbox_h": 0.2,
            "severity_score": 3.0, "severity_level": "LOW",
        }
    elif image_bytes == _Png.HIGH:
        detection = {
            "class_name": "pothole",
            "confidence": 0.92,
            "bbox_x": 0.5, "bbox_y": 0.5, "bbox_w": 0.25, "bbox_h": 0.25,
            "severity_score": 8.0, "severity_level": "CRITICAL",
        }
    else:
        return PipelineResult(status="NO_DETECTIONS", detections=[])
    return PipelineResult(status="SUCCEEDED", detections=[detection])


def _patch_pipeline(monkeypatch: pytest.MonkeyPatch, severity_lookup=None) -> None:
    """Monkeypatch run_pipeline in intake_service to return results keyed off image bytes.

    We obtain intake_service through the route module rather than via importlib, because
    _reload_app pops aria.services.intake_service from sys.modules but NOT aria.services
    (a namespace package). The freshly-reimported route module therefore gets the OLD cached
    module object from the namespace package attribute, while importlib.import_module would
    create a new one — a mismatch. Going through the route guarantees we patch the exact
    object the promote endpoint calls.
    """
    lookup = severity_lookup or _pipeline_for
    route_module = sys.modules["aria.api.routes.intake"]
    intake_module = route_module.intake_service  # same object the route's functions call into
    monkeypatch.setattr(intake_module, "run_pipeline", lambda img_bytes, model: lookup(img_bytes))


def _raw_submission_rows(db_path: Path, *, where: str = "") -> list[sqlite3.Row]:
    con = get_connection(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        return con.execute(
            f"SELECT * FROM raw_submissions {where} ORDER BY id ASC"
        ).fetchall()
    finally:
        con.close()


def _inspection_rows(db_path: Path) -> list[sqlite3.Row]:
    con = get_connection(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        return con.execute("SELECT * FROM inspection_events ORDER BY id ASC").fetchall()
    finally:
        con.close()


def _detection_rows(db_path: Path, inspection_id: int) -> list[sqlite3.Row]:
    con = get_connection(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        return con.execute(
            "SELECT * FROM detections WHERE inspection_event_id = ?",
            (inspection_id,),
        ).fetchall()
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Schema / migration tests
# ---------------------------------------------------------------------------

def test_init_db_creates_intake_tables(client):
    _, db_path, _, _ = client
    con = get_connection(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        tables = {
            row["name"]
            for row in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        }
    finally:
        con.close()
    assert "submission_batches" in tables
    assert "raw_submissions" in tables


def test_inspection_events_has_source_type_and_nullable_segment_id(client):
    _, db_path, _, _ = client
    con = get_connection(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        cols = {row["name"] for row in con.execute("PRAGMA table_info(inspection_events)").fetchall()}
        # raw_submission_id must NOT exist (per plan Non-Goals).
        assert "source_type" in cols
        assert "raw_submission_id" not in cols

        with con:
            cur = con.execute(
                """
                    INSERT INTO inspection_events (segment_id, source_type, lat, lng)
                    VALUES (NULL, 'manual_upload', 1.0, 2.0)
                """
            )
            row = con.execute(
                "SELECT segment_id, source_type FROM inspection_events WHERE id = ?",
                (cur.lastrowid,),
            ).fetchone()
    finally:
        con.close()
    assert row["segment_id"] is None
    assert row["source_type"] == "manual_upload"


def test_init_db_migrates_legacy_inspection_events_to_nullable_segment(tmp_path: Path):
    unique_id = uuid.uuid4().hex
    db_path = tmp_path / f"intake-legacy-{unique_id}.db"
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
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
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
                    pipeline_status TEXT,
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
                )
                """
            )
            con.execute(
                "INSERT INTO road_segments (id, name, gps_min_lat, gps_max_lat, gps_min_lon, gps_max_lon) VALUES (1, 'Legacy', 12.0, 13.0, 77.0, 78.0)"
            )
            con.execute(
                "INSERT INTO inspection_events (segment_id, lat, lng) VALUES (1, 12.5, 77.5)"
            )
    finally:
        con.close()

    init_db(str(db_path))

    migrated = get_connection(str(db_path))
    migrated.row_factory = sqlite3.Row
    try:
        cols = {row["name"] for row in migrated.execute("PRAGMA table_info(inspection_events)").fetchall()}
        row = migrated.execute("SELECT * FROM inspection_events WHERE id = 1").fetchone()
    finally:
        migrated.close()
        _cleanup_sqlite_files(db_path)

    assert row is not None
    assert row["lat"] == 12.5
    assert "source_type" in cols
    assert row["source_type"] == "manual_upload"


# ---------------------------------------------------------------------------
# Auth tests
# ---------------------------------------------------------------------------

def test_intake_clusters_requires_api_key(client):
    test_client, _, _, _ = client
    assert test_client.get("/intake/clusters").status_code == 401


def test_intake_clusters_rejects_invalid_api_key(client):
    test_client, _, _, _ = client
    response = test_client.get("/intake/clusters", headers={"x-api-key": "wrong"})
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Clustering tests
# ---------------------------------------------------------------------------

def test_clusters_group_nearby_submissions_and_split_distant_ones(client, monkeypatch):
    test_client, db_path, upload_dir, _ = client
    # Two close (within 10 m) + one far.
    _seed_submission(db_path, upload_dir, lat=12.93000, lng=77.62000, source_type="citizen_submission", image_bytes=_Png.LOW)
    _seed_submission(db_path, upload_dir, lat=12.93002, lng=77.62002, source_type="citizen_submission", image_bytes=_Png.LOW)
    _seed_submission(db_path, upload_dir, lat=13.50000, lng=78.20000, source_type="roadcam_survey", image_bytes=_Png.LOW)

    response = test_client.get("/intake/clusters", headers=_auth_headers())

    assert response.status_code == 200
    clusters = response.json()
    assert len(clusters) == 2
    # Deterministic ordinal ids starting at 1.
    assert {c["id"] for c in clusters} == {1, 2}
    close = next(c for c in clusters if c["submission_count"] == 2)
    far = next(c for c in clusters if c["submission_count"] == 1)
    assert close["source_types"] == ["citizen_submission"]
    assert far["source_types"] == ["roadcam_survey"]


def test_cluster_detail_returns_one_cluster(client):
    test_client, db_path, upload_dir, _ = client
    _seed_submission(db_path, upload_dir, lat=_SEGMENT_LAT, lng=_SEGMENT_LNG, source_type="citizen_submission", image_bytes=_Png.LOW)

    clusters = test_client.get("/intake/clusters", headers=_auth_headers()).json()
    cluster_id = clusters[0]["id"]

    detail = test_client.get(f"/intake/clusters/{cluster_id}", headers=_auth_headers())
    assert detail.status_code == 200
    assert detail.json()["id"] == cluster_id


def test_cluster_detail_404_after_promotion(client, monkeypatch):
    test_client, db_path, upload_dir, _ = client
    _seed_submission(db_path, upload_dir, lat=_SEGMENT_LAT, lng=_SEGMENT_LNG, source_type="citizen_submission", image_bytes=_Png.HIGH)
    test_client.app.state.model = object()  # non-None so the stub pipeline is used
    _patch_pipeline(monkeypatch)

    clusters = test_client.get("/intake/clusters", headers=_auth_headers()).json()
    cluster_id = clusters[0]["id"]
    promote = test_client.post(
        f"/intake/clusters/{cluster_id}/promote",
        headers={**_auth_headers(), "Content-Type": "application/json"},
        json={"segment_id": None},
    )
    assert promote.status_code == 200

    detail = test_client.get(f"/intake/clusters/{cluster_id}", headers=_auth_headers())
    assert detail.status_code == 404


# ---------------------------------------------------------------------------
# Dismiss tests
# ---------------------------------------------------------------------------

def test_dismiss_persists_status_and_reason(client):
    test_client, db_path, upload_dir, _ = client
    _seed_submission(db_path, upload_dir, lat=_SEGMENT_LAT, lng=_SEGMENT_LNG, source_type="citizen_submission", image_bytes=_Png.LOW)
    cluster_id = test_client.get("/intake/clusters", headers=_auth_headers()).json()[0]["id"]

    response = test_client.post(
        f"/intake/clusters/{cluster_id}/dismiss",
        headers={**_auth_headers(), "Content-Type": "application/json"},
        json={"reason": "not_a_road_defect"},
    )
    assert response.status_code == 200

    rows = _raw_submission_rows(db_path, where="WHERE status = 'dismissed'")
    assert len(rows) == 1
    assert rows[0]["dismiss_reason"] == "not_a_road_defect"


def test_dismiss_rejects_invalid_reason(client):
    test_client, db_path, upload_dir, _ = client
    _seed_submission(db_path, upload_dir, lat=_SEGMENT_LAT, lng=_SEGMENT_LNG, source_type="citizen_submission", image_bytes=_Png.LOW)
    cluster_id = test_client.get("/intake/clusters", headers=_auth_headers()).json()[0]["id"]

    response = test_client.post(
        f"/intake/clusters/{cluster_id}/dismiss",
        headers={**_auth_headers(), "Content-Type": "application/json"},
        json={"reason": "bogus"},
    )
    assert response.status_code == 422


def test_dismissed_endpoint_returns_persisted_data(client):
    test_client, db_path, upload_dir, _ = client
    _seed_submission(db_path, upload_dir, lat=_SEGMENT_LAT, lng=_SEGMENT_LNG, source_type="citizen_submission", image_bytes=_Png.LOW)
    cluster_id = test_client.get("/intake/clusters", headers=_auth_headers()).json()[0]["id"]

    test_client.post(
        f"/intake/clusters/{cluster_id}/dismiss",
        headers={**_auth_headers(), "Content-Type": "application/json"},
        json={"reason": "spam"},
    )

    # Dismissed persists across a fresh fetch (no in-memory only state).
    dismissed = test_client.get("/intake/dismissed", headers=_auth_headers()).json()
    assert len(dismissed) == 1
    assert dismissed[0]["reason"] == "spam"
    assert dismissed[0]["cluster"]["submission_count"] == 1


# ---------------------------------------------------------------------------
# Promotion tests
# ---------------------------------------------------------------------------

def test_promote_twice_second_call_fails_without_duplicate_events(client, monkeypatch):
    test_client, db_path, upload_dir, _ = client
    _seed_submission(db_path, upload_dir, lat=_SEGMENT_LAT, lng=_SEGMENT_LNG, source_type="citizen_submission", image_bytes=_Png.HIGH)
    test_client.app.state.model = object()
    _patch_pipeline(monkeypatch)

    cluster_id = test_client.get("/intake/clusters", headers=_auth_headers()).json()[0]["id"]
    first = test_client.post(
        f"/intake/clusters/{cluster_id}/promote",
        headers={**_auth_headers(), "Content-Type": "application/json"},
        json={"segment_id": None},
    )
    assert first.status_code == 200

    second = test_client.post(
        f"/intake/clusters/{cluster_id}/promote",
        headers={**_auth_headers(), "Content-Type": "application/json"},
        json={"segment_id": None},
    )
    assert second.status_code == 404
    assert len(_inspection_rows(db_path)) == 1


def test_promote_rejects_non_matching_segment_id(client, monkeypatch):
    test_client, db_path, upload_dir, _ = client
    _seed_submission(db_path, upload_dir, lat=_SEGMENT_LAT, lng=_SEGMENT_LNG, source_type="citizen_submission", image_bytes=_Png.HIGH)
    test_client.app.state.model = object()
    _patch_pipeline(monkeypatch)

    cluster_id = test_client.get("/intake/clusters", headers=_auth_headers()).json()[0]["id"]
    # segment_id 9999 exists in neither the cluster matches nor the DB.
    response = test_client.post(
        f"/intake/clusters/{cluster_id}/promote",
        headers={**_auth_headers(), "Content-Type": "application/json"},
        json={"segment_id": 9999},
    )
    assert response.status_code == 400
    assert _inspection_rows(db_path) == []


def test_promote_zero_matches_creates_no_segment_event(client, monkeypatch):
    test_client, db_path, upload_dir, _ = client
    _seed_submission(db_path, upload_dir, lat=_NO_MATCH_LAT, lng=_NO_MATCH_LNG, source_type="citizen_submission", image_bytes=_Png.HIGH)
    test_client.app.state.model = object()
    _patch_pipeline(monkeypatch)

    clusters = test_client.get("/intake/clusters", headers=_auth_headers()).json()
    assert clusters[0]["segment_matches"] == []
    cluster_id = clusters[0]["id"]

    response = test_client.post(
        f"/intake/clusters/{cluster_id}/promote",
        headers={**_auth_headers(), "Content-Type": "application/json"},
        json={"segment_id": None},
    )
    assert response.status_code == 200

    rows = _inspection_rows(db_path)
    assert len(rows) == 1
    assert rows[0]["segment_id"] is None
    assert rows[0]["source_type"] == "citizen_submission"
    promoted = _raw_submission_rows(db_path, where="WHERE status = 'promoted'")
    assert len(promoted) == 1
    assert promoted[0]["promoted_inspection_id"] == rows[0]["id"]


def test_promote_multiple_submissions_creates_single_event(client, monkeypatch):
    test_client, db_path, upload_dir, _ = client
    _seed_submission(db_path, upload_dir, lat=12.93000, lng=77.62000, source_type="citizen_submission", image_bytes=_Png.LOW, submitted_at="2026-01-01T00:00:00Z")
    _seed_submission(db_path, upload_dir, lat=12.93002, lng=77.62002, source_type="roadcam_survey", image_bytes=_Png.HIGH, submitted_at="2026-01-02T00:00:00Z")
    test_client.app.state.model = object()
    _patch_pipeline(monkeypatch)

    clusters = test_client.get("/intake/clusters", headers=_auth_headers()).json()
    cluster_id = clusters[0]["id"]

    response = test_client.post(
        f"/intake/clusters/{cluster_id}/promote",
        headers={**_auth_headers(), "Content-Type": "application/json"},
        json={"segment_id": None},
    )
    assert response.status_code == 200
    inspection_id = response.json()["inspection_id"]

    # Exactly one inspection event; both submissions point at it.
    rows = _inspection_rows(db_path)
    assert len(rows) == 1
    assert rows[0]["id"] == inspection_id
    promoted = _raw_submission_rows(db_path, where="WHERE status = 'promoted'")
    assert len(promoted) == 2
    assert {row["promoted_inspection_id"] for row in promoted} == {inspection_id}
    # Mixed sources resolve to citizen_submission (priority).
    assert rows[0]["source_type"] == "citizen_submission"


def test_promote_stores_winning_submission_detections(client, monkeypatch):
    test_client, db_path, upload_dir, _ = client
    # LOW severity submitted first, CRITICAL severity second — CRITICAL must win.
    _seed_submission(db_path, upload_dir, lat=12.93000, lng=77.62000, source_type="citizen_submission", image_bytes=_Png.LOW, submitted_at="2026-01-01T00:00:00Z")
    _seed_submission(db_path, upload_dir, lat=12.93002, lng=77.62002, source_type="citizen_submission", image_bytes=_Png.HIGH, submitted_at="2026-01-02T00:00:00Z")
    test_client.app.state.model = object()
    _patch_pipeline(monkeypatch)

    cluster_id = test_client.get("/intake/clusters", headers=_auth_headers()).json()[0]["id"]
    response = test_client.post(
        f"/intake/clusters/{cluster_id}/promote",
        headers={**_auth_headers(), "Content-Type": "application/json"},
        json={"segment_id": None},
    )
    assert response.status_code == 200
    inspection_id = response.json()["inspection_id"]

    detections = _detection_rows(db_path, inspection_id)
    assert len(detections) == 1
    # Winning result is the CRITICAL pothole, not the LOW crack.
    assert detections[0]["severity_level"] == "CRITICAL"
    assert detections[0]["class_name"] == "pothole"


def test_no_segment_intake_case_has_no_notice_url(client, monkeypatch):
    test_client, db_path, upload_dir, _ = client
    _seed_submission(db_path, upload_dir, lat=_NO_MATCH_LAT, lng=_NO_MATCH_LNG, source_type="citizen_submission", image_bytes=_Png.HIGH)
    test_client.app.state.model = object()
    _patch_pipeline(monkeypatch)

    cluster_id = test_client.get("/intake/clusters", headers=_auth_headers()).json()[0]["id"]
    promote = test_client.post(
        f"/intake/clusters/{cluster_id}/promote",
        headers={**_auth_headers(), "Content-Type": "application/json"},
        json={"segment_id": None},
    )
    inspection_id = promote.json()["inspection_id"]

    detail = test_client.get(f"/api/v1/detections/{inspection_id}", headers=_auth_headers()).json()
    assert detail["notice_url"] is None
    notice = test_client.get(f"/api/v1/notices/{inspection_id}", headers=_auth_headers())
    assert notice.status_code == 404
