# Chunk 20 — Usable-quality-count fabricated-zero remediation (labeled post-Chunk-19 remediation)

Status: FROZEN

This plan freezes the diagnosis recorded in `Documents/runs/chunk-20.md` (the committed
root-cause record verified read-only before planning). It re-opens nothing about that
diagnosis and introduces no new open question. It is a **post-completion remediation**
(Chunks 14–19 pattern): there is no `requirements-dependency-map.md` §3/§4 gate row, no
new interface file, and no downstream chunk.

Depends on (frozen surfaces consumed unchanged):

- `Documents/runs/chunk-7B.md` — **`GATE: PASSED`** (line 91, and re-affirmed line 141
  after the post-gate review fixes). `quality_raw` and `MetricResult` are the frozen 7B
  surface this chunk repairs.
- `Documents/runs/chunk-6B.md` — **`GATE: PASSED`** (line 27). `finalize_enrichment`
  writes the true sum and its agreement assertion is the downstream consumer.
- `Documents/interfaces/chunk-7B.md` — **`Status: VERIFIED`** (line 3): the public
  `quality_raw` / `MetricResult` contract, including the `usable_sample_count` and
  `eligible_population_count` fields.
- `Documents/interfaces/chunk-10.md` — **`Status: VERIFIED`** (line 3): `_build_scored_rows`
  / `upsert_category_scores` copy the 7B field into `category_scores`.
- `Documents/plans/chunk-7B-sample-aware-raw-estimators.md` §5.4 (lines 563–577) — the
  non-normative per-estimator field-semantics RECOMMENDATION for `.usable_sample_count`
  and `.eligible_population_count`.

Blocks: none. Gate is §8 (offline suite + validators + ruff + traceability
reconciliation). No human live run is required: the defect is offline-verifiable.

## 1. Goal

Make `metrics.quality_raw` return the **accumulated** `usable_sample_count` and
`eligible_population_count` on the two null paths that can follow a usable-stratum
accumulation — `METRIC_REASON_INSUFFICIENT_COVERAGE` and
`METRIC_REASON_ZERO_DENOMINATOR` — so `CategoryRawMetrics.usable_quality_sample_count`
(and the persisted `category_scores.usable_quality_sample_count`) is the true count for
a category whose quality value is null, instead of the fabricated `0` produced by
`_null_result` defaults. Counts are never null (SRS §6.5 line 637), and the SRS requires
`usable_quality_sample_count` as a distinct persisted value (LREQ-SMP-080).

### 1.1 Grounded findings (labels: **read** = opened this session; **counted** = queried
with the query shown; **unverified** = not re-checked here)

- **G1 (read).** `metrics.py:1502–1600` `quality_raw` accumulates
  `usable_sample_count += len(eligible_indices)` (`:1566`) and
  `eligible_population_count += stratum.discovered_population_count` (`:1567`) inside the
  per-stratum loop, and the normal return passes both (`:1594–1600`). The six early
  returns are `METRIC_REASON_ZERO_POPULATION` (`:1527–1531`, pre-loop),
  `METRIC_REASON_ELIGIBLE_SET_TOO_SMALL` (`:1569–1573`),
  `METRIC_REASON_NO_USABLE_STRATUM` (`:1574–1578`),
  `METRIC_REASON_INSUFFICIENT_COVERAGE` (`:1579–1583`),
  `METRIC_REASON_ZERO_DENOMINATOR` (`:1584–1588`), and
  `METRIC_REASON_PAGE_VIEW_SEMANTICS_CONTRADICTED` (`:1589–1593`).
- **G2 (read).** `_null_result` (`:1032–1046`) has `usable_sample_count: int = 0` and
  `eligible_population_count: int = 0` defaults (`:1035–1036`). Every early return except
  the normal return omits both keyword arguments, so both reset to `0`.
- **G3 (read).** `MetricResult.eligible_population_count` is a field (`metrics.py:58`);
  `CategoryRawMetrics` (`:866–887`) exposes `usable_quality_sample_count` (`:885`) but has
  **no** `eligible_population_count` field. `compute_category_raw_metrics` copies
  `quality.usable_sample_count` into `usable_quality_sample_count` (`:1656`). Therefore a
  test that must read `eligible_population_count` reads it off `quality_raw(...)`
  (a `MetricResult`).
- **G4 (read).** The reason constants exist as module-local strings:
  `METRIC_REASON_NO_USABLE_STRATUM = "no_usable_stratum"` (`:667`),
  `METRIC_REASON_ZERO_POPULATION = "zero_population"` (`:668`),
  `METRIC_REASON_ELIGIBLE_SET_TOO_SMALL = "eligible_set_too_small"` (`:670`),
  `METRIC_REASON_ZERO_DENOMINATOR = "zero_denominator"` (`:671`),
  `METRIC_REASON_INSUFFICIENT_COVERAGE = "insufficient_coverage"` (`:672`).
- **G5 (read).** The existing tests at the three named nodes:
  `tests/test_metrics.py:595` (`test_quality_raw_zero_visibility_denominator_is_null`,
  assertion `:596–599`), `:603` (`test_quality_eligible_set_too_small_is_null`,
  assertion `:613–615`), `:619` (`test_quality_raw_null_below_required_coverage`,
  assertion `:631–636`). None reads a count today. The existing house pattern for a count
  assertion is `aggregate = m.compute_category_raw_metrics(...)` then
  `assert aggregate.usable_quality_sample_count == 5` (`:720–724`), but that node's
  fixture (`QUALITY_LOW_COVERAGE` with an ineligible second stratum) reaches the
  **normal** return, so it does not pin the early-return paths.
- **G6 (counted).** Query
  `grep "test_quality_raw_null_below_required_coverage|test_quality_raw_zero_visibility_denominator_is_null|test_quality_eligible_set_too_small_is_null" tests/traceability.json`
  → **3 matching keys**, at lines 1040, 1049, and 1056, with values
  `["LREQ-MET-090"]`, `["LREQ-MET-090"]`, and
  `["LREQ-MET-100", "LREQ-TST-050"]` respectively (unit: JSON key lines, one key per
  match). These are the three nodes S2 extends; the keys are unchanged by this chunk.
- **G7 (read).** Regression consumers, all read this session:
  `scoring.py:496–502` returns `None` for the Q component when coverage is below the
  threshold (`:496–497`) or when `normalized.quality_raw is None` (`:499–500`);
  `scoring.py:936–937` appends `NotRankableReason.QUALITY_UNAVAILABLE` when
  `score.component_q is None`; `scoring.py:1008–1009` returns
  `NOT_RANKABLE` before any count is read; `scoring.py:1580–1581` returns
  `EvidenceGrade.INSUFFICIENT` when `decision.not_rankable_reasons` is non-empty, before
  `minimum_component_sample_count` is read (`:1583`); `scoring.py:1650–1651` maps a
  pre-sensitivity `NOT_RANKABLE` to `RankabilityStatus.NOT_RANKABLE`.
  `SampleEvidenceFacts.minimum_component_sample_count` (`:1268–1303`) consumes the counts
  but is only reached past those guarded returns.
- **G8 (read).** The two genuine-zero assertions in `tests/test_enrichment.py`
  (`:723–730` and `:755–763`) are correct: their fixtures have no quality-usable stratum,
  so `0` is the true count, not a fabrication (S3, §2).
- **G9 (unverified here / recorded in the run log).** The pipeline/report consumption
  chain cited in `Documents/runs/chunk-20.md` (root cause H3 and "Evaluator path":
  `pipeline.py:2029–2047`, `:2071`, `:3133`, `:3478–3479`; `report.py:431`) was verified
  by the prior read-only pass; it is not re-opened by this plan and no file on that chain
  is edited.

## 2. Scope

### In scope

- **S1 — the fix.** Pass `usable_sample_count=usable_sample_count` and
  `eligible_population_count=eligible_population_count` at exactly two returns:
  `METRIC_REASON_INSUFFICIENT_COVERAGE` (`metrics.py:1579–1583`) and
  `METRIC_REASON_ZERO_DENOMINATOR` (`metrics.py:1584–1588`). One function body changes;
  `_null_result`'s signature and defaults are untouched.
- **S2 — docstring.** Add one sentence to `quality_raw`'s docstring stating that
  `usable_sample_count` / `eligible_population_count` describe the quality-usable strata
  and are returned even when `.value` is null, because counts are never null (SRS §6.5
  line 637).
- **S3 — tests first (`test-author`), extending existing nodes.** Add count assertions at
  the three existing node IDs (no renames): the `INSUFFICIENT_COVERAGE` and
  `ZERO_DENOMINATOR` paths pin the accumulated counts, and the two zero paths
  (`ELIGIBLE_SET_TOO_SMALL`, and a locally-built `NO_USABLE_STRATUM` input) stay pinned
  at `0` so the fix cannot leak upward. No new fixture symbol, no new node ID, no
  `tests/traceability.json` change.
- **S4 — records.** Plan and run log.
- **S5 — record, never close**, the residual risks / open obligations (§11).

### Explicitly out of scope (and why)

- **`_null_result` defaults** (`metrics.py:1035–1036`). Kept exactly `0`; changing them
  would alter `ZERO_POPULATION`, `ELIGIBLE_SET_TOO_SMALL`, `NO_USABLE_STRATUM`, and every
  other estimator's null paths.
- **The other four quality early returns.** `ZERO_POPULATION` returns pre-loop (nothing
  accumulated); `ELIGIBLE_SET_TOO_SMALL` and `NO_USABLE_STRATUM` are the true-zero paths
  and SHALL keep `0`; `PAGE_VIEW_SEMANTICS_CONTRADICTED` is unreachable in practice
  (contradicted makes every observation quality-ineligible, so
  `ELIGIBLE_SET_TOO_SMALL` fires first) and keeps its default.
- **`pipeline.py`, `models.py`, `database.py`, `report.py`, `cli.py`, `config.py`,
  `sampling.py`, `scoring.py`, `validation.py`, the collector modules,
  `src/niche_scout/tools/**`, `pyproject.toml`, `config/**`.** Not authorized by 7B §6
  (the remediation is metrics-local) and not needed: the fix propagates through the
  existing `compute_category_raw_metrics` copy (`metrics.py:1656`).
- **`tests/fixtures/enrichment_fixtures.py`.** 7B §6 does not authorize it, and no new
  end-to-end node is needed: `tests/test_enrichment.py::test_finalize_agrees_with_chunk7b_compute_category_raw_metrics`
  already asserts `raw.usable_quality_sample_count == final.usable_quality_sample_count`
  (`:755`) and `test_assert_consistency_clean_run_returns_no_mismatches` covers the
  post-write assertion. Adding an `INSUFFICIENT_COVERAGE` shape to the 6B fixture would
  require editing a file outside this chunk's authorization.
- **`tests/test_enrichment.py:723–730`, `:755–763`, and the comment at `:756–758`.**
  Correct genuine-zero assertions; S3 is a non-scope note (§1.1 G8).
- **A new interface file, a new failure class, a new config knob, a CLI flag, a new
  persisted field, or a new dependency.** None.
- **Live network in development or tests.** No test calls the real endpoint; agents never
  run `niche-scout run`.
- **Any `requirements-dependency-map.md` §3 gate row.** This is a labeled
  post-completion remediation chunk.

## 3. Requirements

Chunk 20 has no `requirements-dependency-map.md` §3 section; the LREQs are taken from
`SRS-lean.md` at the cited lines.

| LREQ ID | Role here | Normative text (quoted/derived) | SRS |
|---|---|---|---|
| LREQ-SMP-080 | **Primary (persistence)** | "Every category SHALL persist discovered population size, sample … usable sample size by component … The following SHALL be persisted as distinct values: `discovered_population_count`, `enriched_sample_count`, `usable_demand_sample_count`, `usable_recent_supply_sample_count`, and `usable_quality_sample_count` as distinct values." A fabricated `0` for a category with usable quality strata violates the distinct/true value. | §5.1, 472–487 |
| LREQ-MET-090 | **Primary (quality availability)** | "Quality is unavailable below the minimum eligible count." "Quality SHALL also be unavailable when weighted usable coverage is below `MIN_REQUIRED_COMPONENT_COVERAGE`, when page-view semantics are contradicted, or when the visibility-weighted denominator is zero." The null rules are the two paths S1 changes. | §7.5, 817–833 |
| LREQ-MET-100 | **Primary (quality raw + counts)** | "It is null when the eligible set is too small, no stratum is quality-usable, or the expanded visibility-weighted denominator is zero." The result carries the usable-sample count of the quality-usable strata; `.value` being null does not make the count null. | §7.5, 842–870 |
| LREQ-MET-010 | Supporting (missing is not zero) | "Null, malformed, future, naive, negative, non-finite, or state-excluded values SHALL be unavailable." A null quality **value** must not be represented as a zero **count**. | §7.1, 655–657 |
| LREQ-NFR-040 | Supporting (docstring) | "Public metric and scoring functions SHALL have type hints and docstrings describing null and edge-case behavior." S2 adds the count-vs-value sentence. | §11, 1171–1172 |
| LREQ-TST-010 | Supporting (test coverage) | "Every formula SHALL have tests for normal values, explicit valid zero where applicable, missing values, invalid values, ties, and minimum boundaries." S3 pins the count on the null paths. | §13, 1225–1226 |
| LREQ-TST-050 | Supporting (metric tests) | "… zero-denominator quality; zero-population categories …". The `ZERO_DENOMINATOR` node is one of these. | §13, 1244–1248 |
| LREQ-TST-090 | Supporting (golden vectors) | "Golden vectors SHALL assert exact results within `1e-9` for sample-aware metrics …". The count assertions are exact-int assertions. | §13, 1266–1271 |
| LREQ-ARCH-010 / LREQ-ARCH-020 | Constraint (purity) | `metrics.py` stays pure: no I/O, no clock; `scoring_cutoff_utc` remains an explicit input. S1 changes no import and reads no clock. | §3 |
| LREQ-ARCH-030 | Constraint (determinism) | Same inputs + policy + config → same outputs; the fix is a deterministic function of the accumulated loop state. | §3 |

The §6.5 field-set clause this chunk leans on, quoted exactly (SRS §6.5 lines 618–620):

> The three `usable_*_sample_count` fields SHALL count distinct sampled observations
> that contribute to strata satisfying the applicable minimum usable-observation rule.
> The stratum summary remains authoritative for the per-stratum counts. No duplicate
> aliases such as `sample_size`, `demand_usable_count`, `recent_supply_usable_count`,
> or `quality_usable_count` SHALL be required in the lean schema.

and the nullability clause (SRS §6.5 line 637):

> Raw metrics and scores except counts and status fields SHALL be nullable.

The 7B plan §5.4 RECOMMENDATION (lines 563–577), quoted exactly:

> | Estimator | `.value` | `.usable_sample_count` | `.eligible_population_count` | `.eligibility_coverage` |
> |---|---|---|---|---|
> | `demand_per_asset_raw` | `DemandPerAssetRaw` | `Σ u_demand_h` over usable strata | `Σ N_h` over usable strata | demand coverage |
> | `demand_median_raw` | `DemandMedianRaw` | usable index observations (all strata) | `Σ N_h` over strata with ≥1 usable index | demand coverage |
> | `recent_share_raw` | `RecentShareRaw` | `Σ u_recent_h` over usable recent strata | `Σ N_h` over usable recent strata | recent coverage |
> | `median_age_raw` | `MedianAgeRaw` | usable age observations (all strata) | `Σ N_h` over strata with ≥1 usable age | recent coverage |
> | `quality_raw` | `QualityRaw` | `Σ` quality-eligible over quality-usable strata | `Σ N_h` over quality-usable strata | quality coverage |
>
> `eligible_population_count` is an SRS-unnamed convenience count: the SRS names
> only the `usable_*_sample_count` fields (SRS §6.5), not `eligible_population_count`.
> This table is a non-normative plan-design RECOMMENDATION and is independent of
> `.value` and `.eligibility_coverage`; Chunk 8/10 may challenge it without
> affecting either.

`quality_raw` therefore already **owns** the correct values on its normal return; S1
makes the two null-following-accumulation paths agree with that normal return. The SRS
sentence "the stratum summary remains authoritative for the per-stratum counts" is
satisfied because S1 copies the in-loop accumulation, it does not re-derive it.

## 4. Design

### 4.1 S1 — the two returns (exact code shape)

`metrics.py` `quality_raw`, inside the precedence chain (`:1579–1588`), becomes:

```python
    if coverage < input.min_required_component_coverage:
        return _null_result(
            METRIC_REASON_INSUFFICIENT_COVERAGE,
            usable_sample_count=usable_sample_count,
            eligible_population_count=eligible_population_count,
            eligibility_coverage=coverage,
        )
    if denominator == 0.0:
        return _null_result(
            METRIC_REASON_ZERO_DENOMINATOR,
            usable_sample_count=usable_sample_count,
            eligible_population_count=eligible_population_count,
            eligibility_coverage=coverage,
        )
```

No other line changes: the four other null returns, the loop, the normal return, and
`_null_result` are byte-identical apart from the S2 docstring sentence.

**Why only these two.** The documented precedence order is "reasons are evaluated in the
order `ZERO_POPULATION` → `ELIGIBLE_SET_TOO_SMALL` → `NO_USABLE_STRATUM` →
`INSUFFICIENT_COVERAGE` → `ZERO_DENOMINATOR` → `PAGE_VIEW_SEMANTICS_CONTRADICTED`"
(7B plan §5.3 / §12 C-1; `metrics.py:1512–1523`). Therefore:

- Reaching `INSUFFICIENT_COVERAGE` or `ZERO_DENOMINATOR` guarantees
  `usable_sample_count > 0` — otherwise `NO_USABLE_STRATUM` would have fired first — so
  both counts are meaningful and must be returned.
- `ZERO_POPULATION` returns pre-loop; there is nothing to return.
- `ELIGIBLE_SET_TOO_SMALL` implies `total_eligible < 5`, so no stratum reached the
  usable minimum and both accumulated counts are genuinely `0`; the default is correct
  and must not be replaced by a stale value (there is none).
- `NO_USABLE_STRATUM` is **defined** by `usable_sample_count == 0`; `0` is the correct
  count.
- `PAGE_VIEW_SEMANTICS_CONTRADICTED` is unreachable in practice because a contradicted
  run-level status makes every observation quality-ineligible through Chunk 7A, so
  `total_eligible == 0 < 5` and `ELIGIBLE_SET_TOO_SMALL` fires first (7B plan §9.2,
  `test_quality_raw_contradicted_semantics_is_null`). It keeps the default `0`.

### 4.2 S1 — six-path expected counts

| # | Return path | Line | Early? | Accumulated before return | `usable_sample_count` returned | `eligible_population_count` returned |
|---|---|---|---|---|---|---|
| 1 | `METRIC_REASON_ZERO_POPULATION` | `:1527–1531` | pre-loop | none | `0` (default) | `0` (default) |
| 2 | `METRIC_REASON_ELIGIBLE_SET_TOO_SMALL` | `:1569–1573` | post-loop | `< 5` eligible ⇒ no usable stratum | `0` (default) | `0` (default) |
| 3 | `METRIC_REASON_NO_USABLE_STRATUM` | `:1574–1578` | post-loop | `usable_sample_count == 0` by definition | `0` (default) | `0` (default) |
| 4 | `METRIC_REASON_INSUFFICIENT_COVERAGE` | `:1579–1583` | post-loop | `> 0` (else #3) | **accumulated (> 0)** | **accumulated (> 0)** |
| 5 | `METRIC_REASON_ZERO_DENOMINATOR` | `:1584–1588` | post-loop | `> 0` (else #3) | **accumulated (> 0)** | **accumulated (> 0)** |
| 6 | `METRIC_REASON_PAGE_VIEW_SEMANTICS_CONTRADICTED` | `:1589–1593` | post-loop | unreachable (contradicted ⇒ #2) | `0` (default, defensive) | `0` (default, defensive) |

The two changed rows are #4 and #5. Rows #1–#3 and #6 keep the `_null_result` defaults;
S1 does not touch those call sites.

### 4.3 S2 — docstring sentence

Append to the `quality_raw` docstring, after the precedence-order sentence and before
"``rating_count`` never weights the formula.":

> ``usable_sample_count`` and ``eligible_population_count`` describe the quality-usable
> strata (the strata whose ``N_h / N`` terms build the coverage) and are returned even
> when ``.value`` is null; counts are never null (SRS §6.5 line 637).

### 4.4 S3 — tests extend existing nodes (no renames)

Node IDs are unchanged; markers and `tests/traceability.json` values are unchanged. The
choice of access path is fixed here so `test-author` has no freedom of interpretation:

- **`mfx.QUALITY_LOW_COVERAGE`** (`INSUFFICIENT_COVERAGE`). Its shape (7B plan §9.2;
  `tests/fixtures/metric_estimator_fixtures.py:557–570`): two strata, stratum 0
  `N_0 = 25` with 5 quality-eligible, stratum 1 `N_1 = 75` with 4 eligible (< 5);
  coverage `25 / 100 = 0.25 < 0.50`; total eligible `9 >= 5`, so only the coverage guard
  fires. Expected: `usable_sample_count == 5` (stratum 0 only),
  `eligible_population_count == 25` (`N_0` only).
  Assert `result = m.quality_raw(mfx.QUALITY_LOW_COVERAGE)` then
  `result.usable_sample_count == 5` and `result.eligible_population_count == 25`, and
  additionally `aggregate = m.compute_category_raw_metrics(mfx.QUALITY_LOW_COVERAGE, mfx.make_breadth_input(None, 100))`
  with `aggregate.usable_quality_sample_count == 5` — this pins the downstream copy at
  `metrics.py:1656`, which is the field the persisted row reads.
- **`mfx.QUALITY_ZERO_VISIBILITY`** (`ZERO_DENOMINATOR`). Its shape
  (`metric_estimator_fixtures.py:527–556`): 5 quality-eligible observations with
  explicit valid `product_page_views = 0` (age 70 ⇒ index `0.0`), one usable stratum,
  `N_h = 25`; coverage `1.0`; `sum(den_h) == 0.0`. Expected: `5` / `25`.
  Assert as above (`result.usable_sample_count == 5`,
  `result.eligible_population_count == 25`, and the aggregate
  `usable_quality_sample_count == 5`).
- **`mfx.QUALITY_ELIGIBLE_SET_TOO_SMALL`** (`ELIGIBLE_SET_TOO_SMALL`). Its shape
  (`metric_estimator_fixtures.py:598–...`): one stratum `N_h = 75`, `n_h = 4`, all four
  eligible, `4 < 5`. Expected: `0` / `0`. This pins that the fix does not leak upward.
  Assert `result.usable_sample_count == 0` and `result.eligible_population_count == 0`.
- **A locally-built `NO_USABLE_STRATUM` quality input**, built inline in
  `tests/test_metrics.py` with the existing helpers `mfx.make_category_input`,
  `mfx.make_stratum`, and `mfx.make_observation` (no new fixture symbol). Shape: two
  strata each with 3 quality-eligible observations (total `6 >= 5`), each stratum
  `3 < 5` ⇒ no quality-usable stratum; coverage `0.0`; both counts `0`. Build it inside
  the existing `test_quality_eligible_set_too_small_is_null` node (the only existing
  zero-count quality node) so no node ID is added, and assert
  `result.unavailable_reason == m.METRIC_REASON_NO_USABLE_STRATUM`,
  `result.usable_sample_count == 0`, `result.eligible_population_count == 0`.

`CategoryRawMetrics` has no `eligible_population_count` field (G3), so every
`eligible_population_count` assertion reads the `MetricResult` from `quality_raw(...)`.
The `usable_quality_sample_count` aggregate assertion is added only on the
`INSUFFICIENT_COVERAGE` node, where the frozen design names it; the `ZERO_DENOMINATOR`
node pins the same value through `quality_raw(...).usable_sample_count`.

## 5. Files touched

No file outside this table is touched.

| File | New/modified | Purpose |
|---|---|---|
| `src/niche_scout/metrics.py` | modified | S1: pass the two accumulated counts at the `INSUFFICIENT_COVERAGE` and `ZERO_DENOMINATOR` returns; S2: one docstring sentence. Nothing else. |
| `tests/test_metrics.py` | modified | S3: extend the three existing node IDs with the count assertions and add the inline `NO_USABLE_STRATUM` input to `test_quality_eligible_set_too_small_is_null`. No node renamed or added. |

**Not touched:** `tests/traceability.json` (no key added, changed, or removed),
`tests/fixtures/**`, `tests/test_enrichment.py`, `src/niche_scout/pipeline.py`,
`src/niche_scout/scoring.py`, `src/niche_scout/models.py`,
`src/niche_scout/database.py`, `src/niche_scout/report.py`, `src/niche_scout/cli.py`,
`src/niche_scout/config.py`, `src/niche_scout/sampling.py`,
`src/niche_scout/validation.py`, the collector modules, `src/niche_scout/tools/**`,
`pyproject.toml`, `config/**`, `Documents/interfaces/**`, `AGENTS.md`, `kilo.json(c)`,
`.kilo/`.

## 6. Typed signatures and null/edge behavior

### 6.1 `quality_raw` (signature unchanged; behavior changed on two null paths)

```python
def quality_raw(input: CategoryMetricInput) -> MetricResult
```

- `input` is a Chunk 7A `CategoryMetricInput`; no new parameter, no default-`0`
  parameter.
- Normal path: returns `MetricResult(value=numerator / denominator,
  usable_sample_count=<accumulated>, eligible_population_count=<accumulated>,
  eligibility_coverage=coverage, unavailable_reason=None)` (`:1594–1600`) — **unchanged**.
- `N == 0` (`METRIC_REASON_ZERO_POPULATION`): `value is None`, counts `0` / `0`,
  coverage `0.0` — **unchanged**.
- `ELIGIBLE_SET_TOO_SMALL`: `value is None`, counts `0` / `0`, coverage the computed
  value — **unchanged**.
- `NO_USABLE_STRATUM`: `value is None`, counts `0` / `0`, coverage the computed value —
  **unchanged**.
- `INSUFFICIENT_COVERAGE`: `value is None`, counts the accumulated quality-usable counts
  (> 0), coverage the computed value — **changed by S1**.
- `ZERO_DENOMINATOR`: `value is None`, counts the accumulated quality-usable counts
  (> 0), coverage the computed value (≥ the required threshold on this path) — **changed
  by S1**.
- `PAGE_VIEW_SEMANTICS_CONTRADICTED`: unreachable under the precedence order; keeps
  `value is None`, counts `0` / `0` — **unchanged**.
- Pure: no I/O, no clock; deterministic function of `input`.

### 6.2 `_null_result` (unchanged)

```python
def _null_result(
    reason: str,
    *,
    usable_sample_count: int = 0,
    eligible_population_count: int = 0,
    eligibility_coverage: float | None = None,
) -> MetricResult
```

Defaults stay `0` (`:1035–1036`). S1 supplies both keywords explicitly at two call sites;
the other four call sites are untouched.

### 6.3 `compute_category_raw_metrics` (unchanged)

`CategoryRawMetrics.usable_quality_sample_count` continues to equal
`quality.usable_sample_count` (`metrics.py:1656`); after S1 it is the accumulated count
on the two changed paths. `CategoryRawMetrics` gains no field and no
`eligible_population_count` (G3).

## 7. Test plan

No live network; all inputs are fixtures or locally-built typed inputs. Tests are
extended by `test-author` before the implementation (the two count assertions are the
required failing shape against the current code: they read `0` now and must read
`5`/`25`).

### 7.1 Node IDs, markers, traceability

`tests/traceability.json` is node-ID → `[LREQ...]`. All three keys exist today (G6) and
are unchanged.

| pytest node ID (unchanged) | `@pytest.mark.lreq` (unchanged) | `tests/traceability.json` value (unchanged) |
|---|---|---|
| `tests/test_metrics.py::test_quality_raw_null_below_required_coverage` | `LREQ-MET-090` | `["LREQ-MET-090"]` |
| `tests/test_metrics.py::test_quality_raw_zero_visibility_denominator_is_null` | `LREQ-MET-100`, `LREQ-TST-050` | `["LREQ-MET-100", "LREQ-TST-050"]` |
| `tests/test_metrics.py::test_quality_eligible_set_too_small_is_null` | `LREQ-MET-090` | `["LREQ-MET-090"]` |

No new or renamed node ID ⇒ **no `tests/traceability.json` change**. `test-author` and
`impl-deep` SHALL confirm this at implementation time by running
`python -m niche_scout.tools.validate_traceability` and by diffing the traceability
file (it must be byte-identical: the file is not a §5-touched file).

### 7.2 Assertions per node

- **`test_quality_raw_null_below_required_coverage`.** Keep the existing reason/coverage
  assertions (`:631–636`). Add:
  `result.usable_sample_count == 5`; `result.eligible_population_count == 25`;
  `aggregate.usable_quality_sample_count == 5` for
  `m.compute_category_raw_metrics(mfx.QUALITY_LOW_COVERAGE, mfx.make_breadth_input(None, 100))`.
- **`test_quality_raw_zero_visibility_denominator_is_null`.** Keep `:595–599`. Add
  `result.usable_sample_count == 5`; `result.eligible_population_count == 25`;
  `aggregate.usable_quality_sample_count == 5` for the same call with
  `mfx.QUALITY_ZERO_VISIBILITY`.
- **`test_quality_eligible_set_too_small_is_null`.** Keep `:613–615`. Add
  `result.usable_sample_count == 0`; `result.eligible_population_count == 0`; then build
  the inline two-strata/three-eligible `NO_USABLE_STRATUM` input and assert its
  `unavailable_reason == m.METRIC_REASON_NO_USABLE_STRATUM`,
  `usable_sample_count == 0`, `eligible_population_count == 0`.

### 7.3 Golden values

All count values are exact `int` assertions (not `pytest.approx`):
`5 / 25` for `QUALITY_LOW_COVERAGE` and `QUALITY_ZERO_VISIBILITY`, `0 / 0` for
`QUALITY_ELIGIBLE_SET_TOO_SMALL` and the inline `NO_USABLE_STRATUM` input. The existing
float assertions keep `abs=1e-9`.

### 7.4 No new end-to-end node

`tests/test_enrichment.py::test_finalize_agrees_with_chunk7b_compute_category_raw_metrics`
(`:736`) already asserts `raw.usable_quality_sample_count == final.usable_quality_sample_count`
(`:755`), and `test_assert_consistency_clean_run_returns_no_mismatches` (`:823`) covers
the post-write assertion. Adding an `INSUFFICIENT_COVERAGE` shape to the 6B fixture would
ingest artifacts outside this chunk's authorization; it is **not** done.

### 7.5 No touch — genuine-zero assertions

`tests/test_enrichment.py:723–730` and `:755–763` (and the comment at `:756–758`) are
correct genuine-zero assertions for fixtures with no quality-usable stratum. S3.

## 8. Definition of done (gate)

- **DoD-1 (offline suite).** `python -m pytest -q` reports `passed, 0 failed`; the exact
  command and verbatim output with real counts are recorded in `Documents/runs/chunk-20.md`.
- **DoD-2 (validators).** `python -m niche_scout.tools.validate_traceability`,
  `python -m niche_scout.tools.check_import_boundaries`,
  `python -m niche_scout.tools.check_scope_prohibitions`, and
  `python -m niche_scout.tools.check_secrets` all valid (exit 0).
- **DoD-3 (lint/format).** `ruff` per `pyproject.toml` over the two changed files; no new
  lint; a pre-existing deviation is reported PARTIAL with the unchanged lines named and a
  byte-exact baseline.
- **DoD-4 (traceability reconciliation).** No `tests/traceability.json` key added,
  changed, or removed. Evidence: `python -m niche_scout.tools.validate_traceability` exits
  0, plus a `git diff --stat -- tests/traceability.json` that is empty (the file is not in
  §5). The three keys named in §7.1 keep their existing values.
- **DoD-5 (prohibitions).** §9 holds: two files changed, all others byte-identical.
- **DoD-6 (records).** Plan and run log recorded; remaining obligations stay open (§11).
- No human live run is required. An operator re-render is optional and not part of this
  gate.

## 9. Prohibitions

- **Do not edit `_null_result`'s signature or defaults** (`metrics.py:1035–1036`), and do
  not pass counts at the four other `quality_raw` null returns.
- **Do not edit any file outside §5.** In particular `pipeline.py`, `scoring.py`,
  `models.py`, `database.py`, `report.py`, `tests/test_enrichment.py`, and
  `tests/fixtures/**` are not authorized.
- **Do not add, rename, or remove a pytest node ID.** Do not change
  `tests/traceability.json`.
- **Do not add a fixture symbol, a parameter, a config knob, a persisted field, or a
  dependency.**
- **Do not collapse null and zero**: the fix makes the count a true measured value on the
  two accumulation paths and leaves the true-zero paths at `0`; it never fabricates a
  value on a path where nothing accumulated.
- **Do not touch `metrics.py` imports, purity, or clock behavior**; the change is
  value-flow only.
- **No live network in development or tests.**

## 10. Routing

1. **`test-author`** — the §7 assertions first (they fail against the current code on the
   `INSUFFICIENT_COVERAGE`/`ZERO_DENOMINATOR` nodes). No fixture file, no traceability
   change.
2. **`impl-deep`** — the two-return change plus the docstring sentence. `impl-fast` is not
   suitable: the change sits on the frozen 7B `MetricResult` surface and the counts feed
   persisted `category_scores` and the evidence-grade minimum. Run pytest and the four
   validators and the traceability reconciliation.
3. **`spec-reviewer`** — review the plan, the diff, the tests, and the run-log evidence.

## 11. Residual risks and open obligations (recorded, never fixed here)

### 11.1 Regression proof (state in the run log)

No rank, evidence grade, or rankability status changes:

- Every category on the two changed paths has `quality_raw is None` ⇒ `component_q is
  None` (`scoring.py:496–502`): for `INSUFFICIENT_COVERAGE` through the coverage branch
  `:496–497`; for `ZERO_DENOMINATOR` (coverage `1.0`) through the
  `normalized.quality_raw is None` branch `:499–500`.
- `component_q is None` ⇒ `QUALITY_UNAVAILABLE` in `not_rankable_reasons`
  (`scoring.py:936–937`).
- `final_evidence_grade` returns `INSUFFICIENT` (`scoring.py:1580–1581`) before
  `minimum_component_sample_count` is read (`:1583`).
- `NOT_RANKABLE` precedes any count read (`scoring.py:1008–1009` pre-sensitivity;
  `:1650–1651` final).
- No existing test asserts `usable_quality_sample_count == 0` on either changed shape
  (prior pass grep over `tests/`; recorded in `Documents/runs/chunk-20.md` H4).

### 11.2 Residual risks (recorded)

- The count on the two paths now describes the **quality-usable** strata, matching the
  7B §5.4 RECOMMENDATION; it is not the count of all quality-eligible observations. This
  is the intended semantics (G1/G3) but is a non-normative plan-design choice and may be
  challenged by a future interface revision without changing `.value` or coverage.
- `SampleEvidenceFacts.minimum_component_sample_count` (`scoring.py:1288–1303`) takes the
  minimum of the three counts; raising the quality count from `0` to a true value can only
  raise (not lower) that minimum, and it is only read on categories that are not already
  `NOT_RANKABLE`. Recorded; no code change here.

### 11.3 Open obligations (recorded, never resolved here)

- **URI trailing-identifier extraction (`identity_mapping_rule 1.0.1`)** — inferred, not
  verified against a real Coveo response; no captured response exists.
- **OI-6 — CSRF/session sufficiency** — has no owning chunk; neither reopened nor closed.
- **`runs.taxonomy_sha256` empty-hash rejection** — owner Chunk 10; not touched.
- **`tests/AGENTS.md` traceability orientation** — prose says LREQ-keyed; the committed
  file is node-ID-keyed. Out of scope (chunk-19 §12.2 records the same); follow the
  committed file.
- **`min_age_days_for_rate` coupling in `quality_observation_eligibility`
  (`metrics.py:544–638`)** — non-goal. It calls `age_normalized_page_view_index` at the
  module default `30` (`metrics.py:620–626`) while finalize/7B use the config value;
  divergence would flag check B, but adding a parameter changes a frozen 7A interface.
  Not changed here.

## 12. Open questions

None. The diagnosis is frozen by `Documents/runs/chunk-20.md`; the two changed returns
and the four unchanged ones are fixed by the documented precedence order; the test host
for the inline `NO_USABLE_STRATUM` input is confined by the "no new node ID" constraint
to `test_quality_eligible_set_too_small_is_null` (§4.4).