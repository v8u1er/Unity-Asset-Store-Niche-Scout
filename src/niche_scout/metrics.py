"""Pure metric contracts.

Metric functions in later chunks consume these typed structures. ``None`` is
unavailable and must not be substituted with zero; zero remains a valid value.
All cutoff timestamps are explicit, timezone-aware UTC inputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .models import PageViewSemanticsStatus


@dataclass(frozen=True, slots=True)
class MetricInput:
    scoring_cutoff_utc: datetime
    page_view_semantics_status: PageViewSemanticsStatus = PageViewSemanticsStatus.UNVALIDATED

    def __post_init__(self) -> None:
        if self.scoring_cutoff_utc.tzinfo is None or self.scoring_cutoff_utc.utcoffset() != timezone.utc.utcoffset(self.scoring_cutoff_utc):
            raise ValueError("scoring_cutoff_utc must be timezone-aware UTC")


@dataclass(frozen=True, slots=True)
class MetricResult:
    value: float | None
    usable_sample_count: int
    eligible_population_count: int
    eligibility_coverage: float | None
    unavailable_reason: str | None = None


@dataclass(frozen=True, slots=True)
class RawMetricBundle:
    demand_per_asset_raw: float | None = None
    demand_median_raw: float | None = None
    breadth_raw: float | None = None
    recent_share_raw: float | None = None
    median_age_raw: float | None = None
    quality_raw: float | None = None
