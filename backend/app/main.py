"""FastAPI application entry point."""

from fastapi import FastAPI

from backend.app.api.routes import health
from backend.app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description=(
        "Demonstration system for profiling, cleaning, validating and reviewing "
        "messy synthetic Pakistani-style datasets. Synthetic data only."
    ),
    version="0.1.0",
)

app.include_router(health.router)