"""Deterministic, offline fixtures for the Chunk 5 GraphQL protocol suite.

Everything here is local and hand-derived. No fixture contacts the network, reads
the system clock, or carries a real credential: ``tests/fixtures/README.md``
forbids all three, and the plan repeats it for this module — "No fixture contains
a credential value, a live response, or a clock-derived value"
(plan ``chunk-05`` line 1452).

**Scope: the contract leg only.** The plan freezes exactly one fixture leg for
this module, the hand-derived contract leg (plan lines 1414–1431). The
capture-derived golden leg is deferred out of Chunk 5's frozen scope by
``§12.3 O-2`` (plan lines 2165–2187): the operator supplied the five batch
captures as chat text and no capture file may be authored from it, so this module
ships no capture content and no ``tests/fixtures/captures/`` path is touched.

**Duplicate sequences.** ``operationName`` is the correlation key because
index-based association would be silently wrong: the captures show batch 1
carrying ``ServerTime`` twice, batch 4 carrying ``ServerTime`` seven times, and
batch 5 carrying ``AddToCartButton`` eight times (plan lines 687–688, repeated at
1852–1854). ``ProductPrice``, ``ProductReview``, ``Recommendations``,
``AddToCartButton``, ``CurrentUser``, ``ShoppingCartQuery``, and ``Publisher``
"are never batched with duplicates of themselves except ``AddToCartButton``
(batch 5, 8×), so the duplicate-handling path must be exercised on more than
``ServerTime``" (plan lines 1855–1858). :data:`DUPLICATE_SEQUENCE_CORPUS` is
built on exactly those two members. The sequences are hand-derived from the
captures' *structure* and are deliberately not framed as capture data.

**Identity.** ``CANONICAL_ASSET_ID`` is reused from ``fixtures.validation_fixtures``
rather than redefined, "so the request/response fixtures and the identity fixtures
agree on one identity string" (plan lines 1415–1417).

**Import discipline.** The adapter is imported for its public names only, and no
fixture value is derived from adapter internals: request bodies and correlation
keys are written out here precisely so a test can disagree with the adapter
instead of mirroring it.
"""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from fixtures.validation_fixtures import CANONICAL_ASSET_ID

from niche_scout import collector_graphql as gql
from niche_scout.config import Credentials
from niche_scout.models import (
    GraphQLOperationCorrelationMode,
    OperationStatus,
    PageViewSemanticsStatus,
)

__all__ = [
    "ADD_TO_CART_BUTTON_OPERATION_NAME",
    "CANONICAL_ASSET_ID",
    "CORRELATION_MODE_MEMBERS",
    "CORRELATION_MODE_UNVALIDATED_RESULT",
    "CREDENTIAL_FREE_CREDENTIALS",
    "CSRF_FAILURE_MESSAGE",
    "CSRF_MISMATCH_BODY",
    "CSRF_MISMATCH_CLASS",
    "DUPLICATE_SEQUENCE_BODIES",
    "DUPLICATE_SEQUENCE_CORPUS",
    "DUPLICATE_SEQUENCE_OPERATION_NAMES",
    "DUPLICATE_SEQUENCE_REQUIRED_REPEATS",
    "EXPECTED_OPERATIONS_HEADER",
    "EXPECTED_PRODUCT_DETAIL_REQUEST_OBJECT",
    "EXPECTED_PRODUCT_PAGE_VIEWS_REQUEST_OBJECT",
    "FOREIGN_OPERATION_NAMES",
    "GQL_CREDENTIALS",
    "GQL_FIXTURE_ASSET_ID",
    "GQL_FIXTURE_ASSET_ID_OTHER",
    "GQL_FIXTURE_CSRF_TOKEN",
    "GQL_OPERATION_NAMES",
    "IDENTITY_AGREEMENT_PRODUCT_DETAIL_PAYLOAD",
    "IDENTITY_MISMATCH_PRODUCT_DETAIL_PAYLOAD",
    "LREQ_GQL_040_FAILURE_CLASSES",
    "NON_FINITE_SCALAR_JSON",
    "OPERATION_STATUS_MEMBERS",
    "PAGE_VIEW_SCALAR_CASES",
    "PAGE_VIEW_SEMANTICS_STATUS_MEMBERS",
    "PER_FAILURE_CLASS_RESPONSES",
    "PERMANENT_FAILURE_RESPONSE",
    "PRODUCT_DETAIL_SELECTION_SET",
    "RecordingSleeper",
    "RecordingTransport",
    "RecordingTransportStatusOverride",
    "RETRY_SEQUENCE_429_THEN_200",
    "RETRY_SEQUENCE_RESPONSES",
    "SERVER_TIME_OPERATION_NAME",
    "TARGET_ASSET_DOCUMENT",
    "TRANSPORT_CALL_COUNTER_OPERATION_NAME",
    "TWO_OPERATION_BODY_JSON",
    "TWO_OPERATION_REVERSED_BODY_JSON",
    "ambiguous_correlation_body",
    "body_json_for_items",
    "correlation_body",
    "duplicated_correlation_body",
    "duplicated_page_views_correlation_body",
    "empty_body",
    "empty_response_body",
    "in_order_success_body",
    "invalid_state_body",
    "missing_correlation_key_body",
    "missing_identity_body",
    "missing_identity_member_body",
    "non_array_body",
    "non_integral_page_views_body",
    "non_json_body",
    "null_page_views_body",
    "null_product_body",
    "operation_errors_body",
    "partial_success_body",
    "product_detail_is_list_body",
    "product_detail_payload",
    "recording_call_counter_body",
    "reversed_order_success_body",
    "scalar_view_body",
    "single_item_body",
    "state_excluded_body",
    "target_asset_body",
    "three_item_body",
    "top_level_errors_body",
    "unknown_correlation_key_body",
    "validated_position_ordering_body",
]

# ---------------------------------------------------------------------------
# Identity and offline credential material
# ---------------------------------------------------------------------------

#: The identity every request fixture is built for. Reused from
#: ``fixtures.validation_fixtures`` (plan lines 1415–1417).
GQL_FIXTURE_ASSET_ID: str = CANONICAL_ASSET_ID

#: A second, distinct identifier, used only to provoke an identity mismatch.
GQL_FIXTURE_ASSET_ID_OTHER: str = "7654321"

#: Offline CSRF credential material. A fixture value, never a real credential.
GQL_FIXTURE_CSRF_TOKEN: str = "fixture-graphql-csrf-token"

#: The credential object every request/header fixture uses.
GQL_CREDENTIALS: Credentials = Credentials(
    coveo_token="fixture-coveo-token", unity_csrf_token=GQL_FIXTURE_CSRF_TOKEN
)

#: Process-local credentials with no CSRF token, for the credential gate.
CREDENTIAL_FREE_CREDENTIALS: Credentials = Credentials(
    coveo_token="fixture-coveo-token", unity_csrf_token=""
)


# ---------------------------------------------------------------------------
# Request goldens (plan sections 5.3, 6 line 1169, 9 lines 1417–1419)
# ---------------------------------------------------------------------------

#: The exact ``ProductDetail`` selection-set member list the request must carry
#: (plan lines 1419–1420): the two identity aliases plus the seven nested
#: members of ``PRODUCT_DETAIL_REQUIRED_MEMBERS``, and nothing else.
PRODUCT_DETAIL_SELECTION_SET: tuple[str, ...] = (
    "id",
    "productId",
    "rating.average",
    "rating.count",
    "reviewCount",
    "firstPublishedDate",
    "state",
    "category",
    "publisher",
)

#: The two operation names, in the order the ``operations`` header joins them.
GQL_OPERATION_NAMES: tuple[str, str] = (
    gql.PRODUCT_DETAIL_OPERATION_NAME,
    gql.PRODUCT_PAGE_VIEWS_OPERATION_NAME,
)

#: The per-operation JSON objects of the expected two-operation request body, as
#: required request GOLDENS. They are written out here rather than produced by
#: the adapter's builders (`build_graphql_batch_request` emits the same text) so
#: the request contract is asserted against the plan, not against itself. The
#: ``ProductDetail`` selection set is byte-identical to
#: ``PRODUCT_DETAIL_REQUIRED_MEMBERS`` in the plan's own order (requirement
#: statement ordering, not the rendered query's grouped order).
EXPECTED_PRODUCT_DETAIL_REQUEST_OBJECT: Mapping[str, Any] = {
    "operationName": "ProductDetail",
    "query": (
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
        "    category\n"
        "    publisher\n"
        "  }\n"
        "}"
    ),
    "variables": {"id": GQL_FIXTURE_ASSET_ID},
}

EXPECTED_PRODUCT_PAGE_VIEWS_REQUEST_OBJECT: Mapping[str, Any] = {
    "operationName": "ProductPageViews",
    "query": (
        "query ProductPageViews($packageId: String!) {\n"
        "  productPageViews(packageId: $packageId)\n"
        "}"
    ),
    "variables": {"packageId": GQL_FIXTURE_ASSET_ID},
}


def _request_object_json(operation_object: Mapping[str, Any]) -> str:
    """Return canonical JSON text for one request operation object."""
    return json.dumps(operation_object, sort_keys=True, separators=(",", ":"))


#: The expected two-operation ``body_json`` (plan lines 1417–1419): a JSON array
#: of exactly two objects, each with exactly ``query``, ``variables``,
#: ``operationName``. ``body_json`` is a sorted-key rendering, so the golden is
#: too; a JSON object is unordered by definition.
TWO_OPERATION_BODY_JSON: str = (
    "["
    + _request_object_json(EXPECTED_PRODUCT_DETAIL_REQUEST_OBJECT)
    + ","
    + _request_object_json(EXPECTED_PRODUCT_PAGE_VIEWS_REQUEST_OBJECT)
    + "]"
)

#: The same two operation objects in the reversed order.
TWO_OPERATION_REVERSED_BODY_JSON: str = (
    "["
    + _request_object_json(EXPECTED_PRODUCT_PAGE_VIEWS_REQUEST_OBJECT)
    + ","
    + _request_object_json(EXPECTED_PRODUCT_DETAIL_REQUEST_OBJECT)
    + "]"
)

#: The expected ``operations`` header value: the comma-joined operation names in
#: batch order (plan lines 1418–1419).
EXPECTED_OPERATIONS_HEADER: str = "ProductDetail,ProductPageViews"


# ---------------------------------------------------------------------------
# Foreign operations and the duplicate-sequence corpora
# ---------------------------------------------------------------------------

#: The two captured operations whose duplicate sequences are the substance of the
#: duplicate-handling requirement (plan lines 687–688, 1852–1858).
SERVER_TIME_OPERATION_NAME: str = "ServerTime"
ADD_TO_CART_BUTTON_OPERATION_NAME: str = "AddToCartButton"

#: The replay corpus's two members, in the order the plan names them.
DUPLICATE_SEQUENCE_OPERATION_NAMES: tuple[str, str] = (
    SERVER_TIME_OPERATION_NAME,
    ADD_TO_CART_BUTTON_OPERATION_NAME,
)

#: How many times the captures repeat each duplicate-sequence member. Both counts
#: are required golden values (plan lines 687–688).
DUPLICATE_SEQUENCE_REQUIRED_REPEATS: Mapping[str, int] = {
    SERVER_TIME_OPERATION_NAME: 7,
    ADD_TO_CART_BUTTON_OPERATION_NAME: 8,
}

#: Operations the adapter never issues. An item carrying one of these names is
#: reported as unassociated and is never attached to another operation.
FOREIGN_OPERATION_NAMES: tuple[str, ...] = (
    SERVER_TIME_OPERATION_NAME,
    ADD_TO_CART_BUTTON_OPERATION_NAME,
    "ProductPrice",
    "ProductReview",
    "Recommendations",
    "CurrentUser",
    "ShoppingCartQuery",
    "Publisher",
)

#: The document identifier of the two operations the adapter issues.
TARGET_ASSET_DOCUMENT: Mapping[str, Any] = {
    "id": GQL_FIXTURE_ASSET_ID,
    "productId": GQL_FIXTURE_ASSET_ID,
}


# ---------------------------------------------------------------------------
# ProductDetail payloads (plan sections 5.7, 9 lines 1436–1447)
# ---------------------------------------------------------------------------


def product_detail_payload(
    asset_identity_key: str = GQL_FIXTURE_ASSET_ID,
    *,
    rating_average: object = 4.5,
    rating_count: object = 210,
    review_count: object = 34,
    state: object = "published",
    category: object = "Tools/Level Design/Tilemap",
    publisher: object = "Fixture Publisher",
) -> dict[str, Any]:
    """Return a valid ``ProductDetail`` payload for ``asset_identity_key``.

    Both identity aliases are populated and agree with the requested identity, so
    the payload validates and carries no identity mismatch. Every member
    ``PRODUCT_DETAIL_REQUIRED_MEMBERS`` names is present.
    """
    return {
        "id": asset_identity_key,
        "productId": asset_identity_key,
        "rating": {"average": rating_average, "count": rating_count},
        "reviewCount": review_count,
        "firstPublishedDate": "2019-03-04T12:30:00Z",
        "state": state,
        "category": category,
        "publisher": publisher,
    }


#: A payload whose returned aliases agree with the requested identity.
IDENTITY_AGREEMENT_PRODUCT_DETAIL_PAYLOAD: dict[str, Any] = product_detail_payload()

#: A payload whose returned aliases disagree with the requested identity: the
#: requested identity is ``GQL_FIXTURE_ASSET_ID`` while both aliases carry
#: ``GQL_FIXTURE_ASSET_ID_OTHER``.
IDENTITY_MISMATCH_PRODUCT_DETAIL_PAYLOAD: dict[str, Any] = product_detail_payload(
    GQL_FIXTURE_ASSET_ID_OTHER
)


def _duplicate_sequence_corpus(
    repeats: int, foreign: str
) -> tuple[dict[str, Any], ...]:
    """Return a corpus replaying one capture's duplicate sequence.

    ``foreign`` is repeated ``repeats`` times — the repetition is what makes index
    association wrong — and the adapter's own two operations appear once each, so
    the corpus also carries real data for both.
    """
    items: list[dict[str, Any]] = []
    for index in range(repeats):
        if foreign == SERVER_TIME_OPERATION_NAME:
            # A minimal but structurally faithful foreign envelope: the batched
            # operation's own key holds a string.
            data: Mapping[str, Any] = {"serverTime": f"fixture-{index}"}
        else:
            data = {"count": index}
        items.append({"operationName": foreign, "data": data})
    items.append(
        {
            "operationName": gql.PRODUCT_DETAIL_OPERATION_NAME,
            "data": product_detail_payload(),
        }
    )
    items.append(
        {
            "operationName": gql.PRODUCT_PAGE_VIEWS_OPERATION_NAME,
            "data": {"pageViews": 4321},
        }
    )
    return tuple(items)


#: The required duplicate sequences (plan lines 1852–1858). Each corpus repeats a
#: single foreign operation — the foreign repeats are left unassociated and no
#: issued operation is itself duplicated, because neither issued operation is
#: ever batched with a duplicate of itself.
DUPLICATE_SEQUENCE_CORPUS: Mapping[str, tuple[dict[str, Any], ...]] = {
    "server_time_7x": _duplicate_sequence_corpus(7, SERVER_TIME_OPERATION_NAME),
    "add_to_cart_button_8x": _duplicate_sequence_corpus(
        8, ADD_TO_CART_BUTTON_OPERATION_NAME
    ),
}

#: The same two sequences as canonical JSON bodies.
DUPLICATE_SEQUENCE_BODIES: Mapping[str, str] = {
    name: json.dumps(list(items), sort_keys=True, separators=(",", ":"))
    for name, items in DUPLICATE_SEQUENCE_CORPUS.items()
}



# ---------------------------------------------------------------------------
# Page-view scalars (plan sections 5.8, 9 lines 1442–1444)
# ---------------------------------------------------------------------------

#: Every page-view scalar case the plan enumerates (line 1443), with the
#: acceptance the adapter must produce. ``expected_page_views`` is ``None``
#: whenever the case is rejected, because a rejection never yields a ``0``
#: (plan lines 1686–1689). ``bool`` is rejected *before* any numeric test.
PAGE_VIEW_SCALAR_CASES: tuple[Mapping[str, Any], ...] = (
    {"case": "zero", "scalar": 0, "expected_page_views": 0, "expected_class": "NONE"},
    {
        "case": "negative",
        "scalar": -1,
        "expected_page_views": None,
        "expected_class": "INVALID_PAGE_VIEWS",
    },
    {
        "case": "true",
        "scalar": True,
        "expected_page_views": None,
        "expected_class": "WRONG_SCALAR_TYPE",
    },
    {
        "case": "false",
        "scalar": False,
        "expected_page_views": None,
        "expected_class": "WRONG_SCALAR_TYPE",
    },
    {
        "case": "non_integral_1_5",
        "scalar": 1.5,
        "expected_page_views": None,
        "expected_class": "INVALID_PAGE_VIEWS",
    },
    {
        "case": "integral_float_1_0",
        "scalar": 1.0,
        "expected_page_views": 1,
        "expected_class": "NONE",
    },
    {
        "case": "string_12",
        "scalar": "12",
        "expected_page_views": None,
        "expected_class": "WRONG_SCALAR_TYPE",
    },
    {
        "case": "empty_list",
        "scalar": [],
        "expected_page_views": None,
        "expected_class": "WRONG_DATA_SHAPE",
    },
    {
        "case": "empty_mapping",
        "scalar": {},
        "expected_page_views": None,
        "expected_class": "WRONG_DATA_SHAPE",
    },
    {
        "case": "null",
        "scalar": None,
        "expected_page_views": None,
        "expected_class": "NULL_REQUIRED_DATA",
    },
    {
        "case": "nan",
        "scalar": float("nan"),
        "expected_page_views": None,
        "expected_class": "INVALID_PAGE_VIEWS",
    },
    {
        "case": "infinity",
        "scalar": float("inf"),
        "expected_page_views": None,
        "expected_class": "INVALID_PAGE_VIEWS",
    },
    {
        "case": "negative_infinity",
        "scalar": float("-inf"),
        "expected_page_views": None,
        "expected_class": "INVALID_PAGE_VIEWS",
    },
)

#: The bare JSON token a non-finite scalar arrives as. ``json.dumps`` renders
#: these non-standard tokens and ``json.loads`` decodes them, so a hand-derived
#: response body must carry the same spelling the wire does.
NON_FINITE_SCALAR_JSON: Mapping[str, str] = {"nan": "NaN", "infinity": "Infinity"}


def _render_scalar(scalar: object) -> str:
    """Return the JSON text of one scalar, including the non-finite tokens."""
    if isinstance(scalar, float):
        if scalar != scalar:
            return NON_FINITE_SCALAR_JSON["nan"]
        if scalar == float("inf"):
            return NON_FINITE_SCALAR_JSON["infinity"]
        if scalar == float("-inf"):
            return "-" + NON_FINITE_SCALAR_JSON["infinity"]
    return json.dumps(scalar, sort_keys=True, separators=(",", ":"))


def scalar_view_body(scalar: object) -> str:
    """Return a two-operation body whose ``ProductPageViews`` scalar is ``scalar``.

    The body is composed from text so a non-finite scalar is spelled the way the
    wire spells it, and the sibling ``ProductDetail`` item is a valid payload, so
    the only failing operation is the page-view one.
    """
    detail = json.dumps(
        product_detail_payload(), sort_keys=True, separators=(",", ":")
    )
    return (
        '[{"data":'
        + detail
        + ',"operationName":"ProductDetail"},'
        + '{"data":{"pageViews":'
        + _render_scalar(scalar)
        + '},"operationName":"ProductPageViews"}]'
    )


def null_page_views_body() -> str:
    """Return a body whose ``ProductPageViews`` scalar is JSON ``null``."""
    return scalar_view_body(None)


def non_integral_page_views_body() -> str:
    """Return a body whose ``ProductPageViews`` scalar is the float ``1.5``."""
    return scalar_view_body(1.5)


# ---------------------------------------------------------------------------
# Hand-derived response bodies (plan lines 1436–1447)
# ---------------------------------------------------------------------------


def body_json_for_items(items: Sequence[object]) -> str:
    """Return canonical JSON text for a sequence of response items."""
    return json.dumps(list(items), sort_keys=True, separators=(",", ":"))


def correlation_body(*items: Mapping[str, object]) -> str:
    """Return a canonical body for the given correlation items, in order."""
    return body_json_for_items(list(items))


def target_asset_body() -> str:
    """Return the in-order two-operation body carrying the golden document."""
    return correlation_body(
        {
            "operationName": gql.PRODUCT_DETAIL_OPERATION_NAME,
            "data": product_detail_payload(),
        },
        {
            "operationName": gql.PRODUCT_PAGE_VIEWS_OPERATION_NAME,
            "data": {"pageViews": 4321},
        },
    )


def in_order_success_body() -> str:
    """Return the in-order success body: ``ProductDetail``, then page views."""
    return target_asset_body()


def reversed_order_success_body() -> str:
    """Return the same two items as :func:`in_order_success_body`, order swapped."""
    return correlation_body(
        {
            "operationName": gql.PRODUCT_PAGE_VIEWS_OPERATION_NAME,
            "data": {"pageViews": 4321},
        },
        {
            "operationName": gql.PRODUCT_DETAIL_OPERATION_NAME,
            "data": product_detail_payload(),
        },
    )


def single_item_body() -> str:
    """Return a one-item body: ``ProductDetail`` only, page views missing."""
    return correlation_body(
        {
            "operationName": gql.PRODUCT_DETAIL_OPERATION_NAME,
            "data": product_detail_payload(),
        }
    )


def three_item_body() -> str:
    """Return a three-item body: both issued operations plus one foreign item."""
    return correlation_body(
        {
            "operationName": gql.PRODUCT_DETAIL_OPERATION_NAME,
            "data": product_detail_payload(),
        },
        {"operationName": SERVER_TIME_OPERATION_NAME, "data": {"serverTime": "fixture"}},
        {
            "operationName": gql.PRODUCT_PAGE_VIEWS_OPERATION_NAME,
            "data": {"pageViews": 4321},
        },
    )


def duplicated_correlation_body() -> str:
    """Return a body carrying the ``ProductDetail`` correlation key twice."""
    return correlation_body(
        {
            "operationName": gql.PRODUCT_DETAIL_OPERATION_NAME,
            "data": product_detail_payload(),
        },
        {
            "operationName": gql.PRODUCT_DETAIL_OPERATION_NAME,
            "data": product_detail_payload(),
        },
        {
            "operationName": gql.PRODUCT_PAGE_VIEWS_OPERATION_NAME,
            "data": {"pageViews": 4321},
        },
    )


def duplicated_page_views_correlation_body() -> str:
    """Return a body carrying the ``ProductPageViews`` correlation key twice."""
    return correlation_body(
        {
            "operationName": gql.PRODUCT_PAGE_VIEWS_OPERATION_NAME,
            "data": {"pageViews": 4321},
        },
        {
            "operationName": gql.PRODUCT_PAGE_VIEWS_OPERATION_NAME,
            "data": {"pageViews": 4321},
        },
        {
            "operationName": gql.PRODUCT_DETAIL_OPERATION_NAME,
            "data": product_detail_payload(),
        },
    )


def unknown_correlation_key_body() -> str:
    """Return a body whose item carries a key naming no issued operation."""
    return correlation_body(
        {
            "operationName": SERVER_TIME_OPERATION_NAME,
            "data": {"serverTime": "fixture"},
        },
        {
            "operationName": gql.PRODUCT_DETAIL_OPERATION_NAME,
            "data": product_detail_payload(),
        },
    )


def missing_correlation_key_body() -> str:
    """Return a body whose page-view item carries no correlation key at all."""
    return correlation_body(
        {
            "operationName": gql.PRODUCT_DETAIL_OPERATION_NAME,
            "data": product_detail_payload(),
        },
        {"data": {"pageViews": 4321}},
    )


def validated_position_ordering_body() -> str:
    """Return a keyed body that cannot present the validated two-operation order."""
    return single_item_body()


def ambiguous_correlation_body() -> str:
    """Return a body whose correlation is ambiguous: a lone issued item."""
    return single_item_body()


def empty_response_body() -> str:
    """Return an empty JSON array: nothing to correlate."""
    return "[]"


def empty_body() -> str:
    """Return an empty body, which decodes to no operation items."""
    return ""


def non_json_body() -> str:
    """Return a body that is not JSON text at all."""
    return "not json"


def non_array_body() -> str:
    """Return a JSON body that is not an array of operation items."""
    return '{"operationName": "ProductDetail"}'


def top_level_errors_body() -> str:
    """Return a 200 body carrying a top-level ``errors`` member."""
    return correlation_body(
        {
            "operationName": gql.PRODUCT_DETAIL_OPERATION_NAME,
            "data": product_detail_payload(),
            "errors": [{"message": "fixture top-level failure"}],
        },
        {
            "operationName": gql.PRODUCT_PAGE_VIEWS_OPERATION_NAME,
            "data": {"pageViews": 4321},
        },
    )


def operation_errors_body() -> str:
    """Return a 200 body carrying operation-level ``errors`` only."""
    return correlation_body(
        {
            "operationName": gql.PRODUCT_DETAIL_OPERATION_NAME,
            "data": {"errors": [{"message": "fixture operation failure"}]},
        },
        {
            "operationName": gql.PRODUCT_PAGE_VIEWS_OPERATION_NAME,
            "data": {"pageViews": 4321},
        },
    )


def partial_success_body() -> str:
    """Return a body where ``ProductDetail`` errors and page views succeed."""
    return operation_errors_body()


def null_product_body() -> str:
    """Return a body whose ``ProductDetail`` data is ``null``."""
    return correlation_body(
        {"operationName": gql.PRODUCT_DETAIL_OPERATION_NAME, "data": None},
        {
            "operationName": gql.PRODUCT_PAGE_VIEWS_OPERATION_NAME,
            "data": {"pageViews": 4321},
        },
    )


def product_detail_is_list_body() -> str:
    """Return a body whose ``ProductDetail`` payload is a JSON list."""
    return correlation_body(
        {
            "operationName": gql.PRODUCT_DETAIL_OPERATION_NAME,
            "data": [product_detail_payload()],
        },
        {
            "operationName": gql.PRODUCT_PAGE_VIEWS_OPERATION_NAME,
            "data": {"pageViews": 4321},
        },
    )


def state_excluded_body() -> str:
    """Return a body whose ``state`` is present but not ``published``."""
    return correlation_body(
        {
            "operationName": gql.PRODUCT_DETAIL_OPERATION_NAME,
            "data": product_detail_payload(state="deprecated"),
        },
        {
            "operationName": gql.PRODUCT_PAGE_VIEWS_OPERATION_NAME,
            "data": {"pageViews": 4321},
        },
    )


def invalid_state_body() -> str:
    """Return a body whose ``state`` value is present but not a usable string."""
    return correlation_body(
        {
            "operationName": gql.PRODUCT_DETAIL_OPERATION_NAME,
            "data": product_detail_payload(state=17),
        },
        {
            "operationName": gql.PRODUCT_PAGE_VIEWS_OPERATION_NAME,
            "data": {"pageViews": 4321},
        },
    )


def missing_identity_member_body() -> str:
    """Return a body whose payload omits the required identity alias itself."""
    payload = product_detail_payload()
    del payload["id"]
    return correlation_body(
        {"operationName": gql.PRODUCT_DETAIL_OPERATION_NAME, "data": payload},
        {
            "operationName": gql.PRODUCT_PAGE_VIEWS_OPERATION_NAME,
            "data": {"pageViews": 4321},
        },
    )


def missing_identity_body() -> str:
    """Return a body whose payload populates no identity alias at all.

    Both aliases are present as required members but carry JSON ``null``, which
    is what makes this a *missing identity* rather than a *missing member*: an
    absent alias fails the required-member check first.
    """
    payload = product_detail_payload()
    payload["id"] = None
    payload["productId"] = None
    return correlation_body(
        {"operationName": gql.PRODUCT_DETAIL_OPERATION_NAME, "data": payload},
        {
            "operationName": gql.PRODUCT_PAGE_VIEWS_OPERATION_NAME,
            "data": {"pageViews": 4321},
        },
    )


def csr_fixture_marker() -> str:
    """Return the fixture-only marker used to label a CSRF response body."""
    return "fixture-csrf-mismatch"


#: The message a CSRF-mismatch body carries. The adapter classifies the *code*
#: ``csrf`` in ``extensions``, at 200 (plan lines 1791–1809).
CSRF_FAILURE_MESSAGE: str = "csrf token invalid"


def _csrf_mismatch_item() -> Mapping[str, object]:
    """Return the ``ProductDetail`` item of the fixture CSRF-mismatch body."""
    return {
        "operationName": gql.PRODUCT_DETAIL_OPERATION_NAME,
        "data": None,
        "errors": [
            {"message": CSRF_FAILURE_MESSAGE, "extensions": {"code": "csrf"}},
        ],
    }


#: A CSRF-mismatch body: a top-level ``errors`` member whose code is ``csrf``.
CSRF_MISMATCH_BODY: str = correlation_body(
    _csrf_mismatch_item(),
    {"operationName": gql.PRODUCT_PAGE_VIEWS_OPERATION_NAME, "data": None},
)

#: The failure class a CSRF-mismatch body must be classified as.
CSRF_MISMATCH_CLASS: str = "CSRF_FAILURE"


# ---------------------------------------------------------------------------
# Per-failure-class responses (plan lines 1439–1442)
# ---------------------------------------------------------------------------


def _transport_response(
    http_status: int, body_text: str, *header_names: str
) -> dict[str, Any]:
    """Return a transport-shaped response mapping for one HTTP exchange."""
    return {
        "http_status": http_status,
        "body_text": body_text,
        "header_names": tuple(header_names),
    }


#: One response per failure class the plan enumerates (plan lines 1439–1442).
#: Each value is a transport-shaped mapping a
#: :class:`RecordingTransport` returns verbatim, so a test names the class it
#: intends to exercise instead of re-deriving the body inline.
PER_FAILURE_CLASS_RESPONSES: Mapping[str, Mapping[str, Any]] = {
    # --- HTTP status families ------------------------------------------------
    "http_429": _transport_response(429, "fixture rate limited", "retry-after"),
    "http_500": _transport_response(500, "fixture server error"),
    "http_502": _transport_response(502, "fixture bad gateway"),
    "http_503": _transport_response(503, "fixture service unavailable"),
    "http_504": _transport_response(504, "fixture gateway timeout"),
    "http_400_malformed_request": _transport_response(
        400, '{"errors":[{"message":"fixture malformed request"}]}'
    ),
    "http_401_authentication_failure": _transport_response(
        401, '{"errors":[{"message":"fixture unauthenticated"}]}'
    ),
    "http_403_authorization_failure": _transport_response(
        403, '{"errors":[{"message":"fixture forbidden"}]}'
    ),
    "http_404_http_permanent": _transport_response(
        404, '{"errors":[{"message":"fixture not found"}]}'
    ),
    # --- 200 with a CSRF mismatch -------------------------------------------
    #: The CSRF body is classified at 200, where the top-level ``errors`` member
    #: reaches ``_classify_top_level_errors``.
    "http_200_csrf_failure": _transport_response(200, CSRF_MISMATCH_BODY),
    # --- 200 operation and payload failures ---------------------------------
    "http_200_top_level_error": _transport_response(200, top_level_errors_body()),
    "http_200_operation_error": _transport_response(200, operation_errors_body()),
    "http_200_null_required_data": _transport_response(200, null_product_body()),
    "http_200_wrong_data_shape": _transport_response(200, product_detail_is_list_body()),
    "http_200_wrong_scalar_type": _transport_response(200, scalar_view_body("12")),
    "http_200_invalid_page_views": _transport_response(200, scalar_view_body(-1)),
    "http_200_missing_identity": _transport_response(200, missing_identity_body()),
    "http_200_invalid_state_value": _transport_response(200, invalid_state_body()),
    "http_200_response_not_json": _transport_response(200, non_json_body()),
    "http_200_empty_body": _transport_response(200, empty_body()),
    "http_200_no_correlation": _transport_response(200, empty_response_body()),
}

#: The retry sequence the plan names: a 500 then a 200 (line 1440).
#: Served in order by a single :class:`RecordingTransport`.
RETRY_SEQUENCE_RESPONSES: tuple[Mapping[str, Any], ...] = (
    PER_FAILURE_CLASS_RESPONSES["http_500"],
    _transport_response(200, in_order_success_body()),
)

#: The same shape with the transient failure rendered as a 429.
RETRY_SEQUENCE_429_THEN_200: tuple[Mapping[str, Any], ...] = (
    PER_FAILURE_CLASS_RESPONSES["http_429"],
    _transport_response(200, in_order_success_body()),
)

#: A permanent failure, which must not be retried at all.
PERMANENT_FAILURE_RESPONSE: Mapping[str, Any] = PER_FAILURE_CLASS_RESPONSES[
    "http_400_malformed_request"
]


# ---------------------------------------------------------------------------
# Typed vocabularies (plan section 3, 11 lines 1686–1700)
# ---------------------------------------------------------------------------

#: The two persisted correlation modes. ``EXCLUDED``/``CANDIDATE`` are **not**
#: members: they are adapter-local (plan lines 1863–1876), and no fixture may
#: present one as a correlation mode.
CORRELATION_MODE_MEMBERS: tuple[GraphQLOperationCorrelationMode, ...] = (
    GraphQLOperationCorrelationMode.EXPLICIT_KEY,
    GraphQLOperationCorrelationMode.VALIDATED_POSITION,
)

#: A replacement correlation result carrying the *unpersisted* mode, produced
#: through ``dataclasses.replace`` so an adapter that validated its mode argument
#: cannot have produced it. A test can therefore assert that an unpersisted mode
#: fails the result's own mode validation instead of assuming it is caught.
CORRELATION_MODE_UNVALIDATED_RESULT: Mapping[str, Any] = {
    "mode_value": f"{GraphQLOperationCorrelationMode.EXPLICIT_KEY.value}_fixture_unvalidated",
    "build": "dataclasses.replace(result.correlation, mode=<unknown mode>)",
}

#: The two operation statuses.
OPERATION_STATUS_MEMBERS: tuple[str, ...] = (
    OperationStatus.SUCCESS.value,
    OperationStatus.ERROR.value,
)

#: Every ``PageViewSemanticsStatus`` member, pinned so no fixture can claim a
#: run-level status: Chunk 6A initializes it and Chunk 7B detects ``contradicted``
#: (plan lines 1694–1700).
PAGE_VIEW_SEMANTICS_STATUS_MEMBERS: tuple[str, ...] = tuple(
    member.value for member in PageViewSemanticsStatus
)

#: Every ``LREQ-GQL-040`` operation-error class the adapter models, by the
#: adapter's own member names. A fixture asserting one of these must fail the
#: affected operation; none may be represented as a zero-valued success.
LREQ_GQL_040_FAILURE_CLASSES: tuple[str, ...] = (
    "CSRF_FAILURE",
    "MALFORMED_REQUEST",
    "AUTHENTICATION_FAILURE",
    "AUTHORIZATION_FAILURE",
    "GRAPHQL_TOP_LEVEL_ERROR",
    "OPERATION_ERROR",
    "NULL_REQUIRED_DATA",
    "WRONG_DATA_SHAPE",
    "WRONG_SCALAR_TYPE",
    "INVALID_PAGE_VIEWS",
    "INVALID_STATE_VALUE",
    "MISSING_IDENTITY",
    "RESPONSE_NOT_JSON",
)


# ---------------------------------------------------------------------------
# The recording fake transport and fake sleeper (plan lines 1448–1451)
# ---------------------------------------------------------------------------

#: The operation name the call-counter seam looks for in a decoded request body.
TRANSPORT_CALL_COUNTER_OPERATION_NAME: str = "FixtureCallCounter"


class _RecordingTransportBase:
    """Shared recording and response-materialization for the fake transports."""

    def __init__(
        self,
        responses: Sequence[object],
        *,
        status_override: int | None = None,
    ) -> None:
        self._responses: tuple[object, ...] = tuple(responses)
        self._status_override = status_override
        #: One ``(request, headers)`` pair per call, in call order.
        self.calls: list[tuple[Any, Mapping[str, str]]] = []
        #: The status each queued response declared, per call.
        self.statuses_declared: list[int] = []

    def _record(self, request: Any, headers: Mapping[str, str]) -> tuple[Any, Mapping[str, str]]:
        """Record one ``(request, headers)`` call pair, in call order."""
        pair = (request, headers)
        self.calls.append(pair)
        return pair

    @property
    def call_count(self) -> int:
        """Return how many times the transport was called."""
        return len(self.calls)

    @property
    def requested_identities(self) -> tuple[str, ...]:
        """Return the ``asset_identity_key`` of each call, in call order."""
        return tuple(
            str(getattr(request, "asset_identity_key", ""))
            for request, _ in self.calls
        )

    @property
    def total_sleep_free_calls(self) -> int:
        """Return the call count, named for readability in retry assertions."""
        return len(self.calls)

    def _next(self) -> object:
        """Return the next queued response, raising it if it is an exception."""
        index = len(self.statuses_declared)
        if index >= len(self._responses):
            raise AssertionError(
                "RecordingTransport ran out of queued responses: "
                "the adapter made more attempts than the fixture expects"
            )
        queued = self._responses[index]
        if isinstance(queued, BaseException):
            raise queued
        return queued

    def _materialize(self, queued: object) -> gql.GraphQLBatchResponse:
        """Return the ``GraphQLBatchResponse`` for one queued value."""
        if isinstance(queued, gql.GraphQLBatchResponse):
            declared = queued.http_status
            body_text = queued.body_text
            header_names = queued.header_names
        else:
            if not isinstance(queued, Mapping):
                raise TypeError("queued responses must be mappings or exceptions")
            declared = int(queued.get("http_status", 200))
            body_text = str(queued.get("body_text", ""))
            header_names = tuple(queued.get("header_names", ()))
        self.statuses_declared.append(declared)
        if self._status_override is not None:
            declared = self._status_override
        return gql.GraphQLBatchResponse(
            http_status=declared,
            body_text=body_text,
            header_names=header_names,
        )


class RecordingTransport(_RecordingTransportBase):
    """A fake ``GraphQLTransport`` returning queued responses in order.

    Constructed with a sequence of transport-shaped mappings (each with
    ``http_status``, ``body_text`` and optional ``header_names``) or with
    ``GraphQLBatchResponse`` values, or with exception instances to raise. Every
    call is recorded in :attr:`calls` as ``(request, headers)``.

    A response's declared status is what the adapter classifies: the fake makes
    no attempt to keep a catch-all status in reserve, because the adapter's retry
    budget is what bounds the attempts (``DEFAULT_MAX_ATTEMPTS``). ``http_status``
    in a *transport-shaped* mapping is therefore the effective status, and
    :attr:`statuses_declared` is what it was.

    :class:`RecordingTransportStatusOverride` exists for the one case where a
    test needs the effective status to differ from the declared one.
    """

    def __call__(self, request: Any, headers: Mapping[str, str]) -> gql.GraphQLBatchResponse:
        """Return the next queued response, or raise the next queued exception."""
        self._record(request, headers)
        return self._materialize(self._next())


class RecordingTransportStatusOverride(_RecordingTransportBase):
    """A :class:`RecordingTransport` whose effective status is forced.

    Used where two runs must differ only in the HTTP status the adapter
    classifies while the response body is held identical — for example a CSRF
    body served under two different statuses, where the body decides at 200 and
    the status decides at the HTTP-status split.
    """

    def __call__(self, request: Any, headers: Mapping[str, str]) -> gql.GraphQLBatchResponse:
        """Return the next queued response with the forced effective status."""
        self._record(request, headers)
        return self._materialize(self._next())


class RecordingSleeper:
    """A fake ``sleep`` callable recording every duration it is handed.

    No fixture reads the system clock: the delays a real sleeper would incur are
    asserted from :attr:`durations`, which is recorded, never waited.
    """

    def __init__(self) -> None:
        self.durations: list[float] = []

    @property
    def call_count(self) -> int:
        """Return how many times ``sleep`` was called."""
        return len(self.durations)

    @property
    def total(self) -> float:
        """Return the sum of every recorded duration."""
        return float(sum(self.durations))

    def __call__(self, duration: float) -> None:
        """Record ``duration`` and return without waiting."""
        self.durations.append(float(duration))


def recording_call_counter_body(counter: int) -> str:
    """Return a body that records the transport call number.

    Used with a transport whose responses are written from
    :data:`TRANSPORT_CALL_COUNTER_OPERATION_NAME`; the counter is what lets an
    N-asset loop assert it called the transport exactly N times.
    """
    return body_json_for_items(
        [{"operationName": TRANSPORT_CALL_COUNTER_OPERATION_NAME, "counter": counter}]
    )
