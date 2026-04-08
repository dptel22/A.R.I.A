from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from aria.api.dependencies import get_api_key, get_db
from aria.services.inspection_service import get_notice_context
from aria.services.notice_service import build_notice_pdf

router = APIRouter()


@router.get("/notices/{inspection_id}")
def get_notice(
    inspection_id: int,
    _key: str = Depends(get_api_key),
    db: sqlite3.Connection = Depends(get_db),
) -> Response:
    inspection, detections = get_notice_context(db=db, inspection_id=inspection_id)
    pdf_bytes = build_notice_pdf(inspection=inspection, detections=detections)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="ARIA_Notice_{inspection_id}.pdf"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )
