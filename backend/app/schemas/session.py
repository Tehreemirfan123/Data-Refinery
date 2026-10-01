"""API response schemas for processing sessions."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from backend.app.models.enums import SessionStatus


class SessionSummary(BaseModel):
    """Public summary of a processing session (no file paths exposed)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_filename: str
    file_type: str
    file_size_bytes: int
    row_count: int
    column_count: int
    columns: list[str]
    status: SessionStatus
    created_at: datetime