from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Request, Response
from sqlalchemy import select

from app.core.config import get_settings
from app.core.deps import DB, CurrentUser, client_ip, require_perm
from app.modules.auth import service
from app.modules.auth.models import User
from app.modules.auth.schemas import (
    LoginIn,
    MeOut,
    PasswordChange,
    PasswordReset,
    TokenOut,
    UserCreate,
    UserOut,
    UserUpdate,
)

router = APIRouter(prefix="/auth", tags=["auth"])
REFRESH_COOKIE = "refresh_token"
COOKIE_PATH = "/api/v1/auth"


def _set_refresh_cookie(response: Response, raw: str) -> None:
    s = get_settings()
    response.set_cookie(
        REFRESH_COOKIE,
        raw,
        max_age=s.refresh_token_days * 86400,
        httponly=True,
        secure=s.cookie_secure,
        samesite="strict",
        path=COOKIE_PATH,
    )


@router.post("/login", response_model=TokenOut)
def login(data: LoginIn, request: Request, response: Response, db: DB):
    service.check_login_rate(db, client_ip(request) or "unknown")
    user = service.authenticate(db, data.phone, data.password)
    token, raw = service.issue_tokens(db, user)
    db.commit()
    _set_refresh_cookie(response, raw)
    return token


@router.post("/refresh", response_model=TokenOut)
def refresh(response: Response, db: DB, refresh_token: Annotated[str | None, Cookie()] = None):
    token, raw = service.rotate_refresh(db, refresh_token)
    db.commit()
    _set_refresh_cookie(response, raw)
    return token


@router.post("/logout", status_code=204)
def logout(response: Response, db: DB, refresh_token: Annotated[str | None, Cookie()] = None):
    service.revoke_refresh(db, refresh_token)
    db.commit()
    response.delete_cookie(REFRESH_COOKIE, path=COOKIE_PATH)


@router.get("/me", response_model=MeOut)
def me(user: CurrentUser):
    return service.me_out(user)


@router.post("/me/password", status_code=204)
def change_my_password(data: PasswordChange, user: CurrentUser, db: DB):
    service.change_password(db, user, data)
    db.commit()


users_router = APIRouter(prefix="/users", tags=["users"])


@users_router.get("", response_model=list[UserOut], dependencies=[Depends(require_perm("users.manage"))])
def list_users(db: DB):
    return db.scalars(select(User).order_by(User.name)).all()


@users_router.post("", response_model=UserOut, status_code=201, dependencies=[Depends(require_perm("users.manage"))])
def create_user(data: UserCreate, db: DB):
    user = service.create_user(db, data)
    db.commit()
    return user


@users_router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: int, data: UserUpdate, db: DB, actor: Annotated[User, Depends(require_perm("users.manage"))]):
    user = service.update_user(db, user_id, data, actor.id)
    db.commit()
    return user


@users_router.post("/{user_id}/reset-password", status_code=204, dependencies=[Depends(require_perm("users.manage"))])
def reset_password(user_id: int, data: PasswordReset, db: DB):
    service.reset_password(db, user_id, data.new_password)
    db.commit()
