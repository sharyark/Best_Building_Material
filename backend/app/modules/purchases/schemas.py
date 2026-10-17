import datetime as dt
import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.types import PositiveMoney, PositiveQty
from app.modules.common_schemas import VoidIn  # noqa: F401  (re-exported for the router)


class PurchaseLineIn(BaseModel):
    material_id: int
    qty: PositiveQty
    rate: PositiveMoney


class PurchaseIn(BaseModel):
    date: dt.date
    supplier_id: int
    supplier_slip_no: str | None = Field(default=None, max_length=40)
    vehicle_id: int | None = None
    driver_id: int | None = None
    transport_by: Literal["own", "supplier"] = "supplier"
    notes: str | None = None
    lines: list[PurchaseLineIn] = Field(min_length=1)
    client_ref: uuid.UUID | None = None


class PurchaseLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    material_id: int
    qty: Decimal
    rate: Decimal
    amount: Decimal


class PurchaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    bill_no: str
    supplier_slip_no: str | None
    date: dt.date
    supplier_id: int
    total: Decimal
    vehicle_id: int | None
    driver_id: int | None
    transport_by: str
    status: str
    void_reason: str | None
    notes: str | None
    journal_id: int | None
    lines: list[PurchaseLineOut]
