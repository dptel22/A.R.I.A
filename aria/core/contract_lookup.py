"""
core/contract_lookup.py — A.R.I.A. GPS-to-Contract Resolver
Maps GPS coordinates to a road segment and retrieves the active contract details.
"""

import sqlite3
from datetime import date

DB_PATH = "db/aria.db"


def lookup_contract(gps_lat: float, gps_lon: float, db_path: str = DB_PATH) -> dict | None:
    """
    Resolve GPS coordinates to a road segment and retrieve contract details.

    Queries the road_segments table to find a segment whose GPS bounding box
    contains the provided coordinates, then retrieves the most recent contract
    for that segment. Computes DLP (Defect Liability Period) status.

    Args:
        gps_lat (float): Latitude of the detected road_damage.
        gps_lon (float): Longitude of the detected road_damage.
        db_path (str): Path to the SQLite database file.

    Returns:
        dict with keys:
            - segment_id (str)
            - segment_name (str)
            - contract_id (str)
            - contractor_name (str)
            - contractor_email (str)
            - dlp_end_date (str): ISO date string
            - within_dlp (bool): True if current date is before dlp_end_date
            - days_remaining (int): Days until DLP expires (negative = expired)
        Returns None if no matching segment or contract is found.
    """
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # --- Step 1: Find the road segment containing these GPS coordinates ---
        cursor.execute(
            """
            SELECT segment_id, segment_name
            FROM road_segments
            WHERE gps_lat_min <= :lat AND :lat <= gps_lat_max
              AND gps_lon_min <= :lon AND :lon <= gps_lon_max
            LIMIT 1
            """,
            {"lat": gps_lat, "lon": gps_lon},
        )
        segment = cursor.fetchone()

        if segment is None:
            return None  # No matching road segment

        segment_id = segment["segment_id"]
        segment_name = segment["segment_name"]

        # --- Step 2: Find the most recent contract for that segment ---
        cursor.execute(
            """
            SELECT contract_id, contractor_name, contractor_email,
                   contract_start, dlp_end_date, contract_value_inr
            FROM contracts
            WHERE segment_id = :segment_id
            ORDER BY contract_start DESC
            LIMIT 1
            """,
            {"segment_id": segment_id},
        )
        contract = cursor.fetchone()

        if contract is None:
            return None  # No contract on record for this segment

        # --- Step 3: Compute DLP status ---
        today = date.today()
        dlp_end = date.fromisoformat(contract["dlp_end_date"])
        days_remaining = (dlp_end - today).days
        within_dlp = days_remaining > 0

        return {
            "segment_id": segment_id,
            "segment_name": segment_name,
            "contract_id": contract["contract_id"],
            "contractor_name": contract["contractor_name"],
            "contractor_email": contract["contractor_email"],
            "contract_value_inr": contract["contract_value_inr"],
            "dlp_end_date": contract["dlp_end_date"],
            "within_dlp": within_dlp,
            "days_remaining": days_remaining,
        }
