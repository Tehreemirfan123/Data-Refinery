"""Tests for clean_record() and the cleaner evaluation."""

from backend.app.models.enums import FieldStatus
from backend.app.services.record_cleaner import clean_record
from scripts.evaluate_cleaners import EVALUATED_FIELDS, evaluate, expected_statuses
from scripts.generate_messy_dataset import generate_dataset

SAMPLE = {
    "family_id": "FAM-000001",
    "full_name": "  ali  RAZA ",
    "father_name": "Ahmed Raza",
    "gender": "m",
    "cnic": "3520112345671",
    "phone": "+92 300 1234567",
    "district": "BWP",
    "address": "House 23, Street 4, Yazman, District Bahawalpur, UC Chak 4",
}


def test_clean_record_returns_every_output_field() -> None:
    results = clean_record(SAMPLE)

    assert set(results) == {
        "cnic", "phone", "full_name", "father_name", "gender", "district",
        "address", "address_district", "tehsil", "union_council",
    }
    assert results["cnic"].cleaned == "35201-1234567-1"
    assert results["district"].cleaned == "Bahawalpur"
    assert results["tehsil"].cleaned == "Yazman"


def test_absent_optional_columns_are_missing_not_errors() -> None:
    record = {key: value for key, value in SAMPLE.items() if key not in {"father_name", "gender"}}

    results = clean_record(record)

    assert results["father_name"].status == FieldStatus.MISSING
    assert results["gender"].status == FieldStatus.MISSING


def test_duplicate_rows_have_no_field_expectations() -> None:
    assert expected_statuses({"near_duplicate"}) is None


def test_evaluation_on_normal_data_fully_agrees() -> None:
    dataset, answer_key = generate_dataset(1000, level="normal", seed=3)

    report = evaluate(dataset, answer_key)

    assert report.disagreements == []
    assert (report.agreement["agreement_%"] == 100).all()
    assert (report.distribution.sum(axis=1) == len(dataset)).all()
    assert list(report.distribution.index) == list(EVALUATED_FIELDS)