# Chunk 7B — run log (Sample-aware raw estimators)

Started 2026-09-20. Branch: `chunk-7B` (created from `chunk-7A` @ `02cac21`). Tree clean at preflight.

## Preflight

| Check | Result |
|---|---|
| Working tree | clean (`git status` → "nothing to commit, working tree clean") |
| Branch | created `chunk-7B` from `chunk-7A` HEAD `02cac21` (the 7A gate tip) |
| Prerequisite Chunk 0 | `Documents/interfaces/chunk-00.md` → `Status: VERIFIED` |
| Prerequisite Chunk 1 | `Documents/interfaces/chunk-01.md` → `Status: VERIFIED` |
| Prerequisite Chunk 2 | `Documents/interfaces/chunk-02.md` → `Status: VERIFIED` |
| Prerequisite Chunk 3 | `Documents/interfaces/chunk-03.md` → `Status: VERIFIED` |
| Prerequisite Chunk 4A | `Documents/runs/chunk-4A.md` ends `GATE: PASSED`; interface `Status: VERIFIED` |
| Prerequisite Chunk 4B | `Documents/runs/chunk-4B.md` ends `GATE: PASSED`; interface `Status: VERIFIED` |
| Prerequisite Chunk 5 | `Documents/interfaces/chunk-05.md` → `Status: VERIFIED` |
| Prerequisite Chunk 7A | `Documents/runs/chunk-7A.md` ends `GATE: PASSED`; interface `Status: VERIFIED` |
| Frozen plan | none yet — planner dispatch required |
| Routing | test-author first, then `impl-deep` (chunk-lead routing table) |

## Stage log

| Stage | Status | Evidence / notes |
|---|---|---|
| Preflight | DONE | See table above. |
| Plan — first dispatch | BLOCKED | `chunk-planner` wrote a full draft plan (`Documents/plans/chunk-7B-sample-aware-raw-estimators.md`) but returned `STATUS: BLOCKED` on Q-1 (contradicted page-view-semantics detection: chunk-05 §5.8 / chunk-7A §5 assign detection to 7B; the dependency-map 7B scope list omits it; SRS supplies no rule), plus Q-2..Q-6. |
| Plan — adjudication (user-delegated) | DONE | Per the user's instruction, a read-only `explore` agent adjudicated Q-1..Q-6 against the SRS, dependency map, and frozen interfaces, and surfaced one new SRS-internal tension (C-1: §6.5 "D and Q unavailable" vs LREQ-MET-090/100 nulling `QualityRaw`). Outcomes: Q-1 → (a) consume the caller-supplied status, no detection function (RECOMMENDATION; precedence decides the pure-function half; interfaces' "7B detects" wording reconciled out of lean-build scope). Q-2 → (a) all usable observations, weight `N_h/n_h` (SRS-backed). Q-3 → (a) `QualityRaw` null below `MIN_REQUIRED_COMPONENT_COVERAGE`, D/R raw not nulled (SRS-backed). Q-4 → (a) `BreadthRaw` always a total count, never null; Competition by Chunk 8 (SRS-backed). Q-5, Q-6 → documented RECOMMENDATIONs. C-1 → RECOMMENDATION (stricter reading; precedence unchanged). |
| Plan — freeze | DONE (FROZEN) | `chunk-planner` applied all adjudications in place: Q-1 operator-resolution note in the header and §12, §5 reads as the intended interface body, Q-2/3/4 resolved SRS-backed, Q-5/Q-6 relabelled RECOMMENDATIONs, C-1 recorded, `Status: FROZEN`. No code, tests, or interface doc written. |
| Plan commit | DONE | `9dfe0f2` — `chunk-7B: plan` (plan + run log). |

### Tests (step 4)

The `test-author` dispatches returned empty results repeatedly (4 dispatches, including one PONG probe that worked); the lead therefore split the authoring into focused batches, each of which wrote a real file. Directory-level `tests/fixtures/__init__.py` edits mutate `tests/traceability.json`'s sibling artifacts, so they were done in a final small batch after the test file was complete.

| Item | Result |
|---|---|
| Fixture module | `tests/fixtures/metric_estimator_fixtures.py` (new) — data only, plan §9.2 vectors plus boundary fixtures (DEMAND_NO_USABLE_STRATUM, DEMAND_NO_USABLE_INDEX, DEMAND_MEDIAN_EXACT_HALF, DEMAND_PARTIAL_COVERAGE, DEMAND_INELIGIBLE_EXCLUDED, RECENT_USABILITY_BOUNDARY, RECENT_MISSING_DATES, QUALITY_ELIGIBLE_SET_TOO_SMALL). Imports the not-yet-existing 7B names, so collection fails until implementation lands (expected). |
| Test module | `tests/test_metrics.py` (new) — 40 nodes (the 39 plan §9.3 rows plus `test_quality_raw_ineligible_observations_are_excluded`, lead-added; the plan row was appended with a dated note). Every node carries its `@pytest.mark.lreq(...)`. |
| Fixture re-export | `tests/fixtures/__init__.py` — `metric_estimator_fixtures` added to imports and `__all__`. |
| Traceability | `tests/traceability.json` — 40 appended `tests/test_metrics.py::` entries (append-only; the previously last entry gained its comma); 244 pre-existing entries untouched. |
| Lead verification (step 4) | `python -m pytest tests/test_metrics.py -q` → **1 collection error**: `ImportError: cannot import name 'BreadthMetricInput' from 'niche_scout.metrics'`. `python -m pytest tests -q` → **8 collection errors**, all the same root `ImportError`. Expected missing-implementation shape after the 7B implementation lands; the import chain is `tests/* → fixtures/__init__.py → metric_estimator_fixtures.py → niche_scout.metrics` (no syntax errors). |
| Plan corrections made by the lead | (a) plan §9.2 `SEMANTICS_CONTRADICTED` bullet corrected: the §5.3 reason precedence fires before the contradicted reason, so the test asserts `eligible_set_too_small`; the fixture comment was corrected to match. (b) plan §9.2 gained the boundary-fixture bullets the nodes reference, and §9.3 gained the added node row. (c) `DEMAND_MEDIAN_EXACT_HALF` comment corrected (weight `N_h/n_h = 5.0`, `T = 50`; expected `5.5` unchanged). |

### Implementation and lead verification (steps 5–6)

| Item | Result |
|---|---|
| `impl-deep` dispatch | DONE. Added the 7B section to `src/niche_scout/metrics.py` (+~990 lines, additive): the typed inputs/results, `METRIC_AGGREGATE_UNAVAILABLE_REASONS`, and the 13 public functions. Chunk 0/7A names untouched. |
| Lead `pytest tests/test_metrics.py -q` | **40 passed, 0 failed** (re-run by the lead). |
| Lead `pytest tests -q` | **293 passed, 0 failed** (re-run by the lead after formatting). |
| Lead `check_import_boundaries` | exit 0 — "Import boundaries valid for metrics.py, scoring.py". |
| Lead `validate_traceability` | exit 0 — "Traceability valid: 7 Chunk 0 requirements mapped, 207 matrix nodes, 89 defined LREQ IDs" (7 pre-existing unmarked tests noted; unchanged from 7A). |
| Lead `ruff check` | "All checks passed!" on `metrics.py`, `test_metrics.py`, the fixture module, and `tests/fixtures/__init__.py`. |
| Lead `ruff format` | Reformatted `tests/test_metrics.py` and `tests/fixtures/metric_estimator_fixtures.py` (whitespace only); then `--check` → "4 files already formatted". Suite re-run green afterwards. |

### Review (step 7)

| Item | Result |
|---|---|
| `spec-reviewer` round 1 (first dispatch) | Truncated result with no `VERDICT` (it hit a bash denial and stopped mid-turn) — treated as a failed dispatch, retried once. |
| `spec-reviewer` round 1 (retry) | `VERDICT: PASS`, no Blocker, no Major. It read `metrics.py` (all 1637 lines), `test_metrics.py`, the fixture module, `traceability.json`, the plan, SRS §6.5/§7.1–7.5/§14/App. A, the interfaces, and `check_import_boundaries.py`. It re-derived 40 nodes / 40 appended entries by query. Its pytest/ruff runs were denied by the environment and labelled `UNVERIFIED`; the lead had already run them green. |
| Round-1 Minors | (1) `quality_min_rating_count` declared/validated but never consumed (rating-count gate is in 7A) — docstring clarified, field retained; (2) stale "raises ImportError until implementation lands" note in the fixture docstring — **not fixed** (Minor, no loop); (3) no demand-path explicit-valid-zero test — **added**; (4) `_null_result` default-`0` count parameters contradict plan §11's letter — **not fixed** (internal convenience following plan §5.4; Minor, no loop). |
| Review-fix commit | `7a64e2b` — `chunk-7B: review fixes`. Lead re-ran: `pytest tests -q` → **294 passed**; `check_import_boundaries` → exit 0; `validate_traceability` → exit 0; `ruff check` → "All checks passed!"; `ruff format --check` → "4 files already formatted". |

**Minors carried forward (no fix round):**
1. `tests/fixtures/metric_estimator_fixtures.py` module docstring still says the module raises `ImportError` until the implementation lands; the implementation has landed. Stale note only.
2. `src/niche_scout/metrics.py` `_null_result` uses default-`0` count parameters; plan §11's letter forbids default-0 parameters on metric inputs, which these are not (they are the null-path `MetricResult` counts per plan §5.4).

### Gate — Chunk 7B

Gate bullets walked one by one from `Documents/requirements-dependency-map.md` §3
Chunk 7B (Gate section, lines 837–844), on commit `7a64e2b` (working tree clean at
verification; interface + run log committed after).

| Gate bullet | Result | Evidence |
|---|---|---|
| 1. All estimators are pure and use the Chunk 7A eligibility results | PASS | `python -m niche_scout.tools.check_import_boundaries` → exit 0, "Import boundaries valid for metrics.py, scoring.py". AST imports of `src/niche_scout/metrics.py` (`:17–31`): `math`, `collections.abc`, `dataclasses`, `datetime`, `.models`, `.validation` — no I/O, network, `sqlite3`, `json`, or `scoring`. Estimators consume 7A: `_observation_index` → `age_normalized_page_view_index` (`:947–954`), `_age_value` → `age_days_exact` (`:935–938`), `_quality_observation_index` → `quality_observation_eligibility` (`:992–1003`), `stratum_is_usable` (`:1300`, `:1535`, `:1146`). `test_estimators_are_pure_no_forbidden_imports_or_clock` (LREQ-ARCH-010/020) passes; `test_estimators_consume_chunk_7a_index_eligibility` (LREQ-MET-040/-030/-080/-100) passes. |
| 2. Raw estimators are implemented in `metrics.py`; `scoring.py` does not own raw metric calculation | PASS | All 13 public estimators/aggregators are defined in `metrics.py` (`:1159–1637`). `git diff --name-only 02cac21..HEAD` shows the only `src/` change is `src/niche_scout/metrics.py`; `src/niche_scout/scoring.py` is unchanged and contains only `ScoringInput`/`ScoreResult`/`SensitivityResult` (read: 52 lines, no metric calculation). |
| 3. Weighted medians use the exact boundary rule | PASS | `weighted_median` (`:1178–1230`): sort key `(value, insertion_index)` (`:1211`); first cumulative weight `> T/2` returns the value (`:1224–1225`); cumulative weight exactly `== T/2` with a next value returns `(value + next)/2` (`:1226–1229`); empty/zero total → `None` (`:1214–1215`). Both `demand_median_raw` (`:1357`) and `median_age_raw` use it. Tests: `test_weighted_median_exact_half_averages_with_next` (three `1.5` vectors), `test_demand_median_exact_half_boundary` (`5.5`), `test_median_age_exact_half_boundary` (`75.0`/`400.0`/`30.0`), `test_demand_explicit_zero_page_views_are_usable` (exact-half `0.5`). |
| 4. Quality uses `N_h / n_h`, not a simple sample average | PASS | `quality_raw` (`:1540–1551`): `weight = stratum_expansion_weight(N_h, n_h)`; `numerator += weight * sum((rating/5)*index)`; `denominator += weight * sum(index)`; `:1581` returns `numerator / denominator`. `stratum_expansion_weight` (`:1159–1175`) = `N_h / n_h` with `int >= 1` guards. `test_quality_raw_uses_n_h_over_n_h_weights` → `0.75` with weight `2.0`; `test_quality_coverage_not_renormalized` (coverage `0.25` ≠ count fraction `5/9`). |
| 5. Zero-population metrics are null where specified and coverage is zero where specified | PASS | Every sample-derived estimator returns `METRIC_REASON_ZERO_POPULATION` with `value=None` when `N == 0` before any `N_h / N`: demand `:1283–1287`, demand median `:1336–1340`, recent share `:1402`, median age `:1445`, quality `:1513–1517`. Coverage helpers return `0.0` when `N == 0`: `_demand_coverage` (`:1044–1045`), `_quality_coverage` (`:1142–1143`), `_recent_coverage`; `_coverage_value` (`:1020–1022`); `_stratum_weight` raises if `N == 0` (`:920–921`) so `N_h / N` is unreachable there. `test_zero_population_bundle_has_null_raws_and_zero_coverages`, `test_demand_coverage_is_zero_for_zero_population`, `test_recent_zero_population_is_null_and_coverage_zero`, `test_quality_zero_population_is_null_and_coverage_zero` pass; `ZERO_POPULATION` breadth is `0` / `verified_total_count` / `complete`. |
| 6. Sample fraction remains distinct from stratum eligibility coverage | PASS | No `sample_fraction` is computed or returned anywhere in `metrics.py` (AST/grep: no such symbol). Coverage functions sum `N_h / N` (`_stratum_weight` `:910–922`) and clamp to `[0,1]` (`_coverage_value` `:1013–1022`), explicitly "never renormalizes to the sampled assets" (`:1016–1018`); `demand_stratum_eligibility_coverage` docstring (`:1262–1264`) states it is distinct from `sample_fraction` and never computes it. `test_demand_coverage_is_distinct_from_sample_fraction` asserts coverage `1.0` vs the enriched/discovered fraction `0.5`. |

Supporting evidence: `python -m pytest tests/test_metrics.py -q` → **41 passed**;
`python -m pytest tests -q` → **294 passed, 0 failed**; `validate_traceability` →
exit 0 (7 Chunk 0 requirements, 207 matrix nodes, 89 defined LREQ IDs; 7
pre-existing unmarked tests); `check_import_boundaries` → exit 0;
`ruff check` → "All checks passed!"; `ruff format --check` → "4 files already formatted".

**GATE: PASSED**

### Interface produced

`Documents/interfaces/chunk-7B.md` (Status: VERIFIED) created from the frozen plan §5.

### Open items carried forward (not gate failures)

- Reviewer Minors 1–2 above.
- `quality_min_rating_count` is inert for 7B (documented); the rating-count gate is
  Chunk 7A's.
- Q-1: contradicted page-view-semantics detection is out of the lean-build scope;
  7B consumes the caller-supplied run-level status.
- The aggregate reason-string spelling is a `RECOMMENDATION`; the outcome categories
  are SRS-backed.
- `raw.breadth_raw` is stored as `float` (frozen `RawMetricBundle` annotation) with
  an integral value.
- Chunk 7B is committed on `chunk-7B` and fast-forwarded into `chunk-7A`; downstream
  merging is the operator's call.

### Completion verification (2026-09-21) — post-gate defect found and fixed

The user asked the lead to confirm chunk 7 completeness and correctness. An independent
`spec-reviewer` re-review of the whole of Chunk 7 (7A + 7B) returned `VERDICT: FAIL` with
two real count defects that the 7B gate's evidence had not caught, because the fixtures
used all-strata-usability cases:

1. **[Blocker] `usable_recent_supply_sample_count`** (`compute_category_raw_metrics`) was
   taken from `median_age_raw(...).usable_sample_count`, which counts usable dated
   observations in **every** stratum. SRS-lean.md §7.4 (LREQ-MET-080, read: lines 789–793)
   requires the sum over the Recent-Supply-**usable** strata; plan §9.2
   `RECENT_USABILITY_BOUNDARY` expects `5`, the code returned `9` (`4 + 5`).
2. **[Major] `usable_demand_sample_count`** had the same defect via
   `demand_median_raw(...).usable_sample_count`; plan §5.2 (CategoryRawMetrics docstring)
   requires observations contributing to strata that satisfy the usable minimum. For
   `DEMAND_PARTIAL_COVERAGE` the code returned `9`, the required value is `5`.

Fix round (one), per chunk-lead step 7:

| Item | Result |
|---|---|
| `test-author` (tests strengthened first) | `tests/test_metrics.py` nodes `test_demand_coverage_sums_usable_stratum_weights` and `test_recent_supply_usability_minimum_boundary` gained the aggregate count assertions (5 each); no node added or renamed. Pre-fix run: **2 failed (`assert 9 == 5`), 39 passed** — the required missing-fix failure shape. |
| `impl-deep` fix | `src/niche_scout/metrics.py` only: `usable_demand_sample_count` now from `demand_per_asset_raw(input).usable_sample_count`, `usable_recent_supply_sample_count` from `recent_share_raw(input).usable_sample_count` (`compute_category_raw_metrics`, `:1654–1655`); the three caller int parameters (`min_age_days_for_rate`, `quality_min_rating_count`, `quality_min_eligible_assets`) now validate through `_require_positive_int` (`:818`), rejecting `bool`/non-int; `weighted_median` accumulates `total_weight` in a plain `+=` loop (`:1225–1227`) so the exact-half comparison matches the walk. No estimator formula, public signature, or symbol name changed. |
| Lead re-verification | `python -m pytest -q` → **294 passed**; `python -m pytest tests/test_metrics.py -q` → **41 passed**; `validate_traceability` → exit 0 (7 Chunk 0 requirements, 207 matrix nodes, 89 defined LREQ IDs; 7 pre-existing unmarked tests); `check_import_boundaries` → exit 0; `ruff check` on the four chunk files → "All checks passed!"; `ruff format --check` → "4 files already formatted". |
| Re-review | Round 2 returned `VERDICT: FAIL` on an evidence-availability ground only: gate bullet 1's "uses the Chunk 7A eligibility results" half could not be re-derived because the reviewer's marker grep hit its 30-match cap and it could not execute any command (bash denied). It confirmed both defective counts now come from `stratum_is_usable`-filtered estimators (`metrics.py:1654–1655`), the `bool` guard, the weighted-median change, 41 nodes with 41 matching traceability entries, and that the strengthened tests are exact-int assertions that fail on the pre-fix code. The lead closed that gap directly: node `test_estimators_consume_chunk_7a_index_eligibility` (`tests/test_metrics.py:851–867`) proves 7A consumption (draft, age `29 < 30`, negative views, `None` views, identity mismatch all excluded; `3.0` not `1.5`), and `test_estimators_are_pure_no_forbidden_imports_or_clock` (`:933`) plus `check_import_boundaries` exit 0 cover purity. No code change was required by round 2. |
| Interface correction | `Documents/interfaces/chunk-7B.md:218` said 40 analytical nodes; the file holds 41 (counted by `grep '^def test_'`, 41 matches in `tests/test_metrics.py`, and 41 `tests/test_metrics.py::` entries in `tests/traceability.json`). Corrected to 41. |
| Fixture docstring | `tests/fixtures/metric_estimator_fixtures.py:34–36` no longer claims the module raises `ImportError` until the implementation lands. |
| Review-fix commit | `581810a` — `chunk-7B: review fixes (...)`. |

**Gate re-walk after the fix: all six 7B bullets still have evidence; the two corrected
fields now satisfy SRS §7.4 and plan §5.2. GATE: PASSED (re-affirmed).**

Post-fix open Minors (no further loop, reported for the user):

- `.scratch/` extracts created read-only by the first reviewer could not be verified as
  present or absent by the lead (they are git-ignored); the directory is not in the repo
  history and nothing was staged from it.
- `tests/test_metrics.py` has an assigned-but-unasserted `dates`/`ages` computation in one
  node; cosmetic.
- The quality-side partial-usability count is pinned only through all-usable or
  full-coverage fixtures.
