"""Health-check endpoint used to confirm the API is running."""

from datetime import datetime, timezone

from fastapi import APIRouter

from backend.app.core.config import get_settings

router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check() -> dict:
    """Report basic service status.

    Returns:
        A dictionary with service status, name, environment and UTC timestamp.
    """
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.app_env,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }