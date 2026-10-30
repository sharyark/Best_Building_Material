from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.accounting import rules
from app.accounting.chart import Chart
from app.accounting.posting import ensure_period_open, post, reverse
from app.accounting.sequences import next_doc_no
from app.core.db import ZERO
from app.core.errors import Conflict, DomainError, NotFound
from app.core.money import money
from app.core.money import qty as q3
from app.core.pagination import ListParams, apply_sort, paginate
from app.modules.common import ensure_active, find_by_client_ref, get_or_404, mark_void
from app.modules.deliveries.models import Delivery
from app.modules.deliveries.schemas import DeliveryIn
from app.modules.masters import service as masters
from app.modules.masters.models import Material, Party, Site, Staff, Vehicle
from app.modules.payments import service as payments
from app.modules.payments.schemas import PaymentIn
from app.modules.stock import service as stock

HALF = Decimal("0.5")
# Units that mean "one vehicle load", so a half load makes sense.
LOAD_UNITS = {"trolley", "dumper", "bucket"}


def _validate(db: Session, data: DeliveryIn) -> tuple[Party, Material, Material | None]:
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
    return customer, material, extra


def _ensure_not_invoiced(delivery: Delivery) -> None:
    if delivery.invoice_id:
        raise Conflict("This challan is on an invoice. Void the invoice first.", code="ON_INVOICE")


def _apply(
    db: Session, d: Delivery, data: DeliveryIn, customer: Party, material: Material, extra: Material | None
) -> None:
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
    d.notes = data.notes
    db.flush()
    _, cost_rate, cost_amount = stock.issue(
        db, date=data.date, material_id=material.id, qty=d.stock_qty, source_type="delivery", source_id=d.id,
        allow_negative=data.allow_negative_stock,
    )  # fmt: skip
    d.cost_rate = cost_rate
    d.cost_amount = cost_amount
    narration = f"Challan {d.challan_no}: {qty} {d.unit} {material.name}"
    d.extra_material_id = d.extra_qty = d.extra_unit = d.extra_rate = None
    d.extra_amount = d.extra_cost_amount = money(ZERO)
    if extra is not None and data.extra_qty:
        extra_rate = data.extra_rate or masters.lookup_sale_rate(db, customer.id, extra.id, data.date).rate
        d.extra_material_id = extra.id
        d.extra_qty = data.extra_qty
        d.extra_unit = extra.unit
        d.extra_rate = extra_rate
        d.extra_amount = money(data.extra_qty * extra_rate)
        _, _, d.extra_cost_amount = stock.issue(
            db, date=data.date, material_id=extra.id, qty=data.extra_qty, source_type="delivery", source_id=d.id,
            allow_negative=data.allow_negative_stock,
        )  # fmt: skip
        narration += f" + {data.extra_qty} {extra.unit} {extra.name}"
    entry = post(
        db,
        date=data.date,
        source_type="delivery",
        source_id=d.id,
        narration=f"{narration} to {customer.name}",
        lines=rules.delivery(
            Chart(db), customer.account_id, sale=d.sale_amount + d.extra_amount, freight=d.freight_amount,
            cost=d.cost_amount + d.extra_cost_amount, vehicle_id=d.vehicle_id,
        ),
    )  # fmt: skip
    d.journal_id = entry.id


def _undo(db: Session, d: Delivery) -> None:
    reverse(db, d.journal_id, reason=f"{d.challan_no} changed")
    stock.reverse_source(db, "delivery", d.id, allow_negative=True)


def create(db: Session, data: DeliveryIn) -> tuple[Delivery, bool]:
    if existing := find_by_client_ref(db, Delivery, data.client_ref):
        return existing, False
    customer, material, extra = _validate(db, data)
    ensure_period_open(db, data.date)
    d = Delivery(
        challan_no=next_doc_no(db, "challan", data.date), client_ref=data.client_ref,
        sale_rate=0, sale_amount=0, qty=data.qty, stock_qty=data.qty, unit=material.unit, customer_id=customer.id,
        material_id=material.id, date=data.date,
    )  # fmt: skip
    db.add(d)
    db.flush()
    _apply(db, d, data, customer, material, extra)
    if data.payment:
        receipt, _ = payments.create(
            db,
            PaymentIn(
                date=data.date, direction="in", party_id=customer.id, money_account_id=data.payment.money_account_id,
                mode=data.payment.mode, amount=data.payment.amount, notes=f"Paid with challan {d.challan_no}",
            ),
        )  # fmt: skip
        d.receipt_id = receipt.id
    return d, True


def update(db: Session, delivery_id: int, data: DeliveryIn) -> Delivery:
    d = get_or_404(db, Delivery, delivery_id, "Challan")
    ensure_active(d)
    _ensure_not_invoiced(d)
    customer, material, extra = _validate(db, data)
    ensure_period_open(db, d.date, data.date)
    _undo(db, d)
    _apply(db, d, data, customer, material, extra)
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
    if invoiced is not None:
        stmt = stmt.where(Delivery.invoice_id.is_not(None) if invoiced else Delivery.invoice_id.is_(None))
    if params.q:
        stmt = stmt.where(Delivery.challan_no.ilike(f"%{params.q}%"))
    stmt = apply_sort(stmt, Delivery, params.sort, [Delivery.date.desc(), Delivery.id.desc()])
    return paginate(db, stmt, params)
