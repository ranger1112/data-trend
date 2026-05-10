"""indicator explanations

Revision ID: 20260510_0007
Revises: 20260510_0006
Create Date: 2026-05-10
"""

from alembic import op
import sqlalchemy as sa


revision = "20260510_0007"
down_revision = "20260510_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("indicators", sa.Column("methodology", sa.Text(), nullable=True))
    op.add_column("indicators", sa.Column("update_frequency", sa.String(length=80), nullable=True))
    op.add_column("indicators", sa.Column("usage_scenario", sa.Text(), nullable=True))
    op.add_column("indicators", sa.Column("caveats", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("indicators", "caveats")
    op.drop_column("indicators", "usage_scenario")
    op.drop_column("indicators", "update_frequency")
    op.drop_column("indicators", "methodology")
