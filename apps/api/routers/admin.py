from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from apps.api.dependencies import SessionLocal
from apps.api.dependencies import get_db
from apps.api.config import get_settings
from apps.api.schemas import (
    AlertTestOut,
    AppConfigOut,
    AppConfigPatch,
    IndicatorOut,
    IndicatorPatch,
    CrawlJobCreate,
    CrawlJobDetailOut,
    CrawlJobOut,
    DataSourceCreate,
    DataSourceDetailOut,
    DataSourceHealthOut,
    DataSourceOut,
    OpsSummaryOut,
    OperationLogOut,
    DataSourcePatch,
    PublishBatchOut,
    QualityReportOut,
    QualityReportDetailOut,
    ReviewBatchPreviewOut,
    ScheduleCreate,
    ScheduleOut,
    SchedulePatch,
    StatValueChangeOut,
    StatValuePatch,
    StatValuePublishRequest,
)
from apps.api.security import AdminPrincipal, require_role
from packages.crawler.cpi import importer as _cpi_importer
from packages.crawler.housing_price import importer as _housing_price_importer
from packages.pipeline.importers import UnsupportedDataSourceType, get_import_runner, list_importer_types
from packages.pipeline.scheduler import create_due_jobs
from packages.storage import repositories as repo

router = APIRouter()
_ = (_housing_price_importer, _cpi_importer)


@router.post("/data-sources", response_model=DataSourceOut)
def create_data_source(
    payload: DataSourceCreate,
    db: Session = Depends(get_db),
    principal: AdminPrincipal = Depends(require_role("operator")),
):
    data_source = repo.create_data_source(
        db,
        name=payload.name,
        entry_url=str(payload.entry_url),
        source=payload.source,
        source_type=payload.type,
        enabled=payload.enabled,
    )
    repo.log_operation(
        db,
        actor=principal.username,
        action="data_source.create",
        target_type="data_source",
        target_id=data_source.id,
        after=repo.serialize_data_source(data_source),
    )
    db.commit()
    db.refresh(data_source)
    return data_source


@router.get("/data-sources", response_model=list[DataSourceOut])
def list_data_sources(db: Session = Depends(get_db), _principal=Depends(require_role("readonly"))):
    return repo.list_data_sources(db)


@router.get("/data-source-types", response_model=list[str])
def list_data_source_types(_principal=Depends(require_role("readonly"))):
    return list_importer_types()


@router.get("/data-sources/health", response_model=list[DataSourceHealthOut])
def list_data_source_health(db: Session = Depends(get_db), _principal=Depends(require_role("readonly"))):
    return repo.list_data_source_health(db)


@router.get("/data-sources/{data_source_id}/detail", response_model=DataSourceDetailOut)
def get_data_source_detail(
    data_source_id: int,
    db: Session = Depends(get_db),
    _principal=Depends(require_role("readonly")),
):
    detail = repo.get_data_source_detail(db, data_source_id)
    if not detail:
        raise HTTPException(status_code=404, detail="data source not found")
    return detail


@router.patch("/data-sources/{data_source_id}", response_model=DataSourceOut)
def patch_data_source(
    data_source_id: int,
    payload: DataSourcePatch,
    db: Session = Depends(get_db),
    principal: AdminPrincipal = Depends(require_role("operator")),
):
    data_source = repo.get_data_source(db, data_source_id)
    if not data_source:
        raise HTTPException(status_code=404, detail="data source not found")
    before = repo.serialize_data_source(data_source)
    updated = repo.update_data_source(
        db,
        data_source,
        name=payload.name,
        entry_url=str(payload.entry_url) if payload.entry_url else None,
        source=payload.source,
        source_type=payload.type,
        enabled=payload.enabled,
    )
    repo.log_operation(
        db,
        actor=principal.username,
        action="data_source.update",
        target_type="data_source",
        target_id=updated.id,
        before=before,
        after=repo.serialize_data_source(updated),
    )
    db.commit()
    db.refresh(updated)
    return updated


@router.post("/crawl-jobs", response_model=CrawlJobOut)
def create_crawl_job(
    payload: CrawlJobCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _principal=Depends(require_role("operator")),
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

    defaults = repo.get_app_config(db, "data_source.defaults").value
    job = repo.create_crawl_job(
        db,
        data_source_id=data_source.id if data_source else None,
        target_url=target_url,
        max_retries=int(defaults.get("max_retries", get_settings().crawl_job_max_retries)),
        timeout_seconds=int(defaults.get("timeout_seconds", get_settings().crawl_job_timeout_seconds)),
    )
    if payload.run_now:
        background_tasks.add_task(run_crawl_job, job.id, target_url, data_source.id if data_source else None)
    return job


@router.get("/crawl-jobs", response_model=list[CrawlJobOut])
def list_crawl_jobs(
    status: str | None = Query(default=None, pattern="^(pending|running|success|failed|cancelled)$"),
    data_source_id: int | None = None,
    db: Session = Depends(get_db),
    _principal=Depends(require_role("readonly")),
):
    return repo.list_crawl_jobs(db, status=status, data_source_id=data_source_id)


@router.get("/crawl-jobs/{job_id}/detail", response_model=CrawlJobDetailOut)
def get_crawl_job_detail(
    job_id: int,
    db: Session = Depends(get_db),
    _principal=Depends(require_role("readonly")),
):
    detail = repo.get_crawl_job_detail(db, job_id)
    if not detail:
        raise HTTPException(status_code=404, detail="crawl job not found")
    return detail


@router.post("/crawl-jobs/{job_id}/retry", response_model=CrawlJobOut)
def retry_crawl_job(
    job_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _principal=Depends(require_role("operator")),
):
    job = db.get(repo.CrawlJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="crawl job not found")
    if not job.target_url:
        raise HTTPException(status_code=422, detail="crawl job target url is missing")
    retry = repo.retry_crawl_job(db, job)
    background_tasks.add_task(run_crawl_job, retry.id, retry.target_url, retry.data_source_id)
    return retry


@router.post("/crawl-jobs/{job_id}/cancel", response_model=CrawlJobOut)
def cancel_crawl_job(
    job_id: int,
    db: Session = Depends(get_db),
    _principal=Depends(require_role("operator")),
):
    job = db.get(repo.CrawlJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="crawl job not found")
    return repo.cancel_crawl_job(db, job)


@router.post("/schedules", response_model=ScheduleOut)
def create_schedule(
    payload: ScheduleCreate,
    db: Session = Depends(get_db),
    _principal=Depends(require_role("operator")),
):
    if payload.data_source_id and not repo.get_data_source(db, payload.data_source_id):
        raise HTTPException(status_code=404, detail="data source not found")
    defaults = repo.get_app_config(db, "data_source.defaults").value
    return repo.create_schedule(
        db,
        name=payload.name,
        target_url=str(payload.target_url),
        data_source_id=payload.data_source_id,
        interval_minutes=payload.interval_minutes or int(defaults.get("interval_minutes", 1440)),
        enabled=payload.enabled,
        next_run_at=payload.next_run_at,
    )


@router.get("/schedules", response_model=list[ScheduleOut])
def list_schedules(db: Session = Depends(get_db), _principal=Depends(require_role("readonly"))):
    return repo.list_schedules(db)


@router.patch("/schedules/{schedule_id}", response_model=ScheduleOut)
def patch_schedule(
    schedule_id: int,
    payload: SchedulePatch,
    db: Session = Depends(get_db),
    _principal=Depends(require_role("operator")),
):
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
def run_due_schedules(db: Session = Depends(get_db), _principal=Depends(require_role("operator"))):
    return create_due_jobs(db)


@router.get("/crawl-records")
def list_crawl_records(
    status: str | None = Query(default=None, pattern="^(parsed|failed|skipped)$"),
    keyword: str | None = None,
    published_from: date | None = None,
    published_to: date | None = None,
    db: Session = Depends(get_db),
    _principal=Depends(require_role("readonly")),
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
    data_source_id: int | None = None,
    db: Session = Depends(get_db),
    _principal=Depends(require_role("readonly")),
):
    values = repo.list_stat_values(
        db,
        status=status,
        region_id=region_id,
        indicator_code=indicator_code,
        period=period,
        house_type=house_type,
        area_type=area_type,
        data_source_id=data_source_id,
    )
    return [repo.serialize_stat_value(value) for value in values]


@router.get("/review-items")
def list_review_items(
    region_id: int | None = None,
    indicator_code: str | None = None,
    period: date | None = None,
    house_type: str | None = None,
    area_type: str | None = None,
    data_source_id: int | None = None,
    db: Session = Depends(get_db),
    _principal=Depends(require_role("reviewer")),
):
    values = repo.list_stat_values(
        db,
        status="ready_for_review",
        region_id=region_id,
        indicator_code=indicator_code,
        period=period,
        house_type=house_type,
        area_type=area_type,
        data_source_id=data_source_id,
    )
    return [repo.serialize_stat_value(value) for value in values]


@router.patch("/stat-values/{stat_value_id}")
def patch_stat_value(
    stat_value_id: int,
    payload: StatValuePatch,
    db: Session = Depends(get_db),
    principal: AdminPrincipal = Depends(require_role("reviewer")),
):
    stat_value = repo.get_stat_value(db, stat_value_id)
    if not stat_value:
        raise HTTPException(status_code=404, detail="stat value not found")
    return repo.update_stat_value(
        db,
        stat_value,
        value=payload.value,
        status=payload.status,
        dimensions=payload.dimensions,
        actor=principal.username,
        reason=payload.reason,
    )


@router.post("/stat-values/publish")
def publish_stat_values(
    payload: StatValuePublishRequest,
    db: Session = Depends(get_db),
    principal: AdminPrincipal = Depends(require_role("reviewer")),
):
    count = repo.publish_stat_values(db, payload.ids, actor=principal.username)
    return {"published": count}


@router.post("/publish-batches")
def publish_batch(db: Session = Depends(get_db), _principal=Depends(require_role("reviewer"))):
    count = repo.publish_draft_values(db)
    return {"published": count}


@router.get("/publish-batches", response_model=list[PublishBatchOut])
def list_publish_batches(db: Session = Depends(get_db), _principal=Depends(require_role("readonly"))):
    return repo.list_publish_batches(db)


@router.post("/review-batches/publish")
def publish_review_batch(
    payload: StatValuePublishRequest,
    db: Session = Depends(get_db),
    principal: AdminPrincipal = Depends(require_role("reviewer")),
):
    return {"published": repo.publish_stat_values(db, payload.ids, actor=principal.username)}


@router.post("/review-batches/reject")
def reject_review_batch(
    payload: StatValuePublishRequest,
    db: Session = Depends(get_db),
    principal: AdminPrincipal = Depends(require_role("reviewer")),
):
    return {
        "rejected": repo.reject_stat_values(
            db,
            payload.ids,
            reason=payload.reason,
            actor=principal.username,
        )
    }


@router.post("/review-batches/publish/preview", response_model=ReviewBatchPreviewOut)
def preview_publish_review_batch(
    payload: StatValuePublishRequest,
    db: Session = Depends(get_db),
    _principal=Depends(require_role("reviewer")),
):
    return repo.preview_stat_value_batch(db, payload.ids, action="publish")


@router.post("/review-batches/reject/preview", response_model=ReviewBatchPreviewOut)
def preview_reject_review_batch(
    payload: StatValuePublishRequest,
    db: Session = Depends(get_db),
    _principal=Depends(require_role("reviewer")),
):
    return repo.preview_stat_value_batch(db, payload.ids, action="reject")


@router.get("/quality-reports", response_model=list[QualityReportOut])
def list_quality_reports(db: Session = Depends(get_db), _principal=Depends(require_role("readonly"))):
    return repo.list_quality_reports(db)


@router.get("/quality-reports/{quality_report_id}", response_model=QualityReportDetailOut)
def get_quality_report_detail(
    quality_report_id: int,
    db: Session = Depends(get_db),
    _principal=Depends(require_role("readonly")),
):
    report = repo.get_quality_report(db, quality_report_id)
    if not report:
        raise HTTPException(status_code=404, detail="quality report not found")
    details = report.details or []
    error_details = [detail for detail in details if detail.get("severity") == "error"]
    warning_details = [detail for detail in details if detail.get("severity") == "warning"]
    return {
        **report.__dict__,
        "error_details": error_details,
        "warning_details": warning_details,
        "suggested_actions": ["复核异常值", "驳回问题数据", "暂缓发布"] if error_details else ["人工复核 warning"],
    }


@router.get("/stat-value-changes", response_model=list[StatValueChangeOut])
def list_stat_value_changes(
    stat_value_id: int | None = None,
    db: Session = Depends(get_db),
    _principal=Depends(require_role("readonly")),
):
    return repo.list_stat_value_changes(db, stat_value_id=stat_value_id)


@router.get("/ops/summary", response_model=OpsSummaryOut)
def get_ops_summary(db: Session = Depends(get_db), _principal=Depends(require_role("readonly"))):
    return repo.get_ops_summary(db)


@router.get("/ops/recent-failures", response_model=list[CrawlJobOut])
def get_recent_failures(db: Session = Depends(get_db), _principal=Depends(require_role("readonly"))):
    return repo.get_recent_failed_jobs(db)


@router.post("/ops/test-alert", response_model=AlertTestOut)
def test_alert(_principal=Depends(require_role("operator"))):
    configured = get_settings().alert_webhook_url is not None
    return {
        "configured": configured,
        "message": "alert webhook configured" if configured else "alert webhook is not configured",
    }


@router.get("/indicators", response_model=list[IndicatorOut])
def list_admin_indicators(db: Session = Depends(get_db), _principal=Depends(require_role("readonly"))):
    return repo.list_indicators(db)


@router.patch("/indicators/{code}", response_model=IndicatorOut)
def patch_indicator(
    code: str,
    payload: IndicatorPatch,
    db: Session = Depends(get_db),
    principal: AdminPrincipal = Depends(require_role("operator")),
):
    indicator = repo.get_indicator_by_code(db, code)
    if not indicator:
        raise HTTPException(status_code=404, detail="indicator not found")
    before = repo.serialize_indicator(indicator)
    updated = repo.update_indicator(db, indicator, **payload.model_dump(exclude_unset=True))
    repo.log_operation(
        db,
        actor=principal.username,
        action="indicator.update",
        target_type="indicator",
        target_id=updated.code,
        before=before,
        after=repo.serialize_indicator(updated),
    )
    db.commit()
    db.refresh(updated)
    return updated


@router.get("/configs", response_model=list[AppConfigOut])
def list_app_configs(db: Session = Depends(get_db), _principal=Depends(require_role("readonly"))):
    return repo.list_app_configs(db)


@router.patch("/configs/{key}", response_model=AppConfigOut)
def patch_app_config(
    key: str,
    payload: AppConfigPatch,
    db: Session = Depends(get_db),
    principal: AdminPrincipal = Depends(require_role("operator")),
):
    if not isinstance(payload.value, dict):
        raise HTTPException(status_code=422, detail="config value must be an object")
    before_config = repo.get_app_config(db, key)
    before = repo.serialize_app_config(before_config)
    updated = repo.update_app_config(db, key=key, value=payload.value, description=payload.description)
    repo.log_operation(
        db,
        actor=principal.username,
        action="app_config.update",
        target_type="app_config",
        target_id=key,
        before=before,
        after=repo.serialize_app_config(updated),
    )
    db.commit()
    db.refresh(updated)
    return updated


@router.get("/operation-logs", response_model=list[OperationLogOut])
def list_operation_logs(
    target_type: str | None = None,
    action: str | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
    _principal=Depends(require_role("readonly")),
):
    return repo.list_operation_logs(db, target_type=target_type, action=action, limit=limit)


def run_crawl_job(job_id: int, url: str, data_source_id: int | None) -> None:
    with SessionLocal() as db:
        job = db.get(repo.CrawlJob, job_id)
        data_source = db.get(repo.DataSource, data_source_id) if data_source_id else None
        if not job:
            return
        source_type = data_source.type if data_source else "housing_price"
        locked = repo.lock_crawl_job(db, job, worker_id="api-background")
        if locked is None:
            return
        try:
            runner = get_import_runner(source_type, db)
            runner.run(url=url, job=locked, data_source=data_source)
        except UnsupportedDataSourceType as exc:
            repo.mark_job_finished(
                db,
                locked,
                status="failed",
                error_type="unsupported_data_source_type",
                error_message=str(exc),
            )
