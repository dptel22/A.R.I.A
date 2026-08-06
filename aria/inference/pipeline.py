"""
aria/inference/pipeline.py - Full detection pipeline for A.R.I.A.

Single responsibility: orchestrate bytes to scored detections.
This is the main entrypoint the inspection service should call.
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
from PIL import Image, UnidentifiedImageError

from aria.inference.detector import detect
from aria.inference.preprocess import preprocess
from aria.inference.severity_calc import score

log: logging.Logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PipelineResult:
    status: str
    detections: list[dict[str, Any]]
    failure_reason: str | None = None
    error_code: str | None = None


def run_pipeline(img_bytes: bytes, model: Any) -> PipelineResult:
    """
    Full inference pipeline: raw image bytes to a structured pipeline outcome.

    Each detection dict contains:
        class_id, class_name, confidence,
        bbox_x, bbox_y, bbox_w, bbox_h,
        severity_score, severity_level
    """
    if model is None:
        log.warning("run_pipeline called with no model loaded")
        return PipelineResult(
            status="FAILED",
            detections=[],
            failure_reason="YOLO model not loaded.",
            error_code="MODEL_UNAVAILABLE",
        )

    try:
        img_pil = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        # Ultralytics treats numpy HWC sources as OpenCV-compatible BGR, so we
        # convert once from the PIL RGB decode and keep the whole pipeline in
        # BGR.  CLAHE's L channel is order-independent, so this yields exactly
        # the same pixels the demo script feeds to model.predict().
        img_array = np.ascontiguousarray(np.array(img_pil)[:, :, ::-1])
        # Shared train/inference preprocess path (letterbox + CLAHE-LAB).
        img_array = preprocess(img_array, color_order="bgr")

        raw_detections = detect(img_array, model)
        if not raw_detections:
            return PipelineResult(status="NO_DETECTIONS", detections=[])

        scored = [score(det) for det in raw_detections]
        scored.sort(key=lambda detection: detection["severity_score"], reverse=True)

        log.info(
            "Pipeline: %d detections, primary=%s (%s, score=%.2f)",
            len(scored),
            scored[0]["class_name"],
            scored[0]["severity_level"],
            scored[0]["severity_score"],
        )

        return PipelineResult(status="SUCCEEDED", detections=scored)

    except UnidentifiedImageError:
        log.warning("Pipeline failed: uploaded file is not a valid image")
        return PipelineResult(
            status="FAILED",
            detections=[],
            failure_reason="Uploaded file could not be decoded as a valid image.",
            error_code="INVALID_IMAGE",
        )
    except Exception as exc:
        log.error("Pipeline failed: %s", exc, exc_info=True)
        return PipelineResult(
            status="FAILED",
            detections=[],
            failure_reason="Inference pipeline failed while processing the uploaded image.",
            error_code="PIPELINE_ERROR",
        )
