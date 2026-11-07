import datetime as dt
import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.core.types import MoneyIn, PositiveMoney, PositiveQty
from app.modules.common_schemas import EditableIn, EditInfoOut, VoidIn  # noqa: F401


class ChallanPaymentIn(BaseModel):
    """Paid on the spot (in full or in part): saved as a receipt with the challan."""

    amount: PositiveMoney
    money_account_id: int
    mode: Literal["cash", "bank", "cheque", "online"] = "cash"


class DeliveryIn(EditableIn):
    date: dt.date
    customer_id: int
    site_id: int | None = None
    material_id: int
    qty: PositiveQty  # number of loads when load_unit is set (or the material is sold by the trolley)
    sale_rate: PositiveMoney | None = None  # per full load/unit; omitted -> customer rate card / material default
    load_unit: Literal["dumper", "bucket"] | None = None
    load_size: Literal["full", "half"] = "full"
    freight_amount: MoneyIn = Decimal("0")
    extra_material_id: int | None = None
    extra_qty: PositiveQty | None = None
    extra_rate: PositiveMoney | None = None
    vehicle_id: int | None = None
    driver_id: int | None = None
    # Driver's pay for this challan; omitted -> trips x the driver's usual trip rate (Masters > Staff).
    trip_pay: MoneyIn | None = None
    notes: str | None = None
    # The UI asks "yard has only X, continue?"; confirming sends true.
    allow_negative_stock: bool = False
    # Only used when creating; later payments are entered on the Payments screen.
    payment: ChallanPaymentIn | None = None
    # False = an order: saved and printable, but not in the khata, trip pay or stock until marked delivered.
    # Defaults to true so API callers that predate orders keep posting at once.
    delivered: bool = True
    client_ref: uuid.UUID | None = None


class DeliverIn(BaseModel):
    allow_negative_stock: bool = False


class DeliveryOut(EditInfoOut):
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
    load_unit: str | None
    load_size: str
    stock_qty: Decimal
    cost_rate: Decimal
    cost_amount: Decimal
    extra_material_id: int | None
    extra_qty: Decimal | None
    extra_unit: str | None
    extra_rate: Decimal | None
    extra_amount: Decimal
    extra_cost_amount: Decimal
    vehicle_id: int | None
    driver_id: int | None
    trips: int
    trip_pay: Decimal
    invoice_id: int | None
    receipt_id: int | None
    journal_id: int | None
    status: str
    void_reason: str | None
    notes: str | None
    delivered: bool
    delivered_at: dt.datetime | None
