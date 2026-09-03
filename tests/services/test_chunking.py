"""Unit tests for aria/services/chunking.py"""
from __future__ import annotations

from aria.services.chunking import build_context_header, chunk_pages, detect_heading


def _pages(*texts: str) -> list[dict]:
    return [{"page": i + 1, "text": text} for i, text in enumerate(texts)]


def test_detect_heading_clause_numbers():
    section, clause = detect_heading("32.1 Defect Liability Period")
    assert section is None and clause == "32.1"

    section, clause = detect_heading("3.2.1.2 Sub-paragraph")
    assert clause == "3.2.1.2"

    section, clause = detect_heading("SCHEDULE B: Payment Terms")
    assert section == "SCHEDULE B" and clause is None

    # Ordinary sentences must not be headings.
    assert detect_heading("The contractor shall repair all defects.") == (None, None)
    assert detect_heading("7 days from notice") == (None, None)


def test_chunks_never_span_pages_and_carry_page_metadata():
    page1 = "32.1 Defect Liability Period\n" + ("The contractor shall repair defects. " * 200)
    page2 = "33.1 Payment Terms\n" + ("Payment shall follow certification. " * 200)
    chunks = chunk_pages(_pages(page1, page2))
    assert len(chunks) >= 2
    pages = {c.page for c in chunks}
    assert pages == {1, 2}
    first_on_page2 = next(c for c in chunks if c.page == 2)
    assert first_on_page2.clause == "33.1"


def test_chunk_indices_are_sequential():
    text = "1.1 General\n" + ("Clause text with obligations. " * 500)
    chunks = chunk_pages(_pages(text))
    assert [c.index for c in chunks] == list(range(len(chunks)))


def test_overlap_between_same_page_chunks():
    body = "\n\n".join(f"Paragraph number {i} with some contractual content." for i in range(120))
    chunks = chunk_pages(_pages(body), target_chars=600, overlap_chars=100)
    if len(chunks) > 1:
        tail = chunks[0].text[-200:]
        assert chunks[1].text.split("\n")[0] in chunks[0].text


def test_context_header_includes_version_page_clause():
    pages = _pages("32.1 Defect Liability Period\nContent of the clause.")
    chunk = chunk_pages(pages)[0]
    header = build_context_header(2, chunk)
    assert "Contract v2" in header
    assert "p.1" in header
    assert "Clause 32.1" in header
