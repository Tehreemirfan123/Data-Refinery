"""Status enumerations shared across models and services."""

from enum import Enum


class SessionStatus(str, Enum):
    """Lifecycle of a processing session through the pipeline."""

    UPLOADED = "UPLOADED"
    PROFILED = "PROFILED"
    PROCESSED = "PROCESSED"
    IN_REVIEW = "IN_REVIEW"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class RecordStatus(str, Enum):
    """Quality classification of a single record."""

    VALID = "VALID"
    CORRECTED = "CORRECTED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    INVALID = "INVALID"
    

class FieldStatus(str, Enum):
    """Outcome of cleaning a single field value."""

    VALID = "VALID"                       # already correct, unchanged
    CORRECTED = "CORRECTED"               # deterministically standardized
    MISSING = "MISSING"                   # empty / blank
    INVALID = "INVALID"                   # information lost or wrong; cannot be fixed
    SUSPICIOUS = "SUSPICIOUS"             # well-formed but implausible
    REVIEW_REQUIRED = "REVIEW_REQUIRED"   # plausible fix exists but needs a human decision