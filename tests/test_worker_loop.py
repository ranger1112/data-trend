from datetime import datetime

from apps.worker.run_housing_price_import import run_due_once
from packages.storage import repositories as repo
from packages.storage.models import Base
from packages.storage.session import create_engine_from_url, create_session_factory


def test_run_due_once_executes_due_jobs_and_keeps_going(monkeypatch, tmp_path):
    db_url = f"sqlite:///{tmp_path / 'worker.db'}"
    engine = create_engine_from_url(db_url)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(db_url)

    with session_factory() as db:
        repo.create_schedule(
            db,
            name="due",
            target_url="https://example.test/list.html",
            interval_minutes=60,
            next_run_at=datetime(2026, 1, 1, 0, 0),
        )

    def fake_run(self, url, job=None, data_source=None):
        return repo.mark_job_finished(
            self.db,
            job,
            status="failed",
            error_type="network_error",
            error_message=url,
        )

    monkeypatch.setattr("packages.crawler.housing_price.importer.HousingPriceImportRunner.run", fake_run)

    jobs = run_due_once(session_factory)

    assert len(jobs) == 1
    assert jobs[0].status == "failed"
    assert jobs[0].error_type == "network_error"

    with session_factory() as db:
        assert repo.list_crawl_jobs(db)[0].status == "failed"
