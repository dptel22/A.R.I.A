"""
FastAPI entry point for A.R.I.A.

Run with:
    uvicorn aria.api.app:app --reload --port 8000
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

import numpy as np
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from aria.api.routes import api_router, health_router
from aria.db.schema import init_db

load_dotenv()

log: logging.Logger = logging.getLogger(__name__)

_MODEL_PATH: str = os.environ.get("ARIA_MODEL_PATH", "./models/aria_best_v1.pt")
_UPLOAD_ROOT: str = os.environ.get("ARIA_UPLOAD_DIR", "./runtime/uploads")
_DB_PATH: str = os.environ.get("ARIA_DB_PATH", "./runtime/db/aria.db")
_ALLOWED_ORIGINS: list[str] = [
    o.strip() for o in os.environ.get(
        "ARIA_ALLOWED_ORIGINS",
        "http://localhost:8501,http://localhost:3000,http://localhost:5173",
    ).split(",") if o.strip()
]

os.makedirs(_UPLOAD_ROOT, exist_ok=True)
os.makedirs(os.path.dirname(_DB_PATH) or ".", exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load and warm up the YOLO model before accepting requests."""
    init_db(_DB_PATH)
    model = None
    if os.path.exists(_MODEL_PATH):
        try:
            from ultralytics import YOLO

            log.info("Loading YOLO model from %s ...", _MODEL_PATH)
            model = YOLO(_MODEL_PATH)

            dummy = np.zeros((640, 640, 3), dtype=np.uint8)
            model.predict(source=dummy, conf=0.25, verbose=False)
            log.info("Model loaded and warmed up. Ready.")
        except Exception:
            log.exception(
                "Failed to load YOLO model from %s. POST /detect will return 503.",
                _MODEL_PATH,
            )
            model = None
    else:
        log.warning(
            "Model file not found at %s. POST /detect will return 503. Other endpoints still work.",
            _MODEL_PATH,
        )

    app.state.model = model
    yield
    app.state.model = None
    log.info("Model unloaded. Shutting down.")


app = FastAPI(
    title="A.R.I.A. â€” Automated Road Inspection & Accountability",
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
app.mount("/uploads", StaticFiles(directory=_UPLOAD_ROOT), name="uploads")
app.include_router(health_router)
app.include_router(api_router, prefix="/api/v1")
