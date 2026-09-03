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
        segment_id              INTEGER REFERENCES road_segments(id) ON DELETE SET NULL,
        source_type             TEXT    NOT NULL DEFAULT 'manual_upload',
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
        CHECK (source_type IN ('manual_upload', 'citizen_submission', 'roadcam_survey')),
        CHECK (is_dlp_active_snapshot IN (0, 1))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS submission_batches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_type TEXT NOT NULL CHECK (source_type IN ('citizen_submission', 'roadcam_survey')),
        submitted_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
        status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'done', 'failed'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS raw_submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id INTEGER NOT NULL REFERENCES submission_batches(id),
        image_url TEXT NOT NULL,
        lat REAL NOT NULL,
        lng REAL NOT NULL,
        exif_lat REAL,
        exif_lng REAL,
        exif_timestamp TEXT,
        gps_mismatch_flag INTEGER NOT NULL DEFAULT 0 CHECK (gps_mismatch_flag IN (0, 1)),
        status TEXT NOT NULL DEFAULT 'unreviewed' CHECK (status IN ('unreviewed', 'promoted', 'dismissed')),
        dismiss_reason TEXT CHECK (dismiss_reason IN ('spam', 'duplicate', 'not_a_road_defect', 'other')),
        promoted_inspection_id INTEGER REFERENCES inspection_events(id),
        submitted_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
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
    # contract_documents  (authoritative contract PDFs, versioned per contract)
    # -----------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS contract_documents (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        contract_id    INTEGER NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
        version        INTEGER NOT NULL,                -- 1-based per contract
        effective_from TEXT    NOT NULL,                -- ISO date this version applies from
        superseded_at  TEXT,                            -- NULL while applicable
        file_name      TEXT    NOT NULL,
        file_hash      TEXT    NOT NULL UNIQUE,         -- SHA-256 hex digest
        file_path      TEXT    NOT NULL,
        status         TEXT    NOT NULL DEFAULT 'PROCESSING'
                       CHECK (status IN ('PROCESSING', 'READY', 'FAILED')),
        page_count     INTEGER,
        error          TEXT,
        created_at     TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
        UNIQUE (contract_id, version)
    )
    """,
    # -----------------------------------------------------------------------
    # document_chunks  (parsed + embedded chunks of a contract document)
    # -----------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS document_chunks (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id   INTEGER NOT NULL REFERENCES contract_documents(id) ON DELETE CASCADE,
        chunk_index   INTEGER NOT NULL,
        page          INTEGER NOT NULL,                 -- 1-based page number
        section       TEXT,
        clause        TEXT,
        text          TEXT    NOT NULL,
        embedding     BLOB,                           -- float32[768], NULL until embedded
        UNIQUE (document_id, chunk_index)
    )
    """,
    # -----------------------------------------------------------------------
    # document_chunks_fts  (BM25 lexical retrieval over chunk text)
    # -----------------------------------------------------------------------
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS document_chunks_fts USING fts5(
        text,
        content='document_chunks',
        content_rowid='id'
    )
    """,
    """
    CREATE TRIGGER IF NOT EXISTS document_chunks_fts_ai AFTER INSERT ON document_chunks BEGIN
        INSERT INTO document_chunks_fts(rowid, text) VALUES (new.id, new.text);
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS document_chunks_fts_ad AFTER DELETE ON document_chunks BEGIN
        INSERT INTO document_chunks_fts(document_chunks_fts, rowid, text)
        VALUES ('delete', old.id, old.text);
    END
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
    # -----------------------------------------------------------------------
    # contract_requirements  (human-approved facts extracted from a contract
    # document, used ONLY by the deterministic notice template. A row is not
    # authoritative until an engineer sets status='approved'; the notice
    # generator falls back to hard-coded literals otherwise.)
    # -----------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS contract_requirements (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        contract_id     INTEGER NOT NULL REFERENCES contracts(id)       ON DELETE CASCADE,
        document_id     INTEGER NOT NULL REFERENCES contract_documents(id) ON DELETE CASCADE,
        field           TEXT    NOT NULL,   -- e.g. repair_hours / restoration_days / dlp_months
                                            --      security_deposit_percent / blacklist_years
                                            --      ld_per_day / max_ld_pct
        value_text      TEXT    NOT NULL,
        status          TEXT    NOT NULL DEFAULT 'proposed'
                        CHECK (status IN ('proposed', 'approved', 'rejected')),
        page            INTEGER NOT NULL,   -- 1-based source page
        clause          TEXT,
        quote           TEXT    NOT NULL,   -- verbatim supporting quote from the source chunk
        source_chunk_id INTEGER NOT NULL REFERENCES document_chunks(id) ON DELETE CASCADE,
        created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
        reviewed_at     TEXT,
        reviewed_by     TEXT,               -- API-key hash for audit trail
        UNIQUE (document_id, field)
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
    "CREATE INDEX IF NOT EXISTS idx_raw_submissions_status ON raw_submissions(status)",
    "CREATE INDEX IF NOT EXISTS idx_raw_submissions_batch ON raw_submissions(batch_id)",
    "CREATE INDEX IF NOT EXISTS idx_raw_submissions_promoted_inspection ON raw_submissions(promoted_inspection_id)",
    "CREATE INDEX IF NOT EXISTS idx_raw_submissions_submitted_at ON raw_submissions(submitted_at)",
    # contract documents / chunks
    "CREATE INDEX IF NOT EXISTS idx_cd_contract   ON contract_documents(contract_id)",
    "CREATE INDEX IF NOT EXISTS idx_dc_document   ON document_chunks(document_id)",
    # contract requirements
    "CREATE INDEX IF NOT EXISTS idx_cr_contract   ON contract_requirements(contract_id)",
    "CREATE INDEX IF NOT EXISTS idx_cr_document   ON contract_requirements(document_id)",
]


_INSPECTION_EVENT_COLUMNS: dict[str, str] = {
    "pipeline_status": "ALTER TABLE inspection_events ADD COLUMN pipeline_status TEXT NOT NULL DEFAULT 'NO_DETECTIONS'",
    "failure_reason": "ALTER TABLE inspection_events ADD COLUMN failure_reason TEXT",
    "contract_id_snapshot": "ALTER TABLE inspection_events ADD COLUMN contract_id_snapshot INTEGER REFERENCES contracts(id) ON DELETE SET NULL",
    "contractor_name_snapshot": "ALTER TABLE inspection_events ADD COLUMN contractor_name_snapshot TEXT",
    "contractor_email_snapshot": "ALTER TABLE inspection_events ADD COLUMN contractor_email_snapshot TEXT",
    "dlp_end_date_snapshot": "ALTER TABLE inspection_events ADD COLUMN dlp_end_date_snapshot TEXT",
    "is_dlp_active_snapshot": "ALTER TABLE inspection_events ADD COLUMN is_dlp_active_snapshot INTEGER NOT NULL DEFAULT 0",
    "source_type": "ALTER TABLE inspection_events ADD COLUMN source_type TEXT NOT NULL DEFAULT 'manual_upload'",
    "document_version_id": "ALTER TABLE inspection_events ADD COLUMN document_version_id INTEGER REFERENCES contract_documents(id) ON DELETE SET NULL",
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


def _inspection_segment_is_nullable(con) -> bool:
    for row in con.execute("PRAGMA table_info(inspection_events)").fetchall():
        if row[1] == "segment_id":
            return int(row[3]) == 0
    return True


def _rebuild_inspection_events_table_for_intake(con) -> None:
    if "inspection_events" not in {
        row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    }:
        return
    existing_columns = _get_existing_columns(con, "inspection_events")
    if _inspection_segment_is_nullable(con) and "source_type" in existing_columns:
        return

    log.info("Migrating inspection_events for nullable segment_id and source_type.")
    foreign_keys_enabled = int(con.execute("PRAGMA foreign_keys").fetchone()[0])
    if foreign_keys_enabled:
        con.execute("PRAGMA foreign_keys = OFF")

    try:
        with con:
            con.execute(
                """
                CREATE TABLE inspection_events__new (
                    id                      INTEGER PRIMARY KEY,
                    segment_id              INTEGER REFERENCES road_segments(id) ON DELETE SET NULL,
                    source_type             TEXT    NOT NULL DEFAULT 'manual_upload',
                    inspector_id            TEXT,
                    lat                     REAL    NOT NULL,
                    lng                     REAL    NOT NULL,
                    image_path              TEXT,
                    pipeline_status         TEXT    NOT NULL DEFAULT 'NO_DETECTIONS',
                    failure_reason          TEXT,
                    contract_id_snapshot    INTEGER REFERENCES contracts(id) ON DELETE SET NULL,
                    contractor_name_snapshot TEXT,
                    contractor_email_snapshot TEXT,
                    dlp_end_date_snapshot   TEXT,
                    is_dlp_active_snapshot  INTEGER NOT NULL DEFAULT 0,
                    created_at              TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                    CHECK (pipeline_status IN ('SUCCEEDED', 'NO_DETECTIONS', 'FAILED')),
                    CHECK (source_type IN ('manual_upload', 'citizen_submission', 'roadcam_survey')),
                    CHECK (is_dlp_active_snapshot IN (0, 1))
                )
                """
            )
            target_columns = [
                "id", "segment_id", "source_type", "inspector_id", "lat", "lng", "image_path",
                "pipeline_status", "failure_reason", "contract_id_snapshot",
                "contractor_name_snapshot", "contractor_email_snapshot", "dlp_end_date_snapshot",
                "is_dlp_active_snapshot", "created_at",
            ]
            _nullable_defaults = {
                "source_type": "'manual_upload'",
                "pipeline_status": "'NO_DETECTIONS'",
                "is_dlp_active_snapshot": "0",
            }
            select_exprs = [
                col if col in existing_columns and col not in _nullable_defaults else (
                    f"COALESCE({col}, {_nullable_defaults[col]})" if col in existing_columns
                    else _nullable_defaults.get(col, "NULL")
                )
                for col in target_columns
            ]
            con.execute(
                f"""
                INSERT INTO inspection_events__new ({", ".join(target_columns)})
                SELECT {", ".join(select_exprs)}
                FROM inspection_events
                """
            )
            con.execute("DROP TABLE inspection_events")
            con.execute("ALTER TABLE inspection_events__new RENAME TO inspection_events")
    finally:
        if foreign_keys_enabled:
            con.execute("PRAGMA foreign_keys = ON")


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
        _rebuild_inspection_events_table_for_intake(con)

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
