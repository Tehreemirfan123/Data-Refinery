"""Generate a synthetic, deliberately messy Pakistani dataset.

Synthetic Data Generator.

Every value is randomly generated. Names, CNICs, phone numbers, family IDs
and addresses are combined at random and are not linked to any real person.

The generator also writes an "answer key" recording which problems were
injected into each row, so later stages can be measured against ground truth.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import pandas as pd

LOCATIONS_FILE = Path("reference_data/locations.json")
DEFAULT_OUTPUT_DIR = Path("data/synthetic")

OUTPUT_COLUMNS = [
    "record_id", "family_id", "full_name", "father_name", "gender",
    "cnic", "phone", "district", "address", "source_system",
]

# --- Synthetic vocabularies -------------------------------------------------

MALE_FIRST_NAMES = [
    "Ahmed", "Ali", "Usman", "Bilal", "Hamza", "Imran", "Asad", "Faisal",
    "Zeeshan", "Kamran", "Tariq", "Naveed", "Adnan", "Waqas", "Hussain",
]
FEMALE_FIRST_NAMES = [
    "Ayesha", "Fatima", "Sana", "Maryam", "Hina", "Rabia", "Zainab", "Saima",
    "Nadia", "Amna", "Sadia", "Kiran", "Iqra", "Mehwish", "Asma",
]
LAST_NAMES = [
    "Khan", "Ahmed", "Hussain", "Iqbal", "Akhtar", "Raza", "Mahmood", "Javed",
    "Anwar", "Rafiq", "Saleem", "Nadeem", "Latif", "Haider", "Ali",
]
# Spelling variations that occur when names are typed by different people.
SPELLING_VARIANTS = {
    "Muhammad": ["Mohammad", "Muhammed", "Mohd", "M."],
    "Ahmed": ["Ahmad"],
    "Hussain": ["Hussein", "Husain"],
    "Ayesha": ["Aisha", "Aysha"],
    "Fatima": ["Fatma"],
    "Usman": ["Osman"],
}
MOHALLAS = ["Islampura", "Model Colony", "Satellite Town", "Shadman Colony", "Iqbal Colony"]
VAGUE_ADDRESSES = ["Near Main Bazar", "Near Jamia Masjid", "Opposite Govt School", "Village area"]
MOBILE_PREFIXES = [
    "0300", "0301", "0302", "0303", "0305", "0306", "0307", "0308", "0310",
    "0312", "0313", "0315", "0321", "0322", "0331", "0333", "0334", "0336",
    "0345", "0346", "0347",
]
SOURCE_SYSTEMS = ["Manual Excel", "Mobile App", "Legacy System", "Web Portal"]
GENDER_NOISE = {"Male": ["M", "male", "MALE", "m"], "Female": ["F", "female", "FEMALE", "f"]}

# --- Messiness configuration ------------------------------------------------

BASE_RATES = {
    "cnic_missing": 0.03, "cnic_invalid": 0.04, "cnic_format": 0.45,
    "phone_missing": 0.05, "phone_invalid": 0.04, "phone_format": 0.55,
    "name_missing": 0.01, "name_spelling": 0.12, "name_noise": 0.30,
    "gender_invalid": 0.02, "gender_conflict": 0.02, "gender_noise": 0.25,
    "district_missing": 0.04, "district_typo": 0.03, "district_variant": 0.35,
    "address_missing": 0.02, "address_vague": 0.04,
    "exact_duplicate": 0.03, "near_duplicate": 0.03, "cnic_conflict": 0.01,
}
LEVEL_MULTIPLIERS = {"clean": 0.15, "normal": 1.0, "high": 2.2}
MAX_RATE = 0.9


def build_rates(level: str) -> dict[str, float]:
    """Scale base problem rates by the chosen messiness level."""
    if level not in LEVEL_MULTIPLIERS:
        raise ValueError(f"Unknown level '{level}'. Use one of {list(LEVEL_MULTIPLIERS)}.")
    multiplier = LEVEL_MULTIPLIERS[level]
    return {name: min(rate * multiplier, MAX_RATE) for name, rate in BASE_RATES.items()}


def load_locations(path: Path = LOCATIONS_FILE) -> list[dict]:
    """Load district/tehsil reference data shared with the cleaning services."""
    with path.open(encoding="utf-8") as file:
        return json.load(file)["districts"]


# --- Clean value generators -------------------------------------------------

def _random_digits(rng: random.Random, count: int) -> str:
    return "".join(rng.choices("0123456789", k=count))


def _make_cnic(rng: random.Random, gender: str) -> str:
    """Synthetic CNIC in canonical form. Last digit: odd = male, even = female."""
    area = "3" + _random_digits(rng, 4)
    serial = _random_digits(rng, 7)
    check = rng.choice("13579" if gender == "Male" else "02468")
    return f"{area}-{serial}-{check}"


def _make_phone(rng: random.Random) -> str:
    """Synthetic mobile number in canonical 03XXXXXXXXX form."""
    return rng.choice(MOBILE_PREFIXES) + _random_digits(rng, 7)


def _make_name(rng: random.Random, gender: str, last_name: str | None = None) -> str:
    last = last_name or rng.choice(LAST_NAMES)
    if gender == "Male":
        first = rng.choice(MALE_FIRST_NAMES)
        if rng.random() < 0.25:
            first = f"Muhammad {first}"
    else:
        first = rng.choice(FEMALE_FIRST_NAMES)
    return f"{first} {last}"


def _make_address(rng: random.Random, district: dict, tehsil: str) -> str:
    house, street = rng.randint(1, 500), rng.randint(1, 40)
    uc = rng.choice([f"UC {rng.randint(1, 60)}", f"UC Chak {rng.randint(1, 200)}"])
    templates = [
        f"House {house}, Street {street}, {tehsil}, District {district['name']}, {uc}",
        f"H# {house} St {street} {tehsil} Distt. {district['name']}",
        f"Mohalla {rng.choice(MOHALLAS)}, {tehsil}, {district['name']}",
        f"House No. {house}, {uc}, Tehsil {tehsil}, {district['urdu']}",
    ]
    return rng.choice(templates)


def _make_family(rng: random.Random, family_number: int, locations: list[dict]) -> list[dict]:
    """Create a household whose members share family ID, address and often a phone."""
    district = rng.choice(locations)
    tehsil = rng.choice(district["tehsils"])
    address = _make_address(rng, district, tehsil)
    family_id = f"FAM-{family_number:06d}"
    surname = rng.choice(LAST_NAMES)
    head_phone = _make_phone(rng)

    def member(gender: str, name: str, father_name: str, phone: str) -> dict:
        return {
            "family_id": family_id,
            "full_name": name,
            "father_name": father_name,
            "gender": gender,
            "cnic": _make_cnic(rng, gender),
            "phone": phone,
            "district": district["name"],
            "address": address,
            "source_system": rng.choice(SOURCE_SYSTEMS),
        }

    head_name = _make_name(rng, "Male", surname)
    members = [member("Male", head_name, _make_name(rng, "Male", surname), head_phone)]

    if rng.random() < 0.8:  # spouse
        phone = _make_phone(rng) if rng.random() < 0.6 else head_phone
        members.append(member("Female", _make_name(rng, "Female"), _make_name(rng, "Male"), phone))

    for _ in range(rng.randint(0, 3)):  # adult children
        gender = rng.choice(["Male", "Female"])
        phone = _make_phone(rng) if rng.random() < 0.5 else head_phone
        members.append(member(gender, _make_name(rng, gender, surname), head_name, phone))

    return members


# --- Messiness ---------------------------------------------------------------

def _vary_cnic_format(rng: random.Random, cnic: str) -> str:
    """Same digits, different formatting (safely fixable later)."""
    d = cnic.replace("-", "")
    return rng.choice([
        d,
        f"{d[:5]} {d[5:12]} {d[12]}",
        f"{d[:5]}.{d[5:12]}.{d[12]}",
        f"  {cnic} ",
        f"{d[:5]}-{d[5:12]}{d[12]}",
    ])


def _corrupt_cnic(rng: random.Random, cnic: str) -> str:
    """Information is lost or wrong; must NOT be auto-corrected later."""
    d = cnic.replace("-", "")
    return rng.choice([
        f"{d[:5]}-{d[5:11]}-{d[12]}",     # a digit is missing (12 digits)
        d + rng.choice("0123456789"),       # an extra digit (14 digits)
        d[:6] + "O" + d[7:],                # letter O typed instead of a digit
        f"{d[0]}.{d[1:6]}E+12",             # Excel scientific notation: digits lost
    ])


def _vary_phone_format(rng: random.Random, phone: str) -> str:
    local = phone[1:]  # without the leading 0
    return rng.choice([
        f"{phone[:4]}-{phone[4:]}",
        f"+92 {local[:3]} {local[3:]}",
        f"92{local}",
        local,                               # leading zero dropped (e.g. by Excel)
        f"+92-{local}",
        f"({phone[:4]}) {phone[4:]}",
    ])


def _corrupt_phone(rng: random.Random, phone: str) -> str:
    return rng.choice([
        phone[:-2],                          # too short
        phone + rng.choice("0123456789"),    # too long
        f"042-{phone[4:]}",                  # landline format, not a mobile
    ])


def _noisy_text(rng: random.Random, text: str) -> str:
    return rng.choice([
        text.upper(), text.lower(), f"  {text}", text.replace(" ", "   "), f"{text} ",
    ])


def _spelling_variant(rng: random.Random, name: str) -> tuple[str, bool]:
    tokens = name.split()
    for index, token in enumerate(tokens):
        if token in SPELLING_VARIANTS:
            tokens[index] = rng.choice(SPELLING_VARIANTS[token])
            return " ".join(tokens), True
    return name, False


def _typo(rng: random.Random, word: str) -> str:
    """Drop one interior character, e.g. Bahawalpur -> Bahwalpur."""
    position = rng.randint(1, len(word) - 2)
    return word[:position] + word[position + 1:]


def _apply_messiness(
    rng: random.Random, clean: dict, rates: dict[str, float], districts: dict[str, dict]
) -> tuple[dict, list[str]]:
    """Return a messy copy of a clean record plus the list of injected issues."""
    record, issues = dict(clean), []

    # CNIC
    if rng.random() < rates["cnic_missing"]:
        record["cnic"] = ""
        issues.append("cnic_missing")
    elif rng.random() < rates["cnic_invalid"]:
        record["cnic"] = _corrupt_cnic(rng, clean["cnic"])
        issues.append("cnic_invalid")
    elif rng.random() < rates["cnic_format"]:
        record["cnic"] = _vary_cnic_format(rng, clean["cnic"])
        issues.append("cnic_format_variation")

    # Phone
    if rng.random() < rates["phone_missing"]:
        record["phone"] = ""
        issues.append("phone_missing")
    elif rng.random() < rates["phone_invalid"]:
        record["phone"] = _corrupt_phone(rng, clean["phone"])
        issues.append("phone_invalid")
    elif rng.random() < rates["phone_format"]:
        record["phone"] = _vary_phone_format(rng, clean["phone"])
        issues.append("phone_format_variation")

    # Names
    if rng.random() < rates["name_missing"]:
        record["full_name"] = ""
        issues.append("name_missing")
    else:
        if rng.random() < rates["name_spelling"]:
            record["full_name"], changed = _spelling_variant(rng, record["full_name"])
            if changed:
                issues.append("name_spelling_variant")
        if rng.random() < rates["name_noise"]:
            record["full_name"] = _noisy_text(rng, record["full_name"])
            issues.append("name_formatting")
    if rng.random() < rates["name_noise"]:
        record["father_name"] = _noisy_text(rng, record["father_name"])
        issues.append("father_name_formatting")

    # Gender
    if rng.random() < rates["gender_invalid"]:
        record["gender"] = rng.choice(["X", "Unknown", ""])
        issues.append("gender_invalid")
    elif rng.random() < rates["gender_conflict"]:
        record["gender"] = "Female" if clean["gender"] == "Male" else "Male"
        issues.append("gender_cnic_conflict")
    elif rng.random() < rates["gender_noise"]:
        record["gender"] = rng.choice(GENDER_NOISE[clean["gender"]])
        issues.append("gender_formatting")

    # District
    district = districts[clean["district"]]
    if rng.random() < rates["district_missing"]:
        record["district"] = ""
        issues.append("district_missing")
    elif rng.random() < rates["district_typo"]:
        record["district"] = _typo(rng, district["name"])
        issues.append("district_typo")
    elif rng.random() < rates["district_variant"]:
        record["district"] = rng.choice(district["variants"] + [district["urdu"]])
        issues.append("district_variant")

    # Address
    if rng.random() < rates["address_missing"]:
        record["address"] = ""
        issues.append("address_missing")
    elif rng.random() < rates["address_vague"]:
        record["address"] = rng.choice(VAGUE_ADDRESSES)
        issues.append("address_vague")

    return record, issues


def _make_near_duplicate(rng: random.Random, clean: dict, record_id: str) -> dict:
    """Same person re-entered from another source with different formatting."""
    record = dict(clean)
    record["record_id"] = record_id
    record["cnic"] = _vary_cnic_format(rng, clean["cnic"])
    record["phone"] = _vary_phone_format(rng, clean["phone"])
    record["full_name"] = _noisy_text(rng, _spelling_variant(rng, clean["full_name"])[0])
    record["source_system"] = rng.choice(SOURCE_SYSTEMS)
    return record


def _make_cnic_conflict(rng: random.Random, clean: dict, record_id: str) -> dict:
    """A different person recorded with the same CNIC: a conflict, not a duplicate."""
    record = dict(clean)
    record["record_id"] = record_id
    record["phone"] = _make_phone(rng)
    while record["full_name"] == clean["full_name"]:
        record["full_name"] = _make_name(rng, clean["gender"])
    return record


# --- Public API --------------------------------------------------------------

def generate_dataset(
    rows: int,
    level: str = "normal",
    seed: int = 42,
    locations: list[dict] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generate a messy dataset and its answer key.

    Args:
        rows: Total number of rows to produce (including duplicates).
        level: Messiness level: "clean", "normal" or "high".
        seed: Random seed; the same seed always produces the same data.
        locations: Optional district reference data (defaults to the JSON file).

    Returns:
        (dataset, answer_key) DataFrames with one answer-key row per dataset row.
    """
    if rows < 1:
        raise ValueError("rows must be at least 1")

    rng = random.Random(seed)
    rates = build_rates(level)
    locations = locations or load_locations()
    districts = {district["name"]: district for district in locations}

    n_exact = round(rows * rates["exact_duplicate"])
    n_near = round(rows * rates["near_duplicate"])
    n_conflict = round(rows * rates["cnic_conflict"])
    n_base = rows - n_exact - n_near - n_conflict

    # 1. Clean base records, built family by family.
    clean_records: list[dict] = []
    family_number = 1
    while len(clean_records) < n_base:
        clean_records.extend(_make_family(rng, family_number, locations))
        family_number += 1
    clean_records = clean_records[:n_base]
    for index, record in enumerate(clean_records, start=1):
        record["record_id"] = f"SRC-{index:06d}"

    # 2. Messiness.
    output = [_apply_messiness(rng, clean, rates, districts) for clean in clean_records]

    # 3. Duplicates and conflicts.
    next_id = n_base + 1
    for _ in range(n_exact):
        messy, _issues = output[rng.randrange(n_base)]
        output.append((dict(messy), ["exact_duplicate"]))
    for _ in range(n_near):
        clean = clean_records[rng.randrange(n_base)]
        output.append((_make_near_duplicate(rng, clean, f"SRC-{next_id:06d}"), ["near_duplicate"]))
        next_id += 1
    for _ in range(n_conflict):
        clean = clean_records[rng.randrange(n_base)]
        output.append((_make_cnic_conflict(rng, clean, f"SRC-{next_id:06d}"), ["cnic_conflict"]))
        next_id += 1

    # 4. Shuffle so duplicates are not grouped at the end.
    rng.shuffle(output)

    dataset = pd.DataFrame([record for record, _ in output], columns=OUTPUT_COLUMNS)
    answer_key = pd.DataFrame({
        "row_number": range(1, len(output) + 1),
        "record_id": dataset["record_id"],
        "injected_issues": ["; ".join(issues) if issues else "none" for _, issues in output],
    })
    return dataset, answer_key


def write_outputs(
    dataset: pd.DataFrame, answer_key: pd.DataFrame, output_dir: Path, name: str, file_format: str
) -> list[Path]:
    """Write the dataset (CSV/XLSX) and its answer key to disk."""
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    if file_format in ("csv", "both"):
        path = output_dir / f"{name}.csv"
        dataset.to_csv(path, index=False, encoding="utf-8-sig")  # -sig: Excel shows Urdu correctly
        paths.append(path)
    if file_format in ("xlsx", "both"):
        path = output_dir / f"{name}.xlsx"
        dataset.to_excel(path, index=False)
        paths.append(path)

    key_path = output_dir / f"{name}_answer_key.csv"
    answer_key.to_csv(key_path, index=False, encoding="utf-8-sig")
    paths.append(key_path)
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a synthetic messy dataset.")
    parser.add_argument("--rows", type=int, default=1000)
    parser.add_argument("--level", choices=list(LEVEL_MULTIPLIERS), default="normal")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--format", choices=["csv", "xlsx", "both"], default="both")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--name", default=None, help="Base file name (without extension)")
    args = parser.parse_args()

    name = args.name or f"synthetic_{args.level}_{args.rows}"
    dataset, answer_key = generate_dataset(args.rows, args.level, args.seed)
    paths = write_outputs(dataset, answer_key, args.output_dir, name, args.format)

    issue_counts = (
        answer_key["injected_issues"].str.split("; ").explode().value_counts()
    )
    print(f"Generated {len(dataset)} synthetic rows (level={args.level}, seed={args.seed})")
    for path in paths:
        print(f"  wrote {path}")
    print("\nInjected issues:")
    print(issue_counts.to_string())


if __name__ == "__main__":
    main()