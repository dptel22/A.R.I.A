"""Export Label Studio annotations to YOLO format with train/val split.

Run via:
  python -m scripts.export_label_studio_yolo --input data/demo/blr_potholes/label_studio_export.json --output data/yolo_export --val-split 0.2
"""
from __future__ import annotations

import argparse
import json
import random
import shutil
from pathlib import Path
from typing import Any

from collections import defaultdict

# ARIA class mapping (must match model.names order)
CLASS_NAMES = [
    "longitudinal_crack",
    "transverse_crack",
    "alligator_crack",
    "pothole",
]
CLASS_TO_ID = {name: i for i, name in enumerate(CLASS_NAMES)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export Label Studio annotations to YOLO format with train/val split."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to Label Studio JSON export file (or directory of JSON files).",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output directory for YOLO format (images/train, labels/train, images/val, labels/val).",
    )
    parser.add_argument(
        "--val-split",
        type=float,
        default=0.2,
        help="Fraction of hand-labeled data to use for validation (default: 0.2).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible train/val split (default: 42).",
    )
    parser.add_argument(
        "--copy-images",
        action="store_true",
        help="Copy images to output directory (default: symlink).",
    )
    parser.add_argument(
        "--include-pseudo",
        action="store_true",
        help="Include pseudo-labeled tasks in training set (default: false - pseudo labels never enter val per V4 Control #4).",
    )
    return parser.parse_args()


def load_label_studio_export(input_path: Path) -> list[dict[str, Any]]:
    """Load Label Studio export from JSON or JSONL file."""
    if input_path.suffix == ".jsonl":
        tasks = []
        with input_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    tasks.append(json.loads(line))
        return tasks
    else:
        with input_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        elif isinstance(data, dict) and "tasks" in data:
            return data["tasks"]
        else:
            raise ValueError(f"Unexpected JSON structure in {input_path}")


def extract_annotations(task: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract ground truth annotations from a Label Studio task.

    Priority: human annotations (annotations) > predictions (preannotations).
    Returns list of dicts with: class_id, x_center, y_center, width, height (normalized 0-1).
    """
    boxes = []

    # Check for human annotations first (completed tasks)
    annotations = task.get("annotations", [])
    for annotation in annotations:
        if annotation.get("was_cancelled") or annotation.get("ground_truth") is False:
            continue
        results = annotation.get("result", [])
        for result in results:
            if result.get("type") != "rectanglelabels":
                continue
            value = result.get("value", {})
            labels = value.get("rectanglelabels", [])
            if not labels:
                continue
            label = labels[0]
            if label not in CLASS_TO_ID:
                print(f"Warning: Unknown label '{label}' in task {task.get('id')}, skipping")
                continue
            class_id = CLASS_TO_ID[label]
            x = value.get("x", 0) / 100.0
            y = value.get("y", 0) / 100.0
            w = value.get("width", 0) / 100.0
            h = value.get("height", 0) / 100.0

            # Convert to YOLO format (center x, center y, width, height)
            x_center = x + w / 2.0
            y_center = y + h / 2.0

            boxes.append({
                "class_id": class_id,
                "x_center": x_center,
                "y_center": y_center,
                "width": w,
                "height": h,
                "source": "human",
            })

    # If no human annotations, fall back to predictions (preannotations)
    if not boxes:
        predictions = task.get("predictions", [])
        for prediction in predictions:
            results = prediction.get("result", [])
            for result in results:
                if result.get("type") != "rectanglelabels":
                    continue
                value = result.get("value", {})
                labels = value.get("rectanglelabels", [])
                if not labels:
                    continue
                label = labels[0]
                if label not in CLASS_TO_ID:
                    continue
                class_id = CLASS_TO_ID[label]
                x = value.get("x", 0) / 100.0
                y = value.get("y", 0) / 100.0
                w = value.get("width", 0) / 100.0
                h = value.get("height", 0) / 100.0

                x_center = x + w / 2.0
                y_center = y + h / 2.0

                boxes.append({
                    "class_id": class_id,
                    "x_center": x_center,
                    "y_center": y_center,
                    "width": w,
                    "height": h,
                    "source": "prediction",
                })

    return boxes


def get_image_path(task: dict[str, Any], data_root: Path) -> Path | None:
    """Resolve the local image path from a Label Studio task."""
    data = task.get("data", {})
    image_url = data.get("image", "")

    # Handle local file URLs: /data/local-files/?d=relative/path
    if image_url.startswith("/data/local-files/?d="):
        relative_path = image_url[len("/data/local-files/?d="):]
        return data_root / relative_path

    # Handle direct relative paths in local_image_path
    local_path = data.get("local_image_path")
    if local_path:
        return Path(local_path)

    return None


def has_human_annotations(task: dict[str, Any]) -> bool:
    """Check if task has human (non-cancelled) annotations."""
    annotations = task.get("annotations", [])
    for annotation in annotations:
        if not annotation.get("was_cancelled") and annotation.get("ground_truth") is not False:
            if annotation.get("result"):
                return True
    return False


def main() -> None:
    args = parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output)
    data_root = Path("C:/Users/dhruv/PycharmProjects/A.R.I.A/data/demo")

    # Load tasks
    tasks = load_label_studio_export(input_path)
    print(f"Loaded {len(tasks)} tasks from {input_path}")

    # Separate human-annotated vs pseudo-labeled
    human_tasks = []
    pseudo_tasks = []

    for task in tasks:
        image_path = get_image_path(task, data_root)
        if image_path is None or not image_path.exists():
            print(f"Warning: Image not found for task {task.get('id')}, skipping")
            continue

        if has_human_annotations(task):
            human_tasks.append((task, image_path))
        elif task.get("predictions"):
            pseudo_tasks.append((task, image_path))

    print(f"Human-annotated tasks: {len(human_tasks)}")
    print(f"Pseudo-labeled tasks: {len(pseudo_tasks)}")

    if len(human_tasks) == 0:
        print("ERROR: No human-annotated tasks found. Cannot create validation set.")
        return

    # Shuffle and split human tasks
    random.seed(args.seed)
    random.shuffle(human_tasks)

    val_count = max(1, int(len(human_tasks) * args.val_split))
    val_tasks = human_tasks[:val_count]
    train_human_tasks = human_tasks[val_count:]

    print(f"Train (human): {len(train_human_tasks)}, Val (human): {len(val_tasks)}")

    # Training set = human train + pseudo (if enabled)
    train_tasks = train_human_tasks.copy()
    if args.include_pseudo:
        train_tasks.extend(pseudo_tasks)
        print(f"Added {len(pseudo_tasks)} pseudo-labeled tasks to training set")

    # Create output directories
    for split in ["train", "val"]:
        (output_dir / "images" / split).mkdir(parents=True, exist_ok=True)
        (output_dir / "labels" / split).mkdir(parents=True, exist_ok=True)

    # Class counts for validation
    class_counts = {"train": defaultdict(int), "val": defaultdict(int)}

    def process_split(tasks_list: list[tuple], split: str) -> None:
        for task, image_path in tasks_list:
            boxes = extract_annotations(task)

            # Write label file
            label_path = output_dir / "labels" / split / f"{image_path.stem}.txt"
            with label_path.open("w") as f:
                for box in boxes:
                    f.write(f"{box['class_id']} {box['x_center']:.6f} {box['y_center']:.6f} {box['width']:.6f} {box['height']:.6f}\n")
                    class_counts[split][CLASS_NAMES[box['class_id']]] += 1

            # Copy or symlink image
            dest_image = output_dir / "images" / split / image_path.name
            if args.copy_images:
                shutil.copy2(image_path, dest_image)
            else:
                try:
                    if dest_image.exists():
                        dest_image.unlink()
                    dest_image.symlink_to(image_path.resolve())
                except OSError:
                    shutil.copy2(image_path, dest_image)

    process_split(train_tasks, "train")
    process_split(val_tasks, "val")

    # Print class distribution
    print("\nClass distribution:")
    for split in ["train", "val"]:
        print(f"  {split}:")
        total = 0
        for class_name in CLASS_NAMES:
            count = class_counts[split][class_name]
            total += count
            print(f"    {class_name}: {count}")
        print(f"    TOTAL: {total}")

    # Validation checks (V4 Anti-Collapse Controls)
    print("\n=== V4 Anti-Collapse Validation ===")

    # Control #3: Validation must contain all 4 classes
    missing_in_val = [c for c in CLASS_NAMES if class_counts["val"][c] == 0]
    if missing_in_val:
        print(f"❌ FAIL: Validation set missing classes: {missing_in_val}")
        print("   (V4 Control #3: Validation must contain all 4 classes)")
    else:
        print("✅ PASS: All 4 classes present in validation set")

    # Control #3: Each class should have >=10 instances in val
    low_count = [(c, class_counts["val"][c]) for c in CLASS_NAMES if class_counts["val"][c] < 10]
    if low_count:
        print(f"⚠️  WARN: Classes with <10 instances in val: {low_count}")

    # Control #4: No pseudo-labels in validation (enforced by design)
    print("✅ PASS: No pseudo-labeled data in validation set (by design)")

    # Write dataset.yaml for YOLO training
    dataset_yaml = output_dir / "dataset.yaml"
    with dataset_yaml.open("w") as f:
        f.write(f"""path: {output_dir.as_posix()}
train: images/train
val: images/val

nc: {len(CLASS_NAMES)}
names: {CLASS_NAMES}
""")
    print(f"\nWrote dataset config to {dataset_yaml}")

    # Write instance counts log (Control #5)
    counts_log = output_dir / "INSTANCE_COUNTS.md"
    with counts_log.open("w") as f:
        f.write("# V4 Instance Counts (Pre-Training)\n\n")
        f.write("| Class | Train (Human) | Train (Pseudo) | Val (Human) | Total |\n")
        f.write("|-------|---------------|----------------|-------------|-------|\n")
        for class_name in CLASS_NAMES:
            train_human = class_counts["train"].get(class_name, 0) - sum(
                1 for t, _ in pseudo_tasks
                for b in extract_annotations(t)
                if CLASS_NAMES[b["class_id"]] == class_name
            )
            train_pseudo = sum(
                1 for t, _ in pseudo_tasks
                for b in extract_annotations(t)
                if CLASS_NAMES[b["class_id"]] == class_name
            )
            val_count = class_counts["val"].get(class_name, 0)
            total = train_human + train_pseudo + val_count
            f.write(f"| {class_name} | {train_human} | {train_pseudo} | {val_count} | {total} |\n")
    print(f"Wrote instance counts log to {counts_log}")


if __name__ == "__main__":
    main()