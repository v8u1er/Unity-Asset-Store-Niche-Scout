# Chunk 19 — GraphQL identity-alias agreement remediation (labeled post-Chunk-18 remediation)

Status: FROZEN

This plan was frozen after the human ruled on both open questions on 2026-09-25
(`Documents/runs/chunk-19.md`): **Q1 = Q1-a** (a present-but-empty/non-string authoritative `id`
with a populated `productId` is a **safe non-agreement**; `validate_product_detail_payload`'s
`no_populated_alias`/`identity_usable` stay as they are) and **Q2 = no diagnostic** (a
populated-but-different `productId` emits no extra warning; the existing
`id_mapping_mismatch`/`GRAPHQL_ID_MAPPING_MISMATCH` vocabulary is untouched). The design decision
for the defect itself is frozen by the human ruling of 2026-09-25 (recorded in
`Documents/runs/chunk-19.md` "Human ruling (approved)"), and the plan re-opens nothing about that
decision.

Depends on (frozen interfaces consumed; the interface amendment in §4):

- `Documents/interfaces/chunk-01.md` §4 — `compare_graphql_identity_aliases`,
  `GraphQLIdentityComparisonResult`, `ProductDetailFields`-independent pure comparison and its
  "every canonicalized alias agreed" semantics. **Consumed unchanged.**
- `Documents/interfaces/chunk-05.md` §5.6 (`PRODUCT_DETAIL_ALIAS_MEMBERS`), §5.8
  (`annotate_product_detail_identity`; the alias-set sentence was at line 543 before this chunk
  amended the section) — **§5.8 amended by this chunk**; the amendment is written into
  `Documents/interfaces/chunk-05.md` (§4).
- `Documents/interfaces/chunk-6A.md` §5.1/§5.2 (`PreflightObservation`,
  `IdentityPreflightSummary`, `run_identity_preflight`, `compute_preflight_rates`) — consumed
  unchanged; the fix is adapter-only and needs no `pipeline.py` edit.
- `Documents/runs/chunk-19.md` "Root cause" and "Human ruling (approved)"; the failed live run's
  persisted evidence; `.scratch/chunk18-capture.json`.

Blocks: none. Labeled post-completion remediation (Chunks 14–18 pattern): no
`requirements-dependency-map.md` §3/§4 gate row, no new interface file, no downstream chunk.
The gate is §9 plus the dispatch DoD (a human `python -m niche_scout run` reaching and **passing**
the identity preflight).

## 1. Goal

Make a human `python -m niche_scout run` reach and **pass** the live identity preflight by making
the adapter compare only the **authoritative returned `id`** for `LREQ-GQL-070` agreement, with
the returned `productId` still requested (`LREQ-GQL-020`), still validated as a required member,
and still persisted, but **not** required to agree with the requested canonical identity.

### 1.1 Grounded findings (labels: **read** = opened this session; **counted** = queried;
**live** = human-run capture recorded in `Documents/runs/chunk-19.md` / `.scratch/`)

- **G1 (read).** `collector_graphql.py:1627-1631` `annotate_product_detail_identity` builds
  `aliases` from **both** `product_detail.graphql_id` (keyed `"id"`) and
  `product_detail.product_id` (keyed `"productId"`), then calls
  `compare_graphql_identity_aliases(requested_identity, aliases, ...)` (`:1632-1634`).
- **G2 (read).** `validation.py:1506-1508, 1536-1567` — the pure function requires **every**
  canonicalized alias to agree; a single agreeing alias plus a single disagreeing alias is
  `id_mapping_mismatch=True`. `validation.py:1533-1534, 1575-1577` — an empty alias map is also
  a mismatch ("no GraphQL identity alias was returned"), never a vacuous agreement.
- **G3 (read).** `PRODUCT_DETAIL_ALIAS_MEMBERS = ("id", "productId")` (`:936`) is the
  required/absent identity-member group used by `validate_product_detail_payload` (`:1219`) and
  by the `LREQ-GQL-040` `response_missing_identity` classification (`:1208-1229`); it is **not**
  the agreement alias set. `_usable_string` (`:1049-1053`) returns `None` for absent, `null`,
  non-string, and whitespace-only values, so a present-but-empty `id` is unusable.
- **G4 (read).** `pipeline.py:576-598, 658` derives `identity_match` from
  `comparison.matches_requested_identity`; `pipeline.py:431-434` classifies
  `identity_match is False` as `conflicting`. No `pipeline.py` change is needed: the rates
  follow the adapter comparison.
- **G5 (read).** `models.py:430-431, 440` and `database.py:158-159, 168` persist `graphql_id`,
  `product_id`, and `id_mapping_mismatch` per identity. Persistence is unaffected by the fix.
- **G6 (live).** All ten captured `ProductDetail` payloads have `product.id` **equal to the
  requested package id** and `product.productId` **a distinct long internal id**
  (`.scratch/chunk18-capture.json`; e.g. `"117382"` vs `"275244114082"`), each body
  `matches_recorded: true` against the failed run's persisted `response_sha256`. That is exactly
  the shape that makes both-alias agreement impossible, so `attempted=10, successful=0,
  conflicting=10`.
- **G7 (read).** Retired provenance for "`id` is authoritative":
  `retired-documents/SRS-revision2.md:476` — `id_mapping_mismatch` "Set when GraphQL's returned
  `id` differs from the requested `asset_identity_key`"; `:163` (OI-4) — `productId`/`itemId` are
  "different identifiers from the one the query accepts as `id`"; `:80` — the package id is the
  id "accepted by GraphQL's `product(id)`", assumed equal to `ec_product_id`/`permanentid`.
- **G8 (read).** The prior plan treated the alias member list as an assumption:
  `plans/chunk-05-...md:2989-2995` ("`PRODUCT_DETAIL_ALIAS_MEMBERS` … an assumption to be
  confirmed against a real capture"); `plans/chunk-18-...md:583-584` deferred exactly this
  verification to a DoD-1 live run ("Identity agreement (`id`/`productId` vs the requested
  canonical identity) was not independently confirmed in the H3 capture; the DoD-1 live run
  verifies it"). The Chunk 18 DoD-1 run is that confirmation, and it falsifies the assumption.
- **G9 (read).** `interfaces/chunk-05.md` §5.8 (pre-amendment `:540-544`) pins the alias set
  (`aliases` "built from `graphql_id` and `product_id` when present"), and the missing-identity
  bullet (pre-amendment `:552-555`) states that a `ProductDetail` "with no usable identity alias
  is an operation error via `MISSING_IDENTITY`". Under Option A the sole agreement alias is `id`;
  this creates the present-but-empty-`id` edge resolved as R1 (§13).
- **G10 (counted).** `grep` pattern
  `PRODUCT_DETAIL_ALIAS_MEMBERS|annotate_product_detail_identity|compared_aliases|product_id`,
  path `tests`, limit 80 → **80 matching lines** (limit reached); refined greps show the only
  adapter-level mismatch fixtures set **both** aliases (`tests/fixtures/graphql_fixtures.py:359-368,
  377-379`, `tests/fixtures/identity_preflight_vectors.py:707-716, 801-811`) and **no** test
  asserts that `productId` participates in agreement, so **no existing node-ID rename is
  required** (§8.4). Unit = matching lines, not distinct nodes.
- **G11 (read).** `tests/fixtures/graphql_fixtures.py:795-813` `keyless_product_detail_payload`
  is the live-shape keyless fixture and currently sets **both** aliases to the requested identity
  (`:807-813`); its golden is the `id == productId` assumption recorded at
  `plans/chunk-18-...md:480`.

## 2. Scope

### In scope

- **S1 — authoritative-`id` agreement (the fix).** `annotate_product_detail_identity` supplies
  only the returned `id` (`graphql_id`) as an agreement alias. The `productId` entry is removed
  from the alias map. **One function body changes.**
- **S2 — the frozen amendment.** `interfaces/chunk-05.md` §5.8 is amended to state the same
  (this chunk owns that amendment per the human ruling).
- **S3 — correct the `id == productId` golden assumption in the durable fixtures.**
  `keyless_product_detail_payload` becomes the live shape: `id == requested`,
  `productId == a distinct captured internal id`; the derived keyless bodies carry that shape.
- **S4 — tests and traceability first** (`test-author` before `impl-deep`): new adapter-level and
  preflight-level nodes plus `tests/traceability.json` entries. No live network in tests.
- **S5 — record, never close** the residual risks (§12).

### Explicitly out of scope (and why)

- **`validation.py` / the Chunk 1 pure function.** `compare_graphql_identity_aliases` keeps its
  "every supplied alias agrees" semantics byte-identical (human ruling). No edit.
- **`pipeline.py`, `models.py`, `database.py`, `report.py`, `cli.py`, `config.py`, `sampling.py`,
  `collector.py`, `collector_coveo.py`, `metrics.py`, `scoring.py`, `src/niche_scout/tools/**`,
  `pyproject.toml`, `config/**`.** No change: the defect is adapter-local and the rates/persistence
  already follow the adapter comparison (G4, G5).
- **The `productId` request field** (`LREQ-GQL-020`). `productId` stays in the selection set
  (`PRODUCT_DETAIL_SELECTION_SET`, `graphql_fixtures.py:193-205`) and in
  `PRODUCT_DETAIL_REQUIRED_MEMBERS` (`:943-951`). No request change.
- **`PRODUCT_DETAIL_ALIAS_MEMBERS` and the `LREQ-GQL-040` missing-identity path.** Left
  unchanged in S1: per R1 (§13), the present-but-empty-`id` edge is a safe non-agreement, not a
  `MISSING_IDENTITY` reclassification.
- **A new interface file, a new failure class, a new config knob, a CLI flag, a new persisted
  field, or a new dependency.** None.
- **Live network in development or tests.** No test calls the endpoint; agents never run
  `niche-scout run`.
- **Editing `plans/chunk-18-...md`** (frozen). Its `:480` golden assumption is **superseded by
  record** in §12.3, not edited.

## 3. Requirements

Chunk 19 has no `requirements-dependency-map.md` §3 section; the LREQs are taken from
`SRS-lean.md` at the cited lines.

| LREQ ID | Role here | Normative text (quoted/derived) | SRS |
|---|---|---|---|
| LREQ-GQL-070 | **Primary** | "If returned GraphQL identity aliases do not agree with the requested canonical identity, the asset SHALL be marked `id_mapping_mismatch` and excluded from D, R, and Q." Option A applies "aliases" to the authoritative returned `id`. | §4.2, 332-334 |
| LREQ-GQL-020 | **Primary (request side)** | "The `ProductDetail` operation SHALL request product identity aliases, `rating.average`, …". `productId` remains requested and persisted; it is not an agreement alias. | §4.2, 294-298 |
| LREQ-GQL-040 | Supporting (Chunk 5 primary) | "… null required data, wrong data shape, wrong scalar type, … or missing identity SHALL be recorded as an operation error." Unchanged in S1; per R1 (§13) a present-but-empty `id` is a safe non-agreement, not a `MISSING_IDENTITY` reclassification. | §4.2, 318-323 |
| LREQ-ID-020 | Supporting (Chunk 6A primary) | "… returned product identifiers are compatible with the requested identity …". The preflight's compatibility check now compares the authoritative `id`. | §4.4, 368-372 |
| LREQ-ID-040 | Integration completion (Chunk 6A primary) | Preflight rates use unique sampled identities as the denominator; `successful` requires the identity check. The fix changes the numerator, not the computation. | §4.4, 386-414 |
| LREQ-TST-030 | Supporting (test coverage) | "Identity tests SHALL cover … GraphQL mismatch …". New nodes cover both directions of the authoritative-`id` rule. | §13, 1235-1237 |
| LREQ-TST-040 | Supporting (test coverage) | "GraphQL tests SHALL cover success, … operation errors, null data, wrong types, … partial success, …". The live-shape success body and the id-agrees/productId-differs success path are added. | §13, 1239-1242 |
| LREQ-SEC-010/020 | Constraint | No secret in any artifact; the captured fixture is public product metadata only; no cookie/header value, no response body persisted. | §4.3, 348-352 |
| LREQ-ARCH-030 | Supporting | Same inputs + policy + config → same outputs; the comparison remains a deterministic pure function of the alias map. | §3 |

Not claimed: the `LREQ-ID-020` caveat that the preflight is "not a statistically representative
validation of all marketplace identity forms" (line 374) is unchanged.

## 4. Frozen-interface amendment (owned by this chunk)

The human ruling (2026-09-25) authorizes this amendment, and interface files are planner-authored
artifacts. `Documents/interfaces/chunk-05.md` §5.8 **is amended in this chunk** (unlike Chunks
17/18, which only recorded conflicts). The amendment:

1. Replace the alias-set sentence at `:543` ("`aliases` is built from `graphql_id` and
   `product_id` when present") with: the agreement alias set is built from the returned `id`
   (`graphql_id`) when present; the returned `productId` is persisted on
   `ProductDetailFields.product_id` and remains in the request (`LREQ-GQL-020`) but is **not** an
   agreement alias.
2. Add a dated `> Recorded amendment (2026-09-25) — Chunk 19` note in §5.8 naming the ruling,
   `plans/chunk-19-...md`, and the fact that `compare_graphql_identity_aliases` semantics are
   unchanged.
3. Add the amended-by line near the file header:
   `Amended by: Documents/plans/chunk-19-graphql-identity-alias-agreement-remediation.md (2026-09-25, ruling Option A).`
   `Status:` stays `VERIFIED`; the amendment is additive and recorded.

No other frozen surface changes. `interfaces/chunk-01.md` and `interfaces/chunk-6A.md` are
consumed unchanged.

## 5. Design

### 5.1 S1 — the authoritative-`id` alias set (exact mechanism)

`collector_graphql.py` `annotate_product_detail_identity` (`:1614-1635`) becomes:

```python
aliases: dict[str, object] = {}
if product_detail.graphql_id is not None:
    aliases["id"] = product_detail.graphql_id
comparison = compare_graphql_identity_aliases(
    requested_identity, aliases, mapping_rule_version=mapping_rule_version
)
return replace(product_detail, identity_comparison=comparison)
```

The `if product_detail.product_id is not None: aliases["productId"] = ...` block is deleted. No
other adapter line changes: `validate_product_detail_payload` still requires and extracts
`productId` (`:1212, 1301`), the draft still persists it (`:2006`), and both call sites
(`:2051-2053`, `:2394-2396`) are unaffected. There is exactly one behavior change: the comparison
map.

The alias key remains `"id"` (not `"graphql_id"`): it is neither a URI field nor an
`_IDENTITY_MEMBER_NAMES` member, so `compare_graphql_identity_aliases` reads it through
`_canonicalize_product_id` (trim, canonical-as-supplied) exactly as before (G2).

### 5.2 Edge behavior under S1

Derived from the frozen pure-function contract (G2) and the unchanged `validate_product_detail_payload`
(G3). `absent` = the key is missing from the payload mapping; `unusable` = `payload.get(key)` is
`None`, non-string, or whitespace-only, so `_usable_string` returns `None` (an absent key also
reads as `unusable` here, but `absent_alias` at `:1219` tests key membership separately);
`product_id` usable means `product_detail.product_id is not None`.

| Returned `id` | Returned `productId` | Operation status (unchanged validator) | Agreement alias map | `identity_match` / preflight class |
|---|---|---|---|---|
| usable, `== requested` | usable, any value (incl. different) | `SUCCESS` | `{"id": <id>}` | **True** / `successful` — **the live shape, the fix** |
| usable, `!= requested` | usable, any value | `SUCCESS` | `{"id": <id>}` | False / `conflicting` |
| key absent | usable | `MISSING_IDENTITY` error (`absent_alias`, `:1219-1229`) | comparison not reached | `other_failed` (operation error) |
| key absent | absent or unusable | `MISSING_IDENTITY` error (`absent_alias` **and** `no_populated_alias`, `:1219-1229`) | comparison not reached | `other_failed` |
| present, `null`/non-string/whitespace-only | absent or unusable | `MISSING_IDENTITY` error (`no_populated_alias`, `:1220-1229`) | comparison not reached | `other_failed` |
| **present, `null`/non-string/whitespace-only** | **usable** | **`SUCCESS` today** (neither `absent_alias` nor `no_populated_alias` fires) | `{}` (empty) | **False / `conflicting`** — safe non-agreement; **R1 (§13)** |

The last row is the Q1-a edge. Under S1 it is a **non-agreement**, never a silent pass: the
empty map makes `compare_graphql_identity_aliases` return `id_mapping_mismatch=True` with reason
"no GraphQL identity alias was returned; a missing alias is not agreement" (G2). **Q1-a (ruled
2026-09-25)** is the implemented behavior: `validate_product_detail_payload` is unchanged, so the
`ProductDetail` operation stays `SUCCESS` and the identity is `conflicting`. It is the minimal
change the ruling authorizes ("only the alias set the adapter supplies changes") and it fails safe
(a conflict stops the run; it never fabricates agreement). No `no_populated_alias`/`identity_usable`
change is made.

### 5.3 S3 — supersede the `id == productId` golden in the durable fixtures

`tests/fixtures/graphql_fixtures.py`:

- Add `GQL_FIXTURE_INTERNAL_PRODUCT_ID: str = "275244114082"` — the captured internal `productId`
  for identity `"117382"` (G6), representative of the live shape.
- `product_detail_payload(...)` (`:343-368`) gains a keyword `product_id: object = None` whose
  `None` default means "the requested identity" (so every existing keyed golden stays
  byte-identical); `"productId"` becomes `asset_identity_key if product_id is None else product_id`.
- `keyless_product_detail_payload` (`:795-813`) passes `product_id=GQL_FIXTURE_INTERNAL_PRODUCT_ID`,
  so the live-shape keyless bodies have `id == requested` and `productId == the distinct internal
  id`. Its docstring and the prose at `:355-357, 765-772` are corrected.
- Add keyed adapter bodies: `authoritative_id_agrees_body()` (payload `id == requested`,
  `productId == GQL_FIXTURE_INTERNAL_PRODUCT_ID`; page views 4321) and
  `authoritative_id_disagrees_body()` (payload `id == GQL_FIXTURE_ASSET_ID_OTHER`,
  `productId == requested`). Add both names to the module `__all__`.

The `id == productId` assumption at `plans/chunk-18-...md:480` is superseded **by record** in
§12.3; the frozen chunk-18 plan is not edited.

### 5.4 No change to rates, persistence, or summary

`pipeline.py` recomputes `identity_match` from the (now id-only) comparison and `compute_preflight_rates`
classifies it; `_build_summary` and `persist_preflight` are untouched. `LREQ-ID-040`'s integration
is completed by the adapter change alone.

## 6. Files touched

No file outside this table is touched.

| File | New/modified | Purpose |
|---|---|---|
| `src/niche_scout/collector_graphql.py` | modified | S1: `annotate_product_detail_identity` supplies only the returned `id`; docstring corrected; a comment at `:936` notes `PRODUCT_DETAIL_ALIAS_MEMBERS` is the required identity-member group, not the agreement set. |
| `Documents/interfaces/chunk-05.md` | modified | §5.8 amendment (§4): alias set is the authoritative returned `id`; dated note; amended-by line. No other section changes. |
| `tests/fixtures/graphql_fixtures.py` | modified | S3: internal-`productId` constant; `product_detail_payload(product_id=...)`; live-shape `keyless_product_detail_payload`; `authoritative_id_agrees_body` / `authoritative_id_disagrees_body`; docstrings; `__all__`. |
| `tests/test_identity.py` | modified | New adapter-level nodes 1–2 and the Q1-a edge node (§8.1). |
| `tests/test_collector.py` | modified | New direct-unit node 3 and the Q1-a edge node 5 (§8.1); update the internal-`productId` assertion at `:3480` (same node ID). |
| `tests/test_identity_preflight.py` | modified | New preflight-level node 4 (§8.1). |
| `tests/traceability.json` | modified | New node keys (§8.1). No renamed key (§8.4). |

**Not touched:** `validation.py`, `models.py`, `database.py`, `pipeline.py`, `report.py`,
`cli.py`, `config.py`, `sampling.py`, `collector.py`, `collector_coveo.py`, `metrics.py`,
`scoring.py`, `src/niche_scout/tools/**`, `pyproject.toml`, `config/**`,
`tests/fixtures/identity_preflight_vectors.py`, `plans/chunk-18-...md`, `AGENTS.md`,
`kilo.json(c)`, `.kilo/`.

## 7. Typed signatures and null/edge behavior

### 7.1 `annotate_product_detail_identity` (signature unchanged; behavior changed)

```python
def annotate_product_detail_identity(
    requested_identity: str,
    product_detail: ProductDetailFields,
    *,
    mapping_rule_version: str = IDENTITY_MAPPING_RULE_VERSION,
) -> ProductDetailFields
```

- Returns a new `ProductDetailFields` (frozen `replace`) with `identity_comparison` set;
  `graphql_id`, `product_id`, and every other field are preserved verbatim.
- `product_detail.graphql_id is not None` → alias map `{"id": graphql_id}`.
- `product_detail.graphql_id is None` → alias map `{}` → the comparison is a **mismatch**
  (`matches_requested_identity is False`, `id_mapping_mismatch is True`, explicit reason), never
  a pass. `product_id` is **never** consulted.
- A non-member `mapping_rule_version` still raises `ValueError` (pure function, `:1522-1525`).
- `product_id` is neither compared nor defaulted: a populated-but-different `productId` yields a
  match; a `None` `product_id` is persisted as `None` and has no effect on the comparison.

### 7.2 `compare_graphql_identity_aliases` (unchanged)

Signature and semantics byte-identical to `interfaces/chunk-01.md` §4 / `validation.py:1497-1620`.
No edit.

### 7.3 `product_detail_payload` (fixture; new keyword only)

```python
def product_detail_payload(
    asset_identity_key: str = GQL_FIXTURE_ASSET_ID, *,
    product_id: object = None,
    rating_average: object = 4.5, rating_count: object = 210, review_count: object = 34,
    state: object = "published", category: object = ..., publisher: object = ...,
) -> dict[str, Any]
```

`product_id is None` reproduces the previous `"productId" == asset_identity_key` output exactly; a
supplied value (including `None` is not distinguishable here) is emitted verbatim; callers that
need a null `productId` set it on the returned mapping.

## 8. Test plan

No live network; every transport is a recording double. Fixtures and failing nodes first
(`test-author`), then the implementation.

### 8.1 Node IDs, markers, traceability

`tests/traceability.json` is node-ID → `[LREQ...]`; markers must equal the values.

| pytest node ID | `@pytest.mark.lreq` | `tests/traceability.json` value |
|---|---|---|
| `tests/test_identity.py::test_authoritative_id_agrees_when_returned_product_id_differs` | `LREQ-GQL-070`, `LREQ-GQL-020` | `["LREQ-GQL-070", "LREQ-GQL-020"]` |
| `tests/test_identity.py::test_authoritative_id_disagrees_when_returned_product_id_agrees` | `LREQ-GQL-070` | `["LREQ-GQL-070"]` |
| `tests/test_collector.py::test_identity_alias_set_compares_authoritative_id_only` | `LREQ-GQL-070` | `["LREQ-GQL-070"]` |
| `tests/test_identity_preflight.py::test_preflight_passes_when_returned_product_id_differs` | `LREQ-ID-020`, `LREQ-GQL-070` | `["LREQ-ID-020", "LREQ-GQL-070"]` |
| `tests/test_identity.py::test_unusable_authoritative_id_is_not_agreement` | `LREQ-GQL-070`, `LREQ-GQL-040` | `["LREQ-GQL-070", "LREQ-GQL-040"]` |

Assertions (`test-author` writes these without the implementation):

- **Node 1 (the fix, adapter level).** One `enrich_asset` for `GQL_FIXTURE_ASSET_ID` over
  `gqlfx.authoritative_id_agrees_body()` (explicit key): `result.correlation.is_fully_correlated`;
  `result.product_detail.is_success`; `draft.graphql_id == GQL_FIXTURE_ASSET_ID`;
  `draft.product_id == GQL_FIXTURE_INTERNAL_PRODUCT_ID` (persisted verbatim, **not** the
  requested identity); `draft.id_mapping_mismatch is False`;
  `"graphql_id_mapping_mismatch" not in {issue.code for issue in result.product_detail.issues}`;
  `result.page_views.is_success`; `draft.product_page_views == 4321`.
- **Node 2 (productId is not authoritative).** Over `gqlfx.authoritative_id_disagrees_body()`:
  `draft.graphql_id == GQL_FIXTURE_ASSET_ID_OTHER`; `draft.product_id == GQL_FIXTURE_ASSET_ID`
  (agrees with the requested identity); `draft.id_mapping_mismatch is True`;
  `"graphql_id_mapping_mismatch" in {issue.code for issue in result.product_detail.issues}`;
  `result.product_detail.is_success` (the mismatch is a flag, not an operation error, and
  `result.product_detail.failure_class is GraphQLFailureClass.NONE`).
- **Node 3 (direct unit, the alias set).** Build a `ProductDetailFields` for the fixture identity
  via `validate_product_detail_payload` and call `annotate_product_detail_identity` directly:
  - `graphql_id == requested`, `product_id == GQL_FIXTURE_INTERNAL_PRODUCT_ID` →
    `comparison.matches_requested_identity is True` and
    `dict(comparison.compared_aliases) == {"id": requested}` (assert the key `"productId"` is
    **absent**).
  - `graphql_id == GQL_FIXTURE_ASSET_ID_OTHER`, `product_id == requested` →
    `comparison.id_mapping_mismatch is True` and
    `dict(comparison.compared_aliases) == {"id": GQL_FIXTURE_ASSET_ID_OTHER}`.
  - `graphql_id is None`, `product_id == GQL_FIXTURE_INTERNAL_PRODUCT_ID` →
    `comparison.id_mapping_mismatch is True`, `comparison.compared_aliases == ()`, reason names
    "no GraphQL identity alias".
  - Assert the emitted request still names `productId`: `"productId" in
    gqlfx.PRODUCT_DETAIL_SELECTION_SET` (request unchanged; `LREQ-GQL-020`).
- **Node 4 (the offline end-to-end proof).** Seed a preflight run (mirror
  `test_run_identity_preflight_uses_chunk5_adapter_per_unique_identity`), serve each selected
  identity a keyless live-shape body
  (`gqlfx.keyless_success_body_for_identity(k).encode("utf-8")`) whose `id == k` and
  `productId == GQL_FIXTURE_INTERNAL_PRODUCT_ID`: `transport.call_count ==` number of unique
  selected identities; every observation `identity_match is True`,
  `product_detail_status == "success"`, `page_views_status == "success"`; `rates.conflicting_unique_identities == 0`;
  `rates.successful_unique_identities == rates.attempted_unique_identities`;
  `rates.success_rate == 1.0`; preflight status `passed`.
- **Node 5 (Q1-a edge, ruled).** Over `gqlfx.authoritative_id_empty_body()` (payload `id == ""`,
  `productId == GQL_FIXTURE_INTERNAL_PRODUCT_ID`, explicit key, page views 4321):
  `result.product_detail.is_success` and `failure_class is GraphQLFailureClass.NONE` (the validator
  is unchanged; a present-but-empty `id` is not `absent_alias` and `product_id` populates
  `no_populated_alias=False`); `draft.graphql_id is None`; `draft.product_id ==
  GQL_FIXTURE_INTERNAL_PRODUCT_ID`; `draft.id_mapping_mismatch is True`;
  `"graphql_id_mapping_mismatch" in {issue.code for issue in result.product_detail.issues}`;
  `result.page_views.is_success`. The identity is a non-agreement, never an operation error.

Existing nodes whose assertions change (node ID and traceability entry unchanged):

- `tests/test_collector.py::test_product_detail_data_product_wrapper_is_unwrapped` — `:3480`
  becomes `assert draft_unwrapped.product_id == gqlfx.GQL_FIXTURE_INTERNAL_PRODUCT_ID`; `:3478`
  (`payload["id"] == GQL_ASSET_ID`) is unchanged. Flat-legacy `:3553` is unchanged (that body uses
  `product_detail_payload()` with the `None` default).

Unaffected, deliberately: `test_correlated_product_detail_reports_alias_mismatch` and
`test_adapter_mismatch_is_a_flag_not_a_metric_exclusion` (both aliases differ → still a mismatch);
`test_missing_returned_identity_is_not_an_implicit_match` and
`test_invalid_state_value_and_missing_identity_are_operation_errors` (missing-identity path
unchanged by S1); `test_preflight_identity_failure_modes[identity_mismatch]` (both aliases differ).

### 8.2 Fixtures and golden vectors

Hand-computed golden from the live capture (identity `117382`, keyless live shape; floats within
`1e-9`):

```text
[{"data":{"product":{"id":"117382","productId":"275244114082","rating":{"average":5.0,"count":4},
"reviewCount":4,"firstPublishedDate":"2018-05-11T21:33:33Z","state":"published",
"category":{"id":"27","name":"Humanoids"},"publisher":{"id":"32451","name":"ZectorLab"}}}},
{"data":{"pageViews":20}}]
```
→ under `VALIDATED_POSITION`: ProductDetail `SUCCESS`, page views `SUCCESS`,
`identity_match is True`, `graphql_id == "117382"`, `product_id == "275244114082"`,
`rating_average == 5.0`, `rating_count == 4`, `review_count == 4`, `product_page_views == 20`,
`id_mapping_mismatch is False`.

Negative golden: the same body with `"id":"999999"` (productId unchanged) → `identity_match is
False`, `conflicting`, `product_detail.is_success`. Third golden: `"id":"117382"`,
`"productId":"999999"` → `identity_match is True` (**the fix**).

The capture is public product metadata only (no credential, cookie, or header value); the fixture
is hand-derived from `.scratch/chunk18-capture.json` (G6). Add the Q1-a edge body
(`authoritative_id_empty_body`: `assert authoritative_id_empty_body() == authoritative_id_agrees_body()`
with the `"id"` member set to `""`; explicit key, page views 4321).

### 8.3 Traceability writes

Add the five node keys in §8.1 with values equal to their markers. No existing key's value changes.

### 8.4 Node-ID renames (traceability moves)

**None.** Verified by counting, not cross-reading (G10): every adapter-level mismatch fixture sets
**both** aliases to the non-requested identity, so no existing node asserts that `productId`
participates in agreement; the one assertion that changes
(`test_collector.py:3480`, internal `productId`) keeps its node ID and its
`tests/traceability.json` key. The `keyless_product_detail_payload` shape change keeps every
fixture-derived node ID. Therefore there is no old-key removal / new-key addition. If a rename
becomes necessary during implementation, it is a scope change: stop and report it.

## 9. Definition of done (gate)

- **DoD-1 (dispatch; human live run).** A human `python -m niche_scout run` reaches and **passes**
  the identity preflight against the live endpoint; the persisted summary shows
  `successful_unique_identities == attempted_unique_identities`, `conflicting_unique_identities == 0`,
  and the run proceeds past the preflight. Not provable offline.
- **DoD-2 (offline suite).** `python -m pytest -q` reports `passed, 0 failed`; the exact command
  and verbatim output are recorded in `Documents/runs/chunk-19.md` with real counts.
- **DoD-3 (validators).** `python -m niche_scout.tools.validate_traceability`,
  `python -m niche_scout.tools.check_import_boundaries`,
  `python -m niche_scout.tools.check_scope_prohibitions`, and
  `python -m niche_scout.tools.check_secrets` all valid (exit 0).
- **DoD-4 (lint).** `ruff` on the changed files with `pyproject.toml` (`line-length = 88`,
  `select = ["E","F","I"]`); no new lint; a pre-existing deviation is reported PARTIAL with the
  unchanged lines named and a byte-exact baseline.
- **DoD-5 (secrets / no live network in tests).** No credential, cookie, or header value in any
  artifact; no test calls the real endpoint; no response body persisted.
- **DoD-6 (records).** Plan, run log, interface amendment, tests, and traceability recorded; the
  R1/R2 rulings recorded in the run log; remaining obligations stay open.

## 10. Prohibitions

- No change to `compare_graphql_identity_aliases`, `validation.py`, or any pure `metrics`/`scoring`
  surface.
- No `productId`-based agreement, no `productId`-as-fallback-identity, and no fabrication of an
  `id` from the request; a missing/unusable authoritative `id` is never agreement.
- No change to the request selection set, `PRODUCT_DETAIL_REQUIRED_MEMBERS`, the DB schema, the
  `LREQ-GQL-040`/`LREQ-GQL-050` classification, or the preflight policy constants.
- No similarity/tolerance matching beyond mapping rule `1.0.1` (no prefix, substring, or
  length-based heuristics).
- No live network in development or tests; no new dependency, config knob, CLI flag, env var, or
  persisted field.
- No edits outside §6, including any other frozen interface, plan, or run document.

## 11. Routing

1. **`test-author`** — S3 fixtures, the failing nodes 1–5, and `tests/traceability.json`
   entries first.
2. **`impl-deep`** — the `annotate_product_detail_identity` alias-set change plus the §4 interface
   amendment already in place; run pytest and the four validators. `impl-fast` is not suitable:
   the change sits on a frozen protocol boundary and the preflight gate, and the direct-unit node
   pins the public comparison map.
3. **Human live run** — DoD-1.
4. **`spec-reviewer`** — review the plan, the interface amendment, tests, implementation, and the
   live-run evidence in `Documents/runs/chunk-19.md`.

## 12. Residual risks and open obligations (recorded, never fixed here)

### 12.1 Residual risks (lead's next-stage findings; recorded only)

- **Zero-tolerance conflict gate.** `IDENTITY_PREFLIGHT_MAX_CONFLICT_RATE = 0`
  (`LREQ-ID-030`, SRS 382) means a single id mismatch fails the run. This chunk does not relax it.
- **Correlation-mode selection skipped when any response is `None`.** `pipeline.py:1142-1148`
  selects the mode only when every response is non-`None`; a partial transport failure keeps the
  candidate mode. Recorded; not changed.
- **Request-side `pageViews` alias not yet live-confirmed.** Chunk 18's G7 alias is pinned by
  offline goldens; the captured body used the pre-G7 `productPageViews` key. DoD-1 observes the
  post-fix live shape. Recorded.
- **`QUALITY_MIN_RATING_COUNT = 5` vs live rating counts 0–4.** Most captured identities have
  `rating.count` 0–4, so Q is unavailable for them downstream. Not a Chunk 19 concern; recorded.
- **`MIN_AGE_DAYS_FOR_RATE = 30`.** Some captured `firstPublishedDate` values are younger than 30
  days, so R is unavailable for them. Recorded.
- **8-category runs never rankable.** `LREQ-SMP` provisional rules give an empty candidate set and
  `null` stability for a minimum-size run. Recorded.
- **Bulk identities outside the capture are not proven.** Only the ten selected preflight
  identities were captured; the authoritative-`id` rule is grounded on those ten. Recorded.

### 12.2 Open obligations (recorded, never closed here)

- **URI trailing-identifier extraction (`identity_mapping_rule 1.0.1`)** — inferred, not verified
  against a real Coveo response; no captured response exists.
- **OI-6 — CSRF/session sufficiency** — has no owning chunk; neither reopened nor closed.
- **`runs.taxonomy_sha256` empty-hash rejection** — owner Chunk 10; not touched.
- **`tests/AGENTS.md` traceability orientation** — prose says LREQ-keyed; the committed file is
  node-ID-keyed. Out of scope; follow the committed file.

### 12.3 Superseded assumption (recorded; the frozen chunk-18 plan is not edited)

- `plans/chunk-18-...md:480` golden assumed `"id":"117382","productId":"117382"` (`id ==
  productId`). `.scratch/chunk18-capture.json` (G6) shows `productId` is a distinct long internal
  id for all ten identities. The durable fixture now carries the live shape (§5.3); the chunk-18
  plan text stands as the historical record of the pre-capture assumption.

## 13. Resolved rulings (2026-09-25) — no open questions remain

**R1 = Q1-a (safe non-agreement), ruled 2026-09-25.** A present-but-empty/non-string
authoritative `id` (`""`, whitespace-only, or non-string) with a populated `productId` is a **safe
non-agreement**: the alias map is `{}`, the comparison is a mismatch → `identity_match is False` /
`conflicting`, and the `ProductDetail` operation stays `SUCCESS`. `validate_product_detail_payload`'s
`no_populated_alias`/`identity_usable` (`collector_graphql.py:1220, :1323`) are **not** made
`id`-based and no `MISSING_IDENTITY` reclassification is added. Implemented by S1 alone; test node 5
(`tests/test_identity.py::test_unusable_authoritative_id_is_not_agreement`) pins the ruled behavior.
The alternative reading (Q1-b, `MISSING_IDENTITY`) was considered and **not** adopted; it remains a
possible future tightening only if a human re-opens it.

**R2 = Q2 (no diagnostic), ruled 2026-09-25.** A populated-but-different `productId` emits no extra
warning; the existing `id_mapping_mismatch`/`GRAPHQL_ID_MAPPING_MISMATCH` vocabulary is untouched.
`productId` is persisted on `draft.product_id`/`enrichment_observations.product_id` and nothing more.

## 14. Conflict notes

- `interfaces/chunk-05.md` §5.8 (pre-amendment alias-set sentence at `:543`) — amended by this
  chunk (§4); recorded in the interface file itself.
- `plans/chunk-18-...md:480` — superseded by record (§12.3); the frozen plan is not edited.
- `plans/chunk-05-...md:2989-2995` — the "confirmed against a real capture" reopening condition is
  met; the member list is confirmed to be an over-broad **agreement** set while remaining the
  correct **request/required-member** set. Recorded.