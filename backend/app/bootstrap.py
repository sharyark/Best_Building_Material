"""First-run setup: system chart of accounts, a cash account and the first admin user.

python -m app.bootstrap
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.accounting.chart import ensure_chart
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.security import hash_password
from app.modules.auth.models import User
from app.modules.masters.models import MoneyAccount
from app.modules.masters.schemas import MoneyAccountIn
from app.modules.masters.service import create_money_account


def bootstrap(db: Session) -> None:
    settings = get_settings()
    ensure_chart(db)
    if not db.scalar(select(func.count()).select_from(MoneyAccount)):
        create_money_account(db, MoneyAccountIn(name="Cash in Hand", kind="cash"))
    if not db.scalar(select(func.count()).select_from(User)):
        db.add(
            User(
                name=settings.bootstrap_admin_name,
                phone=settings.bootstrap_admin_phone,
                password_hash=hash_password(settings.bootstrap_admin_password),
                role="admin",
            )
        )
    db.commit()


if __name__ == "__main__":
    with SessionLocal() as session:
        bootstrap(session)
    print("Bootstrap complete.")
