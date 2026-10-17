from sqlalchemy import select
from sqlalchemy.orm import Session

from app.accounting import rules
from app.accounting.chart import Chart
from app.accounting.posting import ensure_period_open, post, reverse
from app.accounting.sequences import next_doc_no
from app.core.errors import Conflict, NotFound
from app.core.money import money
from app.core.pagination import ListParams, apply_sort, paginate
from app.modules.common import ensure_active, find_by_client_ref, get_or_404, mark_void
from app.modules.masters.models import Party, Site, Staff, Vehicle
from app.modules.rentals.models import Rental
from app.modules.rentals.schemas import RentalIn


def _validate(db: Session, data: RentalIn) -> Party:
    customer = db.get(Party, data.customer_id)
    if customer is None or customer.type == "supplier":
        raise NotFound("Customer not found")
    if not db.get(Vehicle, data.vehicle_id):
        raise NotFound("Vehicle not found")
    if data.site_id:
        site = db.get(Site, data.site_id)
        if site is None or site.party_id != data.customer_id:
            raise NotFound("Site not found for this customer")
    if data.operator_id and not db.get(Staff, data.operator_id):
        raise NotFound("Operator not found")
    return customer


def _apply(db: Session, r: Rental, data: RentalIn, customer: Party) -> None:
    r.date = data.date
    r.customer_id = data.customer_id
    r.site_id = data.site_id
    r.vehicle_id = data.vehicle_id
    r.operator_id = data.operator_id
    r.basis = data.basis
    r.qty = data.qty
    r.rate = data.rate
    r.amount = money(data.qty * data.rate)
    r.notes = data.notes
    db.flush()
    entry = post(
        db,
        date=data.date,
        source_type="rental",
        source_id=r.id,
        narration=f"Rental {r.rental_no}: {data.qty} {data.basis} to {customer.name}",
        lines=rules.rental(Chart(db), customer.account_id, r.amount, r.vehicle_id),
    )
    r.journal_id = entry.id


def _ensure_not_invoiced(r: Rental) -> None:
    if r.invoice_id:
        raise Conflict("This rental is on an invoice. Void the invoice first.", code="ON_INVOICE")


def create(db: Session, data: RentalIn) -> tuple[Rental, bool]:
    if existing := find_by_client_ref(db, Rental, data.client_ref):
        return existing, False
    customer = _validate(db, data)
    ensure_period_open(db, data.date)
    r = Rental(
        rental_no=next_doc_no(db, "rental", data.date), client_ref=data.client_ref, date=data.date,
        customer_id=data.customer_id, vehicle_id=data.vehicle_id, basis=data.basis, qty=data.qty,
        rate=data.rate, amount=0,
    )  # fmt: skip
    db.add(r)
    db.flush()
    _apply(db, r, data, customer)
    return r, True


def update(db: Session, rental_id: int, data: RentalIn) -> Rental:
    r = get_or_404(db, Rental, rental_id, "Rental")
    ensure_active(r)
    _ensure_not_invoiced(r)
    customer = _validate(db, data)
    ensure_period_open(db, r.date, data.date)
    reverse(db, r.journal_id, reason=f"{r.rental_no} changed")
    _apply(db, r, data, customer)
    return r


def void(db: Session, rental_id: int, reason: str, user_id: int | None) -> Rental:
    r = get_or_404(db, Rental, rental_id, "Rental")
    ensure_active(r)
    _ensure_not_invoiced(r)
    ensure_period_open(db, r.date)
    reverse(db, r.journal_id, reason=reason)
    mark_void(r, reason, user_id)
    return r


def list_rentals(
    db: Session,
    params: ListParams,
    *,
    customer_id: int | None,
    vehicle_id: int | None,
    status: str | None,
):
    stmt = select(Rental)
    if params.date_from:
        stmt = stmt.where(Rental.date >= params.date_from)
    if params.date_to:
        stmt = stmt.where(Rental.date <= params.date_to)
    for column, value in ((Rental.customer_id, customer_id), (Rental.vehicle_id, vehicle_id), (Rental.status, status)):
        if value:
            stmt = stmt.where(column == value)
    if params.q:
        stmt = stmt.where(Rental.rental_no.ilike(f"%{params.q}%"))
    stmt = apply_sort(stmt, Rental, params.sort, [Rental.date.desc(), Rental.id.desc()])
    return paginate(db, stmt, params)
