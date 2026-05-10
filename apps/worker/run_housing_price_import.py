import argparse

from apps.api.bootstrap import bootstrap_database
from apps.api.config import get_settings
from packages.crawler.housing_price.importer import HousingPriceImportRunner
from packages.pipeline.scheduler import create_due_jobs
from packages.storage.models import Base
from packages.storage.session import create_engine_from_url, create_session_factory


def main() -> None:
    parser = argparse.ArgumentParser(description="Import housing price statistics.")
    parser.add_argument("--url", help="List page or article URL.")
    parser.add_argument("--run-due", action="store_true", help="Create and run due schedules.")
    args = parser.parse_args()
    if not args.url and not args.run_due:
        parser.error("--url or --run-due is required")

    settings = get_settings()
    bootstrap_database()
    engine = create_engine_from_url(settings.database_url)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(settings.database_url)

    with session_factory() as db:
        runner = HousingPriceImportRunner(db)
        jobs = create_due_jobs(db) if args.run_due else []
        if args.url:
            jobs.append(runner.run(url=args.url))
        else:
            jobs = [runner.run(url=job.target_url, job=job, data_source=job.data_source) for job in jobs if job.target_url]
        for job in jobs:
            print(
                {
                    "job_id": job.id,
                    "status": job.status,
                    "total_records": job.total_records,
                    "imported_records": job.imported_records,
                    "skipped_records": job.skipped_records,
                    "error_message": job.error_message,
                }
            )


if __name__ == "__main__":
    main()
