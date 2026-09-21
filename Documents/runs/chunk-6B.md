# Run log — Chunk 6B: Unique enrichment executor and persistence

| Stage | Status | Notes |
|---|---|---|
| Preflight | DONE | Branch `chunk-6B` created from `chunk6`. Working tree clean. |
| Integration | DONE | Branch integrated with `main` (merge commit `221995f`, "Merge base branch main into chunk-6B (Chunks 7A/7B/8)"). Post-merge: `python -m pytest -q` → **371 passed in 13.37s**. Prerequisites now verified on-tree: Chunk 4B run log `GATE: PASSED` (line 209), Chunk 5 interface `VERIFIED`, Chunk 6A run log `GATE: PASSED` (line 106) + interface `FROZEN`, **Chunk 7A run log `GATE: PASSED` (line 109) + interface `VERIFIED`**, **Chunk 7B run log `GATE: PASSED` (line 91, re-affirmed line 141) + interface `VERIFIED`**, Chunk 08 interface `VERIFIED` (context, not a 6B prerequisite). |
| Plan (first attempt) | BLOCKED | `chunk-planner` hit its step limit (INCOMPLETE) after research; no plan file written. The apparent 6B/7A conflict was an artifact of the `chunk-6B` branch predating the 7A/7B work; resolved by integration plus operator ruling. |
| Plan — rulings | RESOLVED | Operator rulings recorded below. |
| Plan (re-dispatch) | FROZEN | `Documents/plans/chunk-6B-unique-enrichment-executor-and-persistence.md` (Status: FROZEN) and `Documents/interfaces/chunk-6B.md` (Status: FROZEN) written from the real 7A/7B API. Planner raised sub-questions Q1–Q6; the operator delegated the recommended answers, so the lead resolved them as L1–L6 (plan §12) without inventing SRS semantics or changing a frozen interface. §5.2 code fence repaired in both files. |
| Implement | DONE | Split into bounded micro-steps to avoid the subagent output limit (operator-directed reorganisation). Step A (§5.1–§5.3 union/projection/executor) `48e243d`; B1 (cutoff + `finalize_stratum_counts`) `509e042`; B2 (`finalize_enrichment` + persistence) `50c3e5f`; B3 (`assert_finalization_consistency`) `e1d521a`. Each step `pytest -q` green, ruff clean, traceability valid. |
| Tests | DONE | C1 (§5.1–§5.3, 14 nodes) `94a3ac4`; C2a (§5.4, 7 nodes) `e963f06`; C2b (§5.5, 7 nodes) `4bf1984`; review fix added 1 node `046d7c2`. 29 new nodes total, markers limited to `LREQ-GQL-080`/`LREQ-NFR-020`/`LREQ-NFR-030`/`LREQ-SMP-080`; traceability entries added. |
| Verify | DONE | Lead-run after each stage; final: `python -m pytest -q` → **400 passed**; `tests/test_enrichment.py` → **29 passed**; `python -m niche_scout.tools.validate_traceability` → valid (7 Chunk 0 requirements mapped, 316 matrix nodes, 89 LREQ IDs; 7 pre-existing unmarked Chunk 0 nodes, none new); `python -m niche_scout.tools.check_import_boundaries` → valid for `metrics.py`/`scoring.py`; `ruff check`/`ruff format --check` clean on `pipeline.py`, `tests/test_enrichment.py`, `tests/fixtures/enrichment_fixtures.py`. Whole-project `ruff check .` reports 245 pre-existing findings in other chunks' files (e.g. `collector_coveo.py`), not introduced by 6B. |
| Review | Round 1 FAIL → fixed; Round 2 PASS | See "Review findings" below. Round-2 verdict: `VERDICT: PASS` (Major resolved, no regression). |
| Gate | **PASSED** | Per-bullet evidence below. Final: `pytest -q` → **400 passed**; `tests/test_enrichment.py` → **29 passed**; `validate_traceability` → valid; `check_import_boundaries` → valid for `metrics.py`/`scoring.py`; ruff clean on all 6B files. |

## Gate record — dependency map §3 Chunk 6B, lines 927–932

| # | Gate bullet | Evidence (test node / source) |
|---|---|---|
| 1 | Overlapping category samples cause at most one enrichment execution per unique identity. | `compute_enrichment_union` dedups by `asset_identity_key` (`pipeline.py`); `test_union_overlapping_categories_dedups_identities` (`tests/test_enrichment.py:109`), `test_union_reference_count_never_inflates_execution` (:155), `test_enrich_executes_one_request_per_pending_identity` (:248). |
| 2 | Successful preflight observations are not requested again. | `test_union_reuse_split_excludes_preflight_keys` (:141), `test_enrich_does_not_request_reused_preflight_identities` (:266); executor iterates only `union.pending_keys`. |
| 3 | A failed asset does not abort unrelated assets. | `test_enrich_failed_asset_does_not_abort_unrelated_assets` (:290). |
| 4 | No bulk-enrichment request is issued when the preflight gate is failed or `insufficient`. | `test_enrich_failed_preflight_issues_zero_requests` (:344), `test_enrich_insufficient_preflight_issues_zero_requests` (:372); gate-first branch in `enrich_unique_identities`. |
| 5 | After enrichment, every sampled stratum has final usable counts or an explicit unavailable/invalid status with the eligibility rule used; pending placeholders are not left in a completed run. | `test_finalize_usable_status_and_eligibility_rule_present` (:605), `test_no_pending_usable_status_after_finalize` (:849), `test_finalize_zero_population_category_is_empty_and_zero` (:664); §5.6 token emitted by `finalize_stratum_counts`. |
| 6 | Final `u_demand_h`, `u_recent_h`, `u_quality_h` agree with the pure metric inputs and are consistent across `sample_members`, `enrichment_observations`, `stratum_statistics_json`, and `category_scores`. | `test_finalize_agrees_with_chunk7b_compute_category_raw_metrics` (:736), `test_finalize_category_counts_equal_sum_over_usable_strata` (:690), `test_assert_consistency_clean_run_returns_no_mismatches` (:823), `test_assert_consistency_detects_injected_drift` (:792), `test_finalize_enrichment_merges_consistency_assertion_mismatches` (:909), `test_finalize_is_idempotent` (:876), `test_finalize_serialization_is_byte_deterministic` (:643), `test_finalize_unique_enrichment_count_identical_on_every_category` (:769); `finalize_enrichment` runs §5.5 checks A–E after the write (`pipeline.py`). |

**GATE: PASSED** — every bullet has direct test evidence and the full suite, traceability validator,
import-boundary check, and the configured linter/format check pass for the 6B files.

### UNVERIFIED (carried, as planned)
Chunk 10 integration is outside this chunk: the caller must derive `already_enriched_keys` from the
persisted `enrichment_observations`, capture `scoring_cutoff_utc` once at SRS §3.2 step 10, run
`finalize_enrichment` before metric computation, and write `category_scores` without resetting the
6B-written counts. Not exercised in-repo (CLI/network forbidden).

## Review findings

- **Major (fixed, `046d7c2`)** — `finalize_enrichment` must run the §5.5 assertion and return it in
  `mismatches` (interface §5.4 step 4). Fixed; new node
  `test_finalize_enrichment_merges_consistency_assertion_mismatches`.
- **Minor (frozen prose corrected)** — interface/plan §5.4 said a non-UTC `now_utc` raises; the
  implementation converts aware non-UTC via `ensure_utc` per plan §12 L1. Text corrected to
  "aware non-UTC converted; naive raises".
- **Minor (frozen prose corrected)** — interface/plan §5.5 check A said "sum over strata"; it is a
  sum over strata the applicable `stratum_is_usable` accepts (plan §12 A3; SRS §6.5). Text corrected.
- **Minor (recorded, not fixed)** — plan §9 line 906 pins category-level demand `4`; SRS §6.5 and
  7B give `0`. Source follows the SRS; plan prose left frozen.
- **Minor (recorded, not fixed)** — `pipeline.py` `_draft_optional_int` (6A-owned, reused) falls back
  to `_safe_int(default=0)` on the mapping stand-in, contradicting its own docstring and hard rule 2.
  Unreachable with the real Chunk-5 draft; pre-existing 6A code, needs a separate lead decision.
- **Minor (recorded, not fixed)** — `test_projection_minimum_seconds_from_interval` echoes the
  interval with `pytest.approx` default rel tolerance; the computed golden uses `abs=1e-9`.
- **Minor (recorded, not fixed)** — no node covers the `union.members == ()` early return or the
  `finalize_enrichment` read-phase mismatch branches; the §9 node list did not require them.

## Fix round 1 (test-discovered)

C2b's agreement probe found `assert_finalization_consistency` check A summing `u_*_h` over all
strata while `finalize_enrichment` writes the category count over usable strata; a correct golden
run failed its own gate. Fixed in `036539e` (check A now filters with `stratum_is_usable`), and the
two consistency tests migrated to the canonical 4/5/3 golden (demand=0, recent=5, quality=0 per
7B/SRS §6.5). Plan §9 line 906's "category-level demand is 4" is a plan prose error contradicted
by plan §12 A3 and SRS §6.5; source follows the SRS. Recorded as a Minor.

## Adjudication — plan §9 naive-date fixture (Minor)

C2a could not build the plan §9 golden's "one with a naive date" observation: the persisted
`EnrichmentObservationRecord` validates `first_published_date_utc` as timezone-aware UTC
(`models.py` `_UtcRecord`; AGENTS.md rule 3), so a naive date cannot reach
`finalize_stratum_counts` through the frozen record. The test uses a missing date instead,
which yields the same unavailable outcome under the same rule branch (`"null"` rather than
`"naive_date"`). The frozen plan §9 prose is inaccurate on this one word; the fix is
non-interface and the plan is not reopened. Recorded as a Minor.

## Operator rulings (2026-09-21) — resolved

1. **6B/7A eligibility boundary — OVERRIDE the earlier recommendation.** 6B does **not**
   author an eligibility predicate in `metrics.py`. 7A/7B are VERIFIED/PASSED; a second
   predicate would create two sources of truth, and 7B's contract forbids re-derivation of
   7A's per-observation eligibility (`Documents/interfaces/chunk-7B.md` §5). 6B consumes
   7A's public primitives (`age_days_exact`, `age_normalized_page_view_index`,
   `is_within_recent_window`, `stratum_is_usable`, `quality_observation_eligibility`) and
   7B's public aggregates (`compute_category_raw_metrics`). 6B keeps the per-stratum
   `u_demand_h`/`u_recent_h`/`u_quality_h` **finalization** (map line 738) as aggregation
   over 7A/7B results — *the eligibility decision never leaves 7A*. Category-level counts
   are sums over usable strata and must equal 7B's `compute_category_raw_metrics` outputs;
   6B adds its own agreement assertion so drift fails in 6B's gate. A thin additive 7B-owned
   per-stratum counting wrapper is acceptable only with separate explicit sign-off.
2. **`scoring_cutoff_utc` timing — ruling (C).** Keep the SRS ordering: capture
   `scoring_cutoff_utc` once **after enrichment, immediately before metric computation**
   (SRS §3.2 step 10, line 217), and run 6B's finalization after that capture and before
   metric computation, using that one value. Satisfies SRS §3.2 step 10, map Chunk 10 gate
   lines 999 and 1004, and 6B gate line 763; still "post-enrichment" per 6B scope.
3. **`eligibility_rule` format — 6B defines it.** 4B assigned the value to 7A
   (`Documents/interfaces/chunk-4B.md:138-141`), but 7A shipped VERIFIED without defining it
   (repo-wide grep: no token/value format anywhere). 6B owns and freezes the value in a new
   `Documents/interfaces/chunk-6B.md`; source of content is 7A's
   `METRIC_UNAVAILABLE_REASONS` and the frozen `models.py` constants; record 7A as having
   delegated the encoding. Do not reopen 7A. Two shapes must be frozen: per-count rule
   identification (LREQ-SMP-080 requires the rule used for *each* usable count, while the 4B
   schema has one `eligibility_rule` key per stratum) and the mapping from the three counts
   to the single `usable_status` token. Derive the encoding from existing frozen constants
   only; invent no new version constant (SRS §14 defines none). Label spelling as a
   recommendation.

## Lead resolutions (delegated by the operator)

Planner sub-questions Q1–Q6 resolved by adopting the planner's recommendations
(plan §12, L1–L6): (L1) normalize the cutoff via `models.ensure_utc`, naive
raises; (L2) emit only `"usable"`/`"unavailable"`, `"invalid"` reserved
defensive; (L3) `eligibility_rule` = first unavailable reason in
`(stratum_index, sample_rank)` order, spelling a recommendation; (L4)
`upsert_category_scores` is the 6B finalization path with full-record
carry-forward; (L5) projection interval =
`GraphQLRetryPolicy().min_request_interval_seconds`; (L6) a
preflight-attempted identity (even a failed one) is not retried in 6B.

## Open obligations checked (not touched by 6B)

- URI trailing-identifier extraction rule 1.0.1 — still unverified, owner none. 6B does not touch identity extraction.
- OI-6 CSRF/session sufficiency — owner unassigned. 6B does not construct auth; it calls the Chunk 5 adapter.
- `runs.taxonomy_sha256` empty-hash rejection — owner Chunk 10. 6B does not construct `RunRecord`.
