# Chunk 9A — Pre-sensitivity evidence and immutable base candidates (public interface)

Status: VERIFIED
Source: `Documents/plans/chunk-9A-pre-sensitivity-evidence-and-base-candidates.md` §5 (Status: FROZEN, 2026-09-21), reproduced as the frozen public contract.
Implementation: `src/niche_scout/scoring.py` (additive surface; Chunk 0/8 names unchanged).

## 1. Module and boundary rules

| Item | Kind | Rule |
|---|---|---|
| `src/niche_scout/scoring.py` | **Pure** | Reason vocabularies, pre-sensitivity input/decision structures, the base-candidate rule, the preliminary evidence state, and the preliminary rankability state only. |

- Purity: `src/niche_scout/scoring.py` must not import `collector*`, `database`,
  `pipeline`, `report`, `cli`, or `config`; it performs no I/O, no `sqlite3`, no
  network, and no filesystem access, and never reads the clock
  (LREQ-ARCH-010/020). It adds only `enum.StrEnum` plus `models` names.
- Determinism: reason tuples are emitted in the fixed orders below;
  `base_rankable_candidates` follows `all_metrics` order; no set/dict iteration
  determines any output; no randomness (LREQ-ARCH-030).
- Null/zero/unavailable stay distinct: a `None` component means unavailable and is
  never converted to `0.0`; a `FieldUsableCounts` value of `0` is a legitimate
  explicit count, not "missing".
- `ValueError` is raised only for caller/policy breaches — misaligned input
  sequences, or a non-finite/out-of-range threshold — never for a product-level
  value.

## 2. Typed structures

```python
from enum import StrEnum  # Python 3.11+; models.py uses (str, Enum) but the new
                         # reason vocabularies are declared StrEnum per R4.

class NotRankableReason(StrEnum):
    UNRECOVERABLE_DATA_INTEGRITY_ERROR = "unrecoverable_data_integrity_error"
    DISCOVERY_FILTER_UNVERIFIED = "discovery_filter_unverified"
    UNRESOLVED_OR_CONFLICTING_IDENTITY = "unresolved_or_conflicting_identity"
    IDENTITY_PREFLIGHT_FAILED = "identity_preflight_failed"
    COMPETITION_UNBOUNDED_OR_MATERIAL_FAILURE = (
        "competition_unbounded_or_material_failure"
    )
    PAGE_VIEW_SEMANTICS_CONTRADICTED = "page_view_semantics_contradicted"
    REQUIRED_DEMAND_DATA_UNAVAILABLE = "required_demand_data_unavailable"
    RECENT_SUPPLY_MINIMUM_NOT_MET = "recent_supply_minimum_not_met"
    QUALITY_UNAVAILABLE = "quality_unavailable"
    NO_VALID_LEAVE_ONE_OUT_REFERENCE = "no_valid_leave_one_out_reference"
    FIELD_REFERENCE_SUPPORT_INSUFFICIENT = "field_reference_support_insufficient"

#: Fixed emission order; sequence-valued results list every fired reason in this
#: order regardless of input order. This tuple defines output order only; it does
#: not assert that one condition is logically earlier than another
#: (LREQ-ARCH-030 determinism).
NOT_RANKABLE_REASON_ORDER: tuple[NotRankableReason, ...] = (
    NotRankableReason.UNRECOVERABLE_DATA_INTEGRITY_ERROR,
    NotRankableReason.DISCOVERY_FILTER_UNVERIFIED,
    NotRankableReason.UNRESOLVED_OR_CONFLICTING_IDENTITY,
    NotRankableReason.IDENTITY_PREFLIGHT_FAILED,
    NotRankableReason.COMPETITION_UNBOUNDED_OR_MATERIAL_FAILURE,
    NotRankableReason.PAGE_VIEW_SEMANTICS_CONTRADICTED,
    NotRankableReason.REQUIRED_DEMAND_DATA_UNAVAILABLE,
    NotRankableReason.RECENT_SUPPLY_MINIMUM_NOT_MET,
    NotRankableReason.QUALITY_UNAVAILABLE,
    NotRankableReason.NO_VALID_LEAVE_ONE_OUT_REFERENCE,
    NotRankableReason.FIELD_REFERENCE_SUPPORT_INSUFFICIENT,
)

class ProvisionalReason(StrEnum):
    RUN_BELOW_STRONG_REFERENCE = "run_below_strong_reference"
    INCOMPLETE_BREADTH_FALLBACK = "incomplete_breadth_fallback"
    COVERAGE_BELOW_STRONG = "coverage_below_strong"

PROVISIONAL_REASON_ORDER: tuple[ProvisionalReason, ...] = (
    ProvisionalReason.RUN_BELOW_STRONG_REFERENCE,
    ProvisionalReason.INCOMPLETE_BREADTH_FALLBACK,
    ProvisionalReason.COVERAGE_BELOW_STRONG,
)

class PreSensitivityRankabilityState(StrEnum):
    NOT_RANKABLE = "not_rankable"
    PROVISIONAL = "provisional"
    RANKABLE = "rankable"

PRE_SENSITIVITY_RANKABILITY_STATES: tuple[PreSensitivityRankabilityState, ...] = (
    PreSensitivityRankabilityState.NOT_RANKABLE,
    PreSensitivityRankabilityState.PROVISIONAL,
    PreSensitivityRankabilityState.RANKABLE,
)

class PreSensitivityEvidenceState(StrEnum):
    SUFFICIENT = "sufficient"
    PROVISIONAL_ONLY = "provisional_only"
    INSUFFICIENT = "insufficient"

@dataclass(frozen=True, slots=True)
class PreSensitivityCategoryInput:
    category: str
    discovery_status: DiscoveryStatus
    discovery_filter_verified: bool
    discovery_unresolved_identity_count: int
    discovery_conflict_count: int
    discovery_bounded_by_verified_total: bool
    page_view_semantics_status: PageViewSemanticsStatus
    breadth_source: BreadthSource
    breadth_completeness_status: BreadthCompletenessStatus
    demand_stratum_eligibility_coverage: float
    recent_supply_stratum_eligibility_coverage: float
    quality_stratum_eligibility_coverage: float
    reference_size: int
    field_usable_counts: FieldUsableCounts

@dataclass(frozen=True, slots=True)
class PreSensitivityDecision:
    category: str
    evidence_state: PreSensitivityEvidenceState
    rankability_state: PreSensitivityRankabilityState
    not_rankable_reasons: tuple[NotRankableReason, ...]
    provisional_reasons: tuple[ProvisionalReason, ...]
    base_rankable: bool

@dataclass(frozen=True, slots=True)
class BaseCandidateSet:
    base_rankable_candidates: tuple[str, ...]
    decisions: tuple[PreSensitivityDecision, ...]
    run_category_count: int
```

Notes:

- `PreSensitivityEvidenceState` and `PreSensitivityRankabilityState` are distinct
  from `models.EvidenceGrade` and `models.RankabilityStatus`: they are
  pre-sensitivity and are never assigned by Chunk 9A to a persisted
  `evidence_grade` / `rankability_status` field (R2).
- `NOT_RANKABLE_REASON_ORDER` / `PROVISIONAL_REASON_ORDER` define output order only.

## 3. Public functions

```python
def field_reference_support_passes(
    counts: FieldUsableCounts,
    *,
    demand_available: bool,
    competition_available: bool,
    recent_supply_available: bool,
    quality_available: bool,
) -> bool: ...

def not_rankable_reasons(
    score: ScoreResult,
    evidence: PreSensitivityCategoryInput,
    *,
    identity_preflight_status: IdentityPreflightStatus,
) -> tuple[NotRankableReason, ...]: ...

def provisional_reasons(
    score: ScoreResult,
    evidence: PreSensitivityCategoryInput,
    *,
    run_category_count: int,
    min_required_component_coverage: float = MIN_REQUIRED_COMPONENT_COVERAGE,
) -> tuple[ProvisionalReason, ...]: ...

def pre_sensitivity_rankability_state(
    not_rankable: Sequence[NotRankableReason],
    provisional: Sequence[ProvisionalReason],
    *,
    base_rankable: bool,
) -> PreSensitivityRankabilityState: ...

def evaluate_pre_sensitivity_evidence(
    score: ScoreResult,
    evidence: PreSensitivityCategoryInput,
    *,
    identity_preflight_status: IdentityPreflightStatus,
    run_category_count: int,
    min_required_component_coverage: float = MIN_REQUIRED_COMPONENT_COVERAGE,
) -> PreSensitivityDecision: ...

def build_base_rankable_candidates(
    all_metrics: Sequence[CategoryRawMetrics],
    inputs: Sequence[PreSensitivityCategoryInput],
    scores: Sequence[ScoreResult],
    *,
    identity_preflight_status: IdentityPreflightStatus,
    min_required_component_coverage: float = MIN_REQUIRED_COMPONENT_COVERAGE,
) -> BaseCandidateSet: ...
```

The keyword-only availability flags of `field_reference_support_passes` are
derived by the caller from the four `ScoreResult` component fields
(`component_d is not None`, etc.); the pure function never reads a `ScoreResult`
itself.

## 4. Semantics

### 4.1 `field_reference_support_passes` (LREQ-EVD-020 line 993; LREQ-SCR-010/-020/-030/-040)

Field-specific reference support is required only for the raw fields each
**available** component consumes, per the SRS §8.2 mapping:

- Demand (`D`) ← `demand_per_asset_raw`, `demand_median_raw`
- Competition (`C`) ← `breadth_raw`
- Recent supply (`R`) ← `recent_share_raw`, `median_age_raw`
- Quality (`Q`) ← `quality_raw`

Returns `True` iff for **every** available component, every raw field it consumes
has `counts.<field> > 0`. An unavailable component contributes **no** requirement:
its fields may be `0` without failing the predicate. The vacuous case is `True`:
all four components unavailable → no requirement to satisfy. That category is
already `not_rankable` through the component-availability reasons, so vacuous
truth can never promote it. `FIELD_REFERENCE_SUPPORT_INSUFFICIENT` is emitted only
when this predicate returns `False`.

### 4.2 `not_rankable_reasons` (LREQ-EVD-020 lines 980–987)

Returns the subset of `NOT_RANKABLE_REASON_ORDER` that fires, in that order, and is
empty for a category with no `not_rankable` condition. All facts are explicit
inputs; nothing is re-derived.

- `UNRECOVERABLE_DATA_INTEGRITY_ERROR`: `evidence.discovery_status is
  DiscoveryStatus.REQUEST_FAILED` or `is DiscoveryStatus.PAGE_FAILED` (R7;
  LREQ-EXT-050 line 263).
- `DISCOVERY_FILTER_UNVERIFIED`: `not evidence.discovery_filter_verified`, or
  `evidence.discovery_status` is `FILTER_UNVERIFIED` or `CATEGORY_MISMATCH`
  (LREQ-EXT-090 lines 279–281).
- `UNRESOLVED_OR_CONFLICTING_IDENTITY`: `evidence.discovery_status is
  IDENTITY_INCOMPLETE`, or `evidence.discovery_unresolved_identity_count > 0`, or
  `evidence.discovery_conflict_count > 0`.
- `IDENTITY_PREFLIGHT_FAILED`: `identity_preflight_status is
  IdentityPreflightStatus.FAILED` **or** `is
  IdentityPreflightStatus.INSUFFICIENT` (Q4: `INSUFFICIENT` is treated as a
  preflight failure for the category). The distinct run-level value is preserved as
  the input fact; no separate reason code is added for `INSUFFICIENT`, and run
  status stays a separate field.
- `COMPETITION_UNBOUNDED_OR_MATERIAL_FAILURE`: exactly when `score.competition is
  None` (Q3), the pure-layer expression of LREQ-MET-070's competition-unavailability
  conditions (lines 764–766).
- `PAGE_VIEW_SEMANTICS_CONTRADICTED`: `evidence.page_view_semantics_status is
  PageViewSemanticsStatus.CONTRADICTED` (LREQ-SCR-050 line 949).
- `REQUIRED_DEMAND_DATA_UNAVAILABLE`: `score.component_d is None`.
- `RECENT_SUPPLY_MINIMUM_NOT_MET`: `score.component_r is None`.
- `QUALITY_UNAVAILABLE`: `score.component_q is None`.
- `NO_VALID_LEAVE_ONE_OUT_REFERENCE`: `evidence.reference_size <= 0` (no peer
  category exists).
- `FIELD_REFERENCE_SUPPORT_INSUFFICIENT`: `not field_reference_support_passes(
  evidence.field_usable_counts, demand_available=score.component_d is not None,
  competition_available=score.component_c is not None, recent_supply_available=
  score.component_r is not None, quality_available=score.component_q is not None)`
  (R11). Emitted **last**; distinct from the `provisional` coverage policy.

### 4.3 `provisional_reasons` (LREQ-EVD-030 lines 996–1001; LREQ-MET-070)

Returns the subset of `PROVISIONAL_REASON_ORDER` that fires, in that order — the
pre-sensitivity clauses of LREQ-EVD-030 only:

- `RUN_BELOW_STRONG_REFERENCE`: `run_category_count <
  STRONG_REFERENCE_CATEGORY_COUNT` (the 8–20 clause and the fewer-than-21 clause).
- `INCOMPLETE_BREADTH_FALLBACK`: `evidence.breadth_completeness_status is
  BreadthCompletenessStatus.INCOMPLETE_ESTIMATE`. It fires **whenever** the fallback
  status holds, including when `discovery_bounded_by_verified_total` is `True`
  (Q3): the reason is about the fallback estimate itself, not about whether a
  verified total bounded the discovery.
- `COVERAGE_BELOW_STRONG`: at least one of the three
  `*_stratum_eligibility_coverage` values is `< STRONG_COMPONENT_COVERAGE` while
  `>= min_required_component_coverage` ("acceptable but below the strong policy").
  A coverage strictly below `min_required_component_coverage` is not a provisional
  reason: the corresponding component is already `None` and the category is
  `not_rankable` under an earlier reason.
- No `sensitivity_high` member exists; Chunk 9B owns that clause.

### 4.4 `pre_sensitivity_rankability_state` (LREQ-EVD-010)

The pure state transition: `NOT_RANKABLE` if `not_rankable` is non-empty; else
`RANKABLE` if `base_rankable` and `provisional` is empty; else `PROVISIONAL`. The
result is always one of the three `PRE_SENSITIVITY_RANKABILITY_STATES`; it is
**not** a `models.RankabilityStatus` instance (R2).

### 4.5 `evaluate_pre_sensitivity_evidence` (LREQ-EVD-020/-030)

Per-category wiring: compute `base_rankable` from the base-candidate rule below,
then `not_rankable_reasons`, `provisional_reasons`, then
`pre_sensitivity_rankability_state`. `evidence_state` is `INSUFFICIENT` when
`not_rankable` is non-empty, else `PROVISIONAL_ONLY` when `provisional` is
non-empty, else `SUFFICIENT`. The function does not read or accept any sensitivity
input (LREQ-EVD-020 line 994).

### 4.6 Base-candidate rule (LREQ-EVD-020 lines 989–994; R1)

A category is `base_rankable` iff **all** hold:

1. `len(all_metrics) >= STRONG_REFERENCE_CATEGORY_COUNT` (21) for the run;
2. `not_rankable_reasons(...)` is empty;
3. `score.available_component_count == 4` (all four components available);
4. each of demand/recent-supply/quality coverage `>=
   min_required_component_coverage`;
5. `evidence.reference_size > 0`;
6. `field_reference_support_passes(...)` is `True` (R11). When all four components
   are available (condition 3), the flags are all `True` and the predicate reduces
   to "every one of the six consumed raw fields has at least one usable peer
   value".

A run with 8–20 categories therefore yields an empty `base_rankable_candidates`
(R1). A category can be `base_rankable` and still `PROVISIONAL` (e.g. coverage in
`[0.50, 0.80)`), because base candidacy is necessary but not sufficient for final
rankable.

### 4.7 `build_base_rankable_candidates` — alignment and ordering (LREQ-EVD-020; LREQ-ARCH-030)

Run-level, pure. **Caller obligation (R3):** `all_metrics` must be passed in the
caller's deterministic canonical category order (the same order `score_category`
consumes); `inputs` and `scores` must be 1:1 aligned with `all_metrics` by
category. The returned `base_rankable_candidates` is the `tuple[str, ...]` of
`all_metrics` categories whose decision has `base_rankable=True`, **in `all_metrics`
order**; `decisions` is also in `all_metrics` order; `run_category_count =
len(all_metrics)`. `ValueError` when the three sequences differ in length or a
category at an index does not match across them. The function never mutates a
`ScoreResult` and never changes `market_opportunity_score`, `score_state`, or any
component (LREQ-EVD-020 line 994); it reads them only.

### 4.8 Null and edge behaviour

- `field_usable_counts` values are counts, so `0` is a legitimate explicit value,
  not "missing".
- `reference_size` may be `0` (a one-category run) →
  `NO_VALID_LEAVE_ONE_OUT_REFERENCE`.
- A `None` component means unavailable and is never converted to `0.0`.
- `discovery_bounded_by_verified_total` is a boolean fact, not a metric.

## 5. Explicitly not produced here

- Final `evidence_grade` and final `rankability_status`: assigned by **Chunk 9B**
  and persisted by **Chunk 10**. Chunk 9A assigns neither and writes no record
  field.
- Sensitivity policies, top-3/top-5 stability, rank displacement, warning
  thresholds, and sensitivity-driven provisional demotion (**Chunk 9B**;
  LREQ-SEN-010/-020/-030/-040). Chunk 9A's LREQ-SEN-030 role is only the supporting
  contract: the immutable candidate set plus the pre-sensitivity rankability state
  that sensitivity evaluates over. No stability statistic and no warning is
  computed here (R9); no `sensitivity_high` provisional clause exists (Chunk 9B
  owns it).
- LREQ-EVD-040 (final rankable) and LREQ-EVD-050 (final evidence grade):
  **Chunk 9B**.
- The orchestration-status half of LREQ-EVD-020: **Chunk 10** (`pipeline.py`);
  Chunk 9A accepts caller-supplied statuses and never derives them (R10).
- Rejection of runs with fewer than `MIN_CATEGORIES_PER_RUN` categories:
  LREQ-CLI-040 / **Chunk 12**. Chunk 9A does not raise for a small run; it returns
  an empty candidate set with provisional/not-rankable decisions (R1).
- Re-derivation of `DiscoveryStatus`, identity counts, or page-view semantics from
  payloads: Chunks 1/3/5/6A classify; Chunk 9A consumes already-persisted values as
  explicit typed parameters (R7, R10).
- Persistence, SQLite, JSON serialization, logging, report, CLI: **Chunks 10/11/12**.
- Any new numeric threshold or configurable weight: constants come from `models.py`
  (SRS §9.1 lines 1013–1017); no new threshold is invented (R5).

Consumers: **Chunks 9B, 10, 11, 12**.