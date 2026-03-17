# A.R.I.A. (Automated Road Inspection Agent)

An **edge-deployable AI system** for real-time road damage detection, automated severity assessment, and contract enforcement notice generation.

## System Architecture
A.R.I.A. operates through two primary layers designed for resilience and fast iteration:
1. **Inference Pipeline & Core API (FastAPI)**: Integrates a fine-tuned **YOLOv11n model** that processes incoming road imagery, detecting defects across a **4-class severity model** (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`). It performs geospatial coordinate matching to map detections to active municipal road contracts and determines if the Defect Liability Period (DLP) is enforceable.
2. **Interactive Inspector Dashboard (Streamlit)**: A multi-page frontend enabling field agents to upload geo-tagged images, visualize bounding-box detections, query historical inspections, and directly download generated **PDF enforcement notices** for negligent contractors.

## Module Breakdown
- `/api`: The FastAPI application defining critical REST endpoints (e.g., `/detect`, `/detections`, `/notices/{id}`).
- `/core`: Domain logic models, severity mapping algorithms, and the ReportLab-powered PDF enforcement notice generator.
- `/inference`: The isolated YOLOv11 pipeline wrapping model loading and image inferences.
- `/frontend`: The multi-page Streamlit web application.
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
Start the Streamlit interactive dashboard on port `8501`:
```bash
streamlit run frontend/app.py
```

## Security & Deployment
Ensure `ARIA_API_KEY` is completely obfuscated prior to production deployment. This service is intended for **Edge Deployment paradigms**: computational inferences run close to the data source (the inspector's device or proxy endpoint) rather than relying on heavy, distant cloud processing.
