"""POST /api/v1/detections/{inspection_id}/ask — grounded contract assistant.

Advisory only: the answer explains the applicable contract document. It never
modifies enforcement decisions, notices, or contract snapshots.
"""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from aria.api.dependencies import get_api_key, get_db
from aria.domain.document_resolution import resolve_document_version
from aria.services.rag_service import (
    RagNotConfiguredError,
    answer_question,
    get_generation_client,
)

router = APIRouter()


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


def _load_inspection(db: sqlite3.Connection, inspection_id: int) -> sqlite3.Row | None:
    cur = db.cursor()
    cur.row_factory = sqlite3.Row
    return cur.execute(
        """
        SELECT id, segment_id, contract_id_snapshot, document_version_id,
               pipeline_status, lat, lng, created_at
        FROM inspection_events
        WHERE id = ?
        """,
        (inspection_id,),
    ).fetchone()


@router.post("/detections/{inspection_id}/ask")
def ask_contract_question(
    inspection_id: int,
    request: AskRequest,
    _key: str = Depends(get_api_key),
    db: sqlite3.Connection = Depends(get_db),
):
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question must not be empty")

    inspection = _load_inspection(db, inspection_id)
    if inspection is None:
        raise HTTPException(status_code=404, detail="Inspection not found")

    contract_id = inspection["contract_id_snapshot"]
    if contract_id is None:
        raise HTTPException(
            status_code=409,
            detail="No contract was snapshotted for this inspection, so there is "
            "no applicable contract document to query.",
        )

    # Historical correctness first: an inspection-time document snapshot wins.
    document = None
    if inspection["document_version_id"] is not None:
        row = db.execute(
            """
            SELECT id, contract_id, version, effective_from, status
            FROM contract_documents WHERE id = ?
            """,
            (inspection["document_version_id"],),
        ).fetchone()
        if row is not None and row["status"] == "READY" and row["contract_id"] == contract_id:
            cur = db.cursor()
            cur.row_factory = sqlite3.Row
            document = dict(
                cur.execute(
                    "SELECT id, contract_id, version, effective_from FROM contract_documents WHERE id = ?",
                    (row["id"],),
                ).fetchone()
            )
    if document is None:
        resolved = resolve_document_version(
            db, contract_id, at=inspection["created_at"]
        )
        if resolved is not None:
            document = {
                "document_id": resolved["id"],
                "contract_id": resolved["contract_id"],
                "version": resolved["version"],
                "effective_from": resolved["effective_from"],
            }
    if document is None:
        raise HTTPException(
            status_code=409,
            detail="No processed contract document is applicable to this inspection. "
            "Upload the contract document for this contract first.",
        )

    try:
        import aria.services.embedding_client as embedding_module
        import aria.services.rag_service as rag_module

        try:
            embedding_client = embedding_module.get_embedding_client()
        except embedding_module.EmbeddingUnavailableError as exc:
            raise rag_module.RagNotConfiguredError(str(exc))
        generation_client = rag_module.get_generation_client()
    except RagNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    answer = answer_question(
        db=db,
        inspection=dict(inspection),
        document=document,
        question=question,
        embedding_client=embedding_client,
        generation_client=generation_client,
    )
    answer["document"] = {
        "document_id": document["document_id"],
        "version": document["version"],
        "effective_from": document["effective_from"],
    }
    return answer
