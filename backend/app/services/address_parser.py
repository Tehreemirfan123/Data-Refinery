"""Address parsing: district, tehsil and Union Council extraction.

Approach: find KNOWN location names (from reference data) inside the address,
checking the longest word runs first, instead of splitting by position.

Rules:
- A value is extracted only when it is stated unambiguously.
- A district inferred from a tehsil (not stated) is only SUGGESTED.
- Conflicting or multiple locations are sent for human review.
- Extracted fields are new (derived) values: original is None, so every
  extraction is recorded by the audit trail.
"""

import re
from dataclasses import dataclass
from functools import lru_cache

from backend.app.models.enums import FieldStatus
from backend.app.services.cleaning_types import CleaningResult
from backend.app.services.cleaning_utils import is_blank, is_placeholder, normalize_text
from backend.app.services.normalization_service import build_district_index, location_key
from backend.app.services.reference_data import load_reference

DISTRICT_FIELD = "address_district"
TEHSIL_FIELD = "tehsil"
UC_FIELD = "union_council"

MAX_NAME_WORDS = 3  # longest location name in the reference data, in words

_TOKEN_SPLIT = re.compile(r"[\s,;#/()]+")
_UNION_COUNCIL = re.compile(
    r"\b(?:UC|U\.C\.|Union\s+Council)\s*[-#:]?\s*(?:No\.?\s*)?"
    r"(?:(Chak)\s*(?:No\.?\s*)?(\d+)|(\d+))",
    re.IGNORECASE,
)

TehsilOptions = frozenset[tuple[str, str]]  # {(tehsil name, its district), ...}


@dataclass(frozen=True)
class ParsedAddress:
    """The three location fields extracted from one address."""

    district: CleaningResult
    tehsil: CleaningResult
    union_council: CleaningResult

    def results(self) -> tuple[CleaningResult, CleaningResult, CleaningResult]:
        return self.district, self.tehsil, self.union_council


def parse_address(value: str | None) -> ParsedAddress:
    """Extract district, tehsil and Union Council from a free-text address."""
    if is_blank(value) or is_placeholder(value):
        reason = "Address is missing"
        return ParsedAddress(
            _missing(DISTRICT_FIELD, reason),
            _missing(TEHSIL_FIELD, reason),
            _missing(UC_FIELD, reason),
        )

    text = normalize_text(value)
    districts, tehsil_mentions = _find_locations(text)
    district_result, tehsil_result = _resolve_locations(districts, tehsil_mentions)
    return ParsedAddress(district_result, tehsil_result, _extract_union_council(text))


# --- location finding -----------------------------------------------------------

def _find_locations(text: str) -> tuple[set[str], list[TehsilOptions]]:
    """Find district and tehsil names, longest word runs first."""
    tokens = [token for token in _TOKEN_SPLIT.split(text) if token]
    used = [False] * len(tokens)
    district_index, tehsil_index = _district_index(), _tehsil_index()

    districts: list[str] = []
    tehsils: list[TehsilOptions] = []
    ambiguous: list[tuple[str, TehsilOptions]] = []  # names that are district AND tehsil

    for size in range(MAX_NAME_WORDS, 0, -1):
        for start in range(len(tokens) - size + 1):
            if any(used[start:start + size]):
                continue
            key = location_key(" ".join(tokens[start:start + size]))
            district = district_index.get(key)
            tehsil_options = tehsil_index.get(key)
            if district is None and tehsil_options is None:
                continue

            used[start:start + size] = [True] * size
            if district and tehsil_options:
                ambiguous.append((district, tehsil_options))
            elif district:
                districts.append(district)
            else:
                tehsils.append(tehsil_options)

    # Resolve ambiguous mentions only after all unambiguous ones are known.
    for district, tehsil_options in ambiguous:
        if not districts:
            districts.append(district)
        elif not tehsils:
            tehsils.append(tehsil_options)
        else:
            districts.append(district)

    return set(districts), tehsils


def _resolve_locations(
    districts: set[str], tehsil_mentions: list[TehsilOptions]
) -> tuple[CleaningResult, CleaningResult]:
    """Turn the found names into district and tehsil results, checking consistency."""
    pairs: set[tuple[str, str]] = set().union(*tehsil_mentions)

    if len(districts) > 1:
        return (
            _review(DISTRICT_FIELD, "Address mentions more than one district"),
            _tehsil_result(pairs),
        )

    if len(districts) == 1:
        district = next(iter(districts))
        pairs_in_district = {pair for pair in pairs if pair[1] == district}
        if pairs and not pairs_in_district:
            reason = "Tehsil in the address does not belong to the district in the address"
            return _review(DISTRICT_FIELD, reason), _review(TEHSIL_FIELD, reason)
        return (
            _found(DISTRICT_FIELD, district, "District found in the address"),
            _tehsil_result(pairs_in_district),
        )

    # No district stated: a tehsil may imply one, but that is only a suggestion.
    implied = {district for _, district in pairs}
    if len(implied) == 1:
        district_result = _review(
            DISTRICT_FIELD,
            "District not stated in the address; inferred from the tehsil",
            suggestion=next(iter(implied)),
        )
    elif len(implied) > 1:
        district_result = _review(DISTRICT_FIELD, "Tehsil name exists in more than one district")
    else:
        district_result = _missing(DISTRICT_FIELD, "No district found in the address")
    return district_result, _tehsil_result(pairs)


def _tehsil_result(pairs: set[tuple[str, str]]) -> CleaningResult:
    names = {tehsil for tehsil, _ in pairs}
    if len(names) == 1:
        return _found(TEHSIL_FIELD, next(iter(names)), "Tehsil found in the address")
    if len(names) > 1:
        return _review(TEHSIL_FIELD, "Address mentions more than one tehsil")
    return _missing(TEHSIL_FIELD, "No tehsil found in the address")


# --- Union Council --------------------------------------------------------------

def _extract_union_council(text: str) -> CleaningResult:
    values = {_format_union_council(match) for match in _UNION_COUNCIL.finditer(text)}
    if len(values) == 1:
        return _found(UC_FIELD, values.pop(), "Union Council found in the address")
    if len(values) > 1:
        return _review(UC_FIELD, "Address mentions more than one Union Council")
    return _missing(UC_FIELD, "No Union Council found in the address")


def _format_union_council(match: re.Match) -> str:
    chak, chak_number, number = match.groups()
    if chak:
        return f"Chak {int(chak_number)}"
    return f"UC {int(number)}"


# --- reference indexes ----------------------------------------------------------

@lru_cache
def _district_index() -> dict[str, str]:
    return build_district_index(load_reference("locations.json")["districts"])


@lru_cache
def _tehsil_index() -> dict[str, TehsilOptions]:
    """Map each tehsil key to every (tehsil, district) pair that uses that name."""
    index: dict[str, set[tuple[str, str]]] = {}
    for district in load_reference("locations.json")["districts"]:
        for tehsil in district["tehsils"]:
            index.setdefault(location_key(tehsil), set()).add((tehsil, district["name"]))
    return {key: frozenset(pairs) for key, pairs in index.items()}


# --- result helpers -------------------------------------------------------------

def _found(field: str, value: str, reason: str) -> CleaningResult:
    return CleaningResult(field, None, value, FieldStatus.VALID, reason)


def _missing(field: str, reason: str) -> CleaningResult:
    return CleaningResult(field, None, None, FieldStatus.MISSING, reason)


def _review(field: str, reason: str, suggestion: str | None = None) -> CleaningResult:
    return CleaningResult(field, None, None, FieldStatus.REVIEW_REQUIRED, reason, suggestion)