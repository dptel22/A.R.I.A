"""
core/notice_generator.py — PDF Generation for A.R.I.A. Enforcement Notices.
"""
from __future__ import annotations

import datetime
import io
import logging
import os
import re
import textwrap

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

from core.models import ContractStatus, DetectionMetadata

log: logging.Logger = logging.getLogger(__name__)


def generate_pdf_notice(
    detection_data: DetectionMetadata,
    contract_data: ContractStatus,
    output_dir: str | None = None,
    buffer: io.BytesIO | None = None,
) -> str:
    """
    Generate an official, legally-binding enforcement notice PDF from the GBA.

    Args:
        detection_data: DetectionMetadata dataclass instance.
        contract_data: ContractStatus dataclass instance.
        output_dir: Directory to save the generated PDF. Ignored if buffer is provided.
        buffer: Optional BytesIO buffer for in-memory generation (used by the API).

    Returns:
        The absolute path to the generated PDF file, or "IN_MEMORY" if buffer was used.
    """
    # Determine output target: in-memory buffer or on-disk file
    if buffer is not None:
        pdf_target: str | io.BytesIO = buffer
        pdf_path = "IN_MEMORY"
    else:
        if not output_dir:
            output_dir = os.environ.get("ARIA_MEDIA_ROOT", "notices/")
        os.makedirs(output_dir, exist_ok=True)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        # Secure slug: strip path-traversal chars, collapse to safe chars only
        raw_name = contract_data.contractor_name
        contractor_slug = re.sub(r"[^a-zA-Z0-9_-]", "_", raw_name)
        contractor_slug = re.sub(r"_+", "_", contractor_slug).strip("_")[:80]
        if not contractor_slug:
            contractor_slug = "unknown"
        filename = f"Notice_{contractor_slug}_{timestamp}.pdf"
        pdf_path = os.path.join(output_dir, filename)
        # Validate path stays inside output_dir (prevent directory escape)
        from pathlib import Path as _Path
        abs_output = _Path(output_dir).resolve()
        abs_pdf = _Path(pdf_path).resolve()
        try:
            abs_pdf.relative_to(abs_output)
        except ValueError:
            raise ValueError(
                f"Path traversal detected: {abs_pdf} escapes {abs_output}"
            )
        pdf_target = pdf_path

    timestamp_ref = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    try:
        c = canvas.Canvas(pdf_target, pagesize=A4)
        width, height = A4

        margins = 1.0 * inch
        current_y = height - margins

        # 1. Official Header (GBA)
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(width / 2.0, current_y, "GREATER BENGALURU AUTHORITY (GBA)")
        current_y -= 0.3 * inch

        c.setFont("Helvetica", 12)
        c.drawCentredString(width / 2.0, current_y, "Office of the Executive Engineer, East Zone City Corporation")
        current_y -= 0.4 * inch

        c.line(margins, current_y, width - margins, current_y)
        current_y -= 0.5 * inch

        # 2. Date and Reference
        c.setFont("Helvetica", 11)
        generation_date = datetime.datetime.now().strftime("%d %B %Y")
        c.drawString(margins, current_y, f"Date: {generation_date}")
        c.drawRightString(width - margins, current_y, f"Ref: GBA/EE/Z-East/ARI/{timestamp_ref}")
        current_y -= 0.6 * inch

        # 3. Addressee (with text wrapping for long names)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(margins, current_y, "To:")
        current_y -= 0.2 * inch

        c.setFont("Helvetica", 11)
        wrapped_name = textwrap.wrap(f"M/s {contract_data.contractor_name}", width=70)
        for line in wrapped_name:
            c.drawString(margins, current_y, line)
            current_y -= 0.2 * inch

        c.drawString(margins, current_y, f"{contract_data.contractor_email}")
        current_y -= 0.6 * inch

        # 4. Subject Line (wrapped)
        c.setFont("Helvetica-Bold", 11)
        subject_text = "SUBJECT: Mandatory rectification of road defects under active Defect Liability Period (DLP)."
        wrapped_subject = textwrap.wrap(subject_text, width=80)
        for line in wrapped_subject:
            c.drawString(margins, current_y, line)
            current_y -= 0.2 * inch
        current_y -= 0.3 * inch

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
        wrapped_segment = textwrap.wrap(f"• Road Segment: {contract_data.segment_name}", width=80)
        for line in wrapped_segment:
            c.drawString(margins + 0.3 * inch, current_y, line)
            current_y -= 0.2 * inch

        dlp_end_str = str(contract_data.dlp_end_date) if contract_data.dlp_end_date else 'Unknown'
        c.drawString(margins + 0.3 * inch, current_y, f"• DLP End Date: {dlp_end_str}")
        current_y -= 0.4 * inch

        # Detection Details Block
        lat = detection_data.gps_lat
        lon = detection_data.gps_lon
        severity_val = detection_data.severity.value.upper()

        c.drawString(margins, current_y, "Detection Metadata:")
        current_y -= 0.2 * inch
        c.drawString(margins + 0.3 * inch, current_y, f"• GPS Coordinates: {lat:.6f}, {lon:.6f}")
        current_y -= 0.2 * inch
        c.drawString(margins + 0.3 * inch, current_y, f"• Assessed Severity: {severity_val}")
        current_y -= 0.5 * inch

        # 6. Ultimatum (If Active DLP)
        if contract_data.is_dlp_active:
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
            c.drawString(margins, current_y, "NOTICE: The DLP has expired. This incident is logged for municipal assessment.")
            current_y -= 0.4 * inch

        current_y -= 0.2 * inch

        # 7. Evidence Image Placeholder
        image_box_height = 2.5 * inch
        image_box_width = width - (2 * margins)

        if current_y - image_box_height - (1.5 * inch) < margins:
            c.showPage()
            current_y = height - margins

        current_y -= image_box_height
        c.rect(margins, current_y, image_box_width, image_box_height)

        c.setFont("Helvetica-Oblique", 10)
        c.drawCentredString(width / 2.0, current_y + (image_box_height / 2.0) - 4, "[ EVIDENCE IMAGE PLACEHOLDER ]")

        current_y -= 0.5 * inch

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

        if pdf_path != "IN_MEMORY":
            log.info("Generated PDF notice at: %s", os.path.abspath(pdf_path))
            return os.path.abspath(pdf_path)
        else:
            log.info("Generated PDF notice in-memory.")
            return pdf_path

    except Exception as e:
        log.error("Failed to generate PDF notice: %s", e)
        raise
