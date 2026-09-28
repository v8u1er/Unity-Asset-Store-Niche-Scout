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
| 1 | Plan | BLOCKED | `chunk-planner` authored `Documents/plans/chunk-23-coveo-transport-retry-and-persisted-failure-cause.md` as **DRAFT — BLOCKED** (510 lines, R1+R2 separated). Two rulings gate freeze (Q1 frozen-signature change; Q2 `category_scores` column addition), five design questions follow. Stopped per `AGENTS.md` (surface, never resolve). No commit. |
| 2 | Tests first | PENDING | |
| 3 | Implement | PENDING | |
| 4 | Verify (lead) | PENDING | |
| 5 | Review | PENDING | |
| 6 | Gate | PENDING | |

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