"""Columns shared by every financial document (idempotency + void bookkeeping)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import BigIntFK

ACTIVE = "active"
VOID = "void"


class TxnMixin:
    status: Mapped[str] = mapped_column(String(10), default=ACTIVE)
    void_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_by: Mapped[int | None] = mapped_column(BigIntFK, ForeignKey("users.id"), nullable=True)
    # Idempotency: a double-click with the same client_ref can't create two documents.
    client_ref: Mapped[uuid.UUID | None] = mapped_column(Uuid, unique=True, nullable=True)


__all__ = ["ACTIVE", "VOID", "TxnMixin"]
