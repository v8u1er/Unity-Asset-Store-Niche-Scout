# Chunk 7B — Sample-aware raw estimators

Status: FROZEN — operator-adjudicated 2026-09-20. All §12 items are resolved
(Q-1 option (a); Q-2, Q-3, and Q-4 option (a); Q-5 and Q-6 retained as labelled
RECOMMENDATIONS; new item C-1 recorded). No open question remains.

**Operator resolution (2026-09-20).** Chunk 7B **consumes** the caller-supplied
run-level `PageViewSemanticsStatus` and does **not** define or implement
contradicted-semantics detection (Q-1 option (a)). Basis: `Documents/SRS-lean.md`
provides no detection rule (LREQ-MET-040 lists four usability clauses and no
cross-run monotonicity condition; §6.5 defines the status but names no trigger);
`Documents/plans/chunk-05-graphql-protocol-adapter-and-response-correlation.md`
§12 Q5 records O-1 CLOSED with the rule "deliberately unspecified"; the
dependency-map Chunk 7B scope list (lines 806–844) omits detection and assigns
contradicted handling to Chunk 8 (LREQ-SCR-050 and the Chunk 8 outline bullet
"contradicted page-view handling"). Under `.kilo/project-rules.md` §1 the
dependency-map scope governs, which reconciles the frozen interfaces'
"Chunk 7B detects it" wording: the detection obligation is out of the lean-build
scope, and Chunk 7B always receives a non-null enum member. No detection
function is added.

Depends on (frozen interfaces required before this plan can be trusted):
  `Documents/interfaces/chunk-00.md` (Status: VERIFIED) — typed models, frozen
  constants, `MetricInput`/`MetricResult`/`RawMetricBundle`, purity boundary,
  traceability conventions.
  `Documents/interfaces/chunk-01.md` (Status: VERIFIED) — the structural-only
  boundary: no metric-eligibility semantics, no metric input, no D/R/Q verdict.
  `Documents/interfaces/chunk-03.md` (Status: VERIFIED) — `CategoryDiscoveryResult`
  (`total_count` = verified `totalCount` else `None`; `canonical_identity_count`
  = distinct resolved keys with unresolved/conflict and duplicates excluded;
  `discovery_status`; `filter_status`).
  `Documents/interfaces/chunk-05.md` (Status: VERIFIED) — per-operation status
  vocabulary, `PageViewSemanticsStatus`, `EnrichmentObservationDraft` fields, and
  the §5.8 contradicted-semantics wording reconciled by the operator resolution
  above (Q-1); 7B consumes the non-null run-level enum member.
  `Documents/interfaces/chunk-4A.md` (Status: VERIFIED) — `SamplingStratum`
  (`population_count` = `N_h`, `selected_count` = `n_h`), `CategorySamplingResult`.
  `Documents/interfaces/chunk-4B.md` (Status: VERIFIED) — the frozen
  `stratum_statistics_json` schema (`N_h`, `n_h`, `u_demand_h`, `u_recent_h`,
  `u_quality_h`, `usable_status`, `eligibility_rule`) and the explicit
  `sample_fraction`-vs-coverage distinction.
  `Documents/interfaces/chunk-7A.md` (Status: VERIFIED) — the per-observation
  eligibility, age, page-view index, recent-window, usable-stratum, and
  quality-eligibility primitives this chunk aggregates.

Blocks (chunks whose plan/implementation needs this chunk's interface):
  Chunk 8 (Normalization and primary scoring) — consumes the six raw values and
  the three stratum-eligibility coverage values; its matrix rows name Chunk 7B as
  a supporting chunk for `LREQ-NRM-010` and `LREQ-SCR-010`.
  Chunk 10 (Pipeline orchestration) — persists the raw values, coverage values,
  and `usable_*_sample_count` fields and verifies the `u_*_h` agreement gate.

## 1. Goal

Today `metrics.py` ends at Chunk 7A's per-observation primitives: it can say
whether one observation contributes and what its index or age is, but it cannot
compose a category-level raw value. This chunk makes the **sample-aware raw
estimators** real: `DemandPerAssetRaw`, the stratum-expanded weighted
`DemandMedianRaw`, `BreadthRaw`, `RecentShareRaw`, the stratum-expanded weighted
`MedianAgeRaw`, `QualityRaw`, the three stratum-eligibility coverage values, the
stratum expansion weights `N_h / n_h`, the exact weighted-median boundary rule,
and the zero-population behavior. Every estimator is pure, takes plain typed
inputs plus an explicit `scoring_cutoff_utc`, consumes Chunk 7A's eligibility
results rather than re-deriving them, returns a typed result, and keeps null,
explicit valid zero, invalid/unavailable, and low coverage distinct. Nothing
here normalizes, scores, decides evidence, or touches I/O; `scoring.py` begins at
Chunk 8.

## 2. Scope

### In scope

- `DemandPerAssetRaw` = `Σ(stratum_weight_h * stratum_view_mean_h) /
  Σ(stratum_weight_h)` over usable strata, `stratum_weight_h = N_h / N`, with
  `N = Σ N_h`; null when no stratum reaches `MIN_USABLE_SAMPLES_PER_STRATUM`;
  `N = 0` yields null and never evaluates `N_h / N` (LREQ-MET-030; SRS §7.2).
- `DemandMedianRaw` = stratum-expanded weighted median of usable page-view
  indices, each usable observation weighted `N_h / n_h`; null when the usable
  weighted sample is empty; exact-half-boundary rule (LREQ-MET-050; SRS §7.2).
- `demand_stratum_eligibility_coverage` = `Σ(N_h / N)` over strata meeting the
  usable minimum, bounded to `[0, 1]`; `0` for a verified `N = 0` category; kept
  explicitly distinct from `sample_fraction` (LREQ-MET-060; SRS §7.2).
- `BreadthRaw`: `verified_total_count` source when a structurally verified,
  category-filter-consistent `totalCount` is supplied, else
  `distinct_canonical_discovered_count` with `incomplete_estimate`; verified
  zero-result category is `0` (LREQ-MET-070; SRS §7.3).
- `RecentShareRaw` = stratum-population-weighted mean of usable
  `stratum_recent_share_h = count(0 <= age <= RECENT_WINDOW_DAYS) /
  dated_asset_count_h`, renormalized over usable strata; per-stratum share uses the
  inclusive window; missing/unusable dates reduce coverage and never contribute a
  zero to the numerator (LREQ-MET-080; SRS §7.4).
- `MedianAgeRaw` = stratum-expanded weighted median of exact ages, weight
  `N_h / n_h`, same algorithm and boundary rule as `DemandMedianRaw`;
  `recent_supply_stratum_eligibility_coverage` = represented population weight of
  usable recent strata; `usable_recent_supply_sample_count` = sum of usable dated
  observations in those strata (LREQ-MET-080; SRS §7.4).
- `QualityRaw` = `Σ_h (N_h/n_h) * Σ_i ((rating_average_i / 5) *
  age_normalized_page_view_index_i) / Σ_h (N_h/n_h) * Σ_i
  (age_normalized_page_view_index_i)` over quality-usable strata; null when the
  eligible set is too small, no stratum is quality-usable, page-view semantics are
  contradicted, coverage is below `MIN_REQUIRED_COMPONENT_COVERAGE`, or the
  expanded visibility-weighted denominator is zero;
  `quality_stratum_eligibility_coverage` not renormalized to sampled assets
  (LREQ-MET-090, LREQ-MET-100; SRS §7.5).
- The stratum expansion weight `N_h / n_h` as a pure function (SRS §7.2, §7.4,
  §7.5).
- Component coverage: the three `*_stratum_eligibility_coverage` values, each
  distinguishable from `sample_fraction` and from a valid metric value of zero.
- The exact weighted-median boundary behavior and zero-population behavior,
  including a frozen golden-vector set and unequal-stratum fixtures.
- Determinism over identical inputs (LREQ-ARCH-030).

### Explicitly out of scope (and who owns it instead)

- **Normalization, components, and composite score.** `P_ref`, `D0`, `D`, `C`,
  `R0`, `R`, `Q0`, `Q`, the fixed weights, coverage shrinkage, clamping,
  `score_state`, evidence grade, rankability, and sensitivity are **Chunk 8**
  (and 9A/9B). `LREQ-NRM-010` and `LREQ-SCR-010` are Chunk 8's primary
  requirements; Chunk 7B is only their prerequisite and attaches no marker for
  them.
- **Applying `MIN_REQUIRED_COMPONENT_COVERAGE` to Demand and Recent Supply
  rankability.** SRS §7.5 places the D/R effect on "the affected component"
  (rankability/composite weight), which is Chunks 8/9A. Chunk 7B computes and
  returns the coverage value and does **not** null the Demand/Recent raws.
  `QualityRaw` **itself** is null below the threshold (Q-3 resolved, option (a)).
- **Contradicted page-view-semantics detection (out of scope by operator ruling,
  Q-1).** Chunk 7B **consumes** the caller-supplied, non-null
  `PageViewSemanticsStatus` and does **not** detect `contradicted`; no detection
  function is specified here.
- **Persistence, orchestration, warnings, report wording, CLI.** Chunks 2/10/11/12.
  Chunk 7B returns typed values and emits no `WarningCode`.
- **Discovery-side classification.** `total_count` verification, filter
  consistency, canonical identity counts, strata, and `n_h` are Chunks 1/3/4A/4B.
  Chunk 7B consumes already-classified fields and never re-derives them.
- **Per-observation eligibility semantics.** Owned by Chunk 7A; Chunk 7B calls
  its primitives (LREQ-MET-010/020/040/090 primitives) and does not duplicate them.
- **Traceability-validator widening.** Chunk 13 (`LREQ-NFR-060`).

## 3. Requirements this chunk must satisfy

Ownership roles are the labels from `Documents/requirements-dependency-map.md`
"Ownership and test traceability matrix" (lines 45–136). Normative text is quoted
from `Documents/SRS-lean.md`.

| LREQ ID | Ownership role here | Normative text (from SRS-lean.md, quoted) | SRS section |
|---|---|---|---|
| LREQ-MET-030 | **Primary implementation chunk** (matrix line 85; supporting Chunks 4B/7A; completion Chunk 7B). Required test `LREQ-TST-050`. | "The demand-per-asset estimate SHALL be: `DemandPerAssetRaw = sum(stratum_weight_h * stratum_view_mean_h for usable strata) / sum(stratum_weight_h for usable strata)`. It is null when no stratum has at least `MIN_USABLE_SAMPLES_PER_STRATUM` usable observations." / "When `N = 0`, … the implementation SHALL never evaluate `N_h / N`." / "The denominator is the sum of population weights for usable strata, not `N` alone." | §7.2 |
| LREQ-MET-040 | **Primary implementation chunk** (matrix line 86; supporting Chunks 5/7A; completion Chunk 7B). Required test `LREQ-TST-050`. | "The page-view index SHALL be: `age_normalized_page_view_index = product_page_views * 7 / age_days_exact`. It is usable only for a finite non-negative page-view value, a valid UTC date no later than cutoff, `age_days_exact >= MIN_AGE_DAYS_FOR_RATE`, and a matched, published identity. An explicit valid page-view value of zero is usable and yields an index of zero." | §7.2 |
| LREQ-MET-050 | **Primary implementation chunk** (matrix line 87; supporting Chunks 4B/7A; completion Chunk 7B). Required test `LREQ-TST-050`. | "`DemandMedianRaw` SHALL be a stratum-expanded weighted median of usable product indices. Each usable observation in stratum `h` receives weight `N_h / n_h`. The weighted median is the first sorted value whose cumulative weight is at least half the total weight. If cumulative weight equals exactly half at a value boundary, use the arithmetic mean of that value and the next sorted value; when the boundary value is the final sorted value, use that final value. It is null when the usable weighted sample is empty." / "sort finite usable values ascending, retain ties as separate observations, compute cumulative weights in that order, and compare with exactly half the total weight. Missing, invalid, or unusable values contribute no weight. The same algorithm and boundary rule SHALL be used for `MedianAgeRaw`." | §7.2 |
| LREQ-MET-060 | **Primary implementation chunk** (matrix line 88; supporting Chunks 4B/7A; completion Chunk 7B). Required test `LREQ-TST-050`. | "`demand_stratum_eligibility_coverage = sum(stratum_weight_h for strata meeting the usable minimum)` bounded to `[0, 1]`." / "It is not the percentage of assets directly observed, a probability-sampling coverage estimate, or a confidence measure. … it SHALL not be confused with `sample_fraction`." / "For a verified category with `N = 0`, demand stratum eligibility coverage SHALL be `0` and demand raw metrics SHALL be null." | §7.2 |
| LREQ-MET-070 | **Primary implementation chunk** (matrix line 89; supporting Chunks 3/4A/7A; completion Chunk 7B). Required test `LREQ-TST-050`. | "`BreadthRaw` SHALL be the verified discovered canonical population count, not the enrichment sample size. When the endpoint provides a structurally verified, category-filter-consistent `totalCount`, `breadth_source` SHALL be `verified_total_count` and `BreadthRaw` SHALL equal that count. Otherwise, `breadth_source` SHALL be `distinct_canonical_discovered_count`, `BreadthRaw` SHALL equal the distinct canonical discovered count, and `breadth_completeness_status` SHALL be `incomplete_estimate`." / "A failed or truncated discovery page SHALL never be interpreted as zero assets." / "For a verified zero-result category, `discovered_population_count` and `BreadthRaw` SHALL be `0`…" | §7.3 |
| LREQ-MET-080 | **Primary implementation chunk** (matrix line 90; supporting Chunks 5/7A; completion Chunk 7B). Required test `LREQ-TST-050`. | "`stratum_recent_share_h = count(0 <= age_days_exact <= RECENT_WINDOW_DAYS) / dated_asset_count_h`." / "`RecentShareRaw` SHALL be the stratum-population-weighted mean of usable `stratum_recent_share_h` values, renormalized over usable strata. `MedianAgeRaw` SHALL be the corresponding stratum-expanded weighted median of exact ages. A stratum SHALL be usable for Recent Supply only when its dated usable count meets `MIN_USABLE_SAMPLES_PER_STRATUM`; `recent_supply_stratum_eligibility_coverage` SHALL be the represented population weight of those usable strata. `usable_recent_supply_sample_count` SHALL be the sum of usable dated observations in those strata." / "Each usable dated observation receives expansion weight `N_h / n_h` for `MedianAgeRaw`; missing or unusable dates SHALL reduce coverage and SHALL NOT contribute zero to the recent-share numerator." / "When `N = 0`, RecentShareRaw and MedianAgeRaw SHALL be null and `recent_supply_stratum_eligibility_coverage` SHALL be `0`." | §7.4 |
| LREQ-MET-090 | **Primary implementation chunk** (matrix line 91; supporting Chunks 5/7A; completion Chunk 7B). Required test `LREQ-TST-050`. | "Default quality constants SHALL be: `QUALITY_MIN_RATING_COUNT = 5`, `QUALITY_MIN_ELIGIBLE_ASSETS = 5`. Quality is unavailable below the minimum eligible count." / "`quality_stratum_eligibility_coverage` SHALL be the sum of `N_h / N` for strata with at least `MIN_USABLE_SAMPLES_PER_STRATUM` quality-eligible observations; it is not a count fraction and is not renormalized to the sampled assets." / "Quality SHALL also be unavailable when weighted usable coverage is below `MIN_REQUIRED_COMPONENT_COVERAGE`, when page-view semantics are contradicted, or when the visibility-weighted denominator is zero. `rating_count` is a reliability minimum only and SHALL NOT weight the quality formula." | §7.5 |
| LREQ-MET-100 | **Primary implementation chunk** (matrix line 92; supporting Chunks 5/4B/7A; completion Chunk 7B). Required test `LREQ-TST-050`. | "For each quality-usable stratum `h`, define `quality_weight_h = N_h / n_h` and: `quality_numerator_h = quality_weight_h * sum((rating_average_i / 5) * age_normalized_page_view_index_i for quality-eligible i in stratum h)`; `quality_denominator_h = quality_weight_h * sum(age_normalized_page_view_index_i for quality-eligible i in stratum h)`; `QualityRaw = sum(quality_numerator_h for quality-usable strata) / sum(quality_denominator_h for quality-usable strata)`." / "It is null when the eligible set is too small, no stratum is quality-usable, or the expanded visibility-weighted denominator is zero." / "When `N = 0`, QualityRaw SHALL be null and `quality_stratum_eligibility_coverage` SHALL be `0`." | §7.5 |
| LREQ-ARCH-030 | **Supporting chunk** (primary/completion owner Chunk 10; matrix line 49; `metrics.py` is in this LREQ's module set, matrix line 147). | "The same normalized input data, policy versions, and configuration SHALL produce the same metric, score, evidence, and sensitivity outputs." | §3.3 |

### Supporting requirements consumed but not owned (no marker attached here)

Per the `chunk-4A`/`chunk-05`/`chunk-7A` precedent, Chunk 7B attaches **no**
`LREQ-TST-*` marker: `LREQ-TST-010`/`LREQ-TST-050` are Chunk 13's requirements
(matrix lines 127, 131), and Chunk 7B is a supporting chunk only.

| LREQ ID | Role here | What this chunk satisfies | SRS section |
|---|---|---|---|
| LREQ-NRM-010 | Prerequisite (primary owner Chunk 8; matrix line 93 names Chunk 7B as a supporting chunk). | Supplies the six raw values `P_ref` is built over; Chunk 7B does no leave-one-out work. No marker. | §8.1 |
| LREQ-SCR-010 | Prerequisite (primary owner Chunk 8; matrix line 97 names Chunk 7B as a supporting chunk). | Supplies `DemandPerAssetRaw`, `DemandMedianRaw`, and `demand_stratum_eligibility_coverage`; Chunk 8 composes `D`. No marker. | §8.2 |
| LREQ-SMP-080 | Consumed contract (primary owner Chunk 4B). | Reads `N_h`, `n_h`, and the `u_*_h` stratum-summary schema; Chunk 7B recomputes the usable counts from observations so Chunk 10 can verify agreement. No marker. | §5.1 |
| LREQ-TST-010, LREQ-TST-050 | Consumed obligations (primary owner Chunk 13). | Formula tests cover normal, explicit valid zero, missing, invalid, ties, and minimum boundaries; metric tests cover weighted strata/medians and zero denominators. Marker deferred to Chunk 13. | §13 |
| LREQ-MET-010, LREQ-MET-020 | Consumed primitives (primary owner Chunk 7A; completion Chunk 7A). | Chunk 7B calls 7A's classification/age primitives and does not re-implement them. No marker. | §7.1 |

## 4. Interface contracts consumed

Copied from the frozen interface files; none is redefined here.

**From Chunk 0 (`niche_scout.models`, interface §3–§4, §7):**

```python
MIN_USABLE_SAMPLES_PER_STRATUM: int = 5
MIN_AGE_DAYS_FOR_RATE: int = 30
RECENT_WINDOW_DAYS: int = 365
QUALITY_MIN_RATING_COUNT: int = 5
QUALITY_MIN_ELIGIBLE_ASSETS: int = 5
MIN_REQUIRED_COMPONENT_COVERAGE: float = 0.50

class OperationStatus(str, Enum):            # success | error
class PageViewSemanticsStatus(str, Enum):    # unvalidated | validated_cumulative | contradicted
class BreadthSource(str, Enum):              # verified_total_count | distinct_canonical_discovered_count
class BreadthCompletenessStatus(str, Enum):  # complete | incomplete_estimate

@dataclass(frozen=True, slots=True)
class MetricResult:
    value: float | None
    usable_sample_count: int
    eligible_population_count: int
    eligibility_coverage: float | None
    unavailable_reason: str | None = None

@dataclass(frozen=True, slots=True)
class RawMetricBundle:
    demand_per_asset_raw: float | None = None
    demand_median_raw: float | None = None
    breadth_raw: float | None = None
    recent_share_raw: float | None = None
    median_age_raw: float | None = None
    quality_raw: float | None = None
```

Frozen semantics relied on: `MetricResult.value is None` means unavailable and is
never a fabricated `0`/`0.0`; `unavailable_reason` is `None` when the value is
present (`chunk-00.md` §7). `MetricInput`, `MetricResult`, `RawMetricBundle` are
**not** changed; this chunk is additive.

**From Chunk 7A (`niche_scout.metrics`, interface §4):** the frozen primitives
Chunk 7B aggregates — `age_days_exact`, `age_normalized_page_view_index`,
`is_within_recent_window`, `stratum_is_usable`,
`quality_observation_eligibility`, and the result types `MetricValue` /
`MetricEligibility` / `MetricTimestamp`; plus the module-local
`METRIC_UNAVAILABLE_REASONS` vocabulary. Chunk 7B calls these and does not
re-derive the eligibility rules.

**From Chunk 4B (`stratum_statistics_json`, interface §5.2):** each stratum object
carries `N_h`, `n_h`, `u_demand_h`, `u_recent_h`, `u_quality_h`, `usable_status`,
`eligibility_rule`. The per-stratum `usable_status` is the authoritative pending
state; Chunk 7B produces the category-level raw/coverage values, and Chunk 10
verifies that the recomputed `u_*_h` agree.

**From Chunk 4A (`SamplingStratum`, interface §5.3):** `population_count` = `N_h`
and `selected_count` = `n_h`; a census category is one stratum.

**From Chunk 3 (`CategoryDiscoveryResult`, interface §3):**
`total_count: int | None` ("verified totalCount, else None");
`canonical_identity_count: int` (distinct resolved keys, unresolved/conflict
excluded, duplicates collapsed); `discovery_status`; `filter_status`. Chunk 7B
consumes these as already-classified inputs; it never re-verifies a totalCount and
never re-resolves identity.

### 4.1 Input the production caller supplies

Chunk 10 projects persisted `SampleMemberRecord` + `EnrichmentObservationRecord`
rows (and the finalized `stratum_statistics_json`) into the plain typed input of
§5.2 and passes the run's explicit `scoring_cutoff_utc`. That read is I/O and stays
in Chunk 10.

## 5. Interface contract this chunk produces

This section is the frozen `Documents/interfaces/chunk-7B.md` body (the lead
copies it verbatim when the interface file is created). Everything lives in
`src/niche_scout/metrics.py` and is **additive**: nothing in `models.py`,
`validation.py`, `sampling.py`, `scoring.py`, `config.py`, or `database.py` is
redefined, shadowed, or modified.

### 5.0 Module and boundary rules

| Item | Kind | Rule |
|---|---|---|
| `src/niche_scout/metrics.py` | **Pure** | Raw estimators, stratum expansion weights, component coverage, and the shared weighted median only. No I/O, no clock, no randomness, no `sqlite3`, no `json`, no package I/O module import. |

- `metrics.py` adds `collections.abc` (`Sequence`) and continues to import only
  `math` (`isfinite`), `dataclasses`, `datetime`, `enum`, `typing`, `models`, and
  `validation`. It SHALL NOT import `collector`, `collector_coveo`,
  `collector_graphql`, `database`, `pipeline`, `report`, `cli`, `config`,
  `scoring`, or any filesystem/process/network/clock module, and SHALL NOT import
  `json` (LREQ-ARCH-010; `check_import_boundaries.FORBIDDEN_MODULES`, read).
- Every estimator is deterministic: identical typed inputs plus identical
  constants produce structurally and numerically equal results. Weights are
  summed in a fixed stratum order; the weighted median sorts by `(value,
  insertion index)` so ties are stable and no set/dict iteration affects output
  (LREQ-ARCH-030).
- Null, explicit valid zero, invalid/unavailable, and low coverage stay distinct.
  A `None` input never becomes `0`/`0.0`; a valid computed zero (`0.0` share,
  `0` breadth, explicit-zero index) is a value, not a reason.
- `scoring_cutoff_utc` is always an explicit parameter and must be timezone-aware
  UTC (delegated to Chunk 7A's primitives, which raise `ValueError` otherwise).
- **`ValueError` boundary.** A caller/policy parameter or an inconsistent typed
  input raises `ValueError` (e.g. a non-positive `N_h`/`n_h`, a
  `len(observations) != n_h` mismatch, duplicate or negative `stratum_index`, a
  non-int / negative `min_usable_samples_per_stratum`, a coverage threshold
  outside `[0, 1]`, a non-finite/negative element of a weighted-median vector). No
  product-level value is re-classified here; product-level classification stays
  Chunk 7A's and is never raised away.
- No `WarningCode` is emitted and no warning is persisted.

### 5.1 Aggregate unavailable-reason vocabulary (module-local; spelling is a RECOMMENDATION, not SRS-backed)

The SRS names the outcome categories ("null when no stratum …", "null when the
eligible set is too small", "denominator is zero", "coverage below the
threshold") but names no machine-readable string. Following Chunk 7A's
`METRIC_UNAVAILABLE_REASONS` precedent, Chunk 7B adds a closed tuple. **The
string spelling is a RECOMMENDATION (Q-6); the outcome categories are SRS-backed.**

```python
METRIC_REASON_NO_USABLE_STRATUM: str = "no_usable_stratum"        # SRS §7.2/§7.4/§7.5
METRIC_REASON_ZERO_POPULATION: str = "zero_population"           # SRS §7.2/§7.4/§7.5
METRIC_REASON_EMPTY_USABLE_SAMPLE: str = "empty_usable_sample"   # SRS §7.2 (median)
METRIC_REASON_ELIGIBLE_SET_TOO_SMALL: str = "eligible_set_too_small"  # SRS §7.5 (QUALITY_MIN_ELIGIBLE_ASSETS)
METRIC_REASON_ZERO_DENOMINATOR: str = "zero_denominator"         # SRS §7.5
METRIC_REASON_INSUFFICIENT_COVERAGE: str = "insufficient_coverage"  # SRS §7.5 (Q-3)

METRIC_AGGREGATE_UNAVAILABLE_REASONS: tuple[str, ...] = (
    METRIC_REASON_NO_USABLE_STRATUM,
    METRIC_REASON_ZERO_POPULATION,
    METRIC_REASON_EMPTY_USABLE_SAMPLE,
    METRIC_REASON_ELIGIBLE_SET_TOO_SMALL,
    METRIC_REASON_ZERO_DENOMINATOR,
    METRIC_REASON_INSUFFICIENT_COVERAGE,
)
```

`METRIC_REASON_ZERO_POPULATION` is used only when `N = 0`; otherwise a null
result uses the estimator's specific reason. A reason is always paired with a
null value; an available value carries `unavailable_reason is None`.

### 5.2 Typed inputs

```python
@dataclass(frozen=True, slots=True)
class MetricObservation:
    """One sampled asset's product-level inputs for every 7B estimator.

    Fields mirror the persisted `EnrichmentObservationRecord` columns and are
    passed to Chunk 7A's primitives unchanged; Chunk 7B never re-classifies them.
    """
    product_page_views: object
    first_published_date_utc: object
    state: str | None
    id_mapping_mismatch: bool
    rating_average: object
    rating_count: object
    product_detail_status: OperationStatus
    page_views_status: OperationStatus

@dataclass(frozen=True, slots=True)
class StratumMetricInput:
    """One stratum's authoritative population facts plus its sampled assets.

    `discovered_population_count` is `N_h`; `sampled_population_count` is `n_h`
    (SRS §7.2: the persisted stratum summary is authoritative for `N_h` and `n_h`;
    formulas SHALL not reconstruct population denominators from the sample). The
    usable counts `u_demand_h` / `u_recent_h` / `u_quality_h` are **not** inputs:
    Chunk 7B recomputes them from `observations` so Chunk 10 can verify the
    agreement gate. `len(observations)` MUST equal `sampled_population_count`.
    """
    stratum_index: int
    discovered_population_count: int
    sampled_population_count: int
    observations: tuple[MetricObservation, ...]

@dataclass(frozen=True, slots=True)
class CategoryMetricInput:
    """Everything the six raw estimators need for one category (SRS §7).

    `strata` is in ascending `stratum_index` order. `N = sum(N_h)` and is never
    supplied separately. Threshold parameters default to the frozen `models`
    constants because SRS §14 marks them configurable; production callers use the
    defaults.
    """
    category: str
    scoring_cutoff_utc: datetime
    page_view_semantics_status: PageViewSemanticsStatus
    strata: tuple[StratumMetricInput, ...]
    min_usable_samples_per_stratum: int = MIN_USABLE_SAMPLES_PER_STRATUM
    min_age_days_for_rate: int = MIN_AGE_DAYS_FOR_RATE
    recent_window_days: int = RECENT_WINDOW_DAYS
    quality_min_rating_count: int = QUALITY_MIN_RATING_COUNT
    quality_min_eligible_assets: int = QUALITY_MIN_ELIGIBLE_ASSETS
    min_required_component_coverage: float = MIN_REQUIRED_COMPONENT_COVERAGE

@dataclass(frozen=True, slots=True)
class BreadthMetricInput:
    """The already-classified discovery facts for one category (SRS §7.3).

    `verified_total_count` is the endpoint `totalCount` only when it is
    structurally verified and category-filter-consistent, else `None` (Chunk 3's
    `CategoryDiscoveryResult.total_count` semantics). `distinct_canonical_discovered_count`
    is Chunk 3's `canonical_identity_count`: distinct resolved keys with
    duplicates collapsed and unresolved/conflict records excluded.
    """
    verified_total_count: int | None
    distinct_canonical_discovered_count: int

@dataclass(frozen=True, slots=True)
class BreadthResult:
    """`BreadthRaw` plus its provenance (SRS §7.3). Never null (Q-4)."""
    breadth_raw: int
    breadth_source: BreadthSource
    breadth_completeness_status: BreadthCompletenessStatus

@dataclass(frozen=True, slots=True)
class CategoryRawMetrics:
    """The frozen `RawMetricBundle` plus the SRS-named coverage/count fields.

    `usable_*_sample_count` follow SRS §6.5/§7.4: observations contributing to
    strata that satisfy the applicable usable minimum.
    """
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

### 5.3 Public functions

```python
def stratum_expansion_weight(
    discovered_population_count: int, sampled_population_count: int
) -> float:
    """`N_h / n_h`, the per-observation expansion weight (SRS §7.2, §7.4, §7.5).

    Each argument must be an `int >= 1` (a `bool` raises `ValueError`, because
    `isinstance(True, int)` is `True`). Pure. This is the weight used by
    `DemandMedianRaw`, `MedianAgeRaw`, and both sums of `QualityRaw`; it is NOT
    the `N_h / N` stratum weight used by `DemandPerAssetRaw` and `RecentShareRaw`.
    """

def weighted_median(
    values_and_weights: Sequence[tuple[float, float]]
) -> float | None:
    """Exact-boundary stratum-expanded weighted median (LREQ-MET-050).

    Sort by value ascending, retaining equal values as separate observations in
    input order; let `T` be the total weight. Missing, invalid, or unusable
    values contribute no weight, so an entry with weight `0.0` contributes
    nothing and an empty (or all-zero-weight) sequence returns `None` (SRS §7.2:
    "It is null when the usable weighted sample is empty"). Otherwise walk the
    sorted order accumulating weight and return the first value whose cumulative
    weight is `>= T / 2`. When that cumulative weight equals exactly `T / 2` and a
    next sorted value exists, return `(value + next_value) / 2`; the SRS's
    "boundary value is the final sorted value" branch is defensive and
    unreachable for `T > 0` (the last cumulative weight is `T > T / 2`) — see
    §12 Q-2. A non-finite value or weight, or a negative weight, raises
    `ValueError` (caller-contract breach, not a product value). Pure.
    """

def breadth_raw(breadth_input: BreadthMetricInput) -> BreadthResult:
    """Verified discovered canonical breadth (LREQ-MET-070).

    If `verified_total_count is not None`, return
    `BreadthResult(verified_total_count, VERIFIED_TOTAL_COUNT, COMPLETE)`.
    Otherwise return
    `BreadthResult(distinct_canonical_discovered_count,
    DISTINCT_CANONICAL_DISCOVERED_COUNT, INCOMPLETE_ESTIMATE)`. A verified
    zero-result category therefore has `breadth_raw == 0`. Never `None`; a
    failed/truncated page is handled by `Competition` availability (Chunk 8,
    LREQ-SCR-020), not by a null raw (Q-4). Both counts must be `int >= 0`.
    Pure.
    """

def demand_stratum_eligibility_coverage(input: CategoryMetricInput) -> float:
    """`sum(N_h / N)` over strata with `u_demand_h >= min`, clamped to `[0, 1]`.

    Zero when `N == 0` (LREQ-MET-030/060). Distinct from `sample_fraction`
    (`enriched_sample_count / discovered_population_count`, SRS §5.1); Chunk 7B
    never computes or returns `sample_fraction`. Pure.
    """

def demand_per_asset_raw(input: CategoryMetricInput) -> MetricResult:
    """Population-weighted demand mean (LREQ-MET-030; SRS §7.2).

    Usable strata are those with `u_demand_h >= min_usable_samples_per_stratum`;
    `stratum_view_mean_h` is the mean of Chunk 7A's usable indices in stratum
    `h`; `stratum_weight_h = N_h / N`. Returns
    `sum(w_h * mean_h) / sum(w_h)` over usable strata. Null
    (`METRIC_REASON_ZERO_POPULATION`) when `N == 0`, and never evaluates
    `N_h / N` then; null (`METRIC_REASON_NO_USABLE_STRATUM`) when `N > 0` and no
    stratum is usable. An explicit valid index of `0.0` is a value and counts
    toward the stratum mean. Pure.
    """

def demand_median_raw(input: CategoryMetricInput) -> MetricResult:
    """Stratum-expanded weighted median of usable indices (LREQ-MET-050).

    Every usable observation (in any stratum) contributes with weight
    `N_h / n_h`; the shared `weighted_median` boundary rule applies. Null when
    the usable weighted sample is empty (`METRIC_REASON_EMPTY_USABLE_SAMPLE`), or
    (`METRIC_REASON_ZERO_POPULATION`) when `N == 0`. Unusable observations
    contribute no weight and never a zero. Pure.
    """

def recent_supply_stratum_eligibility_coverage(
    input: CategoryMetricInput,
) -> float:
    """`sum(N_h / N)` over strata with `u_recent_h >= min` (LREQ-MET-080).

    Zero when `N == 0`; not renormalized. Pure.
    """

def recent_share_raw(input: CategoryMetricInput) -> MetricResult:
    """Population-weighted recent share (LREQ-MET-080; SRS §7.4).

    For each usable recent stratum,
    `stratum_recent_share_h = count(0 <= age <= recent_window_days) / u_recent_h`
    using Chunk 7A's exact ages and inclusive `is_within_recent_window`; the
    result is `sum(w_h * share_h) / sum(w_h)` with `w_h = N_h / N`, renormalized
    over usable strata. An unusable date reduces `u_recent_h` and the coverage and
    is never a zero numerator entry. Null (`METRIC_REASON_ZERO_POPULATION`) when
    `N == 0`; null (`METRIC_REASON_NO_USABLE_STRATUM`) when no stratum is usable.
    A measured share of `0.0` is a value. Pure.
    """

def median_age_raw(input: CategoryMetricInput) -> MetricResult:
    """Stratum-expanded weighted median of exact ages (LREQ-MET-080).

    Every usable dated observation contributes with weight `N_h / n_h`; exact
    fractional ages come from Chunk 7A's `age_days_exact` and the shared
    `weighted_median` boundary rule applies. Null when the usable weighted sample
    is empty (`METRIC_REASON_EMPTY_USABLE_SAMPLE`), or when `N == 0`
    (`METRIC_REASON_ZERO_POPULATION`). Pure.
    """

def quality_stratum_eligibility_coverage(input: CategoryMetricInput) -> float:
    """`sum(N_h / N)` over strata with `>= min` quality-eligible observations.

    Not a count fraction and not renormalized to the sampled assets (LREQ-MET-090;
    SRS §7.5). Zero when `N == 0`. Pure.
    """

def quality_raw(input: CategoryMetricInput) -> MetricResult:
    """Stratum-expanded visibility-weighted quality (LREQ-MET-090/100; SRS §7.5).

    A quality-usable stratum has at least `min_usable_samples_per_stratum`
    quality-eligible observations (Chunk 7A's `quality_observation_eligibility`
    with `page_view_semantics_status`). For each, recompute the Chunk 7A index and
    use `rating_average`:

    `num_h = (N_h/n_h) * sum((rating_average_i / 5) * index_i)` and
    `den_h = (N_h/n_h) * sum(index_i)`, over quality-eligible observations in `h`;
    `QualityRaw = sum(num_h) / sum(den_h)`. Null with, in precedence order:
    `METRIC_REASON_ZERO_POPULATION` (`N == 0`),
    `METRIC_REASON_ELIGIBLE_SET_TOO_SMALL` (total quality-eligible observations
    below `quality_min_eligible_assets`),
    `METRIC_REASON_NO_USABLE_STRATUM` (no quality-usable stratum),
    `METRIC_REASON_INSUFFICIENT_COVERAGE` (`quality_stratum_eligibility_coverage
    < min_required_component_coverage`),
    `METRIC_REASON_ZERO_DENOMINATOR` (`sum(den_h) == 0.0`), or
    `METRIC_REASON_PAGE_VIEW_SEMANTICS_CONTRADICTED` (run-level status is
    `CONTRADICTED`, which also makes every observation quality-ineligible through
    Chunk 7A). `rating_count` never weights the formula. The reason order above is
    a documented RECOMMENDATION (C-1). Pure.
    """

def compute_raw_metric_bundle(input: CategoryMetricInput) -> RawMetricBundle:
    """The six raw values as the frozen `RawMetricBundle` (SRS §8.1 field set).

    Breadth is not derivable from `CategoryMetricInput`; `breadth_raw` is left
    `None` here and filled by `compute_category_raw_metrics`. Every other field is
    the corresponding estimator's `.value`. Pure.
    """

def compute_category_raw_metrics(
    input: CategoryMetricInput, breadth_input: BreadthMetricInput
) -> CategoryRawMetrics:
    """All six raw values, the three coverages, the three usable counts, and the
    breadth provenance in one deterministic value (SRS §6.5 field set). Pure.
    """
```

### 5.4 `MetricResult` field semantics (non-normative plan-design RECOMMENDATION — Q-5)

| Estimator | `.value` | `.usable_sample_count` | `.eligible_population_count` | `.eligibility_coverage` |
|---|---|---|---|---|
| `demand_per_asset_raw` | `DemandPerAssetRaw` | `Σ u_demand_h` over usable strata | `Σ N_h` over usable strata | demand coverage |
| `demand_median_raw` | `DemandMedianRaw` | usable index observations (all strata) | `Σ N_h` over strata with ≥1 usable index | demand coverage |
| `recent_share_raw` | `RecentShareRaw` | `Σ u_recent_h` over usable recent strata | `Σ N_h` over usable recent strata | recent coverage |
| `median_age_raw` | `MedianAgeRaw` | usable age observations (all strata) | `Σ N_h` over strata with ≥1 usable age | recent coverage |
| `quality_raw` | `QualityRaw` | `Σ` quality-eligible over quality-usable strata | `Σ N_h` over quality-usable strata | quality coverage |

`eligible_population_count` is an SRS-unnamed convenience count: the SRS names
only the `usable_*_sample_count` fields (SRS §6.5), not `eligible_population_count`.
This table is a non-normative plan-design RECOMMENDATION and is independent of
`.value` and `.eligibility_coverage`; Chunk 8/10 may challenge it without
affecting either.

## 6. Files touched

| File | New/modified | Purpose |
|---|---|---|
| `src/niche_scout/metrics.py` | modified | Add the raw estimators, coverage functions, `N_h/n_h` weight, shared weighted median, typed inputs/results, and aggregate reason vocabulary (§5). `MetricInput`, `MetricResult`, `RawMetricBundle`, and all Chunk 7A names are unchanged. |
| `tests/test_metrics.py` | new | Chunk 7B analytical tests (§9). |
| `tests/fixtures/metric_estimator_fixtures.py` | new | Inert golden vectors and builders (§9.2); data only, no logic, no assertions. |
| `tests/fixtures/__init__.py` | modified | Add `metric_estimator_fixtures` to the imports and `__all__`. |
| `tests/traceability.json` | modified (append-only) | One entry per new node (§9.4); no existing entry edited, removed, or reordered. |

No other file is edited. `models.py`, `validation.py`, `sampling.py`,
`scoring.py`, `config.py`, `database.py`, the collector modules,
`src/niche_scout/tools/check_import_boundaries.py` (no `PURE_MODULES` change),
`tests/fixtures/validation_fixtures.py`, `tests/fixtures/date_eligibility_fixtures.py`,
and all interface documents are untouched.

## 7. Task breakdown

Ordered checklist, each item tagged with the LREQ ID(s) it implements:

- [ ] Add `Sequence` (`collections.abc`) and the `BreadthSource` /
  `BreadthCompletenessStatus` / `MIN_REQUIRED_COMPONENT_COVERAGE` /
  `QUALITY_MIN_ELIGIBLE_ASSETS` imports from `models`. Do not re-declare numeric
  values. (LREQ-ARCH-010)
- [ ] Define `METRIC_AGGREGATE_UNAVAILABLE_REASONS` (§5.1). (LREQ-MET-030)
- [ ] Define the typed inputs/results (§5.2). (LREQ-MET-030)
- [ ] Implement `stratum_expansion_weight`. (LREQ-MET-050, LREQ-MET-100)
- [ ] Implement `weighted_median` with the exact boundary rule, stable tie order,
  zero-weight dropping, and null on empty/zero total weight. (LREQ-MET-050)
- [ ] Implement `demand_stratum_eligibility_coverage` and
  `demand_per_asset_raw`, including the `N == 0` no-`N_h/N` guard and the
  no-usable-stratum null. (LREQ-MET-030, LREQ-MET-060)
- [ ] Implement `demand_median_raw` over all usable indices with `N_h/n_h`.
  (LREQ-MET-050)
- [ ] Implement `recent_supply_stratum_eligibility_coverage`, `recent_share_raw`,
  and `median_age_raw` using Chunk 7A's `age_days_exact` and
  `is_within_recent_window`. (LREQ-MET-080)
- [ ] Implement `quality_stratum_eligibility_coverage` and `quality_raw` using
  Chunk 7A's `quality_observation_eligibility` and
  `age_normalized_page_view_index`, the `N_h/n_h` weight, the eligibility-set /
  coverage / zero-denominator / contradicted guards. (LREQ-MET-090, LREQ-MET-100)
- [ ] Implement `breadth_raw` and `BreadthResult`. (LREQ-MET-070)
- [ ] Implement `compute_raw_metric_bundle` and `compute_category_raw_metrics`.
  (LREQ-MET-030, -050, -060, -070, -080, -100)
- [ ] Confirm no product-level value raises; only the caller-contract breaches in
  §5.0 raise `ValueError`. (LREQ-MET-030)
- [ ] Write `tests/fixtures/metric_estimator_fixtures.py` with the vectors in
  §9.2 and re-export it from `tests/fixtures/__init__.py`. (§9)
- [ ] Write `tests/test_metrics.py` with the nodes in §9.3 and add the
  `tests/traceability.json` entries in §9.4. (§9)
- [ ] Run `python -m pytest tests/test_metrics.py -q`, then the full suite, then
  `python -m niche_scout.tools.check_import_boundaries`,
  `python -m niche_scout.tools.validate_traceability`, and `ruff format` /
  `ruff check` over the touched files. (§10)

## 8. Edge cases and invariants

From the dependency map's Edge cases column for every owned LREQ, plus the
chunk's gate text:

- **Never divide by zero.** `N = 0` never evaluates `N_h / N`; `n_h = 0` is
  rejected before `N_h / n_h`; a quality stratum with zero total index is the
  zero-denominator null (SRS §7.2, §7.5).
- **No usable stratum.** `DemandPerAssetRaw` / `RecentShareRaw` / `QualityRaw`
  are null; `DemandMedianRaw` / `MedianAgeRaw` are null only when the *usable
  weighted sample* is empty, which is a different condition (map lines 213, 218).
- **Zero population.** For `N = 0`: all sample-derived raws null, all three
  coverages `0`, and `BreadthRaw` `0` only when the discovery is a *verified*
  zero-result category (SRS §7.3–§7.5).
- **Usable minimum is inclusive.** `u_h == MIN_USABLE_SAMPLES_PER_STRATUM (5)`
  is usable; `4` is not (map lines 213, 218).
- **Weighted median.** Ties stay separate observations; cumulative weights are
  compared with exactly half the total; an exact-half cumulative weight averages
  the value with the next sorted value; a non-finite or negative weight is a
  caller breach; zero-weight entries contribute nothing (map line 215).
- **Sample fraction vs coverage.** `sample_fraction` is
  `enriched_sample_count / discovered_population_count` (Chunk 4A); stratum
  eligibility coverage is a population-weight proportion. They are never
  substituted for each other (map lines 216, 84; chunk gate).
- **Quality expands by `N_h / n_h`, not a sample average.** The `N_h/n_h` weight
  multiplies both the numerator and the denominator per stratum; a stratum's own
  ratio of sums is what survives after the weight cancels within a stratum, so
  unequal strata are expanded by their population-to-sample ratio, not averaged
  (map line 220; chunk gate).
- **Low coverage stays distinct from zero.** A coverage below
  `MIN_REQUIRED_COMPONENT_COVERAGE` remains a coverage value; it is never
  collapsed into `0.0` or a valid metric value of zero (SRS §7.5).
- **Missing is not zero.** An unusable date reduces `u_recent_h` and coverage and
  is never a zero in the recent-share numerator; a failed page is never a
  zero-asset breadth reading (map lines 214, 218).
- **Map checksum.** The `usable_*_sample_count` values Chunk 7B returns must
  agree with the finalized `u_*_h` in `stratum_statistics_json` (Chunk 10 gate,
  dependency map lines 762–763).
- The chunk is deterministic: identical inputs and constants produce equal
  results, no clock, no randomness (LREQ-ARCH-030).

## 9. Test plan

### 9.1 Test files

- `tests/test_metrics.py` (new) — the Chunk 7B analytical tests. Every test
  carries `@pytest.mark.lreq(...)` per §9.3.
- `tests/fixtures/metric_estimator_fixtures.py` (new) — inert constants and
  builders only; no assertions, no logic under test.
- `tests/fixtures/__init__.py` (modified) — add the module to the imports and
  `__all__`.

### 9.2 Golden vectors and fixtures (hand-computed from the SRS formulas)

All vectors use `CUTOFF_UTC = datetime(2025, 1, 31, 0, 0, tzinfo=timezone.utc)`.
Floats are asserted within `1e-9`.

- **Weighted-median vectors** (`weighted_median`):
  - `()` → `None`.
  - `((7.0, 1.0),)` → `7.0`.
  - `((1.0, 1.0), (2.0, 1.0))` → `1.5` (cum `1 == T/2`, next exists).
  - `((1.0, 2.0), (2.0, 2.0))` → `1.5` (same boundary with `N_h/n_h`-style
    integer weights).
  - `((1.0, 1.0), (1.0, 1.0), (2.0, 2.0))` → `1.5` (`T = 4`, cum `1, 2`; exact
    half at the second value `1`, next value `2`).
  - `((1.0, 3.0), (2.0, 3.0), (3.0, 3.0), (4.0, 3.0), (5.0, 3.0), (10.0, 1.0),
    (20.0, 1.0), (30.0, 1.0), (40.0, 1.0), (50.0, 1.0))` → `4.0` (`T = 20`,
    cum `3, 6, 9, 12`; first `>= 10` is `4.0`).
  - `((1.0, 0.0),)` → `None` (zero total weight).
  - `((float("nan"), 1.0),)` and `((1.0, -1.0),)` → `ValueError`.
- **Unequal-stratum demand fixture** (`DEMAND_UNEQUAL_STRATA`, two strata,
  `N_0 = 75`, `n_0 = 25`, `N_1 = 25`, `n_1 = 25`, `N = 100`):
  - Stratum 0: 5 usable indices `[1, 2, 3, 4, 5]` (`mean_0 = 3.0`), 20 unusable
    (`product_page_views = None`); `u_demand_0 = 5`; `w_0 = 0.75`.
  - Stratum 1: 5 usable indices `[10, 20, 30, 40, 50]` (`mean_1 = 30.0`), 20
    unusable; `u_demand_1 = 5`; `w_1 = 0.25`.
  - `DemandPerAssetRaw = (0.75*3.0 + 0.25*30.0) / 1.0 = 9.75`.
  - `DemandMedianRaw = 4.0` (weights `N_h/n_h`: `3.0` and `1.0`; vector above).
  - `demand_stratum_eligibility_coverage = 1.0`;
    `usable_demand_sample_count = 10`.
- **Unequal-stratum recent fixture** (`RECENT_UNEQUAL_STRATA`, `N_0 = N_1 = 50`,
  `n_0 = n_1 = 25`, `N = 100`, `w_0 = w_1 = 0.5`):
  - Stratum 0: usable ages `[100, 200, 300, 400, 500]`, `u_recent_0 = 5`; 3 in the
    inclusive 365-day window → `share_0 = 3/5 = 0.6`.
  - Stratum 1: usable ages `[10, 20, 30, 40, 50]`, `u_recent_1 = 5`; all 5 in the
    window → `share_1 = 1.0`.
  - `RecentShareRaw = (0.5*0.6 + 0.5*1.0) / 1.0 = 0.8`.
  - `MedianAgeRaw`: weights `N_h/n_h = 2.0` each; sorted ages
    `10,20,30,40,50,100,200,300,400,500`, `T = 20`, cum `2,4,6,8,10`; exact half
    `10` at age `50`, next age `100` → `(50 + 100) / 2 = 75.0`.
  - `recent_supply_stratum_eligibility_coverage = 1.0`;
    `usable_recent_supply_sample_count = 10`.
- **Unequal-stratum quality fixture** (`QUALITY_UNEQUAL_STRATA`, `N_0 = N_1 = 50`,
  `n_0 = n_1 = 25`, `N = 100`, `quality_weight_h = 2.0`):
  - Stratum 0: 5 quality-eligible observations, each `rating_average = 2.5`,
    index `10.0` → `num_0 = 2.0 * (5 * (0.5 * 10)) = 50.0`,
    `den_0 = 2.0 * 50.0 = 100.0`.
  - Stratum 1: 5 quality-eligible, each `rating_average = 5.0`, index `10.0` →
    `num_1 = 2.0 * (5 * (1.0 * 10)) = 100.0`, `den_1 = 100.0`.
  - `QualityRaw = (50.0 + 100.0) / (100.0 + 100.0) = 0.75`;
    `quality_stratum_eligibility_coverage = 1.0`;
    `usable_quality_sample_count = 10`.
- **Zero-population fixture** (`ZERO_POPULATION`): `strata = ()`, `N = 0`;
  `DemandPerAssetRaw = DemandMedianRaw = RecentShareRaw = MedianAgeRaw =
  QualityRaw = None`; all three coverages `0.0`; `BreadthMetricInput(0, 0)` →
  `BreadthResult(0, verified_total_count, complete)`.
- **Zero-visibility quality fixture** (`QUALITY_ZERO_VISIBILITY`): 5
  quality-eligible observations with `product_page_views = 0` (index `0.0`),
  one usable stratum → `QualityRaw is None` with
  `METRIC_REASON_ZERO_DENOMINATOR`, while
  `quality_stratum_eligibility_coverage == 1.0` (coverage is not zero).
- **Low-coverage quality fixture** (`QUALITY_LOW_COVERAGE`): two strata, one
  usable; `N_0 = 25, N_1 = 75` → coverage `0.25 < 0.50`; `QualityRaw is None`
  with `METRIC_REASON_INSUFFICIENT_COVERAGE` (Q-3).
- **Contradicted-semantics fixture** (`SEMANTICS_CONTRADICTED`):
  `CategoryMetricInput.page_view_semantics_status = CONTRADICTED`; every
  observation is quality-ineligible through Chunk 7A, so `QualityRaw is None`.
  Reason under the §5.3 precedence order (lead correction 2026-09-20, C-1):
  contradicted makes the observation-level quality-eligible count `0`, so
  `METRIC_REASON_ELIGIBLE_SET_TOO_SMALL` fires before
  `METRIC_REASON_PAGE_VIEW_SEMANTICS_CONTRADICTED`; the 7B test asserts the null
  outcome and that precedence reason. Chunk 7A's own direct-call
  `METRIC_REASON_PAGE_VIEW_SEMANTICS_CONTRADICTED` is covered by
  `tests/test_validation.py`, not here.
- **Breadth vectors**: `(1200, 1180)` → `1200` / `verified_total_count` /
  `complete`; `(None, 250)` → `250` / `distinct_canonical_discovered_count` /
  `incomplete_estimate`; `(0, 0)` → `0` / `verified_total_count` / `complete`.

Additional boundary fixtures the §9.3 nodes reference (all hand-derived in the
same style; `N_0`/`N_1` are `N_h`, `n_0`/`n_1` are `n_h`):

- `DEMAND_NO_USABLE_STRATUM`: `N_0 = 75, N_1 = 25`, `n_0 = n_1 = 4`, each with 4
  usable indices (`u_demand_h = 4 < 5`) → both raw demand values null
  (`no_usable_stratum` for the mean; the median still has a usable weighted
  sample: weights `18.75`×4 and `6.25`×4, `T = 100`, half `50`, cumulative
  `18.75, 37.5, 56.25` → `3.0`); coverage `0.0`.
- `DEMAND_NO_USABLE_INDEX`: one stratum `N_h = 75, n_h = 5`, all `None` views →
  `DemandPerAssetRaw` `None`, `DemandMedianRaw` `None` with
  `empty_usable_sample`, coverage `0.0`.
- `DEMAND_MEDIAN_EXACT_HALF`: two strata `N_0 = N_1 = 25`, `n_0 = n_1 = 5`
  (weight `1.0`), indices `1..5` and `6..10`; `T = 10`, half `5`, exact half at
  value `5.0`, next `6.0` → `5.5`.
- `DEMAND_PARTIAL_COVERAGE`: stratum 0 usable (`u_0 = 5`, `w_0 = 0.75`, mean
  `3.0`), stratum 1 `u_1 = 4` not usable (`w_1` excluded) → coverage `0.75`,
  `DemandPerAssetRaw = 3.0`; median over the 9 usable observations with weights
  `3.0`/`1.0`, `T = 19`, half `9.5` → `4.0`.
- `DEMAND_INELIGIBLE_EXCLUDED`: one stratum `N_h = 75, n_h = 10`; 5 usable
  indices (`[1,2,3,4,5]`, mean `3.0`) and 5 Chunk-7A-ineligible observations
  (negative views, `None` views, draft state, age `29 < MIN_AGE_DAYS_FOR_RATE`,
  identity mismatch) → `DemandPerAssetRaw = 3.0`, never `15/10 = 1.5`.
- `RECENT_USABILITY_BOUNDARY`: `N_0 = N_1 = 50`, `n_0 = n_1 = 25`; stratum 0
  `u_recent_0 = 4` not usable, stratum 1 `u_recent_1 = 5` all in window →
  `RecentShareRaw = 1.0`, coverage `0.5`, `usable_recent_supply_sample_count = 5`;
  `MedianAgeRaw` over all usable dated observations (weight `2.0`), `T = 18`,
  half `9` → `30.0`.
- `RECENT_MISSING_DATES`: one stratum `N_h = 50, n_h = 25`, 5 usable dates
  (ages `10, 20, 400, 500, 600`) and 20 missing; share `= 2/5 = 0.4` (never
  `2/25`), coverage `1.0`; `MedianAgeRaw` weights `2.0`, `T = 10`, half `5` →
  `400.0`.
- `QUALITY_ELIGIBLE_SET_TOO_SMALL`: one stratum `N_h = 75, n_h = 4`, all 4
  quality-eligible → total `4 < QUALITY_MIN_ELIGIBLE_ASSETS (5)` → `QualityRaw`
  null with `eligible_set_too_small` (precedes `no_usable_stratum`).

Expected values are computed from the SRS formulas in this plan's §9.2 comments,
never copied from the implementation.

### 9.3 Test list, mapped to LREQ IDs

| Node (base pytest node ID) | Purpose | LREQ ID(s) |
|---|---|---|
| `test_stratum_expansion_weight_is_population_over_sample` | `N_h/n_h` values and the two distinct weight kinds | LREQ-MET-050, LREQ-MET-100 |
| `test_stratum_expansion_weight_rejects_bool_zero_and_negative` | `ValueError` on a caller breach, never a fabricated weight | LREQ-MET-050 |
| `test_weighted_median_empty_and_all_zero_weight_return_none` | Empty / zero-total-weight → `None` | LREQ-MET-050 |
| `test_weighted_median_single_value_and_first_at_or_above_half` | Single value; `9`-vector → `4.0` | LREQ-MET-050 |
| `test_weighted_median_exact_half_averages_with_next` | Exact-half boundary vectors → `1.5` | LREQ-MET-050 |
| `test_weighted_median_retains_ties_and_rejects_non_finite` | Tie vector; `nan`/negative weight → `ValueError` | LREQ-MET-050 |
| `test_demand_per_asset_uses_population_weighted_means` | `DEMAND_UNEQUAL_STRATA` → `9.75` | LREQ-MET-030 |
| `test_demand_per_asset_null_when_no_usable_stratum` | `u_h < 5` for every stratum → `None` | LREQ-MET-030 |
| `test_demand_per_asset_zero_population_is_null_and_never_divides` | `N = 0` → `None`; no `N_h/N` evaluation | LREQ-MET-030 |
| `test_demand_median_uses_stratum_expansion_weights` | `DEMAND_UNEQUAL_STRATA` → `4.0` | LREQ-MET-050 |
| `test_demand_median_exact_half_boundary` | Exact-half median of usable indices | LREQ-MET-050 |
| `test_demand_median_null_when_no_usable_index` | No usable index → `empty_usable_sample` | LREQ-MET-050 |
| `test_demand_coverage_sums_usable_stratum_weights` | `DEMAND_UNEQUAL_STRATA` → `1.0`; partial coverage case | LREQ-MET-060 |
| `test_demand_coverage_is_zero_for_zero_population` | `N = 0` → `0.0` | LREQ-MET-060 |
| `test_demand_coverage_is_distinct_from_sample_fraction` | Coverage ≠ `enriched/discovered` on the fixture | LREQ-MET-060, LREQ-MET-030 |
| `test_breadth_uses_verified_total_count` | `(1200, 1180)` → `1200` / `verified_total_count` / `complete` | LREQ-MET-070 |
| `test_breadth_falls_back_to_distinct_canonical_count` | `(None, 250)` → `250` / `distinct_canonical_discovered_count` / `incomplete_estimate` | LREQ-MET-070 |
| `test_breadth_verified_zero_result_is_zero` | `(0, 0)` → `0` / `verified_total_count` / `complete` | LREQ-MET-070 |
| `test_recent_share_uses_inclusive_window_per_stratum` | `RECENT_UNEQUAL_STRATA` → `0.8`; ages exactly `365.0` in window | LREQ-MET-080 |
| `test_recent_share_missing_dates_reduce_coverage_not_zero` | Unusable dates shrink `u_recent_h`, never the numerator | LREQ-MET-080 |
| `test_recent_supply_usability_minimum_boundary` | `u_recent_h = 4` unusable, `5` usable | LREQ-MET-080, LREQ-MET-030 |
| `test_recent_supply_coverage_and_usable_count` | Coverage `1.0`; `usable_recent_supply_sample_count = 10` | LREQ-MET-080 |
| `test_median_age_uses_stratum_expansion_weights` | `RECENT_UNEQUAL_STRATA` weights `2.0` | LREQ-MET-080 |
| `test_median_age_exact_half_boundary` | `MEDIAN_AGE = 75.0` (exact-half at age `50`) | LREQ-MET-080, LREQ-MET-050 |
| `test_recent_zero_population_is_null_and_coverage_zero` | `N = 0` → both null, coverage `0.0` | LREQ-MET-080 |
| `test_quality_raw_uses_n_h_over_n_h_weights` | `QUALITY_UNEQUAL_STRATA` → `0.75` | LREQ-MET-100 |
| `test_quality_raw_zero_visibility_denominator_is_null` | All indices `0.0` → `None` / `zero_denominator`, coverage `1.0` | LREQ-MET-100 |
| `test_quality_eligible_set_too_small_is_null` | Total eligible `< QUALITY_MIN_ELIGIBLE_ASSETS` → `None` | LREQ-MET-090 |
| `test_quality_raw_null_below_required_coverage` | Coverage `0.25 < 0.50` → `None` / `insufficient_coverage` | LREQ-MET-090 |
| `test_quality_raw_contradicted_semantics_is_null` | `SEMANTICS_CONTRADICTED` → `None` / `eligible_set_too_small` per the §5.3 precedence and plan §9.2 (lead correction 2026-09-20, C-1) | LREQ-MET-090 |
| `test_quality_coverage_not_renormalized` | Coverage is `Σ N_h/N`, not a count fraction | LREQ-MET-090 |
| `test_quality_zero_population_is_null_and_coverage_zero` | `N = 0` → `None`, coverage `0.0` | LREQ-MET-100 |
| `test_compute_raw_metric_bundle_maps_all_six_values` | Bundle fields and `None` breadth | LREQ-MET-030, LREQ-MET-050, LREQ-MET-060, LREQ-MET-070, LREQ-MET-080, LREQ-MET-100 |
| `test_compute_category_raw_metrics_reports_coverages_and_counts` | Coverage/count/breadth provenance in one value | LREQ-MET-060, LREQ-MET-080, LREQ-MET-090, LREQ-MET-070 |
| `test_zero_population_bundle_has_null_raws_and_zero_coverages` | `ZERO_POPULATION` end-to-end | LREQ-MET-030, LREQ-MET-060, LREQ-MET-080, LREQ-MET-100 |
| `test_estimators_consume_chunk_7a_index_eligibility` | Negative page views / `state_excluded` / age below minimum are excluded from demand, never zero | LREQ-MET-040, LREQ-MET-030, LREQ-MET-080, LREQ-MET-100 |
| `test_estimators_raise_valueerror_only_for_caller_contract` | `len(observations) != n_h`, duplicate/negative stratum, bad thresholds | LREQ-MET-030 |
| `test_estimators_are_pure_no_forbidden_imports_or_clock` | AST check on `metrics.py` (forbidden imports, clock reads) | LREQ-ARCH-010, LREQ-ARCH-020 |
| `test_estimators_repeat_deterministically` | Repeated identical calls are equal | LREQ-ARCH-030 |
| `test_quality_raw_ineligible_observations_are_excluded` | A stratum whose eligible observations are replaced by Chunk-7A-ineligible ones drops out of the coverage and count (lead addition 2026-09-20) | LREQ-MET-090 |

`test_estimators_are_pure_no_forbidden_imports_or_clock` reuses the existing
`check_import_boundaries` helpers (`FORBIDDEN_MODULES`, `check_module`,
`clock_violations`) already imported by `tests/test_validation.py`, mirroring the
Chunk 7A purity test; it carries the `LREQ-ARCH-010` and `LREQ-ARCH-020` markers
and is therefore mapped in `tests/traceability.json`.

### 9.4 `tests/traceability.json` entries to add

Add exactly one entry per node in §9.3, mapping the fully qualified node ID to the
array of the marker(s) on that node, e.g.:

```json
{
  "tests/test_metrics.py::test_demand_per_asset_uses_population_weighted_means": ["LREQ-MET-030"],
  "tests/test_metrics.py::test_median_age_exact_half_boundary": ["LREQ-MET-080", "LREQ-MET-050"],
  "tests/test_metrics.py::test_estimators_are_pure_no_forbidden_imports_or_clock": ["LREQ-ARCH-010", "LREQ-ARCH-020"],
  "tests/test_metrics.py::test_estimators_repeat_deterministically": ["LREQ-ARCH-030"]
}
```

No `LREQ-TST-*` marker is attached and no `LREQ-TST-*` entry is added (Chunk 13
owns those). Existing entries are append-only-preserved.

## 10. Definition of done (gate)

Copied **verbatim** from the dependency map's Chunk 7B Gate section
(`Documents/requirements-dependency-map.md`, lines 837–844):

- All estimators are pure and use the Chunk 7A eligibility results.
- Raw estimators are implemented in `metrics.py`; `scoring.py` does not own raw metric calculation.
- Weighted medians use the exact boundary rule.
- Quality uses `N_h / n_h`, not a simple sample average.
- Zero-population metrics are null where specified and coverage is zero where specified.
- Sample fraction remains distinct from stratum eligibility coverage.

## 11. Explicit prohibitions

- `metrics.py` SHALL NOT import `collector`, `collector_coveo`,
  `collector_graphql`, `database`, `pipeline`, `report`, `cli`, `config`,
  `scoring`, or any filesystem, process, network, or clock module, and SHALL NOT
  import `json` (LREQ-ARCH-010).
- `metrics.py` SHALL NOT read the system clock and SHALL NOT use `random`,
  `secrets`, `uuid`, or any unseeded or platform-dependent hash
  (LREQ-ARCH-020). `scoring_cutoff_utc` is always an explicit input.
- No estimator SHALL have a default-`0` parameter, use `or 0`/`.get(k, 0)`, or
  otherwise convert a missing/invalid/unavailable value to `0`/`0.0`.
- No estimator SHALL re-derive Chunk 1's structural validation, Chunk 5's
  per-operation page-view acceptance, Chunk 3's `totalCount` verification, or
  Chunk 7A's per-observation eligibility; it consumes their results.
- No estimator SHALL evaluate `N_h / N` when `N == 0`, or `N_h / n_h` when
  `n_h == 0`.
- This chunk SHALL NOT implement normalization, `P_ref`, components, the
  composite score, evidence, rankability, or sensitivity; those are Chunks 8/9A/9B.
- This chunk SHALL NOT implement contradicted page-view-semantics **detection**;
  the status is consumed as an explicit input (Q-1).
- This chunk SHALL NOT edit `models.py`, `validation.py`, `sampling.py`,
  `scoring.py`, `config.py`, `database.py`, the collector modules,
  `src/niche_scout/tools/check_import_boundaries.py`, or any interface document.
- This chunk SHALL NOT create `tests/golden_vectors/` (vectors live in
  `tests/fixtures/metric_estimator_fixtures.py`).
- This chunk SHALL NOT add any out-of-scope capability (scheduling,
  resume/checkpoint, historical trends, run comparison, configurable weights,
  confidence intervals, sales calibration).

## 12. Resolved questions, recommendations, and assumptions

**Q-1 — RESOLVED (option (a), operator ruling 2026-09-20): Chunk 7B consumes the
run-level `PageViewSemanticsStatus`; it does not detect `contradicted`.**
`Documents/interfaces/chunk-05.md` §5.8 and `Documents/interfaces/chunk-7A.md`
§5 both state that "Chunk 7B detects `contradicted`". That wording is reconciled
by scope precedence: no detection rule exists in `Documents/SRS-lean.md`
(LREQ-MET-040 lists four usability clauses and no cross-run monotonicity
condition; §6.5 defines the status but names no trigger), the Chunk 5 plan
records O-1 CLOSED with the rule "deliberately unspecified", and the
dependency-map Chunk 7B scope list (lines 806–844) omits detection while
assigning contradicted handling to Chunk 8 (LREQ-SCR-050 and the Chunk 8 outline
bullet "contradicted page-view handling"). Under `.kilo/project-rules.md` §1 the
dependency-map scope governs, so the detection obligation is **out of the
lean-build scope**. Consequences applied in §5: 7B always receives a **non-null**
enum member (`UNVALIDATED`, `VALIDATED_CUMULATIVE`, or `CONTRADICTED`) and
**consumes** it — `QualityRaw` is null when it is `CONTRADICTED` — and **no
detection function is added**. §11's prohibition stands.

**Q-2 — RESOLVED (option (a), operator ruling 2026-09-20): every usable
observation contributes to `DemandMedianRaw` / `MedianAgeRaw` with weight
`N_h / n_h`, regardless of the stratum minimum.**
SRS-backed: LREQ-MET-050 and LREQ-MET-080 name per-observation weighting ("Each
usable observation in stratum `h` receives weight `N_h / n_h`" / "Each usable
dated observation receives expansion weight `N_h / n_h` for `MedianAgeRaw`") and
make the median null "when the usable weighted sample is empty"; the
stratum-minimum language attaches to Recent-Supply renormalization/coverage, not
to the medians. Appendix A's "weighted median of usable values" agrees.
Documented observation (unchanged): the SRS's "when the boundary value is the
final sorted value" branch is defensive and unreachable for a positive total
weight (the final cumulative weight is `T`, and `T == T/2` only when `T == 0`),
so the plan implements it as the last-value fallback without a reachable fixture.

**Q-3 — RESOLVED (option (a), operator ruling 2026-09-20): `QualityRaw` itself is
null below `MIN_REQUIRED_COMPONENT_COVERAGE`; Demand and Recent raw values are
not nulled.**
SRS-backed: LREQ-MET-090 says "Quality SHALL also be unavailable when weighted
usable coverage is below `MIN_REQUIRED_COMPONENT_COVERAGE`", whereas the parallel
sentence says "the affected **component** SHALL be unavailable for rankability"
for Demand and Recent Supply. So `QualityRaw` is null with
`METRIC_REASON_INSUFFICIENT_COVERAGE` when
`quality_stratum_eligibility_coverage < min_required_component_coverage`, and
`DemandPerAssetRaw` / `DemandMedianRaw` / `RecentShareRaw` / `MedianAgeRaw` remain
computed and return their coverage values; their rankability effect is Chunks
8/9A. Supported by the dependency map's LREQ-MET-100 edge case "insufficient
coverage".

**Q-4 — RESOLVED (option (a), operator ruling 2026-09-20): `BreadthRaw` is always
a total count and is never null.**
SRS-backed: LREQ-MET-070 names only two sources (verified `totalCount`, else the
distinct canonical discovered count) and makes a verified zero-result category
`0`; the sentence "Competition is unavailable when filtering is unverified, a
material page failed, identity incompleteness makes breadth an unbounded lower
bound, or the fallback breadth cannot be bounded" has **Competition** as its
subject. `BreadthRaw` is therefore `verified_total_count` when supplied and the
distinct canonical discovered count otherwise (possibly `0`), with
`breadth_source` / `breadth_completeness_status`; `Competition` availability is
Chunk 8's LREQ-SCR-020 decision from `discovery_status` / `breadth_source` /
completeness.

**Q-5 — RECOMMENDATION (operator ruling 2026-09-20): the §5.4
`MetricResult.eligible_population_count` semantics are a non-normative
plan-design recommendation.** The frozen `MetricResult` requires the field, but
the SRS names only the `usable_*_sample_count` fields (SRS §6.5), not
`eligible_population_count`. §5.4's per-estimator definitions are independent of
`.value` and `.eligibility_coverage`; Chunk 8 and Chunk 10 may challenge them.

**Q-6 — RECOMMENDATION (operator ruling 2026-09-20): the §5.1 aggregate reason
spelling is module-local.** As in Chunk 7A, the SRS names no machine-readable
aggregate reason string; the spelling is a recommendation, while the outcome
categories ("null when no stratum …", "null when the eligible set is too small",
"denominator is zero", "coverage below the threshold") are SRS-backed.

**C-1 — SRS-internal tension, RESOLVED as a RECOMMENDATION (operator ruling
2026-09-20).** `SRS-lean.md` §6.5 says a `contradicted` run-level status makes the
components **D and Q** unavailable, while LREQ-MET-090 / LREQ-MET-100 require
`QualityRaw` **itself** to be null when page-view semantics are contradicted. 7B
implements the **stricter** reading: `QualityRaw` is null when the consumed status
is `CONTRADICTED`, which is consistent with both requirements. The quality-raw
reason precedence in §5.3 (zero-population → eligible-set-too-small →
no-usable-stratum → insufficient-coverage → zero-denominator → contradicted) is a
documented RECOMMENDATION; it is not reordered by this ruling.