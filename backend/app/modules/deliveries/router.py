from fastapi import APIRouter, Depends, Response

from app.core.deps import DB, CurrentUser, require_perm
from app.core.pagination import ListQuery, Page
from app.modules.common import get_or_404
from app.modules.deliveries import schemas as s
from app.modules.deliveries import service
from app.modules.deliveries.models import Delivery

router = APIRouter(prefix="/deliveries", tags=["deliveries"])
READ = Depends(require_perm("masters.read"))


@router.get("", response_model=Page[s.DeliveryOut], dependencies=[READ])
def list_deliveries(
    db: DB,
    params: ListQuery,
    customer_id: int | None = None,
    vehicle_id: int | None = None,
    material_id: int | None = None,
    status: str | None = None,
    invoiced: bool | None = None,
):
    rows, total = service.list_deliveries(
        db, params, customer_id=customer_id, vehicle_id=vehicle_id, material_id=material_id,
        status=status, invoiced=invoiced,
    )  # fmt: skip
    return Page(items=rows, total=total, page=params.page, size=params.size)


@router.get("/{delivery_id}", response_model=s.DeliveryOut, dependencies=[READ])
def get_delivery(delivery_id: int, db: DB):
    return get_or_404(db, Delivery, delivery_id, "Challan")


@router.post("", response_model=s.DeliveryOut, status_code=201, dependencies=[Depends(require_perm("challan.create"))])
def create_delivery(data: s.DeliveryIn, db: DB, response: Response):
    delivery, created = service.create(db, data)
    db.commit()
    if not created:
        response.status_code = 200
    return delivery


@router.put("/{delivery_id}", response_model=s.DeliveryOut, dependencies=[Depends(require_perm("challan.update"))])
def update_delivery(delivery_id: int, data: s.DeliveryIn, db: DB):
    delivery = service.update(db, delivery_id, data)
    db.commit()
    return delivery


@router.post("/{delivery_id}/void", response_model=s.DeliveryOut)
def void_delivery(delivery_id: int, data: s.VoidIn, db: DB, user: CurrentUser, _=Depends(require_perm("challan.void"))):
    delivery = service.void(db, delivery_id, data.reason, user.id)
    db.commit()
    return delivery


@router.get("/{delivery_id}/pdf", dependencies=[READ])
def download_pdf(delivery_id: int, db: DB):
    from app.modules.reports import documents

    return documents.challan_pdf(db, delivery_id)
