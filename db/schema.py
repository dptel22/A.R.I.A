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

import os
import sqlite3
import sys

# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

_DDL: list[str] = [
    # -----------------------------------------------------------------------
    # road_segments
    # -----------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS road_segments (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT    NOT NULL,
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
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        road_segment_id INTEGER NOT NULL REFERENCES road_segments(id) ON DELETE CASCADE,
        contractor_name  TEXT    NOT NULL,
        contractor_email TEXT    NOT NULL,
        dlp_end_date    TEXT    NOT NULL,   -- ISO-8601 date string e.g. '2025-12-31'
        contract_value  REAL,               -- optional
        created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
    )
    """,
    # -----------------------------------------------------------------------
    # detections
    # -----------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS detections (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        road_segment_id     INTEGER REFERENCES road_segments(id) ON DELETE SET NULL,
        contract_id         INTEGER REFERENCES contracts(id)     ON DELETE SET NULL,
        gps_lat             REAL    NOT NULL,
        gps_lon             REAL    NOT NULL,
        severity            TEXT    NOT NULL,
        confidence          REAL    NOT NULL,
        bbox                TEXT    NOT NULL DEFAULT '[]',   -- JSON array [x1,y1,x2,y2]
        evidence_image_path TEXT,
        status              TEXT    NOT NULL DEFAULT 'PENDING',
        created_at          TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
        CHECK (severity IN ('damage_low', 'damage_medium', 'damage_high')),
        CHECK (status   IN ('PENDING', 'APPROVED', 'REJECTED')),
        CHECK (confidence BETWEEN 0.0 AND 1.0)
    )
    """,
    # -----------------------------------------------------------------------
    # notices
    # -----------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS notices (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        detection_id INTEGER NOT NULL REFERENCES detections(id) ON DELETE CASCADE,
        contract_id  INTEGER NOT NULL REFERENCES contracts(id)  ON DELETE CASCADE,
        pdf_path     TEXT    NOT NULL,
        generated_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
    )
    """,
]

# ---------------------------------------------------------------------------
# Indexes (separate from table DDL so they can be added safely)
# ---------------------------------------------------------------------------

_INDEXES: list[str] = [
    # Bounding-box spatial lookup on road_segments
    "CREATE INDEX IF NOT EXISTS idx_segs_bbox ON road_segments(gps_min_lat, gps_max_lat, gps_min_lon, gps_max_lon)",
    # detections filtering / sorting
    "CREATE INDEX IF NOT EXISTS idx_det_status     ON detections(status)",
    "CREATE INDEX IF NOT EXISTS idx_det_severity   ON detections(severity)",
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

    Pragmas applied per connection:
        PRAGMA journal_mode = WAL;    -- concurrent readers, one writer
        PRAGMA foreign_keys = ON;     -- enforce FK constraints
    """
    con: sqlite3.Connection = sqlite3.connect(db_path)
    try:
        con.execute("PRAGMA journal_mode = WAL")
        con.execute("PRAGMA foreign_keys = ON")

        with con:  # auto-commit on success, rollback on exception
            for ddl in _DDL:
                con.execute(ddl)
            for idx in _INDEXES:
                con.execute(idx)

        print(f"[schema] Database initialised at: {os.path.abspath(db_path)}")
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Script entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    path: str = (
        sys.argv[1]
        if len(sys.argv) > 1
        else os.environ.get("ARIA_DB_PATH", "./aria.db")
    )
    init_db(path)
