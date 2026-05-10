import argparse
import json
import signal
import sys
import time
from datetime import datetime
from typing import Any

from apps.api.bootstrap import bootstrap_database
from apps.api.config import get_settings
from packages.crawler.housing_price.importer import HousingPriceImportRunner
from packages.pipeline.scheduler import create_due_jobs
from packages.storage.models import Base
from packages.storage.session import create_engine_from_url, create_session_factory


_SHUTDOWN_REQUESTED = False


def request_shutdown(signum: int, _frame: Any) -> None:
    global _SHUTDOWN_REQUESTED
    _SHUTDOWN_REQUESTED = True
    log_event("worker_shutdown_requested", signal=signum)


def log_event(event: str, **fields: Any) -> None:
    payload = {"event": event, "ts": datetime.utcnow().isoformat(timespec="seconds"), **fields}
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def run_due_once(session_factory) -> list[Any]:
    results = []
    with session_factory() as db:
        runner = HousingPriceImportRunner(db)
        jobs = create_due_jobs(db)
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
            try:
                result = runner.run(url=job.target_url, job=job, data_source=job.data_source)
                results.append(result)
                log_event(
                    "job_finished",
                    job_id=result.id,
                    schedule_id=result.schedule_id,
                    target_url=result.target_url,
                    status=result.status,
                    error_type=result.error_type,
                    total_records=result.total_records,
                    imported_records=result.imported_records,
                    skipped_records=result.skipped_records,
                )
            except Exception as exc:
                db.rollback()
                log_event(
                    "job_exception",
                    job_id=job.id,
                    schedule_id=job.schedule_id,
                    target_url=job.target_url,
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
        runner = HousingPriceImportRunner(db)
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
