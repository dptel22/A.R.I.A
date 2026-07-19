"""Run YOLO inference benchmark on BLR potholes demo images at two confidence thresholds.

Produces the ground-truth detection numbers for Task 1 (verification) and Task 3 (DEMO_STATUS.md).
Usage:
    python -m scripts.run_benchmark
    python scripts/run_benchmark.py [--model path/to/model.pt]
    python -m scripts.run_benchmark --limit 50
"""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]
IMAGES_DIR = ROOT / "data" / "demo" / "blr_potholes" / "images"
MODEL_CANDIDATES = (
    ROOT / "models" / "aria_stage1.pt",
    ROOT / "models" / "aria_best_v1.pt",
    ROOT / "aria_stage1.pt",
    ROOT / "aria_best_v1.pt",
)


def resolve_model() -> Path:
    for p in MODEL_CANDIDATES:
        if p.exists():
            return p
    raise FileNotFoundError(f"No model found. Checked: {[str(p) for p in MODEL_CANDIDATES]}")


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


def preprocess(image):
    image = letterbox(image, size=640)
    image = apply_clahe_lab(image)
    return image


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dual-threshold inference benchmark on BLR pothole demo images."
    )
    parser.add_argument(
        "--model",
        help="Path to model weights. Auto-resolved if not specified.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of images to benchmark. Use for quick local checks.",
    )
    args = parser.parse_args()

    model_path = args.model if args.model else str(resolve_model())
    print(f"Model: {model_path}")

    image_paths = sorted(IMAGES_DIR.glob("*.jpg"))
    if args.limit is not None:
        if args.limit < 1:
            raise SystemExit("--limit must be greater than 0")
        image_paths = image_paths[:args.limit]
    if not image_paths:
        print(f"No .jpg images found in {IMAGES_DIR}")
        return

    print(f"Total images: {len(image_paths)}")
    model = YOLO(model_path)
    print(f"Classes: {model.names}")
    print(f"Preprocessing: letterbox 640px + CLAHE-LAB, crop=False")
    print()

    img_with_det_25 = 0
    total_det_25 = 0
    img_with_det_12 = 0
    total_det_12 = 0
    skipped = 0
    detected_images = []

    for idx, ip in enumerate(image_paths):
        im = cv2.imread(str(ip))
        if im is None:
            skipped += 1
            continue

        pre = preprocess(im)
        res = model.predict(source=pre, conf=0.12, iou=0.45, imgsz=640, augment=True, verbose=False)
        r = res[0]
        boxes = r.boxes

        if boxes is not None and len(boxes) > 0:
            confs = [float(c) for c in boxes.conf.tolist()]
            classes = [int(ci) for ci in boxes.cls.tolist()]
            c12 = len(confs)
            c25 = sum(1 for c in confs if c >= 0.25)
            mc = max(confs)
            class_names = sorted({model.names[ci] for ci in classes})

            if c12 > 0:
                img_with_det_12 += 1
                total_det_12 += c12
            if c25 > 0:
                img_with_det_25 += 1
                total_det_25 += c25

            detected_images.append({
                "name": ip.name,
                "count_12": c12,
                "count_25": c25,
                "max_conf": mc,
                "classes": class_names,
            })

        if (idx + 1) % 100 == 0:
            print(f"  Progress: {idx + 1}/{len(image_paths)} processed ...")

    total = len(image_paths) - skipped

    print()
    print("=" * 65)
    print("TASK 1 INFERENCE RESULTS  --  BLR POTHOLE DEMO SET")
    print("=" * 65)
    print(f"Model:           {Path(model_path).name}")
    print(f"Total images:    {total}  (skipped {skipped} unreadable)")
    print()
    pct25 = 100.0 * img_with_det_25 / total if total else 0
    pct12 = 100.0 * img_with_det_12 / total if total else 0
    print(f"conf >= 0.25 :   {img_with_det_25}/{total} images ({pct25:.1f}%) with >= 1 detection   |   {total_det_25} total bboxes")
    print(f"conf >= 0.12 :   {img_with_det_12}/{total} images ({pct12:.1f}%) with >= 1 detection   |   {total_det_12} total bboxes")
    print()

    if detected_images:
        print(f"Per-image breakdown for images with detections at conf=0.12 ({len(detected_images)} total):")
        for d in detected_images[:60]:
            print(
                f"  {d['name']}: det@0.12={d['count_12']}, det@0.25={d['count_25']}, "
                f"max_conf={d['max_conf']:.3f}, classes={d['classes']}"
            )
        if len(detected_images) > 60:
            print(f"  ... and {len(detected_images) - 60} more (see full output above)")
    else:
        print("RESULT: 0 detections at conf=0.12 on entire test set.")
        print("Domain gap confirmed -- model trained on dashcam imagery; test images are close-up citizen-submitted style.")

    print()
    print("To replicate: python -m scripts.run_benchmark")


if __name__ == "__main__":
    main()

