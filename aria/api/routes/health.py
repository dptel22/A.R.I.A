from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
def health(request: Request) -> dict[str, object]:
    model_info = getattr(request.app.state, "model_info", None) or {
        "loaded": request.app.state.model is not None,
    }
    return {
        "status": "ok",
        "model_loaded": request.app.state.model is not None,
        "model": model_info,
        "version": "1.0.0",
    }
