# Chunk 25 — Minimum-usable-samples default re-baseline (D2)

Status: FROZEN (operator answered OQ-1/OQ-2 "go with the recommendation" on
2026-09-28; §8 is resolved).
Chunk id: `chunk-25` (remediation/follow-on; no §3/§4 dependency-map row —
chunk-14/24 precedent).
Run log: `Documents/runs/chunk-25.md`.
Prerequisite: chunk-24, `GATE: PASSED` (`Documents/runs/chunk-24.md:299`).
Declared boundary: `Documents/plans/chunk-24-systematic-strata.md` §1.3 and
`Documents/interfaces/chunk-24.md` §14.4 (D2 was explicitly out of chunk-24).

This plan changes exactly one policy default — `MIN_USABLE_SAMPLES_PER_STRATUM`
5 → 1 — and re-baselines every downstream coverage/evidence/rankability output
and golden vector, plus the SRS text. It changes no formula, weight, threshold,
partition, sampling allocation, or discovery behavior.

Provenance labels used below: **read** = file opened and quoted; **counted** =
queried by tool with the method stated; **model** = analytic inference, not run.

---

## 1. Scope and out of scope

### 1.1 In scope

1. `src/niche_scout/models.py:46`:
   `MIN_USABLE_SAMPLES_PER_STRATUM: int = 5` → `= 1`.
2. `config/default.toml:22`: `min_usable_samples_per_stratum = 5` → `= 1`.
3. `tests/fixtures/config_fixtures.py:68` (`DEFAULT_TOML_BODY`) and `:116`
   (`DEFAULT_TOML_VALUES`): `min_usable_samples_per_stratum` 5 → 1, so the
   default-policy fixture mirrors the shipped default (operator-confirmed, OQ-1).
4. Re-baseline of every golden vector / expected output whose *default-policy*
   result depends on per-stratum usability (§4).
5. SRS text edits S1–S5 in `Documents/SRS-lean-v2.md` only (§3).

`MIN_USABLE_SAMPLES_PER_STRATUM` is a caller/policy parameter with a default;
lowering it changes no wiring: `metrics.stratum_is_usable` (`metrics.py:530-547`),
the `CategoryMetricInput` field default (`metrics.py:804`), the four
`finalize_stratum_counts` / `assert_finalization_consistency` defaulted
parameters (`pipeline.py:1662, 1924, 2123, 2310`), `config.py:59`, and the
`usable:<min>` token (`pipeline.py:1637-1653`) all read the same constant
(**read**).

### 1.2 Explicitly NOT in this chunk

- No change to `SAMPLE_STRATA`, `SAMPLE_PER_STRATUM`,
  `ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY`, `SAMPLING_RULE_VERSION`,
  `SCHEMA_VERSION`, or the chunk-24 systematic partition.
- No change to `QUALITY_MIN_RATING_COUNT`, `QUALITY_MIN_ELIGIBLE_ASSETS`,
  `MIN_REQUIRED_COMPONENT_COVERAGE`, `STRONG_COMPONENT_COVERAGE`,
  `MIN_AGE_DAYS_FOR_RATE`, `RECENT_WINDOW_DAYS`, or any scoring weight.
- No formula change: `stratum_is_usable`, `demand_per_asset_raw`,
  `demand_median_raw`, the three `*_stratum_eligibility_coverage` estimators,
  `quality_raw`, evidence grading, and rankability keep their exact SRS rules
  (SRS §7.2/§7.4/§7.5/§9); only the default minimum they compare against moves.
- No change to `metrics.py`, `scoring.py`, `pipeline.py`, `database.py`,
  `report.py`, `config.py`, `collector*.py`, or `cli.py`.
- No change to persisted schema: `stratum_statistics_json` remains the frozen
  ten-key set (`database.py:2050-2061`); only its `eligibility_rule` /
  `usable_status` *values* change under the new default.
- No database migration, no run/history features, no new warning code.

---

## 2. Exact source changes

| File:line | Current | Change |
|---|---|---|
| `src/niche_scout/models.py:46` | `MIN_USABLE_SAMPLES_PER_STRATUM: int = 5` | `= 1` |
| `config/default.toml:22` | `min_usable_samples_per_stratum = 5` | `= 1` |
| `tests/fixtures/config_fixtures.py:68` | `min_usable_samples_per_stratum = 5` | `= 1` |
| `tests/fixtures/config_fixtures.py:116` | `"min_usable_samples_per_stratum": 5` | `1` |

No other source edit is required. The following are the propagation points and
are **not** edited (they import the constant or forward the parameter):

- `src/niche_scout/config.py:30,59` (import + `IN_CODE_DEFAULTS` entry).
- `src/niche_scout/metrics.py:25,533,804` (import + defaults of
  `stratum_is_usable` and `CategoryMetricInput`).
- `src/niche_scout/pipeline.py:85,1662,1924,2123,2310` (import + defaulted
  parameters) and `pipeline.py:1637-1653, 1774-1789, 1798-1803`
  (`_component_eligibility_rule` token `usable:{min}`, rule assembly,
  `usable_status`); `pipeline.py:2248+` `verify_persisted_sampling`.
- `src/niche_scout/database.py:2050-2061` (`STRATUM_STATISTICS_KEYS`).

Behavioural consequences (all **model**, from the formulas, to be confirmed by
the re-baselined tests):

- A stratum with `u_h >= 1` is now usable. At the default, a stratum is unusable
  **iff** `u_h == 0`.
- The `eligible`-set guard `usable_quality_sample_count >= QUALITY_MIN_ELIGIBLE_ASSETS`
  (`QUALITY_MIN_ELIGIBLE_ASSETS = 5`, unchanged) still precedes the
  no-usable-stratum reason; at default 1 the quality `NO_USABLE_STRATUM` reason
  becomes reachable only with an explicit `min_usable_samples_per_stratum >= 2`
  (see §4.3), so the floor-branch tests pin the former default explicitly.

---

## 3. Enumerated SRS edits (`Documents/SRS-lean-v2.md` only)

Editable file is **`Documents/SRS-lean-v2.md`** (Lean 1.0.2 at read time, header
line 10). `Documents/SRS-lean.md` is retired/absent; historical documents that
cite it (e.g. `tests/AGENTS.md`, older plans) are not edited here. The
implementation stage applies S1–S5 under the chunk-24 operator authorization
(`Documents/runs/chunk-24.md:18-31, 115-126, 241-255`). If the `edit` tool is
denied on `SRS-lean-v2.md` too, that is a **stop-and-surface**, never a
workaround (chunk-24 hit a deny on the retired path). Line refs are current
pre-edit lines (**read**).

| # | Section | Current lines | Edit |
|---|---|---|---|
| S1 | §5.1, `LREQ-SMP-030` constant block | 442-447 | `MIN_USABLE_SAMPLES_PER_STRATUM = 5` → `= 1`. Leave the other three constants and the `ENRICHMENT_SAMPLE_SIZE = STRATA * PER_STRATUM` identity unchanged. |
| S2 | §14 Configuration reference | 1319 | Row `MIN_USABLE_SAMPLES_PER_STRATUM | 5 | Yes | Stratum evidence minimum.` → Default `1`. |
| S3 | Revision history | after line 20 | Add row: `| Lean 1.0.3 | Lowers the default MIN_USABLE_SAMPLES_PER_STRATUM from 5 to 1 (SRS §5.1, §14), re-baselining per-stratum usability, the three stratum eligibility coverages, the usable component sample counts, evidence grades, and rankability for runs scored under the default policy. No formula, weight, partition rule, or other constant changes. |` |
| S4 | Header + status | 10, 24-31 | Header `Version` → `Lean 1.0.3`; add one sentence to the "Document status and relationship to the parent SRS" paragraph stating Lean 1.0.3 supersedes Lean 1.0.2 and its only change is the §5.1/§14 default. |
| S5 | §5.1, after the constant block | after 447 | Add one sentence: at the default, the minimum is an inclusive floor `u_h >= MIN_USABLE_SAMPLES_PER_STRATUM`, so a stratum with zero usable observations stays unusable and coverage excludes its population weight. (Derived from §7.2/§7.4/§7.5; states no new rule.) |

Versioning decision (**read** basis): SRS §5.1:455-457 lists the changes that
require a new sampling-rule version — sample size, stratum count, per-stratum
allocation, or the stratum partition rule. `MIN_USABLE_SAMPLES_PER_STRATUM` is
not in that list and SRS §14 marks it `Configurable = Yes` (line 1319); the
change is therefore a config-default change plus an SRS revision (S3/S4), **not**
a `SAMPLING_RULE_VERSION` bump. Operator answered OQ-2 (2026-09-28): **no bump** —
only usability-derived outputs change (`usable:<min>`, coverages, counts,
evidence grades, rankability); sampling offsets and selection digests are
untouched.

No other SRS text requires a numeric edit: every §7.2/§7.4/§7.5/§9 occurrence of
the minimum references the named constant (SRS-lean-v2.md:721-730, 818-828,
841-854), so the formulas stay literally correct after S1.

---

## 4. Test / fixture re-baseline list

Counting/provenance: node IDs below are **read** from the test files named;
occurrence counts are **counted** with grep and are *matches*, not expanded
parametrized node IDs. No expanded `pytest --collect-only` count is claimed
(that query was not run; it is an implementation-stage obligation in §4.4/§5).
No node ID is renamed; a node keeps its ID and only its expected values /
docstring change.

### 4.0 Grounded baseline (read from `runtime/niche_scout.sqlite3`)

Lead-verified from the in-repo database (not golden vectors; goldens come from
fixtures and recomputed expected values):

- Latest run `run-2026-09-28T05:59:50.085042+00:00`; persisted
  `sampling_rule_version = 1.0.0`; config snapshot
  `min_usable_samples_per_stratum = 1`, `quality_min_rating_count = 3`.
- Quality usability at floor 1: **53/96 strata usable, 43 unavailable**.
- `quality_stratum_eligibility_coverage >= 0.50`: **13/24 categories at floor 1
  vs 2/24 at floor 5**; **16 categories strictly worse at floor 5**.
- Floor-1 persisted outputs: `evidence_grade` {insufficient 11, weak 11,
  moderate 2}; `rankability` {not_rankable 11, provisional 11, rankable 2};
  `eligibility_rule = demand=usable:1;recent=usable:1;quality=usable:1`.

These confirm the direction and magnitude of the re-baseline (coverage and
grades rise when the floor drops) but are a single-run observation, not
deterministic fixtures. They are corroboration for §4.1/§4.5, not expected
values for any test.

### 4.1 Exact re-baselines (default-policy outputs)

| Node ID (file) | LREQ | Old → New |
|---|---|---|
| `tests/test_contracts.py::test_sampling_constants_contract` | LREQ-SMP-030 | `models.MIN_USABLE_SAMPLES_PER_STRATUM == 5` → `== 1` (line 565). |
| `tests/test_contracts.py::test_status_values_and_mandatory_fields_are_typed` | LREQ-SMP-030 | `REQUIRED_CONSTANTS["MIN_USABLE_SAMPLES_PER_STRATUM"]` 5 → 1 (line 237). |
| `tests/test_contracts.py::test_formula_test_conventions` | LREQ-TST-010 | `boundary = models.MIN_USABLE_SAMPLES_PER_STRATUM; assert boundary == 5` → `== 1` (lines 788-789); `boundary - 1 < boundary <= boundary` still holds. |
| `tests/test_validation.py::test_stratum_is_usable_at_minimum_boundary` | LREQ-MET-030 | `dfx.STRATUM_USABLE_VECTORS` re-baselined from `(0,F),(1,F),(2,F),(3,F),(4,F),(5,T),(6,T)` to `(0,F),(1,T),(2,T),(3,T),(4,T),(5,T),(6,T)`; update the vector comment ("at the default minimum 5" → "at the default minimum 1") in `tests/fixtures/date_eligibility_fixtures.py:253-263`. The explicit-parameter asserts at 1726-1728 are unchanged. |
| `tests/test_metrics.py::test_demand_coverage_sums_usable_stratum_weights` | LREQ-MET-060 | `DEMAND_PARTIAL_COVERAGE` **now fully usable**: coverage `0.75` → `1.0`; `usable_demand_sample_count` `5` → `9` (u_0=5 + u_1=4). Docstring lines 248-253 re-worded. |
| `tests/test_enrichment.py::test_finalize_stratum_counts_from_observations` | LREQ-SMP-080 | Uses `ef.FINALIZATION_USABLE_STATUS` (fixture §4.2), so it follows the fixture change. |
| `tests/test_enrichment.py::test_finalize_usable_status_and_eligibility_rule_present` | LREQ-SMP-080 | `final.usable_status` → `"usable"`; `fields["quality"]` → `"usable:1"` (was `METRIC_REASON_NULL`); `fields["recent"]` → `usable:1` (via `MIN_USABLE_SAMPLES_PER_STRATUM`); all-usable literal `"demand=usable:5;recent=usable:5;quality=usable:5"` → `usable:1` each (lines 674-704). |
| `tests/test_enrichment.py::test_finalize_category_counts_equal_sum_over_usable_strata` | LREQ-SMP-080 | `(usable_demand, usable_recent_supply, usable_quality)` `(0, 5, 0)` → `(4, 5, 3)` (lines 793-795); the `usable_sum` helper reads the constant so its own value is unchanged in form. |
| `tests/test_enrichment.py::test_finalize_agrees_with_chunk7b_compute_category_raw_metrics` | LREQ-SMP-080 | Tuple `(0, ef.FINALIZATION_U_RECENT, 0)` → `(4, 5, 3)` (lines 824-828); docstring lines 821-823 re-worded. |
| `tests/test_enrichment.py::test_assert_consistency_clean_run_returns_no_mismatches` | LREQ-SMP-080 | Tuple `(0, ef.FINALIZATION_U_RECENT, 0)` → `(4, 5, 3)` (lines 902-906); docstring 891-893. |
| `tests/test_enrichment.py::test_finalize_enrichment_non_default_policy_is_self_consistent` | LREQ-SMP-080, LREQ-MET-090 | "defaults (M=5)" is now M=1 → defaults `(4,5,3)`; keep a `min_usable_samples_per_stratum=5` call for the `(0,5,0)` case. Recommended shape: defaults `(4,5,3)`, explicit `min=1` `(4,5,3)`, explicit `min=5` `(0,5,0)`, `min_age=101` `(0,5,0)`; update docstring lines 922-928. |
| `tests/test_enrichment.py::test_finalize_enrichment_rating_min_matches_seventh_b` | LREQ-SMP-080, LREQ-MET-090 | The "default" call at 1016-1017 now uses M=1, so `u_quality_h=2` is usable → persist `2`, not `0`. To keep the historical "2 < M = 5 contributes a measured 0" branch, pin that call with `min_usable_samples_per_stratum=5`; update docstring lines 988, 1015-1017. |
| `tests/test_end_to_end.py::test_acceptance_sample_fraction_distinct_from_eligibility_coverage` | LREQ-MET-060, LREQ-TST-090 | Follows `acceptance_fixtures.SAMPLE_FRACTION_VS_COVERAGE_EXPECTED`; docstring `75/100 = 0.75` → `100/100 = 1.0` (lines 917-920). Distinctness from `sample_fraction = 0.45` still holds. |
| `tests/test_metrics.py::test_compute_raw_metric_bundle_maps_all_six_values` / `test_compute_category_raw_metrics_reports_coverages_and_counts` / `test_quality_raw_uses_n_h_over_n_h_weights` / `test_quality_raw_zero_visibility_denominator_is_null` / `test_quality_raw_contradicted_semantics_is_null` / `test_quality_coverage_not_renormalized` (`QUALITY_UNEQUAL_STRATA` half) / `test_quality_zero_population_is_null_and_coverage_zero` / `test_quality_raw_ineligible_observations_are_excluded` / `test_quality_min_rating_count_changes_quality_coverage` / `test_recent_share_uses_inclusive_window_per_stratum` / `test_recent_share_missing_dates_reduce_coverage_not_zero` / `test_recent_supply_coverage_and_usable_count` / `test_compute_category_raw_metrics_reports_coverages_and_counts` | LREQ-MET-030/060/080/090/100 | **No change** — their inputs already have `u_h >= 5` per stratum (verified by reading `metric_estimator_fixtures.py` vectors at lines 382-934). |

### 4.2 Fixture re-baselines

| File | Change |
|---|---|
| `tests/fixtures/enrichment_fixtures.py:322,326` | `FINALIZATION_USABLE_STATUS = "unavailable"` → `"usable"`; `FINALIZATION_ELIGIBILITY_RULE = "demand=null;recent=usable:5;quality=null"` → `"demand=usable:1;recent=usable:1;quality=usable:1"`. Update the comment at 324-326 (F4's null date no longer dominates because demand (4) and quality (3) are now usable). |
| `tests/fixtures/date_eligibility_fixtures.py:253-263` | `STRATUM_USABLE_VECTORS` re-baselined to default 1 (see §4.1); comment updated. |
| `tests/fixtures/acceptance_fixtures.py:350-361` | `SAMPLE_FRACTION_VS_COVERAGE_EXPECTED["demand_stratum_eligibility_coverage"]` `0.75` → `1.0`; comment lines 350-356 states stratum 1's four usable indices are now usable at the default 1. `sample_fraction` stays `0.45`. |
| `tests/fixtures/config_fixtures.py:68,116` | Defaults 5 → 1 (mirror shipped `config/default.toml`). `CUSTOM_TOML_BODY` (`:91`) and `CUSTOM_TOML_VALUES` (`:132`) keep their explicit `4` (a non-default override test). |

### 4.3 Floor-branch tests that pin the former default explicitly

At default 1 the "no usable stratum" / "coverage below 0.50" branches for a
4-usable-observation stratum are unreachable; these nodes are floor/branch tests,
so they pass `min_usable_samples_per_stratum=5` explicitly
(`dataclasses.replace(input, min_usable_samples_per_stratum=5)`) rather than
re-baselining to the floored value. Node IDs are unchanged.

| Node ID | LREQ | Explicit pin |
|---|---|---|
| `tests/test_metrics.py::test_demand_per_asset_null_when_no_usable_stratum` | LREQ-MET-030 | `replace(mfx.DEMAND_NO_USABLE_STRATUM, min_usable_samples_per_stratum=5)`; expected reason `METRIC_REASON_NO_USABLE_STRATUM` unchanged. |
| `tests/test_metrics.py::test_recent_supply_usability_minimum_boundary` | LREQ-MET-080 | `replace(mfx.RECENT_USABILITY_BOUNDARY, min_usable_samples_per_stratum=5)`; coverage `0.5`, count `5` unchanged. |
| `tests/test_metrics.py::test_quality_raw_null_below_required_coverage` | LREQ-MET-090 | `replace(mfx.QUALITY_LOW_COVERAGE, min_usable_samples_per_stratum=5)`; coverage `0.25`, `INSUFFICIENT_COVERAGE`, usable count `5` unchanged. |
| `tests/test_metrics.py::test_quality_coverage_not_renormalized` | LREQ-MET-090 | `replace(mfx.QUALITY_LOW_COVERAGE, min_usable_samples_per_stratum=5)`; `0.25` vs count-fraction `5/9` unchanged. |
| `tests/test_metrics.py::test_quality_eligible_set_too_small_is_null` | LREQ-MET-090 | Pin the local `no_usable_stratum_input` (3 eligible per stratum) at `min=5` so `NO_USABLE_STRATUM` stays reachable. |

### 4.4 New tests (added)

| Node ID | LREQ | Assertion |
|---|---|---|
| `tests/test_metrics.py::test_default_min_usable_is_inclusive_at_one` | LREQ-MET-030, LREQ-SMP-030 | At the module default, `stratum_is_usable(1) is True`, `stratum_is_usable(0) is False`; and `demand_stratum_eligibility_coverage(mfx.DEMAND_PARTIAL_COVERAGE) == 1.0` with `usable_demand_sample_count == 9`. |
| `tests/test_contracts.py::test_sampling_constants_contract` (edit, not new) | LREQ-SMP-030 | Already covers `== 1`; also assert `load_config(toml_path=config/default.toml).min_usable_samples_per_stratum == 1`. |

New node IDs require new `tests/traceability.json` entries (node ID → LREQ list,
the real file's direction; chunk-24 OQ-4). Run
`python -m niche_scout.tools.validate_traceability` after.

### 4.5 Scenario-dependent re-baseline (capture required; operator-confirmed IN scope, OQ-1)

Because `tests/fixtures/config_fixtures.py` default becomes 1, the full-pipeline
and end-to-end scenarios that load `DEFAULT_TOML_BODY` now score under the new
default. Their expected rankability/evidence values depend on the scenario's
per-stratum usable counts and are **not hand-derivable from this plan**; they are
re-baselined from a captured run (chunk-24 precedent: re-baseline to measured,
digest-stable values, recorded in the run log with the command). Candidate nodes
(**read**, expected to move toward more coverage/usable status):

- `tests/test_pipeline.py::test_failed_category_does_not_abort_other_categories`
  (LREQ-NFR-030, LREQ-EXT-090) — docstring at 560-564 says "default
  min_usable_samples_per_stratum (5)"; re-word and re-baseline the
  `evidence_grade`/`rankability_status` asserts at 588-592.
- `tests/test_pipeline.py::test_final_evidence_and_rankability_are_persisted_per_category`
  (LREQ-SEN-020, LREQ-EVD-020) — docstring at 1099-1104; re-baseline the
  `verified` asserts at 1124-1126 (the `unverified` row stays insufficient).
- Any `tests/test_end_to_end.py` acceptance node asserting
  coverage/`evidence_grade`/`rankability_status`/score under the default config.
  `test_acceptance_eight_category_run_is_provisional` stays provisional
  (8 categories never `rankable`); `test_acceptance_contradicted_page_views_*`
  stays `not_rankable` (contradicted semantics). Confirm each by running the suite.

Procedure: apply §2, run `python -m pytest -q`, capture the real output into
`Documents/runs/chunk-25.md`, and update only the failing default-policy
expectations. No expectation is changed to a value the test's LREQ does not
justify; where a branch would become unreachable, pin the parameter (§4.3).

---

## 5. Verification commands (lead-run; PowerShell, chain with `;`)

1. Live-DB corroboration the operator asked for (read-only, no writes). Run from
   the repo root:
   ```
   python -c "import sqlite3,json; c=sqlite3.connect('file:runtime/niche_scout.sqlite3?mode=ro',uri=True); c.row_factory=sqlite3.Row; r=c.execute('select run_id,scoring_cutoff_utc,config_snapshot_json from runs order by run_started_at_utc desc limit 1').fetchone(); print(r['run_id']); print(r['config_snapshot_json']); [print(s['stratum_index'], s['u_quality_h'], s['eligibility_rule'], s['usable_status']) for s in json.loads(c.execute('select stratum_statistics_json from category_scores where run_id=? limit 1',(r['run_id'],)).fetchone()[0])]"
   ```
   Lead-verified result (read from `runtime/niche_scout.sqlite3`): latest run
   `run-2026-09-28T05:59:50.085042+00:00`, `sampling_rule_version = 1.0.0`,
   config snapshot `min_usable_samples_per_stratum = 1`,
   `quality_min_rating_count = 3`. See §4.0 for the full grounded baseline. Note
   `-wal`/`-shm` exist, so use URI read-only mode as above.
2. `python -m pytest -q` — full suite. Record pass/fail counts.
3. `python -m niche_scout.tools.validate_traceability` — exit 0, both directions.
4. `python -m niche_scout.tools.check_import_boundaries` — exit 0 (`metrics.py`,
   `scoring.py` still pure; no pure-module import changed).
5. `python -m niche_scout.tools.check_scope_prohibitions` — exit 0.
6. `python -m niche_scout.tools.check_secrets` — exit 0.
7. `ruff check src/niche_scout/models.py tests/test_metrics.py tests/test_enrichment.py tests/test_validation.py tests/test_contracts.py tests/test_end_to_end.py` (and the changed fixture files) — judged **"no new lint"**. `database.py`'s 6 pre-existing E501 are standing and are **not** to be "fixed" in chunk-25.
8. SRS verification: `Select-String -Path Documents/SRS-lean-v2.md -Pattern 'MIN_USABLE_SAMPLES_PER_STRATUM'` shows `= 1` (line ~446) and the §14 row default `1`; confirm `Documents/SRS-lean.md` is untouched (absent/retired).
9. `git status` / `git diff --stat` — only §6 paths changed.

---

## 6. Files touched (explicit allowlist)

| Path | Change |
|---|---|
| `src/niche_scout/models.py` | `MIN_USABLE_SAMPLES_PER_STRATUM` 5 → 1 |
| `config/default.toml` | default 5 → 1 |
| `Documents/SRS-lean-v2.md` | edits S1–S5 |
| `tests/fixtures/config_fixtures.py` | default body + values 5 → 1 |
| `tests/fixtures/enrichment_fixtures.py` | `FINALIZATION_USABLE_STATUS`, `FINALIZATION_ELIGIBILITY_RULE` |
| `tests/fixtures/date_eligibility_fixtures.py` | `STRATUM_USABLE_VECTORS` |
| `tests/fixtures/acceptance_fixtures.py` | sample-fraction-vs-coverage expected |
| `tests/fixtures/metric_estimator_fixtures.py` | comments only (no input/expected change) |
| `tests/test_metrics.py` | re-baselines + pins + 1 new node (§4) |
| `tests/test_enrichment.py` | re-baselines + pins (§4) |
| `tests/test_validation.py` | boundary test follows re-baselined vector |
| `tests/test_contracts.py` | constant re-baselines |
| `tests/test_end_to_end.py` | sample-fraction expected/docstring; scenario re-baseline if it moves |
| `tests/test_pipeline.py` | scenario re-baseline if it moves (§4.5) |
| `tests/traceability.json` | new node entry (§4.4) |
| `Documents/plans/chunk-25-min-usable-samples.md` | this plan |
| `Documents/runs/chunk-25.md` | stage/gate log (lead-owned) |

Not touched: `src/niche_scout/metrics.py`, `scoring.py`, `pipeline.py`,
`database.py`, `report.py`, `config.py`, `collector*.py`, `cli.py`.

---

## 7. Gate bullets (each needs command-output evidence)

- [ ] `models.MIN_USABLE_SAMPLES_PER_STRATUM == 1` and
      `load_config(toml_path=config/default.toml).min_usable_samples_per_stratum == 1`.
- [ ] Live-DB corroboration recorded (read from `runtime/niche_scout.sqlite3`):
      latest run `run-2026-09-28T05:59:50.085042+00:00` at floor 1 with
      `eligibility_rule = demand=usable:1;recent=usable:1;quality=usable:1`
      (§4.0). This is corroboration, not a golden vector.
- [ ] The `usable:<min>` token emits `usable:1`
      (`pipeline._component_eligibility_rule`); the finalization golden stratum is
      `usable_status == "usable"` with rule
      `demand=usable:1;recent=usable:1;quality=usable:1`.
- [ ] The three `*_stratum_eligibility_coverage` outputs and
      `usable_*_sample_count` are re-baselined where the default changed
      (`DEMAND_PARTIAL_COVERAGE`: coverage 1.0, count 9; finalization 4/5/3);
      explicit-`min` floor branches still test the `u_h < min` behavior (§4.3).
- [ ] `stratum_statistics_json` still carries exactly the frozen ten-key set; the
      persisted payload round-trips and `verify_persisted_sampling` /
      `assert_finalization_consistency` return `()` mismatches on a clean run.
- [ ] Evidence grades / rankability re-baselined wherever a scenario output moved,
      with the captured `pytest` output recorded in `Documents/runs/chunk-25.md`.
- [ ] `python -m pytest -q` passes; `validate_traceability` exit 0 both directions
      (new node mapped); `check_import_boundaries`, `check_scope_prohibitions`,
      `check_secrets` exit 0.
- [ ] Ruff: **no new lint** on changed files. `database.py`'s 6 pre-existing E501
      are standing and MUST NOT be fixed in chunk-25.
- [ ] SRS edits S1–S5 applied textually in `Documents/SRS-lean-v2.md` only; the
      retired `SRS-lean.md` is untouched; a deny on the v2 path is surfaced, not
      worked around.
- [ ] No out-of-scope file changed; no change to `SAMPLE_STRATA`,
      `SAMPLE_PER_STRATUM`, `QUALITY_MIN_RATING_COUNT`, any formula, weight, or
      the chunk-24 partition.
- [ ] No out-of-scope feature added (no scheduling/history/enrich-everything/etc.,
      SRS §15).

---

## 8. Resolved questions (operator, 2026-09-28)

**Open questions: none.** All three items were answered "go with the
recommendation"; the plan is frozen.

1. **Test-fixture default — RESOLVED (in scope).** `tests/fixtures/config_fixtures.py`
   `DEFAULT_TOML_BODY`/`DEFAULT_TOML_VALUES` mirror the shipped default 5 → 1, so
   the suite exercises the shipped default and the §4.5 scenario
   end-to-end/pipeline re-baseline is **in scope**.
2. **Version bump — RESOLVED: NO bump.** `MIN_USABLE_SAMPLES_PER_STRATUM` is a
   configurable policy default (§14 `Configurable = Yes`), not a §5.1 sampling-rule
   trigger; only usability-derived outputs change. `SAMPLING_RULE_VERSION` stays
   `2.0.0`, so offsets and selection digests are untouched.
3. **SRS revision label — RESOLVED: `Lean 1.0.3`** (edits S3/S4), following the
   Lean 1.0.2 precedent.

The grounded baseline in §4.0 (**read** from `runtime/niche_scout.sqlite3`)
corroborates the direction and magnitude of the re-baseline; it is a single-run
observation, not a golden vector, and does not substitute for the fixture- and
scenario-derived expected values in §4.1–§4.5.

---

End of plan.
