# A.R.I.A. | Automated Road Inspection & Accountability

[![CI](https://github.com/dptel22/A.R.I.A/actions/workflows/ci.yml/badge.svg)](https://github.com/dptel22/A.R.I.A/actions/workflows/ci.yml)

A.R.I.A. is a civic-tech inspection platform for municipal road maintenance teams. It combines a FastAPI backend, a YOLO-based road-damage pipeline, a SQLite accountability store, and a React review console so engineers can inspect detections, review repeated failures on the same road segment, and generate contractor-facing notice PDFs.

## Repository Layout

```text
A.R.I.A/
├─ aria/                  # backend package (api, db, domain, inference, services)
├─ tests/                 # backend and inference tests
├─ frontend/              # React + Vite review console
├─ scripts/               # helper scripts and benchmarks
├─ data/demo/             # tracked demo datasets and sample images
├─ docs/
│  ├─ architecture/
│  ├─ notes/
│  └─ setup/
├─ experiments/           # notebooks and exploratory work
├─ runtime/               # local DB, uploads, notices, YOLO config (ignored)
└─ models/                # local model weights (ignored)
```

## Quickstart

### 1. Clone and install Python dependencies

```bash
git clone https://github.com/dptel22/A.R.I.A.git
cd A.R.I.A
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

### 2. Configure the backend

Copy the template and update the values:

```bash
copy .env.example .env
```

Important defaults in `.env.example` now point to the cleaned runtime layout:

- `ARIA_DB_PATH=./runtime/db/aria.db`
- `ARIA_MODEL_PATH=./models/aria_stage1.pt`
- `ARIA_UPLOAD_DIR=./runtime/uploads`

### 3. Seed demo data

```bash
python -m aria.db.seed
```

This creates a local SQLite DB with demo road segments, contracts, and seeded inspections.

### 4. Start the backend

```bash
uvicorn aria.api.app:app --reload --port 8000
```

The backend will:

- initialize the SQLite schema if it does not exist
- load the YOLO model if `ARIA_MODEL_PATH` exists
- keep the archive browsable even when the model is unavailable

### 5. Start the frontend

```bash
cd frontend
npm install
copy .env.example .env.local
npm run dev
```

Set these values in `frontend/.env.local`:

- `VITE_ARIA_API_URL=http://localhost:8000`
- `VITE_ARIA_API_KEY=<same value as ARIA_API_KEY>`

## Run Modes

### Demo Mode

Demo mode works without model weights. You can still browse the dashboard, inspect seeded cases, review repeat-segment history, and open generated notices for seeded detections.

### Full Detection Mode

To enable live detection, download the weights from the latest GitHub Release:

```bash
python -m scripts.download_model
```

Default asset target:

- release asset: `aria_stage1.pt`
- default download URL: `https://github.com/dptel22/A.R.I.A/releases/latest/download/aria_stage1.pt`
- default local path: `./models/aria_stage1.pt`

More detail: [docs/setup/model-release.md](docs/setup/model-release.md)

## Verification

### Backend tests

```bash
.venv\Scripts\python -m pytest tests -q
```

### Frontend checks

```bash
cd frontend
npm ci
npm run lint
npm run build
```

## Project Notes

- Backend code lives under `aria/` with route modules in `aria/api/routes/` and workflow logic in `aria/services/`.
- Frontend source is organized into `src/app/`, `src/features/`, and `src/shared/`.
- Demo assets live under `data/demo/`.
- Runtime outputs are intentionally kept under `runtime/` and ignored by git.

## Supporting Docs

- Frontend setup: [frontend/README.md](frontend/README.md)
- Model release note: [docs/setup/model-release.md](docs/setup/model-release.md)
- Engineering notes: [docs/notes/BUG_IMPROVEMENTS.md](docs/notes/BUG_IMPROVEMENTS.md)
