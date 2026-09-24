# Chunk 18 — GraphQL correlation-mode selection (labeled post-Chunk-17 remediation)

Status: DRAFT

This plan is **DRAFT** and **BLOCKED** on the human checkpoints in §12. A correct fix cannot
be frozen before they are answered: they are either a deliberate human checkpoint per
`.kilo/project-rules.md` ("Chunk pipeline auto-chaining"; "Plan review and audit") or a
frozen-interface conflict, and are not the planner's to choose.

Depends on (frozen interfaces required before this plan can be trusted):
  - `Documents/interfaces/chunk-05.md` §5.2 (`GraphQLFailureClass`, incl.
    `CORRELATION_MODE_UNVALIDATED`), §5.5 (correlation contract; the "Chunk 5 MUST NOT"
    boundary lines 398–416), §5.11 (`execute_graphql_batch`, `enrich_asset` signatures,
    lines 770–786) — **consumed, but this chunk's fix would change behavior those
    boundaries freeze; see §5.1 and checkpoint H1.**
  - `Documents/interfaces/chunk-6A.md` §5.1/§5.2 (`PreflightObservation`,
    `IdentityPreflightSummary`, `run_identity_preflight`) — consumed; the fix would add
    validation inside the preflight, which the Chunk 6A plan forbids Chunk 6A from owning
    (`plans/chunk-6A-identity-preflight-planner-and-gate.md:90-92`, `:794-796`). **Checkpoint
    H1.**
  - `Documents/interfaces/chunk-10.md` §4/§5 (`PipelineResult`, `limitations`), §5.x
    (`run_pipeline` `correlation_mode`), and `Documents/interfaces/chunk-12.md` §5/§6
    (`run_command`) — consumed unchanged.
  - `Documents/runs/chunk-18.md` "Grounded recon" and "Confirmed defect" — the lead recon
    this plan is built on (citations re-read this session; see §1.1).
  - Binding human rulings (2026-09-24) from Chunk 17 on cookie/CSRF/query shape — consumed
    unchanged; this chunk is a **distinct** defect (a 200 with no correlation key), not a
    regression of Chunk 17.

Blocks (chunks whose plan/implementation needs this chunk's interface):
  - None. This is a labeled post-completion remediation (same pattern as Chunks 14/15/16/17):
    it has **no `Documents/requirements-dependency-map.md` §3/§4 gate row**, creates no new
    interface file, and no downstream chunk starts on it. The gate is this plan's own §10,
    plus the dispatch DoD (a human `python -m niche_scout run` reaching and **passing** the
    identity preflight).

## 1. Goal

Make a human `python -m niche_scout run` reach and **pass** the identity preflight against
the live Unity storefront GraphQL endpoint, by making the correlation mode that production
executes actually reach the correlation algorithm, and by implementing the `LREQ-GQL-030`
fallback (`VALIDATED_POSITION`) selection that no chunk currently implements.

Scope of the defect, stated as the lead diagnosed it and as re-read here: on the live
endpoint the batch returns HTTP 200 and a body that carries **no explicit correlation key**
(`operationName`/`operation``/`correlationKey` absent at every level shown), while production
always executes in `EXPLICIT_KEY`, so `_correlate_by_explicit_key` marks both operations
`OPERATION_CORRELATION_MISSING` and the preflight fails. The minimal fix has two halves:
(i) the caller's `correlation_mode` must actually reach the execute/correlate path (today it
is only relabelled after the fact), and (ii) `LREQ-GQL-030`'s "position MAY be used only
after the identity preflight validates the fixed two-operation ordering and expected
operation-specific response shapes across the selected preflight identities" must be
implemented, because no code path selects or validates `VALIDATED_POSITION` today.

### 1.1 Grounded findings (labels: **read** = opened this session; **counted** = queried; **unverified** = not checked; **live** = human-run probe recorded in `.scratch`, not reproduced here)

- **G1 (read).** `collector_graphql.py:2477-2486` `_correlation_mode_for_request` hardcodes
  `GraphQLOperationCorrelationMode.EXPLICIT_KEY`; `:2453-2458`
  `execute_graphql_batch` passes that value into `_interrogate_response`, which calls
  `correlate_operations(items, mode=correlation_mode)` (`:2381`). `execute_graphql_batch`'s
  frozen signature has **no** `correlation_mode` parameter (`:2402-2409`;
  `interfaces/chunk-05.md:770-776`).
- **G2 (read).** `collector_graphql.py:2531-2563` `enrich_asset` accepts a caller
  `correlation_mode`, calls `execute_graphql_batch` **without** it (`:2554-2556`), and then
  post-hoc `replace`s `correlation.mode` and both operation `correlation_mode`s (`:2557-2563`)
  if they differ. The caller's mode therefore never influences correlation; it only relabels
  an explicit-key failure. `interfaces/chunk-05.md:781` does give `enrich_asset` a
  `correlation_mode` parameter.
- **G3 (read).** `_correlate_by_validated_position` (`:815-863`) exists and is reachable only
  through `correlate_operations` when `mode` is `VALIDATED_POSITION` (`:898-903`); it **does
  not** validate ordering itself and says so in its docstring ("position validation is the
  identity preflight's job (Chunk 6A, LREQ-ID-020)"). `_build_pre_exchange_result`
  (`:2298-2350`) and the `TRANSPORT_FAILURE` branch (`:2440-2448`) hardcode `EXPLICIT_KEY`
  as the mode for a no-items result.
- **G4 (read).** The only "mode validation" implemented is an enum-membership check:
  `pipeline.py:599-608` `_correlation_mode_is_valid` ("never fires for a live adapter result");
  `:662-669` `_build_observation` appends `operation_correlation_mode_invalid` when it fires.
  `run_pipeline`'s `correlation_mode` defaults to `EXPLICIT_KEY` (`:3149-3151`); `cli.py:429-443`
  builds `run_kwargs` with no `correlation_mode`, so production is always `EXPLICIT_KEY`.
  `run_identity_preflight` (`:1065-1154`) loops `_run_adapter(..., correlation_mode=...)` and
  writes that value into the summary; `enrich_unique_identities` (`:1443-1530`) likewise.
- **G5 (read).** `extract_operation_correlation_key` (`:620-636`) reads `operationName`,
  `operation_name`, `operation`, `correlationKey` (`CORRELATION_KEY_MEMBERS`, `:607-617`); a
  non-mapping item, or one with no usable string member, returns `None` and is never repaired.
- **G6 (live, from `.scratch/graphql_csrf_finding.md:93-97`, re-read this session).** The
  captured live 200 body for one identity is
  `[{"data":{"product":{...}}},{"data":{"productPageViews":66}}]` — two bare envelopes, no
  explicit key anywhere, and `66` is a bare scalar (not `{"pageViews":66}`). This is **one**
  identity. The shape across the selected preflight identities is **UNVERIFIED**.
- **G7 (read + counted).** `validate_page_views_payload` (`:1374-1412`) requires
  `{"pageViews": <value>}`; a bare `/` scalar payload is `WRONG_DATA_SHAPE`
  (`_is_operation_envelope` is false for a bare scalar, so `payload = item`). **Consequence:
  a keyless live body is not merely a correlation problem — its page-views item is also a
  wrong shape.** `_PRODUCT_PAGE_VIEWS_QUERY` (`:338-342`) selects the bare scalar
  `productPageViews(packageId: $packageId)`. Whether the endpoint's 200 returns
  `{"data":{"productPageViews":66}}` or `{"data":{"pageViews":66}}` under the **tool's exact
  committed query text** (the `.scratch:96` capture used a slightly different query text) is
  **UNVERIFIED**.
  - counted: `grep -n "operationName" tests/fixtures/graphql_fixtures.py` → **46 matches**,
    all in response bodies / expected request objects (line numbers in the file); no fixture
    body is keyless. Count method: `grep` with `path` = that file, `limit` 60, pattern
    `operationName`; the tool returned "Found 46 matches" and the matched lines. Unit =
    matching lines, not distinct bodies.
- **G8 (read).** Pins that will conflict (list only; no rename decided here):
  - `tests/test_collector.py:2057-2117` `test_validated_position_mode_is_accepted_not_validated_here`
    asserts execution "still defaults to the explicit-key mode" and that a keyed one-item body
    under `VALIDATED_POSITION` is `OPERATION_CORRELATION_AMBIGUOUS` (via
    `gqlfx.validated_position_ordering_body()` → `single_item_body()`).
  - `tests/test_identity_preflight.py:65, 623, 810, 1044` pin `correlation_mode=pf.EXPLICIT_KEY`
    and `observation.correlation_mode == EXPLICIT_KEY.value` /
    `summary["graphql_operation_correlation_mode"] == "explicit_key"`.
  - `tests/fixtures/graphql_fixtures.py:614-616, 719-721` — `in_order_success_body()` returns
    `target_asset_body()`, which carries `operationName` on both items (`:600-611`); the whole
    fixture family is keyed. No keyless-success fixture exists.
- **G9 (read).** Frozen-interface conflict, re-read in the interface and plan files:
  `interfaces/chunk-05.md:407-416` ("Chunk 5 MUST NOT ... must not *validate* position under
  `VALIDATED_POSITION`. Position validation is the identity preflight's job (Chunk 6A,
  LREQ-ID-020) ... Under `VALIDATED_POSITION`, Chunk 5 accepts the caller's mode as
  already-validated"); `plans/chunk-6A-identity-preflight-planner-and-gate.md:90-92` ("New
  GraphQL protocol behavior, correlation algorithms, or retry policy — Chunk 5 owns all of
  it. 6A ... must not re-implement request construction or correlation.") and `:794-796`
  ("`pipeline.py` MUST NOT re-implement GraphQL request construction, correlation, response
  validation, or retry classification"). The SRS requirement is a single sentence whose two
  actors (validate in preflight, use validated ordering in adapter) are split across two
  frozen chunks, and neither implemented the selection.
- **G10 (read).** Ownership/support facts: SRS-lean.md:300-312 (`LREQ-GQL-030`),
  `:336-338` (`LREQ-GQL-080`), `:348-352` (`LREQ-SEC-010/020`), `:368-372` (`LREQ-ID-020`),
  `:386-414` (`LREQ-ID-040`), `:283-285` (`LREQ-EXT-100`). Re-read this session.

## 2. Scope

### In scope (the fix's two halves — both currently absent)

- **S1 — the caller's correlation mode must reach correlation (defect half 1).**
  `enrich_asset`'s `correlation_mode` must be passed into the execute path and used by
  `correlate_operations`, instead of the post-hoc relabel at `collector_graphql.py:2557-2563`.
  The exact plumbing (private parameter on `execute_graphql_batch` vs. a private
  `_correlation_mode_for_request`-replacement vs. a public frozen-signature change) is
  **checkpoint H1** — this plan presents the options in §5 and does not choose.
- **S2 — `LREQ-GQL-030` fallback selection and preflight validation (defect half 2).** The
  identity preflight must **validate** the fixed two-operation ordering and the expected
  operation-specific response shapes across the selected preflight identities, and only then
  select `VALIDATED_POSITION`; if validation fails, persist `EXPLICIT_KEY` and let both
  operations be marked malformed with their fields unavailable (the SRS's "if neither mode is
  validated" branch). Where that validation lives is **checkpoint H1**. The validation must
  make the preflight's rows reusable for `enrich_unique_identities` with **one request per
  identity** (`LREQ-GQL-080` / `LREQ-ID-040` / `LREQ-GQL-030`'s "across the selected preflight
  identities").
- **S3 — tests and traceability first.** `test-author` writes the failing nodes and their
  `tests/traceability.json` entries before the implementer edits source. No live network in
  tests. (§9.)
- **S4 — record, never close.** New obligations are recorded in §12, not resolved: the
  keyless live body shape across identities (requires a human live capture), OI-6,
  `taxonomy_sha256` empty-hash rejection (Chunk 10), and URI trailing-identifier extraction
  `1.0.1`.

### Explicitly out of scope (and who owns it instead)

- **Option (B), the `operations` request header.** `GraphQLBatchRequest.operations_header`
  is built (`collector_graphql.py:309, 464-466`) but `build_graphql_headers` (`:395-411`)
  never emits it. Sending it to make the endpoint echo `operationName` is presented as an
  option in §5 (B) and is **not** part of S1/S2.
- **A page-views payload-shape change.** If the live keyless body's page-views item is a bare
  scalar that `validate_page_views_payload` rejects as `WRONG_DATA_SHAPE` (G7), a further
  change may be needed; that is **checkpoint H3** and is not silently bundled into S1/S2.
- **Any new persisted field, enum member, config knob, or CLI flag.** No third correlation
  mode, no new `GraphQLFailureClass`, no new SRS vocabulary.
- **`metrics.py` / `scoring.py` / `models.py` / `database.py` / `report.py` behavior.** No
  change. (`models.GraphQLOperationCorrelationMode` already has exactly the two SRS members,
  `models.py:132-134`; no edit.)
- **`favorite_count`, extra GraphQL operations/fields, scheduling, resume/checkpoint,
  historical trends/run comparison, bulk enrichment before the gate, multi-user/cloud.** SRS
  §15 / AGENTS.md "Out of scope".
- **A new interface file.** None is created (Chunks 14/15/16/17 created none).
- **Live network in development or tests.** No test calls the real endpoint; `niche-scout run`
  is never run by an agent.

## 3. Requirements this chunk must satisfy

Chunk 18 has **no `Documents/requirements-dependency-map.md` §3 section**. The LREQs below are
taken from `SRS-lean.md`, re-read this session at the cited lines.

| LREQ ID | Ownership role here | Normative text (SRS-lean.md, quoted/derived) | SRS section |
|---|---|---|---|
| LREQ-GQL-030 | **Primary (this remediation)** | "GraphQL response items SHALL be associated by explicit operation name or another validated correlation key. Response position alone SHALL NOT be trusted unless separately validated as an endpoint guarantee. ... If the live response provides no explicit operation name or correlation key, the implementation MAY use response position only after the identity preflight validates the fixed two-operation ordering and expected operation-specific response shapes across the selected preflight identities. The persisted correlation mode SHALL be either `explicit_key` or `validated_position`. If neither mode is validated, both operations SHALL be marked malformed and their fields SHALL remain unavailable." | §4.2, lines 300-312 |
| LREQ-ID-020 | **Primary (this remediation's validation half)** | "The preflight SHALL perform the normal GraphQL request and verify: ... the operation-correlation mode is valid; and no unexplained response-shape or operation-association error occurred." | §4.4, lines 368-372 |
| LREQ-ID-040 | Integration completion (Chunk 6A remains primary) | "Successful preflight responses SHALL be reused as the corresponding enrichment observations and SHALL count toward the one-enrichment-per-unique-identity limit." and "The persisted `identity_preflight_summary_json` SHALL include ... the selected `graphql_operation_correlation_mode`." The selected mode (S2) must be the one persisted and the one reused for enrichment. | §4.4, lines 386-414 |
| LREQ-GQL-080 | Integration completion (Chunk 6B remains primary) | "A unique sampled identity SHALL be enriched at most once per run ... The result SHALL be joined to every referencing category." The mode selected in the preflight must be applied to the enrichment path without a second request per reused identity. | §4.2, lines 336-338 |
| LREQ-GQL-040 | Supporting (Chunk 5 remains primary; classification unchanged) | "Each operation SHALL have an independent status. ... null required data, wrong data shape, wrong scalar type ... SHALL be recorded as an operation error." S2 must not turn a wrong-shape or missing association into a success, and must use the existing failure vocabulary. | §4.2, lines 318-323 |
| LREQ-GQL-010 | Supporting (Chunk 5 remains primary) | The two-required-operations / same `asset_identity_key` batch contract is unchanged; S1/S2 change only which association mode the same batch runs under. | §4.2, lines 289-292 |
| LREQ-SEC-010 / LREQ-SEC-020 | Constraint | Secrets stay out of source, logs, SQLite, error messages, and every artifact; no cookie/header value is added to any new persisted field or diagnostic. | §4.3, lines 348-352 |
| LREQ-ARCH-030 | Supporting | "The same normalized input data, policy versions, and configuration SHALL produce the same metric, score, evidence, and sensitivity outputs." The mode selection is a deterministic function of the preflight observations; no clock, RNG, or set/dict-ordering dependence. | §3 |

**Not satisfied here and not claimed:** the SRS's "design annotation only, not a
statistically representative validation" caveat (`LREQ-ID-020`, line 374) is unchanged;
nothing in this chunk claims the live body shape is representative.

## 4. Interface contracts consumed

Copied from the frozen interface files (not re-derived from source):

- `interfaces/chunk-05.md` §5.11 (`:770-786`): `execute_graphql_batch(request, *, transport,
  headers, policy=..., sleep=...) -> EnrichmentResult` — **no `correlation_mode` parameter**;
  `enrich_asset(asset_identity_key, *, credentials, transport, correlation_mode,
  retrieved_at_utc, policy=..., endpoint=..., sleep=...) ->
  tuple[EnrichmentResult, EnrichmentObservationDraft]` — **has one**.
- `interfaces/chunk-05.md` §5.5 (`:398-416`): the "Chunk 5 MUST NOT" boundary quoted in G9;
  failure classification is exact and total (zero items or no key under `EXPLICIT_KEY` →
  `OPERATION_CORRELATION_MISSING`; duplicate key → `..._DUPLICATED`; unknown key →
  `..._UNKNOWN`; keyed body that cannot present the fixed order under `VALIDATED_POSITION` →
  `..._AMBIGUOUS`).
- `interfaces/chunk-05.md` §5.2: `GraphQLFailureClass` incl.
  `CORRELATION_MODE_UNVALIDATED = "correlation_mode_unvalidated"` (defined at
  `collector_graphql.py:209`) and the no-retry invariant for permanent classes.
- `interfaces/chunk-6A.md` §5.1/§5.2: `PreflightObservation.correlation_mode: str` is "a
  `GraphQLOperationCorrelationMode` value"; `IdentityPreflightSummary.graphql_operation_correlation_mode: str`
  is the SRS-mandated key (SRS-lean:414); `run_identity_preflight(repository, run, *,
  credentials, transport, correlation_mode, retrieved_at_utc, policy, endpoint=...,
  retry_policy=..., sleep=...) -> IdentityPreflightOutcome`.
- `interfaces/chunk-6A.md:222-228`: `endpoint_signature`, `mapping_rule_version`,
  `correlation_mode`, `is_both_operations_success`, `diagnostic_summary_json` are
  preflight-only and live in the run-level summary; the draft carries
  `request_metadata_json` per Chunk 5 §5.10.
- `interfaces/chunk-10.md` §4/§5 (`PipelineResult`, `limitations`), `interfaces/chunk-12.md`
  §5/§6 (`run_command` constructs the transport; the returned callable adds nothing beyond
  the caller-supplied headers) — consumed unchanged.

**Signature-freeze facts (read this session).** `execute_graphql_batch` is keyword-only after
`request` and has no mode parameter (`collector_graphql.py:2402-2409`). `enrich_asset` has one
(`:2531-2541`) and ignores it for correlation (`:2554-2563`). `run_pipeline`'s
`correlation_mode` is a keyword parameter defaulting to `EXPLICIT_KEY` (`:3149-3151`);
`cli.run_command` never sets it (`cli.py:429-443`).

## 5. Options and tradeoffs (presented — NOT chosen)

The SRS names exactly two persisted modes and gives a single sentence that splits
responsibility across two frozen chunks; neither chunk implemented the selection. The
following options are the only ones this plan sees. **Relabelling a hard-coded explicit-key
failure as `validated_position`, guessing position without preflight validation, fabricating a
correlation key, and inventing a third correlation mode are NOT acceptable and are not options
below.**

### 5.1 Option (A) — minimal correct: thread the mode + implement the `LREQ-GQL-030` validation

**A.1 The caller's mode must reach correlation.** Three sub-options, all of which fix
`enrich_asset:2557-2563`'s relabel:

- **A.1a — private plumbing.** Add a module-private parameter (for example
  `_correlation_mode: GraphQLOperationCorrelationMode | None = None`) to
  `execute_graphql_batch`, have `enrich_asset` pass `mode`, and delete the relabel. The
  public frozen signature of `execute_graphql_batch` (`interfaces/chunk-05.md:770-776`) stays
  byte-identical; only a private path changes. **Tradeoff:** a private parameter on a public
  function is a behavior change to a frozen surface without a recorded contract change — a
  reviewer may call it a silent divergence; it is the smallest diff.
- **A.1b — public signature change.** Add `correlation_mode` to `execute_graphql_batch`'s
  frozen signature (`interfaces/chunk-05.md:770-776`) and have `enrich_asset` pass it.
  **Tradeoff:** explicit and reviewable, but it is a **frozen-interface change** requiring a
  human checkpoint (H1); the file is not edited by this plan either way.
- **A.1c — replace `_correlation_mode_for_request`.** Keep the public signature and give the
  request object the mode through a private side channel. **Tradeoff:** `GraphQLBatchRequest`
  is a frozen dataclass (`interfaces/chunk-05.md`; `collector_graphql.py:293-311`) and carries
  no mode; adding one is a frozen-structure change to a request object that must stay safe to
  log and fixture. Listed for completeness; strongly disfavored.

**A.2 Where the `LREQ-GQL-030` validation lives.** The SRS's sentence has two actors: the
preflight **validates**; the adapter **uses** the validated ordering. Two placements:

- **A.2a — validation in the preflight (Chunk 6A `pipeline.py`).** `run_identity_preflight`
  collects the per-identity responses (the preflight rows already exist and are already
  reused), then runs a new validation over the **selected preflight identities** that checks
  (i) every response decodes to exactly two bare envelopes, (ii) no item carries any explicit
  key, (iii) item 0 has the `ProductDetail` operation-specific shape and item 1 has the
  `PageViews` operation-specific shape. If all hold across every preflight identity, the
  selected mode is `VALIDATED_POSITION` and that value is passed to the adapter for both the
  reused preflight rows and `enrich_unique_identities`; otherwise `EXPLICIT_KEY` and the
  existing malformed path stands. **Tradeoff:** this is the placement `interfaces/chunk-05.md:410-412`
  names ("Position validation is the identity preflight's job (Chunk 6A, LREQ-ID-020)"), but it
  adds "correlation" logic to `pipeline.py`, which `plans/chunk-6A-...md:90-92, :794-796`
  forbids. **This is the central frozen-interface conflict — checkpoint H1.**
- **A.2b — validation in the adapter, driven by the preflight's evidence.** A Chunk 5
  validation primitive (for example a public `validate_correlation_mode_for_identities(...)`
  in `collector_graphql.py`) implements the ordering/shape check; `pipeline.py` only supplies
  the evidence (the preflight responses/observations) and records the resulting mode. The
  adapter still does not "validate position" per its own §5.5 clause — it validates an
  endpoint guarantee (the fixed ordering and shapes) and hands the preflight a decision it
  persists. **Tradeoff:** honours Chunk 5's correlation-algorithm ownership and Chunk 6A's
  no-re-implementation rule, but requires the preflight rows to expose enough raw association
  evidence (item order and shape) for a second pass, and creates a new public Chunk 5 symbol
  (a contract addition, not a change). **Checkpoint H1.**

**A.3 Reuse without a second request per identity.** Both A.2 placements must keep
`LREQ-GQL-080`/`LREQ-ID-040`: the selected mode is computed from the preflight's own responses
and then applied when the preflight rows are reused by `enrich_unique_identities`. The
preflight already issues exactly one `enrich_asset` per unique identity
(`pipeline.py:1103-1120`, `:1501-1514`); the fix must not add a probe request or a second call
per reused identity. **Checkpoint H4** if a design appears to require an extra request.

### 5.2 Option (B) — send the `operations` header and rely on `EXPLICIT_KEY`

`GraphQLBatchRequest.operations_header` is built (`collector_graphql.py:309, 464-466`,
`",".join(operation_name ...)`) and `build_graphql_headers` never emits it (`:395-411`). A
probe already tried `operations: ProductDetail,ProductPageViews` +
`apollo-require-preflight: true` and "changed nothing", but that probe was **pre-cookie**
(HTTP 400) — whether a successful 200 with the header would echo `operationName` is
**UNVERIFIED** (`.scratch/graphql_csrf_finding.md:20-21`; run log B2).

- **Tradeoff (for):** if the endpoint echoes `operationName` on a 200, this is cheaper and
  avoids `VALIDATED_POSITION` entirely; it uses the primary `LREQ-GQL-030` association
  ("explicit operation name") rather than the fallback.
- **Tradeoff (against):** it is unverified and needs a **live probe**; the captured live 200
  body already shows no explicit key with the tool's header set, and `.scratch:21` shows the
  header made no difference pre-cookie (possibly because the request never executed a GraphQL
  operation at all). It is a request-shape change to a frozen surface (Chunk 5 headers),
  requiring the same checkpoint discipline.
- **Decision:** present only. **Checkpoint H2** — "do we probe (B) first, before committing to
  (A)?" is a human call, because it changes what the fix must contain.

### 5.3 Option (C) — a key member the extractor does not yet read

`extract_operation_correlation_key` already reads `operationName`, `operation_name`,
`operation`, `correlationKey` (`collector_graphql.py:607-636`). The captured live body
(`.scratch:96`) carries **none** of them at any level shown. A further explicit-key member can
only help if the endpoint emits one that the adapter does not read; that would require a live
capture first, and the SRS names no additional member. **Decision:** present only; no member
is invented. **Checkpoint H3** (capture) if a candidate member appears.

### 5.4 Non-options (explicitly rejected)

Relabelling a hard-coded explicit-key failure as `validated_position`; associating by response
position without the preflight's ordering/shape validation; fabricating or synthesizing a
correlation key not present in the response; inventing a third persisted correlation mode or a
new `GraphQLFailureClass`; treating a wrong-shape page-views item as success to make the
preflight pass. None of these is SRS-authorized and none is an option in this plan.

## 6. Human checkpoints (presented; not chosen; none resolved here)

- **H1 — the frozen-interface conflict (blocking; see G9).** `interfaces/chunk-05.md:407-416`
  freezes "Chunk 5 ... must not validate position ... position validation is the identity
  preflight's job (Chunk 6A)", while `plans/chunk-6A-...md:90-92, :794-796` freezes
  "`pipeline.py` MUST NOT re-implement ... correlation". A correct `LREQ-GQL-030` fix must
  place the validation somewhere; every placement touches a frozen surface. **Options:**
  A.1a/A.1b/A.1c (plumbing) × A.2a/A.2b (placement). **This checkpoint must be answered before
  the plan can freeze** — the file(s) touched and the resulting signatures depend on it.
- **H2 — whether to probe option (B) first.** A live probe (human-run, `.scratch/`) with the
  committed request shape plus an `operations` header on a 200 would convert `.scratch:20-21`'s
  pre-cookie probe into evidence. If the endpoint echoes `operationName`, option (B) is the
  cheaper fix and `VALIDATED_POSITION` may be unnecessary for a passing run. **Answer decides
  S1/S2's required content.**
- **H3 — the live capture required to confirm the 200 body shape across the selected
  preflight identities.** `LREQ-GQL-030` requires the ordering/shapes to hold **"across the
  selected preflight identities"**; only one identity's body is captured, and response bodies
  are never persisted (`collector_graphql.py:_decode_operation_items`; SEC), so this cannot be
  confirmed offline. The planner cannot run live network (AGENTS.md). **Capture needed:** at
  least two selected preflight identities spanning at least two products, with the tool's
  exact committed request text, recording for each: HTTP status, the full body, whether any
  explicit key appears, the item order, and the page-views item's exact shape (`productPageViews`
  bare scalar vs. `{"pageViews": ...}`). **This also determines whether a page-views
  payload-shape change (G7) is in scope.**
- **H4 — reuse path if a design needs an extra request.** If the chosen design cannot compute
  the mode from the preflight's existing rows, the minimal correct fix may need an extra live
  request, which would conflict with one-request-per-unique-identity (`LREQ-GQL-080`). No such
  design is proposed here; flagged so a later implementer does not add one silently.

**Because H1 and H3 block a correct plan, this plan stays `DRAFT`.**

## 7. Files this chunk would touch (contingent on H1)

**Expected paths — this chunk must touch no others. The exact set depends on H1; the rows
below are the plausible superset, with the contingency named.**

| File | New/modified | Purpose | Contingent on |
|---|---|---|---|
| `src/niche_scout/collector_graphql.py` | modified | S1: make `enrich_asset`'s `correlation_mode` reach correlation and remove the relabel (`:2557-2563`); A.1a/A.1b/A.1c. S2: under A.2b, the ordering/shape validation primitive. | H1 (A.1a/A.1b/A.2b) |
| `src/niche_scout/pipeline.py` | modified | S2 under A.2a: validation + mode selection in `run_identity_preflight` and propagation to `enrich_unique_identities` / `run_pipeline` / the summary. | H1 (A.2a) |
| `tests/fixtures/graphql_fixtures.py` | modified | A **keyless** two-envelope success body matching `.scratch:96`'s shape, plus a keyless page-views item in the shape the endpoint actually returns (pending H3); keyless variants for ambiguous/duplicated cases if the validation path needs them. | H3 |
| `tests/fixtures/identity_preflight_fixtures.py` (`pf` in `test_identity_preflight.py`) | modified | Extend only if the selected mode or a keyless transport is needed by the new preflight validation nodes. | H1 |
| `tests/test_collector.py` | modified | Update the `test_validated_position_mode_is_accepted_not_validated_here` pin under the chosen design; add the S1 nodes. | H1 |
| `tests/test_identity_preflight.py` | modified | Add S2 nodes; update the `explicit_key` pins only where the plan's chosen behavior changes them. | H1 |
| `tests/traceability.json` | modified | Add entries for every new/renamed node; rename keys old→new only if H1 forces a node rename (one-rename precedent, §9.4). | H1 |
| `Documents/runs/chunk-18.md` | **not** touched by this planner | Lead/run log; the gate records the live run there. | — |

**Not touched (explicit):** `metrics.py`, `scoring.py`, `models.py`, `database.py`,
`report.py`, `cli.py`, `config.py`, `.env.example`, `sampling.py`, `validation.py`,
`collector.py`, `collector_coveo.py`, `src/niche_scout/tools/**`, `pyproject.toml`,
`config/**`, `Documents/SRS-lean.md`, `Documents/requirements-dependency-map.md`,
`AGENTS.md`, `kilo.json(c)`, `.kilo/`, any `Documents/interfaces/*`, and any frozen
`Documents/plans/*` or `Documents/runs/*` file.

## 8. Typed signatures and null/edge-case behavior (target, contingent on H1)

A `test-author` must be able to write tests without seeing the implementation. The exact public
surface is **not frozen** until H1 is answered; the following states the required behavior in
the option-independent terms, and marks the parts H1 fixes.

### 8.1 Correlation mode reaches correlation (S1)

Required behavior regardless of A.1a/A.1b/A.1c: `enrich_asset(..., correlation_mode=X, ...)`
must ensure that **each operation's `correlation_mode` and `correlation.mode` are the mode the
correlation actually ran under**, and is `X`. No post-hoc stamping that changes a failure's
mode without changing the association decision.

- `correlation_mode` must be a `models.GraphQLOperationCorrelationMode`; a non-member raises
  `TypeError` (unchanged `_require_correlation_mode`, `:718-722`).
- Under `EXPLICIT_KEY` with a keyless body → both operations
  `OPERATION_CORRELATION_MISSING`, `correlation.mode is EXPLICIT_KEY` (the current live
  failure; must remain correct and reproducible in a fixture).
- Under `VALIDATED_POSITION` with a two-envelope keyless body → item 0 associated with
  `ProductDetail`, item 1 with `ProductPageViews`, both `NONE`,
  `correlation.is_fully_correlated is True`, `correlation.mode is VALIDATED_POSITION`.
- Under `VALIDATED_POSITION` with a body whose item count ≠ 2, or any item carrying an
  explicit key → both operations `OPERATION_CORRELATION_AMBIGUOUS` (existing
  `_correlate_by_validated_position` behavior, `:839-856`), `correlation.mode is
  VALIDATED_POSITION`.
- The no-items/decode-failure paths (`_build_pre_exchange_result`, the
  `TRANSPORT_FAILURE` branch) must report the same mode the call ran under, not a hardcoded
  `EXPLICIT_KEY` (today `:2446`, `:2310-2313`).

### 8.2 Correlation-mode selection and validation (S2)

Option-independent behavior for the function that decides the persisted/selected mode (name
and home module fixed by H1; under A.2b it would be a new public `collector_graphql.py`
symbol):

- **Input:** the per-identity evidence for the **selected preflight identities**, in
  selection order (the already-executed preflight responses/observations; no new request).
- **Returns:** `GraphQLOperationCorrelationMode` — `VALIDATED_POSITION` iff, for **every**
  selected identity, (i) the decoded body is a list of exactly two items, (ii) no item carries
  any explicit key (`extract_operation_correlation_key(item) is None` for both), (iii) item 0
  matches the expected `ProductDetail` operation-specific shape and item 1 matches the
  expected `ProductPageViews` operation-specific shape; otherwise `EXPLICIT_KEY`.
- **Explicit key present anywhere** → `EXPLICIT_KEY` (the primary mode is already satisfied;
  position is not needed).
- **Any selected identity's shape wrong, item count ≠ 2, unknown item kind, or decode
  failure** → `EXPLICIT_KEY` (selection is all-or-nothing across the selected identities; the
  SRS says "across the selected preflight identities").
- **Zero selected identities** → the preflight is `insufficient` (`LREQ-ID-040`); selection is
  not reached; the value must not be fabricated. (Null/insufficient stays distinct from
  `EXPLICIT_KEY`; no default.)
- **Determinism:** the result is a pure function of the ordered evidence; no clock, RNG, or
  set/dict-ordering dependence.
- **Wrong page-views shape** (bare `productPageViews` scalar vs. `{"pageViews": …}`): if the
  endpoint's 200 item is not `{"pageViews": …}`, shape validation cannot pass and a separate
  payload-shape decision is required (H3). The selection function must not paper over it.

### 8.3 Reuse and persistence (S2 / LREQ-ID-040 / LREQ-GQL-080)

- `PreflightObservation.correlation_mode` and
  `IdentityPreflightSummary.graphql_operation_correlation_mode` carry the **selected** mode
  (`"explicit_key"` or `"validated_position"` only).
- The mode applied to `enrich_unique_identities` for reused identities must equal the
  preflight's selected mode; reused identities are **not** re-requested.
- If selection is `EXPLICIT_KEY` and the keyless body persists, both operations stay marked
  malformed and their fields unavailable — the preflight gate's existing `failed` path is
  unchanged.

## 9. Test plan

- **Files:** new/updated nodes in `tests/test_collector.py` and `tests/test_identity_preflight.py`;
  fixture additions in `tests/fixtures/graphql_fixtures.py` (and
  `identity_preflight_fixtures` only if needed). No live network; every transport is a
  recording double.
- **Fixture needed (blocked on H3 for exact shape):** a **keyless** success body
  `[{"data":{"product":{…}}},{"data":{"productPageViews":66}}]` (exact page-views key/value
  per the capture) and a keyless page-views shape that the chosen design accepts. Hand-derived
  expected values below assume the capture's `66`.
- **Node candidates (names provisional until H1; markers and traceability values are not).**

| pytest node ID (provisional) | Marker args | `tests/traceability.json` value |
|---|---|---|
| `tests/test_collector.py::test_validated_position_selects_keyless_two_envelope_body` | `LREQ-GQL-030` | `["LREQ-GQL-030"]` |
| `tests/test_collector.py::test_validated_position_rejects_explicit_key_body_as_ambiguous` | `LREQ-GQL-030` | `["LREQ-GQL-030"]` |
| `tests/test_collector.py::test_explicit_key_mode_marks_keyless_body_correlation_missing` | `LREQ-GQL-030` | `["LREQ-GQL-030"]` |
| `tests/test_identity_preflight.py::test_preflight_selects_validated_position_for_keyless_bodies` | `LREQ-GQL-030`, `LREQ-ID-020` | `["LREQ-GQL-030", "LREQ-ID-020"]` |
| `tests/test_identity_preflight.py::test_preflight_selects_explicit_key_when_any_identity_is_keyed` | `LREQ-GQL-030`, `LREQ-ID-020` | `["LREQ-GQL-030", "LREQ-ID-020"]` |
| `tests/test_identity_preflight.py::test_preflight_selected_mode_is_persisted_and_reused_without_a_second_request` | `LREQ-ID-040`, `LREQ-GQL-080` | `["LREQ-ID-040", "LREQ-GQL-080"]` |

  Markers must equal the traceability values and vice versa. `tests/traceability.json` is
  **keyed by node ID → array** (confirmed by reading `tests/traceability.json:1-25`);
  `tests/AGENTS.md`'s prose describes ID→node orientation but cannot be true on the same keys
  (a node-ID key cannot be a valid `LREQ-*` ID) — recorded as an open item in §12 rather than
  resolved silently.
- The exact node set depends on H1 (A.1 vs A.2 placement and whether an existing node is
  updated rather than replaced). No node is renamed by this plan's default; if H1 forces a
  rename, follow the one-rename precedent: change the key old→new with the same LREQ values,
  keep the pytest node name consistent with its assertions, and record the rename in
  `Documents/runs/chunk-18.md`.
- **Pins that will be reconciled (list, not renaming):**
  `tests/test_collector.py:2057-2117`, `tests/test_identity_preflight.py:65, 623, 810, 1044`.
  Under S2 with a keyless fixture the pins `observation.correlation_mode == "explicit_key"` /
  `summary[...] == "explicit_key"` change **only for the nodes that now exercise the keyless
  path**; keyed-body nodes keep `explicit_key`.
- **Golden vectors:** the keyless body is the golden (`66` hand-copied from the capture);
  expected association is item 0 → `ProductDetail`, item 1 → `ProductPageViews`, both `NONE`
  under `VALIDATED_POSITION`, both `OPERATION_CORRELATION_MISSING` under `EXPLICIT_KEY`.
- **Contradiction handling:** if any existing test contradicts the SRS after the change, leave
  it and report `DISPUTE: <test id> — SRS §x says ...`.

## 10. Definition of done (gate)

Chunk 18 has no dependency-map §3 gate; the dispatch's DoD is the gate (same shape as
Chunk 14's). Copied from the dispatch:

- **DoD-1 (human live run, the chunk's purpose).** A human `python -m niche_scout run` reaches
  and **passes** the identity preflight against the live endpoint, with the minimum
  consequential changes; the run's persisted summary shows a selected correlation mode of
  `explicit_key` or `validated_position` (SRS §4.2/§4.4). This bullet cannot be proven by the
  offline suite and is the human's check; the lead's live probes and the capture (H3) are the
  supporting evidence.
- **DoD-2 (offline suite).** `python -m pytest -q` reports `passed, 0 failed` with real,
  countable counts written into the run log; the count is the pre-change baseline plus the
  new nodes; the exact command and verbatim output are recorded. An unrelated pre-existing
  failure is reported verbatim, never claimed green.
- **DoD-3 (validators).** `python -m niche_scout.tools.validate_traceability`,
  `check_import_boundaries`, `check_scope_prohibitions`, and `check_secrets` all valid.
- **DoD-4 (lint).** `ruff` on the changed files using `pyproject.toml`
  (`[tool.ruff] line-length = 88`, `select = ["E","F","I"]`); no new lint introduced; any
  pre-existing deviation reported PARTIAL with the unchanged lines named and a byte-exact
  `git show HEAD:<path>` comparison as the baseline.
- **DoD-5 (secrets and no live network in tests).** No credential, cookie, or header value in
  source, tests, fixtures, config, plan, run log, SQLite, or artifacts; no test calls the real
  endpoint.
- **DoD-6 (records).** The plan, run log, tests, traceability, and every new convention are
  recorded; every resolved checkpoint is recorded in the run log with its ruling; every
  remaining obligation stays open.

## 11. Explicit prohibitions

- No relabelling of a hard-coded explicit-key failure as `validated_position`; no
  association by response position without the preflight's ordering/shape validation; no
  fabricated correlation key; no third correlation mode; no new `GraphQLFailureClass`.
- No marking malformed `LREQ-GQL-030` branches as success to make the preflight pass; a wrong
  shape, wrong item count, or unknown item kind stays an operation error (`LREQ-GQL-040`).
- No extra request per unique identity; the preflight issues exactly one `enrich_asset` per
  unique identity and enrichment reuses it (`LREQ-GQL-080`, `LREQ-ID-040`).
- No live network in development or tests; do not run `niche-scout run`.
- No new config knob, CLI flag, environment variable, persisted field, or dependency; no
  configurable weights.
- No edits to `metrics.py`, `scoring.py`, `models.py`, `database.py`, `report.py`,
  `config.py`, `.env.example`, `sampling.py`, `validation.py`, `collector.py`,
  `collector_coveo.py`, `src/niche_scout/tools/**`, `pyproject.toml`, `config/**`, or any
  frozen interface/plan/run document.
- No secret in any artifact; no response body persisted.
- No `favorite_count`, no extra GraphQL operation or field, no scheduling, resume/checkpoint,
  historical trends/run comparison, or bulk enrichment before the gate.
- Do not resolve H1–H4 here; do not pick an option from §5.

## 12. Open questions and remaining obligations

### 12.1 Checkpoints (must be answered before this plan can freeze)

- **H1 (blocking).** Where does the `LREQ-GQL-030` ordering/shape validation live, and how
  does the caller's mode reach correlation? Options: A.1a / A.1b / A.1c × A.2a / A.2b (§5.1).
  Conflict: `interfaces/chunk-05.md:407-416` vs.
  `plans/chunk-6A-...md:90-92, :794-796`. Every option touches a frozen surface.
- **H2 (blocking for S1/S2's content).** Probe option (B) first? Requires a human live probe
  with the `operations` header on a 200 (`.scratch/graphql_csrf_finding.md:20-21` is
  pre-cookie, UNVERIFIED).
- **H3 (blocking for S2's exact shape and for any page-views payload change).** Live capture
  across ≥2 selected preflight identities spanning ≥2 products, with the tool's exact
  committed query text: HTTP status, full body, presence/absence of any explicit key, item
  order, and the page-views item's exact shape. Only one identity's body is captured (`.scratch:96`).
- **H4 (design guard).** If the chosen design needs an extra live request to compute the mode,
  stop: it conflicts with one-request-per-unique-identity (`LREQ-GQL-080`). No such design is
  proposed.

### 12.2 Open obligations (recorded, never closed here)

- **URI trailing-identifier extraction (`identity_mapping_rule 1.0.1`)** — inferred, not
  verified against a real Coveo response; no captured response exists. Owner: identity-mapping
  owner (`interfaces/chunk-01.md` §4.1; dependency-map §6.4). Not touched; no claim.
- **OI-6 — CSRF/session sufficiency** — has no owning chunk. Chunk 17 recorded the live
  cookie/header answers; this chunk neither reopens nor closes it.
- **`runs.taxonomy_sha256` empty-hash rejection** — owner is **Chunk 10** (dependency-map §7).
  Not touched.
- **G7 page-views payload shape under the tool's exact query text** — UNVERIFIED; depends on
  H3. May require a page-views payload change that is not in S1/S2 until H3 answers it.
- **`tests/AGENTS.md` traceability orientation** — the file's prose says "object keyed by
  individual `LREQ-*` IDs" with arrays of node IDs; the committed `tests/traceability.json`
  keys are node IDs. The validator's orientation is not re-derived here; the mismatch is
  recorded, and the plan follows the committed file (node-ID keys). Not resolved here.

## 13. Routing

- **`chunk-planner`** (this task) — write this plan; stop at DRAFT with H1–H4 unresolved.
- **Human checkpoint** — answer H1–H4 (H1/H3 block a correct plan; H2 decides S1/S2's content).
- **`test-author`** — after the rulings, write the new/updated nodes and traceability entries
  **first**, before any source edit (tests-first is required: the change touches the adapter
  protocol and the preflight).
- **`impl-deep`** — implement S1/S2 in the file(s) H1 names, then run the offline suite and
  the validators. `impl-fast` is not suitable: the change spans a frozen protocol boundary and
  the preflight gate.
- **Human live run** — DoD-1, after implementation.
- **`spec-reviewer`** — review the frozen plan, tests, implementation, and the live-run
  evidence recorded in `Documents/runs/chunk-18.md`.