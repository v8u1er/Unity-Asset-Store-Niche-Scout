# Chunk 5 — GraphQL protocol adapter and response correlation (public interface)

Status: VERIFIED
Source plan: `Documents/plans/chunk-05-graphql-protocol-adapter-and-response-correlation.md`
Verified at: working tree state 2026-09-19; gates `python -m pytest tests/ -q`
(150 passed, exit 0), `python -m pytest tests/test_collector.py -q` (54 passed,
exit 0), `python -m pytest tests/test_identity.py -q` (29 passed, exit 0),
`python -m niche_scout.tools.validate_traceability` (exit 0; 148 matrix nodes),
`ruff check src/niche_scout/collector_graphql.py src/niche_scout/collector.py`
(clean).

This file is the **public contract** downstream chunks (6A, 6B, 7A, 10) build
against. It is not the full source; read `src/niche_scout/collector_graphql.py`
for implementation detail. Everything below is frozen: downstream chunks may
consume these names and semantics, and SHALL NOT redefine them. Chunk 5 is an
**I/O** module: it constructs the two-operation GraphQL batch request for one
canonical identity, correlates and validates responses, annotates identity and
state, and classifies failures. It performs no persistence, does not import
`database`, and reads no clock of its own; `retrieved_at_utc` is always
caller-supplied.

> **Recorded note (2026-09-19) — `__all__` breadth is a deliberate state, not a gap.**
> `collector_graphql.__all__` publishes **50** names while
> `src/niche_scout/collector.py` re-exports **49**. `CORRELATION_KEY_MEMBERS` is
> deliberately **NOT** re-exported by the facade because plan §5 does not list it
> (operator ruling D5). The one name the facade omits stays importable from
> `collector_graphql` directly; it is recorded here as a deliberate state rather
> than reported as a defect.

---

## 5.0 Module and boundary rules

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

> **Dated correction (2026-09-19).** The present-tense state claims in this
> subsection — that `collector.py` is 5 lines today and that Chunk 3 will write
> `collector_coveo.py` in parallel — were written against the pre-implementation
> tree and are **superseded**. `collector.py` is now a 54-line facade whose line 4
> re-exports 49 explicit names from `collector_graphql.__all__`, with line 3
> (`from .collector_coveo import *`) byte-identical as this subsection requires,
> and the Chunk 3 `collector_coveo.py` module has landed. The rule stated by the
> table above and the only-line-4-changes instruction remain binding; the line
> counts are retained above as the record of the state they were written against.

## 5.1 Constants and vocabularies

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

## 5.2 Failure classification vocabulary

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

## 5.3 Typed request structures

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

## 5.4 Typed response and operation result structures

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

## 5.5 Correlation

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

## 5.6 Per-operation response validation

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

## 5.7 Page-view type/range rule (derived from LREQ-GQL-040)

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

## 5.8 State and identity annotation (annotation only)

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

## 5.9 Per-identity enrichment result and pre-record value

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

## 5.10 `request_metadata_json` (SRS-lean §6.5)

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

> **Dated decision record (2026-09-19) — what `correlation_keys` persists.** The
> persisted `correlation_keys` value is the **correlation-key member name that
> supplied the association** — `operationName` on the normal path — which is what
> `LREQ-GQL-030` names first; it is never a redaction placeholder. `LREQ-GQL-030`
> (`Documents/SRS-lean.md` lines 300–302) makes the explicit operation name the
> primary correlation key, and the §5.10 `correlation_keys` row requires the
> `{operation_name: correlation_key or null}` shape. This is a clarification of the
> plan §5.10 content, not a new contract clause.

## 5.11 Transport, retry, and failure isolation

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
