# Chunk 1 — Pure taxonomy, identity, and response validation

Status: FROZEN
Re-verification state: NOT RE-VERIFIED against the 2026-09-18 interface text —
  required and not performed (corrected 2026-09-18: the observations below were
  taken against `Documents/interfaces/chunk-01.md` as it stood before that
  file's §4.1 was amended; the observations themselves are unchanged and have
  not been withdrawn).
Interface observations from the prior gate pass, quoted as they were recorded
  (superseded 2026-09-18: these observations previously appeared as a
  `Status: VERIFIED` line — "Documents/interfaces/chunk-01.md (Status: VERIFIED
  — pure `validation.py` surface: typed results, identity candidates,
  canonicalization rule `1.0.0`, GraphQL alias comparison, structural
  validation, redaction)". The observations were made against the pre-2026-09-18
  text; re-verification against the amended text is required and has NOT been
  performed, so this plan does not currently assert that its `1.0.0`-era
  observations still hold):
  Documents/interfaces/chunk-01.md (pure `validation.py` surface: typed results,
  identity candidates, canonicalization rule `1.0.0`, GraphQL alias comparison,
  structural validation, redaction)
Depends on (frozen interfaces required before this plan can be trusted):
  Documents/interfaces/chunk-00.md (Status: VERIFIED — package layout, `models.py`
  typed structures/enums/constants, `config.py` contracts, `database.py` schema
  specification only, pure `metrics.py`/`scoring.py` stubs, traceability tooling,
  test fixtures)
Blocks (chunks whose plan/implementation needs this chunk's interface):
  Chunk 3 (Coveo discovery adapter — integration completion of the LREQ-EXT-*
    primitives), Chunk 4A (canonical populations and deterministic sampling —
    consumes canonical identity + taxonomy matching), Chunk 5 (GraphQL protocol
    adapter — integration completion of LREQ-GQL-060/070 primitives), Chunk 6A
    (identity preflight — consumes identity comparison), Chunk 6B (unique
    enrichment identity units), Chunk 7A (metric eligibility — consumes Chunk 1
    structural primitives and provides the eligibility completion for
    LREQ-MET-010 / LREQ-GQL-060 / LREQ-GQL-070), Chunk 12 (CLI validation and
    exit-code behavior)

## 1. Goal

Establish the pure, deterministic taxonomy, identity, category-membership, and
response-structure validation primitives that every network adapter, sampler, and
metric layer builds on, so that no collector, sampler, or estimator has to invent
its own interpretation of a taxonomy file, an identity candidate, a category path,
or a malformed response value. This chunk makes it true that a taxonomy cache can be
schema-checked and freshness-checked before any network request, that raw
`ec_product_id` / `permanentid` / response-level `clickUri` / response-level `uri`
candidates can be canonicalized under one versioned mapping rule and classified as
`resolved`, `conflict`, or `unresolved` (never silently ordinary assets), that exact
category membership is decided against the canonical taxonomy without prefix
matching on parent paths and with scalar and multi-valued category shapes handled
explicitly, that returned GraphQL identity aliases can be compared against a
requested canonical identity, and that malformed/missing/redacted response data is
represented as an explicit typed state rather than a zero or a default. Adapter
integration of these primitives is completed later in Chunks 3 and 5; metric
eligibility semantics are owned by Chunk 7A.

## 2. Scope

### In scope

- Taxonomy file schema validation: required header fields (`schema_version`,
  `captured_at_utc`, `source_url`, `template_sha256`), a canonical category-path
  inventory, and per-entry category-path shape (LREQ-EXT-020).
- Taxonomy freshness validation: comparison of `captured_at_utc` against a
  caller-supplied timezone-aware UTC reference and `max_taxonomy_age_days`, with
  stale / future / missing / naive timestamps classified explicitly and never
  treated as absent (LREQ-EXT-020). Freshness is **inclusive at the boundary**:
  `age <= max_taxonomy_age_days` is fresh and `age > max_taxonomy_age_days` is
  stale (resolved decision R-5, section 12). The call-site timestamp is supplied by
  the caller as an explicit timezone-aware UTC `reference_utc` argument; which
  concrete timestamp the orchestration layer passes is a Chunk 10/12 decision and is
  deliberately not pinned down by this plan.
- Requested-category presence validation: every requested category must be present
  in the taxonomy inventory; absence is an explicit validation failure that aborts
  before collection, not an empty category (LREQ-EXT-020).
- Exact category-path matching against the canonical taxonomy, including
  normalization rules, explicit non-matching of parent/child prefixes, and explicit
  handling of scalar and multi-valued category response shapes (LREQ-EXT-080).
- Category filter validation status derivation (`verified` / `mismatch` /
  `unverified`) for a category value, using the Chunk 0 enum (LREQ-EXT-080).
- Canonical identity candidate collection from `ec_product_id`, `permanentid`,
  response-level `clickUri`, and response-level `uri`, retaining every non-empty
  candidate (LREQ-EXT-060).
- Canonicalization of every parseable candidate under mapping rule
  `IDENTITY_MAPPING_RULE_VERSION = "1.0.1"`, whose normative content is fixed by
  resolved decision R-2 (section 12) (`superseded 2026-09-18: this bullet
  previously cited `IDENTITY_MAPPING_RULE_VERSION = "1.0.0"`; `1.0.1` is a bug
  fix to the equality comparison only — see section 5.2): `ec_product_id` and
  `permanentid` are treated as
  already-canonical and compared directly after whitespace trimming (as integers
  when both parse as numeric, else as strings); `clickUri`/`uri` contribute the
  trailing numeric identifier after the final `-` in the URL's last path segment,
  and a value not fitting that pattern contributes nothing rather than a wrong
  candidate (LREQ-EXT-060).
- Agreement/conflict/unresolved classification: all successfully-derived canonical
  candidates agree → a canonical `asset_identity_key` with
  `IdentityResolutionStatus.resolved`; any disagreement between derived candidates →
  `conflict` with an explicit conflict reason; nothing derivable from any candidate
  → `unresolved` (LREQ-EXT-070). The comparison/conflict logic is settled (it
  follows directly from LREQ-EXT-070's wording — resolved decision R-2).
- Excluded-from-denominator semantics as typed flags on the identity result
  (`included_in_canonical_denominator`, `included_in_enrichment_set`) so that
  conflict/unresolved records are never silently treated as ordinary assets
  (LREQ-EXT-070).
- GraphQL identity alias comparison: comparison of returned aliases
  (`graphql_id`, `product_id`, plus any canonicalizable alias value) against the
  requested canonical identity, producing `id_mapping_mismatch` plus a typed reason
  (LREQ-GQL-070), and a pure state-eligibility annotation distinguishing `published`
  from excluded/unknown states (LREQ-GQL-060).
- Structural response validation primitives: malformed shape (missing response
  object/member, wrong container kind), wrong scalar type, null required member,
  identity-candidate extraction/aliases, taxonomy shape, and structured redacted
  error summaries (LREQ-MET-010 structural half).
- Typed validation results and typed validation issues (code + redacted message +
  JSON-safe context) returned from every public function.

### Explicitly out of scope (and who owns it instead)

- **Network collection, HTTP clients, request building, pagination, rate limiting,
  retry/backoff**: Chunk 1 is the **supporting contract chunk**; the **primary
  implementation chunk** for Coveo discovery is **Chunk 3** and for GraphQL
  enrichment is **Chunk 5**, which are also the **integration completion chunks**
  for the response-level requirements below.
- **LREQ-EXT-060 and LREQ-EXT-080 integration completion**: Chunk 1 owns the
  **supporting contracts** (pure candidate collection, canonicalization, exact
  matching) only. Chunk 3 is the **integration completion chunk** and is the
  **primary owner of LREQ-EXT-080**; the primitive contracts alone do not satisfy
  either requirement.
- **Retry/backoff, rate limiting, and credential behavior**: owned by Chunk 3
  (primary implementation chunk), with Chunk 0 holding the supporting contract.
  `LREQ-EXT-100` is **not this chunk's requirement** — its matrix row names only
  `Chunk 0` as a supporting chunk — and this plan deliberately does not list,
  test, or claim any part of it.
- **Traceability-validator widening**: deferred to **Chunk 13** (primary owner of
  `LREQ-NFR-060`). `src/niche_scout/tools/validate_traceability.py` stays a Chunk 0
  deliverable and is **not** modified or widened by Chunk 1 (resolved decision R-3,
  section 12).
- **LREQ-EXT-070 (identity conflict/unresolved `Pure` logic)**: Chunk 1 is the
  **primary implementation chunk** for the pure classification primitive; the
  requirement's **completion chunk** is **Chunk 3**, which applies it to real
  discovery records (persisted `identity_resolution_status`, exclusion from the
  canonical denominator and enrichment set at runtime).
- **LREQ-GQL-060 and LREQ-GQL-070**: Chunk 1 owns the **supporting contract**
  (pure alias comparison and state-eligibility annotation). The **primary owner of
  LREQ-GQL-070** is **Chunk 5** (adapter behavior: marking the asset
  `id_mapping_mismatch`), and the **primary owner of LREQ-GQL-060** is **Chunk 7A**
  (metric eligibility). **Metric eligibility semantics** — published-state
  eligibility decisions for D, R, and Q, UTC/date normalization, future-date
  rejection, finite/non-negative checks, minimum-age rules, and page-view
  eligibility — are **owned by Chunk 7A**, and the **metric-eligibility portion of
  LREQ-GQL-060 and the metric identity-mismatch eligibility portion of LREQ-GQL-070
  are not complete until Chunk 7A applies them to metric inputs**. Chunk 5 also
  completes GraphQL response validation and correlation, does not decide metric
  eligibility, and does not perform bulk enrichment.
- **LREQ-MET-010**: Chunk 1 is the **supporting contract chunk** supplying only the
  *structural* malformed-shape / wrong-type / alias checks. The **primary
  implementation chunk** and completion chunk is **Chunk 7A**, which owns the
  semantic decision about whether a value contributes to a metric (null, malformed,
  wrong type, invalid range, future, naive, negative, non-finite, and
  excluded-state values).
- **Identity preflight execution, gate policy, and bulk enrichment**: owned by
  Chunks 6A and 6B (primary implementation chunks). Chunk 1 supplies only pure
  comparison primitives.
- **Canonical population construction, ordinal ordering, strata, and sampling**:
  owned by Chunk 4A (primary implementation chunk).
- **SQLite persistence, transactions, and streamed insertion**: owned by Chunk 2
  (primary implementation chunk). Chunk 1 performs no persistence.
- **Filesystem reading of the taxonomy cache**: `pathlib`/JSON reads of
  `config/category_taxonomy.json` happen in `config.py` (Chunk 0 contract) and in
  the pipeline/CLI orchestration chunks (Chunks 10 and 12), which feed typed data
  into this chunk's pure validators.

## 3. Requirements this chunk must satisfy

**Inclusion rule (both directions).** No LREQ ID may appear in this plan unless
an actual ownership-matrix row in `Documents/requirements-dependency-map.md`
(lines 45–135) names Chunk 1 — as **primary owner**, **supporting chunk**, or
**completion chunk**. The rule is applied in both directions:

- **Nothing missing**: every matrix row that names Chunk 1 appears in the table
  below.
- **Nothing extra**: no other LREQ ID appears anywhere in this plan — not in the
  table, not in the test plan, not in an "excluded tests" list, not in section 12.
  An LREQ mentioned in the Chunk 1 **Requirements:** block prose or in any other
  source without a matrix row naming Chunk 1 is **not** part of this chunk's scope.

This table reconciles the dependency map's `Chunk 1` **Requirements:** block
(lines 461–466) with every ownership-matrix row naming Chunk 1 (line numbers
below are the matrix rows at lines 45–135):

- Primary owner: `LREQ-EXT-020` (line 51), `LREQ-EXT-070` (line 56).
- Supporting chunk: `LREQ-EXT-010` (line 50), `LREQ-EXT-030` (line 52),
  `LREQ-EXT-040` (line 53), `LREQ-EXT-050` (line 54), `LREQ-EXT-060` (line 55),
  `LREQ-EXT-080` (line 57), `LREQ-EXT-090` (line 58), `LREQ-GQL-010` (line 60),
  `LREQ-GQL-020` (line 61), `LREQ-GQL-030` (line 62), `LREQ-GQL-040` (line 63),
  `LREQ-GQL-050` (line 64), `LREQ-GQL-060` (line 65), `LREQ-GQL-070` (line 66),
  `LREQ-ID-020` (line 71), `LREQ-SMP-010` (line 74), `LREQ-MET-010` (line 83),
  `LREQ-CLI-040` (line 120), `LREQ-TST-030` (line 129).
- `LREQ-EXT-100` (line 59) is **deliberately absent**: its matrix row lists
  supporting chunks `Chunk 0` only, so it is not this chunk's requirement and must
  not appear anywhere in this plan.
- The **Requirements:** block names `LREQ-EXT-020`, `LREQ-EXT-060`,
  `LREQ-EXT-070`, `LREQ-EXT-080`, `LREQ-GQL-060`, `LREQ-GQL-070`, `LREQ-MET-010`.
  The matrix adds the remaining rows listed above as **supporting-chunk** rows. Per
  `plan-writer.md`, every ownership-matrix row that names this chunk is part of this
  chunk's LREQ list, so both sets are carried below with their distinct roles.
- Which of the matrix-only supporting rows carry a **Chunk 1-authored test in this
  chunk** versus being satisfied by required tests owned elsewhere is settled in
  section 9 (resolved decision R-1, section 12): Chunk 1 authors tests only for
  `LREQ-EXT-050`, `LREQ-EXT-090`, `LREQ-GQL-010`, `LREQ-GQL-040`,
  `LREQ-GQL-050`, `LREQ-ID-020`, and `LREQ-SMP-010`; `LREQ-GQL-020` and
  `LREQ-GQL-030` are **deliberately excluded** from Chunk 1 testing (pure
  protocol/query-construction and response-correlation concerns with no
  Chunk-1-owned structural or identity angle); `LREQ-EXT-010`, `LREQ-EXT-030`,
  `LREQ-EXT-040`, and `LREQ-CLI-040` correctly get no Chunk 1 test because their
  required tests belong to Chunks 3 and 12.

| LREQ ID | Ownership role here | Normative text (from SRS-lean.md, quoted/derived) | SRS section |
|---|---|---|---|
| LREQ-EXT-020 | **Primary owner** (supporting chunk: Chunk 0; completion chunk: Chunk 3) | "The cached taxonomy file SHALL include `schema_version`, `captured_at_utc`, `source_url`, `template_sha256`, and a canonical category-path inventory. The system SHALL abort before collection if the file is missing, malformed, stale, or does not contain every requested category." (Derived: the pure half — schema validation, freshness validation against a supplied timezone-aware UTC reference and `MAX_TAXONOMY_AGE_DAYS`, and requested-category presence — is this chunk's; the file read and the abort are Chunk 3/Chunk 12 orchestration.) | §4.1 |
| LREQ-EXT-060 | Supporting contract chunk (primary owner: Chunk 3; completion: Chunk 3) | "Each discovery record SHALL retain all non-empty identity candidates from `ec_product_id`, `permanentid`, response-level `clickUri`, and response-level `uri`. Candidates SHALL be canonicalized under one versioned mapping rule." | §4.1 |
| LREQ-EXT-070 | **Primary owner** (supporting chunk: Chunk 2; completion chunk: Chunk 3) | "If canonical candidates disagree, the record SHALL be marked `conflict` and excluded from the canonical denominator and enrichment set. If no candidate can be canonicalized, it SHALL be marked `unresolved`. Neither case may be silently treated as an ordinary asset." | §4.1 |
| LREQ-EXT-080 | Supporting contract chunk (primary owner: Chunk 3; completion: Chunk 3) | "Exact category membership SHALL be checked against the canonical taxonomy. Parent paths SHALL NOT match child paths merely by prefix. Scalar and multi-valued category response shapes SHALL be handled explicitly." | §4.1 |
| LREQ-GQL-060 | Supporting contract chunk (primary owner: Chunk 7A; supporting chunk: Chunk 5; completion: Chunk 5, Chunk 7A) | "Only `state = \"published\"` assets are eligible for D, R, and Q. State-excluded and state-unknown assets remain part of discovered breadth." (Chunk 1 derives only the pure alias/state annotation primitive; the eligibility decision applied to metric inputs is Chunk 7A's.) | §4.2 |
| LREQ-GQL-070 | Supporting contract chunk (primary owner: Chunk 5; completion: Chunk 5, Chunk 7A) | "If returned GraphQL identity aliases do not agree with the requested canonical identity, the asset SHALL be marked `id_mapping_mismatch` and excluded from D, R, and Q." (Chunk 1 derives the pure comparison that produces the mismatch flag and reason; Chunk 5 marks the persisted asset and Chunk 7A completes the metric exclusion.) | §4.2 |
| LREQ-MET-010 | Supporting contract chunk (primary owner: Chunk 7A; supporting chunk: Chunk 5; completion: Chunk 7A) | "A product-level value is usable only when its type, range, state, identity, and timestamp conditions for the relevant metric pass. Null, malformed, future, naive, negative, non-finite, or state-excluded values SHALL be unavailable." (Per the dependency map's edge-case column for LREQ-MET-010: "Structural validation is supplied by Chunk 1; Chunk 7A owns metric eligibility semantics".) | §7.1 |
| LREQ-EXT-010 | Matrix-only supporting row (primary owner: Chunk 3; completion: Chunk 3) | "Discovery SHALL use the parent SRS Coveo endpoint, required headers, captured taxonomy template, and selected-category facet mechanism." (Chunk 1 supplies no endpoint/header behavior; any contribution is limited to taxonomy-template shape consumed through LREQ-EXT-020.) | §4.1 |
| LREQ-EXT-030 | Matrix-only supporting row (primary owner: Chunk 3; completion: Chunk 3) | "The Coveo request SHALL contain no free-text `q` or `query` field that could contaminate category filtering with keyword relevance." (No Chunk 1 behavior identified; no Chunk 1 test — see the deliberate-exclusion note below the table.) | §4.1 |
| LREQ-EXT-040 | Matrix-only supporting row (primary owner: Chunk 3; completion: Chunk 3) | "Discovery SHALL use the parent SRS discovery-only field set: `permanentid`, `ec_product_id`, `ec_name`, `ec_category`, and `publisher_name`. Product rating, page views, publication date, and price SHALL NOT be sourced from Coveo for scoring." (No Chunk 1 behavior identified; no Chunk 1 test — see the deliberate-exclusion note below the table.) | §4.1 |
| LREQ-EXT-050 | Matrix-only supporting row (primary owner: Chunk 3; completion: Chunk 3) | "For every requested category, discovery SHALL retrieve all available pages using the same endpoint, filters, sort order, page size, pagination rules, and category predicate. It SHALL stop when the verified `totalCount` is reached, the endpoint returns a natural terminal page, or `MAX_DISCOVERY_RESULTS_PER_CATEGORY` is reached. The discovery status SHALL be one of `complete`, `truncated`, `page_failed`, `filter_unverified`, `category_mismatch`, `identity_incomplete`, or `request_failed`; a failed or truncated page SHALL never be interpreted as zero assets." (Chunk 1 supplies only the reason vocabulary used for `category_mismatch` / `identity_incomplete`.) | §4.1 |
| LREQ-EXT-090 | Matrix-only supporting row (primary owner: Chunk 3; completion: Chunk 10) | "A failed page, unverified filter, category mismatch, or material identity incompleteness SHALL generate a warning and SHALL prevent a fully rankable competition result for that category." (Chunk 1 supplies the unverified/mismatch classification that produces the condition, not the warning or rankability outcome.) | §4.1 |
| LREQ-GQL-010 | Matrix-only supporting row (primary owner: Chunk 5; completion: Chunk 5) | "Enrichment SHALL use the parent SRS GraphQL batch endpoint and the two required operations: `ProductDetail(id: ID!)` and `ProductPageViews(packageId: String!)`. Both operations SHALL use the same canonical `asset_identity_key`." (Chunk 1 contributes the shared canonical `asset_identity_key` type/validator the adapter consumes.) | §4.2 |
| LREQ-GQL-020 | Matrix-only supporting row (primary owner: Chunk 5; completion: Chunk 5) | "The `ProductDetail` operation SHALL request product identity aliases, `rating.average`, `rating.count`, `reviewCount`, `firstPublishedDate`, `state`, `category`, and `publisher`. The separate `ProductPageViews` operation SHALL request its page-view scalar. Fields not required by scoring MAY be omitted from the lean implementation." (**No Chunk 1 behavior and no Chunk 1 test** — this is pure protocol/query construction, owned by Chunk 5; see the deliberate-exclusion note below the table and section 9.) | §4.2 |
| LREQ-GQL-030 | Matrix-only supporting row (primary owner: Chunk 5; completion: Chunk 5) | "GraphQL response items SHALL be associated by explicit operation name or another validated correlation key. Response position alone SHALL NOT be trusted unless separately validated as an endpoint guarantee. […] Missing, duplicated, unknown, or ambiguous associations SHALL be recorded as malformed operation results; the implementation SHALL never guess from response position. […] The persisted correlation mode SHALL be either `explicit_key` or `validated_position`. If neither mode is validated, both operations SHALL be marked malformed and their fields SHALL remain unavailable." (**No Chunk 1 test** — response correlation is pure protocol behavior owned by Chunk 5; see the deliberate-exclusion note below the table and section 9. The structural malformed-result type Chunk 1 supplies is exercised under LREQ-GQL-040.) | §4.2 |
| LREQ-GQL-040 | Matrix-only supporting row (primary owner: Chunk 5; completion: Chunk 5) | "Each operation SHALL have an independent status. HTTP failures, top-level GraphQL `errors`, HTTP 200 responses with an operation-level `errors` member, null required data, wrong data shape, wrong scalar type, boolean/negative/non-finite page views, invalid state values, or missing identity SHALL be recorded as an operation error. A top-level error SHALL not be treated as a successful operation merely because another operation in the same response succeeded." (Chunk 1 supplies the structural half: shape, type, null-required-member, and missing-identity checks; operation-status recording is Chunk 5's.) | §4.2 |
| LREQ-GQL-050 | Matrix-only supporting row (primary owner: Chunk 5; completion: Chunk 5) | "A valid operation's fields MAY be retained when the other operation fails. Failed fields SHALL remain null or unavailable; they SHALL NOT be filled with zero or another default." (Chunk 1 enforces the "no fabricated default" rule inside its own typed results.) | §4.2 |
| LREQ-ID-020 | Matrix-only supporting row (primary owner: Chunk 6A; completion: Chunk 6A) | "The preflight SHALL perform the normal GraphQL request and verify: the request identifier is accepted by both operations; returned product identifiers are compatible with the requested identity; the page-view operation is associated with the requested package identifier; the operation-correlation mode is valid; and no unexplained response-shape or operation-association error occurred." (Chunk 1 supplies the pure identity-compatibility comparison; preflight execution is Chunk 6A's.) | §4.4 |
| LREQ-SMP-010 | Matrix-only supporting row (primary owner: Chunk 4A; completion: Chunk 4A) | "Sampling SHALL occur only after canonical discovery identities have been resolved and duplicates have been marked." (Chunk 1 supplies the resolution status and denominator-membership flags; population construction and duplicate marking are Chunk 4A's. The dependency map notes sampling occurs "only after canonical identity resolution; conflict/unresolved records excluded".) | §5.1 |
| LREQ-CLI-040 | Matrix-only supporting row (primary owner: Chunk 12; completion: Chunk 12) | "The pipeline SHALL reject a run with fewer than `MIN_CATEGORIES_PER_RUN` requested categories before producing a ranking. It SHALL retain a completed run's collection timestamp and explicit limitations in the report." (Chunk 1 supplies the typed validation result that rejected/invalid input is reported through; run rejection and report retention are Chunk 12's. Correctly **no Chunk 1 test**.) | §10 |
| LREQ-TST-030 | Matrix-only supporting row (primary owner: Chunk 13; completion: Chunk 13) | "Identity tests SHALL cover valid canonical candidates, malformed fallback, unresolved identity, conflicting candidates, URI parsing, GraphQL mismatch, and duplicate cross-category identities." (Chunk 1 authors the tests; Chunk 13 owns the verification requirement.) | §13 |

**Requirements that are deliberately excluded from Chunk 1 testing** (resolved
decision R-1, section 12; the matrix rows themselves remain listed above because
they do name Chunk 1):

- `LREQ-GQL-020`, `LREQ-GQL-030` — no Chunk 1-owned structural or pure half with
  an identity angle exists; both are protocol/query-construction and
  response-correlation concerns owned by Chunk 5. Section 9 carries no marker for
  them.
- `LREQ-EXT-010`, `LREQ-EXT-030`, `LREQ-EXT-040` — endpoint/header/field-set
  behavior owned by Chunk 3; their required tests are `LREQ-TST-040` and
  `LREQ-TST-080` (Chunks 3 and 13).
- `LREQ-CLI-040` — run rejection and report retention owned by Chunk 12; its
  required test is `LREQ-TST-080`.

`LREQ-EXT-100` is not listed at all: its matrix row (line 59) names supporting
chunks `Chunk 0` only, so it is outside this chunk's scope and appears nowhere in
this plan.

### Relevant normative definitions and constraints this chunk depends on (§1.2, §1.4, §2.2, §3.1, §12)

- **Normative language (§1.2)**: "**SHALL** means mandatory for conformance.";
  "All timestamps used in calculations SHALL be timezone-aware UTC timestamps.";
  "Missing, invalid, contradictory, or unavailable values SHALL remain unavailable;
  they SHALL NOT be silently converted to zero."
- **Usable observation (§1.4)**: "An observation satisfying the component-specific
  type, range, state, identity, date, and operation-status rules." — the structural
  subset of this sentence is Chunk 1's; the component-specific eligibility subset is
  Chunk 7A's.
- **Discovered population (§1.4)**: "Distinct canonical asset identities returned by
  verified category discovery, excluding unresolved/conflicting identities from the
  canonical denominator but retaining them in audit data."
- **Safeguards that SHALL NOT be removed (§2.2)**: item 2 "canonical identity
  resolution and conflict detection"; item 3 "operation-level GraphQL response
  validation"; item 8 "no fabricated values for missing data".
- **Component responsibility (§3.1)**: "`validation` | Taxonomy, identity, type,
  date, state, and semantic checks | No network" — this chunk implements the
  taxonomy, identity, type, structural-shape, and redaction parts of that row.
- **Appendix B traceability (§14/Appendix B)**: `LREQ-EXT-*` → "`collector.py`,
  `validation.py`" with required test `test_collector.py`; `LREQ-GQL-*` →
  "`collector.py`, `validation.py`" with required tests `test_collector.py`,
  `test_identity.py`; `LREQ-MET-*` → "`scoring.py`" with required tests
  `test_scoring.py`, `test_validation.py` — hence `tests/test_validation.py` and
  `tests/test_identity.py` are the SRS-required test modules for this chunk.
- **Project structure (§12)**: the lean layout lists `src/niche_scout/validation.py`
  and the test modules `tests/test_identity.py` and `tests/test_validation.py`, all
  of which are this chunk's owned files.
- **§4.4 identity preflight is not this chunk's**: the preflight is "an operational
  endpoint-and-mapping smoke test" and is owned by Chunk 6A; Chunk 1 supplies only
  the pure identity-compatibility comparison it calls.

## 4. Interface contracts consumed

Only one prerequisite exists: **Chunk 1 depends on Chunk 0, and Chunk 0's frozen
interface file exists** (`Documents/interfaces/chunk-00.md`, Status: VERIFIED).
Nothing below is re-derived from Chunk 0's source code; every name and signature is
copied from that interface file. Chunk 1's pure code SHALL NOT import `collector`,
`collector_coveo`, `collector_graphql`, `database`, `pipeline`, `report`, `cli`, or
`config` (config is I/O).

### 4.1 Enums and status types (`niche_scout.models`), from `interfaces/chunk-00.md` §2

All are `class X(str, Enum)`; values are the canonical wire/DB strings.

**Identity-resolution status is a Chunk 0 deliverable that Chunk 1 consumes, not a
type Chunk 1 may invent.** `interfaces/chunk-00.md` §2 ("Enums and status types
(`niche_scout.models`)") documents `IdentityResolutionStatus` with values
`resolved` / `unresolved` / `conflict`, and `§2` also documents
`CategoryFilterValidationStatus` (`verified` / `mismatch` / `unverified`) and
`GraphQLOperationCorrelationMode` (`explicit_key` / `validated_position`). This is
grounded in SRS §6.1, which lists `identity_mapping_rule_version` as a persisted
`runs` field, and in Chunk 0's own committed scope ("discovery,
identity-resolution, operation, score, evidence, and rankability statuses" and
"typed domain/result structures … for the complete SRS data model"). Chunk 1
therefore **checks for and consumes** these types. If Chunk 0 had not actually
delivered a type its own gate says it would, that is a **Chunk 0 gate defect to
escalate to the human** — Chunk 1 must not patch around it in either direction
(neither by adding the missing type itself nor by silently working without it).
See resolved decision R-4 in section 12.

```python
class IdentityResolutionStatus(str, Enum):         # resolved | unresolved | conflict
class OperationStatus(str, Enum):                  # success | error
class GraphQLOperationCorrelationMode(str, Enum):  # explicit_key | validated_position
class CategoryFilterValidationStatus(str, Enum):   # verified | mismatch | unverified
class WarningCode(str, Enum):                      # IDENTITY_UNRESOLVED | IDENTITY_CONFLICT
                                                   # | CATEGORY_MISMATCH | GRAPHQL_ID_MAPPING_MISMATCH
                                                   # | STATE_EXCLUDED | ... (full Appendix C set)
class DiscoveryStatus(str, Enum):                  # complete | truncated | page_failed | filter_unverified
                                                   # | category_mismatch | identity_incomplete | request_failed
```
Chunk 1 SHALL reuse these names and SHALL NOT redefine them.

### 4.2 Constants available from `niche_scout.models` (`interfaces/chunk-00.md` §3)

```python
IDENTITY_MAPPING_RULE_VERSION = "1.0.1"   # the versioned mapping rule for canonicalization
                                          # (normative content fixed by R-2, section 12)
MAX_TAXONOMY_AGE_DAYS = 30                # taxonomy freshness threshold (inclusive boundary;
                                          # SRS Appendix A, §14)
ENDPOINT_CONTRACT_VERSION = "1.0.0"
(deliberately NOT changed here — this is a different constant, not an identity-mapping
version; noted 2026-09-18 only to distinguish it from `IDENTITY_MAPPING_RULE_VERSION`)
```

### 4.3 Serialization / timestamp helpers (`interfaces/chunk-00.md` §4.2)

```python
def ensure_utc(value: datetime) -> datetime: ...
def to_json_dict(instance: Any) -> dict[str, Any]: ...
def to_json(instance: Any) -> str: ...
```

`ensure_utc` is the frozen UTC-normalization helper (rejects naive datetimes with
`ValueError`, converts aware non-UTC to UTC) and is the ONLY timestamp normalization
Chunk 1 may use. `to_json`/`to_json_dict` render enums via `.value`, render
datetimes as ISO-8601 UTC with `Z`, and preserve `None` ("`None` round-trips as
`None`; it is never coerced to `0`/`""`") — the redacted error-summary serializer
builds on them.

### 4.4 Row models whose field semantics Chunk 1 fills (`interfaces/chunk-00.md` §4.1)

- `RawDiscoveryObservationRecord` fields Chunk 1 produces values for:
  `asset_identity_key: Optional[str]`, `identity_candidates_json: str`,
  `identity_resolution_status: str`, `identity_resolution_reason: Optional[str]`,
  `category_value_json: str`, `category_filter_validation_status: str`,
  `error_summary_json: Optional[str]`. Per `interfaces/chunk-00.md` §4.1,
  "Status/state fields on records are stored as `str` (the enum `value`), because
  the records mirror SQLite columns; use the enums for logic." Chunk 1 returns typed
  enums in its pure results and serializes enum `.value` strings for persistence.
- `EnrichmentObservationRecord` fields Chunk 1 validates/computes:
  `graphql_id: Optional[str]`, `product_id: Optional[str]`, `state: Optional[str]`,
  `category_json: Optional[str]`, `id_mapping_mismatch: bool`, and the
  `product_detail_error_summary` / `page_views_error_summary` redacted summaries.

### 4.5 Configuration inputs Chunk 1 may receive as typed arguments

From `interfaces/chunk-00.md` §5: `NicheScoutConfig.max_taxonomy_age_days` is the
only configuration value this chunk needs, and it SHALL be passed in as a typed
argument rather than loaded from `config.py` (which is an I/O module):

```python
@dataclass(frozen=True)
class NicheScoutConfig:
    ...
    max_taxonomy_age_days: int
    ...
def load_config(cli_args: Optional[dict[str, Any]] = None, toml_path: Optional[Path] = None) -> NicheScoutConfig: ...
def read_categories(categories_path: Path) -> Sequence[str]: ...   # I/O; orchestration calls this, not Chunk 1
```
The reference "now" for freshness SHALL be supplied by the caller as a
timezone-aware UTC `datetime`; Chunk 1 SHALL NOT read the clock. Which concrete
timestamp the caller passes is an **orchestration-layer decision (Chunks 10 and
12)** to be made when the call site is wired up, and is deliberately not fixed by
this plan: §3.2 step 2 (configuration and taxonomy validation) runs *before* step 3
creates `run_id` and `run_started_at_utc`, so `run_started_at_utc` does not exist
yet at validation time and cannot be assumed to be the reference value.

### 4.6 Fixtures available (`interfaces/chunk-00.md` §9, read-only for this chunk)

`tests/fixtures/config_fixtures.py` (exported via `tests/fixtures/__init__.py`)
already provides `REQUIRED_TAXONOMY_FIELDS`, `DEFAULT_CATEGORIES` (8 canonical
category paths), `TAXONOMY_FIXTURE` (valid header fields plus
`canonical_category_paths` and `categories` entries). Chunk 1 SHALL reuse these and
SHALL NOT redefine them; per that section, "analytical tests SHALL use fixtures and
golden vectors only; live network calls are forbidden".

### 4.7 Traceability tooling contract (`interfaces/chunk-00.md` §8)

`python -m niche_scout.tools.validate_traceability` currently checks bidirectional
coverage "for Chunk 0's 7 requirements" and **fails** on: unknown/retired LREQ
references, "Tests with lreq markers but no matrix entry", "Marker/matrix LREQ
mismatch", and orphan matrix nodes. Consequence for this chunk: every marked test
in `tests/test_validation.py` and `tests/test_identity.py` MUST have an exactly
matching `tests/traceability.json` entry, or the validator exits 1. Widening the
required-requirement set — expanding the tool's `chunk` parameter beyond `0`,
accepting the `Requirements:` heading wording used by later chunks, and changing
the Chunk-0-specific user-facing messages — is deferred to **Chunk 13** (resolved
decision R-3). Chunk 1 does **not** touch the tool. Until Chunk 13 lands, the
tool's required-set completeness direction is not usable for any chunk, so
gate-verifier must manually cross-check section 3's LREQ table against the actual
`@pytest.mark.lreq` markers in the test files (see section 9).

### 4.8 What Chunk 0 explicitly does NOT provide (`interfaces/chunk-00.md` §10)

"No taxonomy/identity validation logic, no exact category-path matching, no
canonical identity parsing — that is Chunk 1." Chunk 0's `test_taxonomy_contract`
only asserts the taxonomy fixture's field names.

## 5. Interface contract this chunk produces

This section becomes `Documents/interfaces/chunk-01.md` verbatim once frozen by the
gate-verifier. Public surface lives in `src/niche_scout/validation.py`; no new
symbols are added to `models.py` unless section 6's conditional row is taken.

### 5.1 Typed result and issue structures (`niche_scout.validation`)

```python
@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: str                      # stable machine-readable code, e.g. "taxonomy_missing_header"
    message: str                   # redacted, secret-free, no raw response bodies
    context: dict[str, Any]        # JSON-safe, redacted (field name, counts, path)
    def to_json(self) -> str: ...  # deterministic ordering via models.to_json_dict

@dataclass(frozen=True, slots=True)
class TaxonomyValidationResult:
    is_valid: bool
    is_fresh: bool | None          # None when freshness is undeterminable (never False-by-default)
    status: str                    # "valid" | "missing_headers" | "malformed" | "stale"
                                   # | "missing_categories" | "invalid_capture_timestamp"
    missing_header_fields: tuple[str, ...]
    missing_requested_categories: tuple[str, ...]
    age_days_exact: float | None   # None when captured_at_utc is unusable
    issues: tuple[ValidationIssue, ...]

@dataclass(frozen=True, slots=True)
class IdentityCandidate:
    source_field: str              # "ec_product_id" | "permanentid" | "clickUri" | "uri"
    raw_value: str                 # non-empty, retained verbatim
    canonical_value: str | None    # None when the candidate is unparseable
    parse_failure_reason: str | None

@dataclass(frozen=True, slots=True)
class IdentityResolutionResult:
    canonical_identity_key: str | None
    status: IdentityResolutionStatus           # resolved | unresolved | conflict
    reason: str | None                         # redacted; non-None for unresolved/conflict
    candidates: tuple[IdentityCandidate, ...]  # every non-empty candidate, in input order
    included_in_canonical_denominator: bool
    included_in_enrichment_set: bool
    mapping_rule_version: str
    issues: tuple[ValidationIssue, ...]

@dataclass(frozen=True, slots=True)
class CategoryMatchResult:
    matched_path: str | None
    status: CategoryFilterValidationStatus     # verified | mismatch | unverified
    matched_value_count: int
    unmatched_values: tuple[str, ...]
    issues: tuple[ValidationIssue, ...]

@dataclass(frozen=True, slots=True)
class GraphQLIdentityComparisonResult:
    matches_requested_identity: bool
    id_mapping_mismatch: bool
    reason: str | None
    compared_aliases: tuple[tuple[str, str], ...]
    issues: tuple[ValidationIssue, ...]

@dataclass(frozen=True, slots=True)
class StateEligibilityAnnotation:
    state_value: str | None
    is_published: bool
    state_excluded: bool                       # present but not "published"
    state_unknown: bool                        # missing/null/unparsable
    remains_in_discovered_breadth: bool        # always True (annotation only)

@dataclass(frozen=True, slots=True)
class StructuralValidationResult:
    is_valid: bool
    expected_shape: str
    actual_shape: str | None
    issues: tuple[ValidationIssue, ...]
```

### 5.2 Public functions (`niche_scout.validation`)

```python
def validate_taxonomy_structure(payload: object) -> TaxonomyValidationResult: ...
def validate_taxonomy_freshness(
    payload: object,
    *,
    reference_utc: datetime,
    max_taxonomy_age_days: int,
) -> TaxonomyValidationResult: ...
def validate_requested_categories(
    payload: object, requested_categories: Sequence[str]
) -> TaxonomyValidationResult: ...
def validate_taxonomy(
    payload: object,
    *,
    requested_categories: Sequence[str],
    reference_utc: datetime,
    max_taxonomy_age_days: int,
) -> TaxonomyValidationResult: ...

def normalize_category_path(value: str) -> str: ...
def taxonomy_path_set(payload: object) -> frozenset[str]: ...
def match_exact_category(
    category_value: object, taxonomy_paths: Container[str]
) -> CategoryMatchResult: ...

def collect_identity_candidates(record: Mapping[str, object]) -> tuple[IdentityCandidate, ...]: ...
def canonicalize_identity_candidate(
    raw_value: str, *, mapping_rule_version: str = IDENTITY_MAPPING_RULE_VERSION
) -> str | None: ...
def resolve_canonical_identity(
    record: Mapping[str, object],
    *,
    mapping_rule_version: str = IDENTITY_MAPPING_RULE_VERSION,
) -> IdentityResolutionResult: ```

`canonicalize_identity_candidate` implements mapping rule `1.0.1` (resolved
decision R-2, section 12; normative for `LREQ-EXT-060` canonicalization)
(`superseded 2026-09-18: this line previously read "implements mapping rule
`1.0.0`"; the rule content below is unchanged by `1.0.1` — the only substantive
change is in the comparison bullet, where `1.0.0` tolerated a suffix match):

- `ec_product_id` and `permanentid`, if non-empty: trim whitespace, then compare
  directly — as integers when both parse as numeric, else as strings. Both are
  treated as **already canonical**; no further transformation is applied.
- `clickUri` / `uri`, if non-empty: parse the trailing numeric identifier after the
  final `-` in the URL's last path segment. A value that does not fit that pattern
  contributes **nothing** (no candidate) rather than a wrong candidate.
- `resolve_canonical_identity` compares all successfully-derived candidates: all
  equal → `resolved`, with that value as `asset_identity_key`; any disagreement →
  `conflict`; nothing derivable from any candidate → `unresolved`. Matching is
  **strict equality after canonicalization** (`interfaces/chunk-01.md` §4.1 rule
  `1.0.1`; the superseded form of this bullet is recorded below).

**Caveat Chunk 3 must verify** (recorded as risk note RN-1, section 12): the URI
trailing-numeric-segment rule is *inferred* from the retired parent-SRS fragment
(`Documents/retired-documents/SRS-revision2.md`, OI-4 / REQ-EXT-065) plus general
Unity Asset Store URL conventions. It is **NOT** verified against a real captured
Coveo response. Chunk 3 (the `LREQ-EXT-060` integration completion chunk) SHALL
sanity-check this rule against real redacted fixtures before treating it as final;
`IDENTITY_MAPPING_RULE_VERSION = "1.0.1"` exists precisely so a correction is
cheap. Consumers SHALL branch on `IdentityResolutionResult.mapping_rule_version`
rather than assuming `1.0.0` semantics silently.

**Satisfaction condition of the caveat above — explicitly RELAXED by human ruling
(added 2026-09-18, quoted from `Documents/interfaces/chunk-01.md` §4.1, which is
the superseding text; the caveat above is preserved as the record of what this plan
previously stated, and its obligation was previously unconditional).** That
obligation "is now discharged by **scope declaration**: the rule remains
*unverified* and the verification is **deferred to a future capture**, rather than
performed." — `interfaces/chunk-01.md` §4.1, "Satisfaction condition of the caveat
above — explicitly RELAXED by human ruling". `interfaces/chunk-01.md` §4.1,
"Satisfaction condition of the caveat above — explicitly RELAXED by human ruling",
also records the consequence precisely: "the extraction half of rule `1.0.1` is
**UNVERIFIED**, and no artifact in this repository — this contract, an adapter
interface, a plan, a docstring, a `mapping_rule_version` stamp, or a test name —
may state or imply that it was verified against a real Coveo response."

**Relaxed is NOT verified.** The relaxation accepted the exposure rather than
removing it: `interfaces/chunk-01.md` §4.1, "The exposure deferral leaves open",
records that "Deferral does **not** remove that exposure — it accepts it for the
present rule version", that a wrong extraction pattern is "currently surfaced only
by whatever causes *disagreement* among the candidate sources", and that "This
exposure remains open until the deferred verification is performed; the relaxation
does not assert it away." **The extraction rule remains inferred and
NOT capture-verified, and no real captured Coveo response exists anywhere in this
repository to verify it against.** This plan's own statement of the caveat below
(section 12, RN-1) is therefore restated as status-with-pointer rather than
repeated: the obligation remains **OPEN and owned by no chunk**, and RN-1 points
at these paragraphs instead of carrying its own contradicting text.

**Bounded correction of this plan (recorded, not deleted):** the caveat above once
served as this plan's authoritative statement of the verification obligation; it
does so no longer, and this plan does not restate the obligation's satisfaction
condition on its own authority. The obligation's own record lives in
`interfaces/chunk-01.md` §4.1 and in
`requirements-dependency-map.md` §6.4 ("Deferred obligation with no owning
chunk"), which names **Owner: none**. The superseded wording of this plan's
"resolve_canonical_identity compares …" bullet read: "`resolve_canonical_identity`
compares all successfully-derived candidates: all equal → `resolved`, with that
value as `asset_identity_key`; any disagreement → `conflict`; nothing derivable
from any candidate → `unresolved`." — it carried no equality-comparison clause,
and the strict-equality clause now attached to it is the `1.0.1` reading.

```python
def compare_graphql_identity_aliases(
    requested_identity: str,
    aliases: Mapping[str, object],
    *,
    mapping_rule_version: str = IDENTITY_MAPPING_RULE_VERSION,
) -> GraphQLIdentityComparisonResult: ...
def annotate_state_eligibility(state_value: object) -> StateEligibilityAnnotation: ...

def validate_response_shape(
    payload: object,
    *,
    expected_shape: str,
    required_members: Sequence[str],
    field_types: Mapping[str, type | tuple[type, ...]],
) -> StructuralValidationResult: ...
def summarize_validation_issues(
    issues: Sequence[ValidationIssue], *, max_context_chars: int = 256
) -> str: ...            # returns a redacted JSON summary for error_summary_json
def redact_value(value: object) -> str: ...   # never emits credentials/tokens/cookies
```

Behavioral contracts these functions guarantee (and that downstream chunks may
rely on):

- **Structural only**: every function classifies *structure* (shape, type,
  presence, alias agreement, path equality, candidate canonicalizability). None of
  them decides whether a value is *usable for a metric*; that is Chunk 7A.
- **Purity**: no I/O, no clock, no randomness; `reference_utc` is always an explicit
  timezone-aware UTC argument ("`scoring_cutoff_utc` is always an explicit,
  timezone-aware UTC input" — `interfaces/chunk-00.md` §1).
- **Null vs zero vs invalid vs unavailable** stay distinct in every result; a
  missing/malformed/invalid value yields `None` plus an issue, never `0`/`""`/`[]`
  as a sentinel.
- **Determinism**: identical inputs plus identical `mapping_rule_version` produce
  structurally equivalent outputs; candidate order is input order; issue order is
  deterministic (field order, then code).
- **Redaction**: `ValidationIssue.message`/`context` and
  `summarize_validation_issues` never include credential values, `Authorization`
  headers, CSRF tokens, cookies, or full response bodies.

## 6. Files touched

| File | New/modified | Purpose |
|---|---|---|
| `src/niche_scout/validation.py` | Modified (currently a 2-line docstring stub: `"""Validation primitives will be added by later chunks."""`) | The complete pure taxonomy / identity / category-matching / structural-validation / redaction primitive surface described in section 5, with type hints and docstrings describing null and edge-case behavior (LREQ-NFR-040) |
| `tests/test_validation.py` | New | Analytical tests for taxonomy schema + freshness + requested-category validation, exact category matching (parent/child, scalar, multi-valued), structural shape/type validation, redacted error summaries, and the structural half of LREQ-MET-010 |
| `tests/test_identity.py` | New | Analytical tests for candidate collection, URI fallback/parsing, canonicalization, conflict/unresolved classification, canonical-denominator and enrichment-set exclusion, and GraphQL alias comparison / mismatch |
| `tests/traceability.json` | Modified | **Must be extended.** Under the project traceability rule and `interfaces/chunk-00.md` §8, every test carrying `@pytest.mark.lreq(...)` MUST have a matrix entry whose LREQ array matches the marker exactly, and the validator fails on a marker without a matrix entry. Chunk 1 therefore adds one entry per new base pytest node ID |
| `src/niche_scout/models.py` | **Not touched** | Resolved: no change is required or permitted here. `IdentityResolutionStatus` (values `resolved` / `unresolved` / `conflict`) is a **Chunk 0 deliverable** documented in `interfaces/chunk-00.md` §2 ("Enums and status types (`niche_scout.models`)"), grounded in SRS §6.1's persisted `identity_mapping_rule_version` field and Chunk 0's committed scope ("discovery, identity-resolution, operation, score, evidence, and rankability statuses"; "typed domain/result structures … for the complete SRS data model"). Chunk 1 **consumes** that type; it does not create it and does not work around it. `OperationStatus`, `GraphQLOperationCorrelationMode`, `CategoryFilterValidationStatus`, `WarningCode`, `IDENTITY_MAPPING_RULE_VERSION`, `MAX_TAXONOMY_AGE_DAYS`, `ensure_utc`, `to_json_dict`, `to_json`, and `ROW_TYPES` are likewise already present. Chunk 1's own `IdentityCandidate` / `ValidationIssue` / result structures are analytical and belong in `validation.py`, not in `models.py` (the SRS §6 row/serialization contract). **If Chunk 0 had not actually delivered a type its own gate says it would, that is a Chunk 0 gate defect to escalate to the human** — Chunk 1 SHALL NOT patch around it, either by adding the missing type itself or by silently proceeding without it (resolved decision R-4, section 12) |
| `tests/fixtures/validation_fixtures.py` | New | Chunk-1-owned deterministic fixtures/golden vectors (taxonomy payload permutations, identity-candidate rows, expected canonical keys and digests, malformed shapes). Separate from Chunk 0's `tests/fixtures/config_fixtures.py`, which is consumed read-only |
| `tests/fixtures/__init__.py` | **Conditional** | Only if the new fixture module must be re-exported to match the existing convention in `tests/fixtures/__init__.py` |
| `.gitignore` | **Conditional** | Only if a test-written temporary artifact path (e.g. a `.tmp/` taxonomy cache) is not already covered |

**Explicitly NOT touched by this chunk** (confirmed against the dependency map and
`interfaces/chunk-00.md` §1/§10):

- `src/niche_scout/tools/validate_traceability.py` — **deferred to Chunk 13; Chunk 1
  does not touch, widen, or edit this file** (resolved decision R-3, section 12).
  The tool hardcodes Chunk 0's scope in three places:
  `chunk_requirements(..., chunk="0")`, the hardcoded `chunk_requirements` header
  parsing (`"## Chunk {chunk} "` plus the literal string
  `"Requirements primarily covered:"`, which is the **Chunk 0** wording; Chunk 1's
  section says `Requirements:`), and the user-facing messages
  (`"Chunk 0 requirements without mapped tests"`, `"Traceability valid: {n} Chunk 0
  requirements mapped"`). Its closing docstring states: "Chunk 0 intentionally
  checks its own seven requirements only; later chunks widen the required set as
  their requirements become testable." The tool is a Chunk 0 deliverable listed in
  `plans/chunk-00-project-skeleton-and-contracts.md` §6 and its required-set policy
  is a cross-chunk traceability decision owned by Chunk 13
  (`LREQ-NFR-060`), so widening it is **not** Chunk 1's scope. Practical
  consequence: after this chunk's tests are added,
  `python -m niche_scout.tools.validate_traceability` still passes (the
  marker/matrix direction is chunk-agnostic), but it will **not** verify that
  Chunk 1's individual LREQs each have a mapped test until Chunk 13 widens it. See
  section 9 for the standing manual cross-check obligation this imposes on
  gate-verifier.
- `src/niche_scout/collector.py`, `collector_coveo.py`, `collector_graphql.py` —
  Chunks 3 and 5 (primary implementation chunks for adapter integration).
- `src/niche_scout/database.py` — Chunk 2 (physical SQLite implementation).
- `src/niche_scout/sampling.py` — Chunk 4A.
- `src/niche_scout/metrics.py` — Chunks 7A/7B (metric eligibility; note
  `test_validation.py` also carries Chunk 7A's `LREQ-TST-050` date/eligibility
  tests per `interfaces/chunk-00.md` Appendix-B-derived mapping, so Chunk 1's test
  file will later be extended by Chunk 7A — Chunk 1 writes only its own tests).
- `src/niche_scout/scoring.py`, `pipeline.py`, `report.py`, `cli.py`, `config.py`.
- `pyproject.toml` — the `lreq` marker is already registered.

## 7. Task breakdown

Ordered checklist, each item tagged with the LREQ ID(s) it implements:

- [ ] Add `ValidationIssue` plus the deterministic redaction helpers (`redact_value`, `summarize_validation_issues`); assert no credential/token/cookie substring can survive redaction. (LREQ-MET-010, LREQ-GQL-040)
- [ ] Implement taxonomy structure validation: required header fields (`schema_version`, `captured_at_utc`, `source_url`, `template_sha256`), canonical category-path inventory presence, and per-entry path shape; report missing headers and malformed shape as typed issues. (LREQ-EXT-020)
- [ ] Implement taxonomy freshness validation against an explicit `reference_utc` and `max_taxonomy_age_days` using `models.ensure_utc`; classify stale, future, naive, and non-parsable `captured_at_utc` explicitly and never default freshness to `True`. Boundary is inclusive: `age <= max_taxonomy_age_days` is fresh, `age > max_taxonomy_age_days` is stale (R-5). (LREQ-EXT-020)
- [ ] Implement requested-category presence validation; treat a missing requested category as an explicit failure result (the abort itself is the caller's, in Chunks 3/12). (LREQ-EXT-020)
- [ ] Implement `normalize_category_path`, `taxonomy_path_set`, and `match_exact_category`, including exact segment equality (case-insensitive compare plus case-preserving canonical output), explicit non-matching of parent-vs-child prefixes in both directions, and explicit handling of scalar, `null`/absent, and multi-valued category shapes → `verified` / `mismatch` / `unverified`. (LREQ-EXT-080, LREQ-EXT-050, LREQ-EXT-090)
- [ ] Implement `collect_identity_candidates` over `ec_product_id`, `permanentid`, response-level `clickUri`, and response-level `uri`; retain every non-empty candidate verbatim, drop empty/whitespace/non-string values without inventing placeholders, and record the source field per candidate. (LREQ-EXT-060, LREQ-GQL-010)
- [ ] Implement `canonicalize_identity_candidate` as mapping rule `1.0.1` per resolved decision R-2 (superseded 2026-09-18: this item previously read "as mapping rule `1.0.0`"; the rule's content is unchanged — its comparison-half change is the strict-equality clause recorded in section 5.2): trim-then-direct comparison for `ec_product_id`/`permanentid` (integer when both parse numeric, else string; both already canonical, no transformation), and trailing-numeric-identifier-after-the-final-`-` extraction in the last path segment for `clickUri`/`uri` with non-conforming values contributing no candidate; record a typed parse-failure reason. (LREQ-EXT-060)
- [ ] Implement `resolve_canonical_identity` classification: all successfully-derived candidates agree → `resolved` with the canonical key; any derived candidates disagreeing → `conflict` plus reason and `included_in_canonical_denominator = False`, `included_in_enrichment_set = False`; nothing derivable from any candidate → `unresolved` plus reason and the same exclusions. (LREQ-EXT-070, LREQ-SMP-010)
- [ ] Implement `compare_graphql_identity_aliases` returning `ID_MAPPING_MISMATCH` semantics for non-agreeing aliases, treating missing aliases as a mismatch with an explicit unknown/missing reason, and never treating an absent alias as agreement. (LREQ-GQL-070, LREQ-ID-020)
- [ ] Implement `annotate_state_eligibility`: `published` → eligible; any other present state → `state_excluded`; `null`/absent/non-string → `state_unknown`; always `remains_in_discovered_breadth = True`. Do not implement the D/R/Q eligibility decision. (LREQ-GQL-060)
- [ ] Implement `validate_response_shape` for malformed shape, wrong container kind, missing required member, and wrong scalar type; return typed issues with the expected/actual shape names, and leave failed fields `None`. (LREQ-MET-010, LREQ-GQL-040, LREQ-GQL-050)
- [ ] Add type hints and docstrings describing null and edge-case behavior to every public function, and add a purity guard test (no `sqlite3`, no clock, no network, no filesystem, no `config` import). (LREQ-NFR-040, LREQ-ARCH-010 (consumed), LREQ-ARCH-020 (consumed))
- [ ] Write `tests/fixtures/validation_fixtures.py` with taxonomy payloads, identity-candidate rows, malformed-shape payloads, and hand-derived golden vectors. (LREQ-TST-030)
- [ ] Write `tests/test_validation.py` with an explicit `@pytest.mark.lreq("LREQ-...")` marker on every test function. (LREQ-EXT-020, LREQ-EXT-080, LREQ-EXT-050, LREQ-EXT-090, LREQ-MET-010, LREQ-GQL-040, LREQ-GQL-050, LREQ-TST-030)
- [ ] Write `tests/test_identity.py` with an explicit `@pytest.mark.lreq("LREQ-...")` marker on every test function. (LREQ-EXT-060, LREQ-EXT-070, LREQ-GQL-010, LREQ-GQL-060, LREQ-GQL-070, LREQ-ID-020, LREQ-SMP-010, LREQ-TST-030)
- [ ] Extend `tests/traceability.json` with one entry per new base pytest node ID whose array matches the marker set exactly. (LREQ-TST-030, gate bullet 4)
- [ ] Run `pytest tests/test_validation.py tests/test_identity.py`, `python -m niche_scout.tools.check_import_boundaries`, and `python -m niche_scout.tools.validate_traceability`; record exit codes. (gate bullets 1, 4, 5)
- [ ] Manually cross-check section 3's LREQ table against the actual `@pytest.mark.lreq` markers in both test files in both directions, because the validator's required-set completeness direction is deferred to Chunk 13 (R-3). (gate bullets 1, 4)
- [ ] Confirm no file outside section 6 was modified (`git status`), and record in the chunk report that
  `tools/validate_traceability.py` was intentionally left untouched, its widening being deferred to Chunk 13 (R-3). (gate bullets 1–5)

## 8. Edge cases and invariants

From the dependency map's edge-case column for every LREQ this chunk owns, plus the
Chunk 1 description and gate invariants:

- **LREQ-EXT-020** — "Missing, malformed, stale taxonomy; requested category absent; invalid hash or metadata." Also: invalid `schema_version` shape, missing/extra inventory, an inventory path that is itself malformed, duplicated paths, `captured_at_utc` naive (must be rejected via `ensure_utc`, not treated as fresh), `captured_at_utc` in the future, and age exactly equal to `MAX_TAXONOMY_AGE_DAYS`. The boundary is **resolved** (R-5): inclusive, so `age == MAX_TAXONOMY_AGE_DAYS` is **fresh** and `age > MAX_TAXONOMY_AGE_DAYS` is **stale**; both sides of the boundary must be tested.
- **LREQ-EXT-060** — "Multiple identity aliases, URI fallback, empty candidates, versioned canonical mapping." Also: candidates that are present but non-string (must be treated as unusable candidates, not coerced), whitespace-only values, a candidate list containing duplicates from different source fields, `ec_product_id` and `permanentid` given in numerically-equal but textually-different forms (e.g. `"123"` vs `" 123 "`, or `123` vs `"123"` — these **agree** under R-2), a URI whose last path segment does not end in `-<numeric>` (contributes **no** candidate under R-2, never a wrong one), and query-string/fragment-bearing URIs (the trailing identifier is read from the last path segment only).
- **LREQ-EXT-070** — "Conflicting candidates, unresolved candidates, exclusion from denominator and enrichment." Invariant: a `conflict` or `unresolved` record is **never** returned with a canonical key, and `included_in_canonical_denominator`/`included_in_enrichment_set` are `False` for both; `reason` is always non-`None` for both. Neither case may "be silently treated as an ordinary asset."
- **LREQ-EXT-080** — "Parent versus child path, exact match, scalar category, multi-valued category." Invariants: `Parent` does not match `Parent/Child`; `Parent/Child` does not match `Parent`; matching is on full segment sequences; a multi-valued category array where exactly one value matches yields `verified`; zero matches yields `mismatch`; a missing/`null`/wrong-typed category value yields `unverified` (not `mismatch`).
- **LREQ-GQL-060** — "Only `published` assets eligible for D, R, and Q; state-excluded and state-unknown assets remain in discovered breadth and persisted observations." Invariant enforced here: the annotation never removes an asset from breadth and never returns a metric-eligibility verdict.
- **LREQ-GQL-070** — "Returned aliases disagree with requested identity; mismatch must invalidate affected result." Invariants: comparison is done on canonical values, not raw strings; a returned alias that cannot be canonicalized counts as a mismatch with an explicit reason; `id_mapping_mismatch = True` implies `matches_requested_identity = False`.
- **LREQ-MET-010 (structural half only)** — "Null, malformed, wrong type, invalid range, future, naive, negative, non-finite, and excluded-state values" are all owned semantically by Chunk 7A; here the invariants are only: null ≠ wrong type ≠ unparsable shape are reported as distinct issue codes; "Structural malformed-shape/type/alias checks remain owned by Chunk 1."
- **LREQ-TST-030 (cross-category duplicates)** — resolved decision R-6: Chunk 1's
  obligation is only the **pure pairwise** fact that two raw candidates originating
  from different categories can canonicalize to the same `asset_identity_key`, so a
  pure property test on `resolve_canonical_identity` recognizes them as the same
  identity independently of category. Counting, overlap metrics, duplicate marking,
  and persistence stay in Chunks 3, 4B, and 6B; Chunk 1 SHALL NOT implement them.
- **Chunk-level invariants from the Chunk 1 gate**: "All structural identity and taxonomy tests pass without network access"; "Invalid data is represented explicitly, never silently converted to zero or an ordinary asset"; "Validation functions accept typed data and return typed results."
- **Purity and determinism invariants** (inherited from `interfaces/chunk-00.md` §1): no system-clock reads, no unseeded randomness, no filesystem/database/network/process import, and identical inputs plus identical `mapping_rule_version` produce equivalent results.
- **Redaction invariant** (LREQ-SEC-020 as consumed, and `interfaces/chunk-00.md` §9/§5): no credential value, `Authorization` header, CSRF token, or cookie may appear in `ValidationIssue` text, `context`, or `summarize_validation_issues` output; raw response bodies are not retained.

## 9. Test plan

### Test files to create

- `tests/test_validation.py` (new) — taxonomy schema, freshness, requested-category
  presence, exact category matching, structural shape/type validation, redacted
  summaries.
- `tests/test_identity.py` (new) — candidate collection, URI fallback, canonical
  mapping and rule versioning, conflict/unresolved handling, denominator and
  enrichment-set exclusion, GraphQL alias comparison, state annotation.
- `tests/fixtures/validation_fixtures.py` (new) — fixture module; reuse
  `tests/fixtures/config_fixtures.py` values (`REQUIRED_TAXONOMY_FIELDS`,
  `DEFAULT_CATEGORIES`, `TAXONOMY_FIXTURE`) read-only.

### Golden vectors / fixtures needed (with source)

| Vector | Source |
|---|---|
| Valid taxonomy payload with all four header fields + the 8 canonical category paths | `tests/fixtures/config_fixtures.py::TAXONOMY_FIXTURE` (Chunk 0 fixture, `interfaces/chunk-00.md` §9) |
| Taxonomy payloads each missing one of `schema_version`, `captured_at_utc`, `source_url`, `template_sha256` | Derived from the four field names in SRS §4.1 / `REQUIRED_TAXONOMY_FIELDS` |
| Stale / exactly-at-threshold / future / naive `captured_at_utc` payloads | Hand-derived against `MAX_TAXONOMY_AGE_DAYS = 30` (SRS Appendix A constant table; `interfaces/chunk-00.md` §3) with an explicit fixture `reference_utc`. Boundary fixtures must cover **both** `age == 30` (fresh) and `age == 30 + ε` (stale), per the inclusive convention of SRS §7.4 (`RECENT_WINDOW_DAYS` defaults to `365`, inclusive) adopted for taxonomy freshness by resolved decision R-5 |
| Requested-category lists: all present; exactly one absent; requested list containing a parent path of a real inventory path | Hand-derived from `DEFAULT_CATEGORIES` |
| Category-value shapes: scalar exact match; scalar parent path; scalar child path; `null`; wrong type (int/list-of-int); multi-valued list with one exact match; multi-valued list with a parent-path entry; multi-valued list with an entry matching a child path | SRS §4.1 LREQ-EXT-080 edge cases ("Parent versus child path, exact match, scalar category, multi-valued category") |
| Identity records: `ec_product_id` only; `permanentid` only; `clickUri` URL with trailing `-<numeric>` segment; `uri` URL with slug + trailing identifier; a URI whose last path segment has no trailing `-<numeric>` (contributes **no** candidate); all four agreeing; `"123"` vs `" 123 "` vs `123` (agree under R-2); two disagreeing canonical values; `ec_product_id` and `permanentid` disagreeing with the URI-derived value; URLs carrying query strings/fragments; all candidates empty/whitespace; candidates non-string (2026-09-18 note: the fixture rows above are listed by shape only, so nothing in them changed with rule `1.0.1`; its only substantive change is the strict-equality comparison recorded in section 5.2) | SRS §4.1 LREQ-EXT-060/070; normative content is adopted mapping rule `1.0.1` (resolved decision R-2, section 12) (superseded 2026-09-18: this cell previously cited "mapping rule `1.0.0`"; the fixture shapes are unchanged and the reference is a version name only). The retired parent-SRS fragment (`Documents/retired-documents/SRS-revision2.md`, OI-4 / REQ-EXT-065) is retained only as the documented **provenance of the fixture shapes**, not as normative text |
| GraphQL alias maps: agreeing alias; disagreeing alias; missing alias; unparseable alias; alias agreeing only after canonicalization | SRS §4.2 LREQ-GQL-070 |
| State values: `"published"`, another non-empty state string, `null`, absent, non-string | SRS §4.2 LREQ-GQL-060 |
| Malformed response shapes: non-mapping payload, missing required member, `null` required member, wrong scalar type (str where int expected), list where mapping expected, mapping where list expected | SRS §4.2 LREQ-GQL-040; §7.1 LREQ-MET-010 structural half |
| Redaction vectors: issue context containing `Authorization: Bearer <fixture-token>`, `Cookie: ...`, and `NICHESCOUT_COVEO_BEARER_TOKEN`-shaped strings; assert none survive into `summarize_validation_issues` | SRS §4.3 LREQ-SEC-020 as consumed; `interfaces/chunk-00.md` §9 mock-credential convention |

Golden vectors here are exact string/set equality (canonical keys, statuses, path
sets). No `1e-9` float tolerance is needed except for the freshness `age_days_exact`
value, which SHALL be asserted exactly as `(reference_utc - captured_at_utc).total_seconds() / 86400`.

### Required pytest LREQ markers, mapped 1:1 to section 3

| LREQ ID (from section 3) | Test module | Base pytest node IDs carrying `@pytest.mark.lreq("...")` |
|---|---|---|
| LREQ-EXT-020 | `tests/test_validation.py` | `test_taxonomy_requires_all_header_fields`, `test_taxonomy_requires_canonical_path_inventory`, `test_taxonomy_rejects_naive_captured_at`, `test_taxonomy_flags_stale_capture`, `test_taxonomy_flags_future_capture`, `test_taxonomy_reports_missing_requested_categories`, `test_validate_taxonomy_combines_structure_freshness_and_presence` |
| LREQ-EXT-080 | `tests/test_validation.py` | `test_exact_category_path_match`, `test_parent_path_does_not_match_child_path`, `test_child_path_does_not_match_parent_path`, `test_scalar_category_shape_handled_explicitly`, `test_multi_valued_category_shape_handled_explicitly`, `test_unverified_versus_mismatch_classification` |
| LREQ-MET-010 (structural half) | `tests/test_validation.py` | `test_malformed_shape_is_explicitly_invalid`, `test_wrong_scalar_type_is_explicitly_invalid`, `test_null_required_member_is_distinct_from_wrong_type`, `test_failed_fields_remain_none_not_zero`, `test_validation_issues_are_redacted`, `test_structural_validation_does_not_decide_metric_eligibility` |
| LREQ-EXT-060 | `tests/test_identity.py` | `test_collects_all_non_empty_identity_candidates`, `test_candidate_source_fields_are_retained`, `test_uri_fallback_parsing`, `test_canonicalization_is_versioned`, `test_unparseable_candidate_retained_with_reason`, `test_empty_candidates_are_dropped_not_fabricated` |
| LREQ-EXT-070 | `tests/test_identity.py` | `test_agreeing_candidates_resolve`, `test_disagreeing_candidates_become_conflict`, `test_no_canonicalizable_candidate_becomes_unresolved`, `test_conflict_excluded_from_denominator_and_enrichment`, `test_unresolved_excluded_from_denominator_and_enrichment`, `test_conflict_and_unresolved_never_ordinary_asset` |
| LREQ-GQL-060 | `tests/test_identity.py` | `test_published_state_annotated_eligible`, `test_state_excluded_annotation`, `test_state_unknown_annotation`, `test_state_annotation_keeps_asset_in_discovered_breadth`, `test_state_annotation_is_not_metric_eligibility` |
| LREQ-GQL-070 | `tests/test_identity.py` | `test_matching_alias_after_canonicalization`, `test_disagreeing_alias_sets_id_mapping_mismatch`, `test_missing_alias_is_mismatch_not_agreement`, `test_unparseable_alias_is_mismatch_with_reason` |
| LREQ-TST-030 | `tests/test_identity.py` | `test_identity_suite_covers_valid_malformed_unresolved_conflict_uri_and_mismatch` (a suite-completeness test asserting the required identity cases exist as named tests) |

Markers on tests for the matrix-only supporting rows (per resolved decision R-1,
only where this chunk actually authors the primitive's test):

| LREQ ID | Test module | Base pytest node IDs |
|---|---|---|
| LREQ-GQL-010 | `tests/test_identity.py` | `test_canonical_identity_key_type_is_shared_identity_unit` |
| LREQ-GQL-040 / LREQ-GQL-050 (structural half) | `tests/test_validation.py` | `test_missing_identity_member_is_operation_shape_error`, `test_structure_validation_retains_valid_member_when_other_missing` |
| LREQ-EXT-050 / LREQ-EXT-090 (reason vocabulary only) | `tests/test_validation.py` | `test_category_mismatch_and_unverified_map_to_discovery_status_vocabulary` |
| LREQ-ID-020 (pure comparison half) | `tests/test_identity.py` | `test_requested_identity_compatibility_comparison` |
| LREQ-SMP-010 (resolution-status half) | `tests/test_identity.py` | `test_resolution_status_supports_population_exclusion` |
| LREQ-EXT-010 / LREQ-EXT-030 / LREQ-EXT-040 / LREQ-CLI-040 / LREQ-ARCH-010 / LREQ-ARCH-020 / LREQ-NFR-040 | — | **No Chunk 1 test planned**; see resolved decision R-1 (their required tests belong to Chunks 3/12, and Chunk 0 already owns their contract tests) |

No test in either module may perform network I/O, read the system clock for its
expected value, or write outside pytest's `tmp_path`.

### traceability.json entries to add

One entry per base node ID above, with the array equal to that test's marker set,
e.g.:

```json
{
  "tests/test_validation.py::test_taxonomy_requires_all_header_fields": ["LREQ-EXT-020"],
  "tests/test_validation.py::test_parent_path_does_not_match_child_path": ["LREQ-EXT-080"],
  "tests/test_validation.py::test_null_required_member_is_distinct_from_wrong_type": ["LREQ-MET-010"],
  "tests/test_identity.py::test_disagreeing_candidates_become_conflict": ["LREQ-EXT-070"],
  "tests/test_identity.py::test_published_state_annotated_eligible": ["LREQ-GQL-060"],
  "tests/test_identity.py::test_disagreeing_alias_sets_id_mapping_mismatch": ["LREQ-GQL-070"],
  "tests/test_identity.py::test_identity_suite_covers_valid_malformed_unresolved_conflict_uri_and_mismatch": ["LREQ-TST-030"]
}
```

Parameterized tests SHALL be mapped by base node ID, matching the existing
convention (`tests/test_contracts.py` uses base IDs). Required tests referenced by
the ownership matrix for these requirements are `LREQ-TST-030` (identity) and
`LREQ-TST-080` (end-to-end, Chunk 13); `LREQ-TST-080` is not satisfiable in this
chunk because it requires the full collection/sampling/enrichment path.

### Commands to run

```text
python -m pytest tests/test_validation.py tests/test_identity.py -q
python -m pytest tests -q
python -m niche_scout.tools.check_import_boundaries
python -m niche_scout.tools.validate_traceability
```

## 10. Definition of done (gate)

Copied **verbatim** from `Documents/requirements-dependency-map.md` Chunk 1 Gate
(lines 475–479):

- All structural identity and taxonomy tests pass without network access.
- Invalid data is represented explicitly, never silently converted to zero or an ordinary asset.
- Validation functions accept typed data and return typed results.
- This chunk owns structural validity only; metric eligibility rules such as published-state, UTC/date, future-date, finite/non-negative, age, and page-view eligibility are owned by Chunk 7A.
- This chunk does not claim complete Coveo or GraphQL requirement behavior; those validators are applied to external responses in Chunks 3 and 5.

## 11. Explicit prohibitions

- **No network access**: `validation.py` and its tests SHALL NOT import
  `requests`, `urllib`, `http`, `httpx`, `aiohttp`, `socket`, or any other network
  module, and SHALL NOT issue a live Coveo or GraphQL request, including inside
  tests.
- **No filesystem writes**: `validation.py` SHALL NOT open, read, or write files
  (no `open`, `pathlib` reads, or `os` filesystem calls); taxonomy payloads are
  received as already-parsed typed objects. Tests SHALL write nothing outside
  pytest's `tmp_path`.
- **No `sqlite3`**: SHALL NOT import or touch `sqlite3`, the `database` module, the
  `Repository` protocol, or any persistence schema. Persistence of raw observations
  and enrichment rows is Chunks 2, 3, and 5.
- **No system-clock reads**: SHALL NOT call `datetime.now()`, `datetime.utcnow()`,
  `time.time()`, or equivalent. The freshness reference time is an explicit
  timezone-aware UTC argument, and `datetime` may be imported only for type/UTC
  normalization use via `models.ensure_utc`.
- **No fabricated zeros or defaults**: SHALL NOT convert a missing, malformed,
  wrong-typed, unparseable, excluded, or unavailable value to `0`, `0.0`, `""`,
  `[]`, `False`, or any other sentinel; such values remain `None` plus an explicit
  typed issue. In particular, a `conflict`/`unresolved` identity SHALL NOT become an
  ordinary asset and a missing category SHALL NOT become an empty category.
- **No claiming complete Coveo or GraphQL behavior**: the chunk SHALL NOT claim,
  document, or test-complete LREQ-EXT-060/080 or LREQ-GQL-060/070 integration;
  those are completed by Chunks 3 and 5, and the metric-eligibility portion of
  LREQ-GQL-060 plus the metric identity-mismatch portion of LREQ-GQL-070 are
  completed by Chunk 7A. No free-text `q`/`query` request construction, HTTP header
  construction, pagination, correlation-mode selection, retry/backoff, preflight
  execution, or bulk enrichment in this chunk.
- **No metric eligibility semantics in this chunk**: SHALL NOT implement
  published-state eligibility decisions, UTC/date normalization for metrics,
  future-date rejection, finite/non-negative eligibility, age thresholds, or
  page-view eligibility value ranges; SHALL NOT import `metrics` or `scoring`.
- **No I/O module imports**: SHALL NOT import `collector`, `collector_coveo`,
  `collector_graphql`, `database`, `pipeline`, `report`, `cli`, or `config` from
  `validation.py`.
- **No secret leakage**: `ValidationIssue.message`, `context`, and
  `summarize_validation_issues` SHALL NOT contain credential values,
  `Authorization` headers, CSRF tokens, cookies, or raw response bodies.
- **No frozen-interface edits**: SHALL NOT redefine or modify Chunk 0 enums,
  constants, record shapes, `ensure_utc`, or serialization helpers; SHALL NOT modify
  `tools/validate_traceability.py`, `tools/check_import_boundaries.py`, or any other
  chunk's files (see section 6 and resolved decision R-3).
- **No unmarked analytical tests**: every new `test_*` function SHALL carry an
  explicit `@pytest.mark.lreq("LREQ-...")` marker and a matching
  `tests/traceability.json` entry.

## 12. Resolved decisions, recorded assumptions, and flagged risks

### Resolved decisions

These are decisions made by the project owner; this plan records them and does not
re-open them.

- **R-1 — Scope reconciliation of matrix-only supporting rows.** The
  ownership-matrix rows that name Chunk 1 are authoritative. Chunk 1 authors tests
  only for the rows where it actually implements a structural/pure primitive:
  LREQ-EXT-050, LREQ-EXT-090 (discovery-status reason vocabulary), LREQ-GQL-010
  (shared canonical identity unit), LREQ-GQL-040 and LREQ-GQL-050 (structural half),
  LREQ-ID-020 (pure identity-compatibility comparison), LREQ-SMP-010
  (resolution-status/denominator-membership half). LREQ-GQL-020 and LREQ-GQL-030 are
  deliberately excluded from Chunk 1 testing — pure protocol/query-construction and
  response-correlation concerns owned by Chunk 5, with no Chunk-1-owned structural or
  identity angle. LREQ-EXT-010, LREQ-EXT-030, LREQ-EXT-040, and LREQ-CLI-040 get no
  Chunk 1 test; their required tests belong to Chunks 3 and 12. Section 9 is
  conformant with this decision.

- **R-2 — Content of identity-mapping rule `1.0.1`** (heading corrected
  2026-09-18: it previously read "Content of identity-mapping rule 1.0.0", which
  no longer matched the version this plan cites). Adopted as the normative content
  of LREQ-EXT-060 canonicalization, exactly as stated in section 5.2: `ec_product_id`
  and `permanentid` are trimmed then compared directly (as integers when both parse
  as numeric, else as strings) and treated as already canonical with no
  transformation; `clickUri`/`uri` contribute the trailing numeric identifier after
  the final `-` in the URL's last path segment, and a value not fitting that pattern
  contributes nothing rather than a wrong candidate; `resolve_canonical_identity`
  returns `resolved` on full agreement, `conflict` on any disagreement, `unresolved`
  when nothing is derivable. Equality is **strict after canonicalization** (rule
  `1.0.1`): a parseable URI-derived identifier that does not equal the explicit
  anchor is a `conflict`, not an agreement, and no suffix-tolerant comparison is
  part of this rule at any version
  (`interfaces/chunk-01.md` §4.1, "What `1.0.1` is"). The extraction half of this
  rule remains **inferred and NOT capture-verified** — the relaxation paragraph in
  `interfaces/chunk-01.md` §4.1 changes who may treat the obligation as satisfied,
  not whether the rule is verified (see section 5.2 and RN-1 below). The
  comparison and conflict logic follows directly from
  LREQ-EXT-070 and is considered settled. Provenance of the fixture shapes is the
  retired parent SRS (`Documents/retired-documents/SRS-revision2.md`, REQ-EXT-065 /
  OI-4), which is **NOT** normative; the rule text above is what this plan makes
  normative.

- **R-3 — Traceability-validator widening is deferred to Chunk 13.**
  `src/niche_scout/tools/validate_traceability.py` stays a Chunk 0 deliverable and is
  not modified, widened, or edited by Chunk 1. LREQ-NFR-060 (Chunk 13) owns the
  widening. Consequence: until Chunk 13 lands, the validator's required-set
  completeness direction is unusable for every chunk, so gate-verifier MUST manually
  cross-check the plan's section 3 LREQ table against the actual
  `@pytest.mark.lreq` markers in the test files, in both directions. The project
  owner intends this to become a standing line in the project rule's traceability
  section rather than being restated per chunk; this plan records the obligation only
  and does not edit the project rule.

- **R-4 — `models.py` is not touched, and this is not an assumption.**
  Identity-resolution status typing is a Chunk 0 deliverable, grounded in SRS §6.1's
  persisted `identity_mapping_rule_version` field and Chunk 0's own committed scope
  ("discovery, identity-resolution, operation, score, evidence, and rankability
  statuses"; "typed domain/result structures … for the complete SRS data model").
  Chunk 1 checks `Documents/interfaces/chunk-00.md` for it and consumes it.
  Escalation rule: if Chunk 0 did not actually deliver a type its own gate says it
  would, that is a Chunk 0 gate defect to escalate to the human — Chunk 1 must not
  patch around it in either direction, neither by adding the type itself nor by
  silently working without it.

- **R-5 — Taxonomy freshness boundary and reference time.** The boundary is
  inclusive: `age <= MAX_TAXONOMY_AGE_DAYS` (30) is fresh and `age > 30` is stale,
  following the SRS's own inclusive convention for `RECENT_WINDOW_DAYS`
  (`age <= RECENT_WINDOW_DAYS` counts; SRS §7.4). The constant is fixed by SRS
  Appendix A / §14 (`MAX_TAXONOMY_AGE_DAYS = 30`). The freshness reference is a
  caller-supplied timezone-aware UTC `reference_utc` argument; the concrete timestamp
  a caller passes is an orchestration-layer decision for Chunks 10 and 12 and is
  deliberately not pinned down here. Specifically, the caller does **not** pass
  `run_started_at_utc` "per §3.2 step 3": step 2 (taxonomy validation) runs before
  step 3 creates `run_id` and `run_started_at_utc`, so that value does not exist at
  validation time. Section 4.5 states this correctly and stays consistent with it.

- **R-6 — Cross-category duplicate ownership.** Chunk 1's obligation under
  LREQ-TST-030 is the pure pairwise property that two raw candidates originating from
  different categories can canonicalize to the same `asset_identity_key`, tested as a
  pure property test on `resolve_canonical_identity`. LREQ-TST-030's own definition
  row is scoped to `tests/test_identity.py` and depends only on LREQ-EXT-060/070,
  LREQ-GQL-070, and LREQ-GQL-080, with nothing about counting or persistence.
  Duplicate marking, counting, overlap metrics, and persistence stay in Chunks 3, 4B,
  and 6B; Chunk 1 SHALL NOT implement them.

### Flagged risks (downstream verification obligations, not blockers on freezing this plan)

- **RN-1 — The URI trailing-numeric-segment rule is unverified against real data
  (restated 2026-09-18 as status-with-pointer; the paragraph below previously
  carried this plan's own unconditional obligation text — "Chunk 3 (the
  LREQ-EXT-060 integration completion chunk) SHALL sanity-check this rule against
  real redacted fixtures before treating it as final" — which the human ruling
  superseded. It is reproduced here as the record of what this plan said, and it
  does NOT state the obligation's satisfaction condition any longer: that lives in
  `interfaces/chunk-01.md` §4.1, "Satisfaction condition of the caveat above —
  explicitly RELAXED by human ruling", with the residual exposure recorded in the
  same §4.1 at "The exposure deferral leaves open".)** The `clickUri`/`uri`
  parsing half of mapping rule `1.0.1` (R-2) is inferred from the retired
  parent-SRS fragment (`Documents/retired-documents/SRS-revision2.md`, OI-4 /
  REQ-EXT-065) plus general Unity Asset Store URL conventions. It has **NOT** been
  verified against a real captured Coveo response, and **no such capture exists
  anywhere in this repository**: the only capture in the tree is a **request**
  capture (`config/coveo_search_template.json`), which cannot settle a
  response-side extraction question. Chunk 3 (the LREQ-EXT-060 integration
  completion chunk) did **not** discharge the check and does not claim to have
  done so (`interfaces/chunk-03.md` §8;
  `Documents/plans/chunk-03-coveo-discovery-adapter-and-streamed-raw-persistence.md`
  §12.9). `IDENTITY_MAPPING_RULE_VERSION` exists precisely so a correction is
  cheap; `1.0.1` was such a correction, and it deliberately left extraction
  untouched. The obligation is **OPEN and owned by no chunk**, recorded in
  `requirements-dependency-map.md` §6.4 as a "Deferred obligation with no owning
  chunk" with **Owner: none**; **relaxed is not verified**, and no artifact in
  this repository may state or imply that the rule was verified against a real
  Coveo response. This is a downstream verification obligation, not an unresolved
  human decision and not a blocker on freezing this plan.

Section 12 contains no unresolved human decisions. R-1…R-6 are decided; RN-1 is a
downstream verification obligation that owns no chunk (2026-09-18: this closing
sentence previously ended "RN-1 is a downstream Chunk 3 verification obligation",
naming Chunk 3 as its home; the obligation is now recorded as owned by no chunk,
and its satisfaction condition was relaxed by human ruling — see RN-1 above).
