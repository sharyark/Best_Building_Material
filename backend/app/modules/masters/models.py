import datetime as dt
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, BigIntFK, BigIntPK, Money, Qty, TimestampMixin

PARTY_TYPES = ("customer", "supplier", "both")
UNITS = ("trolley", "cft", "ton", "bag", "piece", "brass")
VEHICLE_TYPES = ("tractor_trolley", "dumper", "loader")
STAFF_ROLES = ("driver", "operator", "labour", "helper", "munshi")
WAGE_TYPES = ("monthly", "daily", "per_trip")


class Party(Base, TimestampMixin):
    __tablename__ = "parties"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    type: Mapped[str] = mapped_column(String(10))
    name: Mapped[str] = mapped_column(String(150))
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    tax_no: Mapped[str | None] = mapped_column(String(40), nullable=True)
    account_id: Mapped[int | None] = mapped_column(BigIntFK, ForeignKey("accounts.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Site(Base, TimestampMixin):
    __tablename__ = "sites"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    party_id: Mapped[int] = mapped_column(BigIntFK, ForeignKey("parties.id"), index=True)
    name: Mapped[str] = mapped_column(String(150))
    address: Mapped[str | None] = mapped_column(Text, nullable=True)


class Material(Base, TimestampMixin):
    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    unit: Mapped[str] = mapped_column(String(10))
    default_sale_rate: Mapped[Decimal] = mapped_column(Money, default=0)
    default_purchase_rate: Mapped[Decimal] = mapped_column(Money, default=0)
    hsn_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Loose material sold by the dumper or loader bucket: how much stock (in `unit`) one full load holds,
    # and the sale rate for one full load. Unset means the material can't be sold that way.
    dumper_qty: Mapped[Decimal | None] = mapped_column(Qty, nullable=True)
    dumper_rate: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    bucket_qty: Mapped[Decimal | None] = mapped_column(Qty, nullable=True)
    bucket_rate: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class RateCard(Base, TimestampMixin):
    __tablename__ = "rate_cards"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    party_id: Mapped[int] = mapped_column(BigIntFK, ForeignKey("parties.id"))
    material_id: Mapped[int] = mapped_column(BigIntFK, ForeignKey("materials.id"))
    rate: Mapped[Decimal] = mapped_column(Money)
    effective_from: Mapped[dt.date] = mapped_column(Date)

    __table_args__ = (
        UniqueConstraint("party_id", "material_id", "effective_from", name="uq_rate_cards_party_material_from"),
        Index("ix_rate_cards_lookup", "party_id", "material_id", "effective_from"),
    )


class Vehicle(Base, TimestampMixin):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    type: Mapped[str] = mapped_column(String(20))
    reg_no: Mapped[str | None] = mapped_column(String(30), nullable=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    capacity: Mapped[Decimal | None] = mapped_column(Qty, nullable=True)
    meter_type: Mapped[str] = mapped_column(String(5), default="km")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Staff(Base, TimestampMixin):
    __tablename__ = "staff"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    role: Mapped[str] = mapped_column(String(10))
    wage_type: Mapped[str] = mapped_column(String(10))
    wage_amount: Mapped[Decimal] = mapped_column(Money, default=0)
    default_vehicle_id: Mapped[int | None] = mapped_column(BigIntFK, ForeignKey("vehicles.id"), nullable=True)
    account_id: Mapped[int | None] = mapped_column(BigIntFK, ForeignKey("accounts.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class MoneyAccount(Base, TimestampMixin):
    __tablename__ = "money_accounts"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    kind: Mapped[str] = mapped_column(String(10), default="cash")  # cash | bank | wallet
    account_id: Mapped[int | None] = mapped_column(BigIntFK, ForeignKey("accounts.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
