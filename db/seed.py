"""
db/seed.py — A.R.I.A. idempotent seed data loader.

Exposes:
    seed_db(db_path: str) -> None

Run as a script:
    python -m db.seed [optional_path]
Env override:
    ARIA_DB_PATH=./aria.db python -m db.seed
"""
from __future__ import annotations

import datetime
import logging
import os
import sqlite3
import sys

from db.connection import get_connection

log: logging.Logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

# (name, ward_id, zone_id, gps_min_lat, gps_max_lat, gps_min_lon, gps_max_lon)
_SEGMENTS: list[tuple[str, str, str, float, float, float, float]] = [
    ("Outer Ring Road - Marathahalli to Silk Board",
     "W-150", "East",       12.9252, 12.9578, 77.6267, 77.6971),
    ("Hosur Road - Electronic City Phase 1",
     "W-193", "Bommanahalli", 12.8399, 12.8652, 77.6746, 77.6985),
    ("Bellary Road - Hebbal to Yelahanka",
     "W-004", "Yelahanka",  13.0354, 13.1005, 77.5874, 77.6102),
    ("Mysuru Road - Kengeri to RR Nagar",
     "W-128", "RR Nagar",   12.9082, 12.9347, 77.5165, 77.5524),
    ("Old Madras Road - KR Puram to Tin Factory",
     "W-082", "Mahadevapura", 12.9694, 12.9975, 77.6780, 77.7143),
]

# (segment_idx, contractor_name, contractor_email, dlp_end_date, contract_value_INR)
_CONTRACTS: list[tuple[int, str, str, str, float | None]] = [
    (0, "Infratech Solutions Pvt Ltd",  "contracts@infratech.in",
     "2024-06-30",  4_850_000.0),    # ₹48.5 lakh  — EXPIRED
    (1, "BangaloreRoads Corp",          "work@bangaloreroads.co.in",
     "2026-03-31",  7_200_000.0),    # ₹72 lakh    — EXPIRING SOON
    (2, "NirmaaConsult Engineering",    "nirmaa@nirmaaengg.com",
     "2026-05-15",  9_550_000.0),    # ₹95.5 lakh  — EXPIRING SOON
    (3, "GreenPath Infra Ltd",          "tenders@greenpathinfra.com",
     "2027-12-31", 12_500_000.0),    # ₹1.25 crore — ACTIVE
    (4, "SkyBuild Infrastructure",      "ops@skybuild.in",
     "2028-06-30",  None),           # value unknown — ACTIVE
]

# Sample inspection events: (segment_idx, lat, lng)
_INSPECTIONS: list[tuple[int, float, float]] = [
    (0, 12.9310, 77.6450),
    (1, 12.8510, 77.6820),
    (2, 13.0600, 77.5950),
    (3, 12.9120, 77.5300),
    (4, 12.9800, 77.6950),
]

# Sample detections: (inspection_idx, class_name, confidence, bbox_x, bbox_y, bbox_w, bbox_h, severity_score, severity_level)
_DETECTIONS: list[tuple[int, str, float, float, float, float, float, float, str]] = [
    (0, "pothole",            0.92, 0.45, 0.60, 0.12, 0.15, 7.36, "CRITICAL"),
    (0, "alligator_crack",    0.78, 0.20, 0.35, 0.18, 0.10, 3.54, "MEDIUM"),
    (1, "transverse_crack",   0.65, 0.55, 0.40, 0.08, 0.05, 2.08, "MEDIUM"),
    (2, "longitudinal_crack", 0.71, 0.30, 0.70, 0.04, 0.20, 1.08, "LOW"),
    (3, "pothole",            0.88, 0.60, 0.50, 0.15, 0.18, 6.16, "CRITICAL"),
    (3, "pothole",            0.55, 0.25, 0.30, 0.08, 0.10, 4.32, "HIGH"),
    (4, "alligator_crack",    0.82, 0.40, 0.45, 0.20, 0.12, 3.72, "MEDIUM"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _upsert_segment(
    con: sqlite3.Connection,
    name: str, ward_id: str, zone_id: str,
    min_lat: float, max_lat: float,
    min_lon: float, max_lon: float,
) -> int:
    """Insert segment if name doesn't exist (UNIQUE enforced by DB), return id."""
    con.execute(
        """INSERT OR IGNORE INTO road_segments
               (name, ward_id, zone_id, gps_min_lat, gps_max_lat, gps_min_lon, gps_max_lon)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (name, ward_id, zone_id, min_lat, max_lat, min_lon, max_lon),
    )
    row = con.execute(
        "SELECT id FROM road_segments WHERE name = ?", (name,)
    ).fetchone()
    assert row is not None, f"road_segments row for {name!r} must exist after INSERT OR IGNORE"
    return int(row[0])


def _upsert_contract(
    con: sqlite3.Connection,
    segment_id: int,
    contractor_name: str,
    contractor_email: str,
    dlp_end_date: str,
    contract_value: float | None,
) -> int:
    """Insert a contract once per exact seed payload, return its id."""
    row = con.execute(
        """
        SELECT id
        FROM contracts
        WHERE road_segment_id = ?
          AND contractor_name = ?
          AND contractor_email = ?
          AND dlp_end_date = ?
          AND (
                contract_value = ?
                OR (contract_value IS NULL AND ? IS NULL)
          )
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (
            segment_id,
            contractor_name,
            contractor_email,
            dlp_end_date,
            contract_value,
            contract_value,
        ),
    ).fetchone()
    if row is not None:
        return int(row[0])

    cur = con.execute(
        """
        INSERT INTO contracts (
            road_segment_id,
            contractor_name,
            contractor_email,
            dlp_end_date,
            contract_value
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (segment_id, contractor_name, contractor_email, dlp_end_date, contract_value),
    )
    assert cur.lastrowid is not None, "contract row must exist after insert"
    return int(cur.lastrowid)


def _insert_inspection(
    con: sqlite3.Connection,
    segment_id: int,
    lat: float, lng: float,
    pipeline_status: str,
    contract_id_snapshot: int | None = None,
    contractor_name_snapshot: str | None = None,
    contractor_email_snapshot: str | None = None,
    dlp_end_date_snapshot: str | None = None,
    is_dlp_active_snapshot: bool = False,
) -> int:
    """Insert inspection event, return id. Not idempotent — each seed run adds new events."""
    cur = con.execute(
        """
        INSERT INTO inspection_events (
            segment_id,
            lat,
            lng,
            pipeline_status,
            contract_id_snapshot,
            contractor_name_snapshot,
            contractor_email_snapshot,
            dlp_end_date_snapshot,
            is_dlp_active_snapshot
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            segment_id,
            lat,
            lng,
            pipeline_status,
            contract_id_snapshot,
            contractor_name_snapshot,
            contractor_email_snapshot,
            dlp_end_date_snapshot,
            int(is_dlp_active_snapshot),
        ),
    )
    assert cur.lastrowid is not None
    return cur.lastrowid


def _insert_detection(
    con: sqlite3.Connection,
    inspection_event_id: int,
    class_name: str, confidence: float,
    bbox_x: float, bbox_y: float, bbox_w: float, bbox_h: float,
    severity_score: float, severity_level: str,
) -> int:
    """Insert detection row, return id."""
    cur = con.execute(
        """INSERT INTO detections
               (inspection_event_id, class_name, confidence,
                bbox_x, bbox_y, bbox_w, bbox_h,
                severity_score, severity_level)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (inspection_event_id, class_name, confidence,
         bbox_x, bbox_y, bbox_w, bbox_h,
         severity_score, severity_level),
    )
    assert cur.lastrowid is not None
    return cur.lastrowid


# ---------------------------------------------------------------------------
# Allowed table names for count queries
# ---------------------------------------------------------------------------

_TABLES: tuple[str, ...] = (
    "road_segments", "contracts", "inspection_events", "detections", "notices")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def seed_db(db_path: str) -> None:
    """
    Insert representative Bengaluru data into the database at *db_path*.

    Segments and exact contract seed records are idempotent.
    Inspection events and detections are NOT idempotent — to avoid
    duplicate seed data, delete aria.db before re-seeding.

    The database must already be initialised via ``init_db`` before seeding.
    """
    con = get_connection(db_path)
    try:
        # Check if we already have inspection events — skip if so
        existing = con.execute("SELECT COUNT(*) FROM inspection_events").fetchone()
        if existing and existing[0] > 0:
            log.info("Seed data already present (%d inspection events). Skipping.", existing[0])
            # Still print counts
            for table in _TABLES:
                row = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
                log.info("  %-25s: %d row(s)", table, row[0] if row else 0)
            return

        with con:
            # --- segments ---------------------------------------------------
            seg_ids: list[int] = []
            for name, ward, zone, mn_lat, mx_lat, mn_lon, mx_lon in _SEGMENTS:
                seg_ids.append(
                    _upsert_segment(con, name, ward, zone, mn_lat, mx_lat, mn_lon, mx_lon)
                )

            # --- contracts --------------------------------------------------
            contract_ids: list[int] = []
            for seg_idx, c_name, c_email, dlp, value in _CONTRACTS:
                contract_ids.append(
                    _upsert_contract(
                        con, seg_ids[seg_idx], c_name, c_email, dlp, value
                    )
                )

            # --- inspection events ------------------------------------------
            ie_ids: list[int] = []
            for seg_idx, lat, lng in _INSPECTIONS:
                _, contractor_name, contractor_email, dlp_end_date, _ = _CONTRACTS[seg_idx]
                is_dlp_active = datetime.date.today() <= datetime.date.fromisoformat(dlp_end_date)
                ie_ids.append(
                    _insert_inspection(
                        con,
                        seg_ids[seg_idx],
                        lat,
                        lng,
                        pipeline_status="SUCCEEDED",
                        contract_id_snapshot=contract_ids[seg_idx],
                        contractor_name_snapshot=contractor_name,
                        contractor_email_snapshot=contractor_email,
                        dlp_end_date_snapshot=dlp_end_date,
                        is_dlp_active_snapshot=is_dlp_active,
                    )
                )

            # --- detections -------------------------------------------------
            for ie_idx, cls, conf, bx, by, bw, bh, score, level in _DETECTIONS:
                _insert_detection(
                    con, ie_ids[ie_idx],
                    cls, conf, bx, by, bw, bh, score, level,
                )

        log.info("Seed data loaded into: %s", os.path.abspath(db_path))

        # Quick count summary
        for table in _TABLES:
            row = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            log.info("  %-25s: %d row(s)", table, row[0] if row else 0)

    finally:
        con.close()


# ---------------------------------------------------------------------------
# Script entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format="[%(name)s] %(message)s")

    from db.schema import init_db  # ensure schema exists first

    path: str = (
        sys.argv[1]
        if len(sys.argv) > 1
        else os.environ.get("ARIA_DB_PATH", "./aria.db")
    )
    init_db(path)
    seed_db(path)
