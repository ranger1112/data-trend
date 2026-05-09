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
    status: str
    trigger: str
    total_records: int
    imported_records: int
    skipped_records: int
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None

    model_config = {"from_attributes": True}


class StatValuePatch(BaseModel):
    value: float | None = None
    status: str | None = Field(default=None, pattern="^(draft|published|rejected)$")
    dimensions: dict[str, Any] | None = None


class StatValuePublishRequest(BaseModel):
    ids: list[int] = Field(min_length=1)


class TrendPoint(BaseModel):
    period: date
    value: float
    dimensions: dict[str, Any]


class TrendResponse(BaseModel):
    region_id: int
    indicator_code: str
    items: list[TrendPoint]
