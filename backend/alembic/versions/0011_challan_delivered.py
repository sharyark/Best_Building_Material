"""challan delivered flag: an order reaches the khata only once it is marked delivered

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Every existing challan is already in the khata, so it counts as delivered.
    op.add_column("deliveries", sa.Column("delivered", sa.Boolean(), server_default="true", nullable=False))
    op.add_column("deliveries", sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("deliveries", sa.Column("delivered_by", sa.BigInteger(), nullable=True))
    op.create_foreign_key("fk_deliveries_delivered_by_users", "deliveries", "users", ["delivered_by"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_deliveries_delivered_by_users", "deliveries", type_="foreignkey")
    op.drop_column("deliveries", "delivered_by")
    op.drop_column("deliveries", "delivered_at")
    op.drop_column("deliveries", "delivered")
