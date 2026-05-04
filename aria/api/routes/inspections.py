from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile

from aria.api.dependencies import get_api_key, get_db
import aria.services.inspection_service as inspection_service

router = APIRouter()

_MAX_FILE_SIZE: int = 10 * 1024 * 1024


@router.post("/detect")
def detect(
    request: Request,
    file: UploadFile = File(...),
    lat: float = Form(...),
    lng: float = Form(...),
    _key: str = Depends(get_api_key),
    db: sqlite3.Connection = Depends(get_db),
) -> dict[str, Any]:
    img_bytes = file.file.read()
    if len(img_bytes) > _MAX_FILE_SIZE:
        inspection_service.raise_file_too_large(_MAX_FILE_SIZE)
    return inspection_service.process_detection(
        db=db,
        model=request.app.state.model,
        file_content_type=file.content_type,
        img_bytes=img_bytes,
        lat=lat,
        lng=lng,
    )


@router.get("/detections")
def list_detections(
    ward_id: str | None = Query(None),
    zone_id: str | None = Query(None),
    min_severity: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _key: str = Depends(get_api_key),
    db: sqlite3.Connection = Depends(get_db),
) -> dict[str, Any]:
    return inspection_service.list_detection_summaries(
        db=db,
        ward_id=ward_id,
        zone_id=zone_id,
        min_severity=min_severity,
        limit=limit,
        offset=offset,
    )


@router.get("/detections/{inspection_id}")
def get_detection_detail(
    inspection_id: int,
    _key: str = Depends(get_api_key),
    db: sqlite3.Connection = Depends(get_db),
) -> dict[str, Any]:
    return inspection_service.get_detection_detail(db=db, inspection_id=inspection_id)
