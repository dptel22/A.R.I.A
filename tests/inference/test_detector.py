import math
import threading
import time

import numpy as np
import pytest

from aria.inference.detector import detect


class FakeBox:
    def __init__(self, class_id: int, confidence: float = 0.9):
        self.cls = np.array([class_id], dtype=float)
        self.conf = np.array([confidence], dtype=float)
        self.xywhn = np.array([[0.5, 0.5, 0.25, 0.25]], dtype=float)


class FakeResult:
    def __init__(self, boxes):
        self.boxes = boxes


class FakeModel:
    def __init__(self, names):
        self.names = names

    def predict(self, **kwargs):
        return [FakeResult([FakeBox(3), FakeBox(0, 0.8)])]


def test_detect_uses_model_metadata_for_class_mapping():
    model = FakeModel(
        {
            0: "pothole",
            1: "alligator_crack",
            2: "transverse_crack",
            3: "longitudinal_crack",
        }
    )

    detections = detect(np.zeros((32, 32, 3), dtype=np.uint8), model)

    assert detections[0]["class_name"] == "longitudinal_crack"
    assert detections[1]["class_name"] == "pothole"


def test_detect_rejects_missing_expected_model_labels():
    model = FakeModel({0: "pothole", 1: "alligator_crack", 2: "transverse_crack"})

    with pytest.raises(ValueError, match="missing expected defect classes"):
        detect(np.zeros((32, 32, 3), dtype=np.uint8), model)


def test_float_env_clamps_above_one(monkeypatch):
    import aria.inference.detector as detector_module

    monkeypatch.setenv("ARIA_MODEL_CONF_TEST", "1.5")
    assert detector_module._float_env("ARIA_MODEL_CONF_TEST", 0.12) == 1.0


def test_float_env_rejects_non_positive(monkeypatch):
    import aria.inference.detector as detector_module

    monkeypatch.setenv("ARIA_MODEL_IOU_TEST", "0")
    assert detector_module._float_env("ARIA_MODEL_IOU_TEST", 0.45) == 0.45
    monkeypatch.setenv("ARIA_MODEL_IOU_TEST", "-0.5")
    assert detector_module._float_env("ARIA_MODEL_IOU_TEST", 0.45) == 0.45


def test_float_env_accepts_valid_in_range(monkeypatch):
    import aria.inference.detector as detector_module

    monkeypatch.setenv("ARIA_MODEL_CONF_TEST", "0.25")
    assert detector_module._float_env("ARIA_MODEL_CONF_TEST", 0.12) == 0.25
    monkeypatch.setenv("ARIA_MODEL_CONF_TEST", "1.0")
    assert detector_module._float_env("ARIA_MODEL_CONF_TEST", 0.12) == 1.0


def test_float_env_invalid_uses_default(monkeypatch):
    import aria.inference.detector as detector_module

    monkeypatch.setenv("ARIA_MODEL_CONF_TEST", "abc")
    assert detector_module._float_env("ARIA_MODEL_CONF_TEST", 0.12) == 0.12


def test_float_env_nan_uses_default(monkeypatch):
    import aria.inference.detector as detector_module

    monkeypatch.setenv("ARIA_MODEL_CONF_TEST", "nan")
    value = detector_module._float_env("ARIA_MODEL_CONF_TEST", 0.12)
    assert value == 0.12
    import math
    assert not math.isnan(value)


def test_detect_serializes_predict_with_lock(monkeypatch):
    """F4: model.predict must be guarded by the module-level lock."""
    import aria.inference.detector as detector_module

    acquisitions: list[str] = []

    class RecordingLock:
        def __enter__(self):
            acquisitions.append("acquired")
            return self

        def __exit__(self, *exc):
            acquisitions.append("released")
            return False

    monkeypatch.setattr(detector_module, "_PREDICT_LOCK", RecordingLock())

    model = FakeModel(
        {
            0: "longitudinal_crack",
            1: "transverse_crack",
            2: "alligator_crack",
            3: "pothole",
        }
    )
    detections = detector_module.detect(np.zeros((32, 32, 3), dtype=np.uint8), model)

    assert acquisitions == ["acquired", "released"]
    assert detections  # predict still ran and produced detections


def test_detect_passes_runtime_inference_settings(monkeypatch):
    import aria.inference.detector as detector_module

    class CapturingModel(FakeModel):
        def __init__(self):
            super().__init__(
                {
                    0: "longitudinal_crack",
                    1: "transverse_crack",
                    2: "alligator_crack",
                    3: "pothole",
                }
            )
            self.kwargs = None

        def predict(self, **kwargs):
            self.kwargs = kwargs
            return [FakeResult([])]

    model = CapturingModel()
    monkeypatch.setattr(detector_module, "CONF_THRESHOLD", 0.07)
    monkeypatch.setattr(detector_module, "IOU_THRESHOLD", 0.33)
    monkeypatch.setattr(detector_module, "TEST_TIME_AUGMENT", True)

    detections = detector_module.detect(np.zeros((32, 32, 3), dtype=np.uint8), model)

    assert detections == []
    assert model.kwargs["conf"] == 0.07
    assert model.kwargs["iou"] == 0.33
    assert model.kwargs["augment"] is True
    assert model.kwargs["imgsz"] == 640


def test_float_env_rejects_nan(monkeypatch):
    import aria.inference.detector as detector_module

    monkeypatch.setenv("ARIA_MODEL_CONF_TEST", "nan")
    result = detector_module._float_env("ARIA_MODEL_CONF_TEST", 0.12)
    assert result == 0.12
    assert math.isnan(result) is False


def test_float_env_rejects_infinity(monkeypatch):
    import aria.inference.detector as detector_module

    monkeypatch.setenv("ARIA_MODEL_IOU_TEST", "-inf")
    result = detector_module._float_env("ARIA_MODEL_IOU_TEST", 0.45)
    assert result == 0.45
    assert math.isinf(result) is False


def test_detect_serializes_concurrent_predict_calls():
    import aria.inference.detector as detector_module

    class ConcurrencyRecordingModel(FakeModel):
        def __init__(self):
            super().__init__(
                {
                    0: "longitudinal_crack",
                    1: "transverse_crack",
                    2: "alligator_crack",
                    3: "pothole",
                }
            )
            self._active = 0
            self._max_active = 0
            self._counter_lock = threading.Lock()

        def predict(self, **kwargs):
            with self._counter_lock:
                self._active += 1
                self._max_active = max(self._max_active, self._active)
            try:
                time.sleep(0.02)
                return [FakeResult([])]
            finally:
                with self._counter_lock:
                    self._active -= 1

    model = ConcurrencyRecordingModel()
    image = np.zeros((640, 640, 3), dtype=np.uint8)

    threads = [
        threading.Thread(target=detector_module.detect, args=(image, model))
        for _ in range(8)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert model._max_active == 1
