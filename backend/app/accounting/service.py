import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.accounting import rules
from app.accounting.balances import account_balances
from app.accounting.chart import Chart
from app.accounting.models import Account, JournalEntry, PeriodLock
from app.accounting.posting import active_entries, month_start, post, reverse
from app.accounting.schemas import (
    JournalLineOut,
    JournalOut,
    OpeningBalanceIn,
    OpeningBalanceOut,
    TrialBalanceOut,
    TrialBalanceRow,
)
from app.core.db import ZERO
from app.core.errors import Conflict, NotFound
from app.modules.masters.models import MoneyAccount, Party, Staff

KIND_MODEL = {"party": Party, "staff": Staff, "money_account": MoneyAccount}


def set_opening_balance(db: Session, data: OpeningBalanceIn) -> None:
    """Opening balance from the old register, posted against Opening Balance Equity.

    Re-entering for the same ledger replaces the earlier opening (reverse + re-post).
    """
    owner = db.get(KIND_MODEL[data.kind], data.ref_id)
    if owner is None or owner.account_id is None:
        raise NotFound(f"{data.kind} {data.ref_id} not found")
    for entry in active_entries(db, "opening", owner.account_id):
        reverse(db, entry.id, reason="opening balance re-entered")
    if data.amount > 0:
        post(
            db,
            date=data.date,
            source_type="opening",
            source_id=owner.account_id,
            narration=f"Opening balance: {owner.name}",
            lines=rules.opening_balance(Chart(db), owner.account_id, data.amount, data.side),
        )


def list_opening_balances(db: Session) -> list[OpeningBalanceOut]:
    owners = {}
    for kind, model in KIND_MODEL.items():
        for row in db.scalars(select(model)):
            if row.account_id:
                owners[row.account_id] = (kind, row)
    out = []
    for account_id, (kind, row) in owners.items():
        for entry in active_entries(db, "opening", account_id):
            line = next(ln for ln in entry.lines if ln.account_id == account_id)
            out.append(
                OpeningBalanceOut(
                    kind=kind,
                    ref_id=row.id,
                    name=row.name,
                    date=entry.date,
                    side="dr" if line.debit > 0 else "cr",
                    amount=line.debit if line.debit > 0 else line.credit,
                )
            )
    return sorted(out, key=lambda o: (o.kind, o.name))


def lock_month(db: Session, day: dt.date, user_id: int) -> PeriodLock:
    month = month_start(day)
    if db.get(PeriodLock, month):
        raise Conflict("This month is already locked", code="ALREADY_LOCKED")
    lock = PeriodLock(month=month, locked_by=user_id)
    db.add(lock)
    db.flush()
    return lock


def unlock_month(db: Session, month: dt.date) -> None:
    lock = db.get(PeriodLock, month_start(month))
    if lock is None:
        raise NotFound("This month is not locked")
    db.delete(lock)


def trial_balance(db: Session, upto: dt.date | None) -> TrialBalanceOut:
    balances = account_balances(db, upto=upto)
    rows = []
    for acc in db.scalars(select(Account).order_by(Account.code)):
        bal = balances.get(acc.id, ZERO)
        if bal == 0 and acc.id not in balances:
            continue
        rows.append(
            TrialBalanceRow(
                account_id=acc.id,
                code=acc.code,
                name=acc.name,
                type=acc.type,
                debit=bal if bal > 0 else ZERO,
                credit=-bal if bal < 0 else ZERO,
            )
        )
    total_dr = sum((r.debit for r in rows), ZERO)
    total_cr = sum((r.credit for r in rows), ZERO)
    return TrialBalanceOut(
        upto=upto, rows=rows, total_debit=total_dr, total_credit=total_cr, balanced=total_dr == total_cr
    )


def journal_entries(
    db: Session,
    *,
    date_from: dt.date | None,
    date_to: dt.date | None,
    source_type: str | None,
    source_id: int | None,
    limit: int,
    offset: int,
) -> tuple[list[JournalOut], int]:
    stmt = select(JournalEntry)
    if date_from:
        stmt = stmt.where(JournalEntry.date >= date_from)
    if date_to:
        stmt = stmt.where(JournalEntry.date <= date_to)
    if source_type:
        stmt = stmt.where(JournalEntry.source_type == source_type)
    if source_id:
        stmt = stmt.where(JournalEntry.source_id == source_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    entries = db.scalars(
        stmt.order_by(JournalEntry.date.desc(), JournalEntry.id.desc()).limit(limit).offset(offset)
    ).all()
    accounts = {a.id: a for a in db.scalars(select(Account))}
    out = [
        JournalOut(
            id=e.id,
            date=e.date,
            source_type=e.source_type,
            source_id=e.source_id,
            narration=e.narration,
            reverses_id=e.reverses_id,
            lines=[
                JournalLineOut(
                    account_id=ln.account_id,
                    account_code=accounts[ln.account_id].code,
                    account_name=accounts[ln.account_id].name,
                    debit=ln.debit,
                    credit=ln.credit,
                    vehicle_id=ln.vehicle_id,
                )
                for ln in e.lines
            ],
        )
        for e in entries
    ]
    return out, total
