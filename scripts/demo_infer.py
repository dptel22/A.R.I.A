"""Run preprocessed YOLO inference on BLR potholes demo images."""
from __future__ import annotations

from pathlib import Path

import cv2
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]
IMAGES_DIR = ROOT / "data" / "demo" / "blr_potholes" / "images"
PREDICTIONS_DIR = ROOT / "data" / "demo" / "blr_potholes" / "predictions"
MODEL_CANDIDATES = (
    ROOT / "aria" / "models" / "aria_stage1.pt",
    ROOT / "aria_stage1.pt",
    ROOT / "models" / "aria_stage1.pt",
)


def resolve_model_path() -> Path:
    for path in MODEL_CANDIDATES:
        if path.exists():
            return path
    candidates = ", ".join(path.as_posix() for path in MODEL_CANDIDATES)
    raise FileNotFoundError(f"Model not found. Checked: {candidates}")


def letterbox(image, size: int = 640):
    height, width = image.shape[:2]
    scale = min(size / width, size / height)
    resized_width = int(round(width * scale))
    resized_height = int(round(height * scale))

    resized = cv2.resize(image, (resized_width, resized_height), interpolation=cv2.INTER_AREA)
    output = cv2.copyMakeBorder(
        resized,
        top=(size - resized_height) // 2,
        bottom=size - resized_height - ((size - resized_height) // 2),
        left=(size - resized_width) // 2,
        right=size - resized_width - ((size - resized_width) // 2),
        borderType=cv2.BORDER_CONSTANT,
        value=(0, 0, 0),
    )
    return output


def apply_clahe_lab(image):
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    normalized_l = clahe.apply(l_channel)
    normalized_lab = cv2.merge((normalized_l, a_channel, b_channel))
    return cv2.cvtColor(normalized_lab, cv2.COLOR_LAB2BGR)


def crop_bottom_80_percent(image):
    height = image.shape[0]
    start_y = int(round(height * 0.20))
    return image[start_y:, :]


def preprocess(image):
    image = letterbox(image, size=640)
    image = apply_clahe_lab(image)
    return crop_bottom_80_percent(image)


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


def main() -> None:
    image_paths = sorted(IMAGES_DIR.glob("*.jpg"))
    if not image_paths:
        print(f"No .jpg images found in {IMAGES_DIR.as_posix()}")
        return

    model = YOLO(str(resolve_model_path()))
    PREDICTIONS_DIR.mkdir(parents=True, exist_ok=True)

    total_detections = 0
    for image_path in image_paths:
        image = cv2.imread(str(image_path))
        if image is None:
            print(f"{image_path.name}: skipped unreadable image")
            continue

        preprocessed = preprocess(image)
        results = model.predict(
            source=preprocessed,
            conf=0.12,
            iou=0.45,
            imgsz=640,
            augment=True,
            verbose=False,
        )
        result = results[0]
        total_detections += summarize_result(image_path.name, result)
        cv2.imwrite(str(PREDICTIONS_DIR / image_path.name), result.plot())

    if total_detections == 0:
        print("Domain gap confirmed — consider Stage 2 retraining with blr_potholes images")


if __name__ == "__main__":
    main()
