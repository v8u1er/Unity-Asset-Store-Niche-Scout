# Chunk 0 — Project skeleton and contracts

Status: VERIFIED
Depends on (frozen interfaces required before this plan can be trusted):
  none
Blocks (chunks whose plan/implementation needs this chunk's interface):
  Chunk 1 (Pure taxonomy, identity, and response validation)
  Chunk 2 (SQLite implementation and repository behavior)
  Chunk 3 (Coveo discovery adapter and streamed raw persistence)
  Chunk 4A (Canonical populations and deterministic sampling engine)
  Chunk 5 (GraphQL protocol adapter and response correlation)
  Chunk 6A (Identity preflight planner and gate)
  Chunk 7A (Metric eligibility, date, and page-view primitives)
  Chunk 12 (CLI commands and configuration precedence)
  Chunk 13 (Full acceptance suite and quality workflow)

## 1. Goal

Establish the package layout, module ownership boundaries, pure versus I/O architectural rules, complete typed domain and result models, enums, status types, policy versions, configuration precedence contracts, SQLite schema specifications and repository protocol, and machine-readable bidirectional test traceability validation so that all subsequent parallel and sequential implementation chunks develop against frozen contracts without circular dependencies or runtime guesswork.

## 2. Scope

### In scope

- Package skeleton and project layout: `pyproject.toml`, `src/niche_scout/`, `tests/`, `config/`, `README.md`, `.gitignore`, `.env.example`.
- Architectural module boundaries and pure function rules:
  - Strict separation between pure modules (`metrics.py`, `scoring.py`) and I/O / orchestration modules (`collector.py`, `collector_coveo.py`, `collector_graphql.py`, `database.py`, `pipeline.py`, `report.py`, `cli.py`).
  - Prohibition of clock reads (`time.time()`, `datetime.now()`) in pure modules; `scoring_cutoff_utc` is passed as an explicit timezone-aware UTC datetime.
  - Prohibition of network, filesystem, database, process, or CLI imports in `metrics.py` and `scoring.py`.
  - Automated AST import-boundary verification tool (`src/niche_scout/tools/check_import_boundaries.py`).
- Typed domain models, enums, and statuses representing the complete SRS data model in `src/niche_scout/models.py`:
  - `RunStatus` (`running`, `completed`, `failed`).
  - Discovery statuses (`complete`, `truncated`, `page_failed`, `filter_unverified`, `category_mismatch`, `identity_incomplete`, `request_failed`).
  - Identity resolution statuses (`resolved`, `unresolved`, `conflict`).
  - Operation statuses (`success`, `error`).
  - Page-view semantics status (`unvalidated`, `validated_cumulative`, `contradicted`).
  - GraphQL operation correlation mode (`explicit_key`, `validated_position`).
  - Identity preflight status (`passed`, `failed`, `insufficient`).
  - Catalog breadth source (`verified_total_count`, `distinct_canonical_discovered_count`) and completeness status (`complete`, `incomplete_estimate`).
  - Sampling basis (`census`, `deterministic_stratified_sample`).
  - Score state (`available`, `partial`, `unavailable`).
  - Evidence grade (`strong`, `moderate`, `weak`, `insufficient`).
  - Rankability status (`not_rankable`, `provisional`, `rankable`).
  - Internal category status (`healthy`, `degraded`, `failed`).
  - Standard report warning vocabulary codes from SRS Appendix C.
  - Logical record classes for mandatory fields of `runs`, `raw_discovery_observations`, `sample_members`, `enrichment_observations`, and `category_scores`.
  - JSON serialization/deserialization contracts for all structured audit fields.
- Constants and policy versions:
  - Version strings: `ENDPOINT_CONTRACT_VERSION`, `IDENTITY_MAPPING_RULE_VERSION`, `SAMPLING_RULE_VERSION`.
  - Discovery constants: `MAX_DISCOVERY_RESULTS_PER_CATEGORY = 2000`, `PAGE_SIZE = 96`.
  - Run and reference constants: `MIN_CATEGORIES_PER_RUN = 8`, `STRONG_REFERENCE_CATEGORY_COUNT = 21`, `MAX_TAXONOMY_AGE_DAYS = 30`.
  - Sampling constants: `ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY = 100`, `SAMPLE_STRATA = 4`, `SAMPLE_PER_STRATUM = 25`, `MIN_USABLE_SAMPLES_PER_STRATUM = 5`.
  - Evidence and coverage thresholds: `MIN_REQUIRED_COMPONENT_COVERAGE = 0.50`, `STRONG_COMPONENT_COVERAGE = 0.80`.
  - Age and recent window thresholds: `MIN_AGE_DAYS_FOR_RATE = 30`, `RECENT_WINDOW_DAYS = 365`.
  - Quality thresholds: `QUALITY_MIN_RATING_COUNT = 5`, `QUALITY_MIN_ELIGIBLE_ASSETS = 5`.
  - Identity preflight defaults: `IDENTITY_PREFLIGHT_MIN_CATEGORIES = 5`, `IDENTITY_PREFLIGHT_ASSETS_PER_CATEGORY = 2`, `IDENTITY_PREFLIGHT_MAX_CONFLICT_RATE = 0.0`, `IDENTITY_PREFLIGHT_MIN_SUCCESS_RATE = 0.90`.
  - Fixed scoring weights: `w_D = 0.35`, `w_C = 0.30`, `w_R = 0.20`, `w_Q = 0.15`, subweights for demand `(0.60, 0.40)` and recent supply `(0.70, 0.30)`.
  - Fixed sensitivity weight policies: `balanced`, `demand_heavy`, `competition_heavy`.
- Configuration and security contracts in `src/niche_scout/config.py`:
  - Typed configuration dataclass `NicheScoutConfig`.
  - Precedence hierarchy contract: CLI options override TOML configuration, which overrides in-code defaults.
  - Environment credential reading contract (`NICHESCOUT_COVEO_BEARER_TOKEN`, `NICHESCOUT_UNITY_CSRF_TOKEN`).
  - Secret redaction and `.env` ignore contract (`.env` gitignored, `.env.example` free of credentials).
  - Config files: `config/categories.json` (at least 8 categories), `config/category_taxonomy.json`, `config/default.toml`.
- SQLite schema specification and repository protocol in `src/niche_scout/database.py`:
  - `Repository` `typing.Protocol` declaring all persistence signatures required by collectors, sampling, enrichment, and scoring.
  - SQLite DDL schema definitions for tables `runs`, `raw_discovery_observations`, `sample_members`, `enrichment_observations`, `category_scores`.
  - Explicit specification of constraints, primary keys, and indexes (e.g. `(run_id, category, asset_identity_key)` for samples, `(run_id, category)` for scores).
  - No physical SQLite implementation or SQLite file operations in Chunk 0.
- Test traceability and quality infrastructure:
  - Registration of the `@pytest.mark.lreq("LREQ-...")` marker in `pyproject.toml`.
  - Machine-readable test-to-requirement matrix `tests/traceability.json`.
  - Traceability validator CLI tool `python -m niche_scout.tools.validate_traceability` checking bidirectional completeness. At Chunk 0, traceability validation enforces bidirectional coverage specifically for Chunk 0's 7 requirements: `LREQ-ARCH-010`, `LREQ-ARCH-020`, `LREQ-ARCH-030`, `LREQ-SEC-010`, `LREQ-NFR-040`, `LREQ-NFR-050`, `LREQ-NFR-060`.
  - Initial contract test suite in `tests/test_contracts.py`.

### Explicitly out of scope (and who owns it instead)

- Pure taxonomy schema validation, freshness validation, exact category-path matching, and canonical identity parsing primitives: Chunk 0 defines configuration models and status types, but pure validation logic is owned by Chunk 1 (primary implementation chunk).
- Physical SQLite implementation, database connections, DDL execution, streamed insertions, savepoints, and transactions: Chunk 0 defines the repository protocol and DDL schema specification; physical SQLite persistence behavior is owned by Chunk 2 (primary implementation chunk).
- Coveo network adapter, HTTP client, request building, pagination loop, rate limiting, and retry/backoff execution: Chunk 0 defines configuration contracts and credential types; Coveo HTTP collection and retry execution are owned by Chunk 3 (primary implementation chunk).
- Canonical population construction, four-stratum division, and deterministic SHA-256 sample selection: Chunk 0 defines sampling constants, status enums, and data models; pure sampling computation is owned by Chunk 4A (primary implementation chunk), and sample persistence is owned by Chunk 4B (primary implementation chunk).
- GraphQL network adapter, batch execution, and response correlation: Chunk 0 defines credential contracts and response status models; GraphQL collection is owned by Chunk 5 (primary implementation chunk).
- Identity preflight execution and bulk enrichment executor: preflight orchestration is owned by Chunk 6A (primary implementation chunk), and unique enrichment deduplication/persistence is owned by Chunk 6B (primary implementation chunk).
- Metric eligibility semantics, date calculations, and raw estimators: Chunk 0 defines pure boundary rules and model structures; metric eligibility is owned by Chunk 7A (primary implementation chunk) and raw estimators are owned by Chunk 7B (primary implementation chunk).
- Leave-one-out normalization, composite scoring, and sensitivity analysis: Chunk 0 defines scoring models, weights, and cutoff contracts; normalization and scoring are owned by Chunk 8 (primary implementation chunk), and evidence/sensitivity are owned by Chunk 9A/9B (primary implementation chunks).
- Pipeline orchestration and run lifecycle: Chunk 0 defines `RunStatus` and configuration models; execution orchestration is owned by Chunk 10 (primary implementation chunk).
- Local HTML report generation and dashboard server: Chunk 0 defines score and evidence view models; report rendering is owned by Chunk 11 (primary implementation chunk).
- CLI argument parsing and runtime configuration override execution: Chunk 0 defines typed config contracts; runtime CLI precedence behavior is owned by Chunk 12 (primary implementation chunk).
- Full acceptance test suite, end-to-end integration tests, and project quality verification: Chunk 0 defines test fixtures and traceability validator; final verification is owned by Chunk 13 (primary implementation chunk).

## 3. Requirements this chunk must satisfy

For every LREQ ID this chunk owns (primary, supporting, or completion), the normative text from `Documents/SRS-lean.md` is quoted below:

| LREQ ID | Ownership role here | Normative text (from SRS-lean.md, quoted/derived) | SRS section |
|---|---|---|---|
| LREQ-ARCH-010 | Primary owner (and completion chunk) | `metrics` and `scoring` SHALL accept plain typed input structures and return typed result structures. They SHALL not import or call `collector`, `database`, `report`, or `cli` code, and SHALL perform no network or file I/O. | §3.3 |
| LREQ-ARCH-020 | Primary owner (and completion chunk) | Pure metric and scoring functions SHALL NOT read the system clock. All timestamps SHALL be supplied by the orchestration layer. | §3.3 |
| LREQ-ARCH-030 | Supporting contract chunk (Primary owner: Chunk 10; Completion: Chunk 10) | The same normalized input data, policy versions, and configuration SHALL produce the same metric, score, evidence, and sensitivity outputs. | §3.3 |
| LREQ-EXT-010 | Supporting contract chunk (Primary owner: Chunk 3; Completion: Chunk 3) | Discovery SHALL use the parent SRS Coveo endpoint, required headers, captured taxonomy template, and selected-category facet mechanism. | §4.1 |
| LREQ-EXT-020 | Supporting contract chunk (Primary owner: Chunk 1; Completion: Chunk 3) | The cached taxonomy file SHALL include `schema_version`, `captured_at_utc`, `source_url`, `template_sha256`, and a canonical category-path inventory. The system SHALL abort before collection if the file is missing, malformed, stale, or does not contain every requested category. | §4.1 |
| LREQ-EXT-100 | Supporting contract chunk (Primary owner: Chunk 3; Completion: Chunk 3) | Requests SHALL be rate-limited and retry transient `429` and `5xx` responses with exponential backoff. Permanent authentication, CSRF, malformed request, or authorization failures SHALL not be retried indefinitely. | §4.1 |
| LREQ-GQL-010 | Supporting contract chunk (Primary owner: Chunk 5; Completion: Chunk 5) | Enrichment SHALL use the parent SRS GraphQL batch endpoint and the two required operations: `ProductDetail(id: ID!)` and `ProductPageViews(packageId: String!)`. Both operations SHALL use the same canonical `asset_identity_key`. | §4.2 |
| LREQ-SEC-010 | Primary owner (Supporting chunks: Chunk 3, Chunk 5, Chunk 12; Completion: Chunk 3, Chunk 5, Chunk 12) | Coveo and Unity CSRF credentials SHALL be read from environment variables and SHALL be required before network collection. | §4.3 |
| LREQ-SEC-020 | Supporting contract chunk (Primary owner: Chunk 2; Completion: Chunk 13) | Secrets SHALL NOT be written to source control, logs, SQLite, or error messages. The `.env` pattern SHALL be ignored by version control. | §4.3 |
| LREQ-ID-030 | Supporting contract chunk (Primary owner: Chunk 6A; Completion: Chunk 6A) | Default preflight policy is:<br>`IDENTITY_PREFLIGHT_MIN_CATEGORIES = 5`<br>`IDENTITY_PREFLIGHT_ASSETS_PER_CATEGORY = 2`<br>`IDENTITY_PREFLIGHT_MAX_CONFLICT_RATE = 0`<br>`IDENTITY_PREFLIGHT_MIN_SUCCESS_RATE = 0.90` | §4.4 |
| LREQ-SMP-030 | Supporting contract chunk (Primary owner: Chunk 4A; Completion: Chunk 4A) | Default sampling constants SHALL be:<br>`ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY = 100`<br>`SAMPLE_STRATA = 4`<br>`SAMPLE_PER_STRATUM = 25`<br>`MIN_USABLE_SAMPLES_PER_STRATUM = 5`<br>For lean v1, these sampling constants are fixed and SHALL satisfy:<br>`ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY = SAMPLE_STRATA * SAMPLE_PER_STRATUM`<br>Changing the sample size, stratum count, or per-stratum allocation requires a new sampling-rule version and SRS revision; an implementation SHALL not expose one of these values as independently configurable. | §5.1 |
| LREQ-SMP-040 | Supporting contract chunk (Primary owner: Chunk 4A; Completion: Chunk 4A) | A category with at most 100 canonical discovered assets SHALL be fully enriched. Its `sample_is_census` flag SHALL be true. | §5.1 |
| LREQ-SMP-060 | Supporting contract chunk (Primary owner: Chunk 4A; Completion: Chunk 4A) | Selection within each stratum SHALL compute a SHA-256 digest of the UTF-8 encoding of the three values joined by a NUL delimiter: `sampling_rule_version + NUL + category + NUL + asset_identity_key`. Assets SHALL be sorted by `(digest, asset_identity_key)` and the first `SAMPLE_PER_STRATUM` assets SHALL be selected. The implementation SHALL NOT use an unseeded random generator or platform-dependent hash function. | §5.1 |
| LREQ-MET-020 | Supporting contract chunk (Primary owner: Chunk 7A; Completion: Chunk 7A) | All age calculations SHALL use:<br>`age_days_exact = (scoring_cutoff_utc - first_published_date_utc).total_seconds() / 86400`<br>The floor of age may be used for display only. | §7.1 |
| LREQ-CLI-030 | Supporting contract chunk (Primary owner: Chunk 12; Completion: Chunk 12) | CLI options SHALL override TOML configuration, which SHALL override documented in-code defaults. | §10 |
| LREQ-NFR-040 | Primary owner (Supporting: Chunk 7A, Chunk 8; Completion: Chunk 13) | Public metric and scoring functions SHALL have type hints and docstrings describing null and edge-case behavior. | §11 |
| LREQ-NFR-050 | Primary owner (Completion: Chunk 13) | The system SHALL run on Python 3.11+ on Windows, macOS, and Linux using `pathlib` for paths. | §11 |
| LREQ-NFR-060 | Supporting contract chunk (Primary owner: Chunk 13; Completion: Chunk 13) | Formatting, linting, secret handling, and analytical tests SHALL be part of the normal workflow. Strict project-wide typing, 95% whole-package coverage, and CI-on-every-commit are deferred quality improvements, not lean MVP blockers. | §11 |
| LREQ-TST-010 | Supporting contract chunk (Primary owner: Chunk 13; Completion: Chunk 13) | Every formula SHALL have tests for normal values, explicit valid zero where applicable, missing values, invalid values, ties, and minimum boundaries. | §13 |

### Relevant normative definitions (§1.2, §1.4, §6)

- **Timestamps**: All timestamps used in calculations SHALL be timezone-aware UTC timestamps (§1.2).
- **Float precision**: All formulas operate internally at `float64` precision. Display rounding is not part of the calculation (§1.2).
- **Value distinction**: Missing, invalid, contradictory, or unavailable values SHALL remain unavailable; they SHALL NOT be silently converted to zero (§1.2).
- **Discovered population**: Distinct canonical asset identities returned by verified category discovery, excluding unresolved/conflicting identities from the canonical denominator but retaining them in audit data (§1.4).
- **Enrichment sample**: Assets selected from a category for GraphQL enrichment. It is a census for small categories and a distributed stratified sample for larger categories (§1.4).
- **Stratum**: One ordinal segment of a category's canonical discovery population (§1.4).
- **Usable observation**: An observation satisfying the component-specific type, range, state, identity, date, and operation-status rules (§1.4).
- **Sample fraction**: The proportion of a category's canonical discovered population included in its enrichment sample. It is `1.0` for a census category and is not a measure of statistical representativeness (§1.4).
- **Stratum eligibility coverage**: The proportion of discovered population weight belonging to strata that meet a component's minimum usable-observation rule. It is a data-support measure, not a probability-sampling coverage estimate or confidence measure (§1.4).
- **Age-normalized page-view index**: `product_page_views * 7 / age_days_exact`, using an undocumented page-view field. It is an unvalidated index, not a validated weekly traffic measurement or weekly traffic rate (§1.4).
- **Midrank relative position**: `(L + 0.5E) / m`, where `L` is the number of usable reference values below the target, `E` is the number equal to it, and `m` is the number of usable reference values. It is descriptive, not inferential (§1.4).
- **Base-rankable candidate**: A category that satisfies every rankability requirement except the final sensitivity thresholds. Sensitivity is evaluated over the fixed set of these candidates before final rankability is assigned (§1.4).
- **Rankable**: Evidence state indicating that a category may be used in the primary ranking under the policies in §9 (§1.4).
- **Within-run**: Relative to the category set and collection policy used in one run. Scores are not expected to be comparable across arbitrary runs (§1.4).
- **Data model tables**: Mandatory logical fields for `runs`, `raw_discovery_observations`, `sample_members`, `enrichment_observations`, and `category_scores` are defined in §6.1–6.5.

## 4. Interface contracts consumed

Chunk 0 is the foundational chunk of the project and lists no prerequisites (`none`). It consumes no upstream `interfaces/chunk-XX.md` contracts.

## 5. Interface contract this chunk produces

Downstream chunks depend on the following public surface: enums, domain model dataclasses, constants, configuration models, repository protocols, and traceability tools. Once verified, this section becomes `Documents/interfaces/chunk-00.md`.

### 5.1 Enums and status types (`src/niche_scout/models.py`)

```python
from enum import Enum

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
    """Internal orchestration state; mapped to discovery, warnings, evidence, and rankability."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"

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
```

### 5.2 Constants and policy versions (`src/niche_scout/models.py` / `src/niche_scout/config.py`)

```python
ENDPOINT_CONTRACT_VERSION: str = "1.0.0"
IDENTITY_MAPPING_RULE_VERSION: str = "1.0.0"
SAMPLING_RULE_VERSION: str = "1.0.0"

MAX_DISCOVERY_RESULTS_PER_CATEGORY: int = 2000
PAGE_SIZE: int = 96
MIN_CATEGORIES_PER_RUN: int = 8
STRONG_REFERENCE_CATEGORY_COUNT: int = 21
MAX_TAXONOMY_AGE_DAYS: int = 30

ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY: int = 100
SAMPLE_STRATA: int = 4
SAMPLE_PER_STRATUM: int = 25
MIN_USABLE_SAMPLES_PER_STRATUM: int = 5

MIN_REQUIRED_COMPONENT_COVERAGE: float = 0.50
STRONG_COMPONENT_COVERAGE: float = 0.80

MIN_AGE_DAYS_FOR_RATE: int = 30
RECENT_WINDOW_DAYS: int = 365

QUALITY_MIN_RATING_COUNT: int = 5
QUALITY_MIN_ELIGIBLE_ASSETS: int = 5

IDENTITY_PREFLIGHT_MIN_CATEGORIES: int = 5
IDENTITY_PREFLIGHT_ASSETS_PER_CATEGORY: int = 2
IDENTITY_PREFLIGHT_MAX_CONFLICT_RATE: float = 0.0
IDENTITY_PREFLIGHT_MIN_SUCCESS_RATE: float = 0.90

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
```

### 5.3 Logical data model row structures (`src/niche_scout/models.py`)

All structures represent the exact mandatory fields from SRS-lean §6:

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

@dataclass(frozen=True)
class RunRecord:
    run_id: str
    run_started_at_utc: datetime
    scoring_cutoff_utc: Optional[datetime]
    completed_at_utc: Optional[datetime]
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

@dataclass(frozen=True)
class RawDiscoveryObservationRecord:
    observation_id: str
    run_id: str
    category: str
    discovery_ordinal: int
    asset_identity_key: Optional[str]
    identity_candidates_json: str
    identity_resolution_status: str
    identity_resolution_reason: Optional[str]
    category_value_json: str
    category_filter_validation_status: str
    stratum_index: Optional[int]
    is_duplicate: bool
    duplicate_of_observation_id: Optional[str]
    request_metadata_json: str
    error_summary_json: Optional[str]
    retrieved_at_utc: datetime

@dataclass(frozen=True)
class SampleMemberRecord:
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
    overlap_sample_percentage: Optional[float]
    preflight_selected: bool

@dataclass(frozen=True)
class EnrichmentObservationRecord:
    run_id: str
    asset_identity_key: str
    product_detail_status: str
    page_views_status: str
    graphql_id: Optional[str]
    product_id: Optional[str]
    rating_average: Optional[float]
    rating_count: Optional[int]
    review_count: Optional[int]
    first_published_date_utc: Optional[datetime]
    publisher_json: Optional[str]
    category_json: Optional[str]
    state: Optional[str]
    product_page_views: Optional[int]
    id_mapping_mismatch: bool
    product_detail_error_summary: Optional[str]
    page_views_error_summary: Optional[str]
    request_metadata_json: str
    retrieved_at_utc: datetime

@dataclass(frozen=True)
class CategoryScoreRecord:
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
    sample_fraction: Optional[float]
    unique_enrichment_count: int
    overlap_category_count: int
    overlap_sample_percentage: Optional[float]
    usable_demand_sample_count: int
    usable_recent_supply_sample_count: int
    usable_quality_sample_count: int
    breadth_source: str
    breadth_completeness_status: str
    discovery_bounded_by_verified_total: bool
    demand_stratum_eligibility_coverage: float
    recent_supply_stratum_eligibility_coverage: float
    quality_stratum_eligibility_coverage: float
    demand_per_asset_raw: Optional[float]
    demand_median_raw: Optional[float]
    breadth_raw: Optional[float]
    recent_share_raw: Optional[float]
    median_age_raw: Optional[float]
    quality_raw: Optional[float]
    stratum_statistics_json: str
    component_d: Optional[float]
    component_c: Optional[float]
    component_r: Optional[float]
    component_q: Optional[float]
    market_opportunity_score: Optional[float]
    score_state: str
    evidence_grade: str
    rankability_status: str
    missing_components_json: str
    warnings_json: str
    reference_size: int
    reference_usable_counts_json: str
    top_3_stability: Optional[float]
    top_5_stability: Optional[float]
    maximum_score_delta: Optional[float]
    maximum_rank_displacement: Optional[int]
    sensitivity_warning: Optional[bool]
    ranking_sensitivity_json: str
    computed_at_utc: datetime
```

### 5.4 Repository Protocol and SQLite schema specifications (`src/niche_scout/database.py`)

```python
from typing import Protocol, Sequence, Optional, Iterator
from niche_scout.models import (
    RunRecord,
    RawDiscoveryObservationRecord,
    SampleMemberRecord,
    EnrichmentObservationRecord,
    CategoryScoreRecord,
)

class Repository(Protocol):
    """Persistence protocol consumed by downstream orchestration. No SQLite implementation in Chunk 0."""
    def insert_run(self, run: RunRecord) -> None: ...
    def update_run_status(self, run_id: str, status: str, completed_at_utc: Optional[datetime] = None) -> None: ...
    def insert_raw_discovery_observations(self, observations: Sequence[RawDiscoveryObservationRecord]) -> None: ...
    def insert_sample_members(self, members: Sequence[SampleMemberRecord]) -> None: ...
    def insert_enrichment_observations(self, observations: Sequence[EnrichmentObservationRecord]) -> None: ...
    def insert_category_scores(self, scores: Sequence[CategoryScoreRecord]) -> None: ...
    def get_run(self, run_id: str) -> Optional[RunRecord]: ...
    def iter_raw_discovery_observations(self, run_id: str, category: str) -> Iterator[RawDiscoveryObservationRecord]: ...
    def get_sample_members(self, run_id: str, category: str) -> Sequence[SampleMemberRecord]: ...
    def get_enrichment_observation(self, run_id: str, asset_identity_key: str) -> Optional[EnrichmentObservationRecord]: ...
    def get_category_scores(self, run_id: str) -> Sequence[CategoryScoreRecord]: ...
```

DDL statements defined as contract strings in `src/niche_scout/database.py`:
- `CREATE TABLE runs (...)` with primary key `run_id`.
- `CREATE TABLE raw_discovery_observations (...)` with primary key `observation_id`, index on `(run_id, category, discovery_ordinal)`.
- `CREATE TABLE sample_members (...)` with primary key `(run_id, category, asset_identity_key)`.
- `CREATE TABLE enrichment_observations (...)` with primary key `(run_id, asset_identity_key)`.
- `CREATE TABLE category_scores (...)` with primary key `(run_id, category)`.

### 5.5 Configuration contracts (`src/niche_scout/config.py`)

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

@dataclass(frozen=True)
class Credentials:
    coveo_token: str
    unity_csrf_token: str

@dataclass(frozen=True)
class NicheScoutConfig:
    categories_path: Path
    taxonomy_path: Path
    db_path: Path
    max_discovery_results_per_category: int
    page_size: int
    min_categories_per_run: int
    strong_reference_category_count: int
    max_taxonomy_age_days: int
    min_usable_samples_per_stratum: int
    min_age_days_for_rate: int
    recent_window_days: int
    quality_min_rating_count: int
    quality_min_eligible_assets: int
    identity_preflight_min_categories: int
    identity_preflight_assets_per_category: int
    identity_preflight_min_success_rate: float
    source: str = "defaults"

    def policy_versions(self) -> dict[str, str]: ...

def load_config(
    cli_args: Optional[dict[str, Any]] = None,
    toml_path: Optional[Path] = None,
) -> NicheScoutConfig:
    """Precedence contract: cli_args > toml_path > in-code defaults."""
    ...

def get_credentials() -> Credentials:
    """Read credentials from environment; raise ValueError if missing."""
    ...
```

Note: `IDENTITY_PREFLIGHT_MAX_CONFLICT_RATE` is a frozen policy constant of `src/niche_scout/models.py` (`0.0`), not a user-configurable field on `NicheScoutConfig`.

### 5.6 Test traceability matrix contract (`tests/traceability.json`)

Mapping structure where keys are fully qualified pytest node IDs (base node IDs for parameterized tests) and values are arrays of individual `LREQ-*` strings:

```json
{
  "tests/test_contracts.py::test_models_import": ["LREQ-ARCH-010"],
  "tests/test_contracts.py::test_pure_boundary_no_clock": ["LREQ-ARCH-020"],
  "tests/test_contracts.py::test_determinism_contract": ["LREQ-ARCH-030"],
  "tests/test_contracts.py::test_coveo_endpoint_contract": ["LREQ-EXT-010"],
  "tests/test_contracts.py::test_taxonomy_contract": ["LREQ-EXT-020"],
  "tests/test_contracts.py::test_coveo_retry_contract": ["LREQ-EXT-100"],
  "tests/test_contracts.py::test_graphql_endpoint_contract": ["LREQ-GQL-010"],
  "tests/test_contracts.py::test_credentials_contract": ["LREQ-SEC-010"],
  "tests/test_contracts.py::test_secrets_redaction_contract": ["LREQ-SEC-020"],
  "tests/test_contracts.py::test_preflight_constants_contract": ["LREQ-ID-030"],
  "tests/test_contracts.py::test_sampling_constants_contract": ["LREQ-SMP-030"],
  "tests/test_contracts.py::test_census_model_contract": ["LREQ-SMP-040"],
  "tests/test_contracts.py::test_selection_digest_contract": ["LREQ-SMP-060"],
  "tests/test_contracts.py::test_age_calculation_contract": ["LREQ-MET-020"],
  "tests/test_contracts.py::test_config_precedence_contract": ["LREQ-CLI-030"],
  "tests/test_contracts.py::test_type_hints_and_docstrings": ["LREQ-NFR-040"],
  "tests/test_contracts.py::test_platform_pathlib_contract": ["LREQ-NFR-050"],
  "tests/test_contracts.py::test_quality_workflow_contract": ["LREQ-NFR-060"],
  "tests/test_contracts.py::test_formula_test_conventions": ["LREQ-TST-010"]
}
```

## 6. Files touched

| File | New/modified | Purpose |
|---|---|---|
| `pyproject.toml` | New | Package build metadata, dependencies, pytest configuration, `@pytest.mark.lreq` registration |
| `src/niche_scout/__init__.py` | New | Package exports, version string |
| `src/niche_scout/models.py` | New | Complete domain models, enums, status types, constants, policy versions, serialization |
| `src/niche_scout/config.py` | New | Typed configuration dataclass, TOML parsing, precedence hierarchy, credential reader |
| `src/niche_scout/database.py` | New | SQLite DDL schema specification, `Repository` protocol (no SQLite execution) |
| `src/niche_scout/metrics.py` | New | Pure stub enforcing pure import boundaries and typed signatures |
| `src/niche_scout/scoring.py` | New | Pure stub enforcing pure import boundaries and typed signatures |
| `src/niche_scout/tools/__init__.py` | New | Tools package init |
| `src/niche_scout/tools/check_import_boundaries.py` | New | AST tool asserting `metrics.py` and `scoring.py` import no I/O or clock modules |
| `src/niche_scout/tools/validate_traceability.py` | New | Bidirectional test traceability validation tool |
| `config/categories.json` | New | Default category selection containing at least 8 valid categories |
| `config/category_taxonomy.json` | New | Taxonomy cache fixture containing required header fields and category inventory |
| `config/default.toml` | New | Default configuration file matching SRS-lean constants |
| `.gitignore` | New | Version control ignore rules: ignores `.env`, `.venv`, `__pycache__`, `*.db`, `*.sqlite` |
| `.env.example` | New | Template environment variable file free of actual secrets |
| `README.md` | New | Project overview, architectural boundaries, setup instructions |
| `tests/test_contracts.py` | New | Analytical contract unit tests verifying all Chunk 0 obligations |
| `tests/traceability.json` | New | Machine-readable test-to-requirement matrix |
| `tests/fixtures/__init__.py` | New | Fixtures package init |
| `tests/fixtures/config_fixtures.py` | New | Typed test configuration, taxonomy, and environment dictionary fixtures |
| `tests/fixtures/README.md` | New | Documentation for test fixtures |

Note: Obsolete root-level `tools/` directory is migrated/removed in favor of the package tools at `src/niche_scout/tools/`.

## 7. Task breakdown

Ordered checklist, tagged with LREQ IDs:

- [ ] Initialize repository structure and configuration files (`pyproject.toml`, `.gitignore`, `.env.example`, `README.md`). (LREQ-NFR-050, LREQ-NFR-060, LREQ-SEC-020)
- [ ] Define default category list in `config/categories.json` with at least 8 valid categories. (LREQ-CLI-030)
- [ ] Define default configuration in `config/default.toml` and sample taxonomy in `config/category_taxonomy.json`. (LREQ-EXT-020, LREQ-CLI-030)
- [ ] Implement `src/niche_scout/models.py` with all enums (`RunStatus`, `DiscoveryStatus`, `IdentityResolutionStatus`, `OperationStatus`, `PageViewSemanticsStatus`, `GraphQLOperationCorrelationMode`, `IdentityPreflightStatus`, `BreadthSource`, `BreadthCompletenessStatus`, `SamplingBasis`, `ScoreState`, `EvidenceGrade`, `RankabilityStatus`, `CategoryStatus`, `WarningCode`). (LREQ-ARCH-010, LREQ-SMP-040, LREQ-NFR-040)
- [ ] Add policy versions, sampling constants, preflight constants, quality thresholds, reference sizes, and fixed scoring weights to `src/niche_scout/models.py`. (LREQ-ARCH-030, LREQ-ID-030, LREQ-SMP-030, LREQ-SMP-060)
- [ ] Define typed logical record dataclasses (`RunRecord`, `RawDiscoveryObservationRecord`, `SampleMemberRecord`, `EnrichmentObservationRecord`, `CategoryScoreRecord`) and JSON serialization contracts in `src/niche_scout/models.py`. (LREQ-ARCH-010, LREQ-NFR-040)
- [ ] Implement `src/niche_scout/config.py` with typed `NicheScoutConfig`, `Credentials`, precedence logic (CLI > TOML > defaults), and environment credential readers (`NICHESCOUT_COVEO_BEARER_TOKEN`, `NICHESCOUT_UNITY_CSRF_TOKEN`). (LREQ-EXT-010, LREQ-EXT-100, LREQ-GQL-010, LREQ-SEC-010, LREQ-CLI-030)
- [ ] Implement `src/niche_scout/database.py` with DDL table definitions and `Repository` typing protocol. (LREQ-ARCH-010, LREQ-SEC-020)
- [ ] Create pure module stubs `src/niche_scout/metrics.py` and `src/niche_scout/scoring.py` with typed public function signatures taking explicit `scoring_cutoff_utc` and without clock/IO imports. (LREQ-ARCH-010, LREQ-ARCH-020, LREQ-MET-020, LREQ-NFR-040)
- [ ] Implement AST import-boundary checker `src/niche_scout/tools/check_import_boundaries.py`. (LREQ-ARCH-010, LREQ-ARCH-020)
- [ ] Implement bidirectional traceability validator `src/niche_scout/tools/validate_traceability.py`. (LREQ-NFR-060, LREQ-TST-010)
- [ ] Register `@pytest.mark.lreq` in `pyproject.toml`. (LREQ-NFR-060)
- [ ] Write unit contract tests in `tests/test_contracts.py` with `@pytest.mark.lreq` markers covering all Chunk 0 LREQs. (LREQ-ARCH-010, LREQ-ARCH-020, LREQ-ARCH-030, LREQ-EXT-010, LREQ-EXT-020, LREQ-EXT-100, LREQ-GQL-010, LREQ-SEC-010, LREQ-SEC-020, LREQ-ID-030, LREQ-SMP-030, LREQ-SMP-040, LREQ-SMP-060, LREQ-MET-020, LREQ-CLI-030, LREQ-NFR-040, LREQ-NFR-050, LREQ-NFR-060, LREQ-TST-010)
- [ ] Populate `tests/traceability.json` with mappings from `tests/test_contracts.py` node IDs to LREQ IDs. (LREQ-NFR-060, LREQ-TST-010)
- [ ] Verify that `check_import_boundaries` and `validate_traceability` pass. (LREQ-ARCH-010, LREQ-NFR-060)

## 8. Edge cases and invariants

- **Pure module boundary invariant**: `metrics.py` and `scoring.py` must import only typed structures from `models.py` or standard pure libraries (`math`, `typing`, `dataclasses`, `datetime`). They must never import `sqlite3`, `requests`, `urllib`, `sys`, `time`, or I/O modules (`collector`, `database`, `report`, `cli`).
- **Clock read prohibition invariant**: No pure function reads `datetime.now()` or `time.time()`. All timestamps must be passed explicitly as arguments; specifically, `scoring_cutoff_utc` is a required timezone-aware UTC datetime.
- **Determinism invariant**: Given identical normalized inputs, policy versions, and configuration, pure calculations must produce structurally and numerically equivalent results.
- **Null vs Zero distinction invariant**: Missing, invalid, contradictory, or unavailable values remain unavailable; they must never be silently converted to zero.
- **Distinct status states invariant**: Run status (`running`, `completed`, `failed`), category discovery status, category health status (`healthy`, `degraded`, `failed`), score state (`available`, `partial`, `unavailable`), evidence grade (`strong`, `moderate`, `weak`, `insufficient`), and rankability status (`not_rankable`, `provisional`, `rankable`) are distinct fields that must never be conflated.
- **Primary key uniqueness invariants**:
  - `runs`: `run_id`.
  - `raw_discovery_observations`: `observation_id`.
  - `sample_members`: `(run_id, category, asset_identity_key)` prevents duplicate sample membership.
  - `enrichment_observations`: `(run_id, asset_identity_key)` enforces at most one enrichment record per unique identity per run.
  - `category_scores`: `(run_id, category)` enforces one score row per category per run.
- **Preflight rate edge case**: When attempted preflight unique identities is 0, preflight success and conflict rates must be null and status must be `insufficient`, never zero success.
- **Census boundary edge case**: Categories with discovered canonical population `N <= 100` are census categories (`sample_is_census = True`); when `N = 0`, `sample_fraction` is null.
- **Secret redaction invariant**: `.env` is ignored by version control; `.env.example` contains only placeholder variable names; credentials are never committed, logged, or serialized into SQLite.
- **Cross-platform path invariant**: All file paths must use `pathlib.Path` to ensure identical behavior on Windows, macOS, and Linux.

## 9. Test plan

### Test files to create

- `tests/test_contracts.py`: Comprehensive contract test suite exercising all models, enums, constants, configuration precedence, schema specifications, import boundaries, and traceability validation.

### Fixtures and golden vectors needed

- `tests/fixtures/config_fixtures.py`:
  - Default TOML configuration dictionary.
  - Custom TOML configuration fixture string.
  - Mock CLI argument dictionaries overriding specific keys.
  - Taxonomy JSON fixture with valid headers and sample category tree.
  - Mock environment dictionary containing test credential variables.
- AST import boundary check against `src/niche_scout/metrics.py` and `src/niche_scout/scoring.py`.

### Required pytest LREQ markers

The test suite must register and assert the following markers (1:1 mapping with Section 3):
- `@pytest.mark.lreq("LREQ-ARCH-010")`: Verifies pure boundary rules and typed signatures.
- `@pytest.mark.lreq("LREQ-ARCH-020")`: Verifies prohibition of clock reads in pure modules.
- `@pytest.mark.lreq("LREQ-ARCH-030")`: Verifies configuration and policy version determinism contracts.
- `@pytest.mark.lreq("LREQ-EXT-010")`: Verifies Coveo endpoint configuration contracts.
- `@pytest.mark.lreq("LREQ-EXT-020")`: Verifies taxonomy cache structure and required fields.
- `@pytest.mark.lreq("LREQ-EXT-100")`: Verifies retry and backoff configuration contracts.
- `@pytest.mark.lreq("LREQ-GQL-010")`: Verifies GraphQL batch endpoint contract and operation definitions.
- `@pytest.mark.lreq("LREQ-SEC-010")`: Verifies credential reading from environment and requirement before collection.
- `@pytest.mark.lreq("LREQ-SEC-020")`: Verifies `.gitignore` ignores `.env` and `.env.example` contains no secrets.
- `@pytest.mark.lreq("LREQ-ID-030")`: Verifies default identity preflight policy constants.
- `@pytest.mark.lreq("LREQ-SMP-030")`: Verifies fixed sampling constants and stratum allocation formula.
- `@pytest.mark.lreq("LREQ-SMP-040")`: Verifies census flag contract for populations up to 100.
- `@pytest.mark.lreq("LREQ-SMP-060")`: Verifies SHA-256 NUL-delimited selection digest contract.
- `@pytest.mark.lreq("LREQ-MET-020")`: Verifies exact UTC age calculation formula contract.
- `@pytest.mark.lreq("LREQ-CLI-030")`: Verifies CLI > TOML > in-code defaults configuration precedence contract.
- `@pytest.mark.lreq("LREQ-NFR-040")`: Verifies type hints and docstrings on public metric/scoring stubs.
- `@pytest.mark.lreq("LREQ-NFR-050")`: Verifies Python 3.11+ cross-platform `pathlib.Path` usage.
- `@pytest.mark.lreq("LREQ-NFR-060")`: Verifies code formatting, linting, and analytical test workflow setup.
- `@pytest.mark.lreq("LREQ-TST-010")`: Verifies test suite foundation for formula testing conventions (normal, zero, missing, invalid, ties, boundaries).

### Traceability entries to add (`tests/traceability.json`)

All base node IDs in `tests/test_contracts.py` must map to their respective `LREQ-*` IDs.

## 10. Definition of done (gate)

The gate bullets below are copied **verbatim** from `Documents/requirements-dependency-map.md` Chunk 0 Gate (lines 432–441):

- Package imports successfully.
- `metrics.py` and `scoring.py` do not import I/O modules.
- Configuration precedence has a typed contract and fixture cases; behavioral CLI precedence tests are completed in Chunk 12.
- All required status values and mandatory logical row fields are represented by typed structures.
- The repository protocol and schema specification are defined without requiring SQLite behavior in this chunk.
- Chunk 0A, 0B, and 0C sub-gates pass independently.
- Every analytical test has an explicit `@pytest.mark.lreq("LREQ-...")` marker and a corresponding `tests/traceability.json` entry; missing markers or entries fail the local test command, while parameterized tests use their base node ID.
- The traceability validator passes in both directions: every referenced LREQ exists and every individual LREQ has at least one mapped test.
- `.env` is ignored and `.env.example` contains no credentials.
- No network code is required yet.

## 11. Explicit prohibitions

- **No network I/O**: Must not issue HTTP requests, open network sockets, or initiate live Coveo/GraphQL sessions.
- **No SQLite execution**: Must not create SQLite database files on disk, open database connections, or execute DDL/DML statements during Chunk 0.
- **No clock reads in pure modules**: Must not import or call `time.time()`, `datetime.now()`, `datetime.utcnow()`, or similar clock APIs in `metrics.py` and `scoring.py`.
- **No I/O imports in pure modules**: Must not import `sqlite3`, `requests`, `urllib`, `sys`, `collector`, `database`, `report`, or `cli` inside `metrics.py` and `scoring.py`.
- **No silent zero substitution**: Must not convert null, missing, invalid, or contradictory values to `0` or `0.0`.
- **No committed credentials**: Must not commit real API tokens, session cookies, or secrets to Git; `.env` must remain uncommitted and `.env.example` must contain only empty placeholders.
- **No duplicate alias schema fields**: Must not add duplicate columns such as `sample_size`, `demand_usable_count`, `recent_supply_usable_count`, or `quality_usable_count` to `category_scores`.
- **No configurable sampling constants or scoring weights in v1**: Must not expose sampling constants (`SAMPLE_STRATA`, `SAMPLE_PER_STRATUM`) or composite scoring weights (`w_D`, `w_C`, `w_R`, `w_Q`) as independently user-configurable in `config/default.toml`.

## 12. Open questions / assumptions

None
