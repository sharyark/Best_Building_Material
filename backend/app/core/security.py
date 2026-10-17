import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import get_settings
from app.core.errors import Unauthorized

_hasher = PasswordHasher()
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


# Verified against when the user does not exist, so timing doesn't reveal valid phones.
DUMMY_HASH = hash_password("not-a-real-password")


def create_access_token(user_id: int, role: str) -> tuple[str, int]:
    s = get_settings()
    expires = datetime.now(UTC) + timedelta(minutes=s.access_token_minutes)
    token = jwt.encode(
        {"sub": str(user_id), "role": role, "exp": expires, "typ": "access"},
        s.jwt_secret,
        algorithm=ALGORITHM,
    )
    return token, s.access_token_minutes * 60


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        raise Unauthorized("Invalid or expired token", code="INVALID_TOKEN") from exc
    if payload.get("typ") != "access":
        raise Unauthorized("Invalid token type", code="INVALID_TOKEN")
    return payload


def new_refresh_token() -> tuple[str, str]:
    raw = secrets.token_urlsafe(48)
    return raw, hash_token(raw)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
