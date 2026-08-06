from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse

router = APIRouter()


@router.get("/")
def root():
    return RedirectResponse(url="/docs")


def _readiness(request: Request) -> bool:
    """A.R.I.A. is ready to accept detections only once the model has loaded."""
    return request.app.state.model is not None


def _health_payload(request: Request) -> dict[str, object]:
    model_info = getattr(request.app.state, "model_info", None) or {
        "loaded": request.app.state.model is not None,
    }
    ready = _readiness(request)
    return {
        "status": "ok",
        "model_loaded": ready,
        "ready": ready,
        "model": model_info,
        "version": "1.0.0",
    }


@router.get("/health")
def health(request: Request) -> dict[str, object]:
    """Liveness probe — always 200 while the process is up.

    ``ready``/``model_loaded`` honestly reflect whether the YOLO model has
    loaded; a fresh boot with a missing/broken model reports ``False`` here
    even though the process itself is alive.
    """
    return _health_payload(request)


@router.get("/ready")
def ready(request: Request) -> JSONResponse:
    """Readiness probe — 503 until the YOLO model is loaded."""
    payload = _health_payload(request)
    if not _readiness(request):
        payload["status"] = "not_ready"
        return JSONResponse(status_code=503, content=payload)
    return JSONResponse(status_code=200, content=payload)
