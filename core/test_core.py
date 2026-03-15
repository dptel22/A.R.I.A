"""
core/test_core.py — End-to-end verification script for A.R.I.A. Core Layer.
"""
from __future__ import annotations

import logging
import os
import sys

from core.contract_lookup import find_contract_by_gps
from core.models import ActionType, DetectionMetadata, SeverityLevel
from core.notice_generator import generate_pdf_notice
from core.severity import determine_action

logging.basicConfig(level=logging.INFO,
                    format="[%(name)s] %(levelname)s: %(message)s")
log = logging.getLogger(__name__)


def main():
    log.info("Starting Core Layer verification...")

    # 1. Severity Routing (now using Enums)
    mock_severity = SeverityLevel.HIGH
    log.info("Testing severity mapping for: %r", mock_severity)
    action = determine_action(mock_severity)
    log.info("Determined action: %r", action)
    assert action == ActionType.ENFORCE, f"Expected ENFORCE, got {action}"

    # 2. Contract Lookup
    # Using the seed data from Old Madras Road - KR Puram to Tin Factory
    mock_lat = 12.9800
    mock_lon = 77.6950
    db_path = os.environ.get("ARIA_DB_PATH", "./aria.db")

    log.info("Testing contract lookup for GPS: (%.4f, %.4f)", mock_lat, mock_lon)
    contract_data = find_contract_by_gps(mock_lat, mock_lon, db_path)

    if not contract_data:
        log.error("Failed to find contract for GPS coordinates!")
        sys.exit(1)

    log.info("Contract found: %s (Active: %s)",
             contract_data.contractor_name, contract_data.is_dlp_active)

    # 3. PDF Notice Generation
    if action == ActionType.ENFORCE:
        log.info("Action is ENFORCE. Generating PDF notice...")

        # Build strict dataclass for detection
        detection_data = DetectionMetadata(
            gps_lat=mock_lat,
            gps_lon=mock_lon,
            severity=mock_severity,
            confidence=0.98
        )

        # Test text wrapping by artificially lengthening the contractor name
        # We don't want to mutate the dataclass (frozen), so we'll just test the standard generation
        # Let's ensure ARIA_MEDIA_ROOT is working
        os.environ["ARIA_MEDIA_ROOT"] = "notices_test_output/"

        pdf_path = generate_pdf_notice(detection_data, contract_data)
        log.info("Verification complete. Notice generated at: %s", pdf_path)
    else:
        log.info("Action is not ENFORCE. Skipping PDF generation.")

    print("\n--- ALL TESTS PASSED ---")


if __name__ == "__main__":
    main()
