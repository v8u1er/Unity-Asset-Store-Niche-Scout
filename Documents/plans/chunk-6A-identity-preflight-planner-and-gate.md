# Chunk 6A — Identity preflight planner and gate

Status: FROZEN
Ruling date: 2026-09-20 — operator ruled on all five §12 questions and audit
items A1–A7 (A3 refuted and replaced by A5). §12 records the rulings applied.
Depends on (frozen interfaces required before this plan can be trusted):
  Documents/interfaces/chunk-00.md (Status: VERIFIED) — models/enums/constants:
  `IdentityPreflightStatus`, `RunStatus`, `OperationStatus`,
  `GraphQLOperationCorrelationMode`, `PageViewSemanticsStatus`,
  `IDENTITY_PREFLIGHT_MIN_CATEGORIES`, `IDENTITY_PREFLIGHT_ASSETS_PER_CATEGORY`,
  `IDENTITY_PREFLIGHT_MAX_CONFLICT_RATE`, `IDENTITY_PREFLIGHT_MIN_SUCCESS_RATE`,
  `ENDPOINT_CONTRACT_VERSION`, `IDENTITY_MAPPING_RULE_VERSION`,
  `WarningCode.IDENTITY_PREFLIGHT_FAILED`.
  Documents/interfaces/chunk-01.md (Status: VERIFIED) — `ValidationIssue`,
  `summarize_validation_issues`, `compare_graphql_identity_aliases`.
  Documents/interfaces/chunk-02.md (Status: VERIFIED) — `insert_run`,
  `update_run_status`, `update_run_preflight`, `upsert_sample_members`,
  `upsert_enrichment_observation`, `get_run`, `get_sample_members`,
  `SqliteRepository`, exception semantics.
  Documents/interfaces/chunk-4A.md (Status: VERIFIED) — `RunSamplingResult`,
  `CategorySamplingResult`, `SampledMember`, `select_run_sample`,
  `selection_digest`.
  Documents/interfaces/chunk-4B.md (Status: VERIFIED) — the
  `sample_members.preflight_selected=False` placeholder (Q-5, §5.3) that 6A
  flips to `True`; `upsert_sampling_summary`, `persist_run_sampling`,
  `SamplingPersistenceReport`.
  Documents/interfaces/chunk-05.md (Status: VERIFIED) — `enrich_asset`,
  `EnrichmentResult`, `EnrichmentObservationDraft`, `GRAPHQL_BATCH_ENDPOINT`,
  `ENDPOINT_CONTRACT_VERSION`, `GraphQLOperationCorrelationMode`,
  `GraphQLRetryPolicy`, `GraphQLTransport`, `build_graphql_batch_request`,
  `execute_graphql_batch`, correlation/validation semantics.
Blocks (chunks whose plan/implementation needs this chunk's interface):
  Chunk 6B (bulk enrichment only after the preflight gate passes; reuses
  successful preflight observations), Chunk 10 (run-level status,
  no-downgrade contract, `identity_preflight_summary_json` rendering),
  Chunk 13 (`LREQ-TST-040`/`LREQ-TST-080` marker pass over 6A's nodes).

## 1. Goal

Chunks 4A/4B make deterministic sampling and persistence true. This chunk makes
the run's identity gate true: it selects a deterministic per-run preflight set
from the persisted sampling result, executes the normal GraphQL batch request
for each **unique** preflight identity through the reusable Chunk 5 adapter,
validates both `ProductDetail` and `ProductPageViews` operations and the
identity/correlation checks for each, computes unique-identity success and
conflict rates, persists the preflight status, a JSON summary, and one
observation per attempted identity **before** the gate returns, and decides
whether bulk enrichment may start. Zero attempted identities is an evidence
shortfall (`insufficient`, both rates `null`), never a zero-success result.

## 2. Scope

### In scope

- Deterministic preflight selection from the completed `RunSamplingResult`
  (same stable sampling order, at least two assets per category, at least five
  eligible categories when available; reduced coverage and asset shortfall
  recorded when not).
- Unique-identity dedup for the preflight denominator; category overlap must
  not inflate attempted/successful counts.
- A `PreflightPolicy` value object derived from the SRS §14 / LREQ-ID-030
  constants.
- Invoking the Chunk 5 `enrich_asset` adapter once per unique preflight
  identity, with a caller-injected transport (no live network in tests).
- Per-identity operation outcomes, selected correlation mode, endpoint
  signature, mapping-rule version, and a redacted diagnostic summary.
- Success/conflict rate calculation over unique identities with
  `null`-on-zero-attempted semantics.
- Preflight persistence: status + summary + observations + `preflight_selected`
  flags, all written before the gate returns.
- The gate predicate that blocks bulk enrichment unless `passed`, and the
  run-level transition: `failed` marks the run `failed`; `insufficient` blocks
  enrichment and does **not** mark the run failed in 6A.
- Non-clobbering run-level `page_view_semantics_status` initialization
  (`unvalidated` only when the current value is neither `validated_cumulative`
  nor `contradicted`).

### Explicitly out of scope (and who owns it instead)

- **Bulk enrichment execution and reuse plumbing** — Chunk 6B (LREQ-GQL-080).
  6A records preflight observations so 6B can reuse them; 6A never issues a
  third request or a bulk request.
- **Metric eligibility / identity-mismatch exclusion** — Chunk 7A.
- **Contradicted page-view semantics detection** — Chunk 7B; 6A only performs
  the non-clobbering initialization ruled in §12 Q3.
- **Terminal run finalization** (`completed`, terminal `completed_at_utc`,
  rendering) — Chunk 10; see the no-downgrade contract in §5.7.
- **Report wording and warning rendering** — Chunk 11 / Chunk 10.
- **Run comparison, retries across runs, scheduling** — out of scope (SRS §15).
- **New GraphQL protocol behavior, correlation algorithms, or retry policy** —
  Chunk 5 owns all of it. 6A supplies only controlled execution and gate
  policy; it must not re-implement request construction or correlation.

### Requirement roles

| LREQ | Role |
|---|---|
| LREQ-ID-010 | Primary implementation |
| LREQ-ID-020 | Primary implementation |
| LREQ-ID-030 | Primary implementation |
| LREQ-ID-040 | Primary implementation; **6A owns the `failed` transition** (`update_run_status`). Chunk 10 never downgrades and finalizes terminal state. See §12 Q2. |
| LREQ-GQL-010/030/040/050/070 | Supporting contract consumed from Chunk 5; no re-implementation |
| LREQ-SMP-060/080 | Supporting contract consumed from Chunk 4A/4B |
| LREQ-SEC-010/020 | Constraint: endpoint signature and diagnostic summary are redacted; no credential reaches persisted JSON |
| (none) | `page_view_semantics_status` initialization is named by **no lean LREQ**; it is a carried hand-off from Chunk 5 and is tracked under LREQ-ID-040 as a preflight-persistence invariant (§12 Q3). |

## 3. Requirements this chunk must satisfy

| LREQ ID | Ownership role here | Normative text (SRS-lean.md §4.4, lines 354–415) | SRS section |
|---|---|---|---|
| LREQ-ID-010 | Primary | "select at least two sampled canonical assets from each of at least five categories when five categories with two sampled assets are available. If fewer than five eligible categories are available, use every category with at least two sampled assets and record the reduced preflight coverage and asset shortfall. The preflight selection SHALL use the same stable sampling order and SHALL be persisted. A category with fewer than two sampled assets SHALL not be represented as satisfying the two-asset per-category minimum." | SRS-lean §4.4, lines 359–366 |
| LREQ-ID-020 | Primary | "The preflight SHALL perform the normal GraphQL request and verify: the request identifier is accepted by both operations; returned product identifiers are compatible with the requested identity; the page-view operation is associated with the requested package identifier; the operation-correlation mode is valid; and no unexplained response-shape or operation-association error occurred." | SRS-lean §4.4, lines 368–372 |
| LREQ-ID-030 | Primary | "Default preflight policy is: `IDENTITY_PREFLIGHT_MIN_CATEGORIES = 5`; `IDENTITY_PREFLIGHT_ASSETS_PER_CATEGORY = 2`; `IDENTITY_PREFLIGHT_MAX_CONFLICT_RATE = 0`; `IDENTITY_PREFLIGHT_MIN_SUCCESS_RATE = 0.90`." | SRS-lean §4.4, lines 377–384 |
| LREQ-ID-040 | Primary (owns the `failed` transition; Chunk 10 never downgrades) | "A preflight below the minimum success rate or above the maximum conflict rate SHALL stop bulk enrichment and mark the run failed. The failure SHALL include sampled counts, mismatch counts, endpoint signature, mapping-rule version, and a redacted diagnostic summary. Successful preflight responses SHALL be reused as the corresponding enrichment observations and SHALL count toward the one-enrichment-per-unique-identity limit. Preflight rates SHALL use unique sampled identities as the denominator, so category overlap SHALL not inflate the counts … When `unique preflight identities attempted = 0`, both rates SHALL be null, the preflight SHALL be `insufficient`, and bulk enrichment SHALL not start. This is a preflight evidence shortfall, not a zero-success result. The persisted `identity_preflight_summary_json` SHALL include attempted, successful, conflicting, and other failed unique-identity counts, together with the selected `graphql_operation_correlation_mode`." | SRS-lean §4.4, lines 386–414 |

## 4. Interface contracts consumed

Copied from the frozen interfaces, not re-derived from source (A6 correction:
the mapping-rule version is read from the **code constant**, and the interface
line is stale — see the note below).

```python
# models.py (Chunk 0, VERIFIED)
class IdentityPreflightStatus(str, Enum):
    PASSED = "passed"; FAILED = "failed"; INSUFFICIENT = "insufficient"
class RunStatus(str, Enum):
    RUNNING = "running"; COMPLETED = "completed"; FAILED = "failed"
class OperationStatus(str, Enum):
    SUCCESS = "success"; ERROR = "error"
class GraphQLOperationCorrelationMode(str, Enum):
    EXPLICIT_KEY = "explicit_key"; VALIDATED_POSITION = "validated_position"
class PageViewSemanticsStatus(str, Enum):
    UNVALIDATED = "unvalidated"; VALIDATED_CUMULATIVE = "validated_cumulative"
    CONTRADICTED = "contradicted"
IDENTITY_PREFLIGHT_MIN_CATEGORIES: int = 5
IDENTITY_PREFLIGHT_ASSETS_PER_CATEGORY: int = 2
IDENTITY_PREFLIGHT_MAX_CONFLICT_RATE: float = 0.0
IDENTITY_PREFLIGHT_MIN_SUCCESS_RATE: float = 0.90
ENDPOINT_CONTRACT_VERSION: str = "1.0.0"
IDENTITY_MAPPING_RULE_VERSION: str = "1.0.1"   # src/niche_scout/models.py:26
```

**A6 — mapping-rule version provenance.** Code reads
`models.IDENTITY_MAPPING_RULE_VERSION`; it never hard-codes a literal.
`src/niche_scout/models.py:26` is `"1.0.1"`, and the suite/fixtures use
`"1.0.1"` (`tests/fixtures/sampling_persistence_fixtures.py:226`,
`tests/test_collector.py:241`). `Documents/interfaces/chunk-00.md:115` still
says `"1.0.0"` and is **stale**; that is a doc fix for the lead, not 6A's to
make. This plan does not quote `"1.0.0"` as the value.

```python
# collector_graphql.py (Chunk 5, VERIFIED) — exact signatures from chunk-05.md §5.11
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
) -> tuple[EnrichmentResult, EnrichmentObservationDraft]
def execute_graphql_batch(...) -> EnrichmentResult  # not called directly by 6A
```

`enrich_asset` never raises (chunk-05.md lines 802–805: a raising transport is
caught and classified `TRANSPORT_FAILURE`). 6A therefore never sees an
exception from a call; a `TRANSPORT_FAILURE` result is an `other_failed`
attempt (see §12 A2).

```python
# database.py (Chunk 2, VERIFIED) — exact signatures from chunk-02.md
def update_run_status(self, run_id: str, status: str,
                      completed_at_utc: Optional[datetime] = None) -> None: ...
def update_run_preflight(
    self, run_id: str, *,
    identity_preflight_status: Optional[str] = None,
    identity_preflight_summary_json: Optional[str] = None,
    graphql_operation_correlation_mode: Optional[str] = None,
    page_view_semantics_status: Optional[str] = None,
) -> None: ...
def upsert_enrichment_observation(self, observation: EnrichmentObservationRecord) -> None: ...
def upsert_sample_members(self, members: Sequence[SampleMemberRecord]) -> int: ...
def get_run(self, run_id: str) -> Optional[RunRecord]: ...
def get_sample_members(self, run_id: str) -> tuple[SampleMemberRecord, ...]: ...
```

`update_run_status` leaves `completed_at_utc` unchanged when it is `None`
(`database.py:1122–1135`); see §12 Q2/A7 for 6A's choice.

```python
# sampling.py / 4A (VERIFIED)
class SampledMember:  # category, asset_identity_key, stratum_index,
    ...               # stratum_start_ordinal, stratum_end_ordinal,
                      # sample_rank_within_stratum, sample_is_census, selection_digest
class CategorySamplingResult:
    category: str; members: tuple[SampledMember, ...]
    enriched_sample_count: int; sampling_rule_version: str; ...
class RunSamplingResult:
    run_id: str; sampling_rule_version: str
    categories: tuple[CategorySamplingResult, ...]
    @property
    def by_category(self) -> Mapping[str, CategorySamplingResult]: ...
```

`enrich_asset` writes nothing and accepts no run id (chunk-05.md §5.11);
`EnrichmentObservationDraft.to_record(run_id)` is the only conversion and
performs a field-for-field copy. `preflight_selected` on `sample_members` is the
4B `False` placeholder (chunk-4B.md §5.3) that 6A flips.

**Q3 basis correction (A6-style).** The earlier draft cited
`interfaces/chunk-00.md:373` as a `RunRecord` default; that line is
`MetricInput.page_view_semantics_status`, a pure-metrics default, not
`RunRecord`. The actual state: `models.py:362` declares
`page_view_semantics_status: str` with **no default**; `database.py:101` is
`TEXT NOT NULL` with no DDL `DEFAULT`; `insert_run` inserts whatever
`RunRecord` carries. Nothing already defaults the run-level value — the
run-row inserter (Chunk 10, step 3) seeds it. See §12 Q3.

## 5. Interface contract this chunk produces

This section becomes `Documents/interfaces/chunk-6A.md` verbatim once the lead
freezes it. It is additive: nothing in Chunk 0/1/2/4A/4B/5 names is redefined or
shadowed. All new symbols live in `src/niche_scout/pipeline.py` except the one
additive `database.py` method in §5.4a.

### 5.1 Policy value object (pipeline.py)

```python
@dataclass(frozen=True, slots=True)
class PreflightPolicy:
    """The frozen LREQ-ID-030 policy. Defaults are the models.py constants.

    `max_conflict_rate` has no config knob (SRS §14 exposes only three preflight
    keys); it is always `IDENTITY_PREFLIGHT_MAX_CONFLICT_RATE` in production.
    Construction never reads the clock, config, or environment.
    """
    min_categories: int = IDENTITY_PREFLIGHT_MIN_CATEGORIES
    assets_per_category: int = IDENTITY_PREFLIGHT_ASSETS_PER_CATEGORY
    max_conflict_rate: float = IDENTITY_PREFLIGHT_MAX_CONFLICT_RATE
    min_success_rate: float = IDENTITY_PREFLIGHT_MIN_SUCCESS_RATE

def preflight_policy_from_config(config: NicheScoutConfig) -> PreflightPolicy:
    """Read the three config knobs, keep `max_conflict_rate` from the constant.

    `config.identity_preflight_min_categories`,
    `config.identity_preflight_assets_per_category`, and
    `config.identity_preflight_min_success_rate` are consumed as-is; the value is
    not clamped or re-validated here (`config.load_config` already validates the
    success-rate range). Pure: no I/O, no clock.
    """
```

Edge contract: `min_categories < 1` or `assets_per_category < 1` raises
`ValueError` at selection time (a category or asset minimum of zero is never a
valid preflight). `max_conflict_rate`/`min_success_rate` are used as given.

### 5.2 Pure selection and rate types (pipeline.py)

```python
@dataclass(frozen=True, slots=True)
class PreflightIdentity:
    """One unique preflight identity and the category-order slot that claimed it."""
    asset_identity_key: str
    preflight_rank: int          # 1-based rank in deterministic selection order
    source_category: str         # first category (RunSamplingResult order) selecting it

@dataclass(frozen=True, slots=True)
class PreflightSelection:
    """The deterministic preflight plan; persisted via `preflight_selected`.

    `identities` are unique by `asset_identity_key`, in
    `(category order, member order)` first-seen order. `eligible_categories` are
    the categories with `enriched_sample_count >= assets_per_category` in run
    order. `covered_categories` are the selected ones. `category_shortfall` is
    `max(0, min_categories - len(covered_categories))`; `asset_shortfall` is the
    count of unfilled `(covered category, asset slot)` positions against
    `len(covered_categories) * assets_per_category` after dedup.
    """
    run_id: str
    identities: tuple[PreflightIdentity, ...]
    covered_categories: tuple[str, ...]
    eligible_categories: tuple[str, ...]
    selected_category_count: int
    per_category_counts: tuple[tuple[str, int], ...]
    reduced_coverage: bool
    category_shortfall: int
    asset_shortfall: int

def select_preflight_identities(
    run: RunSamplingResult, *, policy: PreflightPolicy,
) -> PreflightSelection:
    """Deterministic preflight selection (LREQ-ID-010). Pure: no I/O, no clock.

    For each category in `run.categories` order, if
    `category.enriched_sample_count >= policy.assets_per_category`, take the
    first `policy.assets_per_category` members in `(stratum_index,
    sample_rank_within_stratum)` order (the 4A member order). Eligible categories
    are considered in run order and truncated to `policy.min_categories` chosen
    categories when more exist; when fewer exist, all are used and
    `reduced_coverage` is `True`. Identity union dedups by `asset_identity_key`
    with first-seen order preserved, so overlap never increases the attempted
    count. A category with fewer than `assets_per_category` members contributes
    nothing and is never counted toward the two-asset minimum. An empty run
    yields `identities == ()`, `covered_categories == ()`, and a positive
    `category_shortfall`.
    """
```

```python
@dataclass(frozen=True, slots=True)
class PreflightRates:
    """Rates over the unique-identity denominator (LREQ-ID-040).

    `success_rate` and `conflict_rate` are `None` iff
    `attempted_unique_identities == 0`; they are never `0.0` for zero attempts.
    `float64`, unrounded.
    """
    attempted_unique_identities: int
    successful_unique_identities: int
    conflicting_unique_identities: int
    other_failed_unique_identities: int
    success_rate: float | None
    conflict_rate: float | None

def compute_preflight_rates(
    selection: PreflightSelection,
    observations: Sequence["PreflightObservation"],
) -> PreflightRates:
    """Count unique identities, not category references (LREQ-ID-040).

    The denominator is exactly `len(selection.identities)`. An observation whose
    `asset_identity_key` is not in the selection is ignored (it can never
    inflate a rate). `successful` requires `identity_match is True` and both
    operation statuses `OperationStatus.SUCCESS`; `conflicting` requires
    `identity_match is False`; `other_failed` is the remainder. An identity with
    no observation counts in `attempted` and in `other_failed`; that branch is
    defensive only, because `enrich_asset` never raises and always yields a
    result (a `TRANSPORT_FAILURE` is `other_failed`, still attempted). With zero
    attempted both rates are `None`; an all-zero-numerator nonzero denominator
    gives `0.0`. Pure.
    """
```

The partition `attempted = successful + conflicting + other_failed` is an
**assumption**; the SRS never defines `other_failed` (see §12 A2).

### 5.3 Gate and orchestration (pipeline.py)

```python
def evaluate_preflight_gate(
    rates: PreflightRates, *, policy: PreflightPolicy,
) -> IdentityPreflightStatus:
    """Return the gate disposition (LREQ-ID-040). Pure.

    `attempted_unique_identities == 0` -> `INSUFFICIENT` (checked first, before
    any threshold comparison, so zero attempts is never `FAILED`/`PASSED`).
    Otherwise `FAILED` iff `conflict_rate > policy.max_conflict_rate` or
    `success_rate < policy.min_success_rate`; else `PASSED`. Boundary: a success
    rate exactly equal to `min_success_rate` passes; a conflict rate exactly
    equal to `max_conflict_rate` does not by itself fail.
    """

def bulk_enrichment_allowed(status: str) -> bool:
    """`True` iff `status == IdentityPreflightStatus.PASSED.value`. Pure.

    Chunk 6B MUST call this (or consume the returned status) before any bulk
    enrichment; `insufficient` and `failed` both return `False`.
    """
```

```python
@dataclass(frozen=True, slots=True)
class PreflightObservation:
    """The persisted per-identity preflight outcome (one per attempted identity).

    Distinct operation outcomes are preserved (never collapsed): one failed
    operation does not hide the other's success.

    `draft` is the Chunk 5 `EnrichmentObservationDraft` for this identity; it is
    the **only** object from which an `EnrichmentObservationRecord` may be made
    (`draft.to_record(run_id)`). `request_metadata_json` and `retrieved_at_utc`
    are read from `draft` and are never re-constructed here (A5).
    """
    asset_identity_key: str
    draft: EnrichmentObservationDraft     # carries request_metadata_json + retrieved_at_utc
    product_detail_status: str            # OperationStatus value (mirrors draft)
    page_views_status: str                # OperationStatus value (mirrors draft)
    is_both_operations_success: bool
    identity_match: bool | None           # None only when the identity could not be compared
    correlation_mode: str                 # GraphQLOperationCorrelationMode value
    mapping_rule_version: str             # models.IDENTITY_MAPPING_RULE_VERSION
    endpoint_signature: str               # graphql_endpoint_signature()
    diagnostic_summary_json: str | None   # redacted; issue codes/counts only

def graphql_endpoint_signature(
    endpoint: str = GRAPHQL_BATCH_ENDPOINT, *,
    endpoint_contract_version: str = ENDPOINT_CONTRACT_VERSION,
) -> str:
    """Build the persisted endpoint signature (LREQ-ID-040 line 388).

    Returns `f"{endpoint}#{endpoint_contract_version}"` — frozen literal form,
    e.g. `https://assetstore.unity.com/api/graphql/batch#1.0.0`. The `#`
    separator is an **assumption**, not SRS text (see §12 assumption A). It is
    derived only from the Chunk 5 `GRAPHQL_BATCH_ENDPOINT` and the models
    `ENDPOINT_CONTRACT_VERSION`; no new endpoint string, version string, or field
    name is invented. Never contains a credential, header value, cookie, or body.
    """
```

**Not persisted per observation row (A5).** `endpoint_signature`,
`mapping_rule_version`, `correlation_mode`, `is_both_operations_success`, and
`diagnostic_summary_json` are preflight-only and live in the run-level summary
(and, for correlation mode/operation names, in the draft's
`request_metadata_json` per Chunk 5 §5.10). `operation_outcomes_json` is
**dropped**: it restated `product_detail_status`/`page_views_status`, which the
draft already persists as separate columns.

```python
@dataclass(frozen=True, slots=True)
class IdentityPreflightSummary:
    """The `runs.identity_preflight_summary_json` content (LREQ-ID-040)."""
    status: str                              # IdentityPreflightStatus value
    attempted_unique_identities: int
    successful_unique_identities: int
    conflicting_unique_identities: int
    other_failed_unique_identities: int
    success_rate: float | None
    conflict_rate: float | None
    graphql_operation_correlation_mode: str  # SRS-mandated key (SRS-lean:414)
    graphql_endpoint_signature: str          # SRS concept :388; persisted-vocabulary name
    identity_mapping_rule_version: str       # SRS concept :388; persisted-vocabulary name
    selected_category_count: int             # sampled count
    eligible_category_count: int
    reduced_coverage: bool
    category_shortfall: int
    asset_shortfall: int
    diagnostic_summary_json: str | None      # redacted diagnostic summary
    def to_json(self) -> str:
        """Deterministic JSON: `json.dumps(..., sort_keys=True,
        separators=(",", ":"))`. `None` serializes as `null`; rates are
        unrounded `float64`; no credential/header/body text is present."""
```

```python
@dataclass(frozen=True, slots=True)
class IdentityPreflightOutcome:
    status: IdentityPreflightStatus
    selection: PreflightSelection
    rates: PreflightRates
    summary: IdentityPreflightSummary
    observations: tuple[PreflightObservation, ...]

def run_identity_preflight(
    repository: SqliteRepository,
    run: RunSamplingResult,
    *,
    credentials: Credentials,
    transport: GraphQLTransport,
    correlation_mode: GraphQLOperationCorrelationMode,
    retrieved_at_utc: datetime,
    policy: PreflightPolicy,
    endpoint: str = GRAPHQL_BATCH_ENDPOINT,
    retry_policy: GraphQLRetryPolicy = GraphQLRetryPolicy(),
    sleep: Callable[[float], None] = time.sleep,
) -> IdentityPreflightOutcome:
    """Plan, execute, persist, and gate the identity preflight (LREQ-ID-010/020/040).

    Order of operations, all in this call:
      1. `select_preflight_identities(run, policy=policy)`.
      2. For each unique identity in selection order, call the Chunk 5
         `enrich_asset` adapter exactly once; wrap its `EnrichmentResult` and
         `EnrichmentObservationDraft` in a `PreflightObservation`. A failed
         operation never aborts the loop (N identities are N independent calls).
      3. `compute_preflight_rates` over the selection denominator.
      4. `evaluate_preflight_gate`.
      5. Persist status + summary + observations + `preflight_selected` flags
         (§5.4) **before returning**.
      6. Non-clobbering `page_view_semantics_status` write (§5.4 step 4).
      7. On `FAILED`, `repository.update_run_status(run_id,
         RunStatus.FAILED.value)` with `completed_at_utc` **omitted** (Chunk 10
         owns the terminal timestamp; `pipeline.py` reads no clock). On
         `INSUFFICIENT`, no status transition in 6A.

    The function performs no bulk enrichment and issues no request beyond one
    `enrich_asset` call per unique preflight identity. `retrieved_at_utc` is
    caller-supplied; this module reads no clock. `transport` is caller-injected
    (fixtures in tests; never live network). Returns the outcome; the caller
    gates on `outcome.status`.
    """
```

### 5.4 Persistence surface (pipeline.py + one additive database.py method)

```python
@dataclass(frozen=True, slots=True)
class PreflightPersistenceReport:
    status: str
    observations_written: int
    members_marked_selected: int

def persist_preflight(
    repository: SqliteRepository,
    *,
    run_id: str,
    status: str,
    summary: IdentityPreflightSummary,
    observations: Sequence[PreflightObservation],
    selected_identity_keys: Sequence[str],
) -> PreflightPersistenceReport:
    """Persist preflight artifacts before the gate returns (gate bullet line 723).

    Steps, in order:
      1. `update_run_preflight(run_id, identity_preflight_status=status,
         identity_preflight_summary_json=summary.to_json(),
         graphql_operation_correlation_mode=summary.graphql_operation_correlation_mode)`.
      2. `upsert_enrichment_observation(observation.draft.to_record(run_id))`
         for every observation, so a successful preflight response is already
         the corresponding enrichment observation and the `(run_id,
         asset_identity_key)` primary key prevents a second row in 6B (gate
         bullet line 718; §12 Q5). The record is built **only** from
         `PreflightObservation.draft`; `request_metadata_json` is the draft's
         value, never a second construction (A5).
      3. `repository.mark_preflight_selected(run_id, selected_identity_keys)`
         (new, §5.4a) to flip the 4B `False` placeholders to `True`.
      4. Non-clobbering page-view-semantics write (§12 Q3): read the run via
         `get_run(run_id)`; iff the current `page_view_semantics_status` is
         neither `validated_cumulative` nor `contradicted`, call
         `update_run_preflight(run_id,
         page_view_semantics_status=PageViewSemanticsStatus.UNVALIDATED.value)`.

    A row is written for **every non-`insufficient` attempt, including
    failures**; zero-attempted (`insufficient`) writes zero observation rows,
    which is itself a persisted, readable state. `run_identity_preflight` calls
    this before any `update_run_status` call and never rolls back or deletes an
    observation row on failure (A4).

    Returns counts actually written. Never writes a credential/header/body.
    Idempotent under `upsert_enrichment_observation`.
    """
```

#### 5.4a Additive `database.py` method (new public name)

```python
def mark_preflight_selected(
    self, run_id: str, asset_identity_keys: Sequence[str],
) -> int:
    """Set `sample_members.preflight_selected = True` for the given keys.

    Scoped to `(run_id, asset_identity_key)`; returns the number of rows
    changed. Keys not present in the run's sample_members are ignored (never an
    error and never a fabricated row). No other column changes; reads no clock.
    """
```

### 5.5 Persisted shapes

`runs.identity_preflight_status`: one of `passed` / `failed` / `insufficient`
(`IdentityPreflightStatus`). `runs.identity_preflight_summary_json` is the
`IdentityPreflightSummary.to_json()` string with the frozen key set below. The
column is `TEXT NOT NULL` (`database.py:104`), so Chunk 10 must seed a value at
`insert_run`; 6A always overwrites it with the full set.

**Frozen `identity_preflight_summary_json` key table (A1).** Each key is
labelled SRS-mandated (concept or key name fixed by SRS-lean §4.4) vs
plan-derived:

| JSON key | Value source | Provenance |
|---|---|---|
| `status` | `IdentityPreflightStatus` value | plan-derived; required to distinguish `passed`/`failed`/`insufficient` |
| `attempted_unique_identities` | `PreflightRates` | SRS-mandated count (SRS-lean:412–413) |
| `successful_unique_identities` | `PreflightRates` | SRS-mandated count (SRS-lean:412–413) |
| `conflicting_unique_identities` | `PreflightRates` | SRS-mandated count (SRS-lean:412–413) |
| `other_failed_unique_identities` | `PreflightRates` | SRS-mandated count (SRS-lean:412–413); semantics are an assumption (§12 A2) |
| `success_rate` | `PreflightRates.success_rate` | plan-derived key; formula SRS-mandated (SRS-lean:397–400) |
| `conflict_rate` | `PreflightRates.conflict_rate` | plan-derived key; formula SRS-mandated (SRS-lean:402–405) |
| `graphql_operation_correlation_mode` | `PreflightObservation.correlation_mode` | SRS-mandated **key name** (SRS-lean:414) |
| `graphql_endpoint_signature` | `graphql_endpoint_signature()` | SRS-mandated concept (SRS-lean:388); name aligned to the persisted vocabulary `graphql_endpoint_signature` (retired `SRS-revision2.md:334`) |
| `identity_mapping_rule_version` | `models.IDENTITY_MAPPING_RULE_VERSION` | SRS-mandated concept (SRS-lean:388); name aligned to the persisted vocabulary `identity_mapping_rule_version` (`SRS-revision2.md:334`) |
| `selected_category_count` | `PreflightSelection` | plan-derived; LREQ-ID-010 "sampled counts" |
| `eligible_category_count` | `PreflightSelection` | plan-derived; reduced-coverage record (LREQ-ID-010) |
| `reduced_coverage` | `PreflightSelection` | plan-derived; LREQ-ID-010 "reduced preflight coverage" |
| `category_shortfall` | `PreflightSelection` | plan-derived; LREQ-ID-010 shortfall record |
| `asset_shortfall` | `PreflightSelection` | plan-derived; LREQ-ID-010 asset shortfall |
| `diagnostic_summary_json` | redacted diagnostic summary | SRS-mandated concept (SRS-lean:388); key name plan-derived |

Example value:

```json
{
  "status": "failed",
  "attempted_unique_identities": 10,
  "successful_unique_identities": 8,
  "conflicting_unique_identities": 1,
  "other_failed_unique_identities": 1,
  "success_rate": 0.8,
  "conflict_rate": 0.1,
  "graphql_operation_correlation_mode": "explicit_key",
  "graphql_endpoint_signature": "https://assetstore.unity.com/api/graphql/batch#1.0.0",
  "identity_mapping_rule_version": "1.0.1",
  "selected_category_count": 5,
  "eligible_category_count": 6,
  "reduced_coverage": false,
  "category_shortfall": 0,
  "asset_shortfall": 0,
  "diagnostic_summary_json": null
}
```

`identity_preflight_summary_json` for zero attempted identities:
`attempted/successful/conflicting/other_failed` all `0`, `success_rate: null`,
`conflict_rate: null`, `status: "insufficient"`.

**`PreflightObservation` → `EnrichmentObservationRecord` mapping (A5).** The
record is produced **only** by `PreflightObservation.draft.to_record(run_id)`;
6A constructs no record field itself. `PreflightObservation` lacks the
`graphql_id`, `product_id`, `rating_average`, `rating_count`, `review_count`,
`first_published_date_utc`, `publisher_json`, `category_json`, `state`,
`product_page_views`, `product_detail_error_summary`, and
`page_views_error_summary` members (compare `interfaces/chunk-05.md:649–667`),
so it cannot build the record directly.

| Record field | Source |
|---|---|
| `run_id` | the `run_id` argument to `persist_preflight` |
| every other field | `PreflightObservation.draft.to_record(run_id)` (Chunk 5 §5.9 field-for-field copy) |
| `request_metadata_json` | `draft.request_metadata_json` — never a second construction |
| `retrieved_at_utc` | `draft.retrieved_at_utc` |

`preflight_selected = 1` on the selected `sample_members` rows; no other
`sample_members` column changes.

### 5.6 Endpoint signature (resolved)

Resolved by operator ruling (§12 Q1). `graphql_endpoint_signature` lives in
`pipeline.py` **only** and is **not** added to `collector_graphql.py` (outside
6A's file scope). Frozen literal form:
`f"{endpoint}#{endpoint_contract_version}"`, e.g.
`https://assetstore.unity.com/api/graphql/batch#1.0.0`. The `#` separator is a
recorded assumption (§12 assumption A); the operands are the Chunk 5
`GRAPHQL_BATCH_ENDPOINT` and the models `ENDPOINT_CONTRACT_VERSION`, so no new
endpoint string or version string is invented in 6A.

### 5.7 Carried cross-chunk contracts

- **Chunk 10 — no downgrade (Q2).** 6A owns the `failed` transition via
  `repository.update_run_status(run_id, RunStatus.FAILED.value)` with
  `completed_at_utc` omitted. Chunk 10's "Mark the run completed or failed" step
  SHALL NOT overwrite an existing `failed` with `completed`, and SHALL leave
  `insufficient` runs non-completed. Chunk 10 owns the terminal
  `completed_at_utc` (6A reads no clock). Chunk 10 also seeds
  `identity_preflight_summary_json` at `insert_run` (NOT NULL column) and renders
  the frozen key set of §5.5.
- **Chunk 13 — marker pass (Q4).** 6A nodes carry only
  `LREQ-ID-010/020/030/040`. `LREQ-TST-040` and `LREQ-TST-080` are deferred to
  Chunk 13 (matrix rows 130 and 134 give Chunk 13 primary ownership; 6A is only
  *supporting* for `LREQ-TST-040`). The existing `LREQ-TST-080` occurrences in
  `tests/test_database.py` (lines 469, 803) are Chunk 13's marker pass, not 6A's.
- **Chunk 6B — reuse (Q5).** Preflight observations are written at preflight
  time; 6B reuses them and never re-enriches a preflight identity (the
  `(run_id, asset_identity_key)` primary key enforces one row).

## 6. Files touched

| File | New/modified | Purpose |
|---|---|---|
| `src/niche_scout/pipeline.py` | Modified (stub → implementation) | §5.1–5.4 types, selection, rates, gate, observation/summary, endpoint signature, orchestration, persistence |
| `src/niche_scout/database.py` | Modified (additive) | §5.4a `mark_preflight_selected` only; no schema/column/DDL change |
| `tests/test_identity_preflight.py` | New | §9 tests; markers `LREQ-ID-010/020/030/040` only (matrix types informational; TST markers deferred to Chunk 13) |
| `tests/fixtures/identity_preflight_vectors.py` | New (inert data) | preflight fixtures / golden vectors (§9) |
| `tests/traceability.json` | Modified | entries for every new node ID, each mapping to `LREQ-ID-*` only |

No change to `models.py`, `config.py`, `collector_graphql.py`, `sampling.py`,
`validation.py`, `collector.py`, or any report/CLI module.

## 7. Task breakdown

- [ ] `PreflightPolicy` + `preflight_policy_from_config`; defaults from models constants (LREQ-ID-030).
- [ ] `select_preflight_identities`, `PreflightIdentity`, `PreflightSelection`; deterministic order, two-asset/five-category minimum, reduced coverage, shortfall, unique dedup (LREQ-ID-010).
- [ ] `PreflightObservation` carrying the Chunk 5 `EnrichmentObservationDraft`; map `EnrichmentResult`/draft to distinct per-operation outcomes, identity match, correlation mode, endpoint signature, mapping-rule version (LREQ-ID-020).
- [ ] `graphql_endpoint_signature` in `pipeline.py` only, frozen `"<endpoint>#<version>"` form (LREQ-ID-040).
- [ ] `compute_preflight_rates` over unique identities with `None`-on-zero-attempted and the `other_failed` partition (LREQ-ID-040).
- [ ] `evaluate_preflight_gate` and `bulk_enrichment_allowed` with boundary semantics (LREQ-ID-030/040).
- [ ] `run_identity_preflight`: select → one `enrich_asset` per unique identity → rates → gate → persist-before-return → non-clobbering page-view init → mark run failed on `FAILED` with `completed_at_utc` omitted (LREQ-ID-020/040).
- [ ] `IdentityPreflightSummary` + deterministic `to_json` with the frozen §5.5 key set; `persist_preflight`; `mark_preflight_selected` (LREQ-ID-040).
- [ ] Tests + traceability entries (§9, `LREQ-ID-*` markers only); run `python -m niche_scout.tools.validate_traceability`.

## 8. Edge cases and invariants

From dependency map lines 188–191 and the §3 Gate block:

- At least 2 assets from 5 categories where possible; reduced coverage and asset shortfall recorded otherwise (LREQ-ID-010).
- A category with fewer than 2 sampled assets never satisfies the two-asset minimum and contributes no preflight identity (LREQ-ID-010).
- Categories with overlapping sampled identities count each shared identity **once** in the denominator; overlap never inflates attempted/successful/mismatch counts (LREQ-ID-040).
- Zero attempted identities → `insufficient`, both rates `null` (not `0.0`) (LREQ-ID-040).
- Request-ID rejection, incompatible returned identity, page-view package mismatch, invalid correlation mode, and either-operation partial success are each independently represented; one failed operation does not hide the other (LREQ-ID-020, dependency map line 189).
- A failed preflight marks the run `failed`; it is not downgraded to an informational warning (gate line 720). `insufficient` blocks enrichment but is not marked failed in 6A (SRS-lean:408–410; map:720 says "a failed preflight").
- Successful preflight responses count toward enrichment exactly once (gate line 718) and are reused by 6B.
- Preflight status, summary, and observations are persisted before the gate returns (gate line 723), and **before** the run is marked failed — never the reverse; observation rows are never rolled back or deleted on failure (A4). A zero-observation `insufficient` run is a persisted, readable state.
- `page_view_semantics_status` is never clobbered: `validated_cumulative` and `contradicted` are left untouched; `unvalidated` is written only from a different current value (Q3).
- No credential, header value, cookie, or response body appears in any persisted JSON (LREQ-SEC-010/020).
- `float64`, unrounded; rounding is display-only.
- Runs of 8–20 categories provisional / <8 rejected is Chunk 10; 6A imposes no category-count rejection of its own.

## 9. Test plan

Test file: `tests/test_identity_preflight.py`. Fixtures/golden vectors:
`tests/fixtures/identity_preflight_vectors.py` (inert data: `RunSamplingResult`
builders, hand-built `EnrichmentResult`/`EnrichmentObservationDraft` objects, and
injected transports — no live network). Every test carries
`@pytest.mark.lreq("LREQ-ID-...")` — **`LREQ-ID-*` markers only**. Parameterized
tests map by base node ID (see `tests/AGENTS.md`).

**Q4 ruling applied.** No 6A node carries `LREQ-TST-040` or `LREQ-TST-080`;
both are deferred to Chunk 13 (matrix rows 130 and 134 give Chunk 13 primary
ownership; 6A is only *supporting* for `LREQ-TST-040`). The "Matrix type" column
below is **informational test-type classification only** (dependency map lines
70–73's "Required tests" column), not a marker assignment.

| Test node ID | LREQ marker(s) | Matrix type (informational) | Gate bullet it fails if violated |
|---|---|---|---|
| `test_select_preflight_identities_two_assets_five_categories` | LREQ-ID-010 | LREQ-TST-080 | selection minimum |
| `test_select_preflight_identities_reduced_coverage_and_shortfall` | LREQ-ID-010 | LREQ-TST-080 | reduced coverage |
| `test_select_preflight_one_asset_category_not_counted` | LREQ-ID-010 | LREQ-TST-080 | two-asset minimum |
| `test_select_preflight_overlap_dedups_identities` | LREQ-ID-010 | LREQ-TST-080 | line 721 (denominator) |
| `test_preflight_policy_defaults_and_config_read` | LREQ-ID-030 | LREQ-TST-080 | LREQ-ID-030 |
| `test_compute_preflight_rates_unique_identity_denominator` | LREQ-ID-040 | LREQ-TST-080 | line 721 |
| `test_compute_preflight_rates_zero_attempted_null_rates` | LREQ-ID-040 | LREQ-TST-080 | line 719 |
| `test_gate_zero_attempted_is_insufficient` | LREQ-ID-040 | LREQ-TST-080 | line 719 |
| `test_gate_below_min_success_rate_fails` | LREQ-ID-040 | LREQ-TST-080 | line 717 |
| `test_gate_above_max_conflict_rate_fails` | LREQ-ID-040 | LREQ-TST-080 | line 717 |
| `test_gate_exactly_min_success_rate_passes` | LREQ-ID-030 | LREQ-TST-080 | boundary |
| `test_gate_exactly_max_conflict_rate_passes` | LREQ-ID-030 | LREQ-TST-080 | boundary |
| `test_run_identity_preflight_uses_chunk5_adapter_per_unique_identity` | LREQ-ID-020 | LREQ-TST-040 | line 722 |
| `test_run_identity_preflight_preserves_distinct_operation_outcomes` | LREQ-ID-020 | LREQ-TST-040 | LREQ-ID-020 |
| `test_preflight_identity_failure_modes` (parametrized: request-id rejection, identity mismatch, page-view package mismatch, invalid correlation mode, partial success, transport failure) | LREQ-ID-020 | LREQ-TST-040 | LREQ-ID-020 |
| `test_successful_preflight_counts_toward_enrichment_once` | LREQ-ID-040 | LREQ-TST-080 | line 718 |
| `test_preflight_persisted_before_gate_returns` | LREQ-ID-040 | LREQ-TST-080 | line 723 |
| `test_failed_preflight_marks_run_failed_not_warning` | LREQ-ID-040 | LREQ-TST-080 | line 720 |
| `test_failed_preflight_blocks_bulk_enrichment` | LREQ-ID-040 | LREQ-TST-080 | line 717 |
| `test_insufficient_preflight_blocks_bulk_enrichment` | LREQ-ID-040 | LREQ-TST-080 | line 719 |
| `test_insufficient_preflight_does_not_mark_run_failed` | LREQ-ID-040 | LREQ-TST-080 | Q2 ruling |
| `test_failed_preflight_summary_has_counts_endpoint_mapping_diagnostic` | LREQ-ID-040 | LREQ-TST-080 | LREQ-ID-040 line 388 |
| `test_endpoint_signature_form` (resolved, §12 Q1) | LREQ-ID-040 | LREQ-TST-080 | endpoint signature |
| `test_mark_preflight_selected_flips_rows_true` | LREQ-ID-010 | LREQ-TST-080 | selection persisted |
| `test_preflight_observations_are_redacted` | LREQ-ID-040 | LREQ-TST-040 | LREQ-SEC-010/020 |
| `test_page_view_semantics_not_clobbered_when_validated` | LREQ-ID-040 | LREQ-TST-080 | Q3 ruling (non-clobber) |
| `test_page_view_semantics_not_clobbered_when_contradicted` | LREQ-ID-040 | LREQ-TST-080 | Q3 ruling (non-clobber) |

Golden vectors / hand-computed expectations:
- **Denominator golden:** a `RunSamplingResult` where identity `A` appears in
  two categories and identity `B` in one; selection of both categories with 2
  assets each must yield `attempted_unique_identities == 2`, not 3; one
  comparison fails on `A` → `conflicting == 1`, `success_rate == 0.5`,
  `conflict_rate == 0.5`.
- **Zero-attempted golden:** empty selection → `success_rate is None`,
  `conflict_rate is None`, status `insufficient`, zero observation rows.
- **Boundary golden:** 9 success / 1 other-fail of 10 → `success_rate == 0.9`
  passes; one conflict of 10 → `conflict_rate == 0.1 > 0.0` fails.
- **Failure diagnostic golden:** counts `10/8/1/1`, signature
  `<endpoint>#1.0.0`, mapping-rule version read from
  `models.IDENTITY_MAPPING_RULE_VERSION` (`"1.0.1"`), redacted summary present,
  no credential substring.
- **Non-clobber golden:** a run pre-seeded `validated_cumulative`, and separately
  `contradicted`, must be unchanged after `persist_preflight`; a fresh run gets
  `unvalidated`.

`tests/traceability.json` entries (node ID → LREQ list, `LREQ-ID-*` only),
example:
`"tests/test_identity_preflight.py::test_gate_zero_attempted_is_insufficient": ["LREQ-ID-040"]`.
Each new node gets one entry; parameterized tests use the base node ID.

## 10. Definition of done (gate)

Copied verbatim from `Documents/requirements-dependency-map.md` §3, lines
715–723 (the `Gate:` header plus its seven bullets):

```text
Gate:

- Failed preflight prevents bulk enrichment.
- Successful preflight responses count toward enrichment exactly once.
- Zero attempted identities produces `insufficient`, not zero success.
- A failed preflight marks the run failed and does not become an informational-only warning.
- Preflight rates use unique identities, not category references.
- Preflight executes the normal GraphQL request through the reusable Chunk 5 adapter; Chunk 5 supplies protocol behavior, while Chunk 6A supplies controlled execution and gate policy.
- Preflight status, summary, and observations are persisted before the gate returns.
```

## 11. Explicit prohibitions

- `pipeline.py` MUST NOT re-implement GraphQL request construction, correlation,
  response validation, or retry classification; it calls `enrich_asset` and
  consumes `EnrichmentResult`/`EnrichmentObservationDraft` (gate line 722).
- MUST NOT import or perform raw HTTP, `requests`, `urllib`, or a live network
  call; `transport` is always caller-injected (fixtures only).
- MUST NOT add `graphql_endpoint_signature` (or any other 6A symbol) to
  `collector_graphql.py`; it lives in `pipeline.py` only (Q1).
- MUST NOT issue more than one `enrich_asset` call per unique preflight
  identity, and MUST NOT perform bulk enrichment (Chunk 6B).
- MUST NOT use category references or per-category counts as the preflight rate
  denominator (gate line 721).
- MUST NOT represent zero attempted identities as `0.0` success or `failed`;
  it is `insufficient` with `null` rates (gate line 719).
- MUST NOT mark an `insufficient` run `failed` in 6A (Q2).
- MUST NOT downgrade a failed preflight to an informational-only warning (gate
  line 720).
- MUST NOT return from `run_identity_preflight` before status, summary, and
  observations are persisted (gate line 723), and MUST NOT mark the run failed
  before those writes, nor roll back or delete observation rows on failure (A4).
- MUST NOT build an `EnrichmentObservationRecord` from anything but
  `PreflightObservation.draft.to_record(run_id)` (A5).
- MUST NOT clobber `page_view_semantics_status` when it is
  `validated_cumulative` or `contradicted` (Q3).
- MUST NOT pass `completed_at_utc` from `update_run_status`; the terminal
  timestamp is Chunk 10's (Q2/A7).
- MUST NOT write a credential, header value, cookie, or response body into any
  persisted JSON or diagnostic summary (LREQ-SEC-010/020).
- MUST NOT invent a constant, threshold, weight, field name, endpoint string, or
  mapping-rule version: only models/SRS §14 values, read from the constants.
- MUST NOT read the clock in any pure helper; `retrieved_at_utc` is a parameter.
- MUST NOT change any table, column, DDL string, enum, or index; the only
  `database.py` change is the additive `mark_preflight_selected` method.

## 12. Rulings applied (2026-09-20)

All five §12 questions and audit items A1–A7 are resolved below. A3 was refuted
and replaced by A5.

### Q1 — Endpoint signature (ruling: recommendation accepted; separator is an assumption)

Adopted `graphql_endpoint_signature(endpoint: str = GRAPHQL_BATCH_ENDPOINT, *,
endpoint_contract_version: str = ENDPOINT_CONTRACT_VERSION) -> str` returning
`f"{endpoint}#{endpoint_contract_version}"`, in `pipeline.py` **only** (never
added to `collector_graphql.py`). The `#` separator is normative nowhere; it is
recorded as assumption A below. The literal form and the summary key
`graphql_endpoint_signature` are frozen in `interfaces/chunk-6A.md`. §5.6 and
`test_endpoint_signature_form` are **resolved** (no longer provisional).

### Q2 — Run-failed marking (ruling: 6A owns the transition)

6A calls `repository.update_run_status(run_id, RunStatus.FAILED.value)` when the
disposition is `FAILED`. Chunk 10 never downgrades. **No-downgrade cross-chunk
contract (for Chunk 10):** Chunk 10's "Mark the run completed or failed" step
SHALL NOT overwrite an existing `failed` with `completed`, and SHALL leave
`insufficient` runs non-completed. **`completed_at_utc` (A7):** 6A calls
`update_run_status` with `completed_at_utc` **omitted** — the column is
nullable, `database.py:1122–1135` leaves it unchanged on `None`, Chunk 10 owns
the terminal timestamp, and `pipeline.py` reads no clock. **`insufficient`
decision:** `insufficient` does not mark the run failed in 6A; it blocks
enrichment and is finalized by Chunk 10 (SRS-lean:408–410 is a third
disposition; map:720 says "a failed preflight").

### Q3 — `page_view_semantics_status` (ruling: non-clobbering init; re-based citation)

Basis corrected: `interfaces/chunk-00.md:373` is
`MetricInput.page_view_semantics_status` (a pure-metrics default), **not**
`RunRecord`. `models.py:362` declares `page_view_semantics_status: str` with no
default; `database.py:101` is `TEXT NOT NULL` with no DDL `DEFAULT`; `insert_run`
inserts whatever `RunRecord` carries. Nothing already defaults it — the run-row
inserter (Chunk 10, step 3) seeds it.

**Carried hand-off:** `interfaces/chunk-05.md:575–591` and the Chunk 5 plan §12
Q5 (lines 2499–2505) carry "Chunk 6A initializes the run-level value" to 6A,
citing retired `SRS-revision2.md:196` and the 6A dependency-map row, while 6A's
own Implement list (`requirements-dependency-map.md:691–699`) omits it.

**Behaviour ruled:** 6A writes `unvalidated` **only when the current value is
not `validated_cumulative`/`contradicted`** (read via `get_run`, then
`update_run_preflight(page_view_semantics_status=...)`). SRS-lean:639–642 makes
it the endpoint semantic-validation state and forbids deriving it from an
asset-level `page_views_status = "error"`. The test is a **non-clobber** test on
a run pre-seeded `validated_cumulative` and separately `contradicted`; a test
starting from a fresh row would prove only Chunk 10's seed. The former
`test_page_view_semantics_initialized` is renamed to
`test_page_view_semantics_not_clobbered_when_validated` /
`..._when_contradicted` (renaming was free before freeze) and marked resolved.
This item is re-marked **LREQ-ID-040** (a preflight-persistence invariant);
**no lean LREQ names this initialization at all**, so no marker is borrowed.

### Q4 — Test markers (ruling: defer both to Chunk 13)

No 6A node carries `LREQ-TST-040` or `LREQ-TST-080`. Evidence: matrix rows 130
and 134 give **Chunk 13** primary ownership of both, with 6A only *supporting*
for `LREQ-TST-040`; Chunk 5's operator-confirmed ruling attaches neither (Chunk
5 plan lines 229–233 and §12 Q6 at lines 2561–2566, deferred to Chunk 13 as a
marker-edit-only change). The matrix's "Required tests" column (lines 70–73) is
a test-type classification, not a marker assignment. §6, §9, and the header drop
all marker claims; §9 keeps a matrix **type** column as informational. The
existing `tests/test_database.py` `LREQ-TST-080` occurrences (lines 469, 803)
are Chunk 13's marker pass, not 6A's.

### Q5 — Observation persistence timing (ruling: write at preflight time)

The `enrichment_observations` row is written at preflight time; it is the only
per-identity store (`SRS-lean` §6.4; `interfaces/chunk-00.md:353` PK
`(run_id, asset_identity_key)`; `interfaces/chunk-02.md:344–345` upsert rewrites
every non-key column). A row is written for **every non-`insufficient` attempt,
including failures** (map:1003 requires retaining preflight observations on
failure). §5.4 and the §9 tests are resolved accordingly.

### A1 — Frozen summary key set with provenance

§5.5 adds the frozen `identity_preflight_summary_json` key table, each key
labelled SRS-mandated vs plan-derived. SRS fixes exactly one key name:
`graphql_operation_correlation_mode` (SRS-lean:414). SRS-lean:412–413 mandates
the four counts; :388 mandates counts + endpoint signature + mapping-rule
version + redacted diagnostic. The other two keys are aligned to the persisted
vocabulary: `graphql_endpoint_signature` and `identity_mapping_rule_version`
(not `endpoint_signature` / `mapping_rule_version`); §5.5's JSON example is
updated. The column is `NOT NULL` (`database.py:104`), so Chunk 10 must seed a
value at `insert_run` and 6A always overwrites with the full set. **Unverified:**
no dependency-map text names the JSON column; "Chunk 10 renders it / Chunk 11
reads it" is a **forward contract**, not map-stated.

### A2 — "other failed" is an explicit assumption

The SRS never defines `other_failed`. Assumption B below records it. Kept:
identity attempted = successful + conflicting + other_failed; no-observation ⇒
attempted + other_failed; out-of-selection observations ignored. `enrich_asset`
never raises (`interfaces/chunk-05.md:802–805` — a raising transport is caught
as `TRANSPORT_FAILURE`), so the no-observation branch is **defensive, not the
transport path**; a `TRANSPORT_FAILURE` result is therefore `other_failed`,
still attempted.

### A3 — refuted; not applied

`persist_preflight` already takes `run_id: str`, and the summary carries
`graphql_operation_correlation_mode`; no claim that they are missing is made.
The one fix was the `<mode>` placeholder in §5.4 step 1, now
`summary.graphql_operation_correlation_mode`.

### A4 — failed/insufficient read model (recorded)

Grounded in map:1003 ("retain discovery/sample/preflight observations"), :1006
and :1024 (failed-run read model joins runs/discovery/samples/preflight
observations), :1148 (run failed while categories may be `not_rankable`). §8
records the ordering invariant: **persist status + summary + observations, then
mark failed — never the reverse; never roll back or delete observation rows on
failure.** Extended to `insufficient`: zero-observation rows are still a
persisted, readable state.

### A5 (new, replaces A3) — the observation→record path

`persist_preflight` step 2 originally called `draft.to_record(run_id)` on a
`PreflightObservation`, which lacks `graphql_id`, `product_id`,
`rating_average`, `rating_count`, `review_count`, `first_published_date_utc`,
`publisher_json`, `category_json`, `state`, `product_page_views`,
`product_detail_error_summary`, and `page_views_error_summary` (compare
`interfaces/chunk-05.md:649–667`). Rule applied: `PreflightObservation` carries
the `EnrichmentObservationDraft`; `persist_preflight` calls
`PreflightObservation.draft.to_record(run_id)`; `request_metadata_json` is the
draft's value, not a second construction. §5.3 states which preflight-only
fields are not persisted per row (run-level summary / `request_metadata_json`),
and `operation_outcomes_json` is dropped as a restatement of the two statuses.
§5.5 adds the explicit `PreflightObservation` → `EnrichmentObservationRecord`
mapping.

### A6 — mapping-rule version drift

`interfaces/chunk-00.md:115` says `IDENTITY_MAPPING_RULE_VERSION = "1.0.0"` but
`src/niche_scout/models.py:26` is `"1.0.1"`, and the suite/fixtures use
`"1.0.1"` (`tests/fixtures/sampling_persistence_fixtures.py:226`,
`tests/test_collector.py:241`). Rule applied: code reads
`models.IDENTITY_MAPPING_RULE_VERSION`, never a literal; §4 cites
`models.py:26`. **Stale-interface note:** `interfaces/chunk-00.md:115` is stale
and is a doc fix for the lead, not 6A's to make.

### A7 — completed_at_utc; insufficient status

Applied in Q2 and Q3 above.

### Assumptions recorded (not open questions)

- **Assumption A — endpoint signature separator.** The `#` in
  `"<endpoint>#<version>"` is normative nowhere. Basis: retired
  `SRS-revision2.md:334` declares `graphql_endpoint_signature TEXT NOT NULL`
  beside `identity_mapping_rule_version`, with no separate endpoint-version
  column, and `SRS-revision2.md:285` names "endpoint-incompatible" rejection —
  i.e. the value must encode the contract identity, not the bare URL. The Chunk
  5 plan (lines 2344–2348) authorizes the retired document for endpoint details.
- **Assumption B — `other_failed`.** The SRS never defines it; §5.2's partition
  and §5.5's key provenance label it as an assumption.
- **Injected dependencies.** `transport`, `sleep`, and `retrieved_at_utc` are
  always caller-injected, so no test touches the network or the clock.
  `max_conflict_rate` comes from the models constant because SRS §14 exposes only
  three preflight config keys.
