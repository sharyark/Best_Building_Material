"""SQLAlchemy session hooks that write `audit_logs` rows (before/after JSON) for every change.

The acting user is read from `session.info["actor"]`, set by the auth dependency.
"""

import datetime as dt
import enum
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import event, insert, inspect
from sqlalchemy.orm import Session

from app.audit.models import AuditLog

# Derived or high-volume tables: their changes are visible through the owning document.
SKIP_ENTITIES = {
    "audit_logs",
    "journal_entries",
    "journal_lines",
    "stock_moves",
    "stock_items",
    "doc_sequences",
    "refresh_tokens",
    "login_attempts",
    "purchase_lines",
}
SKIP_COLUMNS = {"created_at", "updated_at", "created_by"}
REDACT_COLUMNS = {"password_hash"}


@dataclass(frozen=True)
class Actor:
    user_id: int | None = None
    ip: str | None = None


def set_actor(db: Session, user_id: int | None, ip: str | None = None) -> None:
    db.info["actor"] = Actor(user_id, ip)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dt.datetime | dt.date):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, enum.Enum):
        return value.value
    return value


def _column_keys(obj) -> list[str]:
    return [c.key for c in inspect(obj).mapper.column_attrs if c.key not in SKIP_COLUMNS]


def _snapshot(obj) -> dict[str, Any]:
    return {k: "***" if k in REDACT_COLUMNS else _json_safe(getattr(obj, k, None)) for k in _column_keys(obj)}


def _audited(obj) -> bool:
    table = getattr(obj, "__tablename__", None)
    return table is not None and table not in SKIP_ENTITIES


def _pk(obj) -> int | None:
    key = inspect(obj).mapper.primary_key_from_instance(obj)
    return key[0] if key and isinstance(key[0], int) else None


def _write(session: Session, rows: list[dict]) -> None:
    if rows:
        session.connection().execute(insert(AuditLog.__table__), rows)


def _row(actor: "Actor", action: str, obj, before: dict | None, after: dict | None) -> dict:
    return {
        "user_id": actor.user_id,
        "action": action,
        "entity": obj.__tablename__,
        "entity_id": _pk(obj),
        "before": before,
        "after": after,
        "ip": actor.ip,
    }


def _before_flush(session: Session, flush_context, instances) -> None:
    actor: Actor = session.info.get("actor") or Actor()
    created: dict[int, Any] = session.info.setdefault("audit_created", {})
    pending: list[tuple[str, Any, dict | None, dict | None]] = session.info.setdefault("audit_pending", [])

    for obj in session.new:
        if hasattr(obj, "created_by") and getattr(obj, "created_by", None) is None and actor.user_id:
            obj.created_by = actor.user_id
        if _audited(obj):
            created[id(obj)] = obj  # logged at commit, with the final field values

    updates: dict[int, dict[str, Any]] = session.info.setdefault("audit_updates", {})
    for obj in session.dirty:
        # Fields filled in right after the insert are part of "create", not a separate update.
        if id(obj) in created or not _audited(obj) or not session.is_modified(obj):
            continue
        entry = updates.setdefault(id(obj), {"obj": obj, "before": {}, "after": {}})
        for key in _column_keys(obj):
            hist = inspect(obj).attrs[key].history
            if not hist.has_changes():
                continue
            redact = key in REDACT_COLUMNS
            old = "***" if redact else _json_safe(hist.deleted[0]) if hist.deleted else None
            entry["before"].setdefault(key, old)  # keep the value from before the whole transaction
            entry["after"][key] = "***" if redact else _json_safe(hist.added[0]) if hist.added else None

    for obj in session.deleted:
        if _audited(obj):
            pending.append(("delete", obj, _snapshot(obj), None))


def _after_flush(session: Session, flush_context) -> None:
    pending = session.info.pop("audit_pending", [])
    actor: Actor = session.info.get("actor") or Actor()
    _write(session, [_row(actor, action, obj, before, after) for action, obj, before, after in pending])


def _before_commit(session: Session) -> None:
    """One audit row per object per transaction: creates and merged updates, with final values."""
    session.flush()
    created: dict[int, Any] = session.info.pop("audit_created", {})
    updates: dict[int, dict[str, Any]] = session.info.pop("audit_updates", {})
    actor: Actor = session.info.get("actor") or Actor()
    rows = [_row(actor, "create", obj, None, _snapshot(obj)) for obj in created.values()]
    for entry in updates.values():
        changed = [k for k in entry["after"] if entry["after"][k] != entry["before"].get(k)]
        if not changed:
            continue
        action = "void" if entry["after"].get("status") == "void" else "update"
        rows.append(
            _row(
                actor,
                action,
                entry["obj"],
                {k: entry["before"].get(k) for k in changed},
                {k: entry["after"][k] for k in changed},
            )  # fmt: skip
        )
    _write(session, rows)


def _after_rollback(session: Session) -> None:
    for key in ("audit_created", "audit_updates", "audit_pending"):
        session.info.pop(key, None)


def install_audit_hooks() -> None:
    if not event.contains(Session, "before_flush", _before_flush):
        event.listen(Session, "before_flush", _before_flush)
        event.listen(Session, "after_flush", _after_flush)
        event.listen(Session, "before_commit", _before_commit)
        event.listen(Session, "after_rollback", _after_rollback)
