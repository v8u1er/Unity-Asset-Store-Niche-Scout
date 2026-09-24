# Chunk 17 — run log (GraphQL live-contract remediation, post-Chunk-16)

Post-completion remediation requested by the human after two live `niche-scout run`
attempts reached the identity preflight and failed it. Labeled chunk (same pattern as
Chunks 14/15/16): no dependency-map §3 gate row; the dispatch DoD is the gate.
Goal: make a human `python -m niche_scout run` reach and **pass** the identity preflight
against the live endpoint with the two proven protocol defects corrected and the minimum
consequential changes.
Plan: `Documents/plans/chunk-17-graphql-live-contract-remediation.md` (planned).

## Preflight

| Check | Result |
|---|---|
| Working tree | clean at start (`git status` → "nothing to commit, working tree clean", branch `main`, HEAD `4ff26e7`) |
| Branch | created `chunk-17-graphql-live-contract-remediation` off `main` @ `4ff26e7` (`git switch -c`, succeeded) |
| Prerequisites | Chunks 1, 2, 3, 4A, 4B, 5, 6A, 6B, 7A, 7B, 8, 9A, 9B, 10, 11, 12, 13 all `GATE: PASSED`; interfaces `chunk-05.md`, `chunk-06A.md`, `chunk-06B.md`, `chunk-10.md`, `chunk-12.md` `Status: VERIFIED`; Chunk 14 `GATE: PASSED` (`runs/chunk-14.md:142`), Chunk 15 `GATE: PASSED` (`runs/chunk-15.md:88`), Chunk 16 `GATE: PASSED` (`runs/chunk-16.md:110`). |
| Routing | `chunk-planner` → `test-author` → `impl-deep` → lead verify → `spec-reviewer` → lead gate (dispatch-specified; the remediation touches adapter/protocol logic, so tests-first). |

## Grounded findings (labels: read / counted / live / unverified)

| # | Finding | Evidence |
|---|---|---|
| D1 | The adapter emits `x-csrf-token` only and never a `Cookie` header. `build_graphql_headers` copies `GRAPHQL_REQUEST_HEADERS` and adds only the CSRF header (`collector_graphql.py:386-398`); the module docstring pins "No `Cookie` header is constructed, emitted, or modified" (`:22`); the production transport sends `dict(headers)` and adds no cookie (`cli.py:335-351`, docstring `:16-21`). | read `collector_graphql.py:22,386-398`; `cli.py:16-21,335-351` |
| D2 | Live probes show the endpoint requires the `_csrf` cookie **and** byte-for-byte equality with `X-CSRF-Token`: header-only → 400 `csrf token mismatch`; cookie-only → 400; mismatch → 400; header+cookie equal → 200. `_csrf` is issued by a storefront page GET, not the homepage. | live, recorded `.scratch/graphql_csrf_finding.md` §1–§3, §5, §7 (produced by `.scratch/unity_*_probe.py`, 2026-09-24). Human-pasted browser capture independently confirms the field shapes. Not reproduced by the lead (no live network in agent work). |
| D3 | The frozen `_PRODUCT_DETAIL_QUERY` selects `category` and `publisher` as scalars (`collector_graphql.py:311-327`), but live introspection shows both are object types: bare selection → HTTP 500; `category { id name }` / `publisher { id name }` → 200. All other selected fields are live-valid; `firstPublishedDate` is timezone-aware ISO 8601 `Z`. | live `.scratch/graphql_csrf_finding.md` §4–§5; read `collector_graphql.py:311-327` |
| D4 | The two failed runs recorded `identity_preflight_status = failed`, `attempted=10, successful=0`, every observation `http_status: null`, `response_sha256: null`, `retry {attempts: 4, failure_classes: ["transport_failure"]}`. That shape means the client-side send raised before any HTTP response (DNS/connect), **distinct** from D1/D3. | live `.scratch/graphql_csrf_finding.md` §6; human-supplied `diagnostic_summary_json` inspection. |
| D5 | `operations` / `apollo-require-preflight` headers are not required by the corrected request (200 without them); the frozen `GRAPHQL_REQUEST_HEADERS` set is live-valid. | live `.scratch/graphql_csrf_finding.md` §1, §5 |
| D6 | Live behaviour is pinned by tests that will conflict with D1: `tests/test_cli.py:857` (`test_build_graphql_transport_sends_csrf_header_only_and_no_cookie`) asserts `"cookie" not in lowered`; `tests/test_collector.py:1550-1554` asserts the request's `header_names` equals exactly `GRAPHQL_REQUEST_HEADERS ∪ {x-csrf-token}`. The frozen Chunk 5 interface publishes `build_graphql_headers(*, credentials) -> Mapping[str, str]` and `GRAPHQL_REQUEST_HEADERS` (`interfaces/chunk-05.md` §5.1, §5.3) and the module docstring at `collector_graphql.py:22`. | read `tests/test_cli.py:855-881`; `tests/test_collector.py:1550-1554`; `interfaces/chunk-05.md:96-142,215-251`; `collector_graphql.py:22` |

## Decisions the chunk must make — human checkpoints (planner must present, not pick)

1. **Cookie supply (collides with frozen non-goals ND-8 / Assumption A-4 and the Chunk 5
   "No `Cookie` header is constructed" contract).** (a) keep operator-supplied
   `NICHESCOUT_UNITY_CSRF_TOKEN` as the single value and send it as **both** cookie and
   header; (b) auto-bootstrap — GET a storefront page, harvest `_csrf`, send the pair;
   (c) hybrid. (b)/(c) contradict retired `SRS-revision2.md` ND-8 / Assumption A-4 and the
   frozen Chunk 5 contract; (a) is the minimal change. **The plan must present these and
   let the human choose; `chunk-planner` must not choose.**
2. **`LREQ-GQL-020` field-list correction.** Live `category`/`publisher` are objects, not
   scalars; minimum subfields satisfying current consumption: `category { id name }`,
   `publisher { id name }`. Record the divergence or escalate for a different shape.
3. **Classification of the HTTP 400 `csrf token mismatch` body.** `LREQ-EXT-100` (SRS §4.1
   line 283-285) and the frozen `GraphQLFailureClass` (interface §5.2) already define
   `CSRF_FAILURE` as permanent. Decide whether the corrected request needs an explicit
   body check mapping a 400 `csrf token mismatch` → `CSRF_FAILURE` (non-retrying abort),
   instead of the current plain-400 `MALFORMED_REQUEST`, and whether that stays inside
   `collector_graphql.py`.
4. **New obligations to record, never close:** the storefront page URL used for bootstrap
   (if chosen); the cookie must not be persisted; and the discovery-path item below.

## Recorded correctly, do not silently extend

- **Discovery path.** `REQ-EXT-050`/truncation behaviour and category filtering are out of
  scope. Record: `GET https://assetstore.unity.com/packages/tools/utilities` returns 404
  (probed) while a real product page returns 200; the committed 8 categories and 3
  truncations are a separate item for the discovery owner.
- **`taxonomy_sha256` empty-hash rejection** remains owned by Chunk 10 (dependency-map §7);
  not this chunk.
- **URI trailing-identifier extraction** (`identity_mapping_rule 1.0.1`) remains unverified;
  not this chunk.
- **D4** (client-side send failure) is a run-environment item; report the DNS/connect
  finding, propose no code fix.

## New live evidence (lead, 2026-09-24) — `.scratch/` only

| # | Finding | Evidence |
|---|---|---|
| F1 | Browser-free bootstrap works: `GET https://assetstore.unity.com/packages/tools/utilities-69717` → HTTP 200, jar holds `_csrf` (32 chars) + `DS`/`AC_CURR`/`NEXT_LOCALE`; POST **header-only** (no cookie) → **HTTP 400 `csrf token mismatch`**; POST harvested `cookie: _csrf=<v>` + matching `x-csrf-token` + corrected `category { id name }` / `publisher { id name }` query → **HTTP 200** (296-byte JSON); same-token header-only control → 400. | ran `.scratch/chunk17-graphql-csrf-probe.py` (`python .scratch/...`, 2026-09-24). |
| F2 | A sentinel zero token with the required headers did **not** reproduce the mismatch branch: `POST` returned HTTP 200 with `data` present. So the *envelope* form of a mismatch (200 + CSRF error code) stays UNVERIFIED; only the plain-text 400 body `csrf token mismatch` was observed directly. | ran `.scratch/chunk17-graphql-envelope-probe.py`. |
| F3 | The pre-existing finding `graphql_csrf_finding.md` §2 already shows the option-(a) shape works: `x-csrf-token` + `cookie: _csrf=<same>`, **no other cookie**, → 200. So option (a) needs only the `_csrf` value. | read `.scratch/graphql_csrf_finding.md:23-36`. |

## Human rulings (2026-09-24) — the four checkpoints

1. **Q1 = option (a).** Operator-supplied `NICHESCOUT_UNITY_CSRF_TOKEN` sent as **both**
   `cookie: _csrf=<token>` and `X-CSRF-Token: <token>`, byte-equal. Chosen over
   auto-bootstrap because auto-bootstrap is "automated credential acquisition", listed
   **Out of scope** in SRS-lean §1.3 line 102, and would strand the §14 / LREQ-SEC-010
   credential (the human's "no config variable that does not work" constraint). No new
   config knob, no new param, no `cli.py` logic change.
2. **Q2 = `category { id name }` / `publisher { id name }`** (live 200).
3. **Q3 = yes:** HTTP 400 body `csrf token mismatch` → `CSRF_FAILURE` (permanent,
   non-retrying); other 400s stay `MALFORMED_REQUEST`; 200 `extensions.code == "csrf"`
   path unchanged.
4. **Q4 = record, never close:** the cookie must not be persisted; the discovery-path
   404 is a discovery-owner item; D4 stays an environment finding with no code fix.
5. **One truthful rename** approved under the human's "no misleading artifacts"
   principle: `tests/test_cli.py::test_build_graphql_transport_sends_csrf_header_only_and_no_cookie`
   → `tests/test_cli.py::test_build_graphql_transport_sends_matching_cookie_and_csrf_header`,
   with its `tests/traceability.json` key updated old→new (same LREQ values). No other
   node ID is renamed. Frozen historical plans/logs keep the old name.

## Stage log

| Stage | Status | Session / evidence |
|---|---|---|
| Preflight (lead) | DONE | table above |
| Plan — `chunk-planner` | DONE (**FROZEN**, Q1 = option (a)) | `ses_f2db4e2dfffe1XXyxU3JemYw0s` (resumed 3× after a step-cap recon-only run): DRAFT → BLOCKED on the four checkpoints → frozen with the human rulings → revised to option (a) after the human rejected the dead-config consequence of option (b). Plan `Documents/plans/chunk-17-graphql-live-contract-remediation.md`, `Status: FROZEN`, 767 lines. Commit `a938d7a`. |
| Tests — `test-author` | DONE | `ses_f2d8090d0ffeDcOHW4a4RRSNeu` (provider-error ×2, then step-cap; edits landed). Fixtures: `graphql_fixtures.py` (updated `PRODUCT_DETAIL_SELECTION_SET`/`EXPECTED_PRODUCT_DETAIL_REQUEST_OBJECT`, container payload helpers/goldens, `http_400_csrf_mismatch`), `cli_fixtures.py` (`graphql_headers()` gains the cookie). 5 new collector nodes + the one approved rename; traceability key moved old→new and 5 keys added. Commit `5d9a2db`. |
| Tests — red state (lead) | DONE | `python -m pytest -q` → **7 failed, 627 passed in 40.99s** (5 new nodes + 2 reconciled pins; no collection/syntax error). One test defect found: node 4 asserted a missing required member is *valid*; sent back once. |
| Tests — node-4 correction | DONE | `test-author` resumed: `tests/test_collector.py::test_object_shaped_category_and_publisher_payload_validates` now asserts the SRS/required-member semantics (missing `category`/`publisher` → `WRONG_DATA_SHAPE`, `product_detail is None`, no fabricated `"{}"`). Full suite → **6 failed, 628 passed**. Commit `b8d1058`. |
| Implement — `impl-deep` | DONE | `ses_f2d559d32ffe9aGGd6SwCPTdkb`. R1 `_csrf` cookie from the operator credential + `header_names`; R2 nested query; R3 400 `csrf token mismatch` → `CSRF_FAILURE`; `cli.py` docstrings only. Commit `4e1c8f1`. |
| Lead verify | DONE | `python -m pytest -q` → **634 passed in 23.90s**; four validators valid (traceability `620 matrix nodes`); `git diff --name-only main...HEAD` = exactly the plan §6 files; working tree clean. |
| Review — `spec-reviewer` | VERDICT: PASS | `ses_f2d4b61f9ffeqW6JpoIYqDxQKh`. No Blocker/Major; three Minors recorded below. Independently re-ran `634 passed`, the four validators, and ruff on the changed files. |
| Gate | PASSED | see gate table below. |

## Review (step 7) — Minors recorded, no fix round triggered

1. **Plan citation imprecision (Minor).** Plan §5.1 (and `:10`, `:297`) attributes the
   "No `Cookie` header is constructed" clause to `interfaces/chunk-05.md` §5.3; the
   reviewer grepped `Documents/interfaces/` and the clause is **not** there. Its real
   home is the pre-change module docstring `collector_graphql.py:22` (now updated) and,
   for transport wording, `interfaces/chunk-12.md` §5/§6. No code impact; the interface
   files are unedited. Recorded here; the frozen plan is not edited. (The dispatch
   brief itself carried the same shorthand citation.)
2. **Node-4 plan text vs SRS (Minor).** Plan §9 node 4 said "a missing pair stays `None`";
   the delivered node asserts a missing required member is `WRONG_DATA_SHAPE` with
   `product_detail is None`. The delivered behaviour is the SRS-consistent one
   (`PRODUCT_DETAIL_REQUIRED_MEMBERS` includes `category`/`publisher`; this chunk changed
   no validation code). The correction (commit `b8d1058`, made **before** the
   implementation commit) is recorded here as required; the plan is not edited. Node 4 is
   therefore a **regression pin**, not a missing-implementation red: the validation path
   already accepted a container pre-change (plan §1.1 D3 / A3). The plan §9 "all new
   nodes fail pre-change" claim holds for the other five, not node 4.
3. **Run-log staleness (Minor).** This edit resolves it: the stage log, the real counts,
   and the `b8d1058` record are now present.

## Post-change verification (lead, real output)

| Command | Real result |
|---|---|
| `python -m pytest -q` | `634 passed in 23.90s` (baseline 629 + 5 new collector nodes; the renamed CLI node is not new) |
| `python -m pytest -q` (red state) | `7 failed, 627 passed in 40.99s`, then `6 failed, 628 passed in 21.61s` after the node-4 correction — all failures missing-implementation/behaviour, none collection/syntax |
| `python -m niche_scout.tools.validate_traceability` | `Traceability valid: 89 required/defined LREQ IDs mapped, 620 matrix nodes, 0 unmarked analytical tests outside exemption (3 exempted non-analytical nodes)` |
| `python -m niche_scout.tools.check_import_boundaries` | `Import boundaries valid for metrics.py, scoring.py` |
| `python -m niche_scout.tools.check_scope_prohibitions` | `Scope prohibitions valid: no retired token found ... (6 tokens checked)` |
| `python -m niche_scout.tools.check_secrets` | `Secret check valid: no literal credential found under src, tests, config, pyproject.toml; .gitignore ignores .env and no tracked .env exists` |
| `ruff check` on the two changed files | `All checks passed!` |
| `ruff format --check` on the two changed files | `cli.py` clean; `collector_graphql.py` reports **pre-existing** deviations at lines 704, 830, 1546, 2065, all outside the changed hunks (reviewer method: `git diff main...HEAD` hunk ranges, since byte-exact `git show` extraction was shell-denied) → PARTIAL (pre-existing), same caveat as Chunks 14/15/16 |

## Gate — Chunk 17

Chunk 17 has no dependency-map §3 gate; the gate is plan §10 (the dispatch DoD).

| DoD bullet (plan §10) | Result | Evidence |
|---|---|---|
| Full suite green with real countable counts | PASS | `634 passed in 23.90s` (lead) and `634 passed in 21.47s` (reviewer, independent) |
| All four validators valid | PASS | outputs above; traceability `620 matrix nodes` |
| `ruff` on changed files (Chunk 14 pre-existing-backlog caveat) | PARTIAL (pre-existing) | `ruff check` clean on both changed files; `ruff format` deviations at `collector_graphql.py:704/830/1546/2065` are outside the changed hunks; reviewer used `git diff main...HEAD` hunk ranges, not byte-exact HEAD (shell-denied) |
| Config/template/taxonomy consistency unchanged | PASS | `git diff --name-only main...HEAD` contains no `config/**`, `pyproject.toml`, or `models.py`; only the plan §6 files |
| No secret anywhere; no live network in tests | PASS | `check_secrets` valid; fixture tokens are synthetic (`fixture-graphql-csrf-token`, `fixture-cli-csrf-token`); every transport is a recording double |
| Plan, run log, tests, traceability, conventions recorded | PASS | FROZEN plan; this log; tests `5d9a2db`/`b8d1058`; implementation `4e1c8f1`; 5 new traceability nodes + the renamed key |
| Human live-run bullet reserved for the human | PENDING HUMAN | offline gate cannot prove the live identity-preflight pass; the probes showed the corrected request returns HTTP 200 with a harvested `_csrf` pair |
| Every checkpoint resolved by the human and recorded | PASS | §12.1 Q1=option (a), Q2, Q3=yes, Q4=record; no `LREQ-SEC-010` tension remains |

**GATE: PASSED** on every agent-verifiable bullet. Two caveats recorded, not silently
resolved: the `ruff` bullet is met only as "no new lint" because of the pre-existing
repo-wide backlog on lines this chunk did not touch, and the human live-run bullet is
reserved for the human. Three reviewer Minors are recorded above; none is a Blocker or
Major, so no fix round was triggered.

## Open obligations (recorded, not silently closed)

- **OI-6** (CSRF/session sufficiency, dependency-map §7) — the live probes answer its four
  sub-questions and the human ruled the supply mechanism (option (a)); the item is
  recorded as answered-for-Chunk-17, not retired. Owner stays unassigned in the map.
- **URI trailing-identifier extraction** (`1.0.1`) remains UNVERIFIED; untouched.
- **D4** environment DNS/connect failure is reported, not fixed here.
- **Mismatch envelope** (200 + CSRF error code) UNVERIFIED (F2).
