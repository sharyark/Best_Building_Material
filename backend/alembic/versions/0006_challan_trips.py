"""trips per challan: each trolley/dumper load of loose material is one trip for the driver

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Existing challans count as one trip each, which is what their saved trip pay was based on.
    op.add_column("deliveries", sa.Column("trips", sa.Integer(), server_default="1", nullable=False))


def downgrade() -> None:
    op.drop_column("deliveries", "trips")
