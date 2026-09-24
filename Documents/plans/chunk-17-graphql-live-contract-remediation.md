# Chunk 17 — GraphQL live-contract remediation (labeled post-Chunk-16 remediation)

Status: DRAFT
Depends on (frozen interfaces required before this plan can be trusted):
  - `Documents/interfaces/chunk-05.md` §5.1 (`GRAPHQL_REQUEST_HEADERS`,
    `GRAPHQL_CSRF_HEADER_NAME`), §5.3 (`build_graphql_headers(*, credentials) ->
    Mapping[str, str]`, `build_graphql_batch_request(...)`), §5.2
    (`GraphQLFailureClass` incl. `CSRF_FAILURE`/`MALFORMED_REQUEST`), §5.11
    (transport/retry, `enrich_asset`) — consumed; §5.3's "No `Cookie` header is
    constructed" clause is the contract this chunk must diverge from under a human
    ruling.
  - `Documents/interfaces/chunk-06a.md` and `chunk-06b.md` (preflight/gate and
    one-request-per-identity behavior) — consumed unchanged; this chunk changes only
    the request the adapter sends, not the gate.
  - `Documents/interfaces/chunk-10.md` §4/§5 (`PipelineResult`, `limitations`) —
    consumed unchanged.
  - `Documents/interfaces/chunk-12.md` §5/§6 (`run_command`, transport construction) —
    consumed; `cli.build_graphql_transport` is where the production header map is
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
production transport, and their tests/fixtures.

The diagnosis is complete; nothing is routed as "investigate". The evidence is the
`.scratch` probe log `.scratch/graphql_csrf_finding.md` (probes `.scratch/unity_probe.py`,
`unity_post_probe.py`, `unity_real_probe.py`, `unity_live_check.py`). No project code was
modified by the probes.

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
  - live: `.scratch/graphql_csrf_finding.md` §1–§3, §5, §7.
- **D2 (live).** The endpoint requires the `_csrf` cookie plus **byte-for-byte** equality
  with `X-CSRF-Token`: header-only → HTTP 400 `csrf token mismatch`; cookie-only → 400;
  mismatch → 400; header + cookie equal → 200. `_csrf` is issued by a storefront page GET
  (product/listing page), **not** the homepage.
  - live: `.scratch/graphql_csrf_finding.md` §1–§3, §5, §7. The table at §2 is the
    operative evidence; §3 records that the homepage set no `_csrf`.
- **D3 (Blocker for enrichment, live).** The frozen `_PRODUCT_DETAIL_QUERY` selects
  `category`/`publisher` as scalars; live introspection shows they are **object types**:
  a bare selection → HTTP 500; `category { id name }` / `publisher { id name }` → 200.
  The other selected fields are live-valid; `firstPublishedDate` is a timezone-aware
  ISO 8601 `Z` value, so Chunk 5's parse-only date handling is compatible.
  - live: `.scratch/graphql_csrf_finding.md` §4–§5.
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
  interface; any signature or header-map change must be recorded as an explicit
  behavioural contract divergence with the affected pytest node IDs (§5). Node
  candidates are enumerated in §5.2; the **count** is `UNVERIFIED` (see §5.2).

### 1.2 What "pass the identity preflight" means here

`LREQ-ID-020` requires the normal GraphQL request to verify the request identifier is
accepted by both operations, returned identifiers are compatible, the page-view
operation is associated with the requested package identifier, and the correlation mode
is valid. The corrected request is the request shape that can satisfy it; this chunk
does not change preflight policy, thresholds, or the gate.

## 2. Scope

### In scope

- **R1 — cookie emission (D1/D2).** Make the production GraphQL request carry a
  `Cookie` header `_csrf=<value>` in addition to `X-CSRF-Token: <value>`, with the two
  byte-for-byte equal. The exact supply mechanism (operator-supplied single value vs.
  bootstrap) is **human checkpoint 1** (§12 Q1) and is **not chosen here**; the typed
  signatures for **both** the signature-preserving and the diverging variants are in
  §7 so the plan is implementable once a human picks. (LREQ-GQL-010, LREQ-SEC-010,
  LREQ-GQL-030 supporting)
- **R2 — query-shape correction (D3).** Change `_PRODUCT_DETAIL_QUERY` so `category`
  and `publisher` are selected as `{ id name }`. The exact minimum field list is
  **human checkpoint 2** (§12 Q2); `category { id name }` / `publisher { id name }` is
  the recorded minimum satisfying current consumption. (LREQ-GQL-020)
- **R3 — 400-body classification (optional; D2 mechanism).** `LREQ-EXT-100` and the
  frozen `GraphQLFailureClass` already define `CSRF_FAILURE` as permanent. Today
  `_classify_http_status` maps **every** 400 to `MALFORMED_REQUEST`
  (`collector_graphql.py:1937-1947`), and `CSRF_FAILURE` is reachable only from a
  **200** body whose error code is `csrf` (`_CSRF_ERROR_CODES` /
  `_classify_top_level_errors`, `:1950-1968`). Whether the corrected request needs an
  explicit body check mapping HTTP 400 `csrf token mismatch` → `CSRF_FAILURE`
  (non-retrying abort, same as the existing 200 predicate but at 400) is **human
  checkpoint 3** (§12 Q3). Both outcomes are non-retrying, so this is a classification
  fidelity choice, not a retry-policy change. (LREQ-EXT-100, LREQ-GQL-040 supporting)
- **R4 — tests and traceability first.** `test-author` writes the failing nodes and
  their `tests/traceability.json` entries (§9) **before** `impl-deep` edits
  `collector_graphql.py`/`cli.py`. No live network in tests.
- **R5 — record, never silently extend.** New obligations are recorded in §12: the
  storefront page URL used for bootstrap (if checkpoint 1(b)/(c) is chosen); the cookie
  must not be persisted; and the discovery-path item named below. (LREQ-SEC-020)

### Explicitly out of scope (and who owns it instead)

- **D4's transport/environment failure.** No code change. It is a client-side DNS/connect
  failure; the two defects are proven independently. Owner: none (environment/operator).
- **Discovery path 404.** `GET https://assetstore.unity.com/packages/tools/utilities`
  returns 404 (probed); a real product page returns 200. `REQ-EXT-050`/truncation and
  category filtering are out of scope and are recorded as a **separate discovery-owner
  item** (dependency-map §3 Chunk 3 / §7), never resolved here.
- **`taxonomy_sha256` empty-hash rejection.** Stays owned by **Chunk 10**
  (dependency-map §7). Not touched.
- **URI trailing-identifier extraction (`identity_mapping_rule 1.0.1`).** Stays
  **inferred and UNVERIFIED** (`interfaces/chunk-01.md` §4.1; dependency-map §6.4). Not
  touched and no verification claimed.
- **Bulk enrichment behavior, preflight policy/thresholds, sampling, metrics, scoring,
  `database.py`, `report.py`, `models.py`.** No change. (`metrics.py`/`scoring.py`/
  `models.py`/`database.py`/`report.py` are explicitly untouchable.)
- **New config knobs.** No new CLI flag and no new environment variable beyond the
  existing `NICHESCOUT_UNITY_CSRF_TOKEN` (SRS §14). No configurable score weights.
- **`favorite_count`, extra GraphQL operations/fields, scheduling, resume/checkpoint,
  new dependencies, multi-user/cloud.** Forbidden (dependency-map §15, AGENTS.md
  "Out of scope — do not add").
- **Live network.** No live call in development or tests; the `.scratch` log is the only
  live evidence and is quoted, not re-fetched.

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
| LREQ-GQL-040 | Supporting (Chunk 5 remains primary) | "Each operation SHALL have an independent status. HTTP failures, top-level GraphQL `errors`, … SHALL be recorded as an operation error." R3 is the classification of the HTTP 400 `csrf token mismatch` body; whether it is `CSRF_FAILURE` (preferred by `LREQ-EXT-100`) or `MALFORMED_REQUEST` is checkpoint 3. | §4.2 (line 318) |
| LREQ-EXT-100 | Primary (this remediation's classification half) | "Requests SHALL be rate-limited and retry transient `429` and `5xx` responses with exponential backoff. Permanent authentication, CSRF, malformed request, or authorization failures SHALL not be retried indefinitely." Both R3 outcomes are permanent/non-retried; the corrected request must not be retried on a CSRF mismatch. | §4.1 (line 283) |
| LREQ-SEC-010 | Supporting (Chunk 0/2/5 remain primary) | "Coveo and Unity CSRF credentials SHALL be read from environment variables and SHALL be required before network collection." The cookie value, if operator-supplied, is the existing `NICHESCOUT_UNITY_CSRF_TOKEN`; no new credential source is invented. | §4.3 (line 348) |
| LREQ-SEC-020 | Supporting (Chunk 2/5 remain primary) | "Secrets SHALL NOT be written to source control, logs, SQLite, or error messages." The cookie value and the `Cookie` header value must never reach `header_names`, `request_metadata_json`, an issue, a summary, a log line, a fixture, or any artifact. | §4.3 (line 351) |
| LREQ-ID-020 | Integration completion (Chunk 6A remains primary) | "The preflight SHALL perform the normal GraphQL request and verify … the page-view operation is associated with the requested package identifier; the operation-correlation mode is valid." A corrected request is the prerequisite for the preflight to be able to pass; this chunk changes no preflight logic. | §4.4 (line 368) |
| LREQ-ARCH-030 | Supporting (Chunk 10 remains primary) | "The same normalized input data, policy versions, and configuration SHALL produce the same metric, score, evidence, and sensitivity outputs." The corrected request is a deterministic function of its inputs; no clock, RNG, or set/dict-ordering dependence is introduced. | §3 |

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
  supplied, never the values".
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
  (`cli.py:335-353`); it constructs no header itself.
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

### 5.1 Behavioural contract divergences (replace interface-document state without rewriting the frozen files)

The frozen Chunk 5 contract states in §5.3: "No `Cookie` header is constructed,
emitted, or modified." R1 **diverges** from that clause under a human ruling
(checkpoint 1). This divergence is recorded here and in the run log;
`Documents/interfaces/chunk-05.md` is **not** edited by this chunk.

**Signature disposition, per checkpoint 1 option (do not choose here):**

- **Option 1(a) — operator-supplied value sent as both cookie and header (minimal).**
  Keep both public signatures byte-identical:
  `build_graphql_headers(*, credentials: Credentials) -> Mapping[str, str]` and
  `build_graphql_batch_request(asset_identity_key: str, *, credentials: Credentials,
  endpoint: str = GRAPHQL_BATCH_ENDPOINT) -> GraphQLBatchRequest`. The returned header
  map gains a `"cookie": "_csrf=<token>"` member (lowercase key, per the wire
  convention), and `header_names` gains `"cookie"`. No new parameter is introduced.
  This honours retired ND-8 / Assumption A-4 ("operator-supplied only").
- **Option 1(b)/(c) — bootstrap or hybrid.** These require a new cookie-source step.
  Their typed shape (e.g. a separate cookie-header builder or an added keyword) is
  **not frozen here**; a signature change must name the affected tests and is recorded
  as a behavioural contract change. (b)/(c) contradict retired ND-8 / Assumption A-4
  and the frozen Chunk 5 clause and therefore need an explicit human ruling.

**R2 divergence.** The emitted `ProductDetail` query text changes from the scalar
`category\n    publisher` selection to `category { id name }` / `publisher { id name }`.
This is a behavioural contract change for the request goldens, recorded with the
affected tests below.

**R3 divergence (if adopted).** `_classify_http_status` (or a body-aware HTTP-failure
classifier around it) would classify a 400 body `csrf token mismatch` as
`CSRF_FAILURE` instead of `MALFORMED_REQUEST`. The `GraphQLFailureClass` vocabulary is
unchanged; only which member a 400 body maps to changes.

### 5.2 Pytest node IDs and fixtures pinning the affected contract

The enumeration below is a **reading-derived candidate set**. The **count is
`UNVERIFIED`** (no counted `grep` enumeration was run in the drafting session; the
`bash` tool is denied in this environment). Each row was read this session at the
cited location.

| Artifact | Location read | What it pins |
|---|---|---|
| `tests/test_cli.py::test_build_graphql_transport_sends_csrf_header_only_and_no_cookie` | `tests/test_cli.py:855-881` | asserts `"cookie" not in lowered` — directly contradicted by R1 |
| `tests/test_collector.py::test_batch_request_has_exactly_two_operations_with_one_identity` | `tests/test_collector.py:1520-1554` | asserts `set(request.header_names) == {*GRAPHQL_REQUEST_HEADERS, GRAPHQL_CSRF_HEADER_NAME.lower()}` — contradicted by a `cookie` header name |
| `tests/test_collector.py::test_product_detail_query_requests_only_required_fields` | `tests/test_collector.py:1593-1623` | asserts `query == gqlfx.EXPECTED_PRODUCT_DETAIL_REQUEST_OBJECT["query"]` — contradicted by R2 |
| `tests/test_collector.py::test_page_views_operation_requests_its_scalar` | `tests/test_collector.py:1626-1641` | pins the `ProductPageViews` query; expected unchanged, re-check after R2 |
| `tests/test_collector.py::test_validated_position_mode_is_accepted_not_validated_here` | `tests/test_collector.py:1858-1901` | calls `build_graphql_headers(credentials=...)` at `:1870` and `:1887`; pins the keyword-only signature |
| `tests/test_collector.py::test_operation_level_errors_on_http_200_are_operation_errors` | `tests/test_collector.py:1987-2016` | pins CSRF classification **at 200**; R3 must not remove this path |
| `tests/fixtures/graphql_fixtures.py` `EXPECTED_PRODUCT_DETAIL_REQUEST_OBJECT` | `tests/fixtures/graphql_fixtures.py:185-205` | carries the scalar query text; must be updated for R2 |
| `tests/fixtures/graphql_fixtures.py` `PRODUCT_DETAIL_SELECTION_SET` | `tests/fixtures/graphql_fixtures.py:160-170` | names `"category"`/`"publisher"` as members; R2 changes the emitted nesting |
| `tests/fixtures/graphql_fixtures.py` `product_detail_payload()` | `tests/fixtures/graphql_fixtures.py:296-321` | returns `category`/`publisher` as **strings**; a live-shaped response fixture needs a new helper (or a container-shaped payload) |
| `tests/fixtures/graphql_fixtures.py` `PER_FAILURE_CLASS_RESPONSES` | `tests/fixtures/graphql_fixtures.py:853-888` | has no `http_400_csrf_mismatch` case; R3's test needs one |
| `tests/fixtures/cli_fixtures.py` `graphql_headers()` | `tests/fixtures/cli_fixtures.py:388-390` | returns only `{"x-csrf-token": ...}`; the transport test's header input must gain the cookie for R1 |
| `tests/test_collector.py::test_permanent_auth_csrf_and_malformed_request_are_not_retried` | `tests/test_collector.py:1097-1125` | **Coveo** (`LREQ-EXT-100`) test, not GraphQL; listed so it is not mistaken for the adapter path |

No existing node ID is renamed or deleted. Where a pin is contradicted, `test-author`
updates the node's assertions and the affected fixture values; the node ID and its
`tests/traceability.json` key stay byte-identical unless a human rules otherwise.

## 6. Files touched

**Expected paths — this chunk must touch no others.**

| File | New/modified | Purpose |
|---|---|---|
| `src/niche_scout/collector_graphql.py` | modified | R1: `build_graphql_headers` emits the `cookie` header; `build_graphql_batch_request.header_names` includes `"cookie"`. R2: `_PRODUCT_DETAIL_QUERY` selects `category { id name }` / `publisher { id name }`. R3 (only if checkpoint 3 is decided): 400 `csrf token mismatch` classification in `_classify_http_status`/its caller. |
| `src/niche_scout/cli.py` | modified | Nothing unless checkpoint 1(b)/(c) is chosen; option 1(a) needs **no** `cli.py` change because `build_graphql_transport` already forwards the caller-supplied header map (`cli.py:335-353`). The module docstring `:16-21` may need a one-line update to match the emitted headers. |
| `tests/fixtures/graphql_fixtures.py` | modified | Update `EXPECTED_PRODUCT_DETAIL_REQUEST_OBJECT` and `PRODUCT_DETAIL_SELECTION_SET` for R2; add a live-shaped (container `category`/`publisher`) payload helper and a 400 `csrf token mismatch` response case if R3 is adopted; add a cookie-carrying header-map helper for R1. |
| `tests/fixtures/cli_fixtures.py` | modified | `graphql_headers()` gains the `cookie` member so `test_build_graphql_transport_*` can assert cookie + header both present and equal. |
| `tests/test_collector.py` | modified | Update the contradicted pins (header-name set, query golden) and add the new R1/R2/R3 nodes (§9). Node IDs of existing tests unchanged. |
| `tests/test_cli.py` | modified | Update `test_build_graphql_transport_sends_csrf_header_only_and_no_cookie` (its negative `"cookie" not in lowered` assertion is contradicted by R1) and add the new cookie-emission node (§9). |
| `tests/traceability.json` | modified | Add node-ID → `[LREQ ids]` entries for every new test node (orientation verified: node ID → array, `validate_traceability.py:163-177`). |
| `Documents/runs/chunk-17.md` | new (lead/run log, not this planner) | The run log the gate requires. Recorded here as required output; this planner does **not** create it. |

**Not touched (explicit):** `metrics.py`, `scoring.py`, `models.py`, `database.py`,
`report.py`, `pipeline.py`, `config.py`, `sampling.py`, `validation.py`,
`collector.py`, `collector_coveo.py`, `src/niche_scout/tools/**`, `pyproject.toml`,
`config/**`, `Documents/SRS-lean.md`, `Documents/requirements-dependency-map.md`,
`AGENTS.md`, `kilo.json(c)`, `.kilo/`, and any `Documents/interfaces/*` file.

## 7. Typed function/class signatures

A `test-author` writes tests from these without seeing the implementation, so names,
parameter types, return types, and module paths are exact. Every option is given
because checkpoints 1–3 are unresolved; `test-author` implements the option a human
selects and leaves the others.

### 7.1 R1 — cookie emission

**Option 1(a) (signature-preserving; recommended minimal change under ND-8/A-4):**

```python
# src/niche_scout/collector_graphql.py — signature UNCHANGED
def build_graphql_headers(*, credentials: Credentials) -> Mapping[str, str]: ...
```

- Returns a `MappingProxyType` with the six `GRAPHQL_REQUEST_HEADERS` members plus
  `"x-csrf-token": <token>` plus **`"cookie": "_csrf=" + <token>`** (lowercase keys).
- The cookie value is exactly `"_csrf=" + token`, where `token` is the same
  whitespace-checked value returned by `_require_unity_csrf_token(credentials)`. Header
  and cookie carry the identical token string; a byte mismatch is a defect.
- Empty/whitespace-only or non-`str` CSRF credential raises `ValueError` naming
  `config.UNITY_CSRF_TOKEN_ENV` **before** any map exists, and never echoes the value
  (LREQ-SEC-010).
- The returned map carries the credential; it is never placed in `header_names`,
  `request_metadata_json`, an error summary, a warning, or a log line.
- `header_names` in `build_graphql_batch_request` becomes
  `(*sorted(GRAPHQL_REQUEST_HEADERS), GRAPHQL_CSRF_HEADER_NAME.lower(), "cookie")`
  (eight names). Names only, never values.

**Option 1(b)/(c) (bootstrap/hybrid — NOT frozen here).** A new cookie-source step is
required; the exact signature is a human decision. If adopted, the divergence is
recorded per §5.1 and the new function's name/typing is fixed in a human-approved plan
revision before `test-author` writes against it.

- `cli.build_graphql_transport` needs **no** logic change for 1(a): it already sends
  `dict(headers)` verbatim (`cli.py:335-353`). For 1(b)/(c) it gains the cookie-source
  call and must not add a cookie for any other host.

### 7.2 R2 — query shape

```python
# src/niche_scout/collector_graphql.py — module-private constant, no public signature
_PRODUCT_DETAIL_QUERY: str  # category and publisher selected as { id name }
```

- The emitted text is exactly (after a human confirms checkpoint 2):
  `query ProductDetail($id: ID!) {\n  product(id: $id) {\n    id\n    productId\n    rating {\n      average\n      count\n    }\n    reviewCount\n    firstPublishedDate\n    state\n    category {\n      id\n      name\n    }\n    publisher {\n      id\n      name\n    }\n  }\n}`.
- `build_product_detail_operation(asset_identity_key: str) -> GraphQLOperation` is
  unchanged in signature; only the query text it carries changes.
- No other operation or field is added; `favorite_count`, `packageInListHotness`, and
  every non-required field stay absent.
- The response side already accepts a container for `category`/`publisher`
  (`_usable_container_json`, `:1004-1026`), so `ProductDetailFields.category_json` /
  `publisher_json` continue to hold compact JSON; no validation-path change is in scope.

### 7.3 R3 — 400 CSRF-body classification (only if checkpoint 3 is decided "yes")

```python
# src/niche_scout/collector_graphql.py — private classifier
def _classify_http_status(http_status: int, *, body_text: str = ...) -> GraphQLFailureClass: ...
```

- If a human rules **yes**: a 400 whose (already-read) body text contains the endpoint's
  `csrf token mismatch` marker maps to `GraphQLFailureClass.CSRF_FAILURE`; every other
  400 stays `MALFORMED_REQUEST`. The 200 `extensions.code == "csrf"` path
  (`_classify_top_level_errors`, `:1955-1968`) is unchanged.
- If a human rules **no**: `_classify_http_status` is unchanged; 400 remains
  `MALFORMED_REQUEST`. Both classes are permanent and non-retried already.
- Either way, no retry-policy change and no new `GraphQLFailureClass` member.

## 8. Edge cases and invariants

- **Header/cookie equality.** The `X-CSRF-Token` header value and the `_csrf` cookie
  value are the same token, byte-for-byte; a mismatch is a hard failure, not a retry.
- **No secret leakage (LREQ-SEC-020).** The token, the `Cookie` value, and the
  `X-CSRF-Token` value never appear in `header_names`, `request_metadata_json`, an
  issue, an error summary, a warning, a log line, a fixture, `config/**`, or SQLite.
  `build_request_metadata_json` accepts no cookie/header-value parameter and is
  unchanged.
- **Null vs. empty CSRF credential.** Empty/whitespace-only raises `ValueError` before
  any request object exists; a `None` is rejected by the same predicate
  (`_require_unity_csrf_token`, `:365-383`). No default substitution.
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
  - A live-shaped `ProductDetail` payload helper whose `category`/`publisher` are
    `{"id": ..., "name": ...}` mappings (or a `category_json`/`publisher_json`
    expectation), so `validate_product_detail_payload` is exercised against the live
    object shape (`collector_graphql.py:1235-1236`).
  - A `http_400_csrf_mismatch` entry in `PER_FAILURE_CLASS_RESPONSES`
    (`tests/fixtures/graphql_fixtures.py:853-888`) with body `csrf token mismatch`,
    added only if R3 is adopted.
  - A cookie-carrying header map in `tests/fixtures/cli_fixtures.py` (extend
    `graphql_headers()`, `:388-390`) with a non-secret fixture value.
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
| `tests/test_collector.py::test_http_400_csrf_mismatch_body_is_classified_csrf_failure` *(only if R3 adopted)* | `LREQ-EXT-100`, `LREQ-GQL-040` | `["LREQ-EXT-100", "LREQ-GQL-040"]` |
| `tests/test_cli.py::test_build_graphql_transport_sends_matching_cookie_and_csrf_header` | `LREQ-CLI-010`, `LREQ-SEC-010` | `["LREQ-CLI-010", "LREQ-SEC-010"]` |

- **Node-by-node expected values (hand-derived; no implementation reading).**
  - **Node 1 `test_graphql_headers_include_matching_csrf_cookie_and_header`.** Call
    `build_graphql_headers(credentials=GQL_CREDENTIALS)`. Expected: the map has exactly
    one `x-csrf-token` member and exactly one `cookie` member; both carry the same token
    string from the fixture credential; `cookie == "_csrf=" + token`; the map is a
    read-only `MappingProxyType`; a credential-free fixture raises `ValueError` whose
    text contains neither the fixture token nor any part of it.
  - **Node 2 `test_batch_request_header_names_include_cookie_name_only`.** Build a
    request; expected `set(request.header_names) == {*GRAPHQL_REQUEST_HEADERS,
    "x-csrf-token", "cookie"}` and no header **value** appears in `header_names` or in
    the request object's other fields.
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
  - **Node 5 (R3 only) `test_http_400_csrf_mismatch_body_is_classified_csrf_failure`.**
    A recording transport returns HTTP 400 with body `csrf token mismatch`; expected
    `failure_class is GraphQLFailureClass.CSRF_FAILURE`, `attempts == 1` (never
    retried), and the sibling-200 `extensions.code == "csrf"` node
    (`test_operation_level_errors_on_http_200_are_operation_errors`) still passes.
  - **Node 6 `test_build_graphql_transport_sends_matching_cookie_and_csrf_header`.**
    With a recording `urllib` seam, drive `cli.build_graphql_transport()` with the
    extended `graphql_headers()` fixture. Expected: exactly one `x-csrf-token` name and
    exactly one `cookie` name; the two values are equal and equal `"_csrf=" + token`;
    no other header is added by the transport; the request body is byte-equal to
    `request.body_json` encoded UTF-8.
- **Golden vectors / expected values.** All values above are hand-derived from the live
  log §5 and the SRS; no golden-vector file is added. The request/response fixture
  values already committed are the goldens that change.
- **Existing nodes that must keep passing unchanged:** the six pin rows in §5.2 after
  their contradicted assertions are updated; `test_permanent_auth_csrf_and_malformed_request_are_not_retried`
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
  untouched and remain mutually consistent; this chunk changes no config.
- **No secret anywhere.** The token pasted in the human session is **burned** and must
  not appear in source, tests, fixtures, config, the plan, the run log, SQLite, any
  error message, or any artifact.
- **Plan, run log, tests, traceability, and every new convention recorded.** The plan's
  §9 node IDs are frozen with the plan.
- **Human live-run bullet reserved for the human.** Whether a human
  `python -m niche_scout run` now reaches and passes the identity preflight against the
  live endpoint is the human's check, exactly as in Chunk 14; this chunk's offline gate
  cannot prove the live end-to-end path.
- **Every open question either resolved by a human before plan freeze or left as an
  open question in the plan.** §12 lists them unresolved.

## 11. Explicit prohibitions

- **Live network in development or tests.** No test calls the real endpoint; the
  `.scratch` log is quoted, never re-fetched. Do not run `niche-scout run`.
- **No edits to** `metrics.py`, `scoring.py`, `models.py`, `database.py`, `report.py`,
  `pipeline.py`, `config.py`, `sampling.py`, `validation.py`, `collector.py`,
  `collector_coveo.py`, `src/niche_scout/tools/**`, `pyproject.toml`, `config/**`.
- **No new config knobs, no new CLI flag, no new environment variable** beyond the
  existing `NICHESCOUT_UNITY_CSRF_TOKEN` (SRS §14). No configurable score weights.
- **No `favorite_count`, no extra GraphQL operation or field, no scheduling,
  resume/checkpoint, historical/run-comparison, new dependency, multi-user/cloud.**
- **No secret in source, tests, fixtures, config, plan, run log, SQLite, or logs.**
- **No `Cookie` header for any host other than the frozen GraphQL batch endpoint**, and
  no cookie emitted without the matching `X-CSRF-Token`.
- **No cookie persistence.** The cookie is an in-memory request header only.
- **No rename or deletion of an existing pytest node ID or its
  `tests/traceability.json` entry.**
- **Do not resolve the §12 checkpoints.** Do not adopt bootstrap/hybrid cookie sourcing,
  a different field list, or the 400-classification change without a human ruling.
- **Do not edit** `Documents/SRS-lean.md`, `Documents/requirements-dependency-map.md`,
  `AGENTS.md`, `kilo.json(c)`, `.kilo/`, or any frozen `Documents/interfaces/*` or
  `Documents/runs/*` file (except the new `Documents/runs/chunk-17.md`).
- **Do not change the URI trailing-identifier extraction rule (`1.0.1`)** and add no
  claim that it is verified; it stays inferred and UNVERIFIED.
- **Do not reopen OI-6 as a code obligation** beyond recording the live answers and the
  chosen cookie-supply mechanism.

## 12. Open questions and assumptions

### Assumptions (recorded, not silently resolved)

- **A1 — the `.scratch` log is quote-fidelity evidence, not a committed artifact.**
  §1.1's live findings are human-produced and redacted; this plan trusts them as the
  operative live contract but does not commit the probe scripts or responses.
- **A2 — "the corrected request" means the §5 working request in the log.**
  `content-type`/`accept`/`origin`/`referer`/`x-requested-with`/`x-source` plus
  `x-csrf-token` and `cookie: _csrf=<same>`, with the bare-array two-operation body.
- **A3 — the payload reader already accepts object-shaped `category`/`publisher`.**
  Read at `collector_graphql.py:1004-1026` / `:1235-1236`; R2 therefore changes only the
  query text. If a live response instead returns a different shape, that is a new
  finding for a later plan, not silently absorbed.
- **A4 — D4's `http_status: null` runs are not evidence about D1/D3.** The two defects
  are proven independently by HTTP 400/500 responses.

### Open questions (not resolved by this plan; human decision required before relying on the affected behavior)

These are the **four human checkpoints** from the dispatch. Each is presented with its
options; **none is chosen**. Because they are unresolved, the plan stays
`Status: DRAFT`.

1. **How the `_csrf` cookie is supplied.**
   - Option (a): keep operator-supplied `NICHESCOUT_UNITY_CSRF_TOKEN` as the single value
     and send it as **both** `cookie: _csrf=<token>` and `X-CSRF-Token: <token>`. Honors
     retired ND-8 / Assumption A-4; smallest diff; keeps both frozen Chunk 5 signatures.
   - Option (b): auto-bootstrap — GET a storefront page, harvest `_csrf`, send the pair,
     no env var needed. Contradicts retired ND-8 / Assumption A-4 and the frozen Chunk 5
     clause "No `Cookie` header is constructed".
   - Option (c): hybrid — bootstrap only when the env var is unset. Same contradiction.
   - References: SRS §4.3 `LREQ-SEC-010`; retired `SRS-revision2.md` ND-8 and Assumption
     A-4; `interfaces/chunk-05.md` §5.3; live log §3/§7.
2. **`LREQ-GQL-020` field-list correction.** Minimum satisfying current consumption:
   `category { id name }`, `publisher { id name }`. The retired SRS's scalar field list
   is diverged from; escalate if a different shape is wanted. Reference: SRS §4.2
   `LREQ-GQL-020`; live log §4–§5.
3. **Classification of the HTTP 400 `csrf token mismatch` body.** Should a corrected
   request map 400 `csrf token mismatch` → `CSRF_FAILURE` (non-retrying abort) rather
   than today's plain-400 `MALFORMED_REQUEST`, and does that stay inside
   `collector_graphql.py`? References: SRS §4.1 `LREQ-EXT-100`; `interfaces/chunk-05.md`
   §5.2; `collector_graphql.py:1937-1947`, `:1950-1968`.
4. **New obligations to record, never close.** (i) the storefront page URL used for
   bootstrap, if option 1(b)/(c) is chosen; (ii) the cookie must not be persisted; (iii)
   the discovery-path item below (`packages/tools/utilities` 404) is a separate
   discovery-owner item. References: SRS §4.3 `LREQ-SEC-020`; dependency-map §7.

## 13. Task breakdown

- [ ] **H1 — human:** resolve §12 Q1 (cookie supply), Q2 (field list), Q3 (400
  classification), Q4 (recorded obligations). This plan stays DRAFT until then.
- [ ] T1 — `test-author`: add the fixture additions (§9) and the new nodes + their
  `tests/traceability.json` entries, and update the contradicted pin assertions (header
  name set, query golden, `cli_fixtures.graphql_headers`). All new nodes fail as
  missing-implementation; record the red state. (R4; all listed LREQs)
- [ ] T2 — `impl-deep`: implement R1 (chosen option) in `collector_graphql.py`; update
  `collector_graphql.py:454-457` header names and `:386-398`. (LREQ-GQL-010, LREQ-SEC-010)
- [ ] T3 — `impl-deep`: implement R2 (`_PRODUCT_DETAIL_QUERY`, `:311-327`). (LREQ-GQL-020)
- [ ] T4 — `impl-deep`: implement R3 only if Q3 is decided "yes"
  (`_classify_http_status`/its caller). (LREQ-EXT-100, LREQ-GQL-040)
- [ ] T5 — `impl-deep`: run the suite, the four validators, and `ruff` on the changed
  files; report real counts, the byte-exact HEAD baseline method, and any PARTIAL lint
  state. (all)
- [ ] T6 — lead/reviewer: record the plan freeze, `Documents/runs/chunk-17.md`, the
  live-evidence provenance, the new conventions, and verify no file outside §6 changed.
  (all)

## 14. Freeze record

This plan is **Status: DRAFT**, not frozen. It becomes `FROZEN` only after a human
resolves the four §12 checkpoints (or explicitly freezes with them still open). The §9
pytest node IDs are frozen with the plan once it is frozen and SHALL NOT be renamed by a
later change. The chunk creates no interface file and edits no documented authority file
except this plan. Carried-forward obligations (OI-6's live answers recorded but its
cookie-supply ruling pending; the URI trailing-identifier extraction rule; the
`taxonomy_sha256` empty-hash owner; the discovery-path 404; D4's environment failure)
are recorded, not resolved, and are not claimed here.