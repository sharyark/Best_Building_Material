import datetime as dt
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Depends, Query
from pydantic import BaseModel
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    size: int


@dataclass
class ListParams:
    page: int = 1
    size: int = 50
    q: str | None = None
    date_from: dt.date | None = None
    date_to: dt.date | None = None
    sort: str | None = None


def list_params(
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=500)] = 50,
    q: str | None = None,
    from_: Annotated[dt.date | None, Query(alias="from")] = None,
    to: dt.date | None = None,
    sort: str | None = None,
) -> ListParams:
    return ListParams(page, size, q, from_, to, sort)


ListQuery = Annotated[ListParams, Depends(list_params)]


def apply_sort(stmt: Select, model, sort: str | None, default: list[Any], allowed: set[str] | None = None) -> Select:
    """`sort=-date,name` -> ORDER BY date DESC, name. Unknown fields are ignored."""
    orders = []
    for token in (sort or "").split(","):
        token = token.strip()
        if not token:
            continue
        desc = token.startswith("-")
        name = token.lstrip("-")
        column = getattr(model, name, None)
        if column is None or (allowed is not None and name not in allowed):
            continue
        orders.append(column.desc() if desc else column.asc())
    return stmt.order_by(*(orders or default))


def paginate(db: Session, stmt: Select, params: ListParams) -> tuple[list, int]:
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    rows = db.scalars(stmt.limit(params.size).offset((params.page - 1) * params.size)).all()
    return list(rows), total
