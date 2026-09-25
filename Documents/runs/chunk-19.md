# Chunk 19 — run log (GraphQL identity-alias agreement remediation, post-Chunk-18)

Post-completion remediation requested by the human after the Chunk 18 DoD-1 live run
(`python -m niche_scout run`) reached the identity preflight, got HTTP 200, and **failed**
with `attempted=10, successful=0, conflicting=10` (conflict rate 1.0 > 0). Chunk 17 fixed
CSRF/query shape; Chunk 18 fixed correlation and the `data.product` unwrap; this is a new,
distinct defect in the identity-agreement rule. Labeled chunk (same pattern as Chunks
14–18): no dependency-map §3 gate row; the dispatch DoD is the gate.

Goal (dispatch): make a live run reach and **pass** the identity preflight by correcting the
identity-agreement rule so the authoritative returned `id` is the compared identity, with
`productId` still requested and persisted but not required to agree.

Plan: `Documents/plans/chunk-19-graphql-identity-alias-agreement-remediation.md`
(to be written by `chunk-planner`).

## Human ruling (2026-09-25) — approved

The human approved the lead's independent analysis recommendation, **Option A**: `id` is the
authoritative returned identity for `LREQ-GQL-070` agreement; `productId` remains in the
`ProductDetail` request (`LREQ-GQL-020`) and is persisted, but is not an agreement alias. The
frozen `interfaces/chunk-05.md` §5.8 contract (line 543: "`aliases` is built from
`graphql_id` and `product_id` when present") is **amended** by this remediation; the Chunk 1
pure contract `compare_graphql_identity_aliases` keeps its "every supplied alias agrees"
semantics unchanged.

## Preflight

| Check | Result |
|---|---|
| Working tree | clean at start (`git status --short` → no output; branch `main`; HEAD `c54cefc`) |
| Branch | created `chunk-19` off `main` @ `c54cefc` (succeeded) |
| Prerequisite `interfaces/chunk-01.md` | `Status: VERIFIED` |
| Prerequisite `interfaces/chunk-05.md` | `Status: VERIFIED` |
| Prerequisite `interfaces/chunk-6A.md` | `Status: VERIFIED` |
| Routing | adapter protocol + pure-comparison caller, so tests-first is expected; implementer per frozen plan |

## Root cause (lead, independently re-derived)

The adapter feeds **both** returned aliases to Chunk 1's comparison, and that comparison
requires **every** canonicalized alias to equal the requested identity:

| Step | Evidence (read) |
|---|---|
| `annotate_product_detail_identity` adds `id` and `productId` | `collector_graphql.py:1627-1634` |
| `PRODUCT_DETAIL_ALIAS_MEMBERS = ("id", "productId")` | `collector_graphql.py:936` |
| "every canonicalized alias agreed"; non-agreeing recorded | `validation.py:1506-1508, 1564-1567` |
| `identity_match=False` ⇒ `conflicting` | `pipeline.py:431-434`; `pipeline.py:576-598, 658` |
| `identity_match` from `matches_requested_identity` | `pipeline.py:592-593` |

Live, the two aliases are different identifiers, so no requested key can satisfy both:

| Evidence | Content |
|---|---|
| `.scratch/chunk18-capture.json` (counted across all 10 selected identities) | `product.id` == requested package id (e.g. `"117382"`); `product.productId` == a distinct long internal id (e.g. `"275244114082"`); each body `matches_recorded: true` against the failed run's persisted `response_sha256` |
| Retired parent SRS `retired-documents/SRS-revision2.md:476` | `id_mapping_mismatch` is set when the returned **`id`** differs from the requested `asset_identity_key` |
| `retired-documents/SRS-revision2.md:163` (OI-4) | `productId`/`itemId` are *different* identifiers from the query-accepted `id` |
| `retired-documents/SRS-revision2.md:80` | package id is assumed equal to Coveo `ec_product_id`/`permanentid` |
| `plans/chunk-05-...md:2989-2995` | the alias member list was an assumption "to be confirmed against a real capture" |

The Chunk 18 DoD-1 live run is that confirmation; it falsifies the assumption.

## Stage log

| Stage | Status | Session / evidence |
|---|---|---|
| Preflight (lead) | DONE | table above |
| Recon / root cause (lead) | DONE | chain above; human ruled Option A |
| Plan — `chunk-planner` | **FROZEN** | `ses_f282acf80ffeVl6rup2GFOR8e4`. Wrote `Documents/plans/chunk-19-graphql-identity-alias-agreement-remediation.md` (DRAFT→FROZEN after the human answered Q1/Q2) and amended `Documents/interfaces/chunk-05.md` §5.8 per the human ruling. Root cause re-verified against source and `.scratch/chunk18-capture.json`. Routing: `test-author` then `impl-deep`. |
| Tests — `test-author` | DONE | `ses_f280cff12ffepEtampAXi87CHC` (two passes; first hit the step cap after one fixture edit, resumed). Fixtures: `graphql_fixtures.py` (internal-productId constant, `product_detail_payload(product_id=...)`, live-shape keyless payload, three authoritative-id bodies); 5 new nodes (4 `test_identity.py`/`test_collector.py`/`test_identity_preflight.py` discriminator + 1 Q1-a edge); one same-ID supersession at `test_collector.py:3480`; 5 `traceability.json` keys, no renames. |
| Tests — red state (lead) | DONE | `python -m pytest -q` → **4 failed, 654 passed in 22.76s** (behavioral `AssertionError`s only; no syntax/collection errors). `python -m niche_scout.tools.validate_traceability` → valid, `639 matrix nodes`. `git status --short` → the five `tests/` files only. |
| Implement — `impl-deep` | DONE | `ses_f27e908a7ffe8b93HPWxtFd5oQ`. `annotate_product_detail_identity` builds the agreement alias map from `graphql_id` alone; `product_id` no longer added; comment on `PRODUCT_DETAIL_ALIAS_MEMBERS` records it is the required/absent group, not the agreement set. `compare_graphql_identity_aliases` and `validation.py` untouched. Only `src/niche_scout/collector_graphql.py` changed (+17/-2). |
| Lead verify (step 6) | DONE | `python -m pytest -q` → **658 passed in 22.61s**; `validate_traceability` → valid (`639 matrix nodes`); `check_import_boundaries` valid; `check_scope_prohibitions` valid; `check_secrets` valid; `python -m ruff check src/niche_scout/collector_graphql.py` → `All checks passed!`; `git diff --stat` → exactly `collector_graphql.py` (+17/-2). |

### Plan inconsistency (Minor, resolved by lead ruling, no plan edit)

`plans/chunk-19-...md` §6's `test_collector.py` row says it gets "the Q1-a edge node 5", while §8.1's node table and §13 pin node 5 as `tests/test_identity.py::test_unusable_authoritative_id_is_not_agreement`. The lead directed the test-author to follow the explicit node ID in §8.1/§13 (option a) and create no duplicate; recorded here as a plan-text typo, not an interface change.

## Human rulings (2026-09-25) — resolved

- **Q1 = Q1-a.** Present-but-empty/non-string authoritative `id` with a populated `productId` is a safe non-agreement: alias map `{}` → mismatch/`conflicting`, `ProductDetail` stays `SUCCESS`; `validate_product_detail_payload`'s `no_populated_alias`/`identity_usable` unchanged.
- **Q2 = no diagnostic.** A populated-but-different `productId` emits no extra warning; the existing `id_mapping_mismatch`/`GRAPHQL_ID_MAPPING_MISMATCH` vocabulary is untouched.