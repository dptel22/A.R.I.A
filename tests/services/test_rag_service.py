"""Unit tests for aria/services/rag_service.py retrieval + validation."""
from __future__ import annotations

import numpy as np

from aria.domain.rag_models import RagAnswer, RagSource
from aria.services.rag_service import (
    _fts_query,
    reciprocal_rank_fusion,
    validate_sources,
)


def test_fts_query_is_or_of_quoted_tokens():
    assert _fts_query('What does Clause 32.1 require?') == '"What" OR "does" OR "Clause" OR "32" OR "1" OR "require"'
    assert _fts_query("!!!") == ""


def test_reciprocal_rank_fusion_prefers_items_in_both_lists():
    fused = reciprocal_rank_fusion([[1, 2, 3], [2, 4, 5]])
    assert fused[0] == 2  # appears in both rankings
    assert set(fused) == {1, 2, 3, 4, 5}


def test_reciprocal_rank_fusion_empty():
    assert reciprocal_rank_fusion([[], []]) == []


def test_cosine_top_k_orders_and_scores(tmp_path):
    import sqlite3

    from aria.db.connection import get_connection
    from aria.db.schema import init_db
    from aria.services.rag_service import vector_search

    db_path = tmp_path / "vec.db"
    init_db(str(db_path))
    con = get_connection(str(db_path))
    try:
        with con:
            con.execute(
                "INSERT INTO road_segments (name, gps_min_lat, gps_max_lat, gps_min_lon, gps_max_lon)"
                " VALUES ('V', 12.9, 13.0, 77.6, 77.7)"
            )
            con.execute(
                "INSERT INTO contracts (road_segment_id, contractor_name, contractor_email, dlp_end_date)"
                " VALUES ((SELECT id FROM road_segments LIMIT 1), 'C', 'c@t', '2027-01-01')"
            )
            cid = con.execute("SELECT last_insert_rowid()").fetchone()[0]
            con.execute(
                """INSERT INTO contract_documents (
                    contract_id, version, effective_from, file_name, file_hash, file_path, status
                ) VALUES (?, 1, '2025-01-01', 'a.pdf', 'h1', '/x', 'READY')""",
                (cid,),
            )
            did = con.execute("SELECT last_insert_rowid()").fetchone()[0]
            vecs = [
                (1, np.array([1.0, 0.0], dtype="<f4").tobytes()),
                (2, np.array([0.9, 0.1], dtype="<f4").tobytes()),
                (3, np.array([0.0, 1.0], dtype="<f4").tobytes()),
            ]
            for idx, emb in vecs:
                con.execute(
                    """INSERT INTO document_chunks (document_id, chunk_index, page, text, embedding)
                    VALUES (?, ?, 1, ?, ?)""",
                    (did, idx, f"chunk {idx}", emb),
                )
        hits = vector_search(con, did, [1.0, 0.0])
        assert [h[0] for h in hits] == [1, 2, 3]
        assert hits[0][1] > 0.99
        assert hits[2][1] < 0.1
    finally:
        con.close()


def _evidence():
    return [
        {"id": 10, "page": 5, "section": None, "clause": "32.1", "text": "repair within 48 hours"},
        {"id": 11, "page": 6, "section": None, "clause": None, "text": "deposit terms"},
    ]


def test_validate_sources_keeps_matching_pages_only():
    answer = RagAnswer(
        answer="x",
        supported=True,
        confidence="high",
        sources=[
            RagSource(chunk_id=10, page=5, quote="48 hours"),
            RagSource(chunk_id=99, page=1, quote="hallucinated"),
            RagSource(chunk_id=11, page=5, quote="wrong page"),
        ],
    )
    validated, has_valid = validate_sources(answer, _evidence())
    assert has_valid is True
    assert [s.chunk_id for s in validated.sources] == [10]


def test_validate_sources_all_invalid_forces_abstention_path():
    answer = RagAnswer(
        answer="x",
        supported=True,
        confidence="high",
        sources=[RagSource(chunk_id=99, page=1, quote="made up")],
    )
    _, has_valid = validate_sources(answer, _evidence())
    assert has_valid is False
