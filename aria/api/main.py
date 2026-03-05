"""
api/main.py — A.R.I.A. FastAPI REST API
All endpoints for receiving detections, reviewing notices, and serving road segment data.
"""

from core.notice_generator import generate_notice
from core.contract_lookup import lookup_contract
from core.severity import compute_severity
import sys
import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

# ─────────────────────────────────────────────────────────────
# Configuration — defined once, never hardcoded elsewhere
# ─────────────────────────────────────────────────────────────
DB_PATH = "db/aria.db"
NOTICES_DIR = "notices"

# ─────────────────────────────────────────────────────────────
# Local imports — core modules
# ─────────────────────────────────────────────────────────────

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ─────────────────────────────────────────────────────────────
# FastAPI application
# ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="A.R.I.A. — Autonomous Road Infrastructure Auditor",
    description="Backend API for road defect enforcement. Integrated with BBMP road segments and DLP contracts.",
    version="1.0.0",
)

# ─────────────────────────────────────────────────────────────
# CORS Middleware — allows the dashboard to call the API
# ─────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(NOTICES_DIR, exist_ok=True)


# ─────────────────────────────────────────────────────────────
# Request / Response Models
# ─────────────────────────────────────────────────────────────

class DetectionInput(BaseModel):
    """Payload sent by the YOLO pipeline for a new road_damage detection."""

    gps_lat: float
    gps_lon: float
    confidence: float
    bbox: list[float]          # [x1, y1, x2, y2]
    frame_width: int
    frame_height: int
    frame_path: Optional[str] = None
    timestamp: Optional[str] = None


class ApproveInput(BaseModel):
    """Optional body for the approve endpoint — identifies the reviewing engineer."""

    approved_by: Optional[str] = "engineer"


# ─────────────────────────────────────────────────────────────
# Helper utilities
# ─────────────────────────────────────────────────────────────

def _get_conn() -> sqlite3.Connection:
    """
    Open a SQLite connection with Row factory enabled.

    Returns:
        sqlite3.Connection configured to return sqlite3.Row objects.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row to a plain Python dict."""
    return dict(row)


def _now_iso() -> str:
    """Return the current UTC timestamp as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────────────────────────────────────────
# Health Check
# ─────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
def health_check():
    """
    Health check endpoint.

    Returns:
        JSON with status, version, and current UTC timestamp.
    """
    return {
        "status": "ok",
        "service": "A.R.I.A. Backend",
        "version": "1.0.0",
        "timestamp": _now_iso(),
    }


# ─────────────────────────────────────────────────────────────
# Road Segments
# ─────────────────────────────────────────────────────────────

@app.get("/segments", tags=["Segments"])
def list_segments():
    """
    List all road segments in the database.

    Returns:
        JSON list of road_segments records.
    """
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM road_segments").fetchall()
    return [_row_to_dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────
# Detections
# ─────────────────────────────────────────────────────────────

@app.post("/detections", status_code=201, tags=["Detections"])
def create_detection(payload: DetectionInput):
    """
    Receive a road_damage detection from the YOLO pipeline.

    Automatically:
      1. Computes severity from the bounding box.
      2. Resolves GPS coordinates to a road segment and contract.
      3. Inserts the detection record into the database.

    Args:
        payload (DetectionInput): Detection data from the YOLO pipeline.

    Returns:
        JSON with the new detection_id, severity, contract match, and full record.
    """
    detection_id = str(uuid4())
    timestamp = payload.timestamp or _now_iso()

    # Step 1: Severity
    severity_result = compute_severity(
        payload.bbox, payload.frame_width, payload.frame_height)

    # Step 2: Contract lookup
    contract = lookup_contract(payload.gps_lat, payload.gps_lon, DB_PATH)
    segment_id = contract["segment_id"] if contract else None
    contract_id = contract["contract_id"] if contract else None
    within_dlp = 1 if (contract and contract["within_dlp"]) else 0

    bbox_json = json.dumps(payload.bbox)

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO detections
                (detection_id, segment_id, contract_id, timestamp, gps_lat, gps_lon,
                 severity, confidence, bbox_json, frame_path, within_dlp, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING')
            """,
            (
                detection_id,
                segment_id,
                contract_id,
                timestamp,
                payload.gps_lat,
                payload.gps_lon,
                severity_result["severity"],
                payload.confidence,
                bbox_json,
                payload.frame_path,
                within_dlp,
            ),
        )
        conn.commit()

    return {
        "detection_id": detection_id,
        "severity": severity_result,
        "contract": contract,
        "status": "PENDING",
        "timestamp": timestamp,
    }


@app.get("/detections", tags=["Detections"])
def list_detections(
    status: Optional[str] = Query(
        None, description="Filter by status: PENDING / APPROVED / REJECTED"),
    severity: Optional[str] = Query(
        None, description="Filter by severity: LOW / MEDIUM / HIGH"),
):
    """
    List all detections, with optional filters.

    Args:
        status (str, optional): Filter detections by their review status.
        severity (str, optional): Filter by severity classification.

    Returns:
        JSON list of detection records.
    """
    query = "SELECT * FROM detections WHERE 1=1"
    params: list = []

    if status:
        query += " AND status = ?"
        params.append(status.upper())
    if severity:
        query += " AND severity = ?"
        params.append(severity.upper())

    query += " ORDER BY timestamp DESC"

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, params).fetchall()

    return [_row_to_dict(r) for r in rows]


@app.get("/detections/{detection_id}", tags=["Detections"])
def get_detection(detection_id: str):
    """
    Retrieve a single detection record by ID.

    Args:
        detection_id (str): UUID of the detection.

    Returns:
        JSON detection record.

    Raises:
        HTTPException 404: If the detection is not found.
    """
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM detections WHERE detection_id = ?", (detection_id,)
        ).fetchone()

    if not row:
        raise HTTPException(
            status_code=404, detail=f"Detection '{detection_id}' not found.")

    return _row_to_dict(row)


@app.post("/detections/{detection_id}/approve", tags=["Detections"])
def approve_detection(detection_id: str, body: ApproveInput = ApproveInput()):
    """
    Engineer approves a detection — generates a PDF enforcement notice.

    Steps:
      1. Validates the detection exists and is PENDING.
      2. Updates detection status to APPROVED.
      3. Fetches the associated contract.
      4. Generates a PDF notice via notice_generator.
      5. Inserts a notices record.

    Args:
        detection_id (str): UUID of the detection to approve.
        body (ApproveInput): Optional engineer name.

    Returns:
        JSON with notice_id, pdf_path, and status.

    Raises:
        HTTPException 404: Detection not found.
        HTTPException 409: Detection already processed.
    """
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        detection = conn.execute(
            "SELECT * FROM detections WHERE detection_id = ?", (detection_id,)
        ).fetchone()

        if not detection:
            raise HTTPException(
                status_code=404, detail=f"Detection '{detection_id}' not found.")

        detection = _row_to_dict(detection)

        if detection["status"] != "PENDING":
            raise HTTPException(
                status_code=409,
                detail=f"Detection is already '{detection['status']}'. Cannot approve.",
            )

        # Fetch contract info for the notice
        contract_info: dict = {}
        if detection.get("contract_id"):
            row = conn.execute(
                """
                SELECT c.*, s.segment_name
                FROM contracts c
                JOIN road_segments s ON c.segment_id = s.segment_id
                WHERE c.contract_id = ?
                """,
                (detection["contract_id"],),
            ).fetchone()
            if row:
                contract_info = _row_to_dict(row)
                from datetime import date
                dlp_end = date.fromisoformat(contract_info["dlp_end_date"])
                days_remaining = (dlp_end - date.today()).days
                contract_info["within_dlp"] = days_remaining > 0
                contract_info["days_remaining"] = days_remaining

        # Generate PDF
        notice_id = str(uuid4())
        pdf_path = os.path.join(NOTICES_DIR, f"{notice_id}.pdf")

        detection["notice_id"] = notice_id
        generate_notice(detection, contract_info, pdf_path)

        now = _now_iso()

        # Update detection status
        conn.execute(
            "UPDATE detections SET status = 'APPROVED' WHERE detection_id = ?",
            (detection_id,),
        )

        # Insert notice record
        conn.execute(
            """
            INSERT INTO notices
                (notice_id, detection_id, contract_id, generated_at, pdf_path,
                 approved_by, approved_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'DRAFT')
            """,
            (
                notice_id,
                detection_id,
                detection.get("contract_id"),
                now,
                pdf_path,
                body.approved_by,
                now,
            ),
        )
        conn.commit()

    return {
        "notice_id": notice_id,
        "detection_id": detection_id,
        "pdf_path": pdf_path,
        "status": "DRAFT",
        "approved_by": body.approved_by,
        "approved_at": now,
    }


@app.post("/detections/{detection_id}/reject", tags=["Detections"])
def reject_detection(detection_id: str):
    """
    Engineer rejects a detection — marks it as REJECTED.

    Args:
        detection_id (str): UUID of the detection to reject.

    Returns:
        JSON with the updated status.

    Raises:
        HTTPException 404: Detection not found.
        HTTPException 409: Detection already processed.
    """
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        detection = conn.execute(
            "SELECT * FROM detections WHERE detection_id = ?", (detection_id,)
        ).fetchone()

        if not detection:
            raise HTTPException(
                status_code=404, detail=f"Detection '{detection_id}' not found.")

        detection = _row_to_dict(detection)

        if detection["status"] != "PENDING":
            raise HTTPException(
                status_code=409,
                detail=f"Detection is already '{detection['status']}'. Cannot reject.",
            )

        conn.execute(
            "UPDATE detections SET status = 'REJECTED' WHERE detection_id = ?",
            (detection_id,),
        )
        conn.commit()

    return {
        "detection_id": detection_id,
        "status": "REJECTED",
        "message": "Detection has been rejected. No enforcement notice will be generated.",
    }


# ─────────────────────────────────────────────────────────────
# Notices
# ─────────────────────────────────────────────────────────────

@app.get("/notices", tags=["Notices"])
def list_notices():
    """
    List all generated enforcement notices.

    Returns:
        JSON list of notice records.
    """
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM notices ORDER BY generated_at DESC").fetchall()

    return [_row_to_dict(r) for r in rows]


@app.get("/notices/{notice_id}/pdf", tags=["Notices"])
def download_notice_pdf(notice_id: str):
    """
    Serve the PDF enforcement notice for download.

    Args:
        notice_id (str): UUID of the notice.

    Returns:
        PDF file as a streaming response.

    Raises:
        HTTPException 404: Notice not found or PDF file missing.
    """
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM notices WHERE notice_id = ?", (notice_id,)
        ).fetchone()

    if not row:
        raise HTTPException(
            status_code=404, detail=f"Notice '{notice_id}' not found.")

    pdf_path = _row_to_dict(row).get("pdf_path")

    if not pdf_path or not os.path.exists(pdf_path):
        raise HTTPException(
            status_code=404,
            detail="PDF file has not been generated yet or is missing from disk.",
        )

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=f"ARIA_Notice_{notice_id[:8]}.pdf",
    )
