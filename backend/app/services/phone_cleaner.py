"""Mobile phone cleaning and validation.

Canonical internal format: national mobile, 03XXXXXXXXX (11 digits).
Use to_e164() to convert to the international format (+923XXXXXXXXX).

Safety principle: separators (spaces, dashes, parentheses) are removed only
because the digit count and prefix fully determine the number. Values showing
signs of corruption (spreadsheet conversion, misplaced '+') are returned as
suggestions for human review, never applied automatically.
"""

import re

from backend.app.models.enums import FieldStatus
from backend.app.services.cleaning_types import CleaningResult
from backend.app.services.cleaning_utils import is_blank, normalize_digits

FIELD = "phone"

CANONICAL_PATTERN = re.compile(r"^03\d{9}$")

# Each pattern captures the 10-digit "3XXXXXXXXX" part of a mobile number.
RECOGNIZED_FORMATS = (
    re.compile(r"^0(3\d{9})$"),        # 03001234567
    re.compile(r"^\+92(3\d{9})$"),     # +923001234567
    re.compile(r"^0092(3\d{9})$"),     # 00923001234567
    re.compile(r"^92(3\d{9})$"),       # 923001234567
    re.compile(r"^(3\d{9})$"),         # 3001234567 (leading zero lost)
)

SEPARATORS = re.compile(r"[\s\-()]")
DISALLOWED_CHARACTERS = re.compile(r"[^\d\s\-()+]")
SCIENTIFIC_NOTATION = re.compile(r"\d[eE][+-]?\d")
SPREADSHEET_FLOAT = re.compile(r"^(\d+)\.0$")

# Heuristic: operator codes 030X-034X and 0355 (configurable).
KNOWN_OPERATOR_PATTERN = re.compile(r"^03(?:[0-4]\d|55)\d{7}$")


def clean_phone(value: str | None) -> CleaningResult:
    """Clean and classify a single phone number.

    Args:
        value: The raw phone value as uploaded.

    Returns:
        A CleaningResult with status VALID, CORRECTED, MISSING, INVALID,
        SUSPICIOUS or REVIEW_REQUIRED. Cleaned values use 03XXXXXXXXX.
    """
    if is_blank(value):
        return _result(value, None, FieldStatus.MISSING, "Phone number is missing")

    text = normalize_digits(value.strip())

    if SCIENTIFIC_NOTATION.search(text):
        return _result(
            value, None, FieldStatus.INVALID,
            "Phone number is in scientific notation (spreadsheet conversion); "
            "the original digits are lost",
        )

    spreadsheet_float = SPREADSHEET_FLOAT.match(text)
    if spreadsheet_float:
        return _handle_spreadsheet_float(value, spreadsheet_float.group(1))

    if DISALLOWED_CHARACTERS.search(text):
        return _result(
            value, None, FieldStatus.INVALID,
            "Phone number contains letters or unsupported characters",
        )

    national = _to_national(SEPARATORS.sub("", text))
    if national is None:
        return _handle_unrecognized(value, text)

    suspicious_reason = _suspicious_reason(national)
    if suspicious_reason:
        return _result(value, national, FieldStatus.SUSPICIOUS, suspicious_reason)

    if national == value:
        return _result(value, national, FieldStatus.VALID, "Phone number is in the standard format")

    return _result(
        value, national, FieldStatus.CORRECTED,
        "Phone number standardized to the 03XXXXXXXXX format",
    )


def to_e164(phone: str | None) -> str | None:
    """Convert a standardized 03XXXXXXXXX number to E.164 (+923XXXXXXXXX).

    Returns None if the input is not in the standardized national format.
    """
    if phone is None or not CANONICAL_PATTERN.match(phone):
        return None
    return "+92" + phone[1:]


# --- internal helpers ---------------------------------------------------------

def _result(
    original: str | None,
    cleaned: str | None,
    status: FieldStatus,
    reason: str,
    suggestion: str | None = None,
) -> CleaningResult:
    return CleaningResult(FIELD, original, cleaned, status, reason, suggestion)


def _to_national(compact: str) -> str | None:
    """Return 03XXXXXXXXX if the separator-free text is a recognized mobile format."""
    for pattern in RECOGNIZED_FORMATS:
        match = pattern.match(compact)
        if match:
            return "0" + match.group(1)
    return None


def _handle_spreadsheet_float(original: str, digits: str) -> CleaningResult:
    """A value like '3001234567.0' was probably converted to a number by a spreadsheet."""
    national = _to_national(digits)
    if national:
        return _result(
            original, None, FieldStatus.REVIEW_REQUIRED,
            "Phone number appears to have been converted to a number by a spreadsheet; "
            "the digits look complete but should be confirmed",
            suggestion=national,
        )
    return _result(
        original, None, FieldStatus.INVALID,
        f"Phone number appears to have been converted to a number by a spreadsheet "
        f"and has {len(digits)} digits",
    )


def _handle_unrecognized(original: str, text: str) -> CleaningResult:
    """Explain why a value is not a recognized mobile number."""
    digits = re.sub(r"\D", "", text)

    national = _to_national(digits)
    if national:                   # digits are fine, but the layout is odd (e.g. a misplaced '+')
        return _result(
            original, None, FieldStatus.REVIEW_REQUIRED,
            "Phone number has valid digits but an unusual layout",
            suggestion=national,
        )

    if digits.startswith("0") and not digits.startswith("03") and 9 <= len(digits) <= 11:
        return _result(
            original, None, FieldStatus.INVALID,
            "Phone number appears to be a landline; a mobile number (03XXXXXXXXX) is expected",
        )

    return _result(
        original, None, FieldStatus.INVALID,
        f"Phone number has {len(digits)} digits; expected an 11-digit mobile number",
    )


def _suspicious_reason(national: str) -> str | None:
    subscriber = national[4:]
    if len(set(subscriber)) == 1:
        return "Phone number looks like a placeholder (repeated digits)"
    if not KNOWN_OPERATOR_PATTERN.match(national):
        return "Phone number operator code is not recognized"
    return None