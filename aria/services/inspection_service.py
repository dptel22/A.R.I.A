"""Inspection workflows and query helpers for A.R.I.A."""
from __future__ import annotations

import datetime
import logging
import os
import sqlite3
import uuid
from typing import Any

from fastapi import HTTPException

from aria.domain.models import ActionType, SeverityLevel
from aria.domain.severity import determine_action
from aria.inference.pipeline import PipelineResult, run_pipeline

log: logging.Logger = logging.getLogger(__name__)

SEVERITY_ORDER: dict[str, int] = {
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
    "CRITICAL": 4,
}

_LAT_DELTA: float = 0.00018
_LNG_DELTA: float = 0.00022
_UPLOAD_DIR: str = os.environ.get("ARIA_UPLOAD_DIR", "./runtime/uploads")
_ALLOWED_CONTENT_TYPES: set[str] = {"image/jpeg", "image/png"}
_CONTENT_TYPE_EXTENSIONS: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
}
_SEGMENT_HISTORY_LIMIT: int = 5
_PUBLIC_TO_CORE_SEVERITY: dict[str, SeverityLevel] = {
    severity.public_label: severity
    for severity in SeverityLevel
}


def raise_file_too_large(max_file_size: int) -> None:
    raise HTTPException(413, f"Image too large. Maximum size is {max_file_size // (1024 * 1024)}MB.")


def _build_image_url(image_path: str | None) -> str | None:
    return f"/uploads/{os.path.basename(image_path)}" if image_path else None



from pathlib import Path as _Path  # noqa: E402


def _safe_image_path(image_path, upload_dir=_UPLOAD_DIR):
    """Validate image_path stays within upload_dir. Returns None if invalid."""
    if not image_path:
        return None
    try:
        resolved = _Path(image_path).resolve()
        resolved.relative_to(_Path(upload_dir).resolve())
        return str(resolved)
    except (ValueError, OSError):
        log.warning("Path traversal attempt or invalid path rejected: %s", image_path)
        return None


def _notice_url_for(inspection_id: int, pipeline_status: str, detection_count: int) -> str | None:
    if pipeline_status == "SUCCEEDED" and detection_count > 0:
        return f"/api/v1/notices/{inspection_id}"
    return None


def _save_uploaded_image(img_bytes: bytes, content_type: str) -> str:
    os.makedirs(_UPLOAD_DIR, exist_ok=True)
    extension = _CONTENT_TYPE_EXTENSIONS.get(content_type, ".bin")
    filename = f"{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex}{extension}"
    output_path = os.path.join(_UPLOAD_DIR, filename)
    with open(output_path, "wb") as handle:
        handle.write(img_bytes)
    return filename


def _mask_email(email: str | None) -> str | None:
    if not email:
        return None
    if "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    return f"{local[0]}***@{domain}" if local else f"***@{domain}"


def _contract_snapshot(contract: dict[str, Any] | None) -> dict[str, Any]:
    if not contract:
        return {
            "contract_id_snapshot": None,
            "contractor_name_snapshot": None,
            "contractor_email_snapshot": None,
            "dlp_end_date_snapshot": None,
            "is_dlp_active_snapshot": 0,
        }

    return {
        "contract_id_snapshot": contract["id"],
        "contractor_name_snapshot": contract["contractor_name"],
        "contractor_email_snapshot": contract["contractor_email"],
        "dlp_end_date_snapshot": contract["dlp_end_date"],
        "is_dlp_active_snapshot": int(bool(contract["is_dlp_active"])),
    }


def _contract_payload_from_row(row: dict[str, Any]) -> dict[str, Any]:
    contract_id = row.get("contract_id_snapshot")
    contractor_name = row.get("contractor_name_snapshot")
    contractor_email = row.get("contractor_email_snapshot")
    dlp_end_date = row.get("dlp_end_date_snapshot")
    is_dlp_active = bool(row.get("is_dlp_active_snapshot"))

    if not contract_id and not contractor_name:
        return {
            "status": "NO_CONTRACT",
            "contract_id": None,
            "contractor_name": None,
            "contractor_email": None,
            "dlp_end_date": None,
            "is_dlp_active": False,
            "is_enforceable": False,
        }

    return {
        "status": "ACTIVE_CONTRACT",
        "contract_id": contract_id,
        "contractor_name": contractor_name,
        "contractor_email": _mask_email(contractor_email),
        "dlp_end_date": dlp_end_date,
        "is_dlp_active": is_dlp_active,
        "is_enforceable": is_dlp_active,
    }


def _recommended_action(
    severity_level: str,
    is_dlp_active: bool,
    pipeline_status: str = "SUCCEEDED",
) -> str:
    if pipeline_status == "FAILED":
        return "Escalate Manual Inspection"
    if pipeline_status != "SUCCEEDED" or not is_dlp_active:
        return "No Action"

    severity = _PUBLIC_TO_CORE_SEVERITY.get(severity_level)
    if severity is None:
        return "No Action"

    action = determine_action(severity)
    if action == ActionType.LOG_ONLY:
        return "No Action"
    if action == ActionType.FLAG_INSPECTOR:
        return "Issue Notice"
    if action == ActionType.ENFORCE:
        return "Block Payment" if severity_level == "CRITICAL" else "Issue Notice"
    return "No Action"


def _parse_dlp_date(dlp_end_date: str | None) -> datetime.date | None:
    if not dlp_end_date:
        return None
    try:
        return datetime.datetime.strptime(dlp_end_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        try:
            return datetime.datetime.fromisoformat(dlp_end_date.replace("Z", "+00:00")).date()
        except (ValueError, TypeError):
            return None


def _find_segment(con: sqlite3.Connection, lat: float, lng: float) -> dict[str, Any] | None:
    row = con.execute(
        """
        SELECT id, name, ward_id, zone_id
        FROM road_segments
        WHERE gps_min_lat <= ?
          AND gps_max_lat >= ?
          AND gps_min_lon <= ?
          AND gps_max_lon >= ?
        ORDER BY
            ABS(((gps_min_lat + gps_max_lat) / 2.0) - ?)
            + ABS(((gps_min_lon + gps_max_lon) / 2.0) - ?) ASC
        LIMIT 1
        """,
        (lat + _LAT_DELTA, lat - _LAT_DELTA, lng + _LNG_DELTA, lng - _LNG_DELTA, lat, lng),
    ).fetchone()
    return dict(row) if row else None


def _find_contract(con: sqlite3.Connection, segment_id: int) -> dict[str, Any] | None:
    row = con.execute(
        """
        SELECT id, contractor_name, contractor_email, dlp_end_date, contract_value
        FROM contracts
        WHERE road_segment_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (segment_id,),
    ).fetchone()
    if not row:
        return None

    result = dict(row)
    dlp_end = _parse_dlp_date(result.get("dlp_end_date"))
    if dlp_end is None and result.get("dlp_end_date"):
        log.error("Corrupted DLP date for contract %s: %r", result["id"], result.get("dlp_end_date"))
    result["is_dlp_active"] = bool(dlp_end and datetime.date.today() <= dlp_end)
    return result


def _insert_inspection_event(
    db: sqlite3.Connection,
    *,
    segment_id: int,
    lat: float,
    lng: float,
    image_path: str | None,
    pipeline_result: PipelineResult,
    contract_snapshot: dict[str, Any],
) -> int:
    cur = db.execute(
        """
        INSERT INTO inspection_events (
            segment_id,
            lat,
            lng,
            image_path,
            pipeline_status,
            failure_reason,
            contract_id_snapshot,
            contractor_name_snapshot,
            contractor_email_snapshot,
            dlp_end_date_snapshot,
            is_dlp_active_snapshot
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            segment_id,
            lat,
            lng,
            image_path,
            pipeline_result.status,
            pipeline_result.failure_reason,
            contract_snapshot["contract_id_snapshot"],
            contract_snapshot["contractor_name_snapshot"],
            contract_snapshot["contractor_email_snapshot"],
            contract_snapshot["dlp_end_date_snapshot"],
            contract_snapshot["is_dlp_active_snapshot"],
        ),
    )
    if cur.lastrowid is None:
        raise RuntimeError("INSERT returned no lastrowid")
    return int(cur.lastrowid)


def _persist_inspection(
    db: sqlite3.Connection,
    *,
    segment_id: int,
    lat: float,
    lng: float,
    image_path: str | None,
    pipeline_result: PipelineResult,
    contract_snapshot: dict[str, Any],
) -> int:
    with db:
        inspection_id = _insert_inspection_event(
            db,
            segment_id=segment_id,
            lat=lat,
            lng=lng,
            image_path=image_path,
            pipeline_result=pipeline_result,
            contract_snapshot=contract_snapshot,
        )

        if pipeline_result.status == "SUCCEEDED" and pipeline_result.detections:
            db.executemany(
                """
                INSERT INTO detections (
                    inspection_event_id,
                    class_name,
                    confidence,
                    bbox_x,
                    bbox_y,
                    bbox_w,
                    bbox_h,
                    severity_score,
                    severity_level
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        inspection_id,
                        detection["class_name"],
                        detection["confidence"],
                        detection["bbox_x"],
                        detection["bbox_y"],
                        detection["bbox_w"],
                        detection["bbox_h"],
                        detection["severity_score"],
                        detection["severity_level"],
                    )
                    for detection in pipeline_result.detections
                ],
            )

    return inspection_id


def _pipeline_http_exception(pipeline_result: PipelineResult, inspection_id: int) -> HTTPException:
    if pipeline_result.error_code == "INVALID_IMAGE":
        return HTTPException(422, f"{pipeline_result.failure_reason} Inspection attempt logged under ID {inspection_id}.")
    if pipeline_result.error_code == "MODEL_UNAVAILABLE":
        return HTTPException(503, f"{pipeline_result.failure_reason} Inspection attempt logged under ID {inspection_id}.")
    return HTTPException(503, f"{pipeline_result.failure_reason or 'Image could not be processed.'} Inspection attempt logged under ID {inspection_id}.")


def _severity_case_sql(alias: str = "d") -> str:
    return f"""
        CASE {alias}.severity_level
            WHEN 'CRITICAL' THEN 4
            WHEN 'HIGH' THEN 3
            WHEN 'MEDIUM' THEN 2
            WHEN 'LOW' THEN 1
            ELSE 0
        END
    """


def _highest_severity_sql(alias: str = "d") -> str:
    return f"""
        CASE MAX({_severity_case_sql(alias)})
            WHEN 4 THEN 'CRITICAL'
            WHEN 3 THEN 'HIGH'
            WHEN 2 THEN 'MEDIUM'
            WHEN 1 THEN 'LOW'
            ELSE 'NONE'
        END
    """


def process_detection(
    *,
    db: sqlite3.Connection,
    model: Any,
    file_content_type: str | None,
    img_bytes: bytes,
    lat: float,
    lng: float,
) -> dict[str, Any]:
    if file_content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(400, "Only JPEG and PNG images are accepted.")
    if not (-90 <= lat <= 90):
        raise HTTPException(422, f"Invalid latitude: {lat}")
    if not (-180 <= lng <= 180):
        raise HTTPException(422, f"Invalid longitude: {lng}")

    segment = _find_segment(db, lat, lng)
    if not segment:
        raise HTTPException(
            404,
            {
                "detail": "No mapped road segment found at these coordinates.",
                "lat": lat,
                "lng": lng,
                "suggestion": "This location is not in the road-segment database. Contact your administrator to add coverage for this area.",
            },
        )

    contract = None
    try:
        contract = _find_contract(db, segment["id"])
    except Exception as exc:
        log.warning("Contract lookup failed for segment %s: %s", segment["id"], exc)
    contract_snapshot = _contract_snapshot(contract)

    saved_image_path: str | None = None
    try:
        saved_image_path = _save_uploaded_image(img_bytes, file_content_type or "application/octet-stream")
    except Exception:
        log.exception("Failed to persist uploaded image for GPS=(%s, %s)", lat, lng)

    pipeline_result = run_pipeline(img_bytes, model)
    inspection_id = _persist_inspection(
        db,
        segment_id=segment["id"],
        lat=lat,
        lng=lng,
        image_path=saved_image_path,
        pipeline_result=pipeline_result,
        contract_snapshot=contract_snapshot,
    )

    if pipeline_result.status == "FAILED":
        raise _pipeline_http_exception(pipeline_result, inspection_id)

    contract_payload = _contract_payload_from_row(contract_snapshot)
    detections = pipeline_result.detections
    primary = max(detections, key=lambda detection: detection["severity_score"]) if detections else None
    highest_severity = primary["severity_level"] if primary else "NONE"

    return {
        "inspection_id": inspection_id,
        "pipeline_status": pipeline_result.status,
        "message": (
            "Image processed. Road damage detected."
            if detections
            else "Image processed. No road damage detected."
        ),
        "road_segment": segment["name"],
        "ward_id": segment["ward_id"],
        "zone_id": segment["zone_id"],
        "lat": lat,
        "lng": lng,
        "total_detections": len(detections),
        "primary_defect": (
            {
                "class_name": primary["class_name"],
                "severity_level": primary["severity_level"],
                "severity_score": primary["severity_score"],
                "confidence": primary["confidence"],
            }
            if primary
            else None
        ),
        "all_detections": detections,
        "image_url": _build_image_url(saved_image_path),
        "contract": contract_payload,
        "recommendation": _recommended_action(
            highest_severity,
            contract_payload["is_dlp_active"],
            pipeline_result.status,
        ),
        "notice_url": _notice_url_for(inspection_id, pipeline_result.status, len(detections)),
    }


def list_detection_summaries(
    *,
    db: sqlite3.Connection,
    ward_id: str | None,
    zone_id: str | None,
    min_severity: str | None,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    params: list[Any] = []
    where_clauses: list[str] = []
    having_clause = ""

    if ward_id:
        where_clauses.append("rs.ward_id = ?")
        params.append(ward_id)
    if zone_id:
        where_clauses.append("rs.zone_id = ?")
        params.append(zone_id)

    if min_severity:
        if min_severity not in SEVERITY_ORDER:
            raise HTTPException(400, f"Invalid min_severity: {min_severity}. Allowed: {list(SEVERITY_ORDER.keys())}")
        having_clause = f"HAVING MAX({_severity_case_sql('d')}) >= ?"
        params.append(SEVERITY_ORDER[min_severity])

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    summary_cte = f"""
        WITH inspection_summary AS (
            SELECT
                ie.id AS inspection_id,
                ie.created_at AS timestamp,
                ie.lat,
                ie.lng,
                ie.image_path,
                ie.pipeline_status,
                ie.failure_reason,
                ie.segment_id,
                rs.name AS road_name,
                rs.ward_id,
                rs.zone_id,
                ie.contract_id_snapshot,
                ie.contractor_name_snapshot,
                ie.contractor_email_snapshot,
                ie.dlp_end_date_snapshot,
                ie.is_dlp_active_snapshot,
                COUNT(d.id) AS total_defects,
                {_highest_severity_sql('d')} AS highest_severity,
                (
                    SELECT COUNT(*)
                    FROM inspection_events ie2
                    WHERE ie2.segment_id = ie.segment_id
                      AND ie2.id <> ie.id
                ) AS prior_flags
            FROM inspection_events ie
            JOIN road_segments rs ON ie.segment_id = rs.id
            LEFT JOIN detections d ON d.inspection_event_id = ie.id
            {where_sql}
            GROUP BY ie.id
            {having_clause}
        )
    """

    total_matching_row = db.execute(f"{summary_cte} SELECT COUNT(*) AS total_matching FROM inspection_summary", params).fetchone()
    total_matching = int(total_matching_row["total_matching"]) if total_matching_row else 0

    rows = db.execute(
        f"""
        {summary_cte}
        SELECT *
        FROM inspection_summary
        ORDER BY timestamp DESC
        LIMIT ? OFFSET ?
        """,
        [*params, limit, offset],
    ).fetchall()

    results = []
    for row in rows:
        item = dict(row)
        contract_payload = _contract_payload_from_row(item)
        pipeline_status = item["pipeline_status"]
        item.pop("contract_id_snapshot", None)
        item.pop("contractor_name_snapshot", None)
        item.pop("contractor_email_snapshot", None)
        item.pop("dlp_end_date_snapshot", None)
        item.pop("is_dlp_active_snapshot", None)
        item["image_url"] = _build_image_url(item.pop("image_path", None))
        item["contract_id"] = contract_payload["contract_id"]
        item["contractor_name"] = contract_payload["contractor_name"]
        item["contractor_email"] = contract_payload["contractor_email"]
        item["dlp_end_date"] = contract_payload["dlp_end_date"]
        item["is_dlp_active"] = contract_payload["is_dlp_active"]
        item["recommendation"] = _recommended_action(
            item["highest_severity"],
            contract_payload["is_dlp_active"],
            pipeline_status,
        )
        item["dlp_status"] = "ACTIVE" if contract_payload["is_dlp_active"] else ("EXPIRED" if contract_payload["contract_id"] else "NONE")
        item["notice_url"] = _notice_url_for(item["inspection_id"], pipeline_status, item["total_defects"])
        results.append(item)

    return {
        "total_matching": total_matching,
        "returned_count": len(results),
        "total_returned": len(results),
        "limit": limit,
        "offset": offset,
        "results": results,
    }


def get_detection_detail(*, db: sqlite3.Connection, inspection_id: int) -> dict[str, Any]:
    inspection_row = db.execute(
        """
        SELECT
            ie.id AS inspection_id,
            ie.created_at,
            ie.lat,
            ie.lng,
            ie.image_path,
            ie.segment_id,
            ie.pipeline_status,
            ie.failure_reason,
            ie.contract_id_snapshot,
            ie.contractor_name_snapshot,
            ie.contractor_email_snapshot,
            ie.dlp_end_date_snapshot,
            ie.is_dlp_active_snapshot,
            rs.name AS road_name,
            rs.ward_id,
            rs.zone_id
        FROM inspection_events ie
        JOIN road_segments rs ON ie.segment_id = rs.id
        WHERE ie.id = ?
        """,
        (inspection_id,),
    ).fetchone()

    if not inspection_row:
        raise HTTPException(404, f"Inspection event {inspection_id} not found.")

    inspection = dict(inspection_row)
    if inspection["pipeline_status"] == "SUCCEEDED":
        detection_rows = db.execute(
            """
            SELECT
                id,
                class_name,
                confidence,
                bbox_x,
                bbox_y,
                bbox_w,
                bbox_h,
                severity_score,
                severity_level
            FROM detections
            WHERE inspection_event_id = ?
            ORDER BY severity_score DESC, confidence DESC
            """,
            (inspection_id,),
        ).fetchall()
        detections = [dict(row) for row in detection_rows]
    else:
        detections = []
    primary = detections[0] if detections else None

    prior_flags_row = db.execute(
        """
        SELECT COUNT(*) AS prior_flags
        FROM inspection_events
        WHERE segment_id = ? AND id <> ?
        """,
        (inspection["segment_id"], inspection_id),
    ).fetchone()
    prior_flags = int(prior_flags_row["prior_flags"]) if prior_flags_row else 0

    history_rows = db.execute(
        f"""
        SELECT
            ie.id AS inspection_id,
            ie.created_at,
            ie.pipeline_status,
            ie.is_dlp_active_snapshot,
            COUNT(d.id) AS total_detections,
            {_highest_severity_sql('d')} AS highest_severity
        FROM inspection_events ie
        LEFT JOIN detections d ON d.inspection_event_id = ie.id
        WHERE ie.segment_id = ?
          AND ie.id <> ?
        GROUP BY ie.id
        ORDER BY ie.created_at DESC
        LIMIT ?
        """,
        (inspection["segment_id"], inspection_id, _SEGMENT_HISTORY_LIMIT),
    ).fetchall()

    segment_history = []
    for row in history_rows:
        history_item = dict(row)
        history_item["recommendation"] = _recommended_action(
            history_item["highest_severity"],
            bool(history_item["is_dlp_active_snapshot"]),
            history_item["pipeline_status"],
        )
        history_item["notice_url"] = _notice_url_for(
            history_item["inspection_id"],
            history_item["pipeline_status"],
            history_item["total_detections"],
        )
        segment_history.append(history_item)

    contract_payload = _contract_payload_from_row(inspection)
    highest_severity = primary["severity_level"] if primary else "NONE"

    return {
        "inspection_id": inspection["inspection_id"],
        "created_at": inspection["created_at"],
        "lat": inspection["lat"],
        "lng": inspection["lng"],
        "image_url": _build_image_url(inspection.get("image_path")),
        "road_segment": inspection["road_name"],
        "ward_id": inspection["ward_id"],
        "zone_id": inspection["zone_id"],
        "pipeline_status": inspection["pipeline_status"],
        "failure_reason": inspection["failure_reason"],
        "total_detections": len(detections),
        "primary_defect": primary,
        "detections": detections,
        "contract": contract_payload,
        "prior_flags": prior_flags,
        "segment_history": segment_history,
        "recommendation": _recommended_action(
            highest_severity,
            contract_payload["is_dlp_active"],
            inspection["pipeline_status"],
        ),
        "notice_url": _notice_url_for(inspection_id, inspection["pipeline_status"], len(detections)),
    }


def get_notice_context(*, db: sqlite3.Connection, inspection_id: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    inspection_row = db.execute(
        """
        SELECT
            ie.id AS inspection_id,
            ie.created_at,
            ie.lat,
            ie.lng,
            ie.image_path,
            ie.segment_id,
            ie.pipeline_status,
            ie.contract_id_snapshot,
            ie.contractor_name_snapshot,
            ie.contractor_email_snapshot,
            ie.dlp_end_date_snapshot,
            ie.is_dlp_active_snapshot,
            rs.name AS road_name,
            rs.ward_id,
            rs.zone_id
        FROM inspection_events ie
        JOIN road_segments rs ON ie.segment_id = rs.id
        WHERE ie.id = ?
        """,
        (inspection_id,),
    ).fetchone()

    if not inspection_row:
        raise HTTPException(404, f"Inspection event {inspection_id} not found.")

    inspection = dict(inspection_row)
    image_path = inspection.get("image_path")
    if image_path and not os.path.isabs(image_path):
        image_path = os.path.join(_UPLOAD_DIR, image_path)
    image_path = _safe_image_path(image_path)
    if image_path is None and inspection.get("image_path"):
        log.warning("Image path rejected for inspection %s — treating as no image.", inspection_id)
    inspection["image_path"] = image_path
    if inspection["pipeline_status"] != "SUCCEEDED":
        raise HTTPException(404, f"Inspection event {inspection_id} does not have a noticeable detection result.")

    detection_rows = db.execute(
        """
        SELECT
            class_name,
            confidence,
            bbox_x,
            bbox_y,
            bbox_w,
            bbox_h,
            severity_score,
            severity_level
        FROM detections
        WHERE inspection_event_id = ?
        ORDER BY severity_score DESC, confidence DESC
        """,
        (inspection_id,),
    ).fetchall()
    detections = [dict(row) for row in detection_rows]

    if not detections:
        raise HTTPException(404, f"Inspection event {inspection_id} has no detections available for notice generation.")

    return inspection, detections
