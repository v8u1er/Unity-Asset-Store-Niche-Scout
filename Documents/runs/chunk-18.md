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
| Prerequisite | Chunk 17 `GATE: PASSED` (`runs/chunk-17.md:156`); interface `chunk-05.md`/`chunk-06A.md` `Status: VERIFIED` (per scope) |
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
