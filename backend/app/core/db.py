from collections.abc import Iterator
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, Integer, Numeric, create_engine, func
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings

# BIGSERIAL on Postgres, plain autoincrement INTEGER on SQLite (used for fast tests).
BigIntPK = BigInteger().with_variant(Integer, "sqlite")
BigIntFK = BigInteger().with_variant(Integer, "sqlite")
Money = Numeric(14, 2)  # never float
Qty = Numeric(12, 3)
Rate = Numeric(14, 4)

ZERO = Decimal("0")


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Deliberately not a foreign key: users -> staff/parties -> created_by -> users would be a cycle.
    # The audit log is the authoritative record of who did what.
    created_by: Mapped[int | None] = mapped_column(BigIntFK, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        kwargs: dict = {"connect_args": {"check_same_thread": False}}
        if ":memory:" in url or url.endswith("sqlite://"):
            kwargs["poolclass"] = StaticPool
        return create_engine(url, **kwargs)
    return create_engine(url, pool_pre_ping=True)


engine = make_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, autoflush=True)


def get_db() -> Iterator[Session]:
    """One session per request. Routers commit explicitly; any error rolls back on close."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
