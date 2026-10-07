"""Measure the cleaners against the synthetic generator's answer key.

Usage (from project root):
    python -m scripts.evaluate_cleaners --rows 10000 --level normal --seed 42
    python -m scripts.evaluate_cleaners --rows 10000 --level high --report-dir data/outputs

Exits with status 1 if any field disagrees with the answer key.
Disagreement examples show row numbers and statuses only, never values.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from backend.app.models.enums import FieldStatus as S
from backend.app.services.record_cleaner import clean_record
from scripts.generate_messy_dataset import LEVEL_MULTIPLIERS, generate_dataset

DUPLICATE_TAGS = {"exact_duplicate", "near_duplicate", "cnic_conflict"}
EVALUATED_FIELDS = (
    "cnic", "phone", "full_name", "father_name", "gender",
    "district", "address_district", "tehsil",
)
STATUS_ORDER = [status.value for status in S]


@dataclass
class EvaluationReport:
    rows: int
    seconds: float
    distribution: pd.DataFrame          # field x status counts (all rows)
    agreement: pd.DataFrame             # field: checked, agreed, agreement_%
    disagreements: list[tuple[int, str, str, str]]  # (row, field, got, expected)

    @property
    def rows_per_second(self) -> float:
        return self.rows / self.seconds if self.seconds else float("inf")


def expected_statuses(issues: set[str]) -> dict[str, set[S]] | None:
    """Acceptable statuses per field for a row's injected issues (None = duplicate row)."""
    if issues & DUPLICATE_TAGS:
        return None

    def first_match(rules: list[tuple[str, set[S]]]) -> set[S]:
        for tag, statuses in rules:
            if tag in issues:
                return statuses
        return {S.VALID}

    address = {S.MISSING} if issues & {"address_missing", "address_vague"} else {S.VALID}
    return {
        "cnic": first_match([
            ("cnic_missing", {S.MISSING}),
            ("cnic_invalid", {S.INVALID, S.REVIEW_REQUIRED}),
            ("cnic_format_variation", {S.CORRECTED}),
        ]),
        "phone": first_match([
            ("phone_missing", {S.MISSING}),
            ("phone_invalid", {S.INVALID, S.REVIEW_REQUIRED}),
            ("phone_format_variation", {S.CORRECTED}),
        ]),
        "full_name": first_match([
            ("name_missing", {S.MISSING}),
            ("name_formatting", {S.CORRECTED}),
        ]),
        "father_name": first_match([("father_name_formatting", {S.CORRECTED})]),
        "gender": first_match([
            ("gender_invalid", {S.INVALID, S.MISSING}),
            ("gender_formatting", {S.CORRECTED}),
        ]),
        "district": first_match([
            ("district_missing", {S.MISSING}),
            ("district_typo", {S.REVIEW_REQUIRED}),
            ("district_variant", {S.CORRECTED}),
        ]),
        "address_district": address,
        "tehsil": address,
    }


def evaluate(
    dataset: pd.DataFrame, answer_key: pd.DataFrame, max_examples: int = 10
) -> EvaluationReport:
    """Clean every row and compare each field's status with the answer key."""
    counts = {field: Counter() for field in EVALUATED_FIELDS}
    checked: Counter = Counter()
    agreed: Counter = Counter()
    disagreements: list[tuple[int, str, str, str]] = []

    records = dataset.to_dict(orient="records")
    start = time.perf_counter()

    for row_number, record, issues_text in zip(
        answer_key["row_number"], records, answer_key["injected_issues"]
    ):
        results = clean_record(record)
        expected = expected_statuses(set(issues_text.split("; ")))

        for field in EVALUATED_FIELDS:
            status = results[field].status
            counts[field][status.value] += 1
            if expected is None:
                continue
            checked[field] += 1
            if status in expected[field]:
                agreed[field] += 1
            elif len(disagreements) < max_examples:
                allowed = "/".join(sorted(s.value for s in expected[field]))
                disagreements.append((int(row_number), field, status.value, allowed))

    seconds = time.perf_counter() - start

    distribution = (
        pd.DataFrame.from_dict({field: dict(c) for field, c in counts.items()}, orient="index")
        .reindex(index=list(EVALUATED_FIELDS), columns=STATUS_ORDER)
        .fillna(0)
        .astype(int)
    )
    agreement = pd.DataFrame(
        {
            "checked": [checked[field] for field in EVALUATED_FIELDS],
            "agreed": [agreed[field] for field in EVALUATED_FIELDS],
        },
        index=list(EVALUATED_FIELDS),
    )
    agreement["agreement_%"] = (100 * agreement["agreed"] / agreement["checked"]).round(2)

    return EvaluationReport(len(dataset), seconds, distribution, agreement, disagreements)


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate cleaners against the answer key.")
    parser.add_argument("--rows", type=int, default=10000)
    parser.add_argument("--level", choices=list(LEVEL_MULTIPLIERS), default="normal")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--report-dir", type=Path, default=None,
                        help="Optional folder to save the tables as CSV")
    args = parser.parse_args()

    dataset, answer_key = generate_dataset(args.rows, args.level, args.seed)
    report = evaluate(dataset, answer_key)

    print(f"Cleaned {report.rows:,} rows (level={args.level}, seed={args.seed}) "
          f"in {report.seconds:.2f}s ({report.rows_per_second:,.0f} rows/s)\n")
    print("Status distribution (all rows):")
    print(report.distribution.to_string(), "\n")
    print("Agreement with answer key (duplicate rows excluded):")
    print(report.agreement.to_string(), "\n")

    if report.disagreements:
        print("Disagreement examples (row, field, got, expected):")
        for example in report.disagreements:
            print("  ", example)
    else:
        print("No disagreements.")

    if args.report_dir:
        args.report_dir.mkdir(parents=True, exist_ok=True)
        stem = f"evaluation_{args.level}_{args.rows}"
        report.distribution.to_csv(args.report_dir / f"{stem}_distribution.csv")
        report.agreement.to_csv(args.report_dir / f"{stem}_agreement.csv")
        print(f"\nReports saved to {args.report_dir}")

    return 1 if report.disagreements else 0


if __name__ == "__main__":
    sys.exit(main())