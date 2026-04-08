# A.R.I.A. | Automated Road Inspection & Accountability

[![CI](https://github.com/dptel22/A.R.I.A/actions/workflows/ci.yml/badge.svg)](https://github.com/dptel22/A.R.I.A/actions/workflows/ci.yml)

A.R.I.A. is a civic-tech inspection platform built for municipal road maintenance teams. It combines a FastAPI backend, a YOLO-based road-damage pipeline, a SQLite accountability store, and a React review console so engineers can inspect detections, review repeated failures on the same road segment, and generate contractor-facing notice PDFs.

This repository is designed to be readable by a hiring manager and runnable by an engineer from a fresh clone.

## Why This Project Matters

Municipal road inspections are often slow, inconsistent, and hard to audit. A.R.I.A. turns a road image and GPS coordinates into:

- a structured inspection record
- severity-ranked defect detections
- contractor and DLP context
- a repeat-flag history for the same road segment
- an engineer-facing review workflow with generated notice exports

The recent implementation pass focused on **trust and accountability**:

- failed inference is no longer silently reported as a clean road
- every inspection attempt is persisted, including failed and zero-detection runs
- contract and DLP state are snapshotted at inspection time for historical stability
- repeat segment history is exposed in the engineer UI
- notice downloads now work through authenticated frontend fetches

## Highlights

- **FastAPI backend** with structured inspection and notice endpoints
- **YOLO-powered damage pipeline** with metadata-based class validation
- **SQLite audit store** with inspection snapshots and repeat-failure visibility
- **React + Vite review console** for queue triage, case detail, and decision history
- **ReportLab PDF notice generation** for contractor-facing enforcement artifacts
- **GitHub Actions CI** for backend tests and frontend build validation

## Tech Stack

- Backend: FastAPI, Uvicorn, SQLite, Python
- Inference: Ultralytics YOLO, NumPy, Pillow
- Frontend: React 19, TypeScript, Vite, Tailwind CSS
- Reporting: ReportLab
- Testing: Pytest, TypeScript typecheck

## Architecture

### Backend API

The backend accepts uploads, maps coordinates to road segments, runs inference, stores inspection history, and exposes engineer-facing endpoints for queue/detail/history and notice export.

Important backend modules:

- `api/`: HTTP entrypoints and request handling
- `db/`: schema, connection factory, and seed data
- `core/`: domain models, severity logic, and notice generation
- `inference/`: detection and scoring pipeline

### Review Console

The frontend is a municipal review dashboard that shows:

- a prioritized queue of inspections
- inspection detail with overlays and accountability context
- decision history with repeat-segment timeline
- archive-level operational summaries derived from stored inspections

## Quickstart

### 1. Clone the repository

```bash
git clone https://github.com/dptel22/A.R.I.A.git
cd A.R.I.A
```

### 2. Set up Python

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS / Linux:

```bash
source .venv/bin/activate
```

Install backend dependencies:

```bash
pip install -r requirements.txt
pip install pytest
```

### 3. Configure backend environment

Copy the template:

```bash
copy .env.example .env
```

macOS / Linux:

```bash
cp .env.example .env
```

Required values in `.env`:

- `ARIA_API_KEY`
- `ARIA_DB_PATH`
- `ARIA_MODEL_PATH`
- `ARIA_ALLOWED_ORIGINS`
- `ARIA_UPLOAD_DIR`

The template also includes:

- `ARIA_MODEL_RELEASE_URL`

### 4. Seed demo data

```bash
python -m db.seed
```

This creates a local SQLite DB with demo road segments, contracts, and seeded inspections.
The backend also auto-initializes a missing SQLite schema at startup, so seeding is recommended for reviewable demo data rather than required for basic boot.

### 5. Set up the frontend

```bash
cd frontend
npm install
copy .env.example .env.local
```

macOS / Linux:

```bash
cp .env.example .env.local
```

Set these values in `frontend/.env.local`:

- `VITE_ARIA_API_URL=http://localhost:8000`
- `VITE_ARIA_API_KEY=<same value as ARIA_API_KEY>`

### 6. Start the backend

From the project root:

```bash
uvicorn api.app:app --reload --port 8000
```

The backend will:

- create the SQLite schema if it does not exist yet
- load the YOLO model if `ARIA_MODEL_PATH` is present
- keep the archive browsable even when the model is unavailable

### 7. Start the frontend

From `frontend/`:

```bash
npm run dev
```

Open the frontend in your browser and use the seeded Bengaluru coordinates listed below.

## Run Modes

### Demo Mode

Demo mode works **without the YOLO model file**.

You can still:

- start the backend
- browse the dashboard
- inspect seeded cases
- review repeat segment history
- open generated notices for seeded detections

You cannot run new live detections until the model weights are available.

### Full Detection Mode

To enable live detection, download the YOLO weights from the latest GitHub Release:

```bash
python -m tools.download_model
```

Default asset target:

- release asset: `aria_stage1.pt`
- default download URL: `https://github.com/dptel22/A.R.I.A/releases/latest/download/aria_stage1.pt`
- default local path: `./aria_stage1.pt`

You can change the path with `ARIA_MODEL_PATH`.

More detail: [docs/model-release.md](docs/model-release.md)

## Demo Flow

Use one of the seeded Bengaluru coordinates when running a live upload in the UI:

- `12.9310, 77.6450`
- `13.0600, 77.5950`
- `12.9800, 77.6950`

Expected demo reviewer flow:

1. Launch backend and frontend.
2. Open the Review Queue.
3. Inspect seeded cases and note DLP and contractor context.
4. Open a case to view repeat-segment history and generated notices.
5. If the model file is present, upload a new image and verify the inspection is stored with a pipeline status.

## Verification

### Backend tests

```bash
.venv\Scripts\python -m pytest api\test_routes.py core inference -q
```

### Frontend checks

```bash
cd frontend
npm ci
npm run lint
npm run build
```

## GitHub Automation

This repo includes a GitHub Actions workflow at `.github/workflows/ci.yml` that:

- runs backend tests on Python 3.11
- installs frontend dependencies with `npm ci`
- runs frontend typecheck with `npm run lint`
- runs the production build with `npm run build`

This gives reviewers a visible signal that the project is actively validated.

## Project Quality

- Structured pipeline statuses: `SUCCEEDED`, `NO_DETECTIONS`, `FAILED`
- Snapshot-based inspection persistence for historical contract accuracy
- Repeat-segment inspection history for engineer accountability
- Masked contractor contact in normal API responses
- Detector label validation against model metadata
- Type-checked frontend API contract
- Backend tests for failure handling, pagination totals, masking, and snapshot stability

## Repository Layout

- `api/`: FastAPI app and route handlers
- `core/`: domain models, severity logic, and PDF generation
- `db/`: SQLite schema, connection setup, and seed data
- `frontend/`: React + Vite municipal review console
- `inference/`: model wrapper, pipeline, and inference tests
- `tools/`: helper scripts for dataset and model download

## Limitations

- The current product is still image-first rather than full end-of-day video ingestion
- Persistent engineer decision workflows are not implemented yet
- The archive summary view is derived from stored inspections, not a first-class ingestion-run backend
- The model file must be downloaded separately for live detection mode
- The repository is optimized for local run + CI, not Docker/Codespaces as the primary path

## Roadmap

- persistent engineer decision workflows
- ingestion-run tracking as a first-class backend concept
- repair queue for non-DLP cases
- batch/video ingestion pipeline
- richer geospatial matching beyond seeded bounding-box segments

## Resume Blurb

You can adapt these bullets directly:

- Built a full-stack civic-tech inspection platform using FastAPI, React, SQLite, and YOLO to automate municipal road-damage triage and contractor accountability workflows.
- Designed a reliability-focused inspection pipeline with audit-safe snapshot persistence, explicit failure handling, repeat-segment tracking, and authenticated PDF notice delivery.
- Added automated backend/frontend validation with GitHub Actions and packaged the project for clean demo-mode and full-model local execution from a public GitHub repository.

## Supporting Docs

- Frontend setup: [frontend/README.md](frontend/README.md)
- Model release note: [docs/model-release.md](docs/model-release.md)
