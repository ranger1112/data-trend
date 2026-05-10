from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass(frozen=True)
class CpiRecord:
    region_name: str
    period: date
    year_on_year: float
    month_on_month: float
    cumulative_average: float | None
    source_title: str
    source_url: str
    published_at: datetime | None = None
    raw: dict = field(default_factory=dict)
