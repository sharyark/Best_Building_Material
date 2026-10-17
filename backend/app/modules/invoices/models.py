import datetime as dt
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, BigIntFK, BigIntPK, Money, TimestampMixin
from app.modules.common_models import TxnMixin


class Invoice(Base, TimestampMixin, TxnMixin):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    invoice_no: Mapped[str] = mapped_column(String(30), unique=True)
    date: Mapped[dt.date] = mapped_column(Date)
    customer_id: Mapped[int] = mapped_column(BigIntFK, ForeignKey("parties.id"))
    site_id: Mapped[int | None] = mapped_column(BigIntFK, ForeignKey("sites.id"), nullable=True)
    period_from: Mapped[dt.date] = mapped_column(Date)
    period_to: Mapped[dt.date] = mapped_column(Date)
    subtotal: Mapped[Decimal] = mapped_column(Money)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)
    tax_amount: Mapped[Decimal] = mapped_column(Money, default=0)
    total: Mapped[Decimal] = mapped_column(Money)
    is_tax_invoice: Mapped[bool] = mapped_column(Boolean, default=False)
    journal_id: Mapped[int | None] = mapped_column(BigIntFK, ForeignKey("journal_entries.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (Index("ix_invoices_customer_date", "customer_id", "date"),)
