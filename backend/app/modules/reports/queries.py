"""Every report is a query over `journal_lines` (the single source of truth) or the document tables."""

import datetime as dt
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.accounting.balances import account_balances
from app.accounting.chart import Code
from app.accounting.models import Account, JournalEntry, JournalLine
from app.core.db import ZERO
from app.core.errors import NotFound
from app.modules.deliveries.models import Delivery
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
def ledger(
    db: Session, account_id: int, title: str, date_from: dt.date, date_to: dt.date, subtitle: str | None = None
) -> ReportTable:
    """Date-wise Dr/Cr with a running balance computed by a window function (debit-positive)."""
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
        .subquery()
    )
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
            Col("debit", "Debit", "money"),
            Col("credit", "Credit", "money"),
            Col("balance", "Balance", "drcr"),
        ],
        rows=rows,
        totals={"narration": "Total / Closing", "debit": total_dr, "credit": total_cr, "balance": closing},
        meta={"opening": opening, "closing": closing},
    )


def party_khata(db: Session, party_id: int, date_from: dt.date, date_to: dt.date) -> ReportTable:
    party = db.get(Party, party_id)
    if party is None:
        raise NotFound("Party not found")
    kind = "Supplier" if party.type == "supplier" else "Customer"
    table = ledger(db, party.account_id, f"{kind} khata - {party.name}", date_from, date_to)
    table.meta.update(party_id=party.id, party_name=party.name, phone=party.phone)
    return table


def staff_khata(db: Session, staff_id: int, date_from: dt.date, date_to: dt.date) -> ReportTable:
    """Worker / driver khata: ledger plus attendance, wages earned and advances for the period."""
    staff = db.get(Staff, staff_id)
    if staff is None:
        raise NotFound("Staff member not found")
    table = ledger(db, staff.account_id, f"Labour khata - {staff.name}", date_from, date_to)
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
    table.meta.update(
        staff_id=staff.id,
        staff_name=staff.name,
        days_present=counts["present"],
        half_days=counts["half"],
        days_absent=counts["absent"],
        wages_earned=Decimal(earned or 0),
        advances_paid=Decimal(advances or 0),
        balance_payable=-table.meta["closing"],
    )
    return table


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
                "accounts": f"Dr {dr_names} / Cr {cr_names}",
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
    """Per vehicle: trips, revenue (freight + rent), diesel, repair, driver salary -> profit.

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
            select(Delivery.vehicle_id, func.count()).where(
                Delivery.status == "active", Delivery.vehicle_id.is_not(None),
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
        other = sum((c.get(k, ZERO) for k in (Code.TYRE, Code.INSURANCE, Code.TOLL, Code.OFFICE, Code.MISC)), ZERO)
        salary = c.get(Code.SALARY, ZERO) + c.get(Code.LABOUR_WAGES, ZERO)
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
    sold = {
        mid: (q, sale, cost)
        for mid, q, sale, cost in db.execute(
            select(
                Delivery.material_id,
                func.sum(Delivery.qty),
                func.sum(Delivery.sale_amount),
                func.sum(Delivery.cost_amount),
            )
            .where(Delivery.status == "active", Delivery.date >= date_from, Delivery.date <= date_to)
            .group_by(Delivery.material_id)
        )
    }
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
def dashboard(db: Session) -> dict:
    today = dt.date.today()
    parties = db.scalars(select(Party)).all()
    party_bal = account_balances(db, [p.account_id for p in parties if p.account_id])
    receivable = sum((b for b in party_bal.values() if b > 0), ZERO)
    payable = sum((-b for b in party_bal.values() if b < 0), ZERO)
    staff_bal = account_balances(db, [s.account_id for s in db.scalars(select(Staff)) if s.account_id])
    money_accounts = db.scalars(select(MoneyAccount)).all()
    money_bal = account_balances(db, [m.account_id for m in money_accounts])
    cash = sum((money_bal.get(m.account_id, ZERO) for m in money_accounts if m.kind == "cash"), ZERO)
    bank = sum((money_bal.get(m.account_id, ZERO) for m in money_accounts if m.kind != "cash"), ZERO)

    def sales_between(start: dt.date, end: dt.date) -> Decimal:
        return Decimal(
            db.scalar(
                select(func.coalesce(func.sum(Delivery.sale_amount + Delivery.freight_amount), 0)).where(
                    Delivery.status == "active", Delivery.date >= start, Delivery.date <= end
                )
            )
        )

    trips_today = db.scalar(
        select(func.count()).select_from(Delivery).where(Delivery.status == "active", Delivery.date == today)
    )
    by_material = [
        {"material": name, "unit": unit, "trips": n, "qty": Decimal(q)}
        for name, unit, n, q in db.execute(
            select(Material.name, Material.unit, func.count(), func.sum(Delivery.qty))
            .join(Material, Material.id == Delivery.material_id)
            .where(Delivery.status == "active", Delivery.date == today)
            .group_by(Material.name, Material.unit)
        )
    ]
    top = sorted(((b, p) for p in parties if (b := party_bal.get(p.account_id, ZERO)) > 0), key=lambda t: -t[0])[:5]
    stock_value = Decimal(db.scalar(select(func.coalesce(func.sum(StockItem.value), 0))))
    return {
        "date": today.isoformat(),
        "trips_today": trips_today,
        "trips_by_material": [{**r, "qty": str(r["qty"])} for r in by_material],
        "sales_today": str(sales_between(today, today)),
        "sales_month": str(sales_between(month_start(today), today)),
        "cash_in_hand": str(cash),
        "bank_balance": str(bank),
        "total_receivable": str(receivable),
        "total_payable": str(payable),
        "staff_payable": str(sum((-b for b in staff_bal.values() if b < 0), ZERO)),
        "staff_advances": str(sum((b for b in staff_bal.values() if b > 0), ZERO)),
        "stock_value": str(stock_value),
        "top_debtors": [{"party_id": p.id, "name": p.name, "balance": str(b)} for b, p in top],
    }
