from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from packages.domain.constants import CPI_SOURCE_TYPE, HOUSING_PRICE_SOURCE_TYPE, INDICATORS
from packages.storage.models import CrawlJob, Indicator, QualityReport, Region, StatValue


EXPECTED_REGIONS = 70
EXPECTED_INDICATORS = len(INDICATORS)


QUALITY_RULES = {
    HOUSING_PRICE_SOURCE_TYPE: {
        "expected_regions": 70,
        "expected_indicators": 3,
        "min_values": 210,
        "required_dimensions": ["house_type", "area_type"],
        "value_min": 0,
        "value_max": 200,
        "warning_value_min": 80,
        "warning_value_max": 130,
    },
    CPI_SOURCE_TYPE: {
        "expected_regions": 1,
        "expected_indicators": 3,
        "min_values": 2,
        "required_dimensions": ["source_type", "frequency"],
        "value_min": -20,
        "value_max": 20,
        "warning_value_min": -10,
        "warning_value_max": 10,
    },
}


@dataclass(frozen=True)
class QualityResult:
    report: QualityReport
    passed: bool


class QualityChecker:
    def __init__(
        self,
        source_type: str = HOUSING_PRICE_SOURCE_TYPE,
        expected_regions: int | None = None,
        expected_indicators: int | None = None,
    ) -> None:
        self.source_type = source_type
        self.rules = QUALITY_RULES.get(source_type, QUALITY_RULES[HOUSING_PRICE_SOURCE_TYPE])
        self.expected_regions = expected_regions or int(self.rules["expected_regions"])
        self.expected_indicators = expected_indicators or int(self.rules["expected_indicators"])

    def check_job(self, db: Session, job: CrawlJob) -> QualityResult:
        period = self._latest_period_for_job(db, job)
        errors: list[str] = []
        warnings: list[str] = []
        details: list[dict[str, Any]] = []

        actual_regions = db.scalar(select(func.count(Region.id))) or 0
        actual_indicators = db.scalar(select(func.count(Indicator.id))) or 0
        checked_values = 0

        if actual_regions < self.expected_regions:
            errors.append(f"expected at least {self.expected_regions} regions, got {actual_regions}")
            details.append(
                {
                    "severity": "error",
                    "rule": "expected_regions",
                    "message": f"expected at least {self.expected_regions} regions, got {actual_regions}",
                    "expected": self.expected_regions,
                    "actual": actual_regions,
                }
            )
        if actual_indicators < self.expected_indicators:
            errors.append(f"expected at least {self.expected_indicators} indicators, got {actual_indicators}")
            details.append(
                {
                    "severity": "error",
                    "rule": "expected_indicators",
                    "message": f"expected at least {self.expected_indicators} indicators, got {actual_indicators}",
                    "expected": self.expected_indicators,
                    "actual": actual_indicators,
                }
            )
        if not period:
            errors.append("no stat value period found for imported data")
            details.append(
                {
                    "severity": "error",
                    "rule": "period_presence",
                    "message": "no stat value period found for imported data",
                }
            )
        else:
            values = self._values_for_period(db, period)
            checked_values = len(values)
            if checked_values == 0:
                errors.append(f"no stat values found for period {period.isoformat()}")
                details.append(
                    {
                        "severity": "error",
                        "rule": "period_values",
                        "period": period.isoformat(),
                        "message": f"no stat values found for period {period.isoformat()}",
                    }
                )
            value_min = float(self.rules["value_min"])
            value_max = float(self.rules["value_max"])
            out_of_range = [value for value in values if value.value < value_min or value.value > value_max]
            if out_of_range:
                errors.append(
                    f"{len(out_of_range)} stat values are outside range {value_min:g} to {value_max:g}"
                )
                details.extend(
                    self._build_value_details(
                        out_of_range,
                        severity="error",
                        rule="value_range",
                        message=f"value is outside range {value_min:g} to {value_max:g}",
                    )
                )
            warning_min = float(self.rules["warning_value_min"])
            warning_max = float(self.rules["warning_value_max"])
            unusual_values = [
                value for value in values if value.value < warning_min or value.value > warning_max
            ]
            if unusual_values:
                warnings.append(
                    f"{len(unusual_values)} stat values are outside normal range {warning_min:g} to {warning_max:g}"
                )
                details.extend(
                    self._build_value_details(
                        unusual_values,
                        severity="warning",
                        rule="warning_value_range",
                        message=f"value is outside normal range {warning_min:g} to {warning_max:g}",
                    )
                )
            required_dimensions = list(self.rules["required_dimensions"])
            missing_dimensions = [
                value
                for value in values
                if any(not value.dimensions.get(dimension) for dimension in required_dimensions)
            ]
            if missing_dimensions:
                errors.append(f"{len(missing_dimensions)} stat values are missing dimensions")
                details.extend(
                    self._build_value_details(
                        missing_dimensions,
                        severity="error",
                        rule="required_dimensions",
                        message=f"missing required dimensions: {', '.join(required_dimensions)}",
                    )
                )
            expected_min_values = int(self.rules["min_values"])
            if checked_values < expected_min_values:
                warnings.append(
                    f"period {period.isoformat()} has {checked_values} values, expected at least {expected_min_values}"
                )
                details.append(
                    {
                        "severity": "warning",
                        "rule": "min_values",
                        "period": period.isoformat(),
                        "message": (
                            f"period {period.isoformat()} has {checked_values} values, "
                            f"expected at least {expected_min_values}"
                        ),
                        "expected": expected_min_values,
                        "actual": checked_values,
                    }
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
            details=details,
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

    def _values_for_period(self, db: Session, period: date) -> list[StatValue]:
        values = list(db.scalars(select(StatValue).where(StatValue.period == period)))
        if self.source_type == HOUSING_PRICE_SOURCE_TYPE:
            return [value for value in values if value.indicator.code.startswith("housing_price_")]
        if self.source_type == CPI_SOURCE_TYPE:
            return [value for value in values if value.indicator.code.startswith("cpi_")]
        return values

    def _build_value_details(
        self,
        values: list[StatValue],
        *,
        severity: str,
        rule: str,
        message: str,
    ) -> list[dict[str, Any]]:
        return [
            {
                "severity": severity,
                "rule": rule,
                "message": message,
                "stat_value_id": value.id,
                "indicator": value.indicator.code,
                "region": value.region.name,
                "period": value.period.isoformat(),
                "value": value.value,
                "dimensions": value.dimensions,
            }
            for value in values
        ]
