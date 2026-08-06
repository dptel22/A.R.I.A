import pytest
from aria.inference.severity_calc import score

def test_score_valid_pothole():
    """Test standard valid execution for a 'pothole'."""
    det = {"class_name": "pothole", "bbox_w": 0.1, "bbox_h": 0.1, "confidence": 1.0}
    # Area = 0.01. area * 10 = 0.1. Weight = 1.1! Score = 4 * 1.1 * 1.0 = 4.4 (HIGH)
    result = score(det)
    assert result["severity_score"] == 4.4
    assert result["severity_level"] == "HIGH"
    # Ensure original dict is not mutated
    assert "severity_score" not in det

def test_score_unknown_class_fallback():
    """Test that an unknown class gracefully falls back to a base severity of 1."""
    det = {"class_name": "alien_crater", "bbox_w": 0.1, "bbox_h": 0.1, "confidence": 1.0}
    # base = 1. weight = 1.1 . score = 1.1 (LOW)
    result = score(det)
    assert result["severity_score"] == 1.1
    assert result["severity_level"] == "LOW"

def test_score_area_clipping_max():
    """Test that massive bounding boxes are clamped at a 2.0 multiplier."""
    det = {"class_name": "pothole", "bbox_w": 0.9, "bbox_h": 0.9, "confidence": 1.0}
    # Area = 0.81. area * 10 = 8.1. Clamped to 1.0. Weight = 2.0. Score = 8.0 (CRITICAL)
    result = score(det)
    assert result["severity_score"] == 8.0
    assert result["severity_level"] == "CRITICAL"

def test_score_area_zero_min():
    """Test zero dimensions do not break math and result in a 1.0 multiplier."""
    det = {"class_name": "transverse_crack", "bbox_w": 0.0, "bbox_h": 0.0, "confidence": 1.0}
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
        score({"class_name": "pothole", "bbox_w": "large", "bbox_h": "large", "confidence": 0.9})

def test_score_out_of_range_confidence_throws_valueerror():
    """Test confidence outside [0, 1] fails fast."""
    with pytest.raises(ValueError, match="confidence"):
        score({"class_name": "pothole", "bbox_w": 0.1, "bbox_h": 0.1, "confidence": 1.5})

def test_score_defaults_missing_confidence_to_full_weight():
    """Test that a detection without a confidence key keeps full weight."""
    det = {"class_name": "pothole", "bbox_w": 0.1, "bbox_h": 0.1}
    result = score(det)
    assert result["severity_score"] == 4.4
    assert result["severity_level"] == "HIGH"

def test_score_folds_confidence_into_score():
    """Test that confidence scales the composite severity score."""
    def make(confidence):
        return score({"class_name": "pothole", "bbox_w": 0.5, "bbox_h": 0.5, "confidence": confidence})

    low = make(0.2)
    mid = make(0.5)
    high = make(0.95)
    # Area = 0.25, weight = 2.0, base = 4 -> 8.0 * confidence
    assert low["severity_score"] == pytest.approx(1.6)
    assert mid["severity_score"] == pytest.approx(4.0)
    assert high["severity_score"] == pytest.approx(7.6)
    assert low["severity_score"] < mid["severity_score"] < high["severity_score"]

def test_score_low_confidence_never_reaches_high_or_critical():
    """Test that noise near the admission threshold cannot be HIGH/CRITICAL."""
    # Max-area pothole (base 4, weight 2.0) at the 0.12 confidence threshold.
    result = score({"class_name": "pothole", "bbox_w": 0.9, "bbox_h": 0.9, "confidence": 0.12})
    assert result["severity_score"] == pytest.approx(0.96)
    assert result["severity_level"] not in {"HIGH", "CRITICAL"}

def test_score_low_confidence_box_never_outranks_high_confidence_same_class():
    """Test monotonicity: same class + bbox, higher confidence always outranks."""
    def make(confidence):
        return score({"class_name": "alligator_crack", "bbox_w": 0.9, "bbox_h": 0.9, "confidence": confidence})

    for low_conf, high_conf in ((0.12, 0.95), (0.3, 0.5), (0.5, 0.51)):
        low = make(low_conf)
        high = make(high_conf)
        assert high["severity_score"] > low["severity_score"]
