import datetime as dt
import uuid
from decimal import Decimal
from typing import Literal

from pydantic import ConfigDict

from app.core.types import MoneyIn, PositiveMoney, PositiveQty
from app.modules.common_schemas import EditableIn, EditInfoOut, VoidIn  # noqa: F401


class RentalIn(EditableIn):
    date: dt.date
    customer_id: int
    site_id: int | None = None
    vehicle_id: int
    operator_id: int | None = None
    basis: Literal["hour", "trip", "day"]
    qty: PositiveQty
    rate: PositiveMoney
    # Operator's pay for this job; omitted -> trips x his usual trip rate. 0 = no trip pay.
    trip_pay: MoneyIn | None = None
    notes: str | None = None
    client_ref: uuid.UUID | None = None


class RentalOut(EditInfoOut):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rental_no: str
    date: dt.date
    customer_id: int
    site_id: int | None
    vehicle_id: int
    operator_id: int | None
    trips: int
    trip_pay: Decimal
    basis: str
    qty: Decimal
    rate: Decimal
    amount: Decimal
    invoice_id: int | None
    journal_id: int | None
    status: str
    void_reason: str | None
    notes: str | None
