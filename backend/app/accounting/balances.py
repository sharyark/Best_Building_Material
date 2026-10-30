"""Balances are always derived from journal lines: SUM(debit - credit)."""

import datetime as dt
from collections.abc import Iterable
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.accounting.models import JournalEntry, JournalLine
from app.core.db import ZERO


def account_balances(
    db: Session,
    account_ids: Iterable[int] | None = None,
    *,
    upto: dt.date | None = None,
    before: dt.date | None = None,
) -> dict[int, Decimal]:
    """Debit-positive balance per account. `upto` is inclusive, `before` exclusive."""
    stmt = (
        select(JournalLine.account_id, func.sum(JournalLine.debit - JournalLine.credit))
        .join(JournalEntry, JournalEntry.id == JournalLine.journal_id)
        .group_by(JournalLine.account_id)
    )
    if account_ids is not None:
        ids = list(account_ids)
        if not ids:
            return {}
        stmt = stmt.where(JournalLine.account_id.in_(ids))
    if upto is not None:
        stmt = stmt.where(JournalEntry.date <= upto)
    if before is not None:
        stmt = stmt.where(JournalEntry.date < before)
    return {acc: Decimal(total or 0) for acc, total in db.execute(stmt)}


def balance_of(db: Session, account_id: int, **kwargs) -> Decimal:
    return account_balances(db, [account_id], **kwargs).get(account_id, ZERO)


def oldest_unpaid_dates(db: Session, account_ids: Iterable[int]) -> dict[int, dt.date]:
    """Date of the oldest charge not yet covered by payments, per debit-balance account (first in, first out).

    Works on each day's net movement, so a void (reversed on the same day) cancels out instead of
    looking like a payment.
    """
    ids = list(account_ids)
    if not ids:
        return {}
    rows = db.execute(
        select(JournalLine.account_id, JournalEntry.date, func.sum(JournalLine.debit - JournalLine.credit))
        .join(JournalEntry, JournalEntry.id == JournalLine.journal_id)
        .where(JournalLine.account_id.in_(ids))
        .group_by(JournalLine.account_id, JournalEntry.date)
        .order_by(JournalLine.account_id, JournalEntry.date)
    ).all()
    days: dict[int, list[tuple[dt.date, Decimal]]] = {}
    for account_id, day, net in rows:
        days.setdefault(account_id, []).append((day, Decimal(net or 0)))
    out: dict[int, dt.date] = {}
    for account_id, movements in days.items():
        paid = sum((-net for _, net in movements if net < 0), ZERO)
        for day, net in movements:
            if net <= 0:
                continue
            if paid >= net:
                paid -= net
                continue
            out[account_id] = day
            break
    return out
