from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from apps.api.dependencies import SessionLocal
from apps.api.dependencies import get_db
from apps.api.schemas import (
    CrawlJobCreate,
    CrawlJobOut,
    DataSourceCreate,
    DataSourceOut,
    DataSourcePatch,
    PublishBatchOut,
    QualityReportOut,
    ScheduleCreate,
    ScheduleOut,
    SchedulePatch,
    StatValueChangeOut,
    StatValuePatch,
    StatValuePublishRequest,
)
from packages.crawler.housing_price.importer import HousingPriceImportRunner
from packages.pipeline.scheduler import create_due_jobs
from packages.storage import repositories as repo

router = APIRouter()


@router.post("/data-sources", response_model=DataSourceOut)
def create_data_source(payload: DataSourceCreate, db: Session = Depends(get_db)):
    return repo.create_data_source(
        db,
        name=payload.name,
        entry_url=str(payload.entry_url),
        source=payload.source,
        source_type=payload.type,
        enabled=payload.enabled,
    )


@router.get("/data-sources", response_model=list[DataSourceOut])
def list_data_sources(db: Session = Depends(get_db)):
    return repo.list_data_sources(db)


@router.patch("/data-sources/{data_source_id}", response_model=DataSourceOut)
def patch_data_source(
    data_source_id: int,
    payload: DataSourcePatch,
    db: Session = Depends(get_db),
):
    data_source = repo.get_data_source(db, data_source_id)
    if not data_source:
        raise HTTPException(status_code=404, detail="data source not found")
    return repo.update_data_source(
        db,
        data_source,
        name=payload.name,
        entry_url=str(payload.entry_url) if payload.entry_url else None,
        source=payload.source,
        source_type=payload.type,
        enabled=payload.enabled,
    )


@router.post("/crawl-jobs", response_model=CrawlJobOut)
def create_crawl_job(
    payload: CrawlJobCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    if not payload.data_source_id and not payload.url:
        raise HTTPException(status_code=422, detail="data_source_id or url is required")

    data_source = None
    target_url = str(payload.url) if payload.url else None
    if payload.data_source_id:
        data_source = repo.get_data_source(db, payload.data_source_id)
        if not data_source:
            raise HTTPException(status_code=404, detail="data source not found")
        target_url = target_url or data_source.entry_url

    if repo.has_active_crawl_job(db, data_source.id if data_source else None, target_url):
        raise HTTPException(status_code=409, detail="crawl job already running for target")

    job = repo.create_crawl_job(
        db,
        data_source_id=data_source.id if data_source else None,
        target_url=target_url,
    )
    if payload.run_now:
        background_tasks.add_task(run_crawl_job, job.id, target_url, data_source.id if data_source else None)
    return job


@router.get("/crawl-jobs", response_model=list[CrawlJobOut])
def list_crawl_jobs(
    status: str | None = Query(default=None, pattern="^(pending|running|success|failed|cancelled)$"),
    data_source_id: int | None = None,
    db: Session = Depends(get_db),
):
    return repo.list_crawl_jobs(db, status=status, data_source_id=data_source_id)


@router.post("/crawl-jobs/{job_id}/retry", response_model=CrawlJobOut)
def retry_crawl_job(job_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    job = db.get(repo.CrawlJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="crawl job not found")
    if not job.target_url:
        raise HTTPException(status_code=422, detail="crawl job target url is missing")
    retry = repo.retry_crawl_job(db, job)
    background_tasks.add_task(run_crawl_job, retry.id, retry.target_url, retry.data_source_id)
    return retry


@router.post("/crawl-jobs/{job_id}/cancel", response_model=CrawlJobOut)
def cancel_crawl_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(repo.CrawlJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="crawl job not found")
    return repo.cancel_crawl_job(db, job)


@router.post("/schedules", response_model=ScheduleOut)
def create_schedule(payload: ScheduleCreate, db: Session = Depends(get_db)):
    if payload.data_source_id and not repo.get_data_source(db, payload.data_source_id):
        raise HTTPException(status_code=404, detail="data source not found")
    return repo.create_schedule(
        db,
        name=payload.name,
        target_url=str(payload.target_url),
        data_source_id=payload.data_source_id,
        interval_minutes=payload.interval_minutes,
        enabled=payload.enabled,
        next_run_at=payload.next_run_at,
    )


@router.get("/schedules", response_model=list[ScheduleOut])
def list_schedules(db: Session = Depends(get_db)):
    return repo.list_schedules(db)


@router.patch("/schedules/{schedule_id}", response_model=ScheduleOut)
def patch_schedule(schedule_id: int, payload: SchedulePatch, db: Session = Depends(get_db)):
    schedule = repo.get_schedule(db, schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="schedule not found")
    return repo.update_schedule(
        db,
        schedule,
        name=payload.name,
        target_url=str(payload.target_url) if payload.target_url else None,
        interval_minutes=payload.interval_minutes,
        enabled=payload.enabled,
        next_run_at=payload.next_run_at,
    )


@router.post("/schedules/run-due", response_model=list[CrawlJobOut])
def run_due_schedules(db: Session = Depends(get_db)):
    return create_due_jobs(db)


@router.get("/crawl-records")
def list_crawl_records(
    status: str | None = Query(default=None, pattern="^(parsed|failed|skipped)$"),
    keyword: str | None = None,
    published_from: date | None = None,
    published_to: date | None = None,
    db: Session = Depends(get_db),
):
    return repo.list_crawl_records(
        db,
        status=status,
        keyword=keyword,
        published_from=published_from,
        published_to=published_to,
    )


@router.get("/stat-values")
def list_stat_values(
    status: str | None = Query(default=None, pattern="^(draft|quality_failed|ready_for_review|published|rejected)$"),
    region_id: int | None = None,
    indicator_code: str | None = None,
    period: date | None = None,
    house_type: str | None = None,
    area_type: str | None = None,
    db: Session = Depends(get_db),
):
    values = repo.list_stat_values(
        db,
        status=status,
        region_id=region_id,
        indicator_code=indicator_code,
        period=period,
        house_type=house_type,
        area_type=area_type,
    )
    return [repo.serialize_stat_value(value) for value in values]


@router.get("/review-items")
def list_review_items(
    region_id: int | None = None,
    indicator_code: str | None = None,
    period: date | None = None,
    house_type: str | None = None,
    area_type: str | None = None,
    db: Session = Depends(get_db),
):
    values = repo.list_stat_values(
        db,
        status="ready_for_review",
        region_id=region_id,
        indicator_code=indicator_code,
        period=period,
        house_type=house_type,
        area_type=area_type,
    )
    return [repo.serialize_stat_value(value) for value in values]


@router.patch("/stat-values/{stat_value_id}")
def patch_stat_value(stat_value_id: int, payload: StatValuePatch, db: Session = Depends(get_db)):
    stat_value = repo.get_stat_value(db, stat_value_id)
    if not stat_value:
        raise HTTPException(status_code=404, detail="stat value not found")
    return repo.update_stat_value(
        db,
        stat_value,
        value=payload.value,
        status=payload.status,
        dimensions=payload.dimensions,
        actor="admin",
        reason=payload.reason,
    )


@router.post("/stat-values/publish")
def publish_stat_values(payload: StatValuePublishRequest, db: Session = Depends(get_db)):
    count = repo.publish_stat_values(db, payload.ids)
    return {"published": count}


@router.post("/publish-batches")
def publish_batch(db: Session = Depends(get_db)):
    count = repo.publish_draft_values(db)
    return {"published": count}


@router.get("/publish-batches", response_model=list[PublishBatchOut])
def list_publish_batches(db: Session = Depends(get_db)):
    return repo.list_publish_batches(db)


@router.post("/review-batches/publish")
def publish_review_batch(payload: StatValuePublishRequest, db: Session = Depends(get_db)):
    return {"published": repo.publish_stat_values(db, payload.ids)}


@router.post("/review-batches/reject")
def reject_review_batch(payload: StatValuePublishRequest, db: Session = Depends(get_db)):
    return {"rejected": repo.reject_stat_values(db, payload.ids, reason=payload.reason)}


@router.get("/quality-reports", response_model=list[QualityReportOut])
def list_quality_reports(db: Session = Depends(get_db)):
    return repo.list_quality_reports(db)


@router.get("/stat-value-changes", response_model=list[StatValueChangeOut])
def list_stat_value_changes(stat_value_id: int | None = None, db: Session = Depends(get_db)):
    return repo.list_stat_value_changes(db, stat_value_id=stat_value_id)


def run_crawl_job(job_id: int, url: str, data_source_id: int | None) -> None:
    with SessionLocal() as db:
        job = db.get(repo.CrawlJob, job_id)
        data_source = db.get(repo.DataSource, data_source_id) if data_source_id else None
        if not job:
            return
        runner = HousingPriceImportRunner(db)
        runner.run(url=url, job=job, data_source=data_source)
