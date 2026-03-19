import pytest

from core.models import ActionType
from core.severity import determine_action

@pytest.mark.parametrize(
    "invalid_severity",
    [
        "",
        "INVALID",
        "123",
        "nonsense_string",
        "CRITICAL_TYPO",
    ]
)
def test_determine_action_invalid_string_severity(invalid_severity):
    with pytest.raises(ValueError, match="Unknown severity level"):
        determine_action(invalid_severity)
