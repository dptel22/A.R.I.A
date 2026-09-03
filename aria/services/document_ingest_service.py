"""Contract document ingestion: PDF → validated, hashed, chunked, embedded, indexed.

Pipeline (Phase 2 of the RAG plan):

    PDF upload → validation → SHA-256 hashing → registration → text extraction
    (per page) → clause detection → chunk generation → embedding → indexing

All rows live in the same SQLite database as the rest of A.R.I.A. Retrieval
searches are document-scoped, so a chunk can never leak into another
contract's answers.
"""
from __future__ import annotations

import hashlib
import logging
import os
import sqlite3
import uuid
from typing import Any

from aria.services.chunking import build_context_header, chunk_pages
from aria.services.embedding_client import EmbeddingUnavailableError, get_embedding_client

log: logging.Logger = logging.getLogger(__name__)

PDF_MAGIC = b"%PDF-"
# A PDF with >= 2 pages but almost no text is treated as scanned.
_SCANNED_MIN_CHARS = 200
_SCANNED_MIN_PAGES = 2

DEFAULT_MAX_UPLOAD_MB = 20


class DocumentIngestError(Exception):
    """Base class — carry a machine-readable code."""

    code = "INGEST_ERROR"

    def __init__(self, message: str, code: str | None = None):
        super().__init__(message)
        if code:
            self.code = code


class ContractNotFoundError(DocumentIngestError):
    code = "CONTRACT_NOT_FOUND"


class DuplicateDocumentError(DocumentIngestError):
    code = "DUPLICATE_DOCUMENT"

    def __init__(self, message: str, existing_document_id: int):
        super().__init__(message)
        self.existing_document_id = existing_document_id


class InvalidDocumentError(DocumentIngestError):
    code = "INVALID_DOCUMENT"


def max_upload_bytes() -> int:
    mb = int(os.environ.get("ARIA_RAG_MAX_UPLOAD_MB", str(DEFAULT_MAX_UPLOAD_MB)))
    return mb * 1024 * 1024


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _documents_dir() -> str:
    upload_dir = os.environ.get("ARIA_UPLOAD_DIR", "./runtime/uploads")
    documents_dir = os.path.join(upload_dir, "documents")
    os.makedirs(documents_dir, exist_ok=True)
    return documents_dir


def _extract_pages(pdf_bytes: bytes) -> list[dict]:
    """Extract 1-based page text. Raises InvalidDocumentError for malformed PDFs."""
    import fitz  # pymupdf

    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            pages = [{"page": number + 1, "text": page.get_text()} for number, page in enumerate(doc)]
        return pages
    except Exception as exc:
        raise InvalidDocumentError(f"Could not parse PDF: {exc}")


def ingest_document(
    db: sqlite3.Connection,
    contract_id: int,
    file_bytes: bytes,
    file_name: str,
    effective_from: str | None = None,
    embedding_client: Any = None,
) -> dict[str, Any]:
    """Validate, register, chunk, embed, and index a contract PDF.

    Returns the contract_documents row as a dict (status READY or FAILED —
    a FAILED row is a normal outcome for e.g. scanned PDFs and is returned,
    not raised). Raises DocumentIngestError subclasses for conditions that
    must map to HTTP errors (unknown contract, duplicate hash, bad upload).
    """
    import datetime

    if not file_bytes.startswith(PDF_MAGIC):
        raise InvalidDocumentError("File is not a PDF (missing %PDF- header)")
    if len(file_bytes) > max_upload_bytes():
        raise InvalidDocumentError(
            f"File exceeds maximum size of {max_upload_bytes() // (1024 * 1024)} MB"
        )

    contract = db.execute(
        "SELECT id FROM contracts WHERE id = ?", (contract_id,)
    ).fetchone()
    if contract is None:
        raise ContractNotFoundError(f"Contract {contract_id} does not exist")

    file_hash = _sha256_hex(file_bytes)
    existing = db.execute(
        "SELECT id FROM contract_documents WHERE file_hash = ?", (file_hash,)
    ).fetchone()
    if existing is not None:
        raise DuplicateDocumentError(
            "This document has already been uploaded", int(existing[0])
        )

    if embedding_client is None:
        try:
            embedding_client = get_embedding_client()
        except EmbeddingUnavailableError:
            embedding_client = None

    next_version = int(
        db.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 FROM contract_documents WHERE contract_id = ?",
            (contract_id,),
        ).fetchone()[0]
    )
    if effective_from is None:
        effective_from = datetime.datetime.now(datetime.timezone.utc).date().isoformat()

    documents_dir = _documents_dir()
    stored_name = f"{uuid.uuid4().hex}.pdf"
    file_path = os.path.join(documents_dir, stored_name)
    with open(file_path, "wb") as fh:
        fh.write(file_bytes)

    cur = db.execute(
        """
        INSERT INTO contract_documents (
            contract_id, version, effective_from, file_name, file_hash,
            file_path, status
        ) VALUES (?, ?, ?, ?, ?, ?, 'PROCESSING')
        """,
        (contract_id, next_version, effective_from, file_name, file_hash, file_path),
    )
    document_id = int(cur.lastrowid)
    db.commit()

    try:
        pages = _extract_pages(file_bytes)
        total_text = sum(len(p["text"]) for p in pages)
        if len(pages) >= _SCANNED_MIN_PAGES and total_text < _SCANNED_MIN_CHARS:
            raise InvalidDocumentError(
                "PDF appears to be scanned (no extractable text). OCR is not supported."
            )

        chunks = chunk_pages(pages)
        if not chunks:
            raise InvalidDocumentError("PDF contains no extractable text")

        if embedding_client is None:
            raise DocumentIngestError(
                "GEMINI_API_KEY is not configured — cannot embed document", "EMBEDDING_UNAVAILABLE"
            )

        embedded_texts = [
            f"{build_context_header(next_version, chunk)}\n{chunk.text}" for chunk in chunks
        ]
        vectors = embedding_client.embed_documents(embedded_texts)

        import numpy as np

        db.execute("BEGIN")
        try:
            for chunk, vector in zip(chunks, vectors):
                db.execute(
                    """
                    INSERT INTO document_chunks (
                        document_id, chunk_index, page, section, clause, text, embedding
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        document_id,
                        chunk.index,
                        chunk.page,
                        chunk.section,
                        chunk.clause,
                        chunk.text,
                        np.asarray(vector, dtype="<f4").tobytes(),
                    ),
                )
            db.execute(
                "UPDATE contract_documents SET status = 'READY', page_count = ?, error = NULL"
                " WHERE id = ?",
                (len(pages), document_id),
            )
            # A newly effective version supersedes older open versions from the
            # date the new version becomes effective (not from upload time), so
            # historical lookups keep resolving the old version for older dates.
            db.execute(
                """
                UPDATE contract_documents
                SET superseded_at = MAX(COALESCE(superseded_at, ?), ?)
                WHERE contract_id = ? AND id != ? AND status = 'READY'
                  AND superseded_at IS NULL AND effective_from < ?
                """,
                (effective_from, effective_from, contract_id, document_id, effective_from),
            )
            db.execute("COMMIT")
        except Exception:
            db.execute("ROLLBACK")
            raise
    except Exception as exc:
        error_message = str(exc)
        code = getattr(exc, "code", "INGEST_FAILED")
        db.execute(
            "UPDATE contract_documents SET status = 'FAILED', error = ? WHERE id = ?",
            (error_message[:500], document_id),
        )
        db.commit()
        log.warning("Document %s ingestion failed: %s", document_id, error_message)
        if isinstance(exc, DocumentIngestError):
            row = get_document(db, contract_id, document_id)
            row["error"] = error_message
            return row
        raise DocumentIngestError(f"Ingestion failed: {error_message}", code)

    row = get_document(db, contract_id, document_id)
    log.info("Document %s (contract %s v%s) ingested: %s chunks", document_id, contract_id, next_version, len(chunks))
    return row


def _with_document_id(row: dict[str, Any]) -> dict[str, Any]:
    """Expose the row's primary key as ``document_id`` for API consumers."""
    if "id" in row:
        row["document_id"] = row.pop("id")
    return row


def list_documents(db: sqlite3.Connection, contract_id: int) -> list[dict[str, Any]]:
    cur = db.cursor()
    cur.row_factory = sqlite3.Row
    rows = cur.execute(
        """
        SELECT d.id, d.contract_id, d.version, d.effective_from, d.superseded_at,
               d.file_name, d.file_hash, d.status, d.page_count, d.error, d.created_at,
               (SELECT COUNT(*) FROM document_chunks c WHERE c.document_id = d.id) AS chunk_count
        FROM contract_documents d
        WHERE d.contract_id = ?
        ORDER BY d.version DESC
        """,
        (contract_id,),
    ).fetchall()
    return [_with_document_id(dict(row)) for row in rows]


def get_document(db: sqlite3.Connection, contract_id: int, document_id: int) -> dict[str, Any]:
    cur = db.cursor()
    cur.row_factory = sqlite3.Row
    row = cur.execute(
        """
        SELECT d.id, d.contract_id, d.version, d.effective_from, d.superseded_at,
               d.file_name, d.file_hash, d.status, d.page_count, d.error, d.created_at,
               (SELECT COUNT(*) FROM document_chunks c WHERE c.document_id = d.id) AS chunk_count
        FROM contract_documents d
        WHERE d.id = ? AND d.contract_id = ?
        """,
        (document_id, contract_id),
    ).fetchone()
    if row is None:
        raise DocumentIngestError("Document not found", "DOCUMENT_NOT_FOUND")
    return _with_document_id(dict(row))
