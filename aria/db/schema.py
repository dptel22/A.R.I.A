"""
db/schema.py — A.R.I.A. SQLite Schema
Creates all database tables if they do not already exist.
"""

import sqlite3

DB_PATH = "db/aria.db"


def create_tables(db_path: str = DB_PATH) -> None:
    """
    Create all A.R.I.A. tables inside the SQLite database.
    Tables:
        - road_segments
        - contracts
        - detections
        - notices
    Safe to re-run (uses CREATE TABLE IF NOT EXISTS).
    """
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # -----------------------------------------------------------
        # road_segments: geographic bounding boxes for road segments
        # -----------------------------------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS road_segments (
                segment_id      TEXT PRIMARY KEY,
                segment_name    TEXT NOT NULL,
                gps_lat_min     REAL NOT NULL,
                gps_lat_max     REAL NOT NULL,
                gps_lon_min     REAL NOT NULL,
                gps_lon_max     REAL NOT NULL
            )
        """)

        # -----------------------------------------------------------
        # contracts: contractor agreements tied to road segments
        # -----------------------------------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contracts (
                contract_id         TEXT PRIMARY KEY,
                segment_id          TEXT NOT NULL REFERENCES road_segments(segment_id),
                contractor_name     TEXT NOT NULL,
                contractor_email    TEXT NOT NULL,
                contract_start      DATE NOT NULL,
                dlp_end_date        DATE NOT NULL,
                contract_value_inr  REAL NOT NULL
            )
        """)

        # -----------------------------------------------------------
        # detections: road_damage events captured by the YOLO pipeline
        # -----------------------------------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS detections (
                detection_id    TEXT PRIMARY KEY,
                segment_id      TEXT,
                contract_id     TEXT,
                timestamp       TEXT NOT NULL,
                gps_lat         REAL NOT NULL,
                gps_lon         REAL NOT NULL,
                severity        TEXT NOT NULL,       -- LOW / MEDIUM / HIGH
                confidence      REAL NOT NULL,       -- YOLO confidence score 0.0–1.0
                bbox_json       TEXT,                -- JSON "[x1, y1, x2, y2]"
                frame_path      TEXT,                -- path to saved evidence frame
                within_dlp      INTEGER NOT NULL,    -- 1 = within DLP, 0 = expired
                status          TEXT NOT NULL DEFAULT 'PENDING'  -- PENDING / APPROVED / REJECTED
            )
        """)

        # -----------------------------------------------------------
        # notices: PDF enforcement notices generated after approval
        # -----------------------------------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notices (
                notice_id       TEXT PRIMARY KEY,
                detection_id    TEXT NOT NULL REFERENCES detections(detection_id),
                contract_id     TEXT NOT NULL,
                generated_at    TEXT NOT NULL,
                pdf_path        TEXT,
                approved_by     TEXT,
                approved_at     TEXT,
                status          TEXT NOT NULL DEFAULT 'DRAFT'   -- DRAFT / APPROVED / SENT
            )
        """)

        conn.commit()
        print(
            f"[schema] All tables created (or already exist) in '{db_path}'.")


if __name__ == "__main__":
    create_tables()
