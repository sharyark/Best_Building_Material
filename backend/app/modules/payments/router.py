from fastapi import APIRouter, Depends, Response

from app.core.deps import DB, CurrentUser, require_perm
from app.core.pagination import ListQuery, Page
from app.modules.common import get_or_404
from app.modules.payments import schemas as s
from app.modules.payments import service
from app.modules.payments.models import Payment

router = APIRouter(prefix="/payments", tags=["payments"])
READ = Depends(require_perm("masters.read"))


@router.get("", response_model=Page[s.PaymentOut], dependencies=[READ])
def list_payments(
    db: DB,
    params: ListQuery,
    direction: str | None = None,
    party_id: int | None = None,
    staff_id: int | None = None,
    status: str | None = None,
):
    rows, total = service.list_payments(
        db, params, direction=direction, party_id=party_id, staff_id=staff_id, status=status
    )
    return Page(items=rows, total=total, page=params.page, size=params.size)


@router.get("/{payment_id}", response_model=s.PaymentOut, dependencies=[READ])
def get_payment(payment_id: int, db: DB):
    return get_or_404(db, Payment, payment_id, "Payment")


@router.post("", response_model=s.PaymentOut, status_code=201, dependencies=[Depends(require_perm("payment.create"))])
def create_payment(data: s.PaymentIn, db: DB, response: Response):
    payment, created = service.create(db, data)
    db.commit()
    if not created:
        response.status_code = 200
    return payment


@router.put("/{payment_id}", response_model=s.PaymentOut, dependencies=[Depends(require_perm("payment.update"))])
def update_payment(payment_id: int, data: s.PaymentIn, db: DB):
    payment = service.update(db, payment_id, data)
    db.commit()
    return payment


@router.post("/{payment_id}/void", response_model=s.PaymentOut)
def void_payment(payment_id: int, data: s.VoidIn, db: DB, user: CurrentUser, _=Depends(require_perm("payment.void"))):
    payment = service.void(db, payment_id, data.reason, user.id)
    db.commit()
    return payment


@router.get("/{payment_id}/pdf", dependencies=[READ])
def download_pdf(payment_id: int, db: DB):
    from app.modules.reports import documents

    return documents.payment_pdf(db, payment_id)
