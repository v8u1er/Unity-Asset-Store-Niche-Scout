# Chunk 9B — Sensitivity, final evidence, and final rankability

Status: FROZEN (2026-09-21)
Depends on (frozen interfaces required before this plan can be trusted):
  Documents/interfaces/chunk-9A.md (frozen public surface: `BaseCandidateSet`,
  `PreSensitivityDecision`, `PreSensitivityRankabilityState`,
  `PreSensitivityEvidenceState`, `NotRankableReason`, `ProvisionalReason`,
  `build_base_rankable_candidates`, and its "Explicitly not produced here"
  section naming Chunk 9B)
  Documents/interfaces/chunk-08.md (`ScoreResult`, `ComponentValues`,
  `CompositeResult`, `balanced_composite`, `renormalized_composite`,
  `COMPONENT_WEIGHT_KEYS`, and the frozen `SensitivityResult` shape)
  Documents/interfaces/chunk-05.md §5.8 (page-view semantics status consumed,
  never detected)
  Documents/interfaces/chunk-00.md (`SensitivityResult`, `EvidenceGrade`,
  `RankabilityStatus`, `WarningCode`, all constants and policy versions)
  Documents/interfaces/chunk-02.md (`category_scores` columns the final values
  map to: `evidence_grade`, `rankability_status`, `top_3_stability`,
  `top_5_stability`, `maximum_score_delta`, `maximum_rank_displacement`,
  `sensitivity_warning`, `ranking_sensitivity_json`)
  Documents/interfaces/chunk-7B.md (`CategoryRawMetrics.usable_*_sample_count`,
  `CategoryMetricInput`, stratum eligibility coverage fields)
Blocks (chunks whose plan/implementation needs this chunk's interface):
  Chunk 10 (persists the sensitivity diagnostics and the final
  `evidence_grade` / `rankability_status`), Chunk 11 (report sensitivity,
  evidence grade, and warning vocabulary), Chunk 13 (acceptance golden vectors
  for sensitivity)

## 1. Goal

Make `scoring.py` the pure owner of the **post-candidate** decision: rank the
frozen `BaseCandidateSet.base_rankable_candidates` under the three fixed
sensitivity policies (LREQ-SEN-010/-020), compute deterministic tie-broken
ranks, top-3/top-5 membership stability, per-category and run-level score and
rank displacement, and the sensitivity warning thresholds (LREQ-SEN-030)
without ever adding or removing a candidate or changing the balanced primary
score (LREQ-SEN-040), then assign the final `EvidenceGrade` (LREQ-EVD-050,
completing LREQ-EVD-030's "or sensitivity is high" clause) and the final
`RankabilityStatus` (LREQ-EVD-040) **after** sensitivity. Chunk 10 persists the
complete result; this chunk assigns no record field and writes nothing. The
output is a within-run, sample-based deterministic heuristic; it is not a sales,
revenue, download, or demand prediction, and not a statistically representative
estimate.

## 2. Scope

### In scope
- The three fixed sensitivity policies — balanced, demand-heavy,
  competition-heavy — consumed from `models.SENSITIVITY_POLICIES`, never
  reparameterized (LREQ-SEN-010).
- A deterministic ranker over exactly the frozen `base_rankable_candidates`,
  ties broken by ascending lexical category path (LREQ-SEN-020).
- Top-3 and top-5 membership stability with the explicit null contract when
  fewer than `k` ranked candidates exist (LREQ-SEN-020; dependency-map §6.3).
- Per-category ranks and scores under each policy, maximum score displacement,
  and maximum rank displacement, returned as a complete typed diagnostic that
  Chunk 10 can persist as `ranking_sensitivity_json` (LREQ-SEN-020).
- The LREQ-SEN-030 warning thresholds: `top_3_stability < 2/3`, and a
  per-category rank displacement greater than
  `max(3 positions, 25% of the reference-set size)`.
- Score preservation: sensitivity diagnostics qualify the balanced score and
  never replace or mutate it (LREQ-SEN-040; LREQ-SCR-060).
- The final `EvidenceGrade` from sample size, census status, component coverage,
  discovery integrity, reference size, page-view semantics, and sensitivity
  (LREQ-EVD-050).
- The final `RankabilityStatus`: rankable only when the category is
  base-rankable **and** the sensitivity thresholds pass; a sensitivity warning
  demotes only to provisional (LREQ-EVD-040); an 8–20 category run is never
  rankable (LREQ-EVD-040 line 1008).
- Type hints and null/edge-case docstrings on every new public name
  (LREQ-NFR-040).

### Explicitly out of scope (and who owns it instead)
- **Pre-sensitivity evidence and the frozen candidate set.** Primary owner is
  **Chunk 9A** (LREQ-EVD-010/-020). This chunk consumes `PreSensitivityDecision`
  and `BaseCandidateSet` and never re-derives a not-rankable/provisional reason
  or rebuilds the candidate set.
- **Persistence, SQLite, JSON serialization, logging, report, CLI.** Chunks
  10/11/12. This chunk returns typed values only; it does not serialize.
- **Report rendering of the warning vocabulary** (`RANKING_SENSITIVITY_HIGH`,
  `SAMPLE_BASED_SIGNAL`, etc.). **Chunk 11**; this chunk may name the
  `models.WarningCode` value but does not emit or persist a warning.
- **The orchestration-status half of LREQ-EVD-020 and the run-level status
  mapping.** **Chunk 10** (`pipeline.py`); no `pipeline.py` edit here.
- **Rejection of runs with fewer than `MIN_CATEGORIES_PER_RUN` categories.**
  **Chunk 12** (LREQ-CLI-040). This chunk consumes the run size it is given and
  returns null/provisional outputs; it never raises for a small run.
- **The pre-sensitivity clauses of LREQ-EVD-030** (8–20 categories,
  run below `STRONG_REFERENCE_CATEGORY_COUNT`, incomplete breadth fallback,
  coverage acceptable but below strong). Owned by **Chunk 9A**; this chunk adds
  only the "or sensitivity is high" completion clause.
- **Any new numeric threshold or configurable weight.** Constants come from
  `models.py` / SRS §14; no new threshold is invented except the explicitly
  derived `max(3, 25% of reference-set size)` threshold LREQ-SEN-030 names.

## 3. Requirements this chunk must satisfy

| LREQ ID | Ownership role here | Normative text (from SRS-lean.md, quoted/derived) | SRS section |
|---|---|---|---|
| LREQ-SEN-010 | Primary | "Recompute rankings under these policies: balanced: D=0.35, C=0.30, R=0.20, Q=0.15; demand_heavy: D=0.50, C=0.25, R=0.15, Q=0.10; competition_heavy: D=0.30, C=0.45, R=0.15, Q=0.10" (lines 1060–1066) | §9.3 |
| LREQ-SEN-020 | Primary | "Report top-three membership stability, top-five membership stability, each category's rank under each policy, maximum rank displacement, and maximum score displacement. The persisted field names SHALL include `top_3_stability`, `top_5_stability`, `maximum_score_delta`, `maximum_rank_displacement`, and `sensitivity_warning`. For each policy, rank categories by descending composite score. Ties SHALL be broken deterministically by canonical category path in ascending lexical order. Let `T_k,p` be the resulting top-`k` category set under policy `p`; categories that are not in `base_rankable_candidates` SHALL remain visible but SHALL be excluded from the ranked set. The candidate set SHALL be fixed before any sensitivity policy is evaluated; sensitivity SHALL not remove or add candidates. Define `top_k_stability = |T_k,balanced ∩ T_k,demand_heavy ∩ T_k,competition_heavy| / k` for `k = 3` and `k = 5`. If fewer than `k` rankable categories exist, the value is null rather than padded with unavailable categories. For each category, `maximum_score_delta` is the maximum absolute difference between its score under a non-balanced policy and its balanced score, and `maximum_rank_displacement` is the maximum absolute rank difference across policies. The same diagnostics SHALL be stored in `ranking_sensitivity_json` with each policy's scores and ranks." (lines 1068–1091) | §9.3 |
| LREQ-SEN-030 | Primary | "Warn when `top_3_stability < 2 / 3`, or when a category's rank changes by more than `max(3 positions, 25% of reference-set size)`. The warning threshold SHALL be interpreted using the configured reference-set size and SHALL not silently alter the primary balanced score." (lines 1093–1096) | §9.3 |
| LREQ-SEN-040 | Primary | "Sensitivity diagnostics SHALL qualify the balanced score and SHALL not silently replace it." (lines 1098–1099) | §9.3 |
| LREQ-EVD-030 | Integration completion (sensitivity-high clause only; Chunk 9A owns the pre-sensitivity clauses) | "A score SHALL be `provisional` when computable and required conditions pass, but the run has 8–20 categories, the run has fewer than `STRONG_REFERENCE_CATEGORY_COUNT` categories, breadth uses the incomplete fallback estimate, stratum eligibility coverage is acceptable but below the strong policy, **or sensitivity is high**. Discovery bounded by a verified total is sufficient for rankability and SHALL not by itself force a provisional status." (lines 996–1001; emphasis added) | §9.1 |
| LREQ-EVD-040 | Primary | "A category may be `rankable` only when the run contains at least 8 categories, discovery and identity checks pass, required component evidence conditions pass, sample and field coverage meet configured thresholds, breadth is verified or bounded by a verified total, no critical contradiction exists, the category is in `base_rankable_candidates`, and the final sensitivity thresholds pass. A run with 8–20 categories SHALL never be labeled `rankable`; it may be provisional. Sensitivity failure changes final rankability to `provisional` but does not change the fixed candidate set or the balanced primary score." (lines 1003–1010) | §9.1 |
| LREQ-EVD-050 | Primary | "Evidence grade SHALL consider sample size, census status, component coverage, discovery integrity, reference size, page-view semantics, and sensitivity. Sample count alone SHALL not determine it." (lines 1028–1030) plus the strong/moderate/weak/insufficient table and the `minimum_component_sample_count` definition (lines 1032–1052). | §9.2 |
| LREQ-EVD-010 | Supporting (Chunk 9A primary) — final states are `models.RankabilityStatus` | "Use `not_rankable`, `provisional`, and `rankable` states." (line 978). This chunk maps to the persisted `models.RankabilityStatus`, distinct from 9A's `PreSensitivityRankabilityState`. | §9.1 |
| LREQ-EVD-020 | Supporting (Chunk 9A primary) — not-rankable facts consumed | The not-rankable conditions and the "fixed `base_rankable_candidates` set" construction (lines 980–994). This chunk consumes the resulting decision and never re-derives it; `insufficient` evidence follows from the pre-sensitivity not-rankable state. | §9.1 |
| LREQ-SCR-060 | Supporting (Chunk 8 primary) — balanced policy equals the primary composite | The available-component composite and the fixed balanced weights; `balanced_composite` uses "the fixed Lean v1 weights `models.W_D/W_C/W_R/W_Q` (0.35/0.30/0.20/0.15), so a four-component score equals `S_available` and the balanced primary is exactly the `balanced` sensitivity policy." (interfaces/chunk-08.md §4) | §8.3 |
| LREQ-NRM-020 | Supporting (Chunk 8 primary) — reference size for the displacement threshold | The leave-one-out reference set: `reference_size = len(all_metrics) - 1` (interfaces/chunk-08.md §4); `evaluate_sensitivity` requires the caller-supplied `reference_set_size` to equal `run_category_count - 1` (R3). Used to interpret LREQ-SEN-030's "25% of reference-set size". | §8.1 |
| LREQ-TST-070 | Supporting (Chunk 13 primary; this chunk supplies its subject matter) | "Sensitivity tests SHALL verify all three policies, rank displacement, top-three/top-five stability, warning thresholds, and preservation of the balanced primary score; the sensitivity candidate set SHALL remain unchanged when a warning is raised; and the balanced policy SHALL equal the primary score weights." (lines 1256–1259) | §13 |
| LREQ-TST-060 | Supporting (Chunk 13 primary; completion Chunk 13) | "Scoring tests SHALL cover … fixed `base_rankable_candidates` constructed before sensitivity, sensitivity-driven final provisional status, and non-rankability." (lines 1250–1254). This chunk covers the sensitivity-driven final provisional status. | §13 |
| LREQ-TST-090 | Supporting (Chunk 13 primary) | "Golden vectors SHALL assert exact results within `1e-9` for sample-aware metrics, normalization, components, composite score, coverage, evidence, and sensitivity outputs." (lines 1266–1271) | §13 |
| LREQ-TST-010 | Supporting (Chunk 13 primary) | "Every formula SHALL have tests for normal values, explicit valid zero where applicable, missing values, invalid values, ties, and minimum boundaries." | §13 |
| LREQ-ARCH-010 | Supporting (Chunk 0 primary) | "`metrics` and `scoring` SHALL accept plain typed input structures and return typed result structures. They SHALL not import or call `collector`, `database`, `report`, or `cli` code, and SHALL perform no network or file I/O." (lines 227–229) | §3.3 |
| LREQ-ARCH-020 | Supporting (Chunk 0 primary) | "Pure metric and scoring functions SHALL NOT read the system clock. All timestamps SHALL be supplied by the orchestration layer." (lines 231–232) | §3.3 |
| LREQ-ARCH-030 | Supporting (Chunk 0 primary) | "The same normalized input data, policy versions, and configuration SHALL produce the same metric, score, evidence, and sensitivity outputs." (lines 234–235) | §3.3 |
| LREQ-NFR-040 | Supporting (Chunk 0 primary; completion Chunk 13) | "Public metric and scoring functions SHALL have type hints and docstrings describing null and edge-case behavior." (lines 1171–1172) | §11 |

Constants consumed unchanged (SRS §14 lines 1285–1293; `models.py` lines 35–36,
52–53, 88–92): `MIN_CATEGORIES_PER_RUN = 8`,
`STRONG_REFERENCE_CATEGORY_COUNT = 21`, `MIN_REQUIRED_COMPONENT_COVERAGE = 0.50`,
`STRONG_COMPONENT_COVERAGE = 0.80`, `SENSITIVITY_POLICIES` (three policies).
No new constant is introduced except the derived warning threshold
`max(3, 0.25 * reference_set_size)` that LREQ-SEN-030 names.

## 4. Interface contracts consumed

Copied from the frozen interfaces (not re-derived from source).

### 4.1 From `interfaces/chunk-9A.md` (`niche_scout.scoring`)

```python
class PreSensitivityRankabilityState(StrEnum):
    NOT_RANKABLE = "not_rankable"
    PROVISIONAL = "provisional"
    RANKABLE = "rankable"

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

`base_rankable_candidates` is in the caller's canonical `all_metrics` order and
is **frozen**: this chunk reads it and never adds or removes a member. A run of
8–20 categories yields an empty candidate tuple (interfaces/chunk-9A.md §4.6).

### 4.2 From `interfaces/chunk-08.md` and `interfaces/chunk-00.md`
(`niche_scout.scoring`)

```python
COMPONENT_WEIGHT_KEYS: tuple[str, ...] = ("D", "C", "R", "Q")

@dataclass(frozen=True, slots=True)
class ComponentValues:
    demand: float | None
    competition: float | None
    recent_supply: float | None
    quality: float | None

@dataclass(frozen=True, slots=True)
class ScoreResult:
    market_opportunity_score: float | None
    score_state: ScoreState
    component_d: float | None = None
    component_c: float | None = None
    component_r: float | None = None
    component_q: float | None = None
    available_component_count: int = 0
    rankability_status: RankabilityStatus = RankabilityStatus.NOT_RANKABLE
    evidence_grade: EvidenceGrade = EvidenceGrade.INSUFFICIENT

@dataclass(frozen=True, slots=True)
class SensitivityResult:          # Chunk 0 shape; unchanged and not returned here
    top_3_stability: float | None = None
    top_5_stability: float | None = None
    maximum_score_delta: float | None = None
    maximum_rank_displacement: int | None = None
    warning: bool = False
```

`renormalized_composite(components, weights) -> CompositeResult` and
`balanced_composite(components)` are the frozen recomputation primitives
(interfaces/chunk-08.md §3–§4). With four available components the composite is
`sum(w_x * x)` clamped to `[0, 1]` and `balanced_composite` is exactly the
balanced policy.

### 4.3 From `interfaces/chunk-7B.md` (`niche_scout.metrics`)

`CategoryRawMetrics` carries `usable_demand_sample_count`,
`usable_recent_supply_sample_count`, `usable_quality_sample_count`, the three
stratum eligibility coverage fields, and breadth provenance. `CategoryRawMetrics`
is the ordering authority for the run; it does **not** carry
`sample_is_census` or `discovered_population_count` (those live on
`sampling.CategorySamplingResult` and the `category_scores` row, and reach this
chunk as `SampleEvidenceFacts`; R5). See §5.

### 4.4 From `interfaces/chunk-05.md` §5.8 / `chunk-02.md` (statuses and columns)

`models.PageViewSemanticsStatus` (`unvalidated`/`validated_cumulative`/
`contradicted`) is consumed, never detected. `models.EvidenceGrade` =
`strong`/`moderate`/`weak`/`insufficient`; `models.RankabilityStatus` =
`not_rankable`/`provisional`/`rankable`; `models.WarningCode` includes
`RANKING_SENSITIVITY_HIGH`. `category_scores` exposes the persisted names
`top_3_stability`, `top_5_stability`, `maximum_score_delta`,
`maximum_rank_displacement`, `sensitivity_warning` (`bool | None`),
`ranking_sensitivity_json` (SRS §6.5 lines 604–607).

## 5. Interface contract this chunk produces

Additive to `src/niche_scout/scoring.py`; no Chunk 0/8/9A name is modified. The
Chunk 0 `SensitivityResult` is left byte-identical and is not returned by this
chunk's run-level function: its `warning: bool = False` cannot express the null
contract of dependency-map §6.3 (line 1161) that `SRS-lean.md` §6.5 line 607 and
`models.CategoryScoreRecord.sensitivity_warning: bool | None` require. Chunk 10
persists this chunk's `sensitivity_warning` and `ranking_sensitivity_json`
values from `SensitivityDiagnostics`, not from `SensitivityResult` (R1).

```python
#: Fixed policy evaluation order. Keys are the ones in models.SENSITIVITY_POLICIES.
SENSITIVITY_POLICY_ORDER: tuple[str, ...] = (
    "balanced", "demand_heavy", "competition_heavy",
)

#: Fixed top-k order for the stability statistics.
SENSITIVITY_TOP_K: tuple[int, ...] = (3, 5)

@dataclass(frozen=True, slots=True)
class CategorySensitivityRank:
    """One base candidate's rank/score under every policy plus its displacements.

    ``score_*`` are the alternate-policy composite scores and are never ``None``
    for a base candidate (all four components are available by the 9A base rule).
    ``rank_*`` are 1-based ranks over ``ranked_categories`` (the frozen
    `base_rankable_candidates`). ``maximum_score_delta`` is the maximum absolute
    difference between a non-balanced policy score and ``score_balanced``;
    ``maximum_rank_displacement`` is the maximum absolute rank difference across
    all three policies. ``warning`` is defined in §5.3.
    """

    category: str
    score_balanced: float
    score_demand_heavy: float
    score_competition_heavy: float
    rank_balanced: int
    rank_demand_heavy: int
    rank_competition_heavy: int
    maximum_score_delta: float
    maximum_rank_displacement: int
    warning: bool | None

@dataclass(frozen=True, slots=True)
class SensitivityDiagnostics:
    """Run-level sensitivity result over the immutable candidate set.

    ``ranked_categories`` is exactly ``BaseCandidateSet.base_rankable_candidates``
    (same order, unchanged set). ``categories`` is 1:1 with it. The five
    run-level fields mirror the persisted `category_scores` names. ``warning`` is
    the run-level aggregate (§5.3). ``reference_set_size`` and
    ``displacement_threshold`` record the inputs used so Chunk 10 can persist the
    diagnostics without recomputing them.
    """

    policies: tuple[str, ...]
    ranked_categories: tuple[str, ...]
    categories: tuple[CategorySensitivityRank, ...]
    top_3_stability: float | None
    top_5_stability: float | None
    maximum_score_delta: float | None
    maximum_rank_displacement: int | None
    warning: bool | None
    reference_set_size: int
    displacement_threshold: float

@dataclass(frozen=True, slots=True)
class SampleEvidenceFacts:
    """The sample/census facts the final evidence grade needs but no frozen pure
    scoring input carries (R5).

    ``usable_*_sample_count`` mirror the ``CategoryRawMetrics`` fields of the
    same names; the caller copies them. ``minimum_component_sample_count`` is
    computed here as their minimum (SRS §9.2 lines 1035-1040). ``0`` is a
    legitimate explicit count. ``discovered_population_count`` and
    ``sample_is_census`` mirror ``sampling.CategorySamplingResult`` and the
    persisted `category_scores` columns of the same names. ``scoring.py`` imports
    neither ``sampling`` nor any I/O module; the caller supplies these as plain
    typed values. A verified zero-result category (``discovered_population_count
    == 0``, ``sample_is_census`` is whatever the sampler recorded) is an explicit
    zero, never a missing value (SRS §7.3 lines 769-771).
    """

    category: str
    sample_is_census: bool
    discovered_population_count: int
    usable_demand_sample_count: int
    usable_recent_supply_sample_count: int
    usable_quality_sample_count: int

    @property
    def minimum_component_sample_count(self) -> int: ...

def ranked_under_policy(
    candidates: Sequence[str],
    components_by_category: Mapping[str, ComponentValues],
    *,
    policy: Mapping[str, float],
) -> tuple[tuple[str, float], ...]: ...

def evaluate_sensitivity(
    base_candidates: BaseCandidateSet,
    all_metrics: Sequence[CategoryRawMetrics],
    scores: Sequence[ScoreResult],
    *,
    reference_set_size: int,
    min_required_component_coverage: float = MIN_REQUIRED_COMPONENT_COVERAGE,
) -> SensitivityDiagnostics: ...

def final_evidence_grade(
    evidence: PreSensitivityCategoryInput,
    sample: SampleEvidenceFacts,
    decision: PreSensitivityDecision,
    *,
    run_category_count: int,
    sensitivity_warning: bool | None,
    min_required_component_coverage: float = MIN_REQUIRED_COMPONENT_COVERAGE,
    strong_component_coverage: float = STRONG_COMPONENT_COVERAGE,
) -> EvidenceGrade: ...

def final_rankability_status(
    decision: PreSensitivityDecision,
    *,
    sensitivity_warning: bool | None,
) -> RankabilityStatus: ...
```

### 5.1 `ranked_under_policy`

Pure, deterministic. For every category in ``candidates`` (the frozen set),
build `ComponentValues` from `components_by_category[category]` and compute
`renormalized_composite(components, policy)`; return `(category, score)` pairs
sorted by **descending score**, ties broken by **ascending lexical category
path** (SRS §9.3 line 1074; LREQ-SEN-020). Iteration over `candidates` is the
only container iteration; the sort key is `(-score, category)`, so no dict/set
order determines the result (LREQ-ARCH-030). A missing mapping key, a `None`
component, or a policy missing a `COMPONENT_WEIGHT_KEYS` key raises
`ValueError` (caller breach through `renormalized_composite`). An empty
`candidates` returns `()`.

### 5.2 `evaluate_sensitivity`

Run-level, pure. Caller obligation: `all_metrics` and `scores` are 1:1 aligned
by category, and every `base_candidates.base_rankable_candidates` member appears
in `all_metrics`; otherwise `ValueError` (never a silently dropped or reordered
category). `reference_set_size` is supplied explicitly by the caller (R3); it is
the run's leave-one-out reference-set size and every per-category
`PreSensitivityCategoryInput.reference_size` supplied to the 9A pipeline must
equal it. The function enforces
`reference_set_size == base_candidates.run_category_count - 1` (the value
`leave_one_out_reference` assigns; interfaces/chunk-08.md §4 line 168) and raises
`ValueError` on any mismatch rather than deriving the size silently.

1. Build `components_by_category` for the **candidates only** from the aligned
   `ScoreResult` component fields (`component_d/c/r/q`). A base candidate with a
   `None` component or `available_component_count != 4` is a contract breach →
   `ValueError` (the 9A base rule guarantees four components; failure here means
   the caller passed a mismatched `ScoreResult`).
2. For each policy in `SENSITIVITY_POLICY_ORDER`, rank the candidates with
   `ranked_under_policy`. `balanced` recomputes the same value as
   `balanced_composite` / the primary `market_opportunity_score` to within
   `1e-9` (LREQ-SCR-060; LREQ-SEN-040) — it is recomputed, never read back and
   never written.
3. `top_k_stability` for `k in SENSITIVITY_TOP_K`: `None` when
   `len(ranked_categories) < k`; else
   `|T_k,balanced ∩ T_k,demand_heavy ∩ T_k,competition_heavy| / k` (exact float
   division). No padding, no substitution of unavailable categories (LREQ-SEN-020
   lines 1086–1087; dependency-map §6.3).
4. Per category: the three policy scores, the three ranks, the maximum absolute
   non-balanced-vs-balanced score difference, and the maximum absolute rank
   difference across the three policies.
5. Run-level `maximum_score_delta` = max over candidates of the per-category
   `maximum_score_delta`; `maximum_rank_displacement` = max over candidates of
   the per-category `maximum_rank_displacement`. Both are `None` exactly when
   `ranked_categories` is empty (dependency-map §6.3).
6. `displacement_threshold = max(3.0, 0.25 * reference_set_size)` where
   `reference_set_size` is the caller-supplied run-level value.
7. `warning` per §5.3.

An empty candidate set returns
`top_3_stability = top_5_stability = maximum_score_delta =
maximum_rank_displacement = warning = None`, `categories = ()`, and still
records `reference_set_size` and `displacement_threshold` so
`ranking_sensitivity_json` carries the explicit empty-candidate status
(dependency-map §6.3) rather than an ambiguous object. An 8–20 category run
therefore yields every null output here (dependency-map §6.2).

### 5.3 Warning (LREQ-SEN-030; completing LREQ-EVD-030's sensitivity clause)

LREQ-SEN-030 defines a disjunction, and the two clauses have different domains:

- **Top-3 clause.** *Applicable* only when `top_3_stability is not None`; in that
  domain it fires iff `top_3_stability < 2.0 / 3.0`. When
  `top_3_stability is None` (fewer than 3 ranked candidates) the clause is
  **inapplicable, not `False`** — it contributes nothing to the disjunction
  (dependency-map §6.3 line 1160 keeps `maximum_rank_displacement` computable when
  "comparable policy ranks" exist).
- **Displacement clause.** *Applicable* to every base candidate; it fires iff
  `category.maximum_rank_displacement > displacement_threshold`. It is computable
  with as few as one candidate (displacement `0`), so it alone determines the
  warning when the top-3 clause is inapplicable.

Therefore a category's `warning` is:

- `None` when `ranked_categories` is empty (the only null case: no candidate, no
  comparable policy ranks; R2);
- otherwise `True` iff
  `(top_3_stability is not None and top_3_stability < 2.0 / 3.0)` **or**
  `(category.maximum_rank_displacement > displacement_threshold)`;
- otherwise `False`.

The run-level `warning` is the OR over the base candidates: `None` when
`ranked_categories` is empty, else `True` iff any category warning is `True`, else
`False` (R4). Each base candidate's warning already includes the run-level top-3
clause, so the top-3 condition applies to every base-candidate row; a
non-candidate category carries `warning = None` (R4). `top_3_stability` uses
strict `<`, so exactly `2/3` does **not** warn. The warning is a diagnostic: it
never changes a `ScoreResult`, a component, an alternate-policy score, the
candidate set, or the balanced primary score (LREQ-SEN-030, LREQ-SEN-040).

### 5.4 `final_evidence_grade` (LREQ-EVD-050)

`minimum_component_sample_count` is the minimum of the three usable counts on
`SampleEvidenceFacts` (SRS §9.2 lines 1035–1040). Precedence, all inputs
explicit:

1. `decision.not_rankable_reasons` is non-empty → `INSUFFICIENT` (SRS §9.2
   line 1052: "Required evidence is invalid, unavailable, or contradictory;
   category is not rankable").
2. Strong if **all** hold: `minimum_component_sample_count >= 80` **or**
   (`sample_is_census` and `discovered_population_count >= 50`); every one of the
   three stratum eligibility coverages `>= strong_component_coverage`;
   "verified discovery" = `evidence.discovery_filter_verified is True` **and**
   `evidence.discovery_status is DiscoveryStatus.COMPLETE`;
   `discovery_unresolved_identity_count == 0` and
   `discovery_conflict_count == 0`; `page_view_semantics_status` is not
   `CONTRADICTED`; `run_category_count >= STRONG_REFERENCE_CATEGORY_COUNT`
   (21; equivalently `reference_set_size >= 20`); **acceptable sensitivity** =
   `sensitivity_warning is False`. A `sensitivity_warning` of `None` is **not**
   acceptable for `strong` (R6). Else:
3. Moderate if **all** hold: `minimum_component_sample_count >= 40` **or**
   (`sample_is_census` and `discovered_population_count >= 20`); every required
   coverage `>= min_required_component_coverage`; `run_category_count >=
   MIN_CATEGORIES_PER_RUN`; no critical identity failure
   (`discovery_unresolved_identity_count == 0` and `discovery_conflict_count ==
   0`). Else:
4. `WEAK`.

`sample_is_census = False` means the census alternative is unavailable and only
`minimum_component_sample_count` is used. A `None` coverage/component remains
`None` and is never treated as `0.0`. The strong/moderate/weak/insufficient
conditions follow SRS §9.2 lines 1047–1052 (R6).

### 5.5 `final_rankability_status` (LREQ-EVD-040, completing LREQ-EVD-030)

Maps the pre-sensitivity state to the persisted `models.RankabilityStatus`, with
sensitivity allowed only to demote:

- `decision.rankability_state is NOT_RANKABLE` → `NOT_RANKABLE` (never
  overridden by sensitivity).
- `decision.rankability_state is PROVISIONAL` → `PROVISIONAL` (the 9A
  pre-sensitivity provisional clauses, including the 8–20 category run, remain).
- `decision.rankability_state is RANKABLE` (implies `decision.base_rankable`
  and no provisional reason): `RANKABLE` iff `sensitivity_warning is False`;
  otherwise (`True` or `None`) `PROVISIONAL`. A `None` warning means the final
  sensitivity thresholds were not demonstrated to pass, so the conservative
  outcome is `PROVISIONAL`, never `RANKABLE` (R7; LREQ-EVD-040 line 1007). Under
  R2/R3 this branch is unreachable for a base-rankable category (a base candidate
  always has a boolean warning), but the rule is defined and tested.

An absent candidate (`base_rankable = False`) is never `RANKABLE`; a run with
8–20 categories has an empty candidate set and is never `RANKABLE` (LREQ-EVD-040
line 1008). Sensitivity failure never demotes to `NOT_RANKABLE` and never
changes the candidate set or the balanced primary score (LREQ-EVD-040 lines
1009–1010).

## 6. Files touched

| File | New/modified | Purpose |
|---|---|---|
| `src/niche_scout/scoring.py` | Modified (additive) | `SENSITIVITY_POLICY_ORDER`, `SENSITIVITY_TOP_K`, `CategorySensitivityRank`, `SensitivityDiagnostics`, `SampleEvidenceFacts`, `ranked_under_policy`, `evaluate_sensitivity`, `final_evidence_grade`, `final_rankability_status` |
| `tests/test_scoring_sensitivity.py` | New | Chunk 9B analytical tests (markers + traceability entries) |
| `tests/fixtures/sensitivity_fixtures.py` | New | Data-only sensitivity and final-evidence golden vectors |
| `tests/fixtures/__init__.py` | Modified | Re-export the new fixture module (one-line pattern) |
| `tests/traceability.json` | Modified | Node → LREQ entries for the new tests |

No edit to `models.py`, `pipeline.py`, `database.py`, `report.py`, `cli.py`,
`metrics.py`, or any interface/plan document. If any of those must change, stop
and flag it.

## 7. Task breakdown

- [ ] Add `SENSITIVITY_POLICY_ORDER` and `SENSITIVITY_TOP_K`; assert at plan
      review that the three keys exist in `models.SENSITIVITY_POLICIES`
      (LREQ-SEN-010).
- [ ] Add `CategorySensitivityRank` and `SensitivityDiagnostics` typed
      structures with null/edge docstrings (LREQ-SEN-020).
- [ ] Implement `ranked_under_policy` with descending-score /
      ascending-category-path tie-breaking over exactly the supplied candidates
      (LREQ-SEN-010, LREQ-SEN-020, LREQ-ARCH-030).
- [ ] Implement `evaluate_sensitivity`: candidate-only component extraction,
      three-policy recomputation via `renormalized_composite`, top-3/top-5
      stability with the null contract, per-category and run-level displacement,
      warning thresholds, and the `reference_set_size == run_category_count - 1`
      guard (LREQ-SEN-010, LREQ-SEN-020, LREQ-SEN-030, LREQ-SEN-040,
      LREQ-SCR-060, LREQ-NRM-020; R3).
- [ ] Implement the disjunctive warning with the top-3 clause *inapplicable* when
      `top_3_stability is None`, `None` only for zero base candidates, and the
      run-level OR over candidates (LREQ-SEN-030; R2, R4).
- [ ] Add `SampleEvidenceFacts` with the `minimum_component_sample_count`
      property; document that the three counts mirror `CategoryRawMetrics` and
      that census/population mirror `sampling.CategorySamplingResult` / the
      persisted `category_scores` columns without importing `sampling`
      (LREQ-EVD-050; R5).
- [ ] Implement `final_evidence_grade` with the strong/moderate/weak/insufficient
      precedence, the census alternative, "verified discovery" =
      `discovery_filter_verified and discovery_status is COMPLETE`, and strong
      requiring `sensitivity_warning is False` (LREQ-EVD-050; R6).
- [ ] Implement `final_rankability_status` mapping the pre-sensitivity state and
      adding the sensitivity demotion, with `sensitivity_warning is None` on a
      pre-sensitivity `RANKABLE` category yielding `PROVISIONAL`
      (LREQ-EVD-030, LREQ-EVD-040; R7).
- [ ] Add type hints and null/edge-case docstrings to every new public name
      (LREQ-NFR-040).
- [ ] Write `tests/fixtures/sensitivity_fixtures.py` golden vectors (data only)
      for the §9 stable and warning vectors, the empty/2-candidate null vectors,
      and the four final-evidence grades.
- [ ] Write `tests/test_scoring_sensitivity.py` with the §9 markers.
- [ ] Add the §9 `tests/traceability.json` entries and re-export the fixture
      module.
- [ ] Run `ruff format`, `ruff check`,
      `python -m pytest tests/test_scoring_sensitivity.py -q`, the full suite,
      `python -m niche_scout.tools.check_import_boundaries`, and
      `python -m niche_scout.tools.validate_traceability`.

## 8. Edge cases and invariants

From the dependency-map edge-case rows for LREQ-SEN-010…040 and
LREQ-EVD-030/-040/-050 (lines 248–259), §6.2/§6.3, and the Chunk 9B gate
(lines 947–954):

- **Sensitivity never adds or removes candidates.** The ranked set is exactly
  `BaseCandidateSet.base_rankable_candidates`; a non-candidate remains visible
  on its own `category_scores` row but is absent from
  `ranked_categories`/`categories` and contributes to no stability statistic
  (LREQ-SEN-020 line 1077; gate bullet 1).
- **Sensitivity never modifies the balanced primary score.** `balanced` is
  recomputed and compared, never written back; `ScoreResult` is frozen and is
  never rebuilt or mutated (LREQ-SEN-040; gate bullet 2).
- **Null stability when too few candidates.** `top_3_stability = None` when
  fewer than 3 base candidates; `top_5_stability = None` when fewer than 5;
  `maximum_score_delta` and `maximum_rank_displacement` are `None` exactly when
  the candidate set is empty (LREQ-SEN-020 line 1086; §6.3; gate bullet 4).
- **Empty candidate set.** Every stability/displacement/warning output is
  `None`; `ranking_sensitivity_json` still carries the explicit empty-candidate
  status (8–20 category runs; §6.2/§6.3).
- **Deterministic tie-break.** Descending score, ties by ascending lexical
  category path; set/dict iteration never determines output (LREQ-SEN-020 line
  1074; LREQ-ARCH-030).
- **Warning boundary.** `top_3_stability` exactly `2/3` does not warn (strict
  `<`); a rank displacement exactly equal to the threshold does not warn (strict
  `>`). The threshold is `max(3, 0.25 * reference_set_size)` (LREQ-SEN-030).
- **Top-3 clause domain.** When `top_3_stability is None` (fewer than 3 ranked
  candidates) the top-3 clause is *inapplicable*, not `False`; the displacement
  clause still applies, so a category's warning is a boolean whenever at least
  one base candidate exists and `None` only for zero base candidates (R2, R4).
- **Reference-set size guard.** `evaluate_sensitivity` requires
  `reference_set_size == base_candidates.run_category_count - 1` (the run LOO
  peer count; interfaces/chunk-08.md §4) and raises `ValueError` on a mismatch;
  every per-category `PreSensitivityCategoryInput.reference_size` must equal it
  (R3).
- **A warning demotes only to provisional** — never to `not_rankable`, and never
  changes the candidate set or the balanced score (LREQ-EVD-040 lines 1009–1010;
  gate bullet 3).
- **8–20 category runs are never rankable** but may be provisional; their
  candidate set is empty and every sensitivity stability output is null
  (LREQ-EVD-040 line 1008; §6.2).
- **Final evidence precedence.** `insufficient` iff the pre-sensitivity decision
  has any not-rankable reason; provisional categories may be `moderate`/`weak`.
  A strong sample count does not by itself produce `strong` when coverage,
  discovery integrity, reference size, semantics, or sensitivity fail; strong
  requires `sensitivity_warning is False`, so `None` cannot earn `strong`
  (LREQ-EVD-050 lines 1028–1052; R6).
- **Final rankability with a null warning.** A pre-sensitivity `RANKABLE`
  category with `sensitivity_warning is None` is `PROVISIONAL`, not `RANKABLE`;
  only `sensitivity_warning is False` yields `RANKABLE` (LREQ-EVD-040 line 1007;
  R7). This is unreachable for a base candidate under R2/R3 but is tested.
- **`ranking_sensitivity_json` visibility.** The diagnostic covers the ranked
  candidate set only; non-candidates remain visible through their own
  `category_scores` rows with null rank/displacement/sensitivity fields
  (LREQ-SEN-020 line 1077; §6.3; R8).
- **Sample vs population.** `minimum_component_sample_count` is a usable
  observation count; the census alternative uses `discovered_population_count`.
  Neither is `sample_fraction` and neither is stratum eligibility coverage.
- **Missing is not zero.** `None` component/coverage/`sensitivity_warning` is
  never converted to `0`/`0.0`/`False`; a usable count of `0` and a
  `discovered_population_count` of `0` (a verified zero-result category, SRS §7.3
  lines 769–771) are explicit values.
- **Determinism.** Same inputs + policy versions → same outputs: fixed policy
  order, fixed top-k order, fixed tie-break, no clock, no randomness, no set/dict
  iteration for output order (LREQ-ARCH-030).
- **Purity.** `scoring.py` keeps its existing imports and adds only `models`
  names and, if needed, `enum`/`collections.abc`; it never imports `collector*`,
  `database`, `pipeline`, `report`, `cli`, `config`, `sqlite3`, or an I/O/clock
  module (LREQ-ARCH-010/020).

## 9. Test plan

### Test files
- New `tests/test_scoring_sensitivity.py` (Chunk 9B only;
  `tests/test_scoring_evidence.py` already holds the Chunk 9A nodes and is not
  edited here).
- New data-only fixture module `tests/fixtures/sensitivity_fixtures.py`;
  re-export it from `tests/fixtures/__init__.py`.
- `tests/traceability.json` is keyed **node → array of `LREQ-*` IDs** (confirmed
  by opening the file: line 2 is
  `"tests/test_contracts.py::test_models_import": ["LREQ-ARCH-010"]`). The
  `tests/AGENTS.md` prose states the inverse and is contradicted by the
  artifact; the artifact governs, and this matches the Chunk 9A plan's recorded
  correction.

### Golden vectors / fixtures needed
All expected values are hand-derived from SRS §9.1–§9.3; none is copied from the
implementation. Fixtures are inert builders/constants only. Builders:
`make_score_result(score, state, d, c, r, q)` (derives
`available_component_count`), `make_candidate_set(categories, run_category_count)`
returning a `BaseCandidateSet` with all base-rankable decisions, and
`make_metrics_and_scores(components_by_category)` aligned in the same order.
Vectors that exercise the run-level guard set `run_category_count` and
`reference_set_size = run_category_count - 1` consistently (R3); a vector that
exercises the rank-displacement *breach* needs at least 8 base candidates so a
`maximum_rank_displacement` of `6` is arithmetically possible.

- **Stable vector (5 candidates, no warning).** Components
  `(D, C, R, Q)`: A `(0.9, 0.1, 0.5, 0.5)`, B `(0.1, 0.9, 0.5, 0.5)`,
  C `(0.5, 0.5, 0.9, 0.9)`, D `(0.5, 0.5, 0.5, 0.5)`,
  E `(0.2, 0.2, 0.2, 0.2)`. Hand-computed scores:
  balanced A `0.52`, B `0.48`, C `0.64`, D `0.50`, E `0.20`;
  demand-heavy A `0.60`, B `0.40`, C `0.60`, D `0.50`, E `0.20`;
  competition-heavy A `0.44`, B `0.56`, C `0.60`, D `0.50`, E `0.20`.
  Expected balanced ranks `C,A,D,B,E`; demand ranks `A,C,D,B,E` (A/C tie at
  `0.60` broken by ascending path); competition ranks `C,B,D,A,E`.
  `top_3_stability = 2/3` exactly (intersection `{C, D}` — boundary: does **not**
  warn); `top_5_stability = 1.0`; per-category displacement
  `A=3, B=2, C=1, D=0, E=0`; `maximum_rank_displacement = 3`; per-category max
  score delta `A=0.08, B=0.08, C=0.04, D=0.0, E=0.0`;
  `maximum_score_delta = 0.08`. The fixture is a 21-category run with these 5
  base candidates, so `reference_set_size = run_category_count - 1 = 20` and
  `displacement_threshold = max(3, 0.25 * 20) = 5.0`; every category warning is
  `False`.
- **Top-3-only warning vector (5 candidates; every candidate also breaches the
  displacement clause — not the isolated top-3 vector).** `R = Q = 0.5` for all,
  `(D, C)`: c1 `(1.0, 0.0)`, c2 `(0.8, 0.2)`, c3 `(0.6, 0.4)`, c4 `(0.4, 0.6)`,
  c5 `(0.2, 0.8)`. Hand-computed scores: balanced `c1 0.525, c2 0.515,
  c3 0.505, c4 0.495, c5 0.485`; demand-heavy `c1 0.625, c2 0.575, c3 0.525,
  c4 0.475, c5 0.425`; competition-heavy `c1 0.425, c2 0.455, c3 0.485,
  c4 0.515, c5 0.545`. Ranks: balanced `c1..c5`; demand `c1..c5`; competition
  `c5,c4,c3,c2,c1`. `top_3_stability = 1/3` (< `2/3` → warning `True`);
  `top_5_stability = 1.0`; displacement `c1=4, c2=2, c3=0, c4=2, c5=4`,
  `maximum_rank_displacement = 4`; `maximum_score_delta = 0.100`. With
  `reference_set_size = 20` the threshold is `5.0`; every base candidate is
  `True` because of the top-3 clause (and all five also satisfy the displacement
  clause), and the run-level warning is `True`. This vector is used by
  `test_sensitivity_warning_top_three_boundary` to assert the `1/3 < 2/3`
  condition and the run-level OR; it does **not** isolate the first clause.
- **Displacement-only warning vector (8 candidates; the isolated second clause).**
  A 21-category run whose 8 base candidates move enough that one candidate's
  `maximum_rank_displacement` is `6 > 5.0` while `top_3_stability = 2/3`, so
  **no** candidate satisfies the top-3 condition (`2/3` is not `< 2/3`) and every
  warning that is `True` must come from the displacement clause; the fixture
  records `reference_set_size = 20` so `displacement_threshold = 5.0`.
  Components are chosen so `{T_3,balanced} = {T_3,demand_heavy} =
  {T_3,competition_heavy}` while one low-ranked candidate climbs into the top
  ranks under `competition_heavy`. This vector is used by
  `test_sensitivity_warning_rank_displacement_threshold` to isolate the second
  clause.
- **Top-3-inapplicable vector (2 candidates).** `top_3_stability = top_5_stability
  = None`; the pair is rank-stable, so `maximum_rank_displacement = 0 <= 5.0`
  and every warning is `False` — the top-3 clause contributes nothing rather than
  forcing a warning (R2).
- **Minimum-boundary vector (1 candidate).** `top_3_stability =
  top_5_stability = None`, `maximum_rank_displacement = 0`,
  `maximum_score_delta = 0.0`, warning `False`.
- **Null vector (0 candidates).** `top_3_stability = top_5_stability =
  maximum_score_delta = maximum_rank_displacement = warning = None` and
  `categories == ()` (8–20 category run; §6.2/§6.3).
- **Balanced-preservation vector.** For every candidate,
  `score_balanced == score_result.market_opportunity_score` within `1e-9`, and
  `ranked_under_policy(candidates, components, policy=balanced)` equals
  `balanced_composite(components).market_opportunity_score`; the input
  `ScoreResult` objects and the candidate tuple are unchanged after
  `evaluate_sensitivity` (LREQ-SEN-040; LREQ-SCR-060).
- **Reference-set-size guard vector.** `evaluate_sensitivity` with a
  `BaseCandidateSet.run_category_count` of 21 and `reference_set_size = 19` (or
  21) raises `ValueError`; `reference_set_size = 20` is accepted (R3).
- **Final-evidence vectors** (using `SampleEvidenceFacts` and a
  `PreSensitivityDecision`):
  strong — census `False`, `minimum_component_sample_count = 80`, all coverages
  `0.80`, run size 21, `sensitivity_warning = False` → `STRONG`;
  strong-not-`None` — the same facts with `sensitivity_warning = None` →
  `MODERATE` (a `None` warning is never acceptable for `strong`; R6);
  moderate — count `40`, coverages `0.50`, run size 21, warning `False` →
  `MODERATE`;
  weak — count `39` or a coverage `0.60` with run size 21 → `WEAK`;
  insufficient — `not_rankable_reasons` non-empty → `INSUFFICIENT`;
  census alternative — `sample_is_census = True`,
  `discovered_population_count = 50`, counts `0` (all four components still
  available) → `STRONG`; `discovered_population_count = 20` → `MODERATE`;
  8-category provisional run (count `80`, coverages `0.80`, warning `False`) →
  `MODERATE` (strong requires 21 categories).
- **Final-rankability vectors**: pre-sensitivity `RANKABLE` + warning `False` →
  `RANKABLE`; pre-sensitivity `RANKABLE` + warning `True` → `PROVISIONAL`;
  pre-sensitivity `RANKABLE` + warning `None` → `PROVISIONAL` (R7; defined and
  tested even though R2/R3 make it unreachable for a base candidate);
  pre-sensitivity `PROVISIONAL` (e.g. coverage `[0.50, 0.80)`) + warning `False`
  → `PROVISIONAL`; pre-sensitivity `NOT_RANKABLE` + warning `True` →
  `NOT_RANKABLE`; 8–20 category run (empty candidate set) never `RANKABLE`.

### Exact `@pytest.mark.lreq(...)` markers (1:1 with §3)

| Test node | LREQ marker(s) |
|---|---|
| `test_sensitivity_policy_vocabulary_and_weights` | `LREQ-SEN-010` |
| `test_sensitivity_balanced_policy_equals_primary_weights` | `LREQ-SEN-010`, `LREQ-SCR-060` |
| `test_sensitivity_ranks_only_fixed_candidates` | `LREQ-SEN-020` |
| `test_sensitivity_deterministic_tie_break_by_category_path` | `LREQ-SEN-020`, `LREQ-ARCH-030` |
| `test_sensitivity_top_k_stability` | `LREQ-SEN-020`, `LREQ-TST-070` |
| `test_sensitivity_top_k_null_when_too_few_candidates` | `LREQ-SEN-020` |
| `test_sensitivity_empty_candidate_set_null_outputs` | `LREQ-SEN-020`, `LREQ-TST-070` |
| `test_sensitivity_max_score_and_rank_displacement` | `LREQ-SEN-020` |
| `test_sensitivity_does_not_add_or_remove_candidates` | `LREQ-SEN-020`, `LREQ-SEN-040` |
| `test_sensitivity_returns_typed_diagnostics` | `LREQ-SEN-020` |
| `test_sensitivity_warning_top_three_boundary` | `LREQ-SEN-030` |
| `test_sensitivity_warning_rank_displacement_threshold` | `LREQ-SEN-030`, `LREQ-NRM-020` |
| `test_sensitivity_warning_is_false_when_top_three_inapplicable` | `LREQ-SEN-030` |
| `test_sensitivity_warning_is_none_only_without_candidates` | `LREQ-SEN-030` |
| `test_sensitivity_reference_set_size_mismatch_raises` | `LREQ-SEN-030`, `LREQ-NRM-020` |
| `test_sensitivity_warning_does_not_alter_balanced_score` | `LREQ-SEN-030`, `LREQ-SEN-040` |
| `test_sensitivity_preserves_balanced_primary_score` | `LREQ-SEN-040`, `LREQ-SCR-060` |
| `test_final_evidence_grade_strong_vector` | `LREQ-EVD-050` |
| `test_final_evidence_grade_moderate_vector` | `LREQ-EVD-050` |
| `test_final_evidence_grade_weak_vector` | `LREQ-EVD-050` |
| `test_final_evidence_grade_insufficient_when_not_rankable` | `LREQ-EVD-050`, `LREQ-EVD-020` |
| `test_final_evidence_grade_census_alternative` | `LREQ-EVD-050` |
| `test_final_evidence_grade_uses_min_component_sample_count` | `LREQ-EVD-050`, `LREQ-NRM-020` |
| `test_final_evidence_grade_sensitivity_demotes_strong` | `LREQ-EVD-050`, `LREQ-SEN-030` |
| `test_final_evidence_grade_null_warning_is_not_strong` | `LREQ-EVD-050`, `LREQ-SEN-030` |
| `test_final_rankability_requires_base_and_sensitivity` | `LREQ-EVD-040` |
| `test_final_rankability_sensitivity_demotes_to_provisional` | `LREQ-EVD-040`, `LREQ-EVD-030`, `LREQ-SEN-040` |
| `test_final_rankability_null_warning_is_provisional` | `LREQ-EVD-040`, `LREQ-EVD-030` |
| `test_final_rankability_never_demotes_to_not_rankable` | `LREQ-EVD-040` |
| `test_eight_to_twenty_run_never_rankable` | `LREQ-EVD-040`, `LREQ-EVD-030` |
| `test_final_rankability_states_use_rankability_status` | `LREQ-EVD-010` |
| `test_sensitivity_high_provisional_clause_completes_evd030` | `LREQ-EVD-030` |
| `test_final_evidence_and_rankability_preserve_candidate_set_and_score` | `LREQ-EVD-040`, `LREQ-EVD-050` |
| `test_sensitivity_golden_vectors` | `LREQ-SEN-020`, `LREQ-TST-090` |
| `test_sensitivity_normal_and_boundary_values` | `LREQ-TST-010` |
| `test_scoring_tests_cover_sensitivity_after_base_candidates` | `LREQ-TST-060` |
| `test_sensitivity_outputs_are_deterministic` | `LREQ-ARCH-030` |
| `test_sensitivity_module_is_import_pure_and_clock_free` | `LREQ-ARCH-010`, `LREQ-ARCH-020` |
| `test_sensitivity_public_functions_have_type_hints_and_docstrings` | `LREQ-NFR-040` |

### `tests/traceability.json` entries to add

Direction: node → array of LREQ IDs.

```json
{
  "tests/test_scoring_sensitivity.py::test_sensitivity_policy_vocabulary_and_weights": ["LREQ-SEN-010"],
  "tests/test_scoring_sensitivity.py::test_sensitivity_balanced_policy_equals_primary_weights": ["LREQ-SEN-010", "LREQ-SCR-060"],
  "tests/test_scoring_sensitivity.py::test_sensitivity_ranks_only_fixed_candidates": ["LREQ-SEN-020"],
  "tests/test_scoring_sensitivity.py::test_sensitivity_deterministic_tie_break_by_category_path": ["LREQ-SEN-020", "LREQ-ARCH-030"],
  "tests/test_scoring_sensitivity.py::test_sensitivity_top_k_stability": ["LREQ-SEN-020", "LREQ-TST-070"],
  "tests/test_scoring_sensitivity.py::test_sensitivity_top_k_null_when_too_few_candidates": ["LREQ-SEN-020"],
  "tests/test_scoring_sensitivity.py::test_sensitivity_empty_candidate_set_null_outputs": ["LREQ-SEN-020", "LREQ-TST-070"],
  "tests/test_scoring_sensitivity.py::test_sensitivity_max_score_and_rank_displacement": ["LREQ-SEN-020"],
  "tests/test_scoring_sensitivity.py::test_sensitivity_does_not_add_or_remove_candidates": ["LREQ-SEN-020", "LREQ-SEN-040"],
  "tests/test_scoring_sensitivity.py::test_sensitivity_returns_typed_diagnostics": ["LREQ-SEN-020"],
  "tests/test_scoring_sensitivity.py::test_sensitivity_warning_top_three_boundary": ["LREQ-SEN-030"],
  "tests/test_scoring_sensitivity.py::test_sensitivity_warning_rank_displacement_threshold": ["LREQ-SEN-030", "LREQ-NRM-020"],
  "tests/test_scoring_sensitivity.py::test_sensitivity_warning_is_false_when_top_three_inapplicable": ["LREQ-SEN-030"],
  "tests/test_scoring_sensitivity.py::test_sensitivity_warning_is_none_only_without_candidates": ["LREQ-SEN-030"],
  "tests/test_scoring_sensitivity.py::test_sensitivity_reference_set_size_mismatch_raises": ["LREQ-SEN-030", "LREQ-NRM-020"],
  "tests/test_scoring_sensitivity.py::test_sensitivity_warning_does_not_alter_balanced_score": ["LREQ-SEN-030", "LREQ-SEN-040"],
  "tests/test_scoring_sensitivity.py::test_sensitivity_preserves_balanced_primary_score": ["LREQ-SEN-040", "LREQ-SCR-060"],
  "tests/test_scoring_sensitivity.py::test_final_evidence_grade_strong_vector": ["LREQ-EVD-050"],
  "tests/test_scoring_sensitivity.py::test_final_evidence_grade_moderate_vector": ["LREQ-EVD-050"],
  "tests/test_scoring_sensitivity.py::test_final_evidence_grade_weak_vector": ["LREQ-EVD-050"],
  "tests/test_scoring_sensitivity.py::test_final_evidence_grade_insufficient_when_not_rankable": ["LREQ-EVD-050", "LREQ-EVD-020"],
  "tests/test_scoring_sensitivity.py::test_final_evidence_grade_census_alternative": ["LREQ-EVD-050"],
  "tests/test_scoring_sensitivity.py::test_final_evidence_grade_uses_min_component_sample_count": ["LREQ-EVD-050", "LREQ-NRM-020"],
  "tests/test_scoring_sensitivity.py::test_final_evidence_grade_sensitivity_demotes_strong": ["LREQ-EVD-050", "LREQ-SEN-030"],
  "tests/test_scoring_sensitivity.py::test_final_evidence_grade_null_warning_is_not_strong": ["LREQ-EVD-050", "LREQ-SEN-030"],
  "tests/test_scoring_sensitivity.py::test_final_rankability_requires_base_and_sensitivity": ["LREQ-EVD-040"],
  "tests/test_scoring_sensitivity.py::test_final_rankability_sensitivity_demotes_to_provisional": ["LREQ-EVD-040", "LREQ-EVD-030", "LREQ-SEN-040"],
  "tests/test_scoring_sensitivity.py::test_final_rankability_null_warning_is_provisional": ["LREQ-EVD-040", "LREQ-EVD-030"],
  "tests/test_scoring_sensitivity.py::test_final_rankability_never_demotes_to_not_rankable": ["LREQ-EVD-040"],
  "tests/test_scoring_sensitivity.py::test_eight_to_twenty_run_never_rankable": ["LREQ-EVD-040", "LREQ-EVD-030"],
  "tests/test_scoring_sensitivity.py::test_final_rankability_states_use_rankability_status": ["LREQ-EVD-010"],
  "tests/test_scoring_sensitivity.py::test_sensitivity_high_provisional_clause_completes_evd030": ["LREQ-EVD-030"],
  "tests/test_scoring_sensitivity.py::test_final_evidence_and_rankability_preserve_candidate_set_and_score": ["LREQ-EVD-040", "LREQ-EVD-050"],
  "tests/test_scoring_sensitivity.py::test_sensitivity_golden_vectors": ["LREQ-SEN-020", "LREQ-TST-090"],
  "tests/test_scoring_sensitivity.py::test_sensitivity_normal_and_boundary_values": ["LREQ-TST-010"],
  "tests/test_scoring_sensitivity.py::test_scoring_tests_cover_sensitivity_after_base_candidates": ["LREQ-TST-060"],
  "tests/test_scoring_sensitivity.py::test_sensitivity_outputs_are_deterministic": ["LREQ-ARCH-030"],
  "tests/test_scoring_sensitivity.py::test_sensitivity_module_is_import_pure_and_clock_free": ["LREQ-ARCH-010", "LREQ-ARCH-020"],
  "tests/test_scoring_sensitivity.py::test_sensitivity_public_functions_have_type_hints_and_docstrings": ["LREQ-NFR-040"]
}
```

## 10. Definition of done (gate)

Copied **verbatim** from `Documents/requirements-dependency-map.md` Chunk 9B
(lines 947–954):

- Sensitivity never adds or removes candidates.
- Sensitivity never modifies the balanced primary score.
- A sensitivity warning demotes final rankability only as specified.
- Insufficient candidate counts produce the explicitly defined null outputs.
- `final_evidence_grade` and `final_rankability_status` are assigned here after sensitivity; Chunk 10 persists the complete result.
- Final rankability is assigned only after sensitivity is computed.

## 11. Explicit prohibitions

- Must not import or call `collector`, `collector_coveo`, `collector_graphql`,
  `database`, `pipeline`, `report`, `cli`, `config`, `sqlite3`, or any
  filesystem/network/clock module; must not read the system clock
  (LREQ-ARCH-010/020).
- Must not persist, log, serialize JSON, or write files/DB rows; must not assign
  `ScoreResult.rankability_status` or `ScoreResult.evidence_grade` on any object
  (Chunk 10 persists; this chunk returns the final values as plain types).
- Must not change the frozen Chunk 0 `SensitivityResult` (including its
  `warning: bool = False`), the Chunk 8 names, or the Chunk 9A names.
- Must not add or remove a candidate from `base_rankable_candidates`, or rank a
  category that is not in it (LREQ-SEN-020 line 1077).
- Must not mutate, rebuild, or reassign a `ScoreResult`, its components, its
  `market_opportunity_score`, its `score_state`, or the balanced primary score
  (LREQ-SEN-040; gate bullet 2).
- Must not use sensitivity to construct the candidate set or to re-derive a
  9A `not_rankable`/`provisional` reason (LREQ-EVD-020 line 994).
- Must not allow a sensitivity warning to demote rankability to `not_rankable`
  (LREQ-EVD-040 lines 1009–1010).
- Must not pad a `top_k_stability` value when fewer than `k` rankable categories
  exist; the value is `None` (LREQ-SEN-020 lines 1086–1087).
- Must not invent a numeric threshold or configurable weight; the only derived
  threshold is `max(3, 0.25 * reference_set_size)` from LREQ-SEN-030. Constants
  come from `models.py` / SRS §14.
- Must not convert `None`/missing/unavailable to `0`/`0.0`/`False`; in
  particular a `sensitivity_warning` of `None` must not be read as `False` when
  granting the `strong` evidence grade or the `rankable` status (R6, R7). Must
  not use set/dict iteration order to determine output ordering; no unseeded
  randomness (LREQ-ARCH-030; SRS §1.2).
- Must not derive `reference_set_size` internally, relax the
  `reference_set_size == run_category_count - 1` guard, or import `sampling` to
  obtain census/population facts (R3, R5).
- Must not edit `models.py`, `metrics.py`, `pipeline.py`, `database.py`,
  `report.py`, `cli.py`, `Documents/`, `AGENTS.md`, or `.kilo/`; must not
  reclassify `DiscoveryStatus`, identity counts, or page-view semantics.

## 12. Open questions / assumptions

No open question remains. Q1–Q8 were resolved by lead rulings on 2026-09-21
(recorded below as R1–R8 with their SRS/dependency-map/interface basis so a
reviewer can re-check them). No new SRS gap was found while applying them, and
§3, §5, §8, §9, and §10 all agree with R1–R8.

- **R1 — RESOLVED (Q1 option (a)). `sensitivity_warning` is `bool | None`,
  carried on the new `SensitivityDiagnostics`; the frozen Chunk 0
  `SensitivityResult` stays byte-identical.** Basis: `SRS-lean.md` §6.5 line 607
  names the persisted field; dependency-map §6.3 line 1161 requires
  `sensitivity_warning = null` when the required statistic cannot be computed;
  `models.CategoryScoreRecord.sensitivity_warning: bool | None` (`models.py:507`)
  and the Chunk 0 `SensitivityResult.warning: bool = False` cannot express that
  null, so the null-capable field lives on the new type. Chunk 10 persists the
  `category_scores.sensitivity_warning` value **from
  `SensitivityDiagnostics.warning` / each `CategorySensitivityRank.warning`**,
  not from `SensitivityResult`. §5 (the note above the code block, the
  `SensitivityDiagnostics.warning` and `CategorySensitivityRank.warning`
  annotations) and §11 record this.

- **R2 — RESOLVED (Q2 option (a)). The LREQ-SEN-030 condition is a disjunction;
  the top-3 clause is *inapplicable* (not `False`) when
  `top_3_stability is None`.** A category's `warning` is `None` only for
  **zero** base candidates; with one or more candidates it is a `bool` computed
  from the applicable clauses. Basis: dependency-map §6.3 line 1160 keeps
  `maximum_rank_displacement` computable when comparable policy ranks exist, so
  the displacement clause alone determines the warning when the top-3 clause is
  inapplicable. Recorded in §5.3, §8 ("Top-3 clause domain"), and tested by
  `test_sensitivity_warning_is_none_only_without_candidates` and
  `test_sensitivity_warning_is_false_when_top_three_inapplicable` (corrected
   2026-09-21 by the lead: this note originally named a non-existent node
   `test_sensitivity_warning_displacement_clause_when_top_three_inapplicable`;
   the §9 marker table and the `tests/traceability.json` block — which agree with
   each other — govern the node list).

- **R3 — RESOLVED (Q3 option (a)). `reference_set_size = run_category_count - 1`
  (leave-one-out peers), supplied explicitly by the caller.**
  `displacement_threshold = max(3, 0.25 * reference_set_size)`. Caller
  obligation: every per-category `PreSensitivityCategoryInput.reference_size`
  supplied to the 9A pipeline must equal this value, and `evaluate_sensitivity`
  raises `ValueError` on
  `reference_set_size != base_candidates.run_category_count - 1`. Basis:
  `leave_one_out_reference` assigns `reference_size = len(all_metrics) - 1`
  (interfaces/chunk-08.md §4 line 168); SRS §9.3 line 1095 says "the configured
  reference-set size". Consequence, stated for the record: base candidacy
  requires a run of at least 21 categories, so the threshold is always at least
  `5`, and the displacement clause fires only above `5`. Recorded in §5.2 step 6,
  §8 ("Reference-set size guard"), and tested by
  `test_sensitivity_reference_set_size_mismatch_raises`.

- **R4 — RESOLVED (Q4 option (a)). Each base candidate's `warning` =
  `(top_3_stability is not None and top_3_stability < 2/3)` OR its own
  displacement breach; non-candidates are `None`; the run-level warning is the
  OR over candidates.** Basis: `sensitivity_warning` is a per-category column and
  `top_3_stability` is a run-level statistic (SRS §9.3 line 1069); every
  base-candidate row must be able to explain its own demotion, and a
  non-candidate contributes no rank information. Recorded in §5.3 and §8.
  Because `score` and the primary composite are for four available components
  (the 9A base rule guarantees all four), the top-3 clause also applies to a
  small candidate set whose `top_3_stability` is `None` by being inapplicable
  there (R2).

- **R5 — RESOLVED (Q5 option (a)). Add the pure `SampleEvidenceFacts` dataclass
  to `scoring.py`.** Provenance corrected: `discovered_population_count` and
  `sample_is_census` mirror `sampling.CategorySamplingResult` and the persisted
  `category_scores` columns of the same names; the three
  `usable_*_sample_count` fields mirror `CategoryRawMetrics`. `scoring.py` must
  **not** import `sampling`; the caller supplies the values as plain typed
  values. A verified zero-result category (SRS §7.3 lines 769–771) is an explicit
  `0`, never a missing value. Basis: the frozen `PreSensitivityCategoryInput`
  carries none of these facts; the persistence columns and §6.5 require them.
  Recorded in §5 (`SampleEvidenceFacts` docstring), §4.3, and §7.

- **R6 — RESOLVED (Q6). The §5.4 precedence stands; "verified discovery" =
  `evidence.discovery_filter_verified is True` **and**
  `evidence.discovery_status is DiscoveryStatus.COMPLETE`;
  `sensitivity_warning is None` is **not** acceptable for `strong`; the reference
  condition is `run_category_count >= STRONG_REFERENCE_CATEGORY_COUNT` (= 21).**
  Moderate/weak/insufficient follow SRS §9.2 lines 1049–1052. Basis: the strong
  row names "verified discovery", "no identity conflict", "at least
  `STRONG_REFERENCE_CATEGORY_COUNT` categories", and "acceptable sensitivity";
  a not-evaluated sensitivity cannot satisfy "acceptable". Recorded in §5.4, §8
  ("Final evidence precedence"), and tested by
  `test_final_evidence_grade_null_warning_is_not_strong`.

- **R7 — RESOLVED (Q7 option (b)). For a pre-sensitivity `RANKABLE` category,
  `sensitivity_warning is None` yields final `PROVISIONAL`; only
  `sensitivity_warning is False` yields `RANKABLE`.** Basis: LREQ-EVD-040 line
  1007 requires "the final sensitivity thresholds pass"; a null warning means
  they were not demonstrated to pass, so the conservative outcome is
  `PROVISIONAL`. Under R2/R3 this is unreachable for a base-rankable category (a
  base candidate always has a boolean warning), but the rule is defined and
  tested (`test_final_rankability_null_warning_is_provisional`). Recorded in
  §5.5 and §8.

- **R8 — RESOLVED (Q8 option (a)). `ranking_sensitivity_json` carries only the
  ranked candidate set plus the explicit empty/insufficient-candidate status;
  non-candidates remain visible through their own `category_scores` rows with
  null rank/displacement/sensitivity fields.** Basis: SRS §9.3 line 1077 —
  non-candidates "SHALL remain visible but SHALL be excluded from the ranked
  set" — and dependency-map §6.3 line 1162, which requires an explicit
  empty/insufficient-candidate status rather than an ambiguous object. Recorded
  in §5 (`SensitivityDiagnostics`), §5.2, §8 ("`ranking_sensitivity_json`
  visibility"), and §2.