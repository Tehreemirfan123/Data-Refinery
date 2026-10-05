"""Tests for CNIC cleaning and validation."""

import pytest

from backend.app.models.enums import FieldStatus
from backend.app.services.cnic_cleaner import clean_cnic, gender_from_cnic
from scripts.generate_messy_dataset import generate_dataset

# All values below are synthetic.


def test_standard_cnic_is_valid_and_unchanged() -> None:
    result = clean_cnic("35201-1234567-1")

    assert result.status == FieldStatus.VALID
    assert result.cleaned == "35201-1234567-1"
    assert result.changed is False


@pytest.mark.parametrize("raw", [
    "3520112345671",            # no separators
    "35201 1234567 1",          # spaces
    "35201.1234567.1",          # dots
    "  35201-1234567-1  ",      # surrounding whitespace
    "35201-12345671",           # partial dashes
    "۳۵۲۰۱-۱۲۳۴۵۶۷-۱",          # Urdu digits
])
def test_known_formats_are_corrected(raw: str) -> None:
    result = clean_cnic(raw)

    assert result.status == FieldStatus.CORRECTED
    assert result.cleaned == "35201-1234567-1"
    assert result.changed is True
    assert result.original == raw  # original preserved


def test_dotted_cnic_ending_in_zero_is_corrected_not_treated_as_float() -> None:
    # Regression test: the case found by the SQL check.
    result = clean_cnic("35202.7654321.0")

    assert result.status == FieldStatus.CORRECTED
    assert result.cleaned == "35202-7654321-0"


def test_value_found_during_day1_inspection_is_corrected() -> None:
    result = clean_cnic("38338.4151809.5")

    assert result.cleaned == "38338-4151809-5"


@pytest.mark.parametrize("raw", [None, "", "   "])
def test_blank_values_are_missing(raw: str | None) -> None:
    result = clean_cnic(raw)

    assert result.status == FieldStatus.MISSING
    assert result.cleaned is None


@pytest.mark.parametrize("raw, reason_fragment", [
    ("35201-123456-1", "12 digits"),            # missing digit: never guessed
    ("352011234567190", "15 digits"),           # extra digits
    ("352011O345671", "letters are never"),     # letter O, not assumed to be 0
    ("3.52011E+12", "scientific notation"),     # Excel corruption
    ("3.52011e+12", "scientific notation"),
    ("352011234567.0", "12 digits"),            # 12-digit spreadsheet float
])
def test_unrecoverable_values_are_invalid(raw: str, reason_fragment: str) -> None:
    result = clean_cnic(raw)

    assert result.status == FieldStatus.INVALID
    assert result.cleaned is None
    assert result.suggestion is None
    assert reason_fragment in result.reason


@pytest.mark.parametrize("raw", [
    "3520-11234567-1",         # 13 digits, unusual separator layout
    "3520112345671.0",         # 13-digit spreadsheet float
])
def test_uncertain_values_need_review_with_suggestion(raw: str) -> None:
    result = clean_cnic(raw)

    assert result.status == FieldStatus.REVIEW_REQUIRED
    assert result.cleaned is None              # NOT applied automatically
    assert result.suggestion == "35201-1234567-1"
    assert result.changed is False


@pytest.mark.parametrize("raw, reason_fragment", [
    ("11111-1111111-1", "placeholder"),
    ("12345-1234567-1", "placeholder"),
    ("95201-1234567-1", "province-code"),
])
def test_implausible_values_are_suspicious(raw: str, reason_fragment: str) -> None:
    result = clean_cnic(raw)

    assert result.status == FieldStatus.SUSPICIOUS
    assert result.cleaned is not None
    assert reason_fragment in result.reason


@pytest.mark.parametrize("raw", ["35201-123456-1", "3520-11234567-1", "352011O345671"])
def test_reasons_never_contain_the_identifier(raw: str) -> None:
    result = clean_cnic(raw)

    assert "123456" not in result.reason


@pytest.mark.parametrize("cnic, expected", [
    ("35201-1234567-1", "Male"),
    ("35201-1234567-2", "Female"),
    ("35202-7654321-0", "Female"),
    ("3520112345671", None),      # non-standard format: no inference
    (None, None),
])
def test_gender_from_cnic(cnic: str | None, expected: str | None) -> None:
    assert gender_from_cnic(cnic) == expected


def test_cleaner_agrees_with_generator_answer_key() -> None:
    """Ground-truth check: every injected CNIC problem gets the right category."""
    dataset, answer_key = generate_dataset(2000, level="normal", seed=42)
    duplicate_tags = {"exact_duplicate", "near_duplicate", "cnic_conflict"}

    for raw, issues_text in zip(dataset["cnic"], answer_key["injected_issues"]):
        issues = set(issues_text.split("; "))
        status = clean_cnic(raw).status

        if "cnic_missing" in issues:
            assert status == FieldStatus.MISSING
        elif "cnic_invalid" in issues:
            assert status in {FieldStatus.INVALID, FieldStatus.REVIEW_REQUIRED}
        elif "cnic_format_variation" in issues:
            assert status == FieldStatus.CORRECTED
        elif not issues & duplicate_tags:
            assert status == FieldStatus.VALID