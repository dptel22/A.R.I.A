"""
inference/test_severity_calc.py — Unit tests for inference scoring calculations.
"""
import pytest

from inference.severity_calc import score


def test_score_basic_pothole():
    """Test standard scoring for a pothole detection."""
    detection = {
        "class_name": "pothole",
        "bbox_w": 0.1,
        "bbox_h": 0.1,
        "confidence": 0.95
    }
    # Area = 0.01, Area weight = 1.0 + min(0.1, 1.0) = 1.1
    # Base = 4
    # Score = 4 * 1.1 = 4.4 -> HIGH
    result = score(detection)
    assert result is not detection  # Ensure it returns a new dict
    assert result["class_name"] == "pothole"
    assert result["severity_score"] == 4.4
    assert result["severity_level"] == "HIGH"
    assert result["confidence"] == 0.95  # other keys are preserved


def test_score_alligator_crack_critical():
    """Test scoring for alligator crack that hits critical threshold."""
    detection = {
        "class_name": "alligator_crack",
        "bbox_w": 0.5,
        "bbox_h": 0.5,
    }
    # Area = 0.25, Area weight = 1.0 + min(2.5, 1.0) = 2.0
    # Base = 3
    # Score = 3 * 2.0 = 6.0 -> CRITICAL
    result = score(detection)
    assert result["severity_score"] == 6.0
    assert result["severity_level"] == "CRITICAL"


def test_score_transverse_crack_medium():
    """Test scoring for transverse crack with default severity."""
    detection = {
        "class_name": "transverse_crack",
        "bbox_w": 0.0,
        "bbox_h": 0.0,
    }
    # Area = 0, Area weight = 1.0 + min(0, 1.0) = 1.0
    # Base = 2
    # Score = 2 * 1.0 = 2.0 -> MEDIUM
    result = score(detection)
    assert result["severity_score"] == 2.0
    assert result["severity_level"] == "MEDIUM"


def test_score_longitudinal_crack_low():
    """Test scoring for longitudinal crack with minimum severity."""
    detection = {
        "class_name": "longitudinal_crack",
        "bbox_w": 0.01,
        "bbox_h": 0.01,
    }
    # Area = 0.0001, Area weight = 1.0 + min(0.001, 1.0) = 1.001
    # Base = 1
    # Score = 1 * 1.001 = 1.001 -> LOW
    result = score(detection)
    assert result["severity_score"] == 1.001
    assert result["severity_level"] == "LOW"


def test_score_unknown_class():
    """Test scoring handles unknown classes gracefully with default base 1."""
    detection = {
        "class_name": "unknown_defect",
        "bbox_w": 0.1,
        "bbox_h": 0.1,
    }
    # Base should default to 1.
    # Area = 0.01, Area weight = 1.1
    # Score = 1 * 1.1 = 1.1 -> LOW
    result = score(detection)
    assert result["severity_score"] == 1.1
    assert result["severity_level"] == "LOW"


def test_score_missing_keys():
    """Test missing keys raise KeyError."""
    with pytest.raises(KeyError):
        score({"bbox_w": 0.1, "bbox_h": 0.1})  # Missing class_name

    with pytest.raises(KeyError):
        score({"class_name": "pothole", "bbox_h": 0.1})  # Missing bbox_w

    with pytest.raises(KeyError):
        score({"class_name": "pothole", "bbox_w": 0.1})  # Missing bbox_h
