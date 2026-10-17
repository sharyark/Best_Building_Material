from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.accounting import rules
from app.accounting.chart import Chart
from app.accounting.posting import ensure_period_open, post, reverse
from app.accounting.sequences import next_doc_no
from app.core.errors import NotFound
from app.core.money import money
from app.core.pagination import ListParams, apply_sort, paginate
from app.modules.common import ensure_active, find_by_client_ref, get_or_404, mark_void
from app.modules.masters.models import Material, Party, Staff, Vehicle
from app.modules.purchases.models import Purchase, PurchaseLine
from app.modules.purchases.schemas import PurchaseIn
from app.modules.stock import service as stock


def _validate(db: Session, data: PurchaseIn) -> Party:
    supplier = db.get(Party, data.supplier_id)
    if supplier is None or supplier.type == "customer":
        raise NotFound("Supplier not found")
    if data.vehicle_id and not db.get(Vehicle, data.vehicle_id):
        raise NotFound("Vehicle not found")
    if data.driver_id and not db.get(Staff, data.driver_id):
        raise NotFound("Driver not found")
    for line in data.lines:
        if db.get(Material, line.material_id) is None:
            raise NotFound(f"Material {line.material_id} not found")
    return supplier


def _apply(db: Session, purchase: Purchase, data: PurchaseIn, supplier: Party) -> None:
    """Write the document fields, stock-in moves and the journal. Caller holds the transaction."""
    purchase.date = data.date
    purchase.supplier_id = data.supplier_id
    purchase.supplier_slip_no = data.supplier_slip_no
    purchase.vehicle_id = data.vehicle_id
    purchase.driver_id = data.driver_id
    purchase.transport_by = data.transport_by
    purchase.notes = data.notes
    purchase.lines = [
        PurchaseLine(material_id=ln.material_id, qty=ln.qty, rate=ln.rate, amount=money(ln.qty * ln.rate))
        for ln in data.lines
    ]
    purchase.total = sum((ln.amount for ln in purchase.lines), money(0))
    db.flush()
    for ln in purchase.lines:
        stock.receive(
            db, date=data.date, material_id=ln.material_id, qty=ln.qty, rate=ln.rate,
            source_type="purchase", source_id=purchase.id,
        )  # fmt: skip
    entry = post(
        db,
        date=data.date,
        source_type="purchase",
        source_id=purchase.id,
        narration=f"Purchase {purchase.bill_no} from {supplier.name}",
        lines=rules.purchase(Chart(db), supplier.account_id, purchase.total),
    )
    purchase.journal_id = entry.id


def _undo(db: Session, purchase: Purchase) -> None:
    reverse(db, purchase.journal_id, reason=f"{purchase.bill_no} changed")
    stock.reverse_source(db, "purchase", purchase.id)


def create(db: Session, data: PurchaseIn) -> tuple[Purchase, bool]:
    """Returns (purchase, created). A repeated client_ref returns the original untouched."""
    if existing := find_by_client_ref(db, Purchase, data.client_ref):
        return existing, False
    supplier = _validate(db, data)
    ensure_period_open(db, data.date)
    purchase = Purchase(bill_no=next_doc_no(db, "purchase", data.date), client_ref=data.client_ref, total=0)
    db.add(purchase)
    _apply(db, purchase, data, supplier)
    return purchase, True


def update(db: Session, purchase_id: int, data: PurchaseIn) -> Purchase:
    purchase = get_or_404(db, Purchase, purchase_id, "Purchase")
    ensure_active(purchase)
    supplier = _validate(db, data)
    ensure_period_open(db, purchase.date, data.date)
    _undo(db, purchase)
    _apply(db, purchase, data, supplier)
    return purchase


def void(db: Session, purchase_id: int, reason: str, user_id: int | None) -> Purchase:
    purchase = get_or_404(db, Purchase, purchase_id, "Purchase")
    ensure_active(purchase)
    ensure_period_open(db, purchase.date)
    _undo(db, purchase)
    mark_void(purchase, reason, user_id)
    return purchase


def get(db: Session, purchase_id: int) -> Purchase:
    return get_or_404(db, Purchase, purchase_id, "Purchase")


def list_purchases(db: Session, params: ListParams, supplier_id: int | None, status: str | None):
    stmt = select(Purchase).options(selectinload(Purchase.lines))
    if params.date_from:
        stmt = stmt.where(Purchase.date >= params.date_from)
    if params.date_to:
        stmt = stmt.where(Purchase.date <= params.date_to)
    if supplier_id:
        stmt = stmt.where(Purchase.supplier_id == supplier_id)
    if status:
        stmt = stmt.where(Purchase.status == status)
    if params.q:
        like = f"%{params.q}%"
        stmt = stmt.where(or_(Purchase.bill_no.ilike(like), Purchase.supplier_slip_no.ilike(like)))
    stmt = apply_sort(stmt, Purchase, params.sort, [Purchase.date.desc(), Purchase.id.desc()])
    return paginate(db, stmt, params)
