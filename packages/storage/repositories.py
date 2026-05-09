import re
from datetime import date, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from packages.domain.constants import INDICATORS
from packages.storage.models import (
    CrawlJob,
    CrawlRecord,
    DataSource,
    Indicator,
    Region,
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


def create_crawl_job(db: Session, data_source_id: int | None = None) -> CrawlJob:
    job = CrawlJob(data_source_id=data_source_id)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def mark_job_running(db: Session, job: CrawlJob) -> None:
    job.status = "running"
    job.started_at = datetime.utcnow()
    db.commit()


def mark_job_finished(
    db: Session,
    job: CrawlJob,
    status: str,
    total_records: int | None = None,
    imported_records: int | None = None,
    skipped_records: int | None = None,
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
    job.error_message = error_message
    job.finished_at = finished_at or datetime.utcnow()
    db.commit()
    db.refresh(job)
    return job


def list_crawl_jobs(db: Session) -> list[CrawlJob]:
    return list(db.scalars(select(CrawlJob).order_by(CrawlJob.id.desc()).limit(100)))


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


def list_crawl_records(db: Session) -> list[CrawlRecord]:
    return list(db.scalars(select(CrawlRecord).order_by(CrawlRecord.id.desc()).limit(100)))


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
) -> StatValue:
    if value is not None:
        stat_value.value = value
    if status is not None:
        stat_value.status = status
    if dimensions is not None:
        stat_value.dimensions = dimensions
    stat_value.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(stat_value)
    return stat_value


def list_stat_values(
    db: Session,
    status: str | None = None,
    region_id: int | None = None,
    indicator_code: str | None = None,
    period: date | None = None,
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
    return list(db.scalars(statement))


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
    values = list(db.scalars(select(StatValue).where(StatValue.id.in_(ids))))
    for value in values:
        value.status = "published"
        value.updated_at = datetime.utcnow()
    db.commit()
    return len(values)


def publish_draft_values(db: Session) -> int:
    values = list(db.scalars(select(StatValue).where(StatValue.status == "draft")))
    for value in values:
        value.status = "published"
        value.updated_at = datetime.utcnow()
    db.commit()
    return len(values)


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


def get_latest_published_values(db: Session, indicator_code: str) -> list[dict[str, Any]]:
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
            "period": value.period,
            "value": value.value,
            "dimensions": value.dimensions,
        }
        for value in values
    ]


def get_dashboard_overview(db: Session) -> dict[str, Any]:
    return {
        "regions": db.scalar(select(func.count(Region.id))) or 0,
        "indicators": db.scalar(select(func.count(Indicator.id))) or 0,
        "published_values": db.scalar(
            select(func.count(StatValue.id)).where(StatValue.status == "published")
        )
        or 0,
        "latest_period": db.scalar(select(func.max(StatValue.period))),
    }


def normalize_region_name(name: str) -> str:
    return re.sub(r"[\s\u3000]+", "", name)
