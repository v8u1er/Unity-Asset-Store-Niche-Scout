# Chunk 6B — Unique enrichment executor and persistence (public interface)

Status: VERIFIED
Frozen: 2026-09-21; verified after `spec-reviewer` round 2 `VERDICT: PASS` and
`GATE: PASSED` (`Documents/runs/chunk-6B.md`). Source plan:
`Documents/plans/chunk-6B-unique-enrichment-executor-and-persistence.md`
(Status: FROZEN; §5 reproduced below). This file is the public contract
downstream chunks (10, 11, 13) build against. It reproduces §5 of the plan plus
the §5.6 rule token and the frozen persisted shapes. Operator rulings R1–R3 and
the lead resolutions in plan §12 are incorporated; the `eligibility_rule`
spelling is a recommendation, not SRS-backed.

This chunk is orchestration only, additive to `src/niche_scout/pipeline.py`. It
computes the unique sampled-identity union, enriches each unique identity at most
once per run while reusing the observations Chunk 6A already persisted, logs the
pre-enrichment projection, captures `scoring_cutoff_utc` once after enrichment,
and finalizes the per-stratum and per-category usable counts from Chunk 7A/7B
results. It adds **no** eligibility predicate, **no** `database.py` method, and
**no** metric symbol, and reads no clock.

Additive only. Nothing in Chunk 0/1/2/4A/4B/5/6A/7A/7B is redefined or shadowed.
All new symbols live in `src/niche_scout/pipeline.py`.

---

## 5. Interface contract this chunk produces

This section becomes `Documents/interfaces/chunk-6B.md` verbatim once the lead
freezes it. It is additive: nothing in Chunk 0/1/2/4A/4B/5/6A/7A/7B is redefined
or shadowed. All new symbols live in `src/niche_scout/pipeline.py`. **No new
`database.py` method is required**; 6B uses `upsert_enrichment_observation`,
`upsert_category_scores`, and the existing reads.

### 5.0 Module and boundary rules

| Item | Kind | Rule |
|---|---|---|
| `src/niche_scout/pipeline.py` | **I/O/orchestration** | Union computation, enrichment execution, projection/logging, cutoff capture, finalization, and consistency assertions. No clock read; every timestamp is caller-supplied. No GraphQL protocol behavior; it calls `enrich_asset` (via the 6A helper `_run_adapter`). |
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
    never inflates the execution count. `already_enriched_keys` is supplied by
    the caller from the persisted `enrichment_observations` rows; a key in it is
    a reuse and is excluded from `pending_keys`. An empty run yields
    `members == ()`, both key tuples empty, and `category_reference_count == 0`.
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
    (`DEFAULT_MIN_REQUEST_INTERVAL_SECONDS`). Counts must be `int >= 0` (`bool`
    rejected) and the interval a finite `float >= 0.0`; anything else raises
    `ValueError`. The projection is a **minimum** lower bound and never a
    duration estimate: it ignores per-request latency, retries, and backoff.
    """

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
    after the pass, read back; it equals `len(union.members)` for a completed
    pass. `failed_identity_count` counts persisted observations with at least
    one non-`success` operation status and is an isolation count, never an abort
    reason.
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
         all counts `0` — except `reused_identity_count`, which reports
         `len(union.reuse_keys)` because the preflight rows already exist. This
         branch is a persisted, readable state, not an exception.
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
    second `enrich_asset` call would violate the at-most-once rule. The function
    never enriches an identity outside `union.pending_keys` and never issues a
    request when the gate is not `passed`. `retrieved_at_utc` is caller-supplied;
    this module reads no clock. `transport` is caller-injected.
    """
```

### 5.4 Cutoff capture and post-enrichment finalization (pipeline.py)

```python
def capture_scoring_cutoff_utc(now_utc: datetime) -> datetime:
    """Normalize the caller's single post-enrichment timestamp (operator ruling C).

    Returns the value as a timezone-aware UTC `datetime` (via `models.ensure_utc`).
    An aware non-UTC `now_utc` is converted to UTC; a naive `now_utc` raises
    `ValueError`. This function does not read
    the clock: the caller supplies the one timestamp, captured once, after
    enrichment and immediately before metric computation (SRS §3.2 step 10). It
    exists so the "captured once" invariant has a single named call site and is
    testable without touching the clock.
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
    eligibility_rule: str     # the §5.6 token, never null on a completed run

@dataclass(frozen=True, slots=True)
class CategoryFinalization:
    """One category's finalized counts and per-stratum records (LREQ-SMP-080).

    The three `usable_*_sample_count` values are the sums of the corresponding
    `u_*_h` over strata the applicable `stratum_is_usable` call accepts; they
    equal `CategoryRawMetrics.usable_*_sample_count` from Chunk 7B.
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
    quality_min_rating_count: int = QUALITY_MIN_RATING_COUNT,
) -> tuple[StratumFinalization, ...]:
    """Finalize one category's per-stratum usable counts (LREQ-SMP-080).

    For each `SamplingStratum` in `category.strata` (ascending `stratum_index`),
    every sampled member is projected to a `MetricObservation` from its
    persisted `EnrichmentObservationRecord` and classified **only** by Chunk 7A:

      - `u_demand_h` = count of observations with
        `age_normalized_page_view_index(...).value is not None`.
      - `u_recent_h` = count of observations with
        `age_days_exact(...).value is not None` (the recent-window length does
        not enter this count; it enters only the share numerator, matching
        Chunk 7B's `recent_share_raw` contract).
      - `u_quality_h` = count of observations for which
        `quality_observation_eligibility(...).eligible` is True.

    `usable_status` is `"usable"` iff `stratum_is_usable(u, ...)` for the
    component's own `u`, else `"unavailable"`; `"invalid"` is reserved for the
    structural/membership-disagreement branch. `eligibility_rule` is the §5.6
    token. A missing observation for a sampled member is unavailable and never
    zero. `observations` must contain an entry for every sampled member of
    `category`; a missing key raises `ValueError` naming the category only.
    `min_usable_samples_per_stratum`, `min_age_days_for_rate`, and
    `quality_min_rating_count` are caller/policy parameters (SRS §14) defaulted
    from `models`; they are forwarded to `stratum_is_usable`,
    `age_normalized_page_view_index`, and `quality_observation_eligibility`
    respectively (chunk-21). Pure: no I/O, no clock.
    """

def finalize_enrichment(
    repository: SqliteRepository,
    run: RunSamplingResult,
    *,
    scoring_cutoff_utc: datetime,
    computed_at_utc: datetime,
    page_view_semantics_status: PageViewSemanticsStatus,
    union: EnrichmentUnion,
    min_usable_samples_per_stratum: int = MIN_USABLE_SAMPLES_PER_STRATUM,
    min_age_days_for_rate: int = MIN_AGE_DAYS_FOR_RATE,
    quality_min_rating_count: int = QUALITY_MIN_RATING_COUNT,
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
         with a full `CategoryScoreRecord` (the carry-forward rule below).
      4. Run the §5.5 consistency assertion and return it in `mismatches`.

    Must be called after `capture_scoring_cutoff_utc` and before Chunk 10's
    metric computation. `computed_at_utc` is caller-supplied; this module reads
    no clock. Idempotent.

    `min_usable_samples_per_stratum`, `min_age_days_for_rate`, and
    `quality_min_rating_count` are caller/policy parameters (SRS §14) defaulted
    from `models`; they are forwarded to `finalize_stratum_counts`, replace the
    `MIN_USABLE_SAMPLES_PER_STRATUM` literal in the three category-level sums,
    and are forwarded to `assert_finalization_consistency`, so the finalized path
    and the scored `CategoryMetricInput` read one policy source (chunk-21).
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
    min_usable_samples_per_stratum: int = MIN_USABLE_SAMPLES_PER_STRATUM,
    min_age_days_for_rate: int = MIN_AGE_DAYS_FOR_RATE,
    quality_min_rating_count: int = QUALITY_MIN_RATING_COUNT,
) -> tuple[str, ...]:
    """The 6B-owned agreement check.

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
         `compute_category_raw_metrics`, and require the three
         `usable_*_sample_count` fields to equal the finalized values exactly
         (`int` equality). This drift assertion fails at 6B's gate rather than
         only at Chunk 10.
      C. Persisted round trip: re-read `category_scores` and
         `parse_stratum_statistics`, and require the stored per-stratum counts
         and statuses to equal `finalization`, and the stored category-level
         counts to equal the finalized values.
      D. Coverage cross-check: `sample_members` distinct identity count per
         category equals `enriched_sample_count`; every sampled member has an
         `enrichment_observations` row; no `stratum_statistics_json` object
         retains `usable_status == "pending"` on a completed run.
      E. `unique_enrichment_count` equals the run-wide distinct enriched
         identity count and is identical on every category row.

    `min_usable_samples_per_stratum`, `min_age_days_for_rate`, and
    `quality_min_rating_count` are caller/policy parameters (SRS §14) defaulted
    from `models`; check A uses `min_usable_samples_per_stratum` and check B's
    `CategoryMetricInput` receives all three, so the assertion compares
    like-for-like with the finalized counts under any non-default config
    (chunk-21). The per-category implementation helper
    `_consistency_mismatches_for_category` carries the same three keyword-only
    parameters.
    """
```

### 5.6 `eligibility_rule` value (6B defines it)

The 4B schema carries one `eligibility_rule` key per stratum while
LREQ-SMP-080 requires "the eligibility rule used for each usable count". The
value therefore encodes all three component rules in one token. **The spelling
below is a RECOMMENDATION, not SRS-backed**, exactly as Chunk 7A's reason
vocabulary is a recommendation. It is sourced only from 7A's
`METRIC_UNAVAILABLE_REASONS` and the frozen `models` constants; no new version
constant is introduced (SRS §14 defines none).

Frozen form: three `component=rule` fields joined by `;` in the fixed order
`demand`, `recent`, `quality`:

```text
demand=<rule>;recent=<rule>;quality=<rule>
```

`<rule>` is either

- `usable:<min>` — the component's stratum count met the inclusive usable
  minimum, with `<min>` the decimal value of `MIN_USABLE_SAMPLES_PER_STRATUM`
  (read from `models`, never a literal); or
- one token from `metrics.METRIC_UNAVAILABLE_REASONS` naming the dominant
  classification that made the component's count fall below the minimum.

When a component is usable, its field is `usable:<min>`. When it is not usable,
the field is the reason of the **first** observation in
`(stratum_index, sample_rank)` order whose classification returned an
unavailable reason; when the stratum has no observations, the field is
`METRIC_REASON_NULL`.

Count → single-token mapping (frozen):

| Component | Count field | 7A/7B classification source |
|---|---|---|
| demand | `u_demand_h` | `age_normalized_page_view_index(...)` |
| recent | `u_recent_h` | `age_days_exact(...)` |
| quality | `u_quality_h` | `quality_observation_eligibility(...)` |

`usable_status` stays one of the frozen four tokens (`"usable"`,
`"unavailable"`, `"invalid"`, and `"pending"` only from 4B). `"usable"` iff all
three components are usable; `"unavailable"` when at least one is not.
`eligibility_rule` is never `null` on a completed run. The value survives
`database.parse_stratum_statistics`, which validates only the ten-key set and
the four `usable_status` tokens.

### 5.7 Persisted shapes, ordering, and carry-forward

- `category_scores.usable_demand_sample_count`,
  `usable_recent_supply_sample_count`, `usable_quality_sample_count`, and
  `unique_enrichment_count`: written by 6B with measured values (replacing the
  4B pre-scoring `0` placeholders).
- `category_scores.stratum_statistics_json`: the frozen ten-key payload with
  final `u_*`, `usable_status`, and `eligibility_rule`.
- `enrichment_observations`: one row per unique sampled identity per run.
- **`upsert_category_scores` carry-forward.** `database.upsert_category_scores`
  rewrites every non-key column of `(run_id, category)` (chunk-02.md §2.7). The
  6B write therefore reconstructs the full `CategoryScoreRecord`: every
  `discovery_*` and sampling-phase column is carried forward unchanged from the
  persisted row, `stratum_statistics_json` and the four finalized counts are
  written, and every scoring-phase column (components, score, evidence,
  rankability, references, sensitivity) is left at the module's pre-scoring
  default. Chunk 10 owns the later scoring-phase write.
- **Ordering (operator ruling C).** 6B's internal order is
  `enrich → capture_scoring_cutoff_utc → finalize_enrichment →
  assert_finalization_consistency`; Chunk 10 then computes metrics with the same
  `scoring_cutoff_utc`. 6B never captures a second cutoff and never re-reads the
  clock. Relative to Chunk 10's numbered steps, 6B supplies step 9 (union,
  projection, enrichment, reuse), the capture of step 10, and the finalization
  that Chunk 10's gate requires "before metric calculation"; Chunk 10 owns steps
  1–8, 11–17, and the terminal run status.