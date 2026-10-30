"""challan loads (dumper/bucket, half) and a second material per challan

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FK_NAME = "fk_deliveries_extra_material_id_materials"


def upgrade() -> None:
    op.add_column("deliveries", sa.Column("load_unit", sa.String(length=10), nullable=True))
    op.add_column("deliveries", sa.Column("load_size", sa.String(length=5), server_default="full", nullable=False))
    # Existing challans were all sold in the material's own unit, so stock taken = qty.
    op.add_column("deliveries", sa.Column("stock_qty", sa.Numeric(precision=12, scale=3), nullable=True))
    op.execute("UPDATE deliveries SET stock_qty = qty")
    op.alter_column("deliveries", "stock_qty", nullable=False)
    op.add_column(
        "deliveries",
        sa.Column("extra_material_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True),
    )
    op.add_column("deliveries", sa.Column("extra_qty", sa.Numeric(precision=12, scale=3), nullable=True))
    op.add_column("deliveries", sa.Column("extra_unit", sa.String(length=10), nullable=True))
    op.add_column("deliveries", sa.Column("extra_rate", sa.Numeric(precision=14, scale=2), nullable=True))
    op.add_column(
        "deliveries", sa.Column("extra_amount", sa.Numeric(precision=14, scale=2), server_default="0", nullable=False)
    )
    op.add_column(
        "deliveries",
        sa.Column("extra_cost_amount", sa.Numeric(precision=14, scale=2), server_default="0", nullable=False),
    )
    op.create_foreign_key(FK_NAME, "deliveries", "materials", ["extra_material_id"], ["id"])
    op.add_column("materials", sa.Column("dumper_qty", sa.Numeric(precision=12, scale=3), nullable=True))
    op.add_column("materials", sa.Column("dumper_rate", sa.Numeric(precision=14, scale=2), nullable=True))
    op.add_column("materials", sa.Column("bucket_qty", sa.Numeric(precision=12, scale=3), nullable=True))
    op.add_column("materials", sa.Column("bucket_rate", sa.Numeric(precision=14, scale=2), nullable=True))


def downgrade() -> None:
    for col in ("bucket_rate", "bucket_qty", "dumper_rate", "dumper_qty"):
        op.drop_column("materials", col)
    op.drop_constraint(FK_NAME, "deliveries", type_="foreignkey")
    for col in (
        "extra_cost_amount", "extra_amount", "extra_rate", "extra_unit", "extra_qty", "extra_material_id",
        "stock_qty", "load_size", "load_unit",
    ):  # fmt: skip
        op.drop_column("deliveries", col)
