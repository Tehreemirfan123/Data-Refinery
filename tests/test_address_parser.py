"""Tests for address parsing (district, tehsil, Union Council)."""

import pytest

from backend.app.models.enums import FieldStatus
from backend.app.services.address_parser import parse_address
from backend.app.services.normalization_service import normalize_district
from scripts.generate_messy_dataset import generate_dataset

DUPLICATE_TAGS = {"exact_duplicate", "near_duplicate", "cnic_conflict"}


@pytest.mark.parametrize("address, district, tehsil, union_council", [
    # proposal example
    ("House 23, Street 4, Yazman, District Bahawalpur, UC Chak 4", "Bahawalpur", "Yazman", "Chak 4"),
    # no commas, abbreviated prefix
    ("H# 12 St 4 Hasilpur Distt. Bahawalpur", "Bahawalpur", "Hasilpur", None),
    # no "District" label
    ("Mohalla Islampura, Jaranwala, Faisalabad", "Faisalabad", "Jaranwala", None),
    # Urdu district name
    ("House No. 7, UC 14, Tehsil Shujabad, ملتان", "Multan", "Shujabad", "UC 14"),
])
def test_generator_style_addresses(address, district, tehsil, union_council) -> None:
    parsed = parse_address(address)

    assert parsed.district.cleaned == district
    assert parsed.tehsil.cleaned == tehsil
    assert parsed.union_council.cleaned == union_council


def test_multi_word_tehsil_is_matched_whole() -> None:
    parsed = parse_address("House 3, Bahawalpur City, District Bahawalpur")

    assert parsed.tehsil.cleaned == "Bahawalpur City"
    assert parsed.district.cleaned == "Bahawalpur"


def test_district_inferred_from_tehsil_is_only_suggested() -> None:
    parsed = parse_address("House 3, Bahawalpur City")

    assert parsed.tehsil.status == FieldStatus.VALID
    assert parsed.district.status == FieldStatus.REVIEW_REQUIRED
    assert parsed.district.cleaned is None
    assert parsed.district.suggestion == "Bahawalpur"


@pytest.mark.parametrize("address, expected_tehsil", [
    ("Mohalla Model Colony, Burewala, Vehari", "Burewala"),
    ("Mohalla Model Colony, Vehari, Vehari", "Vehari"),
    ("House No. 2, Tehsil Vehari, وہاڑی", "Vehari"),
])
def test_vehari_district_and_tehsil_ambiguity(address: str, expected_tehsil: str) -> None:
    parsed = parse_address(address)

    assert parsed.district.cleaned == "Vehari"
    assert parsed.tehsil.cleaned == expected_tehsil


def test_tehsil_from_another_district_is_a_conflict() -> None:
    parsed = parse_address("House 5, Yazman, District Lahore")   

    assert parsed.district.status == FieldStatus.REVIEW_REQUIRED
    assert parsed.tehsil.status == FieldStatus.REVIEW_REQUIRED
    assert parsed.district.suggestion is None


def test_two_districts_need_review() -> None:
    parsed = parse_address("House 1, Lahore, Multan")

    assert parsed.district.status == FieldStatus.REVIEW_REQUIRED


def test_two_union_councils_need_review() -> None:
    parsed = parse_address("UC 3, UC 5, Yazman, District Bahawalpur")

    assert parsed.union_council.status == FieldStatus.REVIEW_REQUIRED


@pytest.mark.parametrize("address, expected", [
    ("UC 14, Yazman", "UC 14"),
    ("U.C. No. 05, Yazman", "UC 5"),
    ("union council chak 12, Yazman", "Chak 12"),
])
def test_union_council_formats(address: str, expected: str) -> None:
    assert parse_address(address).union_council.cleaned == expected


def test_arabic_keyboard_district_is_recognized() -> None:
    parsed = parse_address("Mohalla Islampura, Model Town, لاهور")

    assert parsed.district.cleaned == "Lahore"
    assert parsed.tehsil.cleaned == "Model Town"


@pytest.mark.parametrize("address", [None, "", "N/A", "Near Main Bazar"])
def test_missing_or_vague_addresses_yield_nothing(address: str | None) -> None:
    for result in parse_address(address).results():
        assert result.status == FieldStatus.MISSING
        assert result.cleaned is None


def test_extracted_fields_are_derived_values_for_the_audit_trail() -> None:
    parsed = parse_address("House 23, Street 4, Yazman, District Bahawalpur, UC Chak 4")

    for result in parsed.results():
        assert result.original is None
        assert result.changed is True


def test_address_parsing_agrees_with_generator() -> None:
    dataset, answer_key = generate_dataset(2000, level="normal", seed=42)

    for address, district, issues_text in zip(
        dataset["address"], dataset["district"], answer_key["injected_issues"]
    ):
        issues = set(issues_text.split("; "))
        if issues & DUPLICATE_TAGS:
            continue

        parsed = parse_address(address)
        if issues & {"address_missing", "address_vague"}:
            assert parsed.district.status == FieldStatus.MISSING
            assert parsed.tehsil.status == FieldStatus.MISSING
            continue

        assert parsed.district.status == FieldStatus.VALID
        assert parsed.tehsil.status == FieldStatus.VALID
        assert parsed.union_council.status in {FieldStatus.VALID, FieldStatus.MISSING}

        expected_district = normalize_district(district).cleaned
        if expected_district is not None:
            assert parsed.district.cleaned == expected_district