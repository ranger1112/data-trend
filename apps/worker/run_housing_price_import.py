import argparse
import json
import signal
import sys
import time
from datetime import datetime
from uuid import uuid4
from typing import Any

from apps.api.bootstrap import bootstrap_database
from apps.api.config import get_settings
from packages.crawler.cpi import importer as _cpi_importer
from packages.crawler.housing_price import importer as _housing_price_importer
from packages.pipeline.importers import UnsupportedDataSourceType, get_import_runner
from packages.pipeline.scheduler import create_due_jobs
from packages.storage import repositories as repo
from packages.storage.models import Base
from packages.storage.session import create_engine_from_url, create_session_factory


_SHUTDOWN_REQUESTED = False
_ = (_housing_price_importer, _cpi_importer)


def request_shutdown(signum: int, _frame: Any) -> None:
    global _SHUTDOWN_REQUESTED
    _SHUTDOWN_REQUESTED = True
    log_event("worker_shutdown_requested", signal=signum)


def log_event(event: str, **fields: Any) -> None:
    payload = {"event": event, "ts": datetime.utcnow().isoformat(timespec="seconds"), **fields}
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def run_due_once(session_factory) -> list[Any]:
    settings = get_settings()
    worker_id = f"worker-{uuid4().hex[:8]}"
    results = []
    with session_factory() as db:
        recovered = repo.recover_stale_running_jobs(db)
        for job in recovered:
            log_event(
                "job_recovered",
                job_id=job.id,
                retry_count=job.retry_count,
                max_retries=job.max_retries,
                next_retry_at=job.next_retry_at.isoformat() if job.next_retry_at else None,
            )
        jobs = create_due_jobs(db)
        retryable_jobs = repo.list_retryable_jobs(db)
        for job in retryable_jobs:
            job.retry_count += 1
            job.next_retry_at = None
        if retryable_jobs:
            db.commit()
            for job in retryable_jobs:
                db.refresh(job)
        jobs.extend(retryable_jobs)
        log_event("due_jobs_created", count=len(jobs))
        for job in jobs:
            if not job.target_url:
                log_event(
                    "job_skipped",
                    job_id=job.id,
                    schedule_id=job.schedule_id,
                    status=job.status,
                    error_type="missing_target_url",
                )
                continue
            locked = repo.lock_crawl_job(db, job, worker_id=worker_id)
            if locked is None:
                log_event("job_lock_skipped", job_id=job.id, status=job.status)
                continue
            try:
                source_type = locked.data_source.type if locked.data_source else "housing_price"
                runner = get_import_runner(source_type, db)
                result = runner.run(url=locked.target_url, job=locked, data_source=locked.data_source)
                if result.status == "failed":
                    repo.mark_job_retryable(
                        db,
                        result,
                        error_type=result.error_type,
                        error_message=result.error_message,
                        retry_delay_seconds=settings.crawl_job_retry_delay_seconds,
                    )
                results.append(result)
                log_event(
                    "job_finished",
                    job_id=result.id,
                    schedule_id=result.schedule_id,
                    target_url=result.target_url,
                    status=result.status,
                    retry_count=result.retry_count,
                    max_retries=result.max_retries,
                    next_retry_at=result.next_retry_at.isoformat() if result.next_retry_at else None,
                    error_type=result.error_type,
                    total_records=result.total_records,
                    imported_records=result.imported_records,
                    skipped_records=result.skipped_records,
                )
            except UnsupportedDataSourceType as exc:
                result = repo.mark_job_finished(
                    db,
                    locked,
                    status="failed",
                    error_type="unsupported_data_source_type",
                    error_message=str(exc),
                )
                results.append(result)
                log_event(
                    "job_finished",
                    job_id=result.id,
                    schedule_id=result.schedule_id,
                    target_url=result.target_url,
                    status=result.status,
                    error_type=result.error_type,
                )
            except Exception as exc:
                db.rollback()
                repo.mark_job_retryable(
                    db,
                    locked,
                    error_type="worker_exception",
                    error_message=str(exc),
                    retry_delay_seconds=settings.crawl_job_retry_delay_seconds,
                )
                log_event(
                    "job_exception",
                    job_id=locked.id,
                    schedule_id=locked.schedule_id,
                    target_url=locked.target_url,
                    status="failed",
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
        return results


def run_loop(session_factory, poll_seconds: int) -> None:
    signal.signal(signal.SIGINT, request_shutdown)
    signal.signal(signal.SIGTERM, request_shutdown)
    log_event("worker_loop_started", poll_seconds=poll_seconds)
    while not _SHUTDOWN_REQUESTED:
        try:
            run_due_once(session_factory)
        except Exception as exc:
            log_event("worker_loop_exception", error_type=type(exc).__name__, error_message=str(exc))
        for _ in range(max(poll_seconds, 1)):
            if _SHUTDOWN_REQUESTED:
                break
            time.sleep(1)
    log_event("worker_loop_stopped")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import housing price statistics.")
    parser.add_argument("--url", help="List page or article URL.")
    parser.add_argument("--run-due", action="store_true", help="Create and run due schedules.")
    parser.add_argument("--loop", action="store_true", help="Continuously create and run due schedules.")
    args = parser.parse_args()
    if not args.url and not args.run_due and not args.loop:
        parser.error("--url, --run-due or --loop is required")

    settings = get_settings()
    bootstrap_database()
    engine = create_engine_from_url(settings.database_url)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(settings.database_url)

    if args.loop:
        run_loop(session_factory, settings.worker_poll_seconds)
        return

    if args.run_due:
        jobs = run_due_once(session_factory)
        for job in jobs:
            log_event(
                "job_result",
                job_id=job.id,
                status=job.status,
                total_records=job.total_records,
                imported_records=job.imported_records,
                skipped_records=job.skipped_records,
                error_message=job.error_message,
            )
        return

    with session_factory() as db:
        runner = get_import_runner("housing_price", db)
        job = runner.run(url=args.url)
        log_event(
            "job_result",
            job_id=job.id,
            status=job.status,
            total_records=job.total_records,
            imported_records=job.imported_records,
            skipped_records=job.skipped_records,
            error_message=job.error_message,
        )
        if job.status == "failed":
            sys.exit(1)


if __name__ == "__main__":
    main()
