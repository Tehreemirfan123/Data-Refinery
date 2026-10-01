"""Health-check endpoint used to confirm the API is running."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from datetime import datetime, timezone
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

@router.get("/health/db")
def database_health_check(db: Session = Depends(get_db)) -> dict:
    """Confirm the API can reach PostgreSQL."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        # Do not return the raw error: it may contain connection details.
        raise HTTPException(status_code=503, detail="Database unavailable")
    return {"status": "ok", "database": "reachable"}