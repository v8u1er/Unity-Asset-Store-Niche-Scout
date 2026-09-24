# Chunk 18 — run log (GraphQL correlation-mode selection remediation, post-Chunk-17)

Post-completion remediation requested by the human after a live `python -m niche_scout run`
(`run-2026-09-24T09:49:22.649368+00:00`, counted in `runtime/niche_scout.sqlite3`) reached the
identity preflight, got HTTP 200, and **failed** with
`failure_classes=["operation_correlation_missing"]`. Chunk 17 fixed CSRF/query shape; this is a
new, distinct defect. Labeled chunk (same pattern as Chunks 14/15/16/17): no dependency-map §3
gate row; the dispatch DoD is the gate.

Goal (dispatch): determine why correlation fails on a 200 and plan the minimal correct fix; the
DoD is a live `python -m niche_scout run` reaching and **passing** the identity preflight.

Plan: `Documents/plans/chunk-18-*.md` (to be written by `chunk-planner`).

## Preflight

| Check | Result |
|---|---|
| Working tree | clean at start (`git status` → "nothing to commit, working tree clean"; branch `main`; HEAD `dc69c55`) |
| Branch | created `chunk-18-graphql-correlation-mode-selection` off `main` @ `dc69c55` (succeeded) |
| Prerequisite | Chunk 17 `GATE: PASSED` (`runs/chunk-17.md:156`); interface `chunk-05.md`/`chunk-6A.md` `Status: VERIFIED` (per scope). **Citation correction (2026-09-24, after advisory review):** the Chunk 6A interface file is `Documents/interfaces/chunk-6A.md` (not `chunk-06A.md`); the fixture is `tests/fixtures/identity_preflight_vectors.py` (not `identity_preflight_fixtures.py`). The DRAFT plan propagated both wrong locants (`plans/chunk-18-...md:376, 460`) and must correct them at re-freeze. |
| Routing | `chunk-planner` first (dispatch-specified). Implementer/routing TBD by the frozen plan; the change touches adapter protocol + preflight, so tests-first is expected. |

## Grounded recon (labels: read / counted / live / unverified)

### A. Live 200 response body shape

| # | Finding | Evidence |
|---|---|---|
| A1 | A previously captured live 200 batch response for one identity is a JSON array of exactly **two bare envelopes** `[{"data":{"product":{...}}},{"data":{"productPageViews":66}}]` with **no** `operationName`, `operation`, or `correlationKey` at any level shown. Item 0 = `data.product` object (ProductDetail fields); item 1 = `data.productPageViews` scalar. | read `.scratch/graphql_csrf_finding.md:93-97` (capture produced by `.scratch/chunk17-graphql-csrf-probe.py`, 2026-09-24). Not reproduced by the lead (no live network in agent work). |
| A2 | Across the **selected preflight identities** (10 unique identities, 8 categories) the two-operation ordering and the operation-specific shapes are **not** confirmed; no response body is persisted by design (`SEC`: bodies never in SQLite), so this cannot be confirmed from the run DB offline. | read `collector_graphql.py:_decode_operation_items` (body not persisted); counted run summary per dispatch. **UNVERIFIED — requires a human-run live capture across ≥2 identities spanning ≥2 products** (see QUESTIONS). |
| A3 | With no explicit key present, the adapter runs `_correlate_by_explicit_key` and marks **both** operations `OPERATION_CORRELATION_MISSING` — the exact live failure. | read `collector_graphql.py:725-812` (`_correlate_by_explicit_key`), `:898-903` (mode dispatch) |

### B. `operations` request header

| # | Finding | Evidence |
|---|---|---|
| B1 | `GraphQLBatchRequest.operations_header` is built (`",".join(operation_name ...)`) but `build_graphql_headers` never emits an `operations` header; the live-valid corrected request (Chunk 17) has no `operations` header. | read `collector_graphql.py:309, 464-466`; `:395-411` (no `operations`); `.scratch/graphql_csrf_finding.md:70-82` |
| B2 | Adding `operations: ProductDetail,ProductPageViews` and `apollo-require-preflight: true` "changed nothing" — but that probe was **pre-cookie** (still HTTP 400), so whether the endpoint would echo `operationName` on a **successful 200** with an `operations` header is **UNVERIFIED**. | read `.scratch/graphql_csrf_finding.md:20-21`. **UNVERIFIED — requires a live probe** (see QUESTIONS). |

### C. Ownership of correlation-mode validation/selection (frozen-interface conflict)

| # | Finding | Evidence |
|---|---|---|
| C1 | `enrich_asset` accepts a caller `correlation_mode`, but calls `execute_graphql_batch` **without** it and then **post-hoc relabels** the result's mode/operation modes if they differ. A caller-passed `VALIDATED_POSITION` therefore never correlates by position; it only relabels an explicit-key failure. | read `collector_graphql.py:2531-2563` |
| C2 | `_correlation_mode_for_request(request)` **hardcodes** `EXPLICIT_KEY`; this is the only mode the execute path ever runs. | read `collector_graphql.py:2453-2458, 2477-2486` |
| C3 | `_correlate_by_validated_position` exists and is reachable only when a mode is passed into `correlate_operations`; the production execute path never passes it. | read `collector_graphql.py:815-863, 898-903` |
| C4 | The preflight runs in whatever mode the caller passed, with no live mode validation. `run_identity_preflight` loops `_run_adapter(..., correlation_mode=...)` and writes it into the summary; `run_pipeline`'s `correlation_mode` defaults to `EXPLICIT_KEY`; `cli.py` builds `run_kwargs` without `correlation_mode`. No code path selects/validates `VALIDATED_POSITION`. | read `pipeline.py:1100-1131, 3149-3151`; `cli.py:429-443` |
| C5 | The only "mode validation" implemented is a defensive enum-membership check, not the LREQ-GQL-030 ordering/shape validation. | read `pipeline.py:599-608, 661-669` (`_correlation_mode_is_valid`) |
| C6 | **Frozen-interface conflict.** The Chunk 5 interface states position validation is the identity preflight's job (Chunk 6A / LREQ-ID-020) and that under `VALIDATED_POSITION` Chunk 5 "accepts the caller's mode as already-validated" — i.e. Chunk 5 should *honour* the caller's mode. The Chunk 6A plan says "New GraphQL protocol behavior, correlation algorithms" is **Chunk 5's** and "`pipeline.py` MUST NOT re-implement ... correlation". Neither chunk implemented the selection. | read `interfaces/chunk-05.md:398-416, 770-786`; `plans/chunk-6A-...md:90-92, 794-796`; `plans/chunk-6A-...md:112` |
| C7 | The frozen Chunk 5 interface's `execute_graphql_batch` signature has **no** `correlation_mode` parameter (only internal `_correlation_mode_for_request` exists), while `enrich_asset` **does** take one. Honouring the caller mode therefore requires an internal plumbing change (private path) or a frozen-signature change to `execute_graphql_batch`. | read `interfaces/chunk-05.md:770-786`; `collector_graphql.py:2402-2415, 2554-2556` |

### SRS authority

| # | Finding | Evidence |
|---|---|---|
| S1 | `LREQ-GQL-030`: position alone SHALL NOT be trusted unless separately validated as an endpoint guarantee; if the response provides no explicit key, position MAY be used **only after the identity preflight validates the fixed two-operation ordering and expected operation-specific response shapes across the selected preflight identities**. Persisted mode SHALL be `explicit_key` or `validated_position`; if neither validated, both operations marked malformed. | read `SRS-lean.md:300-312` |
| S2 | `LREQ-ID-020`: the preflight SHALL verify "... the operation-correlation mode is valid ...". | read `SRS-lean.md:368-372` |
| S3 | `LREQ-ID-040`: successful preflight responses SHALL be reused as the corresponding enrichment observations and count toward one-enrichment-per-unique-identity; persisted summary includes the selected `graphql_operation_correlation_mode`. | read `SRS-lean.md:386-414` |

### Test pins that will conflict (listed, not renamed)

| # | Pin | Evidence |
|---|---|---|
| P1 | `tests/test_collector.py::test_validated_position_mode_is_accepted_not_validated_here` (LREQ-GQL-030) asserts execution "still defaults to the explicit-key mode" and that the caller's mode is merely stamped; it also asserts `result.correlation.mode is EXPLICIT_KEY`. | read `tests/test_collector.py:2057-2117` |
| P2 | Fixture bodies all carry `operationName`; there is **no keyless-success fixture** for the live `[{data:...},{data:...}]` shape. | read `tests/fixtures/graphql_fixtures.py:202-232, 614-627, 746`; grep (40 matches, all with `operationName`) |
| P3 | `tests/test_identity_preflight.py` pins `observation.correlation_mode == EXPLICIT_KEY.value` and `summary["graphql_operation_correlation_mode"] == "explicit_key"`. | read `tests/test_identity_preflight.py:65, 623, 810, 1044` |

## Confirmed defect (root cause)

On the live endpoint the 200 batch response (A1) carries no explicit correlation key. Production
executes in `EXPLICIT_KEY` (C2/C4), so `_correlate_by_explicit_key` marks both operations
`OPERATION_CORRELATION_MISSING` (A3) and the preflight fails (`attempted=10, successful=0`). The
LREQ-GQL-030 fallback (`VALIDATED_POSITION` after preflight validation of ordering+shapes) is
never selected or exercised (C4/C5/C6), and `enrich_asset`'s caller mode is only relabelled, not
used (C1).

## Human checkpoints surfaced (planner must present, not choose)

1. **Where position validation lives (frozen-interface conflict C6/C7 + Chunk 6A prohibition).**
   Chunk 5 says preflight validates; Chunk 6A says pipeline must not re-implement correlation.
   Any change to `collector_graphql.py` (Chunk 5) or `pipeline.py` preflight (Chunk 6A) is a
   frozen-interface change requiring an explicit conflict call-out and a human checkpoint.
2. **Whether to attempt option B first** (add `operations` header to make `EXPLICIT_KEY` work, if
   the endpoint echoes `operationName`) — cheaper and avoids `VALIDATED_POSITION`, but UNVERIFIED
   (B2) and needs a live probe. Present as an option, not a decision.
3. **A2 capture** — the exact live capture needed to satisfy LREQ-GQL-030's "across the selected
   preflight identities" (see QUESTIONS).

## Stage log

| Stage | Status | Session / evidence |
|---|---|---|
| Preflight (lead) | DONE | table above |
| Recon A/B/C (lead) | DONE | tables above |
| Plan — `chunk-planner` | **BLOCKED (DRAFT)** | `ses_f2d1a1100ffeTQ6TqMtLFj3ywP`. Wrote `Documents/plans/chunk-18-graphql-correlation-mode-selection.md`, `Status: DRAFT`, 594 lines. Confirmed the root cause against source; presented options A (plumbing × placement), B (`operations` header), C (unread key member) without choosing; recorded checkpoints H1–H4. Blocked because H1 (frozen-interface conflict) and H3 (live capture across selected identities) must be answered before the file set/signatures freeze, and H2 decides S1/S2 content. This log not edited by the planner. Awaiting human rulings. |

## Human checkpoints (planner H1–H4; relayed to the human, unresolved)

- **H1 (blocking).** Where the `LREQ-GQL-030` ordering/shape validation lives, and how the caller's
  `correlation_mode` reaches correlation. Frozen-interface conflict: `interfaces/chunk-05.md:407-416`
  ("Chunk 5 must not validate position; it is the identity preflight's job", and under
  `VALIDATED_POSITION` Chunk 5 accepts the caller's mode) vs `plans/chunk-6A-...md:90-92, :794-796`
  ("pipeline.py MUST NOT re-implement ... correlation"). Every option touches a frozen surface.
- **H2 (blocking for S1/S2 content).** Probe option (B) first — send the already-built
  `operations_header` and rely on `EXPLICIT_KEY` if the endpoint echoes `operationName`? UNVERIFIED
  (only probe was pre-cookie HTTP 400: `.scratch/graphql_csrf_finding.md:20-21`).
- **H3 (blocking for S2 shape).** Live capture (human-run) across ≥2 selected preflight identities
  spanning ≥2 products, with the committed query text: status, full body, any explicit key, item
  order, and the page-views item's exact shape.
- **H4 (design guard).** If the chosen design needs an extra live request to compute the mode, that
  collides with one-request-per-unique-identity (LREQ-GQL-080/LREQ-ID-040).

## Advisory review (spec-reviewer, 2026-09-24; session `ses_f2cf2c439ffeVs7Wi9vvWP3EZp`)

Read-only advisory requested by the human ("recommend the best answers ... so I can decide easier";
human prefers test/probe-first when unsure). The reviewer did **not** run a probe and did not edit
any file. Its pytest/traceability/ruff counts are **reviewer-reported**, not lead-verified.

### CRITICAL new finding — H5/G11: a third live-contract defect (ProductDetail `data.product` wrapper)

| # | Finding | Evidence |
|---|---|---|
| H5 | The live 200 `ProductDetail` item is `{"data":{"product":{...fields...}}}` (root field `product(id: $id)`), so the adapter's `payload = item["data"]` is `{"product":{...}}`. `validate_product_detail_payload` requires `id`/`productId`/… at the payload's top level and there is **no code that unwraps a `product` container** — so once correlation is fixed, ProductDetail fails for every identity and the preflight success rate stays 0: **the DoD cannot pass with S1+S2 alone.** | read `.scratch/graphql_csrf_finding.md:88-89, 96`; read `collector_graphql.py:941-949, 2144-2167, 1081-1121`; grep `"product"`/`get("product")` in `collector_graphql.py` → no match (no unwrap); read `tests/fixtures/graphql_fixtures.py:320-345, 600-616` (fixtures model `data` as flat product fields). **Lead independently re-verified the read chain; the executed probe was denied (shell), so the live shape across identities stays UNVERIFIED (H3).** |
| H5b | Consequence: H5 is a new blocking decision not in the planner's H1–H4 — unwrap `data.product` in the adapter (frozen `interfaces/chunk-05.md:294` "the operation's own `data` mapping/scalar, verbatim") or change the committed query/fixtures. |

### Reviewer recommendations (for the human to decide)

| Item | Recommendation | Confidence |
|---|---|---|
| H1 | **A.1b + A.2b**: add `correlation_mode` to the frozen `execute_graphql_batch` signature, pass it from `enrich_asset`, delete the relabel (`:2554-2563`); put the ordering/shape check in a **new public Chunk 5 primitive the preflight calls and persists** (`interfaces/chunk-05.md:407-416` vs `plans/chunk-6A-...md:90-92, :794-796`). Record the conflict note; **one node rename** (`test_collector.py::test_validated_position_mode_is_accepted_not_validated_here`); routing `test-author` first, then `impl-deep`. | med-high |
| H2 | **Probe (B) first**, in the same human-run session as H3's capture: one request, uses the primary explicit-key association. If the endpoint echoes `operationName`, the `VALIDATED_POSITION` fallback may be unnecessary. It does **not** remove the H5 payload defects. | med-high on sequencing; low that B succeeds |
| H3 | Run the capture as specified **plus** the ProductDetail outer key (`product`) and nesting; ≥2 identities spanning ≥2 products; record byte-exact query text. Never generalize if fewer are captured. | high that required; low on uniformity |
| H4 | Keep as a **guard only** — the mode is computed from already-executed preflight rows (`pipeline.py:1103-1120, 1487-1514`), so no design needs an extra request. | high |
| G7 | **Fix the request, not validation**: alias the page-views field to `pageViews` (the committed query selects `productPageViews`, while `validate_page_views_payload` requires `{"pageViews": ...}`). A bare `{"productPageViews":…}` payload yields **`NULL_REQUIRED_DATA`, not `WRONG_DATA_SHAPE`** — the DRAFT plan's `:91, :164` mis-state this and must be corrected (H5b-adjacent). | med (pending H3) |
| Traceability | Follow the committed **node-ID → LREQ** mapping; do not restructure. The `tests/AGENTS.md` prose says otherwise — a separate human-approved docs cleanup, not this chunk. | — |

### Plan defects to correct at re-freeze (DRAFT, not edited by the lead)

- `plans/chunk-18-...md:91, 164` — page-views failure class is `NULL_REQUIRED_DATA` for the captured
  envelope, not `WRONG_DATA_SHAPE`.
- `plans/chunk-18-...md:97` — the "capture used a slightly different query text" claim is unsupported:
  the reviewer's read-compare of `.scratch:88-89` vs `collector_graphql.py:314-342` shows identical
  text (byte-exactness unverified).
- `plans/chunk-18-...md:376, 460` — wrong locants: `interfaces/chunk-6A.md`, `tests/fixtures/identity_preflight_vectors.py`.
- Add H5/G11 (above) and the null-vs-wrong-shape correction; re-freeze only after the human rules on
  H1–H5.

## Human rulings (2026-09-24) — approved

The human approved the advisory recommendations in full: **H1 = A.1b + A.2b**, **H2 = probe first**,
**H3 = capture**, **H4 = guard only**, **H5 = unwrap `data.product` in the adapter**,
**G7 = alias the query field to `pageViews`**, **traceability = follow the committed node-ID→LREQ
mapping**, and "test/probe first when unsure". The plan will be revised and re-frozen by
`chunk-planner` after the live capture lands.

### Counted evidence added (from the failed-run DB, read via `.scratch/diag_run0949.py`)

- **All ten** selected preflight identities are keyless in the tool's own records:
  `correlation_keys` = `{"ProductDetail": null, "ProductPageViews": null}` and
  `additional_correlation_keys` = `{"ProductDetail": [], "ProductPageViews": []}` for each of
  `117382, 119971, 307191, 341506, 373708, 373872, 400474, 405518, 44625, 59028`. This is **counted**
  from `enrichment_observations.request_metadata_json` for
  `run-2026-09-24T09:49:22.649368+00:00` (10 rows; unit = rows). It confirms no explicit key on any
  selected identity; item order and per-operation shapes remain UNVERIFIED (H3).
- The run also persisted a distinct `response_sha256` per identity (10 distinct hashes); those values
  are embedded in the capture probe below so the human's capture can be proven byte-identical to the
  response the tool received.

### Live capture request (human-run; agent must not run credential-bearing network)

- Probe script: `.scratch/chunk18-live-capture.py` (syntactically validated with `python -m
  py_compile`; request body verified to match the committed shape via an offline import — output is
  the exact `json.dumps(..., sort_keys=True, separators=(",", ":"))` the adapter builds).
  - It harvests `_csrf` from the storefront GET, then POSTs the committed two-operation body for each
    of the ten identities (no `operations` header), prints the HTTP status, the body, and the sha256
    vs the recorded value, then repeats identity `117382` **with** `operations` +
    `apollo-require-preflight` to test option (B). It never prints the `_csrf` value.
  - Run: `$env:PYTHONPATH = "src"; python .scratch/chunk18-live-capture.py` (no PYTHONPATH needed; the
    script imports only the stdlib).
  - Capture file: `.scratch/chunk18-capture.json`.
- Equivalent raw curl and the exact fields the human must return are given in the lead's reply.

## Live capture — identity 117382 (human-run, 2026-09-24 11:40:25Z) — VERIFIED

The human pasted one full HTTP 200 response. The lead verified it byte-exactly:

| Check | Result |
|---|---|
| `Content-Length` header | `299` |
| Bytes hashed (`sha256` of the pasted body, computed offline with `python`) | `299` bytes |
| Computed sha256 | `319d7a1dc45e84ad7aff6c80848fe68628d0dab0de78b5e0bfd022bc69dd2a2c` |
| Recorded `response_sha256` for `117382` (from the failed-run DB) | `319d7a1dc45e84ad7aff6c80848fe68628d0dab0de78b5e0bfd022bc69dd2a2c` — **exact match** |

So the pasted body **is** the response the tool received (not an approximation).

Confirmed from the captured body (read, VERIFIED for this identity):
- Item 0 = `{"data":{"product":{...}}}` — the `product` wrapper, `id`/`productId`/`rating`/
  `reviewCount`/`firstPublishedDate`/`state`/`category {id,name}`/`publisher {id,name}`. **H5 confirmed.**
- Item 1 = `{"data":{"productPageViews":20}}` — key is **`productPageViews`**, not `pageViews`. **G7 confirmed.**
- Fixed order for this identity: item 0 = ProductDetail, item 1 = ProductPageViews.
- **No** `operationName`/`operation`/`correlationKey` anywhere → explicit-key correlation cannot work.
- The committed query text (`.scratch:88-89`) produced this body unchanged.

Still UNVERIFIED after this capture: the shape/ordering for the **other nine** selected identities
(uniformity), and whether an `operations` request header makes the endpoint echo `operationName`
(H2 / option B). Both are one `python .scratch/chunk18-live-capture.py` run.

## Full capture — all ten identities + H2 probe (human-run, 2026-09-24 11:45Z) — VERIFIED

The human ran `.scratch/chunk18-live-capture.py`. Results (read from the pasted output):

| Check | Result |
|---|---|
| HTTP status | **200** for all 10 identities |
| sha256 vs recorded | **`matches_recorded=yes` for all 10** — every captured body is byte-identical to the response the tool persisted |
| Ordering | **item 0 = ProductDetail, item 1 = ProductPageViews for all 10** (`product` then `productPageViews`) |
| ProductDetail shape | `{"data":{"product":{id, productId, rating{average,count}, reviewCount, firstPublishedDate, state, category{id,name}, publisher{id,name}}}}` — uniform |
| Page-views shape | `{"data":{"productPageViews": <int>=0>}}` — key is **`productPageViews`**; observed values 20/29/4/30/8/13/2/5/10/**0** (zero is a real value: identity `59028` = 0) |
| Explicit key | **absent** in every item of all 10 |
| **H2 / option (B)** | identity `117382` **with** `operations: ProductDetail,ProductPageViews` + `apollo-require-preflight: true` → HTTP 200, body **unchanged**, `contains_operationName=False`. **Option (B) is dead: the endpoint does not echo `operationName`.** |

Decisive conclusions (VERIFIED):
- **H2 closed: option (B) is not viable.** The explicit-key path cannot work; `VALIDATED_POSITION`
  after preflight validation is required. Design **A.1b + A.2b** (human-approved) is the path.
- **H3 closed:** the fixed two-operation ordering and both operation-specific shapes are uniform
  across all ten selected preflight identities.
- **H5 confirmed on all 10:** the ProductDetail payload is wrapped in `data.product`; the adapter must
  unwrap it.
- **G7 confirmed on all 10:** the page-views item key is `productPageViews`; the request field should be
  aliased to `pageViews` so the frozen validation contract holds.
- **Missing-not-zero note:** `productPageViews = 0` occurs (identity `59028`) and is a valid value, not
  an error — any new validation must keep zero valid and not treat it as absent.

Capture file: `.scratch/chunk18-capture.json`.

## Stage log update

| Stage | Status | Session / evidence |
|---|---|---|
| Plan — `chunk-planner` | **FROZEN** | `ses_f2cc2507bffe2cy4qJ9kft7l46`. Plan `Documents/plans/chunk-18-graphql-correlation-mode-selection.md`, `Status: FROZEN`, 586 lines. Encodes H1=A.1b+A.2b (new public `select_operation_correlation_mode` + pure `interpret_graphql_response`), H2 dead, H3 closed, H4 guard, H5 `data.product` unwrap, G7 `pageViews` alias, mode selected run-level from already-received preflight responses (no second request), carried into `enrich_unique_identities`. Corrected the four DRAFT defects. Commit `2f59463`. |
| Conflict note (plan §4/§12) | recorded | Frozen-interface conflict: `interfaces/chunk-05.md:398-416` vs `plans/chunk-6A-...md:90-92, :794-796`; resolved by A.2b per the human ruling; interfaces are not edited (Chunk 17 precedent). |
| Tests — `test-author` | NEXT | routing per plan §11 (tests first). |
