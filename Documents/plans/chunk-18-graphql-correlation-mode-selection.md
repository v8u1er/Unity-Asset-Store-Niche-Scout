# Chunk 18 — GraphQL correlation-mode selection (labeled post-Chunk-17 remediation)

Status: FROZEN

This plan was revised and frozen after the human ruled on all checkpoints and the live capture
closed H2/H3 (run log `Documents/runs/chunk-18.md`, "Human rulings (approved)" and "Full capture
— all ten identities + H2 probe"). The rulings encoded here are final; the plan does not
re-open them.

- **H1 = A.1b + A.2b.** Add `correlation_mode` to `execute_graphql_batch`'s frozen signature,
  pass it from `enrich_asset`, delete the post-hoc relabel; put the `LREQ-GQL-030`
  ordering/shape validation in a new public Chunk 5 primitive that the preflight calls.
  `pipeline.py` supplies evidence and persists, and MUST NOT re-implement correlation. One
  node rename approved (Chunk 17 precedent).
- **H2 = option (B) is dead.** Live: `operations: ProductDetail,ProductPageViews` +
  `apollo-require-preflight: true` returns HTTP 200, byte-unchanged body, **no `operationName`**.
  This plan does not rely on the `operations` header.
- **H3 = closed.** All ten selected preflight identities returned HTTP 200; **10/10 sha256
  match** the recorded values; ordering item0=`ProductDetail`, item1=`ProductPageViews` for all
  ten; shapes uniform; no explicit key anywhere.
- **H4 = guard only.** No extra request; the mode is computed from already-executed preflight
  responses.
- **H5 = confirmed on all ten.** ProductDetail is wrapped `{"data":{"product":{...}}}`; the
  adapter must unwrap `data.product` before `validate_product_detail_payload`.
- **G7 = confirmed on all ten.** The page-views item is `{"data":{"productPageViews": <int>=0>}}`;
  the request field is aliased to `pageViews` so the frozen `{"pageViews": ...}` validation
  holds. `productPageViews = 0` occurs (identity `59028`) and is a **valid** value.
- **Traceability = follow the committed node-ID → LREQ mapping**; do not restructure
  `tests/traceability.json`. The `tests/AGENTS.md` prose mismatch is a separate docs item.
- **Human preference: probe/test-first when unsure.**

Depends on (frozen interfaces consumed; the required conflict note is §12.1):

- `Documents/interfaces/chunk-05.md` §5.2 (`GraphQLFailureClass`), §5.5 (correlation contract,
  the "Chunk 5 MUST NOT" boundary at `:398-416`), §5.6 (`payload` is "the operation's own
  `data` mapping/scalar, verbatim", `:294`), §5.11 (`execute_graphql_batch`, `enrich_asset`
  signatures, `:770-786`) — **consumed, with two recorded contract changes: the new
  `correlation_mode` keyword (A.1b) and the ProductDetail `data.product` unwrap (H5).**
- `Documents/interfaces/chunk-6A.md` §5.1/§5.2 (`PreflightObservation`,
  `IdentityPreflightSummary`, `run_identity_preflight`, `:185-294`) — consumed; the selected
  mode becomes evidence-derived and persisted (H1/A.2b), which is a recorded semantics change.
- `Documents/interfaces/chunk-10.md:47` (`run_pipeline` `correlation_mode` default
  `EXPLICIT_KEY`) — consumed; the selected mode is carried from the preflight summary into
  `enrich_unique_identities` (§5.7). The default is **not** changed.
- `Documents/runs/chunk-18.md` "Confirmed defect", "Human rulings", and "Full capture" — the
  evidence this plan is built on.
- Binding Chunk 17 rulings on cookie/CSRF/query shape — consumed unchanged; this is a distinct
  defect (a 200 with no correlation key), not a Chunk 17 regression.

Blocks: none. This is a labeled post-completion remediation (Chunks 14/15/16/17 pattern): no
`requirements-dependency-map.md` §3/§4 gate row, no new interface file, no downstream chunk.
The gate is §9 plus the dispatch DoD (a human `python -m niche_scout run` reaching and passing
the identity preflight).

## 1. Goal

Make a human `python -m niche_scout run` reach and **pass** the identity preflight against the
live Unity storefront GraphQL endpoint by (i) making the correlation mode that production
executes actually reach the correlation algorithm, and (ii) implementing the `LREQ-GQL-030`
fallback (`VALIDATED_POSITION`) selection that no chunk implements today.

### 1.1 Grounded findings (labels: **read** = opened this session; **counted** = queried;
**live** = human-run capture recorded in `Documents/runs/chunk-18.md`)

- **G1 (read).** `collector_graphql.py:2477-2486` `_correlation_mode_for_request` hardcodes
  `EXPLICIT_KEY`; `execute_graphql_batch` (`:2402-2409`) passes it to `_interrogate_response`
  (`:2353-2359`), which calls `correlate_operations(items, mode=...)` (`:2381`).
  `execute_graphql_batch`'s frozen signature has no `correlation_mode` parameter.
- **G2 (read).** `enrich_asset` (`:2531-2541`) accepts `correlation_mode`, calls
  `execute_graphql_batch` **without** it (`:2554-2556`), and post-hoc `replace`s
  `correlation.mode` and both operation modes (`:2557-2563`). The caller's mode never
  influences correlation.
- **G3 (read).** `_correlate_by_validated_position` (`:815-863`) exists and is reachable only
  when `correlate_operations` receives `VALIDATED_POSITION` (`:898-903`). It does not validate
  ordering itself; it marks `OPERATION_CORRELATION_AMBIGUOUS` when item count ≠ 2 or any item
  carries an explicit key.
- **G4 (read).** The only "mode validation" implemented is an enum-membership check
  (`pipeline.py:599-608` `_correlation_mode_is_valid`); `run_pipeline`'s `correlation_mode`
  defaults to `EXPLICIT_KEY` (`:3149-3151`); `cli.py:429-443` sets none. No code path
  selects/validates `VALIDATED_POSITION`.
- **G5 (read).** `extract_operation_correlation_key` (`:620-636`) reads `operationName`,
  `operation_name`, `operation`, `correlationKey`; a non-mapping or keyless item returns `None`
  and is never repaired.
- **G6 (live, H3).** The 200 batch body is a JSON array of exactly two bare envelopes with
  **no explicit key**; item0 = `{"data":{"product":{...}}}`, item1 =
  `{"data":{"productPageViews": <int>=0>}}`; ordering and shapes uniform across all ten
  selected identities; 10/10 sha256 match the recorded `response_sha256`.
- **G7 (live + read).** `validate_page_views_payload` (`:1374-1412`) requires
  `{"pageViews": <value>}`. A payload that is a mapping without `pageViews` (e.g.
  `{"productPageViews": 20}`) is **`NULL_REQUIRED_DATA`** (`:1399-1412`), not
  `WRONG_DATA_SHAPE`. Zero is valid (`:1416-1423`, `:495-498`).
- **G8 (live + read).** H5: `_build_result_from_items` (`:2144-2167`) sets
  `payload = item["data"]` = `{"product": {...}}`; `validate_product_detail_payload`
  (`:1081-1121`) requires `id`/`productId`/… at the payload top level, and there is no unwrap.
  The live `product` object carries `id`, `productId`, `rating{average,count}`, `reviewCount`,
  `firstPublishedDate`, `state`, `category{id,name}`, `publisher{id,name}`.
- **G9 (counted).** `grep` pattern `operationName`, `path = tests/fixtures/graphql_fixtures.py`,
  limit 200 → **46 matches**, every one a request/response object or prose/comment; no fixture
  body is keyless. Unit = matching lines, not distinct bodies. This supersedes the run log
  P2's "40 matches". `GraphQLOperationCorrelationMode` has exactly **2** members (read
  `models.py:132-134`). `tests/traceability.json` is keyed by **pytest node ID** → array of
  LREQ IDs (read `tests/traceability.json:1-30`).
- **G10 (read).** Ownership: `SRS-lean.md:300-312` (`LREQ-GQL-030`), `:289-298`
  (`LREQ-GQL-010/020`), `:318-323` (`LREQ-GQL-040`), `:336-338` (`LREQ-GQL-080`), `:348-352`
  (`LREQ-SEC-010/020`), `:368-372` (`LREQ-ID-020`), `:386-414` (`LREQ-ID-040`).

## 2. Scope

### In scope

- **S1 — the caller's correlation mode reaches correlation (A.1b).** `execute_graphql_batch`
  gains a `correlation_mode` keyword; `enrich_asset` passes its mode; the relabel
  (`:2557-2563`) and `_correlation_mode_for_request` (`:2477-2486`) are deleted.
- **S2 — `LREQ-GQL-030` selection + validation (A.2b).** A new public Chunk 5 primitive
  validates the fixed two-operation ordering and the operation-specific response shapes across
  the selected preflight identities; the preflight selects and persists one run-level mode.
- **S3 — H5 unwrap.** Unwrap `data.product` before `validate_product_detail_payload`, with
  defined null/edge classes.
- **S4 — G7 alias.** Alias the page-views request field to `pageViews`.
- **S5 — tests and traceability first** (`test-author` before the implementer). No live network
  in tests.
- **S6 — record, never close** (§12.2).

### Explicitly out of scope (and owner)

- **Option (B), the `operations` header.** Dead (H2); not implemented.
- **A third correlation mode, a new `GraphQLFailureClass`, a new config knob, or a CLI flag.**
  None.
- **Changing `run_pipeline`'s `correlation_mode` default** (frozen `interfaces/chunk-10.md:47`)
  or `cli.py`. The selected mode is carried from the preflight summary instead (§5.7).
- **`models.py`, `database.py`, `report.py`, `cli.py`, `metrics.py`, `scoring.py`,
  `sampling.py`, `validation.py`, `collector.py`, `collector_coveo.py`, `config.py`, tools,
  `pyproject.toml`, `config/**`.** No change.
- **A new interface file.** None.
- **Live network in development or tests.** No test calls the endpoint; agents never run
  `niche-scout run`.
- **`tests/AGENTS.md` prose.** Separate docs item.

## 3. Requirements

Chunk 18 has no `requirements-dependency-map.md` §3 section; the LREQs are taken from
`SRS-lean.md` at the cited lines.

| LREQ ID | Role here | Normative text (quoted/derived) | SRS |
|---|---|---|---|
| LREQ-GQL-030 | **Primary** | "… the implementation MAY use response position only after the identity preflight validates the fixed two-operation ordering and expected operation-specific response shapes across the selected preflight identities. The persisted correlation mode SHALL be either `explicit_key` or `validated_position`. If neither mode is validated, both operations SHALL be marked malformed and their fields SHALL remain unavailable." | §4.2, 300-312 |
| LREQ-ID-020 | **Primary** | "The preflight SHALL perform the normal GraphQL request and verify: … the operation-correlation mode is valid; and no unexplained response-shape or operation-association error occurred." | §4.4, 368-372 |
| LREQ-ID-040 | Integration completion (6A primary) | "Successful preflight responses SHALL be reused as the corresponding enrichment observations and SHALL count toward the one-enrichment-per-unique-identity limit"; the summary includes the selected `graphql_operation_correlation_mode`. | §4.4, 386-414 |
| LREQ-GQL-080 | Integration completion (6B primary) | "A unique sampled identity SHALL be enriched at most once per run." Selection and the second-pass interpretation add no request. | §4.2, 336-338 |
| LREQ-GQL-040 | Supporting (Chunk 5 primary) | "… null required data, wrong data shape, wrong scalar type … SHALL be recorded as an operation error." H5/G7 keep the existing vocabulary; zero page views stays valid. | §4.2, 318-323 |
| LREQ-GQL-020 | Supporting | The `ProductDetail` field set and the `ProductPageViews` scalar; G7 aliases the scalar field. | §4.2, 294-298 |
| LREQ-GQL-010 | Supporting | Two operations, same `asset_identity_key`; unchanged. | §4.2, 289-292 |
| LREQ-SEC-010/020 | Constraint | No secret in any artifact; no response body persisted; no cookie/header value in diagnostics. | §4.3, 348-352 |
| LREQ-ARCH-030 | Supporting | Same inputs + policy + config → same outputs; selection is a pure function of ordered evidence. | §3 |

Not claimed: the `LREQ-ID-020` caveat that the preflight is "not a statistically representative
validation of all marketplace identity forms" (line 374) is unchanged.

## 4. Frozen-interface changes and conflict note

The rulings authorize these changes to frozen surfaces. The interface files are **not** edited;
the conflict is recorded here and in `Documents/runs/chunk-18.md` (§12.1).

1. **`interfaces/chunk-05.md:770-776`** — `execute_graphql_batch` gains
   `correlation_mode: GraphQLOperationCorrelationMode = GraphQLOperationCorrelationMode.EXPLICIT_KEY`.
   A.1b (H1).
2. **`interfaces/chunk-05.md:398-416`** — Chunk 5 "MUST NOT … validate position under
   `VALIDATED_POSITION`; position validation is the identity preflight's job". The new
   primitive *validates the endpoint guarantee* (fixed ordering + shapes) and hands the
   preflight a decision; it does not re-implement the preflight's identity checks. Recorded as
   a boundary clarification (A.2b).
3. **`interfaces/chunk-05.md:294`** — `payload` is "the operation's own `data` mapping/scalar,
   verbatim". H5 makes the ProductDetail payload the **unwrapped `data.product`** object (H5).
4. **`plans/chunk-6A-...md:90-92, :794-796`** — "`pipeline.py` MUST NOT re-implement GraphQL
   request construction, correlation, response validation, or retry classification." This plan
   keeps that: `pipeline.py` calls Chunk 5 `enrich_asset`, the new Chunk 5 primitive, and the
   new Chunk 5 interpreter; it re-implements none of them.
5. **`interfaces/chunk-6A.md:185-294`** — `PreflightObservation.correlation_mode` and
   `IdentityPreflightSummary.graphql_operation_correlation_mode` now carry the **selected**
   (evidence-derived) mode; `run_identity_preflight`'s `correlation_mode` argument is the
   candidate for the first execution pass. Same types, changed value provenance.

## 5. Design

### 5.1 S1 (A.1b) — the caller's mode reaches correlation

- Add `correlation_mode` to `execute_graphql_batch` (keyword-only, default `EXPLICIT_KEY`).
  The value is validated by `_require_correlation_mode` and threaded to
  `_interrogate_response` → `correlate_operations`, and to the `TRANSPORT_FAILURE` branch
  (today `:2446` hardcodes `EXPLICIT_KEY`).
- `enrich_asset` passes `mode` into `execute_graphql_batch` and the relabel block
  (`:2557-2563`) is deleted. Delete `_correlation_mode_for_request` (`:2477-2486`).
- `_build_pre_exchange_result` and `_with_both_operations_failed` already accept the mode;
  no hardcoded `EXPLICIT_KEY` remains on the result path.

### 5.2 New public Chunk 5 primitive — `select_operation_correlation_mode`

In the interface-doc style:

```python
def select_operation_correlation_mode(
    responses: Sequence[GraphQLBatchResponse],
) -> GraphQLOperationCorrelationMode:
    """Select the run-level persisted correlation mode from already-received responses.

    ``responses`` is the ordered per-identity batch response for the selected preflight
    identities, one per unique identity, in selection order. It is evidence only: this
    function issues no request and reads no clock. Pure and deterministic; the result is a
    function of the ordered evidence alone.

    Raises ``ValueError`` for an empty sequence: a zero-identity preflight is
    ``insufficient`` (LREQ-ID-040) and selection is not reached; the caller must not
    substitute a default.

    Returns ``VALIDATED_POSITION`` iff every response decodes to exactly two items, no item
    carries an explicit correlation key (``extract_operation_correlation_key(item) is None``
    for both), item 0 presents the ``ProductDetail`` operation-specific shape, and item 1
    presents the ``ProductPageViews`` operation-specific shape (LREQ-GQL-030). Otherwise
    returns ``EXPLICIT_KEY`` — including when any response carries an explicit key (the
    primary association is available) and when any identity fails shape, count, or decode.
    Selection is all-or-nothing across the selected identities ("across the selected
    preflight identities").
    """
```

Semantics, exhaustively:

- **Decode.** Each response is decoded with the adapter's existing decoder. A response that
  is empty, non-JSON, or not a JSON array → not validated → `EXPLICIT_KEY`.
- **Explicit key present on any item of any response** → `EXPLICIT_KEY`. The primary
  `LREQ-GQL-030` association is the explicit key; position is only the no-key fallback. A
  mixed run (some keyed, some keyless) is `EXPLICIT_KEY`.
- **All keyless.** For every response, require:
  - exactly two items;
  - item 0 = the `ProductDetail` shape: its envelope `data` is a mapping whose root field
    `product` is a mapping that `validate_product_detail_payload` accepts (the H5 unwrap,
    §5.5);
  - item 1 = the `ProductPageViews` shape: its envelope `data` is a mapping
    `{"pageViews": <int >= 0>}` that `validate_page_views_payload` accepts (§5.6).
  All hold → `VALIDATED_POSITION`; any failure → `EXPLICIT_KEY`.
- **Determinism.** No RNG, no clock, no set/dict-ordering dependence.
- **"Neither mode validated".** Returning `EXPLICIT_KEY` for a keyless run means the
  `EXPLICIT_KEY` path marks both operations `OPERATION_CORRELATION_MISSING` (malformed, fields
  unavailable), per `LREQ-GQL-030`. The preflight then fails on the existing gate.

A module-private `_product_detail_root_payload(item)` implements the H5 unwrap and is shared by
this primitive and `_build_result_from_items` (§5.5).

### 5.3 New public Chunk 5 interpreter — `interpret_graphql_response`

The selection is computed after the requests are received; a keyless run received under the
`EXPLICIT_KEY` candidate is a failure and must be re-associated under the selected
`VALIDATED_POSITION` **without a second request**. Chunk 6A forbids a second `enrich_asset`
call per identity (`plans/chunk-6A-...md:801-802`), so the re-interpretation is a pure Chunk 5
function over the already-received response.

```python
def interpret_graphql_response(
    request: GraphQLBatchRequest,
    response: GraphQLBatchResponse,
    *,
    correlation_mode: GraphQLOperationCorrelationMode,
    retrieved_at_utc: datetime,
    attempts: int = 1,
) -> tuple[EnrichmentResult, EnrichmentObservationDraft]:
    """Interpret one already-received response under ``correlation_mode``.

    The public face of the adapter's response interpretation: it correlates and validates
    the given response under ``correlation_mode``, applies the non-200 classification, and
    returns the same ``(result, draft)`` pair ``enrich_asset`` returns. It performs no
    network exchange and reads no clock; ``attempts`` and ``retrieved_at_utc`` are supplied
    by the caller. ``retrieved_at_utc`` must be timezone-aware UTC (``models.ensure_utc``).
    """
```

`enrich_asset`'s tail (field extraction + `build_enrichment_observation_draft`) is factored
into a private helper used by both, so the two paths cannot drift.

### 5.4 Preflight selection, reuse, and persistence (A.2b)

`run_identity_preflight` becomes:

1. `selection = select_preflight_identities(run, policy=policy)`.
2. For each unique identity in selection order, call `enrich_asset` **exactly once** under the
   caller's candidate `correlation_mode`, capturing the request and the received response (the
   existing transport wrapper already receives both; it stashes them). Collect
   `(identity, result, draft, request, response)` and the ordered `responses`.
3. `selected = select_operation_correlation_mode(tuple(responses))` — only when
   `selection.identities` is non-empty; zero identities stays `insufficient` and persists the
   candidate mode (rates `null` carry the distinction; no value is fabricated).
4. For each identity, if `selected is not correlation_mode` (the candidate), rebuild the
   result/draft via `interpret_graphql_response(request, response,
   correlation_mode=selected, retrieved_at_utc=retrieved_at_utc, attempts=result.attempts)`.
   Otherwise reuse the first-pass result/draft. Re-interpretation makes **no** request.
5. `_build_observation(result, draft, correlation_mode=selected)` for each identity.
6. `_build_summary(..., correlation_mode=selected, ...)`; `persist_preflight` writes the
   summary (and `update_run_preflight` writes the selected mode onto the run row).

**Run-level vs per-identity.** `LREQ-GQL-030` requires validation "across the selected
preflight identities" and a single persisted mode, so selection is all-or-nothing at run
level: one identity's failure to present the guarantee selects `EXPLICIT_KEY` for the whole
run. No per-identity mode is invented.

**No second request.** One `enrich_asset` per unique identity (`LREQ-GQL-080`,
`LREQ-ID-040`); the second pass is in-memory. Reused identities are not re-requested.

### 5.5 H5 — unwrap `data.product` (before/after)

`_build_result_from_items` (`:2144-2167`) currently:

```python
if _is_operation_envelope(item):
    operation_data, _ = _operation_data(item)
    ...
    payload = operation_data          # == {"product": {...}}
...
validation = validate_product_detail_payload(payload)   # fails: no id/productId at top level
```

After (shared helper `_product_detail_root_payload(item)`):

```python
payload = _product_detail_root_payload(item)
# root field present -> unwrap data.product; absent -> legacy flat data (unchanged)
```

Rules, with `LREQ-GQL-040` classes and missing-not-zero:

| Input (`item`) | Behavior | `failure_class` |
|---|---|---|
| `{"data":{"product": {<fields>}}}` | unwrap; validate the product object | `NONE` (success) |
| `{"data":{"product": null}}` | no product data returned | `NULL_REQUIRED_DATA` |
| `{"data":{"product": [..]}}` (non-mapping) | wrong container kind | `WRONG_DATA_SHAPE` |
| `{"data": null}` | existing envelope-null branch | `NULL_REQUIRED_DATA` |
| `{"data": {<flat fields>}}` (no `product` key) | legacy payload, validated as today | unchanged |
| `{"data": {}}` (no `product`, no fields) | legacy path → missing required members | `NULL_REQUIRED_DATA` / `WRONG_DATA_SHAPE` per the existing validator |

No field is defaulted or coerced; a failed operation's fields stay `None`. The conditional
unwrap is required to keep the frozen keyed fixtures (flat `data`) green and the frozen
`:294` "verbatim" contract usable; the live endpoint always supplies `product` (10/10).

### 5.6 G7 — alias the page-views request field

`_PRODUCT_PAGE_VIEWS_QUERY` (`:338-342`) becomes:

```graphql
query ProductPageViews($packageId: String!) {
  pageViews: productPageViews(packageId: $packageId)
}
```

Then the live response is `{"data":{"pageViews": N}}`, which the frozen
`validate_page_views_payload` accepts unchanged. `0` is valid and is never absent
(`LREQ-GQL-040`, `:495-498`). The corresponding golden request objects change (only the query
string); keyed response fixtures already use `{"pageViews": ...}` and are unaffected.

### 5.7 Carrying the selected mode into enrichment and `run_pipeline`

After `preflight_outcome`, `run_pipeline` derives
`selected = GraphQLOperationCorrelationMode(preflight_outcome.summary.graphql_operation_correlation_mode)`
and passes `correlation_mode=selected` to `enrich_unique_identities` (replacing the
caller-supplied candidate). The run row already receives the selected mode from
`persist_preflight` → `update_run_preflight`. `run_pipeline`'s signature and default are
unchanged (frozen `interfaces/chunk-10.md:47`). The candidate reaches the preflight as today
via `correlation_mode=correlation_mode`.

## 6. Files touched

No file outside this table is touched.

| File | New/modified | Purpose |
|---|---|---|
| `src/niche_scout/collector_graphql.py` | modified | A.1b (`execute_graphql_batch` keyword, `enrich_asset` pass-through, delete relabel + `_correlation_mode_for_request`); new public `select_operation_correlation_mode`; new public `interpret_graphql_response`; H5 `_product_detail_root_payload` unwrap; G7 query alias; `__all__` additions. |
| `src/niche_scout/pipeline.py` | modified | Capture request/response in the preflight adapter path; call the primitive; second-pass re-interpretation; persist selected mode; carry selected mode into `enrich_unique_identities`. |
| `tests/fixtures/graphql_fixtures.py` | modified | Keyless two-envelope fixtures (success, zero, malformed variants); update `EXPECTED_PRODUCT_PAGE_VIEWS_REQUEST_OBJECT` / `TWO_OPERATION_BODY_JSON` for the G7 alias. |
| `tests/fixtures/identity_preflight_vectors.py` | modified | Keyless preflight transport/body helpers for the new preflight nodes. |
| `tests/test_collector.py` | modified | One approved rename; new adapter-level nodes (§8). |
| `tests/test_identity_preflight.py` | modified | New selection/reuse/persistence nodes (§8). |
| `tests/traceability.json` | modified | Migrated rename key + new node entries. |

**Not touched:** `models.py`, `database.py`, `report.py`, `cli.py`, `config.py`, `sampling.py`,
`validation.py`, `collector.py`, `collector_coveo.py`, `metrics.py`, `scoring.py`,
`src/niche_scout/tools/**`, `pyproject.toml`, `config/**`, `Documents/**` (this plan excepted),
`AGENTS.md`, `kilo.json(c)`, `.kilo/`.

## 7. Typed signatures and null/edge behavior

### 7.1 `execute_graphql_batch` (changed)

```python
def execute_graphql_batch(
    request: GraphQLBatchRequest, *,
    transport: GraphQLTransport,
    headers: Mapping[str, str],
    correlation_mode: GraphQLOperationCorrelationMode = GraphQLOperationCorrelationMode.EXPLICIT_KEY,
    policy: GraphQLRetryPolicy = GraphQLRetryPolicy(),
    sleep: Callable[[float], None] = time.sleep,
) -> EnrichmentResult
```

- A non-member `correlation_mode` raises `TypeError` (`_require_correlation_mode`).
- The passed mode is the mode each operation and `correlation.mode` report; there is no
  post-hoc stamping.
- Omitting the keyword reproduces the previous explicit-key behavior exactly.

### 7.2 `select_operation_correlation_mode` (new)

Signature in §5.2. Null/edge: empty sequence → `ValueError`; decode failure / wrong count /
explicit key / wrong shape → `EXPLICIT_KEY`; the valid keyless fixed-order shape →
`VALIDATED_POSITION`.

### 7.3 `interpret_graphql_response` (new)

Signature in §5.3. Null/edge: a naive `retrieved_at_utc` raises `ValueError`
(`models.ensure_utc`); `attempts < 1` raises `ValueError`; a non-member `correlation_mode`
raises `TypeError`; a non-200 response takes the existing HTTP classification.

### 7.4 ProductDetail unwrap (§5.5 table) and page-views (§5.6)

No default-0, no coercion; failed fields `None`; `pageViews == 0` valid.

## 8. Test plan

No live network; every transport is a recording double. Fixtures and golden vectors first
(`test-author`), then the implementation.

### 8.1 Node IDs, markers, traceability

`tests/traceability.json` is node-ID → `[LREQ...]` (G9); markers must equal the values.

| pytest node ID | `@pytest.mark.lreq` | `tests/traceability.json` value |
|---|---|---|
| `tests/test_collector.py::test_execute_graphql_batch_honours_caller_correlation_mode` | `LREQ-GQL-030` | `["LREQ-GQL-030"]` |
| `tests/test_collector.py::test_validated_position_mode_correlates_by_position_when_requested` (renamed, §8.3) | `LREQ-GQL-030` | `["LREQ-GQL-030"]` |
| `tests/test_collector.py::test_explicit_key_mode_marks_keyless_body_correlation_missing` | `LREQ-GQL-030` | `["LREQ-GQL-030"]` |
| `tests/test_collector.py::test_product_detail_data_product_wrapper_is_unwrapped` | `LREQ-GQL-040` | `["LREQ-GQL-040"]` |
| `tests/test_collector.py::test_product_page_views_request_alias_is_page_views` | `LREQ-GQL-020` | `["LREQ-GQL-020"]` |
| `tests/test_collector.py::test_keyless_page_views_zero_is_a_valid_value` | `LREQ-GQL-040` | `["LREQ-GQL-040"]` |
| `tests/test_collector.py::test_keyless_page_views_wrong_key_is_null_required_data` | `LREQ-GQL-040` | `["LREQ-GQL-040"]` |
| `tests/test_collector.py::test_select_operation_correlation_mode_rejects_empty_evidence` | `LREQ-GQL-030` | `["LREQ-GQL-030"]` |
| `tests/test_identity_preflight.py::test_preflight_selects_validated_position_for_keyless_bodies` | `LREQ-GQL-030`, `LREQ-ID-020` | `["LREQ-GQL-030", "LREQ-ID-020"]` |
| `tests/test_identity_preflight.py::test_preflight_selects_explicit_key_when_any_identity_is_keyed` | `LREQ-GQL-030`, `LREQ-ID-020` | `["LREQ-GQL-030", "LREQ-ID-020"]` |
| `tests/test_identity_preflight.py::test_preflight_rejects_position_when_ordering_is_wrong` | `LREQ-GQL-030`, `LREQ-ID-020` | `["LREQ-GQL-030", "LREQ-ID-020"]` |
| `tests/test_identity_preflight.py::test_preflight_selected_mode_is_persisted_and_reused_without_a_second_request` | `LREQ-ID-040`, `LREQ-GQL-080` | `["LREQ-ID-040", "LREQ-GQL-080"]` |

Assertions (test-author writes these without the implementation):

- **honours caller mode:** `execute_graphql_batch(..., correlation_mode=VALIDATED_POSITION)`
  over a keyless two-envelope body → both operations `SUCCESS`,
  `correlation.mode is VALIDATED_POSITION`; with the keyword omitted →
  `correlation.mode is EXPLICIT_KEY`.
- **validated position correlates:** item0 → `ProductDetail`, item1 → `ProductPageViews`;
  `is_fully_correlated is True`; a keyed or one-item body → both
  `OPERATION_CORRELATION_AMBIGUOUS`.
- **explicit-key keyless:** `EXPLICIT_KEY` over a keyless body → both
  `OPERATION_CORRELATION_MISSING`, `correlation.mode is EXPLICIT_KEY`.
- **H5 unwrap:** `data.product` mapping → success with `product_id`/`graphql_id` populated;
  `product: null` → `NULL_REQUIRED_DATA`; `product: [..]` → `WRONG_DATA_SHAPE`; `data: null` →
  `NULL_REQUIRED_DATA`; flat `data` → unchanged success.
- **G7 alias:** the built request's `ProductPageViews` query is exactly
  `query ProductPageViews($packageId: String!) {\n  pageViews: productPageViews(packageId: $packageId)\n}`
  and `body_json` equals the updated golden.
- **zero:** `{"data":{"pageViews":0}}` under `VALIDATED_POSITION` → success,
  `product_page_views == 0` (not `None`).
- **wrong key:** `{"data":{"productPageViews":20}}` → `NULL_REQUIRED_DATA` (corrects the DRAFT).
- **empty evidence:** `select_operation_correlation_mode(())` raises `ValueError`.
- **preflight keyless:** keyless transport → summary
  `graphql_operation_correlation_mode == "validated_position"`, every observation
  `correlation_mode == "validated_position"`, both operation statuses `success`, preflight
  `passed`.
- **preflight keyed/mixed:** keyed or mixed transport → `"explicit_key"`.
- **preflight wrong ordering:** keyless bodies with reversed shapes → selected
  `"explicit_key"`, preflight `failed`, both operations malformed.
- **persisted/reused:** `transport.call_count == number of unique selected identities` (no
  extra call for the second pass); the persisted run row and summary carry the selected mode.

### 8.2 Fixtures and golden vectors

- Keyless two-envelope success (hand-computed):
  `[{"data":{"product":{"id":"117382","productId":"117382","rating":{"average":4.5,"count":12},"reviewCount":7,"firstPublishedDate":"2019-03-04T12:30:00Z","state":"published","category":{"id":"c1","name":"Tools"},"publisher":{"id":"p1","name":"Pub"}}}},{"data":{"pageViews":20}}]`
  → ProductDetail success; `product_page_views == 20`; `rating_average == 4.5`,
  `rating_count == 12`, `review_count == 7` (assert floats within `1e-9`).
- Keyless page-views zero: `[{"data":{"product":{…}}},{"data":{"pageViews":0}}]` →
  `product_page_views == 0`.
- Captured pre-G7 page-views shape (documents H3): `{"data":{"productPageViews":20}}` →
  `NULL_REQUIRED_DATA` (asserts the DRAFT correction).
- Keyless malformed variants: reversed shapes, one-item, three-item, `product: null`,
  `product: [..]`, `pageViews: -1`, `pageViews: true`, `pageViews: 1.5`, missing `pageViews`.
- G7 request goldens updated in `graphql_fixtures.py`.
- Keyless preflight transport helper in `identity_preflight_vectors.py`.

### 8.3 The one approved rename

- Old: `tests/test_collector.py::test_validated_position_mode_is_accepted_not_validated_here`
- New: `tests/test_collector.py::test_validated_position_mode_correlates_by_position_when_requested`
- Traceability: remove the old key, add the new key with the same value `["LREQ-GQL-030"]`.
- The old name and its assertions ("execution still defaults to the explicit-key mode", "the
  caller's mode is stamped") contradict the frozen design and are replaced.

### 8.4 Conflicting pins from the run log, and reconciliation

| Pin | Reconciliation |
|---|---|
| **P1** `tests/test_collector.py:2057-2117` `test_validated_position_mode_is_accepted_not_validated_here` asserts execution defaults to explicit-key and the caller's mode is merely stamped, and `result.correlation.mode is EXPLICIT_KEY` | Renamed and rewritten (§8.3). New assertions: the caller's `VALIDATED_POSITION` actually drives correlation; omission still defaults to `EXPLICIT_KEY`. |
| **P2** `tests/fixtures/graphql_fixtures.py` — all fixture bodies carry `operationName`; no keyless-success fixture (G9: 46 matches) | Add the keyless fixtures (§8.2); existing keyed fixtures stay (they exercise `explicit_key`). |
| **P3** `tests/test_identity_preflight.py:65, 623, 810, 1044` pin `correlation_mode=pf.EXPLICIT_KEY` and `explicit_key` | Unchanged: those nodes use keyed fixture bodies and the explicit-key candidate, so selection returns `explicit_key`. New keyless nodes assert `validated_position`. |
| DRAFT `:91, :164` page-views failure class `WRONG_DATA_SHAPE` | Corrected to `NULL_REQUIRED_DATA` (G7). |
| DRAFT `:97` "slightly different query text" | Removed; the capture used the committed query text. |
| DRAFT `:376, :460` locants | Corrected to `interfaces/chunk-6A.md` and `tests/fixtures/identity_preflight_vectors.py`. |

## 9. Definition of done (gate)

- **DoD-1 (dispatch; human live run).** A human `python -m niche_scout run` reaches and
  **passes** the identity preflight against the live endpoint; the persisted summary and run
  row show `validated_position`; the minimum consequential changes. Not provable offline.
- **DoD-2 (offline suite).** `python -m pytest -q` reports `passed, 0 failed`; the exact
  command and verbatim output are recorded in the run log with real counts.
- **DoD-3 (validators).** `python -m niche_scout.tools.validate_traceability`,
  `python -m niche_scout.tools.check_import_boundaries`,
  `python -m niche_scout.tools.check_scope_prohibitions`, and
  `python -m niche_scout.tools.check_secrets` all valid.
- **DoD-4 (lint).** `ruff` on the changed files with `pyproject.toml` (`line-length = 88`,
  `select = ["E","F","I"]`); no new lint; a pre-existing deviation is reported PARTIAL with the
  unchanged lines named and a byte-exact baseline.
- **DoD-5 (secrets / no live network in tests).** No credential, cookie, or header value in any
  artifact; no test calls the real endpoint; no response body persisted.
- **DoD-6 (records).** Plan, run log, tests, and traceability recorded; every resolved
  checkpoint recorded in the run log with its ruling; remaining obligations stay open.

## 10. Prohibitions

- No relabel of a hard-coded explicit-key failure as `validated_position`; no positional
  association without the preflight's ordering/shape validation; no fabricated key; no third
  mode; no new `GraphQLFailureClass`.
- No marking an `LREQ-GQL-030` malformed branch as success; wrong shape/count/kind stays an
  operation error.
- No extra request per unique identity; one `enrich_asset` per identity; the second pass is
  in-memory only.
- No live network in development or tests.
- No new config knob, CLI flag, env var, persisted field, or dependency.
- No edits outside §6, including any frozen interface, plan, or run document.

## 11. Routing

1. **`test-author`** — fixtures and failing nodes + `tests/traceability.json` entries first.
2. **`impl-deep`** — adapter (A.1b, H5, G7, new primitives) then preflight selection
   (`pipeline.py`); run pytest and the four validators. `impl-fast` is not suitable: the change
   spans a frozen protocol boundary and the preflight gate.
3. **Human live run** — DoD-1.
4. **`spec-reviewer`** — review the plan, tests, implementation, and the live-run evidence in
   `Documents/runs/chunk-18.md`.

## 12. Conflict notes and open obligations

### 12.1 Frozen-interface conflict notes (recorded; interfaces NOT edited)

- `interfaces/chunk-05.md:398-416` — "Chunk 5 MUST NOT … validate position … position
  validation is the identity preflight's job". Resolved by A.2b: the new primitive validates
  the endpoint guarantee and returns a decision; the preflight's identity checks stay in
  `pipeline.py`.
- `plans/chunk-6A-...md:90-92, :794-796` — "`pipeline.py` MUST NOT re-implement GraphQL
  request construction, correlation, response validation, or retry classification". Honored:
  `pipeline.py` calls Chunk 5 `enrich_asset`, the new primitive, and the new interpreter.
- `interfaces/chunk-05.md:770-776` — `execute_graphql_batch` signature change (A.1b).
- `interfaces/chunk-05.md:294` — ProductDetail payload becomes the unwrapped `data.product`
  (H5).
- `interfaces/chunk-6A.md:185-294` — the persisted correlation mode is evidence-derived; the
  `correlation_mode` argument is the first-pass candidate (H1/A.2b).
- `interfaces/chunk-10.md:47` — default unchanged; the selected mode is carried from the
  preflight summary into `enrich_unique_identities`.

### 12.2 Open obligations (recorded, never closed here)

- **URI trailing-identifier extraction (`identity_mapping_rule 1.0.1`)** — inferred, not
  verified against a real Coveo response; no captured response exists.
- **OI-6 — CSRF/session sufficiency** — has no owning chunk; neither reopened nor closed.
- **`runs.taxonomy_sha256` empty-hash rejection** — owner Chunk 10; not touched.
- **`tests/AGENTS.md` traceability orientation** — prose says LREQ-keyed; the committed file
  is node-ID-keyed (G9). Out of scope; follow the committed file.

### 12.3 Residual UNVERIFIED (not a blocker)

- Identity agreement (`id`/`productId` vs the requested canonical identity) was not
  independently confirmed in the H3 capture; the DoD-1 live run verifies it.
- Whether the endpoint emits keys for non-selected identities is not observed; the selection
  is defined for both branches (keyed → `EXPLICIT_KEY`).
