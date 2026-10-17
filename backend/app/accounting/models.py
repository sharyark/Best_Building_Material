import datetime as dt
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, BigIntFK, BigIntPK, Money, TimestampMixin

ACCOUNT_TYPES = ("asset", "liability", "income", "expense", "equity")


class Account(Base, TimestampMixin):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(150))
    type: Mapped[str] = mapped_column(String(10))
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    parent_id: Mapped[int | None] = mapped_column(BigIntFK, ForeignKey("accounts.id"), nullable=True)

    __table_args__ = (
        CheckConstraint("type in ('asset','liability','income','expense','equity')", name="ck_accounts_type"),
    )


class JournalEntry(Base, TimestampMixin):
    __tablename__ = "journal_entries"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    date: Mapped[dt.date] = mapped_column(Date)
    source_type: Mapped[str] = mapped_column(String(30))
    source_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    narration: Mapped[str] = mapped_column(String(300), default="")
    reverses_id: Mapped[int | None] = mapped_column(
        BigIntFK, ForeignKey("journal_entries.id"), nullable=True, unique=True
    )

    lines: Mapped[list["JournalLine"]] = relationship(
        back_populates="journal", cascade="all, delete-orphan", order_by="JournalLine.id"
    )

    __table_args__ = (
        Index("ix_journal_entries_date", "date"),
        Index("ix_journal_entries_source", "source_type", "source_id"),
    )


class JournalLine(Base):
    __tablename__ = "journal_lines"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    journal_id: Mapped[int] = mapped_column(BigIntFK, ForeignKey("journal_entries.id"))
    account_id: Mapped[int] = mapped_column(BigIntFK, ForeignKey("accounts.id"))
    debit: Mapped[Decimal] = mapped_column(Money, default=0)
    credit: Mapped[Decimal] = mapped_column(Money, default=0)
    # Cost centre: gives profit per vehicle for free.
    vehicle_id: Mapped[int | None] = mapped_column(BigIntFK, ForeignKey("vehicles.id"), nullable=True)

    journal: Mapped[JournalEntry] = relationship(back_populates="lines")

    __table_args__ = (
        CheckConstraint(
            "debit >= 0 AND credit >= 0 AND ((debit = 0) <> (credit = 0))",
            name="ck_journal_lines_one_side",
        ),
        Index("ix_journal_lines_account_journal", "account_id", "journal_id"),
        Index("ix_journal_lines_vehicle", "vehicle_id"),
    )


class PeriodLock(Base):
    __tablename__ = "period_locks"

    month: Mapped[dt.date] = mapped_column(Date, primary_key=True)  # always the 1st of the month
    locked_by: Mapped[int | None] = mapped_column(BigIntFK, ForeignKey("users.id"), nullable=True)
    locked_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DocSequence(Base):
    """Gap-free document numbers. Incremented inside the document's own transaction."""

    __tablename__ = "doc_sequences"

    doc_type: Mapped[str] = mapped_column(String(10), primary_key=True)
    fin_year: Mapped[str] = mapped_column(String(9), primary_key=True)
    last_no: Mapped[int] = mapped_column(Integer, default=0)


__all__ = ["Account", "DocSequence", "JournalEntry", "JournalLine", "PeriodLock", "Text"]
