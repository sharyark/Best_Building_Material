import datetime as dt
import uuid
from decimal import Decimal
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.common_schemas import VoidIn  # noqa: F401
from app.modules.deliveries.schemas import DeliveryOut
from app.modules.rentals.schemas import RentalOut


class InvoiceIn(BaseModel):
    date: dt.date
    customer_id: int
    site_id: int | None = None
    period_from: dt.date
    period_to: dt.date
    delivery_ids: list[int] = []
    rental_ids: list[int] = []
    is_tax_invoice: bool = False
    tax_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100, max_digits=5, decimal_places=2)
    notes: str | None = None
    client_ref: uuid.UUID | None = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        if not self.delivery_ids and not self.rental_ids:
            raise ValueError("Pick at least one challan or rental")
        if self.period_to < self.period_from:
            raise ValueError("period_to is before period_from")
        if self.is_tax_invoice and self.tax_rate <= 0:
            raise ValueError("A tax invoice needs a tax_rate above 0")
        return self


class InvoiceLineOut(BaseModel):
    kind: Literal["challan", "rental"]
    doc_id: int
    doc_no: str
    date: dt.date
    description: str
    qty: Decimal
    unit: str
    rate: Decimal
    amount: Decimal


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    invoice_no: str
    date: dt.date
    customer_id: int
    site_id: int | None
    period_from: dt.date
    period_to: dt.date
    subtotal: Decimal
    tax_rate: Decimal
    tax_amount: Decimal
    total: Decimal
    is_tax_invoice: bool
    journal_id: int | None
    status: str
    void_reason: str | None
    notes: str | None


class InvoiceDetailOut(InvoiceOut):
    lines: list[InvoiceLineOut]


class UninvoicedOut(BaseModel):
    deliveries: list[DeliveryOut]
    rentals: list[RentalOut]
