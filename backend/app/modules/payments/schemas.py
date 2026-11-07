import datetime as dt
import uuid
from decimal import Decimal
from typing import Literal, Self

from pydantic import ConfigDict, model_validator

from app.core.types import MoneyIn, PositiveMoney
from app.modules.common_schemas import EditableIn, EditInfoOut, VoidIn  # noqa: F401


class PaymentIn(EditableIn):
    date: dt.date
    direction: Literal["in", "out"]
    party_id: int | None = None
    staff_id: int | None = None
    money_account_id: int
    mode: Literal["cash", "bank", "cheque", "online"]
    # Staff payments: 'advance' (loan against future wages), 'salary' (pay-out of earned wages) or
    # 'trip' (pay-out of trip money, kept apart so the salary side of the khata is untouched), or
    # 'sal_trip' (both at once: `trip_amount` of it is trip money, the rest salary).
    purpose: Literal["general", "advance", "salary", "trip", "sal_trip"] = "general"
    ref_no: str | None = None
    amount: PositiveMoney
    trip_amount: MoneyIn | None = None
    notes: str | None = None
    client_ref: uuid.UUID | None = None

    @model_validator(mode="after")
    def _one_counterparty(self) -> Self:
        if (self.party_id is None) == (self.staff_id is None):
            raise ValueError("Give exactly one of party_id or staff_id")
        if self.purpose != "general" and self.staff_id is None:
            raise ValueError("advance, salary and trip payments are for staff")
        return self


class PaymentOut(EditInfoOut):
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
    trip_amount: Decimal
    journal_id: int | None
    status: str
    void_reason: str | None
    notes: str | None
