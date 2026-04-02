# A.R.I.A. (Automated Road Inspection Agent)

An **edge-deployable AI system** for real-time road damage detection, automated severity assessment, and contract enforcement notice generation.

## System Architecture
A.R.I.A. operates through two primary layers designed for resilience and fast iteration:
1. **Inference Pipeline & Core API (FastAPI)**: Integrates a fine-tuned **YOLOv11n model** that processes incoming road imagery, detecting defects across a **4-class severity model** (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`). It performs geospatial coordinate matching to map detections to active municipal road contracts and determines if the Defect Liability Period (DLP) is enforceable.
2. **Municipal Review Console (React + Vite)**: A desktop-first frontend for municipal engineers to upload geo-tagged images into the detection pipeline, review historical inspections, inspect live bounding boxes, and open generated **PDF enforcement notices**.

## Module Breakdown
- `/api`: The FastAPI application defining critical REST endpoints (e.g., `/detect`, `/detections`, `/notices/{id}`).
- `/core`: Domain logic models, severity mapping algorithms, and the ReportLab-powered PDF enforcement notice generator.
- `/inference`: The isolated YOLOv11 pipeline wrapping model loading and image inferences.
- `/frontend`: The React + Vite municipal review console.
- `/db`: SQLite schema initialization and data seeding utilities.

## Prerequisites
- **Python 3.10+**
- Appropriate C/C++ build tools (for dependencies on Windows/Linux)
- Required modules defined in `requirements.txt`

## Local Setup

**1. Clone and Virtual Environment**
```bash
git clone https://github.com/dptel22/A.R.I.A.git
cd A.R.I.A
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/MacOS:
source .venv/bin/activate
```

**2. Install Dependencies**
```bash
pip install -r requirements.txt
```

**3. Environment Configuration**
```bash
cp .env.example .env
# Edit .env to populate the ARIA_API_KEY and local paths.
```

**4. Initialize Database**
To construct the local SQLite database schema and seed it with initial test segments and dummy contractors:
```bash
python -m db.seed
```

## Running the Application Layers

### API Backend
Start the Uvicorn ASGI server hosting the FastAPI instance on port `8000`:
```bash
uvicorn api.app:app --reload
```

### Dashboard Frontend
Start the React frontend on port `3000`:
```bash
cd frontend
npm install
copy .env.example .env.local
npm run dev
```

Populate `frontend/.env.local` with:

- `VITE_ARIA_API_URL`
- `VITE_ARIA_API_KEY`

## Downloading BLR Potholes Data For Local Testing

If you want to test A.R.I.A. against the `warlockdn/blr-potholes-data` GitHub issues dataset, use the one-time downloader:

```bash
python -m tools.download_blr_potholes
```

This writes local files to:

- `data/blr_potholes/images/`
- `data/blr_potholes/manifest.jsonl`
- `data/blr_potholes/download_failures.jsonl`

Helpful options:

```bash
python -m tools.download_blr_potholes --limit 25
python -m tools.download_blr_potholes --force
```

Notes:

- The downloader uses GitHub issues as metadata and ImageKit URLs as the image source.
- Downloaded data is kept separate from the repo's existing `images/` folder used by the smoke test script.
- If you have a GitHub token available, export `GITHUB_TOKEN` to reduce API rate-limit risk.

## Security & Deployment
Ensure `ARIA_API_KEY` is completely obfuscated prior to production deployment. This service is intended for **Edge Deployment paradigms**: computational inferences run close to the data source (the inspector's device or proxy endpoint) rather than relying on heavy, distant cloud processing.
