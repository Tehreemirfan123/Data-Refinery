"""Urdu/English location normalization.

Districts are matched through a comparison key that ignores case, spacing,
administrative prefixes, diacritics and Arabic-vs-Urdu letter forms.

- Spellings listed in reference data (curated) are applied automatically.
- Similarity-based matches are only ever SUGGESTED for human review.
"""

import difflib
import re
import unicodedata
from functools import lru_cache

from backend.app.models.enums import FieldStatus
from backend.app.services.cleaning_types import CleaningResult
from backend.app.services.cleaning_utils import is_blank, is_placeholder, normalize_text
from backend.app.services.reference_data import load_reference

FIELD = "district"
SIMILARITY_CUTOFF = 0.8

# Arabic letter forms that look like Urdu letters but are different code points.
_ARABIC_TO_URDU = str.maketrans({
    "ي": "ی",   # Arabic yeh       -> Farsi/Urdu yeh
    "ى": "ی",   # Alef maksura     -> Farsi/Urdu yeh
    "ك": "ک",   # Arabic kaf       -> keheh
    "ه": "ہ",   # Arabic heh       -> heh goal
})

_ADMIN_PREFIX = re.compile(r"^(?:district|distt\.?|dist\.?|ضلع)\s+")
_KEY_SEPARATORS = re.compile(r"[\s.\-']+")


def location_key(text: str) -> str:
    """Build a comparison key for a place name (never stored or displayed).

    Example: "Distt. Bahawal Pur" -> "bahawalpur"; "بهاولپور" == key of "بہاولپور".
    """
    text = normalize_text(text).translate(_ARABIC_TO_URDU)
    decomposed = unicodedata.normalize("NFD", text)
    text = "".join(char for char in decomposed if not unicodedata.category(char).startswith("M"))
    text = _ADMIN_PREFIX.sub("", text.casefold())
    return _KEY_SEPARATORS.sub("", text)


def build_district_index(districts: list[dict]) -> dict[str, str]:
    """Map every known spelling's key to its standard district name.

    Raises:
        ValueError: If one spelling would map to two different districts
            (conflicting reference data must be fixed, not silently resolved).
    """
    index: dict[str, str] = {}
    for district in districts:
        standard = district["name"]
        for spelling in (standard, district["urdu"], *district.get("variants", [])):
            key = location_key(spelling)
            existing = index.get(key)
            if existing is not None and existing != standard:
                raise ValueError(
                    f"Reference data conflict: '{spelling}' maps to both '{existing}' and '{standard}'"
                )
            index[key] = standard
    return index


def normalize_district(value: str | None) -> CleaningResult:
    """Standardize a district value to its English reference name.

    Returns:
        VALID / CORRECTED for known spellings, MISSING for blanks and
        placeholders, REVIEW_REQUIRED (with a suggestion when exactly one
        close match exists) for anything not in the reference data.
    """
    if is_blank(value) or is_placeholder(value):
        return _result(value, None, FieldStatus.MISSING, "District is missing")

    index = _district_index()
    key = location_key(value)

    standard = index.get(key)
    if standard is not None:
        if standard == value:
            return _result(value, standard, FieldStatus.VALID, "District is in the standard form")
        return _result(
            value, standard, FieldStatus.CORRECTED,
            "District mapped to its standard name using reference data",
        )

    close_keys = difflib.get_close_matches(key, index.keys(), n=5, cutoff=SIMILARITY_CUTOFF)
    candidates = {index[close_key] for close_key in close_keys}

    if len(candidates) == 1:
        return _result(
            value, None, FieldStatus.REVIEW_REQUIRED,
            "District not recognized; one similar known district is suggested",
            suggestion=candidates.pop(),
        )
    if len(candidates) > 1:
        return _result(
            value, None, FieldStatus.REVIEW_REQUIRED,
            "District resembles more than one known district; no suggestion is made",
        )
    return _result(
        value, None, FieldStatus.REVIEW_REQUIRED, "District not found in the reference data",
    )


# --- internal helpers ---------------------------------------------------------

@lru_cache
def _district_index() -> dict[str, str]:
    return build_district_index(load_reference("locations.json")["districts"])


def _result(
    original: str | None,
    cleaned: str | None,
    status: FieldStatus,
    reason: str,
    suggestion: str | None = None,
) -> CleaningResult:
    return CleaningResult(FIELD, original, cleaned, status, reason, suggestion)