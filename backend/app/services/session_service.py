"""Creation and retrieval of processing sessions."""

import uuid
from pathlib import Path

import pandas as pd
from sqlalchemy import insert
from sqlalchemy.orm import Session

from backend.app.models import DatasetRecord, ProcessingSession


def create_session_from_upload(
    db: Session,
    *,
    original_filename: str,
    file_type: str,
    content: bytes,
    dataframe: pd.DataFrame,
    upload_dir: str,
) -> ProcessingSession:
    """Save the original file and store the session and all its rows atomically.

    The file is stored under a generated name ({session_id}.{ext}), never the
    user-supplied name, to prevent path-traversal attacks. If the database
    write fails, the saved file is removed so no orphaned data remains.
    """
    session_id = uuid.uuid4()
    stored_filename = f"{session_id}.{file_type}"
    directory = Path(upload_dir)
    directory.mkdir(parents=True, exist_ok=True)
    file_path = directory / stored_filename
    file_path.write_bytes(content)  # original, byte-for-byte

    try:
        processing_session = ProcessingSession(
            id=session_id,
            original_filename=Path(original_filename).name[:255],
            stored_filename=stored_filename,
            file_type=file_type,
            file_size_bytes=len(content),
            row_count=len(dataframe),
            column_count=len(dataframe.columns),
            columns=list(dataframe.columns),
        )
        db.add(processing_session)
        db.flush()  # send the session INSERT so records can reference it

        records = [
            {"session_id": session_id, "row_number": number, "original_data": row}
            for number, row in enumerate(dataframe.to_dict(orient="records"), start=1)
        ]
        db.execute(insert(DatasetRecord), records)  # bulk insert
        db.commit()
    except Exception:
        db.rollback()
        file_path.unlink(missing_ok=True)
        raise

    db.refresh(processing_session)
    return processing_session


def get_session(db: Session, session_id: uuid.UUID) -> ProcessingSession | None:
    """Return a processing session by ID, or None if it does not exist."""
    return db.get(ProcessingSession, session_id)