"""baseline

Revision ID: 20260510_0001
Revises:
Create Date: 2026-05-10
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260510_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("data_sources"):
        op.create_table(
            "data_sources",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("entry_url", sa.Text(), nullable=False),
            sa.Column("source", sa.String(length=80), nullable=False),
            sa.Column("type", sa.String(length=50), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("entry_url"),
        )
    if not inspector.has_table("regions"):
        op.create_table(
            "regions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=80), nullable=False),
            sa.Column("normalized_name", sa.String(length=80), nullable=False),
            sa.Column("level", sa.String(length=20), nullable=False),
            sa.UniqueConstraint("normalized_name"),
        )
    if not inspector.has_table("indicators"):
        op.create_table(
            "indicators",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("code", sa.String(length=80), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("unit", sa.String(length=20), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.UniqueConstraint("code"),
        )
    if not inspector.has_table("crawl_schedules"):
        op.create_table(
            "crawl_schedules",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("target_url", sa.Text(), nullable=False),
            sa.Column("data_source_id", sa.Integer(), sa.ForeignKey("data_sources.id"), nullable=True),
            sa.Column("interval_minutes", sa.Integer(), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False),
            sa.Column("last_run_at", sa.DateTime(), nullable=True),
            sa.Column("next_run_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
    if not inspector.has_table("crawl_jobs"):
        op.create_table(
            "crawl_jobs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("data_source_id", sa.Integer(), sa.ForeignKey("data_sources.id"), nullable=True),
            sa.Column("schedule_id", sa.Integer(), sa.ForeignKey("crawl_schedules.id"), nullable=True),
            sa.Column("target_url", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("trigger", sa.String(length=20), nullable=False),
            sa.Column("retry_count", sa.Integer(), nullable=False),
            sa.Column("total_records", sa.Integer(), nullable=False),
            sa.Column("imported_records", sa.Integer(), nullable=False),
            sa.Column("skipped_records", sa.Integer(), nullable=False),
            sa.Column("error_type", sa.String(length=40), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
        )
    else:
        columns = {column["name"] for column in inspector.get_columns("crawl_jobs")}
        if "created_at" not in columns:
            op.add_column("crawl_jobs", sa.Column("created_at", sa.DateTime(), nullable=True))
            bind.execute(
                sa.text(
                    """
                    UPDATE crawl_jobs
                    SET created_at = COALESCE(started_at, finished_at, CURRENT_TIMESTAMP)
                    WHERE created_at IS NULL
                    """
                )
            )
    if not inspector.has_table("crawl_records"):
        op.create_table(
            "crawl_records",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("data_source_id", sa.Integer(), sa.ForeignKey("data_sources.id"), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("url", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("published_at", sa.DateTime(), nullable=True),
            sa.Column("parsed_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("url", name="uq_crawl_records_url"),
        )
    if not inspector.has_table("stat_values"):
        op.create_table(
            "stat_values",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("region_id", sa.Integer(), sa.ForeignKey("regions.id"), nullable=False),
            sa.Column("indicator_id", sa.Integer(), sa.ForeignKey("indicators.id"), nullable=False),
            sa.Column("period", sa.Date(), nullable=False),
            sa.Column("value", sa.Float(), nullable=False),
            sa.Column("dimensions", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("source_id", sa.Integer(), sa.ForeignKey("data_sources.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
    if not inspector.has_table("quality_reports"):
        op.create_table(
            "quality_reports",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("crawl_job_id", sa.Integer(), sa.ForeignKey("crawl_jobs.id"), nullable=True),
            sa.Column("period", sa.Date(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("expected_regions", sa.Integer(), nullable=False),
            sa.Column("actual_regions", sa.Integer(), nullable=False),
            sa.Column("expected_indicators", sa.Integer(), nullable=False),
            sa.Column("actual_indicators", sa.Integer(), nullable=False),
            sa.Column("checked_values", sa.Integer(), nullable=False),
            sa.Column("errors", sa.JSON(), nullable=False),
            sa.Column("warnings", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
    if not inspector.has_table("publish_batches"):
        op.create_table(
            "publish_batches",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("action", sa.String(length=20), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("actor", sa.String(length=80), nullable=False),
            sa.Column("item_count", sa.Integer(), nullable=False),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
    if not inspector.has_table("stat_value_changes"):
        op.create_table(
            "stat_value_changes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("stat_value_id", sa.Integer(), sa.ForeignKey("stat_values.id"), nullable=False),
            sa.Column("actor", sa.String(length=80), nullable=False),
            sa.Column("before_value", sa.Float(), nullable=True),
            sa.Column("after_value", sa.Float(), nullable=True),
            sa.Column("before_status", sa.String(length=20), nullable=True),
            sa.Column("after_status", sa.String(length=20), nullable=True),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )


def downgrade() -> None:
    op.drop_table("stat_value_changes")
    op.drop_table("publish_batches")
    op.drop_table("quality_reports")
    op.drop_table("stat_values")
    op.drop_table("crawl_records")
    op.drop_table("crawl_jobs")
    op.drop_table("crawl_schedules")
    op.drop_table("indicators")
    op.drop_table("regions")
    op.drop_table("data_sources")
