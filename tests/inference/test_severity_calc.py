import pytest
from aria.inference.severity_calc import score

def test_score_valid_pothole():
    """Test standard valid execution for a 'pothole'."""
    det = {"class_name": "pothole", "bbox_w": 0.1, "bbox_h": 0.1}
    # Area = 0.01. area * 10 = 0.1. Weight = 1.1! Score = 4 * 1.1 = 4.4 (HIGH)
    result = score(det)
    assert result["severity_score"] == 4.4
    assert result["severity_level"] == "HIGH"
    # Ensure original dict is not mutated
    assert "severity_score" not in det

def test_score_unknown_class_fallback():
    """Test that an unknown class gracefully falls back to a base severity of 1."""
    det = {"class_name": "alien_crater", "bbox_w": 0.1, "bbox_h": 0.1}
    # base = 1. weight = 1.1 . score = 1.1 (LOW)
    result = score(det)
    assert result["severity_score"] == 1.1
    assert result["severity_level"] == "LOW"

def test_score_area_clipping_max():
    """Test that massive bounding boxes are clamped at a 2.0 multiplier."""
    det = {"class_name": "pothole", "bbox_w": 0.9, "bbox_h": 0.9}
    # Area = 0.81. area * 10 = 8.1. Clamped to 1.0. Weight = 2.0. Score = 8.0 (CRITICAL)
    result = score(det)
    assert result["severity_score"] == 8.0
    assert result["severity_level"] == "CRITICAL"

def test_score_area_zero_min():
    """Test zero dimensions do not break math and result in a 1.0 multiplier."""
    det = {"class_name": "transverse_crack", "bbox_w": 0.0, "bbox_h": 0.0}
    # base = 2. area = 0. weight = 1.0. Score = 2.0 (MEDIUM)
    result = score(det)
    assert result["severity_score"] == 2.0
    assert result["severity_level"] == "MEDIUM"

def test_score_missing_keys_throws_keyerror():
    """Test strict mapping fails fast on malformed dictionary inputs."""
    with pytest.raises(KeyError):
        score({"class_name": "pothole"})  # missing bbox_w and bbox_h

def test_score_invalid_types_throws_typeerror():
    """Test that mathematical operations fail fast on string dimensions."""
    with pytest.raises(TypeError):
        score({"class_name": "pothole", "bbox_w": "large", "bbox_h": "large"})
