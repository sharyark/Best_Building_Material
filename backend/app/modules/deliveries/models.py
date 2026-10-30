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
    # Sold by the dumper/loader bucket instead of the material's own unit; `qty`/`unit`/`sale_rate` are then
    # in loads, and `stock_qty` is what left the yard in the material's unit.
    load_unit: Mapped[str | None] = mapped_column(String(10), nullable=True)
    load_size: Mapped[str] = mapped_column(String(5), default="full", server_default="full")
    stock_qty: Mapped[Decimal] = mapped_column(Qty)
    cost_rate: Mapped[Decimal] = mapped_column(Rate, default=0)  # avg cost snapshot
    cost_amount: Mapped[Decimal] = mapped_column(Money, default=0)
    # A second material on the same trip, e.g. cement bags on top of a sand trolley.
    extra_material_id: Mapped[int | None] = mapped_column(BigIntFK, ForeignKey("materials.id"), nullable=True)
    extra_qty: Mapped[Decimal | None] = mapped_column(Qty, nullable=True)
    extra_unit: Mapped[str | None] = mapped_column(String(10), nullable=True)
    extra_rate: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    extra_amount: Mapped[Decimal] = mapped_column(Money, default=0, server_default="0")
    extra_cost_amount: Mapped[Decimal] = mapped_column(Money, default=0, server_default="0")
    vehicle_id: Mapped[int | None] = mapped_column(BigIntFK, ForeignKey("vehicles.id"), nullable=True)
    driver_id: Mapped[int | None] = mapped_column(BigIntFK, ForeignKey("staff.id"), nullable=True)
    invoice_id: Mapped[int | None] = mapped_column(BigIntFK, ForeignKey("invoices.id"), nullable=True)
    # Money the customer paid on the spot, entered with the challan as a normal receipt.
    receipt_id: Mapped[int | None] = mapped_column(BigIntFK, ForeignKey("payments.id"), nullable=True)
    journal_id: Mapped[int | None] = mapped_column(BigIntFK, ForeignKey("journal_entries.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_deliveries_customer_date", "customer_id", "date"),
        Index("ix_deliveries_vehicle_date", "vehicle_id", "date"),
        UniqueConstraint("challan_no", name="uq_deliveries_challan_no"),
    )
