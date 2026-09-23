# Chunk 13 — run log (Full acceptance suite and quality workflow)

Started 2026-09-22. Branch `chunk-13` created from `main` at `a8c2fcf`; tree clean at preflight.
Chunk 13 is the final chunk (dependency-map §4). Its prerequisites are all runtime chunks
(Chunk 0 through Chunk 12), evidenced below.

## Preflight

| Check | Result |
|---|---|
| Working tree | clean (`git status` → nothing to commit) |
| Branch | `chunk-13` (new, from `main` `a8c2fcf`) |
| Prerequisite run logs | `chunk-4A`, `chunk-4B`, `chunk-05`, `chunk-6A`, `chunk-6B`, `chunk-7A`, `chunk-7B`, `chunk-08`, `chunk-9A`, `chunk-9B`, `chunk-10`, `chunk-11`, `chunk-12` all end `GATE: PASSED` |
| Prerequisite interfaces | `chunk-00/01/02/03` are `Status: VERIFIED` (run logs for 0–3 do not exist on this tree; same documented exception recorded for Chunks 4A/5/12) |
| Frozen plan | none — planner dispatch required |
| Routing | `chunk-planner` → `impl-deep` (no test-author first) → `spec-reviewer` |
| Python / pytest | 3.12.2 / pytest 9.1.1 |

## Stage log

| Stage | Status | Evidence / notes |
|---|---|---|
| Preflight | DONE | Table above. |
| Plan — `chunk-planner` dispatch 1 | BLOCKED | Session `ses_f358716f3ffeMgmdOieRov7D95`. Plan written DRAFT with 11 open questions (retired-feature list, traceability semantics, AGENTS.md orientation conflict, import-boundary scope, secret check, unmarked count, 21-category vector, contradicted-page-view seam, workflow entry point, lint scope, vector location). |
| Plan — advisory research | DONE | Session `ses_f357fa4ccffe3K8aPdMApSYoU7` (read-only). Recommended answers to all 11 with citations; flagged 5 as human-decision. |
| Lead evidence (counted) | DONE | `python -m pytest -q` → 548 passed; validator → "7 unmarked" but lead found the parser only accepts single-arg markers (99 multi-arg markers misread); corrected AST walk → mismatch 0, unmarked 4, orphans 0; `defined_ids=89`, referenced `86`, exactly TST-020/040/050 unreferenced; `ruff check` 245 errors, `ruff format --check` 14 to reformat. |
| Plan — `chunk-planner` freeze | DONE | Session resumed (first retry hit provider "Connection reset by server"; retried once). Plan rewritten to 658 lines, `Status: FROZEN`, §12 records R1–R12. Commit `47435b8` (`chunk-13: plan`). |
| Implement — `impl-deep` dispatch 1 | INTERRUPTED | Provider "Connection reset by server" during the first dispatch; working tree clean. Retried once, resumed with full task. |
| Implement — `impl-deep` dispatch 2 | INTERRUPTED (provider) | Two consecutive provider errors: "Connection reset by server", then "Payment Required: Insufficient balance after pending billing reservations". Stopped per the one-retry rule. The session had, before the error, written all plan §6 files (see Verify below). |
| Verify (lead, step 6) | FAILED (runtime defect) | `python -m pytest -q` → **594 passed, 1 failed**. The single failure is `tests/test_end_to_end.py::test_acceptance_completed_run_is_durable_across_connections`, which asserts correct durability and documents a genuine **runtime defect in frozen Chunk 10 code**: `pipeline.py:3357–3361` calls `repository.update_run_status(run_id, COMPLETED, completed_at_utc=clock())` as the last write and does not wrap it in `repository.transaction()`; `database.py:866–876 close()` never commits pending DML, so a fresh connection reads `status='running'`, `completed_at_utc=NULL`. The failure path is committed only because a later `upsert_category_scores` transaction flushes it. Chunk 13 must not fix runtime code (AGENTS.md; plan §11) — STOPPED for a human ruling. |
| Verify — other checkers | PASS | `python -m niche_scout.tools.validate_traceability` → "Traceability valid: 89 required/defined LREQ IDs mapped, 581 matrix nodes, 0 unmarked analytical tests outside exemption (3 exempted non-analytical nodes)"; `check_import_boundaries` → valid; `check_scope_prohibitions` → valid (6 tokens); `check_secrets` → valid; `ruff check` + `ruff format --check` on the 8 new/rewritten tool+test files → "All checks passed!" / "8 files already formatted". Pre-existing ruff debt remains in the four marker-bearing test files (63 errors there, mostly E501) and repo-wide (245 errors / 14 unformatted) — unchanged and out of scope (R10). |
| Implement (WIP snapshot) | DONE | Committed all plan §6 files as a WIP snapshot so the large uncommitted delta is preserved (project-rules "Temporary scripts and scratch space" / WIP-snapshot rule). Gate not passed; no `main` merge. |
| STOP — runtime defect (human ruling required) | BLOCKED | SRS §17 acceptance criterion 19 says "golden vectors and the end-to-end fixture pass". The end-to-end fixture does not pass, and the failure is a genuine defect in frozen Chunk 10 code, not a test or plan error. `AGENTS.md`: "If the acceptance suite exposes a runtime defect, STOP and report it as a finding; do not silently fix runtime code." Project-rules "Chunk pipeline auto-chaining": relay to the user and stop. Requested ruling: authorize a minimal Chunk-10-owned remediation (wrap the completion transition at `pipeline.py:3357–3361` in `with repository.transaction():`) or direct another disposition. Chunk 13 makes no runtime edit without that ruling. |

## Chunk 10 remediation (labeled, out-of-chunk) — commit terminal COMPLETED transition

Human ruling received: authorize a labeled, out-of-chunk Chunk-10 remediation, separate from
Chunk 13's implementation. Scope authority is Chunk 10's frozen plan §5.1 step 18 (lines
556–557) and §5.2 table line 592 ("compatible with 17; may share the transaction"); no plan
text changes, no open question.

| Stage | Status | Evidence / notes |
|---|---|---|
| Preflight | DONE | Branch `chunk-13`, tree clean, no push/merge. Verified: `database.py:866–876 close()` never commits; `pipeline.py:3353–3362` terminal write has no transaction wrapper while `pipeline.py:3350–3351` scores commit; `pipeline.py:1133–1146 run_identity_preflight` commits its own `failed`; preflight-failure write `pipeline.py:3211–3214` is flushed by the following limitation-rows transaction. |
| RED confirmation (lead) | DONE | `python -m pytest tests/test_end_to_end.py -q -k durable` → `1 failed, 20 deselected`; `AssertionError: assert 'running' == 'completed'` at `tests/test_end_to_end.py:703`. |
| Implement (`impl-deep`, session `ses_f33583c84ffeGg8OL4FbKbmC0q`) | DONE | Exactly one hunk at `pipeline.py:3354–3364`: terminal `COMPLETED` transition wrapped in `with repository.transaction():`; `FAILED` guard unchanged; no test/other file touched. Red→green on the durable node: `1 failed, 20 deselected` → `1 passed, 20 deselected`. Full suite 595 passed, 0 failed; all four validators valid; `ruff check src/niche_scout/pipeline.py` → "All checks passed!". |
| Review (`spec-reviewer`, session `ses_f335572d4ffeScuW2KFMiPiy5M`) | VERDICT: PASS | Guard intact; both terminal return paths end in a committing `transaction()`; `update_run_status`/status transitions exist only at `pipeline.py:1146, 3214, 3358`, all flushed. One **Minor**: durable node docstring `tests/test_end_to_end.py:684–691` is now stale ("currently FAILS … status = running"), a docs-only inconsistency in a test-author-owned file the remediation was forbidden to edit — record only, no loop. |
| Commit (lead) | DONE | `1f0f4fe` `chunk-10: remediation - commit terminal completed transition` — one file, `src/niche_scout/pipeline.py` only (6 insertions, 5 deletions). `d2cf558` not amended; nothing pushed. |

### Post-remediation verification (lead, step 6 — real output)

| Command | Real result |
|---|---|
| `python -m pytest tests/test_end_to_end.py -q -k durable` | `1 failed, 20 deselected` (pre-fix) → after fix `1 passed, 20 deselected` |
| `python -m pytest -q` | `595 passed in 22.46s` |
| `python -m niche_scout.tools.validate_traceability` | `Traceability valid: 89 required/defined LREQ IDs mapped, 581 matrix nodes, 0 unmarked analytical tests outside exemption (3 exempted non-analytical nodes)` |
| `python -m niche_scout.tools.check_import_boundaries` | `Import boundaries valid for metrics.py, scoring.py` |
| `python -m niche_scout.tools.check_scope_prohibitions` | `Scope prohibitions valid: no retired token found … (6 tokens checked)` |
| `python -m niche_scout.tools.check_secrets` | `Secret check valid: no literal credential found under src, tests, config, pyproject.toml; .gitignore ignores .env and no tracked .env exists` |
| `python -m ruff check src/niche_scout/pipeline.py` | `All checks passed!` |
| `python -m ruff format --check src/niche_scout/pipeline.py` | exit 1, "1 file would be reformatted"; every flagged hunk (2760, 2839, 2932, 3004, 3034, 3122, 3226) is outside the changed hunk `3354–3364` and is pre-existing at HEAD — not introduced; left unfixed per "do not fix repo-wide ruff debt" |

**Provenance:** this defect was latent in frozen Chunk 10 code (plan §5.1 step 18 / §5.2 line 592
permitted sharing the transaction, but the implementation did not), and was surfaced only by
Chunk 13's durability acceptance node (`tests/test_end_to_end.py::test_acceptance_completed_run_is_durable_across_connections`),
which opens a fresh connection like the `dashboard` command. The Chunk 13 acceptance test is the
red→green evidence and remains a normal (non-xfail) node.

## Chunk 13 step 7 — review and fix rounds

| Stage | Status | Evidence / notes |
|---|---|---|
| Review round 1 (`spec-reviewer`, session `ses_f334b0fa6ffe8JulcnfLrRmUP6`) | **FAIL** | One **Major**: `tests/test_end_to_end.py::test_acceptance_four_stratum_sampling_and_one_enrichment_per_identity` asserted only census/stratum-0 members (fixture categories hold 0–2 assets), so SRS §13 LREQ-TST-080 "four-stratum sampling" and the gate bullet "End-to-end fixture covers all required … sampling … behaviors" were not discharged (node ID/name vs. plan §9 "Four strata"). Minors: stale durable-node docstring; duplicate `_ContradictedRepositoryHandle`; N=21 derivation comment mismatch; `quality_workflow` exits non-zero on repo-wide ruff (244 pre-existing, R10); NFR-050/NFR-060 attribution on some tooling nodes; scope-check self-exclusion; `check_secrets` wording. Full suite 595 passed, validator 89/581/0/3 by the reviewer's own run. |
| Fix round 1 (`impl-deep`, session `ses_f333e432bffeHvttelGJ5emvoN`) | DONE | New node `test_acceptance_four_stratum_sampling_drives_non_census_strata` + fixture `afx.four_stratum_artifacts` (120-asset category + seven one-asset census categories): asserts persisted strata 0–3 × 25 members, non-census `sampling_basis`, `sample_fraction = 100/120 < 1.0`, census siblings 1.0, `set(requested) == sampled_union` (one enrichment per unique identity). No existing node renamed/weakened. Three doc Minors fixed. Files: `tests/test_end_to_end.py`, `tests/fixtures/acceptance_fixtures.py`, `tests/traceability.json`. |
| Review round 2 (`spec-reviewer`, session `ses_f3329f247ffeIWe23YEssXwHkI`) | **PASS** | Major confirmed genuinely resolved through the real `cli.run_command`/SQLite path; no renamed node, no weakened assertion, no marker-only file touched; marker/entry match; validator clean. Remaining **Minors** (record only, no loop): unused `_ContradictedRepositoryHandle` (pre-existing dead code); unused `FOUR_STRATUM_SMALL_POPULATION`/`four_stratum_population_records` (inert fixture data); `quality_workflow` non-zero on repo-wide ruff (R10). |
| Commit (lead) | DONE | `40f70d5` `chunk-13: review fixes - four-stratum acceptance coverage and doc minors` (3 files, +347 −21). |
| Lead verification after fix | PASS | `python -m pytest -q` → `596 passed in 20.73s`; `validate_traceability` → 89/582/0/3; `check_import_boundaries` valid; `check_scope_prohibitions` valid (6 tokens); `check_secrets` valid; `ruff check tests/test_end_to_end.py tests/fixtures/acceptance_fixtures.py` → `All checks passed!`; `ruff format --check` → `2 files already formatted`. |

**Open note (not a gate gap):** the fixture's four-stratum identity keys deliberately avoid a
`-<digits>` suffix so identity mapping rule 1.0.1 (URI trailing-identifier extraction, an open
inference obligation) does not fabricate a conflict. The obligation remains open and unverified;
nothing in Chunk 13 claims it resolved. Recorded per AGENTS.md "Open obligations".

## Chunk 13 gate (dependency-map lines 1090–1099)

Gate bullets walked one by one, each with evidence:

| # | Gate bullet (verbatim, dependency-map) | Evidence |
|---|---|---|
| 1 | Exact golden outputs pass within `1e-9`. | `python -m pytest -q -k golden` → `5 passed, 591 deselected` (`test_scoring::test_midrank_golden_vectors`, `test_scoring_evidence::test_pre_sensitivity_golden_vectors`, `test_scoring_sensitivity::test_sensitivity_golden_vectors`, `test_identity_preflight::test_compute_preflight_rates_two_identity_golden`, `test_pipeline::test_taxonomy_sha256_is_non_empty_and_matches_golden`); acceptance `1e-9` vectors `test_acceptance_unequal_stratum_quality_raw_vector`, `test_acceptance_sample_fraction_distinct_from_eligibility_coverage`, `test_acceptance_twenty_one_category_composite_vector`, `test_acceptance_zero_population_category_vector`, `test_acceptance_two_category_run_rejected_before_ranking` all passed. |
| 2 | End-to-end fixture covers all required collection, sampling, enrichment, scoring, persistence, and reporting behaviors. | `python -m pytest tests/test_end_to_end.py -q -k acceptance` → `22 passed` (collection: `test_acceptance_pagination_duplicate_and_overlap`, `test_acceptance_category_validation_rejects_before_network`; sampling: `test_acceptance_four_stratum_sampling_and_one_enrichment_per_identity`, `test_acceptance_four_stratum_sampling_drives_non_census_strata`; enrichment: `test_acceptance_partial_graphql_failure_retains_valid_operation`; scoring/persistence: `test_acceptance_sqlite_rows_match_pure_results`, `test_acceptance_run_persists_and_renders`; reporting: `test_acceptance_rendered_report_contains_required_fields`). |
| 3 | 8-category provisional run behaves correctly. | `test_acceptance_eight_category_run_is_provisional` passed (empty candidate set, null stability, provisional scores). |
| 4 | 21-category strong-reference run behaves correctly. | `test_acceptance_twenty_one_category_composite_vector` passed; `tests/test_scoring.py::test_eight_and_twenty_one_category_run_reference_sizes` passed. |
| 5 | Preflight failure produces a failed run and zero bulk-enrichment requests. | `test_acceptance_preflight_failure_marks_run_failed_zero_enrichment` passed. |
| 6 | Partial GraphQL operation success and contradicted page-view semantics remain distinguishable. | `test_acceptance_partial_graphql_failure_retains_valid_operation` and `test_acceptance_contradicted_page_views_distinct_from_partial_success` passed. |
| 7 | Sensitivity is null when the fixed candidate set is empty and never changes that set. | `test_acceptance_eight_category_run_is_provisional` (null stability), `test_acceptance_sensitivity_never_changes_candidate_set`, `test_acceptance_sensitivity_after_base_candidates_vector` passed. |
| 8 | Every analytical test contains an explicit LREQ marker and a matching matrix entry; missing markers or entries fail local test execution, and a machine-checkable bidirectional traceability check verifies every required test maps to valid individual `LREQ-*` IDs and every individual `LREQ-*` has at least one required test reference. | `python -m niche_scout.tools.validate_traceability` → `Traceability valid: 89 required/defined LREQ IDs mapped, 582 matrix nodes, 0 unmarked analytical tests outside exemption (3 exempted non-analytical nodes)`; the validator command (not a conftest hook) is the enforcement mechanism (R2c). |
| 9 | `python -m niche_scout.tools.validate_traceability` passes for `tests/traceability.json` and pytest markers. | Same command/output as #8 (exit 0). |
| 10 | The scope-prohibition check passes against the maintained retired-feature list; no stale requirement from the retired SRS is accidentally implemented. | `python -m niche_scout.tools.check_scope_prohibitions` → `Scope prohibitions valid: no retired token found … (6 tokens checked)` (exit 0). |

**GATE: PASSED** — every bullet has evidence. Full suite `596 passed, 0 failed`;
`check_import_boundaries` valid; `check_secrets` valid. Out of scope and recorded: repo-wide
`ruff check` debt (244 errors) / `ruff format --check` (14 files), unchanged (R10), and the
`quality_workflow` command therefore exits non-zero on the repo-wide ruff step; the files Chunk 13
added/changed pass both ruff steps.