"""
db/schema.py — A.R.I.A. SQLite schema initialiser.

Exposes:
    init_db(db_path: str) -> None

Run as a script:
    python -m db.schema [optional_path]
Env override:
    ARIA_DB_PATH=./aria.db python -m db.schema
"""
from __future__ import annotations

import logging
import os
import sys

from db.connection import get_connection

log: logging.Logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

_DDL: list[str] = [
    # -----------------------------------------------------------------------
    # road_segments
    # -----------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS road_segments (
        id          INTEGER PRIMARY KEY,
        name        TEXT    NOT NULL UNIQUE,
        ward_id     TEXT    NOT NULL DEFAULT 'UNKNOWN',
        zone_id     TEXT    NOT NULL DEFAULT 'UNKNOWN',
        gps_min_lat REAL    NOT NULL,
        gps_max_lat REAL    NOT NULL,
        gps_min_lon REAL    NOT NULL,
        gps_max_lon REAL    NOT NULL,
        created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
        CHECK (gps_min_lat <= gps_max_lat),
        CHECK (gps_min_lon <= gps_max_lon)
    )
    """,
    # -----------------------------------------------------------------------
    # contracts
    # -----------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS contracts (
        id              INTEGER PRIMARY KEY,
        road_segment_id INTEGER NOT NULL REFERENCES road_segments(id) ON DELETE CASCADE,
        contractor_name  TEXT    NOT NULL,
        contractor_email TEXT    NOT NULL,
        dlp_end_date    TEXT    NOT NULL,   -- ISO-8601 date string e.g. '2025-12-31'
        contract_value  REAL,               -- optional
        created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
        UNIQUE (road_segment_id, contractor_name)
    )
    """,
    # -----------------------------------------------------------------------
    # inspection_events  (parent of detections — one image = one event)
    # -----------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS inspection_events (
        id          INTEGER PRIMARY KEY,
        segment_id  INTEGER NOT NULL REFERENCES road_segments(id) ON DELETE CASCADE,
        inspector_id TEXT,              -- API key hash or worker ID for audit trail
        lat         REAL    NOT NULL,
        lng         REAL    NOT NULL,
        image_path  TEXT,               -- optional, if saved to disk
        created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
    )
    """,
    # -----------------------------------------------------------------------
    # detections  (children of inspection_events — one bbox = one detection)
    # -----------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS detections (
        id                    INTEGER PRIMARY KEY,
        inspection_event_id   INTEGER NOT NULL REFERENCES inspection_events(id) ON DELETE CASCADE,
        class_name            TEXT    NOT NULL,
        confidence            REAL    NOT NULL,
        bbox_x                REAL    NOT NULL,   -- normalised centre x (0-1)
        bbox_y                REAL    NOT NULL,   -- normalised centre y (0-1)
        bbox_w                REAL    NOT NULL,   -- normalised width  (0-1)
        bbox_h                REAL    NOT NULL,   -- normalised height (0-1)
        severity_score        REAL    NOT NULL,
        severity_level        TEXT    NOT NULL,    -- LOW / MEDIUM / HIGH / CRITICAL
        created_at            TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
        CHECK (confidence BETWEEN 0.0 AND 1.0),
        CHECK (severity_level IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
        CHECK (bbox_x BETWEEN 0.0 AND 1.0),
        CHECK (bbox_y BETWEEN 0.0 AND 1.0),
        CHECK (bbox_w BETWEEN 0.0 AND 1.0),
        CHECK (bbox_h BETWEEN 0.0 AND 1.0)
    )
    """,
    # -----------------------------------------------------------------------
    # notices
    # -----------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS notices (
        id                  INTEGER PRIMARY KEY,
        inspection_event_id INTEGER NOT NULL REFERENCES inspection_events(id) ON DELETE CASCADE,
        contract_id         INTEGER NOT NULL REFERENCES contracts(id)  ON DELETE CASCADE,
        pdf_path            TEXT,        -- NULL for in-memory generation
        generated_at        TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
        UNIQUE (inspection_event_id, contract_id)
    )
    """,
]

# ---------------------------------------------------------------------------
# Indexes
# ---------------------------------------------------------------------------

_INDEXES: list[str] = [
    # Bounding-box spatial lookup on road_segments
    "CREATE INDEX IF NOT EXISTS idx_segs_bbox ON road_segments(gps_min_lat, gps_max_lat, gps_min_lon, gps_max_lon)",
    # ward/zone filtering
    "CREATE INDEX IF NOT EXISTS idx_segs_ward ON road_segments(ward_id)",
    "CREATE INDEX IF NOT EXISTS idx_segs_zone ON road_segments(zone_id)",
    # inspection_events filtering
    "CREATE INDEX IF NOT EXISTS idx_ie_segment    ON inspection_events(segment_id)",
    "CREATE INDEX IF NOT EXISTS idx_ie_created_at ON inspection_events(created_at)",
    # detections filtering
    "CREATE INDEX IF NOT EXISTS idx_det_ie        ON detections(inspection_event_id)",
    "CREATE INDEX IF NOT EXISTS idx_det_severity  ON detections(severity_level)",
    "CREATE INDEX IF NOT EXISTS idx_det_created_at ON detections(created_at)",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def init_db(db_path: str) -> None:
    """
    Create all tables and indexes in the SQLite database at *db_path*.

    Safe to call on an already-initialised DB — all statements use
    CREATE TABLE/INDEX IF NOT EXISTS.
    """
    con = get_connection(db_path)
    try:
        with con:  # auto-commit on success, rollback on exception
            for ddl in _DDL:
                con.execute(ddl)
            for idx in _INDEXES:
                con.execute(idx)

        log.info("Database initialised at: %s", os.path.abspath(db_path))
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Script entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format="[%(name)s] %(message)s")
    path: str = (
        sys.argv[1]
        if len(sys.argv) > 1
        else os.environ.get("ARIA_DB_PATH", "./aria.db")
    )
    init_db(path)
