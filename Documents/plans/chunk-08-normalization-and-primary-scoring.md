# Chunk 8 — Normalization and primary scoring

Status: FROZEN
Depends on (frozen interfaces required before this plan can be trusted):
  Documents/interfaces/chunk-7B.md (CategoryRawMetrics, RawMetricBundle, breadth
  provenance)
  Documents/interfaces/chunk-7A.md (metric value/eligibility null semantics)
  Documents/interfaces/chunk-02.md (persistence contract for LREQ-NRM-020's
  "stored separately" half)
  Documents/interfaces/chunk-05.md (page-view semantics status split: consumed,
  not detected)
Blocks (chunks whose plan/implementation needs this chunk's interface):
  Chunk 9A, Chunk 9B, Chunk 10, Chunk 11, Chunk 12 (all consume the normalized
  values / components / composite surface produced here)

## 1. Goal

Make `scoring.py` the pure owner of relative scoring: for each category in a run,
build the leave-one-out reference from all other categories, compute the six
field-specific midrank normalizations, derive the four components `D`, `C`, `R`,
`Q`, apply contradicted page-view handling, and combine them with the fixed Lean
v1 weights and available-component renormalization into a deterministic
within-run `market_opportunity_score` plus a `score_state`. Nothing here is a
sales, revenue, download, or demand prediction, and nothing here is a
statistically representative estimate.

## 2. Scope

### In scope
- Leave-one-out (LOO) reference construction: target excluded from its own
  reference; `reference_size = category_count - 1`; field-specific usable
  reference value tuples and field-specific usable counts (pure computation).
- Midrank normalization `P_ref(x) = (L + 0.5 * E) / m` for the six SRS fields,
  independently (LREQ-NRM-030, LREQ-NRM-040).
- Components `D`, `C`, `R`, `Q` from LREQ-SCR-010/-020/-030/-040, including
  coverage shrinkage (`0.5 + coverage * (X0 - 0.5)`), clamping to `[0, 1]`, and
  single-available-subsignal handling.
- Contradicted page-view handling (LREQ-SCR-050): when the caller-supplied
  run-level `page_view_semantics_status` is `contradicted`, `D` and `Q` are
  unavailable; `C` and `R` may remain available.
- Fixed Lean v1 primary weights (`W_D`, `W_C`, `W_R`, `W_Q` from `models.py`) and
  available-component renormalization (LREQ-SCR-060), including `score_state`.
- The pure half of LREQ-NRM-020 (reference size / field-specific usable counts).

### Explicitly out of scope (and who owns it instead)
- **LREQ-NRM-020 persistence half.** Primary owner is Chunk 8 but the completion
  chunk is **Chunk 10** (dependency map line 94). Chunk 8 owns only the pure
  reference-size and field-specific-usable-count computation; Chunk 8 writes
  nothing and does **not** serialize counts into `reference_usable_counts_json`
  or `reference_size` (those are `CategoryScoreRecord` columns persisted by
  Chunk 10). "A 21-category run stores reference size 20" is satisfied by Chunk 8
  computing `20` and Chunk 10 storing it.
- **Rankability.** LREQ-SCR-050's "the category SHALL not be rankable" clause is
  the consequence applied by **Chunk 9A** (dependency map rows 103–104,
  LREQ-EVD-010/-020; §9.1), which owns `base_rankable_candidates` and the
  not_rankable/provisional/rankable decision. Chunk 8 exposes the contradicted
  component outcome and leaves `ScoreResult.rankability_status` at its Chunk 0
  default; it never assigns rankability.
- **Evidence grading** (LREQ-EVD-*): Chunk 9A/9B.
- **Sensitivity policies and stability** (LREQ-SEN-*): Chunk 9B. Chunk 8 provides
  the weights-parameterized composite helper that lets 9B evaluate alternate
  policies over the same component values (see §5), but does not define, select,
  or evaluate any policy.
- **Coverage-threshold component unavailability is in scope; rankability is
  not.** Per SRS §7.5 lines 835–840 and §9.1 lines 1019–1022, a sample-derived
  component whose stratum eligibility coverage is below
  `MIN_REQUIRED_COMPONENT_COVERAGE` (0.50) "SHALL be unavailable for rankability
  and SHALL not receive composite weight". Chunk 8 implements the **component
  unavailability + no-composite-weight** half for `D` and `R` (using the frozen
  `models.MIN_REQUIRED_COMPONENT_COVERAGE` constant). `Q` is already nulled below
  the threshold by the frozen Chunk 7B behavior (plan §12 Q-3, option (a)), so
  Chunk 8 consumes `QualityRaw = None` and applies no second gate. `C` is not
  sample-derived and is unaffected by this threshold (LREQ-SCR-020). The
  rankability and base-candidate consequences (a category cannot be `rankable`
  when any required coverage is below the threshold; base-candidate construction)
  remain **Chunk 9A**'s (SRS §9.1; dependency-map Chunk 9A gate).
- **Persistence/DB** (Chunk 10), **pipeline orchestration** (Chunk 10),
  **report/CLI** (Chunks 11/12).
- **Contradicted detection**: Chunk 5 records nothing and Chunk 7B/7A consume the
  run-level value; the concrete detection rule is not part of Chunk 8. Chunk 8
  consumes `page_view_semantics_status` as an explicit parameter and must not
  re-detect contradiction from response shape (interfaces/chunk-05.md §5.8;
  interfaces/chunk-7B.md §5).

## 3. Requirements this chunk must satisfy

| LREQ ID | Ownership role here | Normative text (from SRS-lean.md, quoted/derived) | SRS section |
|---|---|---|---|
| LREQ-NRM-010 | Primary (pure) | "Every category SHALL be scored as a target. For target `c_i`, the reference contains all other categories in the same run." | §8.1 |
| LREQ-NRM-020 | Primary (pure half only); completion **Chunk 10** (persistence) | "`reference_size = category_count - 1`. Field-specific usable reference counts SHALL be stored separately. `STRONG_REFERENCE_CATEGORY_COUNT = 21` is an operational run-size threshold: a run with 21 categories qualifies for the strong-reference policy and has 20 leave-one-out peers for each target. The stored `reference_size` remains 20 for that run; the threshold SHALL not be misreported as 21 peers." | §8.1 |
| LREQ-NRM-030 | Primary (pure) | "For target `x` and usable reference values `r_1..r_m`: `L = count(r_k < x)`, `E = count(r_k = x)`, `P_ref(x) = (L + 0.5 * E) / m`. If `m = 0` or `x` is null, the normalized value is null. Ties receive the same midrank. These are descriptive relative positions, not inferential percentiles." | §8.1 |
| LREQ-NRM-040 | Primary (pure) | "Normalize independently: `DemandPerAssetRaw, DemandMedianRaw, BreadthRaw, RecentShareRaw, MedianAgeRaw, QualityRaw`. No log transform is required because strictly monotone transforms do not change midrank ordering." | §8.1 |
| LREQ-SCR-010 | Primary (pure) | "`D0 = 0.60 * P_ref(DemandPerAssetRaw) + 0.40 * P_ref(DemandMedianRaw)` when both normalized values are available; the one available normalized value when exactly one is available; unavailable when neither is available; `D = clamp(0.5 + demand_stratum_eligibility_coverage * (D0 - 0.5), 0, 1)`. `D` is unavailable when no demand raw value is usable." | §8.2 |
| LREQ-SCR-020 | Primary (pure) | "`C = clamp(1 - P_ref(BreadthRaw), 0, 1)`. It is available only with verified and sufficiently complete discovery." | §8.2 |
| LREQ-SCR-030 | Primary (pure) | "`Rpressure0 = 0.70 * P_ref(RecentShareRaw) + 0.30 * (1 - P_ref(MedianAgeRaw))` when both normalized values are available; the one available normalized value when exactly one is available; unavailable when neither is available; `R0 = 1 - Rpressure0`; `R = clamp(0.5 + recent_supply_stratum_eligibility_coverage * (R0 - 0.5), 0, 1)`." | §8.2 |
| LREQ-SCR-040 | Primary (pure) | "`Q0 = 1 - P_ref(QualityRaw)`; `Q = clamp(0.5 + quality_stratum_eligibility_coverage * (Q0 - 0.5), 0, 1)`." | §8.2 |
| LREQ-SCR-050 | Primary (pure) | "If `page_view_semantics_status = "contradicted"`, `D` and `Q` SHALL be unavailable. `C` and `R` MAY remain available, but the category SHALL not be rankable." (Chunk 8 applies the D/Q half; the rankability half is Chunk 9A — see §2.) | §8.2 |
| LREQ-SCR-060 | Primary (pure) | "`W_A = sum(weights of available components)`, `S_available = sum(weight_x * x for available x) / W_A`; `market_opportunity_score = null, score_state = "unavailable"` when fewer than two components are available; `market_opportunity_score = clamp(0.5 + W_A * (S_available - 0.5), 0, 1)`, `score_state = "available"` when all four components are available, otherwise `"partial"`, when at least two components are available." | §8.3 |
| LREQ-NFR-040 | Supporting (Chunk 0 primary; completion Chunk 13) | "Public metric and scoring functions SHALL have type hints and docstrings describing null and edge-case behavior." | §11 |
| LREQ-TST-010 | Supporting (Chunk 13 primary; completion Chunk 13) | "Every formula SHALL have tests for normal values, explicit valid zero where applicable, missing values, invalid values, ties, and minimum boundaries." | §13 |
| LREQ-TST-060 | Supporting (Chunk 13 primary; completion Chunk 13) | "Scoring tests SHALL cover midrank ties, all-equal references, missing-component renormalization, coverage shrinkage, contradicted page views, 8-category provisional runs, 21-category strong-reference runs…" (Chunk 8 covers the normalization/component/composite subset; fixed base candidates, sensitivity-driven status, and non-rankability are 9A/9B.) | §13 |
| LREQ-ARCH-010 | Supporting (Chunk 0 primary) | "`metrics` and `scoring` SHALL accept plain typed input structures and return typed result structures. They SHALL not import or call `collector`, `database`, `report`, or `cli` code, and SHALL perform no network or file I/O." | §3.3 |
| LREQ-ARCH-020 | Supporting (Chunk 0 primary) | "Pure metric and scoring functions SHALL NOT read the system clock. All timestamps SHALL be supplied by the orchestration layer." | §3.3 |
| LREQ-ARCH-030 | Supporting (Chunk 0 primary) | "The same normalized input data, policy versions, and configuration SHALL produce the same metric, score, evidence, and sensitivity outputs." | §3.3 |

**Cross-requirement availability clause (applies to LREQ-SCR-010, -030, -040).**
SRS §7.5 lines 835–840: "The same `MIN_REQUIRED_COMPONENT_COVERAGE` policy
applies to Demand and Recent Supply: if `demand_stratum_eligibility_coverage` or
`recent_supply_stratum_eligibility_coverage` is below the threshold, the affected
component SHALL be unavailable for rankability and SHALL not receive composite
weight. Coverage below the threshold SHALL remain distinguishable from a valid
metric value of zero." SRS §9.1 lines 1019–1022: "A component below this
threshold is unavailable for rankability and receives no composite weight." With
`MIN_REQUIRED_COMPONENT_COVERAGE = 0.50` (§9.1 line 1015 / §14 line 1292), Chunk
8 makes a below-threshold `D`/`R`/`Q` component unavailable (so it receives no
composite weight under LREQ-SCR-060); the rankability consequence remains Chunk
9A's.

## 4. Interface contracts consumed

Copied from the frozen interfaces (not re-derived from source).

### 4.1 From `interfaces/chunk-7B.md` (`niche_scout.metrics`)

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

`RawMetricBundle` (Chunk 0, unchanged): six `float | None` fields
`demand_per_asset_raw`, `demand_median_raw`, `breadth_raw`, `recent_share_raw`,
`median_age_raw`, `quality_raw`. `None` means unavailable; `0.0` is an explicit
valid value. `raw.breadth_raw` is the integral breadth stored as `float`.

Breadth provenance enums (`models.py`): `BreadthSource.VERIFIED_TOTAL_COUNT` /
`DISTINCT_CANONICAL_DISCOVERED_COUNT`, `BreadthCompletenessStatus.COMPLETE` /
`INCOMPLETE_ESTIMATE`. Chunk 7B guarantees: a verified `totalCount` category is
`verified_total_count` + `complete`; the fallback is
`distinct_canonical_discovered_count` + `incomplete_estimate`; a verified
zero-result category is `BreadthRaw == 0.0` + `verified_total_count` + `complete`.

### 4.2 From `interfaces/chunk-7A.md`

`MetricValue`/`MetricEligibility` null contract: `value is None` iff unavailable;
`0.0` is an explicit valid zero; product-level invalidity is classified upstream
and never reaches `scoring.py` as a fabricated zero. Chunk 8 consumes only the
already-computed raw values, so it performs no re-classification.

### 4.3 From `interfaces/chunk-02.md` (persistence contract for LREQ-NRM-020)

`category_scores` exposes `reference_size: int` and
`reference_usable_counts_json: str` (`CategoryScoreRecord`); `upsert_category_scores`
rewrites every non-key column of `(run_id, category)`. Chunk 8 produces the pure
values; Chunk 10 maps them to those columns. Chunk 8 does not import
`database`, `sqlite3`, or serialize JSON.

### 4.4 From `interfaces/chunk-05.md` (page-view semantics status)

`models.PageViewSemanticsStatus` = `unvalidated` / `validated_cumulative` /
`contradicted`. The run-level value is **consumed, never detected**: Chunk 5
initializes nothing, Chunk 6A initializes the run value, Chunk 7B consumes it for
quality eligibility, and Chunk 8 consumes it for LREQ-SCR-050. If it is
`contradicted`, `D` and `Q` are unavailable; `C` and `R` may remain.

### 4.5 Existing frozen Chunk 0 names (NOT redefined)

`scoring.ScoringInput`, `scoring.ScoreResult` (fields
`market_opportunity_score`, `score_state`, `component_d`, `component_c`,
`component_r`, `component_q`, `available_component_count`, `rankability_status`,
`evidence_grade`), `scoring.SensitivityResult`; `models.ScoreState`,
`models.RankabilityStatus`, `models.EvidenceGrade`; weights/subweights
`W_D=0.35`, `W_C=0.30`, `W_R=0.20`, `W_Q=0.15`,
`DEMAND_SUBWEIGHT_PER_ASSET=0.60`, `DEMAND_SUBWEIGHT_MEDIAN=0.40`,
`RECENT_SUBWEIGHT_SHARE=0.70`, `RECENT_SUBWEIGHT_AGE=0.30`,
`SENSITIVITY_POLICIES["balanced"] == {"D":0.35,"C":0.30,"R":0.20,"Q":0.15}`,
`STRONG_REFERENCE_CATEGORY_COUNT=21`, `MIN_CATEGORIES_PER_RUN=8`.

## 5. Interface contract this chunk produces

Additive to `src/niche_scout/scoring.py`; no Chunk 0 name is modified.

```python
COMPONENT_WEIGHT_KEYS: tuple[str, ...] = ("D", "C", "R", "Q")
# Fixed iteration order for deterministic weight summation; the key spelling is
# already used by models.SENSITIVITY_POLICIES.

@dataclass(frozen=True, slots=True)
class FieldUsableCounts:
    demand_per_asset_raw: int
    demand_median_raw: int
    breadth_raw: int
    recent_share_raw: int
    median_age_raw: int
    quality_raw: int

@dataclass(frozen=True, slots=True)
class LeaveOneOutReference:
    target_category: str
    reference_size: int
    demand_per_asset_raw: tuple[float, ...]
    demand_median_raw: tuple[float, ...]
    breadth_raw: tuple[float, ...]
    recent_share_raw: tuple[float, ...]
    median_age_raw: tuple[float, ...]
    quality_raw: tuple[float, ...]
    @property
    def field_usable_counts(self) -> FieldUsableCounts: ...

@dataclass(frozen=True, slots=True)
class NormalizedValues:
    demand_per_asset_raw: float | None
    demand_median_raw: float | None
    breadth_raw: float | None
    recent_share_raw: float | None
    median_age_raw: float | None
    quality_raw: float | None

@dataclass(frozen=True, slots=True)
class ComponentValues:
    demand: float | None
    competition: float | None
    recent_supply: float | None
    quality: float | None
    @property
    def available_component_count(self) -> int: ...

@dataclass(frozen=True, slots=True)
class CompositeResult:
    market_opportunity_score: float | None
    score_state: ScoreState
    available_component_count: int
    available_weight: float

def midrank(target: float | None, reference_values: Sequence[float]) -> float | None: ...

def leave_one_out_reference(
    all_metrics: Sequence[CategoryRawMetrics], target_category: str
) -> LeaveOneOutReference: ...

def normalize_raw_metrics(
    raw: RawMetricBundle, reference: LeaveOneOutReference
) -> NormalizedValues: ...

def demand_component(
    normalized: NormalizedValues,
    *,
    demand_stratum_eligibility_coverage: float,
    min_required_component_coverage: float = MIN_REQUIRED_COMPONENT_COVERAGE,
) -> float | None: ...

def competition_component(
    normalized: NormalizedValues,
    *,
    breadth_source: BreadthSource,
    breadth_completeness_status: BreadthCompletenessStatus,
) -> float | None: ...

def recent_supply_component(
    normalized: NormalizedValues,
    *,
    recent_supply_stratum_eligibility_coverage: float,
    min_required_component_coverage: float = MIN_REQUIRED_COMPONENT_COVERAGE,
) -> float | None: ...

def quality_component(
    normalized: NormalizedValues,
    *,
    quality_stratum_eligibility_coverage: float,
    min_required_component_coverage: float = MIN_REQUIRED_COMPONENT_COVERAGE,
) -> float | None: ...

def compute_components(
    normalized: NormalizedValues,
    *,
    demand_stratum_eligibility_coverage: float,
    recent_supply_stratum_eligibility_coverage: float,
    quality_stratum_eligibility_coverage: float,
    breadth_source: BreadthSource,
    breadth_completeness_status: BreadthCompletenessStatus,
    page_view_semantics_status: PageViewSemanticsStatus,
    min_required_component_coverage: float = MIN_REQUIRED_COMPONENT_COVERAGE,
) -> ComponentValues: ...

def renormalized_composite(
    components: ComponentValues, weights: Mapping[str, float]
) -> CompositeResult: ...

def balanced_composite(components: ComponentValues) -> CompositeResult: ...

def score_category(
    target: CategoryRawMetrics,
    all_metrics: Sequence[CategoryRawMetrics],
    *,
    page_view_semantics_status: PageViewSemanticsStatus,
) -> ScoreResult: ...
```

**Coverage-threshold rule (SRS §7.5 lines 835–840; §9.1 lines 1019–1022).** A
sample-derived component (`D`, `R`, `Q`) whose stratum eligibility coverage is
strictly below `min_required_component_coverage` (`MIN_REQUIRED_COMPONENT_COVERAGE
= 0.50`, imported from `models`) is **unavailable** and receives no composite
weight: the component function returns `None` before applying any shrinkage.
Coverage exactly equal to the threshold is available. `min_required_component_coverage`
is an explicit keyword parameter defaulting to the frozen constant (same pattern
as `metrics.CategoryMetricInput.min_required_component_coverage`); it is not a
new configurable weight and `models.py` is not edited. `C` is not sample-derived
and is unaffected by this threshold (its availability is LREQ-SCR-020).

Contract details:
- `midrank`: `target is None` → `None`; empty `reference_values` (`m == 0`) →
  `None`; otherwise `L = count(r < x)`, `E = count(r == x)`,
  `(L + 0.5 * E) / m` with exact float equality for `E`. Non-finite `target` or
  any non-finite reference element → `ValueError` (caller breach; mirrors
  `metrics.weighted_median`). Duplicate reference values stay repeated and count
  in `m`.
- `leave_one_out_reference`: `reference_size = len(all_metrics) - 1`. The target's
  own entry is excluded from every value tuple. Each field tuple holds the peer
  values that are not `None`, in `all_metrics` order. `field_usable_counts` counts
  those non-null peers per field (breadth counts equal `reference_size` when every
  peer is present). `ValueError` when `all_metrics` is empty, `target_category` is
  not a non-empty `str`, no entry matches, or two entries share a `category`.
  Referencing is stable under input order.
- `normalize_raw_metrics`: applies `midrank` independently to the six raw fields
  against the corresponding reference tuple (LREQ-NRM-040). No log transform.
  A `None` raw value or an empty field reference yields `None` for that field.
- `demand_component`: `None` when
  `demand_stratum_eligibility_coverage < min_required_component_coverage`
  (SRS §7.5). Otherwise `D0 = 0.60 * a + 0.40 * b` when both
  `P_ref(DemandPerAssetRaw)=a` and `P_ref(DemandMedianRaw)=b` are not `None`;
  `D0` = the single available value when exactly one is not `None`; `None` when
  both are `None`. Then `clamp(0.5 + coverage * (D0 - 0.5), 0, 1)`. Uses
  `models.DEMAND_SUBWEIGHT_PER_ASSET` / `DEMAND_SUBWEIGHT_MEDIAN`. A
  `min_required_component_coverage` that is non-finite or outside `[0, 1]` is a
  caller/policy breach → `ValueError`.
- `competition_component`: `None` unless
  `breadth_source is BreadthSource.VERIFIED_TOTAL_COUNT` **and**
  `breadth_completeness_status is BreadthCompletenessStatus.COMPLETE` **and**
  `P_ref(BreadthRaw)` is not `None`; otherwise
  `clamp(1 - P_ref(BreadthRaw), 0, 1)`. No coverage shrinkage (SRS §8.2).
- `recent_supply_component`: `None` when
  `recent_supply_stratum_eligibility_coverage < min_required_component_coverage`
  (SRS §7.5). Otherwise, with `s = P_ref(RecentShareRaw)`,
  `a = P_ref(MedianAgeRaw)`:
  `Rpressure0 = 0.70 * s + 0.30 * (1 - a)` when both available; the single
  available pressure term (`s`, or `(1 - a)`) when exactly one is available;
  `None` when neither. `R0 = 1 - Rpressure0`;
  `R = clamp(0.5 + coverage * (R0 - 0.5), 0, 1)`. Uses
  `models.RECENT_SUBWEIGHT_SHARE` / `RECENT_SUBWEIGHT_AGE`; the
  threshold-parameter validation matches `demand_component`. (When one term is
  available, weighting the single term by 0.70/0.30 renormalized over available
  subweights gives the same value as using the term directly; both readings
  coincide.)
- `quality_component`: `None` when
  `quality_stratum_eligibility_coverage < min_required_component_coverage` or
  when `P_ref(QualityRaw)` is `None`; else `Q0 = 1 - P_ref(QualityRaw)` and
  `Q = clamp(0.5 + coverage * (Q0 - 0.5), 0, 1)`. Chunk 7B already returns
  `QualityRaw = None` below the threshold, on contradicted semantics, and on a
  zero denominator, so the threshold check is defensive and consistent (it
  cannot change a Chunk 7B-produced value). The threshold-parameter validation
  matches `demand_component`.
- `compute_components`: validates `min_required_component_coverage` once, calls
  the four component functions with the supplied scalars (passing the threshold
  to `demand_component`, `recent_supply_component`, `quality_component`), then,
  when `page_view_semantics_status is PageViewSemanticsStatus.CONTRADICTED`,
  replaces `demand` and `quality` with `None` (LREQ-SCR-050). `competition` and
  `recent_supply` are unchanged by contradicted semantics.
- `renormalized_composite`: iterates `COMPONENT_WEIGHT_KEYS` in order.
  `ValueError` when `weights` is missing any key or a weight is non-finite or
  negative. Available components are those with a non-`None` component value.
  `available_weight = W_A = sum(weights of available components)` in key order.
  If `available_component_count < 2`: `market_opportunity_score = None`,
  `score_state = ScoreState.UNAVAILABLE`. Else, if `W_A <= 0`: `ValueError`;
  otherwise `S_available = sum(w_x * x) / W_A` in key order and
  `market_opportunity_score = clamp(0.5 + W_A * (S_available - 0.5), 0, 1)` with
  `score_state = AVAILABLE` when all four are available else `PARTIAL`.
- `balanced_composite`: `renormalized_composite` with the fixed primary weights
  built from `models.W_D/W_C/W_R/W_Q`. Because those sum to `1.0`, a four-component
  score equals `S_available`.
- `score_category`: pure wiring over one target — reference → normalized →
  components → composite → `ScoreResult(market_opportunity_score,
  score_state, component_d, component_c, component_r, component_q,
  available_component_count)`. `rankability_status` and `evidence_grade` are
  left at their Chunk 0 defaults; Chunk 8 assigns neither. The caller supplies
  `page_view_semantics_status` explicitly (the pure module does not read it from
  a record).

## 6. Files touched

| File | New/modified | Purpose |
|---|---|---|
| `src/niche_scout/scoring.py` | Modified (additive) | LOO reference, midrank, `D`/`C`/`R`/`Q`, contradicted handling, weights, composite, score state |
| `tests/test_scoring.py` | New | Chunk 8 analytical tests (marked + traceability entries) |
| `tests/fixtures/scoring_fixtures.py` | New | Data-only golden vectors and builders for the scoring tests |
| `tests/fixtures/__init__.py` | Modified | Re-export the new fixture module for consistency with existing modules |
| `tests/traceability.json` | Modified | Node → LREQ entries for the new scoring tests |

## 7. Task breakdown

- [ ] Add `FieldUsableCounts`, `LeaveOneOutReference`, `NormalizedValues`,
      `ComponentValues`, `CompositeResult` typed structures and
      `COMPONENT_WEIGHT_KEYS` to `scoring.py`, and import
      `MIN_REQUIRED_COMPONENT_COVERAGE` from `models` (no edit to `models.py`)
      (LREQ-NRM-020, LREQ-SCR-060).
- [ ] Implement `midrank` with null/empty/non-finite semantics (LREQ-NRM-030).
- [ ] Implement `leave_one_out_reference` with target exclusion, `reference_size`,
      and field-specific usable counts (LREQ-NRM-010, LREQ-NRM-020).
- [ ] Implement `normalize_raw_metrics` over the six fields independently
      (LREQ-NRM-040).
- [ ] Implement `demand_component` with the below-threshold unavailability
      (`min_required_component_coverage`), both/one/neither sub-signals, and
      coverage shrinkage/clamp (LREQ-SCR-010; SRS §7.5/§9.1).
- [ ] Implement `competition_component` with the verified+complete breadth gate
      and clamping (LREQ-SCR-020).
- [ ] Implement `recent_supply_component` with the below-threshold
      unavailability, both/one/neither pressure terms, and coverage
      shrinkage/clamp (LREQ-SCR-030; SRS §7.5/§9.1).
- [ ] Implement `quality_component` with the below-threshold unavailability, null
      quality, and coverage shrinkage/clamp (LREQ-SCR-040; SRS §7.5/§9.1).
- [ ] Implement `compute_components` (threshold pass-through, one-time parameter
      validation) including the contradicted page-view override (LREQ-SCR-050).
- [ ] Implement `renormalized_composite` and `balanced_composite` using the fixed
      Lean v1 weights (LREQ-SCR-060).
- [ ] Implement `score_category` wiring and leave rankability/evidence at their
      defaults (LREQ-SCR-060).
- [ ] Add type hints and null/edge-case docstrings to every public function
      (LREQ-NFR-040).
- [ ] Write `tests/fixtures/scoring_fixtures.py` golden vectors (data only).
- [ ] Write `tests/test_scoring.py` with the §9 markers.
- [ ] Add the §9 `tests/traceability.json` entries and re-export the fixture
      module.
- [ ] Run `ruff format`, `ruff check`, `python -m pytest tests/test_scoring.py -q`,
      the full suite, `python -m niche_scout.tools.check_import_boundaries`, and
      `python -m niche_scout.tools.validate_traceability`.

## 8. Edge cases and invariants

From the dependency map's edge-case column for every LREQ this chunk owns, plus
the chunk's own gate/description:

- Every category is a target; a category never appears in its own LOO reference
  (LREQ-NRM-010; gate).
- `reference_size = category_count - 1`; field-specific usable counts; 21
  categories means 20 peers, never 21 (LREQ-NRM-020; gate).
- Midrank: null target, empty reference, ties (same midrank), all-equal
  reference (LREQ-NRM-030).
- Normalization is independent per field; no log transform; null raw fields stay
  null (LREQ-NRM-040).
- `D`: both, one, or neither demand sub-signal available; coverage shrinkage;
  below-threshold coverage (`< MIN_REQUIRED_COMPONENT_COVERAGE`) → unavailable
  before shrinkage; coverage exactly `0.50` is available; clamping
  (LREQ-SCR-010; SRS §7.5/§9.1).
- `C`: unverified or incomplete breadth → unavailable; null reference →
  unavailable; clamping; **not** affected by the sample-derived coverage
  threshold (LREQ-SCR-020).
- `R`: both, one, or neither recent-supply sub-signal available; coverage
  shrinkage; below-threshold coverage → unavailable
  (LREQ-SCR-030; SRS §7.5/§9.1).
- `Q`: null quality; insufficient quality support (already null from Chunk 7B);
  zero denominator; coverage shrinkage; below-threshold coverage → unavailable
  (defensive, consistent with Chunk 7B) (LREQ-SCR-040; SRS §7.5/§9.1).
- A below-threshold sample-derived component receives no composite weight: it is
  `None`, so `W_A` excludes its weight and `score_state` follows the
  available-component count (LREQ-SCR-060; SRS §7.5/§9.1).
- Contradicted page views disable `D` and `Q`; `C` and `R` may remain available
  (LREQ-SCR-050).
- Fewer than two components → `market_opportunity_score = None`,
  `score_state = unavailable`; partial score and available-weight
  renormalization; fixed primary weights (LREQ-SCR-060; gate).
- Balanced primary scoring exactly matches the balanced sensitivity weights
  (gate); `score_state` (`unavailable`, `partial`, `available`) is distinct from
  `rankability_status` (`not_rankable`, `provisional`, `rankable`) (gate).
- Missing is not zero: a `None` component/raw/reference is never treated as
  `0.0`; an explicit `0.0` raw (e.g. verified zero breadth) is a value.
- Determinism: fixed key iteration order, no set/dict iteration for numeric
  order, no clock, no randomness (LREQ-ARCH-030).
- Purity: `scoring.py` imports only `dataclasses`, `datetime`/`timezone` (type
  validation), `typing`, `collections.abc`, `math.isfinite` if needed, plus
  `models` and (for types) `metrics`; never `collector*`, `database`, `pipeline`,
  `report`, `cli`, `config`, `sqlite3`, or an I/O/clock module
  (LREQ-ARCH-010, LREQ-ARCH-020).

## 9. Test plan

### Test files
- Extend/create `tests/test_scoring.py` (currently absent; new file).
- New data-only fixture module `tests/fixtures/scoring_fixtures.py`; re-export it
  from `tests/fixtures/__init__.py`.

### Golden vectors / fixtures needed
All expected values are hand-derived from SRS §8 and Appendix A; none is copied
from the implementation. Fixtures are inert constants/builders only.

- **Midrank vectors** (`(label, target, reference_values, expected)`):
  - `(2.0, (1.0, 2.0, 3.0))` → `L=1, E=1, m=3` → `0.5`.
  - `(1.0, (1.0, 1.0, 3.0))` → `L=0, E=2, m=3` → `1/3 = 0.3333333333333333`.
  - `(1.0, (2.0, 3.0, 4.0))` → `0.0` (minimum boundary).
  - `(4.0, (1.0, 2.0, 3.0))` → `1.0` (maximum boundary).
  - `(5.0, (2.0, 2.0, 2.0))` → `1.0` (all-equal reference, target above all; `L=3, E=0, m=3`). *(Corrected 2026-09-21 by the lead: the frozen plan had a transcription error `0.0`; SRS §8.1 / LREQ-NRM-030 gives `(3 + 0)/3 = 1.0`. The test asserts `1.0`; `test-author` raised this as a `DISPUTE` and was upheld.)*
  - `(2.0, (2.0, 2.0, 2.0))` → `0.5` (all-equal reference, target equals all).
  - `(2.0, (1.0, 1.0, 1.0, 3.0, 3.0, 3.0))` → `L=3, E=0, m=6` → `0.5`.
  - `(None, (1.0,))` → `None`; `(1.0, ())` → `None`.
- **Reference-size fixtures**: a builder producing `CategoryRawMetrics` from an
  explicit `RawMetricBundle` plus coverages/provenance. 8-category run → every
  target `reference_size == 7`; 21-category run → `20`, and for target `"c-10"`
  with `demand_per_asset_raw = float(i)` the reference tuple is
  `(0.0..9.0, 11.0..20.0)` (`m = 20`, `P_ref(10.0) = 0.5`). One-category run →
  `reference_size == 0`, all field counts `0`.
- **Field-usable-count fixture**: an 8-category bundle where two peers have
  `quality_raw = None` → `quality_raw` count `5`, other counts `7`.
- **Component vectors** (hand-computed from SRS §8.2, with the §7.5/§9.1
  below-threshold rule; threshold `0.50`):
  - `D`: `a=1.0, b=0.0` → `D0 = 0.6`; coverage `1.0` → `0.6`; coverage `0.5`
    (boundary, available) → `0.55`; coverage `0.49` → `None`. Only `a=0.8` →
    `D0 = 0.8`, coverage `1.0` → `0.8`. Neither sub-signal → `None`.
  - `C`: `P_ref(BreadthRaw)=0.25`, verified+complete → `0.75`; same value with
    fallback source or `incomplete_estimate` → `None`; verified zero breadth
    (`P_ref = 0.0`) → `1.0`. `C` is not gated by the coverage threshold.
  - `R`: `s=0.9, a=0.2` → `Rpressure0 = 0.7*0.9 + 0.3*0.8 = 0.87`, `R0 = 0.13`;
    coverage `1.0` → `0.13`, coverage `0.5` → `0.315`, coverage `0.49` →
    `None`. Only `s=0.9` → `R0 = 0.1`. Only `a=0.2` → `R0 = 0.2`. Neither →
    `None`.
  - `Q`: `P_ref(QualityRaw)=0.4` → `Q0 = 0.6`; coverage `1.0` → `0.6`, coverage
    `0.5` → `0.55`, coverage `0.49` → `None`; `P_ref(QualityRaw)=None` → `None`.
- **Composite vectors** (hand-computed from SRS §8.3, `W_A`, `S_available`):
  - All four `D=0.8, C=0.6, R=0.4, Q=0.2`: `W_A=1.0`,
    `S=0.57`, score `0.57`, `available`, count `4`.
  - Drop `Q` (`D=0.8, C=0.6, R=0.4`): `W_A=0.85`,
    `S=0.54/0.85=0.6352941176470588`, score `0.615`, `partial`, count `3`.
  - Drop `R,Q` (`D=0.8, C=0.6`): `W_A=0.65`,
    `S=0.46/0.65=0.7076923076923077`, score `0.635`, `partial`, count `2`.
  - `D=1.0, Q=0.0`: `W_A=0.50`, `S=0.7`, score `0.6`, `partial`, count `2`.
  - Low-coverage `D` excluded (`demand coverage 0.49` → `D=None`; `C=0.6,
    R=0.4, Q=0.2`): `W_A=0.30+0.20+0.15=0.65`,
    `S=(0.30*0.6+0.20*0.4+0.15*0.2)/0.65=0.29/0.65=0.44615384615384617`, score
    `0.5+0.65*(S-0.5)=0.465`, `partial`, count `3`.
  - One component `D=0.8`: `None`, `unavailable`, count `1`.
  - No components: `None`, `unavailable`, count `0`.
- **Contradicted fixture**: full four-component normalized input under
  `PageViewSemanticsStatus.CONTRADICTED` → `demand is None`, `quality is None`,
  `competition`/`recent_supply` equal their non-contradicted values; under
  `UNVALIDATED` all four are present.
- **Fixed-weight vectors**: `models.W_D/W_C/W_R/W_Q == 0.35/0.30/0.20/0.15` and
  `models.SENSITIVITY_POLICIES["balanced"] == {"D":0.35,"C":0.30,"R":0.20,"Q":0.15}`;
  `balanced_composite(c) == renormalized_composite(c, SENSITIVITY_POLICIES["balanced"])`
  for every composite vector.

> **Below-threshold fixtures (SRS §7.5/§9.1).** The vectors above include
> `coverage = 0.49` → `D`/`R`/`Q` `None`, `coverage = 0.50` → available
> (boundary), and a composite where a below-threshold `D` is excluded from
> `W_A`. `C` has no below-threshold vector because `C` is not sample-derived.

### Exact `@pytest.mark.lreq(...)` markers (1:1 with §3)

| Test node | LREQ marker(s) |
|---|---|
| `test_midrank_golden_vectors` | `LREQ-NRM-030`, `LREQ-TST-010` |
| `test_midrank_ties_receive_same_midrank` | `LREQ-NRM-030` |
| `test_midrank_all_equal_reference` | `LREQ-NRM-030` |
| `test_midrank_null_target_or_empty_reference_returns_none` | `LREQ-NRM-030` |
| `test_midrank_rejects_non_finite_values` | `LREQ-NRM-030` |
| `test_leave_one_out_reference_excludes_target` | `LREQ-NRM-010` |
| `test_reference_size_is_category_count_minus_one` | `LREQ-NRM-020` |
| `test_eight_and_twenty_one_category_run_reference_sizes` | `LREQ-NRM-020`, `LREQ-TST-060` |
| `test_field_specific_usable_reference_counts` | `LREQ-NRM-020` |
| `test_leave_one_out_reference_rejects_absent_or_duplicate_target` | `LREQ-NRM-010` |
| `test_normalize_raw_metrics_independently` | `LREQ-NRM-040` |
| `test_normalize_raw_metrics_null_target_and_null_reference` | `LREQ-NRM-040` |
| `test_demand_component_both_one_or_neither_field` | `LREQ-SCR-010` |
| `test_demand_component_coverage_shrinkage_and_clamp` | `LREQ-SCR-010` |
| `test_competition_component_requires_verified_complete_breadth` | `LREQ-SCR-020` |
| `test_competition_component_inverts_midrank_and_clamps` | `LREQ-SCR-020` |
| `test_recent_supply_component_both_one_or_neither_field` | `LREQ-SCR-030` |
| `test_recent_supply_component_coverage_shrinkage` | `LREQ-SCR-030` |
| `test_quality_component_null_or_shrunk` | `LREQ-SCR-040` |
| `test_below_minimum_component_coverage_is_unavailable` | `LREQ-SCR-010`, `LREQ-SCR-030`, `LREQ-SCR-040` |
| `test_contradicted_page_views_disable_demand_and_quality` | `LREQ-SCR-050` |
| `test_contradicted_page_views_keep_competition_and_recent_supply` | `LREQ-SCR-050` |
| `test_fewer_than_two_components_score_unavailable` | `LREQ-SCR-060` |
| `test_two_or_three_components_score_partial` | `LREQ-SCR-060` |
| `test_available_component_weight_renormalization` | `LREQ-SCR-060` |
| `test_balanced_primary_matches_balanced_sensitivity_policy` | `LREQ-SCR-060`, `LREQ-TST-060` |
| `test_score_category_integration_and_score_state` | `LREQ-SCR-060` |
| `test_score_state_field_is_distinct_from_rankability_status` | `LREQ-SCR-060` |
| `test_scoring_public_functions_have_type_hints_and_docstrings` | `LREQ-NFR-040` |
| `test_scoring_module_is_import_pure_and_clock_free` | `LREQ-ARCH-010`, `LREQ-ARCH-020` |
| `test_scoring_outputs_are_deterministic` | `LREQ-ARCH-030` |

### `tests/traceability.json` entries to add

```json
{
  "tests/test_scoring.py::test_midrank_golden_vectors": ["LREQ-NRM-030", "LREQ-TST-010"],
  "tests/test_scoring.py::test_midrank_ties_receive_same_midrank": ["LREQ-NRM-030"],
  "tests/test_scoring.py::test_midrank_all_equal_reference": ["LREQ-NRM-030"],
  "tests/test_scoring.py::test_midrank_null_target_or_empty_reference_returns_none": ["LREQ-NRM-030"],
  "tests/test_scoring.py::test_midrank_rejects_non_finite_values": ["LREQ-NRM-030"],
  "tests/test_scoring.py::test_leave_one_out_reference_excludes_target": ["LREQ-NRM-010"],
  "tests/test_scoring.py::test_reference_size_is_category_count_minus_one": ["LREQ-NRM-020"],
  "tests/test_scoring.py::test_eight_and_twenty_one_category_run_reference_sizes": ["LREQ-NRM-020", "LREQ-TST-060"],
  "tests/test_scoring.py::test_field_specific_usable_reference_counts": ["LREQ-NRM-020"],
  "tests/test_scoring.py::test_leave_one_out_reference_rejects_absent_or_duplicate_target": ["LREQ-NRM-010"],
  "tests/test_scoring.py::test_normalize_raw_metrics_independently": ["LREQ-NRM-040"],
  "tests/test_scoring.py::test_normalize_raw_metrics_null_target_and_null_reference": ["LREQ-NRM-040"],
  "tests/test_scoring.py::test_demand_component_both_one_or_neither_field": ["LREQ-SCR-010"],
  "tests/test_scoring.py::test_demand_component_coverage_shrinkage_and_clamp": ["LREQ-SCR-010"],
  "tests/test_scoring.py::test_competition_component_requires_verified_complete_breadth": ["LREQ-SCR-020"],
  "tests/test_scoring.py::test_competition_component_inverts_midrank_and_clamps": ["LREQ-SCR-020"],
  "tests/test_scoring.py::test_recent_supply_component_both_one_or_neither_field": ["LREQ-SCR-030"],
  "tests/test_scoring.py::test_recent_supply_component_coverage_shrinkage": ["LREQ-SCR-030"],
  "tests/test_scoring.py::test_quality_component_null_or_shrunk": ["LREQ-SCR-040"],
  "tests/test_scoring.py::test_below_minimum_component_coverage_is_unavailable": ["LREQ-SCR-010", "LREQ-SCR-030", "LREQ-SCR-040"],
  "tests/test_scoring.py::test_contradicted_page_views_disable_demand_and_quality": ["LREQ-SCR-050"],
  "tests/test_scoring.py::test_contradicted_page_views_keep_competition_and_recent_supply": ["LREQ-SCR-050"],
  "tests/test_scoring.py::test_fewer_than_two_components_score_unavailable": ["LREQ-SCR-060"],
  "tests/test_scoring.py::test_two_or_three_components_score_partial": ["LREQ-SCR-060"],
  "tests/test_scoring.py::test_available_component_weight_renormalization": ["LREQ-SCR-060"],
  "tests/test_scoring.py::test_balanced_primary_matches_balanced_sensitivity_policy": ["LREQ-SCR-060", "LREQ-TST-060"],
  "tests/test_scoring.py::test_score_category_integration_and_score_state": ["LREQ-SCR-060"],
  "tests/test_scoring.py::test_score_state_field_is_distinct_from_rankability_status": ["LREQ-SCR-060"],
  "tests/test_scoring.py::test_scoring_public_functions_have_type_hints_and_docstrings": ["LREQ-NFR-040"],
  "tests/test_scoring.py::test_scoring_module_is_import_pure_and_clock_free": ["LREQ-ARCH-010", "LREQ-ARCH-020"],
  "tests/test_scoring.py::test_scoring_outputs_are_deterministic": ["LREQ-ARCH-030"]
}
```

## 10. Definition of done (gate)

Copied verbatim from `Documents/requirements-dependency-map.md` Chunk 8:

- A category never appears in its own LOO reference.
- A 21-category run stores reference size 20.
- Fewer than two components produces an unavailable score.
- Balanced primary scoring exactly matches balanced sensitivity weights.
- `score_state` (`unavailable`, `partial`, `available`) is distinct from `rankability_status` (`not_rankable`, `provisional`, `rankable`).

## 11. Explicit prohibitions

- Must not import or call `collector`, `collector_coveo`, `collector_graphql`,
  `database`, `pipeline`, `report`, `cli`, `config`, or any filesystem/network/
  clock module; must not read the system clock (LREQ-ARCH-010/020).
- Must not redefine, shadow, or modify Chunk 0 names (`ScoringInput`,
  `ScoreResult`, `SensitivityResult`, the status enums, the constants).
- Must not persist, log, serialize JSON, or write files/DB rows (`reference_size`
  and `reference_usable_counts_json` mapping is Chunk 10).
- Must not assign `evidence_grade` or `rankability_status`; must not construct
  `base_rankable_candidates`; must not evaluate sensitivity policies or stability
  (Chunks 9A/9B).
- Must not re-detect contradicted page-view semantics from response payloads; the
  run-level status is consumed as an explicit parameter originating in Chunk 5
  (`interfaces/chunk-05.md` §5.8).
- Must not apply the sample-derived coverage threshold to `C` (LREQ-SCR-020's
  availability is Chunk 9A's); the below-threshold rule applies only to `D`, `R`,
  and `Q` (SRS §7.5/§9.1).
- Must not use a hard-coded `0.50` literal for the threshold; import
  `MIN_REQUIRED_COMPONENT_COVERAGE` from `models` (and do not edit `models.py`).
- Must not convert `None`/missing/unavailable to `0`/`0.0`, and must not treat a
  missing component as a zero-weight component.
- Must not add evidence, sensitivity, persistence, pipeline, report, or CLI
  behavior; must not introduce configurable score weights.
- Must not use unseeded randomness or set/dict iteration order for numeric
  ordering (LREQ-ARCH-030).

## 12. Open questions / assumptions

No blocking open question. Q1 was resolved as an SRS-backed ruling (below); D1–D4,
D6, D7 are recorded design decisions with their sources so a reviewer can
re-check them.

- **Q1 — RESOLVED (SRS-backed ruling): a below-`MIN_REQUIRED_COMPONENT_COVERAGE`
  `D`/`R`/`Q` is unavailable and receives no composite weight.** SRS §7.5 lines
  835–840: "The same `MIN_REQUIRED_COMPONENT_COVERAGE` policy applies to Demand
  and Recent Supply: if `demand_stratum_eligibility_coverage` or
  `recent_supply_stratum_eligibility_coverage` is below the threshold, the
  affected component SHALL be unavailable for rankability and SHALL not receive
  composite weight." SRS §9.1 lines 1019–1022: "A component below this threshold
  is unavailable for rankability and receives no composite weight." With
  `MIN_REQUIRED_COMPONENT_COVERAGE = 0.50` (§9.1 line 1015; §14 line 1292; frozen
  in `src/niche_scout/models.py:52`), Chunk 8 returns `None` for `D`/`R`/`Q`
  before shrinkage, so `W_A` excludes them under LREQ-SCR-060. `Q`'s check is
  defensive and consistent with Chunk 7B's already-frozen threshold nulling of
  `QualityRaw` (Chunk 7B plan §12 Q-3, option (a)). `C` is not sample-derived and
  is unaffected; its availability is LREQ-SCR-020 (Chunk 9A's rankability
  consequence). The threshold is imported from `models`, never hard-coded.
- **D1 — `reference_size` and field counts are pure here.** "Stored separately"
  is Chunk 10's `reference_size` / `reference_usable_counts_json` columns
  (dependency map row 94; `CategoryScoreRecord`). Chunk 8 computes the pure
  values only. (No human decision needed.)
- **D2 — "field-specific usable" means non-null peer raw.** SRS §8.1 says
  "usable reference values `r_1..r_m`" and §1.2 keeps null distinct; Chunk 7B
  already returns `QualityRaw = None` when quality support is insufficient, so a
  non-null peer value is the usable set for every field. The normalized field
  set is the §8.1 list of six raws.
- **D3 — `C` availability maps "verified and sufficiently complete" to
  `breadth_source == VERIFIED_TOTAL_COUNT` + `breadth_completeness_status ==
  COMPLETE`.** The dependency map's SCR-020 edge case says "Unverified or
  incomplete breadth"; those are exactly the two 7B enum distinctions. A verified
  zero-result category (`BreadthRaw = 0.0`, complete) still yields `C = 1.0`.
- **D4 — caller-contract errors raise `ValueError`.** SRS §8 does not define
  behavior for a caller that omits the target, duplicates a category, or supplies
  a non-finite raw/reference value. Mirroring `metrics.weighted_median`, these are
  caller breaches → `ValueError`, never a fabricated product value.
- **D6 — contradicted rankability consequence is Chunk 9A's.** Chunk 8 sets
  `D`/`Q` unavailable and exposes the outcome through `ComponentValues`; the
  "category SHALL not be rankable" clause is applied by Chunk 9A/
  LREQ-EVD-020. `ScoreResult.rankability_status` stays at its default and is not
  read as a Chunk 8 output.
- **D7 — single-available sub-signal handling.** For `D0` and `Rpressure0`, when
  exactly one sub-signal is available the plan uses that term directly; weighting
  it by its renormalized subweight (0.60/0.40 or 0.70/0.30 over the single
  available subweight) yields the same value, so no ambiguity remains.
