"""
inference/pipeline.py — Full detection pipeline for A.R.I.A.

Single responsibility: orchestrate bytes → scored detections.
This is the ONLY function that api/routes.py should call.
"""
from __future__ import annotations

import io
import logging
from typing import Any

import numpy as np
from PIL import Image

from inference.detector import detect
from inference.severity_calc import score

log: logging.Logger = logging.getLogger(__name__)


def run_pipeline(img_bytes: bytes, model: Any) -> list[dict[str, Any]]:
    """
    Full inference pipeline: raw image bytes → list of scored detection dicts.

    Each returned dict contains:
        class_id, class_name, confidence,
        bbox_x, bbox_y, bbox_w, bbox_h,
        severity_score, severity_level

    Returns an empty list if *model* is None, no detections are found,
    or any error occurs during processing.

    **Never raises** — all exceptions are caught and logged so the HTTP
    request handler receives an empty list rather than a 500 error.
    """
    if model is None:
        log.warning("run_pipeline called with no model loaded")
        return []

    try:
        # Convert bytes → RGB numpy array
        img_pil = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        img_array = np.array(img_pil)

        # Stage 1: raw detections from YOLO
        raw_detections = detect(img_array, model)

        if not raw_detections:
            return []

        # Stage 2: add severity score + level to each detection
        scored = [score(det) for det in raw_detections]

        # Sort by severity_score descending — index 0 = primary defect
        scored.sort(key=lambda d: d["severity_score"], reverse=True)

        log.info(
            "Pipeline: %d detections, primary=%s (%s, score=%.2f)",
            len(scored),
            scored[0]["class_name"],
            scored[0]["severity_level"],
            scored[0]["severity_score"],
        )

        return scored

    except Exception as e:
        log.error("Pipeline failed: %s", e, exc_info=True)
        return []
