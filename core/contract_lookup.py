"""
core/contract_lookup.py — GPS-based Contract Lookup for A.R.I.A.
"""
from __future__ import annotations

import datetime
import logging
import sqlite3

from core.models import ContractStatus
from db.connection import get_connection

log: logging.Logger = logging.getLogger(__name__)


def find_contract_by_gps(lat: float, lon: float, db_path: str) -> ContractStatus | None:
    """
    Find the active contract for a given GPS coordinate.

    Args:
        lat: Latitude of the detection.
        lon: Longitude of the detection.
        db_path: Path to the SQLite database.

    Returns:
        A ContractStatus dataclass containing details and DLP active flag.
        Returns None if no contract is found for the GPS coordinate.
    """
    con = get_connection(db_path)
    try:
        con.row_factory = sqlite3.Row

        query = """
            SELECT
                rs.id AS segment_id,
                rs.name AS segment_name,
                c.id AS contract_id,
                c.contractor_name,
                c.contractor_email,
                c.dlp_end_date,
                c.contract_value
            FROM road_segments rs
            JOIN contracts c ON rs.id = c.road_segment_id
            WHERE ? BETWEEN rs.gps_min_lat AND rs.gps_max_lat
              AND ? BETWEEN rs.gps_min_lon AND rs.gps_max_lon
            ORDER BY c.created_at DESC -- get latest contract if multiple match
            LIMIT 1
        """
        row = con.execute(query, (lat, lon)).fetchone()

        if not row:
            log.info("No segment found for GPS (%.4f, %.4f)", lat, lon)
            return None

        result = dict(row)

        # Robustly calculate DLP status
        dlp_end_str = result.get("dlp_end_date")
        dlp_end_date: datetime.date | None = None
        is_dlp_active = False

        if dlp_end_str:
            try:
                # Primary parsing: YYYY-MM-DD
                dlp_end_date = datetime.datetime.strptime(
                    dlp_end_str, "%Y-%m-%d").date()
            except ValueError:
                try:
                    # Fallback parsing: ISO-8601 full string
                    dlp_end_date = datetime.datetime.fromisoformat(
                        dlp_end_str.replace('Z', '+00:00')).date()
                except (ValueError, TypeError) as e:
                    # Do not crash the system for a malformed DB date. Fail closed (DLP inactive).
                    log.error("Corrupted date format in DB for contract %s: %r. Error: %s",
                              result["contract_id"], dlp_end_str, e)

        if dlp_end_date:
            today = datetime.date.today()
            is_dlp_active = today <= dlp_end_date

            if is_dlp_active:
                log.info("Contract for %s active until %s",
                         result["contractor_name"], dlp_end_date)
            else:
                log.info("Contract for %s EXPIRED on %s",
                         result["contractor_name"], dlp_end_date)

        return ContractStatus(
            segment_id=result["segment_id"],
            segment_name=result["segment_name"],
            contract_id=result["contract_id"],
            contractor_name=result["contractor_name"],
            contractor_email=result["contractor_email"],
            dlp_end_date=dlp_end_date,
            is_dlp_active=is_dlp_active
        )

    except Exception as e:
        log.error("Failed to lookup contract by GPS: %s", e)
        raise
    finally:
        con.close()
