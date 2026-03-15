"""
api/app.py — FastAPI entry point for A.R.I.A.

Run with:
    uvicorn api.app:app --reload --port 8000
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

import numpy as np
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

log: logging.Logger = logging.getLogger(__name__)

_MODEL_PATH: str = os.environ.get("ARIA_MODEL_PATH", "./aria_stage1.pt")
_ALLOWED_ORIGINS: list[str] = [
    o.strip() for o in os.environ.get(
        "ARIA_ALLOWED_ORIGINS", "http://localhost:8501"
    ).split(",") if o.strip()
]


# ---------------------------------------------------------------------------
# Lifespan — load YOLO once at startup, release on shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load and warm up the YOLO model before accepting requests."""
    model = None
    if os.path.exists(_MODEL_PATH):
        try:
            from ultralytics import YOLO
            log.info("Loading YOLO model from %s ...", _MODEL_PATH)
            model = YOLO(_MODEL_PATH)

            # Warm-up run — first inference is 3-5x slower due to CUDA kernel init
            dummy = np.zeros((640, 640, 3), dtype=np.uint8)
            model.predict(source=dummy, conf=0.25, verbose=False)
            log.info("Model loaded and warmed up. Ready.")
        except Exception:
            log.exception(
                "Failed to load YOLO model from %s. "
                "POST /detect will return 503.", _MODEL_PATH,
            )
            model = None
    else:
        log.warning(
            "Model file not found at %s. POST /detect will return 503. "
            "Other endpoints still work.",
            _MODEL_PATH,
        )

    app.state.model = model
    yield  # app is running
    app.state.model = None
    log.info("Model unloaded. Shutting down.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="A.R.I.A. — Automated Road Inspection & Accountability",
    version="1.0.0",
    description="Bengaluru road damage detection and enforcement API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health check (no auth required)
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {
        "status": "ok",
        "model_loaded": app.state.model is not None,
        "version": "1.0.0",
    }


# ---------------------------------------------------------------------------
# Mount routes
# ---------------------------------------------------------------------------

from api.routes import router  # noqa: E402  (must come after app definition)

app.include_router(router, prefix="/api/v1")
