# Chunk 9B — Sensitivity, final evidence, and final rankability (public interface)

Status: VERIFIED
Source: `Documents/plans/chunk-9B-sensitivity-final-evidence-and-final-rankability.md` §5 (`Status: FROZEN`, 2026-09-21), reproduced as the frozen public contract.
Implementation: `src/niche_scout/scoring.py` (additive surface; Chunk 0/8/9A names unchanged).

## 1. Module and boundary rules

| Item | Kind | Rule |
|---|---|---|
| `src/niche_scout/scoring.py` | **Pure** | The three fixed sensitivity policies, the deterministic ranker over the frozen candidate set, top-k stability, displacement, the warning thresholds, the final evidence grade, and the final rankability status only. |

- Purity: `src/niche_scout/scoring.py` must not import `collector*`, `database`,
  `pipeline`, `report`, `cli`, `config`, or `sampling`; it performs no I/O, no
  `sqlite3`, no network, and no filesystem access, and never reads the clock
  (LREQ-ARCH-010/020). New imports are only `models` names (plus the existing
  `enum`/`dataclasses`/`collections.abc`/`datetime`/`math`).
- Determinism: fixed policy order, fixed top-k order, and tie-break by
  `(-score, category)`; no set/dict iteration determines any output; no randomness
  (LREQ-ARCH-030).
- Null/zero/unavailable stay distinct: `None` components, coverages, or a
  `None` warning are never converted to `0`/`0.0`/`False`; a usable count of `0`
  and a `discovered_population_count` of `0` are explicit values.
- `ValueError` is raised only for caller/policy breaches — a `None` candidate
  component, a missing candidate, misaligned sequences, a `reference_set_size`
  mismatch, or a non-finite/out-of-range threshold — never for a product value.

## 2. Typed structures

```python
#: Fixed policy evaluation order. Keys are the ones in models.SENSITIVITY_POLICIES.
SENSITIVITY_POLICY_ORDER: tuple[str, ...] = (
    "balanced", "demand_heavy", "competition_heavy",
)

#: Fixed top-k order for the stability statistics.
SENSITIVITY_TOP_K: tuple[int, ...] = (3, 5)

@dataclass(frozen=True, slots=True)
class CategorySensitivityRank:
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
    category: str
    sample_is_census: bool
    discovered_population_count: int
    usable_demand_sample_count: int
    usable_recent_supply_sample_count: int
    usable_quality_sample_count: int

    @property
    def minimum_component_sample_count(self) -> int: ...
```

Notes:

- `ranked_categories` is exactly `BaseCandidateSet.base_rankable_candidates`
  (same order, unchanged set); `categories` is 1:1 with it.
- `SensitivityDiagnostics.warning` is `bool | None`; the frozen Chunk 0
  `SensitivityResult` (with `warning: bool = False`) is left byte-identical and is
  **not** returned here. Chunk 10 persists `category_scores.sensitivity_warning`
  and `ranking_sensitivity_json` from `SensitivityDiagnostics`, not from
  `SensitivityResult` (plan §12 R1).
- `SampleEvidenceFacts` is a plain carrier: the three `usable_*_sample_count`
  values mirror `CategoryRawMetrics`; `sample_is_census` /
  `discovered_population_count` mirror `sampling.CategorySamplingResult` and the
  persisted `category_scores` columns. `scoring.py` does not import `sampling`.
  `minimum_component_sample_count` is the minimum of the three counts (SRS §9.2).

## 3. Public functions

```python
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

## 4. Semantics

### 4.1 `ranked_under_policy` (LREQ-SEN-010, LREQ-SEN-020)

Computes `renormalized_composite(components, policy)` for every supplied
candidate and returns `(category, score)` pairs sorted by descending score, ties
broken by ascending lexical category path (`(-score, category)`). Iteration over
`candidates` is the only container iteration. A missing mapping key, a candidate
whose composite is `None`, or a policy missing a `COMPONENT_WEIGHT_KEYS` key
raises `ValueError`. Empty `candidates` returns `()`.

### 4.2 `evaluate_sensitivity` (LREQ-SEN-010/-020/-030/-040)

Run-level, pure. **Caller obligations:** `all_metrics`/`scores` are 1:1 aligned by
category and every `base_rankable_candidates` member appears in `all_metrics`
(else `ValueError`). `reference_set_size` must equal
`base_candidates.run_category_count - 1` (the leave-one-out peer count; R3), else
`ValueError`.

1. Build candidate components only from the aligned `ScoreResult` fields; a
   non-4-component candidate raises `ValueError` (the 9A base rule guarantees all
   four).
2. Rank under each policy in `SENSITIVITY_POLICY_ORDER`. `balanced` is recomputed
   and equals `market_opportunity_score` / `balanced_composite` within `1e-9`; it
   is never read back or written.
3. `top_k_stability` for `k in (3, 5)`: `None` when fewer than `k` candidates;
   else `|T_k,balanced ∩ T_k,demand_heavy ∩ T_k,competition_heavy| / k`. No
   padding.
4. Per category: the three policy scores and ranks, the maximum absolute
   non-balanced-vs-balanced score difference, and the maximum absolute rank
   difference across the three policies.
5. Run-level `maximum_score_delta` / `maximum_rank_displacement` = max over
   candidates; both `None` exactly when the candidate set is empty.
6. `displacement_threshold = max(3.0, 0.25 * reference_set_size)`.
7. Warning per §4.3.

An empty candidate set returns `top_3_stability = top_5_stability =
maximum_score_delta = maximum_rank_displacement = warning = None`,
`categories = ()`, and still records `reference_set_size` and
`displacement_threshold` (explicit empty-candidate status; dependency-map §6.3).

### 4.3 Warning (LREQ-SEN-030; completing LREQ-EVD-030's sensitivity clause)

- **Top-3 clause:** applicable only when `top_3_stability is not None`; fires iff
  `top_3_stability < 2/3` (strict). When `top_3_stability is None` the clause is
  **inapplicable, not `False`**.
- **Displacement clause:** applies to every base candidate; fires iff
  `maximum_rank_displacement > displacement_threshold` (strict).

A category's `warning` is: `None` only when `ranked_categories` is empty; else
`True` iff `(top_3_stability is not None and top_3_stability < 2/3)` or the
category's displacement breach; else `False`. The run-level `warning` is the OR
over the candidates. The warning never changes a `ScoreResult`, a component, an
alternate-policy score, the candidate set, or the balanced primary score
(LREQ-SEN-030, LREQ-SEN-040).

### 4.4 `final_evidence_grade` (LREQ-EVD-050; plan §12 R6)

Precedence, all inputs explicit:

1. `decision.not_rankable_reasons` non-empty → `INSUFFICIENT`.
2. `STRONG` iff (`minimum_component_sample_count >= 80` or a census of at least
   50) **and** every one of the three stratum eligibility coverages `>=
   strong_component_coverage` **and** "verified discovery" =
   `discovery_filter_verified is True` **and** `discovery_status is
   DiscoveryStatus.COMPLETE` **and** no unresolved/conflicting identity **and**
   page-view semantics not `CONTRADICTED` **and** `run_category_count >=
   STRONG_REFERENCE_CATEGORY_COUNT` (21) **and** `sensitivity_warning is False`.
3. Otherwise `MODERATE` iff (count `>= 40` or a census of at least 20) **and**
   every required coverage `>= min_required_component_coverage` **and**
   `run_category_count >= MIN_CATEGORIES_PER_RUN` **and** no critical identity
   failure.
4. Otherwise `WEAK`.

`sample_is_census = False` means the census alternative is unavailable. A
`sensitivity_warning` of `None` is **not** acceptable for `STRONG`; it falls to
`MODERATE` (plan §12 R6).

### 4.5 `final_rankability_status` (LREQ-EVD-040; completing LREQ-EVD-030's clause)

- pre-sensitivity `NOT_RANKABLE` → `NOT_RANKABLE` (never overridden by
  sensitivity);
- pre-sensitivity `PROVISIONAL` → `PROVISIONAL`;
- pre-sensitivity `RANKABLE` → `RANKABLE` iff `sensitivity_warning is False`,
  otherwise (`True` or `None`) `PROVISIONAL` (plan §12 R7).

A sensitivity warning never demotes to `NOT_RANKABLE` and never changes the
candidate set or the balanced primary score. An 8–20 category run has an empty
candidate set and is never `RANKABLE`.

## 5. Explicitly not produced here

- Persistence, SQLite, JSON serialization, logging, report, CLI: **Chunks
  10/11/12**. This chunk returns typed values only; Chunk 10 persists the final
  `evidence_grade`, `rankability_status`, the five sensitivity columns, and
  `ranking_sensitivity_json`.
- Pre-sensitivity evidence and the frozen candidate set: **Chunk 9A**; this chunk
  consumes `PreSensitivityDecision`/`BaseCandidateSet` and never re-derives a
  not-rankable/provisional reason.
- Report rendering of the warning vocabulary (`RANKING_SENSITIVITY_HIGH`,
  `SAMPLE_BASED_SIGNAL`, …): **Chunk 11**.
- The orchestration-status half of LREQ-EVD-020 and run-level status mapping:
  **Chunk 10**.
- Rejection of runs with fewer than `MIN_CATEGORIES_PER_RUN` categories:
  **Chunk 12** (LREQ-CLI-040).
- The pre-sensitivity clauses of LREQ-EVD-030 (8–20 categories, run below 21,
  incomplete breadth fallback, coverage below strong): **Chunk 9A**. This chunk
  adds only the "or sensitivity is high" completion clause.

Consumers: **Chunks 10, 11, 12, 13**.
