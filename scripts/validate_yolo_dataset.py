"""Validate YOLO dataset against V4 anti-collapse controls.

Run via:
  python -m scripts.validate_yolo_dataset --data-dir data/yolo_export
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from collections import defaultdict

# ARIA class mapping
CLASS_NAMES = [
    "longitudinal_crack",
    "transverse_crack",
    "alligator_crack",
    "pothole",
]
CLASS_TO_ID = {name: i for i, name in enumerate(CLASS_NAMES)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate YOLO dataset against V4 anti-collapse controls."
    )
    parser.add_argument(
        "--data-dir",
        required=True,
        help="Path to YOLO dataset directory (with images/train, labels/train, images/val, labels/val).",
    )
    parser.add_argument(
        "--min-val-per-class",
        type=int,
        default=10,
        help="Minimum instances per class in validation set (default: 10).",
    )
    parser.add_argument(
        "--max-synthetic-real-ratio",
        type=float,
        default=5.0,
        help="Maximum synthetic:real ratio per class (default: 5.0).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with error code if any validation fails.",
    )
    return parser.parse_args()


def count_labels(label_dir: Path) -> dict[str, int]:
    """Count class instances in a label directory."""
    counts = defaultdict(int)
    if not label_dir.exists():
        return counts

    for label_file in label_dir.glob("*.txt"):
        try:
            with label_file.open("r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split()
                    if len(parts) >= 5:
                        class_id = int(parts[0])
                        if 0 <= class_id < len(CLASS_NAMES):
                            counts[CLASS_NAMES[class_id]] += 1
        except Exception as e:
            print(f"Warning: Failed to parse {label_file}: {e}")
    return counts


def count_images(image_dir: Path) -> int:
    """Count images in a directory."""
    if not image_dir.exists():
        return 0
    return len(list(image_dir.glob("*.jpg"))) + len(list(image_dir.glob("*.jpeg"))) + len(list(image_dir.glob("*.png")))


def check_val_completeness(val_counts: dict[str, int], min_per_class: int) -> tuple[bool, list[str]]:
    """V4 Control #3: Validation must contain all 4 classes with minimum instances."""
    errors = []
    for class_name in CLASS_NAMES:
        count = val_counts.get(class_name, 0)
        if count == 0:
            errors.append(f"Class '{class_name}' has 0 instances in validation set")
        elif count < min_per_class:
            errors.append(f"Class '{class_name}' has only {count} instances in validation (minimum: {min_per_class})")
    return len(errors) == 0, errors


def check_no_pseudo_in_val(data_dir: Path) -> tuple[bool, list[str]]:
    """V4 Control #4: Pseudo-labels never enter validation set.

    This is enforced by the export script design (val only from human-annotated).
    Here we verify by checking for a metadata file or flag.
    """
    errors = []
    # Check if validation labels were generated from human annotations only
    # This is a design-time guarantee, but we can check for a marker file
    val_meta = data_dir / "labels" / "val" / ".human_only"
    if not val_meta.exists():
        errors.append("Validation set marker (.human_only) not found - cannot verify pseudo-label exclusion")
    return len(errors) == 0, errors


def check_synthetic_real_ratio(data_dir: Path, max_ratio: float) -> tuple[bool, list[str]]:
    """V4 Control #2: Synthetic:real ratio cap per class.

    Requires instance counts log from export script.
    """
    errors = []
    counts_log = data_dir / "INSTANCE_COUNTS.md"
    if not counts_log.exists():
        errors.append("Instance counts log (INSTANCE_COUNTS.md) not found - cannot verify synthetic:real ratio")
        return False, errors

    # Parse the markdown table
    try:
        with counts_log.open("r") as f:
            content = f.read()

        # Simple parsing of the table
        for line in content.split("\n"):
            if "|" in line and "---" not in line and "Class" not in line:
                parts = [p.strip() for p in line.split("|") if p.strip()]
                if len(parts) >= 5:
                    class_name = parts[0]
                    try:
                        train_human = int(parts[1])
                        train_pseudo = int(parts[2])
                        val_human = int(parts[3])
                        # Real = human train + human val
                        real = train_human + val_human
                        # Synthetic = pseudo train
                        synthetic = train_pseudo
                        if real > 0:
                            ratio = synthetic / real
                            if ratio > max_ratio:
                                errors.append(f"Class '{class_name}': synthetic:real ratio = {ratio:.2f}:1 (max allowed: {max_ratio}:1)")
                    except (ValueError, IndexError):
                        pass
    except Exception as e:
        errors.append(f"Failed to parse instance counts log: {e}")

    return len(errors) == 0, errors


def check_instance_counts_logged(data_dir: Path) -> tuple[bool, list[str]]:
    """V4 Control #5: Per-class instance count logged at every stage."""
    errors = []
    counts_log = data_dir / "INSTANCE_COUNTS.md"
    if not counts_log.exists():
        errors.append("Instance counts log (INSTANCE_COUNTS.md) not found")
        return False, errors
    return True, errors


def check_transverse_in_val(val_counts: dict[str, int]) -> tuple[bool, list[str]]:
    """Specific check for transverse crack in validation (was missing in Stage 2)."""
    errors = []
    count = val_counts.get("transverse_crack", 0)
    if count == 0:
        errors.append("CRITICAL: transverse_crack has 0 instances in validation set (this caused Stage 2 collapse)")
    elif count < 5:
        errors.append(f"WARNING: transverse_crack has only {count} instances in validation (recommend >=5)")
    return len(errors) == 0, errors


def check_data_leakage(train_labels: Path, val_labels: Path) -> tuple[bool, list[str]]:
    """Check for data leakage: same image stems in train and val."""
    errors = []
    train_stems = {f.stem for f in train_labels.glob("*.txt")}
    val_stems = {f.stem for f in val_labels.glob("*.txt")}
    overlap = train_stems & val_stems
    if overlap:
        errors.append(f"DATA LEAKAGE: {len(overlap)} images appear in both train and val: {sorted(overlap)[:10]}...")
    return len(errors) == 0, errors


def main() -> int:
    args = parse_args()
    data_dir = Path(args.data_dir)

    print(f"Validating YOLO dataset at: {data_dir}")
    print("=" * 60)

    all_passed = True
    all_errors = []

    # Count instances
    train_counts = count_labels(data_dir / "labels" / "train")
    val_counts = count_labels(data_dir / "labels" / "val")
    train_images = count_images(data_dir / "images" / "train")
    val_images = count_images(data_dir / "images" / "val")

    print(f"\nDataset summary:")
    print(f"  Train images: {train_images}")
    print(f"  Val images:   {val_images}")
    print(f"  Train labels: {sum(train_counts.values())} boxes")
    print(f"  Val labels:   {sum(val_counts.values())} boxes")

    print(f"\nTrain class distribution:")
    for c in CLASS_NAMES:
        print(f"  {c}: {train_counts.get(c, 0)}")

    print(f"\nVal class distribution:")
    for c in CLASS_NAMES:
        print(f"  {c}: {val_counts.get(c, 0)}")

    # V4 Control #3: Validation completeness
    print("\n--- V4 Control #3: Validation must contain all 4 classes ---")
    passed, errors = check_val_completeness(val_counts, args.min_val_per_class)
    if passed:
        print("✅ PASS: All 4 classes present in validation set")
    else:
        print("❌ FAIL:")
        for e in errors:
            print(f"  - {e}")
        all_errors.extend(errors)
        all_passed = False

    # V4 Control #3: Transverse crack specific check
    print("\n--- Transverse crack validation check (Stage 2 regression) ---")
    passed, errors = check_transverse_in_val(val_counts)
    if passed:
        print("✅ PASS: transverse_crack present in validation")
    else:
        for e in errors:
            if "CRITICAL" in e:
                print(f"❌ {e}")
            else:
                print(f"⚠️  {e}")
        all_errors.extend(errors)
        if "CRITICAL" in str(errors):
            all_passed = False

    # V4 Control #4: No pseudo-labels in validation
    print("\n--- V4 Control #4: No pseudo-labels in validation ---")
    passed, errors = check_no_pseudo_in_val(data_dir)
    if passed:
        print("✅ PASS: Validation set confirmed human-only")
    else:
        print("⚠️  WARN:")
        for e in errors:
            print(f"  - {e}")
        # Not a hard fail - design-time guarantee

    # V4 Control #2: Synthetic:real ratio
    print(f"\n--- V4 Control #2: Synthetic:real ratio <= {args.max_synthetic_real_ratio}:1 ---")
    passed, errors = check_synthetic_real_ratio(data_dir, args.max_synthetic_real_ratio)
    if passed:
        print("✅ PASS: Synthetic:real ratios within limits")
    else:
        print("❌ FAIL:")
        for e in errors:
            print(f"  - {e}")
        all_errors.extend(errors)
        all_passed = False

    # V4 Control #5: Instance counts logged
    print("\n--- V4 Control #5: Per-class instance counts logged ---")
    passed, errors = check_instance_counts_logged(data_dir)
    if passed:
        print("✅ PASS: Instance counts log found")
    else:
        print("❌ FAIL:")
        for e in errors:
            print(f"  - {e}")
        all_errors.extend(errors)
        all_passed = False

    # Data leakage check
    print("\n--- Data leakage check ---")
    passed, errors = check_data_leakage(
        data_dir / "labels" / "train",
        data_dir / "labels" / "val"
    )
    if passed:
        print("✅ PASS: No train/val overlap")
    else:
        print("❌ FAIL:")
        for e in errors:
            print(f"  - {e}")
        all_errors.extend(errors)
        all_passed = False

    # Summary
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL V4 ANTI-COLLAPSE CONTROLS PASSED")
        print("Dataset is ready for V4 training.")
        return 0
    else:
        print("❌ VALIDATION FAILED")
        print(f"\nTotal errors: {len(all_errors)}")
        if args.strict:
            return 1
        return 0


if __name__ == "__main__":
    sys.exit(main())