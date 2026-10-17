import datetime as dt
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.types import MoneyIn, PositiveMoney, PositiveQty

PartyType = Literal["customer", "supplier", "both"]
Unit = Literal["trolley", "cft", "ton", "bag", "piece", "brass"]
VehicleType = Literal["tractor_trolley", "dumper", "loader"]
StaffRole = Literal["driver", "operator", "labour", "helper", "munshi"]
WageType = Literal["monthly", "daily", "per_trip"]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PartyIn(BaseModel):
    type: PartyType
    name: str = Field(min_length=1, max_length=150)
    phone: str | None = Field(default=None, max_length=30)
    address: str | None = None
    tax_no: str | None = Field(default=None, max_length=40)


class PartyUpdate(BaseModel):
    type: PartyType | None = None
    name: str | None = Field(default=None, min_length=1, max_length=150)
    phone: str | None = Field(default=None, max_length=30)
    address: str | None = None
    tax_no: str | None = Field(default=None, max_length=40)
    is_active: bool | None = None


class PartyOut(ORM):
    id: int
    type: PartyType
    name: str
    phone: str | None
    address: str | None
    tax_no: str | None
    account_id: int | None
    is_active: bool
    balance: Decimal | None = None  # debit-positive; only filled with ?with_balance=true


class SiteIn(BaseModel):
    party_id: int
    name: str = Field(min_length=1, max_length=150)
    address: str | None = None


class SiteUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    address: str | None = None


class SiteOut(ORM):
    id: int
    party_id: int
    name: str
    address: str | None


class MaterialIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    unit: Unit
    default_sale_rate: MoneyIn = Decimal("0")
    default_purchase_rate: MoneyIn = Decimal("0")
    hsn_code: str | None = Field(default=None, max_length=20)


class MaterialUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    unit: Unit | None = None
    default_sale_rate: MoneyIn | None = None
    default_purchase_rate: MoneyIn | None = None
    hsn_code: str | None = Field(default=None, max_length=20)
    is_active: bool | None = None


class MaterialOut(ORM):
    id: int
    name: str
    unit: Unit
    default_sale_rate: Decimal
    default_purchase_rate: Decimal
    hsn_code: str | None
    is_active: bool


class RateCardIn(BaseModel):
    party_id: int
    material_id: int
    rate: PositiveMoney
    effective_from: dt.date


class RateCardOut(ORM):
    id: int
    party_id: int
    material_id: int
    rate: Decimal
    effective_from: dt.date


class RateLookup(BaseModel):
    rate: Decimal
    source: Literal["rate_card", "default"]


class VehicleIn(BaseModel):
    type: VehicleType
    reg_no: str | None = Field(default=None, max_length=30)
    name: str = Field(min_length=1, max_length=80)
    capacity: PositiveQty | None = None
    meter_type: Literal["km", "hours"] = "km"


class VehicleUpdate(BaseModel):
    type: VehicleType | None = None
    reg_no: str | None = Field(default=None, max_length=30)
    name: str | None = Field(default=None, min_length=1, max_length=80)
    capacity: PositiveQty | None = None
    meter_type: Literal["km", "hours"] | None = None
    is_active: bool | None = None


class VehicleOut(ORM):
    id: int
    type: VehicleType
    reg_no: str | None
    name: str
    capacity: Decimal | None
    meter_type: str
    is_active: bool


class StaffIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    phone: str | None = Field(default=None, max_length=30)
    role: StaffRole
    wage_type: WageType
    wage_amount: MoneyIn = Decimal("0")
    default_vehicle_id: int | None = None


class StaffUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    phone: str | None = Field(default=None, max_length=30)
    role: StaffRole | None = None
    wage_type: WageType | None = None
    wage_amount: MoneyIn | None = None
    default_vehicle_id: int | None = None
    is_active: bool | None = None


class StaffOut(ORM):
    id: int
    name: str
    phone: str | None
    role: StaffRole
    wage_type: WageType
    wage_amount: Decimal
    default_vehicle_id: int | None
    account_id: int | None
    is_active: bool
    balance: Decimal | None = None  # debit-positive: negative = we owe them, positive = advance given


class MoneyAccountIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    kind: Literal["cash", "bank", "wallet"] = "cash"


class MoneyAccountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    is_active: bool | None = None


class MoneyAccountOut(ORM):
    id: int
    name: str
    kind: str
    account_id: int | None
    is_active: bool
    balance: Decimal | None = None
