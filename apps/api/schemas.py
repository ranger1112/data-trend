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
    total_records: int
    imported_records: int
    skipped_records: int
    error_type: str | None
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None

    model_config = {"from_attributes": True}


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


class ScheduleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    target_url: HttpUrl
    data_source_id: int | None = None
    interval_minutes: int = Field(default=1440, ge=1)
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
    created_at: datetime

    model_config = {"from_attributes": True}


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


class TrendPoint(BaseModel):
    period: date
    value: float
    dimensions: dict[str, Any]


class TrendResponse(BaseModel):
    region_id: int
    indicator_code: str
    items: list[TrendPoint]
