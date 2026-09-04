# 🛣️ A.R.I.A — Automated Road Inspection & Accountability

[![CI](https://github.com/dptel22/A.R.I.A/actions/workflows/ci.yml/badge.svg)](https://github.com/dptel22/A.R.I.A/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)
![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi)
![React](https://img.shields.io/badge/Frontend-React%20%2B%20Vite-61DAFB?logo=react)
![ML](https://img.shields.io/badge/Model-YOLOv11n-purple)
![License](https://img.shields.io/badge/License-MIT-green)

A civic-tech road inspection platform that uses **YOLOv11n** to detect road defects from images, maps detections to geospatial road segments, tracks contractor accountability via a SQLite store, and allows engineers to generate contractor-facing violation notice PDFs — all from a React review console.

---

## 📋 Table of Contents

- [Problem Statement](#problem-statement)
- [Solution Overview](#solution-overview)
- [Features](#features)
- [System Architecture](#system-architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [API Reference](#api-reference)
- [User Stories](#user-stories)
- [Run Modes](#run-modes)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

---

## Problem Statement

Municipal road maintenance suffers from a lack of systematic, evidence-based defect tracking. Inspections are manual, inconsistent, and disconnected from contractor accountability systems. Repeated defects on the same road segment go unnoticed until they become critical failures, leading to public safety hazards and wasted remediation budgets.

---

## Solution Overview

A.R.I.A. is a full-stack inspection platform that:

1. Accepts road images via the review console or API
2. Runs **YOLOv11n inference** to detect and classify road defects
3. Maps each detection to a **geospatial road segment** and associated contract
4. Tracks **repeat failure history** per segment in a SQLite accountability store
5. Allows engineers to generate **contractor-facing notice PDFs** for violations
6. Operates in **Demo Mode** (no model weights needed) for offline/restricted environments

---

## Features

- ✅ **YOLOv11n Defect Detection** — edge-deployable, fast inference on road images
- ✅ **Geospatial Contract Mapping** — links detections to municipal road segments and contractors
- ✅ **Repeat Segment Tracking** — flags roads with recurring defect history
- ✅ **Notice PDF Generation** — contractor-facing violation documents auto-generated
- ✅ **React Review Console** — engineers inspect, filter, and manage detections via UI
- ✅ **Demo Mode** — fully browsable without model weights using seeded data
- ✅ **CI Pipeline** — automated tests on every push via GitHub Actions

---

## 🔍 Scope & Limitations

A.R.I.A. is specifically optimized for **vehicle-mounted systematic sweeps** (dashcam/road-level cameras).
- **Intended Input:** Windshield or bumper-level footage taken at driving distance. Defects typically occupy ~2–8% of the frame, surrounded by road-edge and lane-marking context.
- **Out-of-Scope (v1 Model):** Ad-hoc citizen phone photos (extreme close-ups where a pothole fills 40–90% of the frame). The current model's feature representation is not trained on close-up framing, causing raw confidence to collapse. Generalization to this domain requires a separate Stage 3 training dataset with scale-augmentation.

---

## System Architecture

```
┌─────────────────────────────────────────────────────┐
│              USER (Municipal Engineer)              │
│         Uploads image / reviews detections          │
└──────────────────────────┬──────────────────────────┘
                           │ HTTP
                           ▼
┌─────────────────────────────────────────────────────┐
│            React + Vite Review Console              │
│   Inspect detections | Filter segments | PDF export  │
└──────────────────────────┬──────────────────────────┘
                           │ REST API
                           ▼
┌─────────────────────────────────────────────────────┐
│              FastAPI Backend (Port 8000)             │
│                                                     │
│  ┌─────────────────┐   ┌─────────────────────────┐  │
│  │  Image Router   │──▶│  YOLOv11n Inference     │  │
│  └─────────────────┘   └────────────┬────────────┘  │
│                                     │               │
│  ┌──────────────────────────────────▼────────────┐  │
│  │       Geospatial Contract Mapper              │  │
│  └──────────────────────────────────┬────────────┘  │
│                                     │               │
│  ┌──────────────────────────────────▼────────────┐  │
│  │       SQLite Accountability Store             │  │
│  │   (segments, contracts, detections, history)  │  │
│  └──────────────────────────────────┬────────────┘  │
│                                     │               │
│  ┌──────────────────────────────────▼────────────┐  │
│  │         Notice PDF Generator                 │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18, Vite, JavaScript |
| Backend | Python 3.11, FastAPI, Uvicorn |
| ML Model | YOLOv11n (Ultralytics) |
| Database | SQLite3 |
| PDF Generation | WeasyPrint / ReportLab |
| Testing | pytest |
| CI | GitHub Actions |
| API Docs | Swagger UI (auto via FastAPI) |

---

## Project Structure

```text
A.R.I.A/
├─ aria/                        # Backend package
│  ├─ api/routes/               # FastAPI route modules
│  ├─ db/                       # SQLite schema, seed, migrations
│  ├─ domain/                   # Domain models
│  ├─ inference/                # YOLOv11n inference pipeline
│  └─ services/                 # Business logic (contract mapping, PDF)
├─ tests/                       # Backend + inference tests
├─ frontend/                    # React + Vite review console
├─ scripts/                     # Helper scripts, model downloader
├─ data/demo/                   # Seeded demo datasets and sample images
├─ docs/
│  ├─ architecture/
│  ├─ notes/
│  └─ setup/
├─ experiments/                 # Notebooks and exploratory work
├─ runtime/                     # Local DB, uploads, notices (git-ignored)
└─ models/                      # Model weights (git-ignored)
```

---

## Getting Started

### Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| uv | >=0.4.0 | Recommended canonical package manager |
| Python | 3.11 | Python 3.11 runtime |
| Node.js | 18+ | For React frontend |
| Docker & Compose | Modern (v2+) | For containerized CPU/GPU deployment |

---

### Local Development (uv — Canonical)

#### 1. Clone & Synchronize Dependencies

```bash
git clone https://github.com/dptel22/A.R.I.A.git
cd A.R.I.A

# Synchronize virtual environment directly from uv.lock
uv sync
```

*(Compatibility path: `python -m pip install -r requirements.txt` is maintained as a fallback)*

#### 2. Configure Environment

```bash
cp .env.example .env   # macOS/Linux
copy .env.example .env # Windows
```

#### 3. Model Weights & Database Seed

```bash
# Download YOLO weights from latest release
uv run python -m scripts.download_model

# Seed demo road segments, contracts, and inspections
uv run python -m aria.db.seed
```

#### 4. Run Services

**Backend (Port 8000):**
```bash
uv run uvicorn aria.api.app:app --reload --port 8000
```
Interactive Swagger docs: [http://localhost:8000/docs](http://localhost:8000/docs)

**Frontend (Port 3000):**
```bash
cd frontend
npm install
npm run dev
```
Open: [http://localhost:3000](http://localhost:3000) (Vite dev proxy transparently handles API authentication without exposing secrets in browser code).

**Windows 1-Click Startup:**
Run `start_windows.bat` to automatically sync with `uv`, check weights, and launch both backend and frontend.

---

### Docker Container Deployment

A.R.I.A provides a production-grade, reproducible container architecture:
* **Nginx Reverse Proxy**: Only service exposed to host (`:3000`), injects `X-Api-Key` server-side so production API keys are never visible to browsers.
* **Non-Root FastAPI Backend**: Runs as `aria:aria` user on internal network (`aria-net`), exposing port 8000 only to Nginx.
* **Persistent Named Volumes**: `aria_runtime` (SQLite DB, uploads, notice PDFs) and `aria_models` (YOLO `.pt` weights).
* **Single Worker YOLO**: Serialized inference pipeline on batch-1 / `imgsz=640`.

#### CPU Production Deployment

```bash
# Build and start services
docker compose -f docker-compose.yml up -d --build

# Verify health status
docker compose -f docker-compose.yml ps
curl http://localhost:3000/health
curl http://localhost:3000/ready
```

#### NVIDIA GPU Production Deployment

```bash
# Start with GPU override (requires NVIDIA Container Toolkit)
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
```

Inside the GPU container, inference executes on the dedicated CUDA device (`ARIA_INFERENCE_DEVICE=0`).

#### Local Dev via Compose (Live Reload)

```bash
# Mounts local source directories with live reload
docker compose up
```

To stop containers:
```bash
docker compose down
# Note: named volumes (aria_runtime, aria_models) survive. To wipe: docker compose down -v
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Backend + model status |
| `POST` | `/inspect` | Upload image for defect detection |
| `GET` | `/segments` | List all road segments |
| `GET` | `/segments/{id}/history` | Repeat defect history for a segment |
| `GET` | `/detections` | All logged detections |
| `POST` | `/notices/{detection_id}` | Generate contractor notice PDF |

Full interactive docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## User Stories

> Functional requirements captured as user stories — useful for SRS documentation.

| ID | As a... | I want to... | So that... |
|----|---------|--------------|------------|
| US-01 | Municipal Engineer | Upload a road image | I receive an automated defect detection result |
| US-02 | Engineer | See which road segment a defect belongs to | I can trace it to the responsible contractor |
| US-03 | Engineer | View repeat failure history per segment | I can identify roads with recurring problems |
| US-04 | Engineer | Generate a notice PDF | I can formally hold contractors accountable |
| US-05 | Admin | Browse the dashboard without model weights | I can use the system in demo/offline mode |
| US-06 | Developer | Run the full test suite | I can verify system integrity before deployment |

---

## Run Modes

### Demo Mode (default)
Works without model weights. Browse the dashboard, inspect seeded cases, review segment history, and open generated notices — all with no ML dependency.

### Full Detection Mode
Download model weights from the latest GitHub Release:

```bash
python -m scripts.download_model
```

Default target: `./models/aria_stage1.pt`

See: [docs/setup/model-release.md](docs/setup/model-release.md)

BLR pothole benchmark images are generated local data and are not tracked in git:

```bash
python -m scripts.download_blr_potholes --limit 50
python -m scripts.run_benchmark --limit 50
```

---

## Testing

### Backend Tests

```bash
# Primary (uv)
uv run pytest tests -q

# Compatibility (pip / active virtualenv)
pytest tests -q
```

### Frontend Checks

```bash
cd frontend
npm ci
npm run lint
npm run build
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Model not loading | Run in Demo Mode; download weights with `python -m scripts.download_model` |
| DB not found | Run `python -m aria.db.seed` to initialize the SQLite database |
| Frontend 401 errors | Ensure `VITE_ARIA_API_KEY` matches `ARIA_API_KEY` in backend `.env` |
| Port already in use | Kill existing process on port 8000 or 3000 and restart |
| CI badge failing | Check [Actions tab](https://github.com/dptel22/A.R.I.A/actions) for failing test details |

---

## Supporting Docs

- Frontend setup: [frontend/README.md](frontend/README.md)
- Model release: [docs/setup/model-release.md](docs/setup/model-release.md)
- Bug notes: [docs/notes/BUG_IMPROVEMENTS.md](docs/notes/BUG_IMPROVEMENTS.md)
