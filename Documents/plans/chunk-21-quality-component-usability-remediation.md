# Chunk 21 — Config-vs-constant reconciliation (one policy-parameter source)

Status: **FROZEN** (2026-09-26; amended 2026-09-26 — one accepted forced
deviation recorded in §5 "Accepted deviations"). Single-concern labeled
post-Chunk-20 remediation.

This chunk is a **labeled post-completion remediation** (Chunks 14–20 pattern): it has no
`requirements-dependency-map.md` §3/§4 gate row, no new interface file, and no downstream
chunk. It executes the independently assessed and human-adopted ruling **(c)** (recorded
in `Documents/runs/chunk-21.md`, "Human rulings" and "Assessment verification and adopted
ruling (2026-09-26)"): re-scope from the earlier Q2-only "wire the rating knob" item to a
single **config-vs-constant reconciliation** concern. The earlier S-A and its BLOCKER are
superseded.

One concern: the persisted per-stratum audit and the scored / category-level values must
derive from **one policy-parameter source** (`NicheScoutConfig`), covering
`min_usable_samples_per_stratum`, `min_age_days_for_rate`, and `quality_min_rating_count`.
`recent_window_days` is included only where it enters a comparable output (it does not;
see §5). Defaults remain the `models` constants; unset behavior is byte-identical.

## 0. Consumed frozen surfaces

| Surface | Status consumed | Role here |
|---|---|---|
| `Documents/runs/chunk-21.md` | findings F1–F5; human rulings; "Assessment verification and adopted ruling (2026-09-26)" | the diagnosis and the adopted ruling (c) + authorization |
| `Documents/interfaces/chunk-6B.md` | `Status: VERIFIED` (line 3) | `finalize_stratum_counts` (§5.4, lines 274–283), `finalize_enrichment` (§5.4, lines 308–316), `assert_finalization_consistency` (§5.5, lines 342–349): **three frozen signatures gain additive keyword-only parameters** (authorized) |
| `Documents/interfaces/chunk-7A.md` | `Status: VERIFIED` (line 3) | `quality_observation_eligibility` (§4, lines 119–127) and §4.1 caller-parameter list: **gains two additive keyword-only parameters** (authorized) |
| `Documents/interfaces/chunk-7B.md` | `Status: VERIFIED` (line 3) | `CategoryMetricInput.quality_min_rating_count` (line 77 comment) and the INERT paragraph (lines 106–109): **becomes false; corrected additively** (authorized) |
| `Documents/interfaces/chunk-10.md` | `Status: VERIFIED` (line 3) | orchestration description (step 11, line 81): **additive note that `finalize_enrichment` receives the run policy values from `config`** (authorized); it lists no signature |
| `Documents/plans/chunk-20-usable-quality-count-fabricated-zero-remediation.md` | `Status: FROZEN` | established remediation plan shape; §8 gate checklist reused |
| `Documents/runs/chunk-20.md` | `GATE: PASSED` (line 61) | prerequisite complete; its Minor "config-vs-constant split" (lines 112–116) is the item this chunk resolves (note: its "would flag check B" claim is superseded, see §3) |

## 1. Goal

Make the persisted per-stratum audit (`finalize_stratum_counts` →
`finalize_enrichment`) and the scored / category-level values (`CategoryMetricInput` used
by `compute_category_raw_metrics`, including inside `assert_finalization_consistency`
check B) read the **same** `min_usable_samples_per_stratum`, `min_age_days_for_rate`, and
`quality_min_rating_count` values, so that a non-default `NicheScoutConfig` is honored by
both paths and the consistency assertion compares like-for-like. Today the finalize path
and the assertion use the module constants, while the run-level `CategoryMetricInput` uses
`config` (`pipeline.py:3412–3416`); a non-default config is therefore silently uncaught
(constant-vs-constant agrees) rather than flagged.

This is a conformance/consistency fix, not a usability change and not expected to change
rankability or rank. It does **not** change any default.

## 2. Grounded findings

Labels as recorded in `Documents/runs/chunk-21.md`; the corrected mechanism supersedes the
earlier record.

- **F1 (read/counted).** Latest run scores all 8 categories `not_rankable`; Q null because
  `quality_stratum_eligibility_coverage < MIN_REQUIRED_COMPONENT_COVERAGE (0.50)` at the
  frozen `MIN_USABLE_SAMPLES_PER_STRATUM (5)`.
- **F2 (counted).** The binding lever is `min_usable_samples_per_stratum` (M), not
  `quality_min_rating_count`. Correction carried forward: "at M=5 no Q value changes
  coverage" holds **only because the knob is inert** (F3).
- **F3 (read/counted).** `quality_min_rating_count` is inert: enforced only by the module
  constant in 7A `quality_observation_eligibility` (`metrics.py:322`); `pipeline.py:3415`
  writes the config value into an unused field. Contradicts SRS §14 line 1296
  (Configurable `Yes`). Correction carried forward: F1's `["C","Q"]` for
  icons/humanoids/land is a separate breadth truncation defect (2000 cap), not a quality
  defect.
- **F4 (counted).** `rating_average = 0` occurs only at `rating_count ∈ {0,1,2}`; the
  latest-run subset is 105 rows (all-runs total 210 — correction carried forward). §7.5
  accepts `rating_average ∈ [0,5]`. Whether `average=0` means "unrated" or a real 0-star
  rating is unresolved (Q3, deferred; §4).
- **F5 (unverified).** Whether vfx becomes `provisional` (LREQ-EVD-030) once Q is
  available is SRS-derived, not executed through `scoring.py`.
- **Corrected check-B mechanism (the adopted assessment; supersedes the earlier record).**
  Check B builds `CategoryMetricInput` with only `category`, `scoring_cutoff_utc`,
  `page_view_semantics_status`, `strata` (`pipeline.py:2190–2196`), so all thresholds
  default to the module constants; check A hardcodes `MIN_USABLE_SAMPLES_PER_STRATUM`
  (`pipeline.py:2116/2128/2140`); and `finalize_enrichment` calls `finalize_stratum_counts`
  with no threshold args (`pipeline.py:1997–2002`). Constant-vs-constant agrees, so a
  non-default config is **silently uncaught**, not flagged. The config-vs-constant split is
  real for **M** and **min_age** (`metrics.py:620–626` vs `metrics.py:1013–1016`);
  `recent_window_days` is not window-gated in finalize; `quality_min_eligible_assets` is
  already consistent (`metrics.py:1572`).
- **Adopted ruling (c).** Re-scope to one config-vs-constant reconciliation concern: one
  policy-parameter source feeding both the finalization path and `CategoryMetricInput`,
  with the consistency assertion comparing like-for-like, covering
  `min_usable_samples_per_stratum`, `min_age_days_for_rate`, and
  `quality_min_rating_count`.
- **Authorization recorded.** Adopting (c) authorizes the additive frozen-interface
  updates to `Documents/interfaces/chunk-6B.md`, `chunk-7A.md`, `chunk-7B.md` (INERT
  note), and `chunk-10.md` that the reconciliation requires, and a `models.py` policy
  carrier **if the plan chooses one**. This plan **chooses not to add a carrier** (see §5)
  and changes no `models.py` file; every frozen signature changed is named in §5.

## 3. One policy-parameter source

`NicheScoutConfig` (config.py lines 130–133) is the single source. The run level already
passes its `min_usable_samples_per_stratum` / `min_age_days_for_rate` /
`quality_min_rating_count` into the scored `CategoryMetricInput`
(`pipeline.py:3412–3416`); this chunk also passes the same three fields into the
finalize path, which forwards them to the assertion:

```
config.* ─┬─> finalize_enrichment(..., min_usable_samples_per_stratum, min_age_days_for_rate, quality_min_rating_count)
          │        └─> finalize_stratum_counts(..., min_usable_samples_per_stratum, min_age_days_for_rate, quality_min_rating_count)
          │                 └─> quality_observation_eligibility(..., min_age_days_for_rate, quality_min_rating_count)
          │        └─> assert_finalization_consistency(..., same three)
          │                 └─> check A: stratum_is_usable(..., min_usable_samples_per_stratum)
          │                 └─> check B: CategoryMetricInput(..., same three)
          └─> CategoryMetricInput(..., min_usable_samples_per_stratum, min_age_days_for_rate, quality_min_rating_count)  [existing, unchanged]
```

Within the pure layer, `_quality_observation_index` passes `input.min_age_days_for_rate`
and `input.quality_min_rating_count` into `quality_observation_eligibility`, so 7A and 7B
agree on the same per-observation verdict.

## 4. Scope

### In scope

- **S1 (7A pure surface).**
  - `quality_observation_eligibility` gains keyword-only
    `min_age_days_for_rate: int = MIN_AGE_DAYS_FOR_RATE` and
    `quality_min_rating_count: int = QUALITY_MIN_RATING_COUNT`; both are validated as
    caller/policy parameters (int, not `bool`, `>= 1`) with `ValueError`, per 7A §4.1;
    forwarded to `age_normalized_page_view_index` and `_classify_rating_count`
    respectively.
  - `_classify_rating_count` gains keyword-only
    `quality_min_rating_count: int = QUALITY_MIN_RATING_COUNT`; the comparison at
    `metrics.py:322` uses the parameter.
  - `_quality_observation_index` passes
    `min_age_days_for_rate=input.min_age_days_for_rate` and
    `quality_min_rating_count=input.quality_min_rating_count` into
    `quality_observation_eligibility`.
  - `CategoryMetricInput` docstring / `#:` INERT note (`metrics.py:766–773, 793–798`)
    updated to state the field is live; no dataclass field, default, or validation change.
- **S2 (6B finalize surface).**
  - `finalize_stratum_counts` gains `quality_min_rating_count` and forwards it plus its
    existing `min_age_days_for_rate` into `quality_observation_eligibility`.
  - `finalize_enrichment` gains `min_usable_samples_per_stratum`,
    `min_age_days_for_rate`, `quality_min_rating_count`; forwards them to
    `finalize_stratum_counts`, replaces the hardcoded `MIN_USABLE_SAMPLES_PER_STRATUM` in
    the three category-level sums (`pipeline.py:2018/2026/2034`) with the parameter, and
    forwards all three to `assert_finalization_consistency`.
  - `assert_finalization_consistency` gains the same three; check A
    (`pipeline.py:2116/2128/2140`) uses `min_usable_samples_per_stratum`, and check B's
    `CategoryMetricInput` (`pipeline.py:2190–2196`) passes all three.
- **S3 (10 orchestration).** The run-level `finalize_enrichment` call
  (`pipeline.py:3395–3402`) passes the three `config.*` values, so both paths read the
  same source. `CategoryMetricInput` (`pipeline.py:3407–3417`) is unchanged.
- **S4 (frozen-interface doc updates).** §5.
- **S5 (tests + traceability).** §7.
- **S6 (records).** Plan and run log.

### Explicitly out of scope (recorded, never open here)

- **Q1(b).** Keep the SRS §14 default `MIN_USABLE_SAMPLES_PER_STRATUM = 5`; operator
  per-run override only. No default change.
- **Q3(a), deferred.** `rating_average == 0` as "unrated" is an SRS §7.5 revision;
  behaviorally inert at the frozen minimum and **must not block chunk-21**. The recorded
  interim guard ("never set the rating minimum below 3") is not implemented here.
- **Q4(a).** Accept Q-unavailable for trees/land/orchestral; no sampling revision.
- **Q5(c).** Category expansion to ≥21 is a separate chunk requiring a fresh `ec_category`
  capture plus taxonomy work.
- F1's `["C","Q"]` truncation defect (breadth at the 2000 cap) — not a quality defect.
- `recent_window_days` added to the finalize/assert signatures — it enters no comparable
  finalize output (§5).
- A `models.py` policy carrier; any default change; SRS edit; sampling change;
  category-count change; new config knob; CLI flag; persisted field; dependency.
- Live network; credentials.

## 5. Frozen signatures changed, and why `recent_window_days` is excluded

Every changed signature is additive (new keyword-only parameters with `models` defaults),
so existing positional/keyword calls are unchanged and unset behavior is byte-identical.

**Frozen interface `Documents/interfaces/chunk-7A.md` §4 — one signature changed:**

```python
def quality_observation_eligibility(
    *,
    product_detail_status: OperationStatus,
    page_views_status: OperationStatus,
    id_mapping_mismatch: bool,
    state: str | None,
    rating_average: object,
    rating_count: object,
    page_view_semantics_status: PageViewSemanticsStatus,
    product_page_views: object,
    first_published_date_utc: object,
    scoring_cutoff_utc: datetime,
    min_age_days_for_rate: int = MIN_AGE_DAYS_FOR_RATE,
    quality_min_rating_count: int = QUALITY_MIN_RATING_COUNT,
) -> MetricEligibility: ...
```

§4.1 gains the two new caller/policy parameters in its `ValueError` list.

**Frozen interface `Documents/interfaces/chunk-6B.md` §5.4 — two signatures changed:**

```python
def finalize_stratum_counts(
    category: CategorySamplingResult,
    observations: Mapping[str, EnrichmentObservationRecord],
    *,
    scoring_cutoff_utc: datetime,
    page_view_semantics_status: PageViewSemanticsStatus,
    min_usable_samples_per_stratum: int = MIN_USABLE_SAMPLES_PER_STRATUM,
    min_age_days_for_rate: int = MIN_AGE_DAYS_FOR_RATE,
    recent_window_days: int = RECENT_WINDOW_DAYS,
    quality_min_rating_count: int = QUALITY_MIN_RATING_COUNT,
) -> tuple[StratumFinalization, ...]: ...

def finalize_enrichment(
    repository: SqliteRepository,
    run: RunSamplingResult,
    *,
    scoring_cutoff_utc: datetime,
    computed_at_utc: datetime,
    page_view_semantics_status: PageViewSemanticsStatus,
    union: EnrichmentUnion,
    min_usable_samples_per_stratum: int = MIN_USABLE_SAMPLES_PER_STRATUM,
    min_age_days_for_rate: int = MIN_AGE_DAYS_FOR_RATE,
    quality_min_rating_count: int = QUALITY_MIN_RATING_COUNT,
) -> FinalizationReport: ...
```

**Frozen interface `Documents/interfaces/chunk-6B.md` §5.5 — one signature changed:**

```python
def assert_finalization_consistency(
    repository: SqliteRepository,
    run: RunSamplingResult,
    finalization: FinalizationReport,
    *,
    scoring_cutoff_utc: datetime,
    page_view_semantics_status: PageViewSemanticsStatus,
    min_usable_samples_per_stratum: int = MIN_USABLE_SAMPLES_PER_STRATUM,
    min_age_days_for_rate: int = MIN_AGE_DAYS_FOR_RATE,
    quality_min_rating_count: int = QUALITY_MIN_RATING_COUNT,
) -> tuple[str, ...]: ...
```

**Frozen interface `Documents/interfaces/chunk-7B.md` — no signature change; additive
correction of the false INERT note.** Line 77's `# INERT for 7B` comment and the paragraph
at lines 106–109 are replaced with wording that
`CategoryMetricInput.quality_min_rating_count` is **live**: `_quality_observation_index`
passes it to Chunk 7A's `quality_observation_eligibility`, so an override changes
`quality_stratum_eligibility_coverage`, `quality_raw`, and `usable_quality_sample_count`.
No dataclass field changes; `quality_min_rating_count: int = QUALITY_MIN_RATING_COUNT`
stays.

**Frozen interface `Documents/interfaces/chunk-10.md` — additive orchestration note only
(no signature listed there).** §3 step 11 records that `finalize_enrichment` is called with
`min_usable_samples_per_stratum`, `min_age_days_for_rate`, and `quality_min_rating_count`
taken from `config`, the same source as step 12's `CategoryMetricInput`.

**Module-private helpers changed (not frozen public interface):**
`metrics._classify_rating_count` gains keyword-only
`quality_min_rating_count: int = QUALITY_MIN_RATING_COUNT`;
`metrics._quality_observation_index` forwards `input.min_age_days_for_rate` and
`input.quality_min_rating_count`.

**Why `recent_window_days` is NOT added to `finalize_enrichment` /
`assert_finalization_consistency`.** `recent_window_days` affects only
`recent_share_raw.value` (the inclusive window in `is_within_recent_window`,
`metrics.py:1136–1140`); it does not enter the compared quantities.
`usable_recent_supply_sample_count` counts observations with a valid exact age
(`_usable_ages`), independent of the window; the three `usable_*_sample_count` values are
the only finalize-vs-7B compared outputs. On the scoring side the window is already sourced
from config via `CategoryMetricInput.recent_window_days` (`pipeline.py:3414`) and is
unchanged. Per the adopted scope, it is included "only where it enters a comparable
output" — there is none, so it is excluded and this exclusion is deliberate.

**No `models.py` change; no policy carrier.** The four parameter names already exist in
`NicheScoutConfig` and `CategoryMetricInput`; a new carrier would add a second vocabulary
and would either duplicate or non-additively replace `finalize_stratum_counts`'s existing
parameters. The single source is `NicheScoutConfig`, threaded explicitly. The file
`src/niche_scout/models.py` is untouched.

**Accepted deviations (2026-09-26).**

One forced deviation was accepted during implementation. `metrics.quality_raw`'s
`METRIC_REASON_ELIGIBLE_SET_TOO_SMALL` branch (`metrics.py:1591–1603`) now returns the
accumulated `usable_sample_count` / `eligible_population_count` instead of `0`. This is
required so check B's 7B count can equal the finalized count under
`min_usable_samples_per_stratum=1`: with a non-default minimum the guard can fire while a
stratum is usable, and a forced `0` would make `assert_finalization_consistency` flag a
mismatch that is not a real drift (the test `§8.2` node 5 pins this). It is
default-preserving: at the default `MIN_USABLE_SAMPLES_PER_STRATUM = 5` the guard fires
only when no stratum is usable, so the accumulated values are the same true zeros (`0`).
The count fields are independent of `.value` and non-nullable (frozen chunk-7B interface
§4.2; SRS §6.5 line 637). No default, formula, or reason precedence changes. This adds
`metrics.py::quality_raw` to the touched surface beyond the signatures listed above.

## 6. LREQs by role (cited, not paraphrased)

Chunk 21 has no `requirements-dependency-map.md` §3 section.

| LREQ ID | Role here | Cited SRS location |
|---|---|---|
| LREQ-MET-090 | **Primary** — quality-eligible conditions and default quality constants | §7.5, lines 817–833 |
| LREQ-MET-100 | **Primary** — `QualityRaw` denominator/numerator (unchanged; eligibility inputs only) | §7.5, lines 842–870 |
| LREQ-SMP-080 | **Primary** — persisted per-stratum `u_*_h`, usable counts, and eligibility rule | §5.1, lines 472–489 |
| LREQ-MET-030 | **Supporting** — `stratum_is_usable` inclusive minimum used by check A | §7.1 |
| LREQ-MET-040 | **Supporting** — page-view index age threshold propagation into quality | §7.1 |
| LREQ-MET-010 | **Supporting** — null/zero/invalid/unavailable stay distinct | §7.1 |
| LREQ-ARCH-010 / LREQ-ARCH-020 | **Constraint** — purity; no clock; `scoring_cutoff_utc` explicit | §3 |
| LREQ-ARCH-030 | **Constraint** — determinism | §3 |
| LREQ-NFR-040 | **Supporting** — docstrings state null/edge behavior for public functions | §11 |
| LREQ-TST-010 / LREQ-TST-090 | **Supporting** — normal/zero/missing/invalid/boundary coverage; `1e-9` golden vectors | §13 |

SRS §14: `MIN_USABLE_SAMPLES_PER_STRATUM` default 5 / Yes (line 1291);
`MIN_AGE_DAYS_FOR_RATE` default 30 / Yes (line 1294); `RECENT_WINDOW_DAYS` default 365 /
Yes (line 1295); `QUALITY_MIN_RATING_COUNT` default 5 / Yes (line 1296).

## 7. Files touched

| File | New/modified | Purpose |
|---|---|---|
| `src/niche_scout/metrics.py` | modified | S1: two keyword-only params on `quality_observation_eligibility`; `_classify_rating_count` param; `_quality_observation_index` forwards both; docstrings/INERT note. |
| `src/niche_scout/metrics.py::quality_raw` | modified | accepted deviation (§5): `METRIC_REASON_ELIGIBLE_SET_TOO_SMALL` branch returns accumulated `usable_sample_count` / `eligible_population_count` instead of `0`; default-preserving. |
| `src/niche_scout/pipeline.py` | modified | S2/S3: three frozen signatures gain additive keyword-only params; check A/B use them; run-level call passes `config.*`. |
| `Documents/interfaces/chunk-7A.md` | modified | **authorized**: `quality_observation_eligibility` signature + §4.1 list + §4.2 note. |
| `Documents/interfaces/chunk-6B.md` | modified | **authorized**: the three signatures + their docstring parameter notes. |
| `Documents/interfaces/chunk-7B.md` | modified | **authorized**: INERT note (line 77 comment; lines 106–109) corrected to live. |
| `Documents/interfaces/chunk-10.md` | modified | **authorized**: additive §3 step 11 note (policy values from `config`). |
| `tests/test_validation.py` | modified | S5: two new 7A override nodes (§8). |
| `tests/test_enrichment.py` | modified | S5: three new finalize/assertion nodes (§8). |
| `tests/test_metrics.py` | modified | S5: one new 7B coverage node (§8). |
| `tests/fixtures/enrichment_fixtures.py` | modified | S5: one new rating-count-straddling finalization fixture (§8.3); existing vectors unmoved. |
| `tests/traceability.json` | modified | S5: six new node-ID keys (§8.4). |
| `Documents/runs/chunk-21.md` | modified | S6: record stage 1c outcome, gate output, disposition. |

**Not touched:** `Documents/SRS-lean.md`, `src/niche_scout/models.py`, `config.py`,
`scoring.py`, `database.py`, `report.py`, `cli.py`, `sampling.py`, `validation.py`, the
collector modules, `src/niche_scout/tools/**`, `pyproject.toml`, `AGENTS.md`,
`kilo.json(c)`, `.kilo/`.

## 8. Test plan

No live network; fixtures/local typed inputs only. Authored by `test-author` before
`impl-deep`. Every analytical test carries `@pytest.mark.lreq(...)` and a
`tests/traceability.json` entry (the committed file is **node-ID-keyed**; each value is a
list of LREQ IDs — see `tests/AGENTS.md` orientation note in §10).

### 8.1 Default unchanged — reused nodes (no new key)

- `tests/test_validation.py::test_quality_observation_eligibility_combines_conditions` —
  `["LREQ-MET-090"]`; the default-call eligible verdicts are unchanged.
- `tests/test_validation.py::test_quality_rating_range_and_count_thresholds` —
  `["LREQ-MET-090"]`; `rating_count=4` still `rating_count_below_minimum`, `== 5` eligible.
- `tests/test_validation.py::test_quality_rating_wrong_type_and_negative_are_distinct_reasons`
  — `["LREQ-MET-090", "LREQ-MET-010"]`.
- `tests/test_validation.py::test_quality_eligibility_propagates_page_view_index_reason`
  — `["LREQ-MET-090", "LREQ-MET-040"]`; default `min_age_days_for_rate` still yields
  `age_below_minimum` at `DATE_29D_1H`.
- `tests/test_enrichment.py::test_finalize_stratum_counts_from_observations` —
  `["LREQ-SMP-080"]`; golden 4/5/3 counts unchanged under defaults.
- `tests/test_enrichment.py::test_finalize_agrees_with_chunk7b_compute_category_raw_metrics`
  — `["LREQ-SMP-080"]`; default agreement unchanged.
- `tests/test_enrichment.py::test_assert_consistency_clean_run_returns_no_mismatches` —
  `["LREQ-SMP-080"]`; default clean run still `()`.
- `tests/test_metrics.py::test_quality_coverage_not_renormalized` — `["LREQ-MET-090"]`.
- `tests/test_contracts.py` constant pins (including `QUALITY_MIN_RATING_COUNT == 5`) —
  unchanged, since no default/constant is modified.

### 8.2 New nodes

1. `tests/test_validation.py::test_quality_observation_eligibility_rating_count_override`
   — `LREQ-MET-090`. With `dfx.quality_kwargs(rating_count=3, quality_min_rating_count=3)`
   → eligible `True`; `rating_count=2` at the same minimum →
   `METRIC_REASON_RATING_COUNT_BELOW_MINIMUM`; `rating_count=3` omitting the parameter →
   `rating_count_below_minimum` (default 5 still applies). Also `quality_min_rating_count`
   in `{True, 0, 1.5, "3"}` → `ValueError`.
2. `tests/test_validation.py::test_quality_observation_eligibility_min_age_override`
   — `LREQ-MET-090`. Default `DATE_30D`-based `dfx.quality_kwargs()` at
   `min_age_days_for_rate=30` → eligible; the same kwargs at
   `min_age_days_for_rate=31` → `METRIC_REASON_AGE_BELOW_MINIMUM` (pins the
   `metrics.py:620–626` split). `min_age_days_for_rate` in `{True, 0, 1.5}` →
   `ValueError`.
3. `tests/test_enrichment.py::test_finalize_stratum_counts_quality_min_rating_count_override`
   — `LREQ-SMP-080`, `LREQ-MET-090`. A locally built one-stratum category (`N_h`, `n_h`,
   `ef.observation_record(..., rating_count=3)` members) finalized with
   `quality_min_rating_count=3` and `min_usable_samples_per_stratum=1` counts the
   `rating_count=3` observations in `u_quality_h`; omitting the parameter (default 5)
   leaves them out. Hand-computed integers.
4. `tests/test_enrichment.py::test_finalize_enrichment_non_default_policy_is_self_consistent`
   — `LREQ-SMP-080`, `LREQ-MET-090`. On the seeded golden single-category run
   (`ef.seed_finalization`), call `finalize_enrichment` with
   `min_usable_samples_per_stratum=1` and separately with `min_age_days_for_rate=101`;
   assert `report.mismatches == ()` and the expected `usable_*_sample_count` values. At
   defaults the same fixture yields the known M=5 counts; a non-default that the assertion
   did **not** receive would make check A/B flag a mismatch, so an empty `mismatches`
   proves the assertion received the same parameters.
5. `tests/test_enrichment.py::test_finalize_enrichment_rating_min_matches_seventh_b`
   — `LREQ-SMP-080`, `LREQ-MET-090`. Using the §8.3 straddling fixture seeded through the
   frozen write path, call `finalize_enrichment` with `quality_min_rating_count=3` and
   `min_usable_samples_per_stratum=1`; assert the persisted/returned
   `usable_quality_sample_count` reflects the `rating_count=3` observations and
   `mismatches == ()` (check B's `CategoryMetricInput` consumed the same rating minimum).
6. `tests/test_metrics.py::test_quality_min_rating_count_changes_quality_coverage`
   — `LREQ-MET-090`. A `CategoryMetricInput` built via
   `dataclasses.replace(make_category_input(strata), quality_min_rating_count=3)` over
   `rating_count=3` observations yields a different
   `quality_stratum_eligibility_coverage` / eligible set than the default-5 input; pins
   that `_quality_observation_index` consumes `input.quality_min_rating_count` (not the
   constant).

### 8.3 Golden vectors / fixtures

- **Existing vectors unmoved.** `enrichment_fixtures.finalization_observations()` and all
  `metric_estimator_fixtures` vectors keep byte-identical values; the six-node fixture is
  not edited in place.
- **One new fixture builder** in `tests/fixtures/enrichment_fixtures.py`: a
  rating-count-straddling finalization set returning `(category, run, observations)` (or an
  equivalent `seed_*` helper) whose members carry `rating_count=3`, with the remaining
  fields mirroring the golden finalization fixture (aware UTC date, both operations
  successful, published state). Hand-computed expected `u_quality_h` /
  `usable_quality_sample_count` are stated in the test.
- 7B coverage assertion uses exact eligibility (integers) and `abs=1e-9` for any float
  coverage.

### 8.4 `tests/traceability.json` impact

The committed file is **node-ID-keyed**. The six new nodes in §8.2 add six new keys
(`"tests/test_validation.py::..."` etc.), each carrying its `LREQ-*` list as in §8.2; the
reused nodes in §8.1 keep their entries byte-identical. `validate_traceability` requires
every analytical test to have a marker + entry and every requirement to map to ≥1 node;
the six keys satisfy both. No key is renamed or removed.

## 9. Gate checklist (implementer; copied from the post-completion pattern, chunk-20 §8)

- **DoD-1 (offline suite).** `python -m pytest -q` → `passed, 0 failed`; verbatim output
  with real counts recorded in `Documents/runs/chunk-21.md`.
- **DoD-2 (validators).** `python -m niche_scout.tools.validate_traceability`,
  `python -m niche_scout.tools.check_import_boundaries`,
  `python -m niche_scout.tools.check_scope_prohibitions`, and
  `python -m niche_scout.tools.check_secrets` all exit 0.
- **DoD-3 (lint/format).** `ruff check` and `ruff format --check` over the changed files
  (`line-length = 88`, select `E,F,I` per `pyproject.toml`); no new lint; a pre-existing
  deviation is reported PARTIAL with the unchanged lines named.
- **DoD-4 (traceability reconciliation).** `validate_traceability` exits 0;
  `git diff --stat -- tests/traceability.json` shows exactly the six added keys.
- **DoD-5 (prohibitions).** §10 holds; every file outside §7 is byte-identical.
- **DoD-6 (records).** Plan and run log recorded; remaining obligations stay open (§11).
- **Byte-identity checks.** Existing golden vectors and default-path outputs are unchanged;
  `src/niche_scout/models.py` and `Documents/SRS-lean.md` are untouched (diff empty).
- No human live run is required; no live network; no credentials.

## 10. Prohibitions

- **Do not change any default** (`MIN_USABLE_SAMPLES_PER_STRATUM` stays 5,
  `MIN_AGE_DAYS_FOR_RATE` stays 30, `QUALITY_MIN_RATING_COUNT` stays 5); do **not** modify
  `src/niche_scout/models.py`.
- **Do not edit `Documents/SRS-lean.md`.**
- **Do not edit any interface file except the four authorized in §7** (`chunk-7A.md`,
  `chunk-6B.md`, `chunk-7B.md`, `chunk-10.md`), and only additively/default-preserving.
- **Do not collapse null and zero**; keep `metrics.py` pure (no I/O, imports, or clock);
  `scoring_cutoff_utc` stays an explicit parameter.
- **Do not** add a `models.py` policy carrier, a new config knob, a CLI flag, a persisted
  field, or a dependency; do not add `recent_window_days` to the finalize/assert
  signatures.
- **Do not resolve Q1, Q3, Q4, or Q5** (§4); do not implement the Q3 interim guard.
- **Do not invent** an LREQ ID, formula, threshold, weight, default, or field name.
- **No live network in development or tests**; never run `niche-scout run`; never read
  credentials.
- **One concern per plan.**

## 11. Residual risks and open obligations (recorded, never resolved here)

- **F5 unverified** — vfx → `provisional` via LREQ-EVD-030 is SRS-derived, not executed
  through `scoring.py`.
- **Coverage pinned ~0.25** for trees/land/orchestral for any Q and any M (F2).
- **Behavioral note.** This reconciliation makes a non-default
  `NicheScoutConfig` actually govern the finalize path; at defaults, behavior is
  byte-identical. No rankability or rank change is asserted.
- **`Documents/runs/chunk-20.md:112–116`** ("would flag check B") is inaccurate per §2; it
  is noted here rather than edited (chunk-20 is a closed record; change control is the
  human's).
- **Open obligations unchanged:** URI trailing-identifier extraction
  (`identity_mapping_rule 1.0.1`) unverified; OI-6 CSRF/session sufficiency unassigned;
  `runs.taxonomy_sha256` empty-hash rejection owner Chunk 10; `tests/AGENTS.md`
  traceability orientation prose (LREQ-keyed) disagrees with the committed node-ID-keyed
  `tests/traceability.json`.
- **Adjacent (in scope for this chunk, resolved by it):** `finalize_enrichment`'s three
  category-level sums and `assert_finalization_consistency` check A previously used the
  module constant while `compute_category_raw_metrics` used the config value; both now use
  the passed parameter.

## 12. Open questions

None. Ruling (c) plus the recorded authorization determine the whole plan; Q1(b), Q3(a),
Q4(a), and Q5(c) are closed as out of scope (§4), not open.

## 13. Routing

1. `test-author` — §8 tests first (4–6 fail against current code).
2. `impl-deep` — S1–S4; the change sits on frozen 7A/6B surfaces and feeds persisted
   counts, so `impl-deep` is required (`impl-fast` is not suitable).
3. `spec-reviewer` — plan, diff, tests, run-log evidence, and the four interface-file
   reconciliations.