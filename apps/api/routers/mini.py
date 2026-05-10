from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db
from apps.api.schemas import (
    CityDetailOut,
    ComparisonTrendResponse,
    DashboardOverviewOut,
    HomeRecommendationsOut,
    IndicatorGroupOut,
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


@router.get("/indicator-groups", response_model=list[IndicatorGroupOut])
def list_indicator_groups(db: Session = Depends(get_db)):
    return repo.group_indicators_for_display(db)


@router.get("/home/recommendations", response_model=HomeRecommendationsOut)
def home_recommendations(db: Session = Depends(get_db)):
    return {
        **repo.get_home_recommendations(db),
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
    }


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


@router.get("/stat-values/compare", response_model=ComparisonTrendResponse)
def compare_trends(
    region_ids: str = Query(min_length=1),
    indicator_code: str = Query(default="housing_price_mom"),
    house_type: str | None = None,
    area_type: str | None = None,
    db: Session = Depends(get_db),
):
    ids = [int(item) for item in region_ids.split(",") if item.strip()]
    ids = ids[:3]
    return {
        "indicator_code": indicator_code,
        "series": repo.get_published_comparison_trends(
            db,
            region_ids=ids,
            indicator_code=indicator_code,
            house_type=house_type,
            area_type=area_type,
        ),
        "updated_at": repo.get_latest_published_update_time(db),
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
    }


@router.get("/regions/{region_id}/detail", response_model=CityDetailOut)
def city_detail(region_id: int, db: Session = Depends(get_db)):
    detail = repo.get_city_detail(db, region_id)
    if not detail:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="region not found")
    return {
        **detail,
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
