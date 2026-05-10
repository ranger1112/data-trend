import re
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from packages.domain.constants import INDICATORS
from packages.storage.models import (
    CrawlJob,
    CrawlRecord,
    CrawlSchedule,
    DataSource,
    Indicator,
    PublishBatch,
    QualityReport,
    Region,
    StatValueChange,
    StatValue,
)


def create_data_source(
    db: Session,
    name: str,
    entry_url: str,
    source: str,
    source_type: str,
    enabled: bool = True,
) -> DataSource:
    data_source = DataSource(
        name=name,
        entry_url=entry_url,
        source=source,
        type=source_type,
        enabled=enabled,
    )
    db.add(data_source)
    db.commit()
    db.refresh(data_source)
    return data_source


def get_or_create_data_source(
    db: Session,
    name: str,
    entry_url: str,
    source: str,
    source_type: str,
) -> DataSource:
    existing = db.scalar(select(DataSource).where(DataSource.entry_url == entry_url))
    if existing:
        return existing
    return create_data_source(db, name, entry_url, source, source_type)


def list_data_sources(db: Session) -> list[DataSource]:
    return list(db.scalars(select(DataSource).order_by(DataSource.id.desc())))


def list_data_source_health(db: Session) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for data_source in list_data_sources(db):
        jobs = list(
            db.scalars(
                select(CrawlJob)
                .where(CrawlJob.data_source_id == data_source.id)
                .order_by(CrawlJob.id.desc())
            )
        )
        latest = jobs[0] if jobs else None
        total_jobs = len(jobs)
        success_jobs = len([job for job in jobs if job.status == "success"])
        failed_jobs = len([job for job in jobs if job.status == "failed"])
        items.append(
            {
                "id": data_source.id,
                "name": data_source.name,
                "type": data_source.type,
                "enabled": data_source.enabled,
                "entry_url": data_source.entry_url,
                "latest_job_status": latest.status if latest else None,
                "latest_job_finished_at": latest.finished_at if latest else None,
                "latest_error_type": latest.error_type if latest else None,
                "latest_error_message": latest.error_message if latest else None,
                "total_jobs": total_jobs,
                "success_jobs": success_jobs,
                "failed_jobs": failed_jobs,
                "success_rate": round(success_jobs / total_jobs, 4) if total_jobs else 0,
            }
        )
    return items


def get_data_source(db: Session, data_source_id: int) -> DataSource | None:
    return db.get(DataSource, data_source_id)


def update_data_source(
    db: Session,
    data_source: DataSource,
    name: str | None = None,
    entry_url: str | None = None,
    source: str | None = None,
    source_type: str | None = None,
    enabled: bool | None = None,
) -> DataSource:
    if name is not None:
        data_source.name = name
    if entry_url is not None:
        data_source.entry_url = entry_url
    if source is not None:
        data_source.source = source
    if source_type is not None:
        data_source.type = source_type
    if enabled is not None:
        data_source.enabled = enabled
    data_source.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(data_source)
    return data_source


def create_crawl_job(
    db: Session,
    data_source_id: int | None = None,
    schedule_id: int | None = None,
    target_url: str | None = None,
    trigger: str = "manual",
    retry_count: int = 0,
    max_retries: int = 3,
    timeout_seconds: int = 1800,
    next_retry_at: datetime | None = None,
) -> CrawlJob:
    job = CrawlJob(
        data_source_id=data_source_id,
        schedule_id=schedule_id,
        target_url=target_url,
        trigger=trigger,
        retry_count=retry_count,
        max_retries=max_retries,
        timeout_seconds=timeout_seconds,
        next_retry_at=next_retry_at,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def lock_crawl_job(db: Session, job: CrawlJob, worker_id: str, now: datetime | None = None) -> CrawlJob | None:
    now = now or datetime.utcnow()
    db.refresh(job)
    if job.status not in {"pending", "failed"}:
        return None
    if job.status == "failed" and job.next_retry_at is not None and job.next_retry_at > now:
        return None
    job.status = "running"
    job.started_at = now
    job.locked_at = now
    job.locked_by = worker_id
    job.error_type = None
    job.error_message = None
    db.commit()
    db.refresh(job)
    return job


def mark_job_running(db: Session, job: CrawlJob, worker_id: str | None = None) -> None:
    job.status = "running"
    job.started_at = datetime.utcnow()
    job.locked_at = job.started_at
    job.locked_by = worker_id
    job.error_type = None
    job.error_message = None
    db.commit()


def mark_job_finished(
    db: Session,
    job: CrawlJob,
    status: str,
    total_records: int | None = None,
    imported_records: int | None = None,
    skipped_records: int | None = None,
    error_type: str | None = None,
    error_message: str | None = None,
    finished_at: datetime | None = None,
) -> CrawlJob:
    job.status = status
    if total_records is not None:
        job.total_records = total_records
    if imported_records is not None:
        job.imported_records = imported_records
    if skipped_records is not None:
        job.skipped_records = skipped_records
    job.error_type = error_type
    job.error_message = error_message
    job.finished_at = finished_at or datetime.utcnow()
    job.locked_at = None
    job.locked_by = None
    if status in {"success", "cancelled"}:
        job.next_retry_at = None
    db.commit()
    db.refresh(job)
    return job


def mark_job_retryable(
    db: Session,
    job: CrawlJob,
    error_type: str | None,
    error_message: str | None,
    retry_delay_seconds: int = 300,
    now: datetime | None = None,
) -> CrawlJob:
    now = now or datetime.utcnow()
    job.status = "failed"
    job.error_type = error_type
    job.error_message = error_message
    job.finished_at = now
    job.locked_at = None
    job.locked_by = None
    job.next_retry_at = now + timedelta(seconds=retry_delay_seconds) if is_job_retryable(job) else None
    db.commit()
    db.refresh(job)
    return job


def is_job_retryable(job: CrawlJob) -> bool:
    return job.retry_count < job.max_retries and job.error_type in {
        "network_error",
        "timeout",
        "import_error",
        "worker_exception",
    }


def list_retryable_jobs(db: Session, now: datetime | None = None, limit: int = 20) -> list[CrawlJob]:
    now = now or datetime.utcnow()
    return list(
        db.scalars(
            select(CrawlJob)
            .where(
                CrawlJob.status == "failed",
                CrawlJob.next_retry_at.is_not(None),
                CrawlJob.next_retry_at <= now,
                CrawlJob.retry_count < CrawlJob.max_retries,
            )
            .order_by(CrawlJob.next_retry_at, CrawlJob.id)
            .limit(limit)
        )
    )


def recover_stale_running_jobs(db: Session, now: datetime | None = None) -> list[CrawlJob]:
    now = now or datetime.utcnow()
    running_jobs = list(db.scalars(select(CrawlJob).where(CrawlJob.status == "running")))
    recovered: list[CrawlJob] = []
    for job in running_jobs:
        locked_at = job.locked_at or job.started_at
        if locked_at is None:
            continue
        if locked_at + timedelta(seconds=job.timeout_seconds) > now:
            continue
        job.status = "failed"
        job.error_type = "timeout"
        job.error_message = "job lock timed out"
        job.finished_at = now
        job.locked_at = None
        job.locked_by = None
        job.next_retry_at = now if job.retry_count < job.max_retries else None
        recovered.append(job)
    if recovered:
        db.commit()
        for job in recovered:
            db.refresh(job)
    return recovered


def has_active_crawl_job(db: Session, data_source_id: int | None, target_url: str) -> bool:
    statement = select(CrawlJob).where(
        CrawlJob.status.in_(["pending", "running"]),
        CrawlJob.target_url == target_url,
    )
    if data_source_id is None:
        statement = statement.where(CrawlJob.data_source_id.is_(None))
    else:
        statement = statement.where(CrawlJob.data_source_id == data_source_id)
    return db.scalar(statement.limit(1)) is not None


def list_crawl_jobs(
    db: Session,
    status: str | None = None,
    data_source_id: int | None = None,
) -> list[CrawlJob]:
    statement = select(CrawlJob)
    if status:
        statement = statement.where(CrawlJob.status == status)
    if data_source_id:
        statement = statement.where(CrawlJob.data_source_id == data_source_id)
    statement = statement.order_by(CrawlJob.id.desc()).limit(100)
    return list(db.scalars(statement))


def get_recent_failed_jobs(db: Session, limit: int = 20) -> list[CrawlJob]:
    return list(
        db.scalars(
            select(CrawlJob)
            .where(CrawlJob.status == "failed")
            .order_by(CrawlJob.id.desc())
            .limit(limit)
        )
    )


def create_schedule(
    db: Session,
    name: str,
    target_url: str,
    interval_minutes: int,
    data_source_id: int | None = None,
    enabled: bool = True,
    next_run_at: datetime | None = None,
) -> CrawlSchedule:
    schedule = CrawlSchedule(
        name=name,
        target_url=target_url,
        data_source_id=data_source_id,
        interval_minutes=interval_minutes,
        enabled=enabled,
        next_run_at=next_run_at or datetime.utcnow(),
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule


def list_schedules(db: Session) -> list[CrawlSchedule]:
    return list(db.scalars(select(CrawlSchedule).order_by(CrawlSchedule.id.desc())))


def get_schedule(db: Session, schedule_id: int) -> CrawlSchedule | None:
    return db.get(CrawlSchedule, schedule_id)


def update_schedule(
    db: Session,
    schedule: CrawlSchedule,
    name: str | None = None,
    target_url: str | None = None,
    interval_minutes: int | None = None,
    enabled: bool | None = None,
    next_run_at: datetime | None = None,
) -> CrawlSchedule:
    if name is not None:
        schedule.name = name
    if target_url is not None:
        schedule.target_url = target_url
    if interval_minutes is not None:
        schedule.interval_minutes = interval_minutes
    if enabled is not None:
        schedule.enabled = enabled
    if next_run_at is not None:
        schedule.next_run_at = next_run_at
    schedule.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(schedule)
    return schedule


def list_due_schedules(db: Session, now: datetime) -> list[CrawlSchedule]:
    return list(
        db.scalars(
            select(CrawlSchedule).where(
                CrawlSchedule.enabled.is_(True),
                CrawlSchedule.next_run_at <= now,
            )
        )
    )


def mark_schedule_run(db: Session, schedule: CrawlSchedule, next_run_at: datetime, now: datetime) -> CrawlSchedule:
    schedule.last_run_at = now
    schedule.next_run_at = next_run_at
    schedule.updated_at = now
    db.commit()
    db.refresh(schedule)
    return schedule


def retry_crawl_job(db: Session, job: CrawlJob) -> CrawlJob:
    retry = CrawlJob(
        data_source_id=job.data_source_id,
        schedule_id=job.schedule_id,
        target_url=job.target_url,
        trigger="retry",
        retry_count=job.retry_count + 1,
        max_retries=job.max_retries,
        timeout_seconds=job.timeout_seconds,
    )
    db.add(retry)
    db.commit()
    db.refresh(retry)
    return retry


def cancel_crawl_job(db: Session, job: CrawlJob) -> CrawlJob:
    if job.status not in {"pending", "running"}:
        return job
    job.status = "cancelled"
    job.finished_at = datetime.utcnow()
    job.error_type = "cancelled"
    job.error_message = "cancelled by operator"
    job.locked_at = None
    job.locked_by = None
    job.next_retry_at = None
    db.commit()
    db.refresh(job)
    return job


def upsert_crawl_record(
    db: Session,
    data_source_id: int,
    title: str,
    url: str,
    published_at: datetime | None,
) -> CrawlRecord:
    record = db.scalar(select(CrawlRecord).where(CrawlRecord.url == url))
    if not record:
        record = CrawlRecord(data_source_id=data_source_id, title=title, url=url)
        db.add(record)
    record.title = title
    record.published_at = published_at
    record.status = "parsed"
    record.parsed_at = datetime.utcnow()
    return record


def list_crawl_records(
    db: Session,
    status: str | None = None,
    keyword: str | None = None,
    published_from: date | None = None,
    published_to: date | None = None,
) -> list[CrawlRecord]:
    statement = select(CrawlRecord)
    if status:
        statement = statement.where(CrawlRecord.status == status)
    if keyword:
        pattern = f"%{keyword}%"
        statement = statement.where(CrawlRecord.title.like(pattern))
    if published_from:
        statement = statement.where(CrawlRecord.published_at >= datetime.combine(published_from, datetime.min.time()))
    if published_to:
        statement = statement.where(CrawlRecord.published_at <= datetime.combine(published_to, datetime.max.time()))
    statement = statement.order_by(CrawlRecord.id.desc()).limit(100)
    return list(db.scalars(statement))


def get_or_create_region(db: Session, name: str, level: str) -> Region:
    normalized_name = normalize_region_name(name)
    region = db.scalar(select(Region).where(Region.normalized_name == normalized_name))
    if region:
        return region
    region = Region(name=name, normalized_name=normalized_name, level=level)
    db.add(region)
    db.flush()
    return region


def list_regions(db: Session) -> list[Region]:
    return list(db.scalars(select(Region).order_by(Region.name)))


def get_or_create_indicator(db: Session, code: str) -> Indicator:
    indicator = db.scalar(select(Indicator).where(Indicator.code == code))
    if indicator:
        return indicator
    indicator = Indicator(code=code, name=INDICATORS.get(code, code), unit="index")
    db.add(indicator)
    db.flush()
    return indicator


def list_indicators(db: Session) -> list[Indicator]:
    return list(db.scalars(select(Indicator).order_by(Indicator.code)))


def upsert_stat_value(
    db: Session,
    region_id: int,
    indicator_id: int,
    period: date,
    value: float,
    source_id: int | None,
    dimensions: dict[str, Any],
) -> StatValue:
    existing_values = db.scalars(
        select(StatValue).where(
            StatValue.region_id == region_id,
            StatValue.indicator_id == indicator_id,
            StatValue.period == period,
        )
    )
    for existing in existing_values:
        if existing.dimensions == dimensions:
            existing.value = value
            existing.source_id = source_id
            existing.updated_at = datetime.utcnow()
            return existing

    stat_value = StatValue(
        region_id=region_id,
        indicator_id=indicator_id,
        period=period,
        value=value,
        source_id=source_id,
        dimensions=dimensions,
    )
    db.add(stat_value)
    return stat_value


def get_stat_value(db: Session, stat_value_id: int) -> StatValue | None:
    return db.get(StatValue, stat_value_id)


def update_stat_value(
    db: Session,
    stat_value: StatValue,
    value: float | None,
    status: str | None,
    dimensions: dict[str, Any] | None,
    actor: str = "system",
    reason: str | None = None,
) -> StatValue:
    before_value = stat_value.value
    before_status = stat_value.status
    if value is not None:
        stat_value.value = value
    if status is not None:
        stat_value.status = status
    if dimensions is not None:
        stat_value.dimensions = dimensions
    stat_value.updated_at = datetime.utcnow()
    if before_value != stat_value.value or before_status != stat_value.status:
        db.add(
            StatValueChange(
                stat_value_id=stat_value.id,
                actor=actor,
                before_value=before_value,
                after_value=stat_value.value,
                before_status=before_status,
                after_status=stat_value.status,
                reason=reason,
            )
        )
    db.commit()
    db.refresh(stat_value)
    return stat_value


def list_stat_values(
    db: Session,
    status: str | None = None,
    region_id: int | None = None,
    indicator_code: str | None = None,
    period: date | None = None,
    house_type: str | None = None,
    area_type: str | None = None,
) -> list[StatValue]:
    statement = select(StatValue).join(StatValue.region).join(StatValue.indicator)
    if status:
        statement = statement.where(StatValue.status == status)
    if region_id:
        statement = statement.where(StatValue.region_id == region_id)
    if indicator_code:
        statement = statement.where(Indicator.code == indicator_code)
    if period:
        statement = statement.where(StatValue.period == period)
    statement = statement.order_by(StatValue.period.desc(), Region.name, Indicator.code).limit(200)
    values = list(db.scalars(statement))
    return [
        value
        for value in values
        if (not house_type or value.dimensions.get("house_type") == house_type)
        and (not area_type or value.dimensions.get("area_type") == area_type)
    ]


def serialize_stat_value(value: StatValue) -> dict[str, Any]:
    return {
        "id": value.id,
        "region_id": value.region_id,
        "region": value.region.name,
        "indicator_id": value.indicator_id,
        "indicator_code": value.indicator.code,
        "indicator_name": value.indicator.name,
        "period": value.period,
        "value": value.value,
        "dimensions": value.dimensions,
        "status": value.status,
        "source_id": value.source_id,
        "updated_at": value.updated_at,
    }


def publish_stat_values(db: Session, ids: list[int]) -> int:
    values = list(
        db.scalars(
            select(StatValue).where(
                StatValue.id.in_(ids),
                StatValue.status == "ready_for_review",
            )
        )
    )
    batch = PublishBatch(action="publish", actor="admin", item_count=len(values))
    db.add(batch)
    for value in values:
        before_status = value.status
        value.status = "published"
        value.updated_at = datetime.utcnow()
        db.add(
            StatValueChange(
                stat_value_id=value.id,
                actor="admin",
                before_value=value.value,
                after_value=value.value,
                before_status=before_status,
                after_status=value.status,
            )
        )
    db.commit()
    return len(values)


def publish_draft_values(db: Session) -> int:
    values = list(db.scalars(select(StatValue.id).where(StatValue.status == "ready_for_review")))
    return publish_stat_values(db, values)


def reject_stat_values(db: Session, ids: list[int], reason: str | None = None) -> int:
    values = list(db.scalars(select(StatValue).where(StatValue.id.in_(ids))))
    batch = PublishBatch(action="reject", actor="admin", item_count=len(values), reason=reason)
    db.add(batch)
    for value in values:
        before_status = value.status
        value.status = "rejected"
        value.updated_at = datetime.utcnow()
        db.add(
            StatValueChange(
                stat_value_id=value.id,
                actor="admin",
                before_value=value.value,
                after_value=value.value,
                before_status=before_status,
                after_status=value.status,
                reason=reason,
            )
        )
    db.commit()
    return len(values)


def list_quality_reports(db: Session) -> list[QualityReport]:
    return list(db.scalars(select(QualityReport).order_by(QualityReport.id.desc()).limit(100)))


def get_ops_summary(db: Session, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.utcnow()
    since = now - timedelta(hours=24)
    return {
        "jobs_last_24h": db.scalar(select(func.count(CrawlJob.id)).where(CrawlJob.created_at >= since)) or 0,
        "failed_jobs_last_24h": db.scalar(
            select(func.count(CrawlJob.id)).where(
                CrawlJob.created_at >= since,
                CrawlJob.status == "failed",
            )
        )
        or 0,
        "pending_jobs": db.scalar(select(func.count(CrawlJob.id)).where(CrawlJob.status == "pending")) or 0,
        "running_jobs": db.scalar(select(func.count(CrawlJob.id)).where(CrawlJob.status == "running")) or 0,
        "quality_failed_reports": db.scalar(
            select(func.count(QualityReport.id)).where(QualityReport.status == "failed")
        )
        or 0,
        "review_pending_values": db.scalar(
            select(func.count(StatValue.id)).where(StatValue.status == "ready_for_review")
        )
        or 0,
        "last_success_at": db.scalar(
            select(func.max(CrawlJob.finished_at)).where(CrawlJob.status == "success")
        ),
        "next_schedule_at": db.scalar(
            select(func.min(CrawlSchedule.next_run_at)).where(
                CrawlSchedule.enabled.is_(True),
                CrawlSchedule.next_run_at.is_not(None),
            )
        ),
    }


def list_publish_batches(db: Session) -> list[PublishBatch]:
    return list(db.scalars(select(PublishBatch).order_by(PublishBatch.id.desc()).limit(100)))


def list_stat_value_changes(db: Session, stat_value_id: int | None = None) -> list[StatValueChange]:
    statement = select(StatValueChange)
    if stat_value_id:
        statement = statement.where(StatValueChange.stat_value_id == stat_value_id)
    return list(db.scalars(statement.order_by(StatValueChange.id.desc()).limit(100)))


def get_published_trend(
    db: Session,
    region_id: int,
    indicator_code: str,
    house_type: str | None = None,
    area_type: str | None = None,
) -> list[dict[str, Any]]:
    indicator = db.scalar(select(Indicator).where(Indicator.code == indicator_code))
    if not indicator:
        return []
    values = db.scalars(
        select(StatValue)
        .where(
            StatValue.region_id == region_id,
            StatValue.indicator_id == indicator.id,
            StatValue.status == "published",
        )
        .order_by(StatValue.period)
    )
    items = []
    for value in values:
        if house_type and value.dimensions.get("house_type") != house_type:
            continue
        if area_type and value.dimensions.get("area_type") != area_type:
            continue
        items.append({"period": value.period, "value": value.value, "dimensions": value.dimensions})
    return items


def get_latest_published_update_time(db: Session) -> datetime | None:
    return db.scalar(select(func.max(StatValue.updated_at)).where(StatValue.status == "published"))


def get_latest_published_values(
    db: Session,
    indicator_code: str,
    house_type: str | None = None,
    area_type: str | None = None,
) -> list[dict[str, Any]]:
    indicator = db.scalar(select(Indicator).where(Indicator.code == indicator_code))
    if not indicator:
        return []
    latest_period = db.scalar(
        select(func.max(StatValue.period)).where(
            StatValue.indicator_id == indicator.id,
            StatValue.status == "published",
        )
    )
    if not latest_period:
        return []
    values = db.scalars(
        select(StatValue).where(
            StatValue.indicator_id == indicator.id,
            StatValue.status == "published",
            StatValue.period == latest_period,
        )
    )
    return [
        {
            "region": value.region.name,
            "region_id": value.region_id,
            "period": value.period,
            "value": value.value,
            "dimensions": value.dimensions,
        }
        for value in values
        if (not house_type or value.dimensions.get("house_type") == house_type)
        and (not area_type or value.dimensions.get("area_type") == area_type)
    ]


def get_latest_period_for_indicator(db: Session, indicator_code: str) -> date | None:
    indicator = db.scalar(select(Indicator).where(Indicator.code == indicator_code))
    if not indicator:
        return None
    return db.scalar(
        select(func.max(StatValue.period)).where(
            StatValue.indicator_id == indicator.id,
            StatValue.status == "published",
        )
    )


def get_published_rankings(
    db: Session,
    indicator_code: str,
    house_type: str | None = None,
    area_type: str | None = None,
    limit: int = 10,
) -> dict[str, list[dict[str, Any]]]:
    ranking_area_type = area_type
    if area_type is None and indicator_code.startswith("housing_price_"):
        ranking_area_type = "none"
    values = get_latest_published_values(
        db,
        indicator_code=indicator_code,
        house_type=house_type,
        area_type=ranking_area_type,
    )
    sorted_values = sorted(values, key=lambda item: item["value"], reverse=True)
    return {
        "top": sorted_values[:limit],
        "bottom": list(reversed(sorted_values[-limit:])),
    }


def get_dashboard_overview(db: Session) -> dict[str, Any]:
    return {
        "regions": db.scalar(select(func.count(Region.id))) or 0,
        "indicators": db.scalar(select(func.count(Indicator.id))) or 0,
        "published_values": db.scalar(
            select(func.count(StatValue.id)).where(StatValue.status == "published")
        )
        or 0,
        "latest_period": db.scalar(
            select(func.max(StatValue.period)).where(StatValue.status == "published")
        ),
    }


def normalize_region_name(name: str) -> str:
    return re.sub(r"[\s\u3000]+", "", name)
