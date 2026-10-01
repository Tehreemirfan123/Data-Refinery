"""Tests for ProcessingSession and DatasetRecord models."""

from sqlalchemy import select
from backend.app.models import DatasetRecord, ProcessingSession, SessionStatus


def _make_session() -> ProcessingSession:
    return ProcessingSession(
        original_filename="synthetic_messy.csv",
        stored_filename="abc123.csv",
        file_type="csv",
        file_size_bytes=2048,
        row_count=2,
        column_count=3,
        columns=["name", "cnic", "district"],
    )


def test_session_gets_uuid_and_default_status(db_session) -> None:
    session_obj = _make_session()
    db_session.add(session_obj)
    db_session.flush()

    assert session_obj.id is not None
    assert session_obj.status == SessionStatus.UPLOADED


def test_records_are_linked_and_preserve_original_data(db_session) -> None:
    session_obj = _make_session()
    original = {"name": "  ali  RAZA ", "cnic": "3520112345671", "district": "بہاولپور"}
    session_obj.records.append(DatasetRecord(row_number=1, original_data=original))
    db_session.add(session_obj)
    db_session.flush()

    stored = db_session.scalars(
        select(DatasetRecord).where(DatasetRecord.session_id == session_obj.id)
    ).one()

    assert stored.original_data == original       # messy values stored exactly
    assert stored.original_data["district"] == "بہاولپور"  # Urdu preserved
    assert stored.cleaned_data is None
    assert stored.status is None


def test_deleting_session_deletes_its_records(db_session) -> None:
    session_obj = _make_session()
    session_obj.records.append(DatasetRecord(row_number=1, original_data={"a": 1}))
    db_session.add(session_obj)
    db_session.flush()

    db_session.delete(session_obj)
    db_session.flush()

    assert db_session.scalars(select(DatasetRecord)).all() == []