"""Pure scoring contracts.

This module intentionally contains no I/O, clock access, or orchestration.
Later scoring behavior must preserve unavailable values as ``None`` and accept
an explicit timezone-aware UTC cutoff through its typed inputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .models import EvidenceGrade, RankabilityStatus, ScoreState


@dataclass(frozen=True, slots=True)
class ScoringInput:
    scoring_cutoff_utc: datetime
    demand: float | None = None
    competition: float | None = None
    recent_supply: float | None = None
    quality: float | None = None

    def __post_init__(self) -> None:
        if (
            self.scoring_cutoff_utc.tzinfo is None
            or self.scoring_cutoff_utc.utcoffset()
            != timezone.utc.utcoffset(self.scoring_cutoff_utc)
        ):
            raise ValueError("scoring_cutoff_utc must be timezone-aware UTC")


@dataclass(frozen=True, slots=True)
class ScoreResult:
    market_opportunity_score: float | None
    score_state: ScoreState
    component_d: float | None = None
    component_c: float | None = None
    component_r: float | None = None
    component_q: float | None = None
    available_component_count: int = 0
    rankability_status: RankabilityStatus = RankabilityStatus.NOT_RANKABLE
    evidence_grade: EvidenceGrade = EvidenceGrade.INSUFFICIENT


@dataclass(frozen=True, slots=True)
class SensitivityResult:
    top_3_stability: float | None = None
    top_5_stability: float | None = None
    maximum_score_delta: float | None = None
    maximum_rank_displacement: int | None = None
    warning: bool = False
