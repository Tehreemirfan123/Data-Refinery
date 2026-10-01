"""DatasetRecord: one row from an uploaded dataset."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base
from backend.app.models.enums import RecordStatus


class DatasetRecord(Base):
    __tablename__ = "dataset_records"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("processing_sessions.id", ondelete="CASCADE"), index=True
    )
    row_number: Mapped[int] = mapped_column(Integer)  # position in the uploaded file

    original_data: Mapped[dict] = mapped_column(JSONB)                   # never modified
    cleaned_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    status: Mapped[RecordStatus | None] = mapped_column(
        Enum(RecordStatus, native_enum=False, length=20), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    session: Mapped["ProcessingSession"] = relationship(back_populates="records")

    def __repr__(self) -> str:
        return f"<DatasetRecord session={self.session_id} row={self.row_number}>"