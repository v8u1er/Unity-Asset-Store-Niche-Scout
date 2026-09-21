# Chunk 9A — Pre-sensitivity evidence checks and immutable base candidates

Status: FROZEN (2026-09-21)
Depends on (frozen interfaces required before this plan can be trusted):
  Documents/interfaces/chunk-08.md (`ScoreResult`, `ComponentValues`,
  `FieldUsableCounts`, `LeaveOneOutReference`, `balanced_composite`,
  `score_category`; rankability/evidence left at Chunk 0 defaults)
  Documents/interfaces/chunk-7B.md (`CategoryRawMetrics`, `RawMetricBundle`,
  breadth provenance; stratum eligibility coverage fields)
  Documents/interfaces/chunk-05.md (run-level `PageViewSemanticsStatus` consumed,
  never detected)
  Documents/interfaces/chunk-03.md (`DiscoveryStatus` vocabulary and page-failure
  semantics)
  Documents/interfaces/chunk-6A.md (`IdentityPreflightStatus` vocabulary and the
  run-level preflight gate)
  Documents/interfaces/chunk-02.md (`category_scores` columns named by the SRS,
  including `rankability_status`, `evidence_grade`, and
  `discovery_bounded_by_verified_total`)
Blocks (chunks whose plan/implementation needs this chunk's interface):
  Chunk 9B (sensitivity over the fixed `base_rankable_candidates`, final
  evidence/rankability), Chunk 10 (persistence/orchestration), Chunk 11
  (reporting of non-rankable categories)

## 1. Goal

Make `scoring.py` the pure owner of the **pre-sensitivity** decision: validate the
already-classified discovery, identity, and component evidence for each category
supplied by the caller, determine per-category `not_rankable` reasons under
LREQ-EVD-020, decide the pre-sensitivity evidence state and the preliminary
rankability state under LREQ-EVD-010/-030, and freeze an immutable, ordered
`base_rankable_candidates` tuple **before any sensitivity policy is evaluated**
(LREQ-EVD-020 line 994; dependency-map §3 Chunk 9A gate). The candidate set, the
preliminary rankability state, and the pre-sensitivity evidence state are internal
and non-persisted; they are **not** the final `evidence_grade` /
`rankability_status` (those are Chunk 9B's and are persisted by Chunk 10 —
dependency-map lines 953–954). Nothing here is a sales, revenue, download, or
demand prediction, and nothing here is a statistically representative estimate.

## 2. Scope

### In scope
- A fixed, documented `not_rankable` reason vocabulary (`StrEnum`) with a fixed
  evaluation order, covering every clause of LREQ-EVD-020 (lines 980–987).
- Per-category pre-sensitivity evidence evaluation: discovery/identity/unrecoverable
  integrity checks, required-component availability, page-view semantics, valid
  leave-one-out reference, competition-unbounded/material-failure conditions, and
  field-specific reference support (R4–R8).
- A fixed, ordered `base_rankable_candidates: tuple[str, ...]` (LREQ-EVD-020 lines
  989–994) in the caller's canonical `all_metrics` order (R3; LREQ-ARCH-030).
- The pre-sensitivity evidence state and the preliminary rankability state
  (LREQ-EVD-010, LREQ-EVD-030), kept distinct from `score_state`, `evidence_grade`,
  and `rankability_status` (dependency-map lines 898, 915, 917).
- The provisional-reason vocabulary for the **pre-sensitivity** half of
  LREQ-EVD-030 only: run below `STRONG_REFERENCE_CATEGORY_COUNT`, incomplete
  breadth fallback, and coverage acceptable but below `STRONG_COMPONENT_COVERAGE`.
- The supporting contract for LREQ-SEN-030: the immutable candidate set plus the
  pre-sensitivity rankability state that sensitivity will be evaluated over. No
  stability statistic and no warning are computed here (R9).
- Type hints and null/edge-case docstrings on every new public name
  (LREQ-NFR-040).

### Explicitly out of scope (and who owns it instead)
- **Final evidence grade (`evidence_grade`) and final `rankability_status`.**
  Primary owner is **Chunk 9B** (dependency-map lines 953–954; rows 106–107); Chunk
  10 persists them. This chunk assigns neither and writes no record field.
- **Sensitivity policies, top-3/top-5 stability, rank displacement, warning
  thresholds, sensitivity-driven provisional demotion.** Primary owner is **Chunk
  9B** (LREQ-SEN-010/-020/-030/-040; rows 108–111). This chunk's LREQ-SEN-030 role
  is only the supporting contract named in row 110 (dependency map line 110, 258).
- **The sensitivity-high provisional clause of LREQ-EVD-030** ("or sensitivity is
  high", line 999) is not a pre-sensitivity input; it is added by Chunk 9B. Chunk
  9A's provisional vocabulary has no `sensitivity_high` member.
- **LREQ-EVD-040 (final rankable) and LREQ-EVD-050 (final evidence grade)** are
  Chunk 9B's primary (rows 106–107). Chunk 9A only produces the preliminary state
  and the candidate set those complete over.
- **The orchestration-status half of LREQ-EVD-020.** The dependency map lists
  `pipeline.py` in row 247 with completion chunk **Chunk 10**. Chunk 9A keeps all
  decision logic pure in `scoring.py`; it accepts caller-supplied statuses and
  never derives them (R10). No `pipeline.py` edit.
- **Rejection of runs with fewer than `MIN_CATEGORIES_PER_RUN` categories** is
  LREQ-CLI-040 / Chunk 12 (dependency map row 120). Chunk 9A does not raise for a
  small run; it returns an empty candidate set with provisional/not-rankable
  decisions (R1). Exactly 8 categories still computes a score; 9–20 are provisional
  and never base-rankable.
- **Re-derivation of `DiscoveryStatus`, identity counts, or page-view semantics
  from payloads.** Chunks 1/3/5/6A classify; this chunk consumes already-persisted
  values as explicit typed parameters (R7, R10).
- **Persistence, SQLite, JSON serialization, logging, report, CLI.** Chunks
  10/11/12.
- **Any new numeric threshold or configurable weight.** Constants come from
  `models.py` (SRS §9.1 lines 1013–1017); no new threshold is invented (R5).

## 3. Requirements this chunk must satisfy

| LREQ ID | Ownership role here | Normative text (from SRS-lean.md, quoted/derived) | SRS section |
|---|---|---|---|
| LREQ-EVD-010 | Primary | "Use `not_rankable`, `provisional`, and `rankable` states." (line 978) | §9.1 |
| LREQ-EVD-020 | Primary (pure decision half); completion **Chunk 10** (orchestration status) | "A category is `not_rankable` when any of the following applies: discovery filtering is unverified; any unresolved or conflicting discovery identity remains in the category; required demand data is unavailable; recent-supply minimum evidence is not met; quality is unavailable under the required-component policy; page-view semantics are contradicted for a page-view-dependent score; no valid leave-one-out reference exists; identity preflight fails; or an unrecoverable data-integrity error occurs. Material discovery failure or unbounded breadth also makes competition non-rankable. The implementation SHALL first construct a fixed `base_rankable_candidates` set. A category is a base-rankable candidate only when the requirements above pass, the run contains at least `STRONG_REFERENCE_CATEGORY_COUNT` categories, all four components are available, every required stratum eligibility coverage meets `MIN_REQUIRED_COMPONENT_COVERAGE`, and field-specific reference support passes. Sensitivity SHALL not be used to construct this set." (lines 980–994) | §9.1 |
| LREQ-EVD-030 | Primary (pre-sensitivity half only) | "A score SHALL be `provisional` when computable and required conditions pass, but the run has 8–20 categories, the run has fewer than `STRONG_REFERENCE_CATEGORY_COUNT` categories, breadth uses the incomplete fallback estimate, stratum eligibility coverage is acceptable but below the strong policy, or sensitivity is high. Discovery bounded by a verified total is sufficient for rankability and SHALL not by itself force a provisional status." (lines 996–1001) | §9.1 |
| LREQ-SEN-030 | Supporting contract only | "Warn when `top_3_stability < 2 / 3`, or when a category's rank changes by more than `max(3 positions, 25% of reference-set size)`. The warning threshold SHALL be interpreted using the configured reference-set size and SHALL not silently alter the primary balanced score." (lines 1093–1096). Chunk 9A supplies only the fixed candidate set and pre-sensitivity rankability state that the threshold is evaluated over (row 110; §6.3). | §9.3 |
| LREQ-MET-070 | Supporting (Chunk 7B/3 primary) — competition-unavailability conditions | "Competition is unavailable when filtering is unverified, a material page failed, identity incompleteness makes breadth an unbounded lower bound, or the fallback breadth cannot be bounded. A failed or truncated discovery page SHALL never be interpreted as zero assets." (lines 764–767); "a category using the fallback breadth SHALL not be `rankable`; it MAY be `provisional` only when all other required evidence passes." (lines 758–759) | §7.3 |
| LREQ-EXT-050 | Supporting (Chunk 3 primary) — discovery status vocabulary | "The discovery status SHALL be one of `complete`, `truncated`, `page_failed`, `filter_unverified`, `category_mismatch`, `identity_incomplete`, or `request_failed`; a failed or truncated page SHALL never be interpreted as zero assets." (line 263) | §4.1 |
| LREQ-EXT-090 | Supporting (Chunk 3 primary) — warning / non-rankable competition | "A failed page, unverified filter, category mismatch, or material identity incompleteness SHALL generate a warning and SHALL prevent a fully rankable competition result for that category." (lines 279–281) | §4.1 |
| LREQ-SCR-050 | Supporting (Chunk 8 primary) — contradicted page views are not rankable | "If `page_view_semantics_status = \"contradicted\"`, `D` and `Q` SHALL be unavailable. `C` and `R` MAY remain available, but the category SHALL not be rankable." (line 949) | §8.2 |
| LREQ-ID-040 | Supporting (Chunk 6A primary) — preflight failure is run-level | "A preflight below the minimum success rate or above the maximum conflict rate SHALL stop bulk enrichment and mark the run failed." (lines 386–390). The category-level consequence is applied here as a reason code; run status stays a separate field (dependency-map §6.1). | §4.4 |
| LREQ-TST-060 | Supporting (Chunk 13 primary; completion Chunk 13) | "Scoring tests SHALL cover … fixed `base_rankable_candidates` constructed before sensitivity, sensitivity-driven final provisional status, and non-rankability." (lines 1250–1254). Chunk 9A covers the pre-sensitivity half: the reason matrices, candidate-set construction, and 8- vs 21-category provisional vectors. | §13 |
| LREQ-TST-010 | Supporting (Chunk 13 primary) | "Every formula SHALL have tests for normal values, explicit valid zero where applicable, missing values, invalid values, ties, and minimum boundaries." | §13 |
| LREQ-ARCH-010 | Supporting (Chunk 0 primary) | "`metrics` and `scoring` SHALL accept plain typed input structures and return typed result structures. They SHALL not import or call `collector`, `database`, `report`, or `cli` code, and SHALL perform no network or file I/O." (lines 227–229) | §3.3 |
| LREQ-ARCH-020 | Supporting (Chunk 0 primary) | "Pure metric and scoring functions SHALL NOT read the system clock. All timestamps SHALL be supplied by the orchestration layer." (lines 231–232) | §3.3 |
| LREQ-ARCH-030 | Supporting (Chunk 0 primary) | "The same normalized input data, policy versions, and configuration SHALL produce the same metric, score, evidence, and sensitivity outputs." (lines 234–235) | §3.3 |
| LREQ-NFR-040 | Supporting (Chunk 0 primary; completion Chunk 13) | "Public metric and scoring functions SHALL have type hints and docstrings describing null and edge-case behavior." (lines 1171–1172) | §11 |

Constants consumed unchanged (SRS §9.1 lines 1013–1017; `models.py` lines 35–36,
52–53): `MIN_CATEGORIES_PER_RUN = 8`, `STRONG_REFERENCE_CATEGORY_COUNT = 21`,
`MIN_REQUIRED_COMPONENT_COVERAGE = 0.50`, `STRONG_COMPONENT_COVERAGE = 0.80`.

## 4. Interface contracts consumed

Copied from the frozen interfaces (not re-derived from source).

### 4.1 From `interfaces/chunk-08.md` (`niche_scout.scoring`)

`ScoreResult` (Chunk 0 shape, unchanged by Chunk 8) —
`market_opportunity_score: float | None`, `score_state: ScoreState`,
`component_d/-c/-r/-q: float | None`, `available_component_count: int`,
`rankability_status: RankabilityStatus = NOT_RANKABLE`,
`evidence_grade: EvidenceGrade = INSUFFICIENT`. Chunk 8 leaves
`rankability_status`/`evidence_grade` at these defaults; Chunk 9A reads the
component fields and `score_state` and never writes back to a `ScoreResult`.

`ComponentValues` (`demand`, `competition`, `recent_supply`, `quality`, each
`float | None`; `available_component_count` property). `FieldUsableCounts`
(per-field `int`; `0` is a legitimate explicit count). `LeaveOneOutReference`
(`reference_size: int`; `field_usable_counts` property). `COMPONENT_WEIGHT_KEYS`.

Semantics consumed: an unavailable component is `None` (never `0.0`); a
sample-derived `D`/`R`/`Q` below `MIN_REQUIRED_COMPONENT_COVERAGE` is already
`None` from Chunk 8; `C` is available only for
`BreadthSource.VERIFIED_TOTAL_COUNT` + `BreadthCompletenessStatus.COMPLETE` and is
not coverage-gated.

### 4.2 From `interfaces/chunk-7B.md` (`niche_scout.metrics`)

```python
@dataclass(frozen=True, slots=True)
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
```

`None` in `RawMetricBundle` means unavailable; `0.0` is an explicit value. This
chunk consumes `CategoryRawMetrics` only as the ordering authority (R3); the
coverage/provenance facts are supplied again explicitly through
`PreSensitivityCategoryInput` (R10).

### 4.3 From `interfaces/chunk-05.md` / `chunk-03.md` / `chunk-6A.md` (statuses)

`models.PageViewSemanticsStatus` = `unvalidated` / `validated_cumulative` /
`contradicted` (run-level; consumed, never detected). `models.DiscoveryStatus` =
`complete` / `truncated` / `page_failed` / `filter_unverified` /
`category_mismatch` / `identity_incomplete` / `request_failed`.
`models.IdentityPreflightStatus` = `passed` / `failed` / `insufficient`.
`models.BreadthSource`, `models.BreadthCompletenessStatus`,
`models.RankabilityStatus`, `models.EvidenceGrade`, `models.ScoreState`.

### 4.4 From `interfaces/chunk-02.md` (persisted column names)

`CategoryScoreRecord` exposes `discovery_status`, `discovery_filter_verified`,
`discovery_unresolved_identity_count`, `discovery_conflict_count`,
`discovery_bounded_by_verified_total`, `rankability_status`, `evidence_grade`.
Chunk 9A computes the pure preliminary values with the same fact names; Chunk 10
maps final 9B values to the columns. Chunk 9A never persists.

## 5. Interface contract this chunk produces

Additive to `src/niche_scout/scoring.py`; no Chunk 0/8 name is modified.

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

### 5.1 Semantics

**Signature change (frozen):** the earlier draft of this plan declared
`field_reference_support_passes(counts)` with a single argument. That is
insufficient: the predicate depends on which components are *available*, so the
availability must reach the function explicitly. The final signature is the
keyword-only form above (R11). The available flags are derived by the caller from
the four `ScoreResult` component fields (`component_d is not None`, etc.); the pure
function never reads a `ScoreResult` itself.

**`field_reference_support_passes(counts, *, demand_available,
competition_available, recent_supply_available, quality_available)` — LREQ-EVD-020
"field-specific reference support passes" (line 993).** Field-specific reference
support is required only for the raw fields each **available** component consumes,
per the SRS §8.2 mapping:

- Demand (`D`) ← `demand_per_asset_raw`, `demand_median_raw`
- Competition (`C`) ← `breadth_raw`
- Recent supply (`R`) ← `recent_share_raw`, `median_age_raw`
- Quality (`Q`) ← `quality_raw`

Returns `True` iff for **every** available component, every raw field it consumes
has `counts.<field> > 0`. A component that is unavailable contributes **no**
requirement: its fields may be `0` without failing the predicate. The vacuous case
is `True`: all four components unavailable → no requirement to satisfy, so the
function returns `True`. That category is already `not_rankable` through the
component-availability reasons (`REQUIRED_DEMAND_DATA_UNAVAILABLE`,
`RECENT_SUPPLY_MINIMUM_NOT_MET`, `QUALITY_UNAVAILABLE`, and/or
`COMPETITION_UNBOUNDED_OR_MATERIAL_FAILURE`), so vacuous truth can never promote it.
`FIELD_REFERENCE_SUPPORT_INSUFFICIENT` is emitted only when this predicate returns
`False`. SRS basis: LREQ-EVD-020 line 993 states the requirement; §8.2
LREQ-SCR-010/-020/-030/-040 define which fields each component consumes; and
LREQ-SCR-010's "the one available normalized value when exactly one is available"
(line 916, §8.2) means a component can be legitimately available from a
single sub-signal, which is why the check is per available component and per
consumed field rather than a uniform six-field `> 0` rule. This is a closed
predicate: no option remains open.

**`not_rankable_reasons(score, evidence, *, identity_preflight_status)`** — returns
the subset of `NOT_RANKABLE_REASON_ORDER` that fires, in that order, empty for a
category with no `not_rankable` condition. Firing rules (all facts are explicit
inputs; nothing is re-derived):
- `UNRECOVERABLE_DATA_INTEGRITY_ERROR`: `evidence.discovery_status is
  DiscoveryStatus.REQUEST_FAILED` or `is DiscoveryStatus.PAGE_FAILED` (R7;
  LREQ-EXT-050 line 263; a failed page never becomes zero assets).
- `DISCOVERY_FILTER_UNVERIFIED`: `not evidence.discovery_filter_verified`, or
  `evidence.discovery_status` is `FILTER_UNVERIFIED` or `CATEGORY_MISMATCH`
  (LREQ-EXT-090 lines 279–281).
- `UNRESOLVED_OR_CONFLICTING_IDENTITY`: `evidence.discovery_status is
  IDENTITY_INCOMPLETE`, or `evidence.discovery_unresolved_identity_count > 0`, or
  `evidence.discovery_conflict_count > 0` (LREQ-EVD-020 lines 981–982).
- `IDENTITY_PREFLIGHT_FAILED`: `identity_preflight_status is
  IdentityPreflightStatus.FAILED` **or** `is IdentityPreflightStatus.INSUFFICIENT`
  (R6/Q4: `INSUFFICIENT` is treated as a preflight failure for the category — a
  preflight that cannot establish identity reliability cannot make any category
  rankable, and LREQ-EVD-020 line 985 lists "identity preflight fails" as a
  category-level cause). The distinct run-level value is preserved as the input
  fact; no separate reason code is added for `INSUFFICIENT`. Run status stays a
  separate field (dependency-map §6.1) and is not modelled by this function.
- `COMPETITION_UNBOUNDED_OR_MATERIAL_FAILURE`: exactly when `score.competition is
  None` (R6/Q3). This is the pure-layer expression of LREQ-MET-070's
  competition-unavailability conditions (lines 764–766); no numeric threshold, no
  new enum, and no new input field is introduced.
- `PAGE_VIEW_SEMANTICS_CONTRADICTED`: `evidence.page_view_semantics_status is
  PageViewSemanticsStatus.CONTRADICTED` (LREQ-SCR-050 line 949; the D/Q
  unavailability half is already Chunk 8's).
- `REQUIRED_DEMAND_DATA_UNAVAILABLE`: `score.component_d is None`.
- `RECENT_SUPPLY_MINIMUM_NOT_MET`: `score.component_r is None`.
- `QUALITY_UNAVAILABLE`: `score.component_q is None`.
- `NO_VALID_LEAVE_ONE_OUT_REFERENCE`: `evidence.reference_size <= 0` (no peer
  category exists) — LREQ-EVD-020 line 985.
- `FIELD_REFERENCE_SUPPORT_INSUFFICIENT`: `not field_reference_support_passes(
  evidence.field_usable_counts, demand_available=score.component_d is not None,
  competition_available=score.component_c is not None, recent_supply_available=
  score.component_r is not None, quality_available=score.component_q is not None)`
  (R11; the available-component context is derived from the `ScoreResult`
  components, not from a new input field). This reason is emitted **last** and
  makes a category `not_rankable`; it is distinct from the `provisional` coverage
  policy.

**`provisional_reasons(score, evidence, *, run_category_count,
min_required_component_coverage)`** — returns the subset of
`PROVISIONAL_REASON_ORDER` that fires, in that order. Only the pre-sensitivity
clauses of LREQ-EVD-030 are represented:
- `RUN_BELOW_STRONG_REFERENCE`: `run_category_count <
  STRONG_REFERENCE_CATEGORY_COUNT` (covers the 8–20 clause and the
  fewer-than-21 clause of lines 997–998).
- `INCOMPLETE_BREADTH_FALLBACK`: `evidence.breadth_completeness_status is
  BreadthCompletenessStatus.INCOMPLETE_ESTIMATE` (the fallback estimate of
  LREQ-MET-070 lines 752–759). It fires **whenever** the fallback status holds,
  including when `discovery_bounded_by_verified_total` is `True` (Q3): the
  provisional reason is about the fallback estimate itself, not about whether a
  verified total bounded the discovery.
- `COVERAGE_BELOW_STRONG`: at least one of
  `evidence.demand_stratum_eligibility_coverage`,
  `evidence.recent_supply_stratum_eligibility_coverage`,
  `evidence.quality_stratum_eligibility_coverage` is `< STRONG_COMPONENT_COVERAGE`
  while `>= min_required_component_coverage` (line 999: "acceptable but below the
  strong policy"). A coverage strictly below `min_required_component_coverage` is
  not a provisional reason: the corresponding component is already `None` and the
  category is `not_rankable` under an earlier reason.
- No `sensitivity_high` member exists (Chunk 9B owns that clause).

**`pre_sensitivity_rankability_state(not_rankable, provisional, *,
base_rankable)`** — the LREQ-EVD-010 pure state transition:
`NOT_RANKABLE` if `not_rankable` is non-empty; else `RANKABLE` if `base_rankable`
and `provisional` is empty; else `PROVISIONAL`. The result is always one of the
three `PRE_SENSITIVITY_RANKABILITY_STATES`; it is **not** a
`models.RankabilityStatus` instance (R2).

**`evaluate_pre_sensitivity_evidence(...)`** — per-category wiring: compute
`base_rankable` from the base-candidate rule below, then
`not_rankable_reasons`, `provisional_reasons`, then
`pre_sensitivity_rankability_state`. `evidence_state` is `INSUFFICIENT` when
`not_rankable` is non-empty, else `PROVISIONAL_ONLY` when `provisional` is
non-empty, else `SUFFICIENT`. The function does not read or accept any sensitivity
input (LREQ-EVD-020 line 994).

**Base-candidate rule (LREQ-EVD-020 lines 989–994; R1).** A category is
`base_rankable` iff **all** hold:
1. `len(all_metrics) >= STRONG_REFERENCE_CATEGORY_COUNT` (21) for the run;
2. `not_rankable_reasons(...)` is empty;
3. `score.available_component_count == 4` (all four components available);
4. each of demand/recent-supply/quality coverage `>=
   min_required_component_coverage`;
5. `evidence.reference_size > 0`;
6. `field_reference_support_passes(evidence.field_usable_counts,
   demand_available=score.component_d is not None,
   competition_available=score.component_c is not None,
   recent_supply_available=score.component_r is not None,
   quality_available=score.component_q is not None)` is `True` (R11). When all four
   components are available (condition 3), the flags are all `True` and the
   predicate reduces to "every one of the six consumed raw fields has at least one
   usable peer value".

A run with 8–20 categories therefore yields an empty `base_rankable_candidates`
(R1; dependency-map §6.2 lines 1150–1152). A category can be `base_rankable` and
still `PROVISIONAL` (e.g. coverage in `[0.50, 0.80)`), because base candidacy is
necessary but not sufficient for final rankable (LREQ-EVD-040 line 1007).

**`build_base_rankable_candidates(all_metrics, inputs, scores, *, ...)`** —
run-level, pure. **Caller obligation (R3):** `all_metrics` must be passed in the
caller's deterministic canonical category order (the same order `score_category`
consumes); `inputs` and `scores` must be 1:1 aligned with `all_metrics` by
category. The returned `base_rankable_candidates` is the `tuple[str, ...]` of
`all_metrics` categories whose decision has `base_rankable=True`, **in `all_metrics`
order**; `decisions` is also in `all_metrics` order; `run_category_count =
len(all_metrics)`. `ValueError` when the three sequences differ in length or a
category at an index does not match across them. The function never mutates a
`ScoreResult` and never changes `market_opportunity_score`, `score_state`, or any
component (gate bullet 3; LREQ-EVD-020 line 994): it reads them only.

**Determinism (LREQ-ARCH-030).** Reason tuples are emitted in the fixed orders
above; `base_rankable_candidates` follows `all_metrics` order; no set/dict
iteration determines any output; no clock, no randomness, no I/O.

**Null/edge behaviour.** `field_usable_counts` values are counts, so `0` is a
legitimate explicit value, not "missing". `reference_size` may be `0` (a
one-category run) → `NO_VALID_LEAVE_ONE_OUT_REFERENCE`. A `None` component means
unavailable and is never converted to `0.0`. `discovery_bounded_by_verified_total`
is a boolean fact, not a metric.

## 6. Files touched

| File | New/modified | Purpose |
|---|---|---|
| `src/niche_scout/scoring.py` | Modified (additive) | Reason vocabularies, pre-sensitivity input/decision types, `evaluate_pre_sensitivity_evidence`, `build_base_rankable_candidates`, `pre_sensitivity_rankability_state`, `field_reference_support_passes` |
| `tests/test_scoring_evidence.py` | New | Chunk 9A analytical tests (marker + traceability entries) |
| `tests/fixtures/scoring_evidence_fixtures.py` | New | Data-only builders and pre-sensitivity golden vectors |
| `tests/fixtures/__init__.py` | Modified | Re-export the new fixture module (one-line pattern, as for `scoring_fixtures`) |
| `tests/traceability.json` | Modified | Node → LREQ entries for the new tests |

`pipeline.py` is **not** touched: its LREQ-EVD-020 role is the orchestration-status
completion, owned by Chunk 10 (dependency-map row 247).

## 7. Task breakdown

- [ ] Add `NotRankableReason`, `NOT_RANKABLE_REASON_ORDER`, `ProvisionalReason`,
      `PROVISIONAL_REASON_ORDER`, `PreSensitivityRankabilityState`,
      `PRE_SENSITIVITY_RANKABILITY_STATES`, `PreSensitivityEvidenceState`
      (LREQ-EVD-010, LREQ-EVD-020, LREQ-EVD-030).
- [ ] Add `PreSensitivityCategoryInput`, `PreSensitivityDecision`,
      `BaseCandidateSet` typed structures; import `DiscoveryStatus` and
      `IdentityPreflightStatus` from `models` (no `models.py` edit) (LREQ-EVD-020).
- [ ] Implement `field_reference_support_passes` with the keyword-only
      available-component flags and per-consumed-field support rule (LREQ-EVD-020;
      LREQ-SCR-010/-020/-030/-040; R11).
- [ ] Implement `not_rankable_reasons` with the fixed emission order and every
      LREQ-EVD-020 clause, including `INSUFFICIENT` counting as preflight failure
      and `competition is None` as the unbounded/material-failure trigger
      (LREQ-EVD-020; LREQ-EXT-050/-090; LREQ-MET-070; LREQ-SCR-050; Q3, Q4).
- [ ] Implement `provisional_reasons` for the pre-sensitivity clauses only
      (LREQ-EVD-030; LREQ-MET-070).
- [ ] Implement `pre_sensitivity_rankability_state` (LREQ-EVD-010).
- [ ] Implement `evaluate_pre_sensitivity_evidence` (base-candidate rule,
      evidence state, no sensitivity input) (LREQ-EVD-020, LREQ-EVD-030).
- [ ] Implement `build_base_rankable_candidates` with `all_metrics`-order output,
      alignment validation, and no `ScoreResult` mutation (LREQ-EVD-020,
      LREQ-ARCH-030).
- [ ] Add type hints and null/edge-case docstrings to every new public name
      (LREQ-NFR-040).
- [ ] Write `tests/fixtures/scoring_evidence_fixtures.py` golden vectors (data
      only).
- [ ] Write `tests/test_scoring_evidence.py` with the §9 markers.
- [ ] Add the §9 `tests/traceability.json` entries and re-export the fixture
      module.
- [ ] Run `ruff format`, `ruff check`,
      `python -m pytest tests/test_scoring_evidence.py -q`, the full suite,
      `python -m niche_scout.tools.check_import_boundaries`, and
      `python -m niche_scout.tools.validate_traceability`.

## 8. Edge cases and invariants

From the dependency map edge-case column for LREQ-EVD-010/-020/-030 (rows
246–248) and the Chunk 9A gate/description (lines 886–918):

- Unresolved/conflicting identities, invalid discovery, missing required metrics,
  preflight failure, contradicted page views, and no reference each produce
  `not_rankable` (LREQ-EVD-020; row 247).
- **Run failure and category not-rankable status remain distinct** (row 247;
  dependency-map §6.1): `identity_preflight_status` is a run-level parameter and
  does not collapse run status, score state, or rankability into one field.
- `score_state` (`available`/`partial`/`unavailable`) is independent of the
  pre-sensitivity rankability state and of the evidence state; the gate requires
  them to remain distinct (gate bullet 2).
- Categories with insufficient support are excluded from
  `base_rankable_candidates` **without changing their stored score fields** (gate
  bullet 3). `ScoreResult` is frozen and is never rebuilt or mutated.
- The base candidate set is frozen **before** any alternate policy is ranked
  (gate bullet 1; LREQ-EVD-020 line 994). No sensitivity parameter exists in this
  chunk's surface.
- 8–20 categories: `base_rankable_candidates` is empty; scores are provisional and
  never rankable (R1; dependency-map §6.2; LREQ-EVD-040 lines 1003–1008). Exactly 8
  still computes a score; fewer than 8 is rejected before ranking by Chunk 12
  (LREQ-CLI-040).
- `request_failed` / `page_failed` categories are `not_rankable`, never
  zero-breadth (R7; LREQ-EXT-050 line 263; LREQ-EXT-090 lines 279–281).
- Fallback breadth (`incomplete_estimate`) is never `rankable`; it may be
  `provisional` only when all other required evidence passes (LREQ-MET-070 lines
  758–759). An `INCOMPLETE_BREADTH_FALLBACK` provisional reason fires whenever the
  fallback status holds, including when `discovery_bounded_by_verified_total` is
  `True` (Q3).
- Discovery bounded by a verified total does not by itself force **not-rankable**
  and does not remove the `INCOMPLETE_BREADTH_FALLBACK` provisional reason when the
  breadth source is the incomplete fallback (LREQ-EVD-030 line 1000; Q3).
- `IdentityPreflightStatus.INSUFFICIENT` fires `IDENTITY_PREFLIGHT_FAILED`, the same
  as `FAILED` (Q4); the distinct run-level value is preserved as the input fact,
  not as a separate reason code.
- Field-specific reference support: a component that is unavailable contributes no
  requirement, so an unused raw field with `0` usable peers never fails the
  predicate; the vacuous all-four-unavailable case returns `True` and is already
  `not_rankable` through the component-availability reasons (R11; Q1).
- Missing is not zero: a `None` component/coverage/reference is never treated as
  `0.0`; a `FieldUsableCounts` value of `0` is a count, not a metric zero.
- Determinism: fixed reason order, `all_metrics`-order candidate tuple, no
  set/dict iteration for output order, no clock, no randomness (LREQ-ARCH-030).
- Purity: `scoring.py` keeps its existing imports and adds only `enum.StrEnum`
  plus `models` names; it never imports `collector*`, `database`, `pipeline`,
  `report`, `cli`, `config`, `sqlite3`, or an I/O/clock module (LREQ-ARCH-010/020).

## 9. Test plan

### Test files
- New `tests/test_scoring_evidence.py` (Chunk 9A only; `tests/test_scoring.py`
  already holds the Chunk 8 nodes and is not extended here).
- New data-only fixture module `tests/fixtures/scoring_evidence_fixtures.py`;
  re-export it from `tests/fixtures/__init__.py`.
- `tests/traceability.json` is **keyed by fully qualified test node ID → array of
  `LREQ-*` IDs** (node → LREQ), confirmed by opening the file: entries 1–60 are
  `"tests/test_contracts.py::test_models_import": ["LREQ-ARCH-010"]`-shaped, and
  dependency-map §3 Chunk 0 line 410 states the same direction. The `tests/AGENTS.md`
  prose ("keyed by individual `LREQ-*` IDs") describes the inverse and is
  contradicted by the artifact; the artifact governs. *(The prior planning brief
  asserted LREQ → nodes; that is the inverse of the file and is corrected here.)*

### Golden vectors / fixtures needed
All expected values are hand-derived from SRS §9.1/§7.3; none is copied from the
implementation. Fixtures are inert builders/constants only.

- **Builders**: `make_score_result(score, state, d, c, r, q)` (constructs a
  `ScoreResult` literal, including `available_component_count` derived by the test
  from the four components), and `make_pre_sensitivity_input(category, *, ...)` for
  `PreSensitivityCategoryInput` with explicit keyword facts.
- **21-category fully-verified run** (`run_category_count = 21`): every category
  has `discovery_status = COMPLETE`, `discovery_filter_verified = True`, unresolved
  and conflict counts `0`, all four components present, coverage `1.0` on all three
  sample-derived components, `reference_size = 20`, and all six
  `FieldUsableCounts` fields `= 20`. Expected: `not_rankable_reasons = ()`,
  `provisional_reasons = ()`, `evidence_state = SUFFICIENT`,
  `rankability_state = RANKABLE`, `base_rankable = True`, and
  `base_rankable_candidates == ("c-0", "c-1", …, "c-20")` in `all_metrics` order.
- **8-category fully-verified run** (`run_category_count = 8`): same facts but one
  peer fewer (`reference_size = 7`, counts `= 7`) and run size 8. Expected:
  `provisional_reasons == (RUN_BELOW_STRONG_REFERENCE,)`,
  `base_rankable_candidates == ()`, state `PROVISIONAL` (R1).
- **20-category run**: `base_rankable_candidates == ()`, state `PROVISIONAL`.
- **Mixed 21-category run**: category `"c-3"` has `component_d = None` and the
  other 20 are fully verified. Expected candidates = all categories except `"c-3"`
  in order; `"c-3".not_rankable_reasons == (REQUIRED_DEMAND_DATA_UNAVAILABLE,)`
  and `rankability_state == NOT_RANKABLE`.
- **Reason matrix** (`(label, score, evidence, identity_preflight_status,
  expected_reasons)`), one row per LREQ-EVD-020 clause:
  `request_failed` → `(UNRECOVERABLE_DATA_INTEGRITY_ERROR,)`;
  `page_failed` → same; `filter_unverified` and `category_mismatch` →
  `(DISCOVERY_FILTER_UNVERIFIED,)`; `identity_incomplete` and
  `unresolved_identity_count = 1` / `conflict_count = 1` →
  `(UNRESOLVED_OR_CONFLICTING_IDENTITY,)`;
  `identity_preflight_status = FAILED` (all facts otherwise clean) →
  `(IDENTITY_PREFLIGHT_FAILED,)`;
  `identity_preflight_status = INSUFFICIENT` (all facts otherwise clean) →
  `(IDENTITY_PREFLIGHT_FAILED,)` (Q4);
  `component_d = None` → `(REQUIRED_DEMAND_DATA_UNAVAILABLE,)`;
  `component_r = None` → `(RECENT_SUPPLY_MINIMUM_NOT_MET,)`;
  `component_q = None` → `(QUALITY_UNAVAILABLE,)`;
  `component_c = None` → `(COMPETITION_UNBOUNDED_OR_MATERIAL_FAILURE,)` (Q3);
  `page_view_semantics_status = CONTRADICTED` →
  `(PAGE_VIEW_SEMANTICS_CONTRADICTED,)`;
  `reference_size = 0` → `(NO_VALID_LEAVE_ONE_OUT_REFERENCE,)`.
- **Field-reference-support vectors** (R11; Q1): (i) demand available
  (`component_d` not `None`) with `demand_median_raw = 0` usable peers but
  `demand_per_asset_raw > 0` → predicate `True`; (ii) demand available with both
  demand counts `0` → `False`; (iii) competition available (`component_c` not
  `None`) with `breadth_raw = 0` → `False`; (iv) an unused field at `0` (e.g.
  `quality_raw = 0` while `Q` is unavailable) never fails; (v) all four components
  unavailable → vacuous `True`.
- **Order vector**: a category with several simultaneous conditions (e.g.
  `request_failed` + `component_d = None` + `reference_size = 0`) → the reasons
  appear in the fixed `NOT_RANKABLE_REASON_ORDER` **emission** order, not input
  order.
- **Provisional vectors**: coverage `0.79` on one required component (others
  `1.0`) → `(COVERAGE_BELOW_STRONG,)`; coverage exactly `0.80` → no
  `COVERAGE_BELOW_STRONG`; coverage `0.50` (boundary) → no
  `COVERAGE_BELOW_STRONG` and the component is available; fallback breadth
  (`incomplete_estimate`, `discovery_bounded_by_verified_total = False`) →
  `(INCOMPLETE_BREADTH_FALLBACK,)`; **the same fallback with
  `discovery_bounded_by_verified_total = True` → still
  `(INCOMPLETE_BREADTH_FALLBACK,)` (Q3)**; run size 21 with no other condition →
  no provisional reasons; a category with verified+complete breadth and
  `discovery_bounded_by_verified_total = True` → no provisional reasons (bounded by
  a verified total does not force provisional).
- **Distinctness vectors**: a category with `score_state = PARTIAL` and state
  `PROVISIONAL`; a category with `score_state = AVAILABLE` but
  `rankability_state = NOT_RANKABLE`; assert
  `isinstance(state, PreSensitivityRankabilityState)` and that it is not a
  `models.RankabilityStatus` (R2).

### Exact `@pytest.mark.lreq(...)` markers (1:1 with §3)

| Test node | LREQ marker(s) |
|---|---|
| `test_pre_sensitivity_rankability_state_vocabulary` | `LREQ-EVD-010` |
| `test_pre_sensitivity_rankability_state_precedence` | `LREQ-EVD-010` |
| `test_pre_sensitivity_rankability_state_is_not_final_rankability_status` | `LREQ-EVD-010` |
| `test_not_rankable_reason_matrix` | `LREQ-EVD-020`, `LREQ-TST-010` |
| `test_not_rankable_reason_order_is_deterministic` | `LREQ-EVD-020`, `LREQ-ARCH-030` |
| `test_discovery_filter_unverified_is_not_rankable` | `LREQ-EVD-020`, `LREQ-EXT-090` |
| `test_unresolved_or_conflicting_identity_is_not_rankable` | `LREQ-EVD-020` |
| `test_identity_preflight_failure_is_not_rankable` | `LREQ-EVD-020`, `LREQ-ID-040` |
| `test_identity_preflight_insufficient_is_not_rankable` | `LREQ-EVD-020`, `LREQ-ID-040` |
| `test_field_reference_support_requires_consumed_fields` | `LREQ-EVD-020`, `LREQ-TST-010` |
| `test_required_demand_unavailable_is_not_rankable` | `LREQ-EVD-020` |
| `test_recent_supply_minimum_not_met_is_not_rankable` | `LREQ-EVD-020` |
| `test_quality_unavailable_is_not_rankable` | `LREQ-EVD-020` |
| `test_page_view_semantics_contradicted_is_not_rankable` | `LREQ-EVD-020`, `LREQ-SCR-050` |
| `test_no_valid_leave_one_out_reference_is_not_rankable` | `LREQ-EVD-020` |
| `test_unrecoverable_data_integrity_error_is_not_rankable` | `LREQ-EVD-020`, `LREQ-EXT-050` |
| `test_competition_unbounded_or_material_failure_is_not_rankable` | `LREQ-EVD-020`, `LREQ-MET-070` |
| `test_base_rankable_candidates_require_strong_reference_count` | `LREQ-EVD-020`, `LREQ-TST-060` |
| `test_base_rankable_candidates_empty_for_eight_to_twenty_run` | `LREQ-EVD-020`, `LREQ-TST-060` |
| `test_base_rankable_candidates_preserve_all_metrics_order` | `LREQ-EVD-020`, `LREQ-ARCH-030` |
| `test_base_rankable_candidates_require_all_components_and_coverage` | `LREQ-EVD-020` |
| `test_base_candidate_construction_does_not_change_score_fields` | `LREQ-EVD-020` |
| `test_build_base_rankable_candidates_rejects_misaligned_inputs` | `LREQ-EVD-020` |
| `test_score_state_and_rankability_state_remain_distinct` | `LREQ-EVD-020` |
| `test_provisional_reason_for_run_below_strong_reference` | `LREQ-EVD-030` |
| `test_provisional_reason_for_incomplete_breadth_fallback` | `LREQ-EVD-030`, `LREQ-MET-070` |
| `test_bounded_by_verified_total_does_not_force_provisional` | `LREQ-EVD-030` |
| `test_incomplete_breadth_fallback_with_verified_total_is_provisional` | `LREQ-EVD-030`, `LREQ-MET-070` |
| `test_provisional_reason_for_coverage_between_minimum_and_strong` | `LREQ-EVD-030` |
| `test_eight_category_run_is_provisional_never_rankable` | `LREQ-EVD-030`, `LREQ-TST-060` |
| `test_pre_sensitivity_state_excludes_sensitivity_high_reason` | `LREQ-EVD-030` |
| `test_base_candidate_set_is_fixed_input_to_sensitivity` | `LREQ-SEN-030` |
| `test_scoring_evidence_public_functions_have_type_hints_and_docstrings` | `LREQ-NFR-040` |
| `test_scoring_evidence_module_is_import_pure_and_clock_free` | `LREQ-ARCH-010`, `LREQ-ARCH-020` |
| `test_pre_sensitivity_outputs_are_deterministic` | `LREQ-ARCH-030` |
| `test_pre_sensitivity_golden_vectors` | `LREQ-TST-010`, `LREQ-EVD-020`, `LREQ-EVD-030` |

### `tests/traceability.json` entries to add

Direction: node → array of LREQ IDs.

```json
{
  "tests/test_scoring_evidence.py::test_pre_sensitivity_rankability_state_vocabulary": ["LREQ-EVD-010"],
  "tests/test_scoring_evidence.py::test_pre_sensitivity_rankability_state_precedence": ["LREQ-EVD-010"],
  "tests/test_scoring_evidence.py::test_pre_sensitivity_rankability_state_is_not_final_rankability_status": ["LREQ-EVD-010"],
  "tests/test_scoring_evidence.py::test_not_rankable_reason_matrix": ["LREQ-EVD-020", "LREQ-TST-010"],
  "tests/test_scoring_evidence.py::test_not_rankable_reason_order_is_deterministic": ["LREQ-EVD-020", "LREQ-ARCH-030"],
  "tests/test_scoring_evidence.py::test_discovery_filter_unverified_is_not_rankable": ["LREQ-EVD-020", "LREQ-EXT-090"],
  "tests/test_scoring_evidence.py::test_unresolved_or_conflicting_identity_is_not_rankable": ["LREQ-EVD-020"],
  "tests/test_scoring_evidence.py::test_identity_preflight_failure_is_not_rankable": ["LREQ-EVD-020", "LREQ-ID-040"],
  "tests/test_scoring_evidence.py::test_identity_preflight_insufficient_is_not_rankable": ["LREQ-EVD-020", "LREQ-ID-040"],
  "tests/test_scoring_evidence.py::test_field_reference_support_requires_consumed_fields": ["LREQ-EVD-020", "LREQ-TST-010"],
  "tests/test_scoring_evidence.py::test_required_demand_unavailable_is_not_rankable": ["LREQ-EVD-020"],
  "tests/test_scoring_evidence.py::test_recent_supply_minimum_not_met_is_not_rankable": ["LREQ-EVD-020"],
  "tests/test_scoring_evidence.py::test_quality_unavailable_is_not_rankable": ["LREQ-EVD-020"],
  "tests/test_scoring_evidence.py::test_page_view_semantics_contradicted_is_not_rankable": ["LREQ-EVD-020", "LREQ-SCR-050"],
  "tests/test_scoring_evidence.py::test_no_valid_leave_one_out_reference_is_not_rankable": ["LREQ-EVD-020"],
  "tests/test_scoring_evidence.py::test_unrecoverable_data_integrity_error_is_not_rankable": ["LREQ-EVD-020", "LREQ-EXT-050"],
  "tests/test_scoring_evidence.py::test_competition_unbounded_or_material_failure_is_not_rankable": ["LREQ-EVD-020", "LREQ-MET-070"],
  "tests/test_scoring_evidence.py::test_base_rankable_candidates_require_strong_reference_count": ["LREQ-EVD-020", "LREQ-TST-060"],
  "tests/test_scoring_evidence.py::test_base_rankable_candidates_empty_for_eight_to_twenty_run": ["LREQ-EVD-020", "LREQ-TST-060"],
  "tests/test_scoring_evidence.py::test_base_rankable_candidates_preserve_all_metrics_order": ["LREQ-EVD-020", "LREQ-ARCH-030"],
  "tests/test_scoring_evidence.py::test_base_rankable_candidates_require_all_components_and_coverage": ["LREQ-EVD-020"],
  "tests/test_scoring_evidence.py::test_base_candidate_construction_does_not_change_score_fields": ["LREQ-EVD-020"],
  "tests/test_scoring_evidence.py::test_build_base_rankable_candidates_rejects_misaligned_inputs": ["LREQ-EVD-020"],
  "tests/test_scoring_evidence.py::test_score_state_and_rankability_state_remain_distinct": ["LREQ-EVD-020"],
  "tests/test_scoring_evidence.py::test_provisional_reason_for_run_below_strong_reference": ["LREQ-EVD-030"],
  "tests/test_scoring_evidence.py::test_provisional_reason_for_incomplete_breadth_fallback": ["LREQ-EVD-030", "LREQ-MET-070"],
  "tests/test_scoring_evidence.py::test_bounded_by_verified_total_does_not_force_provisional": ["LREQ-EVD-030"],
  "tests/test_scoring_evidence.py::test_incomplete_breadth_fallback_with_verified_total_is_provisional": ["LREQ-EVD-030", "LREQ-MET-070"],
  "tests/test_scoring_evidence.py::test_provisional_reason_for_coverage_between_minimum_and_strong": ["LREQ-EVD-030"],
  "tests/test_scoring_evidence.py::test_eight_category_run_is_provisional_never_rankable": ["LREQ-EVD-030", "LREQ-TST-060"],
  "tests/test_scoring_evidence.py::test_pre_sensitivity_state_excludes_sensitivity_high_reason": ["LREQ-EVD-030"],
  "tests/test_scoring_evidence.py::test_base_candidate_set_is_fixed_input_to_sensitivity": ["LREQ-SEN-030"],
  "tests/test_scoring_evidence.py::test_scoring_evidence_public_functions_have_type_hints_and_docstrings": ["LREQ-NFR-040"],
  "tests/test_scoring_evidence.py::test_scoring_evidence_module_is_import_pure_and_clock_free": ["LREQ-ARCH-010", "LREQ-ARCH-020"],
  "tests/test_scoring_evidence.py::test_pre_sensitivity_outputs_are_deterministic": ["LREQ-ARCH-030"],
  "tests/test_scoring_evidence.py::test_pre_sensitivity_golden_vectors": ["LREQ-TST-010", "LREQ-EVD-020", "LREQ-EVD-030"]
}
```

## 10. Definition of done (gate)

Copied **verbatim** from `Documents/requirements-dependency-map.md` Chunk 9A
(lines 912–917):

- The base candidate set is frozen before any alternate policy is ranked.
- Score state, pre-sensitivity evidence state, and preliminary rankability status remain distinct.
- Categories with insufficient support are excluded from the base candidate set without changing their stored score fields.
- No final evidence grade is persisted by this chunk when sensitivity is an input to the final grade.

## 11. Explicit prohibitions

- Must not import or call `collector`, `collector_coveo`, `collector_graphql`,
  `database`, `pipeline`, `report`, `cli`, `config`, `sqlite3`, or any
  filesystem/network/clock module; must not read the system clock
  (LREQ-ARCH-010/020).
- Must not persist, log, serialize JSON, or write files/DB rows; must not assign
  or persist `evidence_grade` / `rankability_status` (Chunk 9B assigns; Chunk 10
  persists).
- Must not reuse `models.EvidenceGrade` for the pre-sensitivity evidence state or
  `models.RankabilityStatus` as the preliminary rankability state type (R2).
- Must not compute any sensitivity output: no policy weights, no top-3/top-5
  stability, no rank displacement, no `sensitivity_warning`, no
  sensitivity-driven provisional demotion (Chunk 9B; R9).
- Must not derive or re-classify `DiscoveryStatus`, identity counts, or
  page-view semantics from payloads; they are consumed as explicit typed
  parameters (R7, R10).
- Must not mutate, rebuild, or alter a `ScoreResult` or its stored score fields
  when excluding a category from the candidate set (gate bullet 3).
- Must not add or remove candidates based on any sensitivity policy; the candidate
  set is constructed only from the LREQ-EVD-020 rules (line 994).
- Must not invent a numeric threshold, a new configurable weight, or a per-category
  identity-preflight field; constants come from `models.py` (R5, R6).
- Must not convert `None`/missing/unavailable to `0`/`0.0`, and must not treat a
  component-unavailable value as a zero-weight component.
- Must not use unseeded randomness or set/dict iteration order for output ordering
  (LREQ-ARCH-030).
- Must not edit `models.py`, `pipeline.py`, `Documents/`, `AGENTS.md`, or
  `.kilo/`; must not implement `field_reference_support_passes` with a
  component-availability-blind predicate (the keyword-only availability flags are
  part of the frozen signature; R11).

## 12. Open questions / assumptions

No open question remains. Q1–Q4 were resolved by lead rulings on 2026-09-21 and are
recorded below as RESOLVED with their SRS basis so a reviewer can re-check them.
No new SRS gap was found while applying them.

- **Q1 — RESOLVED (ruling: option (b)). Field-specific reference support is required
  only for the raw fields each *available* component consumes.** SRS basis:
  LREQ-EVD-020 line 993 states the requirement ("field-specific reference support
  passes"); §8.2 LREQ-SCR-010/-020/-030/-040 define which raw fields each component
  consumes (Demand ← `demand_per_asset_raw`, `demand_median_raw`; Competition ←
  `breadth_raw`; Recent supply ← `recent_share_raw`, `median_age_raw`; Quality ←
  `quality_raw`); and LREQ-SCR-010's "the one available normalized value when
  exactly one is available" means a component can be legitimately available from a
  single sub-signal, so a uniform six-field `> 0` rule would wrongly exclude it.
  The frozen predicate is
  `field_reference_support_passes(counts, *, demand_available,
  competition_available, recent_supply_available, quality_available)` (a **signature
  change** from the earlier draft's single-argument form; see §5/§5.1). Semantics:
  for each available component, every raw field it consumes must have
  `counts.<field> > 0`; an unavailable component contributes no requirement; all
  four unavailable → vacuous `True`, and that category is already `not_rankable`
  through the component-availability reasons. `FIELD_REFERENCE_SUPPORT_INSUFFICIENT`
  is emitted only when the predicate returns `False`.

- **Q2 — RESOLVED (ruling: option (a)).** `PreSensitivityEvidenceState` members are
  `SUFFICIENT = "sufficient"`, `PROVISIONAL_ONLY = "provisional_only"`,
  `INSUFFICIENT = "insufficient"`. The type is distinct from `models.EvidenceGrade`
  (R2): it is pre-sensitivity and is never assigned by Chunk 9A to a persisted
  `evidence_grade` column.

- **Q3 — RESOLVED (ruling).** Two rules:
  - `INCOMPLETE_BREADTH_FALLBACK` fires whenever `breadth_completeness_status is
    BreadthCompletenessStatus.INCOMPLETE_ESTIMATE`, **including** when
    `discovery_bounded_by_verified_total` is `True`; the provisional reason is about
    the fallback estimate itself (LREQ-MET-070 lines 758–759).
  - `COMPETITION_UNBOUNDED_OR_MATERIAL_FAILURE` fires exactly when
    `score.competition is None` (an unavailable competition component), the
    pure-layer expression of LREQ-MET-070's competition-unavailability conditions
    (lines 764–766). No new numeric threshold, no new enum, and no new input field
    is added.
  `discovery_bounded_by_verified_total = True` does not remove the
  `INCOMPLETE_BREADTH_FALLBACK` reason and does not by itself make a category
  not-rankable (LREQ-EVD-030 line 1000: "Discovery bounded by a verified total is
  sufficient for rankability and SHALL not by itself force a provisional status").

- **Q4 — RESOLVED (ruling).** `IdentityPreflightStatus.INSUFFICIENT` is treated as a
  preflight failure for the category: it fires `IDENTITY_PREFLIGHT_FAILED`, the same
  as `FAILED`. SRS basis: LREQ-EVD-020 line 985 lists "identity preflight fails" as
  a category-level cause, and a preflight that cannot establish identity reliability
  cannot make any category rankable; dependency-map §6.1 keeps run status and
  category not-rankable separate. The distinct `IdentityPreflightStatus` value is
  preserved only as the run-level input fact, not as a separate reason code.