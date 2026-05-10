from datetime import date

from packages.crawler.cpi.importer import CpiImportRunner
from packages.crawler.cpi.parser import CpiHtmlParser
from packages.storage import repositories as repo
from packages.storage.models import Base
from packages.storage.session import create_engine_from_url, create_session_factory


CPI_HTML = """
<html>
<head><title>2026年3月份居民消费价格同比下降0.1%</title></head>
<body>
<p>发布时间：2026/04/13 09:30</p>
<p>2026年3月份，全国居民消费价格同比下降0.1%。其中，城市下降0.1%，农村下降0.2%。</p>
<p>3月份，全国居民消费价格环比下降0.4%。</p>
<p>1—3月平均，全国居民消费价格比上年同期下降0.1%。</p>
</body>
</html>
"""


class FakeFetcher:
    def fetch(self, url: str) -> str:
        return CPI_HTML


def test_cpi_parser_extracts_core_values():
    records = CpiHtmlParser().parse(CPI_HTML, "https://example.test/cpi.html")

    assert len(records) == 1
    assert records[0].period == date(2026, 3, 1)
    assert records[0].year_on_year == -0.1
    assert records[0].month_on_month == -0.4
    assert records[0].cumulative_average == -0.1


def test_cpi_importer_publishes_unified_stat_values(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'cpi.db'}"
    engine = create_engine_from_url(db_url)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(db_url)

    with session_factory() as db:
        source = repo.create_data_source(
            db,
            name="国家统计局 CPI",
            entry_url="https://example.test/cpi.html",
            source="国家统计局",
            source_type="cpi",
        )
        runner = CpiImportRunner(db, fetcher=FakeFetcher())
        job = runner.run(source.entry_url, data_source=source)

        assert job.status == "success"
        values = repo.list_stat_values(db, indicator_code="cpi_yoy")
        assert values[0].region.name == "全国"
        assert values[0].value == -0.1
        assert values[0].dimensions["source_type"] == "cpi"
        report = repo.list_quality_reports(db)[0]
        assert report.status == "passed"
        assert report.details == []
