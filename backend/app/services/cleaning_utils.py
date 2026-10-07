"""Small helpers shared by cleaners."""
import re
import unicodedata

# Urdu/Persian (U+06F0-06F9) and Arabic-Indic (U+0660-0669) digits -> ASCII digits.
_EASTERN_DIGITS = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)

# Invisible characters removed during normalization: zero-width space and BOM.
# ZWNJ (U+200C) is intentionally NOT removed: it controls letter joining in Urdu.
_INVISIBLE = dict.fromkeys(map(ord, "\u200b\ufeff"), None)

_WHITESPACE = re.compile(r"\s+")                       # includes tabs, newlines, non-breaking spaces

PLACEHOLDER_VALUES = frozenset({
    "na", "n/a", "n.a.", "nil", "none", "null", "-", "--", "---", "?",
    "unknown", "not available", "not applicable",
})


def is_blank(value: str | None) -> bool:
    """True for None, empty strings and whitespace-only strings."""
    return value is None or value.strip() == ""


def normalize_digits(text: str) -> str:
    """Convert Urdu/Arabic-Indic digits to ASCII digits (a fixed 1-to-1 mapping)."""
    return text.translate(_EASTERN_DIGITS)


def normalize_text(text: str) -> str:
    """Unicode NFC, remove invisible characters, collapse whitespace, trim."""
    text = unicodedata.normalize("NFC", text).translate(_INVISIBLE)
    return _WHITESPACE.sub(" ", text).strip()


def is_placeholder(value: str | None) -> bool:
    """True when a value is a stand-in for 'no data' (e.g. 'N/A', '-', 'Unknown')."""
    if value is None:
        return False
    return normalize_text(value).casefold() in PLACEHOLDER_VALUES