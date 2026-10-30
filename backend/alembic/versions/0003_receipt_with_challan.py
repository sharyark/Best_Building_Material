"""receipt taken with a challan (paid on the spot)

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FK_NAME = "fk_deliveries_receipt_id_payments"


def upgrade() -> None:
    op.add_column(
        "deliveries", sa.Column("receipt_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True)
    )
    op.create_foreign_key(FK_NAME, "deliveries", "payments", ["receipt_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint(FK_NAME, "deliveries", type_="foreignkey")
    op.drop_column("deliveries", "receipt_id")
