#!/usr/bin/env python
"""RAG evaluation runner for A.R.I.A.

Builds a synthetic Karnataka-PWD-SBD-style contract PDF in two versions (v1
effective 2025-01-01, v2 effective 2025-06-01 with a changed repair window),
ingests both into a throwaway database with real Gemini embeddings, then runs
the golden question set in ``tests/eval/rag_golden.jsonl`` through the real
retrieval + generation stack and reports metrics.

Usage:
    GEMINI_API_KEY=... python scripts/eval_rag.py

The fixture documents are SYNTHETIC (clearly labelled as such inside the PDF)
and exist only to make evaluation reproducible; replace them with a real SBD
when available.

Gates: retrieval_recall@8 >= 0.85, abstention_accuracy == 1.0,
       citation_validity == 1.0.
"""
from __future__ import annotations

import io
import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402

from aria.db.connection import get_connection  # noqa: E402
from aria.db.schema import init_db  # noqa: E402
from aria.services.document_ingest_service import ingest_document  # noqa: E402
from aria.services.embedding_client import get_embedding_client  # noqa: E402
from aria.services.rag_service import (  # noqa: E402
    get_generation_client,
    retrieve_evidence,
    validate_sources,
)

PAGES_COMMON = [
    # Page 1 — agreement identity
    [
        "AGREEMENT NO: KA/PWD/2025/042 (SYNTHETIC EVALUATION FIXTURE - NOT A REAL CONTRACT)",
        "This Agreement is made between the Greater Bengaluru Authority (GBA) and "
        "SBD Roadways Infra Private Limited, a company incorporated under the Companies Act, 2013.",
        "The accepted contract value of Agreement No. KA/PWD/2025/042 is rupees four crore "
        "and fifty lakh only (Rs. 4,50,00,000/-) inclusive of all taxes.",
        "The works comprise improvement and maintenance of the scheduled road segment "
        "in the Bengaluru South Corporation jurisdiction for a period of thirty-six months.",
        "The engineer-in-charge for all purposes of this agreement is the Executive "
        "Engineer, Roads & Infrastructure Division.",
    ],
    # Page 2 — DLP clauses
    [
        "32.1 Defect Liability Period. The contractor shall remain responsible for "
        "all defects arising in the works for a period of 36 months from the date of "
        "issue of the completion certificate.",
        "32.2 Restoration Standards. All restoration works shall comply with MORTH "
        "specifications and relevant IRC codes, and shall be completed within 7 days "
        "of issue of a defect notice.",
        "__REPAIR_WINDOW_CLAUSE__",
        "32.4 Follow-up Inspection. Upon notified completion, the engineer-in-charge "
        "shall cause a follow-up inspection within fourteen days to certify rectification.",
    ],
    # Page 3 — security deposit / penalties / blacklisting
    [
        "33.1 Security Deposit. Five percent (5%) of the running account bill shall be "
        "withheld as security deposit. In the event of abandonment or persistent default, "
        "the employer may forfeit the security deposit in full.",
        "33.2 Blacklisting. Upon failure to rectify defects within the notice period, "
        "the contractor shall be recommended for blacklisting from all GBA works for "
        "a period of three years.",
        "34.1 Liquidated Damages. Delay beyond the stipulated completion time shall "
        "attract a penalty of Rs. 50,000 per day of delay, subject to a ceiling of "
        "ten percent of the contract value.",
    ],
    # Page 4 — termination + Schedule B
    [
        "35.1 Termination for Default. The employer may terminate the agreement for "
        "persistent default by giving ninety (90 days) written notice, specifying the "
        "grounds of default and providing an opportunity to remedy.",
        "SCHEDULE B - PAYMENT AND MEASUREMENT TERMS",
        "Payment for the works shall be released within thirty days of measurement "
        "and certification by the engineer-in-charge, subject to recoveries under "
        "Clause 33 and Clause 34 of this agreement.",
        "Rate analysis for extra items shall follow the current PWD schedule of rates "
        "with the lead quoted by the contractor at tender.",
    ],
    # Page 5 — arbitration
    [
        "41.1 Arbitration. All disputes arising out of or in connection with this "
        "agreement shall be referred to a sole arbitrator appointed by mutual consent, "
        "and the seat of arbitration shall be Bengaluru, Karnataka.",
        "41.2 Governing Law. This agreement shall be governed by the Indian Contract "
        "Act, 1872, and the Arbitration and Conciliation Act, 1996, as amended.",
        "Notwithstanding any other provision, the engineer-in-charge's decision on "
        "measurement and quality shall be final unless disputed within thirty days.",
    ],
]

REPAIR_V1 = (
    "32.3 Commencement of Repairs. The contractor shall commence repair works within "
    "48 hours of receipt of a defect notice issued under this agreement."
)
REPAIR_V2 = (
    "32.3 Commencement of Repairs. The contractor shall commence repair works within "
    "72 hours of receipt of a defect notice issued under this agreement, revised by "
    "addendum no. 1 to this agreement."
)


def build_pdf(repair_clause: str) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    for page_lines in PAGES_COMMON:
        y = 800
        for i, line in enumerate(page_lines):
            text = repair_clause if line == "__REPAIR_WINDOW_CLAUSE__" else line
            font = "Helvetica-Bold" if i == 0 else "Helvetica"
            c.setFont(font, 10)
            for wrapped in _wrap(text, 95):
                c.drawString(72, y, wrapped)
                y -= 14
            y -= 8
        c.showPage()
    c.save()
    return buffer.getvalue()


def _wrap(text: str, width: int) -> list[str]:
    words = text.split()
    lines, current = [], ""
    for word in words:
        if len(current) + len(word) + 1 > width:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        lines.append(current)
    return lines


def main() -> int:
    try:
        embedding_client = get_embedding_client()
        generation_client = get_generation_client()
    except Exception as exc:
        print(f"Cannot run evaluation: {exc}")
        print("Set GEMINI_API_KEY in the environment (live Gemini is required).")
        return 2

    golden_path = REPO_ROOT / "tests" / "eval" / "rag_golden.jsonl"
    cases = [json.loads(line) for line in golden_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    with tempfile.TemporaryDirectory() as tmp:
        import os

        os.environ["ARIA_UPLOAD_DIR"] = tmp
        db_path = str(Path(tmp) / "eval.db")
        init_db(db_path)
        db = get_connection(db_path)
        with db:
            db.execute(
                "INSERT INTO road_segments (name, gps_min_lat, gps_max_lat, gps_min_lon, gps_max_lon)"
                " VALUES ('Eval Segment', 12.9, 13.0, 77.6, 77.7)"
            )
            db.execute(
                "INSERT INTO contracts (road_segment_id, contractor_name, contractor_email, dlp_end_date)"
                " VALUES ((SELECT id FROM road_segments LIMIT 1), 'Eval Infra', 'eval@infra.test', '2028-12-31')"
            )

        contract_id = 1
        docs = {}
        for name, pdf, effective in (
            ("v1", build_pdf(REPAIR_V1), "2025-01-01"),
            ("v2", build_pdf(REPAIR_V2), "2025-06-01"),
        ):
            row = ingest_document(
                db=db, contract_id=contract_id, file_bytes=pdf,
                file_name=f"sbd_{name}.pdf", effective_from=effective,
                embedding_client=embedding_client,
            )
            if row["status"] != "READY":
                print(f"Ingestion failed for {name}: {row.get('error')}")
                return 2
            docs[name] = row
            print(f"Ingested {name}: document_id={row['document_id']} chunks={row['chunk_count']}")

        results = []
        for case in cases:
            version = case["version"]
            at_date = case.get("at_date") or ("2025-03-15" if version == "v1" else "2025-09-15")
            document = docs[version]
            question = case["question"]

            query_vector = embedding_client.embed_query(question)
            evidence = retrieve_evidence(
                db=db, document_id=document["document_id"],
                question=question, query_vector=query_vector,
            )
            retrieved_pages = {chunk["page"] for chunk in evidence}

            retrieval_hit = (
                case["expected_page"] is None or case["expected_page"] in retrieved_pages
            )

            raw = generation_client.generate(
                question=question,
                evidence_text=__import__(
                    "aria.services.rag_service", fromlist=["build_evidence_blocks"]
                ).build_evidence_blocks(evidence, document["version"]),
            )
            answer, has_valid_sources = validate_sources(raw, evidence)

            supported = bool(answer.supported and has_valid_sources)
            answer_text = answer.answer

            expected_page = case.get("expected_page")
            source_accuracy = None
            if expected_page is not None:
                source_accuracy = any(s.page == expected_page for s in answer.sources)
                expected_clause = case.get("expected_clause")
                if source_accuracy and expected_clause:
                    source_accuracy = any(
                        s.page == expected_page and s.clause == expected_clause
                        for s in answer.sources
                    )

            must = case.get("answer_must_contain", [])
            must_not = case.get("must_not_contain", [])
            faithfulness = None
            if must or must_not:
                faithfulness = all(m in answer_text for m in must) and all(
                    m not in answer_text for m in must_not
                )

            abstention_correct = (not case["unsupported"]) or (not supported)
            version_isolated = any(
                s.chunk_id in {c["id"] for c in evidence} for s in answer.sources
            ) if answer.sources else True

            results.append({
                "category": case["category"],
                "question": question,
                "retrieval_hit": retrieval_hit,
                "supported": supported,
                "source_accuracy": source_accuracy,
                "faithfulness": faithfulness,
                "abstention_correct": abstention_correct,
                "citations_valid": has_valid_sources or not answer.sources,
            })

    total = len(results)

    def rate(key: str, skip_none: bool = True) -> float:
        values = [r[key] for r in results if r[key] is not None] if skip_none else [r[key] for r in results]
        return sum(1 for v in values if v) / len(values) if values else float("nan")

    metrics = {
        "retrieval_recall@8": rate("retrieval_hit"),
        "source_accuracy": rate("source_accuracy"),
        "citation_validity": rate("citations_valid"),
        "answer_faithfulness": rate("faithfulness"),
        "abstention_accuracy": rate("abstention_correct"),
    }

    print("\n## RAG evaluation report\n")
    print(f"Cases: {total}\n")
    print("| Metric | Score | Gate | Pass |")
    print("| --- | --- | --- | --- |")
    gates = {
        "retrieval_recall@8": 0.85,
        "abstention_accuracy": 1.0,
        "citation_validity": 1.0,
    }
    all_passed = True
    for metric, score in metrics.items():
        gate = gates.get(metric)
        passed = "—" if gate is None else ("✅" if score >= gate else "❌")
        if gate is not None and score < gate:
            all_passed = False
        gate_text = "—" if gate is None else f"{gate:.2f}"
        print(f"| {metric} | {score:.3f} | {gate_text} | {passed} |")

    print("\nPer-category:")
    categories = sorted({r["category"] for r in results})
    for category in categories:
        subset = [r for r in results if r["category"] == category]
        hits = sum(1 for r in subset if r["retrieval_hit"])
        print(f"  {category}: retrieval {hits}/{len(subset)}")

    failures = [
        r for r in results
        if not r["retrieval_hit"]
        or r["abstention_correct"] is False
        or r["faithfulness"] is False
        or r["source_accuracy"] is False
    ]
    if failures:
        print("\nFailing cases:")
        for r in failures:
            print(f"  [{r['category']}] {r['question']}")
            print(f"    retrieval={r['retrieval_hit']} supported={r['supported']} "
                  f"source={r['source_accuracy']} faithful={r['faithfulness']}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
