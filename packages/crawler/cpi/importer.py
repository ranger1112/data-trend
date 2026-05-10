from datetime import datetime

import httpx
from sqlalchemy.orm import Session

from packages.crawler.cpi.dto import CpiRecord
from packages.crawler.cpi.parser import CpiHtmlParser
from packages.crawler.http import HtmlFetcher
from packages.domain.constants import CPI_SOURCE_TYPE
from packages.pipeline.importers import register_importer
from packages.pipeline.quality import QualityChecker
from packages.storage import repositories as repo
from packages.storage.models import CrawlJob, DataSource


class CpiImporter:
    def __init__(self, db: Session) -> None:
        self.db = db

    def import_records(self, records: list[CpiRecord], data_source: DataSource | None = None) -> int:
        imported = 0
        for record in records:
            source = data_source or repo.get_or_create_data_source(
                self.db,
                name=record.source_title,
                entry_url=record.source_url,
                source="国家统计局",
                source_type=CPI_SOURCE_TYPE,
            )
            repo.upsert_crawl_record(
                self.db,
                data_source_id=source.id,
                title=record.source_title,
                url=record.source_url,
                published_at=record.published_at,
            )
            region = repo.get_or_create_region(self.db, name=record.region_name, level="country")
            values = {
                "cpi_yoy": record.year_on_year,
                "cpi_mom": record.month_on_month,
                "cpi_avg": record.cumulative_average,
            }
            for indicator_code, value in values.items():
                if value is None:
                    continue
                indicator = repo.get_or_create_indicator(self.db, code=indicator_code)
                repo.upsert_stat_value(
                    self.db,
                    region_id=region.id,
                    indicator_id=indicator.id,
                    period=record.period,
                    value=value,
                    source_id=source.id,
                    dimensions={"source_type": CPI_SOURCE_TYPE, "frequency": "monthly"},
                )
            imported += 1
        self.db.commit()
        return imported


class CpiImportRunner:
    def __init__(self, db: Session, fetcher: HtmlFetcher | None = None) -> None:
        self.db = db
        self.fetcher = fetcher or HtmlFetcher()
        self.parser = CpiHtmlParser()
        self.importer = CpiImporter(db)

    def run(
        self,
        url: str,
        job: CrawlJob | None = None,
        data_source: DataSource | None = None,
    ) -> CrawlJob:
        job = job or repo.create_crawl_job(
            self.db,
            data_source_id=data_source.id if data_source else None,
            target_url=url,
        )
        if job.status != "running":
            repo.mark_job_running(self.db, job)
        try:
            html = self.fetcher.fetch(url)
            records = self.parser.parse(html, source_url=url)
            imported = self.importer.import_records(records, data_source=data_source)
            repo.mark_job_finished(
                self.db,
                job,
                status="success",
                total_records=len(records),
                imported_records=imported,
                skipped_records=max(len(records) - imported, 0),
            )
            QualityChecker(source_type=CPI_SOURCE_TYPE).check_job(self.db, job)
        except Exception as exc:
            self.db.rollback()
            repo.mark_job_finished(
                self.db,
                job,
                status="failed",
                error_type=self._classify_error(exc),
                error_message=str(exc),
                finished_at=datetime.utcnow(),
            )
        return job

    def _classify_error(self, exc: Exception) -> str:
        if isinstance(exc, httpx.HTTPError):
            return "network_error"
        if isinstance(exc, ValueError):
            return "parse_error"
        return "import_error"


register_importer(CPI_SOURCE_TYPE, CpiImportRunner)
