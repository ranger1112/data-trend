from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from packages.storage import repositories as repo
from packages.storage.models import CrawlJob


def create_due_jobs(db: Session, now: datetime | None = None) -> list[CrawlJob]:
    now = now or datetime.utcnow()
    jobs: list[CrawlJob] = []
    for schedule in repo.list_due_schedules(db, now):
        if repo.has_active_crawl_job(db, schedule.data_source_id, schedule.target_url):
            continue
        job = repo.create_crawl_job(
            db,
            data_source_id=schedule.data_source_id,
            schedule_id=schedule.id,
            target_url=schedule.target_url,
            trigger="schedule",
        )
        repo.mark_schedule_run(db, schedule, now + timedelta(minutes=schedule.interval_minutes), now)
        jobs.append(job)
    return jobs
