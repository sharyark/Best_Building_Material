import datetime as dt
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, BigIntFK, BigIntPK, Money, TimestampMixin
from app.modules.common_models import TxnMixin


class Payment(Base, TimestampMixin, TxnMixin):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    voucher_no: Mapped[str] = mapped_column(String(30), unique=True)
    date: Mapped[dt.date] = mapped_column(Date)
    direction: Mapped[str] = mapped_column(String(3))  # in | out
    party_id: Mapped[int | None] = mapped_column(BigIntFK, ForeignKey("parties.id"), nullable=True)
    staff_id: Mapped[int | None] = mapped_column(BigIntFK, ForeignKey("staff.id"), nullable=True)
    money_account_id: Mapped[int] = mapped_column(BigIntFK, ForeignKey("money_accounts.id"))
    mode: Mapped[str] = mapped_column(String(10))  # cash | bank | cheque | online
    purpose: Mapped[str] = mapped_column(String(10), default="general")  # general | advance | salary
    ref_no: Mapped[str | None] = mapped_column(String(60), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Money)
    journal_id: Mapped[int | None] = mapped_column(BigIntFK, ForeignKey("journal_entries.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_payments_amount_positive"),
        CheckConstraint("(party_id IS NULL) <> (staff_id IS NULL)", name="ck_payments_one_counterparty"),
        Index("ix_payments_party_date", "party_id", "date"),
        Index("ix_payments_staff_date", "staff_id", "date"),
    )
