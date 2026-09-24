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

## Stage log

| Stage | Status | Session / evidence |
|---|---|---|
| Preflight (lead) | DONE | table above |
| Plan — `chunk-planner` | DONE (DRAFT) / **BLOCKED on human** | `ses_f2db4e2dfffe1XXyxU3JemYw0s` (resumed once after a step-cap recon-only run). Wrote `Documents/plans/chunk-17-graphql-live-contract-remediation.md` (614 lines, `Status: DRAFT`). Reconnaissance only in the first pass; resumed to author the plan. Returned `STATUS: BLOCKED` with the four human checkpoints in §12. **Chain stopped here per auto-chaining rules** (unresolved open question ⇒ plan not frozen). |
| Tests — `test-author` | BLOCKED | not started — waits on plan freeze |
| Implement — `impl-deep` | BLOCKED | not started |
| Lead verify | BLOCKED | not started |
| Review — `spec-reviewer` | BLOCKED | not started |
| Gate | BLOCKED | plan §10 gate cannot be walked until the plan is frozen |

**Stop point.** Per the project's auto-chaining rules the chain stops when `chunk-planner`
leaves a plan at DRAFT with unresolved open questions. The four checkpoints in plan §12
(Q1 cookie supply, Q2 `LREQ-GQL-020` field list, Q3 400-body classification, Q4 recorded
obligations) are relayed to the human verbatim. On the human's answers the lead
re-dispatches `chunk-planner` with the answers to freeze the plan, then continues
`test-author` → `impl-deep` → lead verify → `spec-reviewer` → gate.

## Open obligations (recorded, not silently closed)

- **OI-6** (CSRF/session sufficiency, dependency-map §7) — this chunk's live diagnosis
  answers its four sub-questions, but the supply-method decision is a human checkpoint
  (Decision 1); the item stays recorded until the human rules.
- **URI trailing-identifier extraction** (`1.0.1`) remains UNVERIFIED; untouched.
- **D4** environment DNS/connect failure is reported, not fixed here.
