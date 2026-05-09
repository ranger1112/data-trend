from packages.crawler.housing_price.dto import HousingPriceRecord
from packages.crawler.housing_price.importer import HousingPriceImporter
from packages.storage.models import Base, StatValue
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

