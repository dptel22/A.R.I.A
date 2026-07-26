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


def find_contract_matches_by_gps(
    lat: float,
    lon: float,
    db_path_or_connection: str | sqlite3.Connection,
) -> list[dict[str, object]]:
    close_connection = False
    if isinstance(db_path_or_connection, sqlite3.Connection):
        con = db_path_or_connection
    else:
        con = get_connection(db_path_or_connection)
        close_connection = True
    try:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            """
            SELECT
                rs.id AS segment_id,
                rs.name AS segment_name,
                c.id AS contract_id,
                c.contractor_name,
                c.contractor_email,
                c.dlp_end_date,
                c.contract_value,
                c.created_at AS contract_created_at
            FROM road_segments rs
            LEFT JOIN contracts c
              ON c.id = (
                SELECT c2.id
                FROM contracts c2
                WHERE c2.road_segment_id = rs.id
                ORDER BY c2.created_at DESC, c2.id DESC
                LIMIT 1
              )
            WHERE ? BETWEEN rs.gps_min_lat AND rs.gps_max_lat
              AND ? BETWEEN rs.gps_min_lon AND rs.gps_max_lon
            ORDER BY rs.id ASC
            """,
            (lat, lon),
        ).fetchall()

        matches: list[dict[str, object]] = []
        today = datetime.date.today()
        for row in rows:
            item = dict(row)
            dlp_end = None
            if item.get("dlp_end_date"):
                try:
                    dlp_end = datetime.datetime.strptime(str(item["dlp_end_date"]), "%Y-%m-%d").date()
                except ValueError:
                    dlp_end = None
            item["is_dlp_active"] = bool(dlp_end and today <= dlp_end)
            matches.append(item)
        return matches
    finally:
        if close_connection:
            con.close()
