import datetime as dt
import uuid
from decimal import Decimal
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, model_validator

from app.core.types import PositiveMoney
from app.modules.common_schemas import VoidIn  # noqa: F401


class PaymentIn(BaseModel):
    date: dt.date
    direction: Literal["in", "out"]
    party_id: int | None = None
    staff_id: int | None = None
    money_account_id: int
    mode: Literal["cash", "bank", "cheque", "online"]
    # Staff payments: 'advance' (loan against future wages) or 'salary' (pay-out of earned wages).
    purpose: Literal["general", "advance", "salary"] = "general"
    ref_no: str | None = None
    amount: PositiveMoney
    notes: str | None = None
    client_ref: uuid.UUID | None = None

    @model_validator(mode="after")
    def _one_counterparty(self) -> Self:
        if (self.party_id is None) == (self.staff_id is None):
            raise ValueError("Give exactly one of party_id or staff_id")
        if self.purpose != "general" and self.staff_id is None:
            raise ValueError("advance/salary payments are for staff")
        return self


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    voucher_no: str
    date: dt.date
    direction: str
    party_id: int | None
    staff_id: int | None
    money_account_id: int
    mode: str
    purpose: str
    ref_no: str | None
    amount: Decimal
    journal_id: int | None
    status: str
    void_reason: str | None
    notes: str | None
