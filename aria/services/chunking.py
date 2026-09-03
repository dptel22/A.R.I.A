"""Clause-aware chunking for contract documents.

Chunks never span pages, so the ``page`` metadata on every chunk is exact and
page-level citations are trustworthy. Section/clause headers detected via regex
are attached to every chunk produced under them.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# ~900 tokens ≈ 3600 chars; overlap ≈ 120 tokens ≈ 480 chars.
TARGET_CHUNK_CHARS = 3600
OVERLAP_CHARS = 480
MIN_CHUNK_CHARS = 200

# "32.1", "3.2.1", "Clause 7", "SCHEDULE B", "ANNEXURE II"
_CLAUSE_RE = re.compile(r"^\s*(?i:clause\s+)?(\d+(?:\.\d+)*)\.?\s+([A-Z].*)$")
_SECTION_WORDS_RE = re.compile(
    r"^\s*((?:SCHEDULE|ANNEXURE|APPENDIX|ARTICLE)\s+[A-Z0-9IVX]+)\b[:.\s]*(.*)$",
    re.IGNORECASE,
)


@dataclass
class Chunk:
    index: int
    page: int
    text: str
    section: str | None = None
    clause: str | None = None


@dataclass
class _Paragraph:
    page: int
    text: str
    section: str | None
    clause: str | None


def detect_heading(line: str) -> tuple[str | None, str | None]:
    """Return (section, clause) if *line* looks like a structural heading."""
    m = _SECTION_WORDS_RE.match(line)
    if m:
        return m.group(1).upper(), None
    m = _CLAUSE_RE.match(line)
    if m and len(m.group(2)) > 3:  # avoid matching ordinary numbered list items
        return None, m.group(1)
    return None, None


def _split_paragraphs(page_text: str) -> list[str]:
    paragraphs: list[str] = []
    buffer: list[str] = []
    for line in page_text.splitlines():
        stripped = line.strip()
        if not stripped:
            if buffer:
                paragraphs.append("\n".join(buffer))
                buffer = []
            continue
        buffer.append(stripped)
    if buffer:
        paragraphs.append("\n".join(buffer))
    return paragraphs


def _parse_pages(pages: list[dict[int, str]]) -> list[_Paragraph]:
    """*pages* is a list of {page_number: text} or dicts with page/text keys."""
    paragraphs: list[_Paragraph] = []
    section: str | None = None
    clause: str | None = None
    for page in pages:
        page_no = page["page"]
        for raw in _split_paragraphs(page["text"]):
            first_line = raw.split("\n", 1)[0]
            hit_section, hit_clause = detect_heading(first_line)
            if hit_section:
                section = hit_section
            if hit_clause:
                clause = hit_clause
            paragraphs.append(
                _Paragraph(page=page_no, text=raw, section=section, clause=clause)
            )
    return paragraphs


def chunk_pages(
    pages: list[dict],
    target_chars: int = TARGET_CHUNK_CHARS,
    overlap_chars: int = OVERLAP_CHARS,
) -> list[Chunk]:
    """Group per-page paragraphs into chunks.

    A chunk never contains text from two pages. Each chunk carries the
    section/clause in force at the position where the chunk *starts*.
    """
    paragraphs = _parse_pages(pages)
    chunks: list[Chunk] = []
    index = 0
    i = 0
    while i < len(paragraphs):
        page_no = paragraphs[i].page
        section = paragraphs[i].section
        clause = paragraphs[i].clause
        parts: list[str] = []
        size = 0
        j = i
        while j < len(paragraphs) and paragraphs[j].page == page_no and size < target_chars:
            parts.append(paragraphs[j].text)
            size += len(paragraphs[j].text) + 1
            j += 1

        body = "\n".join(parts)
        if len(body) < MIN_CHUNK_CHARS and j < len(paragraphs) and chunks:
            # Tiny tail — merge into the previous chunk on the same page if possible.
            prev = chunks[-1]
            if prev.page == page_no:
                prev.text = f"{prev.text}\n{body}"
                i = j
                continue

        if overlap_chars > 0 and chunks and chunks[-1].page == page_no:
            tail = chunks[-1].text[-overlap_chars:]
            cut = tail.find("\n")
            if cut != -1:
                tail = tail[cut + 1 :]
            if tail:
                body = f"{tail}\n{body}"

        chunks.append(
            Chunk(index=index, page=page_no, text=body, section=section, clause=clause)
        )
        index += 1
        i = j
    return chunks


def build_context_header(version: int, chunk: Chunk, contract_label: str = "contract") -> str:
    """Header prepended to chunk text before embedding and shown to the model."""
    parts = [f"Contract v{version}", f"p.{chunk.page}"]
    if chunk.section:
        parts.append(f"Section {chunk.section}")
    if chunk.clause:
        parts.append(f"Clause {chunk.clause}")
    return f"[{' | '.join(parts)}]"
