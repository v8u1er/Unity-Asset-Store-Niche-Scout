# Chunk 6B — Unique enrichment executor and persistence

Status: FROZEN
Frozen: 2026-09-21 by chunk-lead under operator rulings R1–R3 (see the operator-rulings note below) and the lead resolutions recorded in §12.
Depends on (frozen interfaces required before this plan can be trusted):
  `Documents/interfaces/chunk-00.md` (VERIFIED) — `models.py` enums/constants:
  `IdentityPreflightStatus`, `RunStatus`, `OperationStatus`, `PageViewSemanticsStatus`,
  `SamplingBasis`, `MIN_USABLE_SAMPLES_PER_STRATUM`, `MIN_AGE_DAYS_FOR_RATE`,
  `RECENT_WINDOW_DAYS`, `QUALITY_MIN_RATING_COUNT`, `QUALITY_MIN_ELIGIBLE_ASSETS`,
  `MIN_REQUIRED_COMPONENT_COVERAGE`, `IDENTITY_MAPPING_RULE_VERSION`.
  `Documents/interfaces/chunk-02.md` (VERIFIED) — `SqliteRepository`,
  `update_run_status`, `update_run_preflight`, `upsert_enrichment_observation`,
  `get_run`, `get_sample_members`, `get_enrichment_observation`,
  `get_category_scores`, `upsert_category_scores`, `count_discovery_observations`,
  `count_sample_members`, `count_distinct_enrichment_identities`,
  `EnrichmentObservationRecord`, `CategoryScoreRecord`.
  `Documents/interfaces/chunk-4A.md` (VERIFIED) — `RunSamplingResult`,
  `CategorySamplingResult`, `SamplingStratum`, `SampledMember`,
  `RunSamplingResult.enrichment_identity_keys`, `by_category`.
  `Documents/interfaces/chunk-4B.md` (VERIFIED) — `stratum_statistics_json` ten-key
  schema, `USABLE_STATUS_VOCABULARY`, `PENDING_USABLE_STATUS`,
  `STRATUM_STATISTICS_KEYS`, `serialize_stratum_statistics`,
  `parse_stratum_statistics`, `upsert_sampling_summary`.
  `Documents/interfaces/chunk-05.md` (VERIFIED) — `enrich_asset`,
  `EnrichmentResult`, `EnrichmentObservationDraft`, `GraphQLTransport`,
  `GraphQLRetryPolicy`, `GRAPHQL_BATCH_ENDPOINT`.
  `Documents/interfaces/chunk-6A.md` (FROZEN) — `PreflightPolicy`,
  `PreflightSelection`, `PreflightRates`, `PreflightObservation`,
  `IdentityPreflightOutcome`, `run_identity_preflight`, `bulk_enrichment_allowed`,
  `mark_preflight_selected`.
  `Documents/interfaces/chunk-7A.md` (VERIFIED) — `age_days_exact`,
  `age_normalized_page_view_index`, `is_within_recent_window`, `stratum_is_usable`,
  `quality_observation_eligibility`, `METRIC_UNAVAILABLE_REASONS`.
  `Documents/interfaces/chunk-7B.md` (VERIFIED) — `MetricObservation`,
  `StratumMetricInput`, `CategoryMetricInput`, `BreadthMetricInput`,
  `CategoryRawMetrics`, `compute_category_raw_metrics`.
Blocks (chunks whose plan/implementation needs this chunk's interface):
  Chunk 10 (the pipeline order `enrich → cutoff → metrics`, and the
  `category_scores` finalization that must precede metric calculation),
  Chunk 11 (report read model reads the finalized `usable_*_sample_count` and
  `stratum_statistics_json`), Chunk 13 (acceptance over the reuse/failure-isolation
  behavior and the marker pass for `LREQ-TST-030/040/080`).

**Operator rulings applied (binding; do not reopen).** R1 — 6B does NOT author
eligibility predicates; it consumes Chunk 7A's primitives and Chunk 7B's
aggregates, and adds a 6B-owned agreement assertion. R2 — `scoring_cutoff_utc` is
captured once after enrichment and immediately before metric computation, and 6B
finalization runs after that capture, before metric computation, with that one
value (ruling C; SRS §3.2 step 10). R3 — the `eligibility_rule` token is defined
here because Chunk 7A shipped without defining it; the spelling is a
recommendation, and the count→token mapping is frozen in §5.

## 1. Goal

Chunk 6A makes the identity gate true. This chunk makes the run's enrichment
complete and its sample summaries authoritative: it computes the unique
sampled-identity union across categories, enriches each unique identity at most
once per run while reusing the successful preflight observations already written
by 6A, isolates per-asset failures, and then — after a single post-enrichment
`scoring_cutoff_utc` capture — finalizes every stratum's `u_demand_h`,
`u_recent_h`, `u_quality_h` and every category's `usable_*_sample_count` and
`unique_enrichment_count` from the authoritative enrichment observations and
Chunk 7A/7B eligibility results, so that Chunk 10's metric computation reads
exactly the counts this chunk persisted. It also logs the pre-enrichment
projection required by LREQ-NFR-020.

## 2. Scope

### In scope

- The unique sampled-identity union across categories (LREQ-GQL-080), derived
  from the persisted `sample_members` / the `RunSamplingResult`, in a
  deterministic first-seen order.
- At most one enrichment execution per unique identity per run: an identity whose
  successful preflight observation already exists is not requested again; the
  reuse is read from `enrichment_observations` (the row 6A wrote) and the
  execution count is a persisted, checkable invariant.
- Bulk enrichment only after the 6A gate: the executor is entered only when
  `bulk_enrichment_allowed(status)` is true; a `failed` or `insufficient`
  preflight issues zero requests.
- Enrichment persistence coordination: every remaining identity's
  `EnrichmentObservationDraft` is written through
  `upsert_enrichment_observation`, one row per `(run_id, asset_identity_key)`.
- Per-asset failure isolation (LREQ-NFR-030): one failed asset never aborts
  another; failures stay visible in the persisted observation's operation
  statuses.
- Pre-enrichment logging of discovered canonical assets, sampled assets, unique
  enrichment identities, and projected minimum enrichment time (LREQ-NFR-020).
- The single post-enrichment `scoring_cutoff_utc` capture (ruling C) and the
  finalization pass that runs after it and before metric computation.
- Post-enrichment finalization of per-stratum `u_demand_h`, `u_recent_h`,
  `u_quality_h` and `usable_status`/`eligibility_rule`, plus the category-level
  `usable_demand_sample_count`, `usable_recent_supply_sample_count`,
  `usable_quality_sample_count`, and `unique_enrichment_count`
  (LREQ-SMP-080 completion).
- The 6B-owned agreement assertion: category-level counts must equal the sums of
  the per-stratum counts this chunk wrote and must equal Chunk 7B's
  `compute_category_raw_metrics` outputs; drift fails at 6B's gate.
- Final category/sample summary consistency checks across `sample_members`,
  `enrichment_observations`, `stratum_statistics_json`, and `category_scores`
  (gate bullet, dependency map line 763).

### Explicitly out of scope (and who owns it instead)

- **Eligibility predicate authoring.** Chunk 7A (VERIFIED) owns every semantic
  eligibility decision (`stratum_is_usable`, `age_normalized_page_view_index`,
  `age_days_exact`, `is_within_recent_window`, `quality_observation_eligibility`).
  6B never re-derives a predicate; it calls these. The eligibility decision never
  leaves 7A.
- **Category-level raw estimators and coverages.** Chunk 7B (VERIFIED) owns
  `compute_category_raw_metrics` and the three `*_stratum_eligibility_coverage`
  values. 6B consumes them for the agreement assertion only; it does not write
  them (Chunk 10 maps them to `category_scores`).
- **The preflight planner, gate, and the `failed` run transition.** Chunk 6A
  (FROZEN). 6B only reads the gate disposition and the persisted preflight rows.
- **Metric computation, cutoffs, scoring, sensitivity.** Chunks 7B/8/9A/9B/10.
- **Run-level status finalization and terminal timestamps.** Chunk 10.
- **Report wording and warning rendering.** Chunks 10/11.
- **Any schema change.** No new table, column, index, constraint, or enum.
- **A thin additive 7B-owned counting wrapper.** Out of scope absent separate
  operator sign-off (ruling R1); 6B must not modify 7A/7B public surfaces.
- **Deferred obligations recorded, not resolved:** URI trailing-identifier
  extraction (identity mapping rule 1.0.1) remains capture-unverified and owns no
  chunk; `OI-6` (CSRF/session sufficiency) has no owning chunk;
  `runs.taxonomy_sha256` empty-hash rejection is owned by Chunk 10. 6B touches
  none of the three.

### Requirement roles

| LREQ | Role here |
|---|---|
| LREQ-GQL-080 | **Integration completion chunk** (matrix line 67: primary owner 6B; completion 6B). 6B owns at-most-once execution, the union, reuse, and the join to referencing categories. |
| LREQ-NFR-020 | **Primary implementation chunk** (matrix line 122: primary owner 6B; supporting Chunk 2; completion Chunk 10). 6B owns the projection + the pre-enrichment log statement. |
| LREQ-NFR-030 | **Supporting chunk** (matrix line 123: primary owner Chunk 10; supporting 6B). 6B owns per-asset isolation in the enrichment loop. |
| LREQ-SMP-080 | **Completion chunk** (matrix line 81: primary owner 4B; completion 4B/6B). 6B owns post-enrichment finalization of the usable counts and the per-stratum `u_*` fields. |
| LREQ-ID-040 | Consumed contract from Chunk 6A (the gate). No re-implementation. |
| LREQ-SEC-010/020 | Constraint: no credential/header/cookie/body in any persisted value or log line. |
| LREQ-ARCH-010/020/030 | Constraint: `metrics.py` stays pure and untouched; no clock read in `pipeline.py` helpers; determinism. |

## 3. Requirements this chunk must satisfy

| LREQ ID | Ownership role here | Normative text (from SRS-lean.md, quoted) | SRS section |
|---|---|---|---|
| LREQ-GQL-080 | Integration completion | "**LREQ-GQL-080**: A unique sampled identity SHALL be enriched at most once per run, regardless of how many category samples reference it. The result SHALL be joined to every referencing category." (SRS-lean.md lines 336–338.) Reinforced by §5: "The enrichment set SHALL be the union of all category samples, and each unique identity SHALL be enriched once only." (lines 488–489.) | §4.2, §5 |
| LREQ-NFR-020 | Primary implementation | "**LREQ-NFR-020**: Before bulk enrichment, log discovered canonical assets, sampled assets, unique enrichment identities, and projected minimum enrichment time." (lines 1165–1166.) | §11 |
| LREQ-NFR-030 | Supporting | "**LREQ-NFR-030**: A failed page or sampled asset SHALL not abort unrelated categories or assets; the failure SHALL remain visible in status and evidence fields." (lines 1168–1169.) 6B's share: the enrichment loop. | §11 |
| LREQ-SMP-080 | Completion | "For every stratum, the persisted summary SHALL include `N_h` (discovered population), `n_h` (sampled population), `u_demand_h`, `u_recent_h`, and `u_quality_h`, together with the eligibility rule used for each usable count." (lines 476–478.) "The following SHALL be persisted as distinct values: `discovered_population_count`, `enriched_sample_count`, `usable_demand_sample_count`, `usable_recent_supply_sample_count`, and `usable_quality_sample_count` … `enriched_sample_count` SHALL never replace the discovered population." (lines 483–487.) "The three `usable_*_sample_count` fields SHALL count distinct sampled observations that contribute to strata satisfying the applicable minimum usable-observation rule. The stratum summary remains authoritative for the per-stratum counts." (lines 618–620.) "`unique_enrichment_count` is the distinct sampled-identity count enriched once across the entire run and MAY be repeated on each category row for reporting convenience." (lines 614–616.) | §5.1, §6.5 |

## 4. Interface contracts consumed

Copied from the frozen interfaces and verified against the live module where a
name is cited as a signature. 6B redefines none of these.

```python
# chunk-4A (VERIFIED) — sampling.py
class RunSamplingResult:
    run_id: str
    sampling_rule_version: str
    categories: tuple[CategorySamplingResult, ...]
    @property
    def by_category(self) -> Mapping[str, CategorySamplingResult]: ...
    @property
    def enrichment_identity_keys(self) -> tuple[str, ...]:
        """Distinct selected identities across all categories, first-seen order."""

class CategorySamplingResult:
    category: str
    strata: tuple[SamplingStratum, ...]      # ascending stratum_index
    members: tuple[SampledMember, ...]       # (stratum_index, sample_rank) order
    sample_is_census: bool
    discovered_population_count: int
    enriched_sample_count: int
    sample_fraction: float | None

class SamplingStratum:
    stratum_index: int
    start_ordinal: int
    end_ordinal: int
    population_count: int                    # N_h
    selected_count: int                      # n_h
```

```python
# chunk-6A (FROZEN) — pipeline.py
def bulk_enrichment_allowed(status: str) -> bool:
    """True iff status == IdentityPreflightStatus.PASSED.value. Pure."""

class IdentityPreflightOutcome:
    status: IdentityPreflightStatus
    selection: PreflightSelection
    rates: PreflightRates
    summary: IdentityPreflightSummary
    observations: tuple[PreflightObservation, ...]

def run_identity_preflight(...) -> IdentityPreflightOutcome: ...
```

```python
# chunk-05 (VERIFIED) — collector_graphql.py
GraphQLTransport = Callable[[GraphQLBatchRequest, Mapping[str, str]], GraphQLBatchResponse]
def enrich_asset(
    asset_identity_key: str, *,
    credentials: Credentials,
    transport: GraphQLTransport,
    correlation_mode: GraphQLOperationCorrelationMode,
    retrieved_at_utc: datetime,
    policy: GraphQLRetryPolicy = GraphQLRetryPolicy(),
    endpoint: str = GRAPHQL_BATCH_ENDPOINT,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[EnrichmentResult, EnrichmentObservationDraft]: ...
```

`enrich_asset` never raises (chunk-05.md §5.11); a raising transport becomes
`TRANSPORT_FAILURE`. 6B reuses the 6A private helper `pipeline._run_adapter`
(verified present, `src/niche_scout/pipeline.py:931–980`) so the bytes-body
transport envelope and the `sleep` seam are handled once; 6B does not re-implement
request construction or retry.

```python
# chunk-02 (VERIFIED) — database.py
def upsert_enrichment_observation(self, observation: EnrichmentObservationRecord) -> None: ...
def get_enrichment_observation(self, run_id: str, asset_identity_key: str) -> Optional[EnrichmentObservationRecord]: ...
def get_sample_members(self, run_id: str, category: str) -> Sequence[SampleMemberRecord]: ...
def get_category_scores(self, run_id: str) -> Sequence[CategoryScoreRecord]: ...
def upsert_category_scores(self, scores: Sequence[CategoryScoreRecord]) -> int:
    """Finalize existing (run_id, category) rows; rewrites every non-key column."""
def count_discovery_observations(self, run_id: str) -> int: ...
def count_sample_members(self, run_id: str) -> int: ...
def count_distinct_enrichment_identities(self, run_id: str) -> int: ...
```

`upsert_category_scores` is the Chunk 6B/10 finalization path (chunk-02.md:344–347,
chunk-4B plan:243–245). It rewrites every non-key column, so a 6B write must
carry the already-persisted sampling/discovery columns forward unchanged and
leave the Chunk 8/9/10 scoring columns at their pre-scoring defaults; see §11.

```python
# chunk-4B (VERIFIED) — database.py
STRATUM_STATISTICS_KEYS: tuple[str, ...]   # the frozen ten keys
USABLE_STATUS_VOCABULARY: tuple[str, ...]  # ("pending", "usable", "unavailable", "invalid")
PENDING_USABLE_STATUS = "pending"
def serialize_stratum_statistics(category: CategorySamplingResult) -> str: ...
def parse_stratum_statistics(payload: str) -> tuple[dict[str, object], ...]: ...
```

Verified (`src/niche_scout/database.py:1963–2054`): `parse_stratum_statistics`
validates exactly the ten-key set and only the four `usable_status` tokens; it
does **not** constrain `eligibility_rule`, so the §5 token shape survives it.

```python
# chunk-7A (VERIFIED) — metrics.py (read: src/niche_scout/metrics.py)
def age_days_exact(
    first_published_date_utc: object, *, scoring_cutoff_utc: datetime
) -> MetricValue: ...
def age_normalized_page_view_index(
    product_page_views: object, first_published_date_utc: object, *,
    scoring_cutoff_utc: datetime, state: str | None,
    id_mapping_mismatch: bool,
    min_age_days_for_rate: int = MIN_AGE_DAYS_FOR_RATE,
) -> MetricValue: ...
def is_within_recent_window(
    age_days_exact: float, *, recent_window_days: int = RECENT_WINDOW_DAYS
) -> bool: ...
def stratum_is_usable(
    usable_observation_count: int, *,
    min_usable_samples_per_stratum: int = MIN_USABLE_SAMPLES_PER_STRATUM
) -> bool: ...
def quality_observation_eligibility(
    *, product_detail_status: OperationStatus,
    page_views_status: OperationStatus,
    id_mapping_mismatch: bool, state: str | None,
    rating_average: object, rating_count: object,
    page_view_semantics_status: PageViewSemanticsStatus,
    product_page_views: object, first_published_date_utc: object,
    scoring_cutoff_utc: datetime,
) -> MetricEligibility: ...
METRIC_UNAVAILABLE_REASONS: tuple[str, ...]   # the closed reason vocabulary
```

```python
# chunk-7B (VERIFIED) — metrics.py
class MetricObservation:  # mirrors the persisted EnrichmentObservationRecord
    product_page_views: object
    first_published_date_utc: object
    state: str | None
    id_mapping_mismatch: bool
    rating_average: object
    rating_count: object
    product_detail_status: OperationStatus
    page_views_status: OperationStatus

class StratumMetricInput:
    stratum_index: int
    discovered_population_count: int   # N_h
    sampled_population_count: int      # n_h; must equal len(observations)
    observations: tuple[MetricObservation, ...]

class CategoryMetricInput:
    category: str
    scoring_cutoff_utc: datetime
    page_view_semantics_status: PageViewSemanticsStatus
    strata: tuple[StratumMetricInput, ...]
    min_usable_samples_per_stratum: int = MIN_USABLE_SAMPLES_PER_STRATUM
    min_age_days_for_rate: int = MIN_AGE_DAYS_FOR_RATE
    recent_window_days: int = RECENT_WINDOW_DAYS
    quality_min_rating_count: int = QUALITY_MIN_RATING_COUNT  # INERT for 7B
    quality_min_eligible_assets: int = QUALITY_MIN_ELIGIBLE_ASSETS
    min_required_component_coverage: float = MIN_REQUIRED_COMPONENT_COVERAGE

class CategoryRawMetrics:
    category: str
    raw: RawMetricBundle
    demand_stratum_eligibility_coverage: float
    recent_supply_stratum_eligibility_coverage: float
    quality_stratum_eligibility_coverage: float
    usable_demand_sample_count: int
    usable_recent_supply_sample_count: int
    usable_quality_sample_count: int
    breadth_source: BreadthSource
    breadth_completeness_status: BreadthCompletenessStatus

def compute_category_raw_metrics(
    input: CategoryMetricInput, breadth_input: BreadthMetricInput
) -> CategoryRawMetrics: ...
```

`compute_category_raw_metrics` returns counts already summed over *usable strata*
(read: `src/niche_scout/metrics.py:1620–1659`), which is exactly the SRS §6.5
"distinct sampled observations that contribute to strata satisfying the
applicable minimum usable-observation rule" definition. 6B therefore does not
re-derive the category-level counts: it takes them from 7B and asserts its own
per-stratum sums agree.

## 5. Interface contract this chunk produces

This section becomes `Documents/interfaces/chunk-6B.md` verbatim once the lead
freezes it. It is additive: nothing in Chunk 0/1/2/4A/4B/5/6A/7A/7B is redefined
or shadowed. All new symbols live in `src/niche_scout/pipeline.py`. **No new
`database.py` method is required**; 6B uses `upsert_enrichment_observation`,
`upsert_category_scores`, and the existing reads.

### 5.0 Module and boundary rules

| Item | Kind | Rule |
|---|---|---|
| `src/niche_scout/pipeline.py` | **I/O/orchestration** | Union computation, enrichment execution, projection/logging, cutoff capture, finalization, and consistency assertions. No clock read; every timestamp is caller-supplied. No GraphQL protocol behavior; it calls `enrich_asset` (via `_run_adapter`). |
| `src/niche_scout/metrics.py` | **Pure, untouched** | 6B imports and calls 7A/7B; it does not add, rename, or re-declare any metric symbol. |

### 5.1 Unique-identity union and reuse plan (pipeline.py)

```python
@dataclass(frozen=True, slots=True)
class EnrichmentUnionMember:
    """One unique sampled identity in the run-wide union.

    `union_rank` is the 1-based position in the deterministic union order.
    `source_categories` are every category whose sample references the identity,
    in `RunSamplingResult.categories` order; `first_category` is its first
    element. `reused_from_preflight` is True iff a persisted
    `enrichment_observations` row for `(run_id, asset_identity_key)` already
    existed when the plan was built (the 6A preflight write).
    """
    asset_identity_key: str
    union_rank: int
    source_categories: tuple[str, ...]
    first_category: str
    reused_from_preflight: bool

@dataclass(frozen=True, slots=True)
class EnrichmentUnion:
    """The run-wide unique sampled-identity union (LREQ-GQL-080).

    `members` are unique by `asset_identity_key`, in
    `(category order, member order)` first-seen order — the same order as
    `RunSamplingResult.enrichment_identity_keys`. `reuse_keys` are the members
    already enriched by the preflight; `pending_keys` are the remainder, and
    `reuse_keys + pending_keys` partitions `members` with no overlap.
    `category_reference_count` is the total number of (category, identity)
    references and is never the execution count.
    """
    run_id: str
    members: tuple[EnrichmentUnionMember, ...]
    reuse_keys: tuple[str, ...]
    pending_keys: tuple[str, ...]
    category_reference_count: int

def compute_enrichment_union(
    run: RunSamplingResult,
    *,
    already_enriched_keys: AbstractSet[str],
) -> EnrichmentUnion:
    """Build the deterministic union and split reuse from pending (LREQ-GQL-080).

    Pure: no I/O, no clock. Iterates `run.categories` in order and each
    category's `members` in `(stratum_index, sample_rank_within_stratum)` order,
    deduplicating by `asset_identity_key` on first sight. An identity referenced
    by k categories appears once and carries all k in `source_categories`; it
    never inflates the execution count (gate bullet, dependency map line 758).
    `already_enriched_keys` is supplied by the caller from the persisted
    `enrichment_observations` rows; a key in it is a reuse and is excluded from
    `pending_keys`. An empty run yields `members == ()`, both key tuples empty,
    and `category_reference_count == 0`.
    """
```

### 5.2 Pre-enrichment projection and logging (pipeline.py)

```python
@dataclass(frozen=True, slots=True)
class EnrichmentProjection:
    """The LREQ-NFR-020 pre-enrichment projection.

    `discovered_canonical_assets` is the run-wide distinct canonical identity
    count; `sampled_assets` is the run-wide distinct sampled identity count;
    `unique_enrichment_identities` is `len(union.members)`;
    `reused_preflight_identities` is `len(union.reuse_keys)`;
    `pending_enrichment_identities` is `len(union.pending_keys)`.
    `projected_minimum_enrichment_seconds` is a `float` minimum, computed from
    the pending request count and the caller-supplied per-request interval; it
    is `0.0` when there are no pending identities (a measured zero, not null).
    No field is ever `None`.
    """
    discovered_canonical_assets: int
    sampled_assets: int
    unique_enrichment_identities: int
    reused_preflight_identities: int
    pending_enrichment_identities: int
    per_request_interval_seconds: float
    projected_minimum_enrichment_seconds: float

def build_enrichment_projection(
    union: EnrichmentUnion,
    *,
    discovered_canonical_assets: int,
    sampled_assets: int,
    per_request_interval_seconds: float,
) -> EnrichmentProjection:
    """Build the projection; pure arithmetic, no I/O and no clock.

    `projected_minimum_enrichment_seconds` is
    `len(union.pending_keys) * per_request_interval_seconds`. The interval is a
    caller-supplied policy value, not a literal invented here; the production
    caller passes `GraphQLRetryPolicy().min_request_interval_seconds`
    (`DEFAULT_MIN_REQUEST_INTERVAL_SECONDS`, chunk-05.md §5.1), which is the
    frozen constant Chunk 5 documents as "only meaningful for a caller looping
    over identities". Counts must be `int >= 0` (`bool` rejected) and the
    interval a finite `float >= 0.0`; anything else raises `ValueError`.

    The projection is a **minimum** lower bound and never a duration estimate:
    it ignores per-request latency, retries, and backoff. No SRS text authorizes
    a richer model; the SRS says only "projected minimum enrichment time"
    (SRS-lean.md:1166).

    Edge contract: `len(union.pending_keys) == 0` yields
    `projected_minimum_enrichment_seconds == 0.0` for any interval, including
    `0.0` (a measured zero, never `None`). Counts below `0` raise `ValueError`;
    a non-finite or negative interval raises `ValueError`; a zero interval is
    accepted. `unique_enrichment_identities == len(union.reuse_keys) +
    len(union.pending_keys)` always holds.
    """
```

```python
def log_enrichment_projection(projection: EnrichmentProjection) -> None:
    """Emit the LREQ-NFR-020 pre-enrichment log line.

    Logs exactly the four SRS-named quantities (discovered canonical assets,
    sampled assets, unique enrichment identities, projected minimum enrichment
    time) plus the reuse/pending split. A single line at `INFO`. The message
    contains only integers and a float: no credential, header value, cookie,
    response body, identity string, or category string (LREQ-SEC-010/020).
    Reads no clock; the caller invokes it before any bulk request is issued.
    """
```

### 5.3 Enrichment execution (pipeline.py)

```python
@dataclass(frozen=True, slots=True)
class EnrichmentExecutionReport:
    """Outcome of one bulk-enrichment pass (LREQ-GQL-080, LREQ-NFR-030).

    `executed_identity_count` is the number of `enrich_asset` calls actually
    issued — at most `len(union.pending_keys)`, and exactly one per pending
    identity. `reused_identity_count` is `len(union.reuse_keys)` and is the
    number of identities NOT requested again. `persisted_identity_count` is the
    distinct `(run_id, asset_identity_key)` rows in `enrichment_observations`
    after the pass, read back; it equals
    `len(union.members)` for a completed pass. `failed_identity_count` counts
    persisted observations with at least one non-`success` operation status and
    is an isolation count, never an abort reason.
    """
    run_id: str
    executed_identity_count: int
    reused_identity_count: int
    persisted_identity_count: int
    failed_identity_count: int

def enrich_unique_identities(
    repository: SqliteRepository,
    run: RunSamplingResult,
    *,
    preflight_status: str,
    credentials: Credentials,
    transport: GraphQLTransport,
    correlation_mode: GraphQLOperationCorrelationMode,
    retrieved_at_utc: datetime,
    union: EnrichmentUnion,
    projection: EnrichmentProjection,
    endpoint: str = GRAPHQL_BATCH_ENDPOINT,
    retry_policy: GraphQLRetryPolicy = GraphQLRetryPolicy(),
    sleep: Callable[[float], None] = time.sleep,
) -> EnrichmentExecutionReport:
    """Enrich the pending unique identities once each (LREQ-GQL-080/NFR-020/NFR-030).

    Order of operations:
      1. Gate check FIRST: if `bulk_enrichment_allowed(preflight_status)` is
         False, issue **zero** requests, write nothing, and return a report with
         all four counts `0` — except `reused_identity_count`, which reports
         `len(union.reuse_keys)` because the preflight rows already exist
         (dependency map line 761). This branch is a persisted, readable state,
         not an exception.
      2. Log the projection via `log_enrichment_projection(projection)` before
         the first request.
      3. For each key in `union.pending_keys`, in order, call `_run_adapter`
         (the 6A helper over Chunk 5 `enrich_asset`) exactly once, build the
         record with `draft.to_record(run.run_id)`, and
         `upsert_enrichment_observation(record)` inside one
         `repository.transaction()`. A failed asset never aborts the loop
         (LREQ-NFR-030): `enrich_asset` never raises, and one identity's
         `ERROR`/`TRANSPORT_FAILURE` result is persisted as its own row.
      4. Read back `count_distinct_enrichment_identities(run_id)` for
         `persisted_identity_count`.

    An identity in `union.reuse_keys` is never requested here; the 6A
    `(run_id, asset_identity_key)` primary key already holds its row and a
    second `enrich_asset` call for it would violate the at-most-once rule. The
    function never enriches an identity outside `union.pending_keys` and never
    issues a request when the gate is not `passed`. `retrieved_at_utc` is
    caller-supplied; this module reads no clock. `transport` is caller-injected.
    """
```

### 5.4 Cutoff capture and post-enrichment finalization (pipeline.py)

```python
def capture_scoring_cutoff_utc(now_utc: datetime) -> datetime:
    """Normalize the caller's single post-enrichment timestamp (ruling C).

    Returns the value as a timezone-aware UTC `datetime` (via `models.ensure_utc`).
    An aware non-UTC `now_utc` is converted to UTC; a naive `now_utc` raises
    `ValueError`. This function does not read
    the clock: the caller supplies the one timestamp, captured once, after
    enrichment and immediately before metric computation (SRS §3.2 step 10,
    SRS-lean.md:217). It exists so the "captured once" invariant has a single
    named call site and is testable without touching the clock.
    """
```

```python
@dataclass(frozen=True, slots=True)
class StratumFinalization:
    """One stratum's finalized counts and status (LREQ-SMP-080)."""
    stratum_index: int
    N_h: int
    n_h: int
    u_demand_h: int
    u_recent_h: int
    u_quality_h: int
    usable_status: str        # "usable" | "unavailable" | "invalid"
    eligibility_rule: str     # §5.6 token, always non-null on a completed run

@dataclass(frozen=True, slots=True)
class CategoryFinalization:
    """One category's finalized counts and per-stratum records (LREQ-SMP-080).

    `usable_demand_sample_count`, `usable_recent_supply_sample_count`, and
    `usable_quality_sample_count` are the sums of the corresponding `u_*_h`
    over strata the applicable `stratum_is_usable` call accepts; they equal
    `CategoryRawMetrics.usable_*_sample_count` from Chunk 7B (asserted, §5.5).
    """
    category: str
    strata: tuple[StratumFinalization, ...]
    usable_demand_sample_count: int
    usable_recent_supply_sample_count: int
    usable_quality_sample_count: int
    unique_enrichment_count: int
    stratum_statistics_json: str

@dataclass(frozen=True, slots=True)
class FinalizationReport:
    run_id: str
    scoring_cutoff_utc: datetime
    categories: tuple[CategoryFinalization, ...]
    category_rows_written: int
    mismatches: tuple[str, ...]      # empty → verified; never a fabricated 0

def finalize_stratum_counts(
    category: CategorySamplingResult,
    observations: Mapping[str, EnrichmentObservationRecord],
    *,
    scoring_cutoff_utc: datetime,
    page_view_semantics_status: PageViewSemanticsStatus,
    min_usable_samples_per_stratum: int = MIN_USABLE_SAMPLES_PER_STRATUM,
    min_age_days_for_rate: int = MIN_AGE_DAYS_FOR_RATE,
    recent_window_days: int = RECENT_WINDOW_DAYS,
) -> tuple[StratumFinalization, ...]:
    """Finalize one category's per-stratum usable counts (LREQ-SMP-080).

    For each `SamplingStratum` in `category.strata` (ascending `stratum_index`),
    every sampled member is projected to a `MetricObservation` from its
    persisted `EnrichmentObservationRecord` and classified **only** by Chunk 7A:

      - `u_demand_h` = count of observations with
        `age_normalized_page_view_index(...).value is not None`
        (`min_age_days_for_rate=min_age_days_for_rate`).
      - `u_recent_h` = count of observations with
        `age_days_exact(...).value is not None` (a usable dated observation; the
        recent-window length does not enter this count — it enters only the
        share numerator, matching Chunk 7B's `recent_share_raw` contract).
      - `u_quality_h` = count of observations for which
        `quality_observation_eligibility(...).eligible` is True
        (`page_view_semantics_status=page_view_semantics_status`).

    `usable_status` is `"usable"` iff `stratum_is_usable(u, min_usable_...)` for
    the component's own `u`, else `"unavailable"`; `"invalid"` is used only when
    the stratum's sampled population cannot be classified at all (see §8 E6).
    `eligibility_rule` is the §5.6 token for the component.

    A missing observation for a sampled member is **never** treated as zero: it
    is unavailable, and the count is not incremented (missing-not-zero,
    AGENTS.md hard rule 2). `observations` must contain an entry for every
    sampled member of `category`; a missing key raises `ValueError` naming the
    category only. Pure: no I/O, no clock.

    Edge contract: `category.strata == ()` (zero population) returns `()`, and
    the caller's category-level sums are all `0` (an explicit measured zero).
    `usable_status == "usable"` iff each of the three `stratum_is_usable(u, ...)`
    calls is True; otherwise `"unavailable"`. No observation classification
    raises: a product-level value is classified, never raised (Chunk 7A §4.1).
"""
```

```python
def finalize_enrichment(
    repository: SqliteRepository,
    run: RunSamplingResult,
    *,
    scoring_cutoff_utc: datetime,
    computed_at_utc: datetime,
    page_view_semantics_status: PageViewSemanticsStatus,
    union: EnrichmentUnion,
) -> FinalizationReport:
    """Finalize and persist the authoritative sample summaries (LREQ-SMP-080).

    Order of operations:
      1. For each category in `run.categories` order, read its persisted
         `sample_members` and the persisted `enrichment_observations` for each
         member key; build the per-stratum finalization (§5.4) and the three
         category-level sums.
      2. Re-serialize `stratum_statistics_json` with the frozen ten-key schema
         and deterministic `json.dumps(..., sort_keys=True,
         separators=(",", ":"))`, preserving the 4B `N_h`/`n_h`/ordinal values
         byte-for-byte and replacing only `u_demand_h`, `u_recent_h`,
         `u_quality_h`, `usable_status`, `eligibility_rule`.
      3. Write each `(run_id, category)` row through `upsert_category_scores`
         with a full `CategoryScoreRecord` (see §11 for the carry-forward rule).
      4. Run the §5.5 consistency assertion and return it in `mismatches`.

    Must be called after `capture_scoring_cutoff_utc` and before Chunk 10's
    metric computation (ruling C; dependency map line 1004). `computed_at_utc`
    is caller-supplied; this module reads no clock. Idempotent: re-running over
    the same observations produces byte-identical `stratum_statistics_json` and
    identical counts.

    Edge contract: `union.members == ()` yields `categories == ()`,
    `category_rows_written == 0`, and `mismatches == ()`. A category whose
    `sample_members` rows disagree with `category.strata` does not raise: the
    discrepancy is reported as a `mismatches` string naming the category and
    column, and the other categories still finalize.
    """
```

### 5.5 Consistency assertion (pipeline.py, 6B-owned)

```python
def assert_finalization_consistency(
    repository: SqliteRepository,
    run: RunSamplingResult,
    finalization: FinalizationReport,
    *,
    scoring_cutoff_utc: datetime,
    page_view_semantics_status: PageViewSemanticsStatus,
) -> tuple[str, ...]:
    """The 6B-owned agreement check (gate bullet, dependency map line 763).

    Returns `()` when every check holds, otherwise one mismatch string per
    violation. Strings name the category and the column only — never an identity
    string or a secret. Checks, in order:
      A. Per-stratum sums: for each component, the sum of its `u_*_h` over the
         strata the applicable `stratum_is_usable` call accepts equals the
         corresponding `CategoryFinalization.usable_*_sample_count` (plan §12 A3;
         SRS §6.5).
      B. 7B agreement: for each category, build the Chunk 7B
         `CategoryMetricInput`/`BreadthMetricInput` from the same persisted
         observations and the same `scoring_cutoff_utc`, call
         `compute_category_raw_metrics`, and require
         `usable_demand_sample_count`, `usable_recent_supply_sample_count`, and
         `usable_quality_sample_count` to equal the finalized values exactly
         (`int` equality, not a tolerance). This is the drift assertion that
         fails at 6B's gate rather than only at Chunk 10.
      C. Persisted round trip: re-read `category_scores` and
         `parse_stratum_statistics`, and require the stored per-stratum counts
         and statuses to equal `finalization`, and the stored category-level
         counts to equal the finalized values.
      D. Coverage cross-check: `sample_members` distinct identity count per
         category equals `enriched_sample_count`; every sampled member has an
         `enrichment_observations` row; no `stratum_statistics_json` object
         retains `usable_status == "pending"` on a completed run (gate bullet,
         dependency map line 762).
      E. `unique_enrichment_count` equals the run-wide distinct enriched
         identity count and is identical on every category row (SRS-lean:614–616).
    """
```

### 5.6 `eligibility_rule` value (6B defines it; ruling R3)

The 4B schema carries one `eligibility_rule` key per stratum (chunk-4B.md §5.2,
lines 116–148) while LREQ-SMP-080 requires "the eligibility rule used for each
usable count" (SRS-lean.md:478). The value therefore encodes all three component
rules in one token. **The spelling below is a RECOMMENDATION, not SRS-backed** —
the SRS names no machine-readable eligibility-rule value, exactly as Chunk 7A's
reason vocabulary is a recommendation (chunk-7A.md §2). The value is sourced only
from 7A's `METRIC_UNAVAILABLE_REASONS` and the frozen `models` constants; no new
version constant is introduced (SRS §14 defines none).

Frozen form: three `component=rule` fields joined by `;` in the fixed order
`demand`, `recent`, `quality`:

```text
demand=<rule>;recent=<rule>;quality=<rule>
```

`<rule>` is either

- `usable:<min>` — the component's stratum count met the inclusive usable
  minimum, with `<min>` the decimal value of
  `MIN_USABLE_SAMPLES_PER_STRATUM` (read from `models`, never a literal); or
- one token from `metrics.METRIC_UNAVAILABLE_REASONS` naming the dominant
  classification that made the component's count fall below the minimum.

When a component is usable, its field is `usable:<min>` regardless of how many
observations were individually unavailable. When it is not usable, the field is
the reason of the **first** observation in `(stratum_index, sample_rank)` order
whose classification returned an unavailable reason; if every observation was
classified as unusable with a reason, the first such reason is used. When the
stratum has no observations at all (a census category with `n_h == 0` is
impossible; this is the defensive branch of §8 E6), the field is
`METRIC_REASON_NULL`.

Count → single-token mapping (frozen):

| Component | Count field | 7A/7B classification source |
|---|---|---|
| demand | `u_demand_h` | `age_normalized_page_view_index(...)` |
| recent | `u_recent_h` | `age_days_exact(...)` |
| quality | `u_quality_h` | `quality_observation_eligibility(...)` |

`usable_status` stays one of the frozen four tokens (`"usable"`,
`"unavailable"`, `"invalid"`, and `"pending"` only from 4B). `"usable"` iff all
three components are usable; `"unavailable"` when at least one is not; the
`eligibility_rule` token is what carries the per-count rule detail LREQ-SMP-080
requires. Example for a stratum whose demand and recent counts are usable at the minimum
of 5 and whose quality count is not:

```text
demand=usable:5;recent=usable:5;quality=rating_count_below_minimum
```

`eligibility_rule` is never `null` on a completed run, and is never written by
6B as the 4B `null` placeholder.

### 5.7 Persisted shapes and ordering

- `category_scores.usable_demand_sample_count`,
  `usable_recent_supply_sample_count`, `usable_quality_sample_count`, and
  `unique_enrichment_count`: written by 6B with measured values (the 4B
  pre-scoring `0` placeholders are replaced; chunk-4B.md §5.3).
- `category_scores.stratum_statistics_json`: the frozen ten-key payload with
  final `u_*`, `usable_status`, and `eligibility_rule`.
- `enrichment_observations`: one row per unique sampled identity per run.
- **Ordering (ruling C).** The run order inside 6B is
  `enrich → capture_scoring_cutoff_utc → finalize_enrichment →
  assert_finalization_consistency`; Chunk 10 then computes metrics with the same
  `scoring_cutoff_utc`. 6B never captures a second cutoff and never re-reads the
  clock. Relative to Chunk 10's numbered steps (dependency map lines 962–980),
  6B supplies steps 9 (union, projection, enrichment, reuse), the capture of
  step 10, and the finalization that dependency map line 1004 requires "before
  metric calculation"; Chunk 10 owns steps 1–8, 11–17, and the terminal run
  status.

## 6. Files touched

| File | New/modified | Purpose |
|---|---|---|
| `src/niche_scout/pipeline.py` | Modified (additive) | §5.1–5.6 union, projection/logging, execution, cutoff capture, finalization, consistency assertion; extends `__all__` with the new names only |
| `tests/test_enrichment.py` | New | §9 tests; markers `LREQ-GQL-080`, `LREQ-NFR-020`, `LREQ-NFR-030`, `LREQ-SMP-080` only |
| `tests/fixtures/enrichment_fixtures.py` | New (inert data) | union/observation/transport fixtures and golden vectors (§9) |
| `tests/traceability.json` | Modified | entries for every new node ID, each mapping to the four `LREQ-*` IDs above |

No change to `models.py`, `config.py`, `database.py`, `metrics.py`, `scoring.py`,
`sampling.py`, `validation.py`, `collector.py`, `collector_graphql.py`,
`report.py`, or `cli.py`. If implementation finds a `database.py` change
necessary, that is a stop-and-flag event (`.kilo/project-rules.md` file
discipline), not a silent edit.

## 7. Task breakdown

- [ ] `compute_enrichment_union`, `EnrichmentUnion`, `EnrichmentUnionMember`; deterministic first-seen order, source-category join, reuse/pending split, reference-count separation from execution count (LREQ-GQL-080).
- [ ] `EnrichmentProjection`, `build_enrichment_projection`, `log_enrichment_projection`; the four LREQ-NFR-020 quantities and the minimum-time arithmetic from the caller-supplied interval (LREQ-NFR-020).
- [ ] `enrich_unique_identities`, `EnrichmentExecutionReport`; gate-first zero-request branch, log-before-first-request, one `_run_adapter` call per pending key, per-asset isolation, upsert persistence, read-back count (LREQ-GQL-080, LREQ-NFR-020, LREQ-NFR-030).
- [ ] `capture_scoring_cutoff_utc`; single capture point, UTC normalization, no clock (ruling C).
- [ ] `finalize_stratum_counts`, `StratumFinalization`; per-stratum `u_*` from 7A only, `usable_status`, `eligibility_rule` token (LREQ-SMP-080).
- [ ] `CategoryFinalization`, `finalize_enrichment`, `FinalizationReport`; sums over usable strata, deterministic re-serialization, `upsert_category_scores` write with carry-forward (LREQ-SMP-080).
- [ ] `assert_finalization_consistency`; checks A–E including the 7B `compute_category_raw_metrics` agreement (LREQ-SMP-080, LREQ-GQL-080).
- [ ] Tests + traceability entries (§9, the four markers only); run `python -m niche_scout.tools.validate_traceability`, `ruff check`, `ruff format --check`.

## 8. Edge cases and invariants

- **E1 — Overlap.** An identity referenced by k categories is enriched once; the union has one member with k `source_categories` (gate line 758). No overlap value ever increases `unique_enrichment_count`, the execution count, or any preflight count.
- **E2 — Reuse.** A successful preflight observation is not requested again (gate line 759); the reuse is the persisted `(run_id, asset_identity_key)` row. Reuse does not require the preflight observation to be a *successful* one to be excluded from re-execution: an identity 6A attempted is already executed and is never retried in 6B (at-most-once per run).
- **E3 — Gate.** A `failed` or `insufficient` preflight issues zero bulk requests and writes zero observation rows (gate line 761); this is the `enrich_unique_identities` first branch and is not an exception.
- **E4 — Failure isolation.** A failed asset (operation `error`, transport failure, retry exhaustion) is persisted and the loop continues (gate line 760, LREQ-NFR-030). A failed asset contributes to no `u_*` count and never becomes `0`.
- **E5 — Missing is not zero.** A sampled member with no persisted observation is unavailable; `u_*` is not incremented. An explicit `product_page_views == 0` with a valid date is a usable index of `0.0` and does increment `u_demand_h` (Chunk 7A contract).
- **E6 — `invalid` vs `unavailable`.** `usable_status` is `"unavailable"` when the stratum's sampled observations classify as unavailable (a real measurement of unavailability). `"invalid"` is reserved for the defensive case where the stratum's `n_h` disagrees with the persisted membership count or the stratum object itself is structurally unusable; the plan records this branch and the gate treats either non-`"usable"` token as "explicit unavailable/invalid status with the eligibility rule used" (gate line 762). The exact boundary between the two tokens is an open question (§12 Q2).
- **E7 — No pending left.** On a completed run no `stratum_statistics_json` object carries `usable_status == "pending"` and no `eligibility_rule` is `null` (gate line 762).
- **E8 — Zero-population category.** `N == 0` yields no strata (`serialize_stratum_statistics` → `"[]"`); all three counts are `0` (an explicit measured zero) and the 7B estimators return `METRIC_REASON_ZERO_POPULATION`. 6B must not present `0` as a substitute for a missing population.
- **E9 — Census category.** `sample_is_census` categories finalize with the same `N_h`/`n_h`/`u_*` fields (SRS-lean:479–481); 6B does not special-case them beyond using their single stratum.
- **E10 — Category independence.** One category's finalization failure does not abort another (LREQ-NFR-030 spirit); `mismatches` is per category and the report is returned, not raised.
- **E11 — Determinism.** Union order, projection arithmetic, serialization, and the assertion are all order-deterministic; no set/dict iteration order affects output (LREQ-ARCH-030). No RNG, no clock read in `pipeline.py` helpers.
- **E12 — Redaction.** No log line or persisted value carries a credential, header value, cookie, response body, or full identity list (LREQ-SEC-010/020).

## 9. Test plan

Test file: `tests/test_enrichment.py`. Fixtures/golden vectors:
`tests/fixtures/enrichment_fixtures.py` (inert data: `RunSamplingResult` builders
with overlapping categories, hand-built `EnrichmentObservationRecord` rows,
injected transports that count calls and fail selected identities, and a
temporary in-memory `SqliteRepository` seeded through the frozen persistence
path). No live network. Every test carries `@pytest.mark.lreq("LREQ-...")` — the
four markers below only. Parameterized tests map by base node ID
(`tests/AGENTS.md`). `LREQ-TST-030/040/080` are **not** attached here; the
matrix's "Required tests" column is informational and Chunk 13 owns the marker
pass for those IDs (dependency map lines 299–300; chunk-6A.md §5.7 precedent).

| Test node ID | LREQ marker(s) | Matrix type (informational) | Gate bullet it fails if violated |
|---|---|---|---|
| `test_union_overlapping_categories_dedups_identities` | LREQ-GQL-080 | LREQ-TST-030 | line 758 |
| `test_union_preserves_first_seen_order_and_source_categories` | LREQ-GQL-080 | LREQ-TST-030 | line 758 |
| `test_union_reuse_split_excludes_preflight_keys` | LREQ-GQL-080 | LREQ-TST-040 | line 759 |
| `test_union_reference_count_never_inflates_execution` | LREQ-GQL-080 | LREQ-TST-030 | line 758 |
| `test_enrich_executes_one_request_per_pending_identity` | LREQ-GQL-080 | LREQ-TST-040 | line 758 |
| `test_enrich_does_not_request_reused_preflight_identities` | LREQ-GQL-080 | LREQ-TST-040 | line 759 |
| `test_enrich_failed_asset_does_not_abort_unrelated_assets` | LREQ-NFR-030 | LREQ-TST-080 | line 760 |
| `test_enrich_persists_every_pending_identity_observation` | LREQ-GQL-080 | LREQ-TST-040 | line 763 |
| `test_enrich_failed_preflight_issues_zero_requests` | LREQ-GQL-080 | LREQ-TST-080 | line 761 |
| `test_enrich_insufficient_preflight_issues_zero_requests` | LREQ-GQL-080 | LREQ-TST-080 | line 761 |
| `test_enrich_logs_projection_before_first_request` | LREQ-NFR-020 | LREQ-TST-080 | line 761 |
| `test_projection_minimum_seconds_from_interval` | LREQ-NFR-020 | LREQ-TST-080 | LREQ-NFR-020 |
| `test_projection_zero_pending_is_measured_zero` | LREQ-NFR-020 | LREQ-TST-080 | LREQ-NFR-020 |
| `test_projection_log_line_contains_no_credential_or_identity` | LREQ-NFR-020 | LREQ-TST-080 | LREQ-SEC-010/020 |
| `test_capture_scoring_cutoff_normalizes_and_rejects_naive` | LREQ-SMP-080 | LREQ-TST-080 | ruling C |
| `test_finalize_stratum_counts_from_observations` | LREQ-SMP-080 | LREQ-TST-020 | line 762 |
| `test_finalize_counts_missing_observation_not_zero` | LREQ-SMP-080 | LREQ-TST-020 | line 762 |
| `test_finalize_explicit_zero_page_views_counts_toward_demand` | LREQ-SMP-080 | LREQ-TST-020 | Chunk 7A contract |
| `test_finalize_usable_status_and_eligibility_rule_present` | LREQ-SMP-080 | LREQ-TST-020 | line 762 |
| `test_finalize_serialization_is_byte_deterministic` | LREQ-SMP-080 | LREQ-TST-020 | line 763 |
| `test_finalize_category_counts_equal_sum_over_usable_strata` | LREQ-SMP-080 | LREQ-TST-020 | line 763 |
| `test_finalize_agrees_with_chunk7b_compute_category_raw_metrics` | LREQ-SMP-080 | LREQ-TST-020 | line 763 |
| `test_finalize_unique_enrichment_count_identical_on_every_category` | LREQ-SMP-080 | LREQ-TST-020 | line 763 |
| `test_assert_consistency_detects_injected_drift` | LREQ-SMP-080 | LREQ-TST-020 | line 763 |
| `test_assert_consistency_clean_run_returns_no_mismatches` | LREQ-SMP-080 | LREQ-TST-020 | line 763 |
| `test_no_pending_usable_status_after_finalize` | LREQ-SMP-080 | LREQ-TST-020 | line 762 |
| `test_finalize_zero_population_category_is_empty_and_zero` | LREQ-SMP-080 | LREQ-TST-020 | line 762 |
| `test_finalize_is_idempotent` | LREQ-SMP-080 | LREQ-TST-020 | line 763 |

Golden vectors / hand-computed expectations:

- **Overlap golden (E1).** Three categories; identity `A` in categories 1 and 2,
  `B` in 2 and 3, `C` in 3. `members == (A, B, C)`; `len(members) == 3`;
  `category_reference_count == 5`; `A.source_categories == (cat1, cat2)`.
  One transport stub; executed calls `== 3` when no preflight reuse exists.
- **Reuse golden (E2).** Same union with `A` already persisted by preflight:
  `reuse_keys == ("A",)`, `pending_keys == ("B", "C")`, executed calls `== 2`,
  and `get_enrichment_observation(run_id, "A")` is byte-identical before and
  after the pass.
- **Projection golden (LREQ-NFR-020).** `pending == 2`,
  `per_request_interval_seconds == 0.5` → `projected_minimum_enrichment_seconds
  == 1.0`; `pending == 0` → `0.0`.
- **Finalization golden (LREQ-SMP-080).** One category, one stratum, `N_h == 10`,
  `n_h == 6`; observations: three with a valid date ≥ `MIN_AGE_DAYS_FOR_RATE`
  and finite page views (one of them `0`), one with a naive date, one with
  `state = "excluded"`, one with a failed `page_views_status`. Hand-computed
  `u_demand_h == 4`, `u_recent_h == 5` (the five usable dates; the failed
  PageViews observation still has a valid date), `u_quality_h == 3`; all three
  `>= 5`? — no: `u_quality_h == 3 < 5`, so quality is unusable and the
  `eligibility_rule` quality field names the dominant reason. `usable_status`
  is `"unavailable"`; the category-level quality count is `0` while demand and
  recent are `4` and `5`. Exact expected values are pinned in the fixture and
  asserted within `1e-9` where floats appear.
- **7B agreement golden.** The same observations through
  `compute_category_raw_metrics` must return
  `usable_demand_sample_count == 4`,
  `usable_recent_supply_sample_count == 5`,
  `usable_quality_sample_count == 0`.
- **Drift golden (check B).** A fixture that persists one `u_*` value one above
  its true sum must make `assert_finalization_consistency` return a mismatch
  naming the category and column, and never raise.

`tests/traceability.json` entries (node ID → LREQ list), example:
`"tests/test_enrichment.py::test_enrich_failed_asset_does_not_abort_unrelated_assets": ["LREQ-NFR-030"]`.
Each new node gets one entry; parameterized tests use the base node ID.

## 10. Definition of done (gate)

Copied verbatim from `Documents/requirements-dependency-map.md` §3, lines
756–763 (the `Gate:` header plus its six bullets):

```text
Gate:

- Overlapping category samples cause at most one enrichment execution per unique identity.
- Successful preflight observations are not requested again.
- A failed asset does not abort unrelated assets.
- No bulk-enrichment request is issued when the preflight gate is failed or `insufficient`.
- After enrichment, every sampled stratum has final usable counts or an explicit unavailable/invalid status with the eligibility rule used for that count; pending placeholders are not left in a completed run.
- Final `u_demand_h`, `u_recent_h`, and `u_quality_h` values agree with the pure metric inputs and are consistent across `sample_members`, `enrichment_observations`, `stratum_statistics_json`, and `category_scores`.
```

## 11. Explicit prohibitions

- MUST NOT author, re-derive, or duplicate any eligibility predicate; the
  eligibility decision is Chunk 7A's (`stratum_is_usable`,
  `age_normalized_page_view_index`, `age_days_exact`,
  `quality_observation_eligibility`). 6B calls them.
- MUST NOT modify `metrics.py` (7A/7B public surfaces), and MUST NOT add a
  counting wrapper there (ruling R1).
- MUST NOT issue a bulk request when `bulk_enrichment_allowed(preflight_status)`
  is False (gate line 761).
- MUST NOT call `enrich_asset` for an identity in `union.reuse_keys`, and MUST
  NOT call it more than once per unique identity per run (gate lines 758–759).
- MUST NOT abort the enrichment loop on a failed asset, and MUST NOT convert a
  failed or missing observation into `0` (gate line 760; hard rule 2).
- MUST NOT leave `usable_status == "pending"` or `eligibility_rule == null` in a
  completed run's `stratum_statistics_json` (gate line 762).
- MUST NOT write the category-level `usable_*_sample_count` from anything but
  the per-stratum sums / 7B agreement (gate line 763).
- MUST NOT capture `scoring_cutoff_utc` more than once, must capture it after
  enrichment and before metric computation, and MUST NOT read the clock in any
  6B helper (ruling C; LREQ-ARCH-020).
- MUST NOT re-implement GraphQL request construction, correlation, response
  validation, or retry classification; call `_run_adapter`/`enrich_asset`.
- MUST NOT import `sqlite3` outside `database.py`, and MUST NOT add a new
  `database.py` method or change any table, column, DDL string, enum, or index.
- MUST NOT write a scoring-phase `category_scores` column as a fabricated value,
  and MUST NOT let `upsert_category_scores` reset the already-persisted sampling
  or discovery columns. The 6B write SHALL read the existing
  `CategoryScoreRecord` (or the persisted sampling summary) and carry forward
  every sampling/discovery column unchanged; scoring-phase columns stay at their
  pre-scoring defaults until Chunks 8/9A/9B/10 write them.
- MUST NOT write a credential, header value, cookie, or response body into any
  persisted value or log line (LREQ-SEC-010/020).
- MUST NOT invent a constant, threshold, weight, field name, or version: only
  `models` constants, Chunk 7A/7B names, and the frozen 4B/6A field names.
- MUST NOT resolve or implement the three recorded open obligations (URI 1.0.1
  extraction, OI-6 CSRF, `taxonomy_sha256` empty-hash rejection).
- MUST NOT use `upsert_category_scores` before `finalize_enrichment` has the
  final `u_*` values; a pre-finalization write is the 4B pending state.

## 12. Assumptions and lead resolutions (frozen)

The operator delegated the recommended answers for the boundary questions. The
lead resolved the planner's sub-questions below by adopting the planner's
recommendations; none invents SRS semantics or changes a frozen interface. A1 is
confirmed against Chunk 7B's live contract.

**A1 (confirmed against 7B).** `u_recent_h` counts observations with a usable
exact age (`age_days_exact(...).value is not None`), not observations inside the
365-day window. Basis: Chunk 7B's `recent_share_raw` uses "usable dated count" as
the denominator and `recent_supply_stratum_eligibility_coverage` counts "a Chunk
7A-usable exact age regardless of the recent-window length"
(`src/niche_scout/metrics.py`, verified present). Chunk 7A's
`is_within_recent_window` enters only the share numerator. The agreement check B
would fail against 7B under the alternative reading, so this reading is frozen.

**A2 (assumption).** `unique_enrichment_count` is the run-wide distinct enriched
identity count, identical on every category row (SRS-lean:614–616 "MAY be
repeated on each category row for reporting convenience"). 6B writes the
run-wide value on every category row rather than a per-category count.

**A3 (assumption).** The category-level `usable_*_sample_count` is the 7B
definition: the sum of `u_*_h` over strata meeting the applicable usable
minimum (SRS-lean:618–620), not the sum over all strata. Assertion check A uses
the usable-strata sum.

**L1 (was Q1) — cutoff normalization: normalize.** `capture_scoring_cutoff_utc`
normalizes the caller's single timestamp through `models.ensure_utc`; a naive
`datetime` raises `ValueError`. Rationale: Chunk 7B requires a timezone-aware UTC
cutoff and raises otherwise; `models.ensure_utc` is the codebase's standard
normalizer. The returned value is the one Chunk 10 persists on
`runs.scoring_cutoff_utc`.

**L2 (was Q2) — `usable_status`: emit only `"usable"`/`"unavailable"`.** A
measured unavailability (count below the applicable usable minimum, or all
observations individually unavailable) is `"unavailable"`. `"invalid"` remains a
reserved, unreachable-on-a-clean-run defensive branch for a structural /
membership-disagreement state, documented in §8 E6. No SRS text distinguishes the
two tokens; the gate bullet accepts either non-`"usable"` token.

**L3 (was Q3) — `eligibility_rule` selection rule: first unavailable reason.**
When a component is not usable, its field is the reason of the first observation
in `(stratum_index, sample_rank)` order whose classification returned an
unavailable reason; the spelling in §5.6 is a recommendation (operator ruling
R3), sourced only from `metrics.METRIC_UNAVAILABLE_REASONS` and the frozen
`models` constants.

**L4 (was Q4) — `upsert_category_scores` is the 6B finalization path.** 6B
reconstructs the full `CategoryScoreRecord`: discovery/sampling-phase columns are
carried forward unchanged from the persisted row, `stratum_statistics_json` and
the four finalized counts are written, and scoring-phase columns stay at the
pre-scoring default. Chunk 10 rewrites the row later with scoring values (4B plan
§12 names this the 6B/10 path). Writing the row twice is the intended lifecycle.

**L5 (was Q5) — projection interval source.**
`per_request_interval_seconds = GraphQLRetryPolicy().min_request_interval_seconds`
(`DEFAULT_MIN_REQUEST_INTERVAL_SECONDS`); Chunk 5 documents it as the per-identity
pacing value `chunk-05.md` §5.11. No SRS text defines the projection formula, so
the interval stays a caller-supplied policy input, never a literal in 6B.

**L6 (was Q6) — a preflight-attempted identity is not retried in 6B.** An
identity 6A attempted — even if the persisted observation is a failure — is
already executed and is excluded from `pending_keys` (§8 E2). The alternative
would exceed one execution per identity per run and contradict the 6A gate bullet
"Successful preflight responses count toward enrichment exactly once".

**Out-of-scope context, recorded not resolved:** URI trailing-identifier
extraction (identity mapping rule 1.0.1) is inferred and capture-unverified with
no owning chunk; `OI-6` (CSRF/session sufficiency) has no owning chunk;
`runs.taxonomy_sha256` empty-hash rejection is owned by Chunk 10. None of the
three blocks this plan.

**UNVERIFIED (Chunk 10 integration).** 6B cannot verify, in this chunk, that
Chunk 10 (a) captures the cutoff at the SRS §3.2 step-10 point rather than
earlier, (b) passes the same `scoring_cutoff_utc` value into every metric call,
(c) does not re-run finalization or overwrite the finalized counts, (d) maps the
7B coverages and raws onto `category_scores` without resetting the 6B-written
columns, and (e) owns the terminal run status and `completed_at_utc`. These are
Chunk 10's obligations, carried in §5.7 and §11; they are UNVERIFIED here.
