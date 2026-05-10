"""quality report details

Revision ID: 20260510_0003
Revises: 20260510_0002
Create Date: 2026-05-10
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260510_0003"
down_revision: str | None = "20260510_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("quality_reports"):
        return

    columns = {column["name"] for column in inspector.get_columns("quality_reports")}
    if "details" not in columns:
        op.add_column("quality_reports", sa.Column("details", sa.JSON(), nullable=True))
        bind.execute(sa.text("UPDATE quality_reports SET details = '[]' WHERE details IS NULL"))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("quality_reports"):
        return

    columns = {column["name"] for column in inspector.get_columns("quality_reports")}
    if "details" in columns:
        op.drop_column("quality_reports", "details")
