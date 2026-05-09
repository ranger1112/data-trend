import argparse

from apps.api.config import get_settings
from packages.crawler.housing_price.importer import HousingPriceImportRunner
from packages.storage.models import Base
from packages.storage.session import create_engine_from_url, create_session_factory


def main() -> None:
    parser = argparse.ArgumentParser(description="Import housing price statistics.")
    parser.add_argument("--url", required=True, help="List page or article URL.")
    args = parser.parse_args()

    settings = get_settings()
    engine = create_engine_from_url(settings.database_url)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(settings.database_url)

    with session_factory() as db:
        job = HousingPriceImportRunner(db).run(url=args.url)
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

