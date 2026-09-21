"""Inert fixtures and hand-derived vectors for chunk 6A identity preflight.

Data and factory functions only: this module contains no assertions and no logic
under test, so a defect in it cannot mask a preflight, gate, persistence, or
redaction defect.

Sources:
- ``Documents/SRS-lean.md`` §4.4 (``LREQ-ID-010``/``020``/``030``/``040``,
  lines 354-414).
- ``Documents/plans/chunk-6A-identity-preflight-planner-and-gate.md`` §5
  (interface contract) and §9 (test plan, golden vectors).
- ``Documents/interfaces/chunk-6A.md`` (frozen public contract).
- ``Documents/interfaces/chunk-05.md`` §5.4/§5.9 (``EnrichmentResult`` and
  ``EnrichmentObservationDraft`` field sets) and §5.11 (transport type),
  ``chunk-4A.md`` (``select_run_sample``), ``chunk-02.md``
  (``SqliteRepository``).

No credential is real and none is stored: the credential literals are non-secret
fixture strings. No network, no clock read, no file I/O, no ``sqlite3``.
Datetimes are fixed aware-UTC literals, never ``now()``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from fixtures.graphql_fixtures import GQL_CREDENTIALS
from niche_scout import sampling
from niche_scout.collector_graphql import (
    PRODUCT_DETAIL_OPERATION_NAME,
    PRODUCT_PAGE_VIEWS_OPERATION_NAME,
)
from niche_scout.config import Credentials
from niche_scout.models import (
    DiscoveryStatus,
    GraphQLOperationCorrelationMode,
    OperationStatus,
    RunRecord,
)

__all__ = [
    "A",
    "ATTEMPTED_BOUNDARY_GOLDEN",
    "ATTEMPTED_CONFLICT_GOLDEN",
    "ATTEMPTED_DENOMINATOR_GOLDEN",
    "ATTEMPTED_OTHER_FAILED_GOLDEN",
    "ATTEMPTED_ZERO_GOLDEN",
    "B",
    "C",
    "CANONICAL_ENDPOINT_SIGNATURE",
    "CATEGORIES_PATH",
    "CATEGORY_A",
    "CATEGORY_B",
    "CATEGORY_C",
    "CATEGORY_D",
    "CATEGORY_E",
    "CATEGORY_F",
    "CORRELATION_MODE",
    "Credentials",
    "D",
    "DB_PATH",
    "DIAGNOSTIC_COUNTS_GOLDEN",
    "DISTINCT_KEY",
    "E_KEY",
    "ENDPOINT_CONTRACT_VERSION_FIXTURE",
    "EXPLICIT_KEY",
    "F",
    "FAILURE_MODES",
    "FOREIGN_OPERATION_NAME",
    "FailingTransport",
    "GQL_CREDENTIALS",
    "GRAPHQL_BATCH_ENDPOINT",
    "INVALID_STATE_VALUE",
    "MALFORMED_REQUEST",
    "MISSING_IDENTITY",
    "NULL_REQUIRED_DATA",
    "PRODUCT_DETAIL_CATEGORY_JSON",
    "PRODUCT_DETAIL_PUBLISHER_JSON",
    "PRODUCT_DETAIL_OPERATION_NAME",
    "PRODUCT_PAGE_VIEWS_OPERATION_NAME",
    "RECORD_REDACTION_FORBIDDEN",
    "REDACTION_CREDENTIALS",
    "RETRIEVED_AT_UTC",
    "RUN_ID",
    "RecordingTransport",
    "SHARED",
    "SUM_FOUR_KEYS_JSON",
    "SUMMARY_KEY_SET",
    "TAXONOMY_PATH",
    "TRANSPORT_FAILURE",
    "VALIDATED_POSITION",
    "WRONG_DATA_SHAPE",
    "WRONG_SCALAR_TYPE",
    "census_three_run",
    "collision_transport",
    "credential_sentinels",
    "all_sample_members",
    "categories_of",
    "draft_fixture",
    "enrichment_result",
    "failure_mode_body",
    "failure_mode_transport",
    "observation",
    "observation_count",
    "one_asset_category_run",
    "overlap_run",
    "page_view_semantics_of",
    "policy_from_defaults",
    "preflight_selected_flags",
    "record_redaction_scan",
    "records_for",
    "response_body_fixture",
    "retrieved_at_utc",
    "run_from_categories",
    "run_record",
    "seed_sampling_and_run",
    "six_category_run",
    "small_policy",
    "success_body",
    "success_transport",
    "summary_status_of",
    "ten_identity_run",
    "three_category_run",
    "two_asset_run",
    "verdict",
]

# --------------------------------------------------------------------------
# Fixed aware-UTC timestamps. No clock is ever read (LREQ-ARCH-020).
# --------------------------------------------------------------------------

RETRIEVED_AT_UTC = datetime(2025, 6, 7, 8, 9, 10, tzinfo=timezone.utc)
RUN_STARTED_AT_UTC = datetime(2025, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
SCORING_CUTOFF_UTC = datetime(2025, 3, 4, 5, 6, 7, tzinfo=timezone.utc)
TAXONOMY_CAPTURED_AT_UTC = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

#: Inert path values for a fixture ``NicheScoutConfig`` (never opened).
CATEGORIES_PATH = Path("config") / "categories.json"
TAXONOMY_PATH = Path("config") / "category_taxonomy.json"
DB_PATH = Path("runtime") / "niche_scout.sqlite3"


def retrieved_at_utc() -> datetime:
    """Return the fixed aware-UTC retrieval timestamp."""
    return RETRIEVED_AT_UTC


# --------------------------------------------------------------------------
# Fixture-only credential material (non-secret) and redaction sentinels.
#
# ``GQL_CREDENTIALS`` is reused from ``fixtures.graphql_fixtures`` so the
# request fixtures and the preflight fixtures agree on one credential object.
# ``REDACTION_CREDENTIALS`` carries the distinct sentinel strings that the
# redaction tests assert never reach persisted output.
# --------------------------------------------------------------------------

REDACTION_CREDENTIALS: Credentials = Credentials(
    coveo_token="fixture-preflight-bearer-token",
    unity_csrf_token="fixture-preflight-csrf-token",
)

#: The flat sentinel list the redaction tests scan for.
RECORD_REDACTION_FORBIDDEN: tuple[str, ...] = (
    "fixture-preflight-bearer-token",
    "fixture-preflight-csrf-token",
    "sessionid=fixture-cookie-value",
    "Bearer fixture-header-value",
    "fixture-response-body-marker",
)


# --------------------------------------------------------------------------
# Canonical sampling runs (built through the live Chunk 4A engine).
# --------------------------------------------------------------------------

CATEGORY_A = "Category/A"
CATEGORY_B = "Category/B"
CATEGORY_C = "Category/C"
CATEGORY_D = "Category/D"
CATEGORY_E = "Category/E"
CATEGORY_F = "Category/F"

RUN_ID = "run-6a"

#: Identity keys used by the reduced-size vectors.
A = "A"
B = "B"
C = "C"
D = "D"
E_KEY = "E"
F = "F"
SHARED = "S"
DISTINCT_KEY = "Z"


def observation(discovery_ordinal: int, asset_identity_key: str) -> dict:
    """Return one inert 4A population-record mapping (no duplicates)."""
    return {
        "discovery_ordinal": discovery_ordinal,
        "asset_identity_key": asset_identity_key,
        "is_duplicate": False,
    }


def records_for(keys: tuple[str, ...], *, first_ordinal: int = 0) -> tuple[dict, ...]:
    """Return ``keys`` as ascending-ordinal 4A records (one canonical each)."""
    return tuple(
        observation(first_ordinal + index, key) for index, key in enumerate(keys)
    )


def run_from_categories(
    categories: Mapping[str, tuple[dict, ...]], *, run_id: str = RUN_ID
) -> Any:
    """Return a pure ``RunSamplingResult`` for the declared category order."""
    return sampling.select_run_sample(categories, run_id=run_id)


def ten_identity_run() -> Any:
    """Five categories, two distinct members each -> ten unique identities."""
    return run_from_categories(
        {
            CATEGORY_A: records_for(("A1", "A2")),
            CATEGORY_B: records_for(("B1", "B2")),
            CATEGORY_C: records_for(("C1", "C2")),
            CATEGORY_D: records_for(("D1", "D2")),
            CATEGORY_E: records_for(("E1", "E2")),
        }
    )


def two_asset_run() -> Any:
    """Two categories, two members each; the shared pair dedups to two identities."""
    return run_from_categories(
        {
            CATEGORY_A: records_for((A, B)),
            CATEGORY_B: records_for((A, B)),
        }
    )


def three_category_run() -> Any:
    """Three eligible two-member categories (fewer than the five minimum)."""
    return run_from_categories(
        {
            CATEGORY_A: records_for((A, B)),
            CATEGORY_B: records_for((C, D)),
            CATEGORY_C: records_for((E_KEY, F)),
        }
    )


def six_category_run() -> Any:
    """Six eligible two-member categories: five covered, one eligible-but-uncovered."""
    return run_from_categories(
        {
            CATEGORY_A: records_for(("A1", "A2")),
            CATEGORY_B: records_for(("B1", "B2")),
            CATEGORY_C: records_for(("C1", "C2")),
            CATEGORY_D: records_for(("D1", "D2")),
            CATEGORY_E: records_for(("E1", "E2")),
            CATEGORY_F: records_for(("F1", "F2")),
        }
    )


def overlap_run() -> Any:
    """Identity ``S`` in both categories; ``A``/``B`` distinct (denominator 3)."""
    return run_from_categories(
        {
            CATEGORY_A: records_for((A, SHARED)),
            CATEGORY_B: records_for((B, SHARED)),
        }
    )


def one_asset_category_run() -> Any:
    """One eligible two-member category plus a one-member category."""
    return run_from_categories(
        {
            CATEGORY_A: records_for((A, B)),
            CATEGORY_B: records_for((C,)),
        }
    )


def census_three_run() -> Any:
    """One census category of three members plus a two-member category."""
    return run_from_categories(
        {
            CATEGORY_A: records_for((A, B, C)),
            CATEGORY_B: records_for((D, E_KEY)),
        }
    )


# --------------------------------------------------------------------------
# Hand-built Chunk 5 result/draft objects.
#
# ``EnrichmentResult`` and ``EnrichmentObservationDraft`` are read by 6A by
# attribute, per the frozen interfaces. These local shaped stand-ins carry
# exactly the members the plan says 6A consumes; they are deliberately not the
# adapter's classes so a fixture can express any independent case.
# --------------------------------------------------------------------------

CORRELATION_MODE: GraphQLOperationCorrelationMode = (
    GraphQLOperationCorrelationMode.EXPLICIT_KEY
)
EXPLICIT_KEY = GraphQLOperationCorrelationMode.EXPLICIT_KEY
VALIDATED_POSITION = GraphQLOperationCorrelationMode.VALIDATED_POSITION
GRAPHQL_BATCH_ENDPOINT = "https://assetstore.unity.com/api/graphql/batch"
ENDPOINT_CONTRACT_VERSION_FIXTURE = "1.0.0"
CANONICAL_ENDPOINT_SIGNATURE = (
    f"{GRAPHQL_BATCH_ENDPOINT}#{ENDPOINT_CONTRACT_VERSION_FIXTURE}"
)
FOREIGN_OPERATION_NAME = "ServerTime"

MALFORMED_REQUEST = "MALFORMED_REQUEST"
NULL_REQUIRED_DATA = "NULL_REQUIRED_DATA"
WRONG_DATA_SHAPE = "WRONG_DATA_SHAPE"
WRONG_SCALAR_TYPE = "WRONG_SCALAR_TYPE"
INVALID_STATE_VALUE = "INVALID_STATE_VALUE"
MISSING_IDENTITY = "MISSING_IDENTITY"
TRANSPORT_FAILURE = "TRANSPORT_FAILURE"

PRODUCT_DETAIL_CATEGORY_JSON = '{"path":"Tools/Level Design/Tilemap"}'
PRODUCT_DETAIL_PUBLISHER_JSON = '{"name":"Fixture Publisher"}'


class _Op:
    """A minimal stand-in for one Chunk 5 ``GraphQLOperationResult``."""

    def __init__(
        self,
        status: OperationStatus,
        *,
        failure_class: str | None = None,
        payload: Mapping[str, object] | None = None,
        error_summary: str | None = None,
    ) -> None:
        self.status = status
        self.failure_class = failure_class
        self.payload = payload
        self.error_summary = error_summary

    @property
    def is_success(self) -> bool:
        """Return whether this operation status is success."""
        return self.status == OperationStatus.SUCCESS


class _Correlation:
    """A minimal stand-in for a Chunk 5 ``GraphQLCorrelationResult``."""

    def __init__(self, mode: GraphQLOperationCorrelationMode) -> None:
        self.mode = mode
        self.is_fully_correlated = True
        self.by_operation: Mapping[str, object] = {}
        self.matches: tuple[object, ...] = ()
        self.issues: tuple[object, ...] = ()
        self.unassociated_item_indexes: tuple[int, ...] = ()


class _Result:
    """A minimal stand-in for a Chunk 5 ``EnrichmentResult``."""

    def __init__(
        self,
        identity: str,
        correlation: _Correlation,
        product_detail: _Op,
        page_views: _Op,
        http_status: int | None,
        attempts: int,
        response_sha256: str | None,
    ) -> None:
        self.asset_identity_key = identity
        self.correlation = correlation
        self.product_detail = product_detail
        self.page_views = page_views
        self.http_status = http_status
        self.attempts = attempts
        self.response_sha256 = response_sha256
        self.retry_metadata_json = (
            '{"attempts":1,"failure_classes":[],"http_statuses":[200]}'
        )
        self.issues: tuple[object, ...] = ()

    @property
    def is_success(self) -> bool:
        """Return whether both operations succeeded."""
        return self.product_detail.is_success and self.page_views.is_success


def _detail_fields(identity: str | None) -> Mapping[str, object]:
    """Return a ``ProductDetailFields``-shaped mapping for a success."""
    return {
        "graphql_id": identity,
        "product_id": identity,
        "rating_average": 4.5,
        "rating_count": 210,
        "review_count": 34,
        "publisher_json": PRODUCT_DETAIL_PUBLISHER_JSON,
        "category_json": PRODUCT_DETAIL_CATEGORY_JSON,
        "state": "published",
    }


def enrichment_result(
    identity: str,
    *,
    detail_status: OperationStatus = OperationStatus.SUCCESS,
    page_status: OperationStatus = OperationStatus.SUCCESS,
    returned_identity: str | None = None,
    detail_failure_class: str | None = None,
    page_failure_class: str | None = None,
    returned_page_views: int | None = 4321,
) -> _Result:
    """Build an inert ``EnrichmentResult``-shaped result for ``identity``.

    ``returned_identity`` is the identity the ``ProductDetail`` payload carries;
    it defaults to ``identity`` (an identity match). A non-success operation
    carries ``payload=None`` and its failure class, never a zero value.
    """
    detail_ok = detail_status == OperationStatus.SUCCESS
    page_ok = page_status == OperationStatus.SUCCESS

    if detail_ok:
        fields = dict(_detail_fields(identity))
        if returned_identity is not None:
            fields["graphql_id"] = returned_identity
            fields["product_id"] = returned_identity
        detail = _Op(OperationStatus.SUCCESS, payload=fields)
    else:
        detail = _Op(
            detail_status,
            failure_class=detail_failure_class or NULL_REQUIRED_DATA,
            payload=None,
            error_summary=detail_failure_class or NULL_REQUIRED_DATA,
        )

    page = _Op(
        OperationStatus.SUCCESS if page_ok else OperationStatus.ERROR,
        failure_class=None if page_ok else (page_failure_class or WRONG_SCALAR_TYPE),
        payload=(
            {"pageViews": returned_page_views}
            if page_ok and returned_page_views is not None
            else None
        ),
        error_summary=None if page_ok else (page_failure_class or WRONG_SCALAR_TYPE),
    )

    return _Result(
        identity,
        _Correlation(CORRELATION_MODE),
        detail,
        page,
        200,
        1,
        None,
    )


def draft_fixture(
    identity: str, *, retrieved_at: datetime = RETRIEVED_AT_UTC
) -> Mapping[str, object]:
    """Return an ``EnrichmentObservationDraft``-shaped mapping for ``identity``."""
    return {
        "asset_identity_key": identity,
        "product_detail_status": OperationStatus.SUCCESS.value,
        "page_views_status": OperationStatus.SUCCESS.value,
        "graphql_id": identity,
        "product_id": identity,
        "rating_average": 4.5,
        "rating_count": 210,
        "review_count": 34,
        "first_published_date_utc": None,
        "publisher_json": PRODUCT_DETAIL_PUBLISHER_JSON,
        "category_json": PRODUCT_DETAIL_CATEGORY_JSON,
        "state": "published",
        "product_page_views": 4321,
        "id_mapping_mismatch": False,
        "product_detail_error_summary": None,
        "page_views_error_summary": None,
        "request_metadata_json": (
            '{"additional_correlation_keys":{},"correlation_keys":'
            '{"ProductDetail":"ProductDetail","ProductPageViews":"ProductPageViews"},'
            '"correlation_mode":"explicit_key","http_status":200,'
            '"operation_names":["ProductDetail","ProductPageViews"],'
            '"response_sha256":null,"retry":{"attempts":1,"failure_classes":[],'
            '"http_statuses":[200]}}'
        ),
        "retrieved_at_utc": retrieved_at,
    }


@dataclass(frozen=True, slots=True)
class _RuleResult:
    """A hand-built verdict carrying the members 6A consumes."""

    asset_identity_key: str
    product_detail_status: str
    page_views_status: str
    is_both_operations_success: bool
    identity_match: bool | None
    correlation_mode: str
    mapping_rule_version: str
    endpoint_signature: str
    diagnostic_summary_json: str | None
    draft: Mapping[str, object]


def verdict(
    identity: str = "A",
    *,
    identity_match: bool | None = True,
    detail_ok: bool = True,
    page_ok: bool = True,
    diagnostic_summary_json: str | None = None,
    correlation_mode: str = EXPLICIT_KEY.value,
) -> _RuleResult:
    """Build a hand-derived per-identity preflight verdict (no execution)."""
    return _RuleResult(
        asset_identity_key=identity,
        product_detail_status=(
            OperationStatus.SUCCESS.value if detail_ok else OperationStatus.ERROR.value
        ),
        page_views_status=(
            OperationStatus.SUCCESS.value if page_ok else OperationStatus.ERROR.value
        ),
        is_both_operations_success=bool(detail_ok and page_ok),
        identity_match=identity_match,
        correlation_mode=correlation_mode,
        mapping_rule_version="1.0.1",
        endpoint_signature=CANONICAL_ENDPOINT_SIGNATURE,
        diagnostic_summary_json=diagnostic_summary_json,
        draft=draft_fixture(identity),
    )


# --------------------------------------------------------------------------
# Caller-injected transports (inert; never the network).
# --------------------------------------------------------------------------


class RecordingTransport:
    """A fake ``GraphQLTransport`` mapping identity -> response body.

    ``body_for_identity`` is the inert lookup table; ``default_body`` is served
    for an identity absent from it. Every call is recorded on :attr:`calls`.
    """

    def __init__(
        self,
        body_for_identity: Mapping[str, bytes] | None = None,
        *,
        default_body: bytes | None = None,
    ) -> None:
        self._bodies = dict(body_for_identity or {})
        self._default = default_body
        self.calls: list[Any] = []

    def __call__(self, request: Any, headers: Mapping[str, str]) -> Any:
        from niche_scout.collector_graphql import GraphQLBatchResponse

        self.calls.append(request)
        key = str(getattr(request, "asset_identity_key", ""))
        body = self._bodies.get(key, self._default)
        if body is None:
            raise AssertionError(f"no fixture response queued for identity {key!r}")
        if isinstance(body, (bytes, bytearray)):
            body = body.decode("utf-8")
        return GraphQLBatchResponse(http_status=200, body_text=body)

    @property
    def call_count(self) -> int:
        """Return how many times the transport was called."""
        return len(self.calls)

    @property
    def requested_identities(self) -> tuple[str, ...]:
        """Return each call's ``asset_identity_key``, in call order."""
        return tuple(
            str(getattr(call, "asset_identity_key", "")) for call in self.calls
        )

    @property
    def distinct_requested_identities(self) -> tuple[str, ...]:
        """Return the distinct requested identities, in first-call order."""
        seen: list[str] = []
        for key in self.requested_identities:
            if key not in seen:
                seen.append(key)
        return tuple(seen)


class FailingTransport:
    """A transport that always raises (the adapter's ``TRANSPORT_FAILURE`` path)."""

    def __init__(self) -> None:
        self.calls: list[Any] = []

    def __call__(self, request: Any, headers: Mapping[str, str]) -> Any:
        self.calls.append(request)
        raise ConnectionResetError("injected transport failure")


def success_transport(identities: tuple[str, ...]) -> RecordingTransport:
    """Return a transport serving a both-operations-success body per identity."""
    return RecordingTransport({key: success_body(key) for key in identities})


def collision_transport(identity: str) -> RecordingTransport:
    """Return a transport whose every call repeats key ``identity``'s response."""
    return RecordingTransport(default_body=success_body(identity))


# --------------------------------------------------------------------------
# Response bodies (canonical JSON, hand-written so a test does not mirror the
# adapter). 6A is bound by Chunk 5's protocol, so every payload carries every
# member the Chunk 5 selection set requires.
# --------------------------------------------------------------------------


def _detail_payload(
    identity: str,
    *,
    rating_average: object = 4.5,
    rating_count: object = 210,
    review_count: object = 34,
    state: object = "published",
    category: object = "Tools/Level Design/Tilemap",
    publisher: object = "Fixture Publisher",
) -> Mapping[str, object]:
    """Return a valid ``ProductDetail`` payload for ``identity``."""
    return {
        "id": identity,
        "productId": identity,
        "rating": {"average": rating_average, "count": rating_count},
        "reviewCount": review_count,
        "firstPublishedDate": "2019-03-04T12:30:00Z",
        "state": state,
        "category": category,
        "publisher": publisher,
    }


def response_body_fixture(*items: object) -> str:
    """Return canonical JSON text for the given response items, in order."""
    return json.dumps(list(items), sort_keys=True, separators=(",", ":"))


def _two_op_body(detail_item: object, page_item: object) -> bytes:
    """Return the canonical body for the two issued operations, in order."""
    return response_body_fixture(detail_item, page_item).encode("utf-8")


def success_body(identity: str, *, page_views: object = 4321) -> bytes:
    """Return a both-operations-success body for ``identity``.

    ``page_views`` of ``0`` is an explicit valid zero, not a failure sentinel;
    the request-scoped association is what ties the operation to the requested
    package identifier (Chunk 5 §5.4).
    """
    return _two_op_body(
        {
            "operationName": PRODUCT_DETAIL_OPERATION_NAME,
            "data": _detail_payload(identity),
        },
        {
            "operationName": PRODUCT_PAGE_VIEWS_OPERATION_NAME,
            "data": {"pageViews": page_views},
        },
    )


#: The named failure modes exercised by ``test_preflight_identity_failure_modes``.
FAILURE_MODES: tuple[str, ...] = (
    "request_id_rejected",
    "identity_mismatch",
    "page_view_package_mismatch",
    "invalid_correlation_mode",
    "partial_success",
    "transport_failure",
)


def failure_mode_body(mode: str, identity: str) -> bytes:
    """Return the response body for one named failure mode.

    ``request_id_rejected`` makes the ``ProductDetail`` operation fail (the
    request identifier is not accepted); ``identity_mismatch`` returns a valid
    payload whose aliases name another asset; ``page_view_package_mismatch``
    rejects the page-view scalar; ``invalid_correlation_mode`` repeats one
    correlation key so neither operation can be associated; ``partial_success``
    makes exactly one operation fail.
    """
    if mode == "request_id_rejected":
        return _two_op_body(
            {
                "operationName": PRODUCT_DETAIL_OPERATION_NAME,
                "data": {"errors": [{"message": "fixture operation failure"}]},
            },
            {
                "operationName": PRODUCT_PAGE_VIEWS_OPERATION_NAME,
                "data": {"pageViews": 4321},
            },
        )
    if mode == "identity_mismatch":
        payload = dict(_detail_payload(identity))
        payload["id"] = "Retired/Other"
        payload["productId"] = "Retired/Other"
        return _two_op_body(
            {"operationName": PRODUCT_DETAIL_OPERATION_NAME, "data": payload},
            {
                "operationName": PRODUCT_PAGE_VIEWS_OPERATION_NAME,
                "data": {"pageViews": 4321},
            },
        )
    if mode == "page_view_package_mismatch":
        return _two_op_body(
            {
                "operationName": PRODUCT_DETAIL_OPERATION_NAME,
                "data": _detail_payload(identity),
            },
            {
                "operationName": PRODUCT_PAGE_VIEWS_OPERATION_NAME,
                "data": {"pageViews": -1},
            },
        )
    if mode == "invalid_correlation_mode":
        return _two_op_body(
            {
                "operationName": PRODUCT_DETAIL_OPERATION_NAME,
                "data": _detail_payload(identity),
            },
            {
                "operationName": PRODUCT_DETAIL_OPERATION_NAME,
                "data": _detail_payload(identity),
            },
        )
    if mode == "partial_success":
        return _two_op_body(
            {
                "operationName": PRODUCT_DETAIL_OPERATION_NAME,
                "data": {"errors": [{"message": "fixture operation failure"}]},
            },
            {
                "operationName": PRODUCT_PAGE_VIEWS_OPERATION_NAME,
                "data": {"pageViews": 4321},
            },
        )
    raise ValueError(f"unknown failure mode: {mode!r}")


class _FirstIdentityRaises:
    """Raise on the first call, then serve a success body for every later call."""

    def __init__(self, first_identity: str) -> None:
        self._first_identity = first_identity
        self.calls: list[Any] = []

    def __call__(self, request: Any, headers: Mapping[str, str]) -> Any:
        from niche_scout.collector_graphql import GraphQLBatchResponse

        self.calls.append(request)
        key = str(getattr(request, "asset_identity_key", ""))
        if key == self._first_identity:
            raise ConnectionResetError("injected transport failure")
        return GraphQLBatchResponse(
            http_status=200, body_text=success_body(key).decode("utf-8")
        )


def failure_mode_transport(mode: str, identity: str) -> Any:
    """Return an inert transport where only ``identity`` exhibits ``mode``.

    The other sampled identity is always a clean both-operations success, so a
    node can assert that one asset's failure never affects its neighbour.
    ``transport_failure`` raises only on ``identity``'s call.
    """
    if mode == "transport_failure":
        return _FirstIdentityRaises(identity)
    return RecordingTransport(
        {
            identity: failure_mode_body(mode, identity),
            B: success_body(B),
        }
    )


# --------------------------------------------------------------------------
# Golden vectors (hand-derived; the derivation comment lives in the test).
# --------------------------------------------------------------------------

#: Two unique identities, one comparison failure: attempted 2, successful 1,
#: conflicting 1, other_failed 0; rates 1/2 and 1/2.
ATTEMPTED_DENOMINATOR_GOLDEN: Mapping[str, float | int | None] = {
    "attempted_unique_identities": 2,
    "successful_unique_identities": 1,
    "conflicting_unique_identities": 1,
    "other_failed_unique_identities": 0,
    "success_rate": 0.5,
    "conflict_rate": 0.5,
}

#: Ten identities, six successes, one conflict, three other failures:
#: success_rate 6/10 = 0.6, conflict_rate 1/10 = 0.1.
ATTEMPTED_OTHER_FAILED_GOLDEN: Mapping[str, float | int | None] = {
    "attempted_unique_identities": 10,
    "successful_unique_identities": 6,
    "conflicting_unique_identities": 1,
    "other_failed_unique_identities": 3,
    "success_rate": 0.6,
    "conflict_rate": 0.1,
}

#: Ten identities, one conflict, nine both-operations successes:
#: success_rate 9/10 = 0.9 exactly at the 0.90 minimum; conflict_rate 0.1.
ATTEMPTED_BOUNDARY_GOLDEN: Mapping[str, float | int | None] = {
    "attempted_unique_identities": 10,
    "successful_unique_identities": 9,
    "conflicting_unique_identities": 1,
    "other_failed_unique_identities": 0,
    "success_rate": 0.9,
    "conflict_rate": 0.1,
}

#: Ten identities, eight successes, two conflicts: 0.8 and 0.2 both fail.
ATTEMPTED_CONFLICT_GOLDEN: Mapping[str, float | int | None] = {
    "attempted_unique_identities": 10,
    "successful_unique_identities": 8,
    "conflicting_unique_identities": 2,
    "other_failed_unique_identities": 0,
    "success_rate": 0.8,
    "conflict_rate": 0.2,
}

#: Empty selection: attempted 0 and both rates ``None`` (never ``0.0``).
ATTEMPTED_ZERO_GOLDEN: Mapping[str, float | int | None] = {
    "attempted_unique_identities": 0,
    "successful_unique_identities": 0,
    "conflicting_unique_identities": 0,
    "other_failed_unique_identities": 0,
    "success_rate": None,
    "conflict_rate": None,
}

#: The plan §9 failure diagnostic golden: counts 10/8/1/1.
DIAGNOSTIC_COUNTS_GOLDEN: Mapping[str, int] = {
    "attempted_unique_identities": 10,
    "successful_unique_identities": 8,
    "conflicting_unique_identities": 1,
    "other_failed_unique_identities": 1,
}

#: Four summary keys at their golden integer values, serialized canonically.
SUM_FOUR_KEYS_JSON: tuple[str, ...] = (
    '"attempted_unique_identities":10',
    '"conflicting_unique_identities":1',
    '"other_failed_unique_identities":1',
    '"successful_unique_identities":8',
)

#: The frozen §5.5 ``identity_preflight_summary_json`` key set.
SUMMARY_KEY_SET: tuple[str, ...] = (
    "status",
    "attempted_unique_identities",
    "successful_unique_identities",
    "conflicting_unique_identities",
    "other_failed_unique_identities",
    "success_rate",
    "conflict_rate",
    "graphql_operation_correlation_mode",
    "graphql_endpoint_signature",
    "identity_mapping_rule_version",
    "selected_category_count",
    "eligible_category_count",
    "reduced_coverage",
    "category_shortfall",
    "asset_shortfall",
    "diagnostic_summary_json",
)


# --------------------------------------------------------------------------
# The reduced policy used by the small deterministic-selection vectors.
# --------------------------------------------------------------------------


def small_policy(*, min_categories: int = 2, assets_per_category: int = 2) -> Any:
    """Return the default policy reduced to two categories of two assets."""
    from niche_scout import pipeline

    return pipeline.PreflightPolicy(
        min_categories=min_categories,
        assets_per_category=assets_per_category,
        max_conflict_rate=0.0,
        min_success_rate=0.9,
    )


def policy_from_defaults() -> Any:
    """Return ``PreflightPolicy()`` with the frozen LREQ-ID-030 defaults."""
    from niche_scout import pipeline

    return pipeline.PreflightPolicy()


# --------------------------------------------------------------------------
# Repository helpers (Chunk 2/4B runtime order).
# --------------------------------------------------------------------------


def run_record(
    run_id: str = RUN_ID,
    *,
    page_view_semantics_status: str = "unvalidated",
    categories: tuple[str, ...] = (),
) -> RunRecord:
    """Return the fixed 6A ``RunRecord`` (aware UTC, ``status="running"``)."""
    return RunRecord(
        run_id=run_id,
        run_started_at_utc=RUN_STARTED_AT_UTC,
        scoring_cutoff_utc=SCORING_CUTOFF_UTC,
        completed_at_utc=None,
        categories_json=json.dumps(list(categories)),
        config_snapshot_json="{}",
        config_sha256="0" * 64,
        taxonomy_version="2025.1",
        taxonomy_captured_at_utc=TAXONOMY_CAPTURED_AT_UTC,
        taxonomy_sha256="1" * 64,
        endpoint_contract_version=ENDPOINT_CONTRACT_VERSION_FIXTURE,
        identity_mapping_rule_version="1.0.1",
        sampling_rule_version="1.0.0",
        page_view_semantics_status=page_view_semantics_status,
        graphql_operation_correlation_mode=EXPLICIT_KEY.value,
        identity_preflight_status="passed",
        identity_preflight_summary_json="{}",
        status="running",
    )


def seed_sampling_and_run(
    repository: Any,
    run: Any,
    *,
    page_view_semantics_status: str = "unvalidated",
) -> None:
    """Insert the run row and persist the 4B sampling result for ``run``.

    The runtime order 6A depends on: the ``runs`` row exists, the 4B
    ``sample_members`` rows exist with ``preflight_selected=False``, and
    ``get_sample_members(run_id)`` is the 6A-visible pool.
    """
    from niche_scout import database

    repository.insert_run(
        run_record(
            run.run_id,
            page_view_semantics_status=page_view_semantics_status,
            categories=tuple(category.category for category in run.categories),
        )
    )
    for category in run.categories:
        repository.set_category_status(
            run.run_id,
            category.category,
            DiscoveryStatus.COMPLETE.value,
            computed_at_utc=SCORING_CUTOFF_UTC,
        )
    with repository.transaction():
        database.persist_run_sampling(
            repository, run, computed_at_utc=SCORING_CUTOFF_UTC
        )


def page_view_semantics_of(repository: Any, run_id: str) -> str:
    """Read the run-level page-view-semantics status back from the row."""
    record = repository.get_run(run_id)
    assert record is not None
    return record.page_view_semantics_status


def all_sample_members(repository: Any, run_id: str) -> tuple[Any, ...]:
    """Return every ``sample_members`` row for a run, in category order.

    ``get_sample_members`` is scoped to ``(run_id, category)`` per the frozen
    Chunk 2 interface, so the run-wide view walks the run's declared categories
    in order (the order the seeding helper wrote them).
    """
    rows: list[Any] = []
    for category in categories_of(repository, run_id):
        rows.extend(repository.get_sample_members(run_id, category))
    return tuple(rows)


def categories_of(repository: Any, run_id: str) -> tuple[str, ...]:
    """Return the run's declared category list, in stored order."""
    record = repository.get_run(run_id)
    assert record is not None
    return tuple(json.loads(record.categories_json))


def preflight_selected_flags(repository: Any, run_id: str) -> Mapping[str, bool]:
    """Return ``{asset_identity_key: preflight_selected}`` for a run."""
    return {
        row.asset_identity_key: row.preflight_selected
        for row in all_sample_members(repository, run_id)
    }


def observation_count(repository: Any, run_id: str) -> int:
    """Return the number of enrichment observation rows for a run."""
    return int(repository.count_distinct_enrichment_identities(run_id))


def summary_status_of(report: Any) -> str:
    """Read the ``status`` member of a persisted preflight summary JSON string."""
    return str(json.loads(report.identity_preflight_summary_json)["status"])


def record_redaction_scan(record: Any) -> tuple[str, ...]:
    """Return every sentinel string found in a persisted record's text fields."""
    text = " ".join(
        str(getattr(record, field, ""))
        for field in (
            "request_metadata_json",
            "product_detail_error_summary",
            "page_views_error_summary",
            "publisher_json",
            "category_json",
            "state",
            "graphql_id",
            "product_id",
        )
    )
    return tuple(
        sentinel for sentinel in RECORD_REDACTION_FORBIDDEN if sentinel in text
    )


def credential_sentinels() -> Mapping[str, str]:
    """Return the non-secret sentinel strings the redaction tests scan for."""
    return {
        "credential": REDACTION_CREDENTIALS.coveo_token,
        "csrf": REDACTION_CREDENTIALS.unity_csrf_token,
        "cookie": "sessionid=fixture-cookie-value",
        "header_value": "Bearer fixture-header-value",
        "body_marker": "fixture-response-body-marker",
    }
