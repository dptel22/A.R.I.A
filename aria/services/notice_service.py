"""PDF generation and notice assembly for A.R.I.A."""
from __future__ import annotations

import datetime
import io
import logging
import os
import re
import textwrap
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

from aria.domain.models import ContractStatus, DetectionMetadata, SeverityLevel

log: logging.Logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Authority configuration
# ---------------------------------------------------------------------------
# BBMP was dissolved on 2 September 2025 and replaced by the Greater Bengaluru
# Authority (GBA) as the apex body, overseeing five new city corporations:
#   Bengaluru North, Bengaluru South, Bengaluru East, Bengaluru West, Bengaluru Central
# Ref: Greater Bengaluru Governance Act, 2024; BBMP dissolution gazette 02-09-2025
#
# All authority strings are configurable here (and via env vars) so that the
# correct corporation can be set per deployment/demo without touching code.
# ---------------------------------------------------------------------------

# Apex body (always GBA since Sept 2025)
_APEX_AUTHORITY: str = os.environ.get(
    "ARIA_APEX_AUTHORITY",
    "Greater Bengaluru Authority (GBA)",
)

# The specific city corporation handling the contract zone.
# Override via env var or pass explicitly — must be one of:
#   Bengaluru North Corporation | Bengaluru South Corporation
#   Bengaluru East Corporation  | Bengaluru West Corporation
#   Bengaluru Central Corporation
_DEFAULT_CORPORATION: str = os.environ.get(
    "ARIA_CORPORATION_NAME",
    "Bengaluru South Corporation",
)

# Division/department label within the corporation.
_DEFAULT_DIVISION: str = os.environ.get(
    "ARIA_DIVISION_NAME",
    "Roads & Infrastructure Division",
)

# Standard DLP duration per Karnataka PWD SBD Clause 32.1 (36 months from completion)
# Ref: GO_PWD203BMSdated13-08-2025 — configurable per contract if needed
_DEFAULT_DLP_MONTHS: int = 36


def _subtract_months(dt: datetime.date, months: int) -> datetime.date:
    """Subtract months from a date, clamping to the last valid day of the target month."""
    target_month = dt.month - (months % 12)
    target_year = dt.year - (months // 12)
    if target_month <= 0:
        target_month += 12
        target_year -= 1
    import calendar
    last_day = calendar.monthrange(target_year, target_month)[1]
    return dt.replace(year=target_year, month=target_month, day=min(dt.day, last_day))


def _subtract_36_months(value: datetime.date) -> datetime.date:
    try:
        return value.replace(year=value.year - 3)
    except ValueError:
        return value.replace(year=value.year - 3, day=28)


def generate_pdf_notice(
    detection_data: DetectionMetadata,
    contract_data: ContractStatus,
    output_dir: str | None = None,
    buffer: io.BytesIO | None = None,
    corporation_name: str | None = None,
    division_name: str | None = None,
) -> str:
    """Generate a PDF enforcement notice.

    Parameters
    ----------
    detection_data:
        GPS location, severity, and confidence from the A.R.I.A. inference run.
    contract_data:
        Contractor and DLP details for the affected road segment.
    output_dir:
        Directory to write the PDF to.  Ignored when *buffer* is supplied.
    buffer:
        If provided, the PDF bytes are written here instead of a file.
    corporation_name:
        City corporation responsible for this zone, e.g. "Bengaluru East Corporation".
        Defaults to the ``ARIA_CORPORATION_NAME`` env var or :data:`_DEFAULT_CORPORATION`.
    division_name:
        Department within the corporation, e.g. "Roads & Infrastructure Division".
        Defaults to the ``ARIA_DIVISION_NAME`` env var or :data:`_DEFAULT_DIVISION`.
    """
    corp = corporation_name or _DEFAULT_CORPORATION
    div = division_name or _DEFAULT_DIVISION
    if buffer is not None:
        pdf_target: str | io.BytesIO = buffer
        pdf_path = "IN_MEMORY"
    else:
        if not output_dir:
            output_dir = os.environ.get("ARIA_MEDIA_ROOT", "./runtime/notices")
        os.makedirs(output_dir, exist_ok=True)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        contractor_slug = re.sub(r"[^a-zA-Z0-9_-]", "_", contract_data.contractor_name)
        contractor_slug = re.sub(r"_+", "_", contractor_slug).strip("_")[:80] or "unknown"
        filename = f"Notice_{contractor_slug}_{timestamp}.pdf"
        pdf_path = os.path.join(output_dir, filename)

        from pathlib import Path as _Path

        abs_output = _Path(output_dir).resolve()
        abs_pdf = _Path(pdf_path).resolve()
        try:
            abs_pdf.relative_to(abs_output)
        except ValueError:
            raise ValueError(f"Path traversal detected: {abs_pdf} escapes {abs_output}")
        pdf_target = pdf_path

    timestamp_ref = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    # Derive a short corporation slug for the reference number
    # e.g. "Bengaluru South Corporation" -> "South"
    corp_slug = corp.replace("Bengaluru ", "").replace(" Corporation", "").replace(" ", "-")[:10]

    try:
        c = canvas.Canvas(pdf_target, pagesize=A4)
        width, height = A4
        margins = 1.0 * inch
        current_y = height - margins

        # --- Letterhead: Apex authority (GBA) ---
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(width / 2.0, current_y, _APEX_AUTHORITY)
        current_y -= 0.3 * inch

        # --- Sub-header: Corporation + Division ---
        c.setFont("Helvetica", 12)
        c.drawCentredString(width / 2.0, current_y, f"{corp} — {div}")
        current_y -= 0.4 * inch
        c.line(margins, current_y, width - margins, current_y)
        current_y -= 0.5 * inch

        c.setFont("Helvetica", 11)
        generation_date = datetime.datetime.now().strftime("%d %B %Y")
        c.drawString(margins, current_y, f"Date: {generation_date}")
        c.drawRightString(width - margins, current_y, f"Ref: GBA/{corp_slug}/ARIA/{timestamp_ref}")
        current_y -= 0.6 * inch

        c.setFont("Helvetica-Bold", 11)
        c.drawString(margins, current_y, "To:")
        current_y -= 0.2 * inch

        c.setFont("Helvetica", 11)
        for line in textwrap.wrap(f"M/s {contract_data.contractor_name}", width=70):
            c.drawString(margins, current_y, line)
            current_y -= 0.2 * inch

        c.drawString(margins, current_y, contract_data.contractor_email)
        current_y -= 0.6 * inch

        c.setFont("Helvetica-Bold", 11)
        subject = "SUBJECT: Mandatory Rectification of Road Defects Detected under Defect Liability Period (DLP) — Ref: Agreement Clause 32.1, SBD."
        for line in textwrap.wrap(subject, width=80):
            c.drawString(margins, current_y, line)
            current_y -= 0.2 * inch

        completion_certificate_date = (
            _subtract_months(contract_data.dlp_end_date, _DEFAULT_DLP_MONTHS)
            if contract_data.dlp_end_date
            else None
        )
        current_y -= 0.1 * inch

        c.setFont("Helvetica-Bold", 11)
        c.drawString(margins, current_y, "REF:")
        current_y -= 0.2 * inch

        c.setFont("Helvetica", 11)
        for line in [
            f"- Agreement No: {contract_data.contract_id}",
            f"- Completion Certificate Date: {completion_certificate_date if completion_certificate_date else 'On record'}",
            f"- A.R.I.A Inspection Report ID: {timestamp_ref}",
        ]:
            c.drawString(margins + 0.3 * inch, current_y, line)
            current_y -= 0.2 * inch
        current_y -= 0.3 * inch

        c.setFont("Helvetica", 11)
        for line in [
            "This is an automated enforcement notice issued by the A.R.I.A edge-inspection system.",
            "During routine algorithmic surveillance, structural road damage was detected on a segment",
            "currently under your Defect Liability Period (DLP).",
            "",
            "Contract Details:",
        ]:
            c.drawString(margins, current_y, line)
            current_y -= 0.2 * inch

        for line in textwrap.wrap(f"- Road Segment: {contract_data.segment_name}", width=80):
            c.drawString(margins + 0.3 * inch, current_y, line)
            current_y -= 0.2 * inch
        dlp_end_str = str(contract_data.dlp_end_date) if contract_data.dlp_end_date else "Unknown"
        c.drawString(margins + 0.3 * inch, current_y, f"- DLP End Date: {dlp_end_str}")
        current_y -= 0.4 * inch

        c.drawString(margins, current_y, "Detection Metadata:")
        current_y -= 0.2 * inch
        c.drawString(margins + 0.3 * inch, current_y, f"- GPS Coordinates: {detection_data.gps_lat:.6f}, {detection_data.gps_lon:.6f}")
        current_y -= 0.2 * inch
        c.drawString(margins + 0.3 * inch, current_y, f"- Assessed Severity: {detection_data.severity.public_label}")
        current_y -= 0.5 * inch

        if contract_data.is_dlp_active:
            c.setFont("Helvetica-Bold", 11)
            c.drawString(margins, current_y, "YOU ARE HEREBY DIRECTED TO:")
            current_y -= 0.2 * inch
            c.setFont("Helvetica", 11)
            for line in [
                "1. Initiate repair works within 48 hours of this notice.",
                "2. Complete restoration as per MORTH/IRC specifications within 7 days.",
                "3. Notify this office upon completion for follow-up inspection.",
            ]:
                c.drawString(margins, current_y, line)
                current_y -= 0.2 * inch
            current_y -= 0.2 * inch

            c.setFont("Helvetica-Bold", 11)
            for line in [
                "ACTION REQUIRED:",
                "Failure to comply within 7 days will result in the GBA executing repairs departmentally.",
                "Costs will be deducted from your 5% withheld security deposit, and your firm will be",
                "recommended for blacklisting.",
            ]:
                c.drawString(margins, current_y, line)
                current_y -= 0.2 * inch
        else:
            c.setFont("Helvetica-Oblique", 11)
            c.drawString(margins, current_y, "NOTICE: The DLP has expired. This incident is logged for municipal assessment.")
            current_y -= 0.4 * inch

        current_y -= 0.2 * inch
        image_box_height = 2.5 * inch
        image_box_width = width - (2 * margins)
        if current_y - image_box_height - (1.5 * inch) < margins:
            c.showPage()
            current_y = height - margins

        current_y -= image_box_height
        img_path = getattr(detection_data, "image_path", None)
        if img_path and os.path.isfile(img_path):
            try:
                from reportlab.lib.utils import ImageReader

                c.drawImage(
                    ImageReader(img_path),
                    margins, current_y,
                    width=image_box_width,
                    height=image_box_height,
                    preserveAspectRatio=True,
                    anchor="c",
                    mask="auto",
                )
                c.setFont("Helvetica", 8)
                c.drawString(margins, current_y - 0.15 * inch, f"Evidence: {os.path.basename(img_path)}")
            except Exception as img_err:
                log.warning("Could not embed image %s: %s", img_path, img_err)
                c.rect(margins, current_y, image_box_width, image_box_height)
                c.setFont("Helvetica-Oblique", 10)
                c.drawCentredString(width / 2.0, current_y + (image_box_height / 2.0) - 4, f"[Image unavailable: {os.path.basename(img_path)}]")
        else:
            c.rect(margins, current_y, image_box_width, image_box_height)
            c.setFont("Helvetica-Oblique", 10)
            c.drawCentredString(width / 2.0, current_y + (image_box_height / 2.0) - 4, "[ No evidence image recorded ]")

        current_y -= 0.5 * inch
        c.setFont("Helvetica", 11)
        c.drawString(margins, current_y, "Yours faithfully,")
        current_y -= 0.6 * inch
        c.drawString(margins, current_y, f"Commissioner / Executive Engineer — {div}")
        current_y -= 0.2 * inch
        c.drawString(margins, current_y, corp)
        current_y -= 0.15 * inch
        c.setFont("Helvetica", 9)
        c.drawString(margins, current_y, f"(Under the jurisdiction of {_APEX_AUTHORITY})")

        c.setFont("Helvetica", 9)
        c.drawCentredString(width / 2.0, 0.75 * inch, "Digitally generated by A.R.I.A. Edge Inspection System - No wet signature required.")
        c.save()

        if pdf_path != "IN_MEMORY":
            log.info("Generated PDF notice at: %s", os.path.abspath(pdf_path))
            return os.path.abspath(pdf_path)
        log.info("Generated PDF notice in-memory.")
        return pdf_path
    except Exception as exc:
        log.error("Failed to generate PDF notice: %s", exc)
        raise


def _parse_dlp_date(dlp_end_date: str | None) -> datetime.date | None:
    if not dlp_end_date:
        return None
    try:
        return datetime.datetime.strptime(dlp_end_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        try:
            return datetime.datetime.fromisoformat(dlp_end_date.replace("Z", "+00:00")).date()
        except (ValueError, TypeError):
            return None


def build_notice_pdf(inspection: dict[str, Any], detections: list[dict[str, Any]]) -> bytes:
    primary = detections[0]
    severity_map = {
        "CRITICAL": SeverityLevel.CRITICAL,
        "HIGH": SeverityLevel.HIGH,
        "MEDIUM": SeverityLevel.MEDIUM,
        "LOW": SeverityLevel.LOW,
    }
    detection_metadata = DetectionMetadata(
        gps_lat=inspection["lat"],
        gps_lon=inspection["lng"],
        severity=severity_map.get(primary["severity_level"], SeverityLevel.HIGH),
        confidence=primary["confidence"],
        image_path=inspection.get("image_path"),
    )

    dlp_end_date = _parse_dlp_date(inspection.get("dlp_end_date_snapshot"))
    if inspection.get("contract_id_snapshot"):
        contract_status = ContractStatus(
            segment_id=inspection["segment_id"],
            segment_name=inspection["road_name"],
            contract_id=inspection["contract_id_snapshot"],
            contractor_name=inspection.get("contractor_name_snapshot") or "Unknown Contractor",
            contractor_email=inspection.get("contractor_email_snapshot") or "N/A",
            dlp_end_date=dlp_end_date,
            is_dlp_active=bool(inspection.get("is_dlp_active_snapshot")),
        )
    else:
        contract_status = ContractStatus(
            segment_id=inspection["segment_id"],
            segment_name=inspection["road_name"],
            contract_id=0,
            contractor_name="Unknown (No contract on file)",
            contractor_email="N/A",
            dlp_end_date=None,
            is_dlp_active=False,
        )

    pdf_buffer = io.BytesIO()
    generate_pdf_notice(detection_metadata, contract_status, output_dir=None, buffer=pdf_buffer)
    return pdf_buffer.getvalue()
