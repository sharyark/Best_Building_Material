import datetime as dt
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, BigIntFK, BigIntPK, Money, Qty, Rate, TimestampMixin
from app.modules.common_models import TxnMixin


class Delivery(Base, TimestampMixin, TxnMixin):
    """A challan: one trip of material out of the yard to a customer site."""

    __tablename__ = "deliveries"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    challan_no: Mapped[str] = mapped_column(String(30), unique=True)
    date: Mapped[dt.date] = mapped_column(Date)
    customer_id: Mapped[int] = mapped_column(BigIntFK, ForeignKey("parties.id"))
    site_id: Mapped[int | None] = mapped_column(BigIntFK, ForeignKey("sites.id"), nullable=True)
    material_id: Mapped[int] = mapped_column(BigIntFK, ForeignKey("materials.id"))
    qty: Mapped[Decimal] = mapped_column(Qty)
    unit: Mapped[str] = mapped_column(String(10))
    sale_rate: Mapped[Decimal] = mapped_column(Money)
    sale_amount: Mapped[Decimal] = mapped_column(Money)
    freight_amount: Mapped[Decimal] = mapped_column(Money, default=0)
    cost_rate: Mapped[Decimal] = mapped_column(Rate, default=0)  # avg cost snapshot
    cost_amount: Mapped[Decimal] = mapped_column(Money, default=0)
    vehicle_id: Mapped[int | None] = mapped_column(BigIntFK, ForeignKey("vehicles.id"), nullable=True)
    driver_id: Mapped[int | None] = mapped_column(BigIntFK, ForeignKey("staff.id"), nullable=True)
    invoice_id: Mapped[int | None] = mapped_column(BigIntFK, ForeignKey("invoices.id"), nullable=True)
    journal_id: Mapped[int | None] = mapped_column(BigIntFK, ForeignKey("journal_entries.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_deliveries_customer_date", "customer_id", "date"),
        Index("ix_deliveries_vehicle_date", "vehicle_id", "date"),
        UniqueConstraint("challan_no", name="uq_deliveries_challan_no"),
    )
