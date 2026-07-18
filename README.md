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

| Tool | Version |
|------|---------|
| Python | 3.11+ |
| Node.js | 18+ |
| npm | 9+ |

### 1. Clone the Repository

```bash
git clone https://github.com/dptel22/A.R.I.A.git
cd A.R.I.A
```

### 2. Set Up the Backend

```bash
python -m venv .venv

# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
pip install pytest
```

Configure environment:

```bash
cp .env.example .env   # macOS/Linux
copy .env.example .env # Windows
```

Key `.env` defaults:

```
ARIA_DB_PATH=./runtime/db/aria.db
ARIA_MODEL_PATH=./models/aria_best_v1.pt
ARIA_UPLOAD_DIR=./runtime/uploads
```

### 3. Seed Demo Data

```bash
python -m aria.db.seed
```

Creates demo road segments, contracts, and seeded inspections in the local SQLite DB.

### 4. Start the Backend

```bash
uvicorn aria.api.app:app --reload --port 8000
```

Verify: [http://localhost:8000/docs](http://localhost:8000/docs)

### 5. Start the Frontend

```bash
cd frontend
npm install
cp .env.example .env.local   # macOS/Linux
copy .env.example .env.local # Windows
npm run dev
```

Set in `frontend/.env.local`:

```
VITE_ARIA_API_URL=http://localhost:8000
VITE_ARIA_API_KEY=<same value as ARIA_API_KEY in .env>
```

Open: [http://localhost:3000](http://localhost:3000)

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

Default target: `./models/aria_best_v1.pt`

See: [docs/setup/model-release.md](docs/setup/model-release.md)

---

## Testing

### Backend Tests

```bash
.venv/bin/python -m pytest tests -q
# Windows:
.venv\Scripts\python -m pytest tests -q
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
