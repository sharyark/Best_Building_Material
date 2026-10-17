import datetime as dt
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, BigIntFK, BigIntPK, Money, Qty, TimestampMixin
from app.modules.common_models import TxnMixin


class Purchase(Base, TimestampMixin, TxnMixin):
    __tablename__ = "purchases"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    bill_no: Mapped[str] = mapped_column(String(30), unique=True)
    supplier_slip_no: Mapped[str | None] = mapped_column(String(40), nullable=True)
    date: Mapped[dt.date] = mapped_column(Date)
    supplier_id: Mapped[int] = mapped_column(BigIntFK, ForeignKey("parties.id"))
    total: Mapped[Decimal] = mapped_column(Money, default=0)
    vehicle_id: Mapped[int | None] = mapped_column(BigIntFK, ForeignKey("vehicles.id"), nullable=True)
    driver_id: Mapped[int | None] = mapped_column(BigIntFK, ForeignKey("staff.id"), nullable=True)
    transport_by: Mapped[str] = mapped_column(String(10), default="supplier")  # own | supplier
    journal_id: Mapped[int | None] = mapped_column(BigIntFK, ForeignKey("journal_entries.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    lines: Mapped[list["PurchaseLine"]] = relationship(
        back_populates="purchase", cascade="all, delete-orphan", order_by="PurchaseLine.id"
    )

    __table_args__ = (Index("ix_purchases_supplier_date", "supplier_id", "date"),)


class PurchaseLine(Base):
    __tablename__ = "purchase_lines"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    purchase_id: Mapped[int] = mapped_column(BigIntFK, ForeignKey("purchases.id"), index=True)
    material_id: Mapped[int] = mapped_column(BigIntFK, ForeignKey("materials.id"))
    qty: Mapped[Decimal] = mapped_column(Qty)
    rate: Mapped[Decimal] = mapped_column(Money)
    amount: Mapped[Decimal] = mapped_column(Money)

    purchase: Mapped[Purchase] = relationship(back_populates="lines")
