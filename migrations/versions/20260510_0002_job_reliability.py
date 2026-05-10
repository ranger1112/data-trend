"""job reliability fields

Revision ID: 20260510_0002
Revises: 20260510_0001
Create Date: 2026-05-10
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260510_0002"
down_revision: str | None = "20260510_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("crawl_jobs"):
        return

    columns = {column["name"] for column in inspector.get_columns("crawl_jobs")}
    if "max_retries" not in columns:
        op.add_column("crawl_jobs", sa.Column("max_retries", sa.Integer(), nullable=True))
        bind.execute(sa.text("UPDATE crawl_jobs SET max_retries = 3 WHERE max_retries IS NULL"))
    if "next_retry_at" not in columns:
        op.add_column("crawl_jobs", sa.Column("next_retry_at", sa.DateTime(), nullable=True))
    if "timeout_seconds" not in columns:
        op.add_column("crawl_jobs", sa.Column("timeout_seconds", sa.Integer(), nullable=True))
        bind.execute(sa.text("UPDATE crawl_jobs SET timeout_seconds = 1800 WHERE timeout_seconds IS NULL"))
    if "locked_at" not in columns:
        op.add_column("crawl_jobs", sa.Column("locked_at", sa.DateTime(), nullable=True))
    if "locked_by" not in columns:
        op.add_column("crawl_jobs", sa.Column("locked_by", sa.String(length=80), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("crawl_jobs"):
        return
    columns = {column["name"] for column in inspector.get_columns("crawl_jobs")}
    for column in ["locked_by", "locked_at", "timeout_seconds", "next_retry_at", "max_retries"]:
        if column in columns:
            op.drop_column("crawl_jobs", column)
