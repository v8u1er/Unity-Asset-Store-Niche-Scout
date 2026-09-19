# Chunk 5 — GraphQL protocol adapter and response correlation

Status: FROZEN
Depends on (frozen interfaces required before this plan can be trusted):
  Documents/interfaces/chunk-00.md (Status: VERIFIED)
  Documents/interfaces/chunk-01.md (Status: VERIFIED)
  Documents/interfaces/chunk-02.md (Status: VERIFIED) — read-only freeze check; no
  runtime dependency and no import (see §4.3 and §11)
  Documents/interfaces/chunk-03.md (Status: VERIFIED) — **added 2026-09-18**: the
  Coveo discovery adapter's published contract, which fixes the ownership boundary
  §2's Coveo bullets describe. Read for this header; **no runtime dependency and no
  import** (see §12.6 item 4, which records that §11's prohibitions are already
  sufficient and therefore adds no new prohibition text)
Last amended: 2026-09-18 — retroactive authorship, the node-5/node-6 rulings, and the
freeze. See §12.6 item 1 for the provenance record and §12.6 item 7 for the record of
this freeze and of the §12.5 header correction. (★)

(★) This plan was **authored retroactively against existing code**: it was written after
`collector_graphql.py` had already been implemented (see §12.6 item 1). The operator
ruled that retroactive authorship is an **accepted defect of provenance** rather than a
disqualifying one, **on the basis that this plan's content was independently verified**
— requirement text matched against `Documents/SRS-lean.md`, the §10 gate bullets matched
verbatim against the dependency map's Chunk 5 Gate list, and the §9/§11 test markers
confirmed against existing `tests/traceability.json` entries with none guessed. The
freeze rests on that external verification; it is not an inference drawn from anything
this document says about itself.

Blocks (chunks whose plan/implementation needs this chunk's interface):
  Chunk 6A (Identity preflight planner and gate)
  Chunk 6B (Unique enrichment executor and persistence)
  Chunk 7A (Metric eligibility, date, and page-view primitives)
  Chunk 10 (Pipeline orchestration)

## 1. Goal

Today `src/niche_scout/collector_graphql.py` is a two-line docstring and there is
no way to build, send, or interpret a Unity GraphQL enrichment response. This
chunk makes the GraphQL protocol layer real and reusable: it builds the
two-operation batch request (`ProductDetail` / `ProductPageViews`) for one
canonical identity, correlates each returned item to its operation by an explicit
correlation key (never a positional guess), records an independent operation
status per operation, retains a valid operation's fields when the other fails
(leaving failed fields `None`, never `0`), validates the page-view scalar's type
and range, applies Chunk 1's identity-alias comparison and state annotation to the
returned data, and classifies each failure class into a retry/backoff or
permanent-failure policy. It deliberately stops before deciding whether any bulk
enrichment is allowed: the adapter *annotates* and returns typed results, and the
identity preflight gate (Chunk 6A) and the unique-enrichment executor (Chunk 6B)
decide and perform enrichment. The typed surface is published as
`Documents/interfaces/chunk-05.md` after the gate so Chunks 6A, 6B, 7A, and 10 can
build against it without reading source.

## 2. Scope

### In scope

- The two-operation batch request builder for one canonical `asset_identity_key`:
  `ProductDetail(id: ID!)` and `ProductPageViews(packageId: String!)`, both bound
  to the same canonical identity (LREQ-GQL-010, LREQ-GQL-020).
- The lean `ProductDetail` selection set: product identity aliases,
  `rating.average`, `rating.count`, `reviewCount`, `firstPublishedDate`, `state`,
  `category`, `publisher`; and the separate `ProductPageViews` scalar selection
  (LREQ-GQL-020). Fields not required by scoring are omitted.
- Request-shape typing: operation names, operation order, variables, the JSON
  array-of-exactly-two-operations body, and a header mapping built from pinned
  constants plus a caller-supplied CSRF credential. `ENDPOINT_CONTRACT_VERSION`
  (frozen at `"1.0.0"` by Chunk 0) and the endpoint value are recorded as
  single-sourced constants, never invented at a call site. No version bump: the
  endpoint, method, batch shape, and `operations` header are unchanged from the
  parent contract, and adding response-correlation and retry logic is internal to
  Chunk 5 (§12 Q1).
- Response correlation: `operationName` correlation — the explicit correlation key
  LREQ-GQL-030 names first — supplied by the response item itself; detection and
  typed classification of missing, duplicated, unknown, and ambiguous associations;
  reversed-order handling; acceptance of a caller-supplied `validated_position` mode
  without the adapter itself validating that position (LREQ-GQL-030). The key is
  never inferred from response position (§12 Q3).
- Independent operation-level status for both operations, with every failure class
  named in LREQ-GQL-040 mapped to an operation error (HTTP failure, top-level
  `errors`, operation-level `errors` on HTTP 200, null required data, wrong data
  shape, wrong scalar type, boolean/negative/non-finite page views, invalid state
  values, missing identity) (LREQ-GQL-040).
- Partial-success retention: a valid operation's fields are retained when the other
  operation fails; failed fields stay `None`, never `0` or another default
  (LREQ-GQL-050).
- Page-view type/range validation: a non-negative, finite, integral scalar of a
  numeric type; `bool`, negative, non-finite, non-integral, and wrong-shaped
  values are operation errors (LREQ-GQL-040).
- **A ruled correction to the required-member set that this plan has not yet been
  amended for (recorded 2026-09-18).** `PRODUCT_DETAIL_REQUIRED_MEMBERS`
  (`src/niche_scout/collector_graphql.py:876-885`) contains `"state"` today, so the
  structural check at `:1050-1055` still asks Chunk 1 for a
  `response_missing_required_member` / `response_null_required_member` verdict on it.
  The operator has **ruled** that `state` leaves that group: correction is
  `Documents/plans/chunk-03-coveo-discovery-adapter-and-streamed-raw-persistence.md`
  §12.13(i), and the disposition, mechanical proof, and the associated E7 correction
  are §12.6 item 2 below. **The code was not changed in this dispatch** — this is a
  plan record, not a completed fix — so §8's E7 text still reads its pre-ruling
  wording and §12.6 item 2 is gate work through bullets 1–6 (§12.6 item 2(f)).
- **Identity-mismatch handling, in full.** The returned aliases are compared with
  the requested canonical identity through Chunk 1's primitive, the mismatch is
  recorded as a flag plus a redacted reason, and the affected result's scored
  fields are surfaced as unavailable-by-mismatch (LREQ-GQL-070, adapter portion).
- State eligibility *annotation*: the returned `state` is annotated through Chunk
  1's primitive and recorded; state-excluded and state-unknown assets remain in
  persisted observations and discovered breadth (LREQ-GQL-060, adapter portion).
- A typed pre-record value (`EnrichmentObservationDraft`) that maps 1:1 onto the
  frozen `EnrichmentObservationRecord`, plus a builder that takes an
  explicitly supplied UTC `retrieved_at_utc`; `request_metadata_json` carrying
  operation names, correlation keys, correlation mode, HTTP status, response hash
  when available, and retry/error metadata, with no credentials and no full
  response bodies (SRS-lean §6.5).
- Credential gating at the adapter boundary: a GraphQL request builder SHALL NOT
  produce a request until `Credentials.require_for_collection()`-equivalent
  validation has passed with the caller-supplied credential (LREQ-SEC-010).
- Redaction at the adapter boundary: no credential, `Authorization` header, CSRF
  token, cookie, or full response body may appear in any error summary, any
  warning, or `request_metadata_json` (LREQ-SEC-020). **Ruled deviation recorded
  2026-09-18:** the implementation currently redacts the operation names and
  correlation keys too, so `request_metadata_json` does **not** carry the real
  values §5.10's own table requires at `:1080-1081`; the correction is §12.6 item 3
  and has **not** been applied in this dispatch.
- Failure isolation: a per-identity protocol failure produces a typed failed result
  and never raises out of the adapter in a way that aborts unrelated identities
  (LREQ-NFR-030, adapter portion).
- Retry/backoff classification internal to a Chunk 5-owned `GraphQLRetryPolicy`
  (module constants `DEFAULT_*`): retry `429` and `5xx` with exponential backoff up to
  a bounded attempt count; never retry authentication, CSRF, malformed-request, or
  authorization failures indefinitely. Chunk 5 does **not** claim `LREQ-EXT-100`, which
  Chunk 3 owns, and keys no idempotency or attempt tracking off `sentry-trace` (§12 Q4).
- Test modules `tests/test_collector.py` (**modified**, not new — it already exists
  at 2532 lines (corrected 2026-09-18: this previously read "1310 lines", the
  pre-Chunk-5 count; see §12.2 item 9) as Chunk 3's frozen Coveo test module; Chunk 5 appends new GraphQL
  nodes only) and `tests/test_identity.py` (modified), a new local fixture module,
  and the corresponding new `tests/traceability.json` entries.

### Explicitly out of scope (and who owns it instead)

Scope items that are *deferred or omitted deliberately* rather than owned by another
chunk — Cookie construction (O-4, closed as a Chunk 5 scope question; OI-6 itself
remains open in §12.5), contradiction detection, and the
capture-derived golden test leg (O-2) — are recorded with their reasons in §12.3;
§12.5 lists what remains open.

- **Metric eligibility and D/R/Q exclusion.** Chunk 5 is the *supporting chunk* for
  `LREQ-GQL-060` and `LREQ-GQL-070`. The **primary implementation chunk** for
  `LREQ-GQL-060` is **Chunk 7A**, and Chunk 7A is the **integration completion
  chunk** for the metric-eligibility portion of `LREQ-GQL-060` and the metric
  identity-mismatch eligibility portion of `LREQ-GQL-070`. Chunk 5 annotates state
  and records the mismatch; it does not exclude anything from D, R, or Q and does
  not decide whether a value contributes to a metric.
- **Preflight position validation.** `validated_position` correlation mode is
  validated by the **primary implementation chunk Chunk 6A** (LREQ-ID-020: "the
  operation-correlation mode is valid"). Chunk 5 only accepts a
  `GraphQLOperationCorrelationMode` value that the caller supplies and refuses to
  validate position itself; if the mode is not `explicit_key` and no validated
  position has been supplied, both operations are marked malformed.
- **Bulk enrichment and the preflight gate.** `LREQ-GQL-080` is owned by the
  **primary implementation chunk Chunk 6B** (supporting chunks Chunk 2, Chunk 5,
  Chunk 6A). The gate itself is Chunk 6A ("Failed preflight prevents bulk
  enrichment", "Preflight executes the normal GraphQL request through the reusable
  Chunk 5 adapter"). Chunk 5 issues at most the two named operations for the single
  identity it is given and never issues a bulk-enrichment request.
- **Persistence.** Chunk 2 is the **primary implementation chunk** for
  persistence and the **supporting contract chunk** for `LREQ-GQL-080`. Writing
  `EnrichmentObservationRecord` rows, the at-most-once-per-identity decision, and
  the join of one enrichment to every referencing category are Chunks 6A/6B.
  Chunk 5 returns a pre-record value and does not import `database`.
- **Run orchestration, run/category status policy, warning emission into a category
  row, logging, and report rendering.** Chunk 6B and Chunk 10 own orchestration and
  `LREQ-NFR-020`'s log line; Chunk 10 is the **primary implementation and completion
  chunk** for `LREQ-NFR-030`; Chunks 10/11/12 own status transitions and the report.
  Chunk 5 only names the `WarningCode` members it contributes and never writes a
  warning onto a category row.
- **Coveo discovery, pagination, and `LREQ-EXT-100` as such.** `LREQ-EXT-100`
  is primarily owned and completed by **Chunk 3** (dependency map line 59), whose plan
  is now frozen and whose `collector_coveo.py` is implemented; no
  `Documents/interfaces/chunk-03.md` exists yet, so Chunk 5 consumes none of it. Chunk 5
  implements an independent GraphQL retry policy under its own `GraphQLRetryPolicy` and
  does **not** claim `LREQ-EXT-100`; no shared `transport.py` or shared retry module is
  created (§12 Q2, Q4).
- **Page-view semantics at run level.** `PageViewSemanticsStatus` and the run-level
  `validated_cumulative`/`contradicted` decision are not computed, returned, or
  persisted by Chunk 5 (`interfaces/chunk-02.md` confirms the column exists on `runs`
  and is writable through `update_run_preflight`). Ownership is split, and **no part of
  it is Chunk 5's**: Chunk 6A initializes the run-level value, Chunk 7B detects
  `contradicted`, and Chunk 8 applies contradicted page-view handling (§12 Q5). The
  concrete contradiction-detection rule is deliberately unspecified in Chunk 5 — a
  scoped omission, because detection would need cross-run state and Chunk 5 is a
  single-run adapter — and is Chunk 7B's plan-time decision to specify. Chunk 5 neither
  adds an enum member nor sets a value. Contradiction detection is **not** a
  `LREQ-MET-040` obligation either: that requirement's eligibility list (finite
  non-negative value, valid UTC date no later than cutoff,
  `age_days_exact >= MIN_AGE_DAYS_FOR_RATE`, matched published identity) is jointly
  necessary and sufficient for index usability and contains no cross-run monotonicity
  condition (§12 Q5, O-1 closed).

## 3. Requirements this chunk must satisfy

Ownership roles are the exact labels from
`Documents/requirements-dependency-map.md` "Ownership and test traceability
matrix" (lines 45–136); normative text is quoted from `Documents/SRS-lean.md`.

| LREQ ID | Ownership role here | Normative text (from SRS-lean.md, quoted/derived) | SRS section |
|---|---|---|---|
| LREQ-GQL-010 | **Primary implementation chunk**; Supporting chunks: Chunk 0, Chunk 1; Completion chunk: Chunk 5. (Matrix row, line 60.) | "**LREQ-GQL-010**: Enrichment SHALL use the parent SRS GraphQL batch endpoint and the two required operations: `ProductDetail(id: ID!)` and `ProductPageViews(packageId: String!)`. Both operations SHALL use the same canonical `asset_identity_key`." (lines 289–292.) | §4.2 GraphQL enrichment |
| LREQ-GQL-020 | **Primary implementation chunk**; Supporting chunk: Chunk 1; Completion chunk: Chunk 5. (Matrix row, line 61.) | "**LREQ-GQL-020**: The `ProductDetail` operation SHALL request product identity aliases, `rating.average`, `rating.count`, `reviewCount`, `firstPublishedDate`, `state`, `category`, and `publisher`. The separate `ProductPageViews` operation SHALL request its page-view scalar. Fields not required by scoring MAY be omitted from the lean implementation." (lines 294–298.) | §4.2 |
| LREQ-GQL-030 | **Primary implementation chunk**; Supporting chunk: Chunk 1; Completion chunk: Chunk 5. (Matrix row, line 62.) | "**LREQ-GQL-030**: GraphQL response items SHALL be associated by explicit operation name or another validated correlation key. Response position alone SHALL NOT be trusted unless separately validated as an endpoint guarantee." "Reversed operation order SHALL be handled through that correlation key. Missing, duplicated, unknown, or ambiguous associations SHALL be recorded as malformed operation results; the implementation SHALL never guess from response position." "If the live response provides no explicit operation name or correlation key, the implementation MAY use response position only after the identity preflight validates the fixed two-operation ordering and expected operation-specific response shapes across the selected preflight identities. The persisted correlation mode SHALL be either `explicit_key` or `validated_position`. If neither mode is validated, both operations SHALL be marked malformed and their fields SHALL remain unavailable." "For a scalar `ProductPageViews` response, request-scoped identity validation through the associated `ProductPageViews(packageId: ...)` operation is sufficient; the scalar response is not required to repeat the package identifier." (lines 300–316.) | §4.2 |
| LREQ-GQL-040 | **Primary implementation chunk**; Supporting chunk: Chunk 1; Completion chunk: Chunk 5. (Matrix row, line 63.) | "**LREQ-GQL-040**: Each operation SHALL have an independent status. HTTP failures, top-level GraphQL `errors`, HTTP 200 responses with an operation-level `errors` member, null required data, wrong data shape, wrong scalar type, boolean/negative/non-finite page views, invalid state values, or missing identity SHALL be recorded as an operation error. A top-level error SHALL not be treated as a successful operation merely because another operation in the same response succeeded." (lines 318–323.) The "wrong scalar type" and "boolean/negative/non-finite page views" clauses are the source of the page-view type/range rule in §8; the exact scalar acceptance rule is derived there, not invented. | §4.2 |
| LREQ-GQL-050 | **Primary implementation chunk**; Supporting chunks: Chunk 1, Chunk 2; Completion chunk: Chunk 5. (Matrix row, line 64.) | "**LREQ-GQL-050**: A valid operation's fields MAY be retained when the other operation fails. Failed fields SHALL remain null or unavailable; they SHALL NOT be filled with zero or another default." (lines 325–327.) | §4.2 |
| LREQ-GQL-060 | **Supporting chunk** (adapter/annotation portion only). Primary implementation chunk: Chunk 7A; Supporting chunks: Chunk 1, Chunk 5; Completion chunks: Chunk 5, Chunk 7A. (Matrix row, line 65.) | "**LREQ-GQL-060**: Only `state = "published"` assets are eligible for D, R, and Q. State-excluded and state-unknown assets remain part of discovered breadth." (lines 329–330.) Chunk 5's share: annotate the returned `state` through `annotate_state_eligibility`, persist the annotation/state value into the pre-record value, and keep the asset in persisted observations and discovered breadth. The D/R/Q eligibility decision is **not** made here; the dependency map's gate states "The metric-eligibility portion of LREQ-GQL-060 ... are not complete until Chunk 7A applies them to metric inputs." (line 681.) | §4.2 |
| LREQ-GQL-070 | **Primary implementation chunk (adapter portion)**; Supporting chunk: Chunk 1; Completion chunks: Chunk 5, Chunk 7A. (Matrix row, line 66.) | "**LREQ-GQL-070**: If returned GraphQL identity aliases do not agree with the requested canonical identity, the asset SHALL be marked `id_mapping_mismatch` and excluded from D, R, and Q." (lines 332–334.) Chunk 5 owns the `id_mapping_mismatch` marking and the "returned aliases disagree with requested identity; mismatch must invalidate affected result" edge case (dependency map line 174); the D/R/Q exclusion is Chunk 7A. | §4.2 |
| LREQ-SEC-010 | **Supporting chunk** (adapter boundary only). Primary owner: Chunk 0; Supporting chunks: Chunk 3, Chunk 5, Chunk 12; Completion chunks: Chunk 3, Chunk 5, Chunk 12. (Matrix row, line 68.) | "**LREQ-SEC-010**: Coveo and Unity CSRF credentials SHALL be read from environment variables and SHALL be required before network collection." (lines 348–349.) Chunk 0 owns environment reading (`get_credentials`, `UNITY_CSRF_TOKEN_ENV`, `Credentials.require_for_collection()`), verified. Chunk 5's share: the GraphQL request builder SHALL require a non-empty Unity CSRF credential before it produces a request, and SHALL NOT read the environment itself. No exception message may echo any part of the credential value. | §4.3 Credentials and security |
| LREQ-SEC-020 | **Supporting chunk**, adapter boundary only. Primary owner: Chunk 2; Supporting chunks: Chunk 0, Chunk 3, Chunk 5; Completion chunk: Chunk 13. (Matrix row, line 69.) | "**LREQ-SEC-020**: Secrets SHALL NOT be written to source control, logs, SQLite, or error messages. The `.env` pattern SHALL be ignored by version control." (lines 351–352.) Chunk 5's share: no credential, `X-CSRF-Token` value, `_csrf` cookie value, `Authorization` header, or full response body may appear in a `ValidationIssue`, an error summary, a warning, or `request_metadata_json`. | §4.3 |
| LREQ-NFR-030 | **Supporting chunk** (adapter portion only). Primary owner: Chunk 10; Supporting chunks: Chunk 3, Chunk 5, Chunk 6A, Chunk 6B; Completion chunk: Chunk 10. (Matrix row, line 123.) | "**LREQ-NFR-030**: A failed page or sampled asset SHALL not abort unrelated categories or assets; the failure SHALL remain visible in status and evidence fields." (lines 1168–1169.) Chunk 5's share: one identity's protocol failure (HTTP failure, malformed response, both operations malformed, identity mismatch) yields a typed failed `EnrichmentResult` and never propagates an exception that would abort another identity's enrichment. Visibility in status/evidence fields of the run is the completion chunk's. | §11 Non-functional requirements |

Req IDs the plan's LREQ table deliberately does **not** claim, and why:
`LREQ-SEC-020`'s SQLite clause and `LREQ-GQL-080` are owned by Chunks 2 and 6B (see
§2 out-of-scope); `LREQ-EXT-060` is Chunk 1/Chunk 3; `LREQ-ID-020` is Chunk 6A;
`LREQ-TST-040` and `LREQ-TST-080` are Chunk 13's requirements (A.2 lists Chunk 5 as
a supporting chunk for both). Chunk 5 authors the `test_collector.py` tests that A.2's
row 300 of the dependency map names for `LREQ-TST-040`, but attaches neither marker;
the operator has confirmed that placement (§12 Q6), and `LREQ-TST-040` is deferred to
Chunk 13 as a marker-edit-only change.

## 4. Interface contracts consumed

### 4.1 Frozen interfaces this chunk may consume

Copied from `Documents/interfaces/chunk-00.md`, `chunk-01.md`, and `chunk-02.md`.
Chunk 5 SHALL NOT redefine any of these names and SHALL NOT edit `models.py`,
`validation.py`, or `database.py`.

**From Chunk 0 (`niche_scout.models`, interface §2–§4.2):**

```python
class OperationStatus(str, Enum): SUCCESS = "success"; ERROR = "error"
class GraphQLOperationCorrelationMode(str, Enum):
    EXPLICIT_KEY = "explicit_key"; VALIDATED_POSITION = "validated_position"
class PageViewSemanticsStatus(str, Enum):
    UNVALIDATED = "unvalidated"; VALIDATED_CUMULATIVE = "validated_cumulative"
    CONTRADICTED = "contradicted"
class WarningCode(str, Enum):  # GRAPHQL_* and STATE_EXCLUDED members used here
    GRAPHQL_PRODUCT_ERROR = "GRAPHQL_PRODUCT_ERROR"
    GRAPHQL_PAGE_VIEWS_ERROR = "GRAPHQL_PAGE_VIEWS_ERROR"
    GRAPHQL_ID_MAPPING_MISMATCH = "GRAPHQL_ID_MAPPING_MISMATCH"
    STATE_EXCLUDED = "STATE_EXCLUDED"
ENDPOINT_CONTRACT_VERSION: str = "1.0.0"

@dataclass(frozen=True)
class EnrichmentObservationRecord(_UtcRecord):
    run_id: str; asset_identity_key: str
    product_detail_status: str; page_views_status: str
    graphql_id: str | None; product_id: str | None
    rating_average: float | None; rating_count: int | None; review_count: int | None
    first_published_date_utc: datetime | None
    publisher_json: str | None; category_json: str | None; state: str | None
    product_page_views: int | None; id_mapping_mismatch: bool
    product_detail_error_summary: str | None; page_views_error_summary: str | None
    request_metadata_json: str; retrieved_at_utc: datetime

def ensure_utc(value: datetime) -> datetime
def to_json_dict(instance: Any) -> dict[str, Any]
def to_json(instance: Any) -> str
```
`EnrichmentObservationRecord._utc_fields == ("first_published_date_utc",
"retrieved_at_utc")` and `__post_init__` rejects a naive datetime. Datetime fields
serialize to ISO-8601 UTC; `None` round-trips as `None`. Status fields are stored
as the enum `value` (str).

**Correlation-mode vocabulary: the two members above are the whole frozen enum, and
that closure is what forces the local vocabulary (§5.5, §12.1 O-3).** The frozen
Chunk 0 contract — both `Documents/interfaces/chunk-00.md` line 66 and
`src/niche_scout/models.py` lines 132–134 — defines
`GraphQLOperationCorrelationMode` with exactly two members, `EXPLICIT_KEY` and
`VALIDATED_POSITION`, and **no enum extension is authorized**. The earlier
`EXCLUDED = "excluded"; CANDIDATE = "candidate"` line that appeared inside this copy
block is **deleted**: listing members the frozen enum does not have, inside a block
whose header forbids redefinition, contradicted the block's own header. Chunk 5
SHALL NOT edit `models.py` or `interfaces/chunk-00.md`, and no coordination task to
extend the enum is proposed or open.

The SRS closes the *persisted* domain to the same two values. `LREQ-GQL-030`
(`Documents/SRS-lean.md` lines 310–312): "The persisted correlation mode SHALL be
either `explicit_key` or `validated_position`. If neither mode is validated, both
operations SHALL be marked malformed and their fields SHALL remain unavailable."
Because a third value can never be persisted, the adapter-internal dispositions
cannot live on the enum: they are held locally in `collector_graphql.py` as
`GraphQLCorrelationDisposition` (§5.5). The containment rule is therefore not merely
what keeps that local vocabulary *safe*; it is what makes it the *required* design.
Chunk 5's `EXCLUDED`/`CANDIDATE` dispositions are non-persisted and adapter-internal.
Corroborating the two-value persisted domain: `LREQ-ID-020` (`SRS-lean.md` line 371)
requires the preflight to verify "the operation-correlation mode is valid", and
`SRS-lean.md` lines 413–414 require `identity_preflight_summary_json` to carry "the
selected `graphql_operation_correlation_mode`" — a summary field with exactly two
possible values, both of which are members of the frozen enum above.

**From Chunk 0 (`niche_scout.config`, interface §5):**

```python
UNITY_CSRF_TOKEN_ENV = "NICHESCOUT_UNITY_CSRF_TOKEN"
COVEO_TOKEN_ENV = "NICHESCOUT_COVEO_BEARER_TOKEN"

@dataclass(frozen=True)
class Credentials:
    coveo_token: str
    unity_csrf_token: str
    @property
    def coveo_bearer_token(self) -> str: ...
    def require_for_collection(self) -> None:   # raises ValueError if either empty

def get_credentials(environ: Optional[Mapping[str, str]] = None) -> Credentials
```

**From Chunk 1 (`niche_scout.validation`, interface §3–§5):**

```python
@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: str; message: str; context: dict[str, Any]
    def to_json(self) -> str: ...

@dataclass(frozen=True, slots=True)
class GraphQLIdentityComparisonResult:
    matches_requested_identity: bool; id_mapping_mismatch: bool
    reason: str | None
    compared_aliases: tuple[tuple[str, str], ...]
    issues: tuple[ValidationIssue, ...]

@dataclass(frozen=True, slots=True)
class StateEligibilityAnnotation:
    state_value: str | None; is_published: bool
    state_excluded: bool; state_unknown: bool
    remains_in_discovered_breadth: bool          # always True (annotation only)

@dataclass(frozen=True, slots=True)
class StructuralValidationResult:
    is_valid: bool; expected_shape: str; actual_shape: str | None
    issues: tuple[ValidationIssue, ...] = ()

def compare_graphql_identity_aliases(
    requested_identity: str, aliases: Mapping[str, object], *,
    mapping_rule_version: str = IDENTITY_MAPPING_RULE_VERSION,
) -> GraphQLIdentityComparisonResult
def annotate_state_eligibility(state_value: object) -> StateEligibilityAnnotation
def validate_response_shape(
    payload: object, *, expected_shape: str,
    required_members: Sequence[str] = (),
    field_types: Mapping[str, type | tuple[type, ...]] | None = None,
) -> StructuralValidationResult
def validate_requested_categories(payload: object, requested_categories: Sequence[str]) -> TaxonomyValidationResult
def redact_value(value: object) -> str
def summarize_validation_issues(
    issues: Sequence[ValidationIssue], *, max_context_chars: int = 256
) -> str
```
Chunk 1's frozen contract statements that bind this chunk: "**This contract is
structural only.** None of these functions decides whether a value is *usable for a
metric*" (interface preamble), "`annotate_state_eligibility` is an annotation, not a
decision: `remains_in_discovered_breadth` is always `True` and the result exposes no
D/R/Q eligibility attribute" (§5), and "Redaction — `ValidationIssue.message`/
`context`, `redact_value`, and `summarize_validation_issues` never include credential
values, `Authorization` headers, CSRF tokens, cookies, or full response bodies"
(§5). Issue codes emitted by Chunk 1 that Chunk 5 consumes:
`response_missing_required_member`, `response_null_required_member`,
`response_wrong_scalar_type`, `response_wrong_container_kind`,
`response_missing_identity`.
Chunk 1 also carries the caveat that `IDENTITY_MAPPING_RULE_VERSION = "1.0.0"`'s URI
rule is *inferred*, not verified against a real capture, and that consumers SHALL
branch on `IdentityResolutionResult.mapping_rule_version` (§4.1). Chunk 5 is a
consumer of the comparison result, not of the URI rule's correctness.

**From Chunk 2 (`niche_scout.database`, interface §2.7/§3/§6)** — a read-only freeze
check, not a runtime dependency:

```python
def insert_enrichment_observations(self, observations: Sequence[EnrichmentObservationRecord]) -> None
def upsert_enrichment_observation(self, observation: EnrichmentObservationRecord) -> None
def get_enrichment_observation(self, run_id: str, asset_identity_key: str) -> Optional[EnrichmentObservationRecord]
def count_distinct_enrichment_identities(self, run_id: str) -> int
```
`enrichment_observations` primary key `(run_id, asset_identity_key)`; "No fabricated
values — no `value or 0` ... `enrichment_observations.product_page_views` round-trips
as `NULL` on a failed PageViews operation" (§3); and "No at-most-once enrichment
decision, preflight gate, or result join to referencing categories — Chunks 6A/6B"
(§4). Chunk 5's typed pre-record value is judged correct exactly when each of its
fields can be supplied to that record without a `0` sentinel anywhere.

**From Chunk 0 (`DatabaseError`)**: not imported by Chunk 5.

### 4.2 What this chunk may NOT assume

- **The Coveo half of the facade is Chunk 3's, and Chunk 5 does not claim it.**
  Chunk 3's Coveo adapter `collector_coveo.py` is now implemented and Chunk 3's plan
  is frozen, but there is still no frozen `Documents/interfaces/chunk-03.md`, so
  Chunk 5 assumes nothing about `collector_coveo`'s public surface. `collector.py` is
  5 lines today (docstring, blank, two wildcard re-exports, trailing newline); Chunk 5
  edits **line 4 only** and leaves line 3 byte-identical (§5.0, §12.4 A3). Chunk 5
  SHALL keep `collector.py` a facade and SHALL NOT import `collector_coveo`.
- Chunk 1 supplies no network, HTTP, request construction, retry, or rate limiting
  (interface §6). Every transport concern in this chunk is new.
- Chunk 1 does not attach a warning code to a `ValidationIssue`; the
  `WarningCode` vocabulary is Chunk 0's and Chunk 5 only *names* the codes it would
  contribute; the actual warning list on a category is Chunk 10's.

### 4.3 Transport dependency (binding plan decision, §12.4 Q2)

`pyproject.toml` declares `dependencies = []` and `requires-python = ">=3.11"`, so
no HTTP client is available. This plan therefore specifies the adapter's request
building, response parsing, correlation, classification, and retry *policy* as pure
functions over a caller-supplied transport callable, so the adapter is testable with
mocked transports and adds no dependency. A caller-supplied transport callable per
adapter, no shared `transport.py`, and `collector.py` staying a logicless facade are
the decision this plan makes; it is **not derived from any SRS text**. The
authoritative, binding statement of the decision — including what may rely on it and
how it is reopened — is §12.4 Q2. This subsection explains the design; §12.4 Q2 is
the location of record, and neither may diverge from the other.

## 5. Interface contract this chunk produces

This section becomes `Documents/interfaces/chunk-05.md` verbatim once frozen. All
names live in `src/niche_scout/collector_graphql.py` and are re-exported by the
`collector.py` facade. Everything is additive: nothing in `models.py`,
`validation.py`, `config.py`, or `database.py` is redefined or shadowed.

### 5.0 Module and boundary rules

| Item | Kind | Rule |
|---|---|---|
| `src/niche_scout/collector_graphql.py` | **I/O** | GraphQL protocol: request construction, correlation, classification, pure retry policy, response hash. No `sqlite3`, no `metrics`, no `scoring`, no `pipeline`, no `report`, no `cli`, no `database`, no `collector_coveo` import. |
| `src/niche_scout/collector.py` | **Facade** | Line 4 only: `from .collector_graphql import *` is replaced by explicit-name re-exports drawn from `collector_graphql.__all__`. **Line 3 (`from .collector_coveo import *`) stays byte-identical.** Stays a facade over two independent adapters, with no behavior. |

Justification (module-boundary rule, `AGENTS.md` + `src/niche_scout/AGENTS.md`):
`collector_graphql.py` is already the sanctioned I/O home for the GraphQL adapter
("I/O and orchestration live only in `collector.py`, `database.py`, `pipeline.py`,
`report.py`, `cli.py`" extended by `src/niche_scout/AGENTS.md` to
`collector_graphql.py`), and Chunk 3 will write `collector_coveo.py` in parallel.
Putting the public surface on the adapter module and letting the facade re-export it
keeps Coveo and GraphQL independently importable and independently testable, and
keeps a wildcard-free facade from silently shadowing a name once both adapters exist.

```python
# collector_graphql.py
__all__: tuple[str, ...]         # exactly the public names in §5.2–§5.10

# collector.py — line 3 unchanged, line 4 replaced
from .collector_coveo import *                         # line 3: byte-identical
from .collector_graphql import (                       # line 4: explicit names, no "*"
    PRODUCT_DETAIL_OPERATION_NAME, PRODUCT_PAGE_VIEWS_OPERATION_NAME,
    GRAPHQL_BATCH_ENDPOINT, ...,
)                                                      # names drawn from __all__
```
`src/niche_scout/collector.py` is 5 lines today: a docstring, a blank line, the two
wildcard re-exports, and a trailing newline. **Only line 4 changes.** Line 4's
`from .collector_graphql import *` becomes an explicit-name re-export list drawn from
`collector_graphql.__all__`, so the facade's GraphQL half is order-independent and
cannot silently shadow a name. **Line 3 is byte-identical** — this plan does not open,
close, extend, or reorder the `collector_coveo` import, and it is *not* an "additive
alongside" change to a wildcard kept for Coveo's sake: the Coveo half is left exactly
as it is, as a whole. Chunk 3's frozen plan claims a conditional edit at its line 414
("the edit adds the `__all__` re-export path if the star-import does not propagate the
intended surface") and a prohibition at its line 741 ("Must not edit `collector.py`
beyond the single `__all__`/re-export line"); whether line 3 eventually moves is
Chunk 3's call, recorded as an open coordination item in §12.4 A3 — Chunk 5 does not
make it. Consequence: the facade can re-export a GraphQL name only after
`collector_graphql.__all__` exists, which is correct — the facade re-exports only what
exists.

**The ordering/shadowing hazard this removes is invisible when either plan is read
alone.** Read in isolation, Chunk 5's explicit re-export list looks like a pure
improvement and Chunk 3's wildcard import looks unreachable-by-Chunk-5; read together,
the two halves of one 5-line file are edited by two chunks whose plans each describe
only their own half. With two wildcard imports, a name defined by *both* adapters
would silently take the last import's binding, and Chunk 3's conditional line-3 edit
(Chunk 3's plan line 414) would change that binding order without Chunk 5 seeing it.
Chunk 5 therefore takes its own half only and records the hazard rather than resolving
it: see §12.4 A3, which states the never-unilateral rule. The plan records this as a
cross-chunk note, not a claim on Chunk 3's file.

### 5.1 Constants and vocabularies

```python
PRODUCT_DETAIL_OPERATION_NAME: str = "ProductDetail"
PRODUCT_PAGE_VIEWS_OPERATION_NAME: str = "ProductPageViews"
GRAPHQL_OPERATION_NAMES: tuple[str, str] = (
    PRODUCT_DETAIL_OPERATION_NAME, PRODUCT_PAGE_VIEWS_OPERATION_NAME,
)

#: Endpoint contract value. SRS-lean.md `LREQ-GQL-010` says only "Enrichment SHALL
#: use the parent SRS GraphQL batch endpoint" (line 289) and §1.5 (lines 125–126)
#: names `[PARENT]` as "the full-MVP SRS and source for unchanged endpoint details".
#: The operator authorized `Documents/retired-documents/SRS-revision2.md` as a
#: source for endpoint details **and only for endpoint details** (§12 Q1(a)); the
#: value below is the retired document's `REQ-GQL-010` verbatim. Precedent: the
#: frozen `Documents/plans/chunk-03-coveo-discovery-adapter-and-streamed-raw-
#: persistence.md` §12.5 (Status: FROZEN) cites the same retired document for the
#: Coveo endpoint.
GRAPHQL_BATCH_ENDPOINT: str = "https://assetstore.unity.com/api/graphql/batch"

#: Request headers this adapter emits. Sourced from the operator's five redacted
#: request captures (observed values) plus Assumption A-4 / OI-6 for the CSRF
#: header, under the §1.5 endpoint-details authorization. See §12 Q1(b) for the
#: header table and for the excluded client-negotiation / fingerprint / trace
#: headers. `GRAPHQL_CSRF_HEADER_NAME` is the canonical emission name.
GRAPHQL_CSRF_HEADER_NAME: str = "X-CSRF-Token"
GRAPHQL_REQUEST_HEADERS: Mapping[str, str] = MappingProxyType({
    "content-type": "application/json;charset=UTF-8",
    "accept": "application/json, text/plain, */*",
    "origin": "https://assetstore.unity.com",
    "referer": "https://assetstore.unity.com/",
    "x-requested-with": "XMLHttpRequest",
    "x-source": "storefront",
})

#: Retry policy constants. These are module constants, not config keys: lean
#: SRS §14 lists no GraphQL retry constant and `config.load_config` rejects
#: unknown keys. Values pinned by operator ruling (§12 Q4).
DEFAULT_MAX_ATTEMPTS: int = 4                 # 1 initial + 3 retries
DEFAULT_BACKOFF_BASE_SECONDS: float = 0.5
DEFAULT_BACKOFF_MULTIPLIER: float = 2.0
DEFAULT_BACKOFF_MAX_SECONDS: float = 8.0
DEFAULT_MIN_REQUEST_INTERVAL_SECONDS: float = 0.5

RETRYABLE_HTTP_STATUSES: frozenset[int] = frozenset({429, 500, 502, 503, 504})
PERMANENT_HTTP_STATUSES: frozenset[int] = frozenset({400, 401, 403, 404, 409, 422})
```

### 5.2 Failure classification vocabulary

`GraphQLFailureClass` is a **new** enum local to `collector_graphql.py`. It is not an
SRS vocabulary and does not replace `OperationStatus`; it is the adapter's
classification of *why* an operation is an error, and it is the thing a retry
decision is made on. Every member is derived from LREQ-GQL-040's enumeration plus
the `429`/`5xx` and permanent-auth/CSRF/malformed-request/authorization split.

```python
class GraphQLFailureClass(str, Enum):
    NONE = "none"                                    # no failure
    HTTP_TRANSIENT = "http_transient"                 # 429, 5xx  -> retryable
    HTTP_PERMANENT = "http_permanent"                 # 400/401/403/404/409/422 -> permanent
    AUTHENTICATION_FAILURE = "authentication_failure"  # 401/403, or CSRF mismatch body -> permanent
    CSRF_FAILURE = "csrf_failure"                     # csrf token mismatch -> permanent
    MALFORMED_REQUEST = "malformed_request"            # 400 -> permanent
    AUTHORIZATION_FAILURE = "authorization_failure"    # 403 -> permanent
    GRAPHQL_TOP_LEVEL_ERROR = "graphql_top_level_error"
    OPERATION_ERROR = "operation_error"               # HTTP 200 + operation-level `errors`
    NULL_REQUIRED_DATA = "null_required_data"
    WRONG_DATA_SHAPE = "wrong_data_shape"
    WRONG_SCALAR_TYPE = "wrong_scalar_type"
    INVALID_PAGE_VIEWS = "invalid_page_views"         # bool / negative / non-finite / non-integral
    INVALID_STATE_VALUE = "invalid_state_value"
    MISSING_IDENTITY = "missing_identity"
    OPERATION_CORRELATION_MISSING = "operation_correlation_missing"
    OPERATION_CORRELATION_DUPLICATED = "operation_correlation_duplicated"
    OPERATION_CORRELATION_UNKNOWN = "operation_correlation_unknown"
    OPERATION_CORRELATION_AMBIGUOUS = "operation_correlation_ambiguous"
    CORRELATION_MODE_UNVALIDATED = "correlation_mode_unvalidated"
    TRANSPORT_FAILURE = "transport_failure"            # connection reset, DNS, timeout raised by caller transport
    RESPONSE_NOT_JSON = "response_not_json"
```

`is_retryable(failure_class) -> bool` is `True` for exactly `HTTP_TRANSIENT` and
`TRANSPORT_FAILURE`, and `False` for every other non-`NONE` member. Stated as an
invariant: **no `*_FAILURE` auth/CSRF/authorization class and no
`MALFORMED_REQUEST` is ever retried**; a `429`/`5xx`/transport failure is retried at
most `max_attempts - 1` times and never indefinitely.

### 5.3 Typed request structures

```python
@dataclass(frozen=True, slots=True)
class GraphQLOperation:
    """One batch operation: a named operation and its single variable."""
    operation_name: str          # PRODUCT_DETAIL_OPERATION_NAME | PRODUCT_PAGE_VIEWS_OPERATION_NAME
    query: str
    variable_name: str           # "id" | "packageId"
    variable_value: str          # always the same canonical asset_identity_key
    def to_json_dict(self) -> dict[str, Any]: ...

@dataclass(frozen=True, slots=True)
class GraphQLBatchRequest:
    """The exactly-two-operation batch request for one canonical identity.

    `body_json` is a JSON array of exactly two operation objects and
    `operations_header` is the comma-joined operation-name list; the two are the
    only wire shapes this adapter produces. `header_names` is the *names* of the
    headers the caller supplied, never the values, so a request object is always
    safe to log or attach to a fixture.
    """
    asset_identity_key: str
    operations: tuple[GraphQLOperation, GraphQLOperation]
    endpoint: str
    endpoint_contract_version: str            # ENDPOINT_CONTRACT_VERSION, "1.0.0"
    operations_header: str                    # "ProductDetail,ProductPageViews"
    header_names: tuple[str, ...]
    body_json: str
```

```python
def build_product_detail_operation(asset_identity_key: str) -> GraphQLOperation
def build_product_page_views_operation(asset_identity_key: str) -> GraphQLOperation
def build_graphql_batch_request(
    asset_identity_key: str, *,
    credentials: Credentials,
    endpoint: str = GRAPHQL_BATCH_ENDPOINT,
) -> GraphQLBatchRequest
def build_graphql_headers(*, credentials: Credentials) -> Mapping[str, str]
```

Null/edge-case contract (LREQ-NFR-040 style):
- `build_graphql_batch_request` and `build_graphql_headers` raise `ValueError` when
  the Unity CSRF credential is empty/whitespace-only, **before** any request object
  exists, and the message names the environment variable
  (`UNITY_CSRF_TOKEN_ENV`) and never echoes any part of the value (LREQ-SEC-010).
  The check is the same predicate `Credentials.require_for_collection()` applies;
  the adapter **calls** `require_for_collection()` rather than re-implementing it,
  so the two cannot drift.
- `asset_identity_key` that is empty, whitespace-only, or not a `str` raises
  `ValueError`: an unidentifiable asset is never sent, and `"0"`, `""`, and `None`
  are never substituted (AGENTS.md "never fabricate zeros"; Chunk 1 interface §5).
- `build_graphql_headers` returns a `Mapping` whose `GRAPHQL_CSRF_HEADER_NAME`
  (`"X-CSRF-Token"`; canonical emission name frozen by §12 Q1) member is present
  exactly once, carrying the caller-supplied credential. The map is emitted with
  **lowercase** header names, as observed on the wire in all five operator captures;
  because HTTP header names are case-insensitive, any header *lookup* in the adapter
  must be case-insensitive (§11, §12 Q1).
  Returned mappings are `MappingProxyType` so a caller cannot mutate a header map
  shared with another request; the returned mapping carries the credential itself,
  so it is never placed in `header_names`, `request_metadata_json`, an error
  summary, or a warning.
- `GraphQLBatchRequest.operations` is always a 2-tuple in
  `GRAPHQL_OPERATION_NAMES` order, but **request order is not a correlation
  guarantee** and no code path may infer an operation from response position on the
  strength of it. `to_json_dict()` on `GraphQLOperation` emits exactly
  `{"query", "variables", "operationName"}`; extra keys are a defect.

### 5.4 Typed response and operation result structures

```python
@dataclass(frozen=True, slots=True)
class GraphQLBatchResponse:
    """A received HTTP response, already read to text by the caller transport.

    No attribute of this type is retyped or rewritten by the adapter; `body_text`
    is retained verbatim so the response hash is over the received bytes, and
    `body_text` itself is never placed in an error summary or request metadata.
    """
    http_status: int
    body_text: str
    header_names: tuple[str, ...] = ()

@dataclass(frozen=True, slots=True)
class PageViewValue:
    """The validated ProductPageViews scalar, or the reason it is not one.

    `value` is non-None iff `is_valid` is True. A rejected scalar keeps the raw
    JSON type name in `rejected_shape` for audit and never contributes a `0`:
    zero is representable only as a validated `value == 0`.
    """
    is_valid: bool
    value: int | None
    failure_class: GraphQLFailureClass        # NONE iff is_valid
    rejected_shape: str | None

@dataclass(frozen=True, slots=True)
class GraphQLOperationResult:
    """One operation's independent outcome (LREQ-GQL-040, LREQ-GQL-050).

    `status` is models.OperationStatus. Every field of a failed operation is None:
    a failed operation carries no partially-populated value, and `None` here is
    what makes the corresponding EnrichmentObservationRecord column NULL.
    """
    operation_name: str
    status: OperationStatus
    failure_class: GraphQLFailureClass
    correlation_key: str | None              # the key this item was associated by, if any
    correlation_mode: GraphQLOperationCorrelationMode
    payload: Mapping[str, Any] | None        # the operation's own `data` mapping/scalar, verbatim
    issues: tuple[ValidationIssue, ...]
    error_summary: str | None                # redacted, via summarize_validation_issues

    @property
    def is_success(self) -> bool: ...
    @property
    def requirement_warning_code(self) -> WarningCode | None: ...
```

`requirement_warning_code` maps `PRODUCT_DETAIL_OPERATION_NAME` →
`WarningCode.GRAPHQL_PRODUCT_ERROR` and
`PRODUCT_PAGE_VIEWS_OPERATION_NAME` → `WarningCode.GRAPHQL_PAGE_VIEWS_ERROR` when
`status is ERROR`, else `None` (SRS Appendix C vocabulary, frozen as
`models.WarningCode`). Naming the code is not emitting a warning: warnings on a
category row are Chunk 10's.

Null/edge-case contract:
- `GraphQLOperationResult.status is OperationStatus.SUCCESS` **iff**
  `failure_class is GraphQLFailureClass.NONE` and `payload is not None`. The two
  cannot disagree.
- `payload is None` for every error. `payload == {}` never means "success with no
  data": an empty mapping that is missing a member LREQ-GQL-020 requires is
  `WRONG_DATA_SHAPE`/`NULL_REQUIRED_DATA`, not success.
- `payload` for `ProductPageViews` is the scalar wrapped as
  `{"pageViews": <int>}` so a single `payload` field can carry both an object and a
  scalar without a union type; `PageViewValue` carries the validated form. Nothing in
  the adapter reads a package identifier out of the `ProductPageViews` payload —
  LREQ-GQL-030's scalar sentence makes request-scoped identity validation through the
  associated operation sufficient.
- `error_summary` is produced by `validation.summarize_validation_issues` over
  `issues`, and therefore contains only issue codes, member names, counts, and
  redacted context: no headers, cookies, tokens, response bodies, or full payloads.
- A response that is not a JSON array of exactly two objects never yields a
  per-operation result at all; it yields two `ERROR` results via the correlation
  path (`RESPONSE_NOT_JSON`, or both operations `OPERATION_CORRELATION_AMBIGUOUS`).

### 5.5 Correlation

**The correlation key is `operationName` (§12 Q3).** `extract_operation_correlation_key`
reads the `operationName` member of a response item — the explicit operation name
LREQ-GQL-030 names first, and the member the `operations` request header mirrors. The
operator's five redacted request/response captures make this load-bearing rather than a
matter of taste: across those batches the response **must** be matched by
`operationName` and never by index, because batch 1 contains `ServerTime` twice, batch 4
contains `ServerTime` seven times, and batch 5 contains `AddToCartButton` eight times.
Index-based association would be silently wrong. The captures also show that
`ProductPrice`, `ProductReview`, `Recommendations`, `AddToCartButton`, `CurrentUser`,
`ShoppingCartQuery`, and `Publisher` are never batched with duplicates of themselves
**except** `AddToCartButton` (batch 5, 8×), so the duplicate-handling test path must be
exercised on more than `ServerTime` (§9, golden leg).

```python
def extract_operation_correlation_key(item: object) -> str | None
def correlate_operations(
    response_items: Sequence[object], *,
    mode: GraphQLOperationCorrelationMode,
    operation_names: tuple[str, str] = GRAPHQL_OPERATION_NAMES,
) -> GraphQLCorrelationResult

@dataclass(frozen=True, slots=True)
class GraphQLCorrelationResult:
    mode: GraphQLOperationCorrelationMode
    is_fully_correlated: bool
    by_operation: Mapping[str, object | None]   # operation_name -> that operation's item or None
    matches: tuple[GraphQLOperationCorrelationMatch, ...]
    issues: tuple[ValidationIssue, ...]
    unassociated_item_indexes: tuple[int, ...]

@dataclass(frozen=True, slots=True)
class GraphQLOperationCorrelationMatch:
    operation_name: str
    item_index: int | None
    correlation_key: str | None
    failure_class: GraphQLFailureClass        # NONE iff item_index is not None and unambiguous
```

**Correlation-mode vocabulary (§12.1, O-3).** Two members are the *persisted* modes
LREQ-GQL-030 permits, and they are the frozen `models.GraphQLOperationCorrelationMode`
members: `EXPLICIT_KEY` and `VALIDATED_POSITION`. Two further members are
adapter-internal, non-persisted dispositions held locally here:

```python
class GraphQLCorrelationDisposition(str, Enum):
    EXCLUDED = "excluded"      # the item carries no usable key / is unknown-keyed -> not attached
    CANDIDATE = "candidate"    # the item is keyed and attached to exactly one operation, pending shape validation
```

This local vocabulary is not a workaround for a blocked enum extension; it is the
**required** design, because the SRS closes the persisted domain to two values.
`LREQ-GQL-030` (`Documents/SRS-lean.md` lines 310–312): "The persisted correlation
mode SHALL be either `explicit_key` or `validated_position`. If neither mode is
validated, both operations SHALL be marked malformed and their fields SHALL remain
unavailable." A disposition that can never be persisted cannot be a member of the
persisted enum, so `EXCLUDED`/`CANDIDATE` are non-persisted by construction. The
frozen enum stays two-membered with no extension authorized (§4.1, §12.1 O-3).

`EXCLUDED` and `CANDIDATE` are **not** values of the persisted
`GraphQLOperationCorrelationMode`. Nothing in `correlate_operations`'s return value,
`EnrichmentObservationDraft`,
or `request_metadata_json` may carry `EXCLUDED` or `CANDIDATE` as a correlation mode;
`request_metadata_json`'s `correlation_mode` key is `"explicit_key"` or
`"validated_position"` only (§5.10).

Contract, stated as boundaries between "Chunk 5 may" and "Chunk 5 must not":
- **Chunk 5 MAY**: read a correlation key off a response item when one is present
  (an explicit operation name or another explicit key the item carries), group items
  by that key, and report each operation's matched item **and its response index**.
  Reversed response order therefore passes: an item carrying
  `operation_name = ProductPageViews` at index `0` matches that operation, and the
  order of `response_items` is never used to decide anything when a key is present.
  This is the mechanism the gate bullet "Reversed GraphQL response order passes"
  checks.
- **Chunk 5 MUST NOT**: infer an operation from `response_items` index when
  `mode is GraphQLOperationCorrelationMode.EXPLICIT_KEY` and no key is present; and
  must not *validate* position under
  `GraphQLOperationCorrelationMode.VALIDATED_POSITION`. Position validation is the
  identity preflight's job (Chunk 6A, LREQ-ID-020: "the operation-correlation mode
  is valid"). Under `VALIDATED_POSITION`, Chunk 5 accepts the caller's mode as
  already-validated, uses the fixed two-operation ordering that the preflight
  validated, and still reports the per-item failure class and index so the preflight
  can audit the decision. Under `EXPLICIT_KEY`, a missing or unrecognized key is
  never repaired.
- Failure classification is exact and total:
  - zero items, or no key on any item while `mode is EXPLICIT_KEY` →
    `OPERATION_CORRELATION_MISSING`;
  - two items carrying the *same* key → `OPERATION_CORRELATION_DUPLICATED` for both
    operations;
  - an item whose key is not in `operation_names` →
    `OPERATION_CORRELATION_UNKNOWN` (and the item is reported in
    `unassociated_item_indexes`, never attached to another operation);
  - a keyed item that cannot be attached to exactly one operation, or a
    `VALIDATED_POSITION` mode supplied without a validated two-operation ordering →
    `OPERATION_CORRELATION_AMBIGUOUS`.
  Each of these sets the affected operations to `ERROR` with the corresponding
  `failure_class`; **none of them is a positional guess** (LREQ-GQL-030: "SHALL never
  guess from response position").
- An item that carries a shape error is still correlated when its key is present;
  shape validation is per operation (§5.6) and does not change `matches`.
- Correlation uses only `operation_name` and the run's policy version. `mode` is a
  parameter, never a module global, so two calls with different modes cannot
  interfere.

### 5.6 Per-operation response validation

```python
PRODUCT_DETAIL_REQUIRED_MEMBERS: tuple[str, ...]
PRODUCT_DETAIL_ALIAS_MEMBERS: tuple[str, ...]
PRODUCT_DETAIL_NUMERIC_MEMBER_TYPES: Mapping[str, type | tuple[type, ...]]
PRODUCT_PAGE_VIEWS_PAYLOAD_SHAPE: str

def validate_product_detail_payload(
    payload: object, *, mapping_rule_version: str = IDENTITY_MAPPING_RULE_VERSION
) -> GraphQLOperationValidation
def validate_page_views_payload(payload: object) -> GraphQLOperationValidation

@dataclass(frozen=True, slots=True)
class GraphQLOperationValidation:
    is_valid: bool
    failure_class: GraphQLFailureClass
    product_detail: ProductDetailFields | None
    page_views: PageViewValue | None
    issues: tuple[ValidationIssue, ...]

@dataclass(frozen=True, slots=True)
class ProductDetailFields:
    """A validated ProductDetail payload, field by field.

    Every scored field is Optional and stays None when the corresponding member is
    absent, null, or wrong-typed. No field is ever defaulted or coerced: a
    ProductDetail with a valid `rating.average` and no `reviewCount` yields
    `rating_average` set and `review_count = None`, never 0.
    """
    graphql_id: str | None
    product_id: str | None
    rating_average: float | None
    rating_count: int | None
    review_count: int | None
    first_published_date_utc: datetime | None
    first_published_date_issue: str | None    # why the date is unavailable, e.g. "naive", "unparsable"
    publisher_json: str | None
    category_json: str | None
    state: str | None
    state_annotation: StateEligibilityAnnotation | None
    identity_comparison: GraphQLIdentityComparisonResult | None
```

`ProductDetailFields.first_published_date_utc` is produced by **parsing only**: a
timezone-naive, date-only, or unparsable value yields `None` with
`first_published_date_issue` set. This mirrors the parent SRS constraint
(REQ-GEN-035) and SRS-lean §1.2's "All timestamps used in calculations SHALL be
timezone-aware UTC timestamps"; the *normalization* of a valid value is
`models.ensure_utc`. Age thresholds and future-date rejection remain Chunk 7A's
(Chunk 1 interface §6); Chunk 5 does not compare the date to a cutoff.

### 5.7 Page-view type/range rule (derived from LREQ-GQL-040)

LREQ-GQL-040 names as operation errors "wrong scalar type, boolean/negative/
non-finite page views". Derived acceptance predicate for the `ProductPageViews`
scalar, stated exhaustively (see §8 E5):

1. **Accepted**: a JSON integer (`int` in Python, `bool` excluded) that is `>= 0`.
   `0` is a valid value: zero page views is a value, not an error, and is distinct
   from a failed operation's `None` (SRS-lean §6.4 "`product_page_views` SHALL be
   nullable and SHALL never use zero as an error sentinel").
2. **Rejected** — each maps to a `GraphQLFailureClass`, and the value stays `None`:
   - `bool` (JSON `true`/`false`), including `0`-like falsy booleans →
     `WRONG_SCALAR_TYPE`. `bool` is rejected **before** any numeric test, because
     `isinstance(True, int)` is `True` in Python.
   - `int < 0` → `INVALID_PAGE_VIEWS`.
   - `float` that is not finite (`NaN`, `Infinity`, `-Infinity`) →
     `INVALID_PAGE_VIEWS`.
   - `float` that is finite but not integral (`1.5`) → `INVALID_PAGE_VIEWS`. A
     JSON `1.0` is a numeric value with zero fractional part and is **accepted as
     `1`**; that half of the rule is a derivation, not an SRS sentence. It is
     sourced to `LREQ-MET-040` (SRS-lean.md line 711): "It is usable only for a
     finite non-negative page-view value, a valid UTC date no later than cutoff,
     `age_days_exact >= MIN_AGE_DAYS_FOR_RATE`, and a matched, published
     identity. An explicit valid page-view value of zero is usable and yields an
     index of zero." That sentence establishes the eligible numeric domain, which
     `1.5` violates and `1.0` does not; the zero-is-usable clause shows the SRS
     treats the page-view value as a count-like quantity rather than a continuous
     rate, which is what licenses integer-semantics interpretation. Reinforced by
     the parent SRS's field-type domain for `productPageViews`, sourced as an
     endpoint detail under §1.5 per §12 Q1(a). The plan does **not** cite SRS-lean
     §2.2 row 117, which names only the formula `product_page_views * 7 /
     age_days_exact` and calls the field "undocumented" — it states no integrality
     convention. See §12 Q7.
   - `str`, `list`, `dict`, `null`, absent → the JSON-`null`/missing case is
     `NULL_REQUIRED_DATA`; every non-numeric, non-null JSON type is
     `WRONG_SCALAR_TYPE` (a wrong-shaped *container* is `WRONG_DATA_SHAPE`).
3. The rejection is per operation and never per response: a rejected
   `ProductPageViews` scalar leaves `ProductDetail` at `SUCCESS` with its fields
   intact (LREQ-GQL-050).

`validate_page_views_payload` is the single implementation of this table; a caller
must not re-derive acceptance from the raw scalar.

### 5.8 State and identity annotation (annotation only)

```python
def annotate_product_detail_identity(
    requested_identity: str, product_detail: ProductDetailFields, *,
    mapping_rule_version: str = IDENTITY_MAPPING_RULE_VERSION,
) -> ProductDetailFields
```
`annotate_product_detail_identity` returns `product_detail` with
`identity_comparison` set to the result of
`validation.compare_graphql_identity_aliases(requested_identity, aliases)` where
`aliases` is built from `graphql_id` and `product_id` when present. Semantics
copied from LREQ-GQL-070 and the Chunk 1 contract:

- `identity_comparison.id_mapping_mismatch is True` sets the pre-record's
  `id_mapping_mismatch` to `True` and pairs it with
  `WarningCode.GRAPHQL_ID_MAPPING_MISMATCH`; the affected result's scored fields are
  *mismatch-affected*, which the pre-record expresses as
  `EnrichmentObservationRecord.id_mapping_mismatch = True`. This is exactly LREQ-GQL-070's
  "marked `id_mapping_mismatch`" clause.
- A missing or wrong-typed identity member is **not** silently an agreement: the
  comparison's `issues` (`response_missing_identity`) are carried into the
  operation's `issues`, and a `ProductDetail` with no usable identity alias is an
  operation error via `MISSING_IDENTITY` (LREQ-GQL-040's "missing identity").
- The exclusion from D, R, and Q on mismatch is **not implemented here**. The
  dependency map's **Chunk 7A** row (line 786: "metric identity-mismatch eligibility
  completion for LREQ-GQL-070") is what completes it: Chunk 7A is the integration
  completion chunk for `LREQ-GQL-070`. Chunk 5 records the mark and the reason only,
  and no function in this module returns a D/R/Q verdict, a metric input, or an
  "eligible" boolean for scoring. The same applies to `LREQ-GQL-060`'s
  metric-eligibility portion (dependency map line 785, Chunk 7A).

State annotation is the Chunk 1 call `annotate_state_eligibility(state_value)`; the
adapter stores the returned `StateEligibilityAnnotation` unchanged, keeps the raw
`state` string in `ProductDetailFields.state` (verbatim, including a `None` for a
missing state), and adds `WarningCode.STATE_EXCLUDED` to the operation's issue
context when `state_excluded` is true. `state_unknown` and `state_excluded` are
recorded as such, and `remains_in_discovered_breadth` is always `True`, so this
chunk satisfies the dependency map's "state-excluded and state-unknown assets remain
in persisted observations and discovered breadth" (line 652) by construction. The
adapter does not remove the asset from anything; it has no population to remove it
from.

**Run-level `page_view_semantics_status`: a scoped omission, not a pending
resolution.** Chunk 5 does not compute, return, or persist
`models.PageViewSemanticsStatus` on any value, and no code path in
`collector_graphql.py` reads or writes that enum. There is **no** contradicted-
detection obligation here at all: detection would require cross-run state, and
Chunk 5 is a single-run adapter that receives one HTTP exchange. The concrete
contradiction-detection rule is **deliberately unspecified in Chunk 5 and is
Chunk 7B's plan-time decision to specify** — a scoped omission, not something
Chunk 5 is waiting on. Ownership, per the operator's binding split recorded in
§12 Q5:

- **Chunk 6A initializes** the run-level value (dependency map Chunk 6A row; retired
  `SRS-revision2.md` line 196: step 2 of the run data flow "initializes
  `page_view_semantics_status` from the latest operator validation (`unvalidated`
  unless validated or contradicted)"). This is a Chunk 6A detail, carried forward
  for Chunk 6A's plan; it changes nothing about Chunk 5.
- **Chunk 7B detects `contradicted`** (dependency map line 91:
  `| LREQ-MET-090 | Chunk 7B | Chunk 5, Chunk 7A | Chunk 7B | LREQ-TST-050 |`, whose
  edge-case column is the phrase "contradicted page-view semantics"; and line 86:
  `| LREQ-MET-040 | Chunk 7B | Chunk 5, Chunk 7A | Chunk 7B | LREQ-TST-050 |`).
- **Chunk 8 applies** contradicted page-view handling (dependency map line 101:
  `| LREQ-SCR-050 | Chunk 8 | Chunk 5, Chunk 7B | Chunk 8 | LREQ-TST-060 |`, plus the
  Chunk 8 "Implement:" list at line 858, which literally contains
  "- contradicted page-view handling").
- **Chunk 5 sets nothing.** The adapter does not add a member to the enum and does
  not set a value. This is consistent with the frozen enum
  `models.PageViewSemanticsStatus` = `UNVALIDATED` / `VALIDATED_CUMULATIVE` /
  `CONTRADICTED` (`src/niche_scout/models.py` lines 126–129; §4.1 above).

SRS-lean §6.5 (lines 639–642) is consistent with this split and is quoted here for
the boundary it states, not as an assignment: the run-level value "describes the
endpoint semantic-validation state", and an individual malformed or failed page-view
operation is an asset-level `page_views_status = "error"` and "SHALL not by itself
contradict the endpoint".

### 5.9 Per-identity enrichment result and pre-record value

```python
@dataclass(frozen=True, slots=True)
class EnrichmentResult:
    """The adapter's whole result for one canonical identity and one HTTP exchange.

    `is_success` is true when both operations succeeded; a partial success is
    `is_partial_success` and carries whichever operation's fields validated.
    """
    asset_identity_key: str
    correlation: GraphQLCorrelationResult
    product_detail: GraphQLOperationResult
    page_views: GraphQLOperationResult
    http_status: int | None
    attempts: int
    response_sha256: str | None
    retry_metadata_json: str              # redacted: attempt count, failure classes, statuses
    issues: tuple[ValidationIssue, ...]

    @property
    def is_success(self) -> bool: ...
    @property
    def is_partial_success(self) -> bool: ...
    @property
    def both_operations_malformed(self) -> bool: ...
    @property
    def requirement_warning_codes(self) -> tuple[WarningCode, ...]: ...

@dataclass(frozen=True, slots=True)
class EnrichmentObservationDraft:
    """A pre-record value: the exact field set EnrichmentObservationRecord requires,
    minus `run_id`, with `retrieved_at_utc` supplied by the caller.

    Chunk 5 does not persist. `to_record(run_id)` is the only conversion, and it
    performs a field-for-field copy: it never substitutes a default, and it can
    produce no value that EnrichmentObservationRecord would reject for a naive
    timestamp.
    """
    asset_identity_key: str
    product_detail_status: str
    page_views_status: str
    graphql_id: str | None
    product_id: str | None
    rating_average: float | None
    rating_count: int | None
    review_count: int | None
    first_published_date_utc: datetime | None
    publisher_json: str | None
    category_json: str | None
    state: str | None
    product_page_views: int | None
    id_mapping_mismatch: bool
    product_detail_error_summary: str | None
    page_views_error_summary: str | None
    request_metadata_json: str
    retrieved_at_utc: datetime
    def to_record(self, run_id: str) -> EnrichmentObservationRecord: ...

def build_request_metadata_json(
    *, operation_names: Sequence[str],
    correlation_keys: Mapping[str, str | None],
    correlation_mode: GraphQLOperationCorrelationMode,
    http_status: int | None,
    response_sha256: str | None,
    retry_metadata: Mapping[str, object],
    additional_correlation_keys: Mapping[str, Sequence[str]] | None = None,
) -> str
def build_enrichment_observation_draft(
    result: EnrichmentResult, *,
    fields: ProductDetailFields | None = None,
    retrieved_at_utc: datetime,
) -> EnrichmentObservationDraft
```

Mapping rule from `EnrichmentResult` to `EnrichmentObservationDraft` (this table is
the contract Chunks 6A/6B consume, and the reason the adapter needs no `database`
import):

| Target field | Source |
|---|---|
| `asset_identity_key` | `EnrichmentResult.asset_identity_key` (the requested canonical identity, never a returned alias) |
| `product_detail_status` | `product_detail.status.value` (`"success"`/`"error"`) |
| `page_views_status` | `page_views.status.value` |
| `graphql_id`, `product_id`, `rating_average`, `rating_count`, `review_count`, `first_published_date_utc`, `publisher_json`, `category_json`, `state` | the corresponding `ProductDetailFields` member, else `None` |
| `product_page_views` | `page_views.payload["pageViews"]` as the validated `int`, else `None`. **Never 0 for a failed operation.** |
| `id_mapping_mismatch` | `ProductDetailFields.identity_comparison.id_mapping_mismatch`, else `True` when the identity could not be compared (an uncomparable identity is not an agreement) |
| `product_detail_error_summary` | `product_detail.error_summary` (redacted), else `None` |
| `page_views_error_summary` | `page_views.error_summary` (redacted), else `None` |
| `request_metadata_json` | `build_request_metadata_json(...)`, per §5.10 |
| `retrieved_at_utc` | the caller-supplied argument, validated by `models.ensure_utc`; the adapter never reads the clock |

Null/edge-case contract:
- **No zero-value fabrication anywhere.** A partial or failed result yields `None`
  for every failed-operation field. `product_page_views is None` and
  `product_page_views == 0` are different states and the plan's tests assert both.
- `build_enrichment_observation_draft` accepts `retrieved_at_utc` as a required
  keyword-only argument. A naive datetime is rejected by the returned record's
  `_UtcRecord` validation; the builder normalizes through `ensure_utc` and never
  invents a value.
- `is_success` is `True` only when both `GraphQLOperationResult.status` values are
  `SUCCESS`. A `EnrichmentResult` with one `SUCCESS` and one `ERROR` is
  `is_partial_success` and the draft has exactly one non-`None` operation status
  field set to `"success"` and the other `"error"`.

### 5.10 `request_metadata_json` (SRS-lean §6.5)

```python
REQUEST_METADATA_REQUIRED_KEYS: tuple[str, ...] = (
    "operation_names", "correlation_keys", "correlation_mode", "http_status",
    "response_sha256", "retry", "additional_correlation_keys",
)
```
SRS-lean §6.5 (lines 645–647): "`request_metadata_json` SHALL contain concise
operation names, correlation keys, the correlation mode, HTTP status, response hash
when available, and retry/error metadata, but no credentials or full response
bodies." Therefore:

| Key | Content | Absent/null rule |
|---|---|---|
| `operation_names` | the two operation names, in request order | never absent |
| `correlation_keys` | `{operation_name: correlation_key or null}` | `null` per operation when no key was present |
| `additional_correlation_keys` | `{operation_name: [extra key name, ...]}` — any additional explicit key members the response item carried beyond `operationName`, empty list when none (§12 Q3) | never absent; each value is a list (possibly empty), never `null` |
| `correlation_mode` | the `GraphQLOperationCorrelationMode` value in force | never absent; `"explicit_key"` or `"validated_position"` only — never `"excluded"` or `"candidate"` |
| `http_status` | the numeric status, or `null` when no response was received | `null`, never `0` |
| `response_sha256` | lowercase hex SHA-256 of the response body bytes actually received | `null` when the response has no body; never a hash of a synthesized body |
| `retry` | `{"attempts": int, "failure_classes": [str, ...], "http_statuses": [int, ...]}` | `attempts` is always present and is `>= 1`; a class list is never invented for a single-attempt success |

Redaction guarantee (LREQ-SEC-020), stated as a testable invariant:
`build_request_metadata_json` accepts **no credential, header-value, cookie, or body
parameter at all**, so no such value can reach the JSON without a signature change.
Its inputs are operation names, correlation keys (which are operation names), the
mode, an integer status, a hex hash, and a caller-supplied retry mapping whose
nested values are counts, `GraphQLFailureClass` values, and integer statuses. The
`retry` mapping is re-serialized key-by-key against an allowlist rather than passed
through wholesale, so an unredacted string in a caller's mapping cannot leak.

### 5.11 Transport, retry, and failure isolation

```python
GraphQLTransport = Callable[[GraphQLBatchRequest, Mapping[str, str]], GraphQLBatchResponse]

@dataclass(frozen=True, slots=True)
class GraphQLRetryPolicy:
    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    backoff_base_seconds: float = DEFAULT_BACKOFF_BASE_SECONDS
    backoff_multiplier: float = DEFAULT_BACKOFF_MULTIPLIER
    backoff_max_seconds: float = DEFAULT_BACKOFF_MAX_SECONDS
    min_request_interval_seconds: float = DEFAULT_MIN_REQUEST_INTERVAL_SECONDS

def retry_delay_seconds(policy: GraphQLRetryPolicy, attempt: int) -> float
def execute_graphql_batch(
    request: GraphQLBatchRequest, *,
    transport: GraphQLTransport,
    headers: Mapping[str, str],
    policy: GraphQLRetryPolicy = GraphQLRetryPolicy(),
    sleep: Callable[[float], None] = ...,   # injected; default is time.sleep
) -> EnrichmentResult
def enrich_asset(
    asset_identity_key: str, *,
    credentials: Credentials,
    transport: GraphQLTransport,
    correlation_mode: GraphQLOperationCorrelationMode,
    retrieved_at_utc: datetime,
    policy: GraphQLRetryPolicy = GraphQLRetryPolicy(),
    endpoint: str = GRAPHQL_BATCH_ENDPOINT,
    sleep: Callable[[float], None] = ...,
) -> tuple[EnrichmentResult, EnrichmentObservationDraft]
```

Contract:
- `retry_delay_seconds(policy, attempt)` is **pure and total**: it is
  `min(backoff_base_seconds * backoff_multiplier ** (attempt - 1), backoff_max_seconds)`
  for `attempt >= 1`, non-decreasing in `attempt`, and `0.0` for `attempt <= 0`.
  It reads no clock and produces no jitter (determinism, LREQ-ARCH-030 spirit;
  `metrics.py`/`scoring.py` purity is untouched because this module is not pure).
- `execute_graphql_batch` attempts at most `policy.max_attempts` times. It retries
  **only** when the classified failure is retryable (`is_retryable`), sleeps the
  return of `retry_delay_seconds` between attempts through the **injected** `sleep`,
  and returns the last attempt's `EnrichmentResult` with `attempts` set to the number
  actually made. It never retries a
  `AUTHENTICATION_FAILURE`/`CSRF_FAILURE`/`AUTHORIZATION_FAILURE`/
  `MALFORMED_REQUEST`/`HTTP_PERMANENT`, and it never loops without a bound.
- A transport that raises is caught and classified as `TRANSPORT_FAILURE` (retryable)
  with `http_status = None`; it never escapes `execute_graphql_batch` as an
  exception (LREQ-NFR-030 adapter portion). A single identity's exhaustion returns a
  failed result, so N identities are N independent calls and one failure cannot abort
  another.
- `min_request_interval_seconds` is only meaningful for a caller looping over
  identities. It is *not* implemented as hidden module state: the interval is
  enforced by the caller passing the same `sleep`, and `execute_graphql_batch`
  never sleeps between separate `enrich_asset` calls. See §12 Q4.
- `enrich_asset` is the only convenience that pairs the two: it builds the request
  (so the credential gate and the request-shape gate both run), executes it, and
  returns the result and its pre-record. It does **not** accept a run id, does not
  write anything, and does not decide whether the call is allowed.
- **The adapter has no preflight knowledge and no gate.** No function in
  `collector_graphql.py` reads a preflight status, and no function issues more than
  the two named operations. The gate bullet "The adapter does not perform bulk
  enrichment or bypass the preflight gate" is satisfied by there being no
  bulk-enrichment entry point at all: `enrich_asset` takes exactly one identity.

## 6. Files touched

| File | New/modified | Purpose |
|---|---|---|
| `src/niche_scout/collector_graphql.py` | modified | The entire GraphQL adapter: constants, `GraphQLFailureClass`, request/operation/response/result/correlation/validation/draft types, request builders, correlation, per-operation validation, page-view validation, identity/state annotation, retry policy, `execute_graphql_batch`, `enrich_asset`, `__all__`. |
| `src/niche_scout/collector.py` | modified | Facade only, **line 4 only**: `from .collector_graphql import *` becomes explicit-name re-exports drawn from `collector_graphql.__all__`. Line 3 (`from .collector_coveo import *`) is byte-identical and untouched. No behavior. |
| `tests/test_collector.py` | modified | **Append-only.** Chunk 3's frozen Coveo test module (2532 lines, 51 markers over 51 distinct nodes — see §12.2 item 9; corrected 2026-09-18: this cell previously read "1310 lines, 25 markers over 13 distinct nodes", which described the pre-Chunk-5 file) already exists and is listed as New at Chunk 3's plan line 410. Chunk 5 appends new GraphQL protocol nodes only: request shape, correlation (including reversed order, missing/duplicated/unknown/ambiguous), per-operation status and every LREQ-GQL-040 failure class, page-view type/range, partial success, retry/backoff and no-indefinite-retry, `request_metadata_json` contents, redaction, no-bulk/no-gate invariants. No Chunk 3 node, marker, fixture import, or `tests/traceability.json` entry is touched. |
| `tests/test_identity.py` | modified | Extend with adapter-level identity tests only (mismatch detected from a correlated `ProductDetail` payload, missing identity alias, and that the adapter's mismatch marking is not a D/R/Q verdict). Chunk 1's 26 existing marked nodes and their 26 markers are untouched (corrected 2026-09-18: this cell previously read "25 existing marked nodes ... their 25 markers" — see §12.2 item 9). |
| `tests/fixtures/graphql_fixtures.py` | new | Hand-derived, credential-free, clock-free fixtures: request/response golden vectors, reversed-order and partial-success responses, per-failure-class responses, identity-mismatch responses, non-integral/non-finite/bool page-view responses, a recording fake transport, and a recording fake sleeper. |
| `tests/fixtures/__init__.py` | modified | Add `graphql_fixtures` to the existing re-export list (`from fixtures import config_fixtures, graphql_fixtures, validation_fixtures`). |
| `tests/traceability.json` | modified | Add one entry per new base node ID; no existing entry is edited. |

No `tests/fixtures/captures/` path is touched and no capture file is created: the
capture-derived golden leg is deferred as a scoping decision (§12.3 O-2), so this
table lists exactly the files Chunk 5 actually writes.

Deliberately **not** touched: `src/niche_scout/models.py`,
`src/niche_scout/validation.py`, `src/niche_scout/collector_coveo.py`,
`src/niche_scout/database.py`, `tests/test_validation.py`,
`tests/test_contracts.py`, `tests/test_database.py`, `pyproject.toml`, and every
`Documents/` file. In particular `pyproject.toml` is not touched because §4.3's
transport-injection decision adds no dependency, and `tests/test_contracts.py` is
not touched: the node at
`tests/test_contracts.py::test_repository_protocol_and_schema_specification` carries
its `@pytest.mark.lreq("LREQ-ARCH-010")` marker at line 881 and **passes** (it is not
a failing assertion and there is no Chunk 0 document-consistency debt at that
location), but it is still outside Chunk 5's file scope and is **not** Chunk 5's to
fix.

## 7. Task breakdown

Every box below is unchecked **intentionally as implementer work**: this is the
implementable task list for Chunk 5, and an item is done when its code, fixtures,
markers, and `tests/traceability.json` entries all exist. No box is checked here,
none is stale formatting, and no box records work outside this chunk's scope.

- [ ] Define the module boundary and `__all__` in `collector_graphql.py`; add the
      constants of §5.1 as single-sourced constants rather than literals scattered in
      code, including the pinned `GRAPHQL_BATCH_ENDPOINT`,
      `GRAPHQL_REQUEST_HEADERS`, and the `DEFAULT_*` retry constants. (LREQ-GQL-010, LREQ-NFR-040)
- [ ] Implement `GraphQLFailureClass` and `is_retryable` with the retryability table
      of §5.2 stated once. (LREQ-GQL-040, retry policy)
- [ ] Implement `build_product_detail_operation` with the LREQ-GQL-020 lean selection
      set: identity aliases, `rating { average count }`, `reviewCount`,
      `firstPublishedDate`, `state`, `category`, `publisher`; and
      `build_product_page_views_operation` with the scalar selection. Add a shape
      test that the emitted query names exactly those fields and no
      favorite-count/`packageInListHotness` field. (LREQ-GQL-020)
- [ ] Implement `build_graphql_headers` (calling `Credentials.require_for_collection()`
      first) and `build_graphql_batch_request` with its exactly-two-operation JSON
      array body, `operations` header value, redacted `header_names`, and the
      `ValueError`-before-request contract. (LREQ-GQL-010, LREQ-SEC-010)
- [ ] Implement `extract_operation_correlation_key` and `correlate_operations` with
      the four correlation failure classes, the reversed-order pass, the
      `EXPLICIT_KEY` no-positional-fallback rule, and the
      `VALIDATED_POSITION`-is-accepted-not-validated rule. (LREQ-GQL-030)
- [ ] Implement `validate_response_shape`-backed `validate_product_detail_payload`:
      required members, numeric member types, per-field `None` on absence/null/wrong
      type, identity aliases retained, and the failure-class mapping of every
      LREQ-GQL-040 clause except the page-view scalar. (LREQ-GQL-040, LREQ-GQL-050)
- [ ] Implement `validate_page_views_payload` and `PageViewValue` exactly per
      §5.7's acceptance predicate, including the `bool`-before-`int` ordering and
      the `0`-is-valid / `None`-is-failure distinction. (LREQ-GQL-040, LREQ-GQL-050)
- [ ] Implement `annotate_product_detail_identity` and the state annotation wiring,
      including the `GRAPHQL_ID_MAPPING_MISMATCH` / `STATE_EXCLUDED` code pairing and
      the absence of any D/R/Q, eligibility, or metric verdict in the module.
      (LREQ-GQL-060, LREQ-GQL-070)
- [ ] Implement `build_request_metadata_json` with its allowlist re-serialization and
      `build_enrichment_observation_draft` / `to_record` with the field-by-field
      mapping table, the no-zero-fabrication rule, and the caller-supplied
      `retrieved_at_utc`. (LREQ-SEC-020, `EnrichmentObservationRecord` contract)
- [ ] Implement `GraphQLRetryPolicy`, `retry_delay_seconds`, `execute_graphql_batch`,
      and `enrich_asset`, with the injected `transport` and `sleep`, bounded attempts,
      retryable-only retry, transport-exception containment, and no module-level
      mutable state. (LREQ-GQL-040, LREQ-NFR-030)
- [ ] Update `collector.py` **line 4 only**: replace
      `from .collector_graphql import *` with explicit-name re-exports drawn from
      `collector_graphql.__all__`. **Line 3 (`from .collector_coveo import *`) stays
      byte-identical** — no symmetric Coveo edit is claimed or performed here; "for
      both adapters" is the coordination task (§12.4 A3), not this box. Add a
      boundary test asserting `collector.py` remains a facade with no logic and that
      `collector_graphql` imports none of `sqlite3`, `metrics`, `scoring`, `database`,
      `collector_coveo`, `pipeline`, `report`, or `cli`. (LREQ-GQL-010, LREQ-ARCH-010 boundary)
- [ ] Author `tests/fixtures/graphql_fixtures.py` with the fixtures of §9, including
      the recording fake transport and fake sleeper; add it to
      `tests/fixtures/__init__.py`. (LREQ-TST-040 test mechanism)
- [ ] **Extend** `tests/test_collector.py` with the §9 GraphQL node list, each
      carrying its `@pytest.mark.lreq` marker, **append-only**: Chunk 3's frozen
      Coveo nodes, markers, imports, and `tests/traceability.json` entries are
      untouched and byte-identical (§9). (LREQ-TST-040 test mechanism)
- [ ] Extend `tests/test_identity.py` with the §9 adapter-level identity nodes,
      leaving its 26 existing marked nodes and all 26 existing markers untouched
      (corrected 2026-09-18: this previously read "25 existing marked nodes ...
      all 25 existing markers" — see §12.2 item 9).
      (LREQ-GQL-070, LREQ-TST-030)
- [ ] Add the §9 `tests/traceability.json` entries and manually cross-check every new
      marker against the matrix in both directions (the validator's required-set is
      still Chunk 0-scoped; see §9). **(LREQ-TST-040, LREQ-NFR-060 mechanism — the
      matrix entries this box creates carry Chunk 5's own `LREQ-GQL-*` markers;
      `LREQ-TST-040` is named here only as the traceability mechanism, matching
      Chunk 3's §7 box wording for the same file, and no Chunk 5 node claims it —
      see §9's `LREQ-TST-040` note.)**
- [ ] Run `python -m pytest tests -q`, `python -m pytest tests -q --collect-only`,
      `python -m niche_scout.tools.check_import_boundaries`, and
      `python -m niche_scout.tools.validate_traceability`; record the known Chunk 0
      `test_contracts.py::test_repository_protocol_and_schema_specification` failure
      as pre-existing and not caused by this chunk.
- [ ] Freeze §5 into `Documents/interfaces/chunk-05.md` (publish pass; keep the
      `Status:` line semantics of `interfaces/chunk-00.md` and `chunk-01.md`).
      (gate-verifier's step, not the implementer's)

## 8. Edge cases and invariants

Pulled from the dependency map's "Edge cases" column for every LREQ this chunk owns
(lines 168–174), plus the chunk's own gate and description invariants, but split by
ownership: the annotated row is *not* silently promoted to a Chunk 5 decision.

- **E1 — Two operations, one identity (LREQ-GQL-010).** Exactly two operations per
  request; both variables are the same canonical `asset_identity_key`; the adapter is
  independently testable with a typed identity fixture and no network.
- **E2 — Request shape (LREQ-GQL-020).** Required aliases, ratings, dates, state,
  category, publisher, and the page-view scalar are requested; no unused GraphQL
  field, and specifically no favorite-count / `packageInListHotness` operation or
  field is requested (SRS-lean §15 defers favorite count; the retired parent SRS
  forbids the extra operations). Request order is fixed for reviewability but confers
  no correlation authority.
- **E3 — Reversed response order (LREQ-GQL-030).** A response whose items arrive in
  the reverse of request order correlates correctly through the explicit key. This is
  a gate bullet and is asserted with both orderings of the same two items.
- **E4 — Missing, duplicated, unknown, or ambiguous association (LREQ-GQL-030).**
  Each becomes a malformed-operation result with its own `GraphQLFailureClass` and
  **never** a positional guess. Additional invariants: `is_fully_correlated` is false
  when any item is unassociated; unknown-key items appear only in
  `unassociated_item_indexes`; and the same response correlated twice yields
  structurally equal results (determinism).
- **E5 — Page-view boundary set (LREQ-GQL-040).** Value `0` is accepted and distinct
  from a failed operation's `None`; `True`/`False` rejected as `WRONG_SCALAR_TYPE`
  even though Python's `bool` is an `int`; `-1` rejected; `NaN`/`Infinity`/`-Infinity`
  rejected; `1.5` rejected; `1.0` accepted as `1`; `"12"`, `[]`, `{}`, and a nested
  object rejected; `null` and an absent scalar are `NULL_REQUIRED_DATA`. A rejection
  never changes the other operation's status or fields.
- **E6 — HTTP failures and GraphQL errors (LREQ-GQL-040).** A non-200 HTTP response
  is an operation error for both operations with the class implied by the status
  (`HTTP_TRANSIENT` for 429/5xx, `HTTP_PERMANENT`/`MALFORMED_REQUEST` for 400,
  `AUTHENTICATION_FAILURE`/`AUTHORIZATION_FAILURE` for 401/403); a top-level
  `errors` member is not erased by a sibling operation's success; an HTTP 200 with an
  operation-level `errors` member is an operation error for that operation only; a
  non-JSON body is `RESPONSE_NOT_JSON`; `data = null` for one operation is that
  operation's `NULL_REQUIRED_DATA` and leaves the other operation intact.
- **E7 — Wrong data shape and invalid state (LREQ-GQL-040).** `product` present but
  not an object, a required member missing, and `state` present but not a string are
  each an operation error for `ProductDetail`; a present non-`"published"` state is
  **not** an operation error — it is `state_excluded`, annotated, and retains the
  asset in discovered breadth (LREQ-GQL-060 annotation half). **Ruled 2026-09-18:
  this bullet contradicts E10 and §5.8 and the ruling follows them, not E7.**
  **Correction applied, Chunk 5 wave (recorded 2026-09-19).** E7 now reads: a
  `product` present but not an object, a genuinely required member missing, and a
  **present-but-unusable** (non-string) `state` are each an operation error for
  `ProductDetail`; a present non-`"published"` state is **not** an operation error
  — it is `state_excluded`, annotated, and retains the asset in discovered
  breadth (LREQ-GQL-060 annotation half); and a **missing or null** `state` is
  **not** an operation error either — it is `state_unknown`, annotated, and
  retained, because `state` is no longer a member of
  `PRODUCT_DETAIL_REQUIRED_MEMBERS` (§12.6 item 2; the constant and this bullet
  changed as one unit, as that item requires). The pre-ruling wording above is
  retained only as the record of what the ruling superseded; E7 and E10 now
  agree.
- **E8 — Partial success retention (LREQ-GQL-050).** A valid `ProductDetail` is
  retained when page views fail and vice versa. Invariants: failed fields are `None`;
  no `0`, `0.0`, `""`, or `False` appears in the pre-record for a failed operation;
  `is_partial_success` is true exactly when one operation is `SUCCESS` and the other
  `ERROR`; both-failed is not partial success.
- **E9 — Identity mismatch (LREQ-GQL-070).** Returned aliases that disagree with the
  requested identity set `id_mapping_mismatch = True` and
  `WarningCode.GRAPHQL_ID_MAPPING_MISMATCH`; a missing or unparseable returned
  identity is a mismatch-or-error, never an implicit match. **The affected result must
  be invalidated at the adapter level** (its `identity_comparison.matches_requested_identity`
  is false and the flag is set); exclusion from D, R, and Q is Chunk 7A's, exactly as
  the gate's last bullet states.
- **E10 — State eligibility annotation (LREQ-GQL-060).** Only `published` is annotated
  published; a present non-`published` value is `state_excluded`; a missing, null, or
  wrong-typed value is `state_unknown`. In both non-published cases the asset remains
  in persisted observations and discovered breadth
  (`remains_in_discovered_breadth is True`), and no D/R/Q verdict is produced.
- **E11 — No bulk enrichment and no gate bypass (gate bullet).** No function accepts
  more than one identity, no function reads or writes a preflight status, and
  `enrich_asset` performs exactly one HTTP exchange's worth of work per call, subject
  only to the retry bound within that one call.
- **E12 — Retry and no-indefinite-retry.** `attempts <= policy.max_attempts`; retries
  occur only for the retryable classes; delay is non-decreasing in `attempt` and
  capped at `backoff_max_seconds`; the number of `sleep` calls is exactly
  `attempts - 1` on a retry-exhausted transient path and `0` on a permanent-failure
  path. Auth/CSRF/authorization/malformed-request failures are retried zero times.
- **E13 — Determinism and no clock.** Two calls with the same request, response,
  policy, and inputs produce structurally equal results; `retry_delay_seconds` and
  every validation function are pure; the only clock read in the module is the
  default `sleep` bound argument, and it can be replaced. `retrieved_at_utc` is
  always caller-supplied.
- **E14 — Redaction (LREQ-SEC-010/020).** No failure class, error summary, issue
  context, `header_names`, or `request_metadata_json` value contains a credential
  value, an `Authorization` header, a CSRF token, a cookie value, or a full response
  body; error summaries for a failed operation are `summarize_validation_issues`
  output; an exception message from request construction names the environment
  variable and never the value. **The five forbidden categories, enumerated so no
  reader has to derive them: (1) a credential value, (2) an `Authorization` header,
  (3) a CSRF token, (4) a cookie value, (5) a full response body.** An operation
  name (§5.10 `:1080`) and a correlation key (§5.10 `:1081`) are **none of the
  five**, so redacting them is a ruled deviation, not a stricter reading of this
  bullet — see §12.6 item 3.
- **E15 — Failure isolation (LREQ-NFR-030).** A raised transport, a non-JSON body,
  and a both-operations-malformed response each return a typed failed
  `EnrichmentResult` rather than an exception, so a caller looping over identities
  cannot have one identity's failure abort another's.

## 9. Test plan

- **Test files.** `tests/test_collector.py` (**modified, append-only**; the
  dependency map's `Tests:` list names `test_collector.py` and the SRS Appendix B row
  for `LREQ-GQL-*` names `test_collector.py`, `test_identity.py`), and
  `tests/test_identity.py` (modified). The two files are described below with
  their own verified counts and their own byte-identity protection.
  `tests/test_identity.py` currently holds **26 marked test nodes carrying 26
  `@pytest.mark.lreq` marker occurrences over 8 distinct LREQ IDs, 0 unmarked**
  (corrected 2026-09-18: this previously read "25 marked test nodes carrying 25
  ... marker occurrences", the pre-Chunk-5 figure — see §12.2 item 9):
  24 `LREQ-*` analytical nodes (18 single-node IDs, the other 6 nodes belonging to
  IDs that appear more than once) plus 1
  `LREQ-TST-030` suite node
  (`test_identity_suite_covers_valid_malformed_unresolved_conflict_uri_and_mismatch`).
  Markers and nodes are one-to-one here: no node in the file carries a second marker
  (distribution `{1: 26}`), `test_requested_identity_compatibility_comparison`
  (def at line 751) carries exactly one, `LREQ-ID-020` at line 750, and lines 748–749
  are blank. The naive substring count of 27 includes the module docstring's own prose
  mention of `@pytest.mark.lreq` at line 3, which is not a decorator. Node count (26),
  marker count (26), and distinct-LREQ-ID count (8) are three different units and must
  not be interchanged.
  (corrected 2026-09-18: this paragraph previously read `{1: 25}`, "naive substring
  count of 26", and "Node count (25), marker count (25)"; the line-number facts it
  states are unchanged and were re-read — see §12.2 item 9)
  None of the 8 is a Chunk 3 node — Chunk 3's Coveo nodes are in
  `tests/test_collector.py`. They cover Chunk 1's `validation` primitives. Chunk 5
  **extends** it with correlation/identity-flow tests only, adds no marker to an
  existing node, and does not re-assert any Chunk 1 primitive behavior. All 26
  existing `LREQ-*`-and-suite node IDs, and all 26 existing
  markers stay byte-identical, so their
  existing `tests/traceability.json` entries stay untouched.
- **`tests/test_collector.py` protection (append-only).** The file already exists at
  2532 lines (corrected 2026-09-18: this previously read "1310 lines", the
  pre-Chunk-5 count; see §12.2 item 9) as Chunk 3's frozen Coveo test module: its module docstring opens
  "Chunk 3 analytical tests for the Coveo discovery adapter", it carries 51
  `@pytest.mark.lreq` markers over 51 distinct nodes (corrected 2026-09-18:
  this previously read "25 ... markers over 13 distinct nodes", a pre-Chunk-5
  figure — see §12.2 item 9), all of them Chunk 3's
  `LREQ-EXT-*` / `NFR-*` / `SEC-*` and none an `LREQ-GQL-*`, and it already has
  entries in `tests/traceability.json`. Chunk 3's plan
  (`Documents/plans/chunk-03-coveo-discovery-adapter-and-streamed-raw-persistence.md`,
  the real filename; corrected 2026-09-18: this citation previously read
  `…-and-streamed-raw-persistence.md`, dropping "streamed-raw" and misspelling the
  filename, which resolves to no file on this tree),
  `Status: FROZEN` at its line 3) lists the file as **New** at its line 410 and as
  the sole test module at its line 598, and teaches that a module's two
  non-analytical tests carry no marker and no matrix entry (its lines 650–652);
  `tests/test_collector.py` today has 51 markers over 51 nodes (corrected
  2026-09-18: this previously read "25 markers over 13 nodes" — see §12.2
  item 9) for exactly that
  reason. Chunk 5 therefore **appends** new GraphQL nodes only:
  - Chunk 3's 51 markers, its 51 distinct node IDs (corrected 2026-09-18: this
    previously read "25 markers, its 13 distinct node IDs" — see §12.2 item 9),
    its fixtures, its module-level
    imports, and its existing `tests/traceability.json` entries are **untouched —
    byte-identical**, the same protection this plan extends to `tests/test_identity.py`.
    Chunk 5 SHALL NOT delete, rename, reorder, or re-mark a Chunk 3 node.
  - The module-level import collision set Chunk 5's new nodes must not disturb,
    redefine, or shadow — these are the names `tests/test_collector.py` already binds
    at module level today: `fixtures.coveo_discovery` (bound as `fx`) and the
    fixture constants it re-exports (`fx.COVEO_FIXTURE_CATEGORY`,
    `fx.COVEO_FIXTURE_CATEGORY_OTHER`, and the `fx.*` helpers the module imports —
    `template_body` is one; this list is the file's, not a reconstruction);
    `niche_scout.collector_coveo` (module-level import at line 28);
    `RepositoryError`, `SqliteRepository`, and `UniqueConstraintViolation` (from
    `niche_scout.database`, lines 30–34); `get_credentials`
    (`niche_scout.config`, line 29); and the `niche_scout.models` names at lines
    35–45 plus the `niche_scout.validation` names at lines 46–50. A new Chunk 5 node
    that imported a *different* `fixtures.validation_fixtures` alias, rebound
    `fx`, shadowed `collector_coveo`, or rebound any of those names would silently
    change Chunk 3's tests. Chunk 5's additions therefore use their own imports and
    their own `graphql_fixtures` alias, and no Chunk 5 node imports the module-level
    fixture constants at lines 52–70.
- **Fixtures.** New module `tests/fixtures/graphql_fixtures.py`, re-exported from
  `tests/fixtures/__init__.py`, local and clock-free. The contract leg below is the
  whole frozen fixture set.
  - **Contract leg — hand-derived, credential-free, clock-free, implementable now.**
    `CANONICAL_ASSET_ID` reused
    from `fixtures.validation_fixtures` rather than redefined, so the request/response
    fixtures and the identity fixtures agree on one identity string; hand-derived
    request goldens (the expected two-operation `body_json` — a JSON array of exactly
    two `{query, variables, operationName}` objects — the expected `operations` header
    value, and the exact `ProductDetail` selection-set member list); the identity-
    mismatch and non-integral/non-finite/bool page-view responses; the per-failure-
    class responses; and the fake transport/sleeper.
    The contract leg covers every behavior the §10 gate bullets actually test:
    reversed order, duplicate key, unknown key, missing key, ambiguous key, partial
    success, every `LREQ-GQL-040` failure class, page-view type and range, and
    `bool`-before-`int`. The dependency map's reversed-order gate bullet
    ("Reversed GraphQL response order passes", line 676) is satisfied **entirely** by
    the contract leg through §5.5's keyed-grouping mechanism: an item carrying
    `operation_name = ProductPageViews` at index `0` matches that operation, and the
    order of `response_items` decides nothing when a key is present. **The gate does
    not depend on captures.**
  - **Golden (capture-derived) leg — deferred out of frozen scope.** It is a scoping
    decision, not a pending Chunk 5 deliverable: see §12.3 O-2 for what is deferred and
    the clean path by which it reopens. No capture file is read by any node below and
    none is created.
  - Hand-derived response goldens: in-order success,
    reversed-order success (the same two items, order swapped), duplicate-key,
    unknown-key, missing-key, ambiguous-key, single-item, three-item, non-array, and
    non-JSON bodies; per-failure-class responses 429, 500, 503, 400 (malformed-request),
    401, 403 CSRF-mismatch-body, a 500-then-200 retry sequence, 200 with top-level
    `errors`, 200 with operation-level `errors` only, `product = null`, `data = null`,
    `product` as a list, `state` as a number, missing identity aliases, page-view
    scalars `0`, `-1`, `True`, `False`, `1.5`, `1.0`, `"12"`, `[]`, `{}`, `null`, `NaN`,
    `Infinity`, and an absent member;
  - an identity-mismatch golden whose returned `id`/`productId` disagree with the
    requested identity, and a matching golden that agrees — hand-derived from
    mapping rule `1.0.0` semantics as frozen in `interfaces/chunk-01.md` §4.1;
  - `RecordingTransport`, a fake `GraphQLTransport` returning queued
    `GraphQLBatchResponse` values in order and recording each request, plus
    `RecordingSleeper`, a fake `sleep` recording durations. No `unittest.mock`
    patch of a real HTTP client, because no HTTP client exists (§4.3).
  - No fixture contains a credential value, a live response, or a clock-derived
    value; `tests/fixtures/README.md` already forbids all three. No capture file is
    committed and no capture content is inlined anywhere in this plan (§12.3 O-2).
- **Node list and markers.** Every node below is a base node ID (parameterized
  tests are mapped by base ID, per the project rules). Markers are 1:1 with §3.

| Test file | Base node ID | `@pytest.mark.lreq` |
|---|---|---|
| tests/test_collector.py | `test_batch_request_has_exactly_two_operations_with_one_identity` | LREQ-GQL-010 |
| tests/test_collector.py | `test_product_detail_query_requests_only_required_fields` | LREQ-GQL-020 |
| tests/test_collector.py | `test_page_views_operation_requests_its_scalar` | LREQ-GQL-020 |
| tests/test_collector.py | `test_request_construction_requires_graphql_credential` | LREQ-SEC-010 |
| tests/test_collector.py | `test_reversed_response_order_correlates_by_explicit_key` | LREQ-GQL-030 |
| tests/test_collector.py | `test_missing_correlation_key_is_malformed_not_positional` | LREQ-GQL-030 |
| tests/test_collector.py | `test_duplicated_unknown_and_ambiguous_correlation_fail_safely` | LREQ-GQL-030 |
| tests/test_collector.py | `test_explicit_key_mode_never_falls_back_to_response_position` | LREQ-GQL-030 |
| tests/test_collector.py | `test_validated_position_mode_is_accepted_not_validated_here` | LREQ-GQL-030 |
| tests/test_collector.py | `test_http_failure_is_an_operation_error` | LREQ-GQL-040 |
| tests/test_collector.py | `test_top_level_errors_are_not_masked_by_sibling_success` | LREQ-GQL-040 |
| tests/test_collector.py | `test_operation_level_errors_on_http_200_are_operation_errors` | LREQ-GQL-040 |
| tests/test_collector.py | `test_null_required_data_and_wrong_data_shape_are_operation_errors` | LREQ-GQL-040 |
| tests/test_collector.py | `test_invalid_state_value_and_missing_identity_are_operation_errors` | LREQ-GQL-040 |
| tests/test_collector.py | `test_page_view_scalar_type_and_range_acceptance` | LREQ-GQL-040 |
| tests/test_collector.py | `test_partial_success_retains_valid_operation_fields` | LREQ-GQL-050 |
| tests/test_collector.py | `test_failed_operation_fields_are_none_never_zero` | LREQ-GQL-050 |
| tests/test_collector.py | `test_state_annotation_covers_published_excluded_and_unknown` | LREQ-GQL-060 |
| tests/test_collector.py | `test_state_excluded_and_unknown_assets_remain_recorded` | LREQ-GQL-060 |
| tests/test_collector.py | `test_adapter_declares_no_metric_eligibility_verdict` | LREQ-GQL-060 |
| tests/test_collector.py | `test_retry_backoff_on_transient_and_no_indefinite_retry` | LREQ-GQL-040 |
| tests/test_collector.py | `test_transport_failure_does_not_escape_as_an_exception` | LREQ-NFR-030 |
| tests/test_collector.py | `test_request_metadata_json_carries_required_fields_without_secrets` | LREQ-SEC-020 |
| tests/test_collector.py | `test_error_summaries_and_metadata_are_redacted` | LREQ-SEC-020 |
| tests/test_collector.py | `test_adapter_cannot_bulk_enrich_or_consult_preflight_state` | LREQ-GQL-010 |
| tests/test_identity.py | `test_correlated_product_detail_reports_alias_mismatch` | LREQ-GQL-070 |
| tests/test_identity.py | `test_missing_returned_identity_is_not_an_implicit_match` | LREQ-GQL-070 |
| tests/test_identity.py | `test_adapter_mismatch_is_a_flag_not_a_metric_exclusion` | LREQ-GQL-070 |

All 28 nodes above are implementable with the hand-derived contract leg alone; none
reads a capture file. The former 29th node,
`test_duplicate_operation_names_correlate_by_operation_name_in_captured_batches`
(`LREQ-GQL-030`), is **removed from the frozen set along with its
`tests/traceability.json` entry**. It was the capture-derived duplicate-sequence test
(batch 4's 7× `ServerTime`, batch 5's 8× `AddToCartButton`) and cannot exist without
committed capture files; a marker resolving to an unimplemented test would be a
traceability violation, so no entry for it is left behind. Every LREQ ID in §3 still
has at least one marked node: the removal took the LREQ-GQL-030 node count from six to
five, and both `tests/test_collector.py` and `tests/test_identity.py` remain populated
as the dependency map's `Tests:` list requires. Duplicate-key handling is
still covered, hand-derived, by
`test_duplicated_unknown_and_ambiguous_correlation_fail_safely`. The deferral is
recorded as a scoping decision in §12.3 O-2.

Two marker assignments are recorded as **resolved by operator ruling** (§12 Q6), not
left as provisional choices for the implementer:
- `test_retry_backoff_on_transient_and_no_indefinite_retry` carries
  `LREQ-GQL-040` because retry/backoff is not a numbered lean requirement; the
  dependency map lists "rate limiting and retry policy consistent with the
  collector" as an *Implement* bullet (line 654) whose only normative SRS home is
  `LREQ-EXT-100`, owned by Chunk 3 (see §12 Q4). Attaching `LREQ-EXT-100` here would
  claim a Chunk 3 requirement; attaching nothing would leave a marked-test-less
  analytical node. The plan keeps `LREQ-GQL-040` (the operation-error and
  response-status requirement the retry loop is classifying).
- No node is marked `LREQ-TST-040` or `LREQ-TST-080`. Those two are Chunk 13's own
  requirements ("Primary owner: Chunk 13"), and A.2 gives Chunk 5 as a supporting
  chunk only. `LREQ-TST-040`'s attachment to the `test_collector.py` nodes that
  implement its required mechanism is deferred to **Chunk 13 as a marker-edit-only
  change**; §9's `tests/traceability.json` entries below are unchanged by that
  deferral (see §12 Q6).
- **`LREQ-TST-040` — a task-text slip in Chunk 3, not an ownership dispute.**
  `LREQ-TST-040` appears in Chunk 3's frozen plan only as task text: in its §7 box at
  its line 525 ("then add the matching `tests/traceability.json` entries
  (`LREQ-TST-040`)"), while Chunk 3's own §12.1 item 3 (its lines 820–823) reasons
  from the dependency map's line 130
  (`| LREQ-TST-040 | Chunk 13 | Chunk 3, Chunk 5, Chunk 6A | Chunk 13 | LREQ-TST-040 |`)
  to conclude that "primary owner and completion chunk are both Chunk 13". **Zero marked
  nodes exist for `LREQ-TST-040` anywhere in the suite** — it has no
  `@pytest.mark.lreq` marker and no `tests/traceability.json` entry in
  `tests/test_collector.py`, `tests/test_identity.py`, or any other module. Chunk 5
  therefore assigns it to none of its nodes, and the rectification is Chunk 13's
  marker pass. This is consistent with Chunk 3's frozen plan and does not contradict
  it: Chunk 3's §12.1 item 3 already places ownership with Chunk 13, so its §7 box
  names the wrong ID for the entries it creates rather than claiming the requirement.
  The note is recorded here (and carried in §12.4's escalation list) so the collision
  is settled before either file is extended.
- **`tests/traceability.json`.** Add exactly one entry per node above (28 entries),
  each mapping the fully qualified node ID
  (e.g. `"tests/test_collector.py::test_reversed_response_order_correlates_by_explicit_key": ["LREQ-GQL-030"]`)
  to the array of the marker(s) on that node. No existing entry is edited, removed, or
  reordered beyond appending — the 51 `tests/test_collector.py` entries Chunk 3 created
  (all Chunk 3 `LREQ-EXT-*`/`NFR-*`/`SEC-*`; corrected 2026-09-18: this previously
  read "25 `tests/test_collector.py` entries" — see §12.2 item 9) and the `tests/test_identity.py` entries
  standing behind its 26 marked nodes, 26 markers, and 8 distinct LREQ IDs
  (corrected 2026-09-18: this previously read "25 marked nodes, 25 markers" — see
  §12.2 item 9)
  (24 `LREQ-*` nodes — 18 single-node IDs, the other 6 nodes belonging to IDs that
  appear more than once — plus the `LREQ-TST-030` suite
  node) are untouchable here. The multi-LREQ arrays
  already present (e.g.
  `test_category_mismatch_and_unverified_map_to_discovery_status_vocabulary`) are
  the precedent for a node carrying more than one ID if review decides
  `test_page_view_scalar_type_and_range_acceptance` should also carry `LREQ-GQL-050`;
  that precedent is a style model only — no existing array is copied or reused for a
  new node, which is the `marker_mismatch` corruption §11 forbids.
- **Validator limitation — mandatory manual cross-check.** Per
  `interfaces/chunk-01.md` §6 and `chunk-02.md` §7,
  `tools/validate_traceability.py` (corrected 2026-09-18: this citation
  previously read the bare `tools/validate_traceability.py`, a path that does
  not exist on this tree — the real location is
  `src/niche_scout/tools/validate_traceability.py`, as this same sentence's own
  next line already stated; the bare form is retained here as the quoted prior
  wording, not as a live path)
  is still hard-wired to Chunk 0's required set (`src/niche_scout/tools/
  validate_traceability.py` line 131, where `main` calls `chunk_requirements(text)`
  with the default `chunk="0"` — `required = chunk_requirements(...)`) and its
  widening is deferred to Chunk 13. The validator's *completeness* direction therefore
  says nothing about Chunk 5. What it *does* still enforce for these new
  nodes, per its implementation, is: every node in `traceability.json` must exist in
  the collected suite (no `orphan_nodes`), its matrix entry must equal the marker
  set exactly (`marker_mismatch`), and every test node carrying markers must have an
  entry (no `missing_nodes`). Its `missing_required` direction — and therefore the
  "every new node has its own new entry" obligation — is **not** enforced by the
  validator, and is why the plan requires a **manual, two-directional cross-check** of
  §3's LREQ table against the actual markers before the gate, exactly as
  Chunks 1 and 2 did (§11 states the three variants and this same manual-enforcement
  boundary once).
- **No live network.** Every HTTP interaction is a fake transport. `pyproject.toml`
  declares no HTTP dependency and this plan adds none.
- **Not in this chunk's tests.** `LREQ-NFR-040`'s type-hint/docstring check is
  Chunk 0's `test_type_hints_and_docstrings` (its `Module` column does not name
  `collector_graphql.py` for that row, and the SRS states the requirement for "Public
  metric and scoring functions" only); Chunk 5 still writes type hints and
  null/edge-case docstrings on its public surface as a code-quality obligation, and
  no Chunk 5 node claims `LREQ-NFR-040`.

## 10. Definition of done (gate)

Copied verbatim from `Documents/requirements-dependency-map.md`, Chunk 5, "Gate:"
(lines 674–681).

- Reversed GraphQL response order passes.

  **Binding owner note (not optional guidance).** The gate reaches this bullet
  through §5.5's keyed-grouping mechanism, which Chunk 5 owns end to end:
  `correlate_operations` matches a `ProductPageViews` item arriving at index `0`,
  and `response_items` order decides nothing while a key is present. This bullet is
  satisfied **entirely** within Chunk 5, by the hand-derived contract-leg node
  `test_reversed_response_order_correlates_by_explicit_key` (§9). No capture is
  required and no other chunk participates.

- Missing or ambiguous operation correlation fails safely.

  **Binding owner note (not optional guidance).** Owner: **Chunk 5**. "Fails safely"
  has exactly two observable meanings here, and both are Chunk 5's: there is **no
  positional-inference path** under `EXPLICIT_KEY` (§5.5's MUST NOT clause), and the
  result is a **typed failed `EnrichmentResult`** with **no persisted record**
  (`execute_graphql_batch`/`enrich_asset` return values only; §5.11). The *visibility*
  obligation that a failure "SHALL remain visible in status and evidence fields" is
  `LREQ-NFR-030` (`Documents/SRS-lean.md` lines 1168–1169): "A failed page or sampled
  asset SHALL not abort unrelated categories or assets; the failure SHALL remain
  visible in status and evidence fields." The dependency map places that visibility
  obligation on Chunks 6A and 6B, which persist the independent operation outcomes —
  see the note on bullet 3 below. Chunk 5 supplies the typed failure and the
  `requirement_warning_code` that names it; it writes no status or evidence field.

- Partial ProductDetail/PageViews success is persisted independently.

  **Binding owner note (not optional guidance).** The gate phrase is quoted verbatim
  from `Documents/requirements-dependency-map.md` line 696, which reads: "persist
  independent operation outcomes, selected correlation mode, and endpoint signature"
  — that line is an **Implement** bullet of the **Chunk 6A** section (it appears in
  Chunk 6A's list at line 696, immediately after its line 694 "invoke the Chunk 5
  GraphQL adapter for the deterministic preflight set" and its line 695 "validate both
  ProductDetail and ProductPageViews operations for every preflight identity"), so
  the *persisting* half belongs to **Chunk 6A** (preflight) and **Chunk 6B** (bulk
  enrichment). Chunk 5's half is the **per-operation input**: two independent
  `GraphQLOperationResult` values, a partial-success `EnrichmentResult`, and an
  `EnrichmentObservationDraft` whose per-operation status fields are `"success"` and
  `"error"` (§5.9). **Chunk 5 opens no database connection and persists nothing**
  (§11: "SHALL NOT persist, insert, upsert, or connect to a database"), so this
  bullet must not be read as a Chunk 5 persistence obligation. A gate-verifier
  evaluates the bullet on the draft's independent per-operation status fields, not on
  a row.

- The adapter does not perform bulk enrichment or bypass the preflight gate.
- This chunk completes GraphQL response validation and correlation using the primitives from Chunk 1; it does not decide metric eligibility or bulk enrichment. Bulk identity/enrichment behavior remains in Chunks 6A and 6B.
- The metric-eligibility portion of LREQ-GQL-060 and the metric identity-mismatch eligibility portion of LREQ-GQL-070 are not complete until Chunk 7A applies them to metric inputs.

**These notes are binding on Chunk 5.** At a glance: bullets 2, 3, and 6 own their
halves explicitly. Bullets 1, 4, and 5 carry no split and are Chunk 5's alone.
**Bullet 1 is deliberately left unannotated.** Bullets 4–6 need no owner note of
their own — bullet 6 already carries its split in its own text, bullet 4 is satisfied
by Chunk 5 having no bulk-entry point, and bullet 5 names the two behaviors it does
not decide. The two notes above are explanation of the gate's ownership boundary,
not a second copy of the gate text.

## 11. Explicit prohibitions

- `collector_graphql.py` SHALL NOT import `sqlite3`, `metrics`, `scoring`,
  `database`, `pipeline`, `report`, or `cli`.
- `collector_graphql.py` SHALL NOT import `collector` (circular) and SHALL NOT
  import or call `collector_coveo` or any Chunk 3 code, name, or constant.
- `collector_graphql.py` SHALL NOT perform bulk enrichment, SHALL NOT define a
  function that accepts more than one `asset_identity_key`, and SHALL NOT issue any
  GraphQL operation other than `ProductDetail` and `ProductPageViews` (no
  `CurrentUser`, `ShoppingCartQuery`, `ServerTime`, `ProductRatingStar`, `Publisher`,
  `BigQueryCachedPackages`, `ProductTags`, `ProductMLRecommendation`, favorite-count,
  or page-hydration request).
- `collector_graphql.py` SHALL NOT read or accept a preflight status, gate decision,
  run status, or `IdentityPreflightStatus`, SHALL NOT bypass the preflight gate, and
  SHALL NOT persist, insert, upsert, or connect to a database.
- `collector_graphql.py` SHALL NOT read the system clock for calculation. The only
  permitted clock read is the default value of the injected `sleep` callable; every
  timestamp (`retrieved_at_utc`, and any caller-supplied reference time) is an
  explicit argument validated as timezone-aware UTC through `models.ensure_utc`.
- `collector_graphql.py` SHALL NOT read environment variables. Credentials arrive as
  a typed `config.Credentials`; environment reading stays in `config.get_credentials`
  (Chunk 0 / LREQ-SEC-010 primary owner).
- `collector_graphql.py` SHALL NOT put a credential value, an `Authorization` header,
  a CSRF token, a `_csrf` cookie value, a request header *value*, or a full response
  body into any `ValidationIssue`, error summary, warning, `header_names`, exception
  message, or `request_metadata_json`.
- **`collector_graphql.py` SHALL NOT construct, emit, or modify a `Cookie` header**
  (including `Cookie: _csrf=<token>`), and SHALL NOT accept a cookie value, jar, or
  session object as an input. The adapter sends the `X-CSRF-Token` header and nothing
  else that establishes a cookie. Retired `SRS-revision2.md` `OI-6` (line 173) leaves
  CSRF/session *sufficiency* open — whether `_csrf` is the only required cookie,
  whether another storefront session cookie is required, and whether the cookie value
  must equal the `X-CSRF-Token` header byte-for-byte are all unresolved — and
  Assumption A-4 (line 172) describes the observed request shape rather than a
  guaranteed authentication contract. Cookie handling is therefore a **scoped
  omission**, owned by no chunk until OI-6 resolves (§12 Q1(b)).
- **Header lookup in the adapter SHALL be case-insensitive.** `X-CSRF-Token` is
  emitted lowercase on the wire (`x-csrf-token`) and HTTP header names are
  case-insensitive, so any code that reads a header name from a mapping, a
  `GraphQLBatchResponse.header_names`, or a caller-supplied header map SHALL compare
  names case-insensitively and SHALL NOT depend on the caller's casing.
  `GRAPHQL_CSRF_HEADER_NAME` stays `"X-CSRF-Token"` as the canonical emission name
  (§12 Q1).
- **No retry or idempotency decision SHALL be keyed off `sentry-trace`.** The
  operator's captures show batches 4 and 5 omit `sentry-trace` entirely while
  batches 1–3 include it, so a retry layer that keyed idempotency or attempt tracking
  off that header would break on exactly those two batches. `sentry-trace` is an
  excluded header (§12 Q1(b)) and the retry decision stays internal to
  `GraphQLRetryPolicy` (§12 Q4).
- `collector_graphql.py` SHALL NOT fabricate a `0`, `0.0`, `""`, `[]`, `{}`, or
  `False` for a failed operation's field, and SHALL NOT treat a failed
  `ProductPageViews` operation as zero page views. `product_page_views` is either a
  validated non-negative integer or `None`.
- `collector_graphql.py` SHALL NOT infer an operation from a response item's index
  when `mode is EXPLICIT_KEY`, and SHALL NOT validate the fixed two-operation
  ordering itself under `VALIDATED_POSITION`; both are the identity preflight's job
  (Chunk 6A, LREQ-ID-020).
- `collector_graphql.py` SHALL NOT return, compute, or store a D/R/Q eligibility
  verdict, metric input, metric eligibility, usable-for-metric flag,
  `page_view_semantics_status`, run-level status, category warning list, or score.
  In particular it SHALL NOT set, infer, or detect a `PageViewSemanticsStatus` value:
  Chunk 6A initializes the run-level value, Chunk 7B detects `contradicted`, and
  Chunk 8 applies contradicted page-view handling. Chunk 5 has no
  contradicted-detection obligation at all (§12 Q5).
- `collector_graphql.py` and `collector.py` SHALL NOT redefine, shadow, monkeypatch,
  or re-export under a new name anything from `models.py`, `validation.py`,
  `config.py`, or `database.py`; new types specific to the adapter are prefixed
  `GraphQL*` or named `EnrichmentResult` / `EnrichmentObservationDraft` and none of
  them reuses a frozen name.
- No file outside §6 SHALL be edited, in particular `models.py`, `validation.py`,
  `collector_coveo.py`, `database.py`, `pyproject.toml`,
  `tests/test_validation.py`, `tests/test_contracts.py`, and `tests/test_database.py`.
- `collector.py` SHALL remain a facade: no behavior, no state, no logic beyond
  import statements and `__all__`.
- **Test-surface protection (scoped to `tests/`, never to `collector_graphql.py`).**
  Chunk 5's additions to `tests/test_collector.py` and `tests/test_identity.py`, and
  its new `tests/traceability.json` entries, SHALL NOT modify, extend, reuse, reorder,
  or delete any existing node, marker, or matrix entry — in particular, no existing
  marker array is reused for a new node. Both files' existing node IDs, marker sets,
  fixtures, and matrix entries stay byte-identical. The three concrete corruption
  variants this forbids, both enforced by
  `python -m niche_scout.tools.validate_traceability` (read directly; its `main`
  computes exactly these):
  - **`marker_mismatch`** — an entry whose LREQ set no longer matches its own node
    (`set(matrix.get(node, ())) != markers`). Typically caused by reusing an existing
    entry's array.
  - **`orphan_nodes`** — an entry with no corresponding node (`node not in tests`).
    Typically caused by renaming or removing a Chunk 3 node.
  - **`missing_nodes`** — a node with no entry (`markers and node not in matrix`).
  - **Completeness for *new* nodes is a separate, manual obligation.** The validator's
    *required-set* is still Chunk 0-scoped — `main` calls
    `chunk_requirements(text)` with its default `chunk="0"`
    (`src/niche_scout/tools/validate_traceability.py` line 131) — so its
    `missing_required` direction says nothing about Chunk 5. Enforcing "every new node
    carries its own new entry" is therefore §9's **manual, two-directional cross-check**,
    not `validate_traceability.py`. §9 carries the bounds; this bullet adds only the
    three variants and the manual-enforcement statement, and is not a second copy of
    them.
- Tests SHALL NOT make a live network call, read the system clock for an expected
  value, or carry a credential value; every HTTP interaction SHALL go through an
  injected fake transport.
- `metrics.py` and `scoring.py` SHALL remain pure and unmodified;
  `python -m niche_scout.tools.check_import_boundaries` SHALL still exit 0.
- Chunk 5 SHALL NOT fix or modify `tests/test_contracts.py`, including its passing
  `tests/test_contracts.py::test_repository_protocol_and_schema_specification` node
  (marker at line 881): the file is outside Chunk 5's file scope, not a source of
  pre-existing debt.
- Chunk 5 SHALL NOT widen `tools/validate_traceability.py` (corrected
  2026-09-18: this citation previously read the bare
  `tools/validate_traceability.py`; the real location is
  `src/niche_scout/tools/validate_traceability.py`, and the bare form is
  retained here as the quoted prior wording, not as a live path); its required-set
  widening is Chunk 13 (`LREQ-NFR-060`).

## 12. Resolutions, scoped omissions, assumptions, and open items

Every question Q1–Q7 is **CLOSED by operator ruling**; none remains phrased as a
question the operator still has to answer. Three further items that were previously
listed as open are also closed: **O-2** (the capture-derived golden leg) is closed as a
scoping decision and now lives in §12.3, **O-3** (the `EXCLUDED`/`CANDIDATE`
correlation-mode extension) is closed by operator ruling and now lives in §12.1, and
**O-4** (the CSRF/cookie-sufficiency scope question) is closed as a **Chunk 5 scope
question** and now lives in §12.3.

**For the plan's content, nothing blocks the freeze.** No LREQ, contract, or gate
question below is unanswered. **Amended 2026-09-18:** the sentence that stood here read
"**Nothing blocks this plan's freeze.** §12.5 is **empty of blocking items**", and that
is no longer literally true — **§12.5 now also carries the five §12.6 items**, one of
which (the `Status` disposition) is a decision only the operator can make. The
substantive claim is unchanged: none of the five blocks the plan's **content**, and
each concerns the *change* §12.6 records rather than any requirement text. The
paragraph that follows describes OI-6 alone and is retained unedited.

**Prior item.** §12.5 holds one pre-existing item, **OI-6**, which is an external
unknown of the retired parent SRS, open by
design and deferred out of Chunk 5's scope. OI-6 is *not* a Chunk 5 blocker, and O-4 —
the item that previously gave OI-6 a blocking framing — is now resolved as a scope
question. The test applied: *can the plan make the correct choice without more
information?* For O-4 it can. Chunk 5 sends `X-CSRF-Token` and never constructs a
`Cookie` header, and **every** branch of OI-6 — including the worst case, that a
session cookie beyond `_csrf` is required — resolves to the same adapter behavior, so
the plan carries no decision that a downstream chunk would have to guess at. OI-6's own
resolution is an obligation of the retired parent SRS's validation program, which
Chunk 5 does not inherit; the item is recorded in the dependency map's §7 open-items
list so it has an owner-of-record.

### 12.6 Retroactive authorship, the two rulings this plan now carries, and their corrections (recorded 2026-09-18)

This section is **new** and is the only change this dispatch makes to the plan. It
supersedes nothing: no earlier item is deleted, contradicted, or reworded. Its six
entries are the retroactive-authorship record, the two operator rulings with their
mechanical proofs, two corrections, and the test declarations those rulings require.

#### 12.6 item 1 — This plan is retroactive, and its Status is not this plan-writer's to set

`Status:` now reads `DRAFT`, changed from `FROZEN`, for one reason: **this plan was
written after `collector_graphql.py` had already been implemented.** The header's
`Last amended` line and its `(★)` footnote carry the fact and the two dispositions.
The only other element changed on the header is the added
`Documents/interfaces/chunk-03.md` depends-on line (item 4). Nothing in §1–§11 other
than the four ruled-correction markers described in items 2 and 3 was touched.

Two consequences follow, and both belong to the operator:

- **The plan's content is mature even though its provenance is not.**
  `Status` was `FROZEN` and §12.5 holds no blocking item; every question the plan
  carried is closed by ruling. The `DRAFT` value records *how this document came to
  exist*, not doubt about what it says. Restoring `FROZEN` is a legitimate ruling;
  so is keeping `DRAFT` until the corrections in items 2 and 3 land. This
  plan-writer is **not authorized to set `FROZEN`** and has not.
- **Six test nodes are red on the current HEAD, and two of them are this chunk's.**
  §9's baseline facts (one collector test file, 2532 lines, 51 distinct marked
  nodes; one identity test file, 26 distinct marked nodes; 144 matrix nodes) are
  operator-supplied baselines, not a suite run performed for this plan; the current
  failure set is recorded in item 5 with its own status label. The test declarations
  in item 5 do **not** assume those baselines hold — they require a re-count.

#### 12.6 item 2 — RULED: `state` moves out of the structural required-member group, and E7 is corrected in the same unit

**The ruling.** `"state"` leaves `PRODUCT_DETAIL_REQUIRED_MEMBERS` and joins the
semantic state group (`StateEligibilityAnnotation`, whose `state_unknown` is the
missing/null/unparsable case). The constant and E7 (`§8 :1311-1315`) change **as one
unit**. Splitting them — moving the constant while leaving E7 asserting a check that
no longer exists — is what the ruling forbids.

**(a) The predecessor text, quoted, not deleted.** E7 as this plan carried it before
this dispatch read, verbatim:

> **E7 — Wrong data shape and invalid state (LREQ-GQL-040).** `product` present but
> not an object, a required member missing, and `state` present but not a string are
> each an operation error for `ProductDetail`; a present non-`"published"` state is
> **not** an operation error — it is `state_excluded`, annotated, and retains the
> asset in discovered breadth (LREQ-GQL-060 annotation half).

Condition semantics were added to that bullet in this dispatch **without deleting the
old sentence**: the ruling is recorded, and the plan still states the pre-ruling
behavior explicitly rather than rewriting it silently.

**(b) The plan contradicted itself 2–1, and the ruling follows the majority.** §5.8
(`:914-923`, raw `state` kept verbatim, including `None` for a missing state) and E10
(`:1328-1332`, "a missing, null, or wrong-typed value is `state_unknown`") agree with
the ruling; E7 (`:1311-1315`) contradicts them. The 2–1 split is evidenced by reading
two separate sections of this plan. See
`Documents/plans/chunk-03-coveo-discovery-adapter-and-streamed-raw-persistence.md`
§12.13(i)–(iii), which records the same ruling against this plan's E7 by line number.

**(c) No higher authority decides the point, so the ruling is the operator's to make.**

- `Documents/SRS-lean.md:329-330` (LREQ-GQL-060) is the SRS's **only** `state_unknown`
  mention: "Only `state = \"published\"` assets are eligible for D, R, and Q.
  State-excluded and state-unknown assets remain part of discovered breadth." It
  describes **retention** of assets that already are state-unknown and never what
  **produces** that state.
- `Documents/interfaces/chunk-01.md:315-317` is the **entire** prose contract for
  `annotate_state_eligibility` — "is an annotation, not a decision:
  `remains_in_discovered_breadth` is always `True` and the result exposes no D/R/Q
  eligibility attribute." It states **no** condition semantics and **no** check order.
- The dependency map is silent on classification for this requirement. Its Chunk 5
  section (`Documents/requirements-dependency-map.md:639-681`) lists "state
  eligibility annotation; excluded and unknown-state assets remain in persisted
  observations and discovered breadth" at `:652` and names `LREQ-GQL-060` in the
  supporting list at `:664`, but states no condition for `state`.
- The sentence "Absent, null, and wrong-typed members each produce their own issue
  code, stay `None` in the returned fields, and are never substituted with a default"
  is **not** in the chunk-01 interface. It lives at
  `src/niche_scout/collector_graphql.py:1022-1027`, a **Chunk 5 docstring describing
  Chunk 1's behavior**. A prior dispatch attributed it to the interface; that
  attribution was the error, and it is refuted here so no future reader re-derives
  the ruling from it.

**(d) The mechanical proof, written down so it does not have to be re-derived.**
Read on HEAD `4135e6e`; re-runnable by reading the cited lines.

- `:876-885` defines `PRODUCT_DETAIL_REQUIRED_MEMBERS` with `"state"` as its sixth
  member.
- `:1050-1055` calls
  `validate_response_shape(payload, expected_shape="mapping", required_members=PRODUCT_DETAIL_REQUIRED_MEMBERS, field_types=PRODUCT_DETAIL_NUMERIC_MEMBER_TYPES)`
  and **does not short-circuit**: a missing member becomes
  `response_missing_required_member`.
- `:1148` is the guard `elif state_annotation.state_unknown and state_value is not None:`.
- `:1160-1180` constructs `ProductDetailFields`, with `state=` at `:1177` and
  `state_annotation=` at `:1178`. (`:1178` is the **argument line**, not the
  construction line; the construction begins at `:1160`. A prior dispatch recorded
  `:1178` as the construction site and that locant is corrected here.)
- `:1182-1189` returns `product_detail=fields if failure_class is GraphQLFailureClass.NONE else None`.
- `:1192-1209` `_classify_product_detail_failure` maps
  `response_missing_required_member` → `WRONG_DATA_SHAPE` at `:1203-1204`.

Applied to a payload with `state` **absent**: `response_missing_required_member` is
emitted structurally at `:1053`; the `:1148` guard evaluates
`True and False` → `False`, so no `invalid_state_value` issue fires; and
`:1182-1189` returns `WRONG_DATA_SHAPE` with `product_detail=None`, **discarding the
fully-built `fields` object that carries `state_unknown=True`**. So **no caller can
observe a `SUCCESS` operation with `state_unknown == True` for a state reason** —
which is exactly the behavior the ruling changes.

The guard's two sides diverge only for a **present-but-unusable** value: a present
non-string yields `state_value` non-`None` and `state_unknown=True`, so `:1148` fires
and `:1154-1157` records `invalid_state_value`, mapped to `INVALID_STATE_VALUE` at
`:1199-1200`. **That half is unchanged by the ruling and must not regress.**
LREQ-GQL-040's "invalid state values" clause (`Documents/SRS-lean.md:318-323`) keeps
its operation-error mapping for a present-but-unusable value.

**(e) What the ruling does *not* say.** E10's "missing, null, or wrong-typed value is
`state_unknown`" is a rule about the **annotation**, not about the operation outcome,
so correcting E7 does **not** mean every missing/null/wrong-typed `state` is benign —
only **missing** and **null** are. See
`chunk-03-coveo-discovery-adapter-and-streamed-raw-persistence.md` §12.13(i), which
states the same caution.

**(f) The correction is Chunk 5's to land, in a separate wave, and it is not done.**
No file under `src/` or `tests/` was changed by this dispatch. The code change (delete
`"state"` from `PRODUCT_DETAIL_REQUIRED_MEMBERS` at `:876-885`, alongside the E7 text
correction), the fixtures, and the tests in item 5 land together in that wave.
Because the ruling changes observable behavior, it is gate work: gate bullets 1–6 of
§10 are all evaluated on the corrected behavior, and a gate-verifier that finds the
constant unchanged should fail the gate on bullets 2, 4, and 5 rather than accept the
plan text as evidence.

**Status (recorded 2026-09-19): the wave landed.** `"state"` was removed from
`PRODUCT_DETAIL_REQUIRED_MEMBERS` (`src/niche_scout/collector_graphql.py`) and E7
was corrected in the same unit, as this item requires. No fixture or test needed a
change: the tolerance boundary below is exactly what the two tests that were red
before the wave already asserted. The sentence above is retained as the record of
the state before the wave; the E7 bullet's "Not applied" note is superseded by the
"Correction applied" note now carried in that bullet.

**Status (recorded 2026-09-19, later unit): the id-alias classification ORDER did
need a code correction, and the preceding sentence is superseded on that point.**
The wave above left one test red:
`tests/test_collector.py::test_invalid_state_value_and_missing_identity_are_operation_errors`
failed on its `missing_identity_member_body` case
(`tests/fixtures/graphql_fixtures.py:770-780`), asserting
`WRONG_DATA_SHAPE` where `MISSING_IDENTITY` was required. Cause: `id` and
`productId` stay in `PRODUCT_DETAIL_REQUIRED_MEMBERS` (item 2(f) scopes the member
deletion to `"state"` only; `Documents/rulings/chunk-05-state-member-ruling.md:534`
records the same), so a payload that OMITS one alias keeps the identity group in
`validate_response_shape` saturated and emits `response_missing_required_member`
instead of `response_missing_identity`; classification then fell to the
required-member route. LREQ-GQL-040 fixes no order between "wrong data shape" and
"missing identity", so the fix states the absent-alias fact structurally in
`validate_product_detail_payload`'s existing identity backstop, which now fires for
"an alias member was omitted" as well as "no populated alias was returned". Only
`PRODUCT_DETAIL_ALIAS_MEMBERS` members are covered: every absent non-alias required
member still classifies as `WRONG_DATA_SHAPE`. No fixture and no test was changed —
the assertion was correct as written; it is the code that was behind it.

**(g) The tolerance boundary as implemented, so it need not be re-derived.** The
structural path no longer judges `state` at all: `validate_response_shape`
(`:1094-1099`) is called with required members that no longer include `state`, so an
absent `state` emits no `response_missing_required_member` and a `null` `state` emits
no `response_null_required_member`. `state` is then read at `:1181-1182` and
annotated by `annotate_state_eligibility`, whose `state_unknown` covers both. The
guard at `:1192` (`elif state_annotation.state_unknown and state_value is not None:`)
is **unchanged and must stay unchanged**: it is what keeps a present-but-unusable
(non-string) `state` an `invalid_state_value` issue, which
`_classify_product_detail_failure` (`:1260-1261`) maps to `INVALID_STATE_VALUE`.
Deleting the `and state_value is not None` clause would silently swallow the
non-string case and is a regression, not a simplification.

#### 12.6 item 3 — RULED: the metadata must carry real operation names and correlation keys; credential-shaped values stay redacted

**The ruling.** Operation names and correlation keys reach
`request_metadata_json` as their **real values**. Credential-shaped values stay
redacted. The fix is scoped to `_metadata_text` (`:1423-1425`) and to the
name/key/`failure_classes` call sites (`:1501`, `:1503-1504`, `:1509-1511`, `:1454`).

**(a) The implementation is the deviant.** `_metadata_text` (`:1423-1425`) is
`return redact_value(str(value))[:max_chars]`, and `build_request_metadata_json`
routes every operation name, correlation key, and additional key member through it at
`:1501`, `:1503-1504`, and `:1509-1511`. `redact_value`
(`src/niche_scout/validation.py:183-198`) never returns the value's own text; it
returns a placeholder rendered as `f"<{_PREFIX}: {rendered}>"` or
`f"<{_PREFIX}: {rendered} of length {length}>"` (`:196-198`), with the prefix defined
at `:143` as `"value redacted"`. So the persisted metadata contains placeholders
where the plan requires values.

**(b) What the plan requires instead.** §5.10's table requires the names:

> | `operation_names` | the two operation names, in request order | never absent |

(§5.10 `:1080`) and the keys:

> | `correlation_keys` | `{operation_name: correlation_key or null}` | `null` per operation when no key was present |

(§5.10 `:1081`).

**(c) The plan's redaction guarantee is not the obstacle.** §5.10's guarantee
(`:1089-1095`) says `build_request_metadata_json` "accepts **no credential, header-value,
cookie, or body parameter at all**", so no such value can reach the JSON without a
signature change. An operation name is not one of those parameters, and the argument
is stronger than that: **the caller passes the names in already.** Rebuilding them as
placeholders cannot add protection the caller's own inputs do not already determine —
it only destroys the two fields the requirement names.

**(d) The five forbidden categories, from E14, enumerated.** (§8 E14.) (1) a
credential value, (2) an `Authorization` header, (3) a CSRF token, (4) a cookie
value, (5) a full response body. **An operation name is none of the five**, and
neither is a correlation key — which is itself an operation name, per §4.1 and §5.10
(`:1081`, `:1091`). LREQ-SEC-020 (`Documents/SRS-lean.md:351-352`): "Secrets SHALL
NOT be written to source control, logs, SQLite, or error messages. The `.env` pattern
SHALL be ignored by version control." A lean operation name is not a secret under
that text.

**(e) The corrections are two-sided, and the redaction half must not regress.**

- `failure_classes` at `:1454`:
  `text = _metadata_text(item)` **breaks the allow-list check** — a redacted
  placeholder can never equal a member of `allowed_classes`
  (`:1449`, `{member.value for member in GraphQLFailureClass}`), so
  `metadata["retry"]["failure_classes"]` is silently always `[]`, contradicting
  §5.10's `retry` row (`:1086`).
- `_metadata_text` also serves genuinely secret-capable inputs: `:1454`'s
  `failure_classes` items and the `:1509-1511` key **names**. Names are
  structurally safe, but a future caller could pass a credential-shaped string into a
  key slot, and the plan's answer is already written: "The `retry` mapping is
  re-serialized key-by-key against an allowlist rather than passed through wholesale,
  so an unredacted string in a caller's mapping cannot leak" (§5.10 `:1094-1095`).
- So the corrected module keeps **two distinct renderers** — a bounded text renderer
  for names and keys (which must **normalize a non-string through `str()`** before
  bounding, since a non-string key or name would raise from the `len()` inside
  `redact_value`, `validation.py:196-198`) and `redact_value` for
  credential-capable inputs. How the two renderers are named and split is the
  implementer's choice, and is recorded as an open question in §12.5 so the reviewer
  rules on it before it lands.

**(f) The correction is Chunk 5's to land, in a separate wave, and it is not done.**
No file under `src/` or `tests/` was changed by this dispatch. `collector_graphql.py`
is not in Chunk 3's §6 and every code change described here is Chunk 5's.

**(g) How the deviation survived review, recorded because it is the finding and not
an aside.** The test comment at `tests/test_collector.py:2427-2429` states the
deviant behavior as *intent* — "Correlation keys and operation names are persisted
redacted: the JSON never carries a raw operation name, so a name is asserted against
the result, not the serialized metadata" — and the assertions around it are written
to pass either way (`:2430-2433`), so no red node pins it. Second, Chunk 5 was
implemented **before** Chunk 3 was verified and before `Documents/interfaces/chunk-03.md`
existed; the sequencing is the recorded root cause and is why item 4's depends-on line
is added. §6's "Files touched" table is **not** amended here: this plan-writer could
not open `interfaces/chunk-03.md` to confirm what it publishes, and changing that list
on a guess is exactly the failure that produced this item.

#### 12.6 item 4 — Dated correction: the depends-on header gained `interfaces/chunk-03.md`, and the interface is cited by name only

**Correction (recorded 2026-09-18).** The header's depends-on list did not name
`Documents/interfaces/chunk-03.md`, although the chunk that owns the Coveo side of the
shared facade (`src/niche_scout/collector.py`) is verified and its contract is
published. The line is added. **Status label for the interface's content: UNVERIFIED.**
This plan-writer did not open `Documents/interfaces/chunk-03.md`, so **nothing in this
plan quotes it, depends on its wording, or asserts what it contains** — including the
new depends-on line, which records only that the file exists, is named in three
earlier places in this plan, and that Chunk 3's plan reads `Status: VERIFIED`
(READ at that plan's `:3`).

The reason the rename/citation matters is a `Status` change, not a content change:
`Documents/interfaces/chunk-03.md` was **newly added to a `Status: FROZEN` header**,
which is a document-consistency event this plan cannot insist is a no-op until someone
reads what the interface actually publishes. It is therefore recorded as a correction
and left to review, and it is not accompanied by any new §11 prohibition — the
restatement of §11's existing prohibitions ("SHALL NOT import or call `collector_coveo`
or any Chunk 3 code, name, or constant"; "May not edit `collector.py` beyond the single
`__all__`/re-export line") is **deliberately omitted**, because §11 already carries
them and a second copy is exactly the kind of restatement the counting and citation
rules exist to prevent. To be explicit that this is a ruling and not an oversight:
**this dispatch deliberately did not add a prohibition bullet.** §11's two existing
bullets cover the dependency; a duplicate is a defect. This plan-writer could not open
the interface to confirm what it publishes, so the ruling is: no new §11 text, and the
review decides. See §12.5.

#### 12.6 item 5 — Tests this plan declares for the two rulings, and their LREQ markers

**The markers are already-determined, not invented.** Each declaration below names a
marker **and** the existing baseline entry it attaches to. Both new nodes go in
`tests/test_collector.py` and need **new** `tests/traceability.json` entries, because
`validate_traceability.py` requires a matrix entry for every marked node. No existing
entry is edited.

- **The `state`-guard pair — one node, `test_state_missing_and_null_are_benign_but_unusable_state_still_errors`,
  marker `@pytest.mark.lreq("LREQ-GQL-060")`.** This marker is directly evidenced, not
  chosen: **five existing nodes already carry it** —
  `tests/test_collector.py:2271-2272` (`test_state_annotation_covers_published_excluded_and_unknown`),
  `:2289-2290` (`test_state_excluded_and_unknown_assets_remain_recorded`), `:2327-2328`
  (`test_adapter_declares_no_metric_eligibility_verdict`), `:2364-2365`,
  `:2398-2399` — and `tests/traceability.json:142-145` carries one matching entry per
  node. The node asserts **both halves of `:1148`'s guard, as one unit**: a
  **missing** `state` is benign (`product_detail.is_success` is `True`, `state_unknown`
  is `True`, `state` is `None`, the sibling page-view operation is unaffected), a
  **null** `state` is benign on the same terms, and a **present-but-unusable** `state`
  (a non-string) is *still* `GraphQLFailureClass.INVALID_STATE_VALUE` with
  `product_detail=None`. The file already carries the benign half in substance at
  `:2301-2324` (`del payload["state"]` → `assert unknown.product_detail.is_success`,
  which is red on current HEAD) and the error half at `:2040-2051`; this node pins both
  halves **on the corrected behavior**, which is why it is declared rather than
  substituted for either.
- **The node-6 metadata node — one node, `test_request_metadata_json_carries_real_operation_names_and_correlation_keys`,
  marker `@pytest.mark.lreq("LREQ-SEC-020")`.** Evidence: the existing node at
  `:2411-2412` carries `@pytest.mark.lreq("LREQ-SEC-020")` and
  `tests/traceability.json:144` carries its matching entry; the marker is copied from
  a node that already asserts this same contract. The node asserts the two names and
  the correlation keys are the **real values**, not redaction placeholders —
  `set(metadata["operation_names"]) == set(GQL_ORDERED_OPERATIONS)`, `GQL_ORDERED_OPERATIONS[0]`
  appearing **verbatim** in the serialized `request_metadata_json`, the keys present
  as the real names, and **no value containing `"value redacted"`** — while the
  credential assertions at `:2439-2444` still hold (fixture CSRF token, header values,
  `cookie`, `authorization`, and `token` absent). It **replaces** the deviant
  comment and the pass-either-way assertions at `:2427-2433` in the same wave.
- **Optional third node, `test_retry_failure_classes_survive_metadata_serialization`,
  marker `@pytest.mark.lreq("LREQ-GQL-040")`** (evidence: `tests/traceability.json:135`
  pairs `test_invalid_state_value_and_missing_identity_are_operation_errors` with
  `LREQ-GQL-040`, i.e. the class vocabulary is already this requirement's). It pins
  the `:1454` / `allowed_classes` consequence of item 3(e):
  `metadata["retry"]["failure_classes"]` is not silently `[]` for a retry-exhausted
  transient exchange. **Declared, not required** — gate bullets 1–6 do not reach it,
  and it is listed as a decision for the ruling operator rather than as an obligation.
- **Fixture consequences (declared, not written).** The benign-`state` node needs a
  *present-but-null* `state` body, i.e. a variation on
  `tests/fixtures/graphql_fixtures.py`'s `product_detail_payload()`; the metadata node
  needs **no** new fixture, since it uses `gqlfx.in_order_success_body()` and the real
  `GQL_ORDERED_OPERATIONS`. §6's fixture row already lists "request/response golden
  vectors" in that file, so no §6 amendment is proposed here.
- **Baselines these declarations require, and do not assume.** The counts in §9 are
  operator-supplied (one collector file of 2532 lines with 51 distinct marked nodes,
  one identity file with 26, a matrix of 144 nodes — **all UNVERIFIED in this
  dispatch**). The correction wave **MUST re-derive all three by querying the
  artifacts** (`ast` walk for nodes, anchored decorator grep for markers, top-level
  JSON keys for matrix entries), with the unit named, before it adds any entry.
  **Recorded as an open question in §12.5.** The current failure set is also UNVERIFIED
  here: the operator reports **6 failed / 140 passed** across the suite and **6 failed
  / 47 passed** in that one file, all 6 being code-side deviations, of which these two
  rulings are two. The wave **MUST confirm the whole set of six by re-running the
  suite** and **STOP and report** if any failing assertion is entangled differently
  than assumed — in particular if any of the six pins the **pre-ruling** behavior, and
  specifically if one is
  `tests/test_collector.py::test_request_metadata_json_carries_required_fields_without_secrets`
  (`tests/traceability.json:144`), which the `:2427-2433` comment suggests is
  **bystander** rather than a node pinning the defect. Nothing here depends on which
  it is, but the correction wave must not assume either.
- **Correction branch, so the fix does not produce a red test.** If a `request_metadata_json`
  assertion elsewhere **does** encode the placeholder behavior, this plan declares that
  it is corrected **in the same unit as the code change**, with its `tests/traceability.json`
  entry **updated in place to the same LREQ ID it already carries**, and with **no node
  renamed and no entry deleted** so that no existing entry is left orphaned. The same
  rule applies to the `state`-guard node.

#### 12.6 item 6 — What this dispatch did and did not do

- **Changed, in this file only:** the `Status:` value (`FROZEN` → `DRAFT`), the
  `Last amended` line and its `(★)` footnote, the depends-on line for
  `interfaces/chunk-03.md`, four correction markers in §2 and §8 marking ruled text as
  superseded, and this §12.6.
- **Not changed:** §1, §3, §4, §5, §6, §7, §9's baseline figures, §10's six gate
  bullets, §11 in full (including the deliberately-omitted new prohibition of item 4),
  and §12.1–§12.5.
- **Not touched:** `src/`, `tests/`, `Documents/SRS-lean.md`,
  `Documents/interfaces/chunk-01.md`, `Documents/interfaces/chunk-03.md`,
  `Documents/plans/chunk-03-*.md`, and `Documents/requirements-dependency-map.md`.
- **Status labels used in this section.** `READ` — quote taken from an opened file at
  the cited line, re-checked against the citation. `COUNTED` — a stated query over the
  artifact with the unit named. **No count is asserted anywhere in §12.6.** `UNVERIFIED`
  — the §9 baselines, the interface content, and the current failure set, all as
  labelled in items 1, 4, and 5.

#### 12.6 item 7 — The freeze, and the dated record of the §12.5 header correction (recorded 2026-09-18)

**(a) The freeze (OPERATOR-RULED 2026-09-18).** `Status:` was changed `DRAFT` →
`FROZEN` in this pass. The operator's ruling, in their words: "DRAFT is supposed to mean
'the content hasn't been verified as accurate.' This content has been verified as
accurate, twice over, by two different reviewers checking against source rather than
against the document's own claims about itself." The provenance fact is **kept as text
rather than smoothed over** — the `(★)` footnote now states the retroactive-authorship
defect plainly, records it as accepted, and names the independent verification (SRS
requirement text, the dependency map's Gate list, and existing `tests/traceability.json`
entries) as the basis. This supersedes §12.6 item 1's statement that `Status` reads
`DRAFT`; item 1's provenance finding is unchanged and is **not** deleted.

**(b) Dated correction: §12.5's opening sentence asserted there was no change-blocker
while two of its own listed items block the change.** The correction itself was applied
earlier on 2026-09-18 and was **applied silently** — nothing in this document recorded
that a correction had occurred. This entry supplies that record retroactively, per the
operator's ruling: "Chunk-03's plan records its corrections; chunk-05's not doing the
same isn't a style inconsistency, it's the exact 'quiet substitution vs. dated
correction' distinction that's been enforced on every other document this session."

**The superseded sentence, quoted verbatim as it stood (`:2908-2909` before this edit):**

> This section contains no blocking item for the plan's *content*, while carrying two
> acknowledged change-blockers that are the operator's to clear.

**What was wrong with it.** Asserting that the section "contains no blocking item"
immediately above five listed items, **two of which block the change** — item 1 (the
`Status` disposition) and item 4 (the suite must be run and the failing set confirmed
before any edit) — is false on its own terms. It also read as a claim about the
*content* while the two blockers were being acknowledged in the same breath, so a reader
scanning the first sentence would conclude no item gated the change.

**What it says now** — the paragraph's opening was replaced with text that names the
blockers rather than denying them: "This section contains no blocking item for the
plan's *content*, while carrying two acknowledged change-blockers that are the
operator's to clear. … **Two of the five are marked below as blocking the change rather
than the content** — item 1 … and item 4 … — and clearing them is likewise the
operator's." The body of §12.5 was not otherwise rewritten, and its original text stands.

**Recorded, not reopened.** The subject of this entry is the **correction**, not the
five items. The two items it names are now decided (see (c)); the correction record
neither resolves nor re-opens any of them, and no item text in §12.5 was edited by this
pass.

**(c) §12.5's decided items (OPERATOR-RULED 2026-09-18).** Recorded here since §12.5
still presents these as open. Each original question above is retained and marked
decided beneath rather than deleted.

- **Item 1 — DECIDED: `FROZEN`.** Retroactive authorship is an accepted defect of
  provenance, not a review gate. Landed as (a) above; the `(★)` footnote now records it.
  OPERATOR-RULED 2026-09-18.
- **Item 3 — DECIDED, and the plan's constraint is AFFIRMED, not newly created:**
  `"state"` **stays out of the request selection set.** Pulling it from the *structural
  required-member* check says nothing about what fields get *requested*. §12.5 item 3's
  MUST-NOT constraint — do not read a response-validation ruling into a request-shape
  decision — is correct and is now operator-affirmed. OPERATOR-RULED 2026-09-18.
- **Item 5 — DECIDED: re-derive, do not assume, and gate on it explicitly.** §9 takes no
  entry against its baseline counts until those numbers are confirmed at current HEAD.
  The probe re-deriving them is a separate dispatch; **this plan-writer did not run it
  and asserts no baseline figure here.** OPERATOR-RULED 2026-09-18.
- **Items 2 and 4 — unchanged.** Item 2 remains the implementer's and the reviewer's
  call; item 4 is a dependency that resolves when the probe returns, not a decision.

> **Dated correction (2026-09-18): two of the five items in the list above were
> relabelled, and three of its four bullets' opening labels needed correcting.** Every bullet's *body* is
> unchanged; only the item number each bullet is headed with was corrected, and the
> superseded labels are retained here rather than deleted.
>
> - Second bullet: headed **Item 2**, but its body answers **item 3** (*whether
>   `"state"` is still required in the request selection set*) — it even cited §12.5
>   item 3's MUST-NOT constraint. Relabelled **Item 3**.
> - Fourth bullet: headed **Items 3 and 4**, but its second clause answers the
>   **two-renderer split in `collector_graphql.py`**, which is **item 2** (the first
>   clause, carried unchanged, is item 4). Relabelled **Items 2 and 4** — a single
>   opening label naming both items, so one label carries the two relabelled items.
> - Fourth bullet, clause 2: its second clause answers "resolves when the probe returns",
>   which is **item 5's** subject — and which the bullet above it already records as
>   decided. The bullet's opening label does not name it, so this clause was **left
>   as it stands and not relabelled**; only the bullet's opening label moved, from
>   items 3 and 4 to **Items 2 and 4**.
>
> The bullet carrying two clauses is the *fourth* of the list's four bullets, i.e.
> **the "Items 2 and 4" bullet at `:2257-2258`, not the third** — the list has four
> bullets, not five. Unaffected: the first bullet (**Item 1**) and the third bullet
> (**Item 5**), each of which already matched its body, and the fourth bullet's first
> clause. The corrected bullet list occupies `:2245-2258` at
> this file's line numbering (this note begins at `:2260` in the corrected file). No
> ruling's substance and no `OPERATOR-RULED 2026-09-18` attribution was altered.

### 12.1 Closed questions (binding values)

**Q1(a) — RESOLVED: the endpoint and its header set are pinned.**
`Documents/retired-documents/SRS-revision2.md` **is** an authorized source for
endpoint details, and **only** for endpoint details. Authority: `Documents/SRS-lean.md`
§1.5 (lines 123–132) defers to the parent SRS for unchanged endpoint details
("**[PARENT]** — `SRS-revision2.md`, the full-MVP SRS and source for unchanged
endpoint details", lines 125–126) while reserving sampling, sample-derived metrics,
evidence grades, rankability, and sensitivity analysis as the lean SRS's own normative
domain (lines 131–132). Precedent already frozen in this repo: the **FROZEN**
`Documents/plans/chunk-03-coveo-discovery-adapter-and-streamed-raw-persistence.md`
(corrected 2026-09-18: this citation previously read
`…-and-streamed-raw-persistence.md`, which resolves to no file on this tree)
§12.5 ("RESOLVED — endpoint details are capture-confirmed", lines 863–868) cites the
same retired document for the Coveo endpoint, and its §7 uses the same citation at
line 508.

Bound values:

- `GRAPHQL_BATCH_ENDPOINT = "https://assetstore.unity.com/api/graphql/batch"` —
  the retired document's `REQ-GQL-010` (line 244): "Endpoint SHALL be exactly
  `POST https://assetstore.unity.com/api/graphql/batch`".
- **No `ENDPOINT_CONTRACT_VERSION` bump.** The endpoint, method, batch shape, and
  `operations` header are unchanged from the parent contract, and adding
  response-correlation and retry logic is internal to Chunk 5. `"1.0.0"` stands.

**Q1(b) — RESOLVED: headers pinned; CSRF is sourced from A-4 and OI-6, NOT from
retired §4.4.**
Correction recorded: an earlier version of this plan cited retired §4.4 for
`X-CSRF-Token`. §4.4 of the retired document is the *dashboard interface* section and
the lean SRS's own §4.4 is titled "Identity preflight" and states that "The formal
reusable identity-validation study in the parent SRS is replaced by a per-run
deterministic preflight" (SRS-lean.md lines 356–357). That **substitution** is what
survives, so §4.4 must not be cited for CSRF. The correct sources are **Assumption
A-4** and **OI-6**, which explicitly leave the cookie question open
(`SRS-revision2.md` lines 172–173). This is a *narrower* claim than the superseded one
and it is the accurate one.

Header table (operator-supplied from five redacted request captures):

| Header | Action | Value | Source |
|---|---|---|---|
| `content-type` | send | `application/json;charset=UTF-8` | exact value observed in all five captures |
| `accept` | send | `application/json, text/plain, */*` | observed |
| `operations` | send | comma-joined operation names in batch order | observed — **this is the correlation contract** |
| `x-csrf-token` | send | caller-supplied token | Assumption A-4, confirmed by captures |
| `x-requested-with` | send | `XMLHttpRequest` | observed in all five |
| `x-source` | send | `storefront` | observed in all five |
| `origin`, `referer` | keep | same-origin | referer observed in all five |
| `accept-language`, `cache-control`, `pragma`, `priority`, `sec-ch-ua`, `sec-ch-ua-mobile`, `sec-ch-ua-platform`, `sec-fetch-dest`, `sec-fetch-mode`, `sec-fetch-site`, `sentry-trace` | **exclude** | — | client-negotiation, browser-fingerprint, or trace-ID; none is a protocol requirement |

Case-sensitivity note: `X-CSRF-Token` is emitted lowercase on the wire
(`x-csrf-token`) and HTTP header names are case-insensitive, so any header lookup in
the adapter must be case-insensitive. `GRAPHQL_CSRF_HEADER_NAME` stays
`"X-CSRF-Token"` as the canonical emission name. Recorded as a §11 prohibition.

**Cookie construction is a scoped omission, NOT a pending Chunk 5 task.**
`Cookie: _csrf=<token>` is explicitly **not** in Chunk 5's scope, and `OI-6` remains
open. All five captures report `credentials: "include"` with no explicit `Cookie`
header — that is the browser attaching cookies from its jar, and it does not establish
whether `_csrf` is the only required cookie, whether another storefront session cookie
is required, or whether the cookie value must equal `X-CSRF-Token` byte-for-byte.
Assumption A-4 itself says the shape is descriptive, not a guarantee, until OI-6
resolves. Chunk 5 sends the `X-CSRF-Token` header and **must not** attempt Cookie
construction. See §11.

**Q2 — RESOLVED (confirmed, no changes): caller-supplied transport callable; no shared
`transport.py`; `collector.py` stays a logicless facade.**
Its authoritative statement, its reliance clause, and the way it is reopened now live
in **§12.4 Q2**, because it is a plan-level design decision and not an SRS-derived
requirement. The design content is recorded here for continuity: `pyproject.toml`
declares `dependencies = []` and `requires-python = ">=3.11"`, and the
adapter is specified over a caller-supplied transport
(`GraphQLTransport = Callable[[GraphQLBatchRequest, Mapping[str, str]], GraphQLBatchResponse]`),
so mocked-HTTP tests need no dependency and the wire library stays a Chunk 3 / Chunk 10
decision. No shared `transport.py`: it would be a new file outside both Chunk 3's and
Chunk 5's §6 lists. `collector.py` re-exports and gains no retry, header, or
correlation logic. **Q4's Chunk 3 wiring cannot be done**: no frozen chunk-03 interface
file exists in `Documents/interfaces/` (only `chunk-00.md`, `chunk-01.md`,
`chunk-02.md`), so Chunk 5 stays independent — which is also what §6 requires. No
import or shared abstraction is invented. Nothing here is derived from SRS text.

**Q3 — RESOLVED: `operationName` is the correlation key.**
`extract_operation_correlation_key` reads the response item's `operationName` member.
The operator's five redacted captures make this load-bearing: batch 1 contains
`ServerTime` twice, batch 4 contains `ServerTime` seven times, and batch 5 contains
`AddToCartButton` eight times, so index-based association would be silently wrong.
`ProductPrice`, `ProductReview`, `Recommendations`, `AddToCartButton`, `CurrentUser`,
`ShoppingCartQuery`, and `Publisher` are never batched with duplicates of themselves
except `AddToCartButton` (batch 5, 8×), so the duplicate-handling path must be
exercised on more than `ServerTime`. Fixture split: **contract leg** = hand-derived,
covering identity mismatch and non-integral/non-finite page views and freezing now;
**golden leg** = capture-derived and redacted, deferred as a scoping decision
(§12.3 O-2). See §5.5 and §9.

**Q3-note — the `EXCLUDED`/`CANDIDATE` members are NOT added to the enum. RESOLVED,
no extension, no coordination task.** The frozen Chunk 0 contract defines
`GraphQLOperationCorrelationMode` with exactly two members —
`Documents/interfaces/chunk-00.md` line 66 (`# explicit_key | validated_position`) and
`src/niche_scout/models.py` lines 132–134 (`EXPLICIT_KEY = "explicit_key"`,
`VALIDATED_POSITION = "validated_position"`). The operator's Q3 ruling directs that
`EXCLUDED` and `CANDIDATE` exist in the correlation vocabulary; adding them to the
frozen enum would require editing `models.py` and invalidating the frozen Chunk 0
interface, which **no ruling authorizes**. The plan therefore holds the vocabulary
**locally in `collector_graphql.py`** (§5.5, `GraphQLCorrelationDisposition`) as the
*required* design, and the enum-extension question is **closed, not flagged**: see
§12.1 O-3. Chunk 5 SHALL NOT edit `models.py`, and nothing is blocked, because
LREQ-GQL-030 closes the **persisted** domain to `explicit_key` or `validated_position`
only, so a third value can never be persisted and cannot live on the persisted enum.

**O-3 — CLOSED by operator ruling: no enum extension, no coordination task, and
`GraphQLCorrelationDisposition` stands as the required local vocabulary.**
Originally opened as a divergence between the operator's Q3 vocabulary ruling and the
frozen two-member `GraphQLOperationCorrelationMode`. Closed on this reasoning: the SRS
itself closes the persisted domain, so the local vocabulary is not a workaround for a
blocked extension but the design the SRS forces. `Documents/SRS-lean.md` lines 310–312:
"The persisted correlation mode SHALL be either `explicit_key` or `validated_position`.
If neither mode is validated, both operations SHALL be marked malformed and their
fields SHALL remain unavailable." Corroborating: `LREQ-ID-020` (line 371) requires the
preflight to verify "the operation-correlation mode is valid", and lines 413–414
require `identity_preflight_summary_json` to carry "the selected
`graphql_operation_correlation_mode`" — a persisted summary value with exactly two
possible values, both frozen enum members. Consequences: (a) the verbatim-copy line
`EXCLUDED = "excluded"; CANDIDATE = "candidate"` that appeared inside §4.1's frozen
`models.py` copy block is **deleted**, because a block headed "Chunk 5 SHALL NOT
redefine any of these names" may not list members the frozen enum does not have;
(b) `EXCLUDED`/`CANDIDATE` appear as declarations **only** in §5.5's local
`GraphQLCorrelationDisposition`; (c) no coordination task to extend `models.py` or
`interfaces/chunk-00.md` is opened, proposed, or pending; (d) `models.py` and every
interface file stay untouched by Chunk 5.

**Q4 — RESOLVED (confirmed): Chunk 5 keeps an independent `GraphQLRetryPolicy` and does
not claim `LREQ-EXT-100`.**
The dependency map lists "rate limiting and retry policy consistent with the collector"
as a Chunk 5 *Implement* bullet (line 654), but the only retry wording in
`SRS-lean.md` is `LREQ-EXT-100`, whose matrix row (dependency map line 59) names
**Chunk 3** as primary owner and completion chunk. Chunk 5 does **not** claim
`LREQ-EXT-100`. The dependency map's Chunk 5 `Tests:` list names `test_collector.py`
and `test_identity.py`, and `test_retry_backoff_on_transient_and_no_indefinite_retry`
keeps `LREQ-GQL-040`.

The constants are **module constants, not config keys**, renamed to `DEFAULT_*` and
pinned:

```text
DEFAULT_MAX_ATTEMPTS = 4
DEFAULT_BACKOFF_BASE_SECONDS = 0.5
DEFAULT_BACKOFF_MULTIPLIER = 2.0
DEFAULT_BACKOFF_MAX_SECONDS = 8.0
DEFAULT_MIN_REQUEST_INTERVAL_SECONDS = 0.5
```

Rationale for keeping retry internal: batches 4 and 5 of the operator's captures omit
`sentry-trace` entirely while batches 1–3 include it. A retry layer that keyed
idempotency or attempt tracking off `sentry-trace` would break on exactly those two
batches, so the retry decision stays internal to `GraphQLRetryPolicy` and
`sentry-trace` is an excluded header (§11, Q1(b)).

**Q5 — RESOLVED: the three-way ownership split, and O-1 is CLOSED by operator ruling.**

- **Chunk 6A initializes** the run-level `page_view_semantics_status`. Supporting
  evidence in the retired document: `SRS-revision2.md` line 196, step 2 of the run data
  flow — "initializes `page_view_semantics_status` from the latest operator validation
  (`unvalidated` unless validated or contradicted)". This is a Chunk 6A detail, carried
  forward for Chunk 6A's plan; it changes nothing about Chunk 5.
- **Chunk 7B detects `contradicted`.** Grounded in the ownership matrix,
  `Documents/requirements-dependency-map.md` line 91:
  `| LREQ-MET-090 | Chunk 7B | Chunk 5, Chunk 7A | Chunk 7B | LREQ-TST-050 |`
  (column layout is LREQ | Primary implementation chunk | Supporting chunks |
  Completion chunk | Required tests). `LREQ-MET-090` is the `models.py` quality-constants
  requirement (SRS-lean.md line 817: `QUALITY_MIN_RATING_COUNT = 5`,
  `QUALITY_MIN_ELIGIBLE_ASSETS = 5`); the dependency map's Chunk 7B edge-case column
  (line 219) is where the phrase "contradicted page-view semantics" appears. Also
  cited: `LREQ-MET-040` (dependency map line 86: primary Chunk 7B, supporting Chunk 5,
  completion Chunk 7B).
- **Chunk 8 applies** contradicted page-view handling: dependency map line 101
  `| LREQ-SCR-050 | Chunk 8 | Chunk 5, Chunk 7B | Chunk 8 | LREQ-TST-060 |`, and the
  Chunk 8 "Implement:" bullet list (line 858) literally contains
  "- contradicted page-view handling".
- **Chunk 5 sets nothing.** Consistent with the frozen enum
  `models.PageViewSemanticsStatus` = `UNVALIDATED` / `VALIDATED_CUMULATIVE` /
  `CONTRADICTED` (`src/niche_scout/models.py` lines 126–129). Chunk 5 must not add an
  enum member and must not set a value.
- The §6.5 language (SRS-lean.md lines 639–642) is cited for its boundary, not as an
  assignment: an individual malformed or failed page-view operation is an asset-level
  `page_views_status = "error"` and "SHALL not by itself contradict the endpoint".

**Fabrication deleted and reclassified.** An earlier version of this plan asserted a
contradicted-detection obligation for Chunk 5 and supported it with a sentence
attributed to retired-SRS Assumption A-3 — that "a later observation showing a lower
value for the same asset SHALL be treated as a data-quality signal and set the
semantic status to `contradicted`". The operator verified that sentence appears in
neither `Documents/SRS-lean.md` nor
`Documents/retired-documents/SRS-revision2.md`. It was constructed and is **deleted**,
not softened, along with every citation resting on it. What A-3 actually says
(`SRS-revision2.md` line 171, revised in v2.2.0) is that `productPageViews` is
*assumed* to be "a cumulative, monotonically-non-decreasing lifetime total", that
"This assumption is not resolved merely by field availability", and that until
validated "the derived value SHALL be named and presented only as an
**age-normalized page-view index**". That is an assumption about the field's
*meaning*, not a detection rule. The plan's ownership conclusion survives on the
independent grounds above.

**In its place:** the concrete contradiction-detection rule is **deliberately
unspecified in Chunk 5 and is Chunk 7B's plan-time decision to specify** — a *scoped
omission* (deliberately out of scope), not a *pending resolution*. Chunk 5 has **no**
contradicted-detection obligation at all: detection would require cross-run state and
Chunk 5 is a single-run adapter. Chunk 7B inherits this as a real requirement to
define, sourced from `LREQ-MET-090`'s ownership plus the frozen enum, not from A-3.

**O-1 CLOSED by operator ruling** (not deferred). The earlier deferral of the
detection rule is closed, with this reason recorded: `LREQ-MET-040`'s eligibility list
(finite non-negative value, valid UTC date no later than cutoff,
`age_days_exact >= MIN_AGE_DAYS_FOR_RATE`, matched published identity) is jointly
necessary and sufficient for index usability and contains **no** cross-run
monotonicity condition — a non-monotonic lifetime total still satisfies all four, so
monotonicity is not a usability criterion anywhere in the normative text. There is
nothing left to discover. Consequence: Chunk 5's exclusion clause states the scoped
omission, not a wait (§2, §5.8, §11).

**Q6 — RESOLVED (confirmed): attach neither `LREQ-TST-040` nor `LREQ-TST-080`.**
The ownership matrix names Chunk 13 as the primary owner of both, with Chunk 5 among
the supporting chunks (dependency map lines 130–131). `LREQ-TST-040` is deferred to
**Chunk 13 as a marker-edit-only change**. §9's `tests/traceability.json` JSON entries
stay unchanged. `test_retry_backoff_on_transient_and_no_indefinite_retry` keeps
`LREQ-GQL-040`.

**Q7 — RESOLVED: accept `1.0` as `1`; reject `1.5` as `INVALID_PAGE_VIEWS`; no
rounding; check `bool` before `int`/`float.is_integer()`.**
The rule is unchanged; the citation is replaced. `bool` must be checked **before** the
`int` / `float.is_integer()` path, since `bool` is a subclass of `int` and would
otherwise pass silently. Sources:

1. `LREQ-MET-040` (SRS-lean.md line 711): "It is usable only for a finite non-negative
   page-view value, a valid UTC date no later than cutoff,
   `age_days_exact >= MIN_AGE_DAYS_FOR_RATE`, and a matched, published identity. An
   explicit valid page-view value of zero is usable and yields an index of zero." —
   this establishes the eligible numeric domain, which `1.5` violates and `1.0` does
   not.
2. The parent SRS's field-type domain for `productPageViews`, sourced as an **endpoint
   detail** under the §1.5 authorization from Q1(a).

Why this distinction matters: the zero-is-usable sentence shows the SRS treats the
page-view value as a count-like quantity, not a continuous rate — that is what
licenses integer-semantics interpretation, and it is a lean-SRS citation rather than a
retired-document one. The plan no longer cites SRS-lean §2.2 row 117, which names only
the formula `product_page_views * 7 / age_days_exact` and calls the field
"undocumented" and states no integrality convention.

### 12.2 Corrections to previously accepted answers (recorded)

1. **A-3 was the plan's own text, not a requirement.** The ownership conclusion
   survives on independent grounds; the detection rule is deleted and reclassified as a
   scoped omission owned by Chunk 7B. See Q5 above.
2. **`X-CSRF-Token` was sourced to §4.4.** The correct sources are Assumption A-4 and
   OI-6, and OI-6 stays open — so Cookie handling is out of scope. This is a
   *narrower* claim than before and it is the accurate one. See Q1(b).
3. **Q7's citation moved off SRS-lean §2.2 row 117 to `LREQ-MET-040`.** See Q7.
4. **The Q3-note's "flagged, not applied" enum-extension item became O-3 and is now
   closed**, with no coordination task. The reading that Q3's ruling authorized adding
   `EXCLUDED`/`CANDIDATE` to the frozen enum, or that a coordination task should be
   opened, would make the plan assert a role-shift it cannot source. See §12.1 O-3.
5. **The capture files are no longer committed artifacts.** The belief that the
   operator's five chat-pasted captures would be committed under
   `tests/fixtures/captures/` as Q3's golden leg was wrong for two reasons — fabricated
   provenance and circularity — and the leg is now closed as a scoping decision
   (§12.3 O-2, §9, §6). This corrects the *plan's* claim, not the operator's
   ruling: the ruling endorsed refusing the "leave it flagged" remedy.

6. **The §9 test-plan baseline counts were factually wrong.** They were produced by
   grep-substring counting rather than by reading the files and were accepted on trust
   across two review passes. Verified by direct count: `tests/test_collector.py` is
   **2532 lines** with **51 `@pytest.mark.lreq` markers over 51 distinct nodes** (not
   1313 / 26 / 21; corrected 2026-09-18: this previously read "1310 lines ... 25
   `@pytest.mark.lreq` markers over 13 distinct nodes", the pre-Chunk-5 file's
   figures — see item 9), and `tests/test_identity.py` holds **26 marked test nodes carrying
   26 `@pytest.mark.lreq` marker occurrences over 8 distinct LREQ IDs, 0 unmarked**
   (not 26 / 21). Both corrected nodes are analytical: the marker counts are the
   analytical present-node counts, and the earlier "24 + 1 suite node" total (24
   `LREQ-*` + 1 `LREQ-TST-030`) described the pre-Chunk-5 file and excluded the
   `LREQ-GQL-060` / `LREQ-GQL-070` nodes Chunk 5 itself doesn't add but the file already
   contains. The corrected figures are the counts that traverses the file today.
   `tests/traceability.json` carries **51** entries for `tests/test_collector.py`
   and **26** for `tests/test_identity.py` (corrected 2026-09-18: this previously
   read "carries **25** entries for each file, matching marker for marker" — see
   item 9), each matching its file's markers marker for marker. The "26" arose because a raw substring search for `@pytest.mark.lreq` also
   matches line 3's module docstring prose in each file; "21" corresponded to nothing.
   The two non-analytical `tests/test_collector.py` tests (lines 303 and 335, under the
   "Non-analytical tests (no marker, no traceability entry)" banner at line 299) are
   unmarked, as the plan already states. Every count statement in §2, §6, §7, and §9
   was corrected to these figures. **This is an operator-approved corrective amendment
   to the frozen plan**, authorized as a counts-only exception to the no-edit rule for
   a `Status: FROZEN` plan; no non-count text was changed and `Status` remains
   `FROZEN`. (Amended 2026-09-18: `Status` is now `DRAFT`, for the retroactive-authorship
   reason in §12.6 item 1 — **not** because of anything in this item. This item's
   counts-only scope statement and its "no non-count text was changed" claim describe
   *that* amendment and stand; the `Status` value it names is simply no longer the
   file's current value.)

7. **The count correction of item 6 rewrote `tests/test_identity.py`'s figures without
   re-deriving them, and carried a fabricated decomposition with it, so the first
   correction introduced its own fabricated observation.** Amendment
   2026-09-17 (this item). The defects were found by an independent audit of the
   artifact rather than of the plan. Item 6 left `tests/test_identity.py` asserting
   **26** `@pytest.mark.lreq` marker occurrences and a **"17 single-marker and 3
   dual-marker"** `LREQ-*` decomposition; both are false. Measured: a naive substring
   count of `@pytest.mark.lreq` in that file is 26, but the 26th match is line 3, the
   module docstring, which contains the marker text as prose rather than as a decorator.
   The decorator count is 25, so the difference was not a second marker on an existing
   node — and the need for a story to explain the surplus off-by-one was met by
   inventing one: the plan asserted that
   `test_requested_identity_compatibility_comparison` (def at line 751) carries markers
   at **749 and 750**, when line 749 is the second of two consecutive blank lines and
   line 750 holds the node's only marker, `LREQ-ID-020`. Corrected figures:
   **25 marked nodes, 25 marker occurrences, 8 distinct LREQ IDs, 0 unmarked**, composed
   of **24 `LREQ-*` nodes plus 1 `LREQ-TST-030` suite node**, markers-per-node
   distribution `{1: 25}`. The `tests/test_contracts.py` line correction carried by the
   same item is unaffected and stands. All figures below were counted in the artifacts,
   never derived from this plan:
   **(Superseded 2026-09-18 on the `tests/test_identity.py` figures only: the counts
   immediately above and in (a)/(b) below were correct for the pre-Chunk-5 file and are
   now 26 nodes / 26 markers / `{1: 26}` / 26 matrix entries, re-counted from the
   artifact in item 9. This item's *method* findings — the docstring-prose off-by-one,
   the invented two-marker attribution, the bijection argument — are unaffected and
   stand. The `tests/test_contracts.py` line-881 correction in (c)/(d) is unaffected
   and stands.)**
   - **(a) §6 line 1168, §7 line 1253, §9 lines 1363–1376, §9 line 1542, §12.2 item 6 —
     the `tests/test_identity.py` identity-file baseline.** Artifact queries, all
     re-run for this correction: anchored `Grep` for `^@pytest\.mark\.lreq\("(LREQ-[A-Z0-9-]+)"\)`
     returns **25 rows**; the same pattern anchored on `^def test_` returns **25 rows**,
     and each decorator sits at exactly `def_line − 1` (a bijection, so no node carries
     two markers); a Python `ast` walk replicating
     `tools/validate_traceability.py` (corrected 2026-09-18: the citation read
     the bare `tools/validate_traceability.py`; the real location is
     `src/niche_scout/tools/validate_traceability.py` — bare form retained as
     the quoted prior wording, not as a live path)`'s `test_markers` reports **25 marked nodes,
     markers-per-node `{1: 25}`, 25 marker occurrences, 8 distinct LREQ IDs, 0 unmarked,
     no multi-marker node**; `python -m pytest tests/test_identity.py --collect-only -q
     -m lreq` reports **25** nodes and the same 25 node IDs the `ast` walk found. An
     unanchored substring count returns **26** rows, the extra being line 3's docstring
     prose. Units named: node IDs 25, marker occurrences 25, LREQ IDs 8.
   - **(b) §9 lines 1363–1366 and §9 lines 1542–1543 — the decomposition.** Both
     asserted `20 LREQ-*` nodes as `17 single-marker + 3 dual-marker`. Re-derived from
     the same anchored enumeration, which buckets *nodes per ID* rather than markers per
     node: `LREQ-EXT-060` 6 nodes, `LREQ-EXT-070` 6, `LREQ-GQL-060` 5, `LREQ-GQL-070` 4
     (these four IDs account for 21 of the 25 nodes), then `LREQ-GQL-010`,
     `LREQ-ID-020`, `LREQ-SMP-010`, `LREQ-TST-030` 1 node each. That is
     `6 + 6 + 5 + 4 + 1 + 1 + 1 + 1 = 25`, i.e. **24 `LREQ-*` nodes plus 1
     `LREQ-TST-030` suite node = 25 nodes = 25 markers**, since every node carries
     exactly one. `tests/traceability.json` agrees: 25 entries for this file, every
     entry's array equal to its node's marker set, and no multi-ID array among them.
     The old `20` and the "3 dual-marker" describing it were wrong in both the total
     and the mechanism.
   - **(c) §6 line 1184 and §11 line 1731 — the `tests/test_contracts.py` citation.**
     Both cited `line 938` for
     `tests/test_contracts.py::test_repository_protocol_and_schema_specification`.
     Counted in the artifact: line 938 is the string literal
     `"recent_supply_usable_count",` inside the four-element `for alias in (...)`
     tuple at lines 935–940; the node's marker
     `@pytest.mark.lreq("LREQ-ARCH-010")` is at line **881**, decorating the `def` at
     line 882. Both citations now read 881.
   - **(d) §6 lines 1183–1185 and §11 lines 1729–1731 — the "known failing
     assertion".** The plan asserted the node was a known failing assertion and hence
     Chunk 0 document-consistency debt that Chunk 5 must not fix. Measured by running
     it: `python -m pytest
     "tests/test_contracts.py::test_repository_protocol_and_schema_specification" -q`
     → `1 passed in 0.16s`. The node passes, so there is no debt at that location and
     no prohibition-on-repair is needed; the surrounding claim was corrected to say
     the node passes and that the ordinary reason `tests/test_contracts.py` is not
     touched is that it is outside Chunk 5's file scope. The §6 "Deliberately **not**
     touched" list is otherwise unchanged, and no scope is widened.
    §7's task-box count for `tests/test_identity.py` (line 1253) was found by an
    occurrence scan for the same wrong claim and said "all 13 existing distinct nodes
    and all 25 existing markers" — the 13 belonged to `tests/test_collector.py`; it
    now states 25 nodes, 24 `LREQ-*` plus the suite node, and 25 markers.
    **Method failure named:** this item's own first pass measured
    `tests/test_identity.py` by counting *raw substring matches* of the marker text —
    a unit that includes the module docstring's prose mention — and reported the
    result as a *marker occurrence* count; the resulting off-by-one was then closed by
    inverting it into a second marker attribution for one node instead of re-reading
    the node; `tests/test_contracts.py` was measured earlier by reading a *line number*
    out of the file and expecting the node's marker there; and one file's node count
    (*13*) was read into another file's sentence. None of these is a count of the
    property being asserted. The fix is the counting discipline now stated in
    `.cursor/rules/project-rules.md` §"Plan review and audit": every countable claim is
    verified by querying the artifact and is reported with its unit named. This
    amendment is content-only on the verified `tests/test_contracts.py` defects and, per
    item 8, on the `tests/test_identity.py` figures corrected there; `Status` remains
    `FROZEN` and the `Status:` line is untouched. (Amended 2026-09-18: `Status` is now
    `DRAFT` per §12.6 item 1. This item's claim was that *it* changed no `Status` text,
    which is true of this item and remains so; the value is superseded by the later
    amendment, not by this one.)

8. **The plan's own first count-correction introduced a fabricated observation, and the
   record of that is this entry.** Amendment 2026-09-17 (this item), folded into item 7's
   figures rather than left standing behind them. Item 7's first pass kept the wrong
   `26` marker-occurrence count for `tests/test_identity.py` and explained it with a
   node carrying two markers at lines 749 and 750; line 749 is blank, so the explanation
   was an invented observation whose only support was the residual it was meant to
   account for — a *self-validating* error, since the arithmetic (`25 nodes + 1 extra
   marker`) closed correctly on the wrong premise and survived two review passes for
   that reason. It was caught by **anchored enumeration re-derivation**: re-running
   `^@pytest\.mark\.lreq\("(LREQ-[A-Z0-9-]+)"\)` and `^def test_` over
   `tests/test_identity.py` returned 25 rows each with every decorator at exactly
   `def_line − 1` (a bijection, so a two-marker node is impossible in that file), and
   reading `tests/test_identity.py:745-755` showed line 749 blank and line 750 the
   node's single marker. The governing principle is now recorded for the next auditor:
   **the artifact is authoritative over any plan text and over any prior report about
   the artifact** — a count is accepted only when the query that produces it is
   re-runnable and its unit is named, and a discrepancy is resolved by reading the file,
   never by constructing the detail that would make the existing number close.
   Consequence for the freeze: this is a counts-only correction like items 6 and 7, no
   scope, contract, or gate text changed, and `Status` remains `FROZEN`. (Amended
   2026-09-18: `Status` is now `DRAFT` per §12.6 item 1; this item's own point — that
   it was a counts-only correction — is unaffected.)

Numbered deliberately after the three corrections the operator's round supplied
(A-3, §4.4, Q7) so the cross-references already recorded in §12.1 and §12.2 keep
pointing at the same items. Item 7 is appended after item 6 for the same reason: it
corrects item 6 rather than renumbering it, so the existing references to item 6
still resolve. Item 8 follows item 7 for the same reason: it records why item 7's own
first pass was wrong and carries no independent correction of its own, so renumbering
either would break the cross-references above. Item 9 follows item 8 for the same
reason: it is a counts-only correction of figures left stale by the Chunk 5
implementation that items 6–8's own corrections already anticipated in kind.

9. **The `tests/test_collector.py` and `tests/test_identity.py` baselines this plan
   carries were the pre-Chunk-5 figures, and thirteen expression sites still asserted
   them after Chunk 5 landed.** Amendment 2026-09-18 (this item). Correction-only:
   no scope, contract, gate, or `Status:` text is changed and `Status` remains
   `FROZEN`. (Amended 2026-09-18: `Status` is now `DRAFT` per §12.6 item 1; this
   item's claim describes itself only.) Item 6 already stated the principle — the corrected figures are "the
   counts that traverses the file today" — but the figures written into the plan were
   Chunk 3's frozen-file counts, and Chunk 5's own append of the GraphQL protocol
   nodes moved both files. Every number below was **counted in the artifacts by
   querying them**, never derived from this plan and never carried over from an
   earlier item's arithmetic.
   - **`tests/test_collector.py` — the file.** Counted by reading the file: 2532
     bytes-`\n` occurrences and 2532 `str.splitlines()` entries (the file ends with a
     newline, so both agree). **Unit: file lines, 2532.** The plan's `1310` was the
    pre-Chunk-5 count and appeared at four sites (§1 line 98, §6 line 1168, §9 line
    1391, §12.2 item 6), all four now dated-corrected. (corrected 2026-09-18: this
    sentence previously listed the sites as "§1 line 98, §6 line 1167, §9 line 1384,
    §12.2 item 6" — this item's own pre-insertion line numbers; the numbers above
    were read from the file after this item was written. The count of four sites is
    unchanged.)
   - **`tests/test_collector.py` — markers and nodes.** Query: anchored `Grep` for
     `^@pytest\.mark\.lreq\("LREQ-[A-Z0-9-]+"\)` returns **51 rows** (unit: full
     decorator lines). Independently, a Python `ast` walk replicating
     `src/niche_scout/tools/validate_traceability.py`'s `test_markers` reports **51
     marked `def` nodes**, markers-per-node histogram `{1: 51}` (unit: distinct node
     objects). **All 51 decorators are `LREQ-GQL-*`-free Chunk 3 nodes plus Chunk 5's
     appended GraphQL nodes; the file spans 19 distinct LREQ IDs.** `tests/traceability.json`
     carries **51** entries for this file, one per node, no multi-ID array (unit:
     top-level JSON keys). The plan's `25 markers over 13 distinct nodes` appeared at
     §6 line 1168, §9 lines 1394–1395, §9 lines 1407–1408, §9 lines 1410–1411, and
     §12.2 item 6, all now dated-corrected; its `25 entries` claim in item 6 is
     corrected to 51. (corrected 2026-09-18: this sentence previously listed the
     sites as "§6 line 1167, §9 lines 1386 and 1393, §9 line 1395" — this item's own
     pre-insertion line numbers; the numbers above were read from the file after this
     item was written.)
   - **`tests/test_identity.py` — markers and nodes.** Same query shape over that
     file: anchored decorator `Grep` returns **26 rows** (unit: full decorator lines);
     the `ast` walk reports **26 marked `def` nodes**, histogram `{1: 26}`, **8 distinct
     LREQ IDs, 0 unmarked test nodes** (unit: distinct node objects). `tests/traceability.json`
     carries **26** entries for this file (unit: top-level JSON keys). An unanchored
     substring scan for `@pytest.mark.lreq` returns **27** rows because line 3 is the
     module docstring's prose mention — the same off-by-one mechanism item 7 named.
     Correction: **items 6, 7, and 8's `25`/`0 unmarked`/`24 LREQ-* + 1 LREQ-TST-030`
     figures describe the pre-Chunk-5 file and are superseded by 26/26/8**, at the
     sites listed in that bullet below. The `tests/test_identity.py` sites were
     §6 line 1169, §7 line 1254, §9 lines 1365–1368, and §9 lines 1561–1565 — four
    sites, not three. (corrected 2026-09-18: this sentence previously read "The
    three `tests/test_identity.py` sites were §6 line 1168, §7 line 1252, §9 line
    1363, §9 line 1546", which both miscounted four listed sites as three and
    carried this item's pre-insertion line numbers; the numbers above were read
    from the file after this item was written.)
   - **`tests/test_collector.py` protection statements.** §9's byte-identity bullet
     and §11's non-widening bullet both stated "25 markers, 13 distinct node IDs";
     both now read 51/51. (corrected 2026-09-18, on re-reading the sites: those two
     bullets in fact carried **no** numeric count — §9's byte-identity bullet and
     §11's protection block said only "untouched and byte-identical", and the
     `25 markers over 13 distinct nodes` figure this item corrected lived in §6 line
     1168, §9 lines 1394–1395, §9 lines 1407–1408, §9 lines 1410–1411, and §12.2
     item 6, all of which are corrected.
     This bullet's claim about *where* the figures sat was wrong; the corrected
     figures it states are unchanged. No protection text was removed.) The
     protection's *content* is unchanged: Chunk 3's nodes,
     fixtures, imports, and matrix entries are still untouched and byte-identical.
   - **`tests/traceability.json` as a whole.** `python -m
     niche_scout.tools.validate_traceability` was **run** (read-only validator, exit
     **0**) and printed: `Note: 2 test(s) carry no lreq marker:
     tests/test_collector.py::test_module_imports_without_side_effects,
     tests/test_collector.py::test_request_body_builder_signature_is_stable` then
     `Traceability valid: 7 Chunk 0 requirements mapped, 144 matrix nodes, 89 defined
     LREQ IDs`. **Unit: matrix nodes 144** (top-level entries), and the 2 unmarked
     nodes are the two non-analytical tests this plan already names at lines 299–335.
   - **Method statement for this item.** Every count above came from an actual read or
     query of the artifact, named with its unit; none was re-derived from this plan's
     prose. The prior pass's proposed replacement figures were not adopted on trust —
     they were re-measured, and they proved correct for markers/nodes while its
     `13`-node figure and the `53` figure this dispatch's brief carried did **not**
     reproduce **as a markers-over-nodes figure** (51 anchored decorator lines, 51
     marked `def` nodes, 51 matrix entries) — but the `53` **is** a real quantity of
     this file under a different unit, and the parenthetical as first written was
     wrong about it (corrected 2026-09-18: this sentence previously closed
     "…did **not** reproduce (51 unanchored substring rows, 51 anchored, 51 nodes)",
     attributing `53` to no unit; re-counted, the naive substring count of
     `@pytest.mark.lreq` over this file is **53**, not 51, and `53` is also the count
     of `def test_*` functions in the file, both distinct from the 51 marked nodes.
     The `13`-node figure remains non-reproducing: no unit of this file yields 13.
     Units and queries: naive substring `.count("@pytest.mark.lreq")` = 53 (unit:
     substring occurrences), anchored `^@pytest\.mark\.lreq\("LREQ-[A-Z0-9-]+"\)$`
     = 51 (unit: decorator lines), `ast` walk = 51 marked nodes (unit: node objects),
     `def test_*` function count = 53 (unit: function definitions), of which 2 carry
     no marker; the 2 unmarked are the non-analytical tests already named above. See
     §12.2 item 9's method statement, which this correction does not otherwise
     disturb.)
   - **Unchanged by this item:** the two non-analytical `tests/test_collector.py`
     tests remain unmarked and unentried; ¶6's account of the "26"/"21" provenance
     stands; the `tests/test_contracts.py` line-881 correction of item 7 stands; and
     no gate bullet's text is touched.
   - **A reported dangling chunk-13 citation does not reproduce in this file.** A
    dispatch brief asserted that this plan cites a chunk-13 plan file that does not
    exist. Verified by two differently-shaped whole-file scans, both re-run against
    the file as it stands now: a Python line scan for the regex `chunk-13` finds it
    **only inside this item's own correction text and the cross-reference below**
    (i.e. every `chunk-13` match is a *mention of the chunk*, not a citation of a
    `chunk-13-…md` filename), and a second scan for the regex `chunk-\d\d-` returns
    matches **all of them** naming
    `chunk-03-coveo-discovery-adapter-and-streamed-raw-persistence.md` or this item's
    own cross-reference to it — no chunk-13 *filename* anywhere. (corrected
    2026-09-18: this sentence previously read "a Python line scan for the regex
    `chunk-13` over all 2396 lines returns **0 rows**, and a second scan for the
    regex `chunk-\d\d-` returns **3 rows** … at lines 461, 1396, and 1809" and named
    the file as `chunk-03-coveo-discovery-adapter-and-streamed-raw-persistence.md`.
    Those were the figures this item measured *before its own text was inserted*, and
    they are not restatable: inserting this item changed the file's line count and
    added `chunk-13` and `chunk-\d\d-` matches of its own, so any line total or row
    count quoted here is invalidated by the act of quoting it. The line-number list
    is therefore dropped in favour of the content assertion, which is the claim that
    matters and which does not move.) **Unit: matching lines.** The
    absence claim is therefore *about this file*, and it holds: this plan does not
    cite a chunk-13 plan file. (The `chunk-13-…md` citation that does dangle lives in
    `Documents/plans/tooling-p0-2-traceability-blind-spot.md` lines 571 and 1046, which
    is outside this dispatch's authorized edit set — reported, not edited.) This plan's
     chunk-13 references are to the *chunk*, never to a filename: they name Chunk 13 as
     `LREQ-TST-040`/`LREQ-TST-080`/`LREQ-NFR-060`'s owner and defer the validator widening
     to it. **No fix applied — did not reproduce.**

### 12.3 Scoped omissions (deliberately out of scope; owned by no chunk or by another)

- **Cookie construction.** Chunk 5 sends `X-CSRF-Token` and must not construct,
  emit, or modify a `Cookie` header. `OI-6` (CSRF/session sufficiency) is unresolved
  *by design* and stays open; see §11 and Q1(b). Not a pending Chunk 5 task.
- **O-4 — CSRF/cookie sufficiency: RECLASSIFIED as a Chunk 5 scope ruling; it does
  NOT block the freeze.** This is the previously blocking framing of `OI-6`, and it is
  closed *as a Chunk 5 scope question* while `OI-6` itself **remains open**. The two
  halves are different questions and must not be collapsed:
  - **`OI-6` stays open as an external unknown of the retired parent SRS.**
    `SRS-revision2.md` line 173 states the obligation and its four sub-questions
    verbatim: "CSRF/session sufficiency SHALL be confirmed from a reproducible,
    redacted request capture. The validation SHALL determine whether `_csrf` is the only
    required cookie, whether another storefront session cookie is required, whether the
    cookie value must equal the `X-CSRF-Token` header byte-for-byte, and whether any
    User-Agent, encoding, or session-bootstrap requirement exists. Until resolved,
    REQ-GQL-030 and Assumption A-4 describe the observed request shape, not a guaranteed
    complete authentication contract." That obligation is a validation-program task of
    the retired parent SRS, which Chunk 5 does not inherit, and **no chunk owns it
    today**; it is recorded in `Documents/requirements-dependency-map.md` §7 so it
    survives into a later chunk's brief. Chunk 5 *records* it and neither resolves nor
    absorbs it.
  - **Closed as a Chunk 5 scope question.** The governing test is whether the plan can
    make the correct choice without more information. O-2 could not (it would have
    required inventing provenance) and was closed as a scoped omission above; O-4 can.
    The correct choice is already made and stays correct under **every** outcome of
    OI-6: Chunk 5 sends `X-CSRF-Token` and never constructs a `Cookie` header
    (§11, §5.3), so the adapter behavior is invariant across all four sub-questions,
    including the worst case that a session cookie beyond `_csrf` is required. No
    downstream chunk has to guess at anything, so the item carries no unresolved
    decision and does not block freeze.
  - The scope answer is **independently sufficient**: it rests on LREQ-SEC-010
    (the CSRF credential is supplied by the caller and required before a request),
    LREQ-GQL-010's two named operations, and the `X-CSRF-Token` header sourced from
    Assumption A-4 plus the five captures (§12.1 Q1(b)) — none of which depends on
    OI-6. This is the same CSRF/cookie-sufficiency question named in the Cookie bullet
    above and in §11; it is not a second, independent open item, and it is not
    duplicated here.
- **Contradiction detection.** The concrete rule for setting
  `PageViewSemanticsStatus.CONTRADICTED` is unspecified in Chunk 5 and is Chunk 7B's
  plan-time decision. Chunk 5 is a single-run adapter with no cross-run state; see §11
  and Q5.
- **O-2 — the capture-derived (golden) leg of §9's fixture set.** The golden leg is
  **deferred out of Chunk 5's frozen scope**. The operator's five request/response
  captures were supplied as chat transcript text, and **no capture file will be
  authored from it**: a fixture asserting that it is a redacted capture of live
  traffic, but hand-transcribed from a chat window, would put fabricated provenance
  into the test suite — the same defect class as the deleted §12.1 Q5 sentence. For
  this leg it would also be **circular**: batch 4's 7× `ServerTime` and batch 5's 8×
  `AddToCartButton` duplicate sequences *are* the substance of the test, so authoring
  the fixture from the plan's own reasoning and then citing it as independent proof of
  that reasoning is self-confirming. Nothing in Chunk 5 depends on it: the §10 gate
  bullets are satisfied by the hand-derived contract leg (§9), so no capture is a
  Chunk 5 blocker and none is pending from the operator.
  - **Clean reopening path** (a legitimate follow-up task, not a Chunk 5 deliverable):
    open DevTools on `assetstore.unity.com`, run the storefront flow, export the batch
    requests, then strip cookie, `sentry-trace`, `sec-ch-ua*`, `sec-fetch-*`,
    `accept-language`, `priority`, `pragma`, `cache-control`, and all account
    identifiers, and commit the redacted exports under `tests/fixtures/captures/`. A
    **reconstructed** capture — assembled from prose rather than exported — would stay
    circular for this leg specifically and does not satisfy the path.
  - The chat-pasted captures **did** serve as a verification aid this round and that
    use stands: they are the evidentiary basis for §12.1 Q1(b)'s header table and for
    §12.1 Q3's correlation-key reasoning. Only the claim that they are committable
    artifacts is withdrawn.

### 12.4 Assumptions (accepted as assumptions by the operator, not questions)

**A1 (was Q8) — the transport boundary is the caller's, so `http_status` in
`request_metadata_json` is the status of the last attempt, and a request that never
received a response records `null`.**
SRS-lean §6.5 requires "HTTP status" in `request_metadata_json` but does not say which
attempt's status is recorded when a retry sequence spans several statuses (e.g. `500`
then `200`). The plan records the **final** status in `http_status` and keeps the full
per-attempt status list in `retry.http_statuses`, which is a superset of the required
value.

**A2 (was Q9) — the `ProductDetail` property names inside the selection set are taken
from the parameter list of LREQ-GQL-020 read literally.**
LREQ-GQL-020 names `rating.average`, `rating.count`, `reviewCount`,
`firstPublishedDate`, `state`, `category`, `publisher`, and the identity aliases, and
adds "Fields not required by scoring MAY be omitted from the lean implementation"
(lines 294–298). §5.6 declares the alias member set as a named constant
(`PRODUCT_DETAIL_ALIAS_MEMBERS`) rather than an inline guess at what "product identity
aliases" enumerates, and requires a test that the emitted query names exactly the
constant's members. The plan fixes the *mechanism* (one named constant, one shape test)
and treats the *member list* as an assumption to be confirmed against a real capture
if a genuine export is ever committed under §12.3 O-2's reopening path, because the
identity aliases are exactly the fields the correlation read and LREQ-GQL-070's
comparison consume.

**A3 (was Q10) — `collector.py` gains a GraphQL-only explicit re-export edit applied
to line 4; the Coveo half is not claimed, and two coordination items are escalated to
a human.**
Verified state of `src/niche_scout/collector.py` (5 lines, read directly):
line 1 the module docstring `"""Collector facade for the Coveo and GraphQL
adapters."""`, line 2 blank, line 3 `from .collector_coveo import *  # noqa: F401,
F403`, line 4 `from .collector_graphql import *  # noqa: F401, F403`, line 5 end of
file. The plan replaces **line 4 only** with explicit-name re-exports drawn from
`collector_graphql.__all__`; **line 3 stays byte-identical**. The alternative — a
symmetric explicit Coveo re-export — would touch Chunk 3's integration surface without
Chunk 3's consent, so this plan does not propose it as Chunk 5's edit.

**Chunk 3's conditional edit never fired.** Chunk 3's frozen plan lists
`src/niche_scout/collector.py` as "Modified — deliberately minimal facade edit, flagged
by the project rule" at its line 414, with the condition stated as: "the edit adds the
`__all__` re-export path if the star-import does not propagate the intended surface"
(and its line 741 restates the limit: "Must not edit `collector.py` beyond the single
`__all__`/re-export line"). The file's line 3 is still the original wildcard import, so
on the evidence in the repository the conditional edit did not fire. That is a factual
observation about the current tree, not a claim about Chunk 3's intent or compliance.

**Never-unilateral rule.** Neither chunk edits the facade's other half without
coordination. Chunk 5 edits line 4 and nothing else; Chunk 3 owns line 3 and nothing
else; a change spanning both halves is a coordination task (§12.4 Q2's reopening
clause).

**Escalated as open coordination items for a human** (Chunk 5 does not resolve either):
1. **Whether line 3 also moves.** Chunk 3's frozen plan claims an edit at its line 414.
   Chunk 5 leaves line 3 alone; whether Chunk 3's conditional edit should now be
   applied, deferred, or withdrawn is Chunk 3's call and needs a human decision, because
   it changes a frozen chunk's own §6 row.
2. **The ordering/shadowing hazard that is invisible when either plan is read alone.**
   `collector.py` is one 5-line file edited by two chunks whose plans each describe only
   their own half. With two wildcard imports, a name defined by *both* adapters silently
   takes the last import's binding — and Chunk 3's conditional line-3 edit would change
   that binding order without Chunk 5 seeing it. Reading either plan alone, the hazard is
   undetectable; it needs a human ruling that the two edits are sequenced, not
   concurrent.

**Q2 (binding plan decision) — the transport boundary is a caller-supplied transport
callable per adapter; there is no shared `transport.py`; `collector.py` remains a
logicless facade.**
This is recorded as a **plan decision, not a derived requirement**: `SRS-lean.md` does
**not** specify the transport mechanism, so no SRS text, section, or LREQ is cited as
its basis, and it must not be read as carrying one.

- **The decision.** No new dependency is added and none is needed. Each adapter
  (`collector_graphql.py` now, `collector_coveo.py` in Chunk 3) accepts a
  caller-supplied transport callable
  (`GraphQLTransport = Callable[[GraphQLBatchRequest, Mapping[str, str]], GraphQLBatchResponse]`),
  and `collector.py` stays a facade that re-exports and gains **no** retry, header, or
  correlation logic. No shared `transport.py` is created: it would be a new file
  outside both Chunk 3's and Chunk 5's §6 file lists. The facade's own edit is
  Chunk 5's line-4-only change (§5.0, §12.4 A3), not a symmetric rewrite of both
  wildcard imports.
- **Who may rely on it.** **Chunks 6A, 6B, 7A, and 10 may rely on this as the frozen
  contract** — it is the shape of the adapter's public surface they build against, and
  it is what §5.11 publishes. It is not a provisional or flagged item.
- **Rationale.** The caller-supplied callable is what makes the adapter testable under
  the project rule that live network calls are forbidden, and under the dependency
  map's `LREQ-GQL-010` phrase "adapter is independently testable with a typed identity
  fixture" (`Documents/requirements-dependency-map.md` line 168), which states an
  expectation about testability that this decision is the means of meeting. The
  dependency-map phrase is a rationale for *choosing* this design; it is not the
  requirement the decision implements, because the transport mechanism itself is
  unspecified.
- **Reopening it requires a coordination task.** Any change to the transport boundary,
  to `collector.py`'s facade role, or the introduction of a shared transport module
  requires a separate coordination task; no chunk may reopen it unilaterally.
- §4.3 explains the design; this entry is the authoritative location of record, and the
  two do not diverge (§4.3).

### 12.5 Open items

**This section contains no blocking item for the plan's *content*, while carrying two
acknowledged change-blockers that are the operator's to clear.** It carries **five**
open items added 2026-09-18 by §12.6, each of which is a genuine ambiguity or a pending
human decision rather than a gap this plan-writer resolved by guessing. None of the five
is a Chunk 5 deliverable in this dispatch, and none is resolved here. **Two of the five
are marked below as blocking the change rather than the content** — item 1, whose
`Status` disposition is the operator's call, and item 4, which requires the suite to be
run and the failing set confirmed *before* any edit — and clearing them is likewise the
operator's.

**Open from §12.6 (recorded 2026-09-18). Each one blocks that item's *change*, not this
plan's content review:**

1. **The `Status` disposition is the operator's call, and this plan-writer may not
   make it.** `Status` now reads `DRAFT` because this plan was written after the code
   it describes was implemented (§12.6 item 1). Whether a retroactively authored plan
   is restored to `FROZEN` or held at `DRAFT` until §12.6 items 2 and 3 land is not
   decidable from the source documents. The `(★)` footnote on the header records both
   dispositions. **The operator decides.**
2. **The two-renderer split in `collector_graphql.py` is not this plan's to freeze**
   (§12.6 item 3(e)). The corrected module needs a non-redacting bounded renderer for
   operation names and correlation keys **and** `redact_value` for credential-capable
   inputs; the naming, the split, and whether `_metadata_text` survives at all are the
   implementer's and the reviewer's call. `_metadata_text`'s `[:max_chars]` bound is
   preserved either way — it is not the defect.
3. **Whether `"state"` is still *required* in the request selection set is
   unresolved.** §12.6 item 2 removes it from the *response's* structural
   required-member set (so absence in a response stops being an error), but
   LREQ-GQL-020's normative text (`Documents/SRS-lean.md:294-298`) names `state` among
   the members the `ProductDetail` operation **SHALL request**. Those are different
   questions about the same name, and the source documents do not connect them. The
   correction wave **MUST NOT** read the ruling into the request shape; if the
   implementation does not already request `state`, that is a separate finding to
   report rather than resolve.
4. **Whether any further test pins placeholder behavior is unverified** (§12.6 item
   5). This plan declares the correction branch — same-unit test fix, in-place
   `tests/traceability.json` edit, no rename, no deletion — but the operator's six
   reported failures were **not** re-queried for this plan, and it is not known
   whether `tests/test_collector.py:2427-2433`'s node is a bystander. The wave must
   run the suite and confirm the set before editing.
5. **The `§9` baselines must be re-derived before any entry is added** (§12.6 item 5).
   One collector test file of 2532 lines with 51 distinct marked nodes, one identity
   file with 26, a matrix of 144 nodes — all UNVERIFIED in this dispatch. Adding one
   `tests/traceability.json` entry against a stale baseline produces the
   `missing_nodes` / `orphan_nodes` / `marker_mismatch` variants §11 names.

**Prior item, unchanged (and now qualified by the five above):**
**Nothing here was a blocking item before 2026-09-18.** The single item this section
then recorded is not a Chunk 5 deliverable, not a Chunk 5 blocker, and
not awaiting a ruling on Chunk 5's scope.

**OI-6 — open by design; NOT a Chunk 5 blocker.** `OI-6` (CSRF/session sufficiency) is
an external unknown of the retired parent SRS, deferred by design and outside Chunk 5's
scope: Chunk 5 sends the `X-CSRF-Token` header and must not attempt `Cookie`
construction (§11, §12.3). It is recorded here so the plan's stated blocking set is
honest and complete, not as work Chunk 5 is waiting on. **"Until resolved, REQ-GQL-030
and Assumption A-4 describe the observed request shape, not a guaranteed complete
authentication contract"** (`SRS-revision2.md` line 173). It has **no owning chunk**
today; the obligation and its four sub-questions are recorded in
`Documents/requirements-dependency-map.md` §7. Its previously blocking framing is O-4,
now closed as a Chunk 5 scope question and moved to §12.3.

**Closed and no longer listed here** (previously in this section):
- **O-2 — closed as a scoping decision**, moved to §12.3: the capture-derived golden
  leg is deferred out of frozen scope, no capture file is authored, and no capture is
  pending from the operator.
- **O-3 — closed by operator ruling**, moved to §12.1: no enum extension, no
  coordination task, `GraphQLCorrelationDisposition` stands as the required local
  vocabulary, and the §4.1 line is deleted.
- **O-4 — closed as a Chunk 5 scope question**, moved to §12.3: the CSRF/cookie
  question is answered for Chunk 5 by behavior that is invariant under every outcome of
  OI-6, so it does not block the freeze. Dual framing recorded there: closed as a Chunk 5
  scope question, **OI-6 itself still open** as an external unknown of the retired
  parent SRS.