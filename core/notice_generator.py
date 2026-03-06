"""
core/notice_generator.py — PDF Generation for A.R.I.A. Enforcement Notices.
"""
from __future__ import annotations

import datetime
import logging
import os
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

log: logging.Logger = logging.getLogger(__name__)


def generate_pdf_notice(detection_data: dict[str, Any], contract_data: dict[str, Any], output_dir: str = "notices/") -> str:
    """
    Generate an official, legally-binding enforcement notice PDF from the GBA.

    Args:
        detection_data: Dictionary containing detection details (severity, gps_lat, gps_lon).
        contract_data: Dictionary containing contract details (contractor_name, dlp_end_date, is_dlp_active).
        output_dir: Directory to save the generated PDF.

    Returns:
        The absolute path to the generated PDF file.
    """
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    contractor_slug = contract_data.get(
        'contractor_name', 'Unknown').replace(" ", "_").replace("/", "_")
    filename = f"Notice_{contractor_slug}_{timestamp}.pdf"

    # Handle absolute vs relative path for output
    if not os.path.isabs(output_dir):
        project_root = os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))
        output_dir = os.path.join(project_root, output_dir)
        os.makedirs(output_dir, exist_ok=True)

    pdf_path = os.path.join(output_dir, filename)

    try:
        c = canvas.Canvas(pdf_path, pagesize=A4)
        width, height = A4

        margins = 1.0 * inch
        current_y = height - margins

        # 1. Official Header (GBA)
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(width / 2.0, current_y,
                            "GREATER BENGALURU AUTHORITY (GBA)")
        current_y -= 0.3 * inch

        c.setFont("Helvetica", 12)
        c.drawCentredString(
            width / 2.0, current_y, "Office of the Executive Engineer, East Zone City Corporation")
        current_y -= 0.4 * inch

        # Line separator
        c.line(margins, current_y, width - margins, current_y)
        current_y -= 0.5 * inch

        # 2. Date and Reference
        c.setFont("Helvetica", 11)
        generation_date = datetime.datetime.now().strftime("%d %B %Y")
        c.drawString(margins, current_y, f"Date: {generation_date}")
        c.drawRightString(width - margins, current_y,
                          f"Ref: GBA/EE/Z-East/ARI/{timestamp}")
        current_y -= 0.6 * inch

        # 3. Addressee
        c.setFont("Helvetica-Bold", 11)
        c.drawString(margins, current_y, "To:")
        current_y -= 0.2 * inch
        c.setFont("Helvetica", 11)
        c.drawString(margins, current_y,
                     f"M/s {contract_data.get('contractor_name', 'Unknown')}")
        current_y -= 0.2 * inch
        c.drawString(margins, current_y,
                     f"{contract_data.get('contractor_email', 'Email not on file')}")
        current_y -= 0.6 * inch

        # 4. Subject Line
        c.setFont("Helvetica-Bold", 11)
        c.drawString(margins, current_y,
                     "SUBJECT: Mandatory rectification of road defects under active Defect Liability Period (DLP).")
        current_y -= 0.5 * inch

        # 5. Body Text
        c.setFont("Helvetica", 11)
        body_lines = [
            "This is an automated enforcement notice issued by the A.R.I.A edge-inspection system.",
            "During routine algorithmic surveillance, structural road damage was detected on a segment",
            "currently under your Defect Liability Period (DLP).",
            "",
            "Contract Details:",
        ]

        for line in body_lines:
            c.drawString(margins, current_y, line)
            current_y -= 0.2 * inch

        current_y -= 0.1 * inch

        # Contract Details Block
        c.setFont("Helvetica", 11)
        c.drawString(margins + 0.3 * inch, current_y,
                     f"• Road Segment: {contract_data.get('segment_name', 'Unknown')}")
        current_y -= 0.2 * inch
        dlp_end = contract_data.get('dlp_end_date', 'Unknown')
        c.drawString(margins + 0.3 * inch, current_y,
                     f"• DLP End Date: {dlp_end}")
        current_y -= 0.4 * inch

        # Detection Details Block
        lat = detection_data.get('gps_lat', 0.0)
        lon = detection_data.get('gps_lon', 0.0)
        severity = detection_data.get('severity', 'Unknown').upper()

        c.drawString(margins, current_y, "Detection Metadata:")
        current_y -= 0.2 * inch
        c.drawString(margins + 0.3 * inch, current_y,
                     f"• GPS Coordinates: {lat:.6f}, {lon:.6f}")
        current_y -= 0.2 * inch
        c.drawString(margins + 0.3 * inch, current_y,
                     f"• Assessed Severity: {severity}")
        current_y -= 0.5 * inch

        # 6. Ultimatum (If Active)
        is_dlp_active = contract_data.get('is_dlp_active', False)
        if is_dlp_active:
            c.setFont("Helvetica-Bold", 11)
            ultimatum_lines = [
                "ACTION REQUIRED:",
                "Failure to comply within 7 days will result in the GBA executing repairs departmentally.",
                "Costs will be deducted from your 5% withheld security deposit, and your firm will be",
                "recommended for blacklisting."
            ]
            for line in ultimatum_lines:
                c.drawString(margins, current_y, line)
                current_y -= 0.2 * inch
        else:
            c.setFont("Helvetica-Oblique", 11)
            c.drawString(
                margins, current_y, "NOTICE: The DLP has expired. This incident is logged for municipal assessment.")
            current_y -= 0.4 * inch

        current_y -= 0.2 * inch

        # 7. Evidence Image Placeholder
        image_box_height = 2.5 * inch
        image_box_width = width - (2 * margins)

        # Check if we have space, if not, move to next page
        if current_y - image_box_height - (1.5 * inch) < margins:
            c.showPage()
            current_y = height - margins

        current_y -= image_box_height  # Move cursor down by the height of the box FIRST
        c.rect(margins, current_y, image_box_width, image_box_height)

        c.setFont("Helvetica-Oblique", 10)
        # Center text inside the box
        c.drawCentredString(width / 2.0, current_y + (image_box_height /
                            2.0) - 4, "[ EVIDENCE IMAGE PLACEHOLDER ]")

        current_y -= 0.5 * inch  # Add margin below the box

        # 8. Sign-off
        c.setFont("Helvetica", 11)
        c.drawString(margins, current_y, "Yours faithfully,")
        current_y -= 0.6 * inch
        c.drawString(margins, current_y, "Executive Engineer (East Zone)")
        current_y -= 0.2 * inch
        c.drawString(margins, current_y, "Greater Bengaluru Authority")

        # Footer
        c.setFont("Helvetica", 9)
        c.drawCentredString(width / 2.0, 0.75 * inch,
                            "Digitally generated by A.R.I.A. Edge Inspection System — No wet signature required.")

        c.save()
        log.info("Generated PDF notice at: %s", pdf_path)
        return pdf_path

    except Exception as e:
        log.error("Failed to generate PDF notice: %s", e)
        raise
