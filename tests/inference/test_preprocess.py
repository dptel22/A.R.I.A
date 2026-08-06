"""Unit tests for the shared preprocess path (letterbox + CLAHE-LAB)."""
from __future__ import annotations

import importlib
import io
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image

from aria.inference.preprocess import apply_clahe_lab, letterbox, preprocess

_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


class _FakeBox:
    def __init__(self, class_id: int, confidence: float):
        self.cls = np.array([class_id], dtype=float)
        self.conf = np.array([confidence], dtype=float)
        self.xywhn = np.array([[0.5, 0.5, 0.25, 0.2]], dtype=float)


class _FakeResult:
    def __init__(self, boxes):
        self.boxes = boxes


def _rgb_image(height: int = 480, width: int = 640) -> np.ndarray:
    # Deterministic gradient so every channel differs and CLAHE has contrast.
    y, x = np.mgrid[0:height, 0:width]
    r = (x % 256).astype(np.uint8)
    g = (y % 256).astype(np.uint8)
    b = ((x + y) % 256).astype(np.uint8)
    return np.stack([r, g, b], axis=-1)


def test_preprocess_letterboxes_to_square_size():
    out = preprocess(_rgb_image(480, 640), color_order="rgb")
    assert out.shape == (640, 640, 3)
    assert out.dtype == np.uint8


def test_preprocess_preserves_channel_order():
    bgr = _rgb_image()[:, :, ::-1].copy()  # simulate cv2 BGR array
    out_bgr = preprocess(bgr, color_order="bgr")
    out_rgb = preprocess(bgr[:, :, ::-1].copy(), color_order="rgb")
    # Feeding a BGR array as "bgr" must equal feeding its RGB twin as "rgb"
    # (modulo exact round-trip of the reversed channels).
    assert np.array_equal(out_bgr, out_rgb[:, :, ::-1])


def test_preprocess_applies_clahe_enhancement():
    # A low-contrast image should gain contrast on the L channel.
    base = np.full((200, 200, 3), 40, dtype=np.uint8)
    base[80:120, 80:120] = 60
    enhanced = apply_clahe_lab(base, color_order="rgb")
    assert enhanced.shape == base.shape
    assert not np.array_equal(enhanced, base)
    # The flat background stays flat; the enhanced image has at least as much
    # spread as the input patch.
    assert enhanced.std() >= base.std()


def test_preprocess_rejects_non_hwc_input():
    with pytest.raises(ValueError, match=r"\(H, W, 3\)"):
        preprocess(np.zeros((640, 640), dtype=np.uint8), color_order="rgb")
    with pytest.raises(ValueError, match=r"\(H, W, 3\)"):
        preprocess(None, color_order="rgb")  # type: ignore[arg-type]


def test_preprocess_rejects_unknown_color_order():
    with pytest.raises(ValueError, match="color_order"):
        preprocess(_rgb_image(), color_order="yuv")  # type: ignore[arg-type]


def test_letterbox_pads_wide_and_tall_images():
    wide = _rgb_image(100, 640)
    out_wide = letterbox(wide, size=320)
    assert out_wide.shape == (320, 320, 3)
    tall = _rgb_image(640, 100)
    out_tall = letterbox(tall, size=320)
    assert out_tall.shape == (320, 320, 3)


def test_pipeline_and_demo_feed_identical_pixels_to_predict():
    """E2E guard for the predict-boundary channel contract (F1).

    The HTTP pipeline (PIL decode -> BGR) and the demo script (cv2 decode,
    BGR) must feed byte-identical pixels to ``model.predict``.  If the pipeline
    accidentally hands Ultralytics an RGB array, the sources diverge and the
    derived detection confidences differ by far more than the tolerance.
    """
    from aria.inference.pipeline import run_pipeline
    demo_infer = importlib.import_module("demo_infer")

    # Deterministic RGB image with strong, distinct channel gradients.
    rgb = np.zeros((120, 180, 3), dtype=np.uint8)
    yy, xx = np.mgrid[0:120, 0:180]
    rgb[..., 0] = (xx % 256).astype(np.uint8)          # B when seen as BGR
    rgb[..., 1] = (yy % 256).astype(np.uint8)          # G
    rgb[..., 2] = ((xx + yy) % 256).astype(np.uint8)   # R when seen as BGR
    buffer = io.BytesIO()
    Image.fromarray(rgb, "RGB").save(buffer, format="PNG")
    png_bytes = buffer.getvalue()

    recorded_sources: list[np.ndarray] = []

    class RecordingModel:
        names = {
            0: "longitudinal_crack",
            1: "transverse_crack",
            2: "alligator_crack",
            3: "pothole",
        }

        def predict(self, **kwargs):
            source = kwargs["source"]
            recorded_sources.append(source.copy())
            # Derive confidence from channel-2 (R in BGR) so a channel swap at
            # the predict boundary changes the returned detection.
            confidence = 0.1 + float(source[..., 2].mean()) / 512.0
            return [_FakeResult([_FakeBox(3, confidence)])]

    model = RecordingModel()

    # Path A — the HTTP pipeline (PIL decode -> RGB -> BGR -> shared preprocess)
    pipeline_result = run_pipeline(png_bytes, model)
    assert pipeline_result.status == "SUCCEEDED"

    # Path B — the demo script (cv2 decode -> BGR -> shared preprocess)
    bgr = cv2.imdecode(np.frombuffer(png_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    demo_preprocessed = demo_infer.preprocess(bgr, crop=False)
    demo_result = model.predict(source=demo_preprocessed)[0]

    assert len(recorded_sources) == 2
    pipeline_source, demo_source = recorded_sources
    assert pipeline_source.shape == (640, 640, 3)
    assert demo_source.shape == (640, 640, 3)
    assert np.array_equal(pipeline_source, demo_source), (
        "run_pipeline and demo_infer must feed identical (BGR) pixels to "
        "model.predict — an RGB array at the predict boundary fails this."
    )

    # Identical pixels -> identical detections (box count + confidence).
    pipeline_primary = pipeline_result.detections[0]
    assert len(demo_result.boxes) == len(pipeline_result.detections) == 1
    demo_conf = float(demo_result.boxes[0].conf[0])
    assert pipeline_primary["confidence"] == pytest.approx(demo_conf, abs=1e-2)
    assert pipeline_primary["class_name"] == "pothole"


def test_pipeline_hands_bgr_array_to_model_predict():
    """End-to-end: the array handed to ``model.predict`` is BGR.

    Ultralytics treats numpy HWC sources as OpenCV-compatible BGR, so
    ``run_pipeline`` must flip the PIL-derived RGB array to BGR before
    ``detect()`` forwards it to ``model.predict``.  This is a regression guard
    at the predict boundary: it FAILS if the flip is reverted and the
    unflipped RGB array reaches ``model.predict`` (the array would then equal
    ``preprocess(rgb, color_order="rgb")`` instead of its channel-reversed
    twin).
    """
    from aria.inference.pipeline import run_pipeline

    rgb = _rgb_image()  # deterministic (480, 640, 3) RGB gradient
    buffer = io.BytesIO()
    Image.fromarray(rgb, "RGB").save(buffer, format="PNG")
    png_bytes = buffer.getvalue()

    class _RecordingYOLO:
        names = {
            0: "longitudinal_crack",
            1: "transverse_crack",
            2: "alligator_crack",
            3: "pothole",
        }

        def __init__(self) -> None:
            self.source: np.ndarray | None = None

        def predict(self, **kwargs) -> list:
            self.source = kwargs["source"]
            return []

    model = _RecordingYOLO()
    result = run_pipeline(png_bytes, model)

    assert result.status == "NO_DETECTIONS"
    assert model.source is not None
    assert model.source.shape == (640, 640, 3)
    assert model.source.dtype == np.uint8
    # preprocess() preserves channel order, so the BGR array the pipeline must
    # hand to model.predict is the RGB-preprocessed result reversed on channels.
    expected_bgr = preprocess(rgb, color_order="rgb")[:, :, ::-1]
    assert np.array_equal(model.source, expected_bgr)
    # Explicit regression guard: the unflipped RGB array must NOT match.
    assert not np.array_equal(model.source, preprocess(rgb, color_order="rgb"))
