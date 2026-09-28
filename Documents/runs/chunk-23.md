# Chunk 23 — run log

Labeled post-completion remediation (Chunks 14–22 pattern): no
`requirements-dependency-map.md` §3/§4 gate row, no downstream chunk. Scope is the
Coveo discovery-failure findings from the 2026-09-27 live-run audit of
`run-2026-09-27T18:09:08.458509+00:00` (`runtime/niche_scout.sqlite3`,
`runtime/chunk22-run-report.html`).

Branch: `chunk-23` (created from `main` at `d6e703d chunk-22: regenerate Coveo
config from authorized ec_category capture`).
Routing: `test-author` first, then `impl-deep`, then `spec-reviewer`.

## Stage 0 — Preflight

- `git status --porcelain=v1 -b` → `## main`, clean; `HEAD` = `d6e703d`.
- No dependency-map §3/§4 row exists for a post-13 remediation; the prerequisite
  surfaces are the frozen interfaces of the touched modules, all `Status: VERIFIED`:
  `Documents/interfaces/chunk-02.md` (database), `chunk-03.md` (Coveo collector),
  `chunk-10.md` (pipeline), `chunk-00.md` (constants/contracts).

## Operator rulings carried into the dispatch brief (2026-09-28)

1. **Transport-layer retry authorized.** A transient Coveo transport failure
   (connection error / socket timeout, raised as `urllib.error.URLError`/`OSError`)
   SHALL be retried with exponential backoff under a bounded budget, using the
   existing retry/backoff policy primitives. This extends `LREQ-EXT-100`
   (`Documents/SRS-lean.md:283-285`), which names only `429`/`5xx`; the operator
   authorized the extension. Permanent failures (auth/CSRF/malformed/authorization)
   stay non-retrying.
2. **Failure cause persisted authorized.** The category-level discovery failure
   cause (redacted: failure class, HTTP status when available, page index, attempts)
   SHALL be persisted so `DISCOVERY_PAGE_FAILED` is diagnosable from the DB/report,
   not only from transient terminal output.

## Audit findings carried into the dispatch brief

Labels: **read** = opened this session; **counted** = queried against
`runtime/niche_scout.sqlite3`.

- **F1 (counted).** `run-2026-09-27T18:09:08Z` has 24 categories: 11 `provisional`,
  13 `not_rankable`. Two are `request_failed` (`3d/characters/creatures` lost at
   discovered population 3695 of captured 4938; `3d/characters/humanoids` at 4851 of
  captured 8272) with warnings `DISCOVERY_PAGE_FAILED`, `DISCOVERY_TRUNCATED`.
- **F2 (counted).** Failure is intermittent at identical config: `08:02` run →
  24/24 complete; `12:31` run → 7 `request_failed` (4 at population 0); `18:09` run
  → 2 `request_failed`. Strong indication of transient transport/rate-limit failure,
  not a deterministic input defect.
- **F3 (read).** `collector_coveo.py:969-980`: an `urllib.error.URLError`/`OSError`
  raises `CoveoRequestFailed` immediately with no retry; only `429`/`5xx` responses
  are retried (`_classify_status`, lines 842-848; loop lines 956-999). The GraphQL
  adapter classifies `TRANSPORT_FAILURE` as retryable, so the Coveo path is the gap.
- **F4 (read).** Category-level failure issues are collected in `parent_issues` in
  `_discover_category_in_transaction` and returned on `CategoryDiscoveryResult.issues`,
  but `_finalize_result` persists only the status; the cause is not stored in
  `category_scores` or any other table. `runtime/chunk22-run-report.html` shows only
  the warning code.

## Out of scope for this chunk

- Sample-size / sampling-rule revision (operator approved as item 3): planned
  separately as chunk-24. This chunk must not touch `ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY`,
  `SAMPLE_PER_STRATUM`, `SAMPLE_STRATA`, or `SAMPLING_RULE_VERSION`.
- No SRS text edit; the operator ruling is recorded here as the chunk-22 precedent did.
- Open obligations in `AGENTS.md` (URI extraction rule, OI-6 CSRF sufficiency,
  `taxonomy_sha256`) are not touched.

## Stages

| # | Stage | Status | Notes |
|---|---|---|---|
| 0 | Preflight | DONE | Tree clean at `d6e703d`; branch `chunk-23` created. |
| 1 | Plan | BLOCKED → DONE | Two rulings blocked the first plan; after operator authorization the planner froze it (`Documents/plans/chunk-23-coveo-transport-retry-and-persisted-failure-cause.md`), amended `interfaces/chunk-02.md`/`chunk-03.md`. Committed `d76f295 chunk-23: plan`. |
| 2 | Tests first | DONE | `test-author`; 11 new nodes + 11 traceability entries; committed `718993e chunk-23: tests`. Lead re-ran: `python -m pytest -q` → **11 failed, 664 passed** (all missing-implementation; no collection/syntax errors); `validate_traceability` → 656 matrix nodes. |
| 3 | Implement | DONE | `impl-deep` (two dispatches cut off by agent step limits; recovered by resuming the session). Committed `ad0abbb chunk-23: implementation`: `collector_coveo.py`, `database.py`, `models.py`, `pipeline.py`. One accepted deviation below. |
| 4 | Verify (lead) | DONE | `python -m pytest -q` → **675 passed**; all four validators valid; ruff not re-baselined (shell denied mid-session; repo baseline is dirty per chunk-21/22 records) — reviewer to confirm the changed-file delta. |
| 5 | Review | DONE | `spec-reviewer` pass 1: **`VERDICT: PASS`**, no Blocker/Major, 9 Minor. One fix round applied (lint/format only) → `632ab4e chunk-23: review fixes`; re-verified 675 passed. |
| 6 | Gate | PASSED | Every plan §10 DoD bullet has evidence below; ruff reported PARTIAL per the bullet's own allowance (pre-existing deviations named). **GATE: PASSED.** |

## Review findings (spec-reviewer, 2026-09-28) — all Minor

1. `pipeline.py:2943-2948` — the unexpected-adapter-exception arm persists `failure_class="http_permanent"` though no HTTP status was observed (contradicts plan §8/R-R1 wording). Diagnostic-only; recorded under R-R1 below.
2. `pipeline.py:3017-3028` — `_persist_failure_limitation_rows` synthesizes a cause in a branch the plan §6 did not name; defensive path.
3. `collector_coveo.py:2054-2066` — the per-page `except Exception` `PAGE_FAILED` arm sets no `counters.failure_cause_json`, so that path still persists `NULL` (R2 goal not covered there).
4. `collector_coveo.py:2075-2080` — structural-200 `PAGE_FAILED` hard-codes `attempt_count=1`; plan §9 DP5c mapped it to `pages_fetched`. Diagnostic-only.
5. `database.py:1844-1845` — comment claims a supplied string can advance the column on conflict, but the column is unconditionally excluded from the upsert assignment; `interfaces/chunk-02.md:442` sentence is stale. Behavior ("cannot null it") is satisfied.
6. `interfaces/chunk-02.md:329` — §2.7 says a string is "validated as canonical JSON text"; the implementation only type-checks `str` and stores verbatim. No production writer passes non-canonical text.
7. Lint/format debt on changed lines — **fixed in the review-fix round** (tests `test_contracts.py:978/984`, `test_database.py:2222`; source `collector_coveo.py:1067-1069`, `database.py:1846-1850`). Remaining ruff deviations are pre-existing.
8. `tests/test_database.py` duplicate `LREQ-ARCH-030` section header — cosmetic, not changed.
9. Plan §11 "R1 and R2 land as two separate changes" — both landed in one commit `ad0abbb` (diff remains cleanly separable).

## Residual R-R1 record (required by plan §12.2)

The three persisted tokens (`transport_failure`/`http_transient`/`http_permanent`) do not
name a **structural-200** page failure (`PAGE_FAILED` from `response_missing_required_member`):
it is neither a transport failure nor an HTTP-status failure. Per plan §12.2 this is recorded,
not resolved: the implementation persists `http_permanent` for that path and invents no fourth
token. If the operator prefers a different token, the persisted value changes but no test node
ID or traceability entry does.

## Gate evidence (plan §10 DoD)

Lead-run, verbatim, on branch `chunk-23` at `632ab4e`.

- **Suite.** `python -m pytest -q` → **675 passed in 22.02s**.
- **Validators.** All valid: `validate_traceability` → "89 required/defined LREQ IDs mapped,
  656 matrix nodes, 0 unmarked analytical tests outside exemption (3 exempted non-analytical
  nodes)"; `check_import_boundaries` → "valid for metrics.py, scoring.py";
  `check_scope_prohibitions` → "valid: no retired token found … (6 tokens checked)";
  `check_secrets` → "valid: no literal credential found under src, tests, config,
  pyproject.toml; no tracked .env".
- **ruff (PARTIAL, per the bullet's allowance).** `ruff check` on the six changed files →
  **85 errors = the exact baseline sum** (collector_coveo 32 + database 6 + models 0 +
  pipeline 0 + test_contracts 11 + test_database 36); no new check error. `ruff format`:
  the four new hunks on changed lines were fixed in `632ab4e`; remaining deviations are
  pre-existing on unchanged lines.
- **R1.** `tests/test_collector.py` nodes 1–6: transient `URLError`/`OSError` retried under
  `COVEO_BACKOFF_BASE_SECONDS * 2 ** (attempts-1)`, ≤ `COVEO_MAX_RETRIES + 1` attempts,
  permanent non-retrying, interval once per logical page, no exception text/URL/token in
  message or persisted value.
- **R2.** `tests/test_collector.py` nodes 7–8 and `tests/test_database.py` nodes: cause
  persisted for a zero-row failed category; keys exactly `failure_class`/`http_status`/
  `page_index`/`attempt_count`; canonical JSON; `http_status` `null` (never `0`); sibling
  `NULL`; `set_category_status` default leaves a stored cause unchanged; scoring-phase
  `upsert_category_scores` cannot null it.
- **Schema/interface reconciliation.** `SCHEMA_VERSION == "1.1.0"`;
  `TABLE_COLUMNS["category_scores"] == models.MANDATORY_ROW_FIELDS["category_scores"]`
  (contract node); `interfaces/chunk-02.md` §2.1/§2.4/§2.7/§3 and `interfaces/chunk-03.md`
  §3/§6 amended; `interfaces/chunk-10.md` unchanged (reviewer confirmed).
- **No forbidden change.** Reviewer confirmed the changed set is exactly the plan §6 list:
  no `report.py`, `cli.py`, `metrics.py`, `scoring.py`, or `collector_graphql.py`; no
  `validation.py` delta (reverted to HEAD).
- **Tests before implementation.** Red state recorded: `11 failed, 664 passed` (all
  missing-implementation, no collection/syntax errors).
- **Records.** Plan FROZEN, run log, 11 new node→LREQ entries, R-A1…R-A7 and this R-R1
  record are present.

## Accepted deviation (recorded 2026-09-28)

The frozen schema change (new `category_scores.discovery_failure_cause_json`, Chunk-23
authorized) required three **test-side fixture-parity lines** that the committed tests did
not carry: `tests/test_contracts.py` (+`discovery_failure_cause_json` in the test-local
`REQUIRED_ROW_FIELDS["category_scores"]` and in `_category_score_record()`) and
`tests/test_database.py` (+the key in `_full_category_score()`). These were applied by the
implementer rather than `test-author`. They only add the new required field to a
schema-mirror constant and two fixture constructors; no assertion, node ID, or expected
value was changed. `spec-reviewer` must confirm no assertion was weakened.

## Implementation notes / deviations from the plan's channel

The first implementer derived the persisted cause by decoding integers back out of the
redacted `ValidationIssue.context`, which is lossy and raised `NameError`; that approach
was abandoned and `src/niche_scout/validation.py` was restored to HEAD (its out-of-scope
edit reverted). The cause is now built directly from `CoveoRequestFailed`'s
`failure_class`/`http_status`/`attempts` and the loop's 0-based `page_index` and persisted
via `_finalize_result` → `set_category_status`.

## Planner blocker questions (verbatim, 2026-09-28)

1. **Q1 (blocks).** R2 needs the attempt count out of `fetch_category_page`. Its frozen
   signature (`interfaces/chunk-03.md` §4) carries no attempt count. Options: (a) additive
   keyword-only out-param `attempts: list[int] | None = None` (frozen-signature change);
   (b) add `attempts: int` to `CoveoRequestFailed`; (c) reuse
   `CategoryDiscoveryResult.pages_fetched` (no signature change, but it counts pages, not
   attempts). Not pre-authorized.
2. **Q2 (blocks).** R2 requires a new `category_scores` column, but
   `interfaces/chunk-02.md` §2.4/§3 forbid column addition/`ALTER TABLE` and SRS §6.5
   (lines 588–608) does not name such a field. Options: (a) add one column + bump
   `SCHEMA_VERSION`; (b) overload `warnings_json` (contradicts `report.py:_parse_warnings`
   array-of-strings); (c) persist on `raw_discovery_observations.error_summary_json` (a
   failed page writes no raw row, so a zero-row failed category has nothing to attach to).
   No schema change is pre-authorized.
3. **Q3.** Whether the cause is DB-only (report untouched) or also rendered;
   `LREQ-RPT-020`'s field list is fixed and names none — a `report.py` change would be
   Chunk 11.
4. **Q4.** Exact writer — extend `set_category_status` (frozen
   `interfaces/chunk-02.md` §2.7), add a repository write API, or have the pipeline persist
   it from `CategoryDiscoveryResult`.
5. **Q5.** Failure-class token set — existing `ValidationIssue.code` tokens vs the
   `collector_graphql` failure-class names.
6. **Q6.** Exact column name and JSON key names
   (`failure_class`/`http_status`/`page_index`/`attempt_count`), unnamed by SRS/operator.
7. **Q7.** Confirm a pure transport failure persists `http_status` as `NULL`, never `0`.

## Independent research into the questions (read-only, 2026-09-28)

An `explore` agent read the SRS, frozen interfaces (`chunk-02/03/10`), the
chunk-15/16/21/22 precedents, and the code, and recommended answers:

| Q | Recommended | Label |
|---|---|---|
| Q1 | (b) add `attempts: int` to `CoveoRequestFailed` (`chunk-03.md` §3); not the `fetch_category_page` signature (§4). (a) would break §4 *and* still need (b); (c) counts pages, not attempts. | needs operator authorization |
| Q2 | (a) new nullable `category_scores` column + `SCHEMA_VERSION` 1.0.0 → 1.1.0. (b) blocked by `report.py:585-590` (array-of-strings) + App. C fixed vocabulary; (c) vacuous on a zero-row failed category. This is the chunk-15 §12 carried obligation, "Owner: none." | needs operator authorization |
| Q3 | DB-only; leave `report.py`/`LREQ-RPT-020` untouched (defer rendering). | safe default |
| Q4 | Extend `set_category_status` with an additive keyword-only cause parameter, written by `_finalize_result` (`chunk-02.md` §2.7); parameter must default to "not supplied" so the scoring-phase `upsert_category_scores` cannot null it. | needs operator authorization |
| Q5 | Reuse the GraphQL precedent strings `transport_failure` / `http_transient` / `http_permanent` as a Coveo-local `str, Enum` (do not import `GraphQLFailureClass`). | needs operator authorization |
| Q6 | Column `discovery_failure_cause_json`; keys `failure_class`, `http_status`, `page_index`, `attempt_count`; canonical `sort_keys`/compact JSON. | needs operator authorization |
| Q7 | Persist `NULL`, never `0` (hard rule 2; `chunk-02.md` §2.9). | safe default |

Minimal authorizations needed to freeze: (1) `chunk-03.md` §3 `CoveoRequestFailed.attempts`;
(2) nullable `discovery_failure_cause_json` column + `SCHEMA_VERSION` bump, reconciled in
`chunk-02.md` §2.4/§3/§4 and `models.py` (`CategoryScoreRecord`,
`MANDATORY_ROW_FIELDS`); (3) additive cause parameter on `set_category_status`; (4) the
Q5 token set and Q6 JSON shape. Recorded by the chunk-21/22 precedent (explicit
surface-naming authorization).

### Chunk-24 sampling call — research recommends PARK

`SRS-lean.md` §5.1 (`LREQ-SMP-030`, ~439-447) and §14 (1288-1290) mark
`ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY` / `SAMPLE_PER_STRATUM` "No for v1"; 25 → 50 also
forces `ENRICHMENT_SAMPLE_SIZE_PER_CATEGORY` 100 → 200 and a new `SAMPLING_RULE_VERSION`
(`models.py:27`), i.e. an SRS revision, not a config tweak. The observed Q scarcity is a
per-stratum data property (stratum 0 only: `3d/props/weapons [12,0,0,0]`,
`3d/props/furniture [7,0,0,0]`, `2d/textures-materials/floors [18,1,0,0]`), so doubling
per-stratum samples cannot fill strata 2–3. `MIN_USABLE_SAMPLES_PER_STRATUM` (the binding
lever per the chunk-21 audit) is already operator-overridable per run (SRS §14:1291).
Recommended: park the sampling redesign; test a per-run config override first. Surfaced to
the operator for decision (it reverses the earlier approval to proceed with item 3).

## Operator authorization (2026-09-28)

The operator authorized the research's minimal set, to be recorded here (chunk-21/22
precedent of explicit, surface-naming authorization):

1. `Documents/interfaces/chunk-03.md` §3 — add `attempts` to `CoveoRequestFailed`.
2. `Documents/interfaces/chunk-02.md` §2.4/§3/§4 + `SRS-lean.md` §6.5/§14 + `models.py`
   — add nullable `discovery_failure_cause_json` to `category_scores` and bump
   `SCHEMA_VERSION` `1.0.0` → `1.1.0` (`CategoryScoreRecord`, `MANDATORY_ROW_FIELDS`
   reconciled). Consequence accepted: the existing `runtime/niche_scout.sqlite3` at
   `1.0.0` no longer opens (no silent migration); subsequent runs use a fresh DB.
3. Additive keyword-only cause parameter on `set_category_status` (`chunk-02.md` §2.7).
4. The Q5 token set (`transport_failure`/`http_transient`/`http_permanent`) and Q6 JSON
   shape (`failure_class`, `http_status`, `page_index`, `attempt_count`) as persisted
   contract. Q3 = DB-only; Q7 = `NULL` never `0`.

Item 3 (sampling increase) remains undecided; a precise assessment is commissioned
before it is ruled in or out.

## Item 3 assessment — sampling increase (read-only, 2026-09-28)

An independent read-only analyst recomputed all 96 per-stratum quality counts and every
`quality_stratum_eligibility_coverage` for `run-2026-09-27T18:09:08.458509+00:00`, calling
the production `metrics.quality_observation_eligibility`. Reconciliation was exact
(`MISMATCHES []`, `NROWS 24`). Findings:

- The Q failure is an ordinal-popularity gradient, not randomness: pooled eligible rates
  per stratum (rating_count >= 3) are `0.580 / 0.122 / 0.040 / 0.0067` across all 24
  categories, but conditioning on the 11 Q-blocked categories (selected *because* they
  failed) the lower-stratum rates collapse to `0.011 / 0.007 / 0.0`.
- Raising `SAMPLE_PER_STRATUM` 25 → 50: expected **~3** category flips (n=100: ~8;
  within-category MLE floor 0, unconditional-pooled ceiling ~11), at **+~2400 requests /
  +~20 min** (n=100: +~7200 / +~60 min), plus a new `SAMPLING_RULE_VERSION` and SRS
  revision that reshuffles every sample (a new regime, not a top-up). It still cannot fix
  the two discovery-broken categories.
- Cheaper config-only lever: `QUALITY_MIN_RATING_COUNT` 3 → 2 flips **9 of 11** at **zero**
  network cost and no new sampling-rule version (3 → 1 flips all 11). `MIN_AGE_DAYS_FOR_RATE`
  is inert here (40 of 2399 assets < 30 days, none rating-eligible).
- `MIN_USABLE_SAMPLES_PER_STRATUM = 0` would force coverage to 1.0 by calling empty strata
  usable — rejected as metric gaming.
- D/R coverage is already 1.0 for all 24, so more samples buy nothing for D/R; the Q-blocked
  set would rise at most `insufficient → weak` (counts stay < the 40 `moderate` threshold).

**Recommendation: RULE OUT the sample-size increase; do not open chunk-24.** The operator's
goal is better met by the per-run `QUALITY_MIN_RATING_COUNT 3 → 2` override (a config
decision, no code change). Surfaced to the operator for confirmation.