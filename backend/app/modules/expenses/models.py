import datetime as dt
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, BigIntFK, BigIntPK, Money, Qty, TimestampMixin
from app.modules.common_models import TxnMixin


class Expense(Base, TimestampMixin, TxnMixin):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    voucher_no: Mapped[str] = mapped_column(String(30), unique=True)
    date: Mapped[dt.date] = mapped_column(Date)
    category: Mapped[str] = mapped_column(String(10))
    vehicle_id: Mapped[int | None] = mapped_column(BigIntFK, ForeignKey("vehicles.id"), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Money)
    litres: Mapped[Decimal | None] = mapped_column(Qty, nullable=True)
    meter_reading: Mapped[Decimal | None] = mapped_column(Qty, nullable=True)
    paid_via: Mapped[str] = mapped_column(String(15))  # money_account | party_credit
    money_account_id: Mapped[int | None] = mapped_column(BigIntFK, ForeignKey("money_accounts.id"), nullable=True)
    party_id: Mapped[int | None] = mapped_column(BigIntFK, ForeignKey("parties.id"), nullable=True)
    journal_id: Mapped[int | None] = mapped_column(BigIntFK, ForeignKey("journal_entries.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_expenses_amount_positive"),
        Index("ix_expenses_vehicle_date", "vehicle_id", "date"),
    )
