"""
frontend/app.py — Main Streamlit entry point for A.R.I.A.

Run with:
    streamlit run frontend/app.py
"""
from __future__ import annotations

import streamlit as st

# ---------------------------------------------------------------------------
# Page config (must be first Streamlit call)
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="A.R.I.A. — Road Inspection",
    page_icon="🛣️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------

st.sidebar.title("🛣️ A.R.I.A.")
st.sidebar.caption("Adaptive Road Intelligence Architecture")
st.sidebar.divider()

page = st.sidebar.radio(
    "Navigate",
    ["🔍 Inspect Road", "📊 Dashboard", "ℹ️ About"],
    label_visibility="collapsed",
)

st.sidebar.divider()
st.sidebar.caption("YOLOv11n · RDD2022 · 4-class · Bengaluru")

# ---------------------------------------------------------------------------
# Page routing
# ---------------------------------------------------------------------------

if page == "🔍 Inspect Road":
    from frontend.pages.detect import render
    render()

elif page == "📊 Dashboard":
    from frontend.pages.dashboard import render
    render()

elif page == "ℹ️ About":
    st.title("🛣️ A.R.I.A.")
    st.subheader("Adaptive Road Intelligence Architecture")
    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### Detection Model")
        st.markdown("""
        - **Architecture:** YOLOv11n (ultralytics)
        - **Dataset:** RDD2022 (26,800 images)
        - **Training:** 50 epochs, 0.568 mAP50
        - **Classes:** 4 — longitudinal crack, transverse crack, alligator crack, pothole
        """)

    with col2:
        st.markdown("### Enforcement Pipeline")
        st.markdown("""
        - **GPS → Road Segment** lookup with 20m tolerance
        - **Contract + DLP** status from SQLite database
        - **PDF Notice** generation via ReportLab (in-memory)
        - **GBA** (Greater Bengaluru Authority) official format
        """)

    st.divider()
    st.markdown("### Severity Scoring")
    st.markdown("""
    Severity is calculated as: `BASE_SEVERITY[class] × area_weight(bbox_area)`

    | Class | Base | Rationale |
    |-------|------|-----------|
    | Pothole | 4 | CRITICAL — structural hazard |
    | Alligator Crack | 3 | HIGH — failure precursor |
    | Transverse Crack | 2 | MEDIUM — spalling risk |
    | Longitudinal Crack | 1 | LOW — surface issue |

    Area weight clamps between 1.0× and 2.0× based on bounding box area.
    """)

    st.divider()
    st.caption("Built for Bengaluru municipal enforcement. A.R.I.A. v1.0.0")
