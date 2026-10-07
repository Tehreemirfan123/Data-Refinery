"""Name, general text and gender cleaning.

Principles:
- Only presentational problems are fixed automatically: whitespace, invisible
  characters, and words written entirely in upper or lower case.
- Spelling is never changed in stored names. Spelling variants are handled by
  name_match_key(), which is used only for duplicate detection.
- Names containing digits or symbols are left untouched and sent for review.
"""

import re
import unicodedata

from backend.app.models.enums import FieldStatus
from backend.app.services.cleaning_types import CleaningResult
from backend.app.services.cleaning_utils import is_blank, is_placeholder, normalize_text
from backend.app.services.reference_data import load_reference

NAME_PUNCTUATION = frozenset(" .'-")


# --- names --------------------------------------------------------------------

def clean_name(value: str | None, field: str = "full_name") -> CleaningResult:
    """Standardize spacing and capitalization of a person's name.

    Args:
        value: The raw name.
        field: Which field is being cleaned ("full_name", "father_name", ...).
    """
    if is_blank(value):
        return CleaningResult(field, value, None, FieldStatus.MISSING, "Name is missing")
    if is_placeholder(value):
        return CleaningResult(
            field, value, None, FieldStatus.MISSING,
            "Name contains a placeholder (such as N/A) instead of a name",
        )

    text = normalize_text(value)
    if not _is_plausible_name(text):
        return CleaningResult(
            field, value, None, FieldStatus.REVIEW_REQUIRED,
            "Name contains digits or symbols; it is not changed automatically",
        )

    cleaned = " ".join(_fix_word_case(word) for word in text.split(" "))
    if cleaned == value:
        return CleaningResult(field, value, cleaned, FieldStatus.VALID, "Name is already clean")
    return CleaningResult(
        field, value, cleaned, FieldStatus.CORRECTED,
        "Name spacing and capitalization standardized (spelling unchanged)",
    )


def name_match_key(value: str | None) -> str | None:
    """Build a comparison key in which known spelling variants are equal.

    Used ONLY for duplicate detection. Never store or display this value.
    Example: "MOHAMMAD  ali" -> "muhammad ali".
    """
    if is_blank(value) or is_placeholder(value):
        return None
    text = normalize_text(value).casefold()
    words = re.sub(r"[.'\-]", " ", text).split()
    variant_map = _name_variant_map()
    return " ".join(variant_map.get(word, word) for word in words) or None


def _is_plausible_name(text: str) -> bool:
    """Letters (any script, including combining marks) plus . ' - and spaces only."""
    has_letter = False
    for char in text:
        category = unicodedata.category(char)
        if category.startswith("L"):
            has_letter = True
        elif not (category.startswith("M") or char in NAME_PUNCTUATION):
            return False
    return has_letter


def _fix_word_case(word: str) -> str:
    """Re-case a word only when it is entirely upper or entirely lower case."""
    if not (word.isupper() or word.islower()):
        return word  # mixed case (McDonald) or uncased script (Urdu): keep as is
    parts = re.split(r"([-'])", word.lower())
    return "".join(part if part in ("-", "'") else part[:1].upper() + part[1:] for part in parts)


def _name_variant_map() -> dict[str, str]:
    """Reverse lookup: each variant -> its comparison form."""
    variants = load_reference("name_variants.json")["variants"]
    return {variant: canonical for canonical, spellings in variants.items() for variant in spellings}


# --- general text -------------------------------------------------------------

def clean_text(value: str | None, field: str) -> CleaningResult:
    """Normalize whitespace and invisible characters in a free-text field."""
    if is_blank(value):
        return CleaningResult(field, value, None, FieldStatus.MISSING, "Value is missing")
    if is_placeholder(value):
        return CleaningResult(
            field, value, None, FieldStatus.MISSING, "Value is a placeholder (such as N/A)",
        )

    cleaned = normalize_text(value)
    if cleaned == value:
        return CleaningResult(field, value, cleaned, FieldStatus.VALID, "Text is already clean")
    return CleaningResult(
        field, value, cleaned, FieldStatus.CORRECTED, "Whitespace and invisible characters normalized",
    )


# --- gender -------------------------------------------------------------------

def clean_gender(value: str | None) -> CleaningResult:
    """Map gender spellings (m, FEMALE, مرد ...) to the standard labels Male / Female."""
    field = "gender"
    if is_blank(value) or is_placeholder(value):
        return CleaningResult(field, value, None, FieldStatus.MISSING, "Gender is missing")

    label = _gender_lookup().get(normalize_text(value).casefold())
    if label is None:
        return CleaningResult(
            field, value, None, FieldStatus.INVALID, "Gender value is not a recognized category",
        )
    if label == value:
        return CleaningResult(field, value, label, FieldStatus.VALID, "Gender is in the standard form")
    return CleaningResult(
        field, value, label, FieldStatus.CORRECTED, "Gender value mapped to the standard label",
    )


def _gender_lookup() -> dict[str, str]:
    values = load_reference("gender_values.json")["values"]
    return {spelling: label for label, spellings in values.items() for spelling in spellings}