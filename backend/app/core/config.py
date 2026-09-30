"""Application configuration."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings. """
    
    app_name: str = "Automated Data Cleaning & Quality Management System"
    app_env: str = "development"

    database_url: str  

    api_base_url: str = "http://localhost:8000"
    max_upload_size_mb: int = 20
    upload_dir: str = "data/uploads"
    output_dir: str = "data/outputs"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore", 
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (the .env file is read only once)."""
    return Settings()