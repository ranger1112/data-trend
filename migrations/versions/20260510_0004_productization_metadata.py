"""productization metadata and configs

Revision ID: 20260510_0004
Revises: 20260510_0003
Create Date: 2026-05-10
"""

from alembic import op
import sqlalchemy as sa


revision = "20260510_0004"
down_revision = "20260510_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("regions", sa.Column("parent_id", sa.Integer(), nullable=True))
    op.add_column("regions", sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("regions", sa.Column("display_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_foreign_key("fk_regions_parent_id", "regions", "regions", ["parent_id"], ["id"])

    op.add_column("indicators", sa.Column("category", sa.String(length=50), nullable=False, server_default="general"))
    op.add_column("indicators", sa.Column("display_name", sa.String(length=120), nullable=True))
    op.add_column("indicators", sa.Column("precision", sa.Integer(), nullable=False, server_default="2"))
    op.add_column("indicators", sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("indicators", sa.Column("default_dimensions", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("indicators", sa.Column("miniapp_visible", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("indicators", sa.Column("default_chart_type", sa.String(length=40), nullable=False, server_default="line"))

    op.create_table(
        "app_configs",
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("app_configs")
    op.drop_column("indicators", "default_chart_type")
    op.drop_column("indicators", "miniapp_visible")
    op.drop_column("indicators", "default_dimensions")
    op.drop_column("indicators", "sort_order")
    op.drop_column("indicators", "precision")
    op.drop_column("indicators", "display_name")
    op.drop_column("indicators", "category")
    op.drop_constraint("fk_regions_parent_id", "regions", type_="foreignkey")
    op.drop_column("regions", "display_enabled")
    op.drop_column("regions", "sort_order")
    op.drop_column("regions", "parent_id")
