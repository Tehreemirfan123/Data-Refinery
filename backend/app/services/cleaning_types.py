"""Shared result type returned by every field cleaner."""

from dataclasses import dataclass

from backend.app.models.enums import FieldStatus


@dataclass(frozen=True)
class CleaningResult:
    """The outcome of cleaning one field value.

    Attributes:
        field: Name of the field that was cleaned (e.g. "cnic").
        original: The value exactly as received.
        cleaned: The value to store. Set only when the result is certain
            (VALID, CORRECTED, SUSPICIOUS); otherwise None.
        status: The cleaning outcome.
        reason: Human-readable explanation. Must never contain the value itself.
        suggestion: A possible fix for a human to confirm. Never applied automatically.
    """

    field: str
    original: str | None
    cleaned: str | None
    status: FieldStatus
    reason: str
    suggestion: str | None = None

    @property
    def changed(self) -> bool:
        """True when an automatic modification was made (requires an audit entry)."""
        return self.cleaned is not None and self.cleaned != self.original