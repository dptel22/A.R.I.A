"""
pipeline/inference.py — A.R.I.A. Core Inference Pipeline
Workflow: Video/Image → Frame Extraction → Detection → Severity → Contract Lookup → POST to API

This module bridges the YOLO model output with the A.R.I.A. backend:
  1. Load a pre-trained YOLOv8 model
  2. Extract frames from video (1 fps) or accept a single image
  3. Run per-frame road_damage detection
  4. Filter by severity (skip LOW)
  5. Save annotated evidence frames
  6. POST results to the FastAPI backend
"""

from core.contract_lookup import lookup_contract
from core.severity import compute_severity
import os
import sys
import time
from datetime import datetime, timezone
from uuid import uuid4

import cv2
import numpy as np
import requests

# ─────────────────────────────────────────────────────────────
# Configuration — defined once, never hardcoded elsewhere
# ─────────────────────────────────────────────────────────────
MODEL_PATH = "pipeline/aria_best_v0.pt"
API_URL = "http://localhost:8000"
CONF_THRESHOLD = 0.25
DB_PATH = "db/aria.db"

# Class remapping — oracl4 model has 4 classes (D00, D10, D20, D40)
# All map to the unified A.R.I.A. label: road_damage
CLASS_REMAP = {
    0: "road_damage",
    1: "road_damage",
    2: "road_damage",
    3: "road_damage",
}

# ─────────────────────────────────────────────────────────────
# Lazy-import core modules (so script works from aria/ root)
# ─────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ─────────────────────────────────────────────────────────────
# 1. Model loading
# ─────────────────────────────────────────────────────────────

def load_model(model_path: str = MODEL_PATH):
    """
    Load the pre-trained YOLOv8 road_damage detection model.

    Uses ultralytics YOLO. Automatically selects GPU if available,
    otherwise falls back to CPU. Prints the selected device.

    Args:
        model_path (str): Path to the .pt model weights file.

    Returns:
        ultralytics.YOLO: Loaded model ready for inference.

    Raises:
        FileNotFoundError: If the model weights file does not exist.
    """
    if not os.path.exists(model_path):
        raise FileNotFoundError(
            f"Model weights not found at '{model_path}'. "
            "Run `python pipeline/setup_model.py` first."
        )

    from ultralytics import YOLO
    import torch

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(
        f"[inference] Loading model from '{model_path}' on {device.upper()} …")

    model = YOLO(model_path)
    model.to(device)

    print(f"[inference] ✅ Model loaded — device: {device.upper()}")
    return model


# ─────────────────────────────────────────────────────────────
# 2. Frame extraction
# ─────────────────────────────────────────────────────────────

def extract_frames(video_path: str, fps: int = 1) -> list[tuple]:
    """
    Extract frames from a video at the given frame rate, or load a single image.

    For video files:
        Reads the video and samples 1 frame per `fps` seconds using
        OpenCV. The exact sample points are determined by the video's
        native FPS (e.g. a 30 fps video sampled at fps=1 yields every
        30th frame).

    For image files (.jpg, .jpeg, .png, .bmp, .webp):
        Reads the image directly and returns it as a single-element list
        with timestamp 0 seconds.

    Args:
        video_path (str): Path to the source video or image file.
        fps (int): Frames to extract per second for video sources.
                   Ignored for images.

    Returns:
        list[tuple]: Each tuple is (frame: np.ndarray, timestamp_seconds: float).
                     frame is a BGR numpy array in OpenCV format.

    Raises:
        FileNotFoundError: If the source file does not exist.
        ValueError: If the file cannot be opened by OpenCV.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Source file not found: '{video_path}'")

    # ── Single image path ──
    image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff"}
    ext = os.path.splitext(video_path)[1].lower()

    if ext in image_extensions:
        frame = cv2.imread(video_path)
        if frame is None:
            raise ValueError(f"OpenCV could not read image: '{video_path}'")
        return [(frame, 0.0)]

    # ── Video path ──
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"OpenCV could not open video: '{video_path}'")

    native_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    sample_interval = max(1, int(native_fps / fps))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    frames: list[tuple] = []
    frame_index = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_index % sample_interval == 0:
            timestamp_seconds = frame_index / native_fps
            frames.append((frame, timestamp_seconds))
        frame_index += 1

    cap.release()
    print(f"[inference] Extracted {len(frames)} frame(s) from '{video_path}' "
          f"({total_frames} total @ {native_fps:.0f} fps, sampling 1/{sample_interval})")
    return frames


# ─────────────────────────────────────────────────────────────
# 3. Detection on a single frame
# ─────────────────────────────────────────────────────────────

def run_detection(
    model,
    frame: np.ndarray,
    conf: float = CONF_THRESHOLD,
) -> list[dict]:
    """
    Run YOLO road_damage inference on a single video frame.

    Passes the frame through the loaded YOLO model and extracts
    all bounding boxes above the confidence threshold. All detected
    classes are remapped to the unified 'road_damage' label per
    CLASS_REMAP.

    Args:
        model: Loaded ultralytics YOLO model instance.
        frame (np.ndarray): BGR image array from OpenCV.
        conf (float): Minimum confidence threshold (0.0–1.0).

    Returns:
        list[dict]: One dict per detection with keys:
            - bbox (list[float]): [x1, y1, x2, y2] in pixels
            - confidence (float): YOLO confidence score
            - label (str): Always 'road_damage'
            - frame_width (int): Width of the source frame
            - frame_height (int): Height of the source frame
    """
    h, w = frame.shape[:2]

    results = model(frame, verbose=False)
    detections: list[dict] = []

    for result in results:
        boxes = result.boxes
        if boxes is None:
            continue

        for box in boxes:
            box_conf = float(box.conf[0])
            if box_conf < conf:
                continue

            cls_id = int(box.cls[0])
            label = CLASS_REMAP.get(cls_id, "road_damage")

            x1, y1, x2, y2 = box.xyxy[0].tolist()
            detections.append({
                "bbox": [round(x1), round(y1), round(x2), round(y2)],
                "confidence": round(box_conf, 4),
                "label": label,
                "frame_width": w,
                "frame_height": h,
            })

    return detections


# ─────────────────────────────────────────────────────────────
# 4. Evidence frame saving
# ─────────────────────────────────────────────────────────────

def save_evidence_frame(
    frame: np.ndarray,
    bbox: list,
    output_dir: str,
    detection_id: str,
) -> str:
    """
    Save an annotated evidence frame for a road_damage detection.

    Draws a red bounding box rectangle on the full frame and saves it.
    The saved file name is based on the detection_id for traceability.

    Args:
        frame (np.ndarray): Full BGR image from OpenCV.
        bbox (list): [x1, y1, x2, y2] bounding box in pixel coordinates.
        output_dir (str): Directory where the evidence image will be saved.
        detection_id (str): UUID of the detection (used as filename).

    Returns:
        str: Absolute path to the saved evidence image.
    """
    os.makedirs(output_dir, exist_ok=True)

    x1, y1, x2, y2 = [int(v) for v in bbox]
    padding = 20
    h, w = frame.shape[:2]

    # Draw bounding box on a copy of the frame
    annotated = frame.copy()
    cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 0, 220), 3)

    # Label above the box
    label_text = "road_damage"
    cv2.rectangle(annotated, (x1, max(0, y1 - 22)),
                  (x1 + 130, y1), (0, 0, 180), -1)
    cv2.putText(
        annotated,
        label_text,
        (x1 + 4, max(14, y1 - 5)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )

    save_path = os.path.join(output_dir, f"{detection_id}.jpg")
    cv2.imwrite(save_path, annotated)
    return os.path.abspath(save_path)


# ─────────────────────────────────────────────────────────────
# 5. Full source processing pipeline
# ─────────────────────────────────────────────────────────────

def process_source(
    source_path: str,
    gps_lat: float,
    gps_lon: float,
    output_dir: str = "evidence/",
    model_path: str = MODEL_PATH,
    api_url: str = API_URL,
) -> list[dict]:
    """
    Run the complete A.R.I.A. inference pipeline on a video or image.

    Workflow:
      1. Load YOLO model
      2. Extract frames from source
      3. For each frame, run detection
      4. Compute severity via compute_severity()
      5. Skip LOW severity detections (not worth enforcement action)
      6. For MEDIUM/HIGH: resolve GPS → contract via lookup_contract()
      7. Save annotated evidence frame
      8. POST detection payload to FastAPI POST /detections
      9. Print processing summary

    Args:
        source_path (str): Path to a video file or image.
        gps_lat (float): GPS latitude of the recording location.
        gps_lon (float): GPS longitude of the recording location.
        output_dir (str): Directory to save evidence frames.
        model_path (str): Path to YOLO weights.
        api_url (str): Base URL of the running FastAPI backend.

    Returns:
        list[dict]: API responses (JSON) for each successfully posted detection.
    """
    model = load_model(model_path)
    frames = extract_frames(source_path)

    total_frames = len(frames)
    total_detections = 0
    posted = 0
    api_responses: list[dict] = []

    print(
        f"\n[pipeline] Processing {total_frames} frame(s) from '{source_path}' …")
    print(f"[pipeline] GPS: ({gps_lat}, {gps_lon})")

    for frame_idx, (frame, timestamp_sec) in enumerate(frames):
        h, w = frame.shape[:2]
        raw_detections = run_detection(model, frame)
        total_detections += len(raw_detections)

        for raw_det in raw_detections:
            bbox = raw_det["bbox"]

            # Severity scoring
            sev_result = compute_severity(bbox, w, h)
            severity = sev_result["severity"]

            # Skip LOW severity — not worth enforcement
            if severity == "LOW":
                print(f"   [frame {frame_idx}] LOW severity — skipped")
                continue

            # Generate a detection ID for the evidence frame filename
            detection_id = str(uuid4())

            # Save annotated evidence frame
            frame_path = save_evidence_frame(
                frame, bbox, output_dir, detection_id)

            # Build ISO timestamp for this frame
            ts = datetime.now(timezone.utc).replace(
                second=int(timestamp_sec) % 60,
                microsecond=0,
            ).isoformat()

            # POST payload to the FastAPI backend
            payload = {
                "gps_lat": gps_lat,
                "gps_lon": gps_lon,
                "confidence": raw_det["confidence"],
                "bbox": bbox,
                "frame_width": w,
                "frame_height": h,
                "frame_path": frame_path,
                "timestamp": ts,
            }

            try:
                resp = requests.post(
                    f"{api_url}/detections", json=payload, timeout=10)
                resp.raise_for_status()
                api_resp = resp.json()
                api_responses.append(api_resp)
                posted += 1
                print(
                    f"   [frame {frame_idx}] ✅ Posted — severity={severity}, "
                    f"confidence={raw_det['confidence']:.2f}, "
                    f"id={api_resp.get('detection_id', '?')[:8]}…"
                )
            except requests.exceptions.RequestException as exc:
                print(f"   [frame {frame_idx}] ⚠️  API POST failed: {exc}")

    # ── Summary ──
    print(
        f"\n[pipeline] ─────────────────────────────────────────────\n"
        f"[pipeline] ✅ Summary\n"
        f"[pipeline]    Frames processed : {total_frames}\n"
        f"[pipeline]    Detections found : {total_detections}\n"
        f"[pipeline]    Posted to API    : {posted}  (LOW severity skipped)\n"
        f"[pipeline] ─────────────────────────────────────────────\n"
    )

    return api_responses


# ─────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="A.R.I.A. Inference Pipeline")
    parser.add_argument("source", help="Path to video file or image")
    parser.add_argument("--lat", type=float,
                        required=True, help="GPS latitude")
    parser.add_argument("--lon", type=float, required=True,
                        help="GPS longitude")
    parser.add_argument("--output", default="evidence/",
                        help="Evidence output directory")
    args = parser.parse_args()

    process_source(args.source, args.lat, args.lon, args.output)
