"""CNIC cleaning and validation.

Standard format: NNNNN-NNNNNNN-N (5 digits, 7 digits, 1 digit).

Safety principle: a CNIC is reformatted automatically ONLY when it matches an
explicit allow-list of known, unambiguous formats. Values where information
may be lost (wrong digit count, letters, scientific notation) are never
"repaired". Plausible but uncertain fixes are returned as suggestions for
human review.
"""

import re

from backend.app.models.enums import FieldStatus
from backend.app.services.cleaning_types import CleaningResult
from backend.app.services.cleaning_utils import is_blank, normalize_digits

FIELD = "cnic"

CANONICAL_PATTERN = re.compile(r"^\d{5}-\d{7}-\d$")

# Allow-list: patterns (5 digits, 7 digits, 1 digit).
ACCEPTED_FORMATS = (
    re.compile(r"^(\d{5})(\d{7})(\d)$"),        # 3520112345671
    re.compile(r"^(\d{5})-(\d{7})-(\d)$"),      # 35201-1234567-1
    re.compile(r"^(\d{5}) (\d{7}) (\d)$"),      # 35201 1234567 1
    re.compile(r"^(\d{5})\.(\d{7})\.(\d)$"),    # 35201.1234567.1
    re.compile(r"^(\d{5})-(\d{7})(\d)$"),       # 35201-12345671
)

SCIENTIFIC_NOTATION = re.compile(r"\d[eE][+-]?\d")   # 3.52011E+12
SPREADSHEET_FLOAT = re.compile(r"^(\d+)\.0$")        # 3520112345671.0

# Heuristics for well-formed but implausible values (configurable constants).
VALID_FIRST_DIGITS = frozenset("1234567")            # province-code convention
KNOWN_PLACEHOLDERS = frozenset({"1234512345671", "1234567890123"})


def clean_cnic(value: str | None) -> CleaningResult:
    """Clean and classify a single CNIC value.

    Args:
        value: The raw CNIC as uploaded (may be None or messy).

    Returns:
        A CleaningResult with status VALID, CORRECTED, MISSING, INVALID,
        SUSPICIOUS or REVIEW_REQUIRED.
    """
    if is_blank(value):
        return _result(value, None, FieldStatus.MISSING, "CNIC is missing")

    text = normalize_digits(value.strip())

    if SCIENTIFIC_NOTATION.search(text):
        return _result(
            value, None, FieldStatus.INVALID,
            "CNIC is in scientific notation (spreadsheet conversion); "
            "the original digits are lost and cannot be recovered",
        )

    spreadsheet_float = SPREADSHEET_FLOAT.match(text)
    if spreadsheet_float:
        return _handle_spreadsheet_float(value, spreadsheet_float.group(1))

    groups = _match_accepted_format(text)
    if groups is None:
        return _handle_unrecognized(value, text)

    canonical = "-".join(groups)

    suspicious_reason = _suspicious_reason(canonical)
    if suspicious_reason:
        return _result(value, canonical, FieldStatus.SUSPICIOUS, suspicious_reason)

    if canonical == value:
        return _result(value, canonical, FieldStatus.VALID, "CNIC is in the standard format")

    return _result(value, canonical, FieldStatus.CORRECTED, "CNIC reformatted to the standard 5-7-1 format")


def gender_from_cnic(cnic: str | None) -> str | None:
    """Return the gender implied by a standard-format CNIC's last digit.

    Convention: odd last digit = Male, even = Female. Returns None if the
    CNIC is not in the standard format. Used by the validation engine for
    cross-field consistency checks; it does not alter any data.
    """
    if cnic is None or not CANONICAL_PATTERN.match(cnic):
        return None
    return "Male" if int(cnic[-1]) % 2 == 1 else "Female"


# --- internal helpers ---------------------------------------------------------

def _result(
    original: str | None,
    cleaned: str | None,
    status: FieldStatus,
    reason: str,
    suggestion: str | None = None,
) -> CleaningResult:
    return CleaningResult(FIELD, original, cleaned, status, reason, suggestion)


def _match_accepted_format(text: str) -> tuple[str, str, str] | None:
    for pattern in ACCEPTED_FORMATS:
        match = pattern.match(text)
        if match:
            return match.groups()
    return None


def _format_digits(digits: str) -> str:
    return f"{digits[:5]}-{digits[5:12]}-{digits[12]}"


def _handle_spreadsheet_float(original: str, digits: str) -> CleaningResult:
    """A value like '3520112345671.0' was probably converted to a number by a spreadsheet."""
    if len(digits) == 13:
        return _result(
            original, None, FieldStatus.REVIEW_REQUIRED,
            "CNIC appears to have been converted to a number by a spreadsheet; "
            "the digits look complete but should be confirmed",
            suggestion=_format_digits(digits),
        )
    return _result(
        original, None, FieldStatus.INVALID,
        f"CNIC appears to have been converted to a number by a spreadsheet and has "
        f"{len(digits)} digits; expected 13",
    )


def _handle_unrecognized(original: str, text: str) -> CleaningResult:
    """Explain why a value did not match any accepted format."""
    if re.search(r"[^\d\s.\-]", text):
        return _result(
            original, None, FieldStatus.INVALID,
            "CNIC contains characters other than digits and separators; "
            "letters are never assumed to be digits (e.g. 'O' is not treated as '0')",
        )

    digits = re.sub(r"\D", "", text)
    if len(digits) != 13:
        return _result(
            original, None, FieldStatus.INVALID,
            f"CNIC has {len(digits)} digits; expected 13",
        )

    return _result(
        original, None, FieldStatus.REVIEW_REQUIRED,
        "CNIC has 13 digits but an unrecognized separator layout",
        suggestion=_format_digits(digits),
    )


def _suspicious_reason(canonical: str) -> str | None:
    digits = canonical.replace("-", "")
    if len(set(digits)) == 1:
        return "CNIC looks like a placeholder (all digits identical)"
    if digits in KNOWN_PLACEHOLDERS:
        return "CNIC looks like a placeholder (sequential test pattern)"
    if digits[0] not in VALID_FIRST_DIGITS:
        return "CNIC first digit is outside the expected province-code range"
    return None