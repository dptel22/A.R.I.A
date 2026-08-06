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
from aria.api.routes.intake import router as intake_router
from aria.api.routes.segments import router as segments_router
from aria.db.schema import init_db

load_dotenv()

log: logging.Logger = logging.getLogger(__name__)

_MODEL_PATH: str = os.environ.get("ARIA_MODEL_PATH", "./models/aria_stage1.pt")
_UPLOAD_ROOT: str = os.environ.get("ARIA_UPLOAD_DIR", "./runtime/uploads")
_DB_PATH: str = os.environ.get("ARIA_DB_PATH", "./runtime/db/aria.db")
_YOLO_CONFIG_DIR: str = os.environ.get("YOLO_CONFIG_DIR", "./runtime/ultralytics")
_ALLOWED_ORIGINS: list[str] = [
    o.strip() for o in os.environ.get(
        "ARIA_ALLOWED_ORIGINS",
        "http://localhost:8501,http://localhost:3000,http://localhost:5173",
    ).split(",") if o.strip()
]

os.makedirs(_UPLOAD_ROOT, exist_ok=True)
os.makedirs(os.path.dirname(_DB_PATH) or ".", exist_ok=True)
os.makedirs(_YOLO_CONFIG_DIR, exist_ok=True)
os.environ.setdefault("YOLO_CONFIG_DIR", _YOLO_CONFIG_DIR)


def _model_info(*, loaded: bool, error: str | None = None, model=None) -> dict[str, object]:
    path = os.path.abspath(_MODEL_PATH)
    info: dict[str, object] = {
        "loaded": loaded,
        "path": path,
        "exists": os.path.exists(_MODEL_PATH),
        "filename": os.path.basename(_MODEL_PATH),
        "error": error,
    }
    if os.path.exists(_MODEL_PATH):
        info["size_bytes"] = os.path.getsize(_MODEL_PATH)
    if model is not None:
        info["names"] = getattr(model, "names", None)
    return info


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load and warm up the YOLO model before accepting requests."""
    init_db(_DB_PATH)
    model = None
    model_info = _model_info(loaded=False)
    if os.path.exists(_MODEL_PATH):
        try:
            from ultralytics import YOLO

            log.info("Loading YOLO model from %s ...", _MODEL_PATH)
            model = YOLO(_MODEL_PATH)

            # Warm up with the same preprocessed path real requests use, so the
            # first request doesn't pay letterbox + CLAHE cold-start.
            from aria.inference.preprocess import preprocess
            dummy = preprocess(np.zeros((640, 640, 3), dtype=np.uint8), color_order="bgr")
            model.predict(source=dummy, conf=0.25, verbose=False)
            model_info = _model_info(loaded=True, model=model)
            log.info(
                "Model loaded and warmed up. path=%s size=%s names=%s",
                model_info["path"],
                model_info.get("size_bytes"),
                model_info.get("names"),
            )
        except Exception as exc:
            log.exception(
                "Failed to load YOLO model from %s. POST /detect will return 503.",
                _MODEL_PATH,
            )
            model = None
            model_info = _model_info(loaded=False, error=str(exc))
    else:
        log.warning(
            "Model file not found at %s. POST /detect will return 503. Other endpoints still work.",
            _MODEL_PATH,
        )

    app.state.model = model
    app.state.model_info = model_info
    yield
    app.state.model = None
    app.state.model_info = _model_info(loaded=False)
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
app.include_router(intake_router)
app.include_router(segments_router)
