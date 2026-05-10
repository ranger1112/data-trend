"""operation logs

Revision ID: 20260510_0005
Revises: 20260510_0004
Create Date: 2026-05-10
"""

from alembic import op
import sqlalchemy as sa


revision = "20260510_0005"
down_revision = "20260510_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "operation_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("actor", sa.String(length=80), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("target_type", sa.String(length=80), nullable=False),
        sa.Column("target_id", sa.String(length=120), nullable=True),
        sa.Column("before", sa.JSON(), nullable=True),
        sa.Column("after", sa.JSON(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_operation_logs_action", "operation_logs", ["action"])
    op.create_index("ix_operation_logs_target", "operation_logs", ["target_type", "target_id"])


def downgrade() -> None:
    op.drop_index("ix_operation_logs_target", table_name="operation_logs")
    op.drop_index("ix_operation_logs_action", table_name="operation_logs")
    op.drop_table("operation_logs")
