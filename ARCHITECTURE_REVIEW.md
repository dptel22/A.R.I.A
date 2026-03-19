# A.R.I.A. — Architecture & Code Review Guide

This guide explicitly details the architectural decisions, intent, and implementation of the A.R.I.A. system. Read this before attempting to audit the codebase. 

---

## 1. Project Intent & Scope
**The Intent:** A.R.I.A. (Automated Road Inspection Agent) is an **edge-deployable** AI pipeline designed to eliminate manual municipal road inspections. It automates hardware-level damage detection, enforces severity classifications, and dynamically generates actionable legal notices for contractors.

**The "Why":** Manual inspection is inherently biased and slow. By enforcing a **deterministic pipeline** (Image → YOLO Inference → Geospatial Contract Match → PDF Generation), we remove human error and API bloat. 

---

## 2. API & Core Logic (`/api` and `/core`)
**How we built it:** The backend is powered by **FastAPI**, with a local **SQLite** database and a PDF generator utilizing **ReportLab**.

**Why we did it this way:**
- **FastAPI:** Chosen for its native asynchronous capabilities and strict OpenAPI schema validation. Blocking threads while waiting for image uploads or I/O is a **junior mistake**; async endpoints prevent the server from choking under load.
- **In-Memory PDF Streaming:** The `/api/v1/notices/{id}` endpoint constructs PDF binaries in a `BytesIO` buffer and streams them directly. Saving physical PDF files to the disk during an HTTP request creates an I/O bottleneck and requires a garbage collection cron job. Streaming directly to the client is the only **acceptable, scalable** approach.
- **Geospatial Tolerance Matching:** We use a strict bounding-box SQL query against GPS coordinates to find the nearest `road_segment`. This prevents floating-point mismatches from failing to find a road.

---

## 3. Inference Engine (`/inference`)
**How we built it:** A firmly isolated module wrapping the `ultralytics` YOLOv11n engine. It accepts raw bytes from the API, runs the forward pass, and returns an agnostic JSON dictionary of bounding boxes and severities.

**Why we did it this way:**
- **Strict Decoupling:** Mixing machine-learning inference code directly inside HTTP routing files (`routes.py`) results in **unmaintainable spaghetti code**. By isolating the logic in `/inference`, we can independently unit-test the model logic without needing to mock HTTP requests.
- **4-Class Severity Matrix:** We rejected heuristic-based "fuzzing" in favor of mathematical mapping. Defects are strictly typed into `LOW`, `MEDIUM`, `HIGH`, or `CRITICAL`. This eliminates vague logic and makes database sorting absolute.

---

## 4. Database Schema Structure (`/db`)
**How we built it:** A heavily normalized SQLite relational structure comprising four primary layers:
1. `road_segments` (Geospatial boundaries)
2. `contracts` (Contractor details and Defect Liability Periods)
3. `inspection_events` (The metadata of a single upload)
4. `detections` (Individual YOLO defects)

**Why we did it this way:**
- **Relational Integrity:** A lazy developer would dump YOLO detections into a JSON text column attached to the `inspection_event`. This is **inexcusable** because it breaks SQL aggregate queries. By separating `detections` into a 1-to-Many table, our backend can execute fast `GROUP BY` and `MAX(severity)` queries to instantly power the Streamlit dashboard metrics.
- **SQLite:** An edge device deployed on a municipal vehicle does not have the RAM to spool up a full PostgreSQL cluster. SQLite ensures zero-configuration, single-file durability.

---

## 5. Frontend Implementation (`/frontend`)
**How we built it:** A multi-page application utilizing **Streamlit** to handle image uploading, map visualization, and dashboard analytics.

**Why we did it this way:**
- **Strict Client-Server Isolation:** The Streamlit app **does not** import `sqlite3` or talk to the database. It exclusively consumes the FastAPI `/api/v1/...` REST endpoints using the `requests` library. Bypassing an API to let a frontend hit a database directly is a **catastrophic security and architectural failure**. Our implementation forces all traffic through the API's validation layers.
- **Rapid Iteration:** Streamlit sidesteps the heavy boilerplate of a React/Next.js stack, allowing us to build data-dense visualizations rapidly while keeping the focus strictly on Python-based backend performance.
