from fastapi import APIRouter, Depends, Response

from app.core.deps import DB, CurrentUser, require_perm
from app.core.pagination import ListQuery, Page
from app.modules.purchases import schemas as s
from app.modules.purchases import service

router = APIRouter(prefix="/purchases", tags=["purchases"])


@router.get("", response_model=Page[s.PurchaseOut], dependencies=[Depends(require_perm("masters.read"))])
def list_purchases(db: DB, params: ListQuery, supplier_id: int | None = None, status: str | None = None):
    rows, total = service.list_purchases(db, params, supplier_id, status)
    return Page(items=rows, total=total, page=params.page, size=params.size)


@router.get("/{purchase_id}", response_model=s.PurchaseOut, dependencies=[Depends(require_perm("masters.read"))])
def get_purchase(purchase_id: int, db: DB):
    return service.get(db, purchase_id)


@router.post("", response_model=s.PurchaseOut, status_code=201, dependencies=[Depends(require_perm("purchase.create"))])
def create_purchase(data: s.PurchaseIn, db: DB, response: Response):
    purchase, created = service.create(db, data)
    db.commit()
    if not created:
        response.status_code = 200  # idempotent replay
    return purchase


@router.put("/{purchase_id}", response_model=s.PurchaseOut, dependencies=[Depends(require_perm("purchase.update"))])
def update_purchase(purchase_id: int, data: s.PurchaseIn, db: DB):
    purchase = service.update(db, purchase_id, data)
    db.commit()
    return purchase


@router.post("/{purchase_id}/void", response_model=s.PurchaseOut)
def void_purchase(
    purchase_id: int, data: s.VoidIn, db: DB, user: CurrentUser, _=Depends(require_perm("purchase.void"))
):
    purchase = service.void(db, purchase_id, data.reason, user.id)
    db.commit()
    return purchase
