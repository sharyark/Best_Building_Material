"""fuel entries: price per litre (amount = litres x rate)

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("expenses", sa.Column("rate_per_litre", sa.Numeric(14, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("expenses", "rate_per_litre")
