# Chunk 10 — run log (Pipeline orchestration)

Started 2026-09-22. Branch `main` (Chunk 9B merged at `efc34bc`; tree clean at preflight).
Chunk 10 depends on the frozen interfaces of Chunks 0–9B, all present and `VERIFIED`.

## Preflight

| Check | Result |
|---|---|
| Working tree | clean (`git status` → nothing to commit) |
| Branch | `main` at `efc34bc` |
| Prerequisite interfaces | `Documents/interfaces/chunk-00..9B.md` all present; Chunk 10 consumes 02/03/4A/4B/05/6A/6B/7A/7B/08/9A/9B |
| Baseline suite | `python -m pytest tests -q` → **475 passed, 0 failed** |
| Frozen plan | none — planner dispatch required |
| Routing | `chunk-planner` → advisory research → lead rulings → `test-author` → `impl-deep` → `spec-reviewer` |

## Stage log

| Stage | Status | Evidence / notes |
|---|---|---|
| Preflight | DONE | Table above. |
| Plan — `chunk-planner` dispatch 1 | INCOMPLETE | Session `ses_f3884dc7fffe12lA7Ag1YqNbff` gathered all evidence but ran out of steps before writing the file. Resumed; plan written (1,030 lines, Status: DRAFT). |
| Plan — advisory research | DONE | Read-only `general` session `ses_f38789539ffeeQfhQkAzvDoZRC` independently verified all nine §12 open questions against SRS-lean, the dependency map, the frozen interfaces, and live source. Eight recommendations aligned with the plan; it corrected Q5's cited authority (SRS §8.1 is silent on the discovery booleans) and Q7 (`CategoryStatus` is a derived roll-up, not an input to evidence/rankability). |
| Plan — lead rulings 1–9 | DONE | Rulings recorded below; the planner applied them and froze the plan (1,106 lines, Status: FROZEN), adding §5.6 (frozen JSON shapes), §5.7 (`CategoryStatus` roll-up) and §5.8. |
| Plan — lead amendment (§5.8) | DONE | Diagnostic found `runs.scoring_cutoff_utc` (SRS §6.1 required, nullable DDL) had no writer and no database API could set it. The lead amended the frozen plan in place: new §5.8 authorizes one additive `database.py` method `update_run_scoring_cutoff`, §5.1 step 10 now persists the captured cutoff, §5.2 row 10 records the write, §6 authorizes the method, §11 records it. |
| Tests — `test-author` | DONE | 27 nodes in `tests/test_pipeline.py`, one added node in `tests/test_database.py`, `tests/fixtures/pipeline_fixtures.py`, 28 new `tests/traceability.json` entries, `tests/fixtures/__init__.py` re-export. |
| Tests — fixture defect corrections | DONE | An independent diagnostic (grounded in the frozen Chunk 3/7A/7B/8/9B code) found three defects in the authored fixtures: (1) synthetic scenario categories were absent from the committed `ec_category` facet, so the injected transport could not resolve them → fixed with a run-local template written through `coveo_discovery.write_template` and threaded as `template_path`; (2) the "truncated" category was produced by a short page with an unaccounted `totalCount`, which the adapter classifies `filter_unverified`, not `truncated` → fixed by using the SRS §4.1 read cap (`SCENARIO_DISCOVERY_CAP=3`) to produce a genuine cap-branch `truncated`; (3) `evidence_grade != INSUFFICIENT` contradicted `min_usable_samples_per_stratum=5` over two-member censuses → expectation corrected to `insufficient`/`not_rankable`. |
| Tests — lead fixture corrections | DONE | The GraphQL fixture's request-body fingerprint is category-blind (all categories' Coveo bodies carry the same facet-value string set), so it could not serve the sampled identities → the fixture now seeds a merged identity directory. `END_TO_END_CATEGORIES` was declared lexically while `_scenario_category_records()` was Verified-first, so the preflight covered different categories than the pinned vectors → declared order is now authoritative for both. The `LogCapture` was never registered as a logging handler and the transport hook fired on preflight calls (which legitimately precede the projection log) → `LogCapture` is now a real `logging.Handler`, `install_projection_observer` attaches it to `niche_scout.pipeline` and forces the logger level, and the hook skips the preflight identities (derived from the frozen pure selection surfaces). |
| Implementation — `impl-deep` | DONE | Sessions `ses_f3826dfa2ffegeZXLywAvio7EN` (reconnaissance; raised four conflicts, all adjudicated) and `ses_f3811031effetrGjd4OjKkI1dl` (ran out of steps after reconnaissance). Implementation completed in-session by the lead: `PipelineError`/`PipelineConfigurationError`/`TaxonomyInvalidError`/`PipelineResult`/`taxonomy_sha256_for`/`category_status_for`/`run_pipeline` in `pipeline.py`; the `runs` provenance guard and `update_run_scoring_cutoff` in `database.py`. Three defects found and fixed during verification: a `score_category` `NameError` (unqualified call, fixed to `scoring.score_category`), a wrong keyword `discovery_conflict_identity_count` (the frozen field is `discovery_conflict_count`), and a malformed generator indentation. |
| Review — `spec-reviewer` round 1 | FAIL (1 Major) | Session `ses_f372d098dffeoUDgAsQ5V5kMd1`. Major: the `< MIN_CATEGORIES_PER_RUN` rejection used the **configurable** `config.min_categories_per_run`, and the chunk's own suite lowered it to 6 and completed a six-category run — contradicting SRS §14 (`MIN_CATEGORIES_PER_RUN` "Configurable? No"), LREQ-CLI-040, and SRS §17.1. Six Minors also recorded. |
| Fix round 1 | DONE | The rejection now uses the frozen `models.MIN_CATEGORIES_PER_RUN`; `pipeline.py` no longer reads `config.min_categories_per_run`. The e2e scenario was widened from six to eight categories (five synthetic complete categories) so the run is accepted at the frozen minimum with no threshold override; `SIX_CATEGORY_CONFIG` no longer lowers `min_categories_per_run`. Constants re-derived and re-pinned: 15 raw rows, 14 sample members, 13 identities, 3 reused, 10 pending, 5.0 s. The NFR-020 projection node now asserts each `key=value` pair explicitly instead of a substring `or` escape. |
| Review — `spec-reviewer` round 2 | PASS | Session `ses_f371ccc35ffeEERSijsyoq7G6J`. The Major fix verified by code reading, grep, and the widened fixture; nine Minors recorded, none Blocker/Major. It could not run `ruff` (environment permission rule); the lead ran it. |
| Review-fix rounds used | 1 of 2 | Only the Major needed a fix round. |
| Interface produced | DONE | `Documents/interfaces/chunk-10.md` (Status: VERIFIED) written from the frozen plan §5, with the §5.8 amendment and the plan §12 item 4 inconsistency recorded. |
| Gate | PASSED | See gate table below. |

### Review (step 7)

| Item | Result |
|---|---|
| `spec-reviewer` round 1 | `VERDICT: FAIL` — 1 Major (configurable run-size threshold), 6 Minor. No Blocker. |
| `spec-reviewer` round 2 | `VERDICT: PASS` — no Blocker, no Major. Commands re-run by the reviewer: `pytest tests/test_pipeline.py tests/test_database.py -q` → 51 passed; `pytest tests -q` → 503 passed; `validate_traceability` → valid; `check_import_boundaries` → valid. |
| Round-2 Minors (open, recorded) | (1) no node sets `min_categories_per_run` **lower** and requests <8 categories, so config-independence rests on code reading + grep rather than a test; (2) the 8–20-category provisional contract is not asserted on orchestrator-written rows; (3) `test_database.py`'s closing block claims a nullable-column property it does not exercise; (4) the `run_id`-derivation plan/interface inconsistency; (5) the `insufficient` path transitions the run to `failed` (6A's binding text requires only "non-completed"); (6) `tests/test_pipeline.py` exceeds the 800–1,000-line review trigger; (7) a stale fixture comment and the stale `SIX_CATEGORY_CONFIG` name; (8) the projection assertions are substring checks; (9) the cutoff-once node does not count `capture_scoring_cutoff_utc` calls. |
| Reviewer UNVERIFIED | `ruff` was permission-denied for the reviewer; the lead ran `python -m ruff check` and `format --check` on the changed files. Repo-wide pre-existing ruff debt is unchanged by this chunk. |

### Gate — Chunk 10

Gate bullets walked one by one from `Documents/requirements-dependency-map.md` §3 Chunk 10
(Gate section, lines 998–1007), on the working tree with the full suite green.

| Gate bullet | Result | Evidence |
|---|---|---|
| 1. A failed category does not abort unrelated categories | PASS | Per-category discovery runs inside its own `category_transaction` and a per-category failure is recorded as its `DiscoveryStatus` without aborting the loop. Node `test_failed_category_does_not_abort_other_categories` (genuine cap-branch `truncated` category) and `test_failed_page_is_not_zero_assets` (all pages fail; `demand_per_asset_raw is None`, never 0) pass. |
| 2. The scoring cutoff is captured once and passed into pure functions | PASS | `capture_scoring_cutoff_utc(clock())` is called exactly once, after enrichment and before metrics; the same value is passed to `finalize_enrichment`, every `CategoryMetricInput`, and the scoring chain, and persisted once. Node `test_scoring_cutoff_is_captured_once_and_threaded_to_pure_calls` passes (reviewer Minor 9: call-count not asserted). |
| 3. A failed preflight prevents enrichment | PASS | `enrich_unique_identities` returns before logging or requesting when the gate is not `passed`; nodes `test_failed_preflight_blocks_enrichment_and_marks_run_failed` and `test_failed_preflight_issues_zero_enrichment_requests` pass with zero transport calls. |
| 4. Runs with fewer than `MIN_CATEGORIES_PER_RUN` (8) are rejected before ranking | PASS | `run_pipeline` compares `len(requested)` to the imported `models.MIN_CATEGORIES_PER_RUN` (8, SRS §14 non-configurable) before credentials, taxonomy, run insert, or any transport. `pipeline.py` never references `config.min_categories_per_run` (grep). Nodes `test_run_with_fewer_than_min_categories_is_rejected` (2 categories rejected, nothing persisted) and `test_pipeline_runs_completed_end_to_end` (8 categories accepted) pass. |
| 5. Configuration or taxonomy failure causes no network request | PASS | Nodes `test_invalid_configuration_causes_no_network_request` and `test_invalid_taxonomy_causes_no_network_request` assert `coveo.call_count == 0` and `graphql.call_count == 0`. |
| 6. Failed-preflight path | PASS | `run.status = failed`, discovery/sample/preflight rows retained, zero bulk-enrichment requests, metric/score/ranking skipped, one null-score row per requested category with `evidence_grade = insufficient` and `rankability_status = not_rankable` plus preflight warnings, and `PipelineResult(status='failed')` for Chunk 12's non-zero exit. Nodes `test_failed_preflight_*` (5) and `test_insufficient_preflight_leaves_run_non_completed` pass. |
| 7. 6B finalization completes before metrics; `category_scores` use the finalized counts | PASS | `finalize_enrichment` runs before the metrics loop and writes the finalized per-stratum payload and usable counts; the metric inputs are rebuilt from the same persisted observations. Asserted by `test_pipeline_runs_completed_end_to_end` (rows carry non-null usable counts) and by the 6B consistency assertion that `finalize_enrichment` runs. |
| 8. `CategoryStatus` is a typed internal roll-up, not a persisted enum | PASS | `category_status_for` is a pure helper in `pipeline.py`; no `category_status` column exists (schema untouched) and the value is used only for limitations/diagnostics. |
| 9. Preflight-failure read model: one null-score row per requested category, or an equivalent Chunk 11 join | PASS | Chunk 10 writes the rows (first branch): node `test_failed_preflight_persists_per_category_limitations` asserts one row per requested category with the null-score/insufficient/not-rankable contract. |
| 10. 8–20 category runs are provisional with no rankable candidate set and null stability | PASS | The e2e scenario is an eight-category run; `evaluate_sensitivity` returns `top_3_stability`/`top_5_stability`/displacement `None` and an empty candidate set, and the persisted rows carry `NULL` stability (Chunk 9B surface, re-verified by the 9A/9B nodes in this module). Reviewer Minor 2 records that this is not separately asserted on orchestrator-written rows. |

Supporting evidence: `python -m pytest tests -q` → **503 passed, 0 failed**;
`python -m pytest tests/test_pipeline.py tests/test_database.py -q` → **51 passed**;
`python -m niche_scout.tools.validate_traceability` → valid ("7 Chunk 0 requirements
mapped, 489 matrix nodes, 89 defined LREQ IDs"; 7 pre-existing unmarked
collector/sampling tests, none a Chunk 10 node);
`python -m niche_scout.tools.check_import_boundaries` → valid for `metrics.py, scoring.py`;
`python -m ruff check src/niche_scout/pipeline.py tests/test_pipeline.py tests/fixtures/pipeline_fixtures.py` → "All checks passed!";
`python -m ruff check src/niche_scout/database.py` → 6 pre-existing `E501`s (identical count to the pre-change baseline; not introduced by Chunk 10).

**GATE: PASSED**

### Open items carried forward (not gate failures)

- Reviewer round-2 Minors 1–9 above. Minor 4 (`run_id` derivation wording) is recorded
  in `interfaces/chunk-10.md` §10 as a plan/interface inconsistency; Minor 5
  (`insufficient` → `failed`) is an SRS silence, not a defect.
- `tests/test_pipeline.py` (≈1,190 lines) and `tests/fixtures/pipeline_fixtures.py`
  (≈1,200 lines) are past the 800–1,000-line review trigger. Fixtures are exempt
  (inert data); the test file's split boundary is the requirement clusters
  (ARCH-030 / ID-040 / NFR-030+EXT-090 / NFR-020 / EVD+SEN+NRM) and is a
  human/plan decision — no node ID may be renamed by a split.
- Repo-wide pre-existing `ruff` `E501` debt in `database.py` (6) and other modules is
  unchanged and outside this chunk.
- **URI trailing-identifier extraction (identity mapping rule 1.0.1) remains UNVERIFIED
  and owned by no chunk** (dependency-map §6.4; `interfaces/chunk-01.md` §4.1/§8;
  `interfaces/chunk-03.md` §8). Chunk 10 parses no response and must not state or imply
  verification.
- **OI-6 (CSRF/session sufficiency) remains unassigned** (dependency-map §7;
  `interfaces/chunk-05.md` §12 Q1/Q3). Chunk 10 performs no HTTP and neither resolves
  nor absorbs it.
- Chunk 11 must consume the §6 JSON shapes read-only and must not redefine them.

### Lead rulings on the Chunk 10 plan §12 open questions

Each ruling is grounded in the cited SRS/dependency-map/interface text; none invents a
formula or threshold.

- **Q1/Q2 (empty-`taxonomy_sha256` guard location and file authorization) — (c) both.**
  `pipeline.py` never builds an empty hash; `database.py` rejects empty/whitespace
  provenance values on the `runs` write path. Dependency-map §7 assigns the obligation
  to Chunk 10, and this plan is the only artifact that can authorize `database.py`.
- **Q3 (preflight-failure rows) — (a) write them.** The gate's first branch; keeps
  Chunk 11 a pure read model.
- **Q4 (`run_id`) — (b) caller-optional, otherwise clock-derived.** A random UUID would
  break LREQ-ARCH-030; the frozen signature has no suffix parameter (recorded in
  `interfaces/chunk-10.md` §10).
- **Q5 (discovery booleans / breadth source) — (a).** `discovery_filter_verified` from
  the persisted `filter_status is VERIFIED`; `discovery_bounded_by_verified_total` = a
  verified `total_count` exists and discovery is not `truncated`; `breadth_source` is
  decided by 7B's `breadth_raw` from `BreadthMetricInput.verified_total_count`. SRS §8.1
  is silent on the two booleans; the projection is plan-level.
- **Q6 (`PageViewSemanticsStatus` source) — (a) read back from `get_run`.** One source of
  truth, matching 6A's non-clobbering write.
- **Q7 (`CategoryStatus`) — (a) pure helper in `pipeline.py`, a derived roll-up.** It is
  not an input to evidence or rankability (those come from Chunks 9A/9B).
- **Q8 (`warnings_json` / `missing_components_json`) — (a), frozen in
  `interfaces/chunk-10.md` §6.** No Chunk 11 interface exists yet, so Chunk 10 freezes
  the shapes; Chunk 11 consumes them read-only.
- **Q9 (finalization consistency) — (a).** `finalize_enrichment` already runs the 6B
  consistency assertion; non-empty `mismatches` become run limitations.
- **Lead amendment (§5.8).** `update_run_scoring_cutoff(run_id, scoring_cutoff_utc)` is
  authorized in `database.py` and called once at step 10, closing the SRS §6.1 required
  `runs.scoring_cutoff_utc` column.
