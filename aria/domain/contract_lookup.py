"""GPS-based contract lookup helpers for A.R.I.A."""
from __future__ import annotations

import datetime
import logging
import sqlite3

from aria.db.connection import get_connection
from aria.domain.models import ContractStatus

log: logging.Logger = logging.getLogger(__name__)


def find_contract_by_gps(lat: float, lon: float, db_path: str) -> ContractStatus | None:
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
                c.dlp_end_date
            FROM road_segments rs
            JOIN contracts c ON rs.id = c.road_segment_id
            WHERE ? BETWEEN rs.gps_min_lat AND rs.gps_max_lat
              AND ? BETWEEN rs.gps_min_lon AND rs.gps_max_lon
            ORDER BY c.created_at DESC
            LIMIT 1
        """
        row = con.execute(query, (lat, lon)).fetchone()

        if not row:
            log.info("No segment found for GPS (%.4f, %.4f)", lat, lon)
            return None

        result = dict(row)
        dlp_end_str = result.get("dlp_end_date")
        dlp_end_date: datetime.date | None = None
        is_dlp_active = False

        if dlp_end_str:
            try:
                dlp_end_date = datetime.datetime.strptime(dlp_end_str, "%Y-%m-%d").date()
            except ValueError:
                try:
                    dlp_end_date = datetime.datetime.fromisoformat(dlp_end_str.replace("Z", "+00:00")).date()
                except (ValueError, TypeError) as exc:
                    log.error(
                        "Corrupted date format in DB for contract %s: %r. Error: %s",
                        result["contract_id"],
                        dlp_end_str,
                        exc,
                    )

        if dlp_end_date:
            is_dlp_active = datetime.date.today() <= dlp_end_date

        return ContractStatus(
            segment_id=result["segment_id"],
            segment_name=result["segment_name"],
            contract_id=result["contract_id"],
            contractor_name=result["contractor_name"],
            contractor_email=result["contractor_email"],
            dlp_end_date=dlp_end_date,
            is_dlp_active=is_dlp_active,
        )

    except Exception as exc:
        log.error("Failed to lookup contract by GPS: %s", exc)
        raise
    finally:
        con.close()
