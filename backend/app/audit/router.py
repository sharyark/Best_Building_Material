import datetime as dt
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app.audit.models import AuditLog
from app.core.deps import DB, require_perm
from app.core.pagination import ListQuery, Page, paginate

router = APIRouter(prefix="/audit-logs", tags=["audit"])


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None
    action: str
    entity: str
    entity_id: int | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    ip: str | None
    at: dt.datetime


@router.get("", response_model=Page[AuditOut], dependencies=[Depends(require_perm("audit.view"))])
def list_audit_logs(
    db: DB,
    params: ListQuery,
    entity: str | None = None,
    entity_id: int | None = None,
    user_id: int | None = None,
    action: str | None = None,
):
    stmt = select(AuditLog)
    for column, value in (
        (AuditLog.entity, entity),
        (AuditLog.entity_id, entity_id),
        (AuditLog.user_id, user_id),
        (AuditLog.action, action),
    ):
        if value is not None:
            stmt = stmt.where(column == value)
    if params.date_from:
        stmt = stmt.where(AuditLog.at >= dt.datetime.combine(params.date_from, dt.time.min))
    if params.date_to:
        stmt = stmt.where(AuditLog.at < dt.datetime.combine(params.date_to + dt.timedelta(days=1), dt.time.min))
    rows, total = paginate(db, stmt.order_by(AuditLog.id.desc()), params)
    return Page(items=rows, total=total, page=params.page, size=params.size)
