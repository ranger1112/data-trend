from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db
from apps.api.schemas import TrendResponse
from packages.storage import repositories as repo

router = APIRouter()


@router.get("/regions")
def list_regions(db: Session = Depends(get_db)):
    return repo.list_regions(db)


@router.get("/indicators")
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
    return {"region_id": region_id, "indicator_code": indicator_code, "items": items}


@router.get("/stat-values/latest")
def latest_values(
    indicator_code: str = Query(default="housing_price_mom"),
    house_type: str | None = None,
    area_type: str | None = None,
    db: Session = Depends(get_db),
):
    return repo.get_latest_published_values(
        db,
        indicator_code=indicator_code,
        house_type=house_type,
        area_type=area_type,
    )


@router.get("/dashboard/overview")
def dashboard_overview(db: Session = Depends(get_db)):
    return repo.get_dashboard_overview(db)
