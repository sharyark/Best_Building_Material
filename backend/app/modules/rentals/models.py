import datetime as dt
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, BigIntFK, BigIntPK, Money, Qty, TimestampMixin
from app.modules.common_models import TxnMixin


class Rental(Base, TimestampMixin, TxnMixin):
    __tablename__ = "rentals"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    rental_no: Mapped[str] = mapped_column(String(30), unique=True)
    date: Mapped[dt.date] = mapped_column(Date)
    customer_id: Mapped[int] = mapped_column(BigIntFK, ForeignKey("parties.id"))
    site_id: Mapped[int | None] = mapped_column(BigIntFK, ForeignKey("sites.id"), nullable=True)
    vehicle_id: Mapped[int] = mapped_column(BigIntFK, ForeignKey("vehicles.id"))
    operator_id: Mapped[int | None] = mapped_column(BigIntFK, ForeignKey("staff.id"), nullable=True)
    basis: Mapped[str] = mapped_column(String(5))  # hour | trip | day
    qty: Mapped[Decimal] = mapped_column(Qty)
    rate: Mapped[Decimal] = mapped_column(Money)
    amount: Mapped[Decimal] = mapped_column(Money)
    invoice_id: Mapped[int | None] = mapped_column(BigIntFK, ForeignKey("invoices.id"), nullable=True)
    journal_id: Mapped[int | None] = mapped_column(BigIntFK, ForeignKey("journal_entries.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_rentals_customer_date", "customer_id", "date"),
        Index("ix_rentals_vehicle_date", "vehicle_id", "date"),
    )
