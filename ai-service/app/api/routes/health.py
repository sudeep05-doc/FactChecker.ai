"""Service health endpoint."""

from fastapi import APIRouter

from app.config.settings import get_settings
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service="factchecker-ai",
        version=settings.app_version,
    )
