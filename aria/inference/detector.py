"""
aria/inference/detector.py - YOLO model wrapper for A.R.I.A.

Single responsibility: accept a numpy array + loaded YOLO model,
run inference, return a list of raw detection dicts.
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np

log: logging.Logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants previously hardcoded in the legacy monolithic API layer.
# ---------------------------------------------------------------------------

EXPECTED_CLASS_NAMES: set[str] = {
    "longitudinal_crack",
    "transverse_crack",
    "alligator_crack",
    "pothole",
}

CONF_THRESHOLD: float = 0.25
IOU_THRESHOLD: float = 0.45


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _resolve_class_names(model: Any) -> dict[int, str]:
    cached = getattr(model, "_aria_class_names", None)
    if cached is not None:
        return cached

    model_names = getattr(model, "names", None)
    if model_names is None:
        raise ValueError("YOLO model metadata is missing `names`; cannot map defect classes safely.")

    if isinstance(model_names, dict):
        class_names = {int(class_id): str(name) for class_id, name in model_names.items()}
    elif isinstance(model_names, list):
        class_names = {index: str(name) for index, name in enumerate(model_names)}
    else:
        raise ValueError(f"Unsupported YOLO model.names metadata type: {type(model_names)!r}")

    available = set(class_names.values())
    missing = EXPECTED_CLASS_NAMES - available
    if missing:
        raise ValueError(
            "YOLO model metadata is missing expected defect classes: "
            + ", ".join(sorted(missing))
        )

    model._aria_class_names = class_names
    return class_names

def detect(img_array: np.ndarray, model: Any) -> list[dict[str, Any]]:
    """
    Run YOLO inference on a numpy image array.

    Args:
        img_array: RGB image as ``np.ndarray`` with shape ``(H, W, 3)``.
        model: A loaded Ultralytics YOLO model object.

    Returns:
        List of raw detection dicts sorted by confidence descending.
        Each dict contains:
            class_id, class_name, confidence,
            bbox_x, bbox_y, bbox_w, bbox_h  (normalised 0-1)

    Raises:
        ValueError: If *img_array* is None or has the wrong shape.
    """
    if img_array is None or img_array.ndim != 3 or img_array.shape[2] != 3:
        raise ValueError(
            f"Expected (H, W, 3) RGB numpy array, "
            f"got {'None' if img_array is None else img_array.shape}"
        )

    class_names = _resolve_class_names(model)

    results = model.predict(
        source=img_array,
        conf=CONF_THRESHOLD,
        iou=IOU_THRESHOLD,
        verbose=False,
        imgsz=640,
    )

    # Guard: no results or no boxes
    if not results or results[0].boxes is None or len(results[0].boxes) == 0:
        return []

    raw: list[dict[str, Any]] = []
    for box in results[0].boxes:
        class_id = int(box.cls[0])
        if class_id not in class_names:
            raise ValueError(f"YOLO returned unknown class id {class_id}; model metadata is inconsistent.")
        class_name = class_names[class_id]
        confidence = float(box.conf[0])

        # Normalised centre-x, centre-y, width, height
        xywhn = box.xywhn[0]
        bbox_x = round(float(xywhn[0]), 4)
        bbox_y = round(float(xywhn[1]), 4)
        bbox_w = round(float(xywhn[2]), 4)
        bbox_h = round(float(xywhn[3]), 4)

        raw.append({
            "class_id": class_id,
            "class_name": class_name,
            "confidence": round(confidence, 4),
            "bbox_x": bbox_x,
            "bbox_y": bbox_y,
            "bbox_w": bbox_w,
            "bbox_h": bbox_h,
        })

    # Sort by confidence descending — highest-confidence detection first
    raw.sort(key=lambda d: d["confidence"], reverse=True)

    log.debug("Detected %d objects", len(raw))
    return raw
