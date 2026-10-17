import datetime as dt
import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.core.types import PositiveMoney, PositiveQty
from app.modules.common_schemas import VoidIn  # noqa: F401


class RentalIn(BaseModel):
    date: dt.date
    customer_id: int
    site_id: int | None = None
    vehicle_id: int
    operator_id: int | None = None
    basis: Literal["hour", "trip", "day"]
    qty: PositiveQty
    rate: PositiveMoney
    notes: str | None = None
    client_ref: uuid.UUID | None = None


class RentalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rental_no: str
    date: dt.date
    customer_id: int
    site_id: int | None
    vehicle_id: int
    operator_id: int | None
    basis: str
    qty: Decimal
    rate: Decimal
    amount: Decimal
    invoice_id: int | None
    journal_id: int | None
    status: str
    void_reason: str | None
    notes: str | None
