import datetime as dt
import uuid
from decimal import Decimal
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, model_validator

from app.core.types import PositiveMoney, PositiveQty, QtyIn
from app.modules.common_schemas import VoidIn  # noqa: F401

Category = Literal["diesel", "repair", "tyre", "insurance", "toll", "office", "misc"]


class ExpenseIn(BaseModel):
    date: dt.date
    category: Category
    vehicle_id: int | None = None
    amount: PositiveMoney
    litres: PositiveQty | None = None
    meter_reading: QtyIn | None = None
    paid_via: Literal["money_account", "party_credit"]
    money_account_id: int | None = None
    party_id: int | None = None  # the pump / workshop when bought on credit
    notes: str | None = None
    client_ref: uuid.UUID | None = None

    @model_validator(mode="after")
    def _check_payment_source(self) -> Self:
        if self.paid_via == "money_account" and self.money_account_id is None:
            raise ValueError("money_account_id is required when paid from cash/bank")
        if self.paid_via == "party_credit" and self.party_id is None:
            raise ValueError("party_id (the pump/workshop) is required for credit purchases")
        if self.litres is not None and self.category != "diesel":
            raise ValueError("litres only applies to diesel")
        return self


class ExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    voucher_no: str
    date: dt.date
    category: str
    vehicle_id: int | None
    amount: Decimal
    litres: Decimal | None
    meter_reading: Decimal | None
    paid_via: str
    money_account_id: int | None
    party_id: int | None
    journal_id: int | None
    status: str
    void_reason: str | None
    notes: str | None
