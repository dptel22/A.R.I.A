"""
frontend/pages/dashboard.py — Inspection history dashboard for A.R.I.A.

Read-only overview of all past inspections with filters by ward, zone,
and minimum severity level.
"""
from __future__ import annotations

import streamlit as st

from frontend.utils import (
    api_get,
    severity_badge,
    SEVERITY_COLOURS,
)


def render() -> None:
    """Render the inspection dashboard page."""
    st.title("📊 Inspection Dashboard")
    st.caption("All past road inspections. Filter by ward, zone, or severity.")

    # ── Filters in sidebar ───────────────────────────────────────────
    with st.sidebar:
        st.subheader("🔎 Filters")
        ward_id = st.text_input("Ward ID", placeholder="e.g. W-150")
        zone_id = st.text_input("Zone", placeholder="e.g. East")
        min_severity = st.selectbox(
            "Minimum Severity",
            ["", "LOW", "MEDIUM", "HIGH", "CRITICAL"],
            index=0,
            format_func=lambda x: "All" if x == "" else x,
        )
        limit = st.slider("Results per page", 10, 100, 50)

    # ── Fetch data ───────────────────────────────────────────────────
    params: dict[str, str | int] = {"limit": limit, "offset": 0}
    if ward_id:
        params["ward_id"] = ward_id
    if zone_id:
        params["zone_id"] = zone_id
    if min_severity:
        params["min_severity"] = min_severity

    with st.spinner("Loading inspections..."):
        data = api_get("/detections", params=params)

    if data is None:
        return

    results = data.get("results", [])

    if not results:
        st.info("No inspections found matching these filters.")
        return

    # ── Summary metrics ──────────────────────────────────────────────
    total = data["total_returned"]
    critical = sum(1 for r in results if r.get("highest_severity") == "CRITICAL")
    high = sum(1 for r in results if r.get("highest_severity") == "HIGH")
    other = total - critical - high

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Inspections", total)
    with col2:
        st.metric("🔴 Critical", critical)
    with col3:
        st.metric("🟠 High", high)
    with col4:
        st.metric("Other", other)

    st.divider()

    # ── Results list ─────────────────────────────────────────────────
    for result in results:
        sev = result.get("highest_severity", "NONE")
        road = result.get("road_name", "Unknown Road")
        timestamp = result.get("timestamp", "")[:10]  # date only
        insp_id = result.get("inspection_id", "?")

        with st.expander(
            f"[{sev}] {road} — {timestamp}",
            expanded=(sev == "CRITICAL"),
        ):
            ecol1, ecol2, ecol3, ecol4 = st.columns(4)
            with ecol1:
                st.metric("Ward", result.get("ward_id", "—"))
            with ecol2:
                st.metric("Zone", result.get("zone_id", "—"))
            with ecol3:
                st.metric("Defects", result.get("total_defects", 0))
            with ecol4:
                st.markdown(severity_badge(sev), unsafe_allow_html=True)

            crit_count = result.get("critical_count", 0)
            high_count = result.get("high_count", 0)

            if crit_count > 0:
                st.error(f"🚨 {crit_count} CRITICAL defect(s)")
            if high_count > 0:
                st.warning(f"⚠️ {high_count} HIGH defect(s)")

            st.caption(f"Inspection ID: {insp_id}")

            notice_url = f"http://localhost:8000/api/v1/notices/{insp_id}"
            st.markdown(
                f'<a href="{notice_url}" target="_blank">📄 View Enforcement Notice</a>',
                unsafe_allow_html=True,
            )

    # ── Pagination hint ──────────────────────────────────────────────
    if total >= limit:
        st.info(f"Showing {limit} results. Increase 'Results per page' to see more.")
