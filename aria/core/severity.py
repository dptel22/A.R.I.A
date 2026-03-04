"""
core/severity.py — A.R.I.A. Road Damage Severity Scorer
Computes severity level from bounding box area relative to the lane surface.
"""


def compute_severity(
    bbox: list,
    frame_width: int,
    frame_height: int,
) -> dict:
    """
    Compute severity of a detected road_damage from its bounding box.

    The road surface is assumed to occupy the bottom 40% of the frame
    (i.e., the lane area). The defect's area is compared to this lane area
    to produce a ratio that drives severity classification.

    Args:
        bbox (list): Bounding box as [x1, y1, x2, y2] in pixel coordinates.
        frame_width (int): Width of the source video frame in pixels.
        frame_height (int): Height of the source video frame in pixels.

    Returns:
        dict with keys:
            - severity (str): 'LOW' | 'MEDIUM' | 'HIGH'
            - score (float): Defect-area / lane-area ratio (0.0–1.0+)
            - action (str): Recommended action for this severity level

    Severity thresholds:
        LOW    → score < 0.05        (< 5%)  → log_only
        MEDIUM → 0.05 ≤ score < 0.15 (5–15%) → flag_inspector
        HIGH   → score ≥ 0.15        (≥ 15%) → enforce
    """
    x1, y1, x2, y2 = bbox

    # --- Defect bounding box area ---
    defect_width = abs(x2 - x1)
    defect_height = abs(y2 - y1)
    defect_area = defect_width * defect_height

    # --- Lane area: bottom 40% of the frame ---
    lane_height = frame_height * 0.40
    lane_area = frame_width * lane_height

    # Guard against zero-area frames (shouldn't happen in production)
    if lane_area <= 0:
        return {
            "severity": "LOW",
            "score": 0.0,
            "action": "log_only",
        }

    score = defect_area / lane_area

    # --- Severity classification ---
    if score >= 0.15:
        severity = "HIGH"
        action = "enforce"
    elif score >= 0.05:
        severity = "MEDIUM"
        action = "flag_inspector"
    else:
        severity = "LOW"
        action = "log_only"

    return {
        "severity": severity,
        "score": round(score, 4),
        "action": action,
    }
