import datetime as dt
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.core.types import MoneyIn


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    type: str
    is_system: bool
    parent_id: int | None


class JournalLineOut(BaseModel):
    account_id: int
    account_code: str
    account_name: str
    debit: Decimal
    credit: Decimal
    vehicle_id: int | None


class JournalOut(BaseModel):
    id: int
    date: dt.date
    source_type: str
    source_id: int | None
    narration: str
    reverses_id: int | None
    lines: list[JournalLineOut]


class TrialBalanceRow(BaseModel):
    account_id: int
    code: str
    name: str
    type: str
    debit: Decimal
    credit: Decimal


class TrialBalanceOut(BaseModel):
    upto: dt.date | None
    rows: list[TrialBalanceRow]
    total_debit: Decimal
    total_credit: Decimal
    balanced: bool


class LockIn(BaseModel):
    month: dt.date  # any day in the month to lock


class LockOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    month: dt.date
    locked_by: int | None
    locked_at: dt.datetime


class OpeningBalanceIn(BaseModel):
    date: dt.date
    kind: Literal["party", "staff", "money_account"]
    ref_id: int
    # 'dr': customer owes us / staff advance / cash+bank in hand. 'cr': we owe a supplier / staff wages due.
    side: Literal["dr", "cr"]
    amount: MoneyIn  # 0 clears an earlier entry


class OpeningBalanceOut(BaseModel):
    kind: str
    ref_id: int
    name: str
    date: dt.date
    side: str
    amount: Decimal
