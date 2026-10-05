"""Small helpers shared by cleaners."""

# Urdu/Persian (U+06F0-06F9) and Arabic-Indic (U+0660-0669) digits -> ASCII digits.
_EASTERN_DIGITS = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)


def is_blank(value: str | None) -> bool:
    """True for None, empty strings and whitespace-only strings."""
    return value is None or value.strip() == ""


def normalize_digits(text: str) -> str:
    """Convert Urdu/Arabic-Indic digits to ASCII digits (a fixed 1-to-1 mapping)."""
    return text.translate(_EASTERN_DIGITS)