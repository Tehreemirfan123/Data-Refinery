"""Apply every field cleaner to one record.

This is the bridge between the cleaner modules and the processing
pipeline: it composes pure functions and touches no database or files.
Fields without a cleaner yet (family_id, source_system) are passed through
unchanged by the caller.
"""

from collections.abc import Mapping

from backend.app.services.address_parser import parse_address
from backend.app.services.cleaning_types import CleaningResult
from backend.app.services.cnic_cleaner import clean_cnic
from backend.app.services.normalization_service import normalize_district
from backend.app.services.phone_cleaner import clean_phone
from backend.app.services.text_cleaner import clean_gender, clean_name, clean_text


def clean_record(record: Mapping[str, str | None]) -> dict[str, CleaningResult]:
    """Clean one uploaded row and return a CleaningResult per output field.

    Optional columns that are absent from the record are treated as missing.
    """
    parsed_address = parse_address(record.get("address"))
    return {
        "cnic": clean_cnic(record.get("cnic")),
        "phone": clean_phone(record.get("phone")),
        "full_name": clean_name(record.get("full_name"), field="full_name"),
        "father_name": clean_name(record.get("father_name"), field="father_name"),
        "gender": clean_gender(record.get("gender")),
        "district": normalize_district(record.get("district")),
        "address": clean_text(record.get("address"), field="address"),
        "address_district": parsed_address.district,
        "tehsil": parsed_address.tehsil,
        "union_council": parsed_address.union_council,
    }