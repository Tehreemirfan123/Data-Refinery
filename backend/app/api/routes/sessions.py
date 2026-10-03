"""Processing-session endpoints: upload a dataset and fetch session summaries."""

import uuid

from fastapi import APIRouter, Depends, File, Query, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from backend.app.core.config import Settings, get_settings
from backend.app.db.session import get_db
from backend.app.schemas.session import RecordPreview, SessionSummary
from backend.app.services.upload_service import FileValidationError, load_dataset
from backend.app.services.session_service import (
    create_session_from_upload,
    get_session,
    get_session_records,
)

router = APIRouter(prefix="/sessions", tags=["Sessions"])


@router.post("/upload", response_model=SessionSummary, status_code=status.HTTP_201_CREATED)
def upload_dataset(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Validate an uploaded CSV/XLSX file and create a processing session."""
    content = file.file.read()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024

    try:
        dataframe, file_type = load_dataset(file.filename or "", content, max_bytes)
    except FileValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return create_session_from_upload(
        db,
        original_filename=file.filename or "upload",
        file_type=file_type,
        content=content,
        dataframe=dataframe,
        upload_dir=settings.upload_dir,
    )


@router.get("/{session_id}", response_model=SessionSummary)
def read_session(session_id: uuid.UUID, db: Session = Depends(get_db)):
    """Return the summary of one processing session."""
    processing_session = get_session(db, session_id)
    if processing_session is None:
        raise HTTPException(status_code=404, detail="Processing session not found")
    return processing_session

@router.get("/{session_id}/records", response_model=list[RecordPreview])
def read_session_records(
    session_id: uuid.UUID,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Return a page of a session's records (original values)."""
    if get_session(db, session_id) is None:
        raise HTTPException(status_code=404, detail="Processing session not found")
    return get_session_records(db, session_id, limit=limit, offset=offset)