import datetime as dt
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, BigIntFK, BigIntPK, Money, Qty, TimestampMixin
from app.modules.common_models import TxnMixin


class Attendance(Base, TimestampMixin):
    """One row per worker per day. Daily-wage workers accrue their wage when it is saved."""

    __tablename__ = "attendance"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    date: Mapped[dt.date] = mapped_column(Date)
    staff_id: Mapped[int] = mapped_column(BigIntFK, ForeignKey("staff.id"))
    status: Mapped[str] = mapped_column(String(7))  # present | half | absent
    overtime_hours: Mapped[Decimal] = mapped_column(Qty, default=0)
    site_id: Mapped[int | None] = mapped_column(BigIntFK, ForeignKey("sites.id"), nullable=True)
    vehicle_id: Mapped[int | None] = mapped_column(BigIntFK, ForeignKey("vehicles.id"), nullable=True)
    journal_id: Mapped[int | None] = mapped_column(BigIntFK, ForeignKey("journal_entries.id"), nullable=True)

    __table_args__ = (
        UniqueConstraint("date", "staff_id", name="uq_attendance_date_staff"),
        Index("ix_attendance_staff_date", "staff_id", "date"),
    )


class WageSettlement(Base, TimestampMixin, TxnMixin):
    """Monthly staff accrue here; per-trip staff accrue here; daily labour already accrued per day."""

    __tablename__ = "wage_settlements"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    staff_id: Mapped[int] = mapped_column(BigIntFK, ForeignKey("staff.id"), index=True)
    period_from: Mapped[dt.date] = mapped_column(Date)
    period_to: Mapped[dt.date] = mapped_column(Date)
    days: Mapped[Decimal] = mapped_column(Qty, default=0)
    trips: Mapped[int] = mapped_column(Integer, default=0)
    gross: Mapped[Decimal] = mapped_column(Money)
    advances_adjusted: Mapped[Decimal] = mapped_column(Money, default=0)
    deductions: Mapped[Decimal] = mapped_column(Money, default=0)
    net_payable: Mapped[Decimal] = mapped_column(Money)
    journal_id: Mapped[int | None] = mapped_column(BigIntFK, ForeignKey("journal_entries.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
