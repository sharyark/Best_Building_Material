"""Every report is a query over `journal_lines` (the single source of truth) or the document tables."""

import datetime as dt
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from app.accounting.balances import account_balances, oldest_unpaid_dates
from app.accounting.chart import Code
from app.accounting.models import Account, JournalEntry, JournalLine
from app.core.config import get_settings
from app.core.db import ZERO
from app.core.errors import DomainError, NotFound
from app.core.money import money, qty
from app.modules.deliveries.models import Delivery
from app.modules.expenses.models import Expense
from app.modules.labour.models import Attendance, WageSettlement
from app.modules.masters.models import Material, MoneyAccount, Party, Site, Staff, Vehicle
from app.modules.payments.models import Payment
from app.modules.purchases.models import Purchase, PurchaseLine
from app.modules.rentals.models import Rental
from app.modules.reports.table import Col, ReportTable
from app.modules.stock.models import StockItem, StockMove

SOURCE_LABEL = {
    "purchase": "Purchase",
    "delivery": "Challan",
    "rental": "Rental",
    "invoice": "Invoice tax",
    "payment": "Payment",
    "expense": "Expense",
    "attendance": "Wage",
    "wage_settlement": "Settlement",
    "stock_adjustment": "Stock adj.",
    "opening": "Opening",
    "opening_stock": "Opening stock",
}


def month_start(day: dt.date) -> dt.date:
    return day.replace(day=1)


def default_range(date_from: dt.date | None, date_to: dt.date | None) -> tuple[dt.date, dt.date]:
    today = dt.date.today()
    return date_from or month_start(today), date_to or today


def _range_label(date_from: dt.date, date_to: dt.date) -> str:
    return f"{date_from:%d-%m-%Y} to {date_to:%d-%m-%Y}"


# ---------------------------------------------------------------------------------------------------
# Khata / ledger statements
# ---------------------------------------------------------------------------------------------------
# Shop-floor words for the two sides of a khata, by whose khata it is (no debit/credit on screen).
SIDES = {
    "customer": ("Bill", "Wasool"),  # what they bought / what we received
    "supplier": ("Pay", "Bill"),  # what we paid / what we bought on their bill
    "both": ("Bill / Pay", "Wasool / Bill"),
    "staff": ("Pay", "Kamai"),  # what we paid or advanced / what they earned
}


def ledger(
    db: Session,
    account_id: int,
    title: str,
    date_from: dt.date,
    date_to: dt.date,
    subtitle: str | None = None,
    sides: tuple[str, str] = ("Bill", "Wasool"),
    history: bool = False,
) -> ReportTable:
    """Date-wise entries with a running balance computed by a window function (debit-positive: + = lena).

    An edit or void posts a reversal of the old entry on the same day. By default both halves are left out, so
    the khata shows each document once, as it stands now; the balance is the same either way because the pair
    cancels on that day. `history=True` shows every line (the record itself is never deleted)."""
    running = (
        func.sum(JournalLine.debit - JournalLine.credit)
        .over(order_by=[JournalEntry.date, JournalEntry.id, JournalLine.id])
        .label("balance")
    )
    inner = (
        select(
            JournalEntry.date.label("date"),
            JournalEntry.id.label("jid"),
            JournalEntry.source_type,
            JournalEntry.narration,
            JournalLine.debit,
            JournalLine.credit,
            running,
        )
        .join(JournalEntry, JournalEntry.id == JournalLine.journal_id)
        .where(JournalLine.account_id == account_id)
    )
    if not history:
        reversed_ids = select(JournalEntry.reverses_id).where(JournalEntry.reverses_id.is_not(None))
        inner = inner.where(JournalEntry.reverses_id.is_(None), JournalEntry.id.not_in(reversed_ids))
    inner = inner.subquery()
    lines = db.execute(
        select(inner).where(inner.c.date >= date_from, inner.c.date <= date_to).order_by(inner.c.date, inner.c.jid)
    ).all()
    opening = account_balances(db, [account_id], before=date_from).get(account_id, ZERO)
    rows = [
        {"date": date_from, "type": "Opening", "narration": "Opening balance", "debit": None, "credit": None,
         "balance": opening}
    ]  # fmt: skip
    total_dr = total_cr = ZERO
    for ln in lines:
        total_dr += ln.debit
        total_cr += ln.credit
        rows.append(
            {
                "date": ln.date,
                "type": SOURCE_LABEL.get(ln.source_type, ln.source_type),
                "narration": ln.narration,
                "debit": ln.debit or None,
                "credit": ln.credit or None,
                "balance": Decimal(ln.balance),
            }
        )
    closing = opening + total_dr - total_cr
    return ReportTable(
        title=title,
        subtitle=subtitle or _range_label(date_from, date_to),
        columns=[
            Col("date", "Date", "date"),
            Col("type", "Type"),
            Col("narration", "Details"),
            Col("debit", sides[0], "money"),
            Col("credit", sides[1], "money"),
            Col("balance", "Baqaya", "drcr"),
        ],
        rows=rows,
        totals={"narration": "Kul / aakhri baqaya", "debit": total_dr, "credit": total_cr, "balance": closing},
        meta={"opening": opening, "closing": closing},
    )


def party_khata(db: Session, party_id: int, date_from: dt.date, date_to: dt.date, history: bool = False) -> ReportTable:
    party = db.get(Party, party_id)
    if party is None:
        raise NotFound("Party not found")
    kind = "Supplier" if party.type == "supplier" else "Customer"
    table = ledger(
        db, party.account_id, f"{kind} khata - {party.name}", date_from, date_to, sides=SIDES[party.type],
        history=history,
    )  # fmt: skip
    table.meta.update(party_id=party.id, party_name=party.name, phone=party.phone)
    return table


def staff_khata(db: Session, staff_id: int, date_from: dt.date, date_to: dt.date, history: bool = False) -> ReportTable:
    """Worker / driver khata: ledger plus attendance, wages earned and advances for the period."""
    staff = db.get(Staff, staff_id)
    if staff is None:
        raise NotFound("Staff member not found")
    table = ledger(
        db, staff.account_id, f"Labour khata - {staff.name}", date_from, date_to, sides=SIDES["staff"], history=history
    )
    counts = {"present": 0, "half": 0, "absent": 0}
    for status, n in db.execute(
        select(Attendance.status, func.count())
        .where(Attendance.staff_id == staff_id, Attendance.date >= date_from, Attendance.date <= date_to)
        .group_by(Attendance.status)
    ):
        counts[status] = n
    earned = db.scalar(
        select(func.sum(JournalLine.credit - JournalLine.debit))
        .join(JournalEntry, JournalEntry.id == JournalLine.journal_id)
        .where(
            JournalLine.account_id == staff.account_id,
            JournalEntry.source_type.in_(("attendance", "wage_settlement")),
            JournalEntry.date >= date_from,
            JournalEntry.date <= date_to,
        )
    )
    advances = db.scalar(
        select(func.sum(Payment.amount)).where(
            Payment.staff_id == staff_id, Payment.purpose == "advance", Payment.direction == "out",
            Payment.status == "active", Payment.date >= date_from, Payment.date <= date_to,
        )
    )  # fmt: skip
    trip = trip_money(db, staff, date_from, date_to)
    balance_payable = -table.meta["closing"]
    table.meta.update(
        staff_id=staff.id,
        staff_name=staff.name,
        basic_pay=staff.wage_amount if staff.wage_type == "monthly" else None,
        trips=trip["trips"],
        trip_earned=trip["earned"],
        trip_paid=trip["paid"],
        trip_balance=trip["balance"],
        # What is owed apart from trip money: salary/wages less advances and salary payouts.
        salary_balance=balance_payable - trip["balance"],
        salary_paid=Decimal(
            db.scalar(
                select(func.sum(Payment.amount - Payment.trip_amount)).where(
                    Payment.staff_id == staff_id,
                    Payment.purpose.in_(("salary", "sal_trip")),
                    Payment.direction == "out",
                    Payment.status == "active",
                    Payment.date >= date_from,
                    Payment.date <= date_to,
                )
            )
            or 0
        ),  # fmt: skip
        salary_left=_salary_left(db, staff, balance_payable - trip["balance"], date_from, date_to),
        days_present=counts["present"],
        half_days=counts["half"],
        days_absent=counts["absent"],
        wages_earned=Decimal(earned or 0),
        advances_paid=Decimal(advances or 0),
        balance_payable=balance_payable,
    )
    return table


def _salary_left(db: Session, staff: Staff, salary_balance: Decimal, date_from: dt.date, date_to: dt.date):
    """For a monthly worker before the month is settled: basic pay less what he already owes back (advances).
    Once a settlement in the period has posted the salary, the balance itself is what is left."""
    if staff.wage_type != "monthly":
        return None
    settled = db.scalar(
        select(WageSettlement.id).where(
            WageSettlement.staff_id == staff.id, WageSettlement.status == "active",
            WageSettlement.period_to >= date_from, WageSettlement.period_to <= date_to,
        )
    )  # fmt: skip
    return salary_balance if settled else staff.wage_amount + salary_balance


def trip_money(db: Session, staff: Staff, date_from: dt.date, date_to: dt.date) -> dict:
    """Trip pay is credited inside challan/purchase/rental entries and paid out as 'trip' payments, so it can be
    told apart from salary on the same khata. The balance is as of `date_to`; earned/paid are for the period."""

    def earned(since: dt.date | None) -> Decimal:
        q = (
            select(func.sum(JournalLine.credit - JournalLine.debit))
            .join(JournalEntry, JournalEntry.id == JournalLine.journal_id)
            .where(
                JournalLine.account_id == staff.account_id,
                JournalEntry.source_type.in_(("delivery", "purchase", "rental")),
                JournalEntry.date <= date_to,
            )
        )
        return Decimal(db.scalar(q.where(JournalEntry.date >= since) if since else q) or 0)

    def paid(since: dt.date | None) -> Decimal:
        # A 'salary + trip' payment counts only its trip part here.
        part = case((Payment.purpose == "trip", Payment.amount), else_=Payment.trip_amount)
        q = select(func.sum(part)).where(
            Payment.staff_id == staff.id, Payment.purpose.in_(("trip", "sal_trip")), Payment.direction == "out",
            Payment.status == "active", Payment.date <= date_to,
        )  # fmt: skip
        return Decimal(db.scalar(q.where(Payment.date >= since) if since else q) or 0)

    trips = 0
    for model, who, extra in (
        (Delivery, Delivery.driver_id, [Delivery.delivered.is_(True)]),
        (Purchase, Purchase.driver_id, [Purchase.transport_by == "own"]),
        (Rental, Rental.operator_id, []),
    ):
        trips += db.scalar(
            select(func.coalesce(func.sum(model.trips), 0)).where(
                who == staff.id, model.status == "active", model.trip_pay > 0,
                model.date >= date_from, model.date <= date_to, *extra,
            )
        ) or 0  # fmt: skip
    return {"trips": trips, "earned": earned(date_from), "paid": paid(date_from), "balance": earned(None) - paid(None)}


# ---------------------------------------------------------------------------------------------------
# Outstanding / aging
# ---------------------------------------------------------------------------------------------------
def _age_buckets(daily: list[tuple[dt.date, Decimal, Decimal]], as_of: dt.date) -> dict[str, Decimal]:
    """`daily` = (date, charges, payments) per day. Payments settle the oldest charges first.

    What is left open is bucketed by the age of the charge. Within a day charges go in first,
    so a same-day payment still settles older items rather than netting against today's charge.
    """
    open_items: list[list] = []
    for day, charge, payment in sorted(daily):
        if charge > 0:
            open_items.append([day, charge])
        remaining = payment
        while remaining > 0 and open_items:
            take = min(remaining, open_items[0][1])
            open_items[0][1] -= take
            remaining -= take
            if open_items[0][1] == 0:
                open_items.pop(0)
    buckets = {"b0_30": ZERO, "b31_60": ZERO, "b60_plus": ZERO}
    for day, amount in open_items:
        age = (as_of - day).days
        key = "b0_30" if age <= 30 else "b31_60" if age <= 60 else "b60_plus"
        buckets[key] += amount
    return buckets


def outstanding(db: Session, as_of: dt.date, kind: str = "receivable") -> ReportTable:
    receivable = kind == "receivable"
    parties = {p.account_id: p for p in db.scalars(select(Party)) if p.account_id}
    # A voided/edited document leaves an original + reversal pair that nets to zero: leave both out.
    reversed_ids = select(JournalEntry.reverses_id).where(JournalEntry.reverses_id.is_not(None))
    daily: dict[int, list[tuple[dt.date, Decimal, Decimal]]] = defaultdict(list)
    for account_id, day, debit, credit in db.execute(
        select(JournalLine.account_id, JournalEntry.date, func.sum(JournalLine.debit), func.sum(JournalLine.credit))
        .join(JournalEntry, JournalEntry.id == JournalLine.journal_id)
        .where(
            JournalLine.account_id.in_(list(parties)),
            JournalEntry.date <= as_of,
            JournalEntry.reverses_id.is_(None),
            JournalEntry.id.not_in(reversed_ids),
        )
        .group_by(JournalLine.account_id, JournalEntry.date)
    ):
        charge, payment = (Decimal(debit), Decimal(credit)) if receivable else (Decimal(credit), Decimal(debit))
        daily[account_id].append((day, charge, payment))
    rows = []
    for account_id, items in daily.items():
        balance = sum((c - p for _, c, p in items), ZERO)
        if balance <= 0:
            continue
        b = _age_buckets(items, as_of)
        party = parties[account_id]
        oldest = min((d for d, c, _ in items if c > 0), default=as_of)
        rows.append(
            {
                "party_id": party.id, "party": party.name, "phone": party.phone,
                "b0_30": b["b0_30"], "b31_60": b["b31_60"], "b60_plus": b["b60_plus"], "total": balance,
                "oldest_days": (as_of - oldest).days,
            }
        )  # fmt: skip
    rows.sort(key=lambda r: r["total"], reverse=True)
    totals = {"party": "Total"} | {k: sum((r[k] for r in rows), ZERO) for k in ("b0_30", "b31_60", "b60_plus", "total")}
    label = "Receivable (customers owe us)" if receivable else "Payable (we owe suppliers)"
    return ReportTable(
        title=f"Outstanding - {label}",
        subtitle=f"As of {as_of:%d-%m-%Y}",
        columns=[
            Col("party", "Party"),
            Col("phone", "Phone"),
            Col("b0_30", "0-30 days", "money"),
            Col("b31_60", "31-60 days", "money"),
            Col("b60_plus", "60+ days", "money"),
            Col("total", "Total", "money"),
        ],
        rows=rows,
        totals=totals,
    )


# ---------------------------------------------------------------------------------------------------
# Cash book / bank book, day book
# ---------------------------------------------------------------------------------------------------
def cash_book(db: Session, money_account_id: int | None, date_from: dt.date, date_to: dt.date) -> ReportTable:
    stmt = select(MoneyAccount)
    if money_account_id:
        stmt = stmt.where(MoneyAccount.id == money_account_id)
    accounts = db.scalars(stmt).all()
    if money_account_id and not accounts:
        raise NotFound("Cash/bank account not found")
    ids = [a.account_id for a in accounts]
    opening = sum(account_balances(db, ids, before=date_from).values(), ZERO)
    per_day: dict[dt.date, list[Decimal]] = defaultdict(lambda: [ZERO, ZERO])
    for day, debit, credit in db.execute(
        select(JournalEntry.date, func.sum(JournalLine.debit), func.sum(JournalLine.credit))
        .join(JournalEntry, JournalEntry.id == JournalLine.journal_id)
        .where(JournalLine.account_id.in_(ids), JournalEntry.date >= date_from, JournalEntry.date <= date_to)
        .group_by(JournalEntry.date)
    ):
        per_day[day] = [Decimal(debit or 0), Decimal(credit or 0)]
    rows, running = [], opening
    total_in = total_out = ZERO
    for day in sorted(per_day):
        money_in, money_out = per_day[day]
        rows.append(
            {"date": day, "opening": running, "money_in": money_in, "money_out": money_out,
             "closing": running + money_in - money_out}
        )  # fmt: skip
        running += money_in - money_out
        total_in += money_in
        total_out += money_out
    name = accounts[0].name if money_account_id else "All cash & bank"
    return ReportTable(
        title=f"Cash book - {name}",
        subtitle=_range_label(date_from, date_to),
        columns=[
            Col("date", "Date", "date"),
            Col("opening", "Opening", "money"),
            Col("money_in", "Money in", "money"),
            Col("money_out", "Money out", "money"),
            Col("closing", "Closing", "money"),
        ],
        rows=rows,
        totals={"date": "Period", "opening": opening, "money_in": total_in, "money_out": total_out, "closing": running},
        meta={"opening": opening, "closing": running},
    )


def day_book(db: Session, day: dt.date) -> ReportTable:
    accounts = {a.id: a.name for a in db.scalars(select(Account))}
    entries = db.scalars(select(JournalEntry).where(JournalEntry.date == day).order_by(JournalEntry.id)).all()
    rows = []
    for e in entries:
        dr_names = ", ".join(accounts[ln.account_id] for ln in e.lines if ln.debit > 0)
        cr_names = ", ".join(accounts[ln.account_id] for ln in e.lines if ln.credit > 0)
        rows.append(
            {
                "no": e.id,
                "type": ("Reversal: " if e.reverses_id else "") + SOURCE_LABEL.get(e.source_type, e.source_type),
                "narration": e.narration,
                # value moves from the right-hand side to the left: "Sales → Ali Builders"
                "accounts": f"{cr_names} → {dr_names}",
                "amount": sum((ln.debit for ln in e.lines), ZERO),
            }
        )
    return ReportTable(
        title="Day book",
        subtitle=f"{day:%d-%m-%Y}",
        columns=[
            Col("no", "No.", "int"),
            Col("type", "Type"),
            Col("narration", "Details"),
            Col("accounts", "Accounts"),
            Col("amount", "Amount", "money"),
        ],
        rows=rows,
        totals={"narration": "Entries", "amount": sum((r["amount"] for r in rows), ZERO)},
    )


# ---------------------------------------------------------------------------------------------------
# Profit reports (admin)
# ---------------------------------------------------------------------------------------------------
def vehicle_pnl(db: Session, date_from: dt.date, date_to: dt.date) -> ReportTable:
    """Per vehicle: trips (loads), revenue (freight + rent), diesel, repair, driver salary + trip pay -> profit.

    `vehicle_id` on journal lines is the cost centre. Material sale value is NOT vehicle revenue.
    """
    by_vehicle: dict[int, dict[str, Decimal]] = defaultdict(lambda: defaultdict(lambda: ZERO))
    for vehicle_id, code, net in db.execute(
        select(JournalLine.vehicle_id, Account.code, func.sum(JournalLine.debit - JournalLine.credit))
        .join(JournalEntry, JournalEntry.id == JournalLine.journal_id)
        .join(Account, Account.id == JournalLine.account_id)
        .where(JournalLine.vehicle_id.is_not(None), JournalEntry.date >= date_from, JournalEntry.date <= date_to)
        .group_by(JournalLine.vehicle_id, Account.code)
    ):
        by_vehicle[vehicle_id][code] += Decimal(net)
    trips = dict(
        db.execute(
            select(Delivery.vehicle_id, func.sum(Delivery.trips)).where(
                Delivery.status == "active", Delivery.delivered.is_(True), Delivery.vehicle_id.is_not(None),
                Delivery.date >= date_from, Delivery.date <= date_to,
            ).group_by(Delivery.vehicle_id)
        ).all()
    )  # fmt: skip
    rentals = dict(
        db.execute(
            select(Rental.vehicle_id, func.count()).where(
                Rental.status == "active", Rental.date >= date_from, Rental.date <= date_to
            ).group_by(Rental.vehicle_id)
        ).all()
    )  # fmt: skip
    rows = []
    for v in db.scalars(select(Vehicle).order_by(Vehicle.name)):
        c = by_vehicle.get(v.id, {})
        revenue = -(c.get(Code.FREIGHT, ZERO) + c.get(Code.RENT, ZERO))
        diesel, repair = c.get(Code.DIESEL, ZERO), c.get(Code.REPAIR, ZERO)
        other = sum(
            (c.get(k, ZERO) for k in (Code.TYRE, Code.INSURANCE, Code.TOLL, Code.OFFICE, Code.FOOD, Code.MISC)), ZERO
        )
        salary = c.get(Code.SALARY, ZERO) + c.get(Code.LABOUR_WAGES, ZERO) + c.get(Code.TRIP_PAY, ZERO)
        cost = diesel + repair + other + salary
        if not c and v.id not in trips and v.id not in rentals:
            continue
        rows.append(
            {
                "vehicle": v.name, "type": v.type.replace("_", " "), "trips": trips.get(v.id, 0),
                "rentals": rentals.get(v.id, 0), "revenue": revenue, "diesel": diesel, "repair": repair,
                "other": other, "salary": salary, "profit": revenue - cost,
            }
        )  # fmt: skip
    keys = ("trips", "rentals", "revenue", "diesel", "repair", "other", "salary", "profit")
    return ReportTable(
        title="Vehicle P&L",
        subtitle=_range_label(date_from, date_to),
        columns=[
            Col("vehicle", "Vehicle"),
            Col("type", "Type"),
            Col("trips", "Trips", "int"),
            Col("rentals", "Rentals", "int"),
            Col("revenue", "Freight + rent", "money"),
            Col("diesel", "Diesel", "money"),
            Col("repair", "Repair", "money"),
            Col("other", "Tyre/ins./toll/other", "money"),
            Col("salary", "Driver & labour", "money"),
            Col("profit", "Profit", "money"),
        ],
        rows=rows,
        totals={"vehicle": "Total"} | {k: sum((r[k] for r in rows), ZERO) for k in keys},
    )


def fuel(db: Session, date_from: dt.date, date_to: dt.date, group_by: str = "vehicle") -> ReportTable:
    """Fuel given out: fills, litres, amount and average price per litre, per vehicle or per pump.
    "On credit" is what went on a pump's khata; the pump's own balance is in its party khata."""
    by_pump = group_by == "pump"
    key = Expense.party_id if by_pump else Expense.vehicle_id
    on_credit = func.sum(case((Expense.paid_via == "party_credit", Expense.amount), else_=0))
    names = {p.id: p.name for p in db.scalars(select(Party))} if by_pump else {
        v.id: v.name for v in db.scalars(select(Vehicle))
    }  # fmt: skip
    rows = []
    for ref, fills, litres, amount, litre_amount, credit in db.execute(
        select(
            key, func.count(), func.coalesce(func.sum(Expense.litres), 0), func.sum(Expense.amount),
            func.coalesce(func.sum(case((Expense.litres.is_not(None), Expense.amount), else_=0)), 0), on_credit,
        )
        .where(Expense.category == "diesel", Expense.status == "active", Expense.date >= date_from, Expense.date <= date_to)
        .group_by(key)
    ):  # fmt: skip
        litres = Decimal(litres)
        rows.append(
            {
                "name": names.get(ref, "") if ref else ("Paid in cash" if by_pump else "No vehicle"),
                "fills": fills, "litres": qty(litres), "amount": money(Decimal(amount)),
                # only entries that have litres count towards the average price
                "avg_rate": money(Decimal(litre_amount) / litres) if litres else ZERO,
                "on_credit": money(Decimal(credit)),
            }
        )  # fmt: skip
    rows.sort(key=lambda r: r["amount"], reverse=True)
    total_litres = sum((r["litres"] for r in rows), ZERO)
    return ReportTable(
        title="Fuel " + ("by pump" if by_pump else "by vehicle"),
        subtitle=_range_label(date_from, date_to),
        columns=[
            Col("name", "Pump" if by_pump else "Vehicle"),
            Col("fills", "Fills", "int"),
            Col("litres", "Litres", "qty"),
            Col("avg_rate", "Avg rate / litre", "money"),
            Col("amount", "Amount", "money"),
            Col("on_credit", "Pump udhaar", "money"),
        ],
        rows=rows,
        totals={
            "name": "Total",
            "fills": sum(r["fills"] for r in rows),
            "litres": total_litres,
            "amount": sum((r["amount"] for r in rows), ZERO),
            "on_credit": sum((r["on_credit"] for r in rows), ZERO),
        },  # fmt: skip
    )


def material_margin(db: Session, date_from: dt.date, date_to: dt.date) -> ReportTable:
    purchased = {
        mid: (qty or ZERO, amount or ZERO)
        for mid, qty, amount in db.execute(
            select(PurchaseLine.material_id, func.sum(PurchaseLine.qty), func.sum(PurchaseLine.amount))
            .join(Purchase, Purchase.id == PurchaseLine.purchase_id)
            .where(Purchase.status == "active", Purchase.date >= date_from, Purchase.date <= date_to)
            .group_by(PurchaseLine.material_id)
        )
    }
    # Quantities in the material's own unit (stock_qty), so dumper/bucket loads add up with trolleys.
    sold: dict[int, list[Decimal]] = {}
    active = (
        Delivery.status == "active",
        Delivery.delivered.is_(True),
        Delivery.date >= date_from,
        Delivery.date <= date_to,
    )
    for cols in (
        (Delivery.material_id, Delivery.stock_qty, Delivery.sale_amount, Delivery.cost_amount),
        (Delivery.extra_material_id, Delivery.extra_qty, Delivery.extra_amount, Delivery.extra_cost_amount),
    ):
        mid_col, q_col, sale_col, cost_col = cols
        for mid, q, sale, cost in db.execute(
            select(mid_col, func.sum(q_col), func.sum(sale_col), func.sum(cost_col))
            .where(*active, mid_col.is_not(None))
            .group_by(mid_col)
        ):
            acc = sold.setdefault(mid, [ZERO, ZERO, ZERO])
            for i, v in enumerate((q, sale, cost)):
                acc[i] += Decimal(v or 0)
    rows = []
    for m in db.scalars(select(Material).order_by(Material.name)):
        if m.id not in sold:
            continue
        q, sale, cost = (Decimal(x or 0) for x in sold[m.id])
        pq, pa = purchased.get(m.id, (ZERO, ZERO))
        margin = sale - cost
        rows.append(
            {
                "material": m.name, "unit": m.unit, "qty": q, "sale": sale, "cost": cost, "margin": margin,
                "margin_pct": (margin / sale * 100) if sale else ZERO,
                "avg_sale_rate": (sale / q) if q else ZERO,
                "avg_purchase_rate": (Decimal(pa) / Decimal(pq)) if pq else ZERO,
            }
        )  # fmt: skip
    tot = {k: sum((r[k] for r in rows), ZERO) for k in ("sale", "cost", "margin")}
    tot["margin_pct"] = (tot["margin"] / tot["sale"] * 100) if tot["sale"] else ZERO
    return ReportTable(
        title="Material margin",
        subtitle=_range_label(date_from, date_to),
        columns=[
            Col("material", "Material"),
            Col("unit", "Unit"),
            Col("qty", "Qty sold", "qty"),
            Col("avg_sale_rate", "Avg sale rate", "money"),
            Col("avg_purchase_rate", "Avg purchase rate", "money"),
            Col("sale", "Sales", "money"),
            Col("cost", "Cost (avg)", "money"),
            Col("margin", "Margin", "money"),
            Col("margin_pct", "Margin %", "percent"),
        ],
        rows=rows,
        totals={"material": "Total"} | tot,
    )


def labour_cost(db: Session, date_from: dt.date, date_to: dt.date, group_by: str) -> ReportTable:
    """Total wages per week/month, per site, vehicle or worker (labour + salary expense lines)."""
    expense_ids = [
        a for (a,) in db.execute(select(Account.id).where(Account.code.in_((Code.LABOUR_WAGES, Code.SALARY))))
    ]
    lines = db.execute(
        select(JournalEntry.date, JournalEntry.source_type, JournalEntry.source_id, JournalLine.vehicle_id,
               JournalLine.debit - JournalLine.credit)
        .join(JournalEntry, JournalEntry.id == JournalLine.journal_id)
        .where(JournalLine.account_id.in_(expense_ids), JournalEntry.date >= date_from, JournalEntry.date <= date_to)
    ).all()  # fmt: skip
    attendance = {a.id: a for a in db.scalars(select(Attendance))}
    settlements = {s.id: s for s in db.scalars(select(WageSettlement))}
    staff = {s.id: s.name for s in db.scalars(select(Staff))}
    sites = {s.id: s.name for s in db.scalars(select(Site))}
    vehicles = {v.id: v.name for v in db.scalars(select(Vehicle))}
    totals: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for day, source_type, source_id, vehicle_id, net in lines:
        if group_by == "month":
            key = f"{day:%Y-%m}"
        elif group_by == "week":
            iso = day.isocalendar()
            key = f"{iso.year}-W{iso.week:02d}"
        elif group_by == "vehicle":
            key = vehicles.get(vehicle_id, "(no vehicle)")
        else:
            worker = attendance.get(source_id) if source_type == "attendance" else settlements.get(source_id)
            if group_by == "staff":
                key = staff.get(worker.staff_id, "?") if worker else "?"
            else:  # site: only daily-wage attendance records a site
                site_id = getattr(worker, "site_id", None) if source_type == "attendance" else None
                key = sites.get(site_id, "(no site)")
        totals[key] += Decimal(net)
    rows = [{"group": k, "amount": v} for k, v in sorted(totals.items())]
    label = {"month": "Month", "week": "Week", "vehicle": "Vehicle", "site": "Site", "staff": "Worker"}[group_by]
    return ReportTable(
        title=f"Labour cost by {label.lower()}",
        subtitle=_range_label(date_from, date_to),
        columns=[Col("group", label), Col("amount", "Wages & salary", "money")],
        rows=rows,
        totals={"group": "Total", "amount": sum((r["amount"] for r in rows), ZERO)},
    )


def rental_income(db: Session, date_from: dt.date, date_to: dt.date, group_by: str) -> ReportTable:
    rentals = db.scalars(
        select(Rental).where(Rental.status == "active", Rental.date >= date_from, Rental.date <= date_to)
    ).all()
    if group_by == "customer":
        names = {p.id: p for p in db.scalars(select(Party))}
        balances = account_balances(db, [p.account_id for p in names.values() if p.account_id])
        agg: dict[int, dict] = {}
        for r in rentals:
            row = agg.setdefault(r.customer_id, {"count": 0, "income": ZERO})
            row["count"] += 1
            row["income"] += r.amount
        rows = [
            {"name": names[cid].name, "count": a["count"], "income": a["income"],
             "unpaid": max(balances.get(names[cid].account_id, ZERO), ZERO)}
            for cid, a in agg.items()
        ]  # fmt: skip
        cols = [
            Col("name", "Customer"),
            Col("count", "Rentals", "int"),
            Col("income", "Rent billed", "money"),
            Col("unpaid", "Customer balance (unpaid)", "money"),
        ]
        keys = ("count", "income", "unpaid")
    else:
        names = {v.id: v.name for v in db.scalars(select(Vehicle))}
        agg = {}
        for r in rentals:
            row = agg.setdefault(r.vehicle_id, {"hours": ZERO, "trips": ZERO, "days": ZERO, "income": ZERO})
            row[{"hour": "hours", "trip": "trips", "day": "days"}[r.basis]] += r.qty
            row["income"] += r.amount
        rows = [{"name": names[vid], **a} for vid, a in agg.items()]
        cols = [
            Col("name", "Machine"),
            Col("hours", "Hours", "qty"),
            Col("trips", "Trips", "qty"),
            Col("days", "Days", "qty"),
            Col("income", "Income", "money"),
        ]
        keys = ("hours", "trips", "days", "income")
    rows.sort(key=lambda r: r["income"], reverse=True)
    return ReportTable(
        title=f"Rental income by {'customer' if group_by == 'customer' else 'machine'}",
        subtitle=_range_label(date_from, date_to),
        columns=cols,
        rows=rows,
        totals={"name": "Total"} | {k: sum((r[k] for r in rows), ZERO) for k in keys},
    )


def monthly_pnl(db: Session, date_from: dt.date, date_to: dt.date) -> ReportTable:
    stmt = (
        select(Account.code, Account.name, Account.type, func.sum(JournalLine.debit - JournalLine.credit))
        .join(JournalLine, JournalLine.account_id == Account.id)
        .join(JournalEntry, JournalEntry.id == JournalLine.journal_id)
        .where(Account.type.in_(("income", "expense")), JournalEntry.date >= date_from, JournalEntry.date <= date_to)
        .group_by(Account.code, Account.name, Account.type)
        .order_by(Account.code)
    )
    income, expense = [], []
    for code, name, type_, net in db.execute(stmt):
        net = Decimal(net)
        if type_ == "income":
            income.append({"section": "Income", "code": code, "name": name, "amount": -net})
        else:
            expense.append({"section": "Expense", "code": code, "name": name, "amount": net})
    total_income = sum((r["amount"] for r in income), ZERO)
    total_expense = sum((r["amount"] for r in expense), ZERO)
    summary = [
        {"section": "", "code": "", "name": "Total income", "amount": total_income},
        {"section": "", "code": "", "name": "Total expense", "amount": total_expense},
    ]
    return ReportTable(
        title="Profit & loss",
        subtitle=_range_label(date_from, date_to),
        columns=[
            Col("section", "Section"),
            Col("code", "Code"),
            Col("name", "Account"),
            Col("amount", "Amount", "money"),
        ],
        rows=[*income, *expense, *summary],
        totals={"name": "Net profit (income - expense)", "amount": total_income - total_expense},
        meta={"income": total_income, "expense": total_expense, "profit": total_income - total_expense},
    )


# ---------------------------------------------------------------------------------------------------
# Yard stock
# ---------------------------------------------------------------------------------------------------
def yard_stock(db: Session, date_from: dt.date, date_to: dt.date) -> ReportTable:
    """Opening + in - out +/- adjustment = closing, in quantity and value."""
    cols_sum = [
        func.coalesce(func.sum(StockMove.qty_in - StockMove.qty_out), 0),
        func.coalesce(func.sum(StockMove.value), 0),
    ]
    rows = []
    for m in db.scalars(select(Material).order_by(Material.name)):
        opening_q, opening_v = db.execute(
            select(*cols_sum).where(StockMove.material_id == m.id, StockMove.date < date_from)
        ).one()

        def period(source_types, field, m=m):
            return db.scalar(
                select(func.coalesce(func.sum(field), 0)).where(
                    StockMove.material_id == m.id,
                    StockMove.date >= date_from,
                    StockMove.date <= date_to,
                    StockMove.source_type.in_(source_types),
                )
            )

        qty_in = Decimal(period(("purchase",), StockMove.qty_in - StockMove.qty_out))
        qty_out = Decimal(period(("delivery",), StockMove.qty_out - StockMove.qty_in))
        qty_adj = Decimal(period(("adjustment", "opening"), StockMove.qty_in - StockMove.qty_out))
        opening_q = Decimal(opening_q)
        closing_q = opening_q + qty_in - qty_out + qty_adj
        closing_v = Decimal(
            db.scalar(
                select(func.coalesce(func.sum(StockMove.value), 0)).where(
                    StockMove.material_id == m.id, StockMove.date <= date_to
                )
            )
        )
        if not any((opening_q, qty_in, qty_out, qty_adj, closing_q)):
            continue
        rows.append(
            {
                "material": m.name, "unit": m.unit, "opening": opening_q, "qty_in": qty_in, "qty_out": qty_out,
                "adjustment": qty_adj, "closing": closing_q, "value": closing_v,
                "avg_cost": (closing_v / closing_q) if closing_q > 0 else ZERO,
            }
        )  # fmt: skip
    return ReportTable(
        title="Yard stock",
        subtitle=_range_label(date_from, date_to),
        columns=[
            Col("material", "Material"),
            Col("unit", "Unit"),
            Col("opening", "Opening", "qty"),
            Col("qty_in", "In (purchases)", "qty"),
            Col("qty_out", "Out (challans)", "qty"),
            Col("adjustment", "Adjust / opening", "qty"),
            Col("closing", "Closing", "qty"),
            Col("avg_cost", "Avg cost", "money"),
            Col("value", "Stock value", "money"),
        ],
        rows=rows,
        totals={"material": "Total", "value": sum((r["value"] for r in rows), ZERO)},
    )


# ---------------------------------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------------------------------
def _money_moved_on(day: dt.date) -> list:
    """Filters for cash/bank lines that really moved on `day`. Edits and voids post a reversal pair,
    so both halves are left out to show real movement, not bookkeeping. Joins JournalEntry itself."""
    money_ids = select(MoneyAccount.account_id).where(MoneyAccount.account_id.is_not(None))
    reversed_ids = select(JournalEntry.reverses_id).where(JournalEntry.reverses_id.is_not(None))
    return [
        JournalLine.journal_id == JournalEntry.id,
        JournalLine.account_id.in_(money_ids),
        JournalEntry.date == day,
        JournalEntry.reverses_id.is_(None),
        JournalEntry.id.not_in(reversed_ids),
    ]


def money_moves(db: Session, day: dt.date, direction: str = "in") -> ReportTable:
    """Every rupee that came into (or went out of) cash and bank on one day, one line each.
    The total is the dashboard's "Money received" / "Money paid out" for that day."""
    incoming = direction == "in"
    amount = JournalLine.debit if incoming else JournalLine.credit
    accounts = {m.account_id: m.name for m in db.scalars(select(MoneyAccount))}
    rows = [
        {
            "type": SOURCE_LABEL.get(source_type, source_type),
            "narration": narration,
            "account": accounts.get(account_id, ""),
            "amount": money(Decimal(value)),
        }
        for source_type, narration, account_id, value in db.execute(
            select(JournalEntry.source_type, JournalEntry.narration, JournalLine.account_id, amount)
            .where(*_money_moved_on(day), amount > 0)
            .order_by(JournalEntry.id)
        )
    ]
    return ReportTable(
        title="Money received" if incoming else "Money paid out",
        subtitle=f"{day:%d-%m-%Y}",
        columns=[
            Col("type", "Type"),
            Col("narration", "Details"),
            Col("account", "Cash / bank"),
            Col("amount", "Amount", "money"),
        ],
        rows=rows,
        totals={"narration": f"Total ({len(rows)})", "amount": sum((r["amount"] for r in rows), ZERO)},
    )


def dashboard(db: Session, *, with_profit: bool = False, on: dt.date | None = None) -> dict:
    """Owner's one-screen summary: today, where the money is, how business is going, and what needs doing.

    `on` looks at another day: its trips, sales, money in/out and vehicles (balances stay as of now).
    `with_profit` adds that month's income/expense/profit; only roles allowed to see profit get it.
    """
    now = dt.date.today()
    today = on or now
    yesterday = today - dt.timedelta(days=1)
    parties = db.scalars(select(Party)).all()
    party_bal = account_balances(db, [p.account_id for p in parties if p.account_id])
    receivable = sum((b for b in party_bal.values() if b > 0), ZERO)
    payable = sum((-b for b in party_bal.values() if b < 0), ZERO)
    staff_bal = account_balances(db, [s.account_id for s in db.scalars(select(Staff)) if s.account_id])
    money_accounts = db.scalars(select(MoneyAccount)).all()
    money_bal = account_balances(db, [m.account_id for m in money_accounts])
    cash = sum((money_bal.get(m.account_id, ZERO) for m in money_accounts if m.kind == "cash"), ZERO)
    bank = sum((money_bal.get(m.account_id, ZERO) for m in money_accounts if m.kind != "cash"), ZERO)

    # Pending orders are not sales yet: they count once delivered.
    active = and_(Delivery.status == "active", Delivery.delivered.is_(True))
    challan_total = Delivery.sale_amount + Delivery.freight_amount + Delivery.extra_amount

    def sales_between(start: dt.date, end: dt.date) -> Decimal:
        return Decimal(
            db.scalar(
                select(func.coalesce(func.sum(challan_total), 0)).where(
                    active, Delivery.date >= start, Delivery.date <= end
                )
            )
        )

    def trips_on(day: dt.date) -> int:
        # Loads, not challans: 3 trolleys on one challan are 3 trips out of the yard.
        return db.scalar(select(func.sum(Delivery.trips)).where(active, Delivery.date == day)) or 0

    # Last 14 days, one bar per day (days with no challans show as zero).
    first_day = today - dt.timedelta(days=13)
    per_day = {
        d: (Decimal(total), n)
        for d, total, n in db.execute(
            select(Delivery.date, func.sum(challan_total), func.sum(Delivery.trips))
            .where(active, Delivery.date >= first_day, Delivery.date <= today)
            .group_by(Delivery.date)
        )
    }
    daily = []
    for i in range(14):
        day = first_day + dt.timedelta(days=i)
        total, n = per_day.get(day, (ZERO, 0))
        daily.append({"date": day.isoformat(), "sales": str(money(total)), "trips": n})

    # Same stretch of last month (1st .. same day) so "this month" has something to compare with.
    month_from = month_start(today)
    prev_last = month_from - dt.timedelta(days=1)
    prev_from = month_start(prev_last)
    prev_to = prev_from.replace(day=min(today.day, prev_last.day))  # 31st -> 30th in a 30-day month

    trips_by_material = [
        {"material": name, "unit": unit, "trips": n, "qty": str(qty(Decimal(q)))}
        for name, unit, n, q in db.execute(
            select(Material.name, Material.unit, func.sum(Delivery.trips), func.sum(Delivery.stock_qty))
            .join(Material, Material.id == Delivery.material_id)
            .where(active, Delivery.date == today)
            .group_by(Material.name, Material.unit)
            .order_by(func.sum(Delivery.trips).desc())
        )
    ]

    # Every vehicle, with today's challan + rental count, so idle ones are visible too.
    trips_today_by_vehicle: dict[int, int] = defaultdict(int)
    for vid, n in db.execute(
        select(Delivery.vehicle_id, func.sum(Delivery.trips))
        .where(active, Delivery.date == today, Delivery.vehicle_id.is_not(None))
        .group_by(Delivery.vehicle_id)
    ):
        trips_today_by_vehicle[vid] += n
    for vid, n in db.execute(
        select(Rental.vehicle_id, func.count())
        .where(Rental.status == "active", Rental.date == today)
        .group_by(Rental.vehicle_id)
    ):
        trips_today_by_vehicle[vid] += n
    vehicles = [
        {"id": v.id, "name": v.name, "type": v.type, "trips": trips_today_by_vehicle.get(v.id, 0)}
        for v in db.scalars(select(Vehicle).where(Vehicle.is_active).order_by(Vehicle.type, Vehicle.name))
    ]

    moved_in, moved_out = db.execute(
        select(func.coalesce(func.sum(JournalLine.debit), 0), func.coalesce(func.sum(JournalLine.credit), 0)).where(
            *_money_moved_on(today)
        )
    ).one()

    # Every active material, also ones never stocked or used up ("finished" is exactly what the owner must see),
    # plus switched-off materials that still have stock lying in the yard.
    stock = [
        {"material": name, "unit": unit, "qty": str(qty(q or ZERO)), "value": str(money(v or ZERO))}
        for name, unit, q, v in db.execute(
            select(Material.name, Material.unit, StockItem.qty_on_hand, StockItem.value)
            .outerjoin(StockItem, StockItem.material_id == Material.id)
            .where(or_(Material.is_active, func.coalesce(StockItem.qty_on_hand, 0) != 0))
            .order_by(func.coalesce(StockItem.value, 0).desc(), Material.name)
        )
    ]
    stock_value = Decimal(db.scalar(select(func.coalesce(func.sum(StockItem.value), 0))))

    top = sorted(((b, p) for p in parties if (b := party_bal.get(p.account_id, ZERO)) > 0), key=lambda t: -t[0])[:5]
    top_owed = sorted(
        ((-b, p) for p in parties if (b := party_bal.get(p.account_id, ZERO)) < 0 and p.type != "customer"),
        key=lambda t: -t[0],
    )[:3]

    # Payment reminders: customers whose advance is nearly used up, and udhaar left unpaid too long.
    settings = get_settings()
    customers = [p for p in parties if p.type != "supplier" and p.account_id and p.is_active]
    advance_low = sorted(
        (
            {"party_id": p.id, "name": p.name, "advance": str(-b)}
            for p in customers
            if -settings.advance_low_threshold < (b := party_bal.get(p.account_id, ZERO)) < 0
        ),
        key=lambda r: Decimal(r["advance"]),
    )
    owing = [p for p in customers if party_bal.get(p.account_id, ZERO) > 0]
    oldest = oldest_unpaid_dates(db, [p.account_id for p in owing])
    old_udhaar = sorted(
        (
            {"party_id": p.id, "name": p.name, "balance": str(party_bal[p.account_id]), "days": days}
            for p in owing
            if (d := oldest.get(p.account_id)) and (days := (now - d).days) > settings.credit_overdue_days
        ),
        key=lambda r: -r["days"],
    )

    profit = None
    if with_profit:
        pnl = monthly_pnl(db, month_from, today).meta
        profit = {k: str(money(pnl[k])) for k in ("income", "expense", "profit")}

    return {
        "date": today.isoformat(),
        "trips_today": trips_on(today),
        "trips_yesterday": trips_on(yesterday),
        "trips_by_material": trips_by_material,
        # Orders with a challan that are not delivered yet (any date), so none is forgotten.
        "pending_orders": db.scalar(
            select(func.count()).where(Delivery.status == "active", Delivery.delivered.is_(False))
        ),
        "sales_today": str(sales_between(today, today)),
        "sales_yesterday": str(sales_between(yesterday, yesterday)),
        "sales_month": str(sales_between(month_from, today)),
        "sales_prev_month": str(sales_between(prev_from, prev_to)),
        "daily": daily,
        "money_in_today": str(money(Decimal(moved_in))),
        "money_out_today": str(money(Decimal(moved_out))),
        "cash_in_hand": str(cash),
        "bank_balance": str(bank),
        "total_receivable": str(receivable),
        "total_payable": str(payable),
        "staff_payable": str(sum((-b for b in staff_bal.values() if b < 0), ZERO)),
        "staff_advances": str(sum((b for b in staff_bal.values() if b > 0), ZERO)),
        "stock_value": str(stock_value),
        "stock": stock,
        "vehicles": vehicles,
        "top_debtors": [{"party_id": p.id, "name": p.name, "balance": str(b)} for b, p in top],
        "top_owed": [{"party_id": p.id, "name": p.name, "balance": str(b)} for b, p in top_owed],
        "advance_low": advance_low[:8],
        "old_udhaar": old_udhaar[:8],
        "advance_low_threshold": str(settings.advance_low_threshold),
        "credit_overdue_days": settings.credit_overdue_days,
        "profit_month": profit,
    }


def export_range(date_from: dt.date | None, date_to: dt.date | None) -> tuple[dt.date, dt.date]:
    """Day-wise backup exports default to today; a single given date means just that day."""
    today = dt.date.today()
    start, end = date_from or date_to or today, date_to or date_from or today
    if start > end:
        raise DomainError("The start date must be on or before the end date", code="BAD_DATE_RANGE")
    return start, end


def _export_name(prefix: str, date_from: dt.date, date_to: dt.date) -> str:
    return f"{prefix}_{date_from}" if date_from == date_to else f"{prefix}_{date_from}_to_{date_to}"


def _edited(doc) -> str:
    if not doc.edit_count:
        return ""
    times = f" {doc.edit_count}x" if doc.edit_count > 1 else ""
    return f"Edited{times}: {doc.edit_reason}"


def _names(db: Session, model, ids: set) -> dict[int, str]:
    ids = ids - {None}
    return dict(db.execute(select(model.id, model.name).where(model.id.in_(ids))).all()) if ids else {}


def challan_register(
    db: Session, date_from: dt.date, date_to: dt.date, customer_id: int | None = None, status: str | None = None
) -> ReportTable:
    """Every challan in the range, voided ones included, as a day-wise backup sheet (no cost/profit columns)."""
    stmt = select(Delivery).where(Delivery.date >= date_from, Delivery.date <= date_to)
    if customer_id is not None:
        stmt = stmt.where(Delivery.customer_id == customer_id)
    if status:
        stmt = stmt.where(Delivery.status == status)
    deliveries = db.scalars(stmt.order_by(Delivery.date, Delivery.challan_no)).all()

    party = _names(db, Party, {d.customer_id for d in deliveries})
    site = _names(db, Site, {d.site_id for d in deliveries})
    material = _names(db, Material, {d.material_id for d in deliveries} | {d.extra_material_id for d in deliveries})
    vehicle = _names(db, Vehicle, {d.vehicle_id for d in deliveries})
    staff = _names(db, Staff, {d.driver_id for d in deliveries})
    receipt_ids = {d.receipt_id for d in deliveries} - {None}
    paid = (
        dict(db.execute(select(Payment.id, Payment.amount).where(Payment.id.in_(receipt_ids))).all())
        if receipt_ids
        else {}
    )

    rows = []
    for d in deliveries:
        total = d.sale_amount + d.freight_amount + d.extra_amount
        rows.append(
            {
                "challan_no": d.challan_no,
                "date": d.date,
                "customer": party.get(d.customer_id, ""),
                "site": site.get(d.site_id, ""),
                "material": material.get(d.material_id, ""),
                "load": "Half" if d.load_size == "half" else "Full",
                "qty": d.qty,
                "unit": d.unit,
                "rate": d.sale_rate,
                "sale_amount": d.sale_amount,
                "extra_material": material.get(d.extra_material_id, ""),
                "extra_qty": d.extra_qty,
                "extra_unit": d.extra_unit or "",
                "extra_rate": d.extra_rate,
                "extra_amount": d.extra_amount or None,
                "freight": d.freight_amount,
                "total": total,
                "paid_now": paid.get(d.receipt_id),
                "vehicle": vehicle.get(d.vehicle_id, ""),
                "driver": staff.get(d.driver_id, ""),
                "status": "Void" if d.status == "void" else ("Delivered" if d.delivered else "Pending"),
                "void_reason": d.void_reason or "",
                "edited": _edited(d),
                "notes": d.notes or "",
            }
        )
    # Totals match the khata: only delivered challans are in it.
    active = [r for d, r in zip(deliveries, rows, strict=True) if d.status == "active" and d.delivered]
    totals = {
        "challan_no": f"Total ({len(active)} delivered)",
        **{k: sum((r[k] or ZERO for r in active), ZERO) for k in ("sale_amount", "extra_amount", "freight", "total")},
        "paid_now": sum((r["paid_now"] or ZERO for r in active), ZERO),
    }
    columns = [
        Col("challan_no", "Challan"),
        Col("date", "Date", "date"),
        Col("customer", "Customer"),
        Col("site", "Site"),
        Col("material", "Material"),
        Col("load", "Load"),
        Col("qty", "Qty", "qty"),
        Col("unit", "Unit"),
        Col("rate", "Rate", "money"),
        Col("sale_amount", "Material amount", "money"),
        Col("extra_material", "Extra material"),
        Col("extra_qty", "Extra qty", "qty"),
        Col("extra_unit", "Extra unit"),
        Col("extra_rate", "Extra rate", "money"),
        Col("extra_amount", "Extra amount", "money"),
        Col("freight", "Freight", "money"),
        Col("total", "Total", "money"),
        Col("paid_now", "Paid on challan", "money"),
        Col("vehicle", "Vehicle"),
        Col("driver", "Driver"),
        Col("status", "Status"),
        Col("void_reason", "Void reason"),
        Col("edited", "Edited"),
        Col("notes", "Notes"),
    ]
    return ReportTable(
        title="Challans",
        subtitle=_range_label(date_from, date_to),
        columns=columns,
        rows=rows,
        totals=totals if rows else None,
        meta={"filename": _export_name("challans", date_from, date_to)},
    )


def purchase_register(
    db: Session, date_from: dt.date, date_to: dt.date, supplier_id: int | None = None, status: str | None = None
) -> ReportTable:
    """Every purchase in the range, one row per material line, voided ones included (day-wise backup sheet)."""
    stmt = select(Purchase).where(Purchase.date >= date_from, Purchase.date <= date_to)
    if supplier_id is not None:
        stmt = stmt.where(Purchase.supplier_id == supplier_id)
    if status:
        stmt = stmt.where(Purchase.status == status)
    purchases = db.scalars(stmt.order_by(Purchase.date, Purchase.bill_no)).all()

    party = _names(db, Party, {p.supplier_id for p in purchases})
    material = _names(db, Material, {line.material_id for p in purchases for line in p.lines})
    units = (
        dict(db.execute(select(Material.id, Material.unit).where(Material.id.in_(material))).all()) if material else {}
    )
    vehicle = _names(db, Vehicle, {p.vehicle_id for p in purchases})
    staff = _names(db, Staff, {p.driver_id for p in purchases})

    rows = []
    for p in purchases:
        for line in p.lines:
            rows.append(
                {
                    "bill_no": p.bill_no,
                    "date": p.date,
                    "supplier": party.get(p.supplier_id, ""),
                    "slip_no": p.supplier_slip_no or "",
                    "material": material.get(line.material_id, ""),
                    "qty": line.qty,
                    "unit": units.get(line.material_id, ""),
                    "rate": line.rate,
                    "amount": line.amount,
                    "bill_total": p.total,
                    "brought_by": "Own vehicle" if p.transport_by == "own" else "Supplier",
                    "vehicle": vehicle.get(p.vehicle_id, ""),
                    "driver": staff.get(p.driver_id, ""),
                    "status": "Void" if p.status == "void" else "Active",
                    "void_reason": p.void_reason or "",
                    "edited": _edited(p),
                    "notes": p.notes or "",
                }
            )
    active = [p for p in purchases if p.status == "active"]
    totals = {
        "bill_no": f"Total ({len(active)} active)",
        "amount": sum((line.amount for p in active for line in p.lines), ZERO),
    }
    columns = [
        Col("bill_no", "Bill"),
        Col("date", "Date", "date"),
        Col("supplier", "Supplier"),
        Col("slip_no", "Supplier slip"),
        Col("material", "Material"),
        Col("qty", "Qty", "qty"),
        Col("unit", "Unit"),
        Col("rate", "Rate", "money"),
        Col("amount", "Amount", "money"),
        Col("bill_total", "Bill total", "money"),
        Col("brought_by", "Brought by"),
        Col("vehicle", "Vehicle"),
        Col("driver", "Driver"),
        Col("status", "Status"),
        Col("void_reason", "Void reason"),
        Col("edited", "Edited"),
        Col("notes", "Notes"),
    ]
    return ReportTable(
        title="Purchases",
        subtitle=_range_label(date_from, date_to),
        columns=columns,
        rows=rows,
        totals=totals if rows else None,
        meta={"filename": _export_name("purchases", date_from, date_to)},
    )
