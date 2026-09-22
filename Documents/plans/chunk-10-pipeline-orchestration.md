# Chunk 10 — Pipeline orchestration

Status: FROZEN
Depends on (frozen interfaces required before this plan can be trusted):
  `Documents/interfaces/chunk-00.md` (VERIFIED), `chunk-01.md` (VERIFIED),
  `chunk-02.md` (VERIFIED), `chunk-03.md` (VERIFIED), `chunk-4A.md` (VERIFIED),
  `chunk-4B.md` (VERIFIED), `chunk-05.md` (VERIFIED), `chunk-6A.md` (VERIFIED),
  `chunk-6B.md` (VERIFIED), `chunk-7A.md` (VERIFIED), `chunk-7B.md` (VERIFIED),
  `chunk-08.md` (VERIFIED), `chunk-9A.md` (VERIFIED), `chunk-9B.md` (VERIFIED)
Blocks (chunks whose plan/implementation needs this chunk's interface):
  Chunk 11 (report read model consumes the persisted run/category rows this chunk
  writes and completes), Chunk 12 (`run` command invokes this entry point and owns
  the exit code), Chunk 13 (end-to-end acceptance and traceability closure).

## 1. Goal

This chunk makes one whole run executable. Before it, every pure function
(`validation`, `sampling`, `metrics`, `scoring`) and every I/O adapter
(`collector_coveo`, `collector_graphql`, `database`, and the 6A/6B orchestration
already in `pipeline.py`) exists and is separately tested, but nothing connects
them in the SRS-prescribed order for one invocation. Chunk 10 adds the run-level
entry point `run_pipeline(...)` to `pipeline.py`: it loads and validates
configuration/taxonomy before any request, creates the `RunRecord` with real
policy hashes, drives discovery → persistence → canonicalization → sampling →
preflight → enrichment → cutoff → metrics → LOO references → scores →
base candidates → sensitivity → final evidence/rankability → persistence → run
status, isolates every failure to the smallest affected unit, and completes the
`runs.taxonomy_sha256` provenance obligation that dependency-map §7 assigns to
this chunk. The module stays an I/O orchestrator: it reads the clock only at
caller-injected seams, and the pure modules keep their defined boundaries.

## 2. Scope

### In scope

- One public entry point `run_pipeline(...)` in `src/niche_scout/pipeline.py`,
  with caller-injected clock, sleep, Coveo transport, and GraphQL transport so the
  whole run is testable with no network and no real credentials.
- The 17-step sequence of dependency-map Chunk 10 "Implement this sequence",
  including the exact ordering and transaction boundaries below.
- Run metadata creation and policy hashes (step 3), including a **non-empty**
  `taxonomy_sha256` and the `RunRecord` fields the frozen schema requires as
  `NOT NULL` (`identity_preflight_summary_json` seeded at insert).
- Preflight-failure path: `run.status = failed`, retain discovery/sample/preflight
  observations, zero bulk-enrichment requests, skip metric/score/ranking
  computation, persist per-category limitations where possible, no rankable
  scores, dashboard-audit visibility, and a non-zero CLI exit signalled to the
  caller (exit-code ownership is Chunk 12).
- 8–20-category provisional runs (empty `base_rankable_candidates`, null
  stability) and the `< MIN_CATEGORIES_PER_RUN` rejection boundary.
- Run-level status transitions and separation of run status, discovery status,
  score state, evidence grade, and rankability (hard rule 7).
- LREQ-NFR-020 logging is invoked through the existing 6B
  `log_enrichment_projection` before enrichment; this chunk supplies the counts.
- The empty-`taxonomy_sha256` rejection (dependency-map §7), implemented at the
  closest enforcement point, with its persistence test.

### Explicitly out of scope (and who owns it instead)

- **The `niche-scout run` / `niche-scout dashboard` commands, argument parsing,
  CLI/TOML/default precedence, and the process exit code** — Chunk 12 is the
  primary owner (`LREQ-CLI-010`, `LREQ-CLI-030`, `LREQ-CLI-040`). Chunk 10 is a
  *supporting orchestration chunk* for `LREQ-CLI-010` and `LREQ-CLI-040`: it
  accepts resolved configuration and returns a run outcome; it does not call
  `sys.exit`, does not parse `argv`, and does not render a report.
- **Report rendering and the read-only dashboard** — Chunk 11. Chunk 10 writes
  the rows the report reads and returns a value object; it does not import
  `report.py`.
- **Coveo protocol behavior** (request construction, pagination, retry, terminal
  statuses) — Chunk 3 (`collector_coveo.py`). Chunk 10 calls `discover_category`.
- **GraphQL protocol behavior** (query shape, correlation, response validation,
  per-operation status) — Chunk 5 (`collector_graphql.py`). Chunk 10 calls the
  6A helper `_run_adapter`/`enrich_asset`, directly or through 6B.
- **Preflight planning, execution, gate, and the `failed` run transition** —
  Chunk 6A, already implemented in `pipeline.py`. Chunk 10 calls
  `run_identity_preflight` and consumes its outcome; it must not re-decide the
  gate or downgrade an existing `failed` status.
- **Unique enrichment execution, reuse, projection, cutoff capture, and
  post-enrichment finalization** — Chunk 6B, already implemented in
  `pipeline.py`. Chunk 10 computes the union's inputs, calls
  `compute_enrichment_union` → `build_enrichment_projection` →
  `enrich_unique_identities` → `capture_scoring_cutoff_utc` →
  `finalize_enrichment`, and owns steps 1–8, 11–17.
- **Canonical population and sampling math** — Chunk 4A (`sampling.py`, pure);
  **sample persistence, overlap, pending summaries** — Chunk 4B
  (`persist_run_sampling`).
- **Metric eligibility and raw estimators** — Chunks 7A/7B (`metrics.py`, pure).
- **Normalization, components, composite** — Chunk 8; **base candidates and
  pre-sensitivity evidence** — Chunk 9A; **sensitivity, final evidence, final
  rankability** — Chunk 9B (`scoring.py`, pure).
- **Chunk 13's acceptance suite, golden-vector closure, and traceability-validator
  widening** (`LREQ-NFR-060`). Chunk 10 adds pipeline tests only.

## 3. Requirements this chunk must satisfy

Ownership roles below are read from the ownership matrix rows (dependency map
§"Ownership and test traceability matrix"): `LREQ-ARCH-030` primary owner Chunk 10,
completion Chunk 10; `LREQ-ID-040` primary Chunk 6A, completion Chunks 6A and 10;
`LREQ-NFR-020` primary Chunk 6B, completion Chunk 10; `LREQ-NFR-030` primary
Chunk 10; `LREQ-EXT-090` primary Chunk 3, supporting Chunks 1/2, completion
Chunk 10; `LREQ-NRM-020` primary Chunk 8, supporting Chunk 2, completion Chunk 10;
`LREQ-EVD-020` primary Chunk 9A, completion Chunk 10; `LREQ-SEN-020` primary
Chunk 9B, completion Chunk 10; `LREQ-CLI-010` primary Chunk 12, supporting Chunks
6A/6B/8/10/11; `LREQ-CLI-040` primary Chunk 12, supporting Chunks 1/8/9A/10.

| LREQ ID | Ownership role here | Normative text (from SRS-lean.md, quoted/derived) | SRS section |
|---|---|---|---|
| LREQ-ARCH-030 | Primary implementation (matrix: primary Chunk 10, completion Chunk 10) | "The same normalized input data, policy versions, and configuration SHALL produce the same metric, score, evidence, and sensitivity outputs." | §3.3 |
| LREQ-ID-040 | Integration completion (matrix: primary Chunk 6A, completion Chunks 6A, 10) | "A preflight below the minimum success rate or above the maximum conflict rate SHALL stop bulk enrichment and mark the run failed. The failure SHALL include sampled counts, mismatch counts, endpoint signature, mapping-rule version, and a redacted diagnostic summary. Successful preflight responses SHALL be reused as the corresponding enrichment observations and SHALL count toward the one-enrichment-per-unique-identity limit." Plus: "When `unique preflight identities attempted = 0`, both rates SHALL be null, the preflight SHALL be `insufficient`, and bulk enrichment SHALL not start. This is a preflight evidence shortfall, not a zero-success result." | §4.4 |
| LREQ-NFR-020 | Integration completion (matrix: primary Chunk 6B, completion Chunk 10) | "Before bulk enrichment, log discovered canonical assets, sampled assets, unique enrichment identities, and projected minimum enrichment time." | §11 |
| LREQ-NFR-030 | Primary implementation (matrix: primary Chunk 10, completion Chunk 10) | "A failed page or sampled asset SHALL not abort unrelated categories or assets; the failure SHALL remain visible in status and evidence fields." | §11 |
| LREQ-EXT-090 | Integration completion (matrix: primary Chunk 3, supporting Chunks 1, 2, completion Chunk 10) | "A failed page, unverified filter, category mismatch, or material identity incompleteness SHALL generate a warning and SHALL prevent a fully rankable competition result for that category." | §4.1 |
| LREQ-NRM-020 | Integration completion (matrix: primary Chunk 8, supporting Chunk 2, completion Chunk 10) | "`reference_size = category_count - 1`. Field-specific usable reference counts SHALL be stored separately. `STRONG_REFERENCE_CATEGORY_COUNT = 21` is an operational run-size threshold: a run with 21 categories qualifies for the strong-reference policy and has 20 leave-one-out peers for each target. The stored `reference_size` remains 20 for that run; the threshold SHALL not be misreported as 21 peers." | §8.1 |
| LREQ-EVD-020 | Integration completion (matrix: primary Chunk 9A, completion Chunk 10) — orchestration-status half | "A category is `not_rankable` when any of the following applies: discovery filtering is unverified; any unresolved or conflicting discovery identity remains in the category; required demand data is unavailable; recent-supply minimum evidence is not met; quality is unavailable under the required-component policy; page-view semantics are contradicted for a page-view-dependent score; no valid leave-one-out reference exists; identity preflight fails; or an unrecoverable data-integrity error occurs. Material discovery failure or unbounded breadth also makes competition non-rankable. … The implementation SHALL first construct a fixed `base_rankable_candidates` set. … Sensitivity SHALL not be used to construct this set." | §9.1 |
| LREQ-SEN-020 | Integration completion (matrix: primary Chunk 9B, completion Chunk 10) | "Report top-three membership stability, top-five membership stability, each category's rank under each policy, maximum rank displacement, and maximum score displacement. The persisted field names SHALL include `top_3_stability`, `top_5_stability`, `maximum_score_delta`, `maximum_rank_displacement`, and `sensitivity_warning`." Plus: "The same diagnostics SHALL be stored in `ranking_sensitivity_json` with each policy's scores and ranks." | §9.3 |
| LREQ-CLI-010 | Supporting orchestration behavior (matrix: primary Chunk 12, supporting Chunks 6A, 6B, 8, 10, 11) | "The primary command SHALL be equivalent to: `niche-scout run --categories config/categories.json --config config/default.toml`. It SHALL run one pipeline and exit non-zero on unrecoverable errors." | §10 |
| LREQ-CLI-040 | Supporting orchestration behavior (matrix: primary Chunk 12, supporting Chunks 1, 8, 9A, 10) | "The pipeline SHALL reject a run with fewer than `MIN_CATEGORIES_PER_RUN` requested categories before producing a ranking. It SHALL retain a completed run's collection timestamp and explicit limitations in the report." | §10 |

Derived behavior this chunk implements without a new LREQ (from the chunk's own
gate and §6 clarifications, recorded here so the tests can name a source):
`RunRecord.taxonomy_sha256` must be a real, non-empty taxonomy hash
(dependency-map §7, "Owner: **Chunk 10**"); run-level status and category
limitations remain distinct fields (§6.1, §6.5, AGENTS.md hard rule 7);
8–20-category runs are provisional with an empty candidate set and null stability
(§6.2, §6.3, AGENTS.md hard rule 10); the runtime order is
`discover → persist → canonicalize → sample → preflight → enrich → cutoff →
metrics → normalize → score → base candidates → sensitivity → final
evidence/rankability → persist results → report` (§6.4, SRS §3.2).

## 4. Interface contracts consumed

Copied from the frozen interface files (not re-derived from source). Only the
names this chunk calls are quoted.

**Chunk 0 — `models.py`, `config.py` (interfaces/chunk-00.md §2, §3, §4, §5):**

```python
class RunStatus(str, Enum):            # running | completed | failed
class DiscoveryStatus(str, Enum):      # complete | truncated | page_failed | filter_unverified
                                       # | category_mismatch | identity_incomplete | request_failed
class CategoryStatus(str, Enum):       # healthy | degraded | failed  (internal orchestration state)
class ScoreState(str, Enum):           # available | partial | unavailable
class EvidenceGrade(str, Enum):        # strong | moderate | weak | insufficient
class RankabilityStatus(str, Enum):    # not_rankable | provisional | rankable

MIN_CATEGORIES_PER_RUN = 8
STRONG_REFERENCE_CATEGORY_COUNT = 21

@dataclass(frozen=True)
class RunRecord(_UtcRecord):
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

@dataclass(frozen=True)
class CategoryScoreRecord(_UtcRecord):   # 50 fields; the ones this chunk writes:
    run_id: str; category: str; discovery_status: str
    discovery_filter_verified: bool
    discovery_unresolved_identity_count: int; discovery_conflict_count: int
    discovery_duplicate_count: int; discovered_population_count: int
    enriched_sample_count: int; sample_is_census: bool; sampling_basis: str
    sample_fraction: float | None; unique_enrichment_count: int
    overlap_category_count: int; overlap_sample_percentage: float | None
    usable_demand_sample_count: int; usable_recent_supply_sample_count: int
    usable_quality_sample_count: int
    breadth_source: str; breadth_completeness_status: str
    discovery_bounded_by_verified_total: bool
    demand_stratum_eligibility_coverage: float
    recent_supply_stratum_eligibility_coverage: float
    quality_stratum_eligibility_coverage: float
    demand_per_asset_raw: float | None; demand_median_raw: float | None
    breadth_raw: float | None; recent_share_raw: float | None
    median_age_raw: float | None; quality_raw: float | None
    stratum_statistics_json: str
    component_d: float | None; component_c: float | None
    component_r: float | None; component_q: float | None
    market_opportunity_score: float | None; score_state: str
    evidence_grade: str; rankability_status: str
    missing_components_json: str; warnings_json: str
    reference_size: int; reference_usable_counts_json: str
    top_3_stability: float | None; top_5_stability: float | None
    maximum_score_delta: float | None; maximum_rank_displacement: int | None
    sensitivity_warning: bool | None; ranking_sensitivity_json: str
    computed_at_utc: datetime

# config.py
@dataclass(frozen=True)
class NicheScoutConfig: ...            # 16 typed fields + source: str
    def policy_versions(self) -> dict[str, str]: ...
def load_config(cli_args=None, toml_path=None) -> NicheScoutConfig: ...
def read_categories(categories_path: Path) -> Sequence[str]: ...
def get_credentials(environ=None) -> Credentials: ...
def ensure_utc(value: datetime) -> datetime: ...
```

**Chunk 1 — `validation.py` (interfaces/chunk-01.md §4):**

```python
def validate_taxonomy(payload, *, requested_categories: Sequence[str],
    reference_utc: datetime, max_taxonomy_age_days: int = MAX_TAXONOMY_AGE_DAYS
) -> TaxonomyValidationResult: ...
def taxonomy_path_set(payload: object) -> frozenset[str]: ...
def summarize_validation_issues(issues, *, max_context_chars: int = 256) -> str: ...
```

`TaxonomyValidationResult` carries `is_valid`, `is_fresh: bool | None`, `status`,
`missing_header_fields`, `missing_requested_categories`, `age_days_exact:
float | None`, `payload`, `issues`.

**Chunk 2 — `database.py` (interfaces/chunk-02.md §2.3–§2.8):**

```python
def update_run_status(self, run_id: str, status: str,
                      completed_at_utc: datetime | None = None) -> None: ...
def update_run_preflight(self, run_id: str, *, identity_preflight_status=None,
    identity_preflight_summary_json=None,
    graphql_operation_correlation_mode=None,
    page_view_semantics_status=None) -> None: ...
def set_category_status(self, run_id: str, category: str, discovery_status: str,
    *, computed_at_utc: datetime) -> None: ...
def upsert_category_scores(self, scores: Sequence[CategoryScoreRecord]) -> int: ...
def get_run(self, run_id: str) -> RunRecord | None: ...
def get_enrichment_observation(self, run_id: str, asset_identity_key: str
    ) -> EnrichmentObservationRecord | None: ...
def get_category_scores(self, run_id: str) -> Sequence[CategoryScoreRecord]: ...
def count_discovery_observations(self, run_id: str) -> int: ...
def count_sample_members(self, run_id: str) -> int: ...
def count_distinct_enrichment_identities(self, run_id: str) -> int: ...
class SqliteRepository:
    def transaction(self) -> Iterator["SqliteRepository"]: ...
    def category_transaction(self, run_id: str, category: str
        ) -> Iterator["SqliteRepository"]: ...
```
`update_run_status` raises `KeyError` for an unknown `run_id`, accepts only
`running`/`completed`/`failed`, and `completed_at_utc=None` leaves the stored
value unchanged. `set_category_status` **creates** the `(run_id, category)` row
on first write and requires `computed_at_utc`.

**Chunk 3 — `collector_coveo.py` (interfaces/chunk-03.md §4, §5):**

```python
def load_coveo_search_template(template_path=COVEO_TEMPLATE_PATH
    ) -> Mapping[str, object]: ...     # returns provenance header + `request_body`
def discover_category(category: str, taxonomy_payload: object, *,
    config: NicheScoutConfig, credentials: Credentials, reference_utc: datetime,
    sink: CoveoObservationSink, transport: CoveoTransport,
    sleeper: Callable[[float], None] = time.sleep, clock: Callable[[], datetime] = ...,
    run_id: str, template_path=COVEO_TEMPLATE_PATH,
    rate_limiter: CoveoRateLimiter | None = None,
    shared_limiter: CoveoRateLimiter | None = None) -> CategoryDiscoveryResult: ...
class CoveoObservationSink:
    def __init__(self, repository: SqliteRepository, run_id: str, category: str, *,
        clock=None, taxonomy: object = None, batch_size: int = 500) -> None: ...
class CoveoTransport(Protocol):
    def send(self, url: str, headers: Mapping[str, str], payload: bytes) -> Any: ...
```
`CategoryDiscoveryResult` carries `discovery_status`, `ordinal_start`,
`ordinal_end`, `observations_emitted`, `canonical_identity_count`,
`unresolved_identity_count`, `conflict_identity_count`,
`duplicate_observation_count`, `pages_fetched`, `total_count`,
`api_reported_count`, `filter_status`, `conditions`, `issues`. A per-category
failure is returned as this result and never propagates.

**Chunk 4A — `sampling.py` (interfaces/chunk-4A.md §5.2–§5.4):**

```python
def build_canonical_population(records: Sequence[DiscoveryPopulationRecord], *,
    category: str) -> CanonicalPopulation: ...
def select_run_sample(categories: Mapping[str, Sequence[DiscoveryPopulationRecord]], *,
    run_id: str, sampling_rule_version: str = SAMPLING_RULE_VERSION
) -> RunSamplingResult: ...
@dataclass(frozen=True, slots=True)
class DiscoveryPopulationRecord: discovery_ordinal: int
    asset_identity_key: str | None; is_duplicate: bool = False
```
`select_run_sample` preserves the caller mapping's insertion order; the caller
(Chunk 10) decides the declared category order.

**Chunk 4B — `database.py` (interfaces/chunk-4B.md §5.3):**

```python
def persist_run_sampling(repository: SqliteRepository, run: RunSamplingResult, *,
    computed_at_utc: datetime) -> SamplingPersistenceReport: ...
def verify_persisted_sampling(repository: SqliteRepository, run: RunSamplingResult
    ) -> SamplingPersistenceReport: ...
def upsert_sampling_summary(self, run_id: str, category: str, *, ...,
    discovery_status: str | None = None) -> None: ...
```

**Chunk 5 — `collector_graphql.py` (interfaces/chunk-05.md §5.11):**

```python
GraphQLTransport = Callable[[GraphQLBatchRequest, Mapping[str, str]], GraphQLBatchResponse]
@dataclass(frozen=True, slots=True)
class GraphQLRetryPolicy:
    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    backoff_base_seconds: float = DEFAULT_BACKOFF_BASE_SECONDS
    backoff_multiplier: float = DEFAULT_BACKOFF_MULTIPLIER
    backoff_max_seconds: float = DEFAULT_BACKOFF_MAX_SECONDS
    min_request_interval_seconds: float = DEFAULT_MIN_REQUEST_INTERVAL_SECONDS
def enrich_asset(asset_identity_key: str, *, credentials: Credentials,
    transport: GraphQLTransport, correlation_mode: GraphQLOperationCorrelationMode,
    retrieved_at_utc: datetime, policy: GraphQLRetryPolicy = GraphQLRetryPolicy(),
    endpoint: str = GRAPHQL_BATCH_ENDPOINT,
    sleep: Callable[[float], None] = ...) -> tuple[EnrichmentResult, EnrichmentObservationDraft]: ...
```

**Chunk 6A / 6B — `pipeline.py` (interfaces/chunk-6A.md §5.3–§5.4;
interfaces/chunk-6B.md §5.1–§5.5). These already exist and Chunk 10 consumes
them unchanged:**

```python
def preflight_policy_from_config(config: NicheScoutConfig) -> PreflightPolicy: ...
def run_identity_preflight(repository: SqliteRepository, run: RunSamplingResult, *,
    credentials: Credentials, transport: GraphQLTransport,
    correlation_mode: GraphQLOperationCorrelationMode, retrieved_at_utc: datetime,
    policy: PreflightPolicy, endpoint: str = GRAPHQL_BATCH_ENDPOINT,
    retry_policy: GraphQLRetryPolicy = GraphQLRetryPolicy(),
    sleep: Callable[[float], None] = time.sleep) -> IdentityPreflightOutcome: ...
def compute_enrichment_union(run: RunSamplingResult, *,
    already_enriched_keys: AbstractSet[str]) -> EnrichmentUnion: ...
def build_enrichment_projection(union: EnrichmentUnion, *,
    discovered_canonical_assets: int, sampled_assets: int,
    per_request_interval_seconds: float) -> EnrichmentProjection: ...
def log_enrichment_projection(projection: EnrichmentProjection) -> None: ...
def enrich_unique_identities(repository: SqliteRepository, run: RunSamplingResult, *,
    preflight_status: str, credentials: Credentials, transport: GraphQLTransport,
    correlation_mode: GraphQLOperationCorrelationMode, retrieved_at_utc: datetime,
    union: EnrichmentUnion, projection: EnrichmentProjection,
    endpoint: str = GRAPHQL_BATCH_ENDPOINT,
    retry_policy: GraphQLRetryPolicy = GraphQLRetryPolicy(),
    sleep: Callable[[float], None] = time.sleep) -> EnrichmentExecutionReport: ...
def capture_scoring_cutoff_utc(now_utc: datetime) -> datetime: ...
def finalize_enrichment(repository: SqliteRepository, run: RunSamplingResult, *,
    scoring_cutoff_utc: datetime, computed_at_utc: datetime,
    page_view_semantics_status: PageViewSemanticsStatus,
    union: EnrichmentUnion) -> FinalizationReport: ...
def assert_finalization_consistency(repository: SqliteRepository,
    run: RunSamplingResult, finalization: FinalizationReport, *,
    scoring_cutoff_utc: datetime,
    page_view_semantics_status: PageViewSemanticsStatus) -> tuple[str, ...]: ...
```
`run_identity_preflight` already owns the `failed` transition
(`repository.update_run_status(run_id, RunStatus.FAILED.value)` with
`completed_at_utc` omitted). Chunk 6A interface §5.7 binds Chunk 10: "SHALL NOT
overwrite an existing `failed` with `completed`, and SHALL leave `insufficient`
runs non-completed."

**Chunk 7A / 7B — `metrics.py` (interfaces/chunk-7A.md §4;
interfaces/chunk-7B.md §3, §4):**

```python
@dataclass(frozen=True, slots=True)
class MetricObservation:
    product_page_views: object; first_published_date_utc: object; state: str | None
    id_mapping_mismatch: bool; rating_average: object; rating_count: object
    product_detail_status: OperationStatus; page_views_status: OperationStatus
@dataclass(frozen=True, slots=True)
class StratumMetricInput:
    stratum_index: int; discovered_population_count: int
    sampled_population_count: int; observations: tuple[MetricObservation, ...]
@dataclass(frozen=True, slots=True)
class CategoryMetricInput:
    category: str; scoring_cutoff_utc: datetime
    page_view_semantics_status: PageViewSemanticsStatus
    strata: tuple[StratumMetricInput, ...]
    min_usable_samples_per_stratum: int = MIN_USABLE_SAMPLES_PER_STRATUM
    min_age_days_for_rate: int = MIN_AGE_DAYS_FOR_RATE
    recent_window_days: int = RECENT_WINDOW_DAYS
    quality_min_rating_count: int = QUALITY_MIN_RATING_COUNT  # INERT
    quality_min_eligible_assets: int = QUALITY_MIN_ELIGIBLE_ASSETS
    min_required_component_coverage: float = MIN_REQUIRED_COMPONENT_COVERAGE
@dataclass(frozen=True, slots=True)
class BreadthMetricInput:
    verified_total_count: int | None; distinct_canonical_discovered_count: int
@dataclass(frozen=True, slots=True)
class CategoryRawMetrics:
    category: str; raw: RawMetricBundle
    demand_stratum_eligibility_coverage: float
    recent_supply_stratum_eligibility_coverage: float
    quality_stratum_eligibility_coverage: float
    usable_demand_sample_count: int; usable_recent_supply_sample_count: int
    usable_quality_sample_count: int
    breadth_source: BreadthSource; breadth_completeness_status: BreadthCompletenessStatus
def compute_category_raw_metrics(input: CategoryMetricInput,
    breadth_input: BreadthMetricInput) -> CategoryRawMetrics: ...
```

**Chunk 8 / 9A / 9B — `scoring.py` (interfaces/chunk-08.md §2–§3;
chunk-9A.md §2–§3; chunk-9B.md §2–§3):**

```python
def score_category(target: CategoryRawMetrics, all_metrics: Sequence[CategoryRawMetrics], *,
    page_view_semantics_status: PageViewSemanticsStatus) -> ScoreResult: ...
def leave_one_out_reference(all_metrics: Sequence[CategoryRawMetrics],
    target_category: str) -> LeaveOneOutReference: ...
def build_base_rankable_candidates(all_metrics: Sequence[CategoryRawMetrics],
    inputs: Sequence[PreSensitivityCategoryInput], scores: Sequence[ScoreResult], *,
    identity_preflight_status: IdentityPreflightStatus,
    min_required_component_coverage: float = MIN_REQUIRED_COMPONENT_COVERAGE
) -> BaseCandidateSet: ...
def evaluate_pre_sensitivity_evidence(score: ScoreResult,
    evidence: PreSensitivityCategoryInput, *,
    identity_preflight_status: IdentityPreflightStatus, run_category_count: int,
    min_required_component_coverage: float = MIN_REQUIRED_COMPONENT_COVERAGE
) -> PreSensitivityDecision: ...
def evaluate_sensitivity(base_candidates: BaseCandidateSet,
    all_metrics: Sequence[CategoryRawMetrics], scores: Sequence[ScoreResult], *,
    reference_set_size: int,
    min_required_component_coverage: float = MIN_REQUIRED_COMPONENT_COVERAGE
) -> SensitivityDiagnostics: ...
def final_evidence_grade(evidence: PreSensitivityCategoryInput,
    sample: SampleEvidenceFacts, decision: PreSensitivityDecision, *,
    run_category_count: int, sensitivity_warning: bool | None,
    min_required_component_coverage: float = MIN_REQUIRED_COMPONENT_COVERAGE,
    strong_component_coverage: float = STRONG_COMPONENT_COVERAGE) -> EvidenceGrade: ...
def final_rankability_status(decision: PreSensitivityDecision, *,
    sensitivity_warning: bool | None) -> RankabilityStatus: ...
@dataclass(frozen=True, slots=True)
class SampleEvidenceFacts:
    category: str; sample_is_census: bool; discovered_population_count: int
    usable_demand_sample_count: int; usable_recent_supply_sample_count: int
    usable_quality_sample_count: int
```
Caller obligations this chunk must satisfy: `all_metrics` is in the caller's
deterministic canonical category order and `inputs`/`scores` are 1:1 aligned with
it (9A §4.7); `reference_set_size == base_candidates.run_category_count - 1`
(9B §4.2); `PreSensitivityCategoryInput` is the frozen 14-field 9A structure.

## 5. Interface contract this chunk produces

This section becomes `Documents/interfaces/chunk-10.md` verbatim once the lead
freezes it. All names are additive to `src/niche_scout/pipeline.py` except the
one `database.py` validation hardening in §5.5. Nothing in Chunk
0/1/2/3/4A/4B/5/6A/6B/7A/7B/8/9A/9B is redefined or shadowed.

### 5.0 Module and boundary rules

| Item | Kind | Rule |
|---|---|---|
| `src/niche_scout/pipeline.py` | **I/O/orchestration** | Run sequencing, transaction boundaries, status transitions, and the run-level outcome value. No clock read: every timestamp is caller-supplied through an injected `clock`. No protocol behavior; it calls the chunk adapters. |
| `src/niche_scout/database.py` | **I/O** | One additional structural validation (non-empty `taxonomy_sha256`), no schema change. |

### 5.1 Public entry point

```python
@dataclass(frozen=True, slots=True)
class PipelineResult:
    """The run outcome returned to the caller (Chunk 12 maps it to an exit code)."""
    run_id: str
    status: str                       # RunStatus value: completed | failed
    scoring_cutoff_utc: datetime | None
    categories: tuple[str, ...]       # requested categories, declared order
    identity_preflight_status: str    # IdentityPreflightStatus value
    category_scores_written: int
    limitations: tuple[str, ...]      # redacted; names category and field only
    @property
    def succeeded(self) -> bool: ...  # True iff status == RunStatus.COMPLETED.value

def run_pipeline(
    *,
    config: NicheScoutConfig,
    categories: Sequence[str],
    credentials: Credentials,
    repository: SqliteRepository,
    clock: Callable[[], datetime],
    coveo_transport: CoveoTransport,
    graphql_transport: GraphQLTransport,
    sleeper: Callable[[float], None] = time.sleep,
    run_id: str | None = None,
    taxonomy_path: Path | None = None,
    template_path: "Path | str" = COVEO_TEMPLATE_PATH,
    correlation_mode: GraphQLOperationCorrelationMode = GraphQLOperationCorrelationMode.EXPLICIT_KEY,
    preflight_policy: PreflightPolicy | None = None,
    retry_policy: GraphQLRetryPolicy = GraphQLRetryPolicy(),
    taxonomy_sha256: str | None = None,
) -> PipelineResult:
    """Execute one complete run in the SRS-prescribed order (Chunk 10).

    Sequence (dependency-map Chunk 10 "Implement this sequence", SRS §3.2):
      1. Requested categories are the caller-supplied ``categories`` in declared
         order; an empty or duplicate-bearing sequence raises ``ValueError``.
      2. Configuration and taxonomy are validated **before any network request**.
         ``run_pipeline`` reads the taxonomy file at ``taxonomy_path`` (default
         ``config.taxonomy_path``), calls ``validation.validate_taxonomy`` with
         ``reference_utc=clock()``, and raises ``TaxonomyInvalidError`` when the
         payload is invalid, stale, or missing a requested category. No transport
         is touched before this call returns valid.
      3. ``RunRecord`` is created with ``run_id`` (caller-supplied or derived from
         ``clock()`` + a caller-supplied suffix), ``run_started_at_utc=clock()``,
         the three policy versions from ``config.policy_versions()``, a
         ``categories_json`` carrying the declared order, a
         ``config_snapshot_json`` serialization, a ``config_sha256`` over that
         snapshot, and a **non-empty** ``taxonomy_sha256`` (§5.5).
         ``identity_preflight_summary_json`` is seeded with the frozen key set
         (interfaces/chunk-6A.md §5.5) carrying ``status = "insufficient"`` and
         zero counts, because the column is ``TEXT NOT NULL``.
      4. Each category is discovered through ``discover_category`` inside one
         ``category_transaction(run_id, category)``; a per-category failure is
         recorded as its ``DiscoveryStatus`` (via ``set_category_status``) and
         never aborts another category (LREQ-NFR-030).
      5. Raw observations are persisted by the Chunk 3 sink inside the same
         category transaction, and are committed before canonicalization.
      6. Canonical populations are built from the persisted observations
         (``sampling.build_canonical_population`` inputs).
      7. ``sampling.select_run_sample`` selects the deterministic samples; the
         Chunk 4B ``persist_run_sampling`` materializes them with
         ``computed_at_utc=clock()``.
      8. ``run_identity_preflight`` runs the gate and persists its artifacts
         **before** returning.
      9. If the gate is ``passed``: the union is computed via
         ``compute_enrichment_union``, the projection via
         ``build_enrichment_projection`` with
         ``per_request_interval_seconds=retry_policy.min_request_interval_seconds``,
         ``log_enrichment_projection`` is called **before** the first request
         (LREQ-NFR-020), and ``enrich_unique_identities`` executes.
      10. ``capture_scoring_cutoff_utc(clock())`` is called exactly once, **after**
          enrichment and before metric computation, and the single value is passed
          to every pure function and to ``finalize_enrichment`` (LREQ-ARCH-020,
          dependency-map gate: "The scoring cutoff is captured once and passed into
          pure functions"). The same captured value is persisted exactly once with
          ``repository.update_run_scoring_cutoff(run_id, captured)`` (§5.8), so the
          SRS §6.1 required ``runs.scoring_cutoff_utc`` column is non-null on a run
          that reached this step.
      11. ``finalize_enrichment`` finalizes the authoritative per-stratum usable
          counts from the same persisted observations the metrics will read.
      12. Metrics: for each category, a ``CategoryMetricInput`` is built from the
          persisted sample members and enrichment observations and passed to
          ``metrics.compute_category_raw_metrics`` with a ``BreadthMetricInput``.
      13. LOO references and scores: ``scoring.score_category`` for each category,
          with ``all_metrics`` in the declared category order.
      14. Base candidates: ``scoring.build_base_rankable_candidates`` fixes
          ``base_rankable_candidates``.
      15. Sensitivity: ``scoring.evaluate_sensitivity`` over the fixed set only;
          it never adds or removes a candidate and never mutates a balanced score.
      16. Final evidence and rankability: ``final_evidence_grade`` and
          ``final_rankability_status`` per category from the sensitivity result.
      17. Persistence: one ``upsert_category_scores`` write per run carrying the
          full ``CategoryScoreRecord`` (discovery/sampling columns carried forward,
          scoring-phase columns written), inside one ``repository.transaction()``.
      18. Run status: ``update_run_status(run_id, RunStatus.COMPLETED.value,
          completed_at_utc=clock())`` on success.

    Return value: a ``PipelineResult``. ``run_pipeline`` never calls
    ``sys.exit``; the caller (Chunk 12) owns the exit code.

    Null/edge behaviour:
      - A ``configuration`` or ``taxonomy`` failure raises
        ``PipelineConfigurationError`` / ``TaxonomyInvalidError`` **before** any
        transport call. Nothing is persisted except, for a taxonomy failure after
        step 3, no run row either (validation is step 2, before step 3).
      - A failed preflight does **not** raise: it returns
        ``PipelineResult(status=RunStatus.FAILED.value, scoring_cutoff_utc=None,
        category_scores_written=<rows persisted>, limitations=<...>)`` after
        persisting per-category limitation rows where possible.
      - A preflight status of ``insufficient`` is not ``completed``; the run is
        left non-completed (interfaces/chunk-6A.md §5.7).
      - An existing ``failed`` run status is never overwritten with ``completed``.
      - ``clock`` is called at most once per distinct timestamp it must produce;
        the pipeline never reads ``datetime.now`` itself.
    """
```

### 5.2 `run_pipeline` step partition and transaction boundaries

| Step | Owner | Transaction boundary |
|---|---|---|
| 1–3 input/config/taxonomy/run row | Chunk 10 | `insert_run` is one implicit unit; no network before this point |
| 4–5 discovery + raw persistence | Chunk 10 drives, Chunk 3 persists | one `category_transaction(run_id, category)` per category |
| 6–7 canonicalize + sample + persist | Chunk 10 drives, 4A pure, 4B persists | one `repository.transaction()` per persist pass |
| 8 preflight | Chunk 6A | 6A's own single transaction including the `failed` transition |
| 9 union / projection / log / enrich | Chunk 6B | 6B's own transaction around the enrichment loop |
| 10 cutoff capture + persist | Chunk 6B helper, called by Chunk 10; Chunk 10 writes | one single-statement `update_run_scoring_cutoff` UPDATE (no wider transaction) |
| 11 finalization | Chunk 6B | 6B's own write transaction |
| 12–16 metrics / score / candidates / sensitivity / evidence | Chunk 10 drives, 7A/7B/8/9A/9B pure | none (no writes) |
| 17 category-score persistence | Chunk 10 | one `repository.transaction()` |
| 18 run status | Chunk 10 | compatible with 17; may share the transaction |

### 5.3 `PipelineResult` invariants

- ``succeeded`` is `True` iff `status == RunStatus.COMPLETED.value`.
- `scoring_cutoff_utc is None` iff the run did not reach step 10 (preflight
  failure or an aborted run).
- `limitations` is a tuple of redacted strings naming a category and a field
  only; it never contains an identity string, a header value, a token, or a
  response body (LREQ-SEC-010/020). It is empty only when no limitation was
  recorded.
- `category_scores_written` is the number of `(run_id, category)` rows the final
  persistence pass wrote; it is a count, never a fabricated `0` standing in for
  a failed write.

### 5.4 Diagnostics this chunk surfaces

```python
class PipelineError(RuntimeError): ...              # base for run-level aborts
class PipelineConfigurationError(PipelineError): ...  # invalid/missing config
class TaxonomyInvalidError(PipelineError): ...        # invalid/stale/incomplete taxonomy
def taxonomy_sha256_for(payload: object) -> str: ...
    """Return the lowercase-hex SHA-256 over the canonical form of the taxonomy
    payload. Raises ValueError for a payload that yields an empty digest input.
    Pure: no I/O, no clock."""
```

`taxonomy_sha256_for` is the single definition of the run's taxonomy provenance
hash. Its canonical form is `json.dumps(payload, sort_keys=True,
separators=(",", ":"), ensure_ascii=False).encode("utf-8")` — the same canonical
JSON convention Chunk 3 uses for `template_sha256` — and it returns a 64-character
lowercase hex string. It is reused by the tests as the golden derivation, so the
value is not a literal.

### 5.5 `runs.taxonomy_sha256` non-empty enforcement (additive to `database.py`)

Dependency-map §7 assigns this unmet obligation to Chunk 10: "`RunRecord`
validation covers only the UTC fields and the persistence layer rejects only
`None`, not `""`, so an empty taxonomy hash would persist silently". The fix is
two-part and is additive (no schema change, no new column, no altered DDL):

1. **`pipeline.py`** never constructs an empty hash: `taxonomy_sha256_for`
   returns a 64-char digest, and `run_pipeline` raises
   `PipelineConfigurationError` rather than inserting an empty value. A
   caller-supplied `taxonomy_sha256` is accepted only when
   `str.strip()` is non-empty and it is a `str`; otherwise `ValueError`.
2. **`database.py`** gains one structural guard on the `runs` write path: a
   non-empty-string required column whose supplied value is a `str` consisting
   only of whitespace is rejected with `InvalidRecordValueError`, naming the
   table and column only. The guard is scoped to the `runs` table's
   non-nullable text columns that are provenance/identity strings
   (`taxonomy_sha256`, `taxonomy_version`, `endpoint_contract_version`,
   `identity_mapping_rule_version`, `sampling_rule_version`), so it can never
   turn an ordinary nullable text value into an error. `None` remains the
   existing `_validate_required_columns` case; the new guard adds only the
   empty/whitespace case.

The guard lives with the other column validators (`_validate_required_columns`
and `_encode_column`), so the `runs` insert path rejects the empty value before
it reaches SQLite.

### 5.6 Frozen persisted JSON shapes for `warnings_json` and `missing_components_json`

No Chunk 11 interface exists yet, so Chunk 10 freezes both shapes here (§12 item
8); Chunk 11 consumes them read-only and SHALL NOT redefine them. This is the
produced-interface record for both columns.

```python
#: Emission order for the missing-component list. A missing-component vector must
#: always be emitted in exactly this order so two equal component sets serialize
#: equal. Re-exported from scoring (interfaces/chunk-08.md §2), never re-declared.
COMPONENT_WEIGHT_KEYS: tuple[str, ...] = ("D", "C", "R", "Q")
```

- `warnings_json` is `json.dumps(sorted(set(codes)), separators=(",", ":"))` —
  a JSON array of unique warning codes in ascending lexical order. `codes`
  contains `models.WarningCode` values plus the preflight/limitation codes this
  chunk observes. Set-then-sort makes the payload independent of iteration order
  (LREQ-ARCH-030). An empty `codes` serializes to `"[]"`.
- `missing_components_json` is `json.dumps([k for k in COMPONENT_WEIGHT_KEYS if
  component_is_none(k)], separators=(",", ":"))` — a JSON array of component keys
  whose value is `None`, in the fixed `("D", "C", "R", "Q")` order. All four
  available serializes to `"[]"`; all four missing serializes to
  `["D","C","R","Q"]`.
- Neither payload contains a credential, header value, cookie, response body,
  identity string, or category path (LREQ-SEC-010/020): the codes are vocabulary
  tokens and the component keys are the four fixed weight keys.

### 5.7 Internal `CategoryStatus` roll-up (plan-level, §12 item 7)

```python
def category_status_for(
    discovery_status: str,
    *,
    warnings: Sequence[str],
    evidence_grade: str,
    rankability_status: str,
) -> CategoryStatus:
    """Roll up already-final category fields into the internal ``CategoryStatus``.

    Pure: no I/O, no clock. ``CategoryStatus`` is a *derived view* over fields
    that are already final — it is never an input to evidence or rankability
    (those are steps 15–16, Chunks 9A/9B). Rule (plan-level, §12 item 7):
      - ``page_failed`` or ``request_failed`` -> ``CategoryStatus.FAILED``;
      - ``truncated``, ``filter_unverified``, ``category_mismatch``, or
        ``identity_incomplete`` -> ``CategoryStatus.DEGRADED``;
      - otherwise -> ``CategoryStatus.HEALTHY``.
    ``warnings``, ``evidence_grade``, and ``rankability_status`` are carried as
    the already-final fields the roll-up reads; the helper derives nothing from
    them. The value is internal orchestration state: it is never persisted as a
column and is never surfaced as a discovery status, score state, evidence
    grade, or rankability status (interfaces/chunk-00.md §2; dependency-map
    §6.5).
  ```

### 5.8 `runs.scoring_cutoff_utc` persistence (additive to `database.py`)

SRS §6.1 lists ``scoring_cutoff_utc`` as a required ``runs`` field, and Chunk 10 is
the only chunk that writes a run row. The column is nullable by DDL
(``database.py`` line 90) and is ``None`` at ``insert_run`` time because the cutoff
is captured after enrichment. No existing writer
(``insert_run`` / ``update_run_status`` / ``update_run_preflight``) sets it, so
Chunk 10 adds exactly one method, additive and schema-free:

```python
def update_run_scoring_cutoff(
    self, run_id: str, scoring_cutoff_utc: datetime
) -> None:
    """Set ``runs.scoring_cutoff_utc`` to the single captured cutoff value.

    Mirrors ``update_run_status``: ``_check_open()``; encode the column with the
    aware-UTC contract (``_encode_column``); a single
    ``UPDATE runs SET scoring_cutoff_utc = ? WHERE run_id = ?``; ``KeyError``
    when no row matches. The caller passes the exact value
    ``capture_scoring_cutoff_utc`` returned; this method never reads a clock and
    never re-derives a timestamp.
    """
```

Call site and transaction boundary: ``run_pipeline`` calls it once, immediately
after step 10's capture, as a single-statement write (no wider transaction is
needed because one UPDATE is atomic). On a completed run the persisted value
equals ``PipelineResult.scoring_cutoff_utc``; a run that never reaches step 10
(preflight failure, or an abort before enrichment) leaves the column ``None``.

## 6. Files touched

| File | New/modified | Purpose |
|---|---|---|
| `src/niche_scout/pipeline.py` | Modified (additive) | Chunk 10 entry point, `PipelineResult`, error types, `taxonomy_sha256_for`, run sequencing and status transitions. Existing 6A/6B names unchanged. |
| `src/niche_scout/database.py` | Modified (additive) | (a) Non-empty-string guard for `runs` provenance columns (§5.5, item 2). (b) The `update_run_scoring_cutoff` writer for the SRS §6.1 required `runs.scoring_cutoff_utc` column (§5.8). Both are additive and schema-free. Authorized here because dependency-map §7 assigns the unmet `runs.taxonomy_sha256` obligation to Chunk 10, Chunk 10 is the only chunk that constructs and completes a `RunRecord`, and no other chunk's plan can authorize this file. |
| `tests/test_pipeline.py` | New | All §9 pipeline tests: failure isolation, preflight-failure path, run-size rejection, cutoff-once, NFR-020 logging, determinism, empty-hash rejection, end-to-end fixture path. |
| `tests/test_database.py` | Modified (additive) | One test node for the `runs` empty/whitespace provenance rejection. Authorized alongside `database.py` for the obligation above. |
| `tests/traceability.json` | Modified | New node-ID → LREQ-ID entries for every §9 test. |
| `tests/fixtures/pipeline_fixtures.py` | New | In-memory Coveo/GraphQL transports, a fixed clock, taxonomy payloads, category sets, and the end-to-end scenario. |
| `tests/fixtures/__init__.py` | Modified (additive) | Re-export `pipeline_fixtures`. |
| `Documents/runs/chunk-10.md` | New | Run log (chunk-lead's pipeline artifact). |

Authorization note (§12 items 1–2): `database.py` and `tests/test_database.py` are
authorized by **this** frozen plan for the empty/whitespace `runs` provenance
guard only (§5.5, item 2). No other chunk's plan authorizes these files for the
Chunk 10 obligation.

No other source file is touched. `models.py`, `config.py`, `validation.py`,
`sampling.py`, `metrics.py`, `scoring.py`, `collector.py`, `collector_coveo.py`,
`collector_graphql.py`, `report.py`, and `cli.py` are not modified.

## 7. Task breakdown

Ordered checklist, each item tagged with the LREQ ID(s) it implements.

- [ ] Declare `PipelineError`, `PipelineConfigurationError`,
  `TaxonomyInvalidError`, `PipelineResult`, and `taxonomy_sha256_for` in
  `pipeline.py`; add them to `__all__` (LREQ-ARCH-030).
- [ ] Implement step 1–2: validate the requested-category sequence (non-empty,
  no duplicates, non-blank strings) and the taxonomy through
  `validation.validate_taxonomy` before any transport call
  (LREQ-CLI-040, LREQ-EXT-090).
- [ ] Implement step 3: build and insert the `RunRecord` with the three policy
  versions, the config snapshot/hash, a real `taxonomy_sha256`, and a seeded
  `identity_preflight_summary_json` (LREQ-ARCH-030, LREQ-NFR-020 provenance).
- [ ] Implement the `< MIN_CATEGORIES_PER_RUN` rejection before any ranking
  (LREQ-CLI-040). Rejection is a `PipelineConfigurationError`; the caller maps it
  to a non-zero exit (Chunk 12 boundary).
- [ ] Implement steps 4–5: drive `discover_category` per category, one
  `category_transaction` each, persisting `set_category_status` and raw
  observations; a failed category never aborts another (LREQ-NFR-030,
  LREQ-EXT-090).
- [ ] Implement steps 6–7: build canonical populations and call
  `select_run_sample` in declared category order, then
  `persist_run_sampling(..., computed_at_utc=clock())` (LREQ-ARCH-030).
- [ ] Implement step 8: call `run_identity_preflight`; consume
  `IdentityPreflightOutcome` (LREQ-ID-040).
- [ ] Implement the failed/insufficient preflight branch: no enrichment, no
  metrics/scores/ranking, retain discovery/sample/preflight rows, persist
  per-category limitation rows where possible, and return
  `PipelineResult(status=failed)` without overwriting any existing `failed`
  (LREQ-ID-040, LREQ-EVD-020, LREQ-EXT-090).
- [ ] Implement step 9 for a passed gate: union → projection → log → enrich with
  the injected transports (LREQ-NFR-020, LREQ-ID-040).
- [ ] Implement step 10: call `capture_scoring_cutoff_utc(clock())` once and pass
  the same value to `finalize_enrichment`, metrics, scoring, evidence, and
  persistence (LREQ-ARCH-030, dependency-map gate).
- [ ] Implement step 11: `finalize_enrichment` before metric calculation
  (LREQ-NRM-020).
- [ ] Implement step 12: build `CategoryMetricInput`/`BreadthMetricInput` from
  persisted rows and call `compute_category_raw_metrics`
  (LREQ-ARCH-030, LREQ-EXT-090's breadth signal).
- [ ] Implement step 13: `score_category` per category with `all_metrics` in
  declared order (LREQ-NRM-020).
- [ ] Implement step 14: `build_base_rankable_candidates` freezes the candidate
  set; 8–20-category runs produce an empty set (LREQ-EVD-020).
- [ ] Implement step 15: `evaluate_sensitivity` over the fixed set only
  (LREQ-SEN-020, LREQ-EVD-020).
- [ ] Implement step 16: `final_evidence_grade` and `final_rankability_status`
  per category (LREQ-EVD-020, LREQ-SEN-020).
- [ ] Implement step 17: one `upsert_category_scores` write of full
  `CategoryScoreRecord` rows, carrying forward discovery/sampling columns and
  writing scoring-phase columns (LREQ-ARCH-030, LREQ-NRM-020, LREQ-SEN-020).
- [ ] Implement step 18: `update_run_status(completed)` with
  `completed_at_utc=clock()`, never downgrading `failed` (LREQ-ARCH-030).
- [ ] Add the `database.py` non-empty provenance guard (§5.5 item 2)
  (`runs.taxonomy_sha256` obligation).
- [ ] Add `tests/fixtures/pipeline_fixtures.py` and re-export it
  (LREQ-ARCH-030).
- [ ] Add `tests/test_pipeline.py` and the `tests/test_database.py` node from §9,
  plus `tests/traceability.json` entries (LREQ-ARCH-030, LREQ-NFR-020,
  LREQ-NFR-030).
- [ ] Run `python -m pytest tests/test_pipeline.py tests/test_database.py -q`,
  the full suite, `python -m niche_scout.tools.check_import_boundaries`, and
  `python -m niche_scout.tools.validate_traceability`; report real output.

## 8. Edge cases and invariants

From the dependency map's edge-case column for every LREQ this chunk owns, plus
the chunk's own gate:

- **Failure isolation (`LREQ-NFR-030`):** a failed page or sampled asset must not
  abort unrelated categories or assets; the failure stays visible in status and
  evidence fields. One page or asset failure must not abort unrelated
  categories/assets.
- **Failed page is not zero assets:** a failed discovery page is a failure and is
  never interpreted as a zero-breadth category (`LREQ-EXT-050`/`EXT-090`).
- **Warning generation and competition not fully rankable (`LREQ-EXT-090`):** a
  failed page, unverified filter, category mismatch, or material identity
  incompleteness produces a warning and prevents a fully rankable competition
  result for that category.
- **Preflight (`LREQ-ID-040`):** zero attempted identities gives `insufficient`;
  a failed preflight blocks bulk enrichment; successful results are reused;
  preflight rates use unique identities, not category references.
- **Cutoff:** captured once, after enrichment, before metrics; passed into every
  pure function (dependency-map gate).
- **Run size:** fewer than `MIN_CATEGORIES_PER_RUN` (8) is rejected before
  ranking; an 8–20-category run may compute provisional scores but has an empty
  `base_rankable_candidates` and null `top_3_stability`/`top_5_stability`
  (`LREQ-EVD-020`/`EVD-030`; dependency-map §6.2/§6.3).
- **Reference size (`LREQ-NRM-020`):** `category_count - 1`; a 21-category run
  stores 20 peers, never 21; field-specific usable counts are stored separately.
- **Sensitivity (`LREQ-SEN-020`):** it never adds or removes candidates, never
  mutates the balanced score, and evaluates only the frozen set.
- **Separate status fields (hard rule 7):** run status (`running`/`completed`/
  `failed`), discovery status, score state, evidence grade, and rankability stay
  distinct; `CategoryStatus` is internal and is never persisted as one of them
  (dependency-map §6.1, §6.5).
- **Preflight-failure representation (dependency-map gate):** one null-score
  `category_scores` row per requested category with persisted discovery/sample
  fields, `evidence_grade = insufficient`, `rankability_status = not_rankable`,
  and explicit preflight warnings — or, if those rows are omitted, Chunk 11 must
  join runs/discovery/samples/preflight. This chunk prefers writing the rows.
- **Configuration or taxonomy failure causes no network request** (dependency-map
  gate).
- **Non-empty `taxonomy_sha256`** (dependency-map §7): an empty value must never
  persist.
- **Null, explicit valid zero, invalid, and unavailable stay distinct** on every
  value this chunk carries (hard rule 2): no `or 0`, no default-0 parameter.

## 9. Test plan

- **Test files:** new `tests/test_pipeline.py`; one additive node in
  `tests/test_database.py`; new fixture module
  `tests/fixtures/pipeline_fixtures.py`.
- **Fixtures (in-memory, no network):**
  - `RecordingCoveoTransport` / `RecordingGraphQLTransport` — record every call
    and return scripted responses; the GraphQL transport can fail a specific
    identity, and the Coveo transport can fail a specific category/page.
  - `FixedClock` — returns a caller-advanced, timezone-aware UTC instant and
    counts its calls, so "cutoff captured once" is asserted by call count and by
    value identity.
  - `taxonomy_payload(categories)` — a valid taxonomy fixture; the same payload
    is hashed by `taxonomy_sha256_for` to produce the golden hash (hand-derived
    from the canonical JSON, not a literal).
  - `category_set(n)` — 2 / 8 / 21 category sets for the size boundaries.
  - `end_to_end_scenario()` — overlapping samples across categories (one shared
    identity), one category with a failed page, one failed enrichment identity,
    and one preflight-passing path, storing every expected value in the fixture
    so the test reads expected values without touching the implementation.
- **Golden vectors / expected values (hand-computed in the fixture):**
  - `taxonomy_sha256` = lowercase hex SHA-256 of
    `json.dumps(payload, sort_keys=True, separators=(",", ":"),
    ensure_ascii=False).encode("utf-8")` — asserted as a 64-char lowercase hex
    string.
  - `reference_size == n_categories - 1` for 8 and 21 category runs.
  - Enrichment execution count == number of unique sampled identities minus reuse
    count for the overlapping-sample scenario.
  - `projected_minimum_enrichment_seconds == pending_count *
    DEFAULT_MIN_REQUEST_INTERVAL_SECONDS`.
- **Exact pytest node IDs, `@pytest.mark.lreq` markers, and
  `tests/traceability.json` entries to add:**

| Node ID (base node ID for parameterized tests) | `@pytest.mark.lreq` markers | traceability.json value |
|---|---|---|
| `tests/test_pipeline.py::test_pipeline_runs_completed_end_to_end` | `LREQ-ARCH-030` | `["LREQ-ARCH-030"]` |
| `tests/test_pipeline.py::test_pipeline_is_deterministic_across_repeat_runs` | `LREQ-ARCH-030` | `["LREQ-ARCH-030"]` |
| `tests/test_pipeline.py::test_repeat_run_produces_structurally_equal_persisted_rows` | `LREQ-ARCH-030` | `["LREQ-ARCH-030"]` |
| `tests/test_pipeline.py::test_failed_preflight_blocks_enrichment_and_marks_run_failed` | `LREQ-ID-040`, `LREQ-NFR-030` | `["LREQ-ID-040", "LREQ-NFR-030"]` |
| `tests/test_pipeline.py::test_failed_preflight_issues_zero_enrichment_requests` | `LREQ-ID-040` | `["LREQ-ID-040"]` |
| `tests/test_pipeline.py::test_failed_preflight_retains_discovery_sample_and_preflight_rows` | `LREQ-ID-040`, `LREQ-EVD-020` | `["LREQ-ID-040", "LREQ-EVD-020"]` |
| `tests/test_pipeline.py::test_failed_preflight_persists_per_category_limitations` | `LREQ-EVD-020`, `LREQ-EXT-090` | `["LREQ-EVD-020", "LREQ-EXT-090"]` |
| `tests/test_pipeline.py::test_failed_preflight_does_not_complete_or_overwrite_failed` | `LREQ-ID-040` | `["LREQ-ID-040"]` |
| `tests/test_pipeline.py::test_insufficient_preflight_leaves_run_non_completed` | `LREQ-ID-040` | `["LREQ-ID-040"]` |
| `tests/test_pipeline.py::test_failed_category_does_not_abort_other_categories` | `LREQ-NFR-030`, `LREQ-EXT-090` | `["LREQ-NFR-030", "LREQ-EXT-090"]` |
| `tests/test_pipeline.py::test_failed_page_is_not_zero_assets` | `LREQ-NFR-030`, `LREQ-EXT-090` | `["LREQ-NFR-030", "LREQ-EXT-090"]` |
| `tests/test_pipeline.py::test_failed_asset_does_not_abort_other_assets` | `LREQ-NFR-030` | `["LREQ-NFR-030"]` |
| `tests/test_pipeline.py::test_run_with_fewer_than_min_categories_is_rejected` | `LREQ-CLI-040` | `["LREQ-CLI-040"]` |
| `tests/test_pipeline.py::test_eight_category_run_has_empty_candidates_and_null_stability` | `LREQ-EVD-020`, `LREQ-SEN-020` | `["LREQ-EVD-020", "LREQ-SEN-020"]` |
| `tests/test_pipeline.py::test_twenty_one_category_run_stores_reference_size_20` | `LREQ-NRM-020` | `["LREQ-NRM-020"]` |
| `tests/test_pipeline.py::test_scoring_cutoff_is_captured_once_and_threaded_to_pure_calls` | `LREQ-ARCH-030` | `["LREQ-ARCH-030"]` |
| `tests/test_pipeline.py::test_enrichment_projection_is_logged_before_first_request` | `LREQ-NFR-020` | `["LREQ-NFR-020"]` |
| `tests/test_pipeline.py::test_projection_contains_required_counts_and_minimum_time` | `LREQ-NFR-020` | `["LREQ-NFR-020"]` |
| `tests/test_pipeline.py::test_projection_log_contains_no_secret_or_identity` | `LREQ-NFR-020` | `["LREQ-NFR-020"]` |
| `tests/test_pipeline.py::test_invalid_configuration_causes_no_network_request` | `LREQ-CLI-040`, `LREQ-EXT-090` | `["LREQ-CLI-040", "LREQ-EXT-090"]` |
| `tests/test_pipeline.py::test_invalid_taxonomy_causes_no_network_request` | `LREQ-EXT-090` | `["LREQ-EXT-090"]` |
| `tests/test_pipeline.py::test_taxonomy_sha256_is_non_empty_and_matches_golden` | `LREQ-ARCH-030` | `["LREQ-ARCH-030"]` |
| `tests/test_pipeline.py::test_run_record_seeds_required_not_null_columns` | `LREQ-ARCH-030` | `["LREQ-ARCH-030"]` |
| `tests/test_pipeline.py::test_sensitivity_does_not_change_candidate_set_or_balanced_score` | `LREQ-SEN-020`, `LREQ-EVD-020` | `["LREQ-SEN-020", "LREQ-EVD-020"]` |
| `tests/test_pipeline.py::test_final_evidence_and_rankability_are_persisted_per_category` | `LREQ-SEN-020`, `LREQ-EVD-020` | `["LREQ-SEN-020", "LREQ-EVD-020"]` |
| `tests/test_pipeline.py::test_shared_sampled_identity_is_enriched_once` | `LREQ-ID-040` | `["LREQ-ID-040"]` |
| `tests/test_pipeline.py::test_run_uses_injected_clock_transports_and_sleeper` | `LREQ-ARCH-030` | `["LREQ-ARCH-030"]` |
| `tests/test_database.py::test_runs_taxonomy_sha256_empty_is_rejected` | `LREQ-ARCH-030` | `["LREQ-ARCH-030"]` |

Total: 28 new nodes (27 in `tests/test_pipeline.py`, 1 in
`tests/test_database.py`), each with one `tests/traceability.json` entry whose
value list equals the marker list shown. Anchored enumeration of the marker
counts in `tests/test_pipeline.py` (distinct base node IDs): **27** total, of
which **18** carry exactly one marker and **9** carry a two-marker stack. The 9
two-marker nodes are, by node ID: `test_failed_preflight_blocks_enrichment_and_marks_run_failed`,
`test_failed_preflight_retains_discovery_sample_and_preflight_rows`,
`test_failed_preflight_persists_per_category_limitations`,
`test_failed_category_does_not_abort_other_categories`,
`test_failed_page_is_not_zero_assets`,
`test_eight_category_run_has_empty_candidates_and_null_stability`,
`test_invalid_configuration_causes_no_network_request`,
`test_sensitivity_does_not_change_candidate_set_or_balanced_score`, and
`test_final_evidence_and_rankability_are_persisted_per_category`; every other
`tests/test_pipeline.py` node above carries one marker. The one
`tests/test_database.py` node carries one marker. Unit: distinct base pytest node
IDs, not marker decorator lines. 18 + 9 = 27; 27 + 1 = 28.
`LREQ-TST-080`/`LREQ-TST-090` are deliberately **not** attached here: their
primary owner is Chunk 13 (matrix rows 134–135), and attaching them to a Chunk 10
node would be a fabricated mapping.
- **Traceability count units:** node IDs above are distinct base node IDs (not
  marker decorator lines). The count is authored in this plan and SHALL be
  re-measured by the implementer with
  `python -m pytest tests/test_pipeline.py tests/test_database.py --collect-only -q`
  and by reading `tests/traceability.json` for the added keys. The count is a
  **plan-authored, not yet measured against a written file**, figure: the test
  file does not exist yet, so no query against an artifact can verify it and it
  MUST be re-run after `test-author` writes the nodes.

## 10. Definition of done (gate)

Copied verbatim from `Documents/requirements-dependency-map.md` Chunk 10 "Gate"
(lines 998–1007):

- A failed category does not abort unrelated categories.
- The scoring cutoff is captured once and passed into pure functions.
- A failed preflight prevents enrichment.
- Runs with fewer than `MIN_CATEGORIES_PER_RUN` categories (configured as 8) are rejected before ranking.
- Configuration or taxonomy failure causes no network request.
- If identity preflight fails: persist `run.status = failed`, retain discovery/sample/preflight observations, issue no bulk-enrichment requests, skip metric/score/ranking computation, persist category limitations where possible, produce no rankable scores, allow the dashboard to display the failed run as an audit/diagnostic report, and return a non-zero CLI exit code.
- Final sample-summary updates from Chunk 6B must complete before metric calculation; `category_scores` must use the same finalized per-stratum usable counts persisted in the sampling summaries.
- Category-level failure is represented internally by a typed `CategoryStatus` (`healthy`, `degraded`, `failed`) and mapped to `discovery_status`, warnings, `evidence_grade`, and `rankability_status`; it is not a separate persisted enum unless the schema explicitly adds that field.
- On preflight failure, the report read model uses one null-score `category_scores` row per requested category with persisted discovery/sample fields, `evidence_grade = insufficient`, `rankability_status = not_rankable`, and explicit preflight warnings. If implementation instead omits those rows, Chunk 11 must join runs, discovery, samples, and preflight observations to provide the same one-row-per-category view.
- 8–20 category runs may compute provisional scores, but have no rankable candidate set and null sensitivity stability values.

## 11. Explicit prohibitions

- **Must not read the system clock.** `run_pipeline` obtains every timestamp from
  the injected `clock`; `metrics.py`, `scoring.py`, and `sampling.py` read no clock
  and keep their purity boundary (LREQ-ARCH-010/020/030).
- **Must not import `report.py` or `cli.py`**, and must not call `sys.exit` or
  parse `argv`; the exit code is Chunk 12's (LREQ-CLI-010).
- **Must not issue any network request before configuration and taxonomy
  validation succeed** (gate bullet), and must not embed credentials in logs,
  SQLite, errors, or fixtures (LREQ-SEC-010/020).
- **Must not issue a bulk-enrichment request when the preflight gate is `failed`
  or `insufficient`** (LREQ-ID-040; Chunk 6B's gate check must be reached).
- **Must not overwrite an existing `failed` run status with `completed`, and must
  not mark an `insufficient`-preflight run completed** (interfaces/chunk-6A.md
  §5.7).
- **Must not re-derive the preflight gate, the sensitivity candidate set, the
  evidence grade, or the rankability status** — those are 6A/9A/9B outputs; this
  chunk consumes them.
- **Must not add or remove a sensitivity candidate and must not mutate the
  balanced score** (LREQ-SEN-020/-040).
- **Must not persist a pending usable-status placeholder on a completed run**
  (Chunk 6B gate; `finalize_enrichment` must run before metrics).
- **Must not convert null, invalid, or unavailable to `0`/`0.0`/`False`, and must
  not use `or 0`, `.get(k, 0)`, or a default-0 parameter** (AGENTS.md hard rule 2).
- **Must not invent a formula, threshold, weight, or field name.** Constants come
  from `models.py`/SRS §14; every function this chunk calls already defines the
  semantics.
- **Must not add a table, column, index, or status enum.** The only `database.py`
  change is the additive non-empty-value guard of §5.5.
- **Must not implement any out-of-scope item:** scheduling, resume/checkpoint,
  historical trends, run comparison, bulk enrichment of every discovered asset,
  favorite-count, extra GraphQL fields, alternative collection strategies,
  configurable weights, confidence intervals, sales calibration, automated
  credential acquisition, or multi-user/cloud.
- **Must not claim live network verification or statistical representativeness**
  anywhere in the produced code, docstrings, or report text.

## 12. Resolved decisions and carried-forward obligations

All nine items below were open questions when this plan was drafted. The lead has
ruled on each after independent verification, and the rulings are **resolved**:
they are adopted, not recommended. Item 5 carries a correction to the authority
this plan first cited, and item 7 carries a correction to what `CategoryStatus`
is. The two carried-forward obligations at the end remain outstanding and are
**not** resolved by this chunk.

1. **RESOLVED — where the empty-`taxonomy_sha256` guard belongs: option (c),
   both files.** `pipeline.py` never builds an empty hash (`taxonomy_sha256_for`
   returns a 64-char digest; a caller-supplied value must be a non-blank `str`)
   and `database.py` rejects an empty/whitespace provenance column on the `runs`
   write path (§5.5). Evidence: dependency-map §7 places the obligation on
   Chunk 10 and states the persistence layer rejects only `None`, not `""` — so
   both a prevention point and an enforcement point are required.
2. **RESOLVED — `src/niche_scout/database.py` and `tests/test_database.py` are
   authorized.** §6 authorizes both files for the §5.5 guard. Evidence:
   dependency-map §7 assigns the unmet `runs.taxonomy_sha256` obligation to
   Chunk 10, the only chunk that constructs a `RunRecord`; no other chunk's plan
   can authorize these files.
3. **RESOLVED — preflight failure: option (a), write the rows.**
   `run_pipeline` persists one null-score `category_scores` row per requested
   category with the discovery/sample fields it already holds,
   `evidence_grade = insufficient`, `rankability_status = not_rankable`, and
   explicit preflight warnings. Evidence: dependency-map Chunk 10 gate, first
   branch of the preflight-failure bullet; it keeps Chunk 11 a pure read model.
4. **RESOLVED — `run_id`: option (b), deterministic derivation, no random
   default.** `run_id` is caller-supplied optional; when absent it is derived
   deterministically from the injected clock plus a caller-supplied suffix. No
   UUID and no random component. An explicit `run_id` is authoritative and is
   never overwritten by derivation. Two runs with the same clock values and the
   same explicit id/suffix produce structurally equal persisted rows. Evidence:
   LREQ-ARCH-030 (SRS §3.3) — "the same normalized input data, policy versions,
   and configuration SHALL produce the same ... outputs" — which a random
   identifier would violate.
5. **RESOLVED — discovery booleans and breadth source: option (a), with the
   authority corrected.** `discovery_filter_verified` is the persisted
   `filter_status is CategoryFilterValidationStatus.VERIFIED`;
   `discovery_bounded_by_verified_total` is `True` iff a verified `total_count`
   exists **and** the terminal `discovery_status` is not `TRUNCATED`;
   `breadth_source` is decided by Chunk 7B's `breadth_raw` from the
   `BreadthMetricInput.verified_total_count` input (a supplied verified total →
   `verified_total_count`, else `distinct_canonical_discovered_count`).
   **Correction:** SRS §8.1 `LREQ-NRM-020` is silent on these booleans and is
   **not** the authority for them; the authority is SRS §4.1
   (`LREQ-EXT-050`/`LREQ-EXT-090`), the persisted `category_scores` columns
   (`discovery_filter_verified`, `discovery_bounded_by_verified_total`,
   `breadth_source`, `breadth_completeness_status`) that this chunk writes, and
   `interfaces/chunk-7B.md` §3/§4.1. The projection is **plan-level**, not SRS
   text. Note: rankability's "verified or bounded by a verified total" clause is
   realized in Chunk 9A through `Competition is None` (9A §4.2,
   `COMPETITION_UNBOUNDED_OR_MATERIAL_FAILURE`), **not** through `breadth_source`
   itself; `breadth_source`/`breadth_completeness_status` are inputs to Chunk 8's
   `competition_component`, and 9A observes only the resulting `None`.
6. **RESOLVED — `PageViewSemanticsStatus`: option (a), read it back.**
   Immediately after `run_identity_preflight` returns, `run_pipeline` reads
   `get_run(run_id).page_view_semantics_status` and passes that single value to
   `finalize_enrichment`, every `CategoryMetricInput`, and
   `score_category`. Evidence: dependency-map Chunk 6A row and
   `interfaces/chunk-6A.md` §5.4 step 4 (the non-clobbering write); one source of
   truth for the run-level status.
7. **RESOLVED — `CategoryStatus`: option (a), a pure helper in `pipeline.py`,
   with the roll-up corrected.** `CategoryStatus` is a **derived roll-up over
   already-final fields** — the persisted `discovery_status`, the warnings, the
   final `evidence_grade`, and the final `rankability_status`. It is **not an
   input that determines** evidence or rankability; those come from steps 15–16
   (Chunk 9A/9B). The roll-up rule is plan-level and fixed as:
   `page_failed`/`request_failed` → `failed`; `truncated`/`filter_unverified`/
   `category_mismatch`/`identity_incomplete` → `degraded`; otherwise `healthy`.
   It stays internal — no persisted column and no new enum — per
   `models.CategoryStatus`'s definition as internal orchestration state
   (`interfaces/chunk-00.md` §2) and dependency-map §6.5. Evidence: dependency-map
   Chunk 10 gate bullet on `CategoryStatus`, and §6.5 ("If implementation needs a
   standalone category state, it must add and document a typed `category_status`
   field rather than overloading discovery or rankability") — which this plan
   deliberately does not do.
8. **RESOLVED — `warnings_json` / `missing_components_json` shapes: option (a),
   frozen here in §5.** Chunk 10 freezes the two shapes in the produced interface
   because no Chunk 11 interface exists yet; Chunk 11 consumes them read-only.
   - `warnings_json = json.dumps(sorted(set(codes)), separators=(",", ":"))`
     where `codes` are `models.WarningCode` values plus the preflight/limitation
     codes this chunk observes. Sorted + set-deduplicated for determinism
     (LREQ-ARCH-030).
   - `missing_components_json = json.dumps([k for k in COMPONENT_WEIGHT_KEYS if
     component is None], separators=(",", ":"))`, in the fixed `COMPONENT_WEIGHT_KEYS`
     order `("D", "C", "R", "Q")` (`interfaces/chunk-08.md` §2).
   Evidence: the frozen `CategoryScoreRecord` (§4) requires both columns as
   strings; no SRS sentence fixes their content, so the shape is plan-level and is
   frozen with this plan so both consumers agree.
9. **RESOLVED — `run_pipeline` calls `finalize_enrichment` only.** It does not
   call `assert_finalization_consistency` a second time; non-empty
   `FinalizationReport.mismatches` are recorded in `PipelineResult.limitations`.
   Evidence: `interfaces/chunk-6B.md` §5.4 — `finalize_enrichment` already runs
   the §5.5 assertion and merges its result into `mismatches`; a second call would
   compare before the scoring-phase write and is redundant.

**Carried-forward obligations (recorded, not resolved, and not owned by this
chunk):**

- **URI trailing-identifier extraction (identity mapping rule 1.0.1) is
  UNVERIFIED. Owner: none.** The extraction half of the rule — the trailing
  numeric identifier after the final `-` in the last path segment of a
  response-level `clickUri`/`uri` — is inferred, not capture-verified, and no real
  captured Coveo response exists in this repository to verify it against
  (`interfaces/chunk-01.md` §4.1 and §8; `interfaces/chunk-03.md` §8;
  dependency-map §6.4). The satisfaction condition was relaxed by human ruling to
  discharge-by-scope-declaration with verification deferred to a future capture;
  **relaxed is not verified.** No artifact Chunk 10 produces may state or imply
  that the rule was verified against a real response.
- **OI-6 (CSRF/session sufficiency) has no owning chunk.** Its four
  sub-questions — whether `_csrf` is the only required cookie, whether another
  storefront session cookie is required, whether the cookie value must equal the
  `X-CSRF-Token` header byte-for-byte, and whether any User-Agent, encoding, or
  session-bootstrap requirement exists — are unassigned (dependency-map §7;
  `interfaces/chunk-05.md` §12 Q1/Q3). Chunk 10 neither resolves nor absorbs
  them; Chunk 5 already sends `X-CSRF-Token` and never builds a `Cookie` header,
  and this chunk performs no HTTP itself.

**Freeze record.** This plan is **Status: FROZEN**. All nine items above are
resolved rulings (item 5's authority and item 7's `CategoryStatus` direction are
corrections, applied here). The §9 pytest node IDs are frozen with the plan and
SHALL NOT be renamed by a later change; a ruling that changed an expected value
would be recorded as an update to the owning test's expected data, not as a node
rename. The two carried-forward obligations are recorded, not resolved.
