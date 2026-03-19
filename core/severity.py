"""
core/severity.py — Severity Action Mapping for A.R.I.A.
"""
from __future__ import annotations

from core.models import ActionType, SeverityLevel


def determine_action(severity: SeverityLevel | str) -> ActionType:
    """
    Map a YOLOv11 native severity class to a business action.

    Args:
        severity: The detected severity Enum or string.

    Returns:
        The evaluated ActionType enum.

    Raises:
        ValueError: If an unknown severity is passed.
    """
    # Allow loose string passing for backwards compatibility in tests, but cast to Enum
    if isinstance(severity, str):
        try:
            severity = SeverityLevel(severity)
        except ValueError:
            raise ValueError(f"Unknown severity level: {severity!r}")

    mapping = {
        SeverityLevel.LOW:      ActionType.LOG_ONLY,
        SeverityLevel.MEDIUM:   ActionType.FLAG_INSPECTOR,
        SeverityLevel.HIGH:     ActionType.ENFORCE,
        SeverityLevel.CRITICAL: ActionType.ENFORCE,
    }

    try:
        action = mapping.get(severity)
    except TypeError:
        # e.g. unhashable types like list or dict
        raise ValueError(f"Invalid severity type: {type(severity)}")
    if action is None:
        raise ValueError(
            f"No action mapping defined for severity level: {severity!r}. "
            f"Known levels: {list(mapping.keys())}"
        )
    return action
