from sqlalchemy import select
from sqlalchemy.orm import Session

from app.accounting import rules
from app.accounting.posting import ensure_period_open, post, reverse
from app.accounting.sequences import next_doc_no
from app.core.errors import Conflict, DomainError, NotFound
from app.core.money import money
from app.core.pagination import ListParams, apply_sort, paginate
from app.modules.common import ensure_active, find_by_client_ref, get_or_404, mark_edited, mark_void
from app.modules.masters.models import MoneyAccount, Party, Staff
from app.modules.payments.models import Payment
from app.modules.payments.schemas import PaymentIn

# Shown in the staff khata so a trip payout is not mistaken for salary.
PURPOSE_LABEL = {"advance": "advance", "salary": "salary", "trip": "trip money"}


def _trip_part(data: PaymentIn):
    """Trip money inside a 'salary + trip' payment; zero for every other purpose."""
    if data.purpose != "sal_trip":
        return money(0)
    # Either part may be zero, so the munshi can always pick "salary + trip" to pay whatever is owed.
    if data.trip_amount is None:
        raise DomainError("Enter how much of this is trip money (0 if none).", code="TRIP_PART_REQUIRED")
    if data.trip_amount > data.amount:
        raise DomainError("The trip money part cannot be more than the total amount.", code="TRIP_PART_TOO_BIG")
    return money(data.trip_amount)


def _counterparty(db: Session, data: PaymentIn) -> tuple[int, str]:
    """Returns (ledger account id, display name) of the party or staff member."""
    if data.party_id:
        party = db.get(Party, data.party_id)
        if party is None:
            raise NotFound("Party not found")
        return party.account_id, party.name
    staff = db.get(Staff, data.staff_id)
    if staff is None:
        raise NotFound("Staff member not found")
    return staff.account_id, staff.name


def _apply(db: Session, p: Payment, data: PaymentIn) -> None:
    counterparty_account, name = _counterparty(db, data)
    money_account = db.get(MoneyAccount, data.money_account_id)
    if money_account is None:
        raise NotFound("Cash/bank account not found")
    p.date = data.date
    p.direction = data.direction
    p.party_id = data.party_id
    p.staff_id = data.staff_id
    p.money_account_id = data.money_account_id
    p.mode = data.mode
    p.purpose = data.purpose
    p.ref_no = data.ref_no
    p.amount = data.amount
    p.trip_amount = _trip_part(data)
    p.notes = data.notes
    db.flush()
    rule = rules.payment_in if data.direction == "in" else rules.payment_out
    label = "received from" if data.direction == "in" else "paid to"
    what = PURPOSE_LABEL.get(data.purpose)
    if data.purpose == "sal_trip":
        what = f"salary {data.amount - p.trip_amount:,.2f} + trip money {p.trip_amount:,.2f}"
    entry = post(
        db,
        date=data.date,
        source_type="payment",
        source_id=p.id,
        narration=f"{p.voucher_no}: {data.amount:,.2f} {label} {name} ({data.mode})" + (f", {what}" if what else ""),
        lines=rule(money_account.account_id, counterparty_account, data.amount),
    )
    p.journal_id = entry.id


def create(db: Session, data: PaymentIn) -> tuple[Payment, bool]:
    if existing := find_by_client_ref(db, Payment, data.client_ref):
        return existing, False
    ensure_period_open(db, data.date)
    doc_type = "receipt" if data.direction == "in" else "payment"
    p = Payment(
        voucher_no=next_doc_no(db, doc_type, data.date), client_ref=data.client_ref, date=data.date,
        direction=data.direction, party_id=data.party_id, staff_id=data.staff_id,
        money_account_id=data.money_account_id, mode=data.mode, amount=data.amount,
    )  # fmt: skip
    db.add(p)
    db.flush()
    _apply(db, p, data)
    return p, True


def update(db: Session, payment_id: int, data: PaymentIn) -> Payment:
    p = get_or_404(db, Payment, payment_id, "Payment")
    ensure_active(p)
    # Before any other check, so a missing reason is the first thing the munshi is told.
    mark_edited(db, p, data.edit_reason)
    if data.direction != p.direction:
        raise Conflict("Direction cannot be changed. Void this voucher and enter a new one.", code="DIRECTION_LOCKED")
    ensure_period_open(db, p.date, data.date)
    reverse(db, p.journal_id, reason=f"{p.voucher_no} changed")
    _apply(db, p, data)
    return p


def void(db: Session, payment_id: int, reason: str, user_id: int | None) -> Payment:
    p = get_or_404(db, Payment, payment_id, "Payment")
    ensure_active(p)
    ensure_period_open(db, p.date)
    reverse(db, p.journal_id, reason=reason)
    mark_void(p, reason, user_id)
    return p


def list_payments(
    db: Session,
    params: ListParams,
    *,
    direction: str | None,
    party_id: int | None,
    staff_id: int | None,
    status: str | None,
):
    stmt = select(Payment)
    if params.date_from:
        stmt = stmt.where(Payment.date >= params.date_from)
    if params.date_to:
        stmt = stmt.where(Payment.date <= params.date_to)
    for column, value in (
        (Payment.direction, direction),
        (Payment.party_id, party_id),
        (Payment.staff_id, staff_id),
        (Payment.status, status),
    ):
        if value:
            stmt = stmt.where(column == value)
    if params.q:
        like = f"%{params.q}%"
        stmt = stmt.where(Payment.voucher_no.ilike(like) | Payment.ref_no.ilike(like))
    stmt = apply_sort(stmt, Payment, params.sort, [Payment.date.desc(), Payment.id.desc()])
    return paginate(db, stmt, params)
