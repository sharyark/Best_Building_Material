import datetime as dt

from fastapi import APIRouter, Depends, Response

from app.core.deps import DB, CurrentUser, require_perm
from app.core.pagination import ListQuery, Page
from app.modules.common import get_or_404
from app.modules.invoices import schemas as s
from app.modules.invoices import service
from app.modules.invoices.models import Invoice

router = APIRouter(prefix="/invoices", tags=["invoices"])
READ = Depends(require_perm("masters.read"))


@router.get("", response_model=Page[s.InvoiceOut], dependencies=[READ])
def list_invoices(db: DB, params: ListQuery, customer_id: int | None = None, status: str | None = None):
    rows, total = service.list_invoices(db, params, customer_id, status)
    return Page(items=rows, total=total, page=params.page, size=params.size)


@router.get("/uninvoiced", response_model=s.UninvoicedOut, dependencies=[READ])
def uninvoiced(
    db: DB,
    customer_id: int,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    site_id: int | None = None,
):
    """Challans and rentals not yet on a bill, for the 'pick challans -> generate bill' screen."""
    deliveries, rentals = service.uninvoiced(db, customer_id, date_from, date_to, site_id)
    return s.UninvoicedOut(deliveries=deliveries, rentals=rentals)


@router.get("/{invoice_id}", response_model=s.InvoiceDetailOut, dependencies=[READ])
def get_invoice(invoice_id: int, db: DB):
    return service.detail(db, get_or_404(db, Invoice, invoice_id, "Invoice"))


@router.post(
    "", response_model=s.InvoiceDetailOut, status_code=201, dependencies=[Depends(require_perm("invoice.create"))]
)
def create_invoice(data: s.InvoiceIn, db: DB, response: Response):
    invoice, created = service.create(db, data)
    db.commit()
    if not created:
        response.status_code = 200
    return service.detail(db, invoice)


@router.post("/{invoice_id}/void", response_model=s.InvoiceOut)
def void_invoice(invoice_id: int, data: s.VoidIn, db: DB, user: CurrentUser, _=Depends(require_perm("invoice.void"))):
    invoice = service.void(db, invoice_id, data.reason, user.id)
    db.commit()
    return invoice


@router.get("/{invoice_id}/pdf", dependencies=[READ])
def download_pdf(invoice_id: int, db: DB):
    from app.modules.reports import documents

    return documents.invoice_pdf(db, invoice_id)
