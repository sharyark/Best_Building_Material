import datetime as dt

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.accounting import schemas as s
from app.accounting import service
from app.accounting.models import Account, PeriodLock
from app.core.deps import DB, CurrentUser, require_perm

router = APIRouter(prefix="/accounting", tags=["accounting"])
VIEW = Depends(require_perm("accounting.view"))


@router.get("/accounts", response_model=list[s.AccountOut], dependencies=[VIEW])
def chart_of_accounts(db: DB, type: str | None = None):
    stmt = select(Account).order_by(Account.code)
    if type:
        stmt = stmt.where(Account.type == type)
    return db.scalars(stmt).all()


@router.get("/journal", response_model=dict, dependencies=[VIEW])
def journal(
    db: DB,
    date_from: dt.date | None = Query(default=None, alias="from"),
    date_to: dt.date | None = Query(default=None, alias="to"),
    source_type: str | None = None,
    source_id: int | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
):
    items, total = service.journal_entries(
        db, date_from=date_from, date_to=date_to, source_type=source_type, source_id=source_id,
        limit=size, offset=(page - 1) * size,
    )  # fmt: skip
    return {"items": items, "total": total, "page": page, "size": size}


@router.get("/trial-balance", response_model=s.TrialBalanceOut, dependencies=[VIEW])
def trial_balance(db: DB, upto: dt.date | None = None):
    """Total debit must equal total credit; `balanced: false` means the books are corrupt."""
    return service.trial_balance(db, upto)


@router.get("/locks", response_model=list[s.LockOut], dependencies=[VIEW])
def list_locks(db: DB):
    return db.scalars(select(PeriodLock).order_by(PeriodLock.month.desc())).all()


@router.post("/locks", response_model=s.LockOut, status_code=201)
def lock_month(data: s.LockIn, db: DB, user: CurrentUser, _=Depends(require_perm("period.lock"))):
    lock = service.lock_month(db, data.month, user.id)
    db.commit()
    return lock


@router.delete("/locks/{month}", status_code=204, dependencies=[Depends(require_perm("period.lock"))])
def unlock_month(month: dt.date, db: DB):
    service.unlock_month(db, month)
    db.commit()


@router.get(
    "/opening-balances", response_model=list[s.OpeningBalanceOut], dependencies=[Depends(require_perm("opening.write"))]
)
def opening_balances(db: DB):
    return service.list_opening_balances(db)


@router.post("/opening-balances", status_code=204, dependencies=[Depends(require_perm("opening.write"))])
def set_opening_balances(data: list[s.OpeningBalanceIn], db: DB):
    for row in data:
        service.set_opening_balance(db, row)
    db.commit()
