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
    trip_pay: Decimal  # already added to the khata trip by trip; not part of `gross`
    absent_days: Decimal  # absent = 1, half day = 0.5; for the "Chutti" deduction
    day_rate: Decimal | None  # monthly pay / 30: what one day of chutti costs; None for daily/per-trip pay
    gross: Decimal
    accrues_on_settlement: bool  # daily labour already accrued per attendance day
    advances_in_period: Decimal
    current_balance: Decimal  # debit-positive: negative = payable to the worker
    # Salary side of the khata at the end of the period, before this settlement (trip money left out):
    # + = they owe us (advances, also from earlier months), - = we still owe them from before.
    carried_forward: Decimal
    # What is left to pay after this settlement, before any deduction: (gross if it posts now) - carried_forward.
    # Negative = nothing to pay; they still owe that much, and it comes off next month.
    net_before_deductions: Decimal


class SettlementIn(BaseModel):
    staff_id: int
    period_from: dt.date
    period_to: dt.date
    deductions: MoneyIn = Decimal("0")
    deduction_reason: str | None = Field(default=None, max_length=120)
    # No advances field: the settlement takes the advances actually entered in Payments for the period,
    # so the settlement and the khata can never disagree.
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
    deduction_reason: str | None
    net_payable: Decimal
    journal_id: int | None
    status: str
    void_reason: str | None
    notes: str | None
