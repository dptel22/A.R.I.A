"""
tests/conftest.py — A.R.I.A. Pytest Configuration
Provides shared fixtures: in-memory test database, seeded data, and FastAPI TestClient.
Tests run entirely without a live server or network connections (except for model tests).
"""

import os
import shutil
import sqlite3
import sys
import tempfile

import pytest
from fastapi.testclient import TestClient

# ─────────────────────────────────────────────────────────────
# Ensure the aria/ root is on sys.path so imports resolve
# ─────────────────────────────────────────────────────────────
ARIA_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ARIA_ROOT)


# ─────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def tmp_db(tmp_path_factory):
    """
    Create a temporary SQLite database for the test session.

    Copies the seeded production database for read-only tests and
    provides a clean writable copy for mutation tests.

    Yields:
        str: Path to the temporary test database file.
    """
    import db.schema as schema
    import db.seed as seed

    tmp_dir = tmp_path_factory.mktemp("aria_test_db")
    db_path = str(tmp_dir / "test_aria.db")

    schema.create_tables(db_path)
    seed.seed_data(db_path)

    yield db_path
    # Cleanup is handled automatically by pytest tmp_path_factory


@pytest.fixture(scope="session")
def test_client(tmp_db):
    """
    Create a FastAPI TestClient pointed at a temporary test database.

    Monkey-patches the DB_PATH and NOTICES_DIR inside api.main so
    that tests never touch the production database, and notice PDFs
    are written to a temp directory.

    Yields:
        tuple: (TestClient, notices_temp_dir_str)
    """
    import api.main as main_module

    notices_dir = tempfile.mkdtemp(prefix="aria_notices_test_")

    # Patch module-level constants before TestClient initialises the app
    original_db = main_module.DB_PATH
    original_notices = main_module.NOTICES_DIR

    main_module.DB_PATH = tmp_db
    main_module.NOTICES_DIR = notices_dir

    # Also patch DB_PATH inside the imported core modules used by the API
    import core.contract_lookup as cl
    import core.notice_generator  # imported for side effects
    original_cl_db = cl.DB_PATH
    cl.DB_PATH = tmp_db

    client = TestClient(main_module.app)

    yield client, notices_dir

    # Restore originals after test session
    main_module.DB_PATH = original_db
    main_module.NOTICES_DIR = original_notices
    cl.DB_PATH = original_cl_db

    shutil.rmtree(notices_dir, ignore_errors=True)


@pytest.fixture(scope="session")
def seeded_detection_id(test_client):
    """
    Post one HIGH-severity detection to the test API and return its ID.

    Used by tests that need an existing detection in PENDING state
    (e.g., approve / reject tests).

    Args:
        test_client: The pytest fixture that returns (TestClient, notices_dir).

    Returns:
        str: detection_id of the newly created detection.
    """
    client, _ = test_client
    payload = {
        "gps_lat": 12.9735,          # Inside SEG001 — MG Road
        "gps_lon": 77.6130,
        "confidence": 0.91,
        "bbox": [100, 380, 500, 620],  # ~HIGH severity in a 1280×720 frame
        "frame_width": 1280,
        "frame_height": 720,
        "frame_path": None,
    }
    resp = client.post("/detections", json=payload)
    assert resp.status_code == 201
    return resp.json()["detection_id"]
