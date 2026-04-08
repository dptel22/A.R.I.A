from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
def health(request: Request) -> dict[str, object]:
    return {
        "status": "ok",
        "model_loaded": request.app.state.model is not None,
        "version": "1.0.0",
    }
