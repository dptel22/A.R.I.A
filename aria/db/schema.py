"""
aria/db/schema.py - A.R.I.A. SQLite schema initializer.

Exposes:
    init_db(db_path: str) -> None

Run as a script:
    python -m aria.db.schema [optional_path]
Env override:
    ARIA_DB_PATH=./runtime/db/aria.db python -m aria.db.schema
"""
from __future__ import annotations

import logging
import os
import sys

from aria.db.connection import get_connection

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
        created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
    )
    """,
    # -----------------------------------------------------------------------
    # inspection_events  (parent of detections — one image = one event)
    # -----------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS inspection_events (
        id                      INTEGER PRIMARY KEY,
        segment_id              INTEGER NOT NULL REFERENCES road_segments(id) ON DELETE CASCADE,
        inspector_id            TEXT,              -- API key hash or worker ID for audit trail
        lat                     REAL    NOT NULL,
        lng                     REAL    NOT NULL,
        image_path              TEXT,               -- optional, if saved to disk
        pipeline_status         TEXT    NOT NULL DEFAULT 'NO_DETECTIONS',
        failure_reason          TEXT,
        contract_id_snapshot    INTEGER REFERENCES contracts(id) ON DELETE SET NULL,
        contractor_name_snapshot TEXT,
        contractor_email_snapshot TEXT,
        dlp_end_date_snapshot   TEXT,
        is_dlp_active_snapshot  INTEGER NOT NULL DEFAULT 0,
        created_at              TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
        CHECK (pipeline_status IN ('SUCCEEDED', 'NO_DETECTIONS', 'FAILED')),
        CHECK (is_dlp_active_snapshot IN (0, 1))
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
    "CREATE INDEX IF NOT EXISTS idx_ie_pipeline_status ON inspection_events(pipeline_status)",
    # detections filtering
    "CREATE INDEX IF NOT EXISTS idx_det_ie        ON detections(inspection_event_id)",
    "CREATE INDEX IF NOT EXISTS idx_det_severity  ON detections(severity_level)",
    "CREATE INDEX IF NOT EXISTS idx_det_created_at ON detections(created_at)",
]


_INSPECTION_EVENT_COLUMNS: dict[str, str] = {
    "pipeline_status": "ALTER TABLE inspection_events ADD COLUMN pipeline_status TEXT NOT NULL DEFAULT 'NO_DETECTIONS'",
    "failure_reason": "ALTER TABLE inspection_events ADD COLUMN failure_reason TEXT",
    "contract_id_snapshot": "ALTER TABLE inspection_events ADD COLUMN contract_id_snapshot INTEGER REFERENCES contracts(id) ON DELETE SET NULL",
    "contractor_name_snapshot": "ALTER TABLE inspection_events ADD COLUMN contractor_name_snapshot TEXT",
    "contractor_email_snapshot": "ALTER TABLE inspection_events ADD COLUMN contractor_email_snapshot TEXT",
    "dlp_end_date_snapshot": "ALTER TABLE inspection_events ADD COLUMN dlp_end_date_snapshot TEXT",
    "is_dlp_active_snapshot": "ALTER TABLE inspection_events ADD COLUMN is_dlp_active_snapshot INTEGER NOT NULL DEFAULT 0",
}


def _get_existing_columns(con, table_name: str) -> set[str]:
    return {
        row[1]
        for row in con.execute(f"PRAGMA table_info({table_name})").fetchall()
    }


def _ensure_inspection_event_columns(con) -> None:
    existing_columns = _get_existing_columns(con, "inspection_events")
    for column_name, ddl in _INSPECTION_EVENT_COLUMNS.items():
        if column_name not in existing_columns:
            con.execute(ddl)


def _index_columns(con, index_name: str) -> list[str]:
    return [row[2] for row in con.execute(f"PRAGMA index_info('{index_name}')").fetchall()]


def _has_legacy_contract_uniqueness(con) -> bool:
    existing_tables = {
        row[0]
        for row in con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    if "contracts" not in existing_tables:
        return False

    for row in con.execute("PRAGMA index_list('contracts')").fetchall():
        is_unique = bool(row[2])
        if not is_unique:
            continue
        index_name = row[1]
        if _index_columns(con, index_name) == ["road_segment_id", "contractor_name"]:
            return True
    return False


def _rebuild_contracts_table_without_legacy_uniqueness(con) -> None:
    log.info("Migrating contracts table to allow repeat awards on the same road segment.")
    foreign_keys_enabled = int(con.execute("PRAGMA foreign_keys").fetchone()[0])

    if foreign_keys_enabled:
        con.execute("PRAGMA foreign_keys = OFF")

    try:
        with con:
            con.execute(
                """
                CREATE TABLE contracts__new (
                    id               INTEGER PRIMARY KEY,
                    road_segment_id  INTEGER NOT NULL REFERENCES road_segments(id) ON DELETE CASCADE,
                    contractor_name  TEXT    NOT NULL,
                    contractor_email TEXT    NOT NULL,
                    dlp_end_date     TEXT    NOT NULL,
                    contract_value   REAL,
                    created_at       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
                )
                """
            )
            con.execute(
                """
                INSERT INTO contracts__new (
                    id,
                    road_segment_id,
                    contractor_name,
                    contractor_email,
                    dlp_end_date,
                    contract_value,
                    created_at
                )
                SELECT
                    id,
                    road_segment_id,
                    contractor_name,
                    contractor_email,
                    dlp_end_date,
                    contract_value,
                    created_at
                FROM contracts
                """
            )
            con.execute("DROP TABLE contracts")
            con.execute("ALTER TABLE contracts__new RENAME TO contracts")
    finally:
        if foreign_keys_enabled:
            con.execute("PRAGMA foreign_keys = ON")


def _backfill_inspection_event_accountability(con) -> None:
    con.execute(
        """
        UPDATE inspection_events
        SET pipeline_status = CASE
            WHEN pipeline_status = 'FAILED' THEN 'FAILED'
            WHEN EXISTS (
                SELECT 1
                FROM detections d
                WHERE d.inspection_event_id = inspection_events.id
            ) THEN 'SUCCEEDED'
            ELSE 'NO_DETECTIONS'
        END
        WHERE pipeline_status IS NULL
           OR pipeline_status = ''
           OR (
                pipeline_status = 'NO_DETECTIONS'
                AND EXISTS (
                    SELECT 1
                    FROM detections d
                    WHERE d.inspection_event_id = inspection_events.id
                )
            )
           OR (
                pipeline_status = 'SUCCEEDED'
                AND NOT EXISTS (
                    SELECT 1
                    FROM detections d
                    WHERE d.inspection_event_id = inspection_events.id
                )
            )
        """
    )

    con.execute(
        """
        UPDATE inspection_events
        SET contract_id_snapshot = COALESCE(
                contract_id_snapshot,
                (
                    SELECT c.id
                    FROM contracts c
                    WHERE c.road_segment_id = inspection_events.segment_id
                    ORDER BY c.created_at DESC, c.id DESC
                    LIMIT 1
                )
            ),
            contractor_name_snapshot = COALESCE(
                contractor_name_snapshot,
                (
                    SELECT c.contractor_name
                    FROM contracts c
                    WHERE c.road_segment_id = inspection_events.segment_id
                    ORDER BY c.created_at DESC, c.id DESC
                    LIMIT 1
                )
            ),
            contractor_email_snapshot = COALESCE(
                contractor_email_snapshot,
                (
                    SELECT c.contractor_email
                    FROM contracts c
                    WHERE c.road_segment_id = inspection_events.segment_id
                    ORDER BY c.created_at DESC, c.id DESC
                    LIMIT 1
                )
            ),
            dlp_end_date_snapshot = COALESCE(
                dlp_end_date_snapshot,
                (
                    SELECT c.dlp_end_date
                    FROM contracts c
                    WHERE c.road_segment_id = inspection_events.segment_id
                    ORDER BY c.created_at DESC, c.id DESC
                    LIMIT 1
                )
            ),
            is_dlp_active_snapshot = CASE
                WHEN contract_id_snapshot IS NULL
                 AND contractor_name_snapshot IS NULL
                 AND contractor_email_snapshot IS NULL
                 AND dlp_end_date_snapshot IS NULL THEN COALESCE(
                    (
                        SELECT CASE
                            WHEN c.dlp_end_date IS NOT NULL
                             AND date(c.dlp_end_date) >= date('now') THEN 1
                            ELSE 0
                        END
                        FROM contracts c
                        WHERE c.road_segment_id = inspection_events.segment_id
                        ORDER BY c.created_at DESC, c.id DESC
                        LIMIT 1
                    ),
                    0
                )
                ELSE is_dlp_active_snapshot
            END
        """
    )

    con.execute(
        """
        UPDATE inspection_events
        SET is_dlp_active_snapshot = 0
        WHERE is_dlp_active_snapshot IS NULL
        """
    )


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
        if _has_legacy_contract_uniqueness(con):
            _rebuild_contracts_table_without_legacy_uniqueness(con)

        with con:  # auto-commit on success, rollback on exception
            for ddl in _DDL:
                con.execute(ddl)
            _ensure_inspection_event_columns(con)
            _backfill_inspection_event_accountability(con)
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
        else os.environ.get("ARIA_DB_PATH", "./runtime/db/aria.db")
    )
    init_db(path)
