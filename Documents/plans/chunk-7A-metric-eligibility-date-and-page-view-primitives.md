# Chunk 7A — Metric eligibility, date, and page-view primitives

Status: FROZEN — human adjudication superseding the earlier brief's
"decision 3" for value-level invalidity: a product-level value that is malformed,
wrong-typed, negative, or non-finite is classified as unavailable with a distinct
reason, never raised away and never converted to `0`. Basis (all opened and read;
quoted in §12 A-4): `SRS-lean.md:655–657` (LREQ-MET-010), dependency map `:211`,
`:214`, and the Chunk 7A gate bullet at `:801`. Locant correction: the brief cited
the gate bullet as "map lines 768–772", but `:768–772` is the chunk's Implement
bullet list; the quoted sentence "Invalid values are excluded rather than converted
to zero." is at `:801` inside the Gate section (`:795–802`), read and verified.
`§9.2` state-vector correction: mixed-case `"Published"` is **eligible**
(Chunk 1's annotation is case-insensitive;
`src/niche_scout/validation.py:1631–1647`), not `state_unknown`. The plan's §9.2
bullet was corrected; the test fixture follows the frozen contract. No edit was
made to `validation.py`.

Amended in place: §1, §2, §5.0, §5.1, §5.2, §5.3, §7, §8, §9.2, §9.3, §11, §12
(A-4 replaced, A-6 added). Each correction is dated and marked; none is a silent
substitution.
Depends on (frozen interfaces required before this plan can be trusted):
  Documents/interfaces/chunk-00.md (Status: VERIFIED) — typed models, frozen
  constants, `MetricInput`/`MetricResult`/`RawMetricBundle`, purity boundary,
  traceability conventions.
  Documents/interfaces/chunk-01.md (Status: VERIFIED) — structural validation
  primitives, `StateEligibilityAnnotation`, and the explicit statement that metric
  eligibility semantics are **Chunk 7A's** (`chunk-01.md:17–22`, `:336–338`).
  Documents/interfaces/chunk-05.md (Status: VERIFIED) — the validated page-view
  scalar type/range contract (`§5.7`), `first_published_date_utc` parsing and
  `first_published_date_issue`, `id_mapping_mismatch`, the per-operation status
  vocabulary, and the explicit "age thresholds and future-date rejection remain
  Chunk 7A's" boundary (`chunk-05.md:472–487`).
Blocks (chunks whose plan/implementation needs this chunk's interface):
  Chunk 7B (Sample-aware raw estimators) — consumes the per-observation
  eligibility, `age_days_exact`, page-view index, recent-window, usable-stratum,
  and quality-eligibility primitives.
  Chunk 10 (Pipeline orchestration) — constructs the typed inputs from persisted
  `EnrichmentObservationRecord`/`SampleMemberRecord` values.

## 1. Goal

Today `src/niche_scout/metrics.py` is a pure stub that defines `MetricInput`,
`MetricResult`, and `RawMetricBundle` but computes nothing. This chunk makes the
**metric-eligibility layer** real: it normalizes a supplied timestamp to UTC,
computes exact fractional age from an explicit `scoring_cutoff_utc`, distinguishes
naive and future dates from a missing date, computes the age-normalized page-view
index (`product_page_views * 7 / age_days_exact`), applies published-state and
identity-mismatch eligibility, evaluates the inclusive recent-window membership,
decides per-stratum usability at the usable-minimum, and decides per-observation
quality eligibility. Every primitive is pure, takes plain inputs (product-level
values are defensively typed as `object` and classified, not trusted), returns a
typed result, never reads the clock, and keeps null, explicit valid zero,
wrong-typed, invalid-range/negative/non-finite, and unavailable distinct: a
product-level value that is malformed, wrong-typed, negative, or non-finite is
unavailable with a distinct reason, never raised away and never converted to `0`
(LREQ-MET-010). It stops at the primitive level: the raw estimators that
aggregate these primitives (`DemandPerAssetRaw`, weighted medians, `BreadthRaw`,
`RecentShareRaw`, `QualityRaw`, coverage, stratum weights) are **Chunk 7B's** and
are not implemented here.

## 2. Scope

### In scope

- UTC normalization of a metric timestamp with explicit rejection of `None`
  (unavailable) and naive datetimes; aware-non-UTC values are converted to UTC, not
  rejected (LREQ-MET-020, via `models.ensure_utc`).
- Exact fractional age: `age_days_exact =
  (scoring_cutoff_utc - first_published_date_utc).total_seconds() / 86400`, as
  `float64`, with no floor (LREQ-MET-020; SRS §7.1; Appendix A).
- Future-date rejection: a date later than `scoring_cutoff_utc` (`age_days_exact <
  0`) is unavailable with a distinct reason; `age_days_exact == 0` is **not**
  future (LREQ-MET-020; decision 4).
- The page-view index for one observation, usable only for a finite non-negative
  page-view value, a valid UTC date no later than cutoff, `age_days_exact >=
  MIN_AGE_DAYS_FOR_RATE`, a matched identity, and `state = "published"`;
  an explicit valid `0` yields index `0.0` and is **not** unavailable
  (LREQ-MET-040, LREQ-GQL-060, LREQ-GQL-070).
- Published-state metric eligibility completion: reuse Chunk 1's
  `annotate_state_eligibility`; `state = "published"` is eligible, a present
  non-published state is `state_excluded`, a missing/null/unparsable state is
  `state_unknown`, and both are excluded from D/R/Q while remaining in discovered
  breadth (LREQ-GQL-060).
- Metric identity-mismatch eligibility completion: `id_mapping_mismatch is True`
  makes the observation unavailable for D/R/Q (LREQ-GQL-070).
- Inclusive recent-window membership `0 <= age_days_exact <= RECENT_WINDOW_DAYS`
  as a pure predicate (LREQ-MET-080).
- Per-stratum usability at `u_h >= MIN_USABLE_SAMPLES_PER_STRATUM` as a pure
  predicate (LREQ-MET-030, LREQ-MET-080, LREQ-MET-090).
- Per-observation quality eligibility: both operations succeeded, identity
  matched, `state = "published"`, `rating_average` finite in `[0, 5]`,
  `rating_count >= QUALITY_MIN_RATING_COUNT`, page-view index usable, and page-view
  semantics not `contradicted` (SRS §7.5, LREQ-MET-090, LREQ-MET-100 boundary).
- Product-level defensive classification: a supplied product-level value of the
  wrong type, or a negative or non-finite product-level number, yields
  `value is None` / `eligible False` with the distinct reason
  `WRONG_TYPE`/`NEGATIVE`/`NON_FINITE`; it is never raised and never converted to
  `0` (LREQ-MET-010; dependency map `:211`, `:214`; gate bullet `:801`).
- The module-local reason vocabulary and the
  null/zero/wrong-type/invalid/unavailable invariant.

### Explicitly out of scope (and who owns it instead)

- **All raw estimators and coverage values.** `DemandPerAssetRaw`,
  `DemandMedianRaw`, weighted medians, `BreadthRaw`, `RecentShareRaw`,
  `MedianAgeRaw`, `QualityRaw`, `demand_stratum_eligibility_coverage`,
  `recent_supply_stratum_eligibility_coverage`, `quality_stratum_eligibility_coverage`,
  and stratum expansion weights `N_h / n_h` are **Chunk 7B** (dependency map §3
  Chunk 7B, lines 806–844). Chunk 7A supplies the per-observation primitives 7B
  aggregates; it does not compute a category-level metric value.
- **The zero-population / no-usable-stratum estimator outcomes.** When `N = 0` or
  no stratum meets the usable minimum, the null-metric / zero-coverage result is
  composed by Chunk 7B from these primitives (SRS §7.2–§7.5). Chunk 7A states the
  invariants (never divide by zero; missing is not zero) and provides
  `stratum_is_usable`; it emits no category aggregate.
- **Chunk 5's per-operation page-view acceptance decision.** Chunk 5's
  `validate_page_views_payload` / `PageViewValue` remains the single implementation
  of the endpoint-side type/range rule (`chunk-05.md` §5.7, `:529–530`), which
  yields `int | None` with `>= 0`. Chunk 7A does not re-derive that decision: it
  does not construct `PageViewValue`, does not assign a `GraphQLFailureClass`, and
  does not restate Chunk 5's acceptance table. What Chunk 7A **does** own, and what
  the earlier "decision 3" reading wrongly removed, is the product-level value
  classification of LREQ-MET-010: a value that reaches a primitive with a wrong
  type, negative, or non-finite is unavailable with
  `WRONG_TYPE`/`NEGATIVE`/`NON_FINITE`, never raised and never `0` (SRS
  `:655–657`; map `:211`, `:214`; gate bullet `:801`). Chunk 7A's remaining
  page-view decisions are `None` → unavailable and explicit `0` → usable index `0`.
- **Un-parsed response shapes and identity-alias agreement.** Shape and alias
  classification is **Chunk 1's** (gate bullet, dependency map `:802`, quoted:
  "Structural malformed-shape/type/alias checks remain owned by Chunk 1; this chunk
  owns the semantic decision about whether a value contributes to a metric."). No
  7A function receives an un-parsed shape, so the `malformed` reason is retained in
  the closed vocabulary but is unproduced by this function set (§12 A-6). Chunk 7A
  still classifies a product-level value's **type** when one reaches it
  (`WRONG_TYPE`) — a value-level decision, not a shape-level one.
- **Contradicted page-view detection.** The run-level
  `page_view_semantics_status = contradicted` is **detected by Chunk 7B** and
  applied by **Chunk 8** (`chunk-05.md:575–602`). Chunk 7A consumes an explicit
  `PageViewSemanticsStatus` input and treats `contradicted` as ineligible; it does
  not detect it.
- **Identity resolution, state annotation, and response parsing.** Chunks 1 and 5
  produce `id_mapping_mismatch`, `state`, `first_published_date_utc`, and
  `page_views`. Chunk 7A consumes them and does not re-resolve or re-annotate.
- **Persistence, orchestration, warnings, and report wording.** Chunks 2/10/11/12.
  This chunk returns typed values and emits no `WarningCode`.
- **Traceability-validator widening.** Chunk 13 (`LREQ-NFR-060`).

## 3. Requirements this chunk must satisfy

Ownership roles are the labels from `Documents/requirements-dependency-map.md`
"Ownership and test traceability matrix" (lines 45–136). Normative text is quoted
from `Documents/SRS-lean.md`.

| LREQ ID | Ownership role here | Normative text (from SRS-lean.md, quoted) | SRS section |
|---|---|---|---|
| LREQ-MET-010 | **Primary implementation chunk** (matrix line 83). Required tests `LREQ-TST-010`, `LREQ-TST-050`. | "A product-level value is usable only when its type, range, state, identity, and timestamp conditions for the relevant metric pass. Null, malformed, future, naive, negative, non-finite, or state-excluded values SHALL be unavailable." | §7.1 |
| LREQ-MET-020 | **Primary implementation chunk** (matrix line 84). Required tests `LREQ-TST-010`, `LREQ-TST-050`. | "All age calculations SHALL use… `age_days_exact = (scoring_cutoff_utc - first_published_date_utc).total_seconds() / 86400`… The floor of age may be used for display only." | §7.1 |
| LREQ-GQL-060 | **Primary implementation chunk** (matrix line 65: primary owner Chunk 7A; supporting Chunks 1/5; completion Chunks 5/7A); this is the "metric-eligibility completion" the map names at line 785. Required tests `LREQ-TST-040`, `LREQ-TST-050`. | "Only `state = "published"` assets are eligible for D, R, and Q. State-excluded and state-unknown assets remain part of discovered breadth." | §4.2 |
| LREQ-GQL-070 | **Completion chunk** (primary owner Chunk 5; completion Chunks 5/7A; matrix line 66); the map names "metric identity-mismatch eligibility completion for LREQ-GQL-070" at line 786. Required tests `LREQ-TST-030`, `LREQ-TST-040`. | "If returned GraphQL identity aliases do not agree with the requested canonical identity, the asset SHALL be marked `id_mapping_mismatch` and excluded from D, R, and Q." | §4.2 |
| LREQ-MET-040 | **Supporting contract chunk** (primary owner Chunk 7B; matrix line 86); the map names "supporting primitives for … LREQ-MET-040" at line 784. | "The page-view index SHALL be: `age_normalized_page_view_index = product_page_views * 7 / age_days_exact`… It is usable only for a finite non-negative page-view value, a valid UTC date no later than cutoff, `age_days_exact >= MIN_AGE_DAYS_FOR_RATE`, and a matched, published identity. An explicit valid page-view value of zero is usable and yields an index of zero." | §7.2 |
| LREQ-MET-030 | **Supporting contract chunk** (primary owner Chunk 7B; matrix line 85). | "It is null when no stratum has at least `MIN_USABLE_SAMPLES_PER_STRATUM` usable observations." / "A stratum is usable for the mean only when `u_h >= MIN_USABLE_SAMPLES_PER_STRATUM`." / "When `N = 0`… the implementation SHALL never evaluate `N_h / N`." | §7.2 |
| LREQ-MET-080 | **Supporting contract chunk** (primary owner Chunk 7B; matrix line 90). | "`stratum_recent_share_h = count(0 <= age_days_exact <= RECENT_WINDOW_DAYS) / dated_asset_count_h`" / "A stratum SHALL be usable for Recent Supply only when its dated usable count meets `MIN_USABLE_SAMPLES_PER_STRATUM`." | §7.4 |
| LREQ-MET-090 | **Supporting contract chunk** (primary owner Chunk 7B; matrix line 91). | "`QUALITY_MIN_RATING_COUNT = 5`, `QUALITY_MIN_ELIGIBLE_ASSETS = 5`" / "Quality is unavailable below the minimum eligible count." | §7.5 |
| LREQ-ARCH-010 | **Chunk-local purity conformance** (primary/completion owner Chunk 0; matrix line 47). `metrics.py` is in this LREQ's module set (matrix line 145). Required tests `LREQ-TST-010`, `LREQ-NFR-040`. | "`metrics` and `scoring` SHALL accept plain typed input structures and return typed result structures. They SHALL not import or call `collector`, `database`, `report`, or `cli` code, and SHALL perform no network or file I/O." | §3.3 |
| LREQ-ARCH-020 | **Chunk-local purity conformance** (primary/completion owner Chunk 0; matrix line 48). Required tests `LREQ-TST-010`, `LREQ-NFR-040`. | "Pure metric and scoring functions SHALL NOT read the system clock. All timestamps SHALL be supplied by the orchestration layer." | §3.3 |
| LREQ-NFR-040 | **Supporting chunk** (primary owner Chunk 0; supporting Chunks 7A, 8; completion Chunk 13; matrix line 124). Required tests `LREQ-TST-010`, `LREQ-NFR-060`. | "Public metric and scoring functions SHALL have type hints and docstrings describing null and edge-case behavior." | §11 |

### Supporting requirements consumed but not owned (no marker attached here)

Per decision 5 (and the `chunk-4A` plan §"marker not attached" / `chunk-05` plan
`§9` precedent), Chunk 7A attaches **no** `LREQ-TST-*` marker. `LREQ-TST-010` and
`LREQ-TST-050` are Chunk 13's requirements (matrix lines 127, 131); Chunk 7A is a
supporting chunk only, and Chunk 13 owns the marker pass.

| LREQ ID | Role here | What this chunk satisfies | SRS section |
|---|---|---|---|
| LREQ-TST-010 | Consumed obligation (primary owner Chunk 13; supporting Chunks 0/7A/7B/8). | Formula tests cover normal, explicit valid zero, missing, invalid, ties, and minimum boundaries — for these primitives: age/time normal/zero/missing/invalid and the rate-threshold and usable-minimum boundaries. Marker deferred to Chunk 13. | §13 |
| LREQ-TST-050 | Consumed obligation (primary owner Chunk 13; supporting Chunks 7A/7B). | Date and metric tests cover UTC normalization, naive dates, exact fractional age, rate-threshold boundaries, future dates, zero page views, and recent-window boundaries. Marker deferred to Chunk 13. | §13 |

## 4. Interface contracts consumed

Copied from the frozen interface files; none is redefined here.

**From Chunk 0 (`niche_scout.models`, interface §3–§4, §7):**

```python
MIN_AGE_DAYS_FOR_RATE: int = 30
RECENT_WINDOW_DAYS: int = 365
MIN_USABLE_SAMPLES_PER_STRATUM: int = 5
QUALITY_MIN_RATING_COUNT: int = 5
QUALITY_MIN_ELIGIBLE_ASSETS: int = 5

class OperationStatus(str, Enum):        # success | error
class PageViewSemanticsStatus(str, Enum):  # unvalidated | validated_cumulative | contradicted

def ensure_utc(value: datetime) -> datetime: ...
# `ensure_utc` (models.py:217–228, quoted): rejects a non-datetime and a naive
# datetime with `ValueError`; converts an aware value in another offset to UTC.

@dataclass(frozen=True, slots=True)
class MetricResult:
    value: float | None
    usable_sample_count: int
    eligible_population_count: int
    eligibility_coverage: float | None
    unavailable_reason: str | None = None
```

Frozen semantics relied on: `MetricResult.value is None` means unavailable and is
never a fabricated `0`/`0.0`; `unavailable_reason` is `None` when the value is
present (`chunk-00.md` §7, §1). `metrics.py` already declares `MetricInput`,
`MetricResult`, and `RawMetricBundle` (`src/niche_scout/metrics.py`); this chunk is
**additive** and does not change those declarations.

**From Chunk 1 (`niche_scout.validation`, interface §3–§4):**

```python
@dataclass(frozen=True, slots=True)
class StateEligibilityAnnotation:
    state_value: str | None
    is_published: bool
    state_excluded: bool        # present but not "published"
    state_unknown: bool         # missing/null/unparsable
    remains_in_discovered_breadth: bool   # always True (annotation only)

def annotate_state_eligibility(state_value: object) -> StateEligibilityAnnotation: ...
```

Frozen semantics relied on: the annotation is not a decision and exposes no D/R/Q
attribute; `remains_in_discovered_breadth` is always `True` (`chunk-01.md` §5).
Chunk 7A **calls** `annotate_state_eligibility` rather than re-implementing the
state rule (decision 1; dependency map line 771 "the metric-eligibility layer over
Chunk 1's structural validation primitives"; line 211). This is a pure→pure
package import and `validation` is not in
`check_import_boundaries.FORBIDDEN_MODULES` (read; `check_import_boundaries.py:20–56`).

**From Chunk 5 (`niche_scout.collector_graphql`, interface §5.6–§5.9):**

```python
ProductDetailFields.first_published_date_utc: datetime | None
ProductDetailFields.first_published_date_issue: str | None
ProductDetailFields.identity_comparison.id_mapping_mismatch: bool
GraphQLOperationResult.status: OperationStatus
EnrichmentObservationDraft.product_page_views: int | None
EnrichmentObservationDraft.product_detail_status: str     # OperationStatus value
EnrichmentObservationDraft.page_views_status: str         # OperationStatus value
```

Frozen semantics relied on: `product_page_views` is `int | None` with `>= 0`
(`chunk-05.md` §5.7); `None` and `0` are different states and `0` is never an error
sentinel (SRS §6.4; `chunk-05.md:695`); a naive/date-only/unparsable date yields
`None` with `first_published_date_issue` set, while "age thresholds and future-date
rejection remain Chunk 7A's" (`chunk-05.md:486–487`). Chunk 7A does not call any
Chunk 5 function.

### 4.1 Input the production caller supplies

Chunk 7A is pure and receives plain inputs; product-level values are defensively
typed as `object` and classified (§5.3) rather than trusted. Chunk 10 builds them
from the persisted `EnrichmentObservationRecord` (`state`, `id_mapping_mismatch`,
`first_published_date_utc`, `product_page_views`, `product_detail_status`,
`page_views_status`, `rating_average`, `rating_count`) plus the run's
`scoring_cutoff_utc` and `page_view_semantics_status`; that read is I/O and stays in
Chunk 10.

## 5. Interface contract this chunk produces

This section becomes `Documents/interfaces/chunk-7A.md` verbatim once frozen.
Everything lives in `src/niche_scout/metrics.py`. All names are **additive**:
nothing in `models.py`, `validation.py`, `sampling.py`, `scoring.py`, `config.py`,
or `database.py` is redefined, shadowed, or modified.

### 5.0 Module and boundary rules

| Item | Kind | Rule |
|---|---|---|
| `src/niche_scout/metrics.py` | **Pure** | Eligibility, timestamp, date/age, page-view index, recent-window, usable-stratum, and quality-eligibility primitives only. No I/O, no clock, no randomness, no `sqlite3`, no `json`, no package I/O module import. |

- `metrics.py` may import `math` (`isfinite` only), `dataclasses`, `datetime`
  (`datetime`/`timezone`/`timedelta` types and UTC offset validation), `enum`,
  `typing`, plus `models` and `validation`. It SHALL NOT import `collector`,
  `collector_coveo`, `collector_graphql`, `database`, `pipeline`, `report`, `cli`,
  `config`, `scoring`, or any filesystem/process/network/clock module, and SHALL
  NOT import `json` (LREQ-ARCH-010; `check_import_boundaries.FORBIDDEN_MODULES`,
  read).
- `validation.py` is **not** modified and is **not** added to
  `PURE_MODULES` (decision 1; `chunk-01.md` §1 blesses `validation.py`'s `json`
  import).
- Determinism: identical typed inputs plus identical constants produce
  structurally and numerically equal results. No set/dict ordering affects output.
- Null, explicit valid zero, wrong-typed, invalid-range/negative/non-finite, and
  unavailable stay distinct. `None` is unavailable and is never converted to
  `0`/`0.0`; an explicit valid `0` (age `0.0`, page views `0`) is usable and is not
  unavailable; a wrong-typed, negative, or non-finite product-level value is
  unavailable with a distinct reason and is never raised away (LREQ-MET-010).
- **`ValueError` boundary (explicit).** A **product-level value** is always
  classified, never raised. `ValueError` is raised **only** for non-product
  caller/policy parameters and contract breaches: a naive or non-UTC
  `scoring_cutoff_utc`; `min_age_days_for_rate < 1`; a negative or non-`int`
  `recent_window_days` or `min_usable_samples_per_stratum`; and a `bool` or
  negative `usable_observation_count`. Nothing in this boundary is a product-level
  value.
- No `WarningCode` is emitted and no warning is persisted.

### 5.1 Reason vocabulary (module-local) — RECOMMENDATION (not SRS-backed)

The SRS does not define machine-readable reason strings for "why a value is
unavailable". Following the adapter-local vocabulary precedent of
`GraphQLFailureClass`/`GraphQLCorrelationDisposition` (`chunk-05.md` §5.2, §5.5),
`metrics.py` defines a closed module-local tuple of reason strings. **The string
spelling of this vocabulary is a RECOMMENDATION (not SRS-backed)** and is the only
not-SRS-backed choice in this chunk (decision 2); the outcome categories themselves
are required by LREQ-MET-010 and map `:211`/`:214` (§12 A-1). No persisted enum is
added and `models.py` is not edited. A reason is always paired with an unavailable
outcome; an available outcome carries `unavailable_reason is None`.

```python
METRIC_REASON_NULL: str = "null"                       # 7A: a required input is None
METRIC_REASON_MALFORMED: str = "malformed"             # retained, currently unproduced: no 7A function receives an un-parsed shape (Chunk 1 owns shape; gate bullet :802)
METRIC_REASON_WRONG_TYPE: str = "wrong_type"           # 7A: a product-level value of an unexpected type
METRIC_REASON_INVALID_RANGE: str = "invalid_range"     # 7A: rating_average outside [0, 5]
METRIC_REASON_FUTURE_DATE: str = "future_date"         # 7A
METRIC_REASON_NAIVE_DATE: str = "naive_date"           # 7A
METRIC_REASON_NEGATIVE: str = "negative"               # 7A: a product-level numeric below 0
METRIC_REASON_NON_FINITE: str = "non_finite"           # 7A: NaN/Infinity product-level float
METRIC_REASON_STATE_EXCLUDED: str = "state_excluded"   # 7A
METRIC_REASON_STATE_UNKNOWN: str = "state_unknown"     # 7A
METRIC_REASON_IDENTITY_MISMATCH: str = "identity_mismatch"  # 7A
METRIC_REASON_AGE_BELOW_MINIMUM: str = "age_below_minimum"  # 7A
METRIC_REASON_RATING_COUNT_BELOW_MINIMUM: str = "rating_count_below_minimum"  # 7A
METRIC_REASON_OPERATION_UNAVAILABLE: str = "operation_unavailable"            # 7A
METRIC_REASON_PAGE_VIEW_SEMANTICS_CONTRADICTED: str = "page_view_semantics_contradicted"  # 7A
METRIC_REASON_PAGE_VIEWS_UNAVAILABLE: str = "page_views_unavailable"          # 7A

METRIC_UNAVAILABLE_REASONS: tuple[str, ...] = (
    METRIC_REASON_NULL, METRIC_REASON_MALFORMED, METRIC_REASON_WRONG_TYPE,
    METRIC_REASON_INVALID_RANGE, METRIC_REASON_FUTURE_DATE,
    METRIC_REASON_NAIVE_DATE, METRIC_REASON_NEGATIVE, METRIC_REASON_NON_FINITE,
    METRIC_REASON_STATE_EXCLUDED, METRIC_REASON_STATE_UNKNOWN,
    METRIC_REASON_IDENTITY_MISMATCH, METRIC_REASON_AGE_BELOW_MINIMUM,
    METRIC_REASON_RATING_COUNT_BELOW_MINIMUM,
    METRIC_REASON_OPERATION_UNAVAILABLE,
    METRIC_REASON_PAGE_VIEW_SEMANTICS_CONTRADICTED,
    METRIC_REASON_PAGE_VIEWS_UNAVAILABLE,
)
```

- `METRIC_REASON_WRONG_TYPE`, `METRIC_REASON_NEGATIVE`, and
  `METRIC_REASON_NON_FINITE` are **produced** by this module for product-level
  values (LREQ-MET-010; SRS `:655–657`; map `:211`, `:214`; gate bullet `:801`).
- `METRIC_REASON_MALFORMED` is **retained but currently unproduced by this
  function set**: no 7A function receives an un-parsed response shape or an alias
  set — Chunk 1 owns shape/alias classification and Chunk 5 owns per-operation
  payload classification (gate bullet, map `:802`) — so nothing in this module can
  observe a "malformed shape". It is deliberately kept in the closed vocabulary
  because a future 7A caller that maps a Chunk 1/5 structural outcome onto a metric
  input may pass it; this plan does **not** claim it is unreachable in general
  (§12 A-6).
- The reason tuple is closed and ordered as declared; every produced reason is a
  member of `METRIC_UNAVAILABLE_REASONS`.

### 5.2 Typed result structures

```python
@dataclass(frozen=True, slots=True)
class MetricTimestamp:
    """A UTC-normalized metric timestamp, or the reason it is unusable.

    `value_utc` is non-`None` iff `unavailable_reason is None`; the three
    unavailable states — `None`, a naive datetime, and a wrong-typed value — are
    reported by three distinct reasons (`null`, `naive_date`, `wrong_type`). An
    aware value in another offset is converted to UTC, never rejected.
    """
    value_utc: datetime | None = None
    unavailable_reason: str | None = None

    @property
    def is_available(self) -> bool:
        """True iff this timestamp is a usable UTC datetime."""


@dataclass(frozen=True, slots=True)
class MetricValue:
    """A single derived metric value, or the reason it is unavailable.

    Field names, types, and the null contract reuse the frozen
    `MetricResult.value: float | None` and `MetricResult.unavailable_reason: str |
    None`: `value is None` iff the value is unavailable, and `value == 0.0` is an
    explicit valid zero, never an unavailable substitute. This is a
    per-observation primitive with no sample/population counts or coverage; the
    category-level `MetricResult` aggregate is assembled by Chunk 7B from these
    values.
    """
    value: float | None = None
    unavailable_reason: str | None = None

    @property
    def is_available(self) -> bool:
        """True iff a finite value is present."""


@dataclass(frozen=True, slots=True)
class MetricEligibility:
    """A per-observation eligibility verdict and, when ineligible, its reason.

    `unavailable_reason` reuses `MetricResult.unavailable_reason`'s contract:
    `None` iff `eligible` is True, else a member of
    `METRIC_UNAVAILABLE_REASONS`. No numeric value is fabricated for an
    eligibility verdict.
    """
    eligible: bool
    unavailable_reason: str | None = None

    @property
    def is_available(self) -> bool:
        """True iff the observation is eligible (no unavailable reason)."""
```

Null/edge-case contract for the result structures:
- `MetricTimestamp(value_utc=None, unavailable_reason=None)` is an invalid state
  and is never returned: exactly one of the two fields is meaningful.
- `MetricValue(value=None, unavailable_reason=None)` is never returned by a
  function in this module.
- An explicit valid `0.0` (`age_days_exact == 0.0`, index `0.0`) is returned as
  `value == 0.0` with `unavailable_reason is None`, never as unavailable.
- `MetricEligibility(eligible=True, unavailable_reason=<non-None>)` is never
  returned.

### 5.3 Public functions

```python
def normalize_metric_timestamp(value: object) -> MetricTimestamp:
    """Normalize a supplied product-level timestamp to timezone-aware UTC.

    Product-level classification (LREQ-MET-010, LREQ-MET-020):

    - ``None`` → ``MetricTimestamp(None, METRIC_REASON_NULL)``.
    - a naive ``datetime`` → ``MetricTimestamp(None, METRIC_REASON_NAIVE_DATE)``:
      ``models.ensure_utc``'s ``ValueError`` is caught and turned into that reason,
      and no local-time ``astimezone`` is applied.
    - an aware ``datetime`` in another offset → converted to UTC with
      ``models.ensure_utc`` and returned available.
    - any other object (a ``str``, ``int``, ``bool``, ``date``, list, …) →
      ``MetricTimestamp(None, METRIC_REASON_WRONG_TYPE)``: a malformed
      product-level value is classified unavailable, never raised away and never
      replaced by a fabricated timestamp.

    No input raises. Pure.
    """


def age_days_exact(
    first_published_date_utc: object, *,
    scoring_cutoff_utc: datetime,
) -> MetricValue:
    """Exact fractional age in days: ``(cutoff - date).total_seconds() / 86400``.

    ``scoring_cutoff_utc`` is a caller/policy parameter, not a product-level value:
    it must be timezone-aware UTC, else ``ValueError`` (mirrors
    ``MetricInput.__post_init__``). ``first_published_date_utc`` is a
    product-level value and is classified, never raised:

    - ``None`` → ``METRIC_REASON_NULL``.
    - a non-``datetime``, non-``None`` object → ``METRIC_REASON_WRONG_TYPE``.
    - a naive ``datetime`` → ``METRIC_REASON_NAIVE_DATE``.
    - a date later than ``scoring_cutoff_utc`` (``age < 0``) →
      ``METRIC_REASON_FUTURE_DATE``.
    - otherwise the exact ``float64`` age is returned, **without floor**; an age
      of exactly ``0.0`` (date == cutoff) is a valid positive-side zero and is
      returned as available, not future.

    No age threshold is applied here (LREQ-MET-010, LREQ-MET-020; SRS §7.1). Pure.
    """


def age_normalized_page_view_index(
    product_page_views: object,
    first_published_date_utc: object, *,
    scoring_cutoff_utc: datetime,
    state: str | None,
    id_mapping_mismatch: bool,
    min_age_days_for_rate: int = MIN_AGE_DAYS_FOR_RATE,
) -> MetricValue:
    """The age-normalized page-view index for one observation (LREQ-MET-040).

    Computed as ``product_page_views * 7.0 / age_days_exact``. The value is usable
    only when the page-view value, a valid UTC date no later than cutoff,
    ``age_days_exact >= min_age_days_for_rate``, a matched identity, and
    ``state == "published"`` all pass; otherwise ``value is None`` with a distinct
    reason. An explicit ``product_page_views == 0`` is usable and yields ``0.0``
    (never unavailable). ``min_age_days_for_rate`` is a caller/policy parameter,
    not a product-level value, and must be ``>= 1``, else ``ValueError``, so the
    division can never be by zero.

    Deterministic reason precedence. Steps 1–5 classify the product-level page-view
    value defensively (LREQ-MET-010; map `:211`, `:214`); steps 6–13 follow the
    conjunct order of the LREQ-MET-040 sentence (page-view value, date, age, then
    "a matched, published identity"), with identity checked before published-state:

    1. ``product_page_views is None`` → ``METRIC_REASON_PAGE_VIEWS_UNAVAILABLE``.
    2. ``product_page_views`` is a ``bool`` → ``METRIC_REASON_WRONG_TYPE``
       (``bool`` is rejected before any numeric test; ``isinstance(True, int)`` is
       ``True`` in Python).
    3. ``product_page_views`` is neither ``int`` nor ``float`` →
       ``METRIC_REASON_WRONG_TYPE`` (e.g. a ``str`` or ``list``).
    4. a non-finite ``float`` (NaN / ±Infinity) → ``METRIC_REASON_NON_FINITE``.
    5. an ``int`` or ``float`` ``< 0`` → ``METRIC_REASON_NEGATIVE``.
    6. ``first_published_date_utc is None`` → ``METRIC_REASON_NULL``.
    7. a non-``datetime``, non-``None`` date → ``METRIC_REASON_WRONG_TYPE``.
    8. naive date → ``METRIC_REASON_NAIVE_DATE``.
    9. date later than cutoff → ``METRIC_REASON_FUTURE_DATE``.
    10. ``age_days_exact < min_age_days_for_rate`` →
        ``METRIC_REASON_AGE_BELOW_MINIMUM`` (this covers ``age_days_exact == 0.0``).
    11. ``id_mapping_mismatch is True`` → ``METRIC_REASON_IDENTITY_MISMATCH``.
    12. state not ``"published"`` → ``METRIC_REASON_STATE_EXCLUDED`` (present,
        non-published) or ``METRIC_REASON_STATE_UNKNOWN`` (missing/null/unparsable),
        via Chunk 1's ``annotate_state_eligibility`` (LREQ-GQL-060/GQL-070). A
        wrong-typed ``state`` is classified by Chunk 1's annotation as
        ``state_unknown``, not re-classified here.
    13. otherwise ``value = product_page_views * 7.0 / age_days_exact``.

    Chunk 5's per-operation acceptance decision (`PageViewValue` /
    `GraphQLFailureClass`, `chunk-05.md` §5.7) is **not** re-derived; steps 1–5 are
    Chunk 7A's product-level value classification required by LREQ-MET-010. A
    page-view ``float`` with zero fractional part (e.g. ``1.0``) is accepted as the
    equal integer value. No input raises. Pure.
    """


def metric_state_eligibility(state: str | None) -> MetricEligibility:
    """Published-state metric eligibility (LREQ-GQL-060).

    Calls Chunk 1's ``annotate_state_eligibility``. ``state == "published"`` →
    eligible; a present non-published state → ``METRIC_REASON_STATE_EXCLUDED``; a
    missing/null/unparsable state → ``METRIC_REASON_STATE_UNKNOWN``. Both
    unavailable states remain in discovered breadth (that decision is Chunk 1's
    annotation and is not changed here). Pure.
    """


def is_within_recent_window(
    age_days_exact: float, *,
    recent_window_days: int = RECENT_WINDOW_DAYS,
) -> bool:
    """Inclusive recent-window membership: ``0 <= age <= recent_window_days``.

    ``recent_window_days`` must be an ``int >= 0``, else ``ValueError``; it is the
    SRS-configurable ``RECENT_WINDOW_DAYS`` (§14), passed explicitly and defaulted
    from ``models``. A non-finite ``age_days_exact`` (NaN/±Infinity) returns
    ``False`` and never contributes a count; ``0.0`` and the exact upper boundary
    are ``True`` (SRS §7.4, LREQ-MET-080). Pure.
    """


def stratum_is_usable(
    usable_observation_count: int, *,
    min_usable_samples_per_stratum: int = MIN_USABLE_SAMPLES_PER_STRATUM,
) -> bool:
    """A stratum is usable iff ``usable_observation_count >= min`` (LREQ-MET-030).

    ``usable_observation_count`` must be an ``int >= 0`` (``bool`` rejected with
    ``ValueError``); ``min_usable_samples_per_stratum`` must be an ``int >= 0``.
    The boundary is inclusive: count ``== min`` is usable. Pure; it computes no
    coverage and no stratum weight.
    """


def quality_observation_eligibility(
    *, product_detail_status: OperationStatus,
    page_views_status: OperationStatus,
    id_mapping_mismatch: bool,
    state: str | None,
    rating_average: object,
    rating_count: object,
    page_view_semantics_status: PageViewSemanticsStatus,
    product_page_views: object,
    first_published_date_utc: object,
    scoring_cutoff_utc: datetime,
) -> MetricEligibility:
    """Per-observation quality eligibility (SRS §7.5, LREQ-MET-090).

    An observation is quality-eligible only when every condition holds; otherwise
    ``eligible is False`` with the first failing reason in the order SRS §7.5
    lists the conditions. Product-level values (``rating_average``,
    ``rating_count``, ``product_page_views``, ``first_published_date_utc``) are
    classified, not raised (LREQ-MET-010):

    1. ``product_detail_status`` or ``page_views_status`` is not
       ``OperationStatus.SUCCESS`` → ``METRIC_REASON_OPERATION_UNAVAILABLE``
       (a persisted ``str`` equal to the enum value compares equal and is
       accepted).
    2. ``id_mapping_mismatch is True`` → ``METRIC_REASON_IDENTITY_MISMATCH``.
    3. state not ``"published"`` → ``METRIC_REASON_STATE_EXCLUDED`` /
       ``METRIC_REASON_STATE_UNKNOWN`` (a wrong-typed ``state`` is
       ``state_unknown`` via Chunk 1's annotation).
    4. ``rating_average``: ``None`` → ``METRIC_REASON_NULL``; a ``bool`` or any
       non-numeric object → ``METRIC_REASON_WRONG_TYPE``; a non-finite ``float``
       → ``METRIC_REASON_NON_FINITE``; outside ``[0, 5]`` →
       ``METRIC_REASON_INVALID_RANGE``.
    5. ``rating_count``: ``None`` → ``METRIC_REASON_NULL``; a ``bool`` or any
       non-integral numeric object → ``METRIC_REASON_WRONG_TYPE`` (a finite
       ``float`` with zero fractional part is accepted as the equal ``int``);
       an integral value ``< 0`` → ``METRIC_REASON_NEGATIVE``;
       ``< QUALITY_MIN_RATING_COUNT`` →
       ``METRIC_REASON_RATING_COUNT_BELOW_MINIMUM``.
    6. the page-view index is unusable (delegated to
       :func:`age_normalized_page_view_index`, whose steps 1–5 classify
       ``product_page_views`` and ``first_published_date_utc`` the same way) →
       that function's reason.
    7. ``page_view_semantics_status is PageViewSemanticsStatus.CONTRADICTED`` →
       ``METRIC_REASON_PAGE_VIEW_SEMANTICS_CONTRADICTED``.
    8. otherwise ``eligible = True``.

    ``rating_count`` is a reliability minimum only and never weights anything
    here. ``contradicted`` is consumed, not detected (Chunk 7B detects it). No
    product-level value raises; only a caller/policy parameter breach does. Pure.
    """
```

Null/edge-case contract (LREQ-NFR-040 style — public functions carry type hints
and docstrings stating null/edge behaviour):
- Every function is pure: no clock, no randomness, no file/network/DB access, no
  mutation of its arguments.
- `None` inputs yield `value is None` / `eligible is False` with a reason; never a
  fabricated `0`.
- An explicit valid zero (`0.0` age, `0` page views) is available, not a reason.
- A **product-level value** of the wrong type, or a negative or non-finite
  product-level number, yields `WRONG_TYPE` / `NEGATIVE` / `NON_FINITE` as an
  unavailable outcome — never a raised exception and never `0`/`0.0`
  (LREQ-MET-010).
- `scoring_cutoff_utc` is always an explicit parameter and must be timezone-aware
  UTC; a naive or non-UTC cutoff raises `ValueError` (LREQ-ARCH-020).
- **`ValueError` is raised only for non-product parameters / caller-contract
  breaches:** the cutoff check above; `min_age_days_for_rate < 1`; a negative or
  non-`int` `recent_window_days` or `min_usable_samples_per_stratum`; and a
  `bool` or negative `usable_observation_count`. No product-level value is in this
  set.
- `min_age_days_for_rate`, `recent_window_days`, and
  `min_usable_samples_per_stratum` default to the frozen `models` constants and
  are explicit parameters only because SRS §14 marks those constants configurable;
  no other numeric literal is introduced.
- Two calls with identical inputs return structurally and numerically equal
  results.
- No function re-classifies an un-parsed response shape or identity-alias
  agreement (Chunk 1), or re-derives Chunk 5's per-operation `PageViewValue` /
  `GraphQLFailureClass` acceptance. It does classify a product-level value's type
  and range when one reaches it (LREQ-MET-010).

## 6. Files touched

| File | New/modified | Purpose |
|---|---|---|
| `src/niche_scout/metrics.py` | modified | Add the pure eligibility/date/page-view primitives and reason vocabulary (§5). `MetricInput`, `MetricResult`, `RawMetricBundle` are unchanged. |
| `tests/test_validation.py` | modified | Append the Chunk 7A analytical tests (§9); existing tests are untouched. |
| `tests/fixtures/date_eligibility_fixtures.py` | new | Date/eligibility golden vectors and builders (§9). Data only; no logic, no assertions. |
| `tests/fixtures/__init__.py` | modified | Add `date_eligibility_fixtures` to the imports and `__all__`. |
| `tests/traceability.json` | modified (append-only) | Add one entry per new node (§9.4); no existing entry edited, removed, or reordered. |

No other file is edited. `models.py`, `validation.py`, `sampling.py`,
`scoring.py`, `config.py`, `database.py`, the collector modules,
`src/niche_scout/tools/check_import_boundaries.py` (no `PURE_MODULES` change),
`tests/fixtures/validation_fixtures.py`, and all interface documents are
untouched.

## 7. Task breakdown

Ordered checklist, each item tagged with the LREQ ID(s) it implements:

- [ ] Import `MIN_AGE_DAYS_FOR_RATE`, `RECENT_WINDOW_DAYS`,
  `MIN_USABLE_SAMPLES_PER_STRATUM`, `QUALITY_MIN_RATING_COUNT`,
  `OperationStatus`, `PageViewSemanticsStatus`, and `ensure_utc` from `models`;
  import `annotate_state_eligibility` from `validation`; import `math.isfinite`.
  Do not re-declare numeric values. (LREQ-ARCH-010)
- [ ] Define the reason constants and `METRIC_UNAVAILABLE_REASONS` (§5.1). (LREQ-MET-010)
- [ ] Define `MetricTimestamp`, `MetricValue`, `MetricEligibility` (§5.2). (§5)
- [ ] Implement `normalize_metric_timestamp`: `None`/naive/aware-offset/UTC cases,
  plus `WRONG_TYPE` for any non-`datetime` object. (LREQ-MET-010, LREQ-MET-020)
- [ ] Implement `age_days_exact`: exact fractional `float64`,
  `None`/wrong-type/naive/future reasons, explicit-zero age valid, no floor.
  (LREQ-MET-010, LREQ-MET-020)
- [ ] Implement `metric_state_eligibility` via Chunk 1's annotation. (LREQ-GQL-060)
- [ ] Implement `age_normalized_page_view_index` with the documented reason
  precedence: product-level classification (`WRONG_TYPE` for `bool`/non-numeric,
  `NON_FINITE`, `NEGATIVE`), `0`-views-usable, `>= min_age` threshold,
  identity/state gates, and the no-divide-by-zero guard. (LREQ-MET-010,
  LREQ-MET-040, LREQ-GQL-060, LREQ-GQL-070)
- [ ] Implement `is_within_recent_window` (inclusive, non-finite → False).
  (LREQ-MET-080)
- [ ] Implement `stratum_is_usable` (inclusive minimum boundary). (LREQ-MET-030)
- [ ] Implement `quality_observation_eligibility` with the SRS §7.5 condition
  order, classifying `rating_average`/`rating_count` (`WRONG_TYPE`, `NON_FINITE`,
  `INVALID_RANGE`, `NEGATIVE`) rather than raising. (LREQ-MET-090, LREQ-MET-010)
- [ ] Confirm no product-level value raises; only the caller/policy parameter
  breaches listed in §5.3 raise `ValueError`. (LREQ-MET-010)
- [ ] Write `tests/fixtures/date_eligibility_fixtures.py` with the vectors in §9.2
  and re-export it from `tests/fixtures/__init__.py`. (§9)
- [ ] Append the tests in §9.3 to `tests/test_validation.py` with the markers in
  §9.3 and add the `tests/traceability.json` entries in §9.4. (§9)
- [ ] Run `python -m pytest tests/test_validation.py -q`, then the full suite, then
  `python -m niche_scout.tools.check_import_boundaries`,
  `python -m niche_scout.tools.validate_traceability`, and `ruff format`/`ruff check`
  over the touched files. (§10)

## 8. Edge cases and invariants

From the dependency map's Edge cases column for every owned LREQ, plus the chunk's
gate text:

- Metric eligibility is semantic, not structural: Chunk 1 owns malformed
  shape/type/alias checks; Chunk 7A owns the decision about whether a value
  contributes to a metric (map line 211, line 802). "Wrong type" is owned by
  Chunk 7A **at the product-value level** (`WRONG_TYPE`); "malformed" is
  shape-level and stays Chunk 1's (`MALFORMED` is retained but unproduced here;
  §12 A-6).
- Null (`null`), malformed (Chunk 1's shape-level outcome; retained but unproduced
  here), wrong type (`wrong_type`),
  invalid range (`invalid_range`), future (`future_date`), naive (`naive_date`),
  negative (`negative`), non-finite (`non_finite`), and state-excluded
  (`state_excluded`/`state_unknown`) are distinct outcomes (map line 211; SRS
  `:655–657`). A product-level value that is wrong-typed, negative, or non-finite
  is **classified** unavailable with its distinct reason — never raised, never
  converted to `0` (gate bullet, map `:801`).
- UTC normalization, naive dates, exact fractional age, and future dates (map line
  212): a date equal to the cutoff gives `age_days_exact == 0.0` — a valid zero,
  not a future date; only `date > cutoff` is future.
- The age threshold is inclusive at the boundary: `age_days_exact == 30.0` passes
  `>= MIN_AGE_DAYS_FOR_RATE`; `age_days_exact == 29.9583…` does not (30 is the SRS
  default, §14).
- Zero page views are valid (map line 214): the index is `0.0`, available, and
  distinct from a failed operation's `None`. `None` page views are never a `0`; a
  negative page view is `NEGATIVE` (map line 214: "negative/non-finite values
  invalid"), a non-finite float is `NON_FINITE`, and a `bool`/non-numeric is
  `WRONG_TYPE` — each unavailable, none a `0`, none an exception.
- The index division cannot divide by zero because the index is only computed when
  `age_days_exact >= MIN_AGE_DAYS_FOR_RATE (30) > 0`; `min_age_days_for_rate < 1`
  is rejected with `ValueError` (a policy-parameter breach, not a product value).
- A product-level value never raises: a wrong-typed date, `bool`/`str` page views,
  a NaN/Infinity rating average, or a wrong-typed rating count is an unavailable
  outcome with its reason. `ValueError` is reserved for the non-product
  caller/policy parameters in §5.0.
- Identity/state mismatch: a mismatched identity or a non-published/unknown state
  is unavailable for D/R/Q but the asset remains in discovered breadth (Chunk 1's
  annotation owns the breadth decision).
- Query-string/format: dates are compared only after UTC normalization; an
  aware-non-UTC date is converted, never rejected.
- Recent-window boundary is inclusive at both ends (map line 218):
  `0.0 <= age <= RECENT_WINDOW_DAYS (365)`; missing/unusable dates do not enter the
  numerator and must never contribute a zero.
- Usable-stratum boundary is inclusive: `u_h == MIN_USABLE_SAMPLES_PER_STRATUM
  (5)` is usable; fewer is not (map lines 213, 218, 219, 220).
- `N = 0` and no-usable-stratum outcomes are composed by Chunk 7B; Chunk 7A never
  evaluates `N_h / N` and never divides by a population.
- Missing is not zero: an empty/missing value yields `value None` / `eligible
  False`, never `0`/`0.0`; an explicit valid zero stays `0`/`0.0` and available.
- The chunk is deterministic: same typed inputs and constants → equal results, no
  clock, no randomness.

## 9. Test plan

### 9.1 Test files

- `tests/test_validation.py` (modified) — append a
  "LREQ-MET-010 / LREQ-MET-020 / LREQ-GQL-060 / LREQ-GQL-070 — Chunk 7A metric
  eligibility, date, and page-view primitives" section. Every analytical test
  carries `@pytest.mark.lreq(...)` per §9.3.
- `tests/fixtures/date_eligibility_fixtures.py` (new) — inert constants and
  builders only: no assertions, no logic under test.
- `tests/fixtures/__init__.py` (modified) — add the module to the imports and
  `__all__`.

> **File-size review note (not a gate).** `tests/test_validation.py` is already
> **1228** lines (counted: `read` of the file reported `(End of file - total 1228
> lines)`), past the ~800–1,000-line review trigger in the project rules. The
> dependency map names this module for the Chunk 7A tests (`chunk-7A` Tests:
> `test_validation.py`, line 792), so this chunk appends rather than splits; per
> the project rules a split is a human/plan decision and SHALL NOT duplicate or
> rename a pytest node ID. The recommended future boundary, if a human chooses to
> split, is by requirement cluster: the Chunk 1 `LREQ-EXT-*`/structural section
> versus the Chunk 7A `LREQ-MET-*`/`LREQ-GQL-06x` metric-eligibility section —
> never a mechanical first-half/second-half cut.

### 9.2 Golden vectors and fixtures (hand-computed where the SRS pins them)

`tests/fixtures/date_eligibility_fixtures.py` provides these values; the test
author freezes the expected numbers and asserts within `1e-9` where a float is
compared.

- `CUTOFF_UTC = datetime(2025, 1, 31, 0, 0, tzinfo=timezone.utc)`.
- `DATE_AT_CUTOFF = datetime(2025, 1, 31, 0, 0, tzinfo=timezone.utc)` → age
  `0.0` (explicit zero, not future).
- `DATE_30D = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)` → age `30.0`.
- `DATE_29D_1H = datetime(2025, 1, 1, 1, 0, tzinfo=timezone.utc)` → age
  `29.958333333333332` (below the default `MIN_AGE_DAYS_FOR_RATE`).
- `DATE_FUTURE = datetime(2025, 2, 1, 0, 0, tzinfo=timezone.utc)` → age `-1.0`
  (future).
- `DATE_OFFSET_30D = datetime(2024, 12, 31, 19, 0, tzinfo=timezone(timedelta(hours=-5)))`
  → normalizes to `2025-01-01T00:00:00Z` → age `30.0` (proves aware-offset
  normalization, not rejection).
- `DATE_NAIVE = datetime(2025, 1, 1, 0, 0)` (no `tzinfo`) → naive.
- `DATE_HALF_DAY = datetime(2025, 1, 30, 12, 0, tzinfo=timezone.utc)` → age `0.5`.
- Index vectors (page views, age, expected index):
  - `(0, age 30.0) → 0.0` (usable explicit zero).
  - `(10, age 30.0) → 2.3333333333333335` (`10 * 7 / 30`).
  - `(7, age 30.0) → 1.6333333333333333`.
  - `(5, age 30.0) → 1.1666666666666667`.
  - `(1.0, age 30.0) → 0.23333333333333334` (a finite float with zero fractional
    part is accepted as the equal integer value).
- **Product-level invalidity vectors (expected reason, never a value, never a
  raise, never `0`):**
  - page views: `-1` → `NEGATIVE`; `True` → `WRONG_TYPE`; `float("nan")` →
    `NON_FINITE`; `float("inf")` → `NON_FINITE`; `"-1"` (a `str`) → `WRONG_TYPE`;
    `[...]` (a `list`) → `WRONG_TYPE`.
  - timestamp: `"2025-01-01"` (a `str`) → `WRONG_TYPE`; `date(2025, 1, 1)` (a
    `date`, not a `datetime`) → `WRONG_TYPE`.
  - date/age: a `str` or `date` `first_published_date_utc` → `WRONG_TYPE` (for
    both `normalize_metric_timestamp`/`age_days_exact` and the index's step 7).
  - quality: `rating_average` `True`/`"2.5"` → `WRONG_TYPE`; `float("nan")` →
    `NON_FINITE`; `-0.1` / `5.1` → `INVALID_RANGE`; `rating_count` `True`/`4.5` →
    `WRONG_TYPE`; `-1` → `NEGATIVE`; `4` → `RATING_COUNT_BELOW_MINIMUM`.
  - each vector asserts `value is None` / `eligible is False`, the exact reason,
    and that the call did not raise.
- Recent-window vectors (floats): `0.0 → True`, `1.0 → True`, `365.0 → True`,
  `365.0000001 → False`, `-0.5 → False`, `inf → False`, `nan → False`.
- Usable-stratum vectors: counts `0,1,2,3,4 → False`, `5,6 → True` at the default
  minimum `5`.
- Quality vectors: `rating_average` `2.5` with `rating_count` `5` and all other
  conditions satisfied → eligible; `rating_average` `None`, `nan`, `-0.1`, `5.1`
  → the corresponding reason; `rating_count` `4` → below-minimum; `rating_count`
  `None` → null.
- State fixtures: `"published"` (eligible), `"draft"` (excluded),
  `"coming-soon"` (excluded), `None` (unknown), and `"Published"` (eligible —
  Chunk 1's frozen annotation compares the state vocabulary **case-insensitively**
  and strips surrounding whitespace; `src/niche_scout/validation.py:1631–1647`
  docstring + `normalized.casefold() == "published"`, opened and read). The test
  asserts against `annotate_state_eligibility` semantics, not a re-derived rule.
  *Correction 2026-09-20:* this bullet previously read "`"Published"` (unknown —
  case-sensitive exact match)", which contradicted the cited Chunk 1 contract. The
  test fixture (`tests/fixtures/date_eligibility_fixtures.py`
  `STATE_MIXED_CASE_PUBLISHED`) follows the frozen contract: mixed case is eligible.
  No edit was made to `validation.py`.

The test author hand-checks each float within `1e-9`; expected values are computed
from the SRS formula, not copied from the implementation.

### 9.3 Test list, mapped to LREQ IDs

| Node (base pytest node ID) | Purpose | LREQ ID(s) |
|---|---|---|
| `test_metric_timestamp_normalizes_aware_offset_to_utc` | Aware-non-UTC → UTC (`DATE_OFFSET_30D`) | LREQ-MET-020 |
| `test_metric_timestamp_rejects_naive_date_with_reason` | Naive → `NAIVE_DATE`, no local astimezone | LREQ-MET-020 |
| `test_metric_timestamp_wrong_type_is_unavailable_not_raised` | A `str`/`date`/`int` → `WRONG_TYPE`, never a fabricated timestamp and never a raise | LREQ-MET-010, LREQ-MET-020 |
| `test_metric_timestamp_null_is_unavailable_never_zero` | `None` → `NULL`, never a fabricated timestamp | LREQ-MET-010, LREQ-MET-020 |
| `test_age_days_exact_uses_fractional_days` | `DATE_30D` → `30.0`; `DATE_HALF_DAY` → `0.5` | LREQ-MET-020 |
| `test_age_days_exact_at_cutoff_is_valid_zero_not_future` | `DATE_AT_CUTOFF` → `0.0`, available | LREQ-MET-010, LREQ-MET-020 |
| `test_age_days_exact_future_date_is_unavailable_distinct_reason` | `DATE_FUTURE` → `FUTURE_DATE` | LREQ-MET-020 |
| `test_age_days_exact_naive_and_null_are_distinct_reasons` | `NAIVE_DATE` vs `NULL` | LREQ-MET-010, LREQ-MET-020 |
| `test_age_days_exact_wrong_type_date_is_unavailable` | A `str`/`date` date → `WRONG_TYPE`, no raise | LREQ-MET-010, LREQ-MET-020 |
| `test_age_days_exact_requires_aware_utc_cutoff` | Naive/non-UTC cutoff → `ValueError` | LREQ-ARCH-020, LREQ-MET-020 |
| `test_page_view_index_uses_seven_over_age_days` | Index literals (10/7/5 views) | LREQ-MET-040 |
| `test_page_view_index_zero_views_is_usable_zero` | `(0, 30) → 0.0`, available | LREQ-MET-040 |
| `test_page_view_index_missing_views_is_unavailable_not_zero` | `None` views → `PAGE_VIEWS_UNAVAILABLE` | LREQ-MET-040, LREQ-MET-010 |
| `test_page_view_index_rejects_bool_negative_and_non_finite` | `True` → `WRONG_TYPE`; `-1` → `NEGATIVE`; `nan`/`inf` → `NON_FINITE`; each unavailable, never `0`, never a raise | LREQ-MET-010, LREQ-MET-040 |
| `test_page_view_index_rejects_non_numeric_views_and_accepts_integral_float` | `"-1"`/`[...]` → `WRONG_TYPE`; `1.0` accepted as integer `1` | LREQ-MET-010, LREQ-MET-040 |
| `test_page_view_index_wrong_type_date_is_unavailable` | A `str`/`date` date → `WRONG_TYPE` (precedence step 7) | LREQ-MET-010, LREQ-MET-040 |
| `test_page_view_index_age_threshold_boundary` | age `30.0` usable; `29.9583…` → `AGE_BELOW_MINIMUM`; age `0.0` → `AGE_BELOW_MINIMUM` | LREQ-MET-040, LREQ-MET-030 |
| `test_page_view_index_never_divides_by_zero_at_threshold` | threshold `>= 1`; no zero-age division; `min_age_days_for_rate < 1` → `ValueError` | LREQ-MET-040, LREQ-MET-030 |
| `test_page_view_index_rejects_state_excluded_and_unknown` | `state_excluded` / `state_unknown` reasons | LREQ-GQL-060, LREQ-MET-040 |
| `test_page_view_index_rejects_identity_mismatch` | `id_mapping_mismatch` → `IDENTITY_MISMATCH` | LREQ-GQL-070, LREQ-MET-040 |
| `test_metric_state_eligibility_published_excluded_unknown` | Published/excluded/unknown verdicts | LREQ-GQL-060 |
| `test_state_excluded_assets_remain_available_for_nothing_but_breadth` | 7A emits no breadth field; remains Chunk 1's annotation | LREQ-GQL-060 |
| `test_identity_mismatch_marks_all_demand_recent_quality_unavailable` | Same exclusion on the index and quality paths | LREQ-GQL-070 |
| `test_within_recent_window_is_inclusive_at_boundaries` | `0.0`, `365.0` True; `365.0000001`, `-0.5` False | LREQ-MET-080 |
| `test_within_recent_window_non_finite_is_false` | `nan`/`inf` → False, never a count | LREQ-MET-080, LREQ-MET-010 |
| `test_recent_window_parameter_validation_raises` | A negative or non-`int` `recent_window_days` → `ValueError` (policy parameter, not a product value) | LREQ-MET-080 |
| `test_stratum_is_usable_at_minimum_boundary` | counts `4` False, `5` True; negative/bool → `ValueError` | LREQ-MET-030 |
| `test_quality_observation_eligibility_combines_conditions` | All conditions satisfied → eligible | LREQ-MET-090 |
| `test_quality_rating_range_and_count_thresholds` | `None`/`nan`/out-of-range average; count `< 5` | LREQ-MET-090 |
| `test_quality_rating_wrong_type_and_negative_are_distinct_reasons` | `rating_average` `True`/`"2.5"` → `WRONG_TYPE`; `rating_count` `4.5`/`True` → `WRONG_TYPE`; `-1` → `NEGATIVE`; no raise | LREQ-MET-090, LREQ-MET-010 |
| `test_quality_eligibility_operation_state_and_semantics_gates` | Operation error, excluded/unknown state, contradicted semantics | LREQ-MET-090, LREQ-MET-010, LREQ-GQL-060 |
| `test_quality_eligibility_propagates_page_view_index_reason` | Unusable index reason is propagated unchanged | LREQ-MET-090, LREQ-MET-040 |
| `test_metric_primitives_are_pure_no_forbidden_imports_or_clock` | AST check: no forbidden import, no clock read in `metrics.py` | LREQ-ARCH-010, LREQ-ARCH-020 |
| `test_metric_primitives_classify_invalid_values_and_never_convert_to_zero` | Every §9.2 product-level invalidity vector yields its reason with `value is None` / `eligible is False`, never `0`, never a raise | LREQ-MET-010 |
| `test_metric_primitives_raise_valueerror_only_for_caller_parameters` | The §5.0 `ValueError` boundary holds; no product-level input raises | LREQ-MET-010, LREQ-ARCH-010 |
| `test_metric_reason_vocabulary_is_closed_and_malformed_is_unproduced` | Tuple closed; `wrong_type`/`negative`/`non_finite` produced; `malformed` retained but unproduced by this function set | LREQ-MET-010 |
| `test_metric_primitives_repeat_deterministically` | Repeated identical calls are equal | LREQ-ARCH-020 |

`test_metric_primitives_are_pure_no_forbidden_imports_or_clock` reuses the existing
`check_import_boundaries` helpers (`FORBIDDEN_MODULES`, `check_module`,
`clock_violations`) already imported by `tests/test_validation.py` (read;
`tests/test_validation.py:32–36`), mirroring the chunk-4A local purity test. It
carries the `LREQ-ARCH-010` and `LREQ-ARCH-020` markers and is therefore mapped in
`tests/traceability.json` (decision 5).

### 9.4 `tests/traceability.json` entries to add

Add exactly one entry per node in §9.3, mapping the fully qualified node ID to the
array of the marker(s) on that node, e.g.:

```json
{
  "tests/test_validation.py::test_age_days_exact_at_cutoff_is_valid_zero_not_future": ["LREQ-MET-010", "LREQ-MET-020"],
  "tests/test_validation.py::test_page_view_index_zero_views_is_usable_zero": ["LREQ-MET-040"],
  "tests/test_validation.py::test_metric_primitives_are_pure_no_forbidden_imports_or_clock": ["LREQ-ARCH-010", "LREQ-ARCH-020"]
}
```

No `LREQ-TST-*` marker is attached and no `LREQ-TST-*` entry is added by Chunk 7A
(decision 5; matrix lines 127, 131 assign those to Chunk 13). Existing entries are
append-only-preserved.

> **Recorded discrepancy (read, not resolved).** `tests/AGENTS.md` describes
> `tests/traceability.json` as "an object keyed by individual `LREQ-*` IDs" whose
> values are arrays of node IDs. The file on disk is the **opposite** shape:
> keyed by fully qualified pytest node ID with an array of `LREQ-*` IDs (read;
> `tests/traceability.json:2–3`), matching `interfaces/chunk-00.md` §8 and every
> plan precedent. This plan follows the file as it exists. The `tests/AGENTS.md`
> sentence is stale and is left for Chunk 13's document-consistency pass; it is not
> edited here (file discipline).

## 10. Definition of done (gate)

Copied **verbatim** from the dependency map's Chunk 7A Gate section
(`Documents/requirements-dependency-map.md`, lines 797–802):

- All primitives are pure and receive `scoring_cutoff_utc` explicitly.
- No metric reads the current time.
- Exact fractional age is used.
- Zero is distinguished from null, invalid, and unavailable.
- Invalid values are excluded rather than converted to zero.
- Structural malformed-shape/type/alias checks remain owned by Chunk 1; this chunk
  owns the semantic decision about whether a value contributes to a metric.

## 11. Explicit prohibitions

- `metrics.py` SHALL NOT import `collector`, `collector_coveo`,
  `collector_graphql`, `database`, `pipeline`, `report`, `cli`, `config`,
  `scoring`, or any filesystem, process, network, or clock module, and SHALL NOT
  import `json` (LREQ-ARCH-010).
- `metrics.py` SHALL NOT read the system clock and SHALL NOT use `random`,
  `secrets`, `uuid`, or any unseeded or platform-dependent hash (LREQ-ARCH-020).
- `metrics.py` SHALL NOT perform persistence, open a SQLite connection, write a
  file, or emit a log line.
- No primitive SHALL have a default-`0` parameter, use `or 0`/`.get(k, 0)`, or
  otherwise convert a missing/invalid/unavailable value to `0`/`0.0`.
- No primitive SHALL re-derive Chunk 5's per-operation page-view acceptance
  decision (`PageViewValue` / `GraphQLFailureClass`, §5.7) or classify an
  un-parsed response shape or identity-alias agreement (Chunk 1). It SHALL,
  however, classify a product-level value that reaches it: a wrong-typed,
  negative, or non-finite product-level value SHALL be unavailable with a distinct
  reason and SHALL NOT raise and SHALL NOT become `0` (LREQ-MET-010). `malformed`
  remains unproduced by this function set because no 7A function receives an
  un-parsed shape (§12 A-6).
- No primitive SHALL raise for a product-level value. `ValueError` is reserved for
  the non-product caller/policy parameters and contract breaches enumerated in
  §5.0.
- No primitive SHALL detect `contradicted` page-view semantics; it consumes an
  explicit `PageViewSemanticsStatus`. Detection is Chunk 7B's.
- This chunk SHALL NOT implement any raw estimator, weighted median, coverage, or
  stratum weight (`N_h / n_h`); those are Chunk 7B.
- This chunk SHALL NOT edit `models.py`, `validation.py`, `sampling.py`,
  `scoring.py`, `config.py`, `database.py`, the collector modules,
  `src/niche_scout/tools/check_import_boundaries.py` (no `PURE_MODULES` change),
  `tests/fixtures/validation_fixtures.py`, or any interface document.
- This chunk SHALL NOT create `tests/golden_vectors/` and SHALL NOT edit
  `tests/test_metrics.py` (Chunk 7B's module).
- This chunk SHALL NOT add any out-of-scope capability (scheduling,
  resume/checkpoint, historical trends, configurable score weights, alternative
  collection strategies, confidence intervals).

## 12. Open questions / assumptions

No blocking open question was found; the five candidate ambiguities were
adjudicated before this plan was written, and the 2026-09-20 product-level
invalidity adjudication supersedes the earlier "decision 3" (see A-4). The
following are recorded as assumptions so a reviewer can challenge them explicitly.

1. **A-1 — the reason *spelling* is a RECOMMENDATION (not SRS-backed).** Decision
   2. The SRS names no machine-readable unavailability reasons; the tuple in §5.1
   is the only not-SRS-backed choice, modelled on the adapter-local
   `GraphQLFailureClass` precedent (`chunk-05.md` §5.2). What is not-SRS-backed is
   the exact string spelling of each reason — including the now-produced
   `wrong_type`, `negative`, and `non_finite`, and the retained-but-unproduced
   `malformed` — **not** the existence of those outcome categories, which
   LREQ-MET-010 and dependency map `:211`/`:214` require.
2. **A-2 — result types mirror `MetricResult`'s `value`/`unavailable_reason`
   fields.** Decision 2 requires reusing `MetricResult.value: float | None` and
   `MetricResult.unavailable_reason: str | None` without adding a persisted enum or
   editing `models.py`. `MetricValue` carries those two fields with the identical
   null contract; `MetricEligibility` carries the same `unavailable_reason`
   contract for boolean verdicts; `MetricTimestamp` carries `value_utc`. The
   category-level frozen `MetricResult` aggregate is assembled by Chunk 7B. If a
   reviewer prefers returning `MetricResult` directly, the counts
   (`usable_sample_count`/`eligible_population_count`/`eligibility_coverage`) have
   no defensible per-observation meaning; the mirror types avoid fabricating them.
3. **A-3 — condition precedence is derived from the requirement sentences.** The
   SRS does not pin a precedence among simultaneous ineligibility causes.
   `age_normalized_page_view_index` uses the conjunct order of the LREQ-MET-040
   sentence (page views → date → age → matched/published identity), and
   `quality_observation_eligibility` uses the condition order of SRS §7.5. This is
   a derivation from those sentences, not a new rule.
4. **A-4 — product-level invalidity is classified, not raised (SRS-backed;
   supersedes the earlier "decision 3").** LREQ-MET-010 (`Documents/SRS-lean.md`
   `:655–657`, opened and read; quoted): "A product-level value is usable only
   when its type, range, state, identity, and timestamp conditions for the
   relevant metric pass. Null, malformed, future, naive, negative, non-finite, or
   state-excluded values SHALL be unavailable." The dependency map's metric row
   (`:211`, opened and read; quoted): "Structural validation is supplied by Chunk
   1; Chunk 7A owns metric eligibility semantics: null, malformed, wrong type,
   invalid range, future, naive, negative, non-finite, and excluded-state values."
   The LREQ-MET-040 edge-case column (`:214`, opened and read; quoted): "Zero page
   views are valid; negative/non-finite values invalid; age threshold;
   identity/state mismatch; ProductDetail may remain usable when PageViews is
   unavailable." The chunk gate bullet (`:801`, opened and read; quoted): "Invalid
   values are excluded rather than converted to zero." (Locant note: the earlier
   brief cited this bullet as "map lines 768–772"; `:768–772` is the Implement
   bullet list, and the quoted sentence is at `:801`.)
   Therefore a product-level value of the wrong type, or a negative or non-finite
   product-level number, yields `value is None` with the distinct reason
   `wrong_type`/`negative`/`non_finite` — never a raised exception and never `0`;
   `ValueError` remains only for the non-product parameters in §5.0/§5.3. The
   earlier "decision 3" reading (reserved reasons; `ValueError` on a negative or
   `bool` page-view) is superseded by this SRS-backed reading.
5. **A-5 — `metrics.py` imports `validation`.** Decision 1 places the semantics in
   `metrics.py` and forbids editing `validation.py`; it does not forbid importing
   it. Dependency map line 771 ("the metric-eligibility layer over Chunk 1's
   structural validation primitives") and line 211 support consuming
   `annotate_state_eligibility`. The import is pure→pure and allowed by
   `check_import_boundaries.FORBIDDEN_MODULES` (read). The alternative is to
   re-implement the published/excluded/unknown predicate in `metrics.py`, which
   would duplicate Chunk 1's rule.
6. **A-6 — `malformed` is unproduced by the current function set, not unreachable
   in general.** No 7A function receives an un-parsed response shape or an alias
   set: shape/alias classification is Chunk 1's and per-operation payload
   classification is Chunk 5's (gate bullet, dependency map `:802`, opened and
   read; quoted: "Structural malformed-shape/type/alias checks remain owned by
   Chunk 1; this chunk owns the semantic decision about whether a value
   contributes to a metric."). `METRIC_REASON_MALFORMED` is retained in the closed
   vocabulary because a future 7A caller may map a Chunk 1/5 structural outcome
   onto a metric input and pass it; this plan does not claim the category is
   unreachable in general, only that no function in this chunk produces it.