from datetime import datetime

from sqlalchemy.orm import Session

from packages.crawler.housing_price.dto import GovStatsArticle, HousingPriceRecord
from packages.crawler.housing_price.list_crawler import GovStatsListParser
from packages.crawler.housing_price.parser import HousingPriceHtmlParser
from packages.crawler.http import HtmlFetcher
from packages.storage import repositories as repo
from packages.storage.models import CrawlJob, DataSource


class HousingPriceImporter:
    def __init__(self, db: Session) -> None:
        self.db = db

    def import_records(self, records: list[HousingPriceRecord]) -> int:
        imported = 0
        for record in records:
            region = repo.get_or_create_region(self.db, name=record.city_name, level="city")
            source = repo.get_or_create_data_source(
                self.db,
                name=record.source_title,
                entry_url=record.source_url,
                source="国家统计局",
                source_type="housing_price",
            )
            repo.upsert_crawl_record(
                self.db,
                data_source_id=source.id,
                title=record.source_title,
                url=record.source_url,
                published_at=record.published_at,
            )
            for indicator_code, value in {
                "housing_price_mom": record.month_on_month,
                "housing_price_yoy": record.year_on_year,
                "housing_price_ytd": record.ytd_average,
            }.items():
                indicator = repo.get_or_create_indicator(self.db, code=indicator_code)
                repo.upsert_stat_value(
                    self.db,
                    region_id=region.id,
                    indicator_id=indicator.id,
                    period=record.period,
                    value=value,
                    source_id=source.id,
                    dimensions={
                        "house_type": record.house_type,
                        "area_type": record.area_type,
                    },
                )
            imported += 1
        self.db.commit()
        return imported


class HousingPriceImportRunner:
    def __init__(self, db: Session, fetcher: HtmlFetcher | None = None) -> None:
        self.db = db
        self.fetcher = fetcher or HtmlFetcher()
        self.list_parser = GovStatsListParser()
        self.article_parser = HousingPriceHtmlParser()
        self.importer = HousingPriceImporter(db)

    def run(
        self,
        url: str,
        job: CrawlJob | None = None,
        data_source: DataSource | None = None,
    ) -> CrawlJob:
        job = job or repo.create_crawl_job(self.db, data_source_id=data_source.id if data_source else None)
        repo.mark_job_running(self.db, job)
        try:
            html = self.fetcher.fetch(url)
            articles = self.list_parser.parse(html, url)
            records: list[HousingPriceRecord] = []

            for article in articles:
                records.extend(self._parse_article(article, fallback_html=html))

            if not records:
                raise ValueError("no housing price records parsed from target url")

            imported = self.importer.import_records(records)
            repo.mark_job_finished(
                self.db,
                job,
                status="success",
                total_records=len(records),
                imported_records=imported,
                skipped_records=max(len(records) - imported, 0),
            )
        except Exception as exc:
            self.db.rollback()
            repo.mark_job_finished(
                self.db,
                job,
                status="failed",
                error_message=str(exc),
                finished_at=datetime.utcnow(),
            )
        return job

    def _parse_article(self, article: GovStatsArticle, fallback_html: str) -> list[HousingPriceRecord]:
        html = fallback_html if article.url.endswith("#inline") else self.fetcher.fetch(article.url)
        return self.article_parser.parse(html, source_url=article.url)
