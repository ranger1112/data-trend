from datetime import datetime, timedelta

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
        assert repo.list_crawl_jobs(db)[0].next_retry_at is not None


def test_run_due_once_retries_due_failed_jobs(monkeypatch, tmp_path):
    db_url = f"sqlite:///{tmp_path / 'retry.db'}"
    engine = create_engine_from_url(db_url)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(db_url)

    with session_factory() as db:
        job = repo.create_crawl_job(
            db,
            target_url="https://example.test/list.html",
            trigger="schedule",
            retry_count=0,
            max_retries=2,
            next_retry_at=datetime.utcnow() - timedelta(seconds=1),
        )
        job.status = "failed"
        job.error_type = "network_error"
        db.commit()

    def fake_run(self, url, job=None, data_source=None):
        return repo.mark_job_finished(self.db, job, status="success", total_records=1, imported_records=1)

    monkeypatch.setattr("packages.crawler.housing_price.importer.HousingPriceImportRunner.run", fake_run)

    jobs = run_due_once(session_factory)

    assert len(jobs) == 1
    assert jobs[0].status == "success"
    assert jobs[0].retry_count == 1


def test_run_due_once_recovers_stale_running_job(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'stale.db'}"
    engine = create_engine_from_url(db_url)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(db_url)

    with session_factory() as db:
        job = repo.create_crawl_job(
            db,
            target_url="https://example.test/list.html",
            timeout_seconds=1,
            max_retries=1,
        )
        job.status = "running"
        job.started_at = datetime.utcnow() - timedelta(minutes=10)
        job.locked_at = job.started_at
        job.locked_by = "dead-worker"
        db.commit()

    with session_factory() as db:
        repo.recover_stale_running_jobs(db)

    with session_factory() as db:
        job = repo.list_crawl_jobs(db)[0]
        assert job.status == "failed"
        assert job.error_type == "timeout"
        assert job.next_retry_at is not None


def test_run_due_once_fails_unknown_type_without_retry(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'unknown.db'}"
    engine = create_engine_from_url(db_url)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(db_url)

    with session_factory() as db:
        source = repo.create_data_source(
            db,
            name="未知源",
            entry_url="https://example.test/unknown.html",
            source="test",
            source_type="unknown",
        )
        repo.create_schedule(
            db,
            name="unknown",
            target_url=source.entry_url,
            data_source_id=source.id,
            interval_minutes=60,
            next_run_at=datetime.utcnow() - timedelta(minutes=1),
        )

    jobs = run_due_once(session_factory)

    assert len(jobs) == 1
    assert jobs[0].status == "failed"
    assert jobs[0].error_type == "unsupported_data_source_type"
