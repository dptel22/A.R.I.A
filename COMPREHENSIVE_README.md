# A.R.I.A. | Comprehensive Technical Documentation

A.R.I.A. (Automated Road Inspection & Accountability) is a civic-tech platform designed for municipal road maintenance teams, specifically focused on Bengaluru (BLR).

## 1. Project Overview

**What it is:** A web-based application combining a Python/FastAPI backend, a React/Vite frontend dashboard, and a YOLO-based computer vision model.

**Problem it solves:** Municipalities often struggle to track and enforce road maintenance contracts. A.R.I.A. automates the detection of road damage (like potholes and cracks) from imagery, matches the GPS coordinates of the damage to active road segment maintenance contracts (checking the Defect Liability Period or DLP), and generates enforceable PDF notices against contractors for failed segments. This turns visual evidence into an automated accountability workflow.

---

## 2. Repository Structure

```text
A.R.I.A/
├─ aria/                  # Backend Python application package
│  ├─ api/                # FastAPI routing and application lifecycle
│  │  ├─ app.py           # Main FastAPI entry point; handles CORS, lifespan events
│  │  └─ routes/          # API endpoint definitions (/detect, /notices, etc.)
│  ├─ db/                 # SQLite database integration
│  │  ├─ schema.py        # Database schema definitions and initialization
│  │  └─ seed.py          # Script to populate the DB with demo data
│  ├─ domain/             # Core business logic models
│  │  ├─ models.py        # Pydantic models/dataclasses for API and business logic
│  │  └─ severity.py      # Business rules for mapping severity to enforcement actions
│  ├─ inference/          # Machine learning pipeline integration
│  │  ├─ detector.py      # YOLO model wrapper and bounding box parsing
│  │  ├─ pipeline.py      # Orchestrates image decoding -> detection -> scoring
│  │  └─ severity_calc.py # Algorithms to calculate a severity score from bounding boxes
│  └─ services/           # Orchestration layer
│     ├─ inspection_service.py # Handles /detect logic, DB storage, contract matching
│     └─ notice_service.py     # Generates PDF notices from inspection data
├─ frontend/              # React + Vite frontend application (Review UI)
│  ├─ src/                # React source code
│  │  ├─ app/             # Application shell, layout, routing
│  │  ├─ features/        # Main UI modules (queue, case-detail, history, runs)
│  │  └─ shared/          # Shared utilities (API clients, mappers, types)
│  └─ package.json        # Frontend dependencies and scripts
├─ scripts/               # Utility scripts and benchmarks
│  ├─ benchmarks/         # Performance testing scripts
│  ├─ download_blr_potholes.py # Downloader for GitHub issue-based pothole dataset
│  └─ download_model.py   # Script to fetch the YOLO model weights from GitHub Releases
├─ data/demo/             # Tracked demo datasets and sample images for testing
├─ docs/                  # Project documentation
│  ├─ architecture/       # Architectural diagrams and notes
│  ├─ notes/              # Engineering notes, including BUG_IMPROVEMENTS.md
│  └─ setup/              # Setup instructions
├─ experiments/           # Jupyter notebooks for data exploration and model training
├─ runtime/               # (Git Ignored) Local SQLite DB, uploaded images, generated PDFs
└─ models/                # (Git Ignored) Local ML model weights (e.g., aria_best_v1.pt)
```

**Key Files & Roles:**
*   `aria/api/app.py`: The heart of the backend. Loads the YOLO model on startup and exposes the REST API.
*   `aria/services/inspection_service.py`: The brain of the operation. Takes an image and GPS coordinates, runs the model, finds the road segment, checks the contract DLP, saves the result to SQLite, and returns a recommendation.
*   `aria/inference/pipeline.py`: The ML entry point. Converts bytes to an image, passes it to the detector, and scores the results.
*   `frontend/src/features/queue/ReviewQueue.tsx`: The main dashboard view where engineers see the prioritized list of detected damages.
*   `frontend/src/shared/api/mappers.ts`: Crucial for the UI; maps raw backend data (like integer IDs) into user-friendly formats (like `ARIA-000006`).

---

## 3. Features

*   **Automated Damage Detection:** Upload an image with GPS coordinates; the system uses a YOLO model to identify bounding boxes for potholes, longitudinal cracks, transverse cracks, and alligator cracks.
*   **Severity Scoring:** The backend calculates a severity score based on the defect class and the relative size of the bounding box, classifying it from LOW to CRITICAL.
*   **Geospatial Contract Matching:** Uses a bounding box algorithm in SQLite (`BETWEEN` clauses) to find the road segment corresponding to the image's GPS coordinates.
*   **Defect Liability Period (DLP) Enforcement:** Checks if the matched road segment is currently under an active contract warranty. If it is, and the damage is severe enough, it recommends enforcement.
*   **Review Queue Dashboard:** A React UI that lists all inspections, sortable by severity, DLP status, and chronological order, allowing human review.
*   **Notice Generation:** Generates a PDF notice for the contractor, containing the evidence image, defect details, and contract information, accessible via a `/notices/{id}` API route.

---

## 4. ML Model

*   **Model Used:** Ultralytics YOLO (You Only Look Once) object detection model.
*   **Training & Data:** Trained to detect road surface degradation. The specific training pipeline is in the `experiments/` notebooks. It heavily leverages public datasets, notably the `blr-potholes-data` dataset.
*   **Storage:** Weights are NOT committed to Git to keep the repo small. They are stored as a GitHub Release asset (`aria_best_v1.pt`). The `scripts/download_model.py` script downloads it to `./models/aria_best_v1.pt`.
*   **Defect Classes Detected:**
    1.  `longitudinal_crack`
    2.  `transverse_crack`
    3.  `alligator_crack`
    4.  `pothole`
*   **Known Issues/Limitations:**
    *   *Hardcoded Classes (P3 Bug):* `inference/detector.py` currently hardcodes the expectation that these 4 classes exist. If the model is retrained with different classes, it might silently mislabel data or crash.
    *   *Image Validation (P1 Bug):* If inference fails entirely (e.g., bad image bytes), the system currently treats it as an empty list (meaning "No defect detected"), which creates false negatives instead of operational errors.

---

## 5. Data Pipeline

Data flows into A.R.I.A. through two primary channels:

**1. Live API Ingestion (form-data)**
*   **Source:** A mobile app or field worker calling `POST /api/v1/detect`.
*   **Flow:**
    1.  The request includes `file` (image bytes), `lat`, and `lng` as `multipart/form-data`.
    2.  `aria/api/routes.py` receives the request and passes it to `process_detection` in `inspection_service.py`.
    3.  The image is saved to `./runtime/uploads`.
    4.  `run_pipeline` extracts the image frames using Pillow (`PIL.Image`).
    5.  YOLO performs inference; results are stored in the SQLite DB.
    6.  The result appears in the Review UI.

**2. Asynchronous BLR Profiles Ingestion (GitHub Issues)**
*   **Source:** The `scripts/download_blr_potholes.py` script pulls crowdsourced pothole data from a GitHub repository (`warlockdn/blr-potholes-data`) where citizens submit issues.
*   **Flow:**
    1.  The script queries the GitHub Issues API.
    2.  It parses Markdown front-matter or issue-form bodies to extract `lat`, `long`, and image URLs.
    3.  It downloads the raw images and saves them to `data/demo/blr_potholes/images`.
    4.  It generates a `manifest.jsonl` file linking the local image paths to their GPS coordinates.
    5.  *(Note: Currently, these images must be manually pushed through the `/detect` API to enter the formal review UI).*

---

## 6. How to Run Inference Manually

If you have a folder of images (like the ones downloaded from `blr-potholes`), you can run the model manually.

**Prerequisites:** Backend must be running (`uvicorn aria.api.app:app --reload`).

**Step-by-Step Command (using `curl`):**
```bash
# Assuming you have an image at ./test_pothole.jpg and know the GPS coords
curl -X POST "http://localhost:8000/api/v1/detect" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@./test_pothole.jpg;type=image/jpeg" \
  -F "lat=12.9716" \
  -F "lng=77.5946"
```

**Checking Output:** The JSON response will contain an `all_detections` array. You can verify the `confidence` score (e.g., `0.8543`) and the `severity_level` (e.g., `"HIGH"`).

**Debugging 0.0% Confidence:**
If the model returns an empty array or extremely low confidence:
1.  **Check Model Load:** Look at the FastAPI startup logs. Did it say "Loading YOLO model from ./models/aria_best_v1.pt" or "Model file not found"?
2.  **Check Image Format:** Ensure the file is actually a valid JPEG/PNG, not a corrupted file or WebP (the frontend currently posts everything as `image/jpeg` regardless of true type, a known P2 bug).
3.  **Check Image Content:** Is the pothole visible and clear? YOLO struggles with blurry images or extreme angles.
4.  **Review `inference/detector.py`:** The `CONF_THRESHOLD` is hardcoded to `0.25`. Anything below 25% confidence is silently dropped.

---

## 7. Review UI (ARIA Dashboard)

**How it works:** Built with React/Vite. It polls the FastAPI backend `/api/v1/detections` endpoint to populate a prioritized table of road defects.

**ARIA-XXXXXX IDs:**
In the SQLite database, inspections have standard auto-incrementing integer IDs (e.g., `1`, `2`, `3`). However, the UI displays these as `ARIA-000001`. This formatting is applied entirely on the frontend in `frontend/src/shared/api/mappers.ts` via the `toCaseId()` function.

**Statuses & Meanings:**
*   **Awaiting Review:** A successful detection (with or without damage) that has not been manually actioned.
*   **Escalated:** Usually occurs if the inference pipeline fails completely (e.g., corrupt image), requiring a human to look at the raw data.
*   **Pipeline Labels (Badges):**
    *   `Detected`: Defects found.
    *   `No Defects`: Model ran successfully but found nothing.
    *   `Pipeline Failed`: An error occurred during processing.

---

## 8. How to Test the Model is Working

*(See the dedicated `MODEL_TEST_GUIDE.md` file for an exhaustive walkthrough).*

**Quick Sanity Check:**
1.  Ensure weights are downloaded: `python -m scripts.download_model`
2.  Seed the DB: `python -m aria.db.seed`
3.  Start backend: `uvicorn aria.api.app:app`
4.  Upload a known bad road image via the UI or `curl`. A good output JSON will list `"primary_defect": {"class_name": "pothole", ...}`. A broken output might return `"pipeline_status": "FAILED"`.

---

## 9. Environment Setup

### Local Setup (Windows/macOS/Linux)
1.  **Python:** Create a venv: `python -m venv .venv` and activate it.
2.  **Dependencies:** `pip install -r requirements.txt`
3.  **Config:** `cp .env.example .env`
4.  **Model:** `python -m scripts.download_model`
5.  **Database:** `python -m aria.db.seed`
6.  **Backend:** `uvicorn aria.api.app:app --reload --port 8000`
7.  **Frontend:** `cd frontend && npm install && cp .env.example .env.local && npm run dev`

### VM / Linux Server Setup
1.  Ensure Python 3.10+ and Node.js 18+ are installed.
2.  Set environment variables globally or in `/etc/environment`:
    *   `ARIA_DB_PATH=/var/lib/aria/aria.db`
    *   `ARIA_MODEL_PATH=/opt/aria/models/aria_best_v1.pt`
    *   `ARIA_UPLOAD_DIR=/var/www/aria/uploads`
3.  Run the backend as a Systemd service using `gunicorn` with `uvicorn.workers.UvicornWorker`.
4.  Build the frontend (`npm run build`) and serve the `dist/` directory via Nginx, proxying `/api` requests to the Uvicorn port.

### Docker (Conceptual - No Dockerfile currently exists in repo)
You would need two containers:
1.  **API Container:** `FROM python:3.10-slim`, install requirements, mount a volume for `./runtime` and `./models`, expose port 8000.
2.  **UI Container:** `FROM nginx:alpine`, copy the output of `npm run build` into `/usr/share/nginx/html`.

---

## 10. Known Bugs / TODO

*(Sourced directly from `docs/notes/BUG_IMPROVEMENTS.md`)*

**High Priority (P1):**
*   **Inference Failures Hidden:** `run_pipeline()` returns empty lists on failure; `/detect` treats this as "clean road" instead of raising an error.
*   **Contract State Drift:** Inspections don't snapshot contractor names/DLP dates. If a contract is updated, old inspection records retroactively change.

**Medium Priority (P2):**
*   **Auth for PDF Notices:** The UI links directly to PDF notices, which require an `x-api-key`. Browsers fail to load them directly; a proxy or download trigger is needed.
*   **MIME Validation Flaw:** Frontend posts all uploads as `image/jpeg`, bypassing backend validation of things like `webp` files.
*   **Zero-Detection Audit Loss:** If no defect is found, the backend drops the inspection instead of saving it, losing the audit trail that the road was checked.
*   **Ugly PDF Labels:** PDFs show internal ENUM names (e.g., `DAMAGE_CRITICAL`) instead of user-friendly ones (`CRITICAL`).

**Low Priority (P3):**
*   **Hardcoded ML Classes:** `inference/detector.py` ignores the model's built-in `names` metadata and hardcodes the 4 defect classes.
*   **Pagination Math:** `/detections` reports the page limit as the total count, breaking UI pagination.
*   **GPS Tolerance Ignored:** The code claims a 20m tolerance for matching coordinates to roads, but the SQL query only uses a strict bounding box.
*   **PII Exposure:** Contractor emails are returned raw in standard API responses.
*   **Hardcoded Origin:** The frontend hardcodes `http://localhost:8000` in various places instead of using the env config consistently.
