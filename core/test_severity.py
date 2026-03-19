"""
core/test_severity.py — Unit tests for severity routing logic.
"""
import pytest

from core.models import ActionType, SeverityLevel
from core.severity import determine_action


@pytest.mark.parametrize(
    "severity_input, expected_action",
    [
        (SeverityLevel.LOW, ActionType.LOG_ONLY),
        (SeverityLevel.MEDIUM, ActionType.FLAG_INSPECTOR),
        (SeverityLevel.HIGH, ActionType.ENFORCE),
        (SeverityLevel.CRITICAL, ActionType.ENFORCE),
        ("damage_low", ActionType.LOG_ONLY),
        ("damage_medium", ActionType.FLAG_INSPECTOR),
        ("damage_high", ActionType.ENFORCE),
        ("damage_critical", ActionType.ENFORCE),
    ],
)
def test_determine_action_valid_inputs(severity_input, expected_action):
    """Test valid Enum and string inputs map to the correct ActionType."""
    assert determine_action(severity_input) == expected_action


@pytest.mark.parametrize(
    "invalid_input",
    [
        "",
        "INVALID",
        "LOW",  # Valid as Enum key, but not the Enum value ("damage_low")
        "damage_unknown",
        123,
        None,
        [],
        {},
        object(),
    ],
)
def test_determine_action_rejects_invalid_types(invalid_input):
    """Test that invalid, empty, or uncastable types raise a ValueError."""
    with pytest.raises(ValueError):
        determine_action(invalid_input)
