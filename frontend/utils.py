"""
frontend/utils.py — Shared helpers for the A.R.I.A. Streamlit dashboard.

Provides:
    API client functions (get, post image)
    Severity colour scheme and badge renderer
    Bounding box overlay on images
"""
from __future__ import annotations

import io
import logging
import os
from typing import Any

import requests
import streamlit as st
from PIL import Image, ImageDraw, ImageFont

log: logging.Logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_BASE: str = "http://localhost:8000/api/v1"

SEVERITY_COLOURS: dict[str, str] = {
    "CRITICAL": "#FF0000",   # red
    "HIGH":     "#FF6600",   # orange
    "MEDIUM":   "#FFB300",   # amber
    "LOW":      "#4CAF50",   # green
    "NONE":     "#9E9E9E",   # grey
}

SEVERITY_ORDER: dict[str, int] = {
    "CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "NONE": 0,
}


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def get_api_key() -> str:
    """
    Read the API key from Streamlit secrets or environment.

    Checks ``st.secrets["ARIA_API_KEY"]`` first, then falls back to
    the ``ARIA_API_KEY`` environment variable.

    Raises:
        RuntimeError: If no key is found in either location.
    """
    # Streamlit secrets (from .streamlit/secrets.toml)
    try:
        key = st.secrets["ARIA_API_KEY"]
        if key:
            return str(key)
    except (KeyError, FileNotFoundError):
        pass

    # Environment variable
    key = os.environ.get("ARIA_API_KEY", "")
    if key:
        return key

    raise RuntimeError(
        "ARIA_API_KEY not found. Set it in .streamlit/secrets.toml "
        "or as an environment variable."
    )


# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------

def api_get(endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """
    Make an authenticated GET request to the A.R.I.A. API.

    Returns the JSON response on success, or None on error
    (error messages are displayed via ``st.error``).
    """
    try:
        headers = {"x-api-key": get_api_key()}
        resp = requests.get(
            f"{API_BASE}{endpoint}",
            headers=headers,
            params=params,
            timeout=10,
        )
    except requests.ConnectionError:
        st.error("Cannot connect to the API server. Is `uvicorn api.app:app` running?")
        return None
    except RuntimeError as e:
        st.error(str(e))
        return None

    if resp.status_code == 200:
        return resp.json()
    if resp.status_code == 401:
        st.error("❌ Invalid API key. Check your ARIA_API_KEY.")
        return None
    if resp.status_code == 404:
        return None

    st.error(f"API error {resp.status_code}: {resp.text[:200]}")
    return None


def api_post_image(
    endpoint: str,
    img_bytes: bytes,
    filename: str,
    lat: float,
    lng: float,
) -> dict[str, Any] | None:
    """
    POST an image + GPS coordinates to the A.R.I.A. detection endpoint.

    Returns the JSON response on success, or None on error.
    """
    try:
        headers = {"x-api-key": get_api_key()}
        files = {"file": (filename, img_bytes, "image/jpeg")}
        data = {"lat": str(lat), "lng": str(lng)}
        resp = requests.post(
            f"{API_BASE}{endpoint}",
            headers=headers,
            files=files,
            data=data,
            timeout=30,
        )
    except requests.ConnectionError:
        st.error("Cannot connect to the API server. Is `uvicorn api.app:app` running?")
        return None
    except RuntimeError as e:
        st.error(str(e))
        return None

    if resp.status_code == 200:
        return resp.json()
    if resp.status_code == 404:
        st.warning("⚠️ No road segment found at these GPS coordinates.")
        return None
    if resp.status_code == 503:
        st.error("🔴 YOLO model not loaded. Check the server logs.")
        return None

    st.error(f"Detection failed ({resp.status_code}): {resp.text[:200]}")
    return None


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------

def severity_badge(level: str) -> str:
    """Return an HTML badge span styled with the severity colour."""
    colour = SEVERITY_COLOURS.get(level, "#9E9E9E")
    return (
        f'<span style="background:{colour};color:white;padding:4px 12px;'
        f'border-radius:4px;font-weight:bold;font-size:0.9em">{level}</span>'
    )


def draw_boxes_on_image(
    img_bytes: bytes,
    detections: list[dict[str, Any]],
) -> Image.Image:
    """
    Draw bounding boxes on an image using detection data.

    Converts normalised centre-format bboxes (bbox_x, bbox_y, bbox_w, bbox_h)
    to pixel coordinates and draws coloured rectangles with labels.

    Args:
        img_bytes: Raw image bytes.
        detections: List of detection dicts from the API.

    Returns:
        Annotated PIL Image.
    """
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    draw = ImageDraw.Draw(img)
    w, h = img.size

    # Try to use a decent font, fall back to default
    try:
        font = ImageFont.truetype("arial.ttf", size=max(14, h // 40))
    except (OSError, IOError):
        font = ImageFont.load_default()

    for det in detections:
        sev = det.get("severity_level", "NONE")
        colour = SEVERITY_COLOURS.get(sev, "#9E9E9E")

        # Normalised centre-x, centre-y, width, height → pixel corners
        cx = det["bbox_x"] * w
        cy = det["bbox_y"] * h
        bw = det["bbox_w"] * w
        bh = det["bbox_h"] * h
        x1 = cx - bw / 2
        y1 = cy - bh / 2
        x2 = cx + bw / 2
        y2 = cy + bh / 2

        # Rectangle
        thickness = max(2, h // 200)
        for i in range(thickness):
            draw.rectangle([x1 - i, y1 - i, x2 + i, y2 + i], outline=colour)

        # Label above box
        label = f"{det['class_name'].replace('_', ' ')} {det['confidence']:.0%}"
        text_bbox = draw.textbbox((x1, y1), label, font=font)
        text_h = text_bbox[3] - text_bbox[1]
        draw.rectangle(
            [x1, y1 - text_h - 6, text_bbox[2] + 4, y1],
            fill=colour,
        )
        draw.text((x1 + 2, y1 - text_h - 4), label, fill="white", font=font)

    return img
