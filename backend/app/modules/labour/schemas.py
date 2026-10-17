import datetime as dt
import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.types import MoneyIn, QtyIn
from app.modules.common_schemas import VoidIn  # noqa: F401

AttendanceStatus = Literal["present", "half", "absent"]


class AttendanceIn(BaseModel):
    date: dt.date
    staff_id: int
    status: AttendanceStatus
    overtime_hours: QtyIn = Decimal("0")
    site_id: int | None = None
    vehicle_id: int | None = None


class AttendanceBulkIn(BaseModel):
    entries: list[AttendanceIn] = Field(min_length=1, max_length=500)


class AttendanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: dt.date
    staff_id: int
    status: AttendanceStatus
    overtime_hours: Decimal
    site_id: int | None
    vehicle_id: int | None
    journal_id: int | None


class SettlementPreview(BaseModel):
    staff_id: int
    period_from: dt.date
    period_to: dt.date
    wage_type: str
    days: Decimal
    trips: int
    gross: Decimal
    accrues_on_settlement: bool  # daily labour already accrued per attendance day
    advances_in_period: Decimal
    current_balance: Decimal  # debit-positive: negative = payable to the worker


class SettlementIn(BaseModel):
    staff_id: int
    period_from: dt.date
    period_to: dt.date
    deductions: MoneyIn = Decimal("0")
    advances_adjusted: MoneyIn | None = None  # default: advances paid in the period
    notes: str | None = None
    client_ref: uuid.UUID | None = None


class SettlementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    staff_id: int
    period_from: dt.date
    period_to: dt.date
    days: Decimal
    trips: int
    gross: Decimal
    advances_adjusted: Decimal
    deductions: Decimal
    net_payable: Decimal
    journal_id: int | None
    status: str
    void_reason: str | None
    notes: str | None
