import datetime as dt
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response

from app.core.deps import DB, CurrentUser, require_perm
from app.core.pagination import ListQuery, Page
from app.core.permissions import has_permission
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
    delivered: bool | None = None,
):
    rows, total = service.list_deliveries(
        db, params, customer_id=customer_id, vehicle_id=vehicle_id, material_id=material_id,
        status=status, invoiced=invoiced, delivered=delivered,
    )  # fmt: skip
    return Page(items=rows, total=total, page=params.page, size=params.size)


# Declared before "/{delivery_id}" so "export" is not parsed as an id.
@router.get("/export", dependencies=[READ])
def export_deliveries(
    db: DB,
    date_from: Annotated[dt.date | None, Query(alias="from")] = None,
    date_to: Annotated[dt.date | None, Query(alias="to")] = None,
    customer_id: int | None = None,
    status: str | None = None,
    fmt: Annotated[Literal["xlsx", "csv"], Query(alias="format")] = "xlsx",
):
    """Day-wise challan backup as Excel or CSV; defaults to today."""
    from app.modules.reports import queries
    from app.modules.reports.export import respond

    start, end = queries.export_range(date_from, date_to)
    return respond(queries.challan_register(db, start, end, customer_id, status), fmt)


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
def update_delivery(delivery_id: int, data: s.DeliveryIn, db: DB, user: CurrentUser):
    can_edit_delivered = has_permission(user.role, "challan.edit_delivered")
    delivery = service.update(db, delivery_id, data, can_edit_delivered=can_edit_delivered)
    db.commit()
    return delivery


@router.post(
    "/{delivery_id}/deliver", response_model=s.DeliveryOut, dependencies=[Depends(require_perm("challan.update"))]
)
def deliver(delivery_id: int, data: s.DeliverIn, db: DB):
    delivery = service.deliver(db, delivery_id, data.allow_negative_stock)
    db.commit()
    return delivery


@router.post("/{delivery_id}/void", response_model=s.DeliveryOut)
def void_delivery(delivery_id: int, data: s.VoidIn, db: DB, user: CurrentUser, _=Depends(require_perm("challan.void"))):
    delivery = service.void(db, delivery_id, data.reason, user.id)
    db.commit()
    return delivery


@router.get("/{delivery_id}/pdf", dependencies=[READ])
def download_pdf(delivery_id: int, db: DB, paper: Literal["a5", "80mm", "58mm"] = "a5"):
    from app.modules.reports import documents

    return documents.challan_pdf(db, delivery_id, paper)
