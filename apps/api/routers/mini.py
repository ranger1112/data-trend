from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db
from apps.api.schemas import (
    DashboardOverviewOut,
    IndicatorOut,
    LatestValuesResponse,
    RankingsResponse,
    RegionOut,
    TrendResponse,
)
from packages.storage import repositories as repo

router = APIRouter()
CACHE_TTL_SECONDS = 300


@router.get("/regions", response_model=list[RegionOut])
def list_regions(db: Session = Depends(get_db)):
    return repo.list_regions(db)


@router.get("/indicators", response_model=list[IndicatorOut])
def list_indicators(db: Session = Depends(get_db)):
    return repo.list_indicators(db)


@router.get("/stat-values/trend", response_model=TrendResponse)
def get_trend(
    region_id: int,
    indicator_code: str,
    house_type: str | None = None,
    area_type: str | None = None,
    db: Session = Depends(get_db),
):
    items = repo.get_published_trend(
        db,
        region_id=region_id,
        indicator_code=indicator_code,
        house_type=house_type,
        area_type=area_type,
    )
    return {
        "region_id": region_id,
        "indicator_code": indicator_code,
        "items": items,
        "updated_at": repo.get_latest_published_update_time(db),
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
    }


@router.get("/stat-values/latest", response_model=LatestValuesResponse)
def latest_values(
    indicator_code: str = Query(default="housing_price_mom"),
    house_type: str | None = None,
    area_type: str | None = None,
    db: Session = Depends(get_db),
):
    items = repo.get_latest_published_values(
        db,
        indicator_code=indicator_code,
        house_type=house_type,
        area_type=area_type,
    )
    return {
        "items": items,
        "latest_period": items[0]["period"] if items else repo.get_latest_period_for_indicator(db, indicator_code),
        "updated_at": repo.get_latest_published_update_time(db),
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
    }


@router.get("/rankings", response_model=RankingsResponse)
def rankings(
    indicator_code: str = Query(default="housing_price_mom"),
    house_type: str | None = None,
    area_type: str | None = None,
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    ranking = repo.get_published_rankings(
        db,
        indicator_code=indicator_code,
        house_type=house_type,
        area_type=area_type,
        limit=limit,
    )
    items = [*ranking["top"], *ranking["bottom"]]
    return {
        **ranking,
        "latest_period": items[0]["period"] if items else repo.get_latest_period_for_indicator(db, indicator_code),
        "updated_at": repo.get_latest_published_update_time(db),
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
    }


@router.get("/dashboard/overview", response_model=DashboardOverviewOut)
def dashboard_overview(db: Session = Depends(get_db)):
    overview = repo.get_dashboard_overview(db)
    return {
        **overview,
        "updated_at": repo.get_latest_published_update_time(db),
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
    }
