# Chunk 27 — run log (D2 — rating missingness at the collector mapping layer)

Started 2026-09-29. Remediation/follow-on chunk: **no dependency-map §3/§4 row**
(chunk-14/24/25/26 precedent). Registration = plan + run log + branch.

Scope (operator-fixed): **D2 only** — Unity returns a literal `0` for
`rating.average` / `rating.count` on unrated assets; the adapter stores `0.0` / `0`,
violating SRS §1.2 ("missing is not zero") and §6.4 LREQ-GQL-050. Fix at the I/O
adapter (`collector_graphql` ProductDetail mapping), never in the pure layer.

Governing defect plan: `Documents/plans/chunk-26-analytical-defect-remediation.md`
§4 (D2 evidence, consumers, layer/rule) and §14.1 (operator-adopted OQ-3/OQ-4);
§2 item 2.

## Preflight

| Check | Result |
|---|---|
| Prior gate | chunk-26 `GATE: PASSED` — `Documents/runs/chunk-26.md:98`; merged to `main` at `7fdf92e` (log line 104; brief says d4baac7 — see note) |
| Working tree | clean — `git status --porcelain --branch` → `## main` only |
| Branch | `git switch -c chunk-27` → "Switched to a new branch 'chunk-27'" |
| Routing (plan) | `chunk-planner` → `test-author` (tests first) → `impl-deep` → `spec-reviewer` → lead gate |
| Next free id | `chunk-27` per operator-fixed scope; no `chunk-27*` artifact previously existed |

Note on the merge SHA: the run log records `Updating 44fe283..7fdf92e` for the
`chunk-26` fast-forward (chunk-26.md:102-104). The dispatch brief cites `d4baac7`.
The run log is the operative artifact; `d4baac7` is not yet confirmed against git.

## Baseline (lead-run, 2026-09-29; real output)

| Command | Real result |
|---|---|
| `python -m pytest -q` | **695 passed in 22.93s** — clean tree, no failures |

### Live-DB re-verification (lead, read-only `file:runtime/niche_scout.sqlite3?mode=ro`)

Latest run `run-2026-09-29T05:33:21.664034+00:00`. Counted from
`enrichment_observations` by `.scratch/chunk27_db_check.py`:

- rows / distinct `asset_identity_key`: **2400 / 2400** — confirmed.
- `rating_count==0` → **1559** (all `rating_average==0.0`) — confirmed.
- `rc==1` → **289** (all avg `0.0`); `rc==2` → **123** (all avg `0.0`) — confirmed.
- `rc>=5` → **305** — confirmed.
- `rc>0 & avg==0` → **416** (= 289+123+2+1+1) — confirmed.
- `rc>0 & avg>0` → **425**; `rc>0 & avg in (0,5]` → **425** — consistent.
- `avg IS NULL` → **0**; `cnt IS NULL` → **0** — no nulls persisted today (all literal zeros).
- Partition check: 1559+289+123+2+1+1+425 = **2400** ✓.
- Distinct `(count, avg)` pairs show the contradictions: `(3,0.0)×2`, `(9,0.0)×1`,
  `(18,0.0)×1`, plus 289+123 zero-avg rows below 3.

## Stage log

| Stage | Status | Evidence |
|---|---|---|
| Preflight (lead) | DONE | branch `chunk-27`; clean tree; chunk-26 GATE PASSED; baseline 695 passed; DB re-verified above. |
| Plan — `chunk-planner` | DONE (FROZEN) | First dispatch hit its step cap (INCOMPLETE, no file). An `explore` session (`ses_f12fa3e97ffeUihixiWLCDEJnx`) recommended answers to the six open questions; operator adopted them ("go with the suggested answers"). Re-dispatched `chunk-planner` (`ses_f12e27d59ffeft9nAxVc2WC4k8`); plan written (513 lines, §1–§13, `Status: FROZEN`, no open questions), then a follow-up edit froze the draft-path mechanism to one private `_map_rating_pair` builder. Lead verified §3.5/§8/§11 by read. Commit `3f8a15f`. |
| Tests — `test-author` | DONE | `ses_f12d66960ffejwARE7PjRyfzWm` hit its step cap after the edits were applied (2 message constants left unreferenced — see below). Files: `tests/test_collector.py`, `tests/fixtures/graphql_fixtures.py`, `tests/traceability.json`. Lead-reproduced below. Commit `7bf0f87`. |
| Implement — `impl-deep` | DONE | `ses_f12c21b37ffevDc8W4mCRamF16`. `src/niche_scout/collector_graphql.py` (+90) adds `_map_rating_pair` and calls it once in `validate_product_detail_payload`; `tests/test_collector.py` (+20/−6) pins the frozen codes/messages in 3 nodes (the test-author's unreferenced constants are now used). Lead-reproduced below. Commit `000b1b1`. |
| Verify (lead) | DONE | step-6 evidence in the "Implementation stage" section below; re-verified after the review fix (701 passed). |
| Review — `spec-reviewer` | PASS (round 2) | Round 1 `ses_f12adea2cffeMFeHjuBimCRHE9`: **FAIL**, 2 Blocker — (a) "unmocked clock" and (b) "`EnrichmentResult.issues` misses the code"; (a) lead-refuted by read (`git grep datetime.now\|utcnow\|time.time` over `collector_graphql.py` → nothing; `retrieved_at_utc` is caller-supplied; the only clock is the caller `pipeline.py:3387,:3445`), (b) lead-refuted by read + probe (the plan's channel is `result.product_detail.issues`, consumed by `pipeline._operation_diagnostic_issues` at `pipeline.py:627-646`, which iterates the operations, not `result.issues`). One part of Blocker (a) was ACCEPTED: no test drove the row-6 pair end-to-end — fixed. Round 2 `ses_f11d6c544ffeJUcKsTWE6PqopG`: **VERDICT: PASS**, 0 Blocker, 0 Major, 4 Minor (recorded below; Minors do not loop). |
| Gate (lead) | PASSED | Gate table below; `GATE: PASSED`. |

## Gate bullets (the plan must adopt these)

1. `rating_count==0, rating_average==0` round-trips as `None`/`None`.
2. The 416-row case persists `rating_average=None` with the integer count retained and a
   distinct, deterministic validation issue.
3. `count>0, avg in (0,5]` unchanged.
4. `metrics.py` / `scoring.py` unchanged; `check_import_boundaries` exit 0; no `or 0` /
   `.get(k, 0)` added.
5. pytest + four validators exit 0; ruff no new lint.
6. No SRS edit; no version bump; no out-of-scope file changed.

## Allowlist (chunk-planner confirms against its own §6)

- `src/niche_scout/collector_graphql.py`
- `tests/test_collector.py` and collector fixtures; any test pinning rating null-ness
  (`grep -rn "rating_average\|rating_count" tests/`)
- `tests/traceability.json` only if a new node ID is added
- `Documents/plans/chunk-27-*.md`, `Documents/runs/chunk-27.md`

NOT: `metrics.py`, `scoring.py`, `pipeline.py`, `database.py`, `report.py`, config, SRS,
sampling constants. A needed change outside this list is a STOP-and-flag, not an edit.

## Open questions and adopted answers

The planner raised six questions. An `explore` analysis session recommended answers,
and the operator adopted them (2026-09-29): "go with the suggested answers". Plan §3
records the frozen rule.

- **Q1 (channel).** Option (a) only: contradiction issues ride the ProductDetail success
  result's `issues` tuple → `PreflightObservation.diagnostic_summary_json` →
  `runs.identity_preflight_summary_json.diagnostic_summary_json`. The per-row
  `product_detail_error_summary` stays NULL (option (b) would need `pipeline.py`, out of
  allowlist). Success-path `error_summary=None` is NOT changed (rejected alternative,
  plan §6.1). Gate bullet 2's "persists" = the run-level audit-summary channel (plan §12).
- **Q2 (codes).** `rating_average_without_rating_count` (count==0, avg>0) and
  `rating_average_zero_with_positive_count` (count>0, avg==0). No code registry exists;
  unprefixed `snake_case`, not added to the four-code structural dedup dict.
- **Q3 (invariant).** Both codes stay out of `_classify_product_detail_failure`, so
  `is_valid=True` / `failure_class=NONE` and the retained count survive. Load-bearing:
  `select_operation_correlation_mode` stays `VALIDATED_POSITION`.
- **Q4 (precedence).** Total order on the typed pair (plan §3.1, rows 1–7). `count==0`
  with avg in {0, absent, null} → both `None`, no issue; key on the typed count, not the
  raw member (`0.0` count stays `response_wrong_scalar_type`).
- **Q5.** `avg>0` with count absent → unchanged, no issue.
- **Q6 (re-baseline).** Exactly one existing node changes
  (`test_product_detail_rating_average_accepts_integral_json_number`, case `(0, 0.0)`);
  six new nodes; a new fixture helper; traceability entries only for new node IDs.

Recorded-not-fixed: `Documents/interfaces/chunk-05.md` §5.6 omits `mapping_rule_version`
(plan §6.2) — outside the allowlist, not touched.

## Gate

Branch `chunk-27`, base `main`. Commits: `90db498` preflight · `3f8a15f` plan · `28b77f9` plan log · `7bf0f87` tests · `d886cf2` tests log · `000b1b1` implementation · `35d85db` impl log · `885a3a3` review fixes.

| Bullet (plan §12) | Evidence (command output / file:line) | Status |
|---|---|---|
| 1. `rating_count==0, rating_average==0` round-trips as `None`/`None` | `tests/test_collector.py::test_product_detail_rating_zero_count_and_zero_average_is_no_rating` passes; probe read at `collector_graphql.py:1204-1216` (row 5) → `(None, None, ())`. | PASS |
| 2. Row 6 persists `rating_average=None`, integer count retained, distinct deterministic issue in the audit-summary channel | `test_row_six_pair_persists_none_average_with_retained_count` (real `enrich_asset` → draft → `to_record`): probe output `draft.rating_average None`, `draft.rating_count 210 int`, `record.rating_average None`, `record.rating_count 210`; `result.product_detail.issues == ['rating_average_zero_with_positive_count']` consumed by `pipeline._operation_diagnostic_issues` (`pipeline.py:627-646`) → `diagnostic_summary_json` (`:669, :678-680`). | PASS |
| 3. `count>0, avg in (0,5]` unchanged | `test_product_detail_rating_average_accepts_integral_json_number` (cases `(5, 5.0)`, `(4.5, 4.5)`) and the row-7 branch (`collector_graphql.py:1218`) pass; `tests/test_validation.py` pure `[0,5]` nodes untouched. | PASS |
| 4. `metrics.py`/`scoring.py` unchanged; `check_import_boundaries` exit 0; no `or 0` / `.get(k, 0)` added | `git diff main --name-only -- src/niche_scout/metrics.py src/niche_scout/scoring.py` → empty; `check_import_boundaries` → exit 0; reviewer grep for `or 0`/`.get(k,0)`/`fillna(0)` in `collector_graphql.py` → no match. | PASS |
| 5. pytest + four validators exit 0; ruff no new lint | `python -m pytest -q` → **701 passed in 23.54s**; `validate_traceability` exit 0 (89 IDs, 680 nodes); `check_import_boundaries`, `check_scope_prohibitions`, `check_secrets` exit 0; `ruff check collector_graphql.py` → `All checks passed!`; `ruff check tests/test_collector.py` → 29 errors, all pre-existing (highest flagged line 3337 < the new node at 4628). | PASS |
| 6. No SRS edit; no version bump; no out-of-scope file changed | `git diff main --name-only -- Documents/SRS-lean-v2.md Documents/interfaces/ src/niche_scout/{models,database,config,metrics,scoring,validation,pipeline,report}.py` → empty; `SCHEMA_VERSION = "1.2.0"` (`database.py:54`), `SAMPLING_RULE_VERSION = "2.0.0"` (`models.py:27`), `ENDPOINT_CONTRACT_VERSION = "1.0.0"` (`models.py:25`) unchanged; changed set = plan, run log, `collector_graphql.py`, `graphql_fixtures.py`, `test_collector.py`, `traceability.json`. | PASS |

**Gate: PASSED**, with four recorded Minors (below; none triggers a further fix round).

### Review findings (round 2; all Minor — recorded per procedure step 7)

1. `collector_graphql.py` `_map_rating_pair` folds out-of-domain typed negatives into rows 5/6 (`avg < 0, cnt == 0` → row-5 output; `cnt < 0, avg == 0.0` → row-6 code B though its message says "positive rating.count"). Direction is safe (nothing fabricated as zero; `metrics` keeps its inclusive `[0,5]` check) and the live data has no negative counts. Not in the frozen table; recorded, no test added.
2. Row-7 acceptance node parametrizes only `(5, 5.0)` / `(4.5, 4.5)`; no adapter `avg > 5` case. The pure-layer `[0,5]` boundary stays covered by the frozen `test_validation.py` nodes (plan §9.4 says unchanged). Coverage complement only.
3. `Documents/runs/chunk-27.md` ledger line for the implementation stage records 700 passed; final HEAD (`885a3a3`) is 701 passed / 680 matrix nodes (the review-fix node). Refreshed in this log.
4. `ruff format --check` on the touched files exits non-zero with pre-existing deviation; the `_map_rating_pair` region is absent from the format diff. Format ≠ lint; no new lint.

### Refuted reviewer findings (round 1 Blockers, no change made)

- "Unmocked clock in `enrich_asset`": refuted by read — `git grep -n "datetime.now\|utcnow\|time.time" -- src/niche_scout/collector_graphql.py` → no output; `retrieved_at_utc` is caller-supplied (`:2726-2754`, `:2887-2919`); the clock lives only in the caller (`pipeline.py:3387, :3445`).
- "Issue stripped from `EnrichmentResult.issues`": refuted by read + probe — the plan §3.4 channel is the operation success result's `issues` (`collector_graphql.py:2526`), consumed by `pipeline._operation_diagnostic_issues` (`pipeline.py:627-646`), which iterates `result.product_detail` / `result.page_views`; `EnrichmentResult.issues` carries correlation issues by design.

### Tests stage — lead-reproduced (real output)

| Command | Real result |
|---|---|
| `git status --porcelain` | only the three allowlisted test paths modified |
| `python -m pytest tests/test_collector.py -q --collect-only` | 98 tests collected, 0 errors (no syntax/collection errors) |
| `python -m pytest tests/test_collector.py -q` | **4 failed, 94 passed in 4.32s** — all four are missing-implementation value failures (`assert 0 is None` on `rating_count` / `rating_average`); no syntax or collection errors |
| `python -m pytest -q` | **4 failed, 696 passed in 45.18s** — the same 4 nodes; no collateral regression (695 baseline + 5 new nodes; the re-baselined accepts node keeps its ID) |
| `python -m niche_scout.tools.validate_traceability` | exit 0 — 89 IDs, **679 matrix nodes** (was 673 at chunk-26; +6) |
| `python -m ruff check tests/test_collector.py tests/fixtures/graphql_fixtures.py` | **39 pre-existing errors** (E501 ×~35, I001 ×2, F401 ×3) — none chunk-27-introduced except 3 E501 on new long test `def` lines. Recorded so the gate uses "no new lint" (chunk-25/26 precedent). |
| `python -m ruff format --check` on the same two files | 2 files would be reformatted; the diff is **not** confined to chunk-27 hunks (pre-existing formatting deviation across both files). Format ≠ lint. |

**Test-author cap note (carried into implementation):** two module constants
`RATING_AVERAGE_WITHOUT_COUNT_MESSAGE` / `RATING_AVERAGE_ZERO_WITH_COUNT_MESSAGE`
(`tests/test_collector.py:4422-4429`) are defined but unreferenced, and the row-6 node
asserts the code as a **literal** (`:4265`) rather than via
`RATING_AVERAGE_ZERO_WITH_COUNT_CODE`. The implementer must make the row-4 and row-6
nodes assert the frozen message constants (plan §3.2) and use the CODE constants, then
re-run pytest; that is an in-scope test fix within the allowlist (the implementer must
not weaken any assertion).

### Implementation stage — lead-reproduced (step 6, real output)

Changed: `src/niche_scout/collector_graphql.py` (+90), `tests/test_collector.py` (+20/−6).

| Command | Real result |
|---|---|
| `python -m pytest -q` | **700 passed in 26.66s** |
| `python -m niche_scout.tools.validate_traceability` | exit 0 — 89 IDs, 679 matrix nodes |
| `python -m niche_scout.tools.check_import_boundaries` | exit 0 — valid for `metrics.py`, `scoring.py` |
| `python -m niche_scout.tools.check_scope_prohibitions` | exit 0 — 6 tokens, none retired |
| `python -m niche_scout.tools.check_secrets` | exit 0 |
| `python -m ruff check src/niche_scout/collector_graphql.py` | `All checks passed!` |
| `python -m ruff check tests/test_collector.py` | **29 errors** — all pre-existing (32 at the tests commit, less the 3 chunk-introduced E501s the follow-up wrapped; the remaining 29 exist on `main`). No new lint from this chunk. |
| `python -m ruff format --check src/niche_scout/collector_graphql.py` | 1 file would be reformatted — **pre-existing** hunks at `:706`, `:832`, `:1677`, `:1697`, `:1788`, `:2307`; the new `_map_rating_pair` region is absent from the diff |
| `python -m ruff format --check tests/test_collector.py` | would be reformatted — pre-existing hunks only |
| `git diff --name-only main -- src/niche_scout/metrics.py src/niche_scout/scoring.py` | empty — pure modules unchanged |
| `git diff main --name-only` | plan, run log, `collector_graphql.py`, `graphql_fixtures.py`, `test_collector.py`, `traceability.json` only |
| `python -c "..."` | `_map_rating_pair` present; `ENDPOINT_CONTRACT_VERSION == "1.0.0"` (no bump) |

### Test-author questions (none raised; notes only)

The test-author returned `QUESTIONS: none` and `DISPUTES: none`.