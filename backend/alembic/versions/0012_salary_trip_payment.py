"""payments: salary and trip money paid together ('sal_trip'), with the trip part kept apart

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("trip_amount", sa.Numeric(14, 2), server_default="0", nullable=False))


def downgrade() -> None:
    op.drop_column("payments", "trip_amount")
