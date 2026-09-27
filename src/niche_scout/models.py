"""Typed domain contracts for the lean niche-scout data model.

These structures are deliberately persistence-neutral. ``None`` means that a
value is unavailable; it is never silently converted to a fabricated zero.

Every module in the package imports its enums, constants, policy versions, and
record types from here. The records mirror the mandatory logical fields of the
five SRS-lean §6 tables and carry deterministic JSON serialization contracts.
"""

from __future__ import annotations

import json
import types
import typing
from dataclasses import asdict, dataclass, fields
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, ClassVar, TypeVar, get_args, get_origin, get_type_hints

# --------------------------------------------------------------------------
# Policy versions
# --------------------------------------------------------------------------

ENDPOINT_CONTRACT_VERSION: str = "1.0.0"
IDENTITY_MAPPING_RULE_VERSION: str = "1.0.1"
SAMPLING_RULE_VERSION: str = "1.0.0"

# --------------------------------------------------------------------------
# Discovery and reference constants
# --------------------------------------------------------------------------

MAX_DISCOVERY_RESULTS_PER_CATEGORY: int = 9000
PAGE_SIZE: int = 96
MIN_CATEGORIES_PER_RUN: int = 8
STRONG_REFERENCE_CATEGORY_COUNT: int = 21
MAX_TAXONOMY_AGE_DAYS: int = 30

# --------------------------------------------------------------------------
# Sampling constants
# --------------------------------------------------------------------------

ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY: int = 100
SAMPLE_STRATA: int = 4
SAMPLE_PER_STRATUM: int = 25
MIN_USABLE_SAMPLES_PER_STRATUM: int = 5

# --------------------------------------------------------------------------
# Evidence and coverage thresholds
# --------------------------------------------------------------------------

MIN_REQUIRED_COMPONENT_COVERAGE: float = 0.50
STRONG_COMPONENT_COVERAGE: float = 0.80

# --------------------------------------------------------------------------
# Age, recent-window, and quality thresholds
# --------------------------------------------------------------------------

MIN_AGE_DAYS_FOR_RATE: int = 30
RECENT_WINDOW_DAYS: int = 365
QUALITY_MIN_RATING_COUNT: int = 5
QUALITY_MIN_ELIGIBLE_ASSETS: int = 5

# --------------------------------------------------------------------------
# Identity preflight defaults
# --------------------------------------------------------------------------

IDENTITY_PREFLIGHT_MIN_CATEGORIES: int = 5
IDENTITY_PREFLIGHT_ASSETS_PER_CATEGORY: int = 2
IDENTITY_PREFLIGHT_MAX_CONFLICT_RATE: float = 0.0
IDENTITY_PREFLIGHT_MIN_SUCCESS_RATE: float = 0.90

# --------------------------------------------------------------------------
# Fixed composite weights and subweights
# --------------------------------------------------------------------------

W_D: float = 0.35
W_C: float = 0.30
W_R: float = 0.20
W_Q: float = 0.15

DEMAND_SUBWEIGHT_PER_ASSET: float = 0.60
DEMAND_SUBWEIGHT_MEDIAN: float = 0.40

RECENT_SUBWEIGHT_SHARE: float = 0.70
RECENT_SUBWEIGHT_AGE: float = 0.30

SENSITIVITY_POLICIES: dict[str, dict[str, float]] = {
    "balanced": {"D": 0.35, "C": 0.30, "R": 0.20, "Q": 0.15},
    "demand_heavy": {"D": 0.50, "C": 0.25, "R": 0.15, "Q": 0.10},
    "competition_heavy": {"D": 0.30, "C": 0.45, "R": 0.15, "Q": 0.10},
}

# --------------------------------------------------------------------------
# Enums and status types
# --------------------------------------------------------------------------


class RunStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class DiscoveryStatus(str, Enum):
    COMPLETE = "complete"
    TRUNCATED = "truncated"
    PAGE_FAILED = "page_failed"
    FILTER_UNVERIFIED = "filter_unverified"
    CATEGORY_MISMATCH = "category_mismatch"
    IDENTITY_INCOMPLETE = "identity_incomplete"
    REQUEST_FAILED = "request_failed"


class IdentityResolutionStatus(str, Enum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    CONFLICT = "conflict"


class OperationStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"


class PageViewSemanticsStatus(str, Enum):
    UNVALIDATED = "unvalidated"
    VALIDATED_CUMULATIVE = "validated_cumulative"
    CONTRADICTED = "contradicted"


class GraphQLOperationCorrelationMode(str, Enum):
    EXPLICIT_KEY = "explicit_key"
    VALIDATED_POSITION = "validated_position"


class IdentityPreflightStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    INSUFFICIENT = "insufficient"


class BreadthSource(str, Enum):
    VERIFIED_TOTAL_COUNT = "verified_total_count"
    DISTINCT_CANONICAL_DISCOVERED_COUNT = "distinct_canonical_discovered_count"


class BreadthCompletenessStatus(str, Enum):
    COMPLETE = "complete"
    INCOMPLETE_ESTIMATE = "incomplete_estimate"


class SamplingBasis(str, Enum):
    CENSUS = "census"
    DETERMINISTIC_STRATIFIED_SAMPLE = "deterministic_stratified_sample"


class ScoreState(str, Enum):
    AVAILABLE = "available"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class EvidenceGrade(str, Enum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    INSUFFICIENT = "insufficient"


class RankabilityStatus(str, Enum):
    NOT_RANKABLE = "not_rankable"
    PROVISIONAL = "provisional"
    RANKABLE = "rankable"


class CategoryStatus(str, Enum):
    """Internal orchestration state; mapped to discovery, warnings, and evidence."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"


class CategoryFilterValidationStatus(str, Enum):
    VERIFIED = "verified"
    MISMATCH = "mismatch"
    UNVERIFIED = "unverified"


class WarningCode(str, Enum):
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


# --------------------------------------------------------------------------
# Serialization contracts
# --------------------------------------------------------------------------


def ensure_utc(value: datetime) -> datetime:
    """Return ``value`` normalized to a UTC datetime.

    Naive datetimes are rejected: the SRS requires timezone-aware UTC
    timestamps. A timezone-aware value in another offset is converted to UTC
    rather than rejected, so callers can pass any aware timestamp.
    """
    if not isinstance(value, datetime):
        raise ValueError("timestamp must be a datetime")
    if value.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware UTC")
    return value.astimezone(timezone.utc)


def serialize_value(value: Any) -> Any:
    """Convert a value into its deterministic JSON-compatible representation.

    ``datetime`` values are rendered as UTC ISO-8601 with a ``Z`` suffix,
    enums contribute their string value, and containers are serialized
    recursively. ``None`` is preserved: it means unavailable and is never
    replaced by a zero.
    """
    if isinstance(value, datetime):
        return ensure_utc(value).isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): serialize_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [serialize_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return [serialize_value(item) for item in sorted(value, key=repr)]
    return value


T = TypeVar("T")


def to_json_dict(instance: Any) -> dict[str, Any]:
    """Serialize a dataclass instance to a deterministic plain dictionary."""
    return serialize_value(asdict(instance))


def to_json(instance: Any) -> str:
    """Serialize a dataclass instance to compact, key-sorted JSON text."""
    return json.dumps(to_json_dict(instance), sort_keys=True, separators=(",", ":"))


def _deserialize_value(value: Any, annotation: Any) -> Any:
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin in (types.UnionType, typing.Union):
        if value is None and type(None) in args:
            return None
        return _deserialize_value(
            value, next(arg for arg in args if arg is not type(None))
        )
    if value is None:
        return None
    if origin in (list, tuple, set, frozenset):
        converted = [_deserialize_value(item, args[0]) for item in value]
        if origin is tuple:
            return tuple(converted)
        if origin is set:
            return set(converted)
        if origin is frozenset:
            return frozenset(converted)
        return converted
    if origin is dict:
        return {
            _deserialize_value(key, args[0]): _deserialize_value(item, args[1])
            for key, item in value.items()
        }
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return annotation(value)
    if annotation is datetime:
        return ensure_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
    if annotation is date:
        return date.fromisoformat(value)
    return value


def from_json(payload: str, row_type: type[T]) -> T:
    """Deserialize JSON produced by :func:`to_json` into ``row_type``.

    Naive timestamps in the payload are rejected; the round trip is exact for
    every value produced by :func:`to_json`.
    """
    raw = json.loads(payload)
    hints = get_type_hints(row_type)
    return row_type(
        **{name: _deserialize_value(value, hints[name]) for name, value in raw.items()}
    )


def _validate_record(instance: Any, utc_fields: tuple[str, ...]) -> None:
    for name in utc_fields:
        value = getattr(instance, name, None)
        if value is not None:
            ensure_utc(value)


# --------------------------------------------------------------------------
# Logical data model row structures (SRS-lean §6 mandatory fields)
# --------------------------------------------------------------------------


_ROW_TYPE_VAR = TypeVar("_ROW_TYPE_VAR")


class _UtcRecord:
    """Mixin validating that declared timestamp fields are timezone-aware UTC."""

    _utc_fields: ClassVar[tuple[str, ...]] = ()

    def _validate_utc_fields(self) -> None:
        _validate_record(self, self._utc_fields)


@dataclass(frozen=True)
class RunRecord(_UtcRecord):
    """Mandatory `runs` fields. ``status`` carries a :class:`RunStatus` value."""

    _utc_fields: ClassVar[tuple[str, ...]] = (
        "run_started_at_utc",
        "scoring_cutoff_utc",
        "completed_at_utc",
        "taxonomy_captured_at_utc",
    )

    run_id: str
    run_started_at_utc: datetime
    scoring_cutoff_utc: datetime | None
    completed_at_utc: datetime | None
    categories_json: str
    config_snapshot_json: str
    config_sha256: str
    taxonomy_version: str
    taxonomy_captured_at_utc: datetime
    taxonomy_sha256: str
    endpoint_contract_version: str
    identity_mapping_rule_version: str
    sampling_rule_version: str
    page_view_semantics_status: str
    graphql_operation_correlation_mode: str
    identity_preflight_status: str
    identity_preflight_summary_json: str
    status: str

    def __post_init__(self) -> None:
        self._validate_utc_fields()


@dataclass(frozen=True)
class RawDiscoveryObservationRecord(_UtcRecord):
    """Mandatory `raw_discovery_observations` fields plus duplicate audit linkage."""

    _utc_fields: ClassVar[tuple[str, ...]] = ("retrieved_at_utc",)

    observation_id: str
    run_id: str
    category: str
    discovery_ordinal: int
    asset_identity_key: str | None
    identity_candidates_json: str
    identity_resolution_status: str
    identity_resolution_reason: str | None
    category_value_json: str
    category_filter_validation_status: str
    stratum_index: int | None
    is_duplicate: bool
    duplicate_of_observation_id: str | None
    request_metadata_json: str
    error_summary_json: str | None
    retrieved_at_utc: datetime

    def __post_init__(self) -> None:
        self._validate_utc_fields()


@dataclass(frozen=True)
class SampleMemberRecord:
    """Mandatory `sample_members` fields; the triple key blocks duplicate rows."""

    run_id: str
    category: str
    asset_identity_key: str
    stratum_index: int
    stratum_start_ordinal: int
    stratum_end_ordinal: int
    sample_rank_within_stratum: int
    sample_is_census: bool
    selection_digest: str
    overlap_category_count: int
    overlap_sample_percentage: float | None
    preflight_selected: bool


@dataclass(frozen=True)
class EnrichmentObservationRecord(_UtcRecord):
    """Mandatory `enrichment_observations` fields; one row per identity per run."""

    _utc_fields: ClassVar[tuple[str, ...]] = (
        "first_published_date_utc",
        "retrieved_at_utc",
    )

    run_id: str
    asset_identity_key: str
    product_detail_status: str
    page_views_status: str
    graphql_id: str | None
    product_id: str | None
    rating_average: float | None
    rating_count: int | None
    review_count: int | None
    first_published_date_utc: datetime | None
    publisher_json: str | None
    category_json: str | None
    state: str | None
    product_page_views: int | None
    id_mapping_mismatch: bool
    product_detail_error_summary: str | None
    page_views_error_summary: str | None
    request_metadata_json: str
    retrieved_at_utc: datetime

    def __post_init__(self) -> None:
        self._validate_utc_fields()


@dataclass(frozen=True)
class CategoryScoreRecord(_UtcRecord):
    """Mandatory `category_scores` fields: raw values, components, and evidence.

    Unavailable values stay ``None``. No alias columns (``sample_size``,
    ``demand_usable_count``, and similar) exist on this record.
    """

    _utc_fields: ClassVar[tuple[str, ...]] = ("computed_at_utc",)

    run_id: str
    category: str
    discovery_status: str
    discovery_filter_verified: bool
    discovery_unresolved_identity_count: int
    discovery_conflict_count: int
    discovery_duplicate_count: int
    discovered_population_count: int
    enriched_sample_count: int
    sample_is_census: bool
    sampling_basis: str
    sample_fraction: float | None
    unique_enrichment_count: int
    overlap_category_count: int
    overlap_sample_percentage: float | None
    usable_demand_sample_count: int
    usable_recent_supply_sample_count: int
    usable_quality_sample_count: int
    breadth_source: str
    breadth_completeness_status: str
    discovery_bounded_by_verified_total: bool
    demand_stratum_eligibility_coverage: float
    recent_supply_stratum_eligibility_coverage: float
    quality_stratum_eligibility_coverage: float
    demand_per_asset_raw: float | None
    demand_median_raw: float | None
    breadth_raw: float | None
    recent_share_raw: float | None
    median_age_raw: float | None
    quality_raw: float | None
    stratum_statistics_json: str
    component_d: float | None
    component_c: float | None
    component_r: float | None
    component_q: float | None
    market_opportunity_score: float | None
    score_state: str
    evidence_grade: str
    rankability_status: str
    missing_components_json: str
    warnings_json: str
    reference_size: int
    reference_usable_counts_json: str
    top_3_stability: float | None
    top_5_stability: float | None
    maximum_score_delta: float | None
    maximum_rank_displacement: int | None
    sensitivity_warning: bool | None
    ranking_sensitivity_json: str
    computed_at_utc: datetime

    def __post_init__(self) -> None:
        self._validate_utc_fields()


# Mandatory logical schema fields are kept in one place for validators and adapters.
ROW_TYPES: dict[str, type[Any]] = {
    "runs": RunRecord,
    "raw_discovery_observations": RawDiscoveryObservationRecord,
    "sample_members": SampleMemberRecord,
    "enrichment_observations": EnrichmentObservationRecord,
    "category_scores": CategoryScoreRecord,
}

MANDATORY_ROW_FIELDS: dict[str, tuple[str, ...]] = {
    table: tuple(
        field.name for field in fields(row_type) if not field.name.startswith("_")
    )
    for table, row_type in ROW_TYPES.items()
}
