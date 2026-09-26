# Chunk 7A — Metric eligibility, date, and page-view primitives (public interface)

Status: VERIFIED
Source: `Documents/plans/chunk-7A-metric-eligibility-date-and-page-view-primitives.md`
§5 (`Status: FROZEN`), reproduced as the frozen public contract. Implementation:
`src/niche_scout/metrics.py` (additive surface; `MetricInput`, `MetricResult`, and
`RawMetricBundle` are unchanged from Chunk 0).

## 1. Module and boundary rules

| Item | Kind | Rule |
|---|---|---|
| `src/niche_scout/metrics.py` | **Pure** | Eligibility, timestamp, date/age, page-view index, recent-window, usable-stratum, and quality-eligibility primitives only. No I/O, no clock, no randomness, no `sqlite3`, no `json`, no package I/O module import. |

- `metrics.py` imports `math` (`isfinite` only), `dataclasses`, `datetime`,
  `enum`, `typing`, plus `models` and `validation`. It does not import
  `collector`, `collector_coveo`, `collector_graphql`, `database`, `pipeline`,
  `report`, `cli`, `config`, or `scoring` (LREQ-ARCH-010). Verified by
  `python -m niche_scout.tools.check_import_boundaries` → exit 0
  ("Import boundaries valid for metrics.py, scoring.py").
- `validation.py` was **not** modified and is **not** in `PURE_MODULES`;
  `metrics.py` consumes `annotate_state_eligibility` rather than re-deriving the
  published-state rule.
- All symbols below are additive. No numeric literal is introduced except the
  documented `7` in the page-view index (LREQ-MET-040); thresholds come from the
  frozen `models` constants.

## 2. Reason vocabulary (module-local)

**The string spelling of this vocabulary is a RECOMMENDATION (not SRS-backed).**
The SRS names no machine-readable unavailability reason; the *outcome categories*
are required by LREQ-MET-010 and dependency-map rows for the metric area. The
closed tuple `METRIC_UNAVAILABLE_REASONS` is ordered as declared; every produced
reason is a member. A reason is always paired with an unavailable outcome; an
available outcome carries `unavailable_reason is None`.

| Constant | Value | Produced by |
|---|---|---|
| `METRIC_REASON_NULL` | `"null"` | 7A — a required input is `None` |
| `METRIC_REASON_MALFORMED` | `"malformed"` | **retained, unproduced by this function set** — Chunk 1 owns shape/alias classification |
| `METRIC_REASON_WRONG_TYPE` | `"wrong_type"` | 7A — a product-level value of an unexpected type |
| `METRIC_REASON_INVALID_RANGE` | `"invalid_range"` | 7A — `rating_average` outside `[0, 5]` |
| `METRIC_REASON_FUTURE_DATE` | `"future_date"` | 7A |
| `METRIC_REASON_NAIVE_DATE` | `"naive_date"` | 7A |
| `METRIC_REASON_NEGATIVE` | `"negative"` | 7A — a product-level numeric below `0` |
| `METRIC_REASON_NON_FINITE` | `"non_finite"` | 7A — NaN/Infinity product-level float |
| `METRIC_REASON_STATE_EXCLUDED` | `"state_excluded"` | 7A |
| `METRIC_REASON_STATE_UNKNOWN` | `"state_unknown"` | 7A |
| `METRIC_REASON_IDENTITY_MISMATCH` | `"identity_mismatch"` | 7A |
| `METRIC_REASON_AGE_BELOW_MINIMUM` | `"age_below_minimum"` | 7A |
| `METRIC_REASON_RATING_COUNT_BELOW_MINIMUM` | `"rating_count_below_minimum"` | 7A |
| `METRIC_REASON_OPERATION_UNAVAILABLE` | `"operation_unavailable"` | 7A |
| `METRIC_REASON_PAGE_VIEW_SEMANTICS_CONTRADICTED` | `"page_view_semantics_contradicted"` | 7A |
| `METRIC_REASON_PAGE_VIEWS_UNAVAILABLE` | `"page_views_unavailable"` | 7A |

## 3. Typed result structures

```python
@dataclass(frozen=True, slots=True)
class MetricTimestamp:
    value_utc: datetime | None = None
    unavailable_reason: str | None = None
    @property
    def is_available(self) -> bool: ...

@dataclass(frozen=True, slots=True)
class MetricValue:
    value: float | None = None
    unavailable_reason: str | None = None
    @property
    def is_available(self) -> bool: ...

@dataclass(frozen=True, slots=True)
class MetricEligibility:
    eligible: bool
    unavailable_reason: str | None = None
    @property
    def is_available(self) -> bool: ...
```

- `MetricValue` mirrors the frozen `MetricResult.value: float | None` and
  `MetricResult.unavailable_reason: str | None` null contract: `value is None`
  iff unavailable, and `value == 0.0` is an explicit valid zero. It carries no
  sample/population counts or coverage (those belong to the Chunk 7B
  category-level aggregate).
- Exactly one of `MetricTimestamp.value_utc` / `.unavailable_reason` is set.
  `MetricTimestamp(value_utc=None, unavailable_reason=None)` is never returned.
- `MetricValue(value=None, unavailable_reason=None)` is never returned here.
- `MetricEligibility(eligible=True, unavailable_reason=<non-None>)` is never
  returned.

## 4. Public functions

```python
def normalize_metric_timestamp(value: object) -> MetricTimestamp: ...

def age_days_exact(
    first_published_date_utc: object, *, scoring_cutoff_utc: datetime
) -> MetricValue: ...

def age_normalized_page_view_index(
    product_page_views: object, first_published_date_utc: object, *,
    scoring_cutoff_utc: datetime, state: str | None,
    id_mapping_mismatch: bool,
    min_age_days_for_rate: int = MIN_AGE_DAYS_FOR_RATE,
) -> MetricValue: ...

def metric_state_eligibility(state: str | None) -> MetricEligibility: ...

def is_within_recent_window(
    age_days_exact: float, *, recent_window_days: int = RECENT_WINDOW_DAYS
) -> bool: ...

def stratum_is_usable(
    usable_observation_count: int, *,
    min_usable_samples_per_stratum: int = MIN_USABLE_SAMPLES_PER_STRATUM
) -> bool: ...

def quality_observation_eligibility(
    *, product_detail_status: OperationStatus,
    page_views_status: OperationStatus,
    id_mapping_mismatch: bool, state: str | None,
    rating_average: object, rating_count: object,
    page_view_semantics_status: PageViewSemanticsStatus,
    product_page_views: object, first_published_date_utc: object,
    scoring_cutoff_utc: datetime,
    min_age_days_for_rate: int = MIN_AGE_DAYS_FOR_RATE,
    quality_min_rating_count: int = QUALITY_MIN_RATING_COUNT,
) -> MetricEligibility: ...
```

### 4.1 Classification vs caller-parameter errors

- **Product-level values are classified, never raised.** A `None`, wrong-typed,
  negative, non-finite, future, naive, state-excluded, or identity-mismatched
  value returns an unavailable result with its distinct reason; it is never
  converted to `0`/`0.0` (LREQ-MET-010).
- **`ValueError` is raised only for caller/policy parameters**, never for a
  product-level value: a naive or non-UTC `scoring_cutoff_utc`; a
  `min_age_days_for_rate < 1` (so the index division cannot be by zero); a
  `quality_min_rating_count < 1`; a `recent_window_days` or
  `min_usable_samples_per_stratum` that is not an `int >= 0`; a
  `usable_observation_count` that is a `bool` or negative. Both
  `min_age_days_for_rate` and `quality_min_rating_count` are `int >= 1` with
  `bool` rejected.

### 4.2 Behavior summary

- `normalize_metric_timestamp`: `None` → `null`; naive → `naive_date` (no
  local-time `astimezone`); an aware value in another offset is converted to UTC
  by `models.ensure_utc`; any other object → `wrong_type`.
- `age_days_exact`: `(scoring_cutoff_utc - date).total_seconds() / 86400.0`, exact
  fractional `float64`, **no floor**; `date > cutoff` → `future_date`;
  `date == cutoff` → an available `0.0` (not future); no age threshold applied.
  LREQ-MET-020.
- `age_normalized_page_view_index`: `product_page_views * 7.0 / age_days_exact`,
  usable only when the page-view value is finite and non-negative, the date is a
  valid UTC date no later than the cutoff, `age_days_exact >= min_age_days_for_rate`,
  the identity is matched, and the state is published. An explicit `0` views is
  usable and yields `0.0`. Reason precedence (plan §5.3): page-view classification
  (`page_views_unavailable`, `wrong_type`, `non_finite`, `negative`) → date
  (`null`, `wrong_type`, `naive_date`, `future_date`) → age
  (`age_below_minimum`) → identity (`identity_mismatch`) → state
  (`state_excluded` / `state_unknown`). LREQ-MET-040, LREQ-GQL-060, LREQ-GQL-070.
- `metric_state_eligibility`: delegates to Chunk 1's
  `annotate_state_eligibility` (case-insensitive published comparison);
  `published` → eligible; present non-published → `state_excluded`;
  missing/null/unparsable → `state_unknown`. Both unavailable states stay in
  discovered breadth (Chunk 1's decision). LREQ-GQL-060.
- `is_within_recent_window`: inclusive `0 <= age <= recent_window_days`; a
  non-finite age is `False` and contributes no count. LREQ-MET-080.
- `stratum_is_usable`: inclusive `usable_observation_count >= min`. LREQ-MET-030.
- `quality_observation_eligibility`: the SRS §7.5 conjunction with the reason
  precedence in plan §5.3 (operations → identity → state → rating average →
  rating count → page-view index reason propagation → contradicted semantics).
  `contradicted` is consumed, not detected (Chunk 7B detects it). The
  `min_age_days_for_rate` policy value is forwarded to
  `age_normalized_page_view_index` and `quality_min_rating_count` to the
  rating-count classification (`_classify_rating_count`), so a caller override of
  either governs this per-observation verdict (chunk-21). LREQ-MET-090.

## 5. What downstream chunks must NOT expect

- No category-level aggregate, stratum weight, coverage value, or weighted
  median: those are Chunk 7B over these primitives.
- No raw-estimator or scoring function; `scoring.py` starts at Chunk 8.
- No `WarningCode`, persistence, logging, or report text.
- No re-derivation of Chunk 1's structural shape/type/alias classification or
  Chunk 5's per-operation page-view payload acceptance.
- `METRIC_REASON_MALFORMED` will not be produced by this function set.

## 6. Traceability

37 analytical test nodes in `tests/test_validation.py` (22 pre-existing nodes
untouched), each with `@pytest.mark.lreq(...)` and a `tests/traceability.json`
entry. Markers attached: `LREQ-MET-010`, `LREQ-MET-020`, `LREQ-MET-030`,
`LREQ-MET-040`, `LREQ-MET-080`, `LREQ-MET-090`, `LREQ-GQL-060`, `LREQ-GQL-070`,
`LREQ-ARCH-010`, `LREQ-ARCH-020`. No `LREQ-TST-*` marker (Chunk 13 owns those).
Fixture data: `tests/fixtures/date_eligibility_fixtures.py`.
