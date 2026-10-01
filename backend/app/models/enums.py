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
    """Quality classification of a single record (Module 10)."""

    VALID = "VALID"
    CORRECTED = "CORRECTED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    INVALID = "INVALID"