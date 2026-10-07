"""Tests for name, text and gender cleaning."""

import pytest

from backend.app.models.enums import FieldStatus
from backend.app.services.text_cleaner import (
    clean_gender,
    clean_name,
    clean_text,
    name_match_key,
)
from scripts.generate_messy_dataset import generate_dataset

DUPLICATE_TAGS = {"exact_duplicate", "near_duplicate", "cnic_conflict"}

# --- clean_name ---------------------------------------------------------------


def test_clean_name_is_valid_and_unchanged() -> None:
    result = clean_name("Muhammad Ali Khan")

    assert result.status == FieldStatus.VALID
    assert result.changed is False


@pytest.mark.parametrize("raw, expected", [
    ("  ali  RAZA ", "Ali Raza"),
    ("AYESHA BIBI", "Ayesha Bibi"),
    ("fatima noor", "Fatima Noor"),
    ("abdul-rehman khan", "Abdul-Rehman Khan"),
    ("m. ali", "M. Ali"),
    ("Ali\u00a0Raza", "Ali Raza"),        # non-breaking space
    ("Ali \u200bRaza", "Ali Raza"),       # zero-width space
])
def test_formatting_problems_are_corrected(raw: str, expected: str) -> None:
    result = clean_name(raw)

    assert result.status == FieldStatus.CORRECTED
    assert result.cleaned == expected
    assert result.original == raw


@pytest.mark.parametrize("name", ["McDonald Khan", "Ali DeSouza"])
def test_deliberate_mixed_case_is_preserved(name: str) -> None:
    assert clean_name(name).status == FieldStatus.VALID


def test_spelling_is_never_changed() -> None:
    result = clean_name("Mohammad Ali")

    assert result.status == FieldStatus.VALID
    assert result.cleaned == "Mohammad Ali"   # not rewritten to "Muhammad"


def test_urdu_names_are_not_recased_only_spacing_fixed() -> None:
    assert clean_name("علی رضا").status == FieldStatus.VALID

    result = clean_name("  علی   رضا ")
    assert result.status == FieldStatus.CORRECTED
    assert result.cleaned == "علی رضا"


@pytest.mark.parametrize("raw", [None, "", "   ", "N/A", "na", "Unknown", "-"])
def test_blank_and_placeholder_names_are_missing(raw: str | None) -> None:
    result = clean_name(raw)

    assert result.status == FieldStatus.MISSING
    assert result.cleaned is None


@pytest.mark.parametrize("raw", ["Ali 2", "Ali@Raza", "123"])
def test_names_with_digits_or_symbols_need_review_and_are_untouched(raw: str) -> None:
    result = clean_name(raw)

    assert result.status == FieldStatus.REVIEW_REQUIRED
    assert result.cleaned is None
    assert result.suggestion is None


def test_field_name_is_recorded() -> None:
    assert clean_name("ali raza", field="father_name").field == "father_name"


# --- clean_text ---------------------------------------------------------------


def test_clean_text_normalizes_whitespace() -> None:
    result = clean_text("  House 23,   Street 4 ", field="address")

    assert result.status == FieldStatus.CORRECTED
    assert result.cleaned == "House 23, Street 4"


def test_clean_text_keeps_clean_values() -> None:
    assert clean_text("House 23, Street 4", field="address").status == FieldStatus.VALID


def test_clean_text_placeholder_is_missing() -> None:
    assert clean_text("NA", field="address").status == FieldStatus.MISSING


# --- clean_gender -------------------------------------------------------------


@pytest.mark.parametrize("raw, expected", [
    ("male", "Male"), ("M", "Male"), ("MALE", "Male"), ("مرد", "Male"),
    ("f", "Female"), ("FEMALE", "Female"), ("عورت", "Female"),
])
def test_gender_variants_are_mapped(raw: str, expected: str) -> None:
    result = clean_gender(raw)

    assert result.status == FieldStatus.CORRECTED
    assert result.cleaned == expected


def test_standard_gender_is_valid() -> None:
    assert clean_gender("Female").status == FieldStatus.VALID


def test_unrecognized_gender_is_invalid() -> None:
    result = clean_gender("X")

    assert result.status == FieldStatus.INVALID
    assert result.cleaned is None


@pytest.mark.parametrize("raw", ["", "Unknown"])
def test_blank_or_placeholder_gender_is_missing(raw: str) -> None:
    assert clean_gender(raw).status == FieldStatus.MISSING


# --- name_match_key -----------------------------------------------------------


@pytest.mark.parametrize("raw, expected", [
    ("Mohammad Ali", "muhammad ali"),
    ("MUHAMMED   ali", "muhammad ali"),
    ("Muhammad Ali", "muhammad ali"),
    ("Ahmad Raza", "ahmed raza"),
    ("M. Ali", "m ali"),            
    (None, None),
    ("N/A", None),
])
def test_name_match_key(raw: str | None, expected: str | None) -> None:
    assert name_match_key(raw) == expected


# --- ground truth -------------------------------------------------------------


def test_name_cleaning_agrees_with_answer_key() -> None:
    dataset, answer_key = generate_dataset(2000, level="normal", seed=42)

    for full_name, father_name, issues_text in zip(
        dataset["full_name"], dataset["father_name"], answer_key["injected_issues"]
    ):
        issues = set(issues_text.split("; "))
        if issues & DUPLICATE_TAGS:
            continue

        name_status = clean_name(full_name).status
        if "name_missing" in issues:
            assert name_status == FieldStatus.MISSING
        elif "name_formatting" in issues:
            assert name_status == FieldStatus.CORRECTED
        else:
            # includes name_spelling_variant: spelling alone is never "corrected"
            assert name_status == FieldStatus.VALID

        father_status = clean_name(father_name, field="father_name").status
        expected = (
            FieldStatus.CORRECTED if "father_name_formatting" in issues else FieldStatus.VALID
        )
        assert father_status == expected


def test_gender_cleaning_agrees_with_answer_key() -> None:
    dataset, answer_key = generate_dataset(2000, level="normal", seed=42)

    for gender, issues_text in zip(dataset["gender"], answer_key["injected_issues"]):
        issues = set(issues_text.split("; "))
        if issues & DUPLICATE_TAGS:
            continue

        status = clean_gender(gender).status
        if "gender_invalid" in issues:
            assert status in {FieldStatus.INVALID, FieldStatus.MISSING}
        elif "gender_formatting" in issues:
            assert status == FieldStatus.CORRECTED
        else:
            # includes gender_cnic_conflict: the value itself is fine;
            assert status == FieldStatus.VALID