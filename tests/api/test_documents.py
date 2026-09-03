"""Integration tests for the contract document upload/list API (RAG Phase 2).

Gemini is never contacted — a deterministic fake embedding client is injected
via monkeypatching ``get_embedding_client``.
"""
from __future__ import annotations

import importlib
import io
import sqlite3
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aria.db.connection import get_connection
from aria.db.schema import init_db


API_KEY = "test-api-key"


class FakeEmbeddingClient:
    """Deterministic embeddings: hash-based 16-dim vectors, zero API calls."""

    def __init__(self):
        self.document_calls: list[list[str]] = []
        self.query_calls: list[str] = []

    def _embed(self, text: str) -> list[float]:
        import hashlib

        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return [b / 255.0 for b in digest[:16]]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.document_calls.append(list(texts))
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        self.query_calls.append(text)
        return self._embed(text)


def _make_contract_pdf(pages: int = 3, scanned: bool = False) -> bytes:
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer)
    for page in range(pages):
        if scanned:
            c.drawImage = getattr(c, "drawImage", None)  # no text at all
            c.showPage()
            continue
        c.setFont("Helvetica", 11)
        c.drawString(72, 800, f"32.{page + 1} Defect Liability Obligations")
        for line in range(30):
            c.drawString(72, 780 - line * 14,
                         f"Clause 32.{page + 1} paragraph {line}: the contractor shall repair "
                         f"defects within forty-eight hours and complete restoration within seven days.")
        c.showPage()
    c.save()
    return buffer.getvalue()


def _reload_app():
    for module_name in (
        "aria.api.app",
        "aria.api.dependencies",
        "aria.api.routes",
        "aria.api.routes.health",
        "aria.api.routes.inspections",
        "aria.api.routes.notices",
        "aria.api.routes.documents",
        "aria.services.inspection_service",
        "aria.services.notice_service",
        "aria.services.document_ingest_service",
    ):
        sys.modules.pop(module_name, None)
    importlib.invalidate_caches()
    return importlib.import_module("aria.api.app")


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    unique_id = uuid.uuid4().hex
    db_path = tmp_path / f"docs-test-{unique_id}.db"
    upload_dir = tmp_path / f"docs-uploads-{unique_id}"
    upload_dir.mkdir(exist_ok=True)

    monkeypatch.setenv("ARIA_API_KEY", API_KEY)
    monkeypatch.setenv("ARIA_DB_PATH", str(db_path))
    monkeypatch.setenv("ARIA_UPLOAD_DIR", str(upload_dir))
    monkeypatch.setenv("ARIA_MODEL_PATH", str(tmp_path / "missing-model.pt"))

    init_db(str(db_path))
    con = get_connection(str(db_path))
    try:
        with con:
            con.execute(
                "INSERT INTO road_segments (name, gps_min_lat, gps_max_lat, gps_min_lon, gps_max_lon)"
                " VALUES ('Doc Segment', 12.9, 13.0, 77.6, 77.7)"
            )
            cur = con.execute(
                "INSERT INTO contracts (road_segment_id, contractor_name, contractor_email, dlp_end_date)"
                " VALUES ((SELECT id FROM road_segments LIMIT 1), 'Doc Infra', 'doc@infra.test', '2027-12-31')"
            )
            contract_id = int(cur.lastrowid)
    finally:
        con.close()
    return {"db_path": db_path, "contract_id": contract_id, "upload_dir": upload_dir}


@pytest.fixture
def client(env):
    fake = FakeEmbeddingClient()
    app_module = _reload_app()
    import aria.services.document_ingest_service as ingest_module

    original = ingest_module.get_embedding_client
    ingest_module.get_embedding_client = lambda: fake  # type: ignore[assignment]
    with TestClient(app_module.app) as test_client:
        yield test_client, fake
    ingest_module.get_embedding_client = original
    for suffix in ("", "-wal", "-shm"):
        Path(str(env["db_path"]) + suffix).unlink(missing_ok=True)


def _auth_headers() -> dict[str, str]:
    return {"x-api-key": API_KEY}


def test_upload_ingests_and_indexes_document(env, client):
    test_client, fake = client
    pdf = _make_contract_pdf()
    response = test_client.post(
        f"/api/v1/contracts/{env['contract_id']}/documents",
        headers=_auth_headers(),
        files={"file": ("sbd.pdf", pdf, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "READY"
    assert body["version"] == 1
    assert body["page_count"] == 3
    assert body["chunk_count"] > 0
    assert len(fake.document_calls) == 1

    # Chunks are stored with embeddings and searchable via FTS.
    con = get_connection(str(env["db_path"]))
    try:
        row = con.execute(
            "SELECT COUNT(*) FROM document_chunks WHERE document_id = ? AND embedding IS NOT NULL",
            (body["document_id"],),
        ).fetchone()
        assert row[0] == body["chunk_count"]
        fts = con.execute(
            "SELECT COUNT(*) FROM document_chunks_fts WHERE document_chunks_fts MATCH 'contractor'"
        ).fetchone()
        assert fts[0] > 0
    finally:
        con.close()


def test_upload_requires_api_key(env, client):
    test_client, _ = client
    response = test_client.post(
        f"/api/v1/contracts/{env['contract_id']}/documents",
        files={"file": ("sbd.pdf", _make_contract_pdf(), "application/pdf")},
    )
    assert response.status_code == 401


def test_duplicate_upload_is_409_with_existing_id(env, client):
    test_client, _ = client
    pdf = _make_contract_pdf()
    first = test_client.post(
        f"/api/v1/contracts/{env['contract_id']}/documents",
        headers=_auth_headers(),
        files={"file": ("sbd.pdf", pdf, "application/pdf")},
    )
    assert first.status_code == 201
    second = test_client.post(
        f"/api/v1/contracts/{env['contract_id']}/documents",
        headers=_auth_headers(),
        files={"file": ("sbd-copy.pdf", pdf, "application/pdf")},
    )
    assert second.status_code == 409
    assert second.json()["existing_document_id"] == first.json()["document_id"]


def test_non_pdf_rejected(env, client):
    test_client, _ = client
    response = test_client.post(
        f"/api/v1/contracts/{env['contract_id']}/documents",
        headers=_auth_headers(),
        files={"file": ("not.pdf", b"just text, no pdf magic", "application/pdf")},
    )
    assert response.status_code == 422


def test_scanned_pdf_marked_failed(env, client):
    test_client, _ = client
    response = test_client.post(
        f"/api/v1/contracts/{env['contract_id']}/documents",
        headers=_auth_headers(),
        files={"file": ("scan.pdf", _make_contract_pdf(scanned=True), "application/pdf")},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "FAILED"
    assert "scanned" in body["error"].lower()


def test_unknown_contract_404(env, client):
    test_client, _ = client
    response = test_client.post(
        "/api/v1/contracts/999999/documents",
        headers=_auth_headers(),
        files={"file": ("sbd.pdf", _make_contract_pdf(), "application/pdf")},
    )
    assert response.status_code == 404


def test_oversized_upload_422(env, client, monkeypatch):
    test_client, _ = client
    monkeypatch.setenv("ARIA_RAG_MAX_UPLOAD_MB", "1")
    big = b"%PDF-" + b"x" * (1024 * 1024 + 100)
    response = test_client.post(
        f"/api/v1/contracts/{env['contract_id']}/documents",
        headers=_auth_headers(),
        files={"file": ("big.pdf", big, "application/pdf")},
    )
    assert response.status_code == 422


def test_second_upload_supersedes_first_from_effective_date(env, client):
    test_client, _ = client
    first = test_client.post(
        f"/api/v1/contracts/{env['contract_id']}/documents",
        headers=_auth_headers(),
        files={"file": ("v1.pdf", _make_contract_pdf(), "application/pdf")},
        data={"effective_from": "2025-01-01"},
    )
    assert first.status_code == 201
    second_pdf = _make_contract_pdf(pages=2)
    second = test_client.post(
        f"/api/v1/contracts/{env['contract_id']}/documents",
        headers=_auth_headers(),
        files={"file": ("v2.pdf", second_pdf, "application/pdf")},
        data={"effective_from": "2025-06-01"},
    )
    assert second.status_code == 201

    listing = test_client.get(
        f"/api/v1/contracts/{env['contract_id']}/documents", headers=_auth_headers()
    )
    assert listing.status_code == 200
    docs = {d["version"]: d for d in listing.json()}
    assert docs[1]["superseded_at"] == "2025-06-01"
    assert docs[2]["superseded_at"] is None

    detail = test_client.get(
        f"/api/v1/contracts/{env['contract_id']}/documents/{docs[1]['document_id']}",
        headers=_auth_headers(),
    )
    assert detail.status_code == 200
    assert detail.json()["version"] == 1
