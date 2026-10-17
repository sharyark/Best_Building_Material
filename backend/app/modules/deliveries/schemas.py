import datetime as dt
import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.core.types import MoneyIn, PositiveMoney, PositiveQty
from app.modules.common_schemas import VoidIn  # noqa: F401


class DeliveryIn(BaseModel):
    date: dt.date
    customer_id: int
    site_id: int | None = None
    material_id: int
    qty: PositiveQty
    sale_rate: PositiveMoney | None = None  # omitted -> customer rate card / material default
    freight_amount: MoneyIn = Decimal("0")
    vehicle_id: int | None = None
    driver_id: int | None = None
    notes: str | None = None
    # The UI asks "yard has only X, continue?"; confirming sends true.
    allow_negative_stock: bool = False
    client_ref: uuid.UUID | None = None


class DeliveryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    challan_no: str
    date: dt.date
    customer_id: int
    site_id: int | None
    material_id: int
    qty: Decimal
    unit: str
    sale_rate: Decimal
    sale_amount: Decimal
    freight_amount: Decimal
    cost_rate: Decimal
    cost_amount: Decimal
    vehicle_id: int | None
    driver_id: int | None
    invoice_id: int | None
    journal_id: int | None
    status: str
    void_reason: str | None
    notes: str | None
