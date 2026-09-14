"""Typed domain contracts for the lean niche-scout data model.

These structures are deliberately persistence-neutral.  ``None`` means that a
value is unavailable; it is never converted to a fabricated zero.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from datetime import date, datetime, timezone
from enum import StrEnum
from typing import Any, ClassVar, TypeVar, get_args, get_origin, get_type_hints
import json
import types

SRS_VERSION = "lean-1.0.1"
ENDPOINT_CONTRACT_VERSION = "parent-srs-2.3.0"
IDENTITY_MAPPING_RULE_VERSION = "identity-map-1"
SAMPLING_RULE_VERSION = "lean-stratified-v1"


class RunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class DiscoveryStatus(StrEnum):
    COMPLETE = "complete"
    TRUNCATED = "truncated"
    PAGE_FAILED = "page_failed"
    FILTER_UNVERIFIED = "filter_unverified"
    CATEGORY_MISMATCH = "category_mismatch"
    IDENTITY_INCOMPLETE = "identity_incomplete"
    REQUEST_FAILED = "request_failed"


class IdentityResolutionStatus(StrEnum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    CONFLICT = "conflict"


class CategoryFilterValidationStatus(StrEnum):
    VERIFIED = "verified"
    MISMATCH = "mismatch"
    UNVERIFIED = "unverified"


class OperationStatus(StrEnum):
    SUCCESS = "success"
    ERROR = "error"
    MALFORMED = "malformed"
    UNAVAILABLE = "unavailable"


class ScoreState(StrEnum):
    AVAILABLE = "available"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class EvidenceGrade(StrEnum):
    STRONG = "strong"
    MODERATE = "moderate"
    LIMITED = "limited"
    INSUFFICIENT = "insufficient"


class RankabilityStatus(StrEnum):
    NOT_RANKABLE = "not_rankable"
    PROVISIONAL = "provisional"
    RANKABLE = "rankable"


class PageViewSemanticsStatus(StrEnum):
    UNVALIDATED = "unvalidated"
    VALIDATED_CUMULATIVE = "validated_cumulative"
    CONTRADICTED = "contradicted"


class GraphQLCorrelationMode(StrEnum):
    EXPLICIT_KEY = "explicit_key"
    VALIDATED_POSITION = "validated_position"


class IdentityPreflightStatus(StrEnum):
    SUFFICIENT = "sufficient"
    INSUFFICIENT = "insufficient"
    PASSED = "passed"
    FAILED = "failed"


class WarningCode(StrEnum):
    DISCOVERY_TRUNCATED = "DISCOVERY_TRUNCATED"
    DISCOVERY_PAGE_FAILED = "DISCOVERY_PAGE_FAILED"
    DISCOVERY_FILTER_UNVERIFIED = "DISCOVERY_FILTER_UNVERIFIED"
    CATEGORY_MISMATCH = "CATEGORY_MISMATCH"
    IDENTITY_UNRESOLVED = "IDENTITY_UNRESOLVED"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"
    IDENTITY_PREFLIGHT_FAILED = "IDENTITY_PREFLIGHT_FAILED"
    GRAPHQL_PRODUCT_ERROR = "GRAPHQL_PRODUCT_ERROR"
    GRAPHQL_PAGE_VIEWS_ERROR = "GRAPHQL_PAGE_VIEWS_ERROR"
    GRAPHQL_ID_MAPPING_MISMATCH = "GRAPHQL_ID_MAPPING_MISMATCH"
    STATE_EXCLUDED = "STATE_EXCLUDED"
    INSUFFICIENT_DEMAND_SAMPLE = "INSUFFICIENT_DEMAND_SAMPLE"
    INSUFFICIENT_RECENT_SAMPLE = "INSUFFICIENT_RECENT_SAMPLE"
    INSUFFICIENT_QUALITY_SAMPLE = "INSUFFICIENT_QUALITY_SAMPLE"
    PAGE_VIEW_SEMANTICS_CONTRADICTED = "PAGE_VIEW_SEMANTICS_CONTRADICTED"
    REFERENCE_SET_SMALL = "REFERENCE_SET_SMALL"
    RANKING_SENSITIVITY_HIGH = "RANKING_SENSITIVITY_HIGH"
    SAMPLE_BASED_SIGNAL = "SAMPLE_BASED_SIGNAL"


def ensure_utc(value: datetime) -> datetime:
    """Return a UTC datetime, rejecting naive and non-UTC values."""
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware UTC")
    if value.utcoffset() != timezone.utc.utcoffset(value):
        raise ValueError("timestamp must use UTC")
    return value.astimezone(timezone.utc)


def serialize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return ensure_utc(value).isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, dict):
        return {str(k): serialize_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serialize_value(item) for item in value]
    return value


T = TypeVar("T")


def to_json_dict(instance: Any) -> dict[str, Any]:
    """Serialize a dataclass deterministically, including enum values."""
    return serialize_value(asdict(instance))


def to_json(instance: Any) -> str:
    return json.dumps(to_json_dict(instance), sort_keys=True, separators=(",", ":"))


def _deserialize_value(value: Any, annotation: Any) -> Any:
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin in (types.UnionType, __import__("typing").Union):
        if value is None and type(None) in args:
            return None
        return _deserialize_value(value, next(arg for arg in args if arg is not type(None)))
    if value is None:
        return None
    if origin in (list, tuple):
        converted = [_deserialize_value(item, args[0]) for item in value]
        return tuple(converted) if origin is tuple else converted
    if origin is dict:
        return {_deserialize_value(k, args[0]): _deserialize_value(v, args[1]) for k, v in value.items()}
    if isinstance(annotation, type) and issubclass(annotation, StrEnum):
        return annotation(value)
    if annotation is datetime:
        return ensure_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
    if annotation is date:
        return date.fromisoformat(value)
    return value


def from_json(payload: str, row_type: type[T]) -> T:
    """Deserialize JSON produced by :func:`to_json` into a typed dataclass."""
    raw = json.loads(payload)
    hints = get_type_hints(row_type)
    return row_type(**{name: _deserialize_value(value, hints[name]) for name, value in raw.items()})


@dataclass(frozen=True, slots=True)
class RunRow:
    run_id: str
    run_started_at_utc: datetime
    scoring_cutoff_utc: datetime
    status: RunStatus
    completed_at_utc: datetime | None = None
    categories_json: str = "[]"
    config_snapshot_json: str = "{}"
    config_sha256: str = ""
    taxonomy_version: str = ""
    taxonomy_captured_at_utc: datetime | None = None
    taxonomy_sha256: str = ""
    endpoint_contract_version: str = ENDPOINT_CONTRACT_VERSION
    identity_mapping_rule_version: str = IDENTITY_MAPPING_RULE_VERSION
    sampling_rule_version: str = SAMPLING_RULE_VERSION
    page_view_semantics_status: PageViewSemanticsStatus = PageViewSemanticsStatus.UNVALIDATED
    graphql_operation_correlation_mode: GraphQLCorrelationMode | None = None
    identity_preflight_status: IdentityPreflightStatus = IdentityPreflightStatus.INSUFFICIENT
    identity_preflight_summary_json: str = "{}"

    def __post_init__(self) -> None:
        ensure_utc(self.run_started_at_utc)
        ensure_utc(self.scoring_cutoff_utc)
        if self.completed_at_utc is not None:
            ensure_utc(self.completed_at_utc)


@dataclass(frozen=True, slots=True)
class RawDiscoveryObservation:
    observation_id: str
    run_id: str
    category: str
    discovery_ordinal: int
    asset_identity_key: str | None = None
    identity_candidates_json: str = "[]"
    identity_resolution_status: IdentityResolutionStatus = IdentityResolutionStatus.UNRESOLVED
    identity_resolution_reason: str | None = None
    category_value_json: str = "[]"
    category_filter_validation_status: CategoryFilterValidationStatus = CategoryFilterValidationStatus.UNVERIFIED
    stratum_index: int | None = None
    is_duplicate: bool = False
    duplicate_of_observation_id: str | None = None
    request_metadata_json: str = "{}"
    error_summary_json: str | None = None
    retrieved_at_utc: datetime | None = None


@dataclass(frozen=True, slots=True)
class SampleMember:
    run_id: str
    category: str
    asset_identity_key: str
    stratum_index: int
    stratum_start_ordinal: int
    stratum_end_ordinal: int
    sample_rank_within_stratum: int
    sample_is_census: bool
    selection_digest: str
    overlap_category_count: int | None = None
    overlap_sample_percentage: float | None = None
    preflight_selected: bool = False


@dataclass(frozen=True, slots=True)
class EnrichmentObservation:
    run_id: str
    asset_identity_key: str
    product_detail_status: OperationStatus = OperationStatus.UNAVAILABLE
    page_views_status: OperationStatus = OperationStatus.UNAVAILABLE
    graphql_id: str | None = None
    product_id: str | None = None
    rating_average: float | None = None
    rating_count: int | None = None
    review_count: int | None = None
    first_published_date_utc: datetime | None = None
    publisher_json: str | None = None
    category_json: str | None = None
    state: str | None = None
    product_page_views: int | None = None
    id_mapping_mismatch: bool = False
    product_detail_error_summary: str | None = None
    page_views_error_summary: str | None = None
    request_metadata_json: str = "{}"
    retrieved_at_utc: datetime | None = None


@dataclass(frozen=True, slots=True)
class CategoryScore:
    run_id: str
    category: str
    discovery_status: DiscoveryStatus
    discovery_filter_verified: bool
    discovery_unresolved_identity_count: int
    discovery_conflict_count: int
    discovery_duplicate_count: int
    discovered_population_count: int
    enriched_sample_count: int
    sample_is_census: bool
    sampling_basis: str
    sample_fraction: float | None = None
    unique_enrichment_count: int = 0
    overlap_category_count: int = 0
    overlap_sample_percentage: float | None = None
    usable_demand_sample_count: int = 0
    usable_recent_supply_sample_count: int = 0
    usable_quality_sample_count: int = 0
    breadth_source: str | None = None
    breadth_completeness_status: str | None = None
    discovery_bounded_by_verified_total: bool = False
    demand_stratum_eligibility_coverage: float | None = None
    recent_supply_stratum_eligibility_coverage: float | None = None
    quality_stratum_eligibility_coverage: float | None = None
    demand_per_asset_raw: float | None = None
    demand_median_raw: float | None = None
    breadth_raw: float | None = None
    recent_share_raw: float | None = None
    median_age_raw: float | None = None
    quality_raw: float | None = None
    stratum_statistics_json: str = "{}"
    component_d: float | None = None
    component_c: float | None = None
    component_r: float | None = None
    component_q: float | None = None
    market_opportunity_score: float | None = None
    score_state: ScoreState = ScoreState.UNAVAILABLE
    evidence_grade: EvidenceGrade = EvidenceGrade.INSUFFICIENT
    rankability_status: RankabilityStatus = RankabilityStatus.NOT_RANKABLE
    missing_components_json: str = "[]"
    warnings_json: str = "[]"
    reference_size: int = 0
    reference_usable_counts_json: str = "{}"
    top_3_stability: float | None = None
    top_5_stability: float | None = None
    maximum_score_delta: float | None = None
    maximum_rank_displacement: int | None = None
    sensitivity_warning: bool = False
    ranking_sensitivity_json: str = "{}"
    computed_at_utc: datetime | None = None


# Mandatory logical schema fields are kept in one place for validators and adapters.
MANDATORY_ROW_FIELDS: dict[str, tuple[str, ...]] = {
    name: tuple(field.name for field in fields(row_type))
    for name, row_type in {
        "runs": RunRow,
        "raw_discovery_observations": RawDiscoveryObservation,
        "sample_members": SampleMember,
        "enrichment_observations": EnrichmentObservation,
        "category_scores": CategoryScore,
    }.items()
}
