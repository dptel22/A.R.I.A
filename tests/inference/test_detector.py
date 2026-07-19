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
