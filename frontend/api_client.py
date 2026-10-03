"""HTTP client for the DataRefinery backend API.

The Streamlit UI talks to the backend only through these functions, never by
importing backend code, so the frontend and backend can run separately.
"""

import os
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
DEFAULT_TIMEOUT = 10   # seconds
UPLOAD_TIMEOUT = 120   # large files take longer


class ApiError(Exception):
    """A backend request failed. The message is safe to display to users."""


def _request(method: str, path: str, timeout: int = DEFAULT_TIMEOUT, **kwargs) -> Any:
    """Send a request and return parsed JSON, converting failures into ApiError."""
    try:
        response = requests.request(method, f"{API_BASE_URL}{path}", timeout=timeout, **kwargs)
    except requests.ConnectionError as exc:
        raise ApiError(
            "Cannot reach the backend API. Is the FastAPI server running?"
        ) from exc
    except requests.Timeout as exc:
        raise ApiError("The backend took too long to respond.") from exc

    if not response.ok:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        raise ApiError(f"{detail} (HTTP {response.status_code})")

    return response.json()


def get_health() -> dict:
    return _request("GET", "/health")


def upload_dataset(filename: str, content: bytes) -> dict:
    files = {"file": (filename, content)}
    return _request("POST", "/sessions/upload", timeout=UPLOAD_TIMEOUT, files=files)


def get_session(session_id: str) -> dict:
    return _request("GET", f"/sessions/{session_id}")


def get_session_records(session_id: str, limit: int = 20) -> list[dict]:
    return _request("GET", f"/sessions/{session_id}/records", params={"limit": limit})