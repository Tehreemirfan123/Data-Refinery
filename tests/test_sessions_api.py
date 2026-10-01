"""API tests for dataset upload and session retrieval (uses the database)."""

import uuid
from io import BytesIO

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.app.core.config import Settings, get_settings
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.models import DatasetRecord

ROWS = [
    {"family_id": "FAM-000001", "full_name": "Ali Raza", "cnic": "3520112345671",
     "phone": "0300-1234567", "district": "BWP", "address": "House 23, Yazman"},
    {"family_id": "FAM-000001", "full_name": "  sana RAZA", "cnic": "",
     "phone": "+92 300 7654321", "district": "بہاولپور", "address": "House 23, Yazman"},
]


@pytest.fixture
def client(db_session, tmp_path):
    """TestClient using the rollback DB session and a temporary upload folder."""
    test_settings = Settings(
        database_url=get_settings().database_url, upload_dir=str(tmp_path)
    )
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_settings] = lambda: test_settings
    yield TestClient(app)
    app.dependency_overrides.clear()


def _csv_upload(rows: list[dict], filename: str = "synthetic.csv") -> dict:
    content = pd.DataFrame(rows).to_csv(index=False).encode("utf-8-sig")
    return {"file": (filename, BytesIO(content), "text/csv")}


def test_upload_creates_session_records_and_stored_file(client, db_session, tmp_path) -> None:
    response = client.post("/sessions/upload", files=_csv_upload(ROWS))

    assert response.status_code == 201
    body = response.json()
    assert body["row_count"] == 2
    assert body["status"] == "UPLOADED"
    assert "stored_filename" not in body  # internal detail not exposed

    session_id = uuid.UUID(body["id"])
    count = db_session.scalar(
        select(func.count()).select_from(DatasetRecord).where(DatasetRecord.session_id == session_id)
    )
    assert count == 2
    assert (tmp_path / f"{session_id}.csv").exists()  # original preserved


def test_messy_values_are_stored_unchanged(client, db_session) -> None:
    response = client.post("/sessions/upload", files=_csv_upload(ROWS))
    session_id = uuid.UUID(response.json()["id"])

    records = db_session.scalars(
        select(DatasetRecord)
        .where(DatasetRecord.session_id == session_id)
        .order_by(DatasetRecord.row_number)
    ).all()
    assert records[1].original_data["full_name"] == "  sana RAZA"
    assert records[1].original_data["cnic"] == ""


def test_invalid_upload_returns_422_and_creates_nothing(client, tmp_path) -> None:
    response = client.post("/sessions/upload", files=_csv_upload(ROWS, filename="data.txt"))

    assert response.status_code == 422
    assert "Unsupported file type" in response.json()["detail"]
    assert list(tmp_path.iterdir()) == []


def test_get_session_returns_summary(client) -> None:
    created = client.post("/sessions/upload", files=_csv_upload(ROWS)).json()

    response = client.get(f"/sessions/{created['id']}")

    assert response.status_code == 200
    assert response.json()["original_filename"] == "synthetic.csv"


def test_unknown_session_returns_404(client) -> None:
    response = client.get(f"/sessions/{uuid.uuid4()}")

    assert response.status_code == 404