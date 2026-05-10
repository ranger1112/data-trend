from packages.crawler.housing_price.dto import HousingPriceRecord
from packages.crawler.housing_price.importer import HousingPriceImporter, HousingPriceImportRunner
from packages.storage.models import Base, CrawlRecord, StatValue
from packages.storage.session import create_engine_from_url, create_session_factory


def test_importer_is_idempotent(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = create_engine_from_url(db_url)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(db_url)

    record = HousingPriceRecord(
        city_name="北京",
        period=__import__("datetime").date(2025, 10, 1),
        house_type="new_house",
        area_type="none",
        month_on_month=100.2,
        year_on_year=101.1,
        ytd_average=99.8,
        source_title="2025年10月份70个大中城市商品住宅销售价格变动情况",
        source_url="https://example.test/article.html",
    )

    with session_factory() as db:
        importer = HousingPriceImporter(db)
        importer.import_records([record])
        importer.import_records([record])

        assert db.query(StatValue).count() == 3


def test_importer_reuses_crawl_record_for_same_article(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'same_article.db'}"
    engine = create_engine_from_url(db_url)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(db_url)

    base_record = HousingPriceRecord(
        city_name="北京",
        period=__import__("datetime").date(2025, 10, 1),
        house_type="new_house",
        area_type="none",
        month_on_month=100.2,
        year_on_year=101.1,
        ytd_average=99.8,
        source_title="2025年10月份70个大中城市商品住宅销售价格变动情况",
        source_url="https://example.test/article.html",
    )
    second_record = HousingPriceRecord(
        city_name="上海",
        period=base_record.period,
        house_type="second_hand",
        area_type="none",
        month_on_month=99.7,
        year_on_year=100.4,
        ytd_average=98.9,
        source_title=base_record.source_title,
        source_url=base_record.source_url,
    )

    with session_factory() as db:
        importer = HousingPriceImporter(db)
        importer.import_records([base_record, second_record])

        assert db.query(CrawlRecord).count() == 1
        assert db.query(StatValue).count() == 6


def test_runner_marks_empty_parse_as_failed(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'empty.db'}"
    engine = create_engine_from_url(db_url)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(db_url)

    class EmptyFetcher:
        def fetch(self, url):
            return "<html><head><title>空页面</title></head><body></body></html>"

    with session_factory() as db:
        job = HousingPriceImportRunner(db, fetcher=EmptyFetcher()).run("https://example.test/empty.html")

        assert job.status == "failed"
        assert job.error_type == "no_records"
        assert "no housing price records" in job.error_message
