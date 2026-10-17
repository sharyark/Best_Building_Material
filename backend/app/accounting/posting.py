"""The Posting Engine: the ONLY writer of journal entries.

Every financial document calls `post()` inside its own DB transaction, so the document and its
balanced journal either both commit or both roll back.
"""

import datetime as dt
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.accounting.models import JournalEntry, JournalLine, PeriodLock
from app.core.db import ZERO
from app.core.errors import Conflict, NotFound, PeriodLocked, UnbalancedJournal
from app.core.money import money


@dataclass(frozen=True)
class Line:
    account_id: int
    debit: Decimal = ZERO
    credit: Decimal = ZERO
    vehicle_id: int | None = None


def dr(account_id: int, amount, vehicle_id: int | None = None) -> Line:
    return Line(account_id, debit=money(amount), vehicle_id=vehicle_id)


def cr(account_id: int, amount, vehicle_id: int | None = None) -> Line:
    return Line(account_id, credit=money(amount), vehicle_id=vehicle_id)


def month_start(day: dt.date) -> dt.date:
    return day.replace(day=1)


def is_period_locked(db: Session, day: dt.date) -> bool:
    return db.get(PeriodLock, month_start(day)) is not None


def ensure_period_open(db: Session, *days: dt.date) -> None:
    for day in days:
        if is_period_locked(db, day):
            raise PeriodLocked(
                f"{day.strftime('%B %Y')} is locked. Entries dated in it cannot be added, edited or voided.",
                details={"month": month_start(day).isoformat()},
            )


def _clean(lines: Iterable[Line]) -> list[Line]:
    cleaned = []
    for line in lines:
        debit, credit = money(line.debit), money(line.credit)
        if debit < 0 or credit < 0:
            raise UnbalancedJournal("Journal line amounts cannot be negative")
        if debit == 0 and credit == 0:
            continue  # zero lines (e.g. no freight) are simply dropped
        if debit != 0 and credit != 0:
            raise UnbalancedJournal("A journal line must be either a debit or a credit")
        cleaned.append(Line(line.account_id, debit, credit, line.vehicle_id))
    return cleaned


def post(
    db: Session,
    *,
    date: dt.date,
    source_type: str,
    source_id: int | None,
    narration: str,
    lines: Iterable[Line],
    reverses_id: int | None = None,
    check_lock: bool = True,
) -> JournalEntry:
    if check_lock:
        ensure_period_open(db, date)
    cleaned = _clean(lines)
    total_dr = sum((line.debit for line in cleaned), ZERO)
    total_cr = sum((line.credit for line in cleaned), ZERO)
    if len(cleaned) < 2 or total_dr != total_cr:
        raise UnbalancedJournal(
            f"Journal does not balance (debit {total_dr} vs credit {total_cr})",
            details={"debit": str(total_dr), "credit": str(total_cr)},
        )
    entry = JournalEntry(
        date=date,
        source_type=source_type,
        source_id=source_id,
        narration=narration[:300],
        reverses_id=reverses_id,
        lines=[
            JournalLine(account_id=ln.account_id, debit=ln.debit, credit=ln.credit, vehicle_id=ln.vehicle_id)
            for ln in cleaned
        ],
    )
    db.add(entry)
    db.flush()
    return entry


def reverse(db: Session, journal_id: int, *, reason: str = "") -> JournalEntry:
    """Post the mirror image of an entry, dated the same day so the original period stays correct."""
    original = db.get(JournalEntry, journal_id)
    if original is None:
        raise NotFound("Journal entry not found")
    if original.reverses_id is not None:
        raise Conflict("A reversal entry cannot itself be reversed")
    if db.scalar(select(JournalEntry.id).where(JournalEntry.reverses_id == journal_id)):
        raise Conflict("This entry is already reversed")
    narration = f"Reversal of #{original.id}" + (f": {reason}" if reason else "")
    return post(
        db,
        date=original.date,
        source_type=original.source_type,
        source_id=original.source_id,
        narration=narration,
        lines=[
            Line(ln.account_id, debit=ln.credit, credit=ln.debit, vehicle_id=ln.vehicle_id) for ln in original.lines
        ],
        reverses_id=original.id,
    )


def active_entries(db: Session, source_type: str, source_id: int) -> list[JournalEntry]:
    """Original (non-reversal) entries of a document that have not been reversed yet."""
    reversed_ids = select(JournalEntry.reverses_id).where(JournalEntry.reverses_id.is_not(None))
    return list(
        db.scalars(
            select(JournalEntry).where(
                JournalEntry.source_type == source_type,
                JournalEntry.source_id == source_id,
                JournalEntry.reverses_id.is_(None),
                JournalEntry.id.not_in(reversed_ids),
            )
        )
    )
