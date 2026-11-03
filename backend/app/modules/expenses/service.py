from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.accounting import rules
from app.accounting.chart import Chart
from app.accounting.posting import ensure_period_open, post, reverse
from app.accounting.sequences import next_doc_no
from app.core.errors import NotFound
from app.core.money import money
from app.core.pagination import ListParams, apply_sort, paginate
from app.modules.common import ensure_active, find_by_client_ref, get_or_404, mark_edited, mark_void
from app.modules.expenses.models import Expense
from app.modules.expenses.schemas import ExpenseIn, FuelRate
from app.modules.masters.models import MoneyAccount, Party, Vehicle


def _amount(data: ExpenseIn) -> Decimal:
    """With a rate, the amount is litres x rate, so the pump's bill and our books agree to the paisa."""
    if data.rate_per_litre is not None:
        return money(data.litres * data.rate_per_litre)
    return data.amount


def _what(data: ExpenseIn) -> str:
    """Narration shown in the pump's khata: "diesel 40 L @ 280.00" tells the owner what each line was."""
    if data.rate_per_litre is not None:
        return f"diesel {data.litres:g} L @ {data.rate_per_litre:,.2f} ="
    return data.category


def last_fuel_rate(db: Session, party_id: int | None) -> FuelRate:
    """Latest rate per litre, from this pump when given (pumps can differ), else from any fuel entry."""
    q = select(Expense.rate_per_litre, Expense.date).where(
        Expense.category == "diesel", Expense.status == "active", Expense.rate_per_litre.is_not(None)
    )
    if party_id:
        q = q.where(Expense.party_id == party_id)
    row = db.execute(q.order_by(Expense.date.desc(), Expense.id.desc()).limit(1)).first()
    return FuelRate(rate_per_litre=row[0] if row else None, date=row[1] if row else None)


def _apply(db: Session, e: Expense, data: ExpenseIn) -> None:
    if data.vehicle_id and not db.get(Vehicle, data.vehicle_id):
        raise NotFound("Vehicle not found")
    if data.paid_via == "money_account":
        source = db.get(MoneyAccount, data.money_account_id)
        if source is None:
            raise NotFound("Cash/bank account not found")
        paid_from, paid_label = source.account_id, source.name
    else:
        party = db.get(Party, data.party_id)
        if party is None or party.type == "customer":
            raise NotFound("Supplier (pump/workshop) not found")
        paid_from, paid_label = party.account_id, f"credit: {party.name}"
    amount = _amount(data)
    e.date = data.date
    e.category = data.category
    e.vehicle_id = data.vehicle_id
    e.amount = amount
    e.litres = data.litres
    e.rate_per_litre = data.rate_per_litre
    e.meter_reading = data.meter_reading
    e.paid_via = data.paid_via
    e.money_account_id = data.money_account_id if data.paid_via == "money_account" else None
    e.party_id = data.party_id if data.paid_via == "party_credit" else None
    e.notes = data.notes
    db.flush()
    entry = post(
        db,
        date=data.date,
        source_type="expense",
        source_id=e.id,
        narration=f"{e.voucher_no}: {_what(data)} {amount:,.2f} ({paid_label})",
        lines=rules.expense(Chart(db), data.category, amount, data.vehicle_id, paid_from),
    )
    e.journal_id = entry.id


def create(db: Session, data: ExpenseIn) -> tuple[Expense, bool]:
    if existing := find_by_client_ref(db, Expense, data.client_ref):
        return existing, False
    ensure_period_open(db, data.date)
    e = Expense(
        voucher_no=next_doc_no(db, "expense", data.date), client_ref=data.client_ref, date=data.date,
        category=data.category, amount=_amount(data), paid_via=data.paid_via,
    )  # fmt: skip
    db.add(e)
    db.flush()
    _apply(db, e, data)
    return e, True


def update(db: Session, expense_id: int, data: ExpenseIn) -> Expense:
    e = get_or_404(db, Expense, expense_id, "Expense")
    ensure_active(e)
    # Before any other check, so a missing reason is the first thing the munshi is told.
    mark_edited(db, e, data.edit_reason)
    ensure_period_open(db, e.date, data.date)
    reverse(db, e.journal_id, reason=f"{e.voucher_no} changed")
    _apply(db, e, data)
    return e


def void(db: Session, expense_id: int, reason: str, user_id: int | None) -> Expense:
    e = get_or_404(db, Expense, expense_id, "Expense")
    ensure_active(e)
    ensure_period_open(db, e.date)
    reverse(db, e.journal_id, reason=reason)
    mark_void(e, reason, user_id)
    return e


def list_expenses(db: Session, params: ListParams, *, category: str | None, vehicle_id: int | None, status: str | None):
    stmt = select(Expense)
    if params.date_from:
        stmt = stmt.where(Expense.date >= params.date_from)
    if params.date_to:
        stmt = stmt.where(Expense.date <= params.date_to)
    for column, value in ((Expense.category, category), (Expense.vehicle_id, vehicle_id), (Expense.status, status)):
        if value:
            stmt = stmt.where(column == value)
    if params.q:
        stmt = stmt.where(Expense.voucher_no.ilike(f"%{params.q}%"))
    stmt = apply_sort(stmt, Expense, params.sort, [Expense.date.desc(), Expense.id.desc()])
    return paginate(db, stmt, params)
