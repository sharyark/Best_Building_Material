"""wage settlement: why pay was cut (chutti, fine, damage...)

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("wage_settlements", sa.Column("deduction_reason", sa.String(120), nullable=True))


def downgrade() -> None:
    op.drop_column("wage_settlements", "deduction_reason")
