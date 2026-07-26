from __future__ import annotations

import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from aria.api.dependencies import get_api_key, get_db
from aria.services import intake_service

router = APIRouter()


class PromoteRequest(BaseModel):
    segment_id: int | None = None


class DismissRequest(BaseModel):
    reason: Literal["spam", "duplicate", "not_a_road_defect", "other"]


@router.get("/intake/clusters")
def list_clusters(
    _key: str = Depends(get_api_key),
    db: sqlite3.Connection = Depends(get_db),
):
    return intake_service.list_clusters(db)


@router.get("/intake/clusters/{cluster_id}")
def get_cluster(
    cluster_id: int,
    _key: str = Depends(get_api_key),
    db: sqlite3.Connection = Depends(get_db),
):
    return intake_service.get_cluster(db, cluster_id)


@router.post("/intake/clusters/{cluster_id}/promote")
def promote_cluster(
    cluster_id: int,
    body: PromoteRequest,
    request: Request,
    _key: str = Depends(get_api_key),
    db: sqlite3.Connection = Depends(get_db),
):
    return intake_service.promote_cluster(
        db=db,
        model=request.app.state.model,
        cluster_id=cluster_id,
        segment_id=body.segment_id,
    )


@router.post("/intake/clusters/{cluster_id}/dismiss")
def dismiss_cluster(
    cluster_id: int,
    body: DismissRequest,
    _key: str = Depends(get_api_key),
    db: sqlite3.Connection = Depends(get_db),
):
    return intake_service.dismiss_cluster(db=db, cluster_id=cluster_id, reason=body.reason)


@router.get("/intake/dismissed")
def list_dismissed(
    _key: str = Depends(get_api_key),
    db: sqlite3.Connection = Depends(get_db),
):
    return intake_service.list_dismissed(db)
