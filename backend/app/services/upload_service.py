"""Uploaded file validation and parsing.

Pure functions: no database or disk access, so they are easy to test.
All columns are read as text so identifiers (CNIC, phone) are never
reinterpreted as numbers.
"""

from io import BytesIO
from pathlib import Path

import pandas as pd

ALLOWED_EXTENSIONS = {".csv": "csv", ".xlsx": "xlsx"}
REQUIRED_COLUMNS = ("family_id", "full_name", "cnic", "phone", "district", "address")


class FileValidationError(ValueError):
    """An uploaded file cannot be accepted. The message is safe to show to users."""


def get_file_type(filename: str) -> str:
    """Return "csv" or "xlsx" based on the file extension."""
    suffix = Path(filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise FileValidationError(
            f"Unsupported file type '{suffix or 'none'}'. Please upload a .csv or .xlsx file."
        )
    return ALLOWED_EXTENSIONS[suffix]


def check_size(content: bytes, max_bytes: int) -> None:
    """Reject empty files and files above the configured size limit."""
    if not content:
        raise FileValidationError("The uploaded file is empty.")
    if len(content) > max_bytes:
        limit_mb = max_bytes // (1024 * 1024)
        raise FileValidationError(f"The file exceeds the {limit_mb} MB upload limit.")


def read_dataframe(content: bytes, file_type: str) -> pd.DataFrame:
    """Parse file bytes into a DataFrame with every value as text."""
    try:
        if file_type == "csv":
            return pd.read_csv(
                BytesIO(content), dtype=str, keep_default_na=False, encoding="utf-8-sig"
            )
        return pd.read_excel(
            BytesIO(content), dtype=str, keep_default_na=False, engine="openpyxl"
        )
    except pd.errors.EmptyDataError as exc:
        raise FileValidationError("The file has no header row or data.") from exc
    except UnicodeDecodeError as exc:
        raise FileValidationError("The CSV file must be saved with UTF-8 encoding.") from exc
    except Exception as exc:  # untrusted input: many library-specific error types possible
        raise FileValidationError(
            "The file could not be read. It may be corrupted or not a real CSV/Excel file."
        ) from exc


def normalize_headers(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Standardize column names (" Full Name " -> "full_name") and handle blank headers."""
    dataframe = dataframe.copy()
    dataframe.columns = [
        str(column).strip().lower().replace(" ", "_") for column in dataframe.columns
    ]

    unnamed = [column for column in dataframe.columns if column.startswith("unnamed:")]
    for column in unnamed:
        if (dataframe[column].str.strip() != "").any():
            raise FileValidationError(
                "A column containing data has no header. Please add a header name."
            )
    dataframe = dataframe.drop(columns=unnamed)

    if dataframe.columns.duplicated().any():
        duplicates = sorted(set(dataframe.columns[dataframe.columns.duplicated()]))
        raise FileValidationError(f"Duplicate column names found: {', '.join(duplicates)}.")

    return dataframe


def check_required_columns(dataframe: pd.DataFrame) -> None:
    """Ensure every column the pipeline depends on is present."""
    missing = [column for column in REQUIRED_COLUMNS if column not in dataframe.columns]
    if missing:
        raise FileValidationError(f"Missing required columns: {', '.join(missing)}.")


def load_dataset(filename: str, content: bytes, max_bytes: int) -> tuple[pd.DataFrame, str]:
    """Run every upload check and return the parsed DataFrame and its file type.

    Raises:
        FileValidationError: If any check fails.
    """
    file_type = get_file_type(filename)
    check_size(content, max_bytes)
    dataframe = normalize_headers(read_dataframe(content, file_type))
    check_required_columns(dataframe)
    if dataframe.empty:
        raise FileValidationError("The file has a header row but no data rows.")
    return dataframe, file_type