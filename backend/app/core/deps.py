from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.audit.hooks import set_actor
from app.core.db import get_db
from app.core.errors import Forbidden, Unauthorized
from app.core.permissions import has_permission
from app.core.security import decode_access_token
from app.modules.auth.models import User

DB = Annotated[Session, Depends(get_db)]
_bearer = HTTPBearer(auto_error=False)


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def get_current_user(
    request: Request,
    db: DB,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    if creds is None:
        raise Unauthorized("Not authenticated", code="NOT_AUTHENTICATED")
    payload = decode_access_token(creds.credentials)
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise Unauthorized("User is inactive or no longer exists", code="INVALID_TOKEN")
    set_actor(db, user.id, client_ip(request))
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_perm(perm: str) -> Callable[..., User]:
    """Server-side permission check. Frontend hiding is cosmetic only."""

    def dependency(user: CurrentUser) -> User:
        if not has_permission(user.role, perm):
            raise Forbidden(f"Your role '{user.role}' cannot do this ({perm})", details={"permission": perm})
        return user

    return dependency
