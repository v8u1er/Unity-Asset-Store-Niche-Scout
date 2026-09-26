# Chunk 7B — Sample-aware raw estimators (public interface)

Status: VERIFIED
Source: `Documents/plans/chunk-7B-sample-aware-raw-estimators.md` §5
(`Status: FROZEN`, operator-adjudicated 2026-09-20), reproduced as the frozen public
contract. Implementation: `src/niche_scout/metrics.py` (additive surface;
`MetricInput`, `MetricResult`, `RawMetricBundle`, and all Chunk 7A names are
unchanged from Chunk 0/7A).

## 1. Module and boundary rules

| Item | Kind | Rule |
|---|---|---|
| `src/niche_scout/metrics.py` | **Pure** | Sample-aware raw estimators, stratum expansion weights, component coverage, and the shared weighted median only. No I/O, no clock, no randomness, no `sqlite3`, no `json`, no package I/O module import. |

- `metrics.py` imports `math` (`isfinite` only), `collections.abc` (`Sequence`),
  `dataclasses` (`dataclass`), `datetime` (`datetime`, `timezone`), plus `models`
  and `validation` (`src/niche_scout/metrics.py:17–35`, read). It does not import
  `collector`, `collector_coveo`, `collector_graphql`, `database`, `pipeline`,
  `report`, `cli`, `config`, or `scoring` (LREQ-ARCH-010). Verified by
  `python -m niche_scout.tools.check_import_boundaries` → exit 0.
- Every estimator is deterministic: weights are summed in tuple order; the
  weighted median sorts by `(value, insertion index)` so ties are stable and no
  set/dict iteration affects the result (LREQ-ARCH-030).
- Null, explicit valid zero, invalid/unavailable, and low coverage stay distinct.
  A `None` input never becomes `0`/`0.0`.
- `scoring_cutoff_utc` is always an explicit parameter (delegated to Chunk 7A).
- `ValueError` is raised only for caller/policy parameters or inconsistent typed
  inputs, never for a product-level value.
- No `WarningCode` is emitted and no warning is persisted.

## 2. Aggregate reason vocabulary (module-local)

**The string spelling is a RECOMMENDATION (not SRS-backed).** The outcome
categories are required by SRS §7.2/§7.4/§7.5. `METRIC_AGGREGATE_UNAVAILABLE_REASONS`
is the closed tuple; `METRIC_REASON_ZERO_POPULATION` is used only when `N == 0`.

| Constant | Value |
|---|---|
| `METRIC_REASON_NO_USABLE_STRATUM` | `"no_usable_stratum"` |
| `METRIC_REASON_ZERO_POPULATION` | `"zero_population"` |
| `METRIC_REASON_EMPTY_USABLE_SAMPLE` | `"empty_usable_sample"` |
| `METRIC_REASON_ELIGIBLE_SET_TOO_SMALL` | `"eligible_set_too_small"` |
| `METRIC_REASON_ZERO_DENOMINATOR` | `"zero_denominator"` |
| `METRIC_REASON_INSUFFICIENT_COVERAGE` | `"insufficient_coverage"` |

## 3. Typed inputs and results

```python
@dataclass(frozen=True, slots=True)
class MetricObservation:
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
    stratum_index: int
    discovered_population_count: int   # N_h
    sampled_population_count: int      # n_h; must equal len(observations)
    observations: tuple[MetricObservation, ...]

@dataclass(frozen=True, slots=True)
class CategoryMetricInput:
    category: str
    scoring_cutoff_utc: datetime
    page_view_semantics_status: PageViewSemanticsStatus
    strata: tuple[StratumMetricInput, ...]
    min_usable_samples_per_stratum: int = MIN_USABLE_SAMPLES_PER_STRATUM
    min_age_days_for_rate: int = MIN_AGE_DAYS_FOR_RATE
    recent_window_days: int = RECENT_WINDOW_DAYS
    quality_min_rating_count: int = QUALITY_MIN_RATING_COUNT  # live; forwarded to 7A
    quality_min_eligible_assets: int = QUALITY_MIN_ELIGIBLE_ASSETS
    min_required_component_coverage: float = MIN_REQUIRED_COMPONENT_COVERAGE

@dataclass(frozen=True, slots=True)
class BreadthMetricInput:
    verified_total_count: int | None
    distinct_canonical_discovered_count: int

@dataclass(frozen=True, slots=True)
class BreadthResult:
    breadth_raw: int
    breadth_source: BreadthSource
    breadth_completeness_status: BreadthCompletenessStatus

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

`CategoryMetricInput.quality_min_rating_count` is **live** for Chunk 7B:
`_quality_observation_index` forwards `input.quality_min_rating_count` (and
`input.min_age_days_for_rate`) to Chunk 7A's
`quality_observation_eligibility`, so a caller-supplied override changes the
eligibility verdict and therefore `quality_stratum_eligibility_coverage`,
`quality_raw`, and `usable_quality_sample_count` (LREQ-MET-090). The field
default remains `QUALITY_MIN_RATING_COUNT`.

## 4. Public functions

```python
def stratum_expansion_weight(
    discovered_population_count: int, sampled_population_count: int
) -> float: ...

def weighted_median(
    values_and_weights: Sequence[tuple[float, float]]
) -> float | None: ...

def breadth_raw(breadth_input: BreadthMetricInput) -> BreadthResult: ...

def demand_stratum_eligibility_coverage(input: CategoryMetricInput) -> float: ...

def demand_per_asset_raw(input: CategoryMetricInput) -> MetricResult: ...

def demand_median_raw(input: CategoryMetricInput) -> MetricResult: ...

def recent_supply_stratum_eligibility_coverage(
    input: CategoryMetricInput,
) -> float: ...

def recent_share_raw(input: CategoryMetricInput) -> MetricResult: ...

def median_age_raw(input: CategoryMetricInput) -> MetricResult: ...

def quality_stratum_eligibility_coverage(input: CategoryMetricInput) -> float: ...

def quality_raw(input: CategoryMetricInput) -> MetricResult: ...

def compute_raw_metric_bundle(input: CategoryMetricInput) -> RawMetricBundle: ...

def compute_category_raw_metrics(
    input: CategoryMetricInput, breadth_input: BreadthMetricInput
) -> CategoryRawMetrics: ...
```

### 4.1 Behavior summary

- `stratum_expansion_weight`: `N_h / n_h`; both arguments `int >= 1` (`bool`
  rejected). Used by the medians and both quality sums — **not** the `N_h / N`
  weight used by demand/recent means.
- `weighted_median`: sort ascending by `(value, input index)`; total weight `T`;
  first value whose cumulative weight is `>= T/2`; when the cumulative weight
  equals exactly `T/2` and a next value exists, return the arithmetic mean of the
  two; empty or all-zero-weight → `None`; non-finite value/weight or negative
  weight → `ValueError`.
- `breadth_raw`: `verified_total_count` when supplied → `verified_total_count` /
  `complete`; else `distinct_canonical_discovered_count` / `incomplete_estimate`.
  Never null; a verified zero-result category is `0`.
- `demand_per_asset_raw`: `sum(w_h * mean_h) / sum(w_h)` with `w_h = N_h / N` over
  usable strata; null `zero_population` when `N == 0` (never evaluates `N_h / N`),
  `no_usable_stratum` when `N > 0` and none usable. An explicit `0.0` index is a
  value and counts toward the stratum mean.
- `demand_median_raw` / `median_age_raw`: stratum-expanded weighted median with
  per-observation weight `N_h / n_h` for **every usable observation** (regardless
  of stratum minimum); null `empty_usable_sample` when the usable weighted sample
  is empty, `zero_population` when `N == 0`.
- `recent_share_raw`: `sum(w_h * share_h) / sum(w_h)`, renormalized over usable
  recent strata, with `share_h = count(0 <= age <= recent_window_days) / u_recent_h`
  and the inclusive window; unusable dates reduce `u_recent_h` and never add a zero
  numerator.
- `quality_raw`: `sum(num_h) / sum(den_h)` with
  `num_h = (N_h/n_h) * sum((rating_average_i / 5) * index_i)` and
  `den_h = (N_h/n_h) * sum(index_i)` over quality-usable strata; null in the
  precedence order `zero_population` → `eligible_set_too_small` → `no_usable_stratum`
  → `insufficient_coverage` → `zero_denominator` → `page_view_semantics_contradicted`
  (the reason order is a documented RECOMMENDATION, plan §12 C-1). `rating_count`
  never weights.
- Coverages: `sum(N_h / N)` over strata meeting the applicable usable minimum,
  clamped to `[0, 1]`, `0.0` when `N == 0`, never renormalized to the sampled
  assets, and distinct from `sample_fraction`.
- `compute_raw_metric_bundle`: the six raw values; `breadth_raw` is `None` there.
- `compute_category_raw_metrics`: all six raws, the three coverages, the three
  usable counts, and the breadth provenance. `raw.breadth_raw` is the integral
  breadth stored as `float` to satisfy the frozen `RawMetricBundle` annotation.

### 4.2 `MetricResult` field semantics (plan design; not SRS-derived)

| Estimator | `.value` | `.usable_sample_count` | `.eligible_population_count` | `.eligibility_coverage` |
|---|---|---|---|---|
| `demand_per_asset_raw` | `DemandPerAssetRaw` | `Σ u_demand_h` over usable strata | `Σ N_h` over usable strata | demand coverage |
| `demand_median_raw` | `DemandMedianRaw` | usable index observations | `Σ N_h` over strata with ≥1 usable index | demand coverage |
| `recent_share_raw` | `RecentShareRaw` | `Σ u_recent_h` over usable recent strata | `Σ N_h` over usable recent strata | recent coverage |
| `median_age_raw` | `MedianAgeRaw` | usable age observations | `Σ N_h` over strata with ≥1 usable age | recent coverage |
| `quality_raw` | `QualityRaw` | quality-eligible over quality-usable strata | `Σ N_h` over quality-usable strata | quality coverage |

The SRS names only the `usable_*_sample_count` fields (SRS §6.5), not
`eligible_population_count`; §4.2 is independent of `.value` and
`.eligibility_coverage` and may be challenged by Chunks 8/10.

## 5. What downstream chunks must NOT expect

- No normalization, `P_ref`, components, composite score, evidence grade,
  rankability, or sensitivity — those are Chunks 8/9A/9B.
- No contradicted page-view-semantics **detection**: the run-level status is
  consumed as an explicit input (plan §12 Q-1, option (a)); detection is out of the
  lean-build scope.
- No `WarningCode`, persistence, logging, report text, or CLI.
- No re-derivation of Chunk 1's structural validation, Chunk 3's `totalCount`
  verification, Chunk 5's per-operation page-view acceptance, or Chunk 7A's
  per-observation eligibility.
- No `sample_fraction` computation or return.

## 6. Traceability

41 analytical test nodes in `tests/test_metrics.py`, each with
`@pytest.mark.lreq(...)` and a `tests/traceability.json` entry. Markers attached:
`LREQ-MET-030`, `LREQ-MET-040`, `LREQ-MET-050`, `LREQ-MET-060`, `LREQ-MET-070`,
`LREQ-MET-080`, `LREQ-MET-090`, `LREQ-MET-100`, `LREQ-ARCH-010`, `LREQ-ARCH-020`,
`LREQ-ARCH-030`. No `LREQ-TST-*` marker (Chunk 13 owns those). Fixture data:
`tests/fixtures/metric_estimator_fixtures.py`.
