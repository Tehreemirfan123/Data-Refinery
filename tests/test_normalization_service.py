"""Tests for Urdu/English district normalization."""

import pytest

from backend.app.models.enums import FieldStatus
from backend.app.services.normalization_service import (
    build_district_index,
    location_key,
    normalize_district,
)
from scripts.generate_messy_dataset import generate_dataset

DUPLICATE_TAGS = {"exact_duplicate", "near_duplicate", "cnic_conflict"}


def test_standard_district_is_valid() -> None:
    result = normalize_district("Bahawalpur")

    assert result.status == FieldStatus.VALID
    assert result.changed is False


@pytest.mark.parametrize("raw, expected", [
    ("بہاولپور", "Bahawalpur"),          # Urdu script
    ("Bahawal Pur", "Bahawalpur"),       # spacing
    ("BWP", "Bahawalpur"),               # abbreviation
    ("bwp", "Bahawalpur"),
    ("BAHAWALPUR", "Bahawalpur"),        # case
    ("  bahawalpur ", "Bahawalpur"),     # whitespace
    ("District Bahawalpur", "Bahawalpur"),
    ("Distt. Bahawalpur", "Bahawalpur"),
    ("ضلع بہاولپور", "Bahawalpur"),      # Urdu "district" prefix
    ("Lyallpur", "Faisalabad"),          # historical name
    ("FSD", "Faisalabad"),
    ("Faisal Abad", "Faisalabad"),
    ("فیصل آباد", "Faisalabad"),
    ("LHR", "Lahore"),
    ("لاہور", "Lahore"),
])
def test_known_spellings_are_corrected(raw: str, expected: str) -> None:
    result = normalize_district(raw)

    assert result.status == FieldStatus.CORRECTED
    assert result.cleaned == expected
    assert result.original == raw


@pytest.mark.parametrize("raw, expected", [
    ("بهاولپور", "Bahawalpur"),      # Arabic heh instead of Urdu heh
    ("لاهور", "Lahore"),
    ("فيصل آباد", "Faisalabad"),     # Arabic yeh instead of Urdu yeh
])
def test_arabic_keyboard_letter_forms_are_recognized(raw: str, expected: str) -> None:
    result = normalize_district(raw)

    assert result.status == FieldStatus.CORRECTED
    assert result.cleaned == expected


@pytest.mark.parametrize("raw, expected_suggestion", [
    ("Bahwalpur", "Bahawalpur"),
    ("Lhore", "Lahore"),
])
def test_typos_get_a_suggestion_but_are_not_applied(raw: str, expected_suggestion: str) -> None:
    result = normalize_district(raw)

    assert result.status == FieldStatus.REVIEW_REQUIRED
    assert result.cleaned is None                 
    assert result.suggestion == expected_suggestion


@pytest.mark.parametrize("raw", ["Karachi", "Atlantis"])
def test_unknown_districts_need_review_without_suggestion(raw: str) -> None:
    result = normalize_district(raw)

    assert result.status == FieldStatus.REVIEW_REQUIRED
    assert result.suggestion is None
    assert "not found" in result.reason


@pytest.mark.parametrize("raw", [None, "", "N/A"])
def test_blank_and_placeholder_districts_are_missing(raw: str | None) -> None:
    assert normalize_district(raw).status == FieldStatus.MISSING


@pytest.mark.parametrize("raw, expected", [
    ("Bahawal Pur", "bahawalpur"),
    ("District Lahore", "lahore"),
    ("بهاولپور", location_key("بہاولپور")),
])
def test_location_key(raw: str, expected: str) -> None:
    assert location_key(raw) == expected


def test_conflicting_reference_data_is_rejected() -> None:
    broken = [
        {"name": "Alpha", "urdu": "الفا", "variants": ["XYZ"]},
        {"name": "Beta", "urdu": "بیٹا", "variants": ["xyz"]},   
    ]

    with pytest.raises(ValueError, match="conflict"):
        build_district_index(broken)


def test_district_normalization_agrees_with_answer_key() -> None:
    dataset, answer_key = generate_dataset(2000, level="normal", seed=42)

    for district, issues_text in zip(dataset["district"], answer_key["injected_issues"]):
        issues = set(issues_text.split("; "))
        if issues & DUPLICATE_TAGS:
            continue

        result = normalize_district(district)
        if "district_missing" in issues:
            assert result.status == FieldStatus.MISSING
        elif "district_typo" in issues:
            assert result.status == FieldStatus.REVIEW_REQUIRED
            assert result.suggestion is not None       
        elif "district_variant" in issues:
            assert result.status == FieldStatus.CORRECTED
        else:
            assert result.status == FieldStatus.VALID