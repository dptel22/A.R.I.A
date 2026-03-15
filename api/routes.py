"""
api/routes.py — A.R.I.A. API endpoint handlers.

Endpoints:
    POST /api/v1/detect         — Upload image + GPS → run YOLO, store, return summary
    GET  /api/v1/detections     — Paginated, filterable inspection list
    GET  /api/v1/notices/{id}   — Generate enforcement PDF in-memory and stream it
"""
from __future__ import annotations

import datetime
import io
import logging
import sqlite3
from typing import Any

import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from PIL import Image

from api.dependencies import get_api_key, get_db
from core.notice_generator import generate_pdf_notice
from core.models import ContractStatus, DetectionMetadata, SeverityLevel

log: logging.Logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# YOLO class names — must match model training order
CLASS_NAMES: dict[int, str] = {
    0: "longitudinal_crack",
    1: "transverse_crack",
    2: "alligator_crack",
    3: "pothole",
}

# Base severity per damage type (higher = worse)
BASE_SEVERITY: dict[str, int] = {
    "pothole":            4,   # CRITICAL
    "alligator_crack":    3,   # HIGH
    "transverse_crack":   2,   # MEDIUM
    "longitudinal_crack": 1,   # LOW
}

# Severity level thresholds
SEVERITY_ORDER: dict[str, int] = {
    "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4,
}

# GPS tolerance — ≈ 20 metres at Bengaluru latitude
_LAT_DELTA: float = 0.00018
_LNG_DELTA: float = 0.00022

# File upload limits
_MAX_FILE_SIZE: int = 10 * 1024 * 1024   # 10 MB
_ALLOWED_CONTENT_TYPES: set[str] = {"image/jpeg", "image/png"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _map_score_to_level(score: float) -> str:
    """Map a composite severity score to a human-readable level."""
    if score >= 6.0:
        return "CRITICAL"
    if score >= 4.0:
        return "HIGH"
    if score >= 2.0:
        return "MEDIUM"
    return "LOW"


def _find_segment(con: sqlite3.Connection, lat: float, lng: float) -> dict[str, Any] | None:
    """Find the closest road segment within GPS tolerance."""
    row = con.execute(
        """
        SELECT id, name, ward_id, zone_id
        FROM road_segments
        WHERE ? BETWEEN gps_min_lat AND gps_max_lat
          AND ? BETWEEN gps_min_lon AND gps_max_lon
        ORDER BY ABS(gps_min_lat - ?) + ABS(gps_min_lon - ?) ASC
        LIMIT 1
        """,
        (lat, lng, lat, lng),
    ).fetchone()
    return dict(row) if row else None


def _find_contract(con: sqlite3.Connection, segment_id: int) -> dict[str, Any] | None:
    """Find the most recent contract for a segment and calculate DLP status."""
    row = con.execute(
        """
        SELECT id, contractor_name, contractor_email, dlp_end_date, contract_value
        FROM contracts
        WHERE road_segment_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (segment_id,),
    ).fetchone()
    if not row:
        return None

    result = dict(row)
    # Safely calculate DLP status
    try:
        dlp_end = datetime.datetime.strptime(result["dlp_end_date"], "%Y-%m-%d").date()
        result["is_dlp_active"] = datetime.date.today() <= dlp_end
    except (ValueError, TypeError):
        log.error("Corrupted DLP date for contract %s: %r", result["id"], result.get("dlp_end_date"))
        result["is_dlp_active"] = False

    return result


# ---------------------------------------------------------------------------
# POST /detect
# ---------------------------------------------------------------------------

@router.post("/detect")
async def detect(
    request: Request,
    file: UploadFile = File(...),
    lat: float = Form(...),
    lng: float = Form(...),
    _key: str = Depends(get_api_key),
    db: sqlite3.Connection = Depends(get_db),
):
    """
    Accept image + GPS from an inspector's device.
    Run YOLO inference. Store inspection event + detections.
    Return JSON summary with contract/DLP status.
    """
    # --- Step 1: Validate input -----------------------------------------------
    if file.content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(400, "Only JPEG and PNG images are accepted.")

    img_bytes = await file.read()
    if len(img_bytes) > _MAX_FILE_SIZE:
        raise HTTPException(413, f"Image too large. Maximum size is {_MAX_FILE_SIZE // (1024*1024)}MB.")

    if not (-90 <= lat <= 90):
        raise HTTPException(422, f"Invalid latitude: {lat}")
    if not (-180 <= lng <= 180):
        raise HTTPException(422, f"Invalid longitude: {lng}")

    # --- Step 2: GPS → Road segment ------------------------------------------
    segment = _find_segment(db, lat, lng)
    if not segment:
        raise HTTPException(404, {
            "detail": "No GBA road segment found within tolerance of these coordinates.",
            "lat": lat,
            "lng": lng,
            "suggestion": "Verify GPS signal and retry outdoors.",
        })

    # --- Step 3: YOLO inference -----------------------------------------------
    model = request.app.state.model
    if model is None:
        raise HTTPException(503, "YOLO model not loaded. Server cannot process detections.")

    img_pil = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    img_array = np.array(img_pil)

    results = model.predict(
        source=img_array,
        conf=0.25,
        iou=0.45,
        verbose=False,
        imgsz=640,
    )

    # --- Step 4: Extract + score detections -----------------------------------
    raw_detections: list[dict[str, Any]] = []
    for box in results[0].boxes:
        class_id = int(box.cls[0])
        class_name = CLASS_NAMES.get(class_id, f"unknown_{class_id}")
        confidence = float(box.conf[0])
        # Normalised xywh
        xywhn = box.xywhn[0]
        bbox_x, bbox_y, bbox_w, bbox_h = (
            float(xywhn[0]), float(xywhn[1]),
            float(xywhn[2]), float(xywhn[3]),
        )

        # Composite severity score
        base = BASE_SEVERITY.get(class_name, 1)
        area_ratio = bbox_w * bbox_h
        area_weight = 1.0 + min(area_ratio * 10, 1.0)
        severity_score = round(base * area_weight, 3)
        severity_level = _map_score_to_level(severity_score)

        raw_detections.append({
            "class_name": class_name,
            "confidence": round(confidence, 4),
            "bbox_x": round(bbox_x, 4),
            "bbox_y": round(bbox_y, 4),
            "bbox_w": round(bbox_w, 4),
            "bbox_h": round(bbox_h, 4),
            "severity_score": severity_score,
            "severity_level": severity_level,
        })

    # --- Step 5: Store in DB --------------------------------------------------
    if not raw_detections:
        return {
            "message": "Image processed. No road damage detected.",
            "inspection_id": None,
            "road_segment": segment["name"],
            "detections": [],
        }

    with db:  # atomic transaction
        cur = db.execute(
            "INSERT INTO inspection_events (segment_id, lat, lng) VALUES (?, ?, ?)",
            (segment["id"], lat, lng),
        )
        inspection_id = cur.lastrowid

        for det in raw_detections:
            db.execute(
                """INSERT INTO detections
                       (inspection_event_id, class_name, confidence,
                        bbox_x, bbox_y, bbox_w, bbox_h,
                        severity_score, severity_level)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (inspection_id, det["class_name"], det["confidence"],
                 det["bbox_x"], det["bbox_y"], det["bbox_w"], det["bbox_h"],
                 det["severity_score"], det["severity_level"]),
            )

    # --- Step 6: Contract lookup (informational, never fails the request) -----
    contract_info: dict[str, Any] = {"status": "NO_CONTRACT", "contractor_name": None, "is_dlp_active": False}
    try:
        contract = _find_contract(db, segment["id"])
        if contract:
            contract_info = {
                "contractor_name": contract["contractor_name"],
                "contractor_email": contract["contractor_email"],
                "dlp_end_date": contract["dlp_end_date"],
                "is_dlp_active": contract["is_dlp_active"],
                "is_enforceable": contract["is_dlp_active"],
            }
    except Exception as e:
        log.warning("Contract lookup failed for segment %s: %s", segment["id"], e)

    # --- Step 7: Build response -----------------------------------------------
    primary = max(raw_detections, key=lambda d: d["severity_score"])

    return {
        "inspection_id": inspection_id,
        "road_segment": segment["name"],
        "ward_id": segment["ward_id"],
        "zone_id": segment["zone_id"],
        "total_detections": len(raw_detections),
        "primary_defect": {
            "class_name": primary["class_name"],
            "severity_level": primary["severity_level"],
            "severity_score": primary["severity_score"],
            "confidence": primary["confidence"],
        },
        "all_detections": raw_detections,
        "contract": contract_info,
        "notice_url": f"/api/v1/notices/{inspection_id}",
    }


# ---------------------------------------------------------------------------
# GET /detections
# ---------------------------------------------------------------------------

@router.get("/detections")
def list_detections(
    ward_id: str | None = Query(None),
    zone_id: str | None = Query(None),
    min_severity: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _key: str = Depends(get_api_key),
    db: sqlite3.Connection = Depends(get_db),
):
    """
    Paginated, filterable list of past inspection events
    with aggregated detection metadata.
    """
    params: list[Any] = []
    where_clauses: list[str] = []
    having_clause = ""

    if ward_id:
        where_clauses.append("rs.ward_id = ?")
        params.append(ward_id)
    if zone_id:
        where_clauses.append("rs.zone_id = ?")
        params.append(zone_id)

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    if min_severity and min_severity in SEVERITY_ORDER:
        min_rank = SEVERITY_ORDER[min_severity]
        having_clause = f"""
        HAVING MAX(
            CASE d.severity_level
                WHEN 'CRITICAL' THEN 4
                WHEN 'HIGH'     THEN 3
                WHEN 'MEDIUM'   THEN 2
                WHEN 'LOW'      THEN 1
                ELSE 0
            END
        ) >= ?
        """
        params.append(min_rank)

    query = f"""
        SELECT
            ie.id              AS inspection_id,
            ie.created_at      AS timestamp,
            rs.name            AS road_name,
            rs.ward_id,
            rs.zone_id,
            COUNT(d.id)        AS total_defects,
            MAX(d.severity_level) AS highest_severity,
            SUM(CASE WHEN d.severity_level = 'CRITICAL' THEN 1 ELSE 0 END) AS critical_count,
            SUM(CASE WHEN d.severity_level = 'HIGH'     THEN 1 ELSE 0 END) AS high_count
        FROM inspection_events ie
        JOIN road_segments rs ON ie.segment_id = rs.id
        LEFT JOIN detections d ON d.inspection_event_id = ie.id
        {where_sql}
        GROUP BY ie.id
        {having_clause}
        ORDER BY ie.created_at DESC
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])

    rows = db.execute(query, params).fetchall()
    results = [dict(r) for r in rows]

    return {
        "total_returned": len(results),
        "limit": limit,
        "offset": offset,
        "results": results,
    }


# ---------------------------------------------------------------------------
# GET /notices/{inspection_id}
# ---------------------------------------------------------------------------

@router.get("/notices/{inspection_id}")
def get_notice(
    inspection_id: int,
    _key: str = Depends(get_api_key),
    db: sqlite3.Connection = Depends(get_db),
):
    """
    Fetch inspection data, generate enforcement PDF in-memory, stream it back.
    """
    # --- Step 1: Fetch inspection + detections --------------------------------
    rows = db.execute(
        """
        SELECT
            ie.id AS inspection_id, ie.created_at, ie.lat, ie.lng,
            ie.segment_id,
            rs.name AS road_name, rs.ward_id, rs.zone_id,
            d.class_name, d.confidence,
            d.bbox_x, d.bbox_y, d.bbox_w, d.bbox_h,
            d.severity_score, d.severity_level
        FROM inspection_events ie
        JOIN road_segments rs ON ie.segment_id = rs.id
        JOIN detections d ON d.inspection_event_id = ie.id
        WHERE ie.id = ?
        """,
        (inspection_id,),
    ).fetchall()

    if not rows:
        raise HTTPException(404, f"Inspection event {inspection_id} not found.")

    first = dict(rows[0])
    all_dets = [dict(r) for r in rows]
    primary = max(all_dets, key=lambda d: d["severity_score"])

    # --- Step 2: Fetch contract -----------------------------------------------
    contract = _find_contract(db, first["segment_id"])

    # Build the typed dataclasses that notice_generator expects
    # Map the API severity levels back to our Enum
    severity_map = {
        "CRITICAL": SeverityLevel.HIGH,
        "HIGH": SeverityLevel.HIGH,
        "MEDIUM": SeverityLevel.MEDIUM,
        "LOW": SeverityLevel.LOW,
    }
    detection_metadata = DetectionMetadata(
        gps_lat=first["lat"],
        gps_lon=first["lng"],
        severity=severity_map.get(primary["severity_level"], SeverityLevel.HIGH),
        confidence=primary["confidence"],
    )

    if contract:
        try:
            dlp_end = datetime.datetime.strptime(contract["dlp_end_date"], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            dlp_end = None

        contract_status = ContractStatus(
            segment_id=first["segment_id"],
            segment_name=first["road_name"],
            contract_id=contract["id"],
            contractor_name=contract["contractor_name"],
            contractor_email=contract["contractor_email"],
            dlp_end_date=dlp_end,
            is_dlp_active=contract.get("is_dlp_active", False),
        )
    else:
        contract_status = ContractStatus(
            segment_id=first["segment_id"],
            segment_name=first["road_name"],
            contract_id=0,
            contractor_name="Unknown (No contract on file)",
            contractor_email="N/A",
            dlp_end_date=None,
            is_dlp_active=False,
        )

    # --- Step 3: Generate PDF in-memory ---------------------------------------
    pdf_buffer = io.BytesIO()
    generate_pdf_notice(detection_metadata, contract_status, output_dir=None, buffer=pdf_buffer)
    pdf_bytes = pdf_buffer.getvalue()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="ARIA_Notice_{inspection_id}.pdf"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )
