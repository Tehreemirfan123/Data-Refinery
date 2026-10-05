"""Tests for mobile phone cleaning and validation."""

import pytest

from backend.app.models.enums import FieldStatus
from backend.app.services.phone_cleaner import clean_phone, to_e164
from scripts.generate_messy_dataset import generate_dataset

# All numbers below are synthetic.

VARIANTS_OF_SAME_NUMBER = [
    "0300-1234567",
    "+92 300 1234567",
    "923001234567",
    "3001234567",               # leading zero lost
    "+92-3001234567",
    "(0300) 1234567",
    "0092 300 1234567",
    "  03001234567 ",
    "۰۳۰۰۱۲۳۴۵۶۷",              # Urdu digits
]


def test_standard_number_is_valid_and_unchanged() -> None:
    result = clean_phone("03001234567")

    assert result.status == FieldStatus.VALID
    assert result.cleaned == "03001234567"
    assert result.changed is False


@pytest.mark.parametrize("raw", VARIANTS_OF_SAME_NUMBER)
def test_recognized_formats_are_corrected(raw: str) -> None:
    result = clean_phone(raw)

    assert result.status == FieldStatus.CORRECTED
    assert result.cleaned == "03001234567"
    assert result.original == raw


def test_all_variants_produce_one_value_for_duplicate_detection() -> None:
    cleaned_values = {clean_phone(raw).cleaned for raw in VARIANTS_OF_SAME_NUMBER}

    assert cleaned_values == {"03001234567"}


@pytest.mark.parametrize("raw", [None, "", "   "])
def test_blank_values_are_missing(raw: str | None) -> None:
    assert clean_phone(raw).status == FieldStatus.MISSING


@pytest.mark.parametrize("raw, reason_fragment", [
    ("030012345", "9 digits"),           # too short
    ("030012345678", "12 digits"),       # too long
    ("042-1234567", "landline"),         # not a mobile
    ("0300-12A4567", "letters"),         # letter inside
    ("3.00123E+09", "scientific"),       # Excel corruption
])
def test_unrecoverable_values_are_invalid(raw: str, reason_fragment: str) -> None:
    result = clean_phone(raw)

    assert result.status == FieldStatus.INVALID
    assert result.cleaned is None
    assert result.suggestion is None
    assert reason_fragment in result.reason


@pytest.mark.parametrize("raw", [
    "3001234567.0",    # spreadsheet float with complete digits
    "0300+1234567",    # misplaced '+'
])
def test_uncertain_values_need_review_with_suggestion(raw: str) -> None:
    result = clean_phone(raw)

    assert result.status == FieldStatus.REVIEW_REQUIRED
    assert result.cleaned is None
    assert result.suggestion == "03001234567"


@pytest.mark.parametrize("raw, reason_fragment", [
    ("03000000000", "placeholder"),
    ("0390-1234567", "operator code"),
])
def test_implausible_values_are_suspicious(raw: str, reason_fragment: str) -> None:
    result = clean_phone(raw)

    assert result.status == FieldStatus.SUSPICIOUS
    assert result.cleaned is not None
    assert reason_fragment in result.reason


@pytest.mark.parametrize("raw", ["030012345", "0300+1234567", "3001234567.0"])
def test_reasons_never_contain_the_number(raw: str) -> None:
    assert "1234567" not in clean_phone(raw).reason
    assert "12345" not in clean_phone(raw).reason


@pytest.mark.parametrize("phone, expected", [
    ("03001234567", "+923001234567"),
    ("0300-1234567", None),     # not standardized: no conversion
    (None, None),
])
def test_to_e164(phone: str | None, expected: str | None) -> None:
    assert to_e164(phone) == expected


def test_cleaner_agrees_with_generator_answer_key() -> None:
    """Ground-truth check: every injected phone problem gets the right category."""
    dataset, answer_key = generate_dataset(2000, level="normal", seed=42)
    duplicate_tags = {"exact_duplicate", "near_duplicate", "cnic_conflict"}

    for raw, issues_text in zip(dataset["phone"], answer_key["injected_issues"]):
        issues = set(issues_text.split("; "))
        status = clean_phone(raw).status

        if "phone_missing" in issues:
            assert status == FieldStatus.MISSING
        elif "phone_invalid" in issues:
            assert status in {FieldStatus.INVALID, FieldStatus.REVIEW_REQUIRED}
        elif "phone_format_variation" in issues:
            assert status == FieldStatus.CORRECTED
        elif not issues & duplicate_tags:
            assert status == FieldStatus.VALID