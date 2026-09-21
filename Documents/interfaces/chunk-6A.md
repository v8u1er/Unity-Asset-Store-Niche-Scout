# Chunk 6A — Identity preflight planner and gate (public interface)

Status: VERIFIED
Source plan: `Documents/plans/chunk-6A-identity-preflight-planner-and-gate.md`
(Status: FROZEN; ruled 2026-09-20). This file is the public contract downstream
chunks (6B, 10, 13) build against. It reproduces §5 of the frozen plan verbatim.

Verified at: 2026-09-21, branch `chunk-6-verify` (from `main` `4f51bf1`).
`spec-reviewer` `VERDICT: PASS`; the lead re-ran `python -m pytest -q` (400
passed), `python -m pytest tests/test_identity_preflight.py -q` (46 passed),
`python -m niche_scout.tools.validate_traceability` (exit 0; 386 matrix nodes,
89 defined LREQ IDs), `python -m niche_scout.tools.check_import_boundaries`
(exit 0), and `ruff check` / `ruff format --check` (clean) on the 6A files. Gate
`GATE: PASSED` re-affirmed. See `Documents/runs/chunk-6A.md` "Reverification
pass" and `Documents/runs/chunk-6-verify.md` for evidence and recorded Minors.

This chunk is orchestration plus one additive persistence method. It plans and
executes a deterministic identity preflight through the Chunk 5 adapter,
computes unique-identity success/conflict rates, persists status + summary +
observations before the gate returns, and owns the `failed` run transition. It
performs no bulk enrichment, re-implements no GraphQL protocol behavior, and
reads no clock.

Additive only. Nothing in Chunk 0/1/2/4A/4B/5 names is redefined or shadowed.
All new symbols live in `src/niche_scout/pipeline.py` except the one additive
`database.py` method in §5.4a. `graphql_endpoint_signature` lives in
`pipeline.py` **only** and is not added to `collector_graphql.py`.

---

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
**assumption**; the SRS never defines `other_failed` (see plan §12 A2).

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
    separator is an **assumption**, not SRS text (see plan §12 assumption A). It
    is derived only from the Chunk 5 `GRAPHQL_BATCH_ENDPOINT` and the models
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

---

## Frozen `identity_preflight_summary_json` key table

Reproduced from §5.5 as the frozen contract Chunk 6B and Chunk 10 consume. The
full table with provenance is in §5.5; the frozen key set is:

```text
status
attempted_unique_identities
successful_unique_identities
conflicting_unique_identities
other_failed_unique_identities
success_rate
conflict_rate
graphql_operation_correlation_mode
graphql_endpoint_signature
identity_mapping_rule_version
selected_category_count
eligible_category_count
reduced_coverage
category_shortfall
asset_shortfall
diagnostic_summary_json
```

Serialization is deterministic:
`json.dumps(value, sort_keys=True, separators=(",", ":"))`. The column is
`TEXT NOT NULL`; Chunk 10 seeds it at `insert_run` and 6A always overwrites it
with the full set. SRS fixes exactly one key name
(`graphql_operation_correlation_mode`, SRS-lean:414); `graphql_endpoint_signature`
and `identity_mapping_rule_version` are aligned to the persisted vocabulary.
