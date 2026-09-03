"""Contract document upload/list endpoints (RAG ingestion surface)."""
from __future__ import annotations

import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from aria.api.dependencies import get_api_key, get_db
from aria.services.document_ingest_service import (
    ContractNotFoundError,
    DocumentIngestError,
    DuplicateDocumentError,
    InvalidDocumentError,
    get_document,
    ingest_document,
    list_documents,
)

router = APIRouter()


def _error_response(exc: DocumentIngestError) -> JSONResponse:
    status = {
        "CONTRACT_NOT_FOUND": 404,
        "DOCUMENT_NOT_FOUND": 404,
        "DUPLICATE_DOCUMENT": 409,
        "INVALID_DOCUMENT": 422,
        "EMBEDDING_UNAVAILABLE": 503,
    }.get(exc.code, 500)
    payload: dict = {"detail": str(exc), "code": exc.code}
    if isinstance(exc, DuplicateDocumentError):
        payload["existing_document_id"] = exc.existing_document_id
    return JSONResponse(status_code=status, content=payload)


@router.post("/contracts/{contract_id}/documents", status_code=201)
def upload_contract_document(
    contract_id: int,
    file: UploadFile = File(...),
    effective_from: Optional[str] = Form(default=None),
    _key: str = Depends(get_api_key),
    db: sqlite3.Connection = Depends(get_db),
):
    file_bytes = file.file.read()
    try:
        document = ingest_document(
            db=db,
            contract_id=contract_id,
            file_bytes=file_bytes,
            file_name=file.filename or "contract.pdf",
            effective_from=effective_from,
        )
    except (ContractNotFoundError, DuplicateDocumentError, InvalidDocumentError) as exc:
        return _error_response(exc)
    except DocumentIngestError as exc:
        return _error_response(exc)
    return document


@router.get("/contracts/{contract_id}/documents")
def list_contract_documents(
    contract_id: int,
    _key: str = Depends(get_api_key),
    db: sqlite3.Connection = Depends(get_db),
):
    return list_documents(db, contract_id)


@router.get("/contracts/{contract_id}/documents/{document_id}")
def get_contract_document(
    contract_id: int,
    document_id: int,
    _key: str = Depends(get_api_key),
    db: sqlite3.Connection = Depends(get_db),
):
    try:
        return get_document(db, contract_id, document_id)
    except DocumentIngestError as exc:
        return _error_response(exc)
