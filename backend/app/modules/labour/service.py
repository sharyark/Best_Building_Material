import datetime as dt
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.accounting import rules
from app.accounting.balances import balance_of
from app.accounting.chart import Chart, Code
from app.accounting.posting import ensure_period_open, post, reverse
from app.core.config import get_settings
from app.core.db import ZERO
from app.core.errors import Conflict, NotFound
from app.core.money import money
from app.core.money import qty as q3
from app.modules.common import ensure_active, find_by_client_ref, get_or_404, mark_void
from app.modules.deliveries.models import Delivery
from app.modules.labour.models import Attendance, WageSettlement
from app.modules.labour.schemas import AttendanceIn, SettlementIn, SettlementPreview
from app.modules.masters.models import Site, Staff, Vehicle
from app.modules.payments.models import Payment
from app.modules.purchases.models import Purchase

DAY_FACTOR = {"present": Decimal("1"), "half": Decimal("0.5"), "absent": Decimal("0")}


def daily_wage(staff: Staff, status: str, overtime_hours: Decimal) -> Decimal:
    s = get_settings()
    base = staff.wage_amount * DAY_FACTOR[status]
    hourly = staff.wage_amount / s.workday_hours
    return money(base + overtime_hours * hourly * s.overtime_multiplier)


def _same(att: Attendance, data: AttendanceIn) -> bool:
    return (
        att.status == data.status
        and att.overtime_hours == data.overtime_hours
        and att.site_id == data.site_id
        and att.vehicle_id == data.vehicle_id
    )


def save_attendance(db: Session, entries: list[AttendanceIn]) -> list[Attendance]:
    """Upsert one row per (date, worker). Daily-wage workers accrue that day's wage in the journal."""
    chart = Chart(db)
    saved = []
    for data in entries:
        staff = db.get(Staff, data.staff_id)
        if staff is None:
            raise NotFound(f"Staff {data.staff_id} not found")
        if data.site_id and not db.get(Site, data.site_id):
            raise NotFound("Site not found")
        if data.vehicle_id and not db.get(Vehicle, data.vehicle_id):
            raise NotFound("Vehicle not found")
        ensure_period_open(db, data.date)
        att = db.scalar(select(Attendance).where(Attendance.date == data.date, Attendance.staff_id == data.staff_id))
        if att is not None and _same(att, data):
            saved.append(att)
            continue
        if att is None:
            att = Attendance(date=data.date, staff_id=data.staff_id, status=data.status)
            db.add(att)
        elif att.journal_id:
            reverse(db, att.journal_id, reason="attendance changed")
            att.journal_id = None
        att.status = data.status
        att.overtime_hours = data.overtime_hours
        att.site_id = data.site_id
        att.vehicle_id = data.vehicle_id
        db.flush()
        amount = daily_wage(staff, data.status, data.overtime_hours) if staff.wage_type == "daily" else ZERO
        if amount > 0:
            entry = post(
                db,
                date=data.date,
                source_type="attendance",
                source_id=att.id,
                narration=f"Wage {staff.name} {data.date:%d-%m-%Y} ({data.status})",
                lines=rules.labour_wage(chart, staff.account_id, amount, data.vehicle_id or staff.default_vehicle_id),
            )
            att.journal_id = entry.id
        saved.append(att)
    return saved


def list_attendance(db: Session, date_from: dt.date, date_to: dt.date, staff_id: int | None = None):
    stmt = select(Attendance).where(Attendance.date >= date_from, Attendance.date <= date_to)
    if staff_id:
        stmt = stmt.where(Attendance.staff_id == staff_id)
    return db.scalars(stmt.order_by(Attendance.date, Attendance.staff_id)).all()


def preview(db: Session, staff_id: int, period_from: dt.date, period_to: dt.date) -> SettlementPreview:
    staff = get_or_404(db, Staff, staff_id, "Staff")
    rows = db.scalars(
        select(Attendance).where(
            Attendance.staff_id == staff_id, Attendance.date >= period_from, Attendance.date <= period_to
        )
    ).all()
    days = q3(sum((DAY_FACTOR[a.status] for a in rows), ZERO))
    trips = (
        db.scalar(
            select(func.count())
            .select_from(Delivery)
            .where(
                Delivery.driver_id == staff_id,
                Delivery.status == "active",
                Delivery.date >= period_from,
                Delivery.date <= period_to,
            )
        )
        or 0
    )
    trips += (
        db.scalar(
            select(func.count())
            .select_from(Purchase)
            .where(
                Purchase.driver_id == staff_id,
                Purchase.transport_by == "own",
                Purchase.status == "active",
                Purchase.date >= period_from,
                Purchase.date <= period_to,
            )
        )
        or 0
    )
    if staff.wage_type == "monthly":
        gross = money(staff.wage_amount)
    elif staff.wage_type == "per_trip":
        gross = money(staff.wage_amount * trips)
    else:
        gross = money(sum((daily_wage(staff, a.status, a.overtime_hours) for a in rows), ZERO))
    advances = db.scalar(
        select(func.sum(Payment.amount)).where(
            Payment.staff_id == staff_id,
            Payment.purpose == "advance",
            Payment.direction == "out",
            Payment.status == "active",
            Payment.date >= period_from,
            Payment.date <= period_to,
        )
    )
    return SettlementPreview(
        staff_id=staff_id,
        period_from=period_from,
        period_to=period_to,
        wage_type=staff.wage_type,
        days=days,
        trips=trips,
        gross=gross,
        accrues_on_settlement=staff.wage_type != "daily",
        advances_in_period=money(advances or 0),
        current_balance=balance_of(db, staff.account_id),
    )


def create_settlement(db: Session, data: SettlementIn) -> tuple[WageSettlement, bool]:
    if existing := find_by_client_ref(db, WageSettlement, data.client_ref):
        return existing, False
    if data.period_to < data.period_from:
        raise Conflict("Period end is before its start", code="BAD_PERIOD")
    staff = get_or_404(db, Staff, data.staff_id, "Staff")
    overlap = db.scalar(
        select(WageSettlement.id).where(
            WageSettlement.staff_id == data.staff_id,
            WageSettlement.status == "active",
            WageSettlement.period_from <= data.period_to,
            WageSettlement.period_to >= data.period_from,
        )
    )
    if overlap:
        raise Conflict("An active settlement already covers part of this period", code="PERIOD_OVERLAP")
    ensure_period_open(db, data.period_to)
    pv = preview(db, data.staff_id, data.period_from, data.period_to)
    advances = data.advances_adjusted if data.advances_adjusted is not None else pv.advances_in_period
    settlement = WageSettlement(
        staff_id=staff.id,
        period_from=data.period_from,
        period_to=data.period_to,
        days=pv.days,
        trips=pv.trips,
        gross=pv.gross,
        advances_adjusted=advances,
        deductions=data.deductions,
        net_payable=money(pv.gross - advances - data.deductions),
        notes=data.notes,
        client_ref=data.client_ref,
    )
    db.add(settlement)
    db.flush()
    chart = Chart(db)
    if pv.accrues_on_settlement:
        lines = rules.salary(chart, staff.account_id, pv.gross, data.deductions, staff.default_vehicle_id)
    else:
        # Daily wages were accrued per attendance day; only a deduction needs posting now.
        lines = rules.salary(
            chart, staff.account_id, ZERO, data.deductions, staff.default_vehicle_id, expense_code=Code.LABOUR_WAGES
        )
    if any(line.debit or line.credit for line in lines):
        entry = post(
            db,
            date=data.period_to,
            source_type="wage_settlement",
            source_id=settlement.id,
            narration=f"Wage settlement {staff.name} {data.period_from:%d-%m-%Y} to {data.period_to:%d-%m-%Y}",
            lines=lines,
        )
        settlement.journal_id = entry.id
    return settlement, True


def void_settlement(db: Session, settlement_id: int, reason: str, user_id: int | None) -> WageSettlement:
    settlement = get_or_404(db, WageSettlement, settlement_id, "Settlement")
    ensure_active(settlement)
    ensure_period_open(db, settlement.period_to)
    if settlement.journal_id:
        reverse(db, settlement.journal_id, reason=reason)
    mark_void(settlement, reason, user_id)
    return settlement


def list_settlements(db: Session, staff_id: int | None, status: str | None):
    stmt = select(WageSettlement).order_by(WageSettlement.period_to.desc(), WageSettlement.id.desc())
    if staff_id:
        stmt = stmt.where(WageSettlement.staff_id == staff_id)
    if status:
        stmt = stmt.where(WageSettlement.status == status)
    return db.scalars(stmt.limit(500)).all()
