import datetime as dt
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import or_, select

from app.core.deps import DB, require_perm
from app.core.errors import NotFound
from app.core.pagination import ListQuery, Page, apply_sort, paginate
from app.modules.common import get_or_404
from app.modules.masters import schemas as s
from app.modules.masters import service
from app.modules.masters.models import Material, MoneyAccount, Party, RateCard, Site, Staff, Vehicle

router = APIRouter(prefix="/masters", tags=["masters"])
READ = Depends(require_perm("masters.read"))
WRITE = Depends(require_perm("masters.write"))


def _list(
    db, request: Request, model, out_schema, params, *, search: tuple[str, ...], filters: dict[str, Any], where=()
):
    """Shared list handler: ?q= searches text columns, `filters` map query params to equality filters."""
    stmt = select(model).where(*where)
    if params.q:
        like = f"%{params.q}%"
        stmt = stmt.where(or_(*[getattr(model, col).ilike(like) for col in search]))
    qp = request.query_params
    if "active" in qp and hasattr(model, "is_active"):
        stmt = stmt.where(model.is_active == (qp["active"].lower() in ("1", "true", "yes")))
    for name, (column, cast) in filters.items():
        if name in qp:
            stmt = stmt.where(column == cast(qp[name]))
    stmt = apply_sort(stmt, model, params.sort, [model.name] if hasattr(model, "name") else [model.id])
    rows, total = paginate(db, stmt, params)
    items = [out_schema.model_validate(r) for r in rows]
    if qp.get("with_balance", "").lower() in ("1", "true") and hasattr(model, "account_id"):
        service.attach_balances(db, rows, items)
    return Page(items=items, total=total, page=params.page, size=params.size)


# ---- parties -------------------------------------------------------------------------------------
@router.get("/parties", response_model=Page[s.PartyOut], dependencies=[READ])
def list_parties(request: Request, db: DB, params: ListQuery, type: str | None = None):
    # 'customer' also returns type 'both', and vice versa
    where = [Party.type.in_([type, "both"])] if type in ("customer", "supplier") else []
    return _list(db, request, Party, s.PartyOut, params, search=("name", "phone"), filters={}, where=where)


@router.post("/parties", response_model=s.PartyOut, status_code=201, dependencies=[WRITE])
def create_party(data: s.PartyIn, db: DB):
    party = service.create_party(db, data)
    db.commit()
    return party


@router.patch("/parties/{party_id}", response_model=s.PartyOut, dependencies=[WRITE])
def update_party(party_id: int, data: s.PartyUpdate, db: DB):
    party = service.update_party(db, get_or_404(db, Party, party_id, "Party"), data.model_dump(exclude_unset=True))
    db.commit()
    return party


# ---- sites ---------------------------------------------------------------------------------------
@router.get("/sites", response_model=Page[s.SiteOut], dependencies=[READ])
def list_sites(request: Request, db: DB, params: ListQuery):
    return _list(
        db, request, Site, s.SiteOut, params, search=("name", "address"), filters={"party_id": (Site.party_id, int)}
    )


@router.post("/sites", response_model=s.SiteOut, status_code=201, dependencies=[WRITE])
def create_site(data: s.SiteIn, db: DB):
    site = service.create_site(db, data)
    db.commit()
    return site


@router.patch("/sites/{site_id}", response_model=s.SiteOut, dependencies=[WRITE])
def update_site(site_id: int, data: s.SiteUpdate, db: DB):
    site = get_or_404(db, Site, site_id, "Site")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(site, key, value)
    db.commit()
    return site


# ---- materials -----------------------------------------------------------------------------------
@router.get("/materials", response_model=Page[s.MaterialOut], dependencies=[READ])
def list_materials(request: Request, db: DB, params: ListQuery):
    return _list(db, request, Material, s.MaterialOut, params, search=("name",), filters={})


@router.post("/materials", response_model=s.MaterialOut, status_code=201, dependencies=[WRITE])
def create_material(data: s.MaterialIn, db: DB):
    material = service.create_material(db, data)
    db.commit()
    return material


@router.patch("/materials/{material_id}", response_model=s.MaterialOut, dependencies=[WRITE])
def update_material(material_id: int, data: s.MaterialUpdate, db: DB):
    material = get_or_404(db, Material, material_id, "Material")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(material, key, value)
    db.commit()
    return material


# ---- rate cards ----------------------------------------------------------------------------------
@router.get("/rate-cards", response_model=list[s.RateCardOut], dependencies=[READ])
def list_rate_cards(db: DB, party_id: int | None = None, material_id: int | None = None):
    stmt = select(RateCard).order_by(RateCard.party_id, RateCard.material_id, RateCard.effective_from.desc())
    if party_id:
        stmt = stmt.where(RateCard.party_id == party_id)
    if material_id:
        stmt = stmt.where(RateCard.material_id == material_id)
    return db.scalars(stmt).all()


@router.post("/rate-cards", response_model=s.RateCardOut, status_code=201, dependencies=[WRITE])
def save_rate_card(data: s.RateCardIn, db: DB):
    card = service.upsert_rate_card(db, data)
    db.commit()
    return card


@router.get("/rate", response_model=s.RateLookup, dependencies=[READ])
def lookup_rate(
    db: DB,
    party_id: int,
    material_id: int,
    on: Annotated[dt.date | None, Query(alias="date")] = None,
):
    """Challan screen auto-fill: customer's rate card if one applies, else the material default."""
    return service.lookup_sale_rate(db, party_id, material_id, on or dt.date.today())


# ---- vehicles / staff / money accounts -----------------------------------------------------------
@router.get("/vehicles", response_model=Page[s.VehicleOut], dependencies=[READ])
def list_vehicles(request: Request, db: DB, params: ListQuery):
    return _list(db, request, Vehicle, s.VehicleOut, params, search=("name", "reg_no"), filters={})


@router.post("/vehicles", response_model=s.VehicleOut, status_code=201, dependencies=[WRITE])
def create_vehicle(data: s.VehicleIn, db: DB):
    vehicle = service.create_vehicle(db, data)
    db.commit()
    return vehicle


@router.patch("/vehicles/{vehicle_id}", response_model=s.VehicleOut, dependencies=[WRITE])
def update_vehicle(vehicle_id: int, data: s.VehicleUpdate, db: DB):
    vehicle = get_or_404(db, Vehicle, vehicle_id, "Vehicle")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(vehicle, key, value)
    db.commit()
    return vehicle


@router.get("/staff", response_model=Page[s.StaffOut], dependencies=[READ])
def list_staff(request: Request, db: DB, params: ListQuery):
    return _list(
        db,
        request,
        Staff,
        s.StaffOut,
        params,
        search=("name", "phone"),
        filters={"role": (Staff.role, str), "wage_type": (Staff.wage_type, str)},
    )


@router.post("/staff", response_model=s.StaffOut, status_code=201, dependencies=[WRITE])
def create_staff(data: s.StaffIn, db: DB):
    if data.default_vehicle_id and not db.get(Vehicle, data.default_vehicle_id):
        raise NotFound("Default vehicle not found")
    staff = service.create_staff(db, data)
    db.commit()
    return staff


@router.patch("/staff/{staff_id}", response_model=s.StaffOut, dependencies=[WRITE])
def update_staff(staff_id: int, data: s.StaffUpdate, db: DB):
    staff = service.update_staff(db, get_or_404(db, Staff, staff_id, "Staff"), data.model_dump(exclude_unset=True))
    db.commit()
    return staff


@router.get("/money-accounts", response_model=Page[s.MoneyAccountOut], dependencies=[READ])
def list_money_accounts(request: Request, db: DB, params: ListQuery):
    return _list(db, request, MoneyAccount, s.MoneyAccountOut, params, search=("name",), filters={})


@router.post("/money-accounts", response_model=s.MoneyAccountOut, status_code=201, dependencies=[WRITE])
def create_money_account(data: s.MoneyAccountIn, db: DB):
    money_account = service.create_money_account(db, data)
    db.commit()
    return money_account


@router.patch("/money-accounts/{money_account_id}", response_model=s.MoneyAccountOut, dependencies=[WRITE])
def update_money_account(money_account_id: int, data: s.MoneyAccountUpdate, db: DB):
    money_account = service.update_money_account(
        db, get_or_404(db, MoneyAccount, money_account_id, "Money account"), data.model_dump(exclude_unset=True)
    )
    db.commit()
    return money_account
