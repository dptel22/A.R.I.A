"""
tests/inference/test_inference.py - Smoke test for the A.R.I.A. detection pipeline.

Loads `aria_stage1.pt`, runs all images in `data/demo/sample_images/` through the pipeline,
and prints scored detection results.

Usage:
    python -m tests.inference.test_inference
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from aria.inference.pipeline import run_pipeline

logging.basicConfig(level=logging.INFO, format="[%(name)s] %(levelname)s: %(message)s")
log = logging.getLogger(__name__)


def main() -> None:
    model_path = Path("models/aria_stage1.pt")
    images_dir = Path("data/demo/sample_images")

    # --- Validate model -------------------------------------------------------
    if not model_path.exists():
        print(f"ERROR: {model_path} not found. Place it in the project root.")
        sys.exit(1)

    from ultralytics import YOLO
    print(f"Loading model from {model_path} ...")
    model = YOLO(str(model_path))
    print("Model loaded.\n")

    # --- Validate images ------------------------------------------------------
    image_files = (
        list(images_dir.glob("*.jpg"))
        + list(images_dir.glob("*.jpeg"))
        + list(images_dir.glob("*.png"))
        + list(images_dir.glob("*.webp"))
    )

    if not image_files:
        print(f"ERROR: No images found in {images_dir}/")
        sys.exit(1)

    print(f"Found {len(image_files)} image(s) in {images_dir}/\n")

    # --- Run pipeline on each image -------------------------------------------
    total_detections = 0

    for img_path in image_files:
        print(f"{'=' * 60}")
        print(f"Image: {img_path.name}")

        img_bytes = img_path.read_bytes()
        pipeline_result = run_pipeline(img_bytes, model)
        results = pipeline_result.detections

        if pipeline_result.status == "FAILED":
            print(f"  Pipeline failed: {pipeline_result.failure_reason}\n")
            continue

        if not results:
            print("  No detections\n")
            continue

        total_detections += len(results)

        for det in results:
            print(
                f"  {det['class_name']:<22} "
                f"conf={det['confidence']:.3f}  "
                f"severity={det['severity_level']:<8}  "
                f"score={det['severity_score']:.3f}"
            )

        primary = results[0]  # already sorted by severity_score desc
        print(f"\n  PRIMARY DEFECT: {primary['class_name']} ({primary['severity_level']})\n")

    # --- Summary --------------------------------------------------------------
    print(f"{'=' * 60}")
    print(f"SUMMARY: {total_detections} total detections across {len(image_files)} images")
    print("--- SMOKE TEST PASSED ---")


if __name__ == "__main__":
    main()
