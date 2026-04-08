from fastapi import APIRouter

from aria.api.routes.health import router as health_router
from aria.api.routes.inspections import router as inspections_router
from aria.api.routes.notices import router as notices_router

api_router = APIRouter()
api_router.include_router(inspections_router)
api_router.include_router(notices_router)

__all__ = ["api_router", "health_router"]
