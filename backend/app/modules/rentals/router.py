from fastapi import APIRouter, Depends, Response

from app.core.deps import DB, CurrentUser, require_perm
from app.core.pagination import ListQuery, Page
from app.modules.common import get_or_404
from app.modules.rentals import schemas as s
from app.modules.rentals import service
from app.modules.rentals.models import Rental

router = APIRouter(prefix="/rentals", tags=["rentals"])
READ = Depends(require_perm("masters.read"))


@router.get("", response_model=Page[s.RentalOut], dependencies=[READ])
def list_rentals(
    db: DB, params: ListQuery, customer_id: int | None = None, vehicle_id: int | None = None, status: str | None = None
):
    rows, total = service.list_rentals(db, params, customer_id=customer_id, vehicle_id=vehicle_id, status=status)
    return Page(items=rows, total=total, page=params.page, size=params.size)


@router.get("/{rental_id}", response_model=s.RentalOut, dependencies=[READ])
def get_rental(rental_id: int, db: DB):
    return get_or_404(db, Rental, rental_id, "Rental")


@router.post("", response_model=s.RentalOut, status_code=201, dependencies=[Depends(require_perm("rental.create"))])
def create_rental(data: s.RentalIn, db: DB, response: Response):
    rental, created = service.create(db, data)
    db.commit()
    if not created:
        response.status_code = 200
    return rental


@router.put("/{rental_id}", response_model=s.RentalOut, dependencies=[Depends(require_perm("rental.update"))])
def update_rental(rental_id: int, data: s.RentalIn, db: DB):
    rental = service.update(db, rental_id, data)
    db.commit()
    return rental


@router.post("/{rental_id}/void", response_model=s.RentalOut)
def void_rental(rental_id: int, data: s.VoidIn, db: DB, user: CurrentUser, _=Depends(require_perm("rental.void"))):
    rental = service.void(db, rental_id, data.reason, user.id)
    db.commit()
    return rental
