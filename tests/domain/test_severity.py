import pytest
from aria.domain.models import ActionType
from aria.domain.severity import determine_action

@pytest.mark.parametrize("invalid_input", [
    "INVALID",
    "",
    "123",
    "nonsense_string",
    "CRITICAL_TYPO"
])
def test_determine_action_invalid_string_severity(invalid_input):
    """
    Test that determine_action strictly rejects invalid string inputs.
    It should raise a ValueError instead of silently allowing them.
    """
    with pytest.raises(ValueError, match="Unknown severity level"):
        determine_action(invalid_input)
