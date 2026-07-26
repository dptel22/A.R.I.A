from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from aria.api.dependencies import get_api_key, get_db
from aria.services import segments_service

router = APIRouter()


@router.get("/segments")
def list_segments(
    _key: str = Depends(get_api_key),
    db: sqlite3.Connection = Depends(get_db),
):
    return segments_service.list_segments(db)


@router.get("/segments/{segment_id}")
def get_segment_detail(
    segment_id: int,
    _key: str = Depends(get_api_key),
    db: sqlite3.Connection = Depends(get_db),
):
    return segments_service.get_segment_detail(db, segment_id)
