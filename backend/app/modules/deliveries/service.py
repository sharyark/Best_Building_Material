import datetime as dt
import math
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.accounting import rules
from app.accounting.chart import Chart
from app.accounting.posting import ensure_period_open, post, reverse
from app.accounting.sequences import next_doc_no
from app.core.db import ZERO
from app.core.errors import Conflict, DomainError, Forbidden, NotFound
from app.core.money import money
from app.core.money import qty as q3
from app.core.pagination import ListParams, apply_sort, paginate
from app.modules.common import ensure_active, find_by_client_ref, get_or_404, mark_edited, mark_void
from app.modules.deliveries.models import Delivery
from app.modules.deliveries.schemas import DeliveryIn
from app.modules.masters import service as masters
from app.modules.masters.models import Material, Party, Site, Staff, Vehicle
from app.modules.payments import service as payments
from app.modules.payments.schemas import PaymentIn
from app.modules.stock import service as stock

HALF = Decimal("0.5")
# Loads that are one trip each for the driver/operator: trolley, dumper load, loader bucket.
TRIP_LOADS = {"trolley", "dumper", "bucket"}
# Units that mean "one vehicle load", so a half load makes sense.
LOAD_UNITS = {"trolley", "dumper", "bucket"}


def _validate(db: Session, data: DeliveryIn, saved: Delivery | None = None) -> tuple[Party, Material, Material | None]:
    customer = db.get(Party, data.customer_id)
    if customer is None or customer.type == "supplier":
        raise NotFound("Customer not found")
    material = db.get(Material, data.material_id)
    if material is None:
        raise NotFound("Material not found")
    if data.load_size == "half" and (data.load_unit or material.unit) not in LOAD_UNITS:
        raise DomainError(
            f"A half load only applies to trolley, dumper or bucket loads, not {material.unit}.",
            code="HALF_NOT_ALLOWED",
        )
    extra = None
    if data.extra_material_id is not None:
        if not data.extra_qty:
            raise DomainError("Enter the quantity of the second material.", code="EXTRA_QTY_REQUIRED")
        if data.extra_material_id == data.material_id:
            raise DomainError("The second material must be different from the main one.", code="EXTRA_SAME_MATERIAL")
        extra = db.get(Material, data.extra_material_id)
        if extra is None:
            raise NotFound("Second material not found")
    if data.site_id:
        site = db.get(Site, data.site_id)
        if site is None or site.party_id != data.customer_id:
            raise NotFound("Site not found for this customer")
    if data.vehicle_id and not db.get(Vehicle, data.vehicle_id):
        raise NotFound("Vehicle not found")
    if data.driver_id and not db.get(Staff, data.driver_id):
        raise NotFound("Driver not found")
    if saved is None or (saved.vehicle_id, saved.driver_id) != (data.vehicle_id, data.driver_id):
        masters.ensure_driver_allowed(db, data.vehicle_id, data.driver_id, data.date)
    return customer, material, extra


def trips_of(data: DeliveryIn, material: Material) -> int:
    """2 trolleys / dumpers / buckets of sand = 2 trips (a half load is still one); bags or pieces = 1 trip."""
    if (data.load_unit or material.unit) in TRIP_LOADS:
        return max(1, math.ceil(data.qty))
    return 1


def _ensure_not_invoiced(delivery: Delivery) -> None:
    if delivery.invoice_id:
        raise Conflict("This challan is on an invoice. Void the invoice first.", code="ON_INVOICE")


def _apply(
    db: Session, d: Delivery, data: DeliveryIn, customer: Party, material: Material, extra: Material | None
) -> None:
    """Copy the form onto the challan. Nothing is posted here: see `_post`."""
    rate = data.sale_rate or masters.lookup_sale_rate(db, customer.id, material.id, data.date, data.load_unit).rate
    qty = q3(data.qty * HALF) if data.load_size == "half" else data.qty
    d.date = data.date
    d.customer_id = customer.id
    d.site_id = data.site_id
    d.material_id = material.id
    d.load_unit = data.load_unit
    d.load_size = data.load_size
    d.qty = qty
    d.unit = data.load_unit or material.unit
    d.stock_qty = q3(qty * masters.load_factor(material, data.load_unit))
    d.sale_rate = rate
    d.sale_amount = money(qty * rate)
    d.freight_amount = data.freight_amount
    d.vehicle_id = data.vehicle_id
    d.driver_id = data.driver_id
    d.trips = trips_of(data, material)
    d.trip_pay, _ = masters.trip_pay_for(db, data.driver_id, data.trip_pay, d.trips)
    d.notes = data.notes
    d.extra_material_id = d.extra_qty = d.extra_unit = d.extra_rate = None
    d.extra_amount = money(ZERO)
    if extra is not None and data.extra_qty:
        extra_rate = data.extra_rate or masters.lookup_sale_rate(db, customer.id, extra.id, data.date).rate
        d.extra_material_id = extra.id
        d.extra_qty = data.extra_qty
        d.extra_unit = extra.unit
        d.extra_rate = extra_rate
        d.extra_amount = money(data.extra_qty * extra_rate)
    # Cost is only known when the material actually leaves the yard (at the average cost of that moment).
    d.cost_rate = d.cost_amount = d.extra_cost_amount = money(ZERO)
    db.flush()


def _post(db: Session, d: Delivery, allow_negative: bool) -> None:
    """A delivered challan: take the material out of stock and post the khata + trip pay entry."""
    customer = db.get(Party, d.customer_id)
    material = db.get(Material, d.material_id)
    _, d.cost_rate, d.cost_amount = stock.issue(
        db, date=d.date, material_id=d.material_id, qty=d.stock_qty, source_type="delivery", source_id=d.id,
        allow_negative=allow_negative,
    )  # fmt: skip
    narration = f"Challan {d.challan_no}: {d.qty} {d.unit} {material.name}"
    if d.extra_material_id and d.extra_qty:
        extra = db.get(Material, d.extra_material_id)
        _, _, d.extra_cost_amount = stock.issue(
            db, date=d.date, material_id=d.extra_material_id, qty=d.extra_qty, source_type="delivery",
            source_id=d.id, allow_negative=allow_negative,
        )  # fmt: skip
        narration += f" + {d.extra_qty} {extra.unit} {extra.name}"
    driver = db.get(Staff, d.driver_id) if d.driver_id else None
    entry = post(
        db,
        date=d.date,
        source_type="delivery",
        source_id=d.id,
        narration=f"{narration} to {customer.name}",
        lines=rules.delivery(
            Chart(db), customer.account_id, sale=d.sale_amount + d.extra_amount, freight=d.freight_amount,
            cost=d.cost_amount + d.extra_cost_amount, vehicle_id=d.vehicle_id,
        ) + rules.trip_pay(Chart(db), driver.account_id if driver else None, d.trip_pay, d.vehicle_id),
    )  # fmt: skip
    d.journal_id = entry.id


def _undo(db: Session, d: Delivery) -> None:
    if d.journal_id is None:  # still an order: nothing was posted
        return
    reverse(db, d.journal_id, reason=f"{d.challan_no} changed")
    stock.reverse_source(db, "delivery", d.id, allow_negative=True)
    d.journal_id = None


def _mark_delivered(db: Session, d: Delivery) -> None:
    actor = db.info.get("actor")
    d.delivered = True
    d.delivered_at = dt.datetime.now(dt.UTC)
    d.delivered_by = getattr(actor, "user_id", None)


def create(db: Session, data: DeliveryIn) -> tuple[Delivery, bool]:
    if existing := find_by_client_ref(db, Delivery, data.client_ref):
        return existing, False
    customer, material, extra = _validate(db, data)
    ensure_period_open(db, data.date)
    d = Delivery(
        challan_no=next_doc_no(db, "challan", data.date), client_ref=data.client_ref,
        sale_rate=0, sale_amount=0, qty=data.qty, stock_qty=data.qty, unit=material.unit, customer_id=customer.id,
        material_id=material.id, date=data.date, delivered=False,
    )  # fmt: skip
    db.add(d)
    db.flush()
    _apply(db, d, data, customer, material, extra)
    if data.delivered:
        _mark_delivered(db, d)
        _post(db, d, data.allow_negative_stock)
    if data.payment:
        # Money handed over with the order is real cash in hand, so it is received now even if not yet delivered.
        receipt, _ = payments.create(
            db,
            PaymentIn(
                date=data.date, direction="in", party_id=customer.id, money_account_id=data.payment.money_account_id,
                mode=data.payment.mode, amount=data.payment.amount, notes=f"Paid with challan {d.challan_no}",
            ),
        )  # fmt: skip
        d.receipt_id = receipt.id
    return d, True


def update(db: Session, delivery_id: int, data: DeliveryIn, *, can_edit_delivered: bool) -> Delivery:
    d = get_or_404(db, Delivery, delivery_id, "Challan")
    ensure_active(d)
    if d.delivered and not can_edit_delivered:
        raise Forbidden(
            "This challan is already delivered, so it can no longer be changed. Ask the owner to correct it.",
            code="CHALLAN_DELIVERED",
        )
    if d.delivered and not data.delivered:
        raise Conflict("A delivered challan cannot go back to pending.", code="DELIVERED_IS_FINAL")
    # Before any other check, so a missing reason is the first thing the munshi is told.
    mark_edited(db, d, data.edit_reason)
    _ensure_not_invoiced(d)
    customer, material, extra = _validate(db, data, d)
    ensure_period_open(db, d.date, data.date)
    _undo(db, d)
    _apply(db, d, data, customer, material, extra)
    if data.delivered:
        if not d.delivered:
            _mark_delivered(db, d)
        _post(db, d, data.allow_negative_stock)
    return d


def deliver(db: Session, delivery_id: int, allow_negative: bool) -> Delivery:
    """Mark an order delivered: from now on it is in the khata, trip pay and stock, and cannot go back."""
    d = get_or_404(db, Delivery, delivery_id, "Challan")
    ensure_active(d)
    if d.delivered:
        raise Conflict(f"Challan {d.challan_no} is already delivered.", code="ALREADY_DELIVERED")
    ensure_period_open(db, d.date)
    _mark_delivered(db, d)
    _post(db, d, allow_negative)
    return d


def void(db: Session, delivery_id: int, reason: str, user_id: int | None) -> Delivery:
    d = get_or_404(db, Delivery, delivery_id, "Challan")
    ensure_active(d)
    _ensure_not_invoiced(d)
    ensure_period_open(db, d.date)
    _undo(db, d)
    mark_void(d, reason, user_id)
    return d


def list_deliveries(
    db: Session,
    params: ListParams,
    *,
    customer_id: int | None,
    vehicle_id: int | None,
    material_id: int | None,
    status: str | None,
    invoiced: bool | None,
    delivered: bool | None = None,
):
    stmt = select(Delivery)
    if params.date_from:
        stmt = stmt.where(Delivery.date >= params.date_from)
    if params.date_to:
        stmt = stmt.where(Delivery.date <= params.date_to)
    for column, value in (
        (Delivery.customer_id, customer_id),
        (Delivery.vehicle_id, vehicle_id),
        (Delivery.material_id, material_id),
        (Delivery.status, status),
    ):
        if value:
            stmt = stmt.where(column == value)
    if delivered is not None:
        stmt = stmt.where(Delivery.delivered.is_(delivered))
    if invoiced is not None:
        stmt = stmt.where(Delivery.invoice_id.is_not(None) if invoiced else Delivery.invoice_id.is_(None))
    if params.q:
        stmt = stmt.where(Delivery.challan_no.ilike(f"%{params.q}%"))
    stmt = apply_sort(stmt, Delivery, params.sort, [Delivery.date.desc(), Delivery.id.desc()])
    return paginate(db, stmt, params)
