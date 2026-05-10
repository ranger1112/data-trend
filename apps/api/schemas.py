from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class DataSourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    entry_url: HttpUrl
    source: str = "国家统计局"
    type: str = "housing_price"
    enabled: bool = True


class DataSourcePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    entry_url: HttpUrl | None = None
    source: str | None = None
    type: str | None = None
    enabled: bool | None = None


class DataSourceOut(BaseModel):
    id: int
    name: str
    entry_url: str
    source: str
    type: str
    enabled: bool

    model_config = {"from_attributes": True}


class DataSourceHealthOut(BaseModel):
    id: int
    name: str
    type: str
    enabled: bool
    entry_url: str
    latest_job_status: str | None
    latest_job_finished_at: datetime | None
    latest_error_type: str | None
    latest_error_message: str | None
    total_jobs: int
    success_jobs: int
    failed_jobs: int
    success_rate: float


class DataSourceDetailOut(BaseModel):
    data_source: DataSourceOut
    health: DataSourceHealthOut | None
    recent_jobs: list["CrawlJobOut"]
    schedules: list["ScheduleOut"]
    quality_reports: list["QualityReportOut"]
    available_actions: list[str]


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    username: str
    role: str


class MeResponse(BaseModel):
    username: str
    role: str


class CrawlJobCreate(BaseModel):
    data_source_id: int | None = None
    url: HttpUrl | None = None
    run_now: bool = True


class CrawlJobOut(BaseModel):
    id: int
    data_source_id: int | None
    schedule_id: int | None
    target_url: str | None
    status: str
    trigger: str
    retry_count: int
    max_retries: int
    next_retry_at: datetime | None
    timeout_seconds: int
    locked_at: datetime | None
    locked_by: str | None
    total_records: int
    imported_records: int
    skipped_records: int
    error_type: str | None
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None

    model_config = {"from_attributes": True}


class CrawlJobDetailOut(BaseModel):
    job: CrawlJobOut
    data_source: DataSourceOut | None
    schedule: "ScheduleOut | None"
    quality_reports: list["QualityReportOut"]
    duration_seconds: int | None
    retry_available: bool


class StatValuePatch(BaseModel):
    value: float | None = None
    status: str | None = Field(
        default=None,
        pattern="^(draft|quality_failed|ready_for_review|published|rejected)$",
    )
    dimensions: dict[str, Any] | None = None
    reason: str | None = None


class StatValuePublishRequest(BaseModel):
    ids: list[int] = Field(min_length=1)
    reason: str | None = None


class AppConfigPatch(BaseModel):
    value: dict[str, Any]
    description: str | None = None


class IndicatorPatch(BaseModel):
    display_name: str | None = None
    category: str | None = None
    unit: str | None = None
    description: str | None = None
    precision: int | None = Field(default=None, ge=0, le=6)
    sort_order: int | None = None
    default_dimensions: dict[str, Any] | None = None
    miniapp_visible: bool | None = None
    default_chart_type: str | None = None


class ScheduleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    target_url: HttpUrl
    data_source_id: int | None = None
    interval_minutes: int | None = Field(default=None, ge=1)
    enabled: bool = True
    next_run_at: datetime | None = None


class SchedulePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    target_url: HttpUrl | None = None
    interval_minutes: int | None = Field(default=None, ge=1)
    enabled: bool | None = None
    next_run_at: datetime | None = None


class ScheduleOut(BaseModel):
    id: int
    name: str
    target_url: str
    data_source_id: int | None
    interval_minutes: int
    enabled: bool
    last_run_at: datetime | None
    next_run_at: datetime | None

    model_config = {"from_attributes": True}


class QualityReportOut(BaseModel):
    id: int
    crawl_job_id: int | None
    period: date | None
    status: str
    expected_regions: int
    actual_regions: int
    expected_indicators: int
    actual_indicators: int
    checked_values: int
    errors: list[str]
    warnings: list[str]
    details: list[dict[str, Any]]
    created_at: datetime

    model_config = {"from_attributes": True}


class QualityReportDetailOut(QualityReportOut):
    error_details: list[dict[str, Any]]
    warning_details: list[dict[str, Any]]
    suggested_actions: list[str]


class PublishBatchOut(BaseModel):
    id: int
    action: str
    status: str
    actor: str
    item_count: int
    reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class StatValueChangeOut(BaseModel):
    id: int
    stat_value_id: int
    actor: str
    before_value: float | None
    after_value: float | None
    before_status: str | None
    after_status: str | None
    reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class OpsSummaryOut(BaseModel):
    jobs_last_24h: int
    failed_jobs_last_24h: int
    pending_jobs: int
    running_jobs: int
    quality_failed_reports: int
    review_pending_values: int
    last_success_at: datetime | None
    next_schedule_at: datetime | None


class AlertTestOut(BaseModel):
    configured: bool
    message: str


class TrendPoint(BaseModel):
    period: date
    value: float
    dimensions: dict[str, Any]


class RegionOut(BaseModel):
    id: int
    name: str
    normalized_name: str
    level: str
    parent_id: int | None = None
    sort_order: int = 0
    display_enabled: bool = True

    model_config = {"from_attributes": True}


class IndicatorOut(BaseModel):
    id: int
    code: str
    name: str
    display_name: str | None = None
    category: str = "general"
    unit: str | None
    description: str | None
    precision: int = 2
    sort_order: int = 0
    default_dimensions: dict[str, Any] = {}
    miniapp_visible: bool = True
    default_chart_type: str = "line"

    model_config = {"from_attributes": True}


class IndicatorGroupOut(BaseModel):
    category: str
    name: str
    items: list[IndicatorOut]


class LatestValueOut(BaseModel):
    region_id: int
    region: str
    period: date
    value: float
    dimensions: dict[str, Any]


class LatestValuesResponse(BaseModel):
    items: list[LatestValueOut]
    latest_period: date | None
    updated_at: datetime | None
    cache_ttl_seconds: int


class RankingsResponse(BaseModel):
    top: list[LatestValueOut]
    bottom: list[LatestValueOut]
    latest_period: date | None
    updated_at: datetime | None
    cache_ttl_seconds: int


class DashboardOverviewOut(BaseModel):
    regions: int
    indicators: int
    published_values: int
    latest_period: date | None
    updated_at: datetime | None
    cache_ttl_seconds: int


class TrendResponse(BaseModel):
    region_id: int
    indicator_code: str
    items: list[TrendPoint]
    updated_at: datetime | None = None
    cache_ttl_seconds: int = 300


class ComparisonTrendItem(BaseModel):
    region_id: int
    region: str
    items: list[TrendPoint]


class ComparisonTrendResponse(BaseModel):
    indicator_code: str
    series: list[ComparisonTrendItem]
    updated_at: datetime | None = None
    cache_ttl_seconds: int = 300


class CityDetailOut(BaseModel):
    region: dict[str, Any]
    indicator_cards: list[dict[str, Any]]
    updated_at: datetime | None
    cache_ttl_seconds: int = 300


class HomeRecommendationsOut(BaseModel):
    recommended_indicators: list[IndicatorOut]
    recommended_regions: list[dict[str, Any]]
    ranking_indicator: str | None
    default_trend_indicator: str | None
    updated_at: datetime | None
    cache_ttl_seconds: int = 300


class AppConfigOut(BaseModel):
    key: str
    value: dict[str, Any]
    description: str | None
    updated_at: datetime

    model_config = {"from_attributes": True}
