# Chunk 8 — Normalization and primary scoring (public interface)

Status: VERIFIED
Source: `Documents/plans/chunk-08-normalization-and-primary-scoring.md` §5
(`Status: FROZEN`, 2026-09-21), reproduced as the frozen public contract.
Implementation: `src/niche_scout/scoring.py` (additive surface; `ScoringInput`,
`ScoreResult`, `SensitivityResult`, and the Chunk 0 names are unchanged).

## 1. Module and boundary rules

| Item | Kind | Rule |
|---|---|---|
| `src/niche_scout/scoring.py` | **Pure** | Leave-one-out reference, midrank normalization, the `D`/`C`/`R`/`Q` components, the fixed-weight composite, and `score_state` only. No I/O, no clock, no randomness, no `sqlite3`, no network, no package I/O module import. |

- `scoring.py` imports `dataclasses`, `datetime`/`timezone`, `math`, `typing`,
  `collections.abc`, plus `models` and `metrics` (`src/niche_scout/scoring.py`,
  read). It does not import `collector`, `collector_coveo`, `collector_graphql`,
  `database`, `pipeline`, `report`, `cli`, or `config` (LREQ-ARCH-010). Verified by
  `python -m niche_scout.tools.check_import_boundaries` → exit 0
  ("Import boundaries valid for metrics.py, scoring.py").
- Determinism: `COMPONENT_WEIGHT_KEYS` fixes the weight-summation order; the
  weighted components iterate explicit tuples; no set/dict iteration determines a
  numeric result (LREQ-ARCH-030).
- Null, explicit valid zero, and unavailable stay distinct: a `None` component,
  raw, or normalized value is never converted to `0.0`.
- `scoring_cutoff_utc` is not consumed here; Chunk 8 does not read the clock.
- `ValueError` is raised only for caller/policy breaches (a non-finite value,
  missing/invalid weight, absent/duplicate target, invalid threshold), never for a
  product-level value.

## 2. Typed structures

```python
COMPONENT_WEIGHT_KEYS: tuple[str, ...] = ("D", "C", "R", "Q")
# Fixed iteration order for deterministic weight summation; the key spelling is
# the one used by models.SENSITIVITY_POLICIES.

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
# All six fields are required (no defaults); None means unavailable.

@dataclass(frozen=True, slots=True)
class ComponentValues:
    demand: float | None
    competition: float | None
    recent_supply: float | None
    quality: float | None
    @property
    def available_component_count(self) -> int: ...
# All four fields are required (no defaults); None means unavailable.

@dataclass(frozen=True, slots=True)
class CompositeResult:
    market_opportunity_score: float | None
    score_state: ScoreState
    available_component_count: int
    available_weight: float
```

- `LeaveOneOutReference` field tuples hold only the non-`None` peer values, in
  `all_metrics` order; a tuple may be shorter than `reference_size`.
  `field_usable_counts` reports each tuple's length.
- `ComponentValues` keys map `demand→D`, `competition→C`, `recent_supply→R`,
  `quality→Q`.

## 3. Public functions

```python
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

## 4. Semantics

- `midrank` (LREQ-NRM-030): `L = count(r < x)`, `E = count(r == x)`,
  `P_ref(x) = (L + 0.5 * E) / m` with exact float equality for `E`. `target is
  None` or `m == 0` → `None`. Duplicate reference values stay repeated and count in
  `m`. A non-finite target or reference element raises `ValueError`. Descriptive
  relative position, not an inferential percentile.
- `leave_one_out_reference` (LREQ-NRM-010/-020): `reference_size =
  len(all_metrics) - 1`; the target's own entry is excluded from every field tuple.
  Empty run, non-`str`/empty target, absent target, or two entries sharing a
  `category` → `ValueError`. A one-category run yields `reference_size == 0` with
  empty tuples (a valid empty reference).
- `normalize_raw_metrics` (LREQ-NRM-040): applies `midrank` independently to the
  six fields (no log transform); a `None` raw or empty field reference → `None` for
  that field only.
- `demand_component` (LREQ-SCR-010): a coverage strictly below
  `min_required_component_coverage` → `None` before shrinkage (SRS §7.5/§9.1);
  coverage equal to the threshold is available. Otherwise `D0 = 0.60 * a + 0.40 *
  b` when both midranks are available, the single available one when exactly one
  is, `None` when neither; then `clamp(0.5 + coverage * (D0 - 0.5), 0, 1)`.
- `competition_component` (LREQ-SCR-020): `None` unless `breadth_source is
  BreadthSource.VERIFIED_TOTAL_COUNT` and `breadth_completeness_status is
  BreadthCompletenessStatus.COMPLETE` and `P_ref(BreadthRaw)` is not `None`; else
  `clamp(1 - P_ref(BreadthRaw), 0, 1)`. No coverage shrinkage; **not** gated by
  `MIN_REQUIRED_COMPONENT_COVERAGE`.
- `recent_supply_component` (LREQ-SCR-030): a coverage strictly below the threshold
  → `None`. Otherwise `Rpressure0 = 0.70 * s + 0.30 * (1 - a)` when both available,
  the single available pressure term when exactly one is, `None` when neither;
  `R0 = 1 - Rpressure0`; `clamp(0.5 + coverage * (R0 - 0.5), 0, 1)`.
- `quality_component` (LREQ-SCR-040): a coverage strictly below the threshold or a
  `None` `P_ref(QualityRaw)` → `None`; else `Q0 = 1 - P_ref(QualityRaw)` and
  `clamp(0.5 + coverage * (Q0 - 0.5), 0, 1)`.
- `compute_components` (LREQ-SCR-050): validates the threshold once, dispatches to
  the four component functions, then, when `page_view_semantics_status is
  PageViewSemanticsStatus.CONTRADICTED`, replaces `demand` and `quality` with
  `None`; `competition` and `recent_supply` are unchanged. The status is consumed as
  an explicit caller parameter and is never re-detected (interfaces/chunk-05.md
  §5.8).
- `renormalized_composite` (LREQ-SCR-060): iterates `COMPONENT_WEIGHT_KEYS` in
  order; `weights` must contain every key with a finite non-negative value (else
  `ValueError`). `W_A = sum(weights of available components)`. Fewer than two
  available → `market_opportunity_score = None`,
  `score_state = ScoreState.UNAVAILABLE` (with `W_A` still reported). Otherwise,
  `W_A <= 0` → `ValueError`; else `S_available = sum(w_x * x) / W_A` and
  `market_opportunity_score = clamp(0.5 + W_A * (S_available - 0.5), 0, 1)` with
  `score_state = AVAILABLE` when all four are available else `PARTIAL`.
- `balanced_composite`: `renormalized_composite` with the fixed Lean v1 weights
  `models.W_D/W_C/W_R/W_Q` (0.35/0.30/0.20/0.15), so a four-component score equals
  `S_available` and the balanced primary is exactly the `balanced` sensitivity
  policy.
- `score_category`: reference → normalized → components → composite, returning
  `ScoreResult(market_opportunity_score, score_state, component_d, component_c,
  component_r, component_q, available_component_count)`. `rankability_status` and
  `evidence_grade` are left at their Chunk 0 defaults — Chunk 8 assigns neither.

## 5. Explicitly not produced here

- Storage of `reference_size` / `reference_usable_counts_json` (Chunk 10; the pure
  values are computed here).
- `rankability_status`, `evidence_grade`, and `base_rankable_candidates`
  (Chunk 9A); sensitivity policies, stability, and final rankability (Chunk 9B).
- Contradicted page-view *detection* (Chunk 5 records; callers supply the status).
