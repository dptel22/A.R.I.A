"""
dashboard/app.py — A.R.I.A. Streamlit Engineer Review Dashboard
Provides a visual interface for engineers to review, approve, or reject road defect detections.
"""

import time
from datetime import datetime

import requests
import streamlit as st

# ─────────────────────────────────────────────────────────────
# Configuration — defined once, never hardcoded elsewhere
# ─────────────────────────────────────────────────────────────
API_URL = "http://localhost:8000"

# ─────────────────────────────────────────────────────────────
# Page configuration
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="A.R.I.A. — Road Defect Review Dashboard",
    page_icon="🛣️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────
# Custom CSS — premium dark-themed UI
# ─────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* Main background */
    .stApp {
        background: linear-gradient(135deg, #0a0f1e 0%, #0d1b2a 50%, #0a1628 100%);
        color: #e0e6f0;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0d1b2a 0%, #0a1628 100%);
        border-right: 1px solid rgba(0,186,255,0.15);
    }

    /* Cards */
    .aria-card {
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(0,186,255,0.15);
        border-radius: 12px;
        padding: 16px 20px;
        margin-bottom: 12px;
        transition: border-color 0.2s ease, box-shadow 0.2s ease;
    }
    .aria-card:hover {
        border-color: rgba(0,186,255,0.4);
        box-shadow: 0 4px 24px rgba(0,186,255,0.08);
    }

    /* Severity badges */
    .badge-high   { background:#c0392b; color:#fff; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600; }
    .badge-medium { background:#e67e22; color:#fff; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600; }
    .badge-low    { background:#27ae60; color:#fff; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600; }

    /* DLP badges */
    .dlp-active  { background:#1a6b3a; color:#7dffb0; padding:3px 10px; border-radius:20px; font-size:11px; font-weight:500; }
    .dlp-expired { background:#6b1a1a; color:#ffb0b0; padding:3px 10px; border-radius:20px; font-size:11px; font-weight:500; }

    /* Status badges */
    .status-pending  { color:#f0c040; font-weight:600; }
    .status-approved { color:#27ae60; font-weight:600; }
    .status-rejected { color:#e74c3c; font-weight:600; }

    /* Title header */
    .aria-title {
        font-size: 28px;
        font-weight: 700;
        background: linear-gradient(90deg, #00baff, #0055ff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 4px;
    }
    .aria-subtitle {
        font-size: 13px;
        color: #6a8aaa;
        margin-bottom: 24px;
    }

    /* Metrics */
    [data-testid="stMetric"] {
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(0,186,255,0.1);
        border-radius: 10px;
        padding: 12px 16px;
    }

    /* Buttons */
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.2s ease;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    }

    /* Dividers */
    hr { border-color: rgba(0,186,255,0.1); }

    /* Expander */
    [data-testid="stExpander"] {
        background: rgba(255,255,255,0.02);
        border: 1px solid rgba(0,186,255,0.12);
        border-radius: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ─────────────────────────────────────────────────────────────
# API helpers
# ─────────────────────────────────────────────────────────────

def _api_get(path: str, params: dict = None) -> list | dict | None:
    """
    Perform a GET request against the A.R.I.A. API.

    Args:
        path (str): Endpoint path (e.g. '/detections').
        params (dict, optional): Query parameters.

    Returns:
        Parsed JSON response, or None on failure.
    """
    try:
        resp = requests.get(f"{API_URL}{path}", params=params, timeout=5)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        st.error(
            "🔌 Cannot reach A.R.I.A. API. Is the FastAPI server running on port 8000?")
        return None
    except Exception as e:
        st.error(f"API error: {e}")
        return None


def _api_post(path: str, body: dict = None) -> dict | None:
    """
    Perform a POST request against the A.R.I.A. API.

    Args:
        path (str): Endpoint path.
        body (dict, optional): JSON body.

    Returns:
        Parsed JSON response, or None on failure.
    """
    try:
        resp = requests.post(f"{API_URL}{path}", json=body or {}, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        st.error("🔌 Cannot reach A.R.I.A. API.")
        return None
    except Exception as e:
        st.error(f"API error: {e}")
        return None


# ─────────────────────────────────────────────────────────────
# UI helpers
# ─────────────────────────────────────────────────────────────

def _severity_badge(severity: str) -> str:
    """Return an HTML severity badge string."""
    cls = f"badge-{severity.lower()}"
    return f'<span class="{cls}">{severity}</span>'


def _dlp_badge(within_dlp: int | bool) -> str:
    """Return an HTML DLP status badge string."""
    if within_dlp:
        return '<span class="dlp-active">✓ Within DLP</span>'
    return '<span class="dlp-expired">✗ DLP Expired</span>'


def _status_badge(status: str) -> str:
    """Return an HTML status badge string."""
    cls = f"status-{status.lower()}"
    return f'<span class="{cls}">{status}</span>'


def _format_ts(ts: str) -> str:
    """Parse and reformat an ISO timestamp into a readable string."""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%d %b %Y  %H:%M UTC")
    except Exception:
        return ts


# ─────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### 🛣️ A.R.I.A.")
    st.markdown("<small style='color:#6a8aaa;'>Autonomous Road Infrastructure Auditor</small>",
                unsafe_allow_html=True)
    st.divider()

    st.markdown("**🔍 Filters**")
    severity_filter = st.selectbox(
        "Severity",
        options=["ALL", "HIGH", "MEDIUM", "LOW"],
        index=0,
        key="severity_filter",
    )
    status_filter = st.selectbox(
        "Status",
        options=["ALL", "PENDING", "APPROVED", "REJECTED"],
        index=1,       # Default: show PENDING
        key="status_filter",
    )

    st.divider()
    st.markdown("<small style='color:#6a8aaa;'>🔄 Auto-refreshes every 30s</small>",
                unsafe_allow_html=True)

    if st.button("🔄 Refresh Now", use_container_width=True):
        st.rerun()

    st.divider()

    # API health indicator
    health = _api_get("/health")
    if health:
        st.success("🟢 API Online")
    else:
        st.error("🔴 API Offline")


# ─────────────────────────────────────────────────────────────
# Main Panel — Header
# ─────────────────────────────────────────────────────────────

st.markdown('<div class="aria-title">A.R.I.A. — Road Defect Review Dashboard</div>',
            unsafe_allow_html=True)
st.markdown('<div class="aria-subtitle">BRUHAT BENGALURU MAHANAGARA PALIKE | Road Infrastructure Department</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# Summary Metrics
# ─────────────────────────────────────────────────────────────

all_detections = _api_get("/detections") or []
total = len(all_detections)
pending = sum(1 for d in all_detections if d.get("status") == "PENDING")
approved = sum(1 for d in all_detections if d.get("status") == "APPROVED")
high_sev = sum(1 for d in all_detections if d.get("severity") == "HIGH")

col1, col2, col3, col4 = st.columns(4)
col1.metric("📋 Total Detections", total)
col2.metric("⏳ Pending Review", pending,
            delta=f"{pending} awaiting action", delta_color="inverse")
col3.metric("✅ Approved", approved)
col4.metric("🔴 High Severity", high_sev)

st.divider()

# ─────────────────────────────────────────────────────────────
# Build filtered detections list
# ─────────────────────────────────────────────────────────────

params = {}
if status_filter != "ALL":
    params["status"] = status_filter
if severity_filter != "ALL":
    params["severity"] = severity_filter

detections = _api_get("/detections", params=params) or []
all_notices = _api_get("/notices") or []
notices_map = {n.get("detection_id"): n for n in all_notices}

if not detections:
    st.info("No road defect detections match the current filters.")
else:
    st.markdown(f"**Showing {len(detections)} detection(s)** &nbsp;|&nbsp; "
                f"Status: `{status_filter}` &nbsp;|&nbsp; Severity: `{severity_filter}`",
                unsafe_allow_html=True)
    st.markdown("")

    # ─────────────────────────────────────────────────────────
    # Detection rows with expandable details
    # ─────────────────────────────────────────────────────────
    for det in detections:
        det_id = det.get("detection_id", "unknown")
        segment = det.get("segment_id", "Unknown Segment")
        severity = det.get("severity", "LOW")
        status = det.get("status", "PENDING")
        confidence = float(det.get("confidence", 0)) * 100
        ts = _format_ts(det.get("timestamp", ""))
        within_dlp = det.get("within_dlp", 0)
        contract_id = det.get("contract_id", "—")

        # Row header title
        expander_label = (
            f"{'🔴' if severity == 'HIGH' else '🟠' if severity == 'MEDIUM' else '🟢'}  "
            f"{segment}  ·  {severity}  ·  {status}  ·  {ts}"
        )

        with st.expander(expander_label, expanded=(status == "PENDING" and severity == "HIGH")):
            col_img, col_info = st.columns([1, 1.5])

            # ── Evidence image ──
            with col_img:
                frame_path = det.get("frame_path")
                if frame_path:
                    import os
                    if os.path.exists(frame_path):
                        st.image(frame_path, caption="Evidence Frame",
                                 use_container_width=True)
                    else:
                        st.markdown(
                            "<div style='background:#1a2030;border:1px dashed #334;border-radius:8px;"
                            "height:200px;display:flex;align-items:center;justify-content:center;"
                            "color:#445;font-size:13px;'>No evidence image on file</div>",
                            unsafe_allow_html=True,
                        )
                else:
                    st.markdown(
                        "<div style='background:#1a2030;border:1px dashed #334;border-radius:8px;"
                        "height:200px;display:flex;align-items:center;justify-content:center;"
                        "color:#445;font-size:13px;'>No evidence image on file</div>",
                        unsafe_allow_html=True,
                    )

            # ── Detection details ──
            with col_info:
                st.markdown(f"**Road Segment:** {segment}")
                st.markdown(
                    f"**Severity:** {_severity_badge(severity)} &nbsp;&nbsp; "
                    f"**Confidence:** `{confidence:.1f}%`",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"**DLP Status:** {_dlp_badge(within_dlp)} &nbsp;&nbsp; "
                    f"**Status:** {_status_badge(status)}",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"**GPS:** `{det.get('gps_lat', '—')}°, {det.get('gps_lon', '—')}°`")
                st.markdown(f"**Contract ID:** `{contract_id}`")
                st.markdown(f"**Bounding Box:** `{det.get('bbox_json', '—')}`")
                st.markdown(f"**Detection ID:** `{det_id[:12]}…`")

            st.divider()

            # ── Action buttons ──
            if status == "PENDING":
                btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 2])

                approve_key = f"approve_{det_id}"
                reject_key = f"reject_{det_id}"

                with btn_col1:
                    if st.button("✅ Approve Notice", key=approve_key, use_container_width=True):
                        result = _api_post(
                            f"/detections/{det_id}/approve", {"approved_by": "engineer"})
                        if result:
                            notice_id = result.get("notice_id", "")
                            st.success(
                                f"✅ Notice generated! Notice ID: `{notice_id[:12]}…`")
                            pdf_url = f"{API_URL}/notices/{notice_id}/pdf"
                            st.markdown(
                                f"📥 **[Download Enforcement Notice PDF]({pdf_url})**",
                                unsafe_allow_html=False,
                            )
                            time.sleep(1.5)
                            st.rerun()

                with btn_col2:
                    if st.button("❌ Reject", key=reject_key, use_container_width=True):
                        result = _api_post(f"/detections/{det_id}/reject")
                        if result:
                            st.warning(
                                "❌ Detection rejected. No notice will be issued.")
                            time.sleep(1.5)
                            st.rerun()

            elif status == "APPROVED":
                # Show download link for approved detections with a notice
                notice = notices_map.get(det_id)
                if notice:
                    notice_id = notice.get("notice_id", "")
                    pdf_url = f"{API_URL}/notices/{notice_id}/pdf"
                    st.markdown(
                        f"📥 **[Download Enforcement Notice PDF]({pdf_url})**")
                else:
                    st.markdown("*No notice PDF on record.*")

# ─────────────────────────────────────────────────────────────
# Auto-refresh every 30 seconds
# ─────────────────────────────────────────────────────────────

if "last_refresh" not in st.session_state:
    st.session_state["last_refresh"] = time.time()

elapsed = time.time() - st.session_state["last_refresh"]
if elapsed >= 30:
    st.session_state["last_refresh"] = time.time()
    st.rerun()

# Show countdown in sidebar
remaining_secs = max(0, int(30 - elapsed))
with st.sidebar:
    st.markdown(
        f"<small style='color:#6a8aaa;'>Next refresh in {remaining_secs}s</small>", unsafe_allow_html=True)
