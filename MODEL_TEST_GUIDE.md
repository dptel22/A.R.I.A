# A.R.I.A. | Model Test & Verification Guide

This guide details how to manually run, verify, and troubleshoot the YOLO object detection model within the A.R.I.A. pipeline.

## 1. Prerequisites & Setup

Before testing, ensure the model weights are downloaded and the backend is running.

1.  **Download Weights:**
    ```bash
    # Run from the project root. This downloads aria_stage1.pt to ./models/
    python -m scripts.download_model
    ```
2.  **Seed the Database (Optional but recommended for contract matching):**
    ```bash
    python -m aria.db.seed
    ```
3.  **Start the Backend Server:**
    ```bash
    uvicorn aria.api.app:app --reload --port 8000
    ```
    *Look at the startup logs.* You must see:
    `INFO: aria.api.app: Loading YOLO model from ./models/aria_stage1.pt ...`
    `INFO: aria.api.app: Model loaded and warmed up. Ready.`

## 2. Acquiring Sample Images

You can test using standard image files. To get realistic civic data, use the built-in dataset downloader:

```bash
# Downloads 10 real pothole images submitted by citizens in Bengaluru
python -m scripts.download_blr_potholes --limit 10
```

This will populate `data/demo/blr_potholes/images/` with sample JPEGs/PNGs, and a `manifest.jsonl` file containing their GPS coordinates.

## 3. Running the Model (Inference)

You can run the model manually by sending an image to the API via `curl`.

### The Command

Pick an image (e.g., from the `blr_potholes` folder or any sample image) and run:

```bash
curl -X POST "http://localhost:8000/api/v1/detect" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@data/demo/blr_potholes/images/SOME_IMAGE.jpg;type=image/jpeg" \
  -F "lat=12.9716" \
  -F "lng=77.5946"
```
*(Replace `SOME_IMAGE.jpg` with an actual filename, and use a `lat/lng` near Bengaluru for successful contract matching, though inference will run regardless of location).*

### Verifying the Output

A **successful** detection of damage looks like this in the JSON response:

```json
{
  "inspection_id": 42,
  "pipeline_status": "SUCCEEDED",
  "total_detections": 1,
  "primary_defect": {
    "class_name": "pothole",
    "severity_level": "HIGH",
    "severity_score": 0.85,
    "confidence": 0.9241
  },
  "all_detections": [
    {
      "class_id": 3,
      "class_name": "pothole",
      "confidence": 0.9241,
      "bbox_x": 0.5,
      "bbox_y": 0.5,
      "bbox_w": 0.2,
      "bbox_h": 0.2
    }
  ]
}
```

A **successful** run that found **NO damage** looks like this:

```json
{
  "inspection_id": 43,
  "pipeline_status": "SUCCEEDED",
  "total_detections": 0,
  "primary_defect": null,
  "all_detections": []
}
```

## 4. Debugging 0.0% Confidence / Empty Detections

If you expect an image to show damage, but the model returns `total_detections: 0` or you suspect it's failing, follow these steps:

### A. Check the Confidence Threshold
The YOLO model wrapper (`aria/inference/detector.py`) hardcodes the confidence threshold:
```python
CONF_THRESHOLD: float = 0.25
```
If the model is 24% confident it saw a pothole, it will silently drop it, resulting in 0 detections.
*   **Fix:** Temporarily change `CONF_THRESHOLD = 0.05` in `detector.py`, restart the server, and rerun the test to see if the model is detecting anything at all.

### B. Verify the Image Pipeline (P1 Bug Alert)
Due to a known bug (documented in `BUG_IMPROVEMENTS.md`), if the Pillow library fails to decode the image, `run_pipeline` might fail and the route might swallow the error, treating it as "no damage".
*   **Check Server Logs:** Look at the terminal where `uvicorn` is running. Do you see:
    `WARNING: aria.inference.pipeline: Pipeline failed: uploaded file is not a valid image`
    If so, your file is corrupted or unsupported.
*   **Frontend Upload Issue:** If using the React UI, it currently forces the `Content-Type` to `image/jpeg` even for `.webp` or `.png` files. Always use `curl` for strict pipeline debugging to ensure the exact bytes are sent correctly.

### C. Check Class Mapping (P3 Bug Alert)
If the model was recently retrained or replaced, the class IDs might have shifted.
*   `detector.py` expects: `0=longitudinal_crack`, `1=transverse_crack`, `2=alligator_crack`, `3=pothole`.
*   If the model returns an ID outside this range, it will crash. Check the Uvicorn error logs for `ValueError: YOLO returned unknown class id`.

### D. Verify the Input Image Quality
YOLO models are highly sensitive to:
1.  **Resolution:** Images are resized to `640x640`. Extremely wide panoramas will be squished and fail detection.
2.  **Blur:** Motion blur from moving vehicles drastically reduces confidence scores.
3.  **Lighting:** Nighttime photos without flash will almost certainly return 0 detections.

## 5. Summary Workflow for AI Agents

To verify the model is operational autonomously:
1. `ls ./models/aria_stage1.pt` (Verify weights exist).
2. `curl http://localhost:8000/health` (Verify API is up).
3. Use a known good base64 string or local file to `POST /api/v1/detect`.
4. Parse the JSON response. Assert `pipeline_status == "SUCCEEDED"`.
5. If `total_detections == 0`, lower `CONF_THRESHOLD` in code to prove the inference engine is executing without exceptions, just scoring low.