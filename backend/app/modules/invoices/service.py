import datetime as dt

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.accounting import rules
from app.accounting.chart import Chart
from app.accounting.posting import ensure_period_open, post, reverse
from app.accounting.sequences import next_doc_no
from app.core.errors import Conflict, NotFound
from app.core.money import money
from app.core.pagination import ListParams, apply_sort, paginate
from app.modules.common import ensure_active, find_by_client_ref, get_or_404, mark_void
from app.modules.deliveries.models import Delivery
from app.modules.invoices.models import Invoice
from app.modules.invoices.schemas import InvoiceDetailOut, InvoiceIn, InvoiceLineOut, InvoiceOut
from app.modules.masters.models import Material, Party, Site, Vehicle
from app.modules.rentals.models import Rental


def _fetch_docs(db: Session, model, ids: list[int], data: InvoiceIn, label: str) -> list:
    if not ids:
        return []
    docs = db.scalars(select(model).where(model.id.in_(ids))).all()
    if len(docs) != len(set(ids)):
        raise NotFound(f"Some {label} were not found")
    for doc in docs:
        no = getattr(doc, "challan_no", None) or getattr(doc, "rental_no", "")
        if doc.customer_id != data.customer_id:
            raise Conflict(f"{no} belongs to a different customer", code="WRONG_CUSTOMER")
        if doc.status != "active":
            raise Conflict(f"{no} is void", code="DOCUMENT_VOID")
        if doc.invoice_id is not None:
            raise Conflict(f"{no} is already on an invoice", code="ON_INVOICE")
        if data.site_id and doc.site_id != data.site_id:
            raise Conflict(f"{no} is for a different site", code="WRONG_SITE")
    return list(docs)


def create(db: Session, data: InvoiceIn) -> tuple[Invoice, bool]:
    if existing := find_by_client_ref(db, Invoice, data.client_ref):
        return existing, False
    customer = db.get(Party, data.customer_id)
    if customer is None or customer.type == "supplier":
        raise NotFound("Customer not found")
    if data.site_id:
        site = db.get(Site, data.site_id)
        if site is None or site.party_id != data.customer_id:
            raise NotFound("Site not found for this customer")
    ensure_period_open(db, data.date)
    deliveries = _fetch_docs(db, Delivery, data.delivery_ids, data, "challans")
    rentals = _fetch_docs(db, Rental, data.rental_ids, data, "rentals")

    subtotal = money(
        sum(d.sale_amount + d.freight_amount + d.extra_amount for d in deliveries) + sum(r.amount for r in rentals)
    )
    tax = money(subtotal * data.tax_rate / 100) if data.is_tax_invoice else money(0)
    invoice = Invoice(
        invoice_no=next_doc_no(db, "invoice", data.date),
        client_ref=data.client_ref,
        date=data.date,
        customer_id=data.customer_id,
        site_id=data.site_id,
        period_from=data.period_from,
        period_to=data.period_to,
        subtotal=subtotal,
        tax_rate=data.tax_rate if data.is_tax_invoice else 0,
        tax_amount=tax,
        total=subtotal + tax,
        is_tax_invoice=data.is_tax_invoice,
        notes=data.notes,
    )
    db.add(invoice)
    db.flush()
    for doc in [*deliveries, *rentals]:
        doc.invoice_id = invoice.id
    if tax > 0:
        # Sales are already in the customer's khata from each challan; only the tax is new.
        entry = post(
            db,
            date=data.date,
            source_type="invoice",
            source_id=invoice.id,
            narration=f"Tax on {invoice.invoice_no} ({data.tax_rate}%)",
            lines=rules.invoice_tax(Chart(db), customer.account_id, tax),
        )
        invoice.journal_id = entry.id
    db.flush()
    return invoice, True


def void(db: Session, invoice_id: int, reason: str, user_id: int | None) -> Invoice:
    invoice = get_or_404(db, Invoice, invoice_id, "Invoice")
    ensure_active(invoice)
    ensure_period_open(db, invoice.date)
    if invoice.journal_id:
        reverse(db, invoice.journal_id, reason=reason)
    db.execute(update(Delivery).where(Delivery.invoice_id == invoice.id).values(invoice_id=None))
    db.execute(update(Rental).where(Rental.invoice_id == invoice.id).values(invoice_id=None))
    mark_void(invoice, reason, user_id)
    return invoice


def lines_of(db: Session, invoice: Invoice) -> list[InvoiceLineOut]:
    lines: list[InvoiceLineOut] = []
    deliveries = db.scalars(
        select(Delivery).where(Delivery.invoice_id == invoice.id).order_by(Delivery.date, Delivery.id)
    )
    materials = {m.id: m.name for m in db.scalars(select(Material))}
    for d in deliveries:
        lines.append(
            InvoiceLineOut(
                kind="challan", doc_id=d.id, doc_no=d.challan_no, date=d.date,
                description=f"{materials.get(d.material_id, '')}" + (f" (+ freight {d.freight_amount})" if d.freight_amount else ""),
                qty=d.qty, unit=d.unit, rate=d.sale_rate, amount=d.sale_amount + d.freight_amount,
            )
        )  # fmt: skip
        if d.extra_material_id:
            lines.append(
                InvoiceLineOut(
                    kind="challan", doc_id=d.id, doc_no=d.challan_no, date=d.date,
                    description=materials.get(d.extra_material_id, ""),
                    qty=d.extra_qty, unit=d.extra_unit, rate=d.extra_rate, amount=d.extra_amount,
                )
            )  # fmt: skip
    vehicles = {v.id: v.name for v in db.scalars(select(Vehicle))}
    for r in db.scalars(select(Rental).where(Rental.invoice_id == invoice.id).order_by(Rental.date, Rental.id)):
        lines.append(
            InvoiceLineOut(
                kind="rental", doc_id=r.id, doc_no=r.rental_no, date=r.date,
                description=f"{vehicles.get(r.vehicle_id, 'Equipment')} hire", qty=r.qty, unit=r.basis,
                rate=r.rate, amount=r.amount,
            )
        )  # fmt: skip
    return lines


def detail(db: Session, invoice: Invoice) -> InvoiceDetailOut:
    base = InvoiceOut.model_validate(invoice).model_dump()
    if invoice.status == "void":
        return InvoiceDetailOut(**base, lines=[])
    return InvoiceDetailOut(**base, lines=lines_of(db, invoice))


def uninvoiced(db: Session, customer_id: int, date_from: dt.date | None, date_to: dt.date | None, site_id: int | None):
    d_stmt = select(Delivery).where(
        Delivery.customer_id == customer_id, Delivery.status == "active", Delivery.invoice_id.is_(None)
    )
    r_stmt = select(Rental).where(
        Rental.customer_id == customer_id, Rental.status == "active", Rental.invoice_id.is_(None)
    )
    if date_from:
        d_stmt, r_stmt = d_stmt.where(Delivery.date >= date_from), r_stmt.where(Rental.date >= date_from)
    if date_to:
        d_stmt, r_stmt = d_stmt.where(Delivery.date <= date_to), r_stmt.where(Rental.date <= date_to)
    if site_id:
        d_stmt, r_stmt = d_stmt.where(Delivery.site_id == site_id), r_stmt.where(Rental.site_id == site_id)
    return (
        db.scalars(d_stmt.order_by(Delivery.date, Delivery.id)).all(),
        db.scalars(r_stmt.order_by(Rental.date, Rental.id)).all(),
    )


def list_invoices(db: Session, params: ListParams, customer_id: int | None, status: str | None):
    stmt = select(Invoice)
    if params.date_from:
        stmt = stmt.where(Invoice.date >= params.date_from)
    if params.date_to:
        stmt = stmt.where(Invoice.date <= params.date_to)
    if customer_id:
        stmt = stmt.where(Invoice.customer_id == customer_id)
    if status:
        stmt = stmt.where(Invoice.status == status)
    if params.q:
        stmt = stmt.where(Invoice.invoice_no.ilike(f"%{params.q}%"))
    stmt = apply_sort(stmt, Invoice, params.sort, [Invoice.date.desc(), Invoice.id.desc()])
    return paginate(db, stmt, params)
