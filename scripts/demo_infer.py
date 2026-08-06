"""Run preprocessed YOLO inference on BLR potholes demo images."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aria.inference.detector import (  # noqa: E402
    CONF_THRESHOLD,
    IOU_THRESHOLD,
    TEST_TIME_AUGMENT,
)
from aria.inference.preprocess import preprocess as shared_preprocess  # noqa: E402

IMAGES_DIR = ROOT / "data" / "demo" / "blr_potholes" / "images"
PREDICTIONS_DIR = ROOT / "data" / "demo" / "blr_potholes" / "predictions"
MODEL_CANDIDATES = (
    ROOT / "aria" / "models" / "aria_stage1.pt",
    ROOT / "models" / "aria_stage1.pt",
    ROOT / "aria_stage1.pt",
    ROOT / "aria" / "models" / "aria_best_v1.pt",
    ROOT / "models" / "aria_best_v1.pt",
    ROOT / "aria_best_v1.pt",
)


def resolve_model_path() -> Path:
    for path in MODEL_CANDIDATES:
        if path.exists():
            return path
    candidates = ", ".join(path.as_posix() for path in MODEL_CANDIDATES)
    raise FileNotFoundError(f"Model not found. Checked: {candidates}")


def crop_bottom_80_percent(image):
    height = image.shape[0]
    start_y = int(round(height * 0.20))
    return image[start_y:, :]


def preprocess(image, crop: bool = False):
    # cv2.imread() returns BGR — declare it explicitly so the shared path
    # preserves BGR for model.predict() (Ultralytics expects BGR numpy input).
    image = shared_preprocess(image, color_order="bgr")
    if crop:
        image = crop_bottom_80_percent(image)
    return image


def summarize_result(filename: str, result) -> int:
    boxes = result.boxes
    detection_count = 0 if boxes is None else len(boxes)
    if detection_count == 0:
        print(f"{filename}: detections=0, classes=none, max_confidence=0.000")
        return 0

    class_ids = [int(class_id) for class_id in boxes.cls.tolist()]
    class_names = sorted({result.names[class_id] for class_id in class_ids})
    max_confidence = max(float(confidence) for confidence in boxes.conf.tolist())
    print(
        f"{filename}: detections={detection_count}, "
        f"classes={', '.join(class_names)}, max_confidence={max_confidence:.3f}"
    )
    return detection_count


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run preprocessed YOLO inference on BLR potholes demo images."
    )
    parser.add_argument(
        "--model",
        help="Path to the model weights. If not specified, resolves automatically.",
    )
    parser.add_argument(
        "--crop",
        action="store_true",
        help="Apply 20%% top crop (assumes dashcam framing).",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    image_paths = sorted(IMAGES_DIR.glob("*.jpg"))
    if not image_paths:
        print(f"No .jpg images found in {IMAGES_DIR.as_posix()}")
        return

    model_path = args.model if args.model else str(resolve_model_path())
    print(f"Loading YOLO model from {model_path} ...")
    model = YOLO(model_path)

    PREDICTIONS_DIR.mkdir(parents=True, exist_ok=True)

    total_detections = 0
    for image_path in image_paths:
        image = cv2.imread(str(image_path))
        if image is None:
            print(f"{image_path.name}: skipped unreadable image")
            continue

        preprocessed = preprocess(image, crop=args.crop)
        results = model.predict(
            source=preprocessed,
            conf=CONF_THRESHOLD,
            iou=IOU_THRESHOLD,
            imgsz=640,
            augment=TEST_TIME_AUGMENT,
            verbose=False,
        )
        result = results[0]
        total_detections += summarize_result(image_path.name, result)
        cv2.imwrite(str(PREDICTIONS_DIR / image_path.name), result.plot())

    if total_detections == 0:
        print("Domain gap confirmed — consider Stage 2 retraining with blr_potholes images")


if __name__ == "__main__":
    main()
