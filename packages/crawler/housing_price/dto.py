from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass(frozen=True)
class GovStatsArticle:
    title: str
    url: str
    publish_date: str | None = None


@dataclass(frozen=True)
class HousingPriceRecord:
    city_name: str
    period: date
    house_type: str
    area_type: str
    month_on_month: float
    year_on_year: float
    ytd_average: float
    source_title: str
    source_url: str
    published_at: datetime | None = None
    raw: dict = field(default_factory=dict)

