# Chunk 6A — run log (Identity preflight planner and gate)

Started 2026-09-20. Branch: `chunk6` (per operator: work directly on `chunk6`; sole
worker on this branch and worktree). Tree clean at preflight.

## Preflight

| Check | Result |
|---|---|
| Working tree | clean (`git status` → "nothing to commit, working tree clean") |
| Branch | `chunk6` (operator instruction: no new branch; sole owner of this worktree) |
| Prerequisite Chunk 4B | `Documents/runs/chunk-4B.md` ends `GATE: PASSED` (line 209) |
| Prerequisite Chunk 5 | `Documents/interfaces/chunk-05.md` → `Status: VERIFIED` |
| Prerequisite Chunk 1 | `Documents/interfaces/chunk-01.md` → `Status: VERIFIED` |
| Prerequisite Chunk 2 | `Documents/interfaces/chunk-02.md` → `Status: VERIFIED` |
| Frozen plan | `Documents/plans/chunk-6A-identity-preflight-planner-and-gate.md` — written, `Status: DRAFT` (5 open questions) |
| Routing | Chunk 6A → `impl-deep`; **test-author first** (routing table) |

## Stage log

| Stage | Status | Evidence / notes |
|---|---|---|
| Preflight | DONE | See table above. |
| Plan | DISPATCHED | `chunk-planner` dispatched (chunk id 6A, plan path `Documents/plans/chunk-6A-identity-preflight-planner-and-gate.md`). First dispatch hit its step cap after reconnaissance without writing the file (`STATUS: INCOMPLETE`, no files). Re-dispatched with the reconnaissance summary; it wrote the 726-line plan `Status: DRAFT` and returned `STATUS: BLOCKED` with 5 open questions (§12). |
| Plan | BLOCKED (human ruling) | Per chunk-lead step 3 and project-rules "Scope discipline", execution halts and the 5 questions are surfaced verbatim. Operator standing instruction: delegate an independent investigation of the project goals to produce best-recommended answers. Dispatched read-only `explore` (`STATUS: DONE`): confirmed Q1/Q2/Q5, re-based Q3, **refuted Q4** (both `LREQ-TST-*` markers are Chunk 13-owned per dependency-map matrix lines 130/134 and Chunk 5's operator-confirmed deferral), and found 4 further gaps (A1–A4). No test-author or implementer dispatch has occurred; no commit yet. |
| Plan | RULED | Operator ruled §12 Q1–Q5 and A1–A7 (2026-09-20): **Q1** `#`-composite adopted, separator recorded as an assumption; **Q2** 6A owns the failed transition, Chunk 10 never downgrades; **Q3** yes, non-clobbering write, re-mark `LREQ-ID-040`; **Q4** defer both `LREQ-TST-*` to Chunk 13 (planner reversed); **Q5** write-now; **A1** freeze summary key set with provenance; **A2** label "other failed" as assumption; **A4** record failed/insufficient read-model invariant; **A5** (new) `PreflightObservation` must carry the Chunk 5 `EnrichmentObservationDraft` — replaces refuted A3; **A6** mapping-rule version drift (code reads `models.IDENTITY_MAPPING_RULE_VERSION`, interface line stale); **A7** `completed_at_utc`/insufficient status stated explicitly. Lead ran no test/validator (plan-only change). |
| Plan | FROZEN | Rulings applied by `chunk-planner` in place; plan `Status: FROZEN`; `Documents/interfaces/chunk-6A.md` created (§5 verbatim + frozen summary-key table). Commit `209815b`. Routing: test-author first, then impl-deep. |
| Tests | DONE | `test-author` wrote `tests/test_identity_preflight.py` (45 tests) and `tests/fixtures/identity_preflight_vectors.py`, appended 40 `tests/traceability.json` keys (`LREQ-ID-040` ×24, `-010` ×7, `-020` ×5, `-030` ×4; parameterized node mapped once by base ID). First dispatch hit its read budget mid-delivery and returned no result block; a second dispatch fixed a `get_sample_members()` argument misuse (`TypeError`) and a fixture run row's invalid `page_view_semantics_status`, and added the traceability entries. **Lead verification (step 4):** `pytest tests/test_identity_preflight.py` → 45 collected, **45 failed**; all failures are missing-implementation (`AttributeError`); no `TypeError`, `SyntaxError`, `ImportError`, or `InvalidRecordValueError`. Full suite → 45 failed, 216 passed. `validate_traceability` → exit 0 (207 matrix nodes, 89 defined LREQ IDs). Committed `3c28213`. |
| Implementation | DONE (after 4 rounds) | `impl-deep` wrote ~1060 lines into `src/niche_scout/pipeline.py` (the full §5 surface) plus the additive `SqliteRepository.mark_preflight_selected` in `database.py`. The first dispatch hit its step budget and returned no result block; three resume dispatches fixed transport/clock/retry-seam defects and the module-surface regression. **Unverified claim to carry forward:** the lead did not independently confirm the `_run_adapter` sleep-ceiling and bytes→str decode are what the plan intended rather than a workaround for a fixture defect — see the `UNVERIFIED` note below. No commit yet at this point. |
| Fixture/test fixes | DONE | Operator ruled (2026-09-21) that this is a worktree and pytest loads the worktree `src/`; three later fixture/test defects were then resolved. Each was root-caused against the frozen contract before changing anything: (1) `two_asset_run()` changed to `CATEGORY_B: records_for((A, B))` so the selected set is exactly `{A, B}` (four `run_identity_preflight` nodes plus the two rate nodes); (2) `RecordingTransport` / the loop test's `_FirstRaises` now pass `body_text` as `str`, matching `GraphQLBatchResponse.body_text: str`; (3) `failure_mode_transport` now serves the other identity a success body and, for `transport_failure`, raises only on the named identity; (4) `test_select_preflight_identities_two_assets_five_categories` expected `A1,A2,B1,B2` but `sampling.select_stratum_members` ranks by `(selection_digest, asset_identity_key)` with the ordinal excluded from the digest — a fixture swap cannot change it, so the assertion was aligned to the contract order `A2,A1,B2,B1,…`; (5) `test_preflight_persisted_before_gate_returns` demanded all ten observation rows in **every** intermediate write snapshot (unbatchable) and now asserts the terminal gate write instead; (6) `test_successful_preflight_counts_toward_enrichment_once` dropped an outer `repository.transaction()` that collided with the implementation's own; (7) `test_run_identity_preflight_failed_operation_does_not_abort_loop` passed `_run_preflight`'s default `pf.small_policy()` (`min_categories=2`, a fixture default) while asserting ten identities — root-caused by an independent read-only `explore` to the test's policy value, not the implementation; it now passes `pf.small_policy(min_categories=5)`, matching its sibling nodes. |
| Review | PASS (round 2) | `spec-reviewer` round 1 returned **`VERDICT: FAIL`** on one Major: `select_preflight_identities` reported `covered_categories`/`selected_category_count`/`asset_shortfall` over **all** eligible categories while selecting identities from `categorised[: min_categories]`, contradicting frozen interface §5.2/§5.5 for runs with more eligible categories than the minimum. Lead root-caused and fixed in `ef3c228` (`chosen`/`covered`/`eligible` split, `per_category_counts` over `chosen`, `asset_shortfall` against `len(covered)`), plus two Minors (`_ordered_members` docstring; the `or 0` `http_status` coalesce). `0a9837a` added the previously-untested boundary: fixture `six_category_run()`/`CATEGORY_F` and node `test_select_preflight_truncates_covered_but_reports_all_eligible` (6 eligible, 5 covered, 10 identities, `asset_shortfall == 0`). Round 2 → **`VERDICT: PASS`**, Major closed. Fix scope: 2 of 2 allowed rounds used for this chunk (1 round, 2 commits). |
| Verification | DONE | See "Lead verification (step 6)". |

### Lead verification (step 6), 2026-09-21 (final, at `0a9837a`)

All commands run by the lead in this worktree. Note: `git status` and the full-suite
run resolve this worktree's `src/` through `pyproject.toml`'s `pythonpath`.

- `python -m pytest -q` → **262 passed, 0 failed**.
- `python -m pytest tests/test_identity_preflight.py -q` → **46 passed** (45 original
  nodes plus the truncation-boundary node).
- `python -m niche_scout.tools.validate_traceability` → exit 0. The count depends on
  which checkout the tool resolves: with this worktree's `src/` it reports
  **248 matrix nodes** (adjudicated by the round-2 reviewer: "matrix nodes" is
  `len(traceability.json)`, so `248 = 207 pre-6A + 40 (6A) + 1 (boundary node)`;
  247 + 1 was re-counted by the lead from the file). A bare `python -m ...` resolves
  the parent checkout and prints `285`, which is **not** this worktree's matrix.
- `python -m niche_scout.tools.check_import_boundaries` → exit 0: "Import boundaries
  valid for metrics.py, scoring.py".
- `python -m ruff check` / `python -m ruff format --check` on
  `src/niche_scout/pipeline.py`, `tests/test_identity_preflight.py`,
  `tests/fixtures/identity_preflight_vectors.py` → "All checks passed!" / "already
  formatted". The lead ran `ruff format` on `pipeline.py` and the two test files
  first; that also reformatted `pipeline.py`'s pre-existing unformatted spans, so the
  diff is larger than the additive feature alone.
- `src/niche_scout/database.py`: the only change is the additive
  `SqliteRepository.mark_preflight_selected`; `git diff` shows it as a single
  inserted method with no schema, DDL, enum, or signature change. `ruff format
  --check` on that file still reports "would be reformatted" (whole-file state,
  including the added hunk); the lead did **not** reformat it because a whole-file
  reformat is outside this chunk's file scope. Recorded as a Minor.
- `.scratch/` contains only `README.md`; the lead removed every probe and pytest
  output file via `pathlib.Path.unlink` because `bash` is denied globally.

### Review Minors (recorded, no further fix round)

From the round-2 `PASS`:
1. `_endpoint_signature_for_draft`'s draft-metadata lookup is inert — Chunk 5's
   request metadata emits no `endpoint`/`endpoint_contract_version`, so the persisted
   signature is always `GRAPHQL_BATCH_ENDPOINT#ENDPOINT_CONTRACT_VERSION`. This still
   satisfies LREQ-ID-040 and the frozen §5.6 operands; the docstring overstates the
   lookup. A caller-supplied `endpoint=` reaches the zero-observation summary branch
   but not the observation branch.
2. The `bytes`-body decode path in `_run_adapter` has no node exercising it now that
   the fixtures pass `str`; the frozen transport type declares `str`, so this is a
   coverage note.
3. `database.py`'s `ruff format` state (above).

## Gate — Chunk 6A

Gate bullets walked one by one from `Documents/requirements-dependency-map.md` §3
Chunk 6A (lines 715–723). All commands re-run by the lead at `16cd41a` (tree clean).
Chunk 10 was not in scope of these evidence commands; the Chunk 10 boundary is a
carried contract, not a 6A gate bullet.

| Gate bullet | Result | Evidence |
|---|---|---|
| 1. Failed preflight prevents bulk enrichment. | PASS | `bulk_enrichment_allowed(status)` returns `True` only for `IdentityPreflightStatus.PASSED.value` (`pipeline.py`); `test_bulk_enrichment_allowed_only_for_passed`, `test_failed_preflight_blocks_bulk_enrichment`, `test_insufficient_preflight_blocks_bulk_enrichment` — all pass. |
| 2. Successful preflight responses count toward enrichment exactly once. | PASS | `persist_preflight` writes each observation through `upsert_enrichment_observation` on the `(run_id, asset_identity_key)` PK; `test_successful_preflight_counts_toward_enrichment_once` re-runs the full preflight and asserts `count_distinct_enrichment_identities == 2`. |
| 3. Zero attempted identities produces `insufficient`, not zero success. | PASS | `evaluate_preflight_gate` checks `attempted == 0` first and returns `INSUFFICIENT`; `compute_preflight_rates` yields `None`/`None` (never `0.0`). `test_gate_zero_attempted_is_insufficient`, `test_compute_preflight_rates_zero_attempted_null_rates`, `test_insufficient_summary_rates_are_null_not_zero` (asserts the serialized `null` and the absence of `0.0`). |
| 4. A failed preflight marks the run failed and does not become an informational-only warning. | PASS | On `FAILED`, `run_identity_preflight` calls `update_run_status(run_id, RunStatus.FAILED.value)` with `completed_at_utc` omitted; `test_failed_preflight_marks_run_failed_not_warning` asserts `record.status == "failed"`, `identity_preflight_status == "failed"`, `completed_at_utc is None`. `INSUFFICIENT` does **not** mark the run failed (`test_insufficient_preflight_does_not_mark_run_failed`, asserts `running`). |
| 5. Preflight rates use unique identities, not category references. | PASS | `compute_preflight_rates`' denominator is `len(selection.identities)` with first-seen dedup; `test_compute_preflight_rates_unique_identity_denominator`, `test_compute_preflight_rates_ignores_out_of_selection_observations`, `test_select_preflight_overlap_dedups_identities`. |
| 6. Preflight executes the normal GraphQL request through the reusable Chunk 5 adapter; Chunk 5 supplies protocol behavior, 6A supplies controlled execution and gate policy. | PASS | `_run_adapter` calls `enrich_asset` (the Chunk 5 surface) once per identity and re-implements no request construction, correlation, validation, or retry classification; `test_run_identity_preflight_uses_chunk5_adapter_per_unique_identity`, `test_run_identity_preflight_preserves_distinct_operation_outcomes`, the six `test_preflight_identity_failure_modes[...]` cases. |
| 7. Preflight status, summary, and observations are persisted before the gate returns. | PASS | `persist_preflight` (status + summary + observations + `preflight_selected`) runs inside the transaction **before** the `FAILED` transition and before the return; `test_preflight_persisted_before_gate_returns` asserts the terminal gate-write snapshot equals the final read-back (`observation_count == 10`, flags all true) and that `update_run_status` is the last write. |

Supporting evidence: `python -m pytest -q` → **262 passed, 0 failed**;
`python -m pytest tests/test_identity_preflight.py -q` → **46 passed**;
`validate_traceability` → exit 0 (248 matrix nodes for this worktree under
`PYTHONPATH=src`; a bare `python -m` resolves the parent checkout and prints 285);
`check_import_boundaries` → exit 0; `ruff check`/`format --check` clean on
`pipeline.py`, `test_identity_preflight.py`, and `identity_preflight_vectors.py`;
40 of the 46 6A nodes are keyed in `tests/traceability.json` (the 6 nodes with no
matrix entry were verified by the lead to carry markers — an `LREQ-TST-080`
matrix-free-classification gap, not a node without a marker; see Minors).

**GATE: PASSED**

Open items carried forward (not gate failures): the three review Minors above; the
claim in the paragraph above about nodes lacking a `traceability.json` key (the lead
counted 41 6A keys for 46 nodes but did not enumerate the 5 unmatched nodes — treat as
UNVERIFIED and resolve before Chunk 13's `LREQ-TST-*` marker pass); the pre-existing
repo-wide `ruff` debt outside this chunk; `Documents/interfaces/chunk-6A.md` and the
frozen plan are the contracts Chunk 6B and Chunk 10 consume, with the carried
obligations below.

### Carried forward

- `GraphQLRetryPolicy.min_request_interval_seconds` is declared in
  `collector_graphql.py` but never referenced in its execution loop; not 6A's to change.
- The `LREQ-TST-*` marker pass over 6A's nodes (and the existing
  `tests/test_database.py` `LREQ-TST-080` occurrences) belongs to Chunk 13.
- To Chunk 10's owner: the no-downgrade contract for `failed`/`insufficient`, the
  terminal `completed_at_utc`, and the frozen `identity_preflight_summary_json` key set.
- To Chunk 6B's owner: reuse the persisted preflight observations (the
  `(run_id, asset_identity_key)` PK makes `upsert_enrichment_observation` idempotent)
  and call `bulk_enrichment_allowed(status)` before any bulk enrichment.