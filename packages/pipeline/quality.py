from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from packages.domain.constants import INDICATORS
from packages.storage.models import CrawlJob, Indicator, QualityReport, Region, StatValue


EXPECTED_REGIONS = 70
EXPECTED_INDICATORS = len(INDICATORS)


@dataclass(frozen=True)
class QualityResult:
    report: QualityReport
    passed: bool


class QualityChecker:
    def __init__(
        self,
        expected_regions: int = EXPECTED_REGIONS,
        expected_indicators: int = EXPECTED_INDICATORS,
    ) -> None:
        self.expected_regions = expected_regions
        self.expected_indicators = expected_indicators

    def check_job(self, db: Session, job: CrawlJob) -> QualityResult:
        period = self._latest_period_for_job(db, job)
        errors: list[str] = []
        warnings: list[str] = []

        actual_regions = db.scalar(select(func.count(Region.id))) or 0
        actual_indicators = db.scalar(select(func.count(Indicator.id))) or 0
        checked_values = 0

        if actual_regions < self.expected_regions:
            errors.append(f"expected at least {self.expected_regions} regions, got {actual_regions}")
        if actual_indicators < self.expected_indicators:
            errors.append(f"expected at least {self.expected_indicators} indicators, got {actual_indicators}")
        if not period:
            errors.append("no stat value period found for imported data")
        else:
            values = list(db.scalars(select(StatValue).where(StatValue.period == period)))
            checked_values = len(values)
            if checked_values == 0:
                errors.append(f"no stat values found for period {period.isoformat()}")
            if any(value.value <= 0 for value in values):
                errors.append("stat values must be positive")
            missing_dimensions = [
                value.id
                for value in values
                if not value.dimensions.get("house_type") or not value.dimensions.get("area_type")
            ]
            if missing_dimensions:
                errors.append(f"{len(missing_dimensions)} stat values are missing dimensions")
            expected_min_values = self.expected_regions * self.expected_indicators
            if checked_values < expected_min_values:
                warnings.append(
                    f"period {period.isoformat()} has {checked_values} values, expected at least {expected_min_values}"
                )

        status = "passed" if not errors else "failed"
        report = QualityReport(
            crawl_job_id=job.id,
            period=period,
            status=status,
            expected_regions=self.expected_regions,
            actual_regions=actual_regions,
            expected_indicators=self.expected_indicators,
            actual_indicators=actual_indicators,
            checked_values=checked_values,
            errors=errors,
            warnings=warnings,
        )
        db.add(report)

        if status == "passed" and period:
            values = list(db.scalars(select(StatValue).where(StatValue.period == period, StatValue.status == "draft")))
            for value in values:
                value.status = "ready_for_review"
        elif period:
            values = list(db.scalars(select(StatValue).where(StatValue.period == period, StatValue.status == "draft")))
            for value in values:
                value.status = "quality_failed"

        db.commit()
        db.refresh(report)
        return QualityResult(report=report, passed=status == "passed")

    def _latest_period_for_job(self, db: Session, job: CrawlJob) -> date | None:
        if not job.started_at:
            return db.scalar(select(func.max(StatValue.period)))
        return db.scalar(
            select(func.max(StatValue.period)).where(StatValue.updated_at >= job.started_at)
        )
