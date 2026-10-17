import datetime as dt

from fastapi import APIRouter, Depends, Response

from app.core.deps import DB, CurrentUser, require_perm
from app.modules.labour import schemas as s
from app.modules.labour import service

router = APIRouter(prefix="/labour", tags=["labour"])
READ = Depends(require_perm("masters.read"))


@router.get("/attendance", response_model=list[s.AttendanceOut], dependencies=[READ])
def get_attendance(db: DB, date_from: dt.date, date_to: dt.date, staff_id: int | None = None):
    """Rows for the attendance grid (workers x days). Missing rows mean 'not marked yet'."""
    return service.list_attendance(db, date_from, date_to, staff_id)


@router.put(
    "/attendance", response_model=list[s.AttendanceOut], dependencies=[Depends(require_perm("attendance.write"))]
)
def save_attendance(data: s.AttendanceBulkIn, db: DB):
    rows = service.save_attendance(db, data.entries)
    db.commit()
    return rows


@router.get("/settlements/preview", response_model=s.SettlementPreview, dependencies=[READ])
def preview_settlement(db: DB, staff_id: int, period_from: dt.date, period_to: dt.date):
    return service.preview(db, staff_id, period_from, period_to)


@router.get("/settlements", response_model=list[s.SettlementOut], dependencies=[READ])
def list_settlements(db: DB, staff_id: int | None = None, status: str | None = None):
    return service.list_settlements(db, staff_id, status)


@router.post(
    "/settlements",
    response_model=s.SettlementOut,
    status_code=201,
    dependencies=[Depends(require_perm("wages.settle"))],
)
def create_settlement(data: s.SettlementIn, db: DB, response: Response):
    settlement, created = service.create_settlement(db, data)
    db.commit()
    if not created:
        response.status_code = 200
    return settlement


@router.post("/settlements/{settlement_id}/void", response_model=s.SettlementOut)
def void_settlement(
    settlement_id: int, data: s.VoidIn, db: DB, user: CurrentUser, _=Depends(require_perm("settlement.void"))
):
    settlement = service.void_settlement(db, settlement_id, data.reason, user.id)
    db.commit()
    return settlement
