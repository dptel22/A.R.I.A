"""
db/seed.py — A.R.I.A. Mock Data Seeder
Populates the database with realistic Bengaluru road segments and contracts.
Run this AFTER schema.py has been executed.
"""

import sqlite3
from datetime import date, timedelta

DB_PATH = "db/aria.db"

# Current date reference (2026-03-04)
TODAY = date(2026, 3, 4)


def seed_data(db_path: str = DB_PATH) -> None:
    """
    Seed the database with 5 Bengaluru road segments and 5 matching contracts.
    Contract DLP scenarios:
        - SEG001 / CON001 → within DLP (expires 2027-01-15)
        - SEG002 / CON002 → within DLP (expires 2026-11-30)
        - SEG003 / CON003 → DLP expired  (expired 2025-06-30)
        - SEG004 / CON004 → DLP expired  (expired 2024-12-31)
        - SEG005 / CON005 → expiring soon (expires 2026-04-02, ~29 days away)
    Clears existing seed data before inserting to allow re-runs.
    """
    segments = [
        {
            "segment_id": "SEG001",
            "segment_name": "MG Road, Block 4",
            "gps_lat_min": 12.9716,
            "gps_lat_max": 12.9760,
            "gps_lon_min": 77.6090,
            "gps_lon_max": 77.6180,
        },
        {
            "segment_id": "SEG002",
            "segment_name": "Outer Ring Road, Marathahalli Section",
            "gps_lat_min": 12.9560,
            "gps_lat_max": 12.9640,
            "gps_lon_min": 77.6970,
            "gps_lon_max": 77.7090,
        },
        {
            "segment_id": "SEG003",
            "segment_name": "Hosur Road, Electronic City Flyover Approach",
            "gps_lat_min": 12.8320,
            "gps_lat_max": 12.8450,
            "gps_lon_min": 77.6710,
            "gps_lon_max": 77.6820,
        },
        {
            "segment_id": "SEG004",
            "segment_name": "Whitefield Main Road, ITPL Stretch",
            "gps_lat_min": 12.9840,
            "gps_lat_max": 12.9920,
            "gps_lon_min": 77.7370,
            "gps_lon_max": 77.7480,
        },
        {
            "segment_id": "SEG005",
            "segment_name": "Old Airport Road, Domlur Junction",
            "gps_lat_min": 12.9590,
            "gps_lat_max": 12.9660,
            "gps_lon_min": 77.6380,
            "gps_lon_max": 77.6470,
        },
    ]

    contracts = [
        {
            "contract_id": "CON001",
            "segment_id": "SEG001",
            "contractor_name": "Larsen & Toubro Infrastructure Ltd",
            "contractor_email": "contracts@lti.co.in",
            "contract_start": "2024-01-15",
            "dlp_end_date": "2027-01-15",          # Within DLP — 3-year DLP
            "contract_value_inr": 48_50_00_000.0,  # ₹48.5 Cr
        },
        {
            "contract_id": "CON002",
            "segment_id": "SEG002",
            "contractor_name": "KMC Constructions Ltd",
            "contractor_email": "roads@kmccon.in",
            "contract_start": "2023-11-30",
            "dlp_end_date": "2026-11-30",          # Within DLP — ~9 months left
            "contract_value_inr": 31_20_00_000.0,  # ₹31.2 Cr
        },
        {
            "contract_id": "CON003",
            "segment_id": "SEG003",
            "contractor_name": "Nagarjuna Construction Company",
            "contractor_email": "infra@ncc.co.in",
            "contract_start": "2022-07-01",
            "dlp_end_date": "2025-06-30",          # DLP Expired — 9 months ago
            "contract_value_inr": 22_75_00_000.0,  # ₹22.75 Cr
        },
        {
            "contract_id": "CON004",
            "segment_id": "SEG004",
            "contractor_name": "Dilip Buildcon Ltd",
            "contractor_email": "projects@dilipbuildcon.com",
            "contract_start": "2022-01-01",
            "dlp_end_date": "2024-12-31",          # DLP Expired — 14+ months ago
            "contract_value_inr": 56_00_00_000.0,  # ₹56 Cr
        },
        {
            "contract_id": "CON005",
            "segment_id": "SEG005",
            "contractor_name": "AFCONS Infrastructure Ltd",
            "contractor_email": "roads@afcons.com",
            "contract_start": "2024-04-02",
            # Expiring in 29 days (edge case)
            "dlp_end_date": str(TODAY + timedelta(days=29)),
            "contract_value_inr": 18_90_00_000.0,  # ₹18.9 Cr
        },
    ]

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # Clear existing seed data to allow safe re-runs
        cursor.execute("DELETE FROM contracts")
        cursor.execute("DELETE FROM road_segments")

        # Insert road segments
        cursor.executemany(
            """
            INSERT INTO road_segments
                (segment_id, segment_name, gps_lat_min, gps_lat_max, gps_lon_min, gps_lon_max)
            VALUES
                (:segment_id, :segment_name, :gps_lat_min, :gps_lat_max, :gps_lon_min, :gps_lon_max)
            """,
            segments,
        )
        print(f"[seed] Inserted {len(segments)} road segments.")

        # Insert contracts
        cursor.executemany(
            """
            INSERT INTO contracts
                (contract_id, segment_id, contractor_name, contractor_email,
                 contract_start, dlp_end_date, contract_value_inr)
            VALUES
                (:contract_id, :segment_id, :contractor_name, :contractor_email,
                 :contract_start, :dlp_end_date, :contract_value_inr)
            """,
            contracts,
        )
        print(f"[seed] Inserted {len(contracts)} contracts.")

        conn.commit()
    print(f"[seed] Database seeded successfully at '{db_path}'.")


if __name__ == "__main__":
    seed_data()
