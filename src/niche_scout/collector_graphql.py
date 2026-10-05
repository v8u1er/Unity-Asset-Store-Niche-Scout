"""Unity GraphQL enrichment adapter boundary.

This module builds, sends, and interprets one two-operation GraphQL batch
request (``ProductDetail`` / ``ProductPageViews``) for a single canonical
``asset_identity_key``, correlates each returned item to its operation by an
explicit correlation key, and records one independent status per operation.

Contracts this module honours:

* Null, zero, invalid, and unavailable remain distinct. A failed operation's
  fields are ``None`` and are never filled with ``0``, ``0.0``, ``""``, ``[]``,
  ``{}``, or ``False`` (SRS-lean LREQ-GQL-050).
* ``operationName`` is the correlation key. Response position is never used to
  guess an operation (SRS-lean LREQ-GQL-030).
* Nothing is persisted. This module opens no database connection, reads no
  environment variable, is never called with more than one identity, and
  returns a typed pre-record value for the persisting chunks to consume.
* No credential, ``Authorization`` header, CSRF token, cookie, request header
  *value*, or full response body reaches an issue, an error summary, a warning,
  ``header_names``, an exception message, or ``request_metadata_json``
  (SRS-lean LREQ-SEC-010, LREQ-SEC-020).
* The operator-supplied Unity CSRF credential is emitted as both the
  ``X-CSRF-Token`` header and the ``_csrf`` cookie, from the same credential,
  byte-for-byte (Chunk 17 R1, option (a)). No separate ``Cookie`` bootstrap,
  cookie jar, or second credential source exists.
* The transport and the sleeper are injected. The only clock read in the module
  is the default value of the injected ``sleep`` callable, so every
  calculation is a pure function of its arguments.

``collector_graphql`` must not import ``collector`` (circular), ``sqlite3``,
``metrics``, ``scoring``, ``database``, ``pipeline``, ``report``, ``cli``, or
``collector_coveo``.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence

from .config import UNITY_CSRF_TOKEN_ENV, Credentials
from .models import (
    ENDPOINT_CONTRACT_VERSION,
    IDENTITY_MAPPING_RULE_VERSION,
    EnrichmentObservationRecord,
    GraphQLOperationCorrelationMode,
    OperationStatus,
    WarningCode,
    ensure_utc,
)
from .validation import (
    GraphQLIdentityComparisonResult,
    StateEligibilityAnnotation,
    StructuralValidationResult,
    ValidationIssue,
    annotate_state_eligibility,
    compare_graphql_identity_aliases,
    summarize_validation_issues,
    validate_response_shape,
)

__all__ = (
    "PRODUCT_DETAIL_OPERATION_NAME",
    "PRODUCT_PAGE_VIEWS_OPERATION_NAME",
    "GRAPHQL_OPERATION_NAMES",
    "CORRELATION_KEY_MEMBERS",
    "GRAPHQL_BATCH_ENDPOINT",
    "GRAPHQL_CSRF_HEADER_NAME",
    "GRAPHQL_REQUEST_HEADERS",
    "DEFAULT_MAX_ATTEMPTS",
    "DEFAULT_BACKOFF_BASE_SECONDS",
    "DEFAULT_BACKOFF_MULTIPLIER",
    "DEFAULT_BACKOFF_MAX_SECONDS",
    "DEFAULT_MIN_REQUEST_INTERVAL_SECONDS",
    "RETRYABLE_HTTP_STATUSES",
    "PERMANENT_HTTP_STATUSES",
    "PRODUCT_DETAIL_REQUIRED_MEMBERS",
    "PRODUCT_DETAIL_ALIAS_MEMBERS",
    "PRODUCT_DETAIL_NUMERIC_MEMBER_TYPES",
    "PRODUCT_PAGE_VIEWS_PAYLOAD_SHAPE",
    "REQUEST_METADATA_REQUIRED_KEYS",
    "GraphQLFailureClass",
    "is_retryable",
    "GraphQLCorrelationDisposition",
    "GraphQLOperation",
    "GraphQLBatchRequest",
    "GraphQLBatchResponse",
    "PageViewValue",
    "GraphQLOperationResult",
    "GraphQLCorrelationResult",
    "GraphQLOperationCorrelationMatch",
    "GraphQLOperationValidation",
    "ProductDetailFields",
    "EnrichmentResult",
    "EnrichmentObservationDraft",
    "GraphQLRetryPolicy",
    "GraphQLTransport",
    "build_product_detail_operation",
    "build_product_page_views_operation",
    "build_graphql_batch_request",
    "build_graphql_headers",
    "header_name_in",
    "extract_operation_correlation_key",
    "correlate_operations",
    "validate_product_detail_payload",
    "validate_page_views_payload",
    "annotate_product_detail_identity",
    "build_request_metadata_json",
    "build_enrichment_observation_draft",
    "retry_delay_seconds",
    "execute_graphql_batch",
    "enrich_asset",
    "select_operation_correlation_mode",
    "interpret_graphql_response",
)

# --------------------------------------------------------------------------
# Constants and vocabularies
# --------------------------------------------------------------------------

PRODUCT_DETAIL_OPERATION_NAME: str = "ProductDetail"
PRODUCT_PAGE_VIEWS_OPERATION_NAME: str = "ProductPageViews"
GRAPHQL_OPERATION_NAMES: tuple[str, str] = (
    PRODUCT_DETAIL_OPERATION_NAME,
    PRODUCT_PAGE_VIEWS_OPERATION_NAME,
)

#: Endpoint contract value. SRS-lean.md ``LREQ-GQL-010`` (lines 289-292) names the
#: parent SRS GraphQL batch endpoint, and SRS-lean.md section 1.5 (lines 125-126)
#: names ``[PARENT]`` as the source for unchanged endpoint details. The operator
#: authorized ``Documents/retired-documents/SRS-revision2.md`` as a source for
#: endpoint details and only for endpoint details, so the value below is that
#: document's endpoint verbatim. Precedent: the frozen Chunk 3 plan cites the same
#: retired document for the Coveo endpoint.
GRAPHQL_BATCH_ENDPOINT: str = "https://assetstore.unity.com/api/graphql/batch"

#: Canonical emission name of the CSRF header (operator ruling, plan section 12
#: Q1(b)). The header is emitted lowercase on the wire like every other header in
#: ``GRAPHQL_REQUEST_HEADERS``; header *lookup* is case-insensitive because HTTP
#: header names are case-insensitive. See :func:`header_name_in`.
GRAPHQL_CSRF_HEADER_NAME: str = "X-CSRF-Token"

#: Request headers this adapter emits, excluding the caller-supplied credential.
#: Every value here is a constant: no request header *value* is ever echoed into
#: an issue, a summary, or request metadata (LREQ-SEC-020).
GRAPHQL_REQUEST_HEADERS: Mapping[str, str] = MappingProxyType(
    {
        "content-type": "application/json;charset=UTF-8",
        "accept": "application/json, text/plain, */*",
        "origin": "https://assetstore.unity.com",
        "referer": "https://assetstore.unity.com/",
        "x-requested-with": "XMLHttpRequest",
        "x-source": "storefront",
    }
)

#: Retry policy defaults. These are module constants, not configuration keys: the
#: lean SRS section 14 lists no GraphQL retry constant and ``config.load_config``
#: rejects unknown keys (operator ruling, plan section 12 Q4).
DEFAULT_MAX_ATTEMPTS: int = 4  # 1 initial attempt + 3 retries
DEFAULT_BACKOFF_BASE_SECONDS: float = 0.5
DEFAULT_BACKOFF_MULTIPLIER: float = 2.0
DEFAULT_BACKOFF_MAX_SECONDS: float = 8.0
DEFAULT_MIN_REQUEST_INTERVAL_SECONDS: float = 0.5

RETRYABLE_HTTP_STATUSES: frozenset[int] = frozenset({429, 500, 502, 503, 504})
PERMANENT_HTTP_STATUSES: frozenset[int] = frozenset({400, 401, 403, 404, 409, 422})

PRODUCT_PAGE_VIEWS_PAYLOAD_SHAPE: str = "mapping"


# --------------------------------------------------------------------------
# Failure classification (plan section 5.2)
# --------------------------------------------------------------------------


class GraphQLFailureClass(str, Enum):
    """Why an operation is an error.

    This is a local adapter vocabulary, not an SRS vocabulary, and it does not
    replace ``models.OperationStatus``. Every member is derived from
    ``LREQ-GQL-040``'s enumeration of operation errors plus the HTTP status split
    and the correlation failure classes of ``LREQ-GQL-030``.
    """

    NONE = "none"
    HTTP_TRANSIENT = "http_transient"
    HTTP_PERMANENT = "http_permanent"
    AUTHENTICATION_FAILURE = "authentication_failure"
    CSRF_FAILURE = "csrf_failure"
    MALFORMED_REQUEST = "malformed_request"
    AUTHORIZATION_FAILURE = "authorization_failure"
    GRAPHQL_TOP_LEVEL_ERROR = "graphql_top_level_error"
    OPERATION_ERROR = "operation_error"
    NULL_REQUIRED_DATA = "null_required_data"
    WRONG_DATA_SHAPE = "wrong_data_shape"
    WRONG_SCALAR_TYPE = "wrong_scalar_type"
    INVALID_PAGE_VIEWS = "invalid_page_views"
    INVALID_STATE_VALUE = "invalid_state_value"
    MISSING_IDENTITY = "missing_identity"
    OPERATION_CORRELATION_MISSING = "operation_correlation_missing"
    OPERATION_CORRELATION_DUPLICATED = "operation_correlation_duplicated"
    OPERATION_CORRELATION_UNKNOWN = "operation_correlation_unknown"
    OPERATION_CORRELATION_AMBIGUOUS = "operation_correlation_ambiguous"
    CORRELATION_MODE_UNVALIDATED = "correlation_mode_unvalidated"
    TRANSPORT_FAILURE = "transport_failure"
    RESPONSE_NOT_JSON = "response_not_json"


_RETRYABLE_FAILURE_CLASSES: frozenset[GraphQLFailureClass] = frozenset(
    {GraphQLFailureClass.HTTP_TRANSIENT, GraphQLFailureClass.TRANSPORT_FAILURE}
)


def is_retryable(failure_class: GraphQLFailureClass) -> bool:
    """Return whether ``failure_class`` may be retried.

    Exactly ``HTTP_TRANSIENT`` (429 and 5xx) and ``TRANSPORT_FAILURE`` are
    retryable. No authentication, CSRF, or authorization failure and no
    malformed-request or other permanent HTTP failure is ever retried, and a
    retryable failure is retried at most ``max_attempts - 1`` times.
    """
    if not isinstance(failure_class, GraphQLFailureClass):
        raise TypeError("failure_class must be a GraphQLFailureClass")
    return failure_class in _RETRYABLE_FAILURE_CLASSES


# --------------------------------------------------------------------------
# Correlation disposition vocabulary (adapter-internal, never persisted)
# --------------------------------------------------------------------------


class GraphQLCorrelationDisposition(str, Enum):
    """Adapter-internal, non-persisted dispositions of a response item.

    ``EXCLUDED`` and ``CANDIDATE`` are deliberately **not** members of
    ``models.GraphQLOperationCorrelationMode``: ``LREQ-GQL-030`` (SRS-lean.md
    lines 310-312) closes the *persisted* domain to ``explicit_key`` and
    ``validated_position``, so a disposition that can never be persisted cannot
    live on that enum. This local vocabulary is the required design, not a
    workaround, and no value of it may appear as a correlation mode in a result
    or in ``request_metadata_json``.
    """

    EXCLUDED = "excluded"
    CANDIDATE = "candidate"


# --------------------------------------------------------------------------
# Typed request structures (plan section 5.3)
# --------------------------------------------------------------------------


def _reject_non_identifier(value: object, label: str) -> str:
    """Return ``value`` when it is a usable identifier, else raise ``ValueError``.

    An unidentifiable asset is never sent: an empty, whitespace-only, or
    non-``str`` value raises before any request object exists, and no ``"0"`` or
    ``""`` sentinel is ever substituted. The message reports structure only and
    never echoes the supplied value.
    """
    if not isinstance(value, str) or value.strip() == "":
        raise ValueError(f"{label} must be a non-empty string identity")
    return value


@dataclass(frozen=True, slots=True)
class GraphQLOperation:
    """One batch request operation: a named operation and its single variable."""

    operation_name: str
    query: str
    variable_name: str
    variable_value: str

    def to_json_dict(self) -> dict[str, Any]:
        """Return the exact wire shape: ``query``, ``variables``, ``operationName``.

        These three keys are the whole operation object; extra keys would be a
        defect, so none is added.
        """
        return {
            "query": self.query,
            "variables": {self.variable_name: self.variable_value},
            "operationName": self.operation_name,
        }


@dataclass(frozen=True, slots=True)
class GraphQLBatchRequest:
    """The exactly-two-operation batch request for one canonical identity.

    ``body_json`` is a JSON array of exactly two operation objects and
    ``operations_header`` is the comma-joined operation-name list; the two are
    the only wire shapes this adapter produces. ``header_names`` holds the
    *names* of the headers the caller supplied, never the values, so a request
    object is always safe to log or attach to a fixture. Request order is fixed
    for reviewability but confers no correlation authority.
    """

    asset_identity_key: str
    operations: tuple[GraphQLOperation, GraphQLOperation]
    endpoint: str
    endpoint_contract_version: str
    operations_header: str
    header_names: tuple[str, ...]
    body_json: str


_PRODUCT_DETAIL_QUERY: str = (
    "query ProductDetail($id: ID!) {\n"
    "  product(id: $id) {\n"
    "    id\n"
    "    productId\n"
    "    rating {\n"
    "      average\n"
    "      count\n"
    "    }\n"
    "    reviewCount\n"
    "    firstPublishedDate\n"
    "    state\n"
    "    category {\n"
    "      id\n"
    "      name\n"
    "    }\n"
    "    publisher {\n"
    "      id\n"
    "      name\n"
    "    }\n"
    "  }\n"
    "}"
)

_PRODUCT_PAGE_VIEWS_QUERY: str = (
    "query ProductPageViews($packageId: String!) {\n"
    "  pageViews: productPageViews(packageId: $packageId)\n"
    "}"
)


def build_product_detail_operation(asset_identity_key: str) -> GraphQLOperation:
    """Build the lean ``ProductDetail`` operation for one canonical identity.

    The selection set is exactly the fields ``LREQ-GQL-020`` (SRS-lean.md lines
    294-298) requires - identity aliases, ``rating.average``, ``rating.count``,
    ``reviewCount``, ``firstPublishedDate``, ``state``, ``category``, and
    ``publisher`` - and nothing else. No favorite-count or
    ``packageInListHotness`` field is requested.
    """
    identity = _reject_non_identifier(asset_identity_key, "asset_identity_key")
    return GraphQLOperation(
        operation_name=PRODUCT_DETAIL_OPERATION_NAME,
        query=_PRODUCT_DETAIL_QUERY,
        variable_name="id",
        variable_value=identity,
    )


def build_product_page_views_operation(asset_identity_key: str) -> GraphQLOperation:
    """Build the ``ProductPageViews`` operation bound to the same canonical identity."""
    identity = _reject_non_identifier(asset_identity_key, "asset_identity_key")
    return GraphQLOperation(
        operation_name=PRODUCT_PAGE_VIEWS_OPERATION_NAME,
        query=_PRODUCT_PAGE_VIEWS_QUERY,
        variable_name="packageId",
        variable_value=identity,
    )


def _require_unity_csrf_token(credentials: Credentials) -> str:
    """Return the CSRF credential after the shared collection gate passes.

    ``Credentials.require_for_collection()`` is *called* rather than
    re-implemented so the two predicates cannot drift, and the pre-existing gate
    message already names ``UNITY_CSRF_TOKEN_ENV`` without echoing any part of
    the value. The additional check below covers a whitespace-only token and is
    deliberately value-free.
    """
    if not isinstance(credentials, Credentials):
        raise TypeError("credentials must be a config.Credentials instance")
    credentials.require_for_collection()
    token = credentials.unity_csrf_token
    if not isinstance(token, str) or token.strip() == "":
        raise ValueError(
            f"Unity CSRF credential is empty or whitespace-only; set the environment "
            f"variable {UNITY_CSRF_TOKEN_ENV} before collection"
        )
    return token


def build_graphql_headers(*, credentials: Credentials) -> Mapping[str, str]:
    """Build the request header map for one GraphQL batch request.

    The returned mapping carries the caller-supplied CSRF credential under
    ``GRAPHQL_CSRF_HEADER_NAME`` (emitted lowercase, as observed on the wire) and
    as the ``_csrf`` cookie (``"cookie": "_csrf=" + <token>``), both from the same
    operator-supplied credential and equal byte-for-byte. The map is wrapped in
    ``MappingProxyType`` so a caller cannot mutate a map shared with another
    request. A missing, empty, or whitespace-only credential raises ``ValueError``
    before any map exists; no credential value is returned by any other function
    in this module.
    """
    token = _require_unity_csrf_token(credentials)
    headers = dict(GRAPHQL_REQUEST_HEADERS)
    headers[GRAPHQL_CSRF_HEADER_NAME.lower()] = token
    headers["cookie"] = "_csrf=" + token
    return MappingProxyType(headers)


def header_name_in(name: str, names: Sequence[str]) -> bool:
    """Return whether ``name`` appears in ``names``, comparing case-insensitively.

    HTTP header names are case-insensitive and this adapter emits them lowercase,
    so no code path may depend on the caller's casing.
    """
    if not isinstance(name, str):
        raise TypeError("header name must be a string")
    wanted = name.casefold()
    return any(
        isinstance(candidate, str) and candidate.casefold() == wanted
        for candidate in names
    )


def build_graphql_batch_request(
    asset_identity_key: str,
    *,
    credentials: Credentials,
    endpoint: str = GRAPHQL_BATCH_ENDPOINT,
) -> GraphQLBatchRequest:
    """Build the two-operation batch request for one canonical identity.

    The credential gate and the identity gate both run *before* any request
    object exists, so an unauthenticated or unidentifiable asset is never sent.
    Both operations carry the same canonical ``asset_identity_key``, and the
    body is a JSON array of exactly two operation objects in
    ``GRAPHQL_OPERATION_NAMES`` order.
    """
    identity = _reject_non_identifier(asset_identity_key, "asset_identity_key")
    if not isinstance(endpoint, str) or endpoint.strip() == "":
        raise ValueError("endpoint must be a non-empty string")
    operations = (
        build_product_detail_operation(identity),
        build_product_page_views_operation(identity),
    )
    # The credential gate runs before the body is rendered so a missing
    # credential can never yield a sendable request object.
    credentials.require_for_collection()

    body_json = json.dumps(
        [operation.to_json_dict() for operation in operations],
        sort_keys=True,
        separators=(",", ":"),
    )
    return GraphQLBatchRequest(
        asset_identity_key=identity,
        operations=operations,
        endpoint=endpoint,
        endpoint_contract_version=ENDPOINT_CONTRACT_VERSION,
        operations_header=",".join(
            operation.operation_name for operation in operations
        ),
        header_names=(
            *sorted(GRAPHQL_REQUEST_HEADERS),
            GRAPHQL_CSRF_HEADER_NAME.lower(),
            "cookie",
        ),
        body_json=body_json,
    )


# --------------------------------------------------------------------------
# Typed response and operation result structures (plan section 5.4)
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GraphQLBatchResponse:
    """A received HTTP response, already read to text by the caller transport.

    No attribute of this type is retyped or rewritten by the adapter.
    ``body_text`` is retained verbatim so the response hash is computed over the
    received bytes, and it is never placed in an error summary or in request
    metadata.
    """

    http_status: int
    body_text: str
    header_names: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PageViewValue:
    """The validated ``ProductPageViews`` scalar, or the reason it is not one.

    ``value`` is non-``None`` if and only if ``is_valid`` is ``True``. A rejected
    scalar keeps a structural name of the observed JSON kind in
    ``rejected_shape`` for audit and never contributes a ``0``: zero is
    representable only as a validated ``value == 0``.
    """

    is_valid: bool
    value: int | None
    failure_class: GraphQLFailureClass
    rejected_shape: str | None


@dataclass(frozen=True, slots=True)
class GraphQLOperationResult:
    """One operation's independent outcome (LREQ-GQL-040, LREQ-GQL-050).

    ``status`` is ``models.OperationStatus`` and cannot disagree with
    ``failure_class``: success holds if and only if ``failure_class`` is
    ``NONE`` and ``payload`` is not ``None``. Every field of a failed operation
    is ``None``, and that ``None`` is what makes the corresponding
    ``EnrichmentObservationRecord`` column NULL.
    """

    operation_name: str
    status: OperationStatus
    failure_class: GraphQLFailureClass
    correlation_key: str | None
    correlation_mode: GraphQLOperationCorrelationMode
    payload: Mapping[str, Any] | None
    issues: tuple[ValidationIssue, ...]
    error_summary: str | None

    @property
    def is_success(self) -> bool:
        """Return whether this operation succeeded."""
        return self.status is OperationStatus.SUCCESS

    @property
    def requirement_warning_code(self) -> WarningCode | None:
        """Return the warning code naming this operation's failure, if any.

        Naming the code is not emitting a warning: category warning lists are
        Chunk 10's, and this module writes nothing.
        """
        if self.status is not OperationStatus.ERROR:
            return None
        if self.operation_name == PRODUCT_DETAIL_OPERATION_NAME:
            return WarningCode.GRAPHQL_PRODUCT_ERROR
        if self.operation_name == PRODUCT_PAGE_VIEWS_OPERATION_NAME:
            return WarningCode.GRAPHQL_PAGE_VIEWS_ERROR
        return None


def _shape_name(value: object) -> str:
    """Return a structural name for a JSON value's kind, never its content."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, Mapping):
        return "mapping"
    if isinstance(value, (list, tuple)):
        return "list"
    return type(value).__name__


def _issue(code: str, message: str, **context: object) -> ValidationIssue:
    """Build a redaction-safe structural issue with a bounded context."""
    return ValidationIssue(code=code, message=message, context=dict(context))


def _error_summary(issues: Sequence[ValidationIssue]) -> str | None:
    """Return the redacted summary for a failed operation, or ``None`` on success."""
    return summarize_validation_issues(issues) if issues else None


def _failed_operation_result(
    operation_name: str,
    failure_class: GraphQLFailureClass,
    *,
    correlation_key: str | None = None,
    mode: GraphQLOperationCorrelationMode,
    issues: tuple[ValidationIssue, ...] = (),
) -> GraphQLOperationResult:
    """Build a failed operation result: no payload, no fabricated field value."""
    return GraphQLOperationResult(
        operation_name=operation_name,
        status=OperationStatus.ERROR,
        failure_class=failure_class,
        correlation_key=correlation_key,
        correlation_mode=mode,
        payload=None,
        issues=issues,
        error_summary=_error_summary(issues),
    )


# --------------------------------------------------------------------------
# Correlation (plan section 5.5)
# --------------------------------------------------------------------------

_ADDITIONAL_CORRELATION_KEY_MEMBERS: tuple[str, ...] = (
    "operation_name",
    "operation",
    "correlationKey",
)

#: Every correlation-key member this adapter accepts, in look-up order.
CORRELATION_KEY_MEMBERS: tuple[str, ...] = (
    "operationName",
    *_ADDITIONAL_CORRELATION_KEY_MEMBERS,
)


def extract_operation_correlation_key(item: object) -> str | None:
    """Return the explicit correlation key an item carries, else ``None``.

    ``operationName`` is the correlation key ``LREQ-GQL-030`` (SRS-lean.md lines
    300-302) names first and the member the ``operations`` request header mirrors.
    The additional accepted members are explicit key members, never positions, so
    reading one is still an explicit-key association. An item that is not a
    mapping, or whose key member is absent, ``None``, or not a usable string,
    yields ``None`` and is never repaired.
    """
    if not isinstance(item, Mapping):
        return None
    for member in ("operationName", *_ADDITIONAL_CORRELATION_KEY_MEMBERS):
        value = item.get(member)
        if isinstance(value, str) and value.strip() != "":
            return value
    return None


def _correlation_key_member_of(item: object) -> str:
    """Return which accepted member supplied ``item``'s correlation key."""
    if isinstance(item, Mapping):
        for member in CORRELATION_KEY_MEMBERS:
            value = item.get(member)
            if isinstance(value, str) and value.strip() != "":
                return member
    return "operationName"


def additional_correlation_key_names(item: object) -> tuple[str, ...]:
    """Return the extra explicit key members an item carries beyond
    ``operationName``."""
    if not isinstance(item, Mapping):
        return ()
    return tuple(
        member
        for member in _ADDITIONAL_CORRELATION_KEY_MEMBERS
        if isinstance(item.get(member), str) and item.get(member).strip() != ""
    )


@dataclass(frozen=True, slots=True)
class GraphQLOperationCorrelationMatch:
    """How one operation was (or was not) associated with a response item."""

    operation_name: str
    item_index: int | None
    correlation_key: str | None
    failure_class: GraphQLFailureClass


@dataclass(frozen=True, slots=True)
class GraphQLCorrelationResult:
    """The correlation outcome for one response: per-operation matches plus issues.

    ``correlation_members`` records which correlation-key member supplied each
    operation's key: ``"operationName"``, or one of the additional members. A key
    drawn from an additional member is response-derived and is therefore not one
    of this adapter's own operation names, so metadata never persists it as a
    name.
    """

    mode: GraphQLOperationCorrelationMode
    is_fully_correlated: bool
    by_operation: Mapping[str, object | None]
    matches: tuple[GraphQLOperationCorrelationMatch, ...]
    issues: tuple[ValidationIssue, ...]
    unassociated_item_indexes: tuple[int, ...]
    correlation_members: Mapping[str, str] = field(default_factory=dict)

    @property
    def correlation_keys(self) -> Mapping[str, str | None]:
        """Return ``{operation_name: correlation_key or None}`` for metadata.

        A key read from an additional member is replaced by that member's name
        from the frozen ``CORRELATION_KEY_MEMBERS`` vocabulary, so the persisted
        entry reports which member correlated without echoing response text.
        """
        others = {name: () for name in CORRELATION_KEY_MEMBERS}
        return MappingProxyType(
            {
                match.operation_name: (
                    (
                        self.correlation_members.get(match.operation_name)
                        if self.correlation_members.get(match.operation_name) in others
                        else None
                    )
                    if match.correlation_key is not None
                    else None
                )
                if match.failure_class is GraphQLFailureClass.NONE
                else None
                for match in self.matches
            }
        )


def _require_correlation_mode(mode: object) -> GraphQLOperationCorrelationMode:
    """Return ``mode`` when it is a member of the frozen correlation-mode enum."""
    if not isinstance(mode, GraphQLOperationCorrelationMode):
        raise TypeError("mode must be a models.GraphQLOperationCorrelationMode")
    return mode


def _correlate_by_explicit_key(
    matches: list[GraphQLOperationCorrelationMatch],
    response_items: Sequence[object],
    operation_names: tuple[str, str],
    issues: list[ValidationIssue],
    unassociated: list[int],
    members: dict[str, str],
) -> None:
    """Assign one item per operation by explicit key, never by position."""
    keyed_items: dict[str, int] = {}
    keyed_members: dict[str, str] = {}
    duplicate_keys: set[str] = set()
    for index, item in enumerate(response_items):
        key = extract_operation_correlation_key(item)
        if key is None or key not in operation_names:
            # No usable key, or a key naming no operation this adapter issues:
            # the item is reported and never attached to another operation.
            unassociated.append(index)
            continue
        if key in keyed_items:
            duplicate_keys.add(key)
            continue
        keyed_items[key] = index
        keyed_members[key] = _correlation_key_member_of(item)

    if not response_items:
        issues.append(
            _issue(
                "operation_correlation_missing",
                "the response contained no items to correlate",
                correlation_mode=GraphQLOperationCorrelationMode.EXPLICIT_KEY.value,
            )
        )
        for match in matches:
            matches[matches.index(match)] = replace(
                match,
                failure_class=GraphQLFailureClass.OPERATION_CORRELATION_MISSING,
            )
        return

    for index, item in enumerate(response_items):
        key = extract_operation_correlation_key(item)
        if key is not None and key not in operation_names:
            issues.append(
                _issue(
                    "operation_correlation_unknown",
                    "a response item carries a correlation key that names no "
                    "issued operation",
                    item_index=index,
                )
            )

    for position, match in enumerate(matches):
        operation_name = match.operation_name
        if operation_name in duplicate_keys:
            issues.append(
                _issue(
                    "operation_correlation_duplicated",
                    "more than one response item carries this operation's "
                    "correlation key",
                    operation=operation_name,
                )
            )
            matches[position] = replace(
                match,
                failure_class=GraphQLFailureClass.OPERATION_CORRELATION_DUPLICATED,
            )
            continue
        if operation_name in keyed_items:
            members[operation_name] = keyed_members.get(operation_name, "operationName")
            matches[position] = replace(
                match,
                item_index=keyed_items[operation_name],
                correlation_key=operation_name,
                failure_class=GraphQLFailureClass.NONE,
            )
            continue
        issues.append(
            _issue(
                "operation_correlation_missing",
                "no response item carries this operation's correlation key",
                operation=operation_name,
            )
        )
        matches[position] = replace(
            match,
            failure_class=GraphQLFailureClass.OPERATION_CORRELATION_MISSING,
        )


def _correlate_by_validated_position(
    matches: list[GraphQLOperationCorrelationMatch],
    response_items: Sequence[object],
    issues: list[ValidationIssue],
    unassociated: list[int],
) -> None:
    """Accept the caller's already-validated fixed two-operation ordering.

    The adapter does not validate the ordering itself: position validation is the
    identity preflight's job (Chunk 6A, LREQ-ID-020). It uses the fixed
    two-operation ordering the preflight validated and still reports each item's
    index, so the preflight can audit the decision. A response that does not have
    exactly the expected two positions is ambiguous rather than repaired.
    """
    unrelated = [
        index
        for index, item in enumerate(response_items)
        if extract_operation_correlation_key(item)
        not in (match.operation_name for match in matches)
        and extract_operation_correlation_key(item) is not None
    ]
    unassociated.extend(unrelated)

    if len(response_items) != len(matches) or any(
        extract_operation_correlation_key(response_items[position]) is not None
        for position in range(len(response_items))
    ):
        issues.append(
            _issue(
                "operation_correlation_ambiguous",
                "the response does not present the validated two-operation "
                "ordering, so no operation can be attached",
                item_count=len(response_items),
            )
        )
        for position, match in enumerate(matches):
            matches[position] = replace(
                match,
                failure_class=GraphQLFailureClass.OPERATION_CORRELATION_AMBIGUOUS,
            )
        return

    for position, match in enumerate(matches):
        matches[position] = replace(
            match,
            item_index=position,
            failure_class=GraphQLFailureClass.NONE,
        )


def correlate_operations(
    response_items: Sequence[object],
    *,
    mode: GraphQLOperationCorrelationMode,
    operation_names: tuple[str, str] = GRAPHQL_OPERATION_NAMES,
) -> GraphQLCorrelationResult:
    """Associate each response item with an operation through an explicit key.

    ``operationName`` is the correlation key, so an item carrying
    ``operationName = ProductPageViews`` at index ``0`` matches that operation and
    a reversed response passes; ``response_items`` order decides nothing while a
    key is present. Missing, duplicated, unknown, and ambiguous associations are
    recorded as typed failures on the affected operations and are never repaired
    from response position. Under ``VALIDATED_POSITION`` the adapter accepts the
    caller's mode as already validated and does not validate position itself.
    """
    active_mode = _require_correlation_mode(mode)
    items = tuple(response_items)

    matches: list[GraphQLOperationCorrelationMatch] = [
        GraphQLOperationCorrelationMatch(
            operation_name=name,
            item_index=None,
            correlation_key=None,
            failure_class=GraphQLFailureClass.NONE,
        )
        for name in operation_names
    ]
    issues: list[ValidationIssue] = []
    unassociated: list[int] = []
    members: dict[str, str] = {}

    if active_mode is GraphQLOperationCorrelationMode.EXPLICIT_KEY:
        _correlate_by_explicit_key(
            matches, items, operation_names, issues, unassociated, members
        )
    else:
        _correlate_by_validated_position(matches, items, issues, unassociated)

    resolved = tuple(matches)
    by_operation = MappingProxyType(
        {
            match.operation_name: (
                items[match.item_index]
                if match.item_index is not None
                and match.failure_class is GraphQLFailureClass.NONE
                else None
            )
            for match in resolved
        }
    )
    return GraphQLCorrelationResult(
        mode=active_mode,
        is_fully_correlated=all(
            match.failure_class is GraphQLFailureClass.NONE for match in resolved
        ),
        by_operation=by_operation,
        matches=resolved,
        issues=tuple(issues),
        unassociated_item_indexes=tuple(sorted(set(unassociated))),
        correlation_members=MappingProxyType(dict(members)),
    )


# --------------------------------------------------------------------------
# Per-operation response validation (plan sections 5.6, 5.7)
# --------------------------------------------------------------------------

# The required/absent identity-member group used by
# ``validate_product_detail_payload`` and the ``LREQ-GQL-040``
# ``response_missing_identity`` classification. It is **not** the
# ``LREQ-GQL-070`` agreement alias set: the agreement alias set is the
# authoritative returned ``id`` alone, supplied by
# ``annotate_product_detail_identity`` (Chunk 19; interfaces/chunk-05.md §5.8).
PRODUCT_DETAIL_ALIAS_MEMBERS: tuple[str, ...] = ("id", "productId")

# ``state`` is deliberately not a member here: it is validated semantically by
# ``annotate_state_eligibility`` below, where a missing/null value is
# ``state_unknown`` rather than a structural failure (plan section 12.6 item 2,
# E10). A present-but-unusable ``state`` still fails as ``INVALID_STATE_VALUE``
# on the semantic path, not as a missing-member complaint.
PRODUCT_DETAIL_REQUIRED_MEMBERS: tuple[str, ...] = (
    "id",
    "productId",
    "rating",
    "reviewCount",
    "firstPublishedDate",
    "category",
    "publisher",
)

PRODUCT_DETAIL_NUMERIC_MEMBER_TYPES: Mapping[str, type | tuple[type, ...]] = (
    MappingProxyType({"reviewCount": int})
)

_TOP_LEVEL_RESULT_KEYS: tuple[str, ...] = ("errors", "data", "extensions")


def _product_detail_root_payload(
    item: object,
) -> tuple[object | None, str | None]:
    """Return the ProductDetail payload from one response item, or why it fails.

    The live endpoint answers ``ProductDetail`` with the ``data.product`` wrapper
    (Chunk 18 H5, plan §5.5): the root field ``product`` holds the product object,
    so the adapter must unwrap ``data.product`` before
    :func:`validate_product_detail_payload`, which reads its members at the
    payload's own top level. The rules, with ``LREQ-GQL-040`` classes:

    * ``{"data": {"product": <mapping>}}`` -> the unwrapped product object,
      status ``None`` (validate it);
    * ``{"data": {"product": null}}`` -> ``(None, "product_null")``: no product
      data returned, classified ``NULL_REQUIRED_DATA``, never a zero-valued
      success;
    * ``{"data": {"product": <non-mapping>}}`` -> ``(None, "wrong_container")``:
      a wrong container kind, classified ``WRONG_DATA_SHAPE``;
    * ``{"data": null}`` -> ``(None, "data_null")``: the existing envelope-null
      branch (``NULL_REQUIRED_DATA``, issue member ``data``);
    * any other item (a flat legacy ``data`` with no ``product`` key, a bare
      payload item, a non-envelope item) -> ``(<payload>, None)``: validated as
      today, with the payload the existing code would have chosen.

    Pure: reads no clock, performs no I/O, and never defaults or coerces a field.
    """
    if not isinstance(item, Mapping):
        return item, None
    if _is_operation_envelope(item):
        if "data" not in item:
            # An envelope with no ``data`` member at all: the existing code
            # validates the item itself; keep that unchanged.
            return item, None
        data = item["data"]
        if data is None:
            return None, "data_null"
        if isinstance(data, Mapping) and "product" in data:
            product = data["product"]
            if isinstance(product, Mapping):
                return product, None
            if product is None:
                return None, "product_null"
            return None, "wrong_container"
        return data, None
    return item, None


@dataclass(frozen=True, slots=True)
class ProductDetailFields:
    """A validated ``ProductDetail`` payload, field by field.

    Every scored field is optional and stays ``None`` when the corresponding
    member is absent, null, or wrong-typed. No field is ever defaulted or
    coerced: a payload with a valid ``rating.average`` and no ``reviewCount``
    yields ``rating_average`` set and ``review_count = None``, never ``0``.

    ``mapping_rule_version`` records which identity mapping rule this payload's
    fields were read under. It is required rather than defaulted so that no
    payload object can exist without stating the rule that produced its
    identity candidates, and so no construction site can silently pin the rule
    to the module-level constant at the moment it is read.
    """

    mapping_rule_version: str
    graphql_id: str | None
    product_id: str | None
    rating_average: float | None
    rating_count: int | None
    review_count: int | None
    first_published_date_utc: datetime | None
    first_published_date_issue: str | None
    publisher_json: str | None
    category_json: str | None
    state: str | None
    state_annotation: StateEligibilityAnnotation | None
    identity_comparison: GraphQLIdentityComparisonResult | None


@dataclass(frozen=True, slots=True)
class GraphQLOperationValidation:
    """The verdict for one operation payload: validity, class, and typed value."""

    is_valid: bool
    failure_class: GraphQLFailureClass
    product_detail: ProductDetailFields | None
    page_views: PageViewValue | None
    issues: tuple[ValidationIssue, ...]


def _usable_string(value: object) -> str | None:
    """Return ``value`` when it is a usable non-empty string, else ``None``."""
    if isinstance(value, str) and value.strip() != "":
        return value
    return None


def _usable_number(value: object, declared: type) -> int | float | None:
    """Return ``value`` when it matches ``declared``, excluding ``bool``.

    A ``declared is float`` member accepts a non-bool ``float`` as-is and a
    non-bool ``int`` as ``float(value)``: JSON carries no distinction between
    integral and fractional numbers, so an integral JSON number (``5``, ``0``)
    is a valid value for a float member and is widened without rounding. The
    ``bool`` exclusion applies first, so ``True``/``False`` are never accepted
    as ``1.0``/``0.0``. A ``declared is int`` member stays int-only.
    """
    if isinstance(value, bool):
        return None
    if declared is int and isinstance(value, int):
        return value
    if declared is float:
        if isinstance(value, float):
            return value
        if isinstance(value, int):
            return float(value)
    return None


def _usable_container_json(value: object) -> str | None:
    """Return compact JSON for a non-empty container, else ``None``.

    A mapping or list that is present but empty is ``{}`` or ``[]`` - a container
    kind carrying no data - and is reported as unavailable rather than serialized
    as a placeholder.
    """
    if isinstance(value, Mapping):
        if not value:
            return None
        return json.dumps(
            {str(key): item for key, item in value.items()},
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
    if isinstance(value, (list, tuple)):
        if not value:
            return None
        return json.dumps(
            list(value), sort_keys=True, separators=(",", ":"), default=str
        )
    return None


def _parse_first_published_date(value: object) -> tuple[datetime | None, str | None]:
    """Parse a published-date member, reporting why it is unavailable.

    Parsing only: a timezone-naive, date-only, or unparsable value yields ``None``
    with the reason recorded. Age thresholds and future-date rejection are Chunk
    7A's, and this module never compares the date to a cutoff.
    """
    if value is None:
        return None, "absent"
    if not isinstance(value, str) or value.strip() == "":
        return None, "wrong_type"
    text = value.strip()
    candidate: datetime | None = None
    if "T" in text:
        try:
            candidate = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None, "unparsable"
    else:
        try:
            from datetime import date as _date

            _date.fromisoformat(text)
        except ValueError:
            return None, "unparsable"
        return None, "date_only"
    if candidate.tzinfo is None:
        return None, "naive"
    return ensure_utc(candidate), None


def _collect_payload_issues(
    structure: StructuralValidationResult,
) -> list[ValidationIssue]:
    """Return the structural issues of a payload in a deterministic order."""
    return list(structure.issues)


def _map_rating_pair(
    rating_average_value: float | None,
    rating_count_value: int | None,
) -> tuple[float | None, int | None, tuple[ValidationIssue, ...]]:
    """Apply the ``chunk-27`` §3.1 typed-pair precedence (frozen rule).

    Returns ``(rating_average, rating_count, contradiction_issues)``. It never
    fabricates a value: row 4 returns ``(None, None, (code A,))``, row 5 returns
    ``(None, None, ())``, and row 6 returns ``(None, count, (code B,))``.

    The rule keys on the **typed** pair the caller passes -- a Python ``float``
    for ``rating.average`` and a Python ``int`` for ``rating.count``, each
    ``None`` when the member was absent, null, or wrong-typed -- never on the raw
    JSON member. Rows 1-3 and 7 are existing behavior and are returned unchanged;
    rows 4-6 are the Unity "unrated" placeholders:

    * row 1 ``(None, None)`` -> ``(None, None)``, no issue;
    * row 2 ``(None, cnt)`` -> ``(None, cnt)``, no issue;
    * row 3 ``(avg, None)`` -> ``(avg, None)``, no issue (Q5);
    * row 4 ``cnt == 0`` and ``avg > 0`` -> ``(None, None)``, code
      ``rating_average_without_rating_count``;
    * row 5 ``cnt == 0`` and ``avg == 0.0`` -> ``(None, None)``, no issue;
    * row 6 ``cnt > 0`` and ``avg == 0.0`` -> ``(None, cnt)`` with the count
      retained as returned, code ``rating_average_zero_with_positive_count``;
    * row 7 ``cnt > 0`` and ``0 < avg <= 5`` -> ``(avg, cnt)``, no issue.

    A count of ``0`` with an absent (``None``) average is row 5, not row 4: an
    absent member is not a positive average. Pure and deterministic: no RNG, no
    clock, no set/dict-ordering dependence.
    """
    if rating_count_value is None:
        # Rows 1-3: no count, so no zero-count contradiction is possible.
        return rating_average_value, None, ()

    if rating_count_value == 0:
        if rating_average_value is not None and rating_average_value > 0:
            # Row 4: a genuine positive average cannot sit alongside a zero count.
            return (
                None,
                None,
                (
                    _issue(
                        "rating_average_without_rating_count",
                        "rating.average is positive while rating.count is zero; "
                        "both are unavailable and neither is coerced to a default",
                        field="rating.average",
                    ),
                ),
            )
        # Row 5: ``avg`` is ``0.0`` or absent (``None``); both are "no rating".
        return None, None, ()

    if rating_average_value is not None and rating_average_value == 0.0:
        # Row 6: a zero average placeholder with a positive count. The count is
        # genuinely returned, so it is retained; only the average is unavailable.
        return (
            None,
            rating_count_value,
            (
                _issue(
                    "rating_average_zero_with_positive_count",
                    "rating.average is a zero placeholder with a positive "
                    "rating.count; the average is unavailable and the count is "
                    "retained as returned",
                    field="rating.average",
                ),
            ),
        )

    # Rows 2/3/7 (non-zero count): retain both members unchanged.
    return rating_average_value, rating_count_value, ()


def validate_product_detail_payload(
    payload: object,
    *,
    mapping_rule_version: str = IDENTITY_MAPPING_RULE_VERSION,
) -> GraphQLOperationValidation:
    """Validate a correlated ``ProductDetail`` payload, field by field.

    Required members are checked structurally through Chunk 1's
    ``validate_response_shape``; numeric members are additionally checked for
    type, because Chunk 1's required-member check deliberately does not judge a
    present member's type unless a ``field_types`` entry declares one. Absent,
    null, and wrong-typed members each produce their own issue code, stay ``None``
    in the returned fields, and are never substituted with a default.

    A payload with no usable identity alias is an operation error via
    ``MISSING_IDENTITY`` (``LREQ-GQL-040``'s "missing identity"). An invalid
    ``state`` value is *not* an operation error: a present non-``"published"``
    value is an exclusion annotation, recorded and retained
    (``LREQ-GQL-060``).

    The caller unwraps the live ``data.product`` root before calling this
    function (Chunk 18 H5), so the payload here is always the product object or
    the legacy flat mapping.
    """
    if not isinstance(payload, Mapping):
        issue = _issue(
            "response_wrong_container_kind",
            "the ProductDetail payload is not an object",
            expected_shape="mapping",
            actual_shape=_shape_name(payload),
        )
        return GraphQLOperationValidation(
            is_valid=False,
            failure_class=GraphQLFailureClass.WRONG_DATA_SHAPE,
            product_detail=None,
            page_views=None,
            issues=(issue,),
        )

    structure = validate_response_shape(
        payload,
        expected_shape="mapping",
        required_members=PRODUCT_DETAIL_REQUIRED_MEMBERS,
        field_types=PRODUCT_DETAIL_NUMERIC_MEMBER_TYPES,
    )
    raw_issues = _collect_payload_issues(structure)

    error_classes: dict[str, str] = {
        "response_missing_required_member": "response_missing_required_member",
        "response_null_required_member": "response_null_required_member",
        "response_wrong_scalar_type": "response_wrong_scalar_type",
        "response_missing_identity": "response_missing_identity",
    }

    issues: list[ValidationIssue] = []
    seen: set[tuple[str, str]] = set()
    for issue in raw_issues:
        if issue.code not in error_classes:
            issues.append(issue)
            continue
        member = str(issue.context.get("member", issue.context.get("field", "")))
        key = (issue.code, member)
        if key in seen:
            continue
        seen.add(key)
        issues.append(issue)

    missing_identity = any(
        issue.code == "response_missing_identity" for issue in issues
    )
    graphql_id = _usable_string(payload.get("id"))
    product_id = _usable_string(payload.get("productId"))
    # ``response_missing_required_member`` fires for an ABSENT member, but the
    # identity group check in ``validate_response_shape`` stays silent for it: one
    # omitted alias leaves the group saturated. An absent alias is therefore
    # identity-unusable too, and saying so here lets
    # ``_classify_product_detail_failure`` reach ``MISSING_IDENTITY`` by the
    # LREQ-GQL-040 route instead of falling through to the required-member route.
    absent_alias = any(member not in payload for member in PRODUCT_DETAIL_ALIAS_MEMBERS)
    no_populated_alias = graphql_id is None and product_id is None
    if not missing_identity and (absent_alias or no_populated_alias):
        issues.append(
            _issue(
                "response_missing_identity",
                "no populated identity member was returned; a missing identity is an "
                "operation error, not an empty identity",
            )
        )
        missing_identity = True

    rating_container = payload.get("rating")
    rating_mapping = rating_container if isinstance(rating_container, Mapping) else None
    rating_average_value = (
        _usable_number(rating_mapping.get("average"), float)
        if rating_mapping is not None
        else None
    )
    rating_count_value = (
        _usable_number(rating_mapping.get("count"), int)
        if rating_mapping is not None
        else None
    )
    if rating_mapping is not None and "average" in rating_mapping:
        if rating_average_value is None and rating_mapping.get("average") is not None:
            issues.append(
                _issue(
                    "response_wrong_scalar_type",
                    "member 'average' does not match its declared type",
                    member="rating.average",
                    field="rating.average",
                    expected_type="float",
                    actual_shape=_shape_name(rating_mapping.get("average")),
                )
            )
    if rating_mapping is not None and "count" in rating_mapping:
        if rating_count_value is None and rating_mapping.get("count") is not None:
            issues.append(
                _issue(
                    "response_wrong_scalar_type",
                    "member 'count' does not match its declared type",
                    member="rating.count",
                    field="rating.count",
                    expected_type="int",
                    actual_shape=_shape_name(rating_mapping.get("count")),
                )
            )

    review_count_raw = payload.get("reviewCount")
    review_count_value = _usable_number(review_count_raw, int)

    # Chunk 27 / D2: apply the §3.1 typed-pair precedence once, after the
    # wrong-scalar-type checks and before the field construction. The mapped pair
    # feeds both this validated path and the draft-only path, which reads
    # ``validation.product_detail`` (§3.5). Any contradiction issue rides on the
    # validation result's ``issues`` tuple and therefore reaches the operation
    # success result's issue channel (§3.4).
    (
        rating_average_mapped,
        rating_count_mapped,
        rating_issues,
    ) = _map_rating_pair(rating_average_value, rating_count_value)
    issues.extend(rating_issues)

    first_published_date_utc, first_published_date_issue = _parse_first_published_date(
        payload.get("firstPublishedDate")
    )

    state_value = payload.get("state")
    state_annotation = annotate_state_eligibility(state_value)
    if state_annotation.state_excluded:
        issues.append(
            _issue(
                "state_excluded",
                "the returned state is not 'published'; the asset is annotated as "
                "state-excluded and remains in discovered breadth",
                warning_code=WarningCode.STATE_EXCLUDED.value,
            )
        )
    elif state_annotation.state_unknown and state_value is not None:
        # A present but unusable state value is an invalid state value
        # (LREQ-GQL-040's "invalid state values" clause). A missing or null state
        # is state-unknown only (LREQ-GQL-060's annotation half).
        issues.append(
            _issue(
                "invalid_state_value",
                "the returned state value is not a usable string",
                actual_shape=_shape_name(state_value),
            )
        )

    fields = ProductDetailFields(
        mapping_rule_version=mapping_rule_version,
        graphql_id=graphql_id,
        product_id=product_id,
        rating_average=(
            float(rating_average_mapped) if rating_average_mapped is not None else None
        ),
        rating_count=(
            int(rating_count_mapped) if rating_count_mapped is not None else None
        ),
        review_count=(
            int(review_count_value) if review_count_value is not None else None
        ),
        first_published_date_utc=first_published_date_utc,
        first_published_date_issue=first_published_date_issue,
        publisher_json=_usable_container_json(payload.get("publisher")),
        category_json=_usable_container_json(payload.get("category")),
        state=state_value if isinstance(state_value, str) else None,
        state_annotation=state_annotation,
        identity_comparison=None,
    )

    failure_class = _classify_product_detail_failure(
        issues,
        missing_identity,
        identity_usable=(graphql_id is not None or product_id is not None),
    )
    return GraphQLOperationValidation(
        is_valid=failure_class is GraphQLFailureClass.NONE,
        failure_class=failure_class,
        product_detail=fields if failure_class is GraphQLFailureClass.NONE else None,
        page_views=None,
        issues=tuple(issues),
    )


def _classify_product_detail_failure(
    issues: Sequence[ValidationIssue],
    missing_identity: bool,
    *,
    identity_usable: bool = True,
) -> GraphQLFailureClass:
    """Map a ``ProductDetail`` payload's issues to its single failure class.

    ``LREQ-GQL-040`` lists "wrong data shape" and "missing identity" as peer
    operation errors and fixes no order between them, so a payload that
    qualifies as both is resolved toward the one the SRS names specifically:
    *no usable identity alias at all* is a missing identity first, and only then
    a shape complaint. ``identity_usable`` carries that fact, so an absent
    required alias (``response_missing_required_member``) does not mask a
    ``MISSING_IDENTITY`` verdict. A payload whose identity is usable and whose
    shape is not is still ``WRONG_DATA_SHAPE``.
    """
    codes = {issue.code for issue in issues}
    if missing_identity or "response_missing_identity" in codes or not identity_usable:
        return GraphQLFailureClass.MISSING_IDENTITY
    if "invalid_state_value" in codes:
        return GraphQLFailureClass.INVALID_STATE_VALUE
    if "response_wrong_container_kind" in codes:
        return GraphQLFailureClass.WRONG_DATA_SHAPE
    if "response_missing_required_member" in codes:
        return GraphQLFailureClass.WRONG_DATA_SHAPE
    if "response_null_required_member" in codes:
        return GraphQLFailureClass.NULL_REQUIRED_DATA
    if "response_wrong_scalar_type" in codes:
        return GraphQLFailureClass.WRONG_SCALAR_TYPE
    return GraphQLFailureClass.NONE


def validate_page_view_scalar(scalar: object) -> PageViewValue:
    """Validate the raw ``ProductPageViews`` scalar against the acceptance table.

    Accepted: a JSON integer (``bool`` excluded) that is ``>= 0``. ``bool`` is
    rejected *before* any numeric test because ``isinstance(True, int)`` is true
    in Python. A finite float with zero fractional part is accepted as its integer
    value; a negative, non-finite, or non-integral value is rejected. ``None`` and
    an absent scalar are ``NULL_REQUIRED_DATA``; every other non-numeric kind is
    ``WRONG_SCALAR_TYPE``. A rejection never yields a ``0``.
    """
    if scalar is None:
        return PageViewValue(
            is_valid=False,
            value=None,
            failure_class=GraphQLFailureClass.NULL_REQUIRED_DATA,
            rejected_shape="null",
        )
    if isinstance(scalar, bool):
        return PageViewValue(
            is_valid=False,
            value=None,
            failure_class=GraphQLFailureClass.WRONG_SCALAR_TYPE,
            rejected_shape="bool",
        )
    if isinstance(scalar, int):
        if scalar < 0:
            return PageViewValue(
                is_valid=False,
                value=None,
                failure_class=GraphQLFailureClass.INVALID_PAGE_VIEWS,
                rejected_shape="int",
            )
        return PageViewValue(
            is_valid=True,
            value=scalar,
            failure_class=GraphQLFailureClass.NONE,
            rejected_shape=None,
        )
    if isinstance(scalar, float):
        if not math.isfinite(scalar):
            return PageViewValue(
                is_valid=False,
                value=None,
                failure_class=GraphQLFailureClass.INVALID_PAGE_VIEWS,
                rejected_shape="float",
            )
        if scalar < 0 or scalar != math.floor(scalar):
            return PageViewValue(
                is_valid=False,
                value=None,
                failure_class=GraphQLFailureClass.INVALID_PAGE_VIEWS,
                rejected_shape="float",
            )
        return PageViewValue(
            is_valid=True,
            value=int(scalar),
            failure_class=GraphQLFailureClass.NONE,
            rejected_shape=None,
        )
    return PageViewValue(
        is_valid=False,
        value=None,
        failure_class=(
            GraphQLFailureClass.WRONG_SCALAR_TYPE
            if not isinstance(scalar, (Mapping, list, tuple))
            else GraphQLFailureClass.WRONG_DATA_SHAPE
        ),
        rejected_shape=_shape_name(scalar),
    )


def validate_page_views_payload(payload: object) -> GraphQLOperationValidation:
    """Validate a correlated ``ProductPageViews`` payload and its scalar.

    The scalar must arrive as ``{"pageViews": <value>}``. A wrong-shaped container
    is ``WRONG_DATA_SHAPE``, a missing member is ``NULL_REQUIRED_DATA``, and an
    invalid scalar carries the class
    :func:`validate_page_view_scalar` assigns. Nothing in the adapter reads a
    package identifier out of this payload: ``LREQ-GQL-030`` (SRS-lean.md lines
    314-316) makes request-scoped identity validation through the associated
    operation sufficient.
    """
    if not isinstance(payload, Mapping):
        issue = _issue(
            "response_wrong_container_kind",
            "the ProductPageViews payload is not an object",
            expected_shape=PRODUCT_PAGE_VIEWS_PAYLOAD_SHAPE,
            actual_shape=_shape_name(payload),
        )
        return GraphQLOperationValidation(
            is_valid=False,
            failure_class=GraphQLFailureClass.WRONG_DATA_SHAPE,
            product_detail=None,
            page_views=None,
            issues=(issue,),
        )
    if "pageViews" not in payload:
        issue = _issue(
            "response_missing_required_member",
            "response payload is missing the required member 'pageViews'",
            member="pageViews",
            field="pageViews",
        )
        return GraphQLOperationValidation(
            is_valid=False,
            failure_class=GraphQLFailureClass.NULL_REQUIRED_DATA,
            product_detail=None,
            page_views=None,
            issues=(issue,),
        )
    raw_scalar = payload["pageViews"]
    page_view_value = validate_page_view_scalar(raw_scalar)
    if page_view_value.is_valid:
        return GraphQLOperationValidation(
            is_valid=True,
            failure_class=GraphQLFailureClass.NONE,
            product_detail=None,
            page_views=page_view_value,
            issues=(),
        )

    if page_view_value.failure_class is GraphQLFailureClass.WRONG_DATA_SHAPE:
        issue = _issue(
            "response_wrong_container_kind",
            "the page-view scalar is not a scalar",
            member="pageViews",
            field="pageViews",
            actual_shape=page_view_value.rejected_shape,
        )
    elif page_view_value.failure_class is GraphQLFailureClass.NULL_REQUIRED_DATA:
        issue = _issue(
            "response_null_required_member",
            "required member 'pageViews' is present but null; a null value is "
            "unavailable and is not substituted with a default",
            member="pageViews",
            field="pageViews",
        )
    elif page_view_value.failure_class is GraphQLFailureClass.WRONG_SCALAR_TYPE:
        issue = _issue(
            "response_wrong_scalar_type",
            "member 'pageViews' does not match its declared type",
            member="pageViews",
            field="pageViews",
            expected_type="int",
            actual_shape=page_view_value.rejected_shape,
        )
    else:
        issue = _issue(
            "response_invalid_page_views",
            "the page-view scalar is not a non-negative integral value",
            member="pageViews",
            field="pageViews",
            actual_shape=page_view_value.rejected_shape,
        )
    return GraphQLOperationValidation(
        is_valid=False,
        failure_class=page_view_value.failure_class,
        product_detail=None,
        page_views=None,
        issues=(issue,),
    )


# --------------------------------------------------------------------------
# Correlation-mode selection (Chunk 18, LREQ-GQL-030)
# --------------------------------------------------------------------------


def _response_page_views_payload(item: object) -> object:
    """Return an item's page-views payload, as the adapter's own extraction does.

    An envelope item's payload is its ``data`` member; a bare item is its own
    payload. A ``data`` that is absent or ``None`` yields ``None``, which
    :func:`validate_page_views_payload` reports as a wrong container kind rather
    than a zero.
    """
    if isinstance(item, Mapping) and "data" in item:
        return item.get("data")
    return item


def select_operation_correlation_mode(
    responses: Sequence[GraphQLBatchResponse],
) -> GraphQLOperationCorrelationMode:
    """Select the run-level persisted correlation mode from already-received responses.

    ``responses`` is the ordered per-identity batch response for the selected
    preflight identities, one per unique identity, in selection order. It is
    evidence only: this function issues no request and reads no clock. Pure and
    deterministic; the result is a function of the ordered evidence alone.

    Raises ``ValueError`` for an empty sequence: a zero-identity preflight is
    ``insufficient`` (LREQ-ID-040) and selection is not reached; the caller must
    not substitute a default.

    Returns ``VALIDATED_POSITION`` iff every response decodes to exactly two
    items, no item carries an explicit correlation key
    (``extract_operation_correlation_key(item) is None`` for both), item 0
    presents the ``ProductDetail`` operation-specific shape (the H5 unwrap of
    ``data.product``, or the legacy flat payload) and item 1 presents the
    ``ProductPageViews`` operation-specific shape (``{"pageViews": <int >= 0>}``,
    ``LREQ-GQL-030``). Otherwise returns ``EXPLICIT_KEY`` -- including when any
    response carries an explicit key (the primary association is available) and
    when any identity fails shape, count, or decode. Selection is
    all-or-nothing across the selected identities.

    Determinism: no RNG, no clock, no set/dict-ordering dependence.
    """
    responses = tuple(responses)
    if not responses:
        raise ValueError(
            "select_operation_correlation_mode requires at least one response; "
            "an empty evidence sequence has no selected mode"
        )

    for response in responses:
        if not isinstance(response, GraphQLBatchResponse):
            raise TypeError("responses must contain GraphQLBatchResponse values")
        items, decode_failure = _decode_operation_items(response)
        if items is None or decode_failure is not None:
            return GraphQLOperationCorrelationMode.EXPLICIT_KEY
        if any(extract_operation_correlation_key(item) is not None for item in items):
            # An explicit key is the primary association; position is only the
            # no-key fallback, so any keyed item selects the explicit-key mode.
            return GraphQLOperationCorrelationMode.EXPLICIT_KEY
        if len(items) != 2:
            return GraphQLOperationCorrelationMode.EXPLICIT_KEY

        detail_payload, detail_failure = _product_detail_root_payload(items[0])
        if detail_failure is not None:
            return GraphQLOperationCorrelationMode.EXPLICIT_KEY
        if not validate_product_detail_payload(detail_payload).is_valid:
            return GraphQLOperationCorrelationMode.EXPLICIT_KEY
        if not validate_page_views_payload(
            _response_page_views_payload(items[1])
        ).is_valid:
            return GraphQLOperationCorrelationMode.EXPLICIT_KEY

    return GraphQLOperationCorrelationMode.VALIDATED_POSITION


# --------------------------------------------------------------------------
# State and identity annotation (plan section 5.8)
# --------------------------------------------------------------------------


def annotate_product_detail_identity(
    requested_identity: str,
    product_detail: ProductDetailFields,
    *,
    mapping_rule_version: str = IDENTITY_MAPPING_RULE_VERSION,
) -> ProductDetailFields:
    """Return ``product_detail`` with its identity comparison annotated.

    Chunk 1's ``compare_graphql_identity_aliases`` is the comparison, and its
    result is stored unchanged. A mismatch is an adapter-level mark and a redacted
    reason only: whether a mismatched asset is excluded from D, R, and Q is Chunk
    7A's decision, and this module produces no such verdict.

    The agreement alias set is built from the returned authoritative ``id``
    (``graphql_id``) when present, and from nothing else (``LREQ-GQL-070``;
    ``Documents/interfaces/chunk-05.md`` §5.8, amended by Chunk 19). The returned
    ``productId`` is still requested (``LREQ-GQL-020``) and persisted on
    ``ProductDetailFields.product_id``, but it is not an agreement alias, so a
    populated-but-different ``productId`` does not make an agreeing ``id`` a
    mismatch. When ``graphql_id`` is ``None`` the alias map is empty and the
    comparison is an explicit mismatch ("no GraphQL identity alias was
    returned"), never an assumed agreement; ``product_id`` is never consulted as
    a fallback identity.
    """
    aliases: dict[str, object] = {}
    if product_detail.graphql_id is not None:
        aliases["id"] = product_detail.graphql_id
    comparison = compare_graphql_identity_aliases(
        requested_identity, aliases, mapping_rule_version=mapping_rule_version
    )
    return replace(product_detail, identity_comparison=comparison)


# --------------------------------------------------------------------------
# request_metadata_json (plan section 5.10)
# --------------------------------------------------------------------------

REQUEST_METADATA_REQUIRED_KEYS: tuple[str, ...] = (
    "operation_names",
    "correlation_keys",
    "correlation_mode",
    "http_status",
    "response_sha256",
    "retry",
    "additional_correlation_keys",
)

_ALLOWED_RETRY_KEYS: tuple[str, ...] = (
    "attempts",
    "failure_classes",
    "http_statuses",
)
_METADATA_MAX_TEXT_CHARS: int = 256


def _metadata_text(value: object, *, max_chars: int = _METADATA_MAX_TEXT_CHARS) -> str:
    """Render a caller-supplied name or key verbatim, bounded and secret-free.

    Operation names and correlation keys reach ``request_metadata_json`` as their
    **real values** (plan section 5.10, ruling D4): a placeholder would destroy
    the two fields the requirement names. Nothing is decided on the strength of
    the value's shape -- every input is rendered, so no caller-supplied string is
    silently dropped -- and a non-string is normalized through ``str()`` before
    bounding, because a non-string would raise from the ``len()`` inside
    :func:`redact_value`.

    Credential-capable inputs never reach this renderer; they stay on
    :func:`redact_value`, which never returns the value's own text.
    """
    return str(value)[:max_chars]


def render_operation_name(name: object) -> str | None:
    """Return ``name`` verbatim when it is one of this adapter's own operations.

    ``operation_names`` are not caller-supplied: they are the fixed names this
    adapter issues (``GRAPHQL_OPERATION_NAMES``). Persisting them verbatim is
    what makes a stored ``request_metadata_json`` auditable, and it cannot leak
    a credential because membership is decided by equality against that frozen
    allowlist -- nothing is passed through on the strength of its shape.

    Any value that is not exactly one of the allowlisted names returns ``None``
    and is therefore never emitted by this function; the caller falls back to
    :func:`_metadata_text`, which renders the real name.
    """
    if isinstance(name, str) and name in GRAPHQL_OPERATION_NAMES:
        return name[:_METADATA_MAX_TEXT_CHARS]
    return None


def _metadata_int(value: object) -> int | None:
    """Return ``value`` when it is a genuine integer, else ``None``."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _allowlisted_retry_metadata(retry_metadata: Mapping[str, object]) -> dict[str, Any]:
    """Re-serialize a caller's retry mapping key by key against an allowlist.

    The mapping is never passed through wholesale, so an unredacted string in a
    caller's mapping cannot leak into persisted metadata. ``attempts`` is always
    present and at least ``1``; a class list is never invented for a
    single-attempt success.
    """
    if not isinstance(retry_metadata, Mapping):
        raise TypeError("retry_metadata must be a mapping")
    attempts = _metadata_int(retry_metadata.get("attempts"))
    if attempts is None or attempts < 1:
        attempts = 1

    allowed_classes = {member.value for member in GraphQLFailureClass}
    failure_classes: list[str] = []
    raw_classes = retry_metadata.get("failure_classes")
    if isinstance(raw_classes, (list, tuple)):
        for item in raw_classes:
            text = item.value if isinstance(item, GraphQLFailureClass) else item
            if text in allowed_classes and text not in failure_classes:
                failure_classes.append(text)

    http_statuses: list[int] = []
    raw_statuses = retry_metadata.get("http_statuses")
    if isinstance(raw_statuses, (list, tuple)):
        for item in raw_statuses:
            status = _metadata_int(item)
            if status is not None and status not in http_statuses:
                http_statuses.append(status)

    return {
        "attempts": attempts,
        "failure_classes": failure_classes,
        "http_statuses": http_statuses,
    }


def build_request_metadata_json(
    *,
    operation_names: Sequence[str],
    correlation_keys: Mapping[str, str | None],
    correlation_mode: GraphQLOperationCorrelationMode,
    http_status: int | None,
    response_sha256: str | None,
    retry_metadata: Mapping[str, object],
    additional_correlation_keys: Mapping[str, Sequence[str]] | None = None,
    correlation_key_members: Sequence[str] = (),
) -> str:
    """Build the ``request_metadata_json`` payload for one identity.

    The signature accepts no credential, header-value, cookie, or body parameter
    at all, so none of those can reach the JSON without a signature change. The
    persisted operation names and correlation keys are their **real values**
    (plan section 5.10, ruling D4): names pass through the operation-name
    allowlist and keys are bounded text, so neither is a redaction placeholder.
    ``correlation_mode`` is always one of the two persisted modes, and the
    ``retry`` mapping is re-serialized key by key against an allowlist.
    """
    if correlation_mode not in (
        GraphQLOperationCorrelationMode.EXPLICIT_KEY,
        GraphQLOperationCorrelationMode.VALIDATED_POSITION,
    ):
        raise ValueError(
            "correlation_mode must be 'explicit_key' or 'validated_position'; "
            "adapter-internal correlation dispositions are never persisted"
        )
    if not isinstance(response_sha256, (str, type(None))):
        raise TypeError("response_sha256 must be a hex string or None")

    names = [
        rendered
        for rendered in (render_operation_name(name) for name in operation_names)
        if rendered is not None
    ]
    keys: dict[str, str | None] = {}
    other_key_members: list[str] = []
    for name, key in correlation_keys.items():
        rendered_name = render_operation_name(name)
        if rendered_name is None:
            other_key_members.append(_metadata_text(name))
        # Names and keys are persisted as their real values; the correlation key
        # is itself an operation name (plan section 5.10), so both are bounded
        # text and neither is a redaction placeholder.
        keys[rendered_name or _metadata_text(name)] = (
            None if key is None else _metadata_text(key)
        )

    extra: dict[str, list[str]] = {name: [] for name in names}
    if additional_correlation_keys is not None:
        for name, members in additional_correlation_keys.items():
            rendered_name = render_operation_name(name)
            if rendered_name is None:
                rendered_name = _metadata_text(name)
            extra.setdefault(rendered_name, [])
            for member in members if isinstance(members, (list, tuple)) else []:
                rendered_member = _metadata_text(member)
                if rendered_member not in extra[rendered_name]:
                    extra[rendered_name].append(rendered_member)

    status = _metadata_int(http_status)
    payload: dict[str, Any] = {
        "operation_names": names,
        "correlation_keys": keys,
        "correlation_mode": correlation_mode.value,
        "http_status": status,
        "response_sha256": response_sha256,
        "retry": _allowlisted_retry_metadata(retry_metadata),
    }
    if additional_correlation_keys is not None:
        payload["additional_correlation_keys"] = extra
    if other_key_members:
        # The item's correlation key came from a member other than
        # ``operationName``, so the operation name here is response-derived and is
        # reported by member name only. ``CORRELATION_KEY_MEMBERS`` is this
        # adapter's frozen vocabulary, so only those names are ever emitted.
        payload["correlation_key_members"] = other_key_members
    if correlation_key_members:
        payload["correlation_key_members"] = sorted(
            {
                member
                for member in correlation_key_members
                if member in CORRELATION_KEY_MEMBERS and member != "operationName"
            }
        )
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


# --------------------------------------------------------------------------
# Per-identity enrichment result and pre-record value (plan section 5.9)
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EnrichmentResult:
    """The adapter's whole result for one canonical identity and one HTTP exchange.

    ``is_success`` holds only when both operations succeeded; a partial success
    carries whichever operation's fields validated and leaves the other
    operation's fields ``None``.
    """

    asset_identity_key: str
    correlation: GraphQLCorrelationResult
    product_detail: GraphQLOperationResult
    page_views: GraphQLOperationResult
    http_status: int | None
    attempts: int
    response_sha256: str | None
    retry_metadata_json: str
    issues: tuple[ValidationIssue, ...]

    @property
    def is_success(self) -> bool:
        """Return whether both operations succeeded."""
        return self.product_detail.is_success and self.page_views.is_success

    @property
    def is_partial_success(self) -> bool:
        """Return whether exactly one operation succeeded."""
        return self.product_detail.is_success != self.page_views.is_success

    @property
    def both_operations_malformed(self) -> bool:
        """Return whether neither operation produced a usable result."""
        return not self.product_detail.is_success and not self.page_views.is_success

    @property
    def requirement_warning_codes(self) -> tuple[WarningCode, ...]:
        """Return the warning codes naming this result's failed operations."""
        codes = (
            self.product_detail.requirement_warning_code,
            self.page_views.requirement_warning_code,
        )
        return tuple(code for code in codes if code is not None)


@dataclass(frozen=True, slots=True)
class EnrichmentObservationDraft:
    """A pre-record value: the ``EnrichmentObservationRecord`` field set minus
    ``run_id``.

    Chunk 5 does not persist. :meth:`to_record` is the only conversion and it
    performs a field-for-field copy: it never substitutes a default, so a failed
    operation's field stays ``None`` and is never a fabricated ``0``.
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

    def to_record(self, run_id: str) -> EnrichmentObservationRecord:
        """Return the persistable record for ``run_id``, copying every field."""
        if not isinstance(run_id, str) or run_id.strip() == "":
            raise ValueError("run_id must be a non-empty string")
        return EnrichmentObservationRecord(
            run_id=run_id,
            asset_identity_key=self.asset_identity_key,
            product_detail_status=self.product_detail_status,
            page_views_status=self.page_views_status,
            graphql_id=self.graphql_id,
            product_id=self.product_id,
            rating_average=self.rating_average,
            rating_count=self.rating_count,
            review_count=self.review_count,
            first_published_date_utc=self.first_published_date_utc,
            publisher_json=self.publisher_json,
            category_json=self.category_json,
            state=self.state,
            product_page_views=self.product_page_views,
            id_mapping_mismatch=self.id_mapping_mismatch,
            product_detail_error_summary=self.product_detail_error_summary,
            page_views_error_summary=self.page_views_error_summary,
            request_metadata_json=self.request_metadata_json,
            retrieved_at_utc=self.retrieved_at_utc,
        )


def _validated_page_views(result: GraphQLOperationResult) -> int | None:
    """Return the validated page-view count, or ``None`` when the operation failed."""
    if not result.is_success or result.payload is None:
        return None
    value = result.payload.get("pageViews")
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def build_enrichment_observation_draft(
    result: EnrichmentResult,
    *,
    fields: ProductDetailFields | None = None,
    retrieved_at_utc: datetime,
) -> EnrichmentObservationDraft:
    """Build the pre-record value for one identity.

    ``retrieved_at_utc`` is a required caller-supplied timezone-aware UTC value and
    is normalized through ``models.ensure_utc``; the adapter never reads the clock.
    Every field is a field-for-field copy of the typed result: a failed operation
    yields ``None``, never a fabricated default. ``id_mapping_mismatch`` is the
    comparison's own flag, and an identity that could not be compared is ``True``,
    because an uncomparable identity is not an agreement.
    """
    detail = fields
    if detail is None and result.product_detail.is_success:
        detail = _product_detail_fields_from_payload(
            result.product_detail.payload, result.asset_identity_key
        )

    comparison = detail.identity_comparison if detail is not None else None
    id_mapping_mismatch = (
        comparison.id_mapping_mismatch if comparison is not None else True
    )
    if (
        result.product_detail.is_success
        and comparison is not None
        and not comparison.matches_requested_identity
    ):
        # A mismatch is an adapter-level mark on the affected result. Exclusion
        # from D, R, and Q remains Chunk 7A's decision, and no verdict for it is
        # produced here.
        pass

    names = tuple(match.operation_name for match in result.correlation.matches)
    correlation_members = sorted(
        {
            member
            for operation_name, member in result.correlation.correlation_members.items()
            if operation_name in names and member != "operationName"
        }
    )
    request_metadata_json = build_request_metadata_json(
        operation_names=names,
        correlation_keys=result.correlation.correlation_keys,
        correlation_mode=result.correlation.mode,
        http_status=result.http_status,
        response_sha256=result.response_sha256,
        retry_metadata=json.loads(result.retry_metadata_json),
        additional_correlation_keys=_additional_correlation_keys_by_operation(
            result, names
        ),
        correlation_key_members=tuple(correlation_members),
    )

    return EnrichmentObservationDraft(
        asset_identity_key=result.asset_identity_key,
        product_detail_status=result.product_detail.status.value,
        page_views_status=result.page_views.status.value,
        graphql_id=detail.graphql_id if detail is not None else None,
        product_id=detail.product_id if detail is not None else None,
        rating_average=detail.rating_average if detail is not None else None,
        rating_count=detail.rating_count if detail is not None else None,
        review_count=detail.review_count if detail is not None else None,
        first_published_date_utc=(
            detail.first_published_date_utc if detail is not None else None
        ),
        publisher_json=detail.publisher_json if detail is not None else None,
        category_json=detail.category_json if detail is not None else None,
        state=detail.state if detail is not None else None,
        product_page_views=_validated_page_views(result.page_views),
        id_mapping_mismatch=id_mapping_mismatch,
        product_detail_error_summary=result.product_detail.error_summary,
        page_views_error_summary=result.page_views.error_summary,
        request_metadata_json=request_metadata_json,
        retrieved_at_utc=ensure_utc(retrieved_at_utc),
    )


def _additional_correlation_keys_by_operation(
    result: EnrichmentResult, names: Sequence[str]
) -> dict[str, list[str]]:
    """Return each operation's extra explicit correlation-key member names."""
    extra: dict[str, list[str]] = {name: [] for name in names}
    for match in result.correlation.matches:
        if match.item_index is None:
            continue
        item = result.correlation.by_operation.get(match.operation_name)
        if item is None:
            continue
        for member in additional_correlation_key_names(item):
            if member not in extra.setdefault(match.operation_name, []):
                extra[match.operation_name].append(member)
    return extra


def _product_detail_fields_from_payload(
    payload: Mapping[str, Any] | None, requested_identity: str
) -> ProductDetailFields | None:
    """Re-validate a retained payload and annotate its identity, or return ``None``."""
    if payload is None:
        return None
    validation = validate_product_detail_payload(payload)
    if not validation.is_valid or validation.product_detail is None:
        return None
    return annotate_product_detail_identity(
        requested_identity, validation.product_detail
    )


# --------------------------------------------------------------------------
# Transport, retry, and failure isolation (plan section 5.11)
# --------------------------------------------------------------------------

GraphQLTransport = Callable[
    [GraphQLBatchRequest, Mapping[str, str]], GraphQLBatchResponse
]


@dataclass(frozen=True, slots=True)
class GraphQLRetryPolicy:
    """A bounded, jitter-free retry policy.

    ``max_attempts`` counts the initial attempt, so ``4`` means one attempt plus
    at most three retries.
    """

    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    backoff_base_seconds: float = DEFAULT_BACKOFF_BASE_SECONDS
    backoff_multiplier: float = DEFAULT_BACKOFF_MULTIPLIER
    backoff_max_seconds: float = DEFAULT_BACKOFF_MAX_SECONDS
    min_request_interval_seconds: float = DEFAULT_MIN_REQUEST_INTERVAL_SECONDS


def retry_delay_seconds(policy: GraphQLRetryPolicy, attempt: int) -> float:
    """Return the deterministic delay before retry ``attempt``.

    The delay is ``min(backoff_base_seconds * backoff_multiplier ** (attempt - 1),
    backoff_max_seconds)`` for ``attempt >= 1``, is non-decreasing in ``attempt``,
    and is ``0.0`` for ``attempt <= 0``. It reads no clock and produces no jitter.
    """
    if attempt <= 0:
        return 0.0
    delay = policy.backoff_base_seconds * policy.backoff_multiplier ** (attempt - 1)
    return float(min(delay, policy.backoff_max_seconds))


_CSRF_MISMATCH_BODY_MARKER: str = "csrf token mismatch"


def _classify_http_status(
    http_status: int, *, body_text: str = ""
) -> GraphQLFailureClass:
    """Classify a non-200 HTTP status into the operation failure it implies.

    An HTTP ``400`` whose already-read ``body_text`` carries the endpoint's
    ``csrf token mismatch`` marker is a ``CSRF_FAILURE``; **every other** ``400``
    stays ``MALFORMED_REQUEST``. The body is inspected only for a ``400`` and is
    never read for any other status. Both classes are permanent and non-retrying,
    so this changes no retry path.
    """
    if http_status == 400:
        if (
            isinstance(body_text, str)
            and _CSRF_MISMATCH_BODY_MARKER in body_text.casefold()
        ):
            return GraphQLFailureClass.CSRF_FAILURE
        return GraphQLFailureClass.MALFORMED_REQUEST
    if http_status == 401:
        return GraphQLFailureClass.AUTHENTICATION_FAILURE
    if http_status == 403:
        return GraphQLFailureClass.AUTHORIZATION_FAILURE
    if http_status in RETRYABLE_HTTP_STATUSES:
        return GraphQLFailureClass.HTTP_TRANSIENT
    return GraphQLFailureClass.HTTP_PERMANENT


_CSRF_ERROR_CODES: frozenset[str] = frozenset(
    {"csrf", "csrf_token_invalid", "invalid_csrf", "csrf_error"}
)


def _classify_top_level_errors(errors: Sequence[object]) -> GraphQLFailureClass:
    """Classify a top-level ``errors`` member, distinguishing a CSRF mismatch."""
    for error in errors:
        if isinstance(error, Mapping):
            extensions = error.get("extensions")
            candidates = [error.get("message"), error.get("code")]
            if isinstance(extensions, Mapping):
                candidates.append(extensions.get("code"))
            for candidate in candidates:
                if isinstance(candidate, str) and candidate.strip().casefold() in (
                    _CSRF_ERROR_CODES
                ):
                    return GraphQLFailureClass.CSRF_FAILURE
    return GraphQLFailureClass.GRAPHQL_TOP_LEVEL_ERROR


def _decode_operation_items(
    response: GraphQLBatchResponse,
) -> tuple[list[object] | None, GraphQLFailureClass | None]:
    """Decode the response body into a list of operation items, or report why not."""
    if not isinstance(response.body_text, str) or response.body_text.strip() == "":
        return None, GraphQLFailureClass.NULL_REQUIRED_DATA
    try:
        decoded = json.loads(response.body_text)
    except ValueError:
        return None, GraphQLFailureClass.RESPONSE_NOT_JSON
    if not isinstance(decoded, list):
        return None, GraphQLFailureClass.WRONG_DATA_SHAPE
    return decoded, None


def _top_level_errors_of(item: object) -> list[object]:
    """Return an item's top-level ``errors`` entries as a list, else an empty list."""
    if isinstance(item, Mapping):
        errors = item.get("errors")
        if isinstance(errors, list) and errors:
            return errors
    return []


def _is_operation_envelope(item: object) -> bool:
    """Return whether an item carries the batch envelope rather than bare data."""
    if not isinstance(item, Mapping):
        return False
    return any(member in item for member in _TOP_LEVEL_RESULT_KEYS)


def _operation_level_errors(item: object) -> list[object]:
    """Return an item's envelope-level ``errors`` entries, else an empty list."""
    envelope = item.get("data") if isinstance(item, Mapping) else None
    if isinstance(envelope, Mapping):
        errors = envelope.get("errors")
        if isinstance(errors, list) and errors:
            return errors
    return []


def _operation_data(item: object) -> tuple[object | None, bool]:
    """Return an item's operation data and whether the operation carried data at all."""
    if isinstance(item, Mapping) and "data" in item:
        return item.get("data"), True
    return item, False


def _summarize_transport_failure(exc: BaseException) -> ValidationIssue:
    """Return a redacted issue for a raised transport, naming only its type."""
    return _issue(
        "transport_failure",
        "the caller-supplied transport raised an exception",
        exception_type=type(exc).__name__,
    )


def _build_result_from_items(
    request: GraphQLBatchRequest,
    items: Sequence[object],
    response: GraphQLBatchResponse,
    correlation: GraphQLCorrelationResult,
    issues: tuple[ValidationIssue, ...],
    attempts: int,
) -> EnrichmentResult:
    """Build the typed result for one HTTP exchange over already-correlated items."""
    match_by_operation = {match.operation_name: match for match in correlation.matches}
    operation_results: list[GraphQLOperationResult] = []

    top_level_classes: dict[str, GraphQLFailureClass] = {}
    for operation_name in GRAPHQL_OPERATION_NAMES:
        match = match_by_operation[operation_name]
        if match.item_index is None:
            continue
        item = items[match.item_index]
        errors = _top_level_errors_of(item)
        if errors:
            top_level_classes[operation_name] = _classify_top_level_errors(errors)

    for operation_name in GRAPHQL_OPERATION_NAMES:
        match = match_by_operation[operation_name]
        correlation_key = match.correlation_key

        if match.failure_class is not GraphQLFailureClass.NONE:
            operation_results.append(
                _failed_operation_result(
                    operation_name,
                    match.failure_class,
                    mode=correlation.mode,
                    issues=correlation.issues,
                )
            )
            continue

        assert match.item_index is not None
        item = items[match.item_index]

        # A top-level error is not erased by a sibling operation's success, and it
        # applies to every operation in the same response.
        if top_level_classes:
            classified = top_level_classes.get(
                operation_name, GraphQLFailureClass.GRAPHQL_TOP_LEVEL_ERROR
            )
            operation_results.append(
                _failed_operation_result(
                    operation_name,
                    classified,
                    correlation_key=correlation_key,
                    mode=correlation.mode,
                    issues=(
                        _issue(
                            "graphql_top_level_error",
                            "the response is not a valid GraphQL result",
                            http_status=response.http_status,
                        ),
                    ),
                )
            )
            continue

        operation_errors = _operation_level_errors(item)
        if operation_errors:
            operation_results.append(
                _failed_operation_result(
                    operation_name,
                    GraphQLFailureClass.OPERATION_ERROR,
                    correlation_key=correlation_key,
                    mode=correlation.mode,
                    issues=(
                        _issue(
                            "operation_level_errors",
                            "the operation returned an errors member",
                            operation=operation_name,
                            error_count=len(operation_errors),
                        ),
                    ),
                )
            )
            continue

        if _is_operation_envelope(item):
            operation_data, _ = _operation_data(item)
            if operation_data is None:
                operation_results.append(
                    _failed_operation_result(
                        operation_name,
                        GraphQLFailureClass.NULL_REQUIRED_DATA,
                        correlation_key=correlation_key,
                        mode=correlation.mode,
                        issues=(
                            _issue(
                                "response_null_required_member",
                                "the operation returned null data; a null value is "
                                "unavailable and is not substituted with a default",
                                member="data",
                                field="data",
                            ),
                        ),
                    )
                )
                continue
            payload: object = operation_data
        else:
            payload = item

        if operation_name == PRODUCT_DETAIL_OPERATION_NAME:
            # The shared helper applies the H5 ``data.product`` unwrap (plan
            # §5.5): a mapping root is unwrapped, ``product: null`` and
            # ``data: null`` are ``NULL_REQUIRED_DATA``, a non-mapping
            # ``product`` is ``WRONG_DATA_SHAPE``, and a flat legacy payload is
            # validated as today. Its ``data_null`` status carries no payload, so
            # the frozen envelope-null branch below supplies the issue spelling.
            payload, root_failure = _product_detail_root_payload(item)
            if root_failure == "product_null":
                operation_results.append(
                    _failed_operation_result(
                        operation_name,
                        GraphQLFailureClass.NULL_REQUIRED_DATA,
                        correlation_key=correlation_key,
                        mode=correlation.mode,
                        issues=(
                            _issue(
                                "response_null_required_member",
                                "the operation returned null data; a null value is "
                                "unavailable and is not substituted with a default",
                                member="product",
                                field="product",
                            ),
                        ),
                    )
                )
                continue
            if root_failure == "wrong_container":
                operation_results.append(
                    _failed_operation_result(
                        operation_name,
                        GraphQLFailureClass.WRONG_DATA_SHAPE,
                        correlation_key=correlation_key,
                        mode=correlation.mode,
                        issues=(
                            _issue(
                                "response_wrong_container_kind",
                                "the ProductDetail payload is not an object",
                                expected_shape="mapping",
                                actual_shape=_shape_name(item["data"]["product"]),
                            ),
                        ),
                    )
                )
                continue
            # A ProductDetail item carries bare data (its own top level is the
            # payload) or the batch envelope, not the envelope keys
            # ``_operation_level_errors`` reads. An absent ``data`` member under
            # that envelope is the keyless twin of a JSON ``null``: both mean no
            # payload was returned, so both are ``NULL_REQUIRED_DATA``
            # (LREQ-GQL-040: "null required data ... SHALL be recorded as an
            # operation error") rather than a wrong container kind.
            if root_failure == "data_null":
                operation_results.append(
                    _failed_operation_result(
                        operation_name,
                        GraphQLFailureClass.NULL_REQUIRED_DATA,
                        correlation_key=correlation_key,
                        mode=correlation.mode,
                        issues=(
                            _issue(
                                "response_null_required_member",
                                "the operation returned null data; a null value is "
                                "unavailable and is not substituted with a default",
                                member="data",
                                field="data",
                            ),
                        ),
                    )
                )
                continue
            validation = validate_product_detail_payload(payload)
            if not validation.is_valid or validation.product_detail is None:
                operation_results.append(
                    _failed_operation_result(
                        operation_name,
                        validation.failure_class,
                        correlation_key=correlation_key,
                        mode=correlation.mode,
                        issues=validation.issues,
                    )
                )
                continue
            annotated = annotate_product_detail_identity(
                request.asset_identity_key, validation.product_detail
            )
            operation_issues = list(validation.issues)
            comparison = annotated.identity_comparison
            assert comparison is not None
            operation_issues.extend(comparison.issues)
            if comparison.id_mapping_mismatch:
                # The affected result is invalidated at the adapter level: the
                # mark is set and a redacted reason is carried. Exclusion from D,
                # R, and Q stays Chunk 7A's decision.
                operation_issues.append(
                    _issue(
                        "graphql_id_mapping_mismatch",
                        "returned identity aliases do not agree with the requested "
                        "canonical identity",
                        warning_code=WarningCode.GRAPHQL_ID_MAPPING_MISMATCH.value,
                    )
                )
            retained_payload: Mapping[str, Any] = {
                **{str(key): value for key, value in payload.items()},
                "_annotated_fields": annotated,
            }
            operation_results.append(
                GraphQLOperationResult(
                    operation_name=operation_name,
                    status=OperationStatus.SUCCESS,
                    failure_class=GraphQLFailureClass.NONE,
                    correlation_key=correlation_key,
                    correlation_mode=correlation.mode,
                    payload=MappingProxyType(retained_payload),
                    issues=tuple(operation_issues),
                    error_summary=None,
                )
            )
            continue

        validation = validate_page_views_payload(payload)
        if not validation.is_valid or validation.page_views is None:
            operation_results.append(
                _failed_operation_result(
                    operation_name,
                    validation.failure_class,
                    correlation_key=correlation_key,
                    mode=correlation.mode,
                    issues=validation.issues,
                )
            )
            continue
        operation_results.append(
            GraphQLOperationResult(
                operation_name=operation_name,
                status=OperationStatus.SUCCESS,
                failure_class=GraphQLFailureClass.NONE,
                correlation_key=correlation_key,
                correlation_mode=correlation.mode,
                payload=MappingProxyType({"pageViews": validation.page_views.value}),
                issues=(),
                error_summary=None,
            )
        )

    product_detail_result, page_views_result = operation_results
    return EnrichmentResult(
        asset_identity_key=request.asset_identity_key,
        correlation=correlation,
        product_detail=product_detail_result,
        page_views=page_views_result,
        http_status=response.http_status,
        attempts=attempts,
        response_sha256=hashlib.sha256(response.body_text.encode("utf-8")).hexdigest(),
        retry_metadata_json=json.dumps(
            {
                "attempts": attempts,
                "failure_classes": sorted(
                    {
                        result.failure_class.value
                        for result in operation_results
                        if result.failure_class is not GraphQLFailureClass.NONE
                    }
                ),
                "http_statuses": [response.http_status],
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        issues=issues,
    )


def _build_pre_exchange_result(
    request: GraphQLBatchRequest,
    failure_class: GraphQLFailureClass,
    *,
    attempts: int,
    http_status: int | None,
    response_sha256: str | None,
    correlation_mode: GraphQLOperationCorrelationMode,
    issues: tuple[ValidationIssue, ...],
    extra_correlation_issues: tuple[ValidationIssue, ...] = (),
) -> EnrichmentResult:
    """Build a typed failed result for an exchange that yielded no operation data."""
    correlation = correlate_operations((), mode=correlation_mode)
    if extra_correlation_issues:
        correlation = replace(
            correlation, issues=correlation.issues + extra_correlation_issues
        )
    operation_issues = issues if issues else correlation.issues
    product_detail = _failed_operation_result(
        PRODUCT_DETAIL_OPERATION_NAME,
        failure_class,
        mode=correlation_mode,
        issues=operation_issues,
    )
    page_views = _failed_operation_result(
        PRODUCT_PAGE_VIEWS_OPERATION_NAME,
        failure_class,
        mode=correlation_mode,
        issues=operation_issues,
    )
    return EnrichmentResult(
        asset_identity_key=request.asset_identity_key,
        correlation=correlation,
        product_detail=product_detail,
        page_views=page_views,
        http_status=http_status,
        attempts=attempts,
        response_sha256=response_sha256,
        retry_metadata_json=json.dumps(
            {
                "attempts": attempts,
                "failure_classes": (
                    []
                    if failure_class is GraphQLFailureClass.NONE
                    else [failure_class.value]
                ),
                "http_statuses": [] if http_status is None else [http_status],
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        issues=issues,
    )


def _interrogate_response(
    request: GraphQLBatchRequest,
    response: GraphQLBatchResponse,
    *,
    correlation_mode: GraphQLOperationCorrelationMode,
    attempts: int,
) -> EnrichmentResult:
    """Interpret one received response into a typed result, without raising."""
    items, decode_failure = _decode_operation_items(response)
    if items is None or decode_failure is not None:
        assert decode_failure is not None
        issue = _issue(
            "response_not_json",
            "the response body is not a JSON array of operation items",
            http_status=response.http_status,
        )
        return _build_pre_exchange_result(
            request,
            decode_failure,
            attempts=attempts,
            http_status=response.http_status,
            response_sha256=hashlib.sha256(
                response.body_text.encode("utf-8")
            ).hexdigest(),
            correlation_mode=correlation_mode,
            issues=(issue,),
        )

    correlation = correlate_operations(items, mode=correlation_mode)
    return _build_result_from_items(
        request,
        items,
        response,
        correlation,
        correlation.issues,
        attempts,
    )


def _interpret_response(
    request: GraphQLBatchRequest,
    response: GraphQLBatchResponse,
    *,
    correlation_mode: GraphQLOperationCorrelationMode,
    attempts: int,
) -> EnrichmentResult:
    """Interpret one received response, applying the non-200 classification.

    This is the single interpretation path shared by :func:`execute_graphql_batch`
    and :func:`interpret_graphql_response`, so the two callers cannot drift: a
    non-200 status is replaced by the failure class its status (and, for ``400``,
    its body marker) implies.
    """
    result = _interrogate_response(
        request, response, correlation_mode=correlation_mode, attempts=attempts
    )
    if result.http_status != 200:
        status_class = _classify_http_status(
            int(result.http_status), body_text=response.body_text
        )
        result = _with_both_operations_failed(
            result, status_class, response.http_status
        )
    return result


def _draft_from_result(
    result: EnrichmentResult, *, retrieved_at_utc: datetime
) -> EnrichmentObservationDraft:
    """Build the pre-record value for an interpreted result.

    The validated ``ProductDetailFields`` the adapter annotated onto a successful
    payload are reused when present; otherwise the draft re-validates the retained
    payload. ``retrieved_at_utc`` is the caller-supplied timestamp and is never
    read from the clock.
    """
    fields: ProductDetailFields | None = None
    if result.product_detail.is_success and result.product_detail.payload is not None:
        annotated = result.product_detail.payload.get("_annotated_fields")
        if isinstance(annotated, ProductDetailFields):
            fields = annotated
    return build_enrichment_observation_draft(
        result, fields=fields, retrieved_at_utc=retrieved_at_utc
    )


def interpret_graphql_response(
    request: GraphQLBatchRequest,
    response: GraphQLBatchResponse,
    *,
    correlation_mode: GraphQLOperationCorrelationMode,
    retrieved_at_utc: datetime,
    attempts: int = 1,
) -> tuple[EnrichmentResult, EnrichmentObservationDraft]:
    """Interpret one already-received response under ``correlation_mode``.

    The public face of the adapter's response interpretation: it correlates and
    validates the given response under ``correlation_mode``, applies the non-200
    classification, and returns the same ``(result, draft)`` pair
    ``enrich_asset`` returns. It performs no network exchange and reads no clock;
    ``attempts`` and ``retrieved_at_utc`` are supplied by the caller.
    ``retrieved_at_utc`` must be timezone-aware UTC (``models.ensure_utc``).

    Null/edge: a naive ``retrieved_at_utc`` raises ``ValueError``; ``attempts``
    below ``1`` or a non-integer raises ``ValueError``; a non-member
    ``correlation_mode`` raises ``TypeError``; a non-200 response takes the
    existing HTTP classification and both operation fields stay ``None``.
    """
    mode = _require_correlation_mode(correlation_mode)
    if isinstance(attempts, bool) or not isinstance(attempts, int) or attempts < 1:
        raise ValueError("attempts must be an integer >= 1")
    result = _interpret_response(
        request, response, correlation_mode=mode, attempts=attempts
    )
    return result, _draft_from_result(result, retrieved_at_utc=retrieved_at_utc)


def _failures_are_retryable(result: EnrichmentResult) -> bool:
    """Return whether a failed result's classes are all retryable."""
    classes = [
        operation.failure_class
        for operation in (result.product_detail, result.page_views)
        if operation.failure_class is not GraphQLFailureClass.NONE
    ]
    return bool(classes) and all(is_retryable(item) for item in classes)


def execute_graphql_batch(
    request: GraphQLBatchRequest,
    *,
    transport: GraphQLTransport,
    headers: Mapping[str, str],
    correlation_mode: GraphQLOperationCorrelationMode = (
        GraphQLOperationCorrelationMode.EXPLICIT_KEY
    ),
    policy: GraphQLRetryPolicy = GraphQLRetryPolicy(),
    sleep: Callable[[float], None] = time.sleep,
) -> EnrichmentResult:
    """Send one batch request, retrying only retryable failures, and never raise.

    At most ``policy.max_attempts`` attempts are made. Between attempts the
    injected ``sleep`` receives the return of :func:`retry_delay_seconds`. The
    last attempt's result is returned with ``attempts`` set to the number actually
    made. A raised transport is contained and classified as ``TRANSPORT_FAILURE``,
    so N identities are N independent calls and one failure cannot abort another.
    ``execute_graphql_batch`` never sleeps between separate ``enrich_asset`` calls;
    the caller looping over identities enforces the minimum interval by passing
    the same ``sleep``.

    ``correlation_mode`` is the mode every attempt correlates under; it is
    validated by :func:`_require_correlation_mode` (a non-member raises
    ``TypeError``) and is the mode each operation and ``correlation.mode`` report.
    Omitting the keyword reproduces the previous explicit-key behavior exactly
    (Chunk 18 A.1b; no post-hoc stamping exists on the result path).
    """
    active_mode = _require_correlation_mode(correlation_mode)
    if not callable(transport):
        raise TypeError("transport must be callable")
    if not callable(sleep):
        raise TypeError("sleep must be callable")
    if isinstance(policy.max_attempts, bool) or not isinstance(
        policy.max_attempts, int
    ):
        raise TypeError("policy.max_attempts must be an integer")
    if policy.max_attempts < 1:
        raise ValueError("policy.max_attempts must be at least 1")

    attempts = 0
    retry_after_attempt = 0
    while attempts < policy.max_attempts:
        attempts += 1
        try:
            response = transport(request, headers)
        except Exception as exc:  # contained: never escapes as an exception
            if attempts >= policy.max_attempts:
                return _build_pre_exchange_result(
                    request,
                    GraphQLFailureClass.TRANSPORT_FAILURE,
                    attempts=attempts,
                    http_status=None,
                    response_sha256=None,
                    correlation_mode=active_mode,
                    issues=(_summarize_transport_failure(exc),),
                )
            retry_after_attempt += 1
            sleep(retry_delay_seconds(policy, retry_after_attempt))
            continue

        result = _interpret_response(
            request,
            response,
            correlation_mode=active_mode,
            attempts=attempts,
        )

        if result.is_success or not _failures_are_retryable(result):
            return result
        if attempts >= policy.max_attempts:
            return result
        retry_after_attempt += 1
        sleep(retry_delay_seconds(policy, retry_after_attempt))

    raise AssertionError("unreachable: the attempt loop is bounded")


def _with_both_operations_failed(
    result: EnrichmentResult,
    failure_class: GraphQLFailureClass,
    http_status: int,
) -> EnrichmentResult:
    """Replace a non-200 exchange's results with the failure its status implies."""
    issue = _issue(
        "http_failure",
        "the response carried a non-200 HTTP status",
        http_status=http_status,
    )
    product_detail = _failed_operation_result(
        PRODUCT_DETAIL_OPERATION_NAME,
        failure_class,
        correlation_key=result.product_detail.correlation_key,
        mode=result.product_detail.correlation_mode,
        issues=(issue,),
    )
    page_views = _failed_operation_result(
        PRODUCT_PAGE_VIEWS_OPERATION_NAME,
        failure_class,
        correlation_key=result.page_views.correlation_key,
        mode=result.page_views.correlation_mode,
        issues=(issue,),
    )
    return replace(
        result,
        product_detail=product_detail,
        page_views=page_views,
        retry_metadata_json=json.dumps(
            {
                "attempts": result.attempts,
                "failure_classes": [failure_class.value],
                "http_statuses": [http_status],
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        issues=result.issues + (issue,),
    )


def enrich_asset(
    asset_identity_key: str,
    *,
    credentials: Credentials,
    transport: GraphQLTransport,
    correlation_mode: GraphQLOperationCorrelationMode,
    retrieved_at_utc: datetime,
    policy: GraphQLRetryPolicy = GraphQLRetryPolicy(),
    endpoint: str = GRAPHQL_BATCH_ENDPOINT,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[EnrichmentResult, EnrichmentObservationDraft]:
    """Enrich exactly one identity and return its result and its pre-record value.

    Both request-shape gates run here, so an unusable credential or identity
    raises before any network exchange. The function accepts no run id, writes
    nothing, and decides nothing about whether the call is allowed: it issues at
    most the two named operations for the one identity it is given.
    """
    mode = _require_correlation_mode(correlation_mode)
    request = build_graphql_batch_request(
        asset_identity_key, credentials=credentials, endpoint=endpoint
    )
    headers = build_graphql_headers(credentials=credentials)
    result = execute_graphql_batch(
        request,
        transport=transport,
        headers=headers,
        correlation_mode=mode,
        policy=policy,
        sleep=sleep,
    )
    draft = _draft_from_result(result, retrieved_at_utc=retrieved_at_utc)
    return result, draft
