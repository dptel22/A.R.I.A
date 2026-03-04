"""
core/notice_generator.py — A.R.I.A. PDF Enforcement Notice Generator
Generates a professional PDF notice using ReportLab for BBMP road defect enforcement.
"""

import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    Image,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

DB_PATH = "db/aria.db"

# Colour palette — BBMP blue + enforce red
BBMP_BLUE = colors.HexColor("#003A70")
BBMP_LIGHT = colors.HexColor("#E8F0F7")
SEVERITY_COLORS = {
    "HIGH": colors.HexColor("#C0392B"),
    "MEDIUM": colors.HexColor("#E67E22"),
    "LOW": colors.HexColor("#27AE60"),
}


def _severity_color(severity: str) -> colors.Color:
    """Return the colour associated with a severity level."""
    return SEVERITY_COLORS.get(severity.upper(), colors.grey)


def _build_styles() -> dict:
    """Build and return a dictionary of custom paragraph styles."""
    base = getSampleStyleSheet()

    styles = {
        "title": ParagraphStyle(
            "ARIATitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=13,
            textColor=colors.white,
            alignment=TA_CENTER,
            spaceAfter=2,
        ),
        "subtitle": ParagraphStyle(
            "ARIASubtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            textColor=colors.white,
            alignment=TA_CENTER,
            spaceAfter=0,
        ),
        "section_header": ParagraphStyle(
            "ARIASectionHeader",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            textColor=BBMP_BLUE,
            spaceBefore=10,
            spaceAfter=4,
        ),
        "field_label": ParagraphStyle(
            "ARIAFieldLabel",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=colors.HexColor("#333333"),
        ),
        "field_value": ParagraphStyle(
            "ARIAFieldValue",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            textColor=colors.HexColor("#111111"),
        ),
        "footer": ParagraphStyle(
            "ARIAFooter",
            parent=base["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=8,
            textColor=colors.grey,
            alignment=TA_CENTER,
        ),
        "notice_id": ParagraphStyle(
            "ARIANoticeId",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=colors.HexColor("#555555"),
            alignment=TA_RIGHT,
        ),
    }
    return styles


def generate_notice(detection: dict, contract: dict, output_path: str) -> str:
    """
    Generate a professional PDF enforcement notice for a road_damage detection.

    Creates an A4 PDF using ReportLab containing:
      - BBMP header with notice metadata
      - Road segment and GPS coordinate details
      - Contractor and contract information
      - DLP status indicator
      - Severity classification with colour coding
      - Embedded evidence frame (or placeholder if unavailable)
      - Footer citing A.R.I.A. and pending engineer approval status

    Args:
        detection (dict): Detection record with keys:
            detection_id, timestamp, gps_lat, gps_lon, severity,
            confidence, bbox_json, frame_path, within_dlp, segment_id
        contract (dict): Contract record with keys:
            contract_id, contractor_name, contractor_email,
            segment_name, dlp_end_date, days_remaining, within_dlp,
            contract_value_inr
        output_path (str): Absolute or relative path where the PDF will be saved.

    Returns:
        str: The path to the saved PDF file.
    """
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(
        output_path) else ".", exist_ok=True)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=15 * mm,
        bottomMargin=20 * mm,
    )

    styles = _build_styles()
    story = []

    page_width = A4[0] - 40 * mm  # usable width

    # ----------------------------------------------------------------
    # Header banner
    # ----------------------------------------------------------------
    header_data = [
        [Paragraph("BRUHAT BENGALURU MAHANAGARA PALIKE", styles["title"])],
        [Paragraph(
            "Road Infrastructure Department — Road Defect Enforcement Notice", styles["subtitle"])],
    ]
    header_table = Table(header_data, colWidths=[page_width])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BBMP_BLUE),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("ROUNDEDCORNERS", [4, 4, 4, 4]),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 6 * mm))

    # ----------------------------------------------------------------
    # Notice meta bar (Notice ID | Date)
    # ----------------------------------------------------------------
    notice_id = detection.get(
        "notice_id", detection.get("detection_id", "N/A"))
    generated_at = datetime.now().strftime("%d %B %Y, %H:%M IST")

    meta_data = [
        [
            Paragraph(f"Notice ID: <b>{notice_id}</b>", styles["field_label"]),
            Paragraph(f"Date: {generated_at}", styles["notice_id"]),
        ]
    ]
    meta_table = Table(meta_data, colWidths=[
                       page_width * 0.5, page_width * 0.5])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BBMP_LIGHT),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (0, -1), 8),
        ("RIGHTPADDING", (-1, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 5 * mm))

    # ----------------------------------------------------------------
    # Section 1 — Location Details
    # ----------------------------------------------------------------
    story.append(Paragraph("1. LOCATION DETAILS", styles["section_header"]))
    story.append(HRFlowable(width=page_width, thickness=1,
                 color=BBMP_BLUE, spaceAfter=4))

    loc_data = [
        ["Road Segment", ":", contract.get(
            "segment_name", detection.get("segment_id", "—"))],
        ["GPS Coordinates", ":",
            f"Lat {detection['gps_lat']:.6f}°  |  Lon {detection['gps_lon']:.6f}°"],
        ["Detection Timestamp", ":", detection.get("timestamp", "—")],
    ]
    loc_table = Table(loc_data, colWidths=[
                      45 * mm, 5 * mm, page_width - 50 * mm])
    loc_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#333333")),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, BBMP_LIGHT]),
    ]))
    story.append(loc_table)
    story.append(Spacer(1, 5 * mm))

    # ----------------------------------------------------------------
    # Section 2 — Contractor & Contract Details
    # ----------------------------------------------------------------
    story.append(Paragraph("2. CONTRACTOR & CONTRACT DETAILS",
                 styles["section_header"]))
    story.append(HRFlowable(width=page_width, thickness=1,
                 color=BBMP_BLUE, spaceAfter=4))

    dlp_status_text = (
        f"WITHIN DLP  ({contract.get('days_remaining', 0)} days remaining)"
        if contract.get("within_dlp")
        else f"DLP EXPIRED  ({abs(contract.get('days_remaining', 0))} days ago)"
    )
    dlp_color = colors.HexColor("#27AE60") if contract.get(
        "within_dlp") else colors.HexColor("#C0392B")

    con_data = [
        ["Contractor Name", ":", contract.get("contractor_name", "—")],
        ["Contractor Email", ":", contract.get("contractor_email", "—")],
        ["Contract ID", ":", contract.get("contract_id", "—")],
        ["DLP End Date", ":", contract.get("dlp_end_date", "—")],
        ["DLP Status", ":", dlp_status_text],
    ]
    con_table = Table(con_data, colWidths=[
                      45 * mm, 5 * mm, page_width - 50 * mm])
    con_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#333333")),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, BBMP_LIGHT]),
        # Highlight DLP Status row
        ("TEXTCOLOR", (2, 4), (2, 4), dlp_color),
        ("FONTNAME", (2, 4), (2, 4), "Helvetica-Bold"),
    ]))
    story.append(con_table)
    story.append(Spacer(1, 5 * mm))

    # ----------------------------------------------------------------
    # Section 3 — Road Defect Classification
    # ----------------------------------------------------------------
    story.append(Paragraph("3. ROAD DEFECT CLASSIFICATION",
                 styles["section_header"]))
    story.append(HRFlowable(width=page_width, thickness=1,
                 color=BBMP_BLUE, spaceAfter=4))

    severity = detection.get("severity", "UNKNOWN").upper()
    sev_color = _severity_color(severity)

    det_data = [
        ["Severity Level", ":", severity],
        ["Detection Confidence", ":",
            f"{float(detection.get('confidence', 0)) * 100:.1f}%"],
        ["Bounding Box (px)", ":", detection.get("bbox_json", "—")],
    ]
    det_table = Table(det_data, colWidths=[
                      45 * mm, 5 * mm, page_width - 50 * mm])
    det_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#333333")),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, BBMP_LIGHT]),
        # Colour-code the severity value
        ("TEXTCOLOR", (2, 0), (2, 0), sev_color),
        ("FONTNAME", (2, 0), (2, 0), "Helvetica-Bold"),
        ("FONTSIZE", (2, 0), (2, 0), 10),
    ]))
    story.append(det_table)
    story.append(Spacer(1, 5 * mm))

    # ----------------------------------------------------------------
    # Section 4 — Evidence Frame
    # ----------------------------------------------------------------
    story.append(Paragraph("4. EVIDENCE PHOTOGRAPH", styles["section_header"]))
    story.append(HRFlowable(width=page_width, thickness=1,
                 color=BBMP_BLUE, spaceAfter=4))

    frame_path = detection.get("frame_path")
    if frame_path and os.path.exists(frame_path):
        try:
            img = Image(frame_path, width=page_width,
                        height=60 * mm, kind="proportional")
            story.append(img)
        except Exception:
            story.append(_placeholder_box(page_width, styles))
    else:
        story.append(_placeholder_box(page_width, styles))

    story.append(Spacer(1, 8 * mm))

    # ----------------------------------------------------------------
    # Footer
    # ----------------------------------------------------------------
    story.append(HRFlowable(width=page_width, thickness=0.5,
                 color=colors.grey, spaceAfter=4))
    story.append(Paragraph(
        "Generated by <b>A.R.I.A.</b> — Autonomous Road Infrastructure Auditor  |  "
        "Status: <b>Pending Engineer Approval</b>  |  "
        "This is a system-generated draft notice. Not valid without engineer signature.",
        styles["footer"],
    ))

    doc.build(story)
    return output_path


def _placeholder_box(width: float, styles: dict):
    """
    Return a Table that renders as a grey placeholder box when no evidence image exists.

    Args:
        width (float): Available page width in points.
        styles (dict): Style dictionary built by _build_styles().

    Returns:
        Table: A ReportLab Table acting as an image placeholder.
    """
    placeholder_data = [[Paragraph(
        "[ No evidence frame on record — image not available ]",
        ParagraphStyle(
            "Placeholder",
            fontName="Helvetica-Oblique",
            fontSize=9,
            textColor=colors.grey,
            alignment=TA_CENTER,
        ),
    )]]
    t = Table(placeholder_data, colWidths=[width], rowHeights=[50 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F2F2F2")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    return t
