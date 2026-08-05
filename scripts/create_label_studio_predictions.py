"""Create Label Studio tasks with YOLO preannotations for BLR pothole images.

Run via:
  python -m scripts.create_label_studio_predictions --limit 50
  python -m scripts.create_label_studio_predictions
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import cv2
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_ROOT = ROOT / "data" / "demo" / "blr_potholes"
DEFAULT_DOCUMENT_ROOT = ROOT / "data" / "demo"
DEFAULT_OUTPUT = DEFAULT_SOURCE_ROOT / "label_studio_preannotations.jsonl"
MODEL_CANDIDATES = (
    ROOT / "models" / "aria_stage1.pt",
    ROOT / "models" / "aria_best_v1.pt",
    ROOT / "aria_stage1.pt",
    ROOT / "aria_best_v1.pt",
)
ALLOWED_LABELS = {
    "longitudinal_crack",
    "transverse_crack",
    "alligator_crack",
    "pothole",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create Label Studio JSONL tasks with YOLO rectangle predictions."
    )
    parser.add_argument(
        "--source-root",
        default=str(DEFAULT_SOURCE_ROOT),
        help="Folder containing manifest.jsonl and the images directory.",
    )
    parser.add_argument(
        "--document-root",
        default=str(DEFAULT_DOCUMENT_ROOT),
        help="Folder configured as LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Output JSONL path for Label Studio import.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Path to YOLO model weights. Auto-resolved when omitted.",
    )
    parser.add_argument(
        "--conf",
        type=float,
        default=0.12,
        help="Confidence threshold for preannotations.",
    )
    parser.add_argument(
        "--iou",
        type=float,
        default=0.45,
        help="IOU threshold for YOLO NMS.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional number of tasks to write for a small test import.",
    )
    return parser


def resolve_model_path(model_arg: str | None) -> Path:
    if model_arg:
        path = Path(model_arg)
        if path.exists():
            return path
        raise FileNotFoundError(f"Model not found: {path}")

    for path in MODEL_CANDIDATES:
        if path.exists():
            return path

    checked = ", ".join(str(path) for path in MODEL_CANDIDATES)
    raise FileNotFoundError(f"Model not found. Checked: {checked}")


def read_manifest(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {path} line {line_number}") from exc
    return records


def local_file_url(image_path: Path, document_root: Path) -> str:
    relative_path = image_path.resolve().relative_to(document_root.resolve())
    return f"/data/local-files/?d={relative_path.as_posix()}"


def prediction_results(model: YOLO, image_path: Path, conf: float, iou: float) -> tuple[list[dict[str, Any]], float | None]:
    image = cv2.imread(str(image_path))
    if image is None:
        return [], None

    height, width = image.shape[:2]
    result = model.predict(
        source=str(image_path),
        conf=conf,
        iou=iou,
        imgsz=640,
        augment=True,
        verbose=False,
    )[0]

    boxes = result.boxes
    if boxes is None or len(boxes) == 0:
        return [], None

    label_studio_results: list[dict[str, Any]] = []
    confidences: list[float] = []

    for box in boxes:
        class_id = int(box.cls[0])
        label = str(result.names[class_id])
        if label not in ALLOWED_LABELS:
            continue

        x1, y1, x2, y2 = [float(value) for value in box.xyxy[0].tolist()]
        x1 = max(0.0, min(x1, width))
        x2 = max(0.0, min(x2, width))
        y1 = max(0.0, min(y1, height))
        y2 = max(0.0, min(y2, height))

        if x2 <= x1 or y2 <= y1:
            continue

        confidence = float(box.conf[0])
        confidences.append(confidence)
        label_studio_results.append(
            {
                "from_name": "label",
                "to_name": "image",
                "type": "rectanglelabels",
                "original_width": width,
                "original_height": height,
                "image_rotation": 0,
                "value": {
                    "x": round(100.0 * x1 / width, 4),
                    "y": round(100.0 * y1 / height, 4),
                    "width": round(100.0 * (x2 - x1) / width, 4),
                    "height": round(100.0 * (y2 - y1) / height, 4),
                    "rotation": 0,
                    "rectanglelabels": [label],
                },
                "score": confidence,
            }
        )

    if not confidences:
        return [], None

    return label_studio_results, sum(confidences) / len(confidences)


def make_task(
    record: dict[str, Any],
    document_root: Path,
    model: YOLO,
    conf: float,
    iou: float,
) -> dict[str, Any] | None:
    local_image_path = record.get("local_image_path")
    if not isinstance(local_image_path, str) or not local_image_path:
        return None

    image_path = Path(local_image_path)
    if not image_path.is_absolute():
        image_path = ROOT / image_path
    if not image_path.exists():
        return None

    results, score = prediction_results(model, image_path, conf=conf, iou=iou)
    task: dict[str, Any] = {
        "data": {
            "image": local_file_url(image_path, document_root),
            "issue_number": record.get("issue_number"),
            "issue_url": record.get("issue_url"),
            "uuid": record.get("uuid"),
            "lat": record.get("lat"),
            "long": record.get("long"),
            "created_at": record.get("created_at"),
            "source_image_url": record.get("source_image_url"),
        }
    }

    if results:
        task["predictions"] = [
            {
                "model_version": "aria_stage1",
                "score": score,
                "result": results,
            }
        ]

    return task


def main() -> None:
    args = build_parser().parse_args()
    source_root = Path(args.source_root)
    document_root = Path(args.document_root)
    output_path = Path(args.output)
    model_path = resolve_model_path(args.model)

    print(f"Loading YOLO model from {model_path} ...")
    model = YOLO(str(model_path))

    tasks: list[dict[str, Any]] = []
    tasks_with_predictions = 0
    manifest_path = source_root / "manifest.jsonl"

    for index, record in enumerate(read_manifest(manifest_path), start=1):
        task = make_task(record, document_root, model, conf=args.conf, iou=args.iou)
        if task is None:
            continue
        if task.get("predictions"):
            tasks_with_predictions += 1
        tasks.append(task)

        if index % 100 == 0:
            print(f"Processed {index} manifest records ...")
        if args.limit is not None and len(tasks) >= args.limit:
            break

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        for task in tasks:
            handle.write(json.dumps(task, ensure_ascii=True) + "\n")

    print(f"Wrote {len(tasks)} Label Studio tasks to {output_path}")
    print(f"Tasks with predictions: {tasks_with_predictions}")
    print(f"Use LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT={document_root.resolve()}")


if __name__ == "__main__":
    main()
