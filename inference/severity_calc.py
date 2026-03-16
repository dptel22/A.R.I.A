"""
inference/severity_calc.py — Pure severity scoring for A.R.I.A.

Single responsibility: take one raw detection dict, compute severity_score
and severity_level. Zero I/O, zero model calls, fully unit-testable.
"""
from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Constants (previously hardcoded in api/routes.py)
# ---------------------------------------------------------------------------

BASE_SEVERITY: dict[str, int] = {
    "pothole":            4,   # CRITICAL — 9,438 deaths India 2020-2024
    "alligator_crack":    3,   # HIGH — structural failure precursor
    "transverse_crack":   2,   # MEDIUM — full-width spalling risk
    "longitudinal_crack": 1,   # LOW — surface issue
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def score(detection: dict[str, Any]) -> dict[str, Any]:
    """
    Score a single detection dict.

    Takes a raw detection dict from ``detector.detect()`` and returns a
    **new** dict with two additional keys: ``severity_score`` and
    ``severity_level``.  Does **not** modify the input dict.

    Args:
        detection: Dict with at least ``class_name``, ``bbox_w``, ``bbox_h``.

    Returns:
        New dict with all original keys plus ``severity_score`` (float)
        and ``severity_level`` (str: LOW / MEDIUM / HIGH / CRITICAL).
    """
    class_name = detection["class_name"]
    bbox_w = detection["bbox_w"]
    bbox_h = detection["bbox_h"]

    base = BASE_SEVERITY.get(class_name, 1)
    area_ratio = bbox_w * bbox_h
    area_weight = 1.0 + min(area_ratio * 10, 1.0)  # clamps [1.0, 2.0]
    sev_score = round(base * area_weight, 3)

    sev_level = _map_score_to_level(sev_score)

    return {**detection, "severity_score": sev_score, "severity_level": sev_level}


def _map_score_to_level(score_value: float) -> str:
    """Map a composite severity score to a human-readable level."""
    if score_value >= 6.0:
        return "CRITICAL"
    if score_value >= 4.0:
        return "HIGH"
    if score_value >= 2.0:
        return "MEDIUM"
    return "LOW"
