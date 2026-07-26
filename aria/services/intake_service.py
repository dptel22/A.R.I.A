"""Engineer Intake clustering, promotion, and dismissal."""
from __future__ import annotations

import math
import os
import sqlite3
from typing import Any
from urllib.parse import urlparse
from urllib.request import urlopen

from fastapi import HTTPException

from aria.domain.contract_lookup import find_contract_matches_by_gps
from aria.inference.pipeline import PipelineResult, run_pipeline
import aria.services.inspection_service as inspection_service

CLUSTER_THRESHOLD_METERS = 10.0
# O(n^2) read-time clustering is acceptable for portfolio-scale demo data; production should persist clusters in a background job.
_SOURCE_PRIORITY = ("citizen_submission", "roadcam_survey")
_SEVERITY_RANK = {"NONE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}


def _haversine_meters(a_lat: float, a_lng: float, b_lat: float, b_lng: float) -> float:
    radius = 6_371_000.0
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp = math.radians(b_lat - a_lat)
    dl = math.radians(b_lng - a_lng)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.atan2(math.sqrt(h), math.sqrt(1 - h))


def _raw_rows(db: sqlite3.Connection, status: str = "unreviewed") -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in db.execute(
            """
            SELECT
                rs.id, rs.batch_id, rs.image_url, rs.lat, rs.lng, rs.exif_lat, rs.exif_lng,
                rs.exif_timestamp, rs.gps_mismatch_flag, rs.status, rs.dismiss_reason,
                rs.promoted_inspection_id, rs.submitted_at, sb.source_type
            FROM raw_submissions rs
            JOIN submission_batches sb ON sb.id = rs.batch_id
            WHERE rs.status = ?
            ORDER BY rs.submitted_at ASC, rs.id ASC
            """,
            (status,),
        ).fetchall()
    ]


def _submission_payload(row: dict[str, Any], cluster_id: int | None = None) -> dict[str, Any]:
    return {
        "id": row["id"],
        "batch_id": row["batch_id"],
        "image_url": row["image_url"],
        "lat": row["lat"],
        "lng": row["lng"],
        "exif_lat": row["exif_lat"],
        "exif_lng": row["exif_lng"],
        "exif_timestamp": row["exif_timestamp"],
        "gps_mismatch_flag": bool(row["gps_mismatch_flag"]),
        "cluster_id": cluster_id,
        "status": row["status"],
        "submitted_at": row["submitted_at"],
        "source": row["source_type"],
    }


def _contract_match_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "segment_id": row["segment_id"],
        "segment_name": row["segment_name"],
        "contract_id": row["contract_id"],
        "contractor_name": row["contractor_name"] or "No contract on file",
        "contractor_email": row["contractor_email"],
        "dlp_end_date": row["dlp_end_date"],
        "is_dlp_active": bool(row["is_dlp_active"]),
    }


def _cluster_payload(cluster_id: int, rows: list[dict[str, Any]], db: sqlite3.Connection) -> dict[str, Any]:
    center_lat = sum(row["lat"] for row in rows) / len(rows)
    center_lng = sum(row["lng"] for row in rows) / len(rows)
    source_types = [source for source in _SOURCE_PRIORITY if source in {row["source_type"] for row in rows}]
    return {
        "id": cluster_id,
        "center_lat": center_lat,
        "center_lng": center_lng,
        "submission_count": len(rows),
        "first_submitted_at": min(row["submitted_at"] for row in rows),
        "last_submitted_at": max(row["submitted_at"] for row in rows),
        "source_types": source_types,
        "submissions": [_submission_payload(row, cluster_id) for row in rows],
        "segment_matches": [
            _contract_match_payload(match)
            for match in find_contract_matches_by_gps(center_lat, center_lng, db)
        ],
    }


def list_clusters(db: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = _raw_rows(db)
    grouped: list[list[dict[str, Any]]] = []
    for row in rows:
        for cluster in grouped:
            c_lat = sum(item["lat"] for item in cluster) / len(cluster)
            c_lng = sum(item["lng"] for item in cluster) / len(cluster)
            if _haversine_meters(row["lat"], row["lng"], c_lat, c_lng) <= CLUSTER_THRESHOLD_METERS:
                cluster.append(row)
                break
        else:
            grouped.append([row])
    return [_cluster_payload(index + 1, cluster, db) for index, cluster in enumerate(grouped)]


def get_cluster(db: sqlite3.Connection, cluster_id: int) -> dict[str, Any]:
    for cluster in list_clusters(db):
        if cluster["id"] == cluster_id:
            return cluster
    raise HTTPException(404, f"Cluster {cluster_id} not found.")


def _winning_result(results: list[tuple[dict[str, Any], PipelineResult, str | None]]) -> tuple[dict[str, Any], PipelineResult, str | None]:
    def key(item: tuple[dict[str, Any], PipelineResult, str | None]) -> tuple[int, float, int]:
        row, result, _image_path = item
        primary = result.detections[0] if result.detections else None
        severity = primary["severity_level"] if primary else "NONE"
        confidence = float(primary["confidence"]) if primary else 0.0
        return (_SEVERITY_RANK[severity], confidence, -int(row["id"]))

    return max(results, key=key)


def _source_type(rows: list[dict[str, Any]]) -> str:
    sources = {row["source_type"] for row in rows}
    if len(sources) == 1:
        return next(iter(sources))
    return "citizen_submission" if "citizen_submission" in sources else "roadcam_survey"


def _read_image_bytes(image_url: str) -> bytes:
    parsed = urlparse(image_url)
    if parsed.scheme in ("http", "https"):
        with urlopen(image_url, timeout=10) as response:
            return response.read(10 * 1024 * 1024 + 1)
    path = parsed.path if parsed.scheme == "file" else image_url
    if path.startswith("/uploads/"):
        path = os.path.join(os.environ.get("ARIA_UPLOAD_DIR", "./runtime/uploads"), os.path.basename(path))
    with open(path, "rb") as handle:
        return handle.read()


def promote_cluster(
    *,
    db: sqlite3.Connection,
    model: Any,
    cluster_id: int,
    segment_id: int | None,
) -> dict[str, Any]:
    with db:
        cluster = get_cluster(db, cluster_id)
        matches = cluster["segment_matches"]
        valid_segment_ids = {match["segment_id"] for match in matches}
        if segment_id is not None and segment_id not in valid_segment_ids:
            raise HTTPException(400, "Selected segment does not match this cluster.")
        if len(matches) > 1 and segment_id is None:
            raise HTTPException(400, "Multiple segment matches require segment_id.")
        if len(matches) == 1 and segment_id is None:
            segment_id = matches[0]["segment_id"]

        rows = [
            row for row in _raw_rows(db)
            if row["id"] in {submission["id"] for submission in cluster["submissions"]}
        ]
        results: list[tuple[dict[str, Any], PipelineResult, str | None]] = []
        for row in rows:
            image_bytes = _read_image_bytes(row["image_url"])
            result = run_pipeline(image_bytes, model)
            image_path = inspection_service.save_intake_image(image_bytes)
            results.append((row, result, image_path))

        winning_row, winning_result, image_path = _winning_result(results)
        inspection_id = inspection_service.persist_intake_inspection(
            db=db,
            segment_id=segment_id,
            source_type=_source_type(rows),
            lat=cluster["center_lat"],
            lng=cluster["center_lng"],
            image_path=image_path,
            pipeline_result=winning_result,
            contract_snapshot=inspection_service.find_contract_snapshot(db, segment_id),
        )
        db.executemany(
            """
            UPDATE raw_submissions
            SET status = 'promoted', promoted_inspection_id = ?, dismiss_reason = NULL
            WHERE id = ?
            """,
            [(inspection_id, row["id"]) for row in rows],
        )
    return {"inspection_id": inspection_id, "winning_submission_id": winning_row["id"]}


def dismiss_cluster(*, db: sqlite3.Connection, cluster_id: int, reason: str) -> dict[str, Any]:
    cluster = get_cluster(db, cluster_id)
    submission_ids = [submission["id"] for submission in cluster["submissions"]]
    with db:
        db.executemany(
            "UPDATE raw_submissions SET status = 'dismissed', dismiss_reason = ? WHERE id = ?",
            [(reason, submission_id) for submission_id in submission_ids],
        )
    return {"dismissed_count": len(submission_ids)}


def list_dismissed(db: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = _raw_rows(db, "dismissed")
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row.get("dismiss_reason") or "other", []).append(row)
    dismissed = []
    index = 1
    for reason, reason_rows in grouped.items():
        dismissed.append({
            "cluster": _cluster_payload(index, reason_rows, db),
            "reason": reason,
            "dismissed_at": max(row["submitted_at"] for row in reason_rows),
        })
        index += 1
    return dismissed
