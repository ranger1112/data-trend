from apps.api.config import get_settings
from packages.storage.models import Base
from packages.storage.session import create_engine_from_url
from sqlalchemy import inspect, text


def bootstrap_database() -> None:
    engine = create_engine_from_url(get_settings().database_url)
    Base.metadata.create_all(bind=engine)
    upgrade_sqlite_schema(engine)


def upgrade_sqlite_schema(engine) -> None:
    if engine.dialect.name != "sqlite":
        return
    inspector = inspect(engine)
    if "crawl_jobs" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("crawl_jobs")}
    statements = []
    if "schedule_id" not in columns:
        statements.append("ALTER TABLE crawl_jobs ADD COLUMN schedule_id INTEGER")
    if "retry_count" not in columns:
        statements.append("ALTER TABLE crawl_jobs ADD COLUMN retry_count INTEGER DEFAULT 0")
    if "created_at" not in columns:
        statements.append("ALTER TABLE crawl_jobs ADD COLUMN created_at DATETIME")
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
        if "created_at" not in columns:
            connection.execute(
                text(
                    """
                    UPDATE crawl_jobs
                    SET created_at = COALESCE(started_at, finished_at, CURRENT_TIMESTAMP)
                    WHERE created_at IS NULL
                    """
                )
            )


if __name__ == "__main__":
    bootstrap_database()
