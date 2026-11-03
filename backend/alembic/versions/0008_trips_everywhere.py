"""trip pay on rentals (operator) and trip counts on own-vehicle purchases

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Existing documents count as one trip with no trip pay, as they were saved.
    op.add_column("rentals", sa.Column("trip_pay", sa.Numeric(14, 2), server_default="0", nullable=False))
    op.add_column("rentals", sa.Column("trips", sa.Integer(), server_default="1", nullable=False))
    op.add_column("purchases", sa.Column("trips", sa.Integer(), server_default="1", nullable=False))


def downgrade() -> None:
    op.drop_column("purchases", "trips")
    op.drop_column("rentals", "trips")
    op.drop_column("rentals", "trip_pay")
