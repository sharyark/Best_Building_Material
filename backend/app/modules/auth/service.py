import datetime as dt

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import Conflict, Forbidden, NotFound, TooManyAttempts, Unauthorized
from app.core.permissions import permissions_for
from app.core.security import (
    DUMMY_HASH,
    create_access_token,
    hash_password,
    hash_token,
    new_refresh_token,
    verify_password,
)
from app.modules.auth.models import LoginAttempt, RefreshToken, User
from app.modules.auth.schemas import MeOut, PasswordChange, TokenOut, UserCreate, UserUpdate


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _aware(value: dt.datetime) -> dt.datetime:
    return value if value.tzinfo else value.replace(tzinfo=dt.UTC)


def me_out(user: User) -> MeOut:
    base = {c: getattr(user, c) for c in MeOut.model_fields if c != "permissions"}
    return MeOut(**base, permissions=sorted(permissions_for(user.role)))


def check_login_rate(db: Session, ip: str) -> None:
    """Record this attempt and refuse the 6th one inside the window. Committed immediately."""
    s = get_settings()
    now = _now()
    db.execute(delete(LoginAttempt).where(LoginAttempt.at < now - dt.timedelta(days=1)))
    recent = db.scalar(
        select(func.count())
        .select_from(LoginAttempt)
        .where(LoginAttempt.ip == ip, LoginAttempt.at >= now - dt.timedelta(seconds=s.login_window_seconds))
    )
    db.add(LoginAttempt(ip=ip, at=now))
    db.commit()
    if (recent or 0) >= s.login_max_attempts:
        raise TooManyAttempts("Too many login attempts. Try again in a minute.")


def authenticate(db: Session, phone: str, password: str, portal: str | None = None) -> User:
    user = db.scalar(select(User).where(User.phone == phone))
    # Always run one hash verification so response time doesn't reveal whether the phone exists.
    ok = verify_password(user.password_hash if user else DUMMY_HASH, password)
    if not user or not ok or not user.is_active:
        raise Unauthorized("Wrong phone or password", code="INVALID_CREDENTIALS")
    # Checked only after the password is right, so it can't be used to discover which phones exist.
    if portal and user.role != portal:
        other = "accountant" if user.role == "accountant" else "owner (admin)"
        raise Forbidden(
            f"This is an {other} account. Please use the {other.split()[0]} login page.", code="WRONG_PORTAL"
        )
    user.last_login_at = _now()
    return user


def issue_tokens(db: Session, user: User) -> tuple[TokenOut, str]:
    access, expires_in = create_access_token(user.id, user.role)
    raw, hashed = new_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hashed,
            expires_at=_now() + dt.timedelta(days=get_settings().refresh_token_days),
        )
    )
    return TokenOut(access_token=access, expires_in=expires_in, user=me_out(user)), raw


def rotate_refresh(db: Session, raw: str | None) -> tuple[TokenOut, str]:
    if not raw:
        raise Unauthorized("No refresh token", code="NO_REFRESH_TOKEN")
    token = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw)))
    if token is None:
        raise Unauthorized("Invalid refresh token", code="INVALID_REFRESH_TOKEN")
    if token.revoked_at is not None:
        # A rotated token was replayed: assume theft and kill every session of this user.
        revoke_all(db, token.user_id)
        db.commit()
        raise Unauthorized("Refresh token was already used", code="REFRESH_TOKEN_REUSED")
    if _aware(token.expires_at) < _now():
        raise Unauthorized("Refresh token expired", code="INVALID_REFRESH_TOKEN")
    user = db.get(User, token.user_id)
    if user is None or not user.is_active:
        raise Unauthorized("User is inactive", code="INVALID_REFRESH_TOKEN")
    token.revoked_at = _now()
    return issue_tokens(db, user)


def revoke_refresh(db: Session, raw: str | None) -> None:
    if raw:
        db.execute(
            update(RefreshToken)
            .where(RefreshToken.token_hash == hash_token(raw), RefreshToken.revoked_at.is_(None))
            .values(revoked_at=_now())
        )


def revoke_all(db: Session, user_id: int) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )


def create_user(db: Session, data: UserCreate) -> User:
    if db.scalar(select(User.id).where(User.phone == data.phone)):
        raise Conflict("A user with this phone already exists", code="PHONE_TAKEN")
    user = User(
        name=data.name,
        phone=data.phone,
        email=data.email,
        password_hash=hash_password(data.password),
        role=data.role,
        staff_id=data.staff_id,
        party_id=data.party_id,
    )
    db.add(user)
    db.flush()
    return user


def update_user(db: Session, user_id: int, data: UserUpdate, acting_user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFound("User not found")
    changes = data.model_dump(exclude_unset=True)
    if user.id == acting_user_id and (changes.get("is_active") is False or changes.get("role") not in (None, "admin")):
        raise Conflict("You cannot deactivate or demote yourself", code="SELF_LOCKOUT")
    for key, value in changes.items():
        setattr(user, key, value)
    if changes.get("is_active") is False:
        revoke_all(db, user.id)
    db.flush()
    return user


def reset_password(db: Session, user_id: int, new_password: str) -> None:
    user = db.get(User, user_id)
    if user is None:
        raise NotFound("User not found")
    user.password_hash = hash_password(new_password)
    revoke_all(db, user.id)


def change_password(db: Session, user: User, data: PasswordChange) -> None:
    if not verify_password(user.password_hash, data.current_password):
        raise Unauthorized("Current password is wrong", code="INVALID_CREDENTIALS")
    user.password_hash = hash_password(data.new_password)
    revoke_all(db, user.id)
