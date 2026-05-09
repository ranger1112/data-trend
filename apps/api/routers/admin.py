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
    StatValuePatch,
    StatValuePublishRequest,
)
from packages.crawler.housing_price.importer import HousingPriceImportRunner
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

    job = repo.create_crawl_job(db, data_source_id=data_source.id if data_source else None)
    if payload.run_now:
        background_tasks.add_task(run_crawl_job, job.id, target_url, data_source.id if data_source else None)
    return job


@router.get("/crawl-jobs", response_model=list[CrawlJobOut])
def list_crawl_jobs(db: Session = Depends(get_db)):
    return repo.list_crawl_jobs(db)


@router.get("/crawl-records")
def list_crawl_records(db: Session = Depends(get_db)):
    return repo.list_crawl_records(db)


@router.get("/stat-values")
def list_stat_values(
    status: str | None = Query(default=None, pattern="^(draft|published|rejected)$"),
    region_id: int | None = None,
    indicator_code: str | None = None,
    period: date | None = None,
    db: Session = Depends(get_db),
):
    values = repo.list_stat_values(
        db,
        status=status,
        region_id=region_id,
        indicator_code=indicator_code,
        period=period,
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
    )


@router.post("/stat-values/publish")
def publish_stat_values(payload: StatValuePublishRequest, db: Session = Depends(get_db)):
    count = repo.publish_stat_values(db, payload.ids)
    return {"published": count}


@router.post("/publish-batches")
def publish_batch(db: Session = Depends(get_db)):
    count = repo.publish_draft_values(db)
    return {"published": count}


def run_crawl_job(job_id: int, url: str, data_source_id: int | None) -> None:
    with SessionLocal() as db:
        job = db.get(repo.CrawlJob, job_id)
        data_source = db.get(repo.DataSource, data_source_id) if data_source_id else None
        if not job:
            return
        runner = HousingPriceImportRunner(db)
        runner.run(url=url, job=job, data_source=data_source)
