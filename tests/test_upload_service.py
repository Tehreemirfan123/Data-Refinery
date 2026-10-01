"""Unit tests for upload validation and parsing."""

from io import BytesIO

import pandas as pd
import pytest

from backend.app.services.upload_service import FileValidationError, load_dataset

MAX_BYTES = 5 * 1024 * 1024

VALID_ROW = {
    "family_id": "FAM-000001",
    "full_name": "Ali Raza",
    "cnic": "3520112345671",
    "phone": "03001234567",
    "district": "بہاولپور",
    "address": "House 23, Street 4, Yazman, District Bahawalpur, UC Chak 4",
}


def make_csv(rows: list[dict]) -> bytes:
    return pd.DataFrame(rows).to_csv(index=False).encode("utf-8-sig")


def make_xlsx(rows: list[dict]) -> bytes:
    buffer = BytesIO()
    pd.DataFrame(rows).to_excel(buffer, index=False)
    return buffer.getvalue()


def test_valid_csv_is_parsed_as_text() -> None:
    dataframe, file_type = load_dataset("data.csv", make_csv([VALID_ROW]), MAX_BYTES)

    assert file_type == "csv"
    assert len(dataframe) == 1
    assert dataframe.loc[0, "phone"] == "03001234567"   # leading zero kept
    assert dataframe.loc[0, "cnic"] == "3520112345671"  # not a number
    assert dataframe.loc[0, "district"] == "بہاولپور"   # Urdu preserved


def test_valid_xlsx_is_parsed() -> None:
    dataframe, file_type = load_dataset("data.xlsx", make_xlsx([VALID_ROW]), MAX_BYTES)

    assert file_type == "xlsx"
    assert dataframe.loc[0, "phone"] == "03001234567"


def test_literal_na_text_is_not_converted_to_missing() -> None:
    row = {**VALID_ROW, "address": "NA"}
    dataframe, _ = load_dataset("data.csv", make_csv([row]), MAX_BYTES)

    assert dataframe.loc[0, "address"] == "NA"


def test_headers_are_normalized() -> None:
    row = {" Full Name ": "Ali", **{k: v for k, v in VALID_ROW.items() if k != "full_name"}}
    dataframe, _ = load_dataset("data.csv", make_csv([row]), MAX_BYTES)

    assert "full_name" in dataframe.columns


@pytest.mark.parametrize("filename", ["data.txt", "data.pdf", "data", "data.xls"])
def test_unsupported_extensions_are_rejected(filename: str) -> None:
    with pytest.raises(FileValidationError, match="Unsupported file type"):
        load_dataset(filename, make_csv([VALID_ROW]), MAX_BYTES)


def test_empty_file_is_rejected() -> None:
    with pytest.raises(FileValidationError, match="empty"):
        load_dataset("data.csv", b"", MAX_BYTES)


def test_header_only_file_is_rejected() -> None:
    header_only = ",".join(VALID_ROW.keys()).encode("utf-8")
    with pytest.raises(FileValidationError, match="no data rows"):
        load_dataset("data.csv", header_only, MAX_BYTES)


def test_missing_required_column_is_reported() -> None:
    row = {k: v for k, v in VALID_ROW.items() if k != "cnic"}
    with pytest.raises(FileValidationError, match="cnic"):
        load_dataset("data.csv", make_csv([row]), MAX_BYTES)


def test_file_over_size_limit_is_rejected() -> None:
    with pytest.raises(FileValidationError, match="limit"):
        load_dataset("data.csv", make_csv([VALID_ROW]), max_bytes=10)


def test_fake_excel_file_is_rejected() -> None:
    with pytest.raises(FileValidationError, match="could not be read"):
        load_dataset("data.xlsx", b"this is not an excel file", MAX_BYTES)