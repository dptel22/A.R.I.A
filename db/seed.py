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

import os
import sqlite3
import sys
from typing import Any


# ---------------------------------------------------------------------------
# Seed data — 5 Bengaluru road segments + 5 contracts
# ---------------------------------------------------------------------------

# Each tuple maps to: (name, gps_min_lat, gps_max_lat, gps_min_lon, gps_max_lon)
_SEGMENTS: list[tuple[str, float, float, float, float]] = [
    ("Outer Ring Road - Marathahalli to Silk Board",
     12.9252, 12.9578, 77.6267, 77.6971),
    ("Hosur Road - Electronic City Phase 1",
     12.8399, 12.8652, 77.6746, 77.6985),
    ("Bellary Road - Hebbal to Yelahanka",
     13.0354, 13.1005, 77.5874, 77.6102),
    ("Mysuru Road - Kengeri to RR Nagar",
     12.9082, 12.9347, 77.5165, 77.5524),
    ("Old Madras Road - KR Puram to Tin Factory",
     12.9694, 12.9975, 77.6780, 77.7143),
]

# Each tuple maps to:
# (segment_idx_0based, contractor_name, contractor_email, dlp_end_date, contract_value)
# DLP states: expired (2024), expiring soon (within 90 days of today ~2026-03-06),
#             active (2027+)
_CONTRACTS: list[tuple[int, str, str, str, float | None]] = [
    (0, "Infratech Solutions Pvt Ltd",  "contracts@infratech.in",
     "2024-06-30",  48_50_000.0),   # EXPIRED
    (1, "BangaloreRoads Corp",          "work@bangaloreroads.co.in",
     "2026-03-31",  72_00_000.0),   # EXPIRING SOON (~25 days)
    (2, "NirmaaConsult Engineering",    "nirmaa@nirmaaengg.com",
     "2026-05-15",  95_50_000.0),   # EXPIRING SOON (~70 days)
    (3, "GreenPath Infra Ltd",          "tenders@greenpathinfra.com",
     "2027-12-31", 1_25_00_000.0),  # ACTIVE
    (4, "SkyBuild Infrastructure",      "ops@skybuild.in",
     "2028-06-30",  None),          # ACTIVE, value unknown
]

# A handful of detections to make join queries interesting
# Maps to: (seg_idx, contract_idx, lat, lon, severity, confidence, bbox_json, img_path, status)
_DETECTIONS: list[tuple[int, int, float, float, str, float, str, str | None, str]] = [
    (0, 0, 12.9310, 77.6450, "damage_high",   0.92,
     "[120,300,250,420]", "evidence/det_001.jpg", "APPROVED"),
    (1, 1, 12.8510, 77.6820, "damage_medium", 0.78,
     "[80,200,190,350]",  None,                   "PENDING"),
    (2, 2, 13.0600, 77.5950, "damage_low",    0.65,
     "[40,100,120,200]",  "evidence/det_003.jpg", "PENDING"),
    (3, 3, 12.9120, 77.5300, "damage_high",   0.88,
     "[200,400,350,550]", "evidence/det_004.jpg", "REJECTED"),
    (4, 4, 12.9800, 77.6950, "damage_medium", 0.71,
     "[60,150,180,300]",  None,                   "PENDING"),
]

# Notices — one per approved/rejected detection for demo purposes
_NOTICES: list[tuple[int, int, str]] = [
    (0, 0, "notices/notice_001.pdf"),  # detection 0, contract 0
    (3, 3, "notices/notice_004.pdf"),  # detection 3, contract 3
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_or_insert_segment(
    con: sqlite3.Connection,
    name: str,
    min_lat: float, max_lat: float,
    min_lon: float, max_lon: float,
) -> int:
    """Return existing segment id by name, or insert and return new id."""
    row = con.execute(
        "SELECT id FROM road_segments WHERE name = ?", (name,)
    ).fetchone()
    if row:
        return int(row[0])
    cur = con.execute(
        """INSERT INTO road_segments
               (name, gps_min_lat, gps_max_lat, gps_min_lon, gps_max_lon)
           VALUES (?, ?, ?, ?, ?)""",
        (name, min_lat, max_lat, min_lon, max_lon),
    )
    return int(cur.lastrowid)  # type: ignore[arg-type]


def _get_or_insert_contract(
    con: sqlite3.Connection,
    segment_id: int,
    contractor_name: str,
    contractor_email: str,
    dlp_end_date: str,
    contract_value: float | None,
) -> int:
    """Return existing contract id (matched on segment + contractor_name), or insert."""
    row = con.execute(
        "SELECT id FROM contracts WHERE road_segment_id = ? AND contractor_name = ?",
        (segment_id, contractor_name),
    ).fetchone()
    if row:
        return int(row[0])
    cur = con.execute(
        """INSERT INTO contracts
               (road_segment_id, contractor_name, contractor_email, dlp_end_date, contract_value)
           VALUES (?, ?, ?, ?, ?)""",
        (segment_id, contractor_name, contractor_email, dlp_end_date, contract_value),
    )
    return int(cur.lastrowid)  # type: ignore[arg-type]


def _get_or_insert_detection(
    con: sqlite3.Connection,
    segment_id: int,
    contract_id: int,
    lat: float, lon: float,
    severity: str,
    confidence: float,
    bbox: str,
    img_path: str | None,
    status: str,
) -> int:
    """Detect duplicates on (road_segment_id, gps_lat, gps_lon, severity)."""
    row = con.execute(
        """SELECT id FROM detections
           WHERE road_segment_id = ? AND gps_lat = ? AND gps_lon = ? AND severity = ?""",
        (segment_id, lat, lon, severity),
    ).fetchone()
    if row:
        return int(row[0])
    cur = con.execute(
        """INSERT INTO detections
               (road_segment_id, contract_id, gps_lat, gps_lon,
                severity, confidence, bbox, evidence_image_path, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (segment_id, contract_id, lat, lon, severity,
         confidence, bbox, img_path, status),
    )
    return int(cur.lastrowid)  # type: ignore[arg-type]


def _get_or_insert_notice(
    con: sqlite3.Connection,
    detection_id: int,
    contract_id: int,
    pdf_path: str,
) -> None:
    """Idempotent: skip if notice for this (detection_id, contract_id) already exists."""
    row = con.execute(
        "SELECT id FROM notices WHERE detection_id = ? AND contract_id = ?",
        (detection_id, contract_id),
    ).fetchone()
    if row:
        return
    con.execute(
        "INSERT INTO notices (detection_id, contract_id, pdf_path) VALUES (?, ?, ?)",
        (detection_id, contract_id, pdf_path),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def seed_db(db_path: str) -> None:
    """
    Insert representative Bengaluru data into the database at *db_path*.

    Fully idempotent: running this function multiple times will never
    produce duplicate rows — each helper checks for existence first.

    The database must already be initialised via ``init_db`` before seeding.
    """
    con: sqlite3.Connection = sqlite3.connect(db_path)
    try:
        con.execute("PRAGMA journal_mode = WAL")
        con.execute("PRAGMA foreign_keys = ON")

        with con:
            # --- segments ---------------------------------------------------
            seg_ids: list[int] = []
            for name, mn_lat, mx_lat, mn_lon, mx_lon in _SEGMENTS:
                seg_ids.append(_get_or_insert_segment(
                    con, name, mn_lat, mx_lat, mn_lon, mx_lon))

            # --- contracts --------------------------------------------------
            contract_ids: list[int] = []
            for seg_idx, c_name, c_email, dlp, value in _CONTRACTS:
                contract_ids.append(
                    _get_or_insert_contract(
                        con, seg_ids[seg_idx], c_name, c_email, dlp, value
                    )
                )

            # --- detections -------------------------------------------------
            detection_ids: list[int] = []
            for seg_idx, con_idx, lat, lon, sev, conf, bbox, img, status in _DETECTIONS:
                detection_ids.append(
                    _get_or_insert_detection(
                        con,
                        seg_ids[seg_idx],
                        contract_ids[con_idx],
                        lat, lon, sev, conf, bbox, img, status,
                    )
                )

            # --- notices ----------------------------------------------------
            for det_local_idx, con_local_idx, pdf in _NOTICES:
                _get_or_insert_notice(
                    con,
                    detection_ids[det_local_idx],
                    contract_ids[con_local_idx],
                    pdf,
                )

        print(f"[seed] Seed data loaded into: {os.path.abspath(db_path)}")

        # Quick count summary
        counts: dict[str, Any] = {}
        for table in ("road_segments", "contracts", "detections", "notices"):
            row = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            counts[table] = row[0] if row else 0
        for tbl, cnt in counts.items():
            print(f"  {tbl:<20}: {cnt} row(s)")

    finally:
        con.close()


# ---------------------------------------------------------------------------
# Script entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from db.schema import init_db  # ensure schema exists first

    path: str = (
        sys.argv[1]
        if len(sys.argv) > 1
        else os.environ.get("ARIA_DB_PATH", "./aria.db")
    )
    init_db(path)
    seed_db(path)
