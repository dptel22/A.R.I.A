"""Road Segment read models."""
from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import HTTPException

from aria.services.inspection_service import _build_image_url, _highest_severity_sql, _recommended_action


def _contract_payload(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    item = dict(row)
    return {
        "id": item["id"],
        "contractor_name": item["contractor_name"],
        "contractor_email": item["contractor_email"],
        "dlp_end_date": item["dlp_end_date"],
        "is_dlp_active": bool(item["is_dlp_active"]),
        "contract_value": item["contract_value"],
        "created_at": item["created_at"],
    }


def _segment_payload(db: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    segment = dict(row)
    contracts = [
        _contract_payload(contract)
        for contract in db.execute(
            """
            SELECT *, CASE WHEN date(dlp_end_date) >= date('now') THEN 1 ELSE 0 END AS is_dlp_active
            FROM contracts
            WHERE road_segment_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (segment["id"],),
        ).fetchall()
    ]
    active = next((contract for contract in contracts if contract["is_dlp_active"]), None)
    case_count = int(db.execute(
        "SELECT COUNT(*) AS count FROM inspection_events WHERE segment_id = ?",
        (segment["id"],),
    ).fetchone()["count"])
    return {
        "id": segment["id"],
        "name": segment["name"],
        "ward_id": segment["ward_id"],
        "zone_id": segment["zone_id"],
        "bbox": {
            "min_lat": segment["gps_min_lat"],
            "max_lat": segment["gps_max_lat"],
            "min_lng": segment["gps_min_lon"],
            "max_lng": segment["gps_max_lon"],
        },
        "active_contract": active,
        "contract_history": contracts,
        "case_count": case_count,
    }


def list_segments(db: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = db.execute(
        """
        SELECT id, name, ward_id, zone_id, gps_min_lat, gps_max_lat, gps_min_lon, gps_max_lon
        FROM road_segments
        ORDER BY name ASC, id ASC
        """
    ).fetchall()
    return [_segment_payload(db, row) for row in rows]


def get_segment_detail(db: sqlite3.Connection, segment_id: int) -> dict[str, Any]:
    row = db.execute(
        """
        SELECT id, name, ward_id, zone_id, gps_min_lat, gps_max_lat, gps_min_lon, gps_max_lon
        FROM road_segments
        WHERE id = ?
        """,
        (segment_id,),
    ).fetchone()
    if not row:
        raise HTTPException(404, f"Road segment {segment_id} not found.")

    cases = []
    for case_row in db.execute(
        f"""
        SELECT
            ie.id AS inspection_id,
            ie.created_at,
            ie.pipeline_status,
            ie.is_dlp_active_snapshot,
            ie.image_path,
            rs.name AS road_segment,
            COUNT(d.id) AS total_detections,
            {_highest_severity_sql('d')} AS highest_severity
        FROM inspection_events ie
        JOIN road_segments rs ON rs.id = ie.segment_id
        LEFT JOIN detections d ON d.inspection_event_id = ie.id
        WHERE ie.segment_id = ?
        GROUP BY ie.id
        ORDER BY ie.created_at DESC, ie.id DESC
        """,
        (segment_id,),
    ).fetchall():
        item = dict(case_row)
        cases.append({
            "id": f"ARIA-{int(item['inspection_id']):06d}",
            "inspection_id": item["inspection_id"],
            "road_segment": item["road_segment"],
            "severity": item["highest_severity"],
            "status": "Escalated" if item["pipeline_status"] == "FAILED" else "Awaiting Review",
            "created": item["created_at"],
            "recommendation": _recommended_action(
                item["highest_severity"],
                bool(item["is_dlp_active_snapshot"]),
                item["pipeline_status"],
            ),
            "image_url": _build_image_url(item.get("image_path")),
        })

    return {"segment": _segment_payload(db, row), "cases": cases}
