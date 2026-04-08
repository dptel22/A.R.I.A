"""Severity action mapping for A.R.I.A."""
from __future__ import annotations

from aria.domain.models import ActionType, SeverityLevel


def determine_action(severity: SeverityLevel | str) -> ActionType:
    if isinstance(severity, str):
        try:
            severity = SeverityLevel(severity)
        except ValueError:
            raise ValueError(f"Unknown severity level: {severity!r}")

    mapping = {
        SeverityLevel.LOW: ActionType.LOG_ONLY,
        SeverityLevel.MEDIUM: ActionType.FLAG_INSPECTOR,
        SeverityLevel.HIGH: ActionType.ENFORCE,
        SeverityLevel.CRITICAL: ActionType.ENFORCE,
    }

    action = mapping.get(severity)
    if action is None:
        raise ValueError(
            f"No action mapping defined for severity level: {severity!r}. "
            f"Known levels: {list(mapping.keys())}"
        )
    return action
