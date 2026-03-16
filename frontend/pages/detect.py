"""
frontend/pages/detect.py — Road inspection page for A.R.I.A.

Primary inspector workflow: upload image → provide GPS → detect damage →
view annotated results → download enforcement notice.
"""
from __future__ import annotations

import requests
import streamlit as st

from frontend.utils import (
    api_post_image,
    draw_boxes_on_image,
    get_api_key,
    severity_badge,
    SEVERITY_COLOURS,
)


def render() -> None:
    """Render the road inspection page."""
    st.title("🔍 Road Inspection")
    st.caption("Upload a road image and provide GPS coordinates to detect damage.")

    # ── Section 1: Upload ────────────────────────────────────────────
    uploaded_file = st.file_uploader(
        "Upload road image",
        type=["jpg", "jpeg", "png", "webp"],
        help="Maximum 10 MB. JPEG or PNG preferred.",
    )

    # ── Section 2: GPS Input ─────────────────────────────────────────
    st.subheader("📍 GPS Coordinates")
    st.caption("Enter coordinates from your device. Must be within a known GBA road segment.")

    col1, col2 = st.columns(2)
    with col1:
        lat = st.number_input("Latitude", value=12.9310, format="%.6f", step=0.0001)
    with col2:
        lng = st.number_input("Longitude", value=77.6450, format="%.6f", step=0.0001)

    st.caption("💡 Default: Outer Ring Road — Marathahalli to Silk Board")

    # ── Section 3: Preview + Submit ──────────────────────────────────
    submit = False

    if uploaded_file is not None:
        col_img, col_btn = st.columns([3, 1])
        with col_img:
            st.image(uploaded_file, caption="Uploaded image", use_container_width=True)
        with col_btn:
            st.write("")  # spacer
            st.write("")
            submit = st.button(
                "🔍 Detect Damage",
                type="primary",
                use_container_width=True,
            )
    else:
        st.info("📷 Upload an image to begin inspection.")

    # ── Section 4: Results ───────────────────────────────────────────
    if not submit or uploaded_file is None:
        return

    with st.spinner("Running YOLO inference..."):
        img_bytes = uploaded_file.read()
        result = api_post_image("/detect", img_bytes, uploaded_file.name, lat, lng)

    if result is None:
        return  # error already displayed by api_post_image

    if result.get("total_detections", 0) == 0:
        st.success("✅ No road damage detected at this location.")
        return

    st.divider()
    st.subheader("Detection Results")

    # Annotated image with bounding boxes
    annotated = draw_boxes_on_image(img_bytes, result["all_detections"])
    st.image(annotated, caption="Detections overlaid", use_container_width=True)

    # Primary defect highlight
    primary = result["primary_defect"]
    pcol1, pcol2, pcol3 = st.columns(3)
    with pcol1:
        st.markdown(
            f"**Primary Defect:** {primary['class_name'].replace('_', ' ').title()}"
        )
        st.markdown(severity_badge(primary["severity_level"]), unsafe_allow_html=True)
    with pcol2:
        st.metric("Confidence", f"{primary['confidence']:.1%}")
    with pcol3:
        st.metric("Severity Score", f"{primary['severity_score']:.2f}")

    # All detections table
    if len(result["all_detections"]) > 1:
        st.divider()
        st.subheader(f"All Detections ({result['total_detections']})")
        rows = []
        for det in result["all_detections"]:
            rows.append({
                "Type": det["class_name"].replace("_", " ").title(),
                "Severity": det["severity_level"],
                "Score": det["severity_score"],
                "Confidence": f"{det['confidence']:.1%}",
            })
        st.dataframe(rows, use_container_width=True, hide_index=True)

    # Road + contract info
    st.divider()
    st.subheader("🛣️ Road & Contract Details")

    rcol1, rcol2, rcol3 = st.columns(3)
    with rcol1:
        st.metric("Road Segment", result["road_segment"])
    with rcol2:
        st.metric("Ward", result["ward_id"])
    with rcol3:
        st.metric("Zone", result["zone_id"])

    contract = result.get("contract", {})
    if contract.get("contractor_name"):
        st.write(f"**Contractor:** {contract['contractor_name']}")
        st.write(f"**DLP Expiry:** {contract.get('dlp_end_date', 'Unknown')}")
        if contract.get("is_dlp_active"):
            st.success("✅ DLP Active — contractor is liable for repairs")
        else:
            st.warning("⚠️ DLP Expired — municipal maintenance required")

    # Enforcement notice download
    st.divider()
    st.subheader("📄 Enforcement Notice")

    inspection_id = result["inspection_id"]
    notice_url = f"http://localhost:8000/api/v1/notices/{inspection_id}"

    with st.spinner("Generating PDF notice..."):
        try:
            pdf_resp = requests.get(
                notice_url,
                headers={"x-api-key": get_api_key()},
                timeout=15,
            )
        except Exception as e:
            st.error(f"Failed to fetch notice: {e}")
            pdf_resp = None

    if pdf_resp and pdf_resp.status_code == 200:
        st.download_button(
            label="📄 Download Enforcement Notice (PDF)",
            data=pdf_resp.content,
            file_name=f"ARIA_Notice_{inspection_id}.pdf",
            mime="application/pdf",
            type="primary",
        )
    else:
        st.error("Failed to generate PDF notice.")

    st.caption(f"Inspection ID: {inspection_id} — saved to database")
