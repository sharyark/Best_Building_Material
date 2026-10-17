import datetime as dt
from decimal import Decimal

from sqlalchemy import BigInteger, Date, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, BigIntFK, BigIntPK, Money, Qty, Rate, TimestampMixin


class StockItem(Base):
    """Live yard balance per material. Maintained only by the stock service."""

    __tablename__ = "stock_items"

    material_id: Mapped[int] = mapped_column(BigIntFK, ForeignKey("materials.id"), primary_key=True)
    qty_on_hand: Mapped[Decimal] = mapped_column(Qty, default=0)
    avg_cost: Mapped[Decimal] = mapped_column(Rate, default=0)
    value: Mapped[Decimal] = mapped_column(Money, default=0)


class StockMove(Base):
    """Signed ledger of stock changes. A reversal is a move with negated quantities."""

    __tablename__ = "stock_moves"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    date: Mapped[dt.date] = mapped_column(Date)
    material_id: Mapped[int] = mapped_column(BigIntFK, ForeignKey("materials.id"))
    qty_in: Mapped[Decimal] = mapped_column(Qty, default=0)
    qty_out: Mapped[Decimal] = mapped_column(Qty, default=0)
    rate: Mapped[Decimal] = mapped_column(Rate, default=0)
    value: Mapped[Decimal] = mapped_column(Money, default=0)  # signed effect on stock value
    source_type: Mapped[str] = mapped_column(String(15))  # purchase|delivery|adjustment|opening
    source_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reverses_id: Mapped[int | None] = mapped_column(BigIntFK, ForeignKey("stock_moves.id"), nullable=True, unique=True)

    __table_args__ = (
        Index("ix_stock_moves_material_date", "material_id", "date"),
        Index("ix_stock_moves_source", "source_type", "source_id"),
    )


class StockCount(Base, TimestampMixin):
    __tablename__ = "stock_counts"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    date: Mapped[dt.date] = mapped_column(Date)
    material_id: Mapped[int] = mapped_column(BigIntFK, ForeignKey("materials.id"))
    system_qty: Mapped[Decimal] = mapped_column(Qty)
    physical_qty: Mapped[Decimal] = mapped_column(Qty)
    diff: Mapped[Decimal] = mapped_column(Qty)
    journal_id: Mapped[int | None] = mapped_column(BigIntFK, ForeignKey("journal_entries.id"), nullable=True)
