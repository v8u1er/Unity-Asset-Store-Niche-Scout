# Chunk 17 — GraphQL live-contract remediation (labeled post-Chunk-16 remediation)

Status: FROZEN
Depends on (frozen interfaces required before this plan can be trusted):
  - `Documents/interfaces/chunk-05.md` §5.1 (`GRAPHQL_REQUEST_HEADERS`,
    `GRAPHQL_CSRF_HEADER_NAME`), §5.3 (`build_graphql_headers(*, credentials) ->
    Mapping[str, str]`, `build_graphql_batch_request(...)`), §5.2
    (`GraphQLFailureClass` incl. `CSRF_FAILURE`/`MALFORMED_REQUEST`), §5.11
    (transport/retry, `enrich_asset`) — consumed. Both §5.3 public **signatures are
    kept unchanged**; §5.3's "No `Cookie` header is constructed" clause is
    **diverged from by binding human ruling** (2026-09-24): the operator-supplied Unity
    CSRF credential is emitted as **both** the `_csrf` cookie and the header (§5.1).
    `Documents/interfaces/chunk-05.md` is **not** edited.
  - Binding human rulings (2026-09-24, revised) on the four checkpoints:
    **Q1 = option (a)**, operator-supplied token sent as both cookie and header;
    Q2 = `category { id name }` / `publisher { id name }`; Q3 = yes, 400
    `csrf token mismatch` → `CSRF_FAILURE`; Q4 = the listed obligations are recorded,
    not closed. Recorded in §12.1.
  - `Documents/interfaces/chunk-06a.md` and `chunk-06b.md` (preflight/gate and
    one-request-per-identity behavior) — consumed unchanged; this chunk changes only
    the request the adapter sends, not the gate.
  - `Documents/interfaces/chunk-10.md` §4/§5 (`PipelineResult`, `limitations`) —
    consumed unchanged.
  - `Documents/interfaces/chunk-12.md` §5/§6 (`run_command`, transport construction) —
    consumed; `cli.build_graphql_transport` is where the caller-supplied header map is
    put on the wire.
Blocks (chunks whose plan/implementation needs this chunk's interface):
  - None. This is a labeled post-Chunk-16 remediation (same pattern as Chunks 14/15/16):
    it has **no `Documents/requirements-dependency-map.md` §3/§4 gate row**, it
    introduces no new interface file, and no downstream chunk starts on it. The gate
    is this plan's own §10.

## 1. Goal

Make a human `python -m niche_scout run` reach and **pass** the identity preflight
against the live Unity storefront GraphQL endpoint, correcting the two proven protocol
defects with the minimum consequential changes and no scope beyond the adapter, its
production transport's docstrings, and their tests/fixtures.

The diagnosis is complete; nothing is routed as "investigate". The evidence is:
- the original `.scratch` probe log `.scratch/graphql_csrf_finding.md` (probes
  `.scratch/unity_probe.py`, `unity_post_probe.py`, `unity_real_probe.py`,
  `unity_live_check.py`). Its §2 table row `x-csrf-token` + `cookie: _csrf=<same>` →
  **200** (with no other cookie needed) is the **option-(a) evidence**;
- **lead-run this session (`.scratch/` only; supersedes the earlier "not reproduced by
  the lead" note for D1/D2/D3/D5):**
  `.scratch/chunk17-graphql-csrf-probe.py` — GET storefront page → 200, jar holds
  `_csrf` (32 chars); POST header-only (no cookie) → **400 `csrf token mismatch`**; POST
  with `cookie: _csrf=<same value>` + matching header + the corrected query → **200**
  (296-byte JSON); same-token header-only control → 400. The probe harvested the same
  `_csrf` value the runner supplies as the operator credential and got 200, matching the
  `.scratch/graphql_csrf_finding.md` §2 row. `.scratch/chunk17-graphql-envelope-probe.py`
  — a sentinel token returned **200 with `data`**, so the mismatch **envelope**
  classification could not be probed live (recorded as UNVERIFIED in §1.1 D3); the
  plain-text 400 body was observed directly.

No project code was modified by the probes.

### 1.1 Grounded findings

Labels: **read** = verified by reading committed source/tests this session (paths and
line ranges cited); **live** = observed by the human-run `.scratch` probes against
`assetstore.unity.com` (dated 2026-09-24, recorded in the log); **unverified** = not
confirmed by either.

- **D1 (Blocker, read + live).** The adapter sends the `X-CSRF-Token` header and never
  a `Cookie` header.
  - read: `collector_graphql.py:22` (docstring "No `Cookie` header is constructed,
    emitted, or modified"), `:386-398` (`build_graphql_headers`), `:416-459`
    (`build_graphql_batch_request`, `header_names` at `:454-457`); `cli.py:16-21`
    (module docstring) and `:320-353` (`build_graphql_transport`).
  - live: `.scratch/graphql_csrf_finding.md` §1–§3, §5, §7;
    `.scratch/chunk17-graphql-csrf-probe.py` (the §2-equivalent row re-confirmed).
- **D2 (live).** The endpoint requires the `_csrf` cookie plus **byte-for-byte** equality
  with `X-CSRF-Token`: header-only → HTTP 400 `csrf token mismatch`; cookie-only → 400;
  mismatch → 400; header + cookie from the **same** operator-supplied value → 200. No
  other cookie is needed for the POST.
  - live: `.scratch/graphql_csrf_finding.md` §1–§3, §5, §7. The §2 table is the
    operative evidence: `x-csrf-token` + `cookie: _csrf=<same>` → 200.
- **D3 (Blocker for enrichment, live; one half unverified).** The frozen
  `_PRODUCT_DETAIL_QUERY` selects `category`/`publisher` as scalars; live introspection
  shows they are **object types**: a bare selection → HTTP 500;
  `category { id name }` / `publisher { id name }` → 200. The other selected fields are
  live-valid; `firstPublishedDate` is a timezone-aware ISO 8601 `Z` value, so Chunk 5's
  parse-only date handling is compatible.
  - live: `.scratch/graphql_csrf_finding.md` §4–§5;
    `.scratch/chunk17-graphql-csrf-probe.py` (corrected query → 200).
  - **UNVERIFIED half.** `.scratch/chunk17-graphql-envelope-probe.py` returned HTTP 200
    **with `data`** for a sentinel token, so the *envelope* form of a mismatch response
    (a 200 body carrying a CSRF error code) could not be reproduced live this session;
    only the plain-text HTTP 400 body `csrf token mismatch` was observed directly. R3
    therefore classifies the observed 400 body and leaves the existing 200
    `extensions.code == "csrf"` path untouched. The envelope path stays unverified and
    is not claimed.
  - read: `collector_graphql.py:311-327` (`_PRODUCT_DETAIL_QUERY`); the payload reader
    already accepts a container for these members (`_usable_container_json`,
    `collector_graphql.py:1004-1026`, used at `:1235-1236`), so the **validation** side
    already handles an object; only the **query text** is wrong. This is a read finding
    and reduces the change surface.
- **D4 (environment, read + live; NOT a protocol defect).** Both failed runs recorded
  `identity_preflight_status = failed`, `attempted = 10`, `successful = 0`, every
  observation `http_status: null`, `response_sha256: null`,
  `retry {attempts: 4, failure_classes: ["transport_failure"]}` — a client-side send
  failure (DNS/connect) that produced **no** HTTP response, distinct from D1/D3.
  - live: `.scratch/graphql_csrf_finding.md` §6 (includes a reproduced
    `URLError: <urlopen error [Errno 11001] getaddrinfo failed>`).
  - **This chunk proposes no code fix for D4.** It is reported; the two proven defects
    would fail the run even on a clean network.
- **D5 (live).** `operations` / `apollo-require-preflight` headers are **not** required
  by the corrected request; the frozen `GRAPHQL_REQUEST_HEADERS` set, the bare-array
  batch body, and the two-operation contract are live-valid and need no code.
  - live: `.scratch/graphql_csrf_finding.md` §1 (both headers "changed nothing"), §5
    (working request omits them).
- **D6 (read).** Live behaviour is pinned by committed tests and by the frozen Chunk 5
  interface; the header-map/query-shape change is a **certain** behavioural contract
  divergence (human ruling Q1/Q2), recorded in §5 with the affected pytest node IDs and
  fixtures, including the explicit rename of one `test_cli.py` node (§5.2). Node
  candidates are enumerated in §5.2; the **count** is `UNVERIFIED` (see §5.2).

### 1.2 What "pass the identity preflight" means here

`LREQ-ID-020` requires the normal GraphQL request to verify the request identifier is
accepted by both operations, returned identifiers are compatible, the page-view
operation is associated with the requested package identifier, and the correlation mode
is valid. The corrected request is the request shape that can satisfy it; this chunk
does not change preflight policy, thresholds, or the gate.

## 2. Scope

### In scope

- **R1 — operator-supplied token sent as both cookie and header (D1/D2; human ruling
  Q1 = option (a)).** `build_graphql_headers` emits, in addition to the six
  `GRAPHQL_REQUEST_HEADERS` members and `"x-csrf-token": <token>`, a
  `"cookie": "_csrf=" + <token>` member (lowercase key). The header and the cookie carry
  the same `credentials.unity_csrf_token` value, byte-for-byte. **No bootstrap GET, no
  cookie jar, no new credential source.** This honours SRS-lean §1.3 ("automated
  credential acquisition" is Out of scope, line 102), §3.2 step 1 ("the Unity CSRF
  credential", line 202), `LREQ-SEC-010` (§4.3 line 348), and §14 (lines 1305-1306,
  `NICHESCOUT_UNITY_CSRF_TOKEN` named as an operator-supplied Environment GraphQL
  credential) simultaneously, and leaves no dead or misleading config variable.
  (LREQ-GQL-010, LREQ-SEC-010, LREQ-GQL-030 supporting)
- **R2 — query-shape correction (D3; human ruling Q2).** Change `_PRODUCT_DETAIL_QUERY`
  so `category` and `publisher` are selected as `{ id name }` — the minimum satisfying
  current consumption, confirmed live at HTTP 200. (LREQ-GQL-020)
- **R3 — 400-body classification (human ruling Q3 = yes).** An HTTP **400** whose body is
  `csrf token mismatch` maps to `GraphQLFailureClass.CSRF_FAILURE` (permanent,
  non-retrying) inside `collector_graphql.py`; **every other** 400 stays
  `MALFORMED_REQUEST`; the existing 200 `extensions.code == "csrf"` path is unchanged.
  Today `_classify_http_status` maps **every** 400 to `MALFORMED_REQUEST`
  (`collector_graphql.py:1937-1947`). (LREQ-EXT-100, LREQ-GQL-040 supporting)
- **R4 — tests and traceability first.** `test-author` writes the failing nodes and
  their `tests/traceability.json` entries (§9) **before** `impl-deep` edits
  `collector_graphql.py`/`cli.py`. No live network in tests. (all listed LREQs)
- **R5 — record, never silently extend.** New obligations are recorded in §12.2 and not
  closed: the cookie must not be persisted; the discovery-path 404 item; D4 stays an
  environment finding with no code fix; the unverified mismatch-envelope path.
  (LREQ-SEC-010, LREQ-SEC-020)

### Explicitly out of scope (and who owns it instead)

- **D4's transport/environment failure.** No code fix; it is a client-side DNS/connect
  failure, distinct from D1/D3, and remains an environment finding. Owner:
  none (environment/operator).
- **Discovery path 404.** `GET https://assetstore.unity.com/packages/tools/utilities`
  returns 404 (probed); a real product page returns 200. `REQ-EXT-050`/truncation and
  category filtering are out of scope and are recorded as a **separate discovery-owner
  item** (dependency-map §3 Chunk 3 / §7), never resolved here.
- **`config.py`, `.env.example`, and the `Credentials` contract.** **Not edited.**
  `NICHESCOUT_UNITY_CSRF_TOKEN` stays declared and stays the one working source; the
  Coveo credential gate and the Unity-CSRF requirement in
  `Credentials.require_for_collection()` are unchanged. Option (a) is chosen precisely
  because it creates no dead or misleading config variable.
- **Cookie persistence.** No cookie is persisted anywhere; it exists only as an
  in-memory request header built from the operator credential. Owner: this chunk (by
  prohibition).
- **`taxonomy_sha256` empty-hash rejection.** Stays owned by **Chunk 10**
  (dependency-map §7). Not touched.
- **URI trailing-identifier extraction (`identity_mapping_rule 1.0.1`).** Stays
  **inferred and UNVERIFIED** (`interfaces/chunk-01.md` §4.1; dependency-map §6.4). Not
  touched and no verification claimed.
- **Bulk enrichment behavior, preflight policy/thresholds, sampling, metrics, scoring,
  `database.py`, `report.py`, `models.py`.** No change. (`metrics.py`/`scoring.py`/
  `models.py`/`database.py`/`report.py` are explicitly untouchable.)
- **New config knobs.** No new CLI flag and no new environment variable; the existing
  `NICHESCOUT_UNITY_CSRF_TOKEN` (SRS §14) remains the credential. No configurable score
  weights.
- **New dependencies.** No new dependency; no bootstrap, so no `http.cookiejar` use.
- **`favorite_count`, extra GraphQL operations/fields, scheduling, resume/checkpoint,
  multi-user/cloud.** Forbidden (dependency-map §15, AGENTS.md "Out of scope — do not
  add").
- **Live network.** No live call in development or tests; the `.scratch` logs are the
  only live evidence and are quoted, not re-fetched.

## 3. Requirements this chunk must satisfy

Chunk 17 is a labeled remediation and has **no `Documents/requirements-dependency-map.md`
§3 section** (the map's chunked plan ends at Chunk 13; Chunks 14/15/16 are the same kind
of remediation and are likewise absent). No dependency-map section is created and no
interface file is edited.

| LREQ ID | Ownership role here | Normative text (from SRS-lean.md, quoted/derived) | SRS section |
|---|---|---|---|
| LREQ-GQL-010 | Primary (this remediation) | "Enrichment SHALL use the parent SRS GraphQL batch endpoint and the two required operations: `ProductDetail(id: ID!)` and `ProductPageViews(packageId: String!)`. Both operations SHALL use the same canonical `asset_identity_key`." The endpoint, the two operations, and the shared identity are unchanged; R1 changes only the headers the request carries. | §4.2 (line 289) |
| LREQ-GQL-020 | Primary (this remediation) | "The `ProductDetail` operation SHALL request product identity aliases, `rating.average`, `rating.count`, `reviewCount`, `firstPublishedDate`, `state`, `category`, and `publisher`." The live `category`/`publisher` are object types, so R2 requests their `{ id name }` selection; the SRS names the fields, not their selection shape. | §4.2 (line 294) |
| LREQ-GQL-030 | Supporting (Chunk 5 remains primary; no behavior change) | "GraphQL response items SHALL be associated by explicit operation name or another validated correlation key." The corrected request keeps the two-operation envelope and `operationName` correlation; D5 confirms the batch body is live-valid. | §4.2 (line 300) |
| LREQ-GQL-040 | Supporting (Chunk 5 remains primary) | "Each operation SHALL have an independent status. HTTP failures, top-level GraphQL `errors`, … SHALL be recorded as an operation error." R3 (human ruling Q3 = yes) classifies the HTTP 400 `csrf token mismatch` body as `CSRF_FAILURE`; every other 400 stays `MALFORMED_REQUEST`. | §4.2 (line 318) |
| LREQ-EXT-100 | Primary (this remediation's classification half) | "Requests SHALL be rate-limited and retry transient `429` and `5xx` responses with exponential backoff. Permanent authentication, CSRF, malformed request, or authorization failures SHALL not be retried indefinitely." R3 (human ruling Q3 = yes) classifies the observed HTTP 400 `csrf token mismatch` body as `CSRF_FAILURE` (permanent, non-retried); every other 400 stays `MALFORMED_REQUEST`. | §4.1 (line 283) |
| LREQ-SEC-010 | Supporting; **honoured by option (a)** | Verbatim: "Coveo and Unity CSRF credentials SHALL be read from environment variables and SHALL be required before network collection." Option (a) reads the Unity CSRF credential from `NICHESCOUT_UNITY_CSRF_TOKEN` (SRS §14) and sends it as both cookie and header; the gate `Credentials.require_for_collection()` is unchanged. No tension is created. | §4.3 (line 348) |
| LREQ-SEC-020 | Supporting (Chunk 2/5 remain primary) | "Secrets SHALL NOT be written to source control, logs, SQLite, or error messages." The cookie value and the `Cookie` header value must never reach `header_names`, `request_metadata_json`, an issue, a summary, a log line, a fixture, or any artifact. | §4.3 (line 351) |
| LREQ-ID-020 | Integration completion (Chunk 6A remains primary) | "The preflight SHALL perform the normal GraphQL request and verify … the page-view operation is associated with the requested package identifier; the operation-correlation mode is valid." A corrected request is the prerequisite for the preflight to be able to pass; this chunk changes no preflight logic. | §4.4 (line 368) |
| LREQ-ARCH-030 | Supporting (Chunk 10 remains primary) | "The same normalized input data, policy versions, and configuration SHALL produce the same metric, score, evidence, and sensitivity outputs." The corrected request is a deterministic function of its inputs; no clock, RNG, or set/dict-ordering dependence is introduced. | §3 |

Opting for **option (a)** over auto-bootstrap is itself the SRS-anchored decision:
SRS-lean §1.3 lists "automated credential acquisition" as **Out of scope** (line 102);
§3.2 step 1 loads "the Unity CSRF credential" (line 202); `LREQ-SEC-010` (§4.3 line 348)
requires it from environment variables before network collection; and §14 (lines
1305-1306) names `NICHESCOUT_UNITY_CSRF_TOKEN` as an operator-supplied Environment
GraphQL credential. Option (a) is the only choice that honours all four.

`AGENTS.md` "Hard rules" 2 is the supporting invariant: null, explicit valid zero,
invalid, and unavailable stay distinct. R1/R2 introduce no default substitution and no
zero-fill.

## 4. Interface contracts consumed

Copied from the frozen interface files (not re-derived from source):

- `interfaces/chunk-05.md` §5.1:
  `GRAPHQL_REQUEST_HEADERS: Mapping[str, str]` (six constant headers, no credential),
  `GRAPHQL_CSRF_HEADER_NAME: str = "X-CSRF-Token"`,
  `GRAPHQL_BATCH_ENDPOINT = "https://assetstore.unity.com/api/graphql/batch"`.
- `interfaces/chunk-05.md` §5.3:
  `build_graphql_headers(*, credentials: Credentials) -> Mapping[str, str]`;
  `build_graphql_batch_request(asset_identity_key: str, *, credentials: Credentials,
  endpoint: str = GRAPHQL_BATCH_ENDPOINT) -> GraphQLBatchRequest`;
  `GraphQLBatchRequest.header_names` is "the *names* of the headers the caller
  supplied, never the values". **Both signatures are kept byte-identical.**
- `interfaces/chunk-05.md` §5.2: `GraphQLFailureClass` members
  `CSRF_FAILURE = "csrf_failure"` ("csrf token mismatch -> permanent"),
  `MALFORMED_REQUEST = "malformed_request"` ("400 -> permanent"), and the invariant
  "no `*_FAILURE` auth/CSRF/authorization class and no `MALFORMED_REQUEST` is ever
  retried".
- `interfaces/chunk-05.md` §5.11: `GraphQLTransport`,
  `execute_graphql_batch(request, *, transport, headers, policy, sleep)`,
  `enrich_asset(...)` (builds the request and the headers, then executes).
- `interfaces/chunk-12.md` §5/§6: `cli.run_command` constructs
  `build_graphql_transport()` when no transport is injected; the returned callable
  receives `(request, headers)` and adds nothing of its own beyond the caller-supplied
  headers (`cli.py:335-353`).
- `interfaces/chunk-10.md` §4/§5: `PipelineResult.limitations` redaction invariant —
  consumed unchanged.

**Signature-freeze facts (verified by reading, this session).**

- `build_graphql_headers` is keyword-only (`*, credentials`) and returns a `Mapping`.
  `build_graphql_batch_request` currently builds `header_names` as
  `(*sorted(GRAPHQL_REQUEST_HEADERS), GRAPHQL_CSRF_HEADER_NAME.lower())`
  (`collector_graphql.py:454-457`) — i.e. seven names, `x-csrf-token` included.
- `cli.build_graphql_transport` sends exactly `dict(headers)` via
  `urllib.request.Request(endpoint, data=payload, headers=..., method="POST")`
  (`cli.py:335-353`); it constructs no header itself, so option (a) needs **no logic
  change** there.
- `_PRODUCT_DETAIL_QUERY` is a module-private constant (`collector_graphql.py:311-327`).
  The payload reader already accepts a container for `category`/`publisher`
  (`_usable_container_json`, `:1004-1026`, used at `:1235-1236`), so R2 changes only the
  query text, not the validation path.
- `_classify_http_status` maps 400 → `MALFORMED_REQUEST` (`:1937-1947`); `CSRF_FAILURE`
  is reachable only via `_classify_top_level_errors` on a 200 body (`:1950-1968`).

## 5. Interface contract this chunk produces

**None.** This is a labeled remediation, not a dependency-map chunk. No
`Documents/interfaces/chunk-17.md` is created (Chunks 14/15/16 created none) and no
downstream chunk consumes a new surface.

### 5.1 Behavioural contract divergences (adopted under binding human ruling; frozen interface files NOT edited)

The frozen Chunk 5 contract states in §5.3: "No `Cookie` header is constructed,
emitted, or modified." R1 **diverges** from that clause **under binding human ruling
Q1 = option (a)**. The cookie is built from the **existing operator credential**, not a
bootstrap. The divergence is recorded here and in the run log;
`Documents/interfaces/chunk-05.md` is **not** edited by this chunk.

**There is NO signature divergence.** Both frozen public signatures are kept
byte-identical; only the returned header map and `header_names` gain the `"cookie"` /
`"_csrf=..."` member:

- `build_graphql_headers(*, credentials: Credentials) -> Mapping[str, str]` — unchanged.
  The returned map carries the six `GRAPHQL_REQUEST_HEADERS` members plus
  `"x-csrf-token": <credentials.unity_csrf_token>` plus
  `"cookie": "_csrf=" + <credentials.unity_csrf_token>`. Header and cookie carry the
  same value byte-for-byte.
- `build_graphql_batch_request(...)` — unchanged. Its `header_names` becomes
  `(*sorted(GRAPHQL_REQUEST_HEADERS), GRAPHQL_CSRF_HEADER_NAME.lower(), "cookie")`
  (eight names, always, because the credential is required). Names only, never values.
- The Chunk 5 §5.3 docstring clause "No `Cookie` header is constructed" is therefore
  superseded by behaviour; the module docstring `collector_graphql.py:22` and the
  `build_graphql_headers` docstring are updated to state the cookie is emitted from the
  credential.

**R2 divergence (adopted).** The emitted `ProductDetail` query text changes from the
scalar `category` / `publisher` selection to `category { id name }` /
`publisher { id name }` (ruling Q2). A behavioural contract change for the request
goldens, recorded with the affected tests in §5.2.

**R3 divergence (adopted).** `_classify_http_status` (or a body-aware HTTP-failure
classifier wrapping it) classifies an HTTP **400** whose body is `csrf token mismatch`
as `CSRF_FAILURE` instead of `MALFORMED_REQUEST` (ruling Q3 = yes). The
`GraphQLFailureClass` vocabulary is unchanged; only which member a matching 400 body
maps to changes. Every other 400 stays `MALFORMED_REQUEST`; the 200
`extensions.code == "csrf"` path is unchanged.

### 5.2 Pytest node IDs and fixtures pinning the affected contract

The enumeration below is a **reading-derived candidate set**. The **count is
`UNVERIFIED`** (no counted `grep` enumeration was run; the `bash` tool is denied in this
environment). Each row was read this session at the cited location. Every one of these
is part of the **certain** Q1/Q2 divergence and must be reconciled.

| Artifact | Location read | What it pins | Action |
|---|---|---|---|
| `tests/test_cli.py::test_build_graphql_transport_sends_csrf_header_only_and_no_cookie` (**old name**) → `tests/test_cli.py::test_build_graphql_transport_sends_matching_cookie_and_csrf_header` (**new name**) | `tests/test_cli.py:855-881` | asserts `"cookie" not in lowered` | **RENAME** the node (its name now asserts the opposite of the behaviour); update its assertions to exactly one `x-csrf-token` and exactly one `cookie`, `_csrf` equal to the header; update its `tests/traceability.json` key old→new with the same LREQ values `["LREQ-CLI-010","LREQ-SEC-010"]`; record the rename in the run log |
| `tests/test_collector.py::test_batch_request_has_exactly_two_operations_with_one_identity` | `tests/test_collector.py:1520-1554` | asserts `set(request.header_names) == {*GRAPHQL_REQUEST_HEADERS, GRAPHQL_CSRF_HEADER_NAME.lower()}` | contradicted by the `cookie` name; updated; node ID unchanged |
| `tests/test_collector.py::test_product_detail_query_requests_only_required_fields` | `tests/test_collector.py:1593-1623` | asserts `query == gqlfx.EXPECTED_PRODUCT_DETAIL_REQUEST_OBJECT["query"]` | contradicted by R2; golden updated; node ID unchanged |
| `tests/test_collector.py::test_page_views_operation_requests_its_scalar` | `tests/test_collector.py:1626-1641` | pins the `ProductPageViews` query | expected unchanged; re-check after R2 |
| `tests/test_collector.py::test_validated_position_mode_is_accepted_not_validated_here` | `tests/test_collector.py:1858-1901` | calls `build_graphql_headers(credentials=...)` at `:1870` and `:1887` | pins the keyword-only frozen signature; unchanged by option (a) |
| `tests/test_collector.py::test_operation_level_errors_on_http_200_are_operation_errors` | `tests/test_collector.py:1987-2016` | pins CSRF classification **at 200** | must keep passing unchanged under R3 |
| `tests/fixtures/graphql_fixtures.py` `EXPECTED_PRODUCT_DETAIL_REQUEST_OBJECT` | `tests/fixtures/graphql_fixtures.py:185-205` | carries the scalar query text | updated for R2 |
| `tests/fixtures/graphql_fixtures.py` `PRODUCT_DETAIL_SELECTION_SET` | `tests/fixtures/graphql_fixtures.py:160-170` | names `"category"`/`"publisher"` as members | updated for R2's nesting |
| `tests/fixtures/graphql_fixtures.py` `product_detail_payload()` | `tests/fixtures/graphql_fixtures.py:296-321` | returns `category`/`publisher` as **strings** | a container-shaped helper is added; the existing helper and its consumers stay valid |
| `tests/fixtures/graphql_fixtures.py` `PER_FAILURE_CLASS_RESPONSES` | `tests/fixtures/graphql_fixtures.py:853-888` | no `http_400_csrf_mismatch` case | a 400 `csrf token mismatch` case is added for R3 |
| `tests/fixtures/cli_fixtures.py` `graphql_headers()` | `tests/fixtures/cli_fixtures.py:388-390` | returns only `{"x-csrf-token": ...}` | extended with the `cookie` member for R1 |
| `tests/test_collector.py::test_permanent_auth_csrf_and_malformed_request_are_not_retried` | `tests/test_collector.py:1097-1125` | **Coveo** (`LREQ-EXT-100`) test, not GraphQL | listed so it is not mistaken for the adapter path; unchanged |

**The one rename.** `tests/test_cli.py::test_build_graphql_transport_sends_csrf_header_only_and_no_cookie`
(`:855-881`) currently asserts the **opposite** of its name, so the name becomes
misleading under R1. Per the human's "no misleading artifacts" principle it is renamed
to `tests/test_cli.py::test_build_graphql_transport_sends_matching_cookie_and_csrf_header`,
with its assertions updated and its `tests/traceability.json` key changed old→new (same
LREQ values). Frozen historical documents that mention the old name — for example
`Documents/plans/chunk-12-*.md` and the old `Documents/runs/chunk-*` logs — keep the old
name as a record of the state they were written against and are **NOT** edited. The
rename is also recorded in the new `Documents/runs/chunk-17.md`.

No other existing node ID is renamed or deleted. Where a pin is contradicted,
`test-author` updates the node's assertions and the affected fixture values; the node ID
and its `tests/traceability.json` key stay byte-identical.

## 6. Files touched

**Expected paths — this chunk must touch no others.**

| File | New/modified | Purpose |
|---|---|---|
| `src/niche_scout/collector_graphql.py` | modified | R1: `build_graphql_headers` emits `"cookie": "_csrf=" + token` and `build_graphql_batch_request.header_names` includes `"cookie"`; signatures unchanged; module/function docstrings updated. R2: `_PRODUCT_DETAIL_QUERY` selects `category { id name }` / `publisher { id name }`. R3: 400 `csrf token mismatch` → `CSRF_FAILURE` in `_classify_http_status`/its caller. |
| `src/niche_scout/cli.py` | modified (**docstring-only**) | No logic change. `build_graphql_transport` already forwards the caller-supplied header map verbatim (`cli.py:335-353`). Its docstring `:323-331` and the module docstring `:16-21` currently say the transport "adds no `Cookie` header" and "makes no CSRF/session sufficiency claim"; under (a) the caller-supplied map may now carry the adapter-built `_csrf` cookie, so those docstrings are updated to state the transport forwards the caller's header map verbatim and may carry it. |
| `tests/fixtures/graphql_fixtures.py` | modified | Update `EXPECTED_PRODUCT_DETAIL_REQUEST_OBJECT` / `PRODUCT_DETAIL_SELECTION_SET` for R2; add a container-shaped `category`/`publisher` payload helper; add a 400 `csrf token mismatch` `PER_FAILURE_CLASS_RESPONSES` case for R3; add a cookie-carrying header-map helper for R1. |
| `tests/fixtures/cli_fixtures.py` | modified | `graphql_headers()` gains the `cookie` member so the transport test can assert cookie + header both present and equal. |
| `tests/test_collector.py` | modified | Update the contradicted pins (header-name set, query golden) and add the new R1/R2/R3 nodes (§9). Existing node IDs unchanged. |
| `tests/test_cli.py` | modified | Rename `test_build_graphql_transport_sends_csrf_header_only_and_no_cookie` → `test_build_graphql_transport_sends_matching_cookie_and_csrf_header` and update its assertions (§5.2, §9). |
| `tests/traceability.json` | modified | Replace the renamed node's key (old→new, same LREQ values) and add node-ID → `[LREQ ids]` entries for the new nodes (orientation verified: node ID → array, `validate_traceability.py:163-177`). |
| `Documents/runs/chunk-17.md` | new (lead/run log, not this planner) | The run log the gate requires, including the old→new node rename record. Recorded here as required output; this planner does **not** create it. |

**Not touched (explicit):** `metrics.py`, `scoring.py`, `models.py`, `database.py`,
`report.py`, `pipeline.py`, `config.py`, `.env.example`, `sampling.py`,
`validation.py`, `collector.py`, `collector_coveo.py`, `src/niche_scout/tools/**`,
`pyproject.toml`, `config/**`, `Documents/SRS-lean.md`,
`Documents/requirements-dependency-map.md`, `AGENTS.md`, `kilo.json(c)`, `.kilo/`, any
`Documents/interfaces/*` file, and any frozen `Documents/plans/*` or `Documents/runs/*`
file other than the new `Documents/runs/chunk-17.md`.

## 7. Typed function/class signatures

A `test-author` writes tests from these without seeing the implementation, so names,
parameter types, return types, and module paths are exact. **All four checkpoints are
resolved by binding human ruling (Q1=(a), Q2, Q3=yes, Q4=record); the signatures below
are the frozen target for `impl-deep`.**

### 7.1 R1 — operator-supplied token as cookie and header

**Signatures — UNCHANGED (no new parameter):**

```python
# src/niche_scout/collector_graphql.py — signatures byte-identical to interfaces/chunk-05.md §5.3
def build_graphql_headers(*, credentials: Credentials) -> Mapping[str, str]: ...

def build_graphql_batch_request(
    asset_identity_key: str,
    *,
    credentials: Credentials,
    endpoint: str = GRAPHQL_BATCH_ENDPOINT,
) -> GraphQLBatchRequest: ...
```

Null/edge-case behavior, stated exhaustively:

- The token is the existing `_require_unity_csrf_token(credentials)` value
  (`collector_graphql.py:365-383`), i.e. `Credentials.require_for_collection()` runs and
  then `credentials.unity_csrf_token` is whitespace-checked. `build_graphql_headers`
  returns a `MappingProxyType` carrying:
  - the six `GRAPHQL_REQUEST_HEADERS` members;
  - `"x-csrf-token": <token>`;
  - `"cookie": "_csrf=" + <token>` (lowercase key; `_csrf` appears exactly once).
  The `_csrf` value equals the `x-csrf-token` value byte-for-byte.
- Empty/whitespace-only or non-`str` token raises `ValueError` **before** any map exists,
  naming `config.UNITY_CSRF_TOKEN_ENV`, never echoing any part of the value
  (LREQ-SEC-010).
- `build_graphql_batch_request` keeps its signature and its credential gate. Its
  `header_names` is
  `(*sorted(GRAPHQL_REQUEST_HEADERS), GRAPHQL_CSRF_HEADER_NAME.lower(), "cookie")`
  (eight names, always). Names only, never values.
- The returned mapping carries a credential and is never placed in `header_names`,
  `request_metadata_json`, an error summary, a warning, or a log line (LREQ-SEC-020).
- `cli.build_graphql_transport` needs **no logic change**: it forwards `dict(headers)`
  verbatim (`cli.py:335-353`), so the adapter-built cookie travels without transport
  code.

### 7.2 R2 — query shape

```python
# src/niche_scout/collector_graphql.py — module-private constant, no public signature
_PRODUCT_DETAIL_QUERY: str  # category and publisher selected as { id name }
```

- The emitted text is exactly (ruling Q2):
  `query ProductDetail($id: ID!) {\n  product(id: $id) {\n    id\n    productId\n    rating {\n      average\n      count\n    }\n    reviewCount\n    firstPublishedDate\n    state\n    category {\n      id\n      name\n    }\n    publisher {\n      id\n      name\n    }\n  }\n}`.
- `build_product_detail_operation(asset_identity_key: str) -> GraphQLOperation` is
  unchanged in signature; only the query text it carries changes.
- No other operation or field is added; `favorite_count`, `packageInListHotness`, and
  every non-required field stay absent.
- The response side already accepts a container for `category`/`publisher`
  (`_usable_container_json`, `:1004-1026`), so `ProductDetailFields.category_json` /
  `publisher_json` continue to hold compact JSON; no validation-path change is in scope.

### 7.3 R3 — 400 CSRF-body classification (adopted, ruling Q3 = yes)

```python
# src/niche_scout/collector_graphql.py — private classifier
def _classify_http_status(http_status: int, *, body_text: str = "") -> GraphQLFailureClass: ...
```

- An HTTP **400** whose already-read `body_text` carries the endpoint's
  `csrf token mismatch` marker maps to `GraphQLFailureClass.CSRF_FAILURE`; **every other**
  400 stays `MALFORMED_REQUEST`. The 200 `extensions.code == "csrf"` path
  (`_classify_top_level_errors`, `:1955-1968`) is unchanged.
- `CSRF_FAILURE` and `MALFORMED_REQUEST` are both permanent and non-retried; the
  `GraphQLFailureClass` vocabulary is unchanged and no retry-policy change occurs.
- The unpublished **envelope** form of a mismatch (a 200 body carrying a CSRF error
  code) is **UNVERIFIED** (the envelope probe returned 200 with `data` for a sentinel
  token); R3 does not claim it and leaves the existing envelope path alone.

## 8. Edge cases and invariants

- **Header/cookie equality.** The `X-CSRF-Token` header value and the `_csrf` cookie
  value are the same operator-supplied token, byte-for-byte; a mismatch is a hard
  failure, not a retry. `_csrf` appears exactly once in the emitted `Cookie` header.
- **One credential source.** The token comes only from
  `NICHESCOUT_UNITY_CSRF_TOKEN` via `Credentials`; there is no bootstrap, no cookie jar,
  no fallback, and no second source. `config.py`/`.env.example` are unchanged and no
  variable becomes dead.
- **No secret leakage (LREQ-SEC-020).** The token, the `Cookie` value, and the
  `X-CSRF-Token` value never appear in `header_names`, `request_metadata_json`, an
  issue, an error summary, a warning, a log line, a fixture, `config/**`, `.env.example`,
  SQLite, or the run log. `build_request_metadata_json` accepts no cookie/header-value
  parameter and is unchanged.
- **Empty/whitespace token.** `_require_unity_csrf_token` raises `ValueError` before any
  request or cookie exists; the message names `UNITY_CSRF_TOKEN_ENV` and echoes no part
  of the value.
- **No cookie persistence.** The `_csrf` value exists only as an in-memory request
  header for the batch POST; it is never written to disk, SQLite,
  `request_metadata_json`, a log line, or a committed fixture.
- **D4 is not a defect.** A `transport_failure` with `http_status = None` is a
  client-side send failure; it is distinct from the 400/500 responses the defects
  produce. No code change; recorded only.
- **Object-shaped `category`/`publisher` in a response.** With R2, the response carries
  objects. `_usable_container_json` returns `None` for an empty container and compact
  JSON otherwise; a missing/absent member stays `None` (no zero-fill).
- **Determinism.** The request and header map are deterministic functions of
  `(asset_identity_key, credentials, endpoint)`; no clock, RNG, or set/dict-ordering
  dependence (LREQ-ARCH-030).
- **No new artifact semantics.** No schema, no persisted column, no metric/score/report
  field changes.

## 9. Test plan

- **Files:** new nodes in `tests/test_collector.py` and `tests/test_cli.py`; fixture
  edits in `tests/fixtures/graphql_fixtures.py` and `tests/fixtures/cli_fixtures.py`.
  No live network; every transport is a recording double.
- **Fixture additions (proposed; `test-author` owns names):**
  - A container-shaped `ProductDetail` payload helper whose `category`/`publisher` are
    `{"id": ..., "name": ...}` mappings, so `validate_product_detail_payload` is
    exercised against the live object shape (`collector_graphql.py:1235-1236`).
  - A `http_400_csrf_mismatch` entry in `PER_FAILURE_CLASS_RESPONSES`
    (`tests/fixtures/graphql_fixtures.py:853-888`) with body `csrf token mismatch`.
  - A cookie-carrying header map in `tests/fixtures/cli_fixtures.py` — extend
    `graphql_headers()` (`:388-390`) so it returns both `"x-csrf-token"` and `"cookie"`
    with a non-secret fixture value; the `cookie` value is `"_csrf=" + <same fixture
    value>`.
- **Exact markers and traceability entries.** `tests/traceability.json` is
  **node-ID → array of LREQ IDs** (orientation verified against
  `tools/validate_traceability.py:163-177`). Each node must carry exactly these marker
  arguments and exactly matching matrix values.

| pytest node ID | `@pytest.mark.lreq(...)` marker args | `tests/traceability.json` value |
|---|---|---|
| `tests/test_collector.py::test_graphql_headers_include_matching_csrf_cookie_and_header` | `LREQ-GQL-010`, `LREQ-SEC-010` | `["LREQ-GQL-010", "LREQ-SEC-010"]` |
| `tests/test_collector.py::test_batch_request_header_names_include_cookie_name_only` | `LREQ-SEC-020` | `["LREQ-SEC-020"]` |
| `tests/test_collector.py::test_product_detail_query_selects_category_and_publisher_id_name` | `LREQ-GQL-020` | `["LREQ-GQL-020"]` |
| `tests/test_collector.py::test_object_shaped_category_and_publisher_payload_validates` | `LREQ-GQL-020` | `["LREQ-GQL-020"]` |
| `tests/test_collector.py::test_http_400_csrf_mismatch_body_is_classified_csrf_failure` | `LREQ-EXT-100`, `LREQ-GQL-040` | `["LREQ-EXT-100", "LREQ-GQL-040"]` |
| `tests/test_cli.py::test_build_graphql_transport_sends_matching_cookie_and_csrf_header` | `LREQ-CLI-010`, `LREQ-SEC-010` | `["LREQ-CLI-010", "LREQ-SEC-010"]` |

- **Renamed node.** `tests/test_cli.py::test_build_graphql_transport_sends_matching_cookie_and_csrf_header`
  replaces the old node ID; its `tests/traceability.json` key changes old→new with the
  same LREQ values. The old node ID must not remain as an orphan key.
- **Node-by-node expected values (hand-derived; no implementation reading).**
  - **Node 1 `test_graphql_headers_include_matching_csrf_cookie_and_header`.** Call
    `build_graphql_headers(credentials=GQL_CREDENTIALS)` where `GQL_CREDENTIALS` carries
    the fixture token (for example `"fixture-csrf-token"`). Expected: the map has exactly
    one `x-csrf-token` member and exactly one `cookie` member; both carry the same token
    value; `cookie == "_csrf=" + token`; the map is a read-only `MappingProxyType`. A
    credential-free fixture (`unity_csrf_token == ""`) raises `ValueError` whose text
    contains neither the token nor any part of it.
  - **Node 2 `test_batch_request_header_names_include_cookie_name_only`.** Build a
    request; expected `set(request.header_names) == {*GRAPHQL_REQUEST_HEADERS,
    "x-csrf-token", "cookie"}` (eight names, always); no header **value** appears in
    `header_names` or in the request object's other fields.
  - **Node 3 `test_product_detail_query_selects_category_and_publisher_id_name`.**
    Expected exact query text per §7.2; `"category"` and `"publisher"` each followed (in
    the text) by a `{ id name }` block; no forbidden field
    (`favoriteCount`, `packageInListHotness`, `hotness`); the frozen
    `EXPECTED_PRODUCT_DETAIL_REQUEST_OBJECT["query"]` fixture is updated to match.
  - **Node 4 `test_object_shaped_category_and_publisher_payload_validates`.** A payload
    with `"category": {"id": "38", "name": "Props"}` and
    `"publisher": {"id": "12140", "name": "Lukas Bobor"}` validates with
    `failure_class is NONE`, `category_json`/`publisher_json` are compact JSON of the
    object, and a missing pair stays `None` (never `"{}"`/`0`). Hand-derived expected
    strings: `'{"id":"38","name":"Props"}'` and
    `'{"id":"12140","name":"Lukas Bobor"}'` (sorted-key compact JSON).
  - **Node 5 `test_http_400_csrf_mismatch_body_is_classified_csrf_failure`.** A
    recording transport returns HTTP 400 with body `csrf token mismatch`; expected
    `failure_class is GraphQLFailureClass.CSRF_FAILURE`, `attempts == 1` (never
    retried), and the sibling-200 `extensions.code == "csrf"` node
    (`test_operation_level_errors_on_http_200_are_operation_errors`) still passes
    unchanged. A 400 with any other body stays `MALFORMED_REQUEST`.
  - **Node 6 (renamed) `test_build_graphql_transport_sends_matching_cookie_and_csrf_header`.**
    With a recording `urllib` seam, drive `cli.build_graphql_transport()` with the
    extended `graphql_headers()` fixture. Expected: the recorded `Request` carries
    exactly one `x-csrf-token` name and exactly one `cookie` name; the `_csrf` cookie
    value equals the header value byte-for-byte; no other header is added by the
    transport; the request body is byte-equal to `request.body_json` encoded UTF-8.
- **Golden vectors / expected values.** All values above are hand-derived from the live
  log §2/§5 and the SRS; no golden-vector file is added. The request/response fixture
  values already committed are the goldens that change.
- **Existing nodes that must keep passing unchanged:** the pin rows in §5.2 after their
  contradicted assertions are updated; `test_permanent_auth_csrf_and_malformed_request_are_not_retried`
  (Coveo, `LREQ-EXT-100`) and every `test_identity_preflight.py` node are untouched.
- **Contradiction handling.** If any existing test contradicts the SRS or this plan
  after these changes, `test-author` leaves it and reports
  `DISPUTE: <test id> — SRS §x says ...`; it is not silently edited.

## 10. Definition of done (gate)

Chunk 17 has **no `requirements-dependency-map.md` §3 gate**. The gate below is the
dispatch's Definition of Done (same shape as Chunk 14's).

Copied from the dispatch:

- **Full suite green, with real, countable counts.** `python -m pytest -q` reports
  `passed, 0 failed` with the real counts written into the run log; the count is stated
  as the pre-change baseline plus the number of new nodes, and the exact command and its
  verbatim output are recorded. An unrelated pre-existing failure is reported verbatim
  rather than claimed green.
- **All four validators valid:** `python -m niche_scout.tools.validate_traceability`,
  `python -m niche_scout.tools.check_import_boundaries`,
  `python -m niche_scout.tools.check_scope_prohibitions`,
  `python -m niche_scout.tools.check_secrets`.
- **`ruff` on changed files with the Chunk 14 pre-existing-backlog caveat.** Using the
  configuration in `pyproject.toml` (`[tool.ruff] line-length = 88`,
  `select = ["E", "F", "I"]`); no new lint is introduced; any pre-existing deviation is
  reported as PARTIAL with the unchanged lines named, never silently reformatted. State
  the byte-exact HEAD baseline method (compare the changed files against their
  `git show HEAD:<path>` byte-exact extraction, per the project's git-object rules).
- **Configuration/template/taxonomy consistency unchanged.** `config/categories.json`,
  `config/category_taxonomy.json`, and `config/coveo_search_template.json` are
  untouched and remain mutually consistent; this chunk changes no config. `config.py`
  and `.env.example` are untouched; `NICHESCOUT_UNITY_CSRF_TOKEN` remains the one
  working source.
- **No secret anywhere; no live network in tests.** The `_csrf` cookie is a credential:
  only non-secret fixture literals appear in tests, and the real value never appears in
  source, tests, fixtures, config, the plan, the run log, SQLite, any error message, or
  any artifact. No test calls the real batch endpoint.
- **Plan, run log, tests, traceability, and every new convention recorded**, including
  the old→new `test_cli.py` node rename in `Documents/runs/chunk-17.md`.
- **Human live-run bullet reserved for the human.** Whether a human
  `python -m niche_scout run` now reaches and passes the identity preflight against the
  live endpoint is the human's check, exactly as in Chunk 14; this chunk's offline gate
  cannot prove the live end-to-end path. The lead's probe already showed the corrected
  request with a matching cookie+header returns HTTP 200, but the full run is the
  human's.
- **Every checkpoint resolved by a human is recorded in §12.1; every remaining
  obligation is recorded in §12.2 and not resolved.**

## 11. Explicit prohibitions

- **Live network in development or tests.** No test calls the real endpoint; the
  `.scratch` logs are quoted, never re-fetched. Do not run `niche-scout run`.
- **No edits to** `metrics.py`, `scoring.py`, `models.py`, `database.py`, `report.py`,
  `pipeline.py`, `config.py`, `.env.example`, `sampling.py`, `validation.py`,
  `collector.py`, `collector_coveo.py`, `src/niche_scout/tools/**`, `pyproject.toml`,
  `config/**`.
- **No new config knob, no new CLI flag, no new environment variable.** No new parameter
  on the two frozen builders (`build_graphql_headers`, `build_graphql_batch_request`).
- **No env-var removal.** `NICHESCOUT_UNITY_CSRF_TOKEN` is the one working source and
  stays required by `Credentials.require_for_collection()`; do not delete it, rename it,
  or default around it.
- **No `favorite_count`, no extra GraphQL operation or field, no scheduling,
  resume/checkpoint, historical/run-comparison, new dependency, multi-user/cloud.**
- **No secret in source, tests, fixtures, config, plan, run log, SQLite, or logs.** The
  `_csrf` cookie is a credential: tests use only non-secret fixture literals and no token
  literal appears in any test.
- **No bootstrap, no cookie jar, no automated credential acquisition.** The token comes
  only from the operator credential; SRS-lean §1.3 lists automated credential
  acquisition as out of scope.
- **No `Cookie` header for any host other than the frozen GraphQL batch endpoint**, and
  no cookie emitted without the matching `X-CSRF-Token`.
- **No cookie persistence.** The cookie is an in-memory request header only; it is never
  written to disk, SQLite, `request_metadata_json`, a log line, or a fixture.
- **Do not rename any node ID other than the one explicit rename**
  (`test_build_graphql_transport_sends_csrf_header_only_and_no_cookie` →
  `test_build_graphql_transport_sends_matching_cookie_and_csrf_header`); do not delete
  any `tests/traceability.json` entry.
- **Do not re-open the four checkpoints.** They are resolved by binding human ruling
  (2026-09-24) and recorded in §12.1; implement the ruled behavior, not an alternative.
- **Do not edit** `Documents/SRS-lean.md`, `Documents/requirements-dependency-map.md`,
  `AGENTS.md`, `kilo.json(c)`, `.kilo/`, or any frozen `Documents/interfaces/*`,
  `Documents/plans/*`, or `Documents/runs/*` file (except the new
  `Documents/runs/chunk-17.md`).
- **Do not change the URI trailing-identifier extraction rule (`1.0.1`)** and add no
  claim that it is verified; it stays inferred and UNVERIFIED.
- **Do not reopen OI-6 as a code obligation** beyond recording the live answers and the
  chosen (option (a), operator-supplied) cookie-supply mechanism.
- **Do not claim the mismatch *envelope* path is verified.** Only the plain-text HTTP 400
  body was observed live; the 200-with-error-code envelope stays UNVERIFIED.

## 12. Checkpoint record and remaining open items

### 12.1 The four checkpoints — RESOLVED by binding human ruling (2026-09-24; Q1 revised)

The DRAFT revision of this plan presented four unresolved checkpoints. The human resolved
all four; the rulings are binding and supersede the options. **Q1 was revised from option
(b) to option (a).**

1. **Q1 — cookie supply = option (a), operator-supplied token sent as both cookie and
   header.** `build_graphql_headers(*, credentials)` keeps its frozen signature
   **unchanged** and emits, in addition to the six `GRAPHQL_REQUEST_HEADERS` and
   `"x-csrf-token": <token>`, a `"cookie": "_csrf=" + <token>` member (lowercase key).
   Header and cookie carry the same `credentials.unity_csrf_token`, byte-for-byte.
   `build_graphql_batch_request(...)` also keeps its frozen signature; its
   `header_names` becomes
   `(*sorted(GRAPHQL_REQUEST_HEADERS), GRAPHQL_CSRF_HEADER_NAME.lower(), "cookie")`.
   Recorded as R1/§5.1/§7.1.
   - **SRS basis accepted:** SRS-lean §1.3 (line 102) lists "automated credential
     acquisition" as **Out of scope**; §3.2 step 1 (line 202) loads "the Unity CSRF
     credential"; `LREQ-SEC-010` (§4.3 line 348) requires it from environment variables
     before network collection; §14 (lines 1305-1306) names
     `NICHESCOUT_UNITY_CSRF_TOKEN` as an operator-supplied Environment GraphQL
     credential. Option (a) honours all four and leaves no dead/misleading config
     variable.
   - Divergence adopted: `interfaces/chunk-05.md` §5.3 "No `Cookie` header is
     constructed" (§5.1), now via the existing credential rather than a bootstrap; **no
     signature divergence**. `Documents/interfaces/chunk-05.md` is **not** edited.
2. **Q2 — field-list correction = `category { id name }` / `publisher { id name }`**,
   the minimum satisfying current consumption; the live probe returned HTTP 200 with
   this text. Recorded as R2/§7.2.
3. **Q3 — 400 classification = yes.** An HTTP 400 whose body is `csrf token mismatch`
   maps to `GraphQLFailureClass.CSRF_FAILURE` (permanent, non-retrying) inside
   `collector_graphql.py`; every other 400 stays `MALFORMED_REQUEST`; the existing 200
   `extensions.code == "csrf"` path is unchanged. Recorded as R3/§7.3.
4. **Q4 — record, never close:** the cookie must not be persisted; the
   `packages/tools/utilities` 404 is a separate discovery-owner item; D4 stays an
   environment finding with no code fix.

Reference: SRS-lean §1.3 (line 102), §3.2 (line 202), §4.1 `LREQ-EXT-100`, §4.2
`LREQ-GQL-010`/`LREQ-GQL-020`, §4.3 `LREQ-SEC-010`/`LREQ-SEC-020`, §14 (lines 1305-1306);
`interfaces/chunk-05.md` §5.2/§5.3/§5.11; the `.scratch` live probes named in §1.

### 12.2 Open items (recorded, not resolved)

- **O3 — cookie non-persistence.** The `_csrf` value is in-memory only; a committed
  fixture or captured response carrying a real `_csrf` must never enter the repository.
- **O4 — discovery-path 404.** `GET .../packages/tools/utilities` returned 404 (probed);
  a real product page returned 200. `REQ-EXT-050`/truncation and category filtering stay
  out of scope; this is a separate discovery-owner item (dependency-map §3 Chunk 3 / §7).
- **O5 — D4 environment finding.** `transport_failure`, `http_status = None` on both
  failed runs; a client-side DNS/connect failure, not a protocol defect. No code fix
  proposed.
- **O6 — mismatch *envelope* path UNVERIFIED.** The envelope probe
  (`.scratch/chunk17-graphql-envelope-probe.py`) returned HTTP 200 with `data` for a
  sentinel token, so the 200-with-CSRF-error-code envelope could not be probed live.
  Only the plain-text 400 body was observed. R3 classifies the 400 body and makes no
  claim about the envelope.
- **O7 — carried-forward, not this chunk's:** URI trailing-identifier extraction
  (`identity_mapping_rule 1.0.1`) stays inferred and UNVERIFIED
  (`interfaces/chunk-01.md` §4.1; dependency-map §6.4);
  `runs.taxonomy_sha256` empty-hash rejection stays owned by Chunk 10
  (dependency-map §7).

### Assumptions (recorded, not silently resolved)

- **A1 — the `.scratch` logs are quote-fidelity evidence, not committed artifacts.**
  §1.1's live findings are human-produced and redacted; this plan trusts them as the
  operative live contract but does not commit the probe scripts or responses.
- **A2 — "the corrected request" means the live-verified working request.** The six
  constant headers plus `x-csrf-token` and `cookie: _csrf=<same>`, with the bare-array
  two-operation body.
- **A3 — the payload reader already accepts object-shaped `category`/`publisher`.**
  Read at `collector_graphql.py:1004-1026` / `:1235-1236`; R2 therefore changes only the
  query text. If a live response instead returns a different shape, that is a new
  finding for a later plan, not silently absorbed.
- **A4 — D4's `http_status: null` runs are not evidence about D1/D3.** The two defects
  are proven independently by HTTP 400/500 responses.
- **A5 — the operator-supplied token is the token the endpoint accepts.** The
  `.scratch/graphql_csrf_finding.md` §2 table row (`x-csrf-token` + `cookie: _csrf=<same>`
  → 200) and the lead's `chunk17-graphql-csrf-probe.py` row (harvested `_csrf` value as
  both cookie and header → 200) are the evidence; the operator must supply a live token,
  and a stale one yields the classified 400.

## 13. Task breakdown

- [ ] T1 — `test-author`: add the fixture additions (§9) and the new nodes + their
  `tests/traceability.json` entries; update the contradicted pin assertions (header
  name set at `tests/test_collector.py:1520-1554`, query golden,
  `cli_fixtures.graphql_headers`); and perform the single node **rename** in
  `tests/test_cli.py` (§5.2) with its traceability key old→new. All new nodes fail as
  missing-implementation; record the red state. (R4; all listed LREQs)
- [ ] T2 — `impl-deep`: implement R1 in `collector_graphql.py` — `build_graphql_headers`
  emits the cookie from the credential, `build_graphql_batch_request.header_names`
  includes `"cookie"` (`:386-398`, `:454-457`); signatures unchanged; docstrings
  updated. `cli.py` docstring-only update (`:16-21`, `:323-331`). (LREQ-GQL-010,
  LREQ-SEC-010, LREQ-SEC-020)
- [ ] T3 — `impl-deep`: implement R2 (`_PRODUCT_DETAIL_QUERY`, `:311-327`). (LREQ-GQL-020)
- [ ] T4 — `impl-deep`: implement R3 (`_classify_http_status`/its caller). (LREQ-EXT-100,
  LREQ-GQL-040)
- [ ] T5 — `impl-deep`: run the suite, the four validators, and `ruff` on the changed
  files; report real counts, the byte-exact HEAD baseline method, and any PARTIAL lint
  state. (all)
- [ ] T6 — lead/reviewer: record the plan freeze, `Documents/runs/chunk-17.md` (including
  the old→new node rename), the live-evidence provenance, the new conventions, O3–O7,
  and verify no file outside §6 changed. (all)

## 14. Freeze record

This plan is **Status: FROZEN**. All four checkpoints are resolved by binding human
ruling (2026-09-24; **Q1 = option (a)**, revised), recorded in §12.1. Option (a) creates
**no `LREQ-SEC-010` tension**: the Unity CSRF credential is read from the environment and
required before network collection, exactly as the LREQ states. The §9 pytest node IDs
are frozen with this plan; the **one explicit rename** in §5.2 (old→new, same LREQ
values, with the traceability key updated) is part of this freeze and no other node ID is
renamed. The chunk creates no interface file and edits no documented authority file
except this plan; `Documents/interfaces/chunk-05.md` is not edited and the §5.3
divergence (cookie emitted from the operator credential, no signature change) is recorded
here. Carried-forward obligations (the URI trailing-identifier extraction rule; the
`taxonomy_sha256` empty-hash owner; the discovery-path 404; D4's environment failure; the
unverified mismatch-envelope path; cookie non-persistence) are recorded, not resolved,
and are not claimed here.