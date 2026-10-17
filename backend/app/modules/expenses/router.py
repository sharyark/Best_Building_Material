from fastapi import APIRouter, Depends, Response

from app.core.deps import DB, CurrentUser, require_perm
from app.core.pagination import ListQuery, Page
from app.modules.common import get_or_404
from app.modules.expenses import schemas as s
from app.modules.expenses import service
from app.modules.expenses.models import Expense

router = APIRouter(prefix="/expenses", tags=["expenses"])
READ = Depends(require_perm("masters.read"))


@router.get("", response_model=Page[s.ExpenseOut], dependencies=[READ])
def list_expenses(
    db: DB, params: ListQuery, category: str | None = None, vehicle_id: int | None = None, status: str | None = None
):
    rows, total = service.list_expenses(db, params, category=category, vehicle_id=vehicle_id, status=status)
    return Page(items=rows, total=total, page=params.page, size=params.size)


@router.get("/{expense_id}", response_model=s.ExpenseOut, dependencies=[READ])
def get_expense(expense_id: int, db: DB):
    return get_or_404(db, Expense, expense_id, "Expense")


@router.post("", response_model=s.ExpenseOut, status_code=201, dependencies=[Depends(require_perm("expense.create"))])
def create_expense(data: s.ExpenseIn, db: DB, response: Response):
    expense, created = service.create(db, data)
    db.commit()
    if not created:
        response.status_code = 200
    return expense


@router.put("/{expense_id}", response_model=s.ExpenseOut, dependencies=[Depends(require_perm("expense.update"))])
def update_expense(expense_id: int, data: s.ExpenseIn, db: DB):
    expense = service.update(db, expense_id, data)
    db.commit()
    return expense


@router.post("/{expense_id}/void", response_model=s.ExpenseOut)
def void_expense(expense_id: int, data: s.VoidIn, db: DB, user: CurrentUser, _=Depends(require_perm("expense.void"))):
    expense = service.void(db, expense_id, data.reason, user.id)
    db.commit()
    return expense
