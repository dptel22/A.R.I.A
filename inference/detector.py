"""
inference/detector.py — YOLO model wrapper for A.R.I.A.

Single responsibility: accept a numpy array + loaded YOLO model,
run inference, return a list of raw detection dicts.
"""
from __future__ import annotations

import logging
from typing import Any

log: logging.Logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants (previously hardcoded in api/routes.py)
# ---------------------------------------------------------------------------

CLASS_NAMES: dict[int, str] = {
    0: "longitudinal_crack",
    1: "transverse_crack",
    2: "alligator_crack",
    3: "pothole",
}

CONF_THRESHOLD: float = 0.25
IOU_THRESHOLD: float = 0.45


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect(img_array: Any, model: Any) -> list[dict[str, Any]]:
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
        class_name = CLASS_NAMES.get(class_id, f"unknown_{class_id}")
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
