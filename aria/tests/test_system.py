"""
tests/test_system.py — A.R.I.A. End-to-End Test Suite
Tests run in dependency order. All DB operations use the tmp_db fixture (no production data touched).
Model tests require pipeline/aria_best_v0.pt to be present.
"""

import os
import sqlite3
import sys

import pytest

# Ensure aria/ root is on path
ARIA_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ARIA_ROOT)


# ═══════════════════════════════════════════════════════════════
# Test 1 — Health Check
# ═══════════════════════════════════════════════════════════════

def test_api_health(test_client):
    """
    GET /health should return HTTP 200 and status='ok'.
    Verifies the FastAPI application starts correctly.
    """
    client, _ = test_client
    resp = client.get("/health")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    body = resp.json()
    assert body["status"] == "ok", f"Unexpected status: {body}"
    assert "version" in body
    print(
        f"\n  ✅ Health OK — version={body['version']}, ts={body['timestamp']}")


# ═══════════════════════════════════════════════════════════════
# Test 2 — DB Seed Validation
# ═══════════════════════════════════════════════════════════════

def test_db_seeded(tmp_db):
    """
    Confirm the test database contains at least 5 road_segments and 5 contracts.
    Validates that seed data was inserted correctly.
    """
    with sqlite3.connect(tmp_db) as conn:
        seg_count = conn.execute(
            "SELECT COUNT(*) FROM road_segments").fetchone()[0]
        con_count = conn.execute(
            "SELECT COUNT(*) FROM contracts").fetchone()[0]

    print(f"\n  DB: {seg_count} road_segments, {con_count} contracts")
    assert seg_count >= 5, f"Expected ≥5 road_segments, got {seg_count}"
    assert con_count >= 5, f"Expected ≥5 contracts, got {con_count}"


# ═══════════════════════════════════════════════════════════════
# Test 3 — Severity Scoring
# ═══════════════════════════════════════════════════════════════

def test_severity_low():
    """
    A very small bounding box (<5% of lane area) should return severity=LOW.
    Frame: 1280×720. Lane area = 1280 × (720 × 0.4) = 368,640 px².
    LOW threshold: bbox_area < 5% → < 18,432 px². Use bbox 50×50 = 2,500 px².
    """
    from core.severity import compute_severity
    result = compute_severity([100, 600, 150, 650],
                              frame_width=1280, frame_height=720)
    print(f"\n  LOW test: score={result['score']}, action={result['action']}")
    assert result["severity"] == "LOW"
    assert result["score"] < 0.05
    assert result["action"] == "log_only"


def test_severity_medium():
    """
    A medium-sized bounding box (8% of lane area) should return MEDIUM.
    Lane area = 368,640. 8% ≈ 29,491 px². Use bbox 200×150 = 30,000 px².
    """
    from core.severity import compute_severity
    result = compute_severity([100, 400, 300, 550],
                              frame_width=1280, frame_height=720)
    print(
        f"\n  MEDIUM test: score={result['score']}, action={result['action']}")
    assert result["severity"] == "MEDIUM"
    assert 0.05 <= result["score"] < 0.15
    assert result["action"] == "flag_inspector"


def test_severity_high():
    """
    A large bounding box (>15% of lane area) should return HIGH.
    Lane area = 368,640. >15% → >55,296 px². Use bbox 400×200 = 80,000 px².
    """
    from core.severity import compute_severity
    result = compute_severity(
        [0, 300, 400, 500], frame_width=1280, frame_height=720)
    print(f"\n  HIGH test: score={result['score']}, action={result['action']}")
    assert result["severity"] == "HIGH"
    assert result["score"] >= 0.15
    assert result["action"] == "enforce"


# ═══════════════════════════════════════════════════════════════
# Test 4 — Contract Lookup
# ═══════════════════════════════════════════════════════════════

def test_contract_lookup_found(tmp_db):
    """
    GPS coordinates within SEG001 (MG Road) should resolve to CON001 (L&T).
    """
    from core.contract_lookup import lookup_contract
    result = lookup_contract(12.9735, 77.6130, db_path=tmp_db)

    print(f"\n  Lookup: {result}")
    assert result is not None, "Expected contract to be found for MG Road GPS"
    assert result["segment_id"] == "SEG001"
    assert result["contract_id"] == "CON001"
    assert "within_dlp" in result
    assert isinstance(result["days_remaining"], int)
    assert "contractor_name" in result


def test_contract_lookup_not_found(tmp_db):
    """
    GPS 0.0, 0.0 (Gulf of Guinea) should return None — no matching segment.
    """
    from core.contract_lookup import lookup_contract
    result = lookup_contract(0.0, 0.0, db_path=tmp_db)

    print(f"\n  Lookup (0,0): {result}")
    assert result is None, f"Expected None for (0,0) GPS, got: {result}"


# ═══════════════════════════════════════════════════════════════
# Test 5 — POST /detections
# ═══════════════════════════════════════════════════════════════

def test_post_detection(test_client):
    """
    POST /detections with a HIGH-severity MG Road detection.
    Expects HTTP 201, a detection_id UUID, and status=PENDING.
    Severity and contract lookup should be auto-computed by the API.
    """
    client, _ = test_client
    payload = {
        "gps_lat": 12.9735,
        "gps_lon": 77.6130,
        "confidence": 0.91,
        "bbox": [0, 300, 400, 500],   # HIGH severity (>15% lane area)
        "frame_width": 1280,
        "frame_height": 720,
        "frame_path": None,
    }
    resp = client.post("/detections", json=payload)
    print(f"\n  POST /detections → {resp.status_code}: {resp.json()}")
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert "detection_id" in body
    assert body["status"] == "PENDING"
    assert body["severity"]["severity"] == "HIGH"
    assert body["contract"] is not None
    assert body["contract"]["segment_id"] == "SEG001"


# ═══════════════════════════════════════════════════════════════
# Test 6 — Approve Detection
# ═══════════════════════════════════════════════════════════════

def test_approve_detection(test_client, seeded_detection_id):
    """
    POST /detections/{id}/approve should:
      - Return HTTP 200
      - Return a notice_id and pdf_path
      - Create a notice record (status=DRAFT)
    """
    client, _ = test_client
    det_id = seeded_detection_id

    resp = client.post(
        f"/detections/{det_id}/approve",
        json={"approved_by": "Test Engineer"},
    )
    print(f"\n  Approve → {resp.status_code}: {resp.json()}")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert "notice_id" in body
    assert "pdf_path" in body
    assert body["status"] == "DRAFT"
    assert body["approved_by"] == "Test Engineer"

    # Store notice info for next test (via pytest cache workaround: write to module var)
    test_approve_detection._last_pdf_path = body["pdf_path"]


test_approve_detection._last_pdf_path = None


# ═══════════════════════════════════════════════════════════════
# Test 7 — PDF File Exists on Disk
# ═══════════════════════════════════════════════════════════════

def test_pdf_generated():
    """
    The PDF file returned by the approve endpoint must exist on disk
    and have a non-zero size (i.e., actually wrote bytes).
    """
    pdf_path = test_approve_detection._last_pdf_path
    assert pdf_path is not None, "No pdf_path captured — did test_approve_detection run first?"

    print(f"\n  Checking PDF: {pdf_path}")
    assert os.path.exists(pdf_path), f"PDF file not found: {pdf_path}"

    size_bytes = os.path.getsize(pdf_path)
    print(f"  PDF size: {size_bytes} bytes")
    assert size_bytes > 1000, f"PDF seems too small ({size_bytes} bytes) — likely corrupt"


# ═══════════════════════════════════════════════════════════════
# Test 8 — YOLO Model Inference
# ═══════════════════════════════════════════════════════════════

@pytest.mark.skipif(
    not os.path.exists("pipeline/aria_best_v0.pt"),
    reason="Model weights not found — run `python pipeline/setup_model.py` first",
)
def test_model_inference():
    """
    Load the pre-trained model and run inference on the first test image.
    Verifies that the pipeline does not crash and produces a valid results object.
    Prints the count of detections found.
    """
    from pipeline.inference import load_model, run_detection, extract_frames
    from pipeline.download_test_images import download_test_images

    # Ensure at least one test image exists
    images = download_test_images()
    assert images, "No test images available — check download_test_images.py"

    model = load_model("pipeline/aria_best_v0.pt")

    frames = extract_frames(images[0])
    assert len(frames) == 1, "Expected exactly 1 frame from a single image"

    frame, _ = frames[0]
    detections = run_detection(model, frame)

    print(f"\n  Inference on '{os.path.basename(images[0])}'")
    print(f"  Detections found: {len(detections)}")
    for d in detections:
        print(
            f"    → {d['label']}  conf={d['confidence']:.2f}  bbox={d['bbox']}")

    # Results object should be a list (possibly empty on novel images)
    assert isinstance(detections, list)


# ═══════════════════════════════════════════════════════════════
# Test 9 — Full Pipeline on Test Image
# ═══════════════════════════════════════════════════════════════

@pytest.mark.skipif(
    not os.path.exists("pipeline/aria_best_v0.pt"),
    reason="Model weights not found — run `python pipeline/setup_model.py` first",
)
def test_full_pipeline(test_client, tmp_path):
    """
    Run process_source() end-to-end on the first test image
    using MG Road GPS coordinates. Verifies:
      - Function completes without exception
      - Returns a list (API responses)
      - Summary is printed
    The FastAPI server is NOT required here — this test patches API_URL
    to use the TestClient via requests_mock or gracefully handles failures.
    """
    import pipeline.inference as inf_module
    from pipeline.download_test_images import download_test_images

    images = download_test_images()
    assert images, "No test images available"

    output_dir = str(tmp_path / "evidence")
    os.makedirs(output_dir, exist_ok=True)

    # Override API_URL to point at a dummy — process_source will catch
    # connection errors gracefully (prints warning, continues)
    original_url = inf_module.API_URL
    # unused port → connection refused
    inf_module.API_URL = "http://localhost:19999"

    try:
        responses = inf_module.process_source(
            source_path=images[0],
            gps_lat=12.9735,   # MG Road, Block 4
            gps_lon=77.6130,
            output_dir=output_dir,
            api_url=inf_module.API_URL,
        )
    finally:
        inf_module.API_URL = original_url  # restore

    print(f"\n  Full pipeline returned {len(responses)} API response(s)")
    # process_source returns only successfully posted items
    # With a dead API_URL this will be 0 — that's expected and handled gracefully
    assert isinstance(responses, list)
