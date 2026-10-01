"""Tests for the synthetic messy data generator."""

import pandas as pd
import pytest

from scripts.generate_messy_dataset import OUTPUT_COLUMNS, generate_dataset


def _issue_set(answer_key: pd.DataFrame) -> set[str]:
    return set(answer_key["injected_issues"].str.split("; ").explode())


def test_row_count_and_columns() -> None:
    dataset, answer_key = generate_dataset(500, seed=1)

    assert len(dataset) == 500
    assert len(answer_key) == 500
    assert list(dataset.columns) == OUTPUT_COLUMNS


def test_same_seed_is_reproducible() -> None:
    first, _ = generate_dataset(300, seed=7)
    second, _ = generate_dataset(300, seed=7)

    pd.testing.assert_frame_equal(first, second)


def test_different_seeds_produce_different_data() -> None:
    first, _ = generate_dataset(300, seed=7)
    second, _ = generate_dataset(300, seed=8)

    assert not first.equals(second)


def test_messiness_increases_with_level() -> None:
    _, clean_key = generate_dataset(1000, level="clean", seed=3)
    _, high_key = generate_dataset(1000, level="high", seed=3)

    clean_problem_rows = (clean_key["injected_issues"] != "none").sum()
    high_problem_rows = (high_key["injected_issues"] != "none").sum()
    assert clean_problem_rows < high_problem_rows


def test_normal_level_injects_core_issue_types() -> None:
    _, answer_key = generate_dataset(2000, level="normal", seed=42)

    expected = {
        "cnic_format_variation", "cnic_invalid", "phone_format_variation",
        "district_variant", "exact_duplicate", "near_duplicate", "cnic_conflict",
    }
    assert expected <= _issue_set(answer_key)


def test_exact_duplicates_are_truly_identical_rows() -> None:
    dataset, answer_key = generate_dataset(2000, level="normal", seed=42)

    injected = (answer_key["injected_issues"] == "exact_duplicate").sum()
    assert dataset.duplicated().sum() >= injected


def test_identifiers_are_stored_as_text() -> None:
    dataset, _ = generate_dataset(200, seed=5)

    assert all(isinstance(value, str) for value in dataset["cnic"])
    assert all(isinstance(value, str) for value in dataset["phone"])


def test_invalid_level_raises() -> None:
    with pytest.raises(ValueError):
        generate_dataset(100, level="extreme")