"""driver trip pay: usual rate on staff, amount on each challan / own-vehicle purchase

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MONEY = sa.Numeric(14, 2)


def upgrade() -> None:
    op.add_column("staff", sa.Column("trip_rate", MONEY, server_default="0", nullable=False))
    op.add_column("deliveries", sa.Column("trip_pay", MONEY, server_default="0", nullable=False))
    op.add_column("purchases", sa.Column("trip_pay", MONEY, server_default="0", nullable=False))


def downgrade() -> None:
    op.drop_column("purchases", "trip_pay")
    op.drop_column("deliveries", "trip_pay")
    op.drop_column("staff", "trip_rate")
