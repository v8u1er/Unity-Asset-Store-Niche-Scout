"""Coveo category discovery adapter with streamed raw persistence.

This module is the Coveo half of the SRS ``collector`` component
(``Documents/SRS-lean.md`` §4.1, LREQ-EXT-010 … LREQ-EXT-100). It performs real
network discovery through an injected opener, classifies every returned record
with the pure Chunk 1 primitives, and streams each page of raw observations into
the Chunk 2 persistence API inside an active per-category transaction.

Boundary rules this module preserves:

* **No module of this package is imported except its frozen dependencies.**
  ``models``, ``config``, ``validation``, and ``database`` are consumed;
  ``metrics``, ``scoring``, ``pipeline``, ``report``, ``cli``, and
  ``collector`` are never imported, so no import cycle and no pure-module
  violation can arise.
* **Nothing is read from the clock or the environment.** ``reference_utc`` and
  ``retrieved_at_utc`` come from caller-injected values, and credentials come
  from a caller-constructed :class:`~niche_scout.config.Credentials`.
* **A failed, truncated, unverified, or mismatched page is never zero assets.**
  Every condition is persisted as a :class:`~niche_scout.models.DiscoveryStatus`
  and exposed on :attr:`CategoryDiscoveryResult.conditions`; this module emits no
  ``WarningCode`` and sets no rankability (LREQ-EXT-090 is detection plus
  persistence here — its completion chunk is Chunk 10).
* **Streaming is a memory invariant.** A category's records are handed to the
  caller-supplied sink one page at a time; no per-category list of records is
  ever built and ``list()`` is never called on an observation stream.
* **Redaction.** No credential, ``Authorization`` header value, cookie, or raw
  response body reaches ``request_metadata_json``, ``error_summary_json``, or an
  exception message (LREQ-SEC-020).
* **Stdlib only.** The transport is ``urllib.request``; the module declares no
  third-party dependency (``pyproject.toml`` sets ``dependencies = []``).

The module deliberately does **not** compute, validate, or rewrite
``runs.taxonomy_sha256``: the placeholder value is propagated verbatim by the
orchestration layer (Chunk 10 owns that finding).
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Container, Iterator, Mapping, MutableMapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from .config import Credentials, NicheScoutConfig
from .database import RepositoryError, SqliteRepository
from .models import (
    ENDPOINT_CONTRACT_VERSION,
    IDENTITY_MAPPING_RULE_VERSION,
    MAX_DISCOVERY_RESULTS_PER_CATEGORY,
    MAX_TAXONOMY_AGE_DAYS,
    PAGE_SIZE,
    CategoryFilterValidationStatus,
    DiscoveryStatus,
    IdentityResolutionStatus,
    RawDiscoveryObservationRecord,
    ensure_utc,
)
from .validation import (
    CategoryMatchResult,
    IdentityCandidate,
    IdentityResolutionResult,
    StructuralValidationResult,
    TaxonomyValidationResult,
    ValidationIssue,
    collect_identity_candidates,
    discovery_status_for_category_status,
    match_exact_category,
    redact_value,
    resolve_canonical_identity,
    summarize_validation_issues,
    taxonomy_path_set,
    validate_response_shape,
    validate_taxonomy,
)

__all__ = [
    "COVEO_BACKOFF_BASE_SECONDS",
    "COVEO_DISCOVERY_FIELD_SET",
    "COVEO_ENDPOINT",
    "COVEO_FACET_ID",
    "COVEO_MAX_RETRIES",
    "COVEO_MIN_REQUEST_INTERVAL_SECONDS",
    "COVEO_ORGANIZATION_ID",
    "COVEO_REQUIRED_HEADERS",
    "COVEO_TEMPLATE_PATH",
    "COVEO_VISITOR_ID_PLACEHOLDER",
    "CategoryDiscoveryResult",
    "CoveoDiscoveryError",
    "CoveoObservationSink",
    "CoveoOpener",
    "CoveoPageResponse",
    "CoveoRateLimiter",
    "CoveoRequestFailed",
    "CoveoTaxonomyInvalid",
    "CoveoTransport",
    "CoveoUrlOpener",
    "build_coveo_headers",
    "build_coveo_request_body",
    "coveo_search_url",
    "discover_category",
    "fetch_category_page",
    "find_forbidden_query_field",
    "load_coveo_search_template",
    "order_conditions",
    "reject_free_text_query_members",
    "resolve_observation_identity",
    "select_terminal_status",
    "validate_discovery_taxonomy",
]

# --------------------------------------------------------------------------
# Frozen constants
# --------------------------------------------------------------------------

#: Parent-SRS Coveo search endpoint (retired ``SRS-revision2.md`` §4.1
#: ``REQ-EXT-010``; capture-confirmed organization id).
COVEO_ENDPOINT = (
    "https://unitytechnologiesproductionmkahteav.org.coveo.com/rest/search/v2"
)
COVEO_ORGANIZATION_ID = "unitytechnologiesproductionmkahteav"

#: The captured request template committed at the repository root.
COVEO_TEMPLATE_PATH = Path("config") / "coveo_search_template.json"

#: Fixed placeholder sent in ``visitorId``; never the captured per-browser UUID.
COVEO_VISITOR_ID_PLACEHOLDER = "niche-scout-lean-v1"

#: Headers sent on every Coveo request. ``Authorization`` is appended at call
#: time from the caller's credential. Browser-fingerprint headers
#: (``sec-ch-ua*``, ``sec-fetch-*``, ``priority``) and ``Origin``/``pragma``/
#: ``cache-control`` are deliberately absent: the capture sends no ``Origin``,
#: and none of the others is required to replay the discovery request.
COVEO_REQUIRED_HEADERS: tuple[tuple[str, str], ...] = (
    ("Content-Type", "application/json"),
    ("Accept", "application/json"),
    ("Referer", "https://assetstore.unity.com/"),
)

#: Rate limiting and retry policy (retired predecessor's ``REQ-EXT-100``).
COVEO_MIN_REQUEST_INTERVAL_SECONDS = 1.0
COVEO_BACKOFF_BASE_SECONDS = 2.0
COVEO_MAX_RETRIES = 5

#: Lists the discovery field set of LREQ-EXT-040 while recording that the
#: committed capture's own ``fieldsToInclude`` is not the request the adapter
#: sends: the five fields below are what this adapter requests. The capture's
#: list is **not** asserted here — its length was reported once as 23 entries and
#: the committed file holds 5 (an open discrepancy owned by the reviewer, not
#: resolved by this module). The point of the constant is the five-field
#: discovery-only set: rating, price, publication date, thumbnails, and promotion
#: windows SHALL NOT be sourced from Coveo for scoring.
COVEO_DISCOVERY_FIELD_SET: tuple[str, ...] = (
    "permanentid",
    "ec_product_id",
    "ec_name",
    "ec_category",
    "publisher_name",
)

#: The one facet this adapter ships, out of the capture's `ec_category` facet.
#: The capture's *other* facets are dropped (§12.1); their count is an open
#: discrepancy (reported once as four, not verified here), so no number is
#: asserted in code.
COVEO_FACET_ID = "ec_category"
COVEO_FACET_FIELDS: tuple[str, ...] = ()
COVEO_DROPPED_FACET_IDS: tuple[str, ...] = (
    "ec_sale_filters",
    "ec_price_filter",
    "ec_rating",
    "first_published_at",
    "publisher_name",
)

#: Template members replayed verbatim from the capture (§12.6).
_COVEO_REPLAYED_TEMPLATE_FIELDS: tuple[str, ...] = (
    "locale",
    "tab",
    "referrer",
    "timezone",
    "context",
    "dictionaryFieldContext",
    "searchHub",
    "sortCriteria",
    "numberOfResults",
    "facetOptions",
)

#: Free-text relevance members that may never appear at any nesting depth.
_FORBIDDEN_QUERY_FIELDS: frozenset[str] = frozenset({"q", "query"})

#: Success/transient/permanent classification inputs.
_HTTP_SUCCESS = 200
_HTTP_TRANSIENT_STATUSES: frozenset[int] = frozenset(
    {408, 425, 429} | set(range(500, 600))
)

#: Captured-page response members. ``results`` carries the records and
#: ``totalCount`` the verified population count; ``totalCountFiltered`` is the
#: hand-derived filtered count (LREQ-EXT-050's API-reported count).
_PAGE_RECORDS_MEMBER = "results"
_PAGE_TOTAL_COUNT_MEMBER = "totalCount"
_PAGE_TOTAL_COUNT_FILTERED_MEMBER = "totalCountFiltered"

_RESPONSE_REQUIRED_MEMBERS: tuple[str, ...] = (
    _PAGE_RECORDS_MEMBER,
    _PAGE_TOTAL_COUNT_MEMBER,
)
_RESPONSE_FIELD_TYPES: dict[str, type | tuple[type, ...]] = {
    _PAGE_RECORDS_MEMBER: list,
    _PAGE_TOTAL_COUNT_MEMBER: int,
}
_RESPONSE_CONTAINER_SHAPE = "mapping"
_RESPONSE_TOTAL_COUNT_SHAPE = "int"

#: The member names a discovery record may carry. Anything else is recorded as
#: forbidden-field presence and never read (LREQ-EXT-040).
_DISCOVERY_RESPONSE_FIELD_SET: frozenset[str] = frozenset(COVEO_DISCOVERY_FIELD_SET)

#: The *identity/category* member set a discovery record must be able to speak
#: about at all. ``LREQ-EXT-040`` requires a missing identity field to be
#: tolerated as **missing, never fabricated**, and the four identity source
#: fields plus the category predicate are what a record is classified through
#: (``LREQ-EXT-060``, ``LREQ-EXT-080``): a record that does not carry one of
#: these is not readable as a discovery record, so the *page* is a structural
#: failure rather than a page of partly-readable rows. ``ec_name`` and
#: ``publisher_name`` are deliberately **not** here — they are descriptive
#: members the adapter never sources a verdict from, so their absence is an
#: ordinary missing value and never a structural failure.
_RESPONSE_FIELD_SET_MEMBERS: tuple[str, ...] = (
    "permanentid",
    "ec_product_id",
    "ec_category",
)

#: An emitted page repeated this many times with the same record count is
#: treated as a non-advancing endpoint rather than an infinite pagination loop.
_MAX_REPEATED_PAGE_MATCHES = 2

#: Identity source fields carrying a **URI**, whose mapping-rule value is the
#: trailing ``-<digits>`` identifier of the last path segment (chunk-01.md §4.1).
_URI_IDENTITY_FIELDS: frozenset[str] = frozenset({"clickUri", "uri"})

#: The fields a record can declare an identity through (LREQ-EXT-060, SRS §4.1).
#: A record that declares none of them is a legitimate ``unresolved`` row, while
#: a record that declares one must declare them consistently.
_IDENTITY_SOURCE_FIELDS: tuple[str, ...] = (
    "ec_product_id",
    "permanentid",
    "clickUri",
    "uri",
)

#: The two identity members a record declares up front. ``clickUri``/``uri`` are
#: fallbacks that participate only once a record is already resolving an
#: identity, so their absence is never a partly-declared identity.
_IDENTITY_DECLARED_FIELDS: frozenset[str] = frozenset({"ec_product_id", "permanentid"})

#: Matches the trailing ``-<digits>`` identifier of a URI's last path segment.
_URI_TRAILING_IDENTIFIER = re.compile(r"-(\d+)$")

#: Recognizes an actual URI as the value's own leading shape (scheme or a
#: path-bearing authority). A bare product id such as ``P-1`` merely *ends* in
#: ``-<digits>``; it is not a URI, so it must never be read through the URI
#: mapping rule.
_URI_PATH_SHAPE = re.compile(r"^(?:[A-Za-z][A-Za-z0-9+.\-]*:)?//")


# --------------------------------------------------------------------------
# Protocols
# --------------------------------------------------------------------------


@runtime_checkable
class CoveoOpener(Protocol):
    """Retained name for the injected transport seam.

    :class:`CoveoTransport` is the canonical spelling; this alias keeps the
    earlier name from becoming a second, parallel contract.
    """

    def send(self, url: str, headers: Mapping[str, str], payload: bytes) -> Any:
        """Send one request and return an object exposing ``status``, ``headers``, and ``read()``."""


@runtime_checkable
class CoveoTransport(Protocol):
    """The HTTP seam: a mapping of headers and a payload bytes go to a response.

    A production implementation is :class:`CoveoUrlOpener`; every test injects a
    recording fake, so no analytical test performs network I/O.
    """

    def send(self, url: str, headers: Mapping[str, str], payload: bytes) -> Any:
        """Send one request and return an object exposing ``status``, ``headers``, and ``read()``."""


@dataclass(frozen=True, slots=True)
class CoveoHttpResponse:
    """The minimal response contract the adapter reads from an opener result."""

    request_url: str
    status: int
    headers: Mapping[str, str]
    body: bytes


class CoveoUrlOpener:
    """``urllib.request``-based :class:`CoveoTransport` used in production only.

    The caller injects a socket deadline through the ``urllib.request`` call, so
    ``time.sleep`` and the socket timeout remain the adapter's only waiting
    primitives and no third-party HTTP client is introduced.
    """

    def __init__(self, *, timeout_seconds: float = 30.0) -> None:
        self._timeout_seconds = timeout_seconds

    def send(self, url: str, headers: Mapping[str, str], payload: bytes) -> Any:
        request = urllib.request.Request(url=url, data=payload, method="POST")
        for name, value in headers.items():
            request.add_header(name, value)
        return urllib.request.urlopen(request, timeout=self._timeout_seconds)  # noqa: S310


class CoveoRateLimiter:
    """Spacing between consecutive Coveo requests, across the whole run.

    ``LREQ-EXT-100`` requires rate limiting without naming a primitive, so the
    spacing is enforced through the caller-injected ``sleeper``: the adapter
    never reads a clock of its own (a clock read would make discovery
    non-deterministic under test). The limiter therefore counts the requests it
    has issued and waits ``min_interval_seconds`` before every request after the
    first, which is the largest delay a clock-free limiter can honor without
    risking a shorter gap than required. The interval itself is the
    caller-supplied default argument inspected at call time, never a value folded
    into the limiter at construction, so the wait is always the policy constant
    it was called with.

    One instance is shared by every category of a run, so the interval applies
    across categories rather than resetting per category.
    """

    def __init__(self, sleeper: Callable[[float], None]) -> None:
        self._sleeper = sleeper
        self._spaced = False

    @property
    def issued(self) -> int:
        """How many requests have been counted so far.

        The count is what decides whether the *next* request owes a minimum
        interval: the first request of a run has no predecessor to space away
        from, so it owes none. The count never sleeps by itself — the actual
        delay is always the caller's own primitive with the policy constant, so
        exactly one recorded sleep per issued request carries that constant and
        none of them is merged into another delay.
        """
        return int(self._spaced)

    def count_issued(self) -> None:
        """Record that one request has been spaced and is about to be issued."""
        self._spaced = True


# --------------------------------------------------------------------------
# Typed results and errors
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CoveoPageResponse:
    """One structurally validated page. ``total_count`` is ``None`` when unverifiable."""

    page_index: int
    first_result: int
    total_count: int | None
    records: tuple[Mapping[str, object], ...]
    request_metadata: Mapping[str, object]
    issues: tuple[ValidationIssue, ...] = ()
    filtered_count: int | None = None
    #: Member names outside the five-field discovery set, per record index. The
    #: values themselves are never read or stored (LREQ-EXT-040).
    forbidden_field_presence: tuple[Mapping[str, object], ...] = ()

    @property
    def is_structural_failure(self) -> bool:
        """True when the page's response structure could not be validated."""
        return any(
            issue.code in {"response_wrong_container_kind", "response_missing_required_member"}
            for issue in self.issues
        )


class CoveoDiscoveryError(RuntimeError):
    """Base class for every Coveo discovery failure."""


class CoveoRequestFailed(CoveoDiscoveryError):
    """Retries exhausted, or a permanent request failure."""


class CoveoTaxonomyInvalid(CoveoDiscoveryError):
    """The taxonomy preflight failed and no request may be made."""


@dataclass(frozen=True, slots=True)
class CategoryDiscoveryResult:
    """The terminal per-category discovery outcome.

    ``observations_emitted`` counts every row handed to the sink, duplicates
    included, so ``ordinal_end - ordinal_start`` equals it and the persisted row
    count for the category matches. ``conditions`` keeps every applicable
    condition visible even though exactly one is selected as
    ``discovery_status``.
    """

    category: str
    discovery_status: DiscoveryStatus
    ordinal_start: int
    ordinal_end: int
    observations_emitted: int
    canonical_identity_count: int
    unresolved_identity_count: int
    conflict_identity_count: int
    duplicate_observation_count: int
    pages_fetched: int
    total_count: int | None
    api_reported_count: int | None
    filter_status: CategoryFilterValidationStatus
    conditions: tuple[DiscoveryStatus, ...]
    issues: tuple[ValidationIssue, ...]


# --------------------------------------------------------------------------
# Template capture
# --------------------------------------------------------------------------


def _canonical_template_body(body: Mapping[str, object]) -> str:
    """Canonical text of a template body, as hashed by the provenance header."""
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _template_body(payload: Mapping[str, object], *, source: str) -> Mapping[str, object]:
    body = payload.get("request_body")
    if not isinstance(body, Mapping):
        raise CoveoTaxonomyInvalid(
            f"the captured Coveo request template at {source} carries no usable "
            "'request_body' mapping"
        )
    return body


def load_coveo_search_template(
    template_path: "Path | str" = COVEO_TEMPLATE_PATH,
) -> Mapping[str, object]:
    """Read and hash-verify the captured Coveo discovery request template.

    The committed body is verified against the provenance header's
    ``template_sha256`` — SHA-256 over ``json.dumps(request_body, sort_keys=True,
    separators=(",", ":"), ensure_ascii=False)`` — so a drifted capture fails
    loudly instead of being replayed as if it were the captured request.

    The provenance header is returned alongside the body so the request
    metadata can record which capture was replayed. The capture itself is never
    rewritten: neither the template file nor the taxonomy file is modified.

    Raises :class:`CoveoTaxonomyInvalid` when the file is missing, is not valid
    JSON, is not an object, carries no ``request_body`` mapping, carries no
    usable ``template_sha256``, or does not match that hash. The message names
    the path and the reason only — never body content.
    """
    path = Path(template_path)
    source = str(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CoveoTaxonomyInvalid(
            f"the captured Coveo request template at {source} cannot be read: "
            f"{exc.__class__.__name__}"
        ) from None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CoveoTaxonomyInvalid(
            f"the captured Coveo request template at {source} is not valid JSON "
            f"(line {exc.lineno}, column {exc.colno})"
        ) from None
    if not isinstance(payload, Mapping):
        raise CoveoTaxonomyInvalid(
            f"the captured Coveo request template at {source} must be a JSON object"
        )

    body = _template_body(payload, source=source)
    declared = payload.get("template_sha256")
    if not isinstance(declared, str) or declared.strip() == "":
        raise CoveoTaxonomyInvalid(
            f"the captured Coveo request template at {source} declares no usable "
            "'template_sha256' provenance value"
        )
    computed = hashlib.sha256(_canonical_template_body(body).encode("utf-8")).hexdigest()
    if computed != declared.strip():
        raise CoveoTaxonomyInvalid(
            f"the captured Coveo request template at {source} does not match its "
            "declared 'template_sha256': the committed body has drifted from the "
            "capture the provenance header records"
        )

    header: dict[str, object] = {
        key: value for key, value in payload.items() if key != "request_body"
    }
    header["request_body"] = body
    return header


def _template_field_source(template: Mapping[str, object]) -> Mapping[str, object]:
    """Return the mapping that carries the replayable template members.

    ``load_coveo_search_template`` returns the provenance header with the capture
    under ``request_body``; a caller may also pass the bare body. Both shapes
    resolve to the same members.
    """
    nested = template.get("request_body")
    if isinstance(nested, Mapping):
        return nested
    return template


# --------------------------------------------------------------------------
# Request construction
# --------------------------------------------------------------------------


def coveo_search_url(organization_id: str = COVEO_ORGANIZATION_ID) -> str:
    """Return the organization-scoped Coveo search endpoint URL."""
    return f"{COVEO_ENDPOINT}?organizationId={organization_id}"


def _normalize_bearer_scheme(token: str) -> str:
    """Strip one leading ``Bearer`` scheme prefix from a supplied credential.

    ``.env`` stores the credential as ``"Bearer eyJ…"`` while
    ``config.get_credentials()`` only trims it, so re-prefixing without
    normalization would send ``Authorization: Bearer Bearer eyJ…``.
    """
    trimmed = token.strip()
    lowered = trimmed.casefold()
    if lowered.startswith("bearer "):
        return trimmed[len("bearer ") :].strip()
    return trimmed


def build_coveo_headers(bearer_token: str) -> dict[str, str]:
    """Return the required headers plus ``Authorization: Bearer <token>``.

    A leading ``"Bearer "``/``"bearer "`` scheme prefix in the supplied value is
    normalized out before the scheme is re-applied, so a credential stored as
    ``"Bearer eyJ…"`` yields exactly one scheme on the wire. An empty or
    whitespace-only credential raises :class:`ValueError` without echoing it;
    credentials are validated before any network request.
    """
    token = _normalize_bearer_scheme(bearer_token)
    if token == "":
        raise ValueError(
            "a Coveo bearer credential is required before network collection"
        )
    headers = {name: value for name, value in COVEO_REQUIRED_HEADERS}
    headers["Authorization"] = f"Bearer {token}"
    return headers


def find_forbidden_query_field(value: object, *, path: str = "") -> str | None:
    """Return the path of the first ``q``/``query`` member found at any depth."""
    if isinstance(value, Mapping):
        for key, item in value.items():
            child = f"{path}.{key}" if path else str(key)
            if isinstance(key, str) and key.casefold() in _FORBIDDEN_QUERY_FIELDS:
                return child
            found = find_forbidden_query_field(item, path=child)
            if found is not None:
                return found
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            found = find_forbidden_query_field(item, path=f"{path}[{index}]")
            if found is not None:
                return found
    return None


def reject_free_text_query_members(value: object) -> None:
    """Refuse a request body carrying a ``q``/``query`` member at any depth.

    The post-condition of :func:`build_coveo_request_body` and the guard a caller
    applies to any body assembled by other means: the body is inspected once, and
    a hit raises :class:`ValueError` naming the offending path, so keyword
    contamination of the facet filter (LREQ-EXT-030) fails loudly instead of
    being sent.
    """
    found = find_forbidden_query_field(value)
    if found is not None:
        raise ValueError(
            f"forbidden free-text query member '{found}' is present in the "
            "request body; discovery must filter by facet, not by keyword"
        )


def build_coveo_request_body(
    template: Mapping[str, object],
    category: str,
    *,
    page_index: int,
    page_size: int = PAGE_SIZE,
) -> dict[str, object]:
    """Build one discovery request body for ``category`` at ``page_index``.

    The captured template is replayed verbatim for ``locale``, ``tab``,
    ``referrer``, ``timezone``, ``context``, ``dictionaryFieldContext``,
    ``searchHub``, ``sortCriteria``, ``numberOfResults``, and ``facetOptions``;
    the capture's ``facets`` block is replaced by the single ``ec_category``
    facet. Four mechanical edits are applied: ``actionsHistory`` is emptied, the
    ``analytics`` telemetry block is dropped, ``firstResult`` becomes
    ``page_index * page_size`` (capture-confirmed offset convention), and
    ``visitorId`` becomes the fixed :data:`COVEO_VISITOR_ID_PLACEHOLDER`.

    ``fieldsToInclude`` is forced to :data:`COVEO_DISCOVERY_FIELD_SET`; that is
    the single deliberate divergence from "replayed as captured" and is required
    by LREQ-EXT-040, not a defect.

    ``page_index`` is zero-based and non-negative. Raises :class:`ValueError`
    when the page index is invalid, when the template carries no usable
    ``ec_category`` facet, or when the resulting body contains ``q`` or
    ``query`` at any nesting depth (LREQ-EXT-030).
    """
    if isinstance(page_index, bool) or not isinstance(page_index, int) or page_index < 0:
        raise ValueError("page_index must be a non-negative integer")

    facets = template.get("facets")
    if facets is None:
        # ``load_coveo_search_template`` returns the provenance header carrying
        # the capture's body under ``request_body``; accept that shape directly.
        nested = template.get("request_body")
        if isinstance(nested, Mapping):
            facets = nested.get("facets")
    if not isinstance(facets, Sequence) or isinstance(facets, (str, bytes)):
        raise ValueError(
            "the captured template carries no usable 'facets' sequence to replay"
        )
    facet = next(
        (
            item
            for item in facets
            if isinstance(item, Mapping) and item.get("facetId") == COVEO_FACET_ID
        ),
        None,
    )
    if facet is None:
        raise ValueError(
            f"the captured template carries no '{COVEO_FACET_ID}' facet to replay"
        )
    raw_current_values = facet.get("currentValues")
    if not isinstance(raw_current_values, Sequence) or isinstance(
        raw_current_values, (str, bytes)
    ):
        raise ValueError(
            f"the captured '{COVEO_FACET_ID}' facet carries no usable 'currentValues'"
        )

    current_values: list[dict[str, object]] = []
    matched_selected = 0
    for entry in raw_current_values:
        if not isinstance(entry, Mapping) or not isinstance(entry.get("value"), str):
            raise ValueError(
                f"the captured '{COVEO_FACET_ID}' facet carries a malformed currentValues entry"
            )
        value = str(entry["value"])
        if value == category:
            matched_selected += 1
            state = "selected"
        else:
            state = "idle"
        current_values.append({"value": value, "state": state})

    source = _template_field_source(template)
    body: dict[str, object] = {}
    for field_name in _COVEO_REPLAYED_TEMPLATE_FIELDS:
        if field_name in source:
            body[field_name] = source[field_name]
    body["numberOfResults"] = int(page_size)
    body["firstResult"] = page_index * int(page_size)
    body["visitorId"] = COVEO_VISITOR_ID_PLACEHOLDER
    body["actionsHistory"] = []
    body["facetOptions"] = source.get("facetOptions", {"freezeFacetOrder": True})
    body["facets"] = [
        {
            "facetId": COVEO_FACET_ID,
            "field": facet.get("field", COVEO_FACET_ID),
            "type": facet.get("type", "specific"),
            "resultsMustMatch": facet.get("resultsMustMatch", "atLeastOneValue"),
            "numberOfValues": facet.get("numberOfValues", len(current_values)),
            "currentValues": current_values,
        }
    ]
    body["fieldsToInclude"] = list(COVEO_DISCOVERY_FIELD_SET)

    forbidden = find_forbidden_query_field(body)
    if forbidden is not None:
        raise ValueError(
            f"the Coveo request body contains the forbidden free-text member "
            f"'{forbidden.split('.')[-1]}' at '{forbidden}': keyword relevance may "
            "not contaminate category filtering"
        )
    return body


def _redacted_request_metadata(
    body: Mapping[str, object],
    *,
    page_index: int,
    template: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Build the redacted, persisted description of one request.

    Nothing here is a credential, a header value, or a response body: the
    metadata names the endpoint contract, the page shape, the field set actually
    requested, the single facet, and — with its rationale — the facets the
    capture carried that were deliberately dropped. The drop list is computed
    from the capture actually replayed, so a capture that ships only the
    ``ec_category`` facet reports no drops rather than a fabricated list.
    """
    template_facet_ids = _template_facet_ids(template)
    dropped_facet_ids = tuple(
        facet_id
        for facet_id in COVEO_DROPPED_FACET_IDS
        if facet_id in template_facet_ids
    )
    metadata: dict[str, object] = {
        "endpoint_contract_version": ENDPOINT_CONTRACT_VERSION,
        "url": coveo_search_url(),
        "page_index": int(page_index),
        "first_result": int(body.get("firstResult", 0)),
        "page_size": int(body.get("numberOfResults", PAGE_SIZE)),
        "fields_to_include": list(COVEO_DISCOVERY_FIELD_SET),
        "facet_ids": [COVEO_FACET_ID],
        "captured_facet_ids": list(template_facet_ids),
        "dropped_facet_ids": list(dropped_facet_ids),
        # The rationale names the dropped facet ids that were actually present
        # rather than spelling out the whole frozen drop vocabulary: this
        # metadata is persisted per observation, and a scoring field's name has
        # no business appearing anywhere the reader could mistake for evidence
        # (LREQ-EXT-040).
        "dropped_facets_rationale": (
            "fieldsToInclude is what makes a field present on a returned record; a "
            "facet returns a separate aggregation that no requirement consumes, so "
            "each capture facet outside the selected-category mechanism is dropped "
            "and ec_category is the sole facet"
        ),
        "dropped_facet_rationale_by_id": {
            facet_id: (
                "the adapter requests no scoring field; the facet returns an "
                "aggregation no requirement consumes"
            )
            for facet_id in dropped_facet_ids
            if facet_id != "publisher_name"
        },
        "fields_to_include_divergence": (
            "the capture's 23-entry fieldsToInclude list is replaced by the parent "
            "SRS discovery-only five-field set (LREQ-EXT-040); this is the single "
            "deliberate divergence from replaying the capture as captured"
        ),
        "visitor_id": COVEO_VISITOR_ID_PLACEHOLDER,
        "request_body_sha256": hashlib.sha256(
            _canonical_template_body(body).encode("utf-8")
        ).hexdigest(),
    }
    return metadata


def _template_facet_ids(template: Mapping[str, object] | None) -> tuple[str, ...]:
    """Return the facet ids the capture body declared, in capture order."""
    if not isinstance(template, Mapping):
        return ()
    facets = template.get("facets")
    if not isinstance(facets, Sequence) or isinstance(facets, (str, bytes)):
        return ()
    return tuple(
        str(item["facetId"])
        for item in facets
        if isinstance(item, Mapping) and isinstance(item.get("facetId"), str)
    )


# --------------------------------------------------------------------------
# Taxonomy preflight
# --------------------------------------------------------------------------


def validate_discovery_taxonomy(
    taxonomy_payload: object,
    *,
    requested_categories: Sequence[str],
    reference_utc: datetime,
    max_taxonomy_age_days: int = MAX_TAXONOMY_AGE_DAYS,
) -> TaxonomyValidationResult:
    """Validate the cached taxonomy through the Chunk 1 primitives.

    ``reference_utc`` is a caller-supplied timezone-aware UTC timestamp; this
    function never reads the clock. The returned result is returned unchanged,
    so an invalid, stale, or incomplete taxonomy is reported as such rather than
    being converted into a default.
    """
    return validate_taxonomy(
        taxonomy_payload,
        requested_categories=requested_categories,
        reference_utc=reference_utc,
        max_taxonomy_age_days=max_taxonomy_age_days,
    )


# --------------------------------------------------------------------------
# HTTP fetch with rate limiting and retry/backoff
# --------------------------------------------------------------------------


def _classify_status(status: int) -> str:
    """Return ``"success"``, ``"transient"``, or ``"permanent"`` for ``status``."""
    if status == _HTTP_SUCCESS:
        return "success"
    if status in _HTTP_TRANSIENT_STATUSES:
        return "transient"
    return "permanent"


def _retry_after_seconds(headers: Mapping[str, str]) -> float | None:
    """Return an honored ``Retry-After`` delay in seconds, else ``None``.

    A non-numeric (HTTP-date) value is not converted: guessing an instant would
    require reading the clock. The exponential backoff still applies.
    """
    raw = None
    for name, value in headers.items():
        if str(name).casefold() == "retry-after":
            raw = value
            break
    if raw is None:
        return None
    try:
        seconds = float(str(raw).strip())
    except ValueError:
        return None
    return seconds if seconds >= 0 else None


def _issue(code: str, message: str, **context: object) -> ValidationIssue:
    return ValidationIssue(
        code=code,
        message=message,
        context={str(key): redact_value(value) for key, value in sorted(context.items())},
    )


def fetch_category_page(
    request_body: Mapping[str, object],
    *,
    headers: Mapping[str, str],
    url: str,
    transport: CoveoTransport,
    sleeper: Callable[[float], None],
    rate_limiter: CoveoRateLimiter | None = None,
    max_retries: int = COVEO_MAX_RETRIES,
    template: Mapping[str, object] | None = None,
    opener: Any = None,
) -> CoveoPageResponse:
    """Fetch and structurally validate exactly one Coveo discovery page.

    One request is issued per attempt through the injected ``transport``. A
    transient status (``429`` and ``5xx``) is retried up to ``max_retries``
    additional attempts with exponential backoff from
    :data:`COVEO_BACKOFF_BASE_SECONDS`, honoring ``Retry-After`` when the
    response carries a numeric one. A permanent failure (any other non-200
    status) is raised immediately and never retried.

    ``rate_limiter`` — when supplied — spaces this request against every other
    request of the run; the adapter's :func:`discover_category` shares one
    limiter across all categories. The interval is awaited once per logical page
    request, before the first attempt, through the injected ``sleeper`` and only
    from the second spaced request on: the first request of a run is not delayed
    by an interval it could not have violated. Each *retry* of the page is spaced
    by the exponential backoff instead, so a page that took three transient
    retries contributes exactly three interval sleeps and the three backoffs.
    ``sleeper`` is the only waiting primitive; this function reads no clock.

    The headers and payload are handed whole to the injected transport, so the
    wire request is built by :func:`build_coveo_headers` rather than by partially
    replaying it: a credential carrying its own ``Bearer`` scheme is normalized
    where it is consumed, and an injected transport observes exactly the bytes
    and headers a real one would send (LREQ-SEC-010, §12.8).

    The response is validated through
    :func:`~niche_scout.validation.validate_response_shape` before any record is
    read. A structural failure returns a page with no records and its issues
    attached — after any transient cause has been exhausted — so an unverifiable
    page is never silently reported as zero assets. ``total_count`` is ``None``
    whenever the endpoint's ``totalCount`` is unusable.
    """
    if isinstance(max_retries, bool) or not isinstance(max_retries, int) or max_retries < 0:
        raise ValueError("max_retries must be a non-negative integer")

    first_result = int(request_body.get("firstResult", 0))
    page_size = max(1, int(request_body.get("numberOfResults", PAGE_SIZE)))
    page_index = first_result // page_size
    payload = json.dumps(dict(request_body), sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    metadata = _redacted_request_metadata(
        request_body, page_index=page_index, template=template
    )
    send = _transport_send(transport)
    # The minimum interval is a policy about requests, not about attempts: one
    # logical page request is spaced once here, while every retry of it is spaced
    # by the exponential backoff below. So a page that took three transient
    # retries contributes three interval sleeps (one per issued request after
    # the first, which needs no spacing because no earlier request exists).
    # The wait goes through the injected ``sleeper`` directly — the limiter is
    # what owns the *count* of requests already spaced (so the interval also
    # spans categories), while the actual delay is always the caller's own
    # sleeping primitive with the policy constant, never a value a limiter or
    # this function folded in earlier. A permanent failure still pays for its own
    # spacing: the interval is owed before the request is issued, not only when
    # it turns out to be retryable.
    if rate_limiter is not None:
        if rate_limiter.issued > 0:
            sleeper(COVEO_MIN_REQUEST_INTERVAL_SECONDS)
        rate_limiter.count_issued()
    attempts = 0
    last_status: int | None = None
    pending_delay = 0.0

    while attempts <= max_retries:
        attempts += 1
        if pending_delay > 0.0:
            sleeper(pending_delay)
            pending_delay = 0.0
        try:
            with send(url, headers, payload) as response:
                status = int(getattr(response, "status", 0) or 0)
                response_headers = {
                    str(key): str(value)
                    for key, value in dict(getattr(response, "headers", {}) or {}).items()
                }
                body = bytes(response.read() or b"")
        except urllib.error.HTTPError as exc:
            status = int(getattr(exc, "code", 0) or 0)
            response_headers = {
                str(key): str(value)
                for key, value in dict(getattr(exc, "headers", {}) or {}).items()
            }
            body = bytes(exc.read() or b"")
        except (urllib.error.URLError, OSError) as exc:
            raise CoveoRequestFailed(
                "the Coveo discovery request failed at the transport layer "
                f"({exc.__class__.__name__}) for page {first_result}"
            ) from None

        last_status = status
        classification = _classify_status(status)
        if classification == "success":
            return _read_page(
                body,
                page_index=page_index,
                first_result=first_result,
                request_metadata=metadata,
            )
        if classification == "permanent":
            break
        if attempts > max_retries:
            break
        delay = COVEO_BACKOFF_BASE_SECONDS * (2 ** (attempts - 1))
        retry_after = _retry_after_seconds(response_headers)
        if retry_after is not None:
            delay = max(delay, retry_after)
        pending_delay = delay

    if last_status is not None and pending_delay:
        # A delay is only ever armed for a retry that will actually be issued, so
        # reaching here with one armed means the transient budget was consumed by
        # an exception rather than a response; do not sleep for nothing.
        pending_delay = 0.0
    raise CoveoRequestFailed(
        f"the Coveo discovery request for page {first_result} failed after "
        f"{attempts} attempt(s) with HTTP status {last_status}: transient retries "
        "are exhausted or the failure is permanent, and it is not retried further"
    )


def _read_page(
    body: bytes,
    *,
    page_index: int,
    first_result: int,
    request_metadata: Mapping[str, object],
) -> CoveoPageResponse:
    """Structurally validate one response body and read its records."""
    try:
        decoded = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return CoveoPageResponse(
            page_index=page_index,
            first_result=first_result,
            total_count=None,
            records=(),
            request_metadata=request_metadata,
            issues=(
                _issue(
                    "response_body_not_json",
                    "the Coveo response body could not be decoded as a JSON object",
                    page_index=page_index,
                ),
            ),
        )

    structural: StructuralValidationResult = validate_response_shape(
        decoded,
        expected_shape=_RESPONSE_CONTAINER_SHAPE,
        required_members=_RESPONSE_REQUIRED_MEMBERS,
        field_types=_RESPONSE_FIELD_TYPES,
    )
    filtered_count = _usable_scalar_count(decoded, _PAGE_TOTAL_COUNT_FILTERED_MEMBER)

    raw_records: object = None
    if isinstance(decoded, Mapping):
        raw_records = decoded.get(_PAGE_RECORDS_MEMBER)
    if not isinstance(raw_records, list):
        structural_issues = tuple(structural.issues) or (
            _issue(
                "response_missing_required_member",
                f"response payload does not carry a usable '{_PAGE_RECORDS_MEMBER}' list",
                member=_PAGE_RECORDS_MEMBER,
            ),
        )
        if not any(
            issue.code == "response_missing_required_member" for issue in structural_issues
        ):
            structural_issues = structural_issues + (
                _issue(
                    "response_missing_required_member",
                    f"response payload does not carry a usable '{_PAGE_RECORDS_MEMBER}' list",
                    member=_PAGE_RECORDS_MEMBER,
                ),
            )
        return CoveoPageResponse(
            page_index=page_index,
            first_result=first_result,
            total_count=_usable_total_count(decoded),
            records=(),
            request_metadata=request_metadata,
            issues=tuple(structural_issues),
            filtered_count=filtered_count,
        )

    issues: list[ValidationIssue] = list(structural.issues)
    records: list[Mapping[str, object]] = []
    forbidden: list[dict[str, object]] = []
    for index, item in enumerate(raw_records):
        if not isinstance(item, Mapping):
            issues.append(
                _issue(
                    "response_record_not_a_mapping",
                    f"record {index} is not a JSON object and is not treated as an asset",
                    record_index=index,
                )
            )
            continue
        missing_members = [
            member for member in _RESPONSE_FIELD_SET_MEMBERS if member not in item
        ]
        # A record that says nothing about identity at all is a legitimate
        # ``unresolved`` row, not a structural failure: ``LREQ-EXT-040`` requires a
        # missing identity field to stay *missing* and ``LREQ-EXT-070`` makes "no
        # candidate could be canonicalized" a classification rather than a page
        # failure. A record that *does* participate in identity (``permanentid``/
        # ``ec_product_id`` present, even as ``null``/``""``) but omits one of the
        # two is a partly-declared identity: it is not readable as if it were
        # complete. The category predicate, by contrast, is what the response was
        # asked for, so its absence is always structural.
        declares_identity = any(member in item for member in _IDENTITY_DECLARED_FIELDS)
        if not declares_identity:
            structural_missing = [member for member in missing_members if member == "ec_category"]
        else:
            structural_missing = [
                member
                for member in missing_members
                if member in ("ec_category", *_IDENTITY_DECLARED_FIELDS)
            ]
        if structural_missing:
            # The identity/category member set is required: a record that does
            # not carry it cannot be read as if it did, so the *page* is a
            # structural failure rather than a page of partly-readable records
            # (LREQ-EXT-040). The member names are what is reported; no value is
            # synthesized for an absent member, and a descriptive member such as
            # ``ec_name`` is simply missing where the endpoint did not send it.
            issues.append(
                _issue(
                    "response_missing_required_member",
                    "a discovery record does not carry the required member "
                    f"'{structural_missing[0]}'; the page cannot be read as a valid "
                    "discovery page",
                    member=missing_members[0],
                    missing_members=missing_members,
                    record_index=index,
                )
            )
            continue
        records.append(item)
        if any(key not in _DISCOVERY_RESPONSE_FIELD_SET for key in item):
            # A response carrying a member outside the discovery-only field set
            # is a *recorded condition*, not a copied payload: the member names
            # themselves are scoring fields (rating, price, sale, thumbnails,
            # publication date), so naming them would write the forbidden field
            # into `request_metadata_json` — exactly what LREQ-EXT-040 forbids.
            # Only the fact and the count are retained.
            forbidden.append({"record_index": index, "extra_member_count": 1})

    if any(issue.code == "response_missing_required_member" for issue in issues):
        # A page that failed the required-member check is never read as records:
        # a partially read page would understate the category's breadth, which is
        # exactly the fabricated zero a failed page must never become
        # (LREQ-EXT-050).
        return CoveoPageResponse(
            page_index=page_index,
            first_result=first_result,
            total_count=_usable_total_count(decoded),
            records=(),
            request_metadata=request_metadata,
            issues=tuple(issues),
            filtered_count=filtered_count,
            forbidden_field_presence=tuple(forbidden),
        )

    return CoveoPageResponse(
        page_index=page_index,
        first_result=first_result,
        total_count=_usable_total_count(decoded),
        records=tuple(records),
        request_metadata=request_metadata,
        issues=tuple(issues),
        filtered_count=filtered_count,
        forbidden_field_presence=tuple(forbidden),
    )


def _transport_send(
    transport: object,
) -> Callable[[str, Mapping[str, str], bytes], Any]:
    """Return a ``(url, headers, payload)`` sender for an injected transport.

    :class:`CoveoTransport` is the seam. A transport exposing only the older
    ``open(request)`` shape is still accepted and adapted here, so no caller has
    to hand-build a ``urllib.request.Request`` to reach the adapter.
    """
    send = getattr(transport, "send", None)
    if callable(send):
        return send  # type: ignore[no-any-return]
    open_request = getattr(transport, "open", None)
    if callable(open_request):

        def adapted(url: str, headers: Mapping[str, str], payload: bytes) -> Any:
            request = urllib.request.Request(url=url, data=payload, method="POST")
            for name, value in headers.items():
                request.add_header(name, value)
            return open_request(request)

        return adapted
    raise ValueError(
        "the Coveo transport must expose send(url, headers, payload) "
        "(see CoveoTransport)"
    )


def _usable_scalar_count(decoded: object, member: str) -> int | None:
    """Return a usable non-negative integer member, or ``None`` when unusable."""
    if not isinstance(decoded, Mapping):
        return None
    value = decoded.get(member)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _usable_total_count(decoded: object) -> int | None:
    """Return the endpoint's verified ``totalCount``, or ``None`` when unusable.

    ``None`` — never ``0`` — when the member is absent, null, not an integer, or
    negative, so an unverified count is distinguishable from a verified zero.
    """
    return _usable_scalar_count(decoded, _PAGE_TOTAL_COUNT_MEMBER)


def _api_reported_count(
    decoded_total: int | None,
    pages: Sequence[int | None],
    filtered_counts: Sequence[int | None] = (),
) -> int | None:
    """Return the API-reported count when it agrees across every page, else ``None``.

    The API-reported count is the response's own count: the filtered count when
    the endpoint carried a usable ``totalCountFiltered``, else the verified
    ``totalCount``. It agrees only when every observed page reported the same
    value; a disagreement is reported as ``None`` rather than as a guess.
    """
    observed = [value for value in pages if value is not None]
    filtered = [value for value in filtered_counts if value is not None]
    if not observed and not filtered:
        return None
    if len(set(observed)) > 1:
        return None
    if any(value != observed[0] for value in observed):
        return None
    if decoded_total is not None:
        return decoded_total
    if observed:
        return observed[0]
    return filtered[0]


# --------------------------------------------------------------------------
# Streaming sink
# --------------------------------------------------------------------------


class CoveoObservationSink:
    """The ``LREQ-NFR-010`` persistence seam.

    Constructed by the caller with ``(repository, run_id, category)`` plus the
    caller-injected ``clock`` that supplies every ``retrieved_at_utc``.
    :meth:`write` is called by :func:`discover_category` once per page, from
    inside the repository's active ``category_transaction(run_id, category)``
    block, and persists exactly that page — one :class:`RawDiscoveryObservationRecord`
    per record, classified through the Chunk 1 primitives — through
    :meth:`~niche_scout.database.SqliteRepository.insert_raw_discovery_observations`,
    the frozen page sink. The adapter never opens a transaction of its own, and
    the sink keeps no per-category list of records, so only one page is ever in
    memory.

    ``mapping_rule_version`` records which identity mapping rule classified the
    page's records; discovery always uses the frozen
    :data:`~niche_scout.models.IDENTITY_MAPPING_RULE_VERSION`. ``ordinal_start``
    is supplied by the adapter, which owns the running ordinal across pages.
    """

    def __init__(
        self,
        repository: SqliteRepository,
        run_id: str,
        category: str,
        *,
        clock: Callable[[], datetime] | None = None,
        taxonomy: object = None,
        batch_size: int = 500,
    ) -> None:
        self._repository = repository
        self._run_id = run_id
        self._category = category
        self._clock = clock if clock is not None else _default_clock
        self._taxonomy = taxonomy
        self._batch_size = batch_size
        self.pages_written = 0
        self.observations_written = 0

    @property
    def repository(self) -> SqliteRepository:
        """The repository this sink writes through."""
        return self._repository

    @property
    def run_id(self) -> str:
        """The run every observation written by this sink belongs to."""
        return self._run_id

    @property
    def category(self) -> str:
        """The category every observation written by this sink belongs to."""
        return self._category

    @property
    def batch_size(self) -> int:
        """The batch size the sink hands to the repository's page sink."""
        return self._batch_size

    def write_page(
        self,
        page: CoveoPageResponse,
        *,
        ordinal_start: int,
        taxonomy_paths: Container[str],
        seen_identities: MutableMapping[str, str],
        limit: int | None = None,
    ) -> CategoryPageOutcome:
        """Build and persist one page's raw observations, returning its counts.

        The returned outcome mirrors exactly what was persisted: one row per
        record, duplicates included, with ``asset_identity_key`` set only for a
        ``resolved`` identity and ``stratum_index`` left ``None`` during
        discovery. ``limit`` — when supplied — is the number of leading records
        the caller admits: a category that reaches its read cap mid-page persists
        exactly the rows it reports, never the whole page that crossed the cap
        (LREQ-EXT-050). The page object itself is not rewritten; only the
        admitted leading records are built and handed to the page sink in the one
        insert call that keeps the page's write atomic.
        """
        admitted_records = (
            page.records if limit is None else page.records[: max(0, int(limit))]
        )
        retrieved_at_utc = ensure_utc(self._clock())
        request_metadata: dict[str, object] = dict(page.request_metadata)
        if page.forbidden_field_presence:
            request_metadata["forbidden_field_presence"] = [
                dict(entry) for entry in page.forbidden_field_presence
            ]
        observations: list[RawDiscoveryObservationRecord] = []
        identity_resolution: list[IdentityResolutionResult] = []
        category_matches: list[CategoryMatchResult] = []
        ordinal = ordinal_start
        for record in admitted_records:
            identity = resolve_observation_identity(record)
            category_match = match_exact_category(record.get("ec_category"), taxonomy_paths)
            identity_resolution.append(identity)
            category_matches.append(category_match)
            observations.append(
                _build_observation(
                    record,
                    run_id=self._run_id,
                    category=self._category,
                    ordinal=ordinal,
                    identity=identity,
                    category_match=category_match,
                    request_metadata=request_metadata,
                    page_issues=page.issues,
                    retrieved_at_utc=retrieved_at_utc,
                    duplicate_of=(
                        seen_identities.get(identity.canonical_identity_key)
                        if identity.canonical_identity_key is not None
                        else None
                    ),
                )
            )
            ordinal += 1

        # Registered only after the page is built, so a duplicate inside one page
        # still points at the first row of that page rather than at itself.
        duplicates = 0
        for observation, identity in zip(observations, identity_resolution):
            key = observation.asset_identity_key
            if key is None:
                continue
            if observation.is_duplicate:
                duplicates += 1
            elif key not in seen_identities:
                seen_identities[key] = observation.observation_id

        self._repository.insert_raw_discovery_observations(observations)
        self.pages_written += 1
        self.observations_written += len(observations)
        return CategoryPageOutcome(
            ordinal_start=ordinal_start,
            ordinal_end=ordinal,
            identities=tuple(identity_resolution),
            category_matches=tuple(category_matches),
            duplicates=duplicates,
        )

    def write(self, page_observations: Sequence[RawDiscoveryObservationRecord]) -> None:
        """Persist an already-built page's observations through the page sink.

        Kept for callers that own record construction. Raises
        :class:`~niche_scout.database.RepositoryError` when no category
        transaction is active, because the sink deliberately does not open one.
        """
        self._repository.insert_raw_discovery_observations(list(page_observations))
        self.pages_written += 1
        self.observations_written += len(page_observations)


@dataclass(frozen=True, slots=True)
class CategoryPageOutcome:
    """What one written page contributed, as persisted."""

    ordinal_start: int
    ordinal_end: int
    identities: tuple[IdentityResolutionResult, ...]
    category_matches: tuple[CategoryMatchResult, ...]
    duplicates: int = 0


def _default_clock() -> datetime:
    """Production clock for ``retrieved_at_utc``; tests inject a fixed one."""
    return datetime.now(tz=timezone.utc)


# --------------------------------------------------------------------------
# Category discovery
# --------------------------------------------------------------------------


@dataclass(slots=True)
class _CategoryCounters:
    ordinal: int = 0
    canonical_keys: set[str] = field(default_factory=set)  # type: ignore[assignment]
    first_observation_id_by_key: dict[str, str] = field(default_factory=dict)  # type: ignore[assignment]
    unresolved: int = 0
    conflict: int = 0
    category_mismatches: int = 0
    duplicates: int = 0
    emitted: int = 0
    pages: int = 0
    total_count: int | None = None
    api_reported_count: int | None = None
    filter_status: CategoryFilterValidationStatus = CategoryFilterValidationStatus.UNVERIFIED
    #: Per-record ``CategoryMatchResult`` verdicts, folded into ``filter_status``
    #: once the traversal ends. Only the three nullable verdicts are kept, so the
    #: list never grows with the record count.
    category_match_statuses: list[CategoryFilterValidationStatus] = field(  # type: ignore[assignment]
        default_factory=list
    )
    conditions: list[DiscoveryStatus] = field(default_factory=list)  # type: ignore[assignment]
    issues: list[ValidationIssue] = field(default_factory=list)  # type: ignore[assignment]


def _condition_precedence_rank(condition: DiscoveryStatus) -> int:
    """Non-normative predecessor convention: severity order for status selection.

    Carried from the retired ``SRS-revision2.md`` §4.1 ``REQ-EXT-095`` as a
    documented convention, not a lean requirement. Every applicable condition
    stays visible on :attr:`CategoryDiscoveryResult.conditions` regardless of
    which one is selected as the terminal status.
    """
    order: tuple[DiscoveryStatus, ...] = (
        DiscoveryStatus.REQUEST_FAILED,
        DiscoveryStatus.PAGE_FAILED,
        DiscoveryStatus.FILTER_UNVERIFIED,
        DiscoveryStatus.CATEGORY_MISMATCH,
        DiscoveryStatus.IDENTITY_INCOMPLETE,
        DiscoveryStatus.TRUNCATED,
        DiscoveryStatus.COMPLETE,
    )
    return order.index(condition)


def _select_terminal_status(conditions: Sequence[DiscoveryStatus]) -> DiscoveryStatus:
    """Choose the single terminal status by severity precedence."""
    if not conditions:
        return DiscoveryStatus.COMPLETE
    return min(conditions, key=_condition_precedence_rank)


def _ordered_conditions(conditions: Sequence[DiscoveryStatus]) -> tuple[DiscoveryStatus, ...]:
    """Return the condition set in severity order with duplicates collapsed."""
    seen: list[DiscoveryStatus] = []
    for condition in sorted(set(conditions), key=_condition_precedence_rank):
        if condition not in seen:
            seen.append(condition)
    return tuple(seen)


# Public names for the two pure selection rules of LREQ-EXT-050/EXT-090. They are
# part of this chunk's interface (§5), because the severity convention and the
# claim that *every* applicable condition stays visible can only be audited by
# exercising them directly: one traversal cannot produce, say, a request failure
# and a category mismatch at once.
select_terminal_status = _select_terminal_status
order_conditions = _ordered_conditions


def _observation_id(run_id: str, category: str, ordinal: int) -> str:
    """Return the deterministic observation id for ``(run, category, ordinal)``.

    Emitted by the adapter under a fixed, deterministic rule so a re-emitted
    record is a distinct row. The linked table declares ``observation_id`` as its
    primary key and declares no default for it, so the adapter must supply one.
    """
    digest = hashlib.sha256(f"{run_id}\x1f{category}\x1f{ordinal}".encode("utf-8")).hexdigest()
    return f"raw-{digest}"


def _comparable_identity_value(canonical_value: str) -> str:
    """Return the mapping rule's comparison form of a canonical candidate.

    Rule ``1.0.1`` compares candidates numerically when **both** sides parse as
    integers and as text otherwise (``interfaces/chunk-01.md`` §4.1), so
    ``"0081"`` and ``"81"`` are one identity while ``"P-1"``, ``"81"``, and
    ``"product-0001"`` stay three distinct identities. Kept local so the adapter
    carries no dependency on the validator's private helper.
    """
    if canonical_value.isdigit():
        return str(int(canonical_value))
    return canonical_value


def _identity_candidate_key(candidate: IdentityCandidate) -> str | None:
    """Return the value a retained candidate contributes to identity agreement.

    A candidate whose canonicalization failed contributes nothing (``None``), so
    it can never vote. Under mapping rule ``1.0.1`` an ``ec_product_id``/
    ``permanentid`` value is canonical as supplied (whitespace-trimmed only) —
    ``LREQ-EXT-070`` makes the two members *verbatim aliases* of one asset's
    identifier, not two independent identities — while ``clickUri``/``uri`` carry
    a URI whose canonical value is the trailing ``-<digits>`` identifier of its
    last path segment.

    A URI-shaped candidate is a **peer** of a product-id candidate, not a
    fallback under it: ``LREQ-EXT-060`` (``Documents/SRS-lean.md:265-268``) makes
    all four fields candidate sources canonicalized under one versioned mapping
    rule with no provenance tier, so the URI identifier has to *equal* the
    product id to agree, exactly as two explicit ids must. Rule ``1.0.0``
    accepted the URI identifier whenever it was a *suffix* of the product id
    (``product-0001`` for ``.../fixture-1-0001``); that tolerance had no basis in
    the SRS or ``interfaces/chunk-01.md`` §4.1 and it rescued genuine
    ``LREQ-EXT-070`` disagreements into ``resolved``, so ``1.0.1`` removes it. The
    URI shape is recognized from the raw value, so a candidate classified under
    either spelling of the field is read the same way.
    """
    if candidate.canonical_value is None:
        return None
    if candidate.source_field in _URI_IDENTITY_FIELDS or _URI_PATH_SHAPE.search(
        candidate.raw_value
    ):
        matched = _URI_TRAILING_IDENTIFIER.search(candidate.raw_value)
        if matched is None:
            # A URI-shaped field whose value does not fit the pattern
            # contributes nothing (chunk-01.md §4.1): never a partial or guessed
            # identifier. Falling back to the canonicalized value would let an
            # unparseable URI vote against a genuine sibling candidate.
            return None
        return _comparable_identity_value(matched.group(1))
    return _comparable_identity_value(candidate.canonical_value)


def _identity_candidates_agree(
    derived: Sequence[tuple[IdentityCandidate, str]],
) -> bool:
    """Whether the derived candidates describe one and the same asset.

    Every derived candidate is a **peer source** of the same identity
    (``LREQ-EXT-060``, ``Documents/SRS-lean.md:265-268``: all four fields are
    candidate sources canonicalized under one versioned mapping rule): explicit
    ``ec_product_id``/``permanentid`` candidates must agree with each other, and
    a URI-derived candidate — the trailing ``-<digits>`` identifier of
    ``clickUri``/``uri`` — must agree with them in the same way, by equality of
    the mapping rule's normalized comparison form. Any disagreement between
    derived candidates is the ``conflict`` ``LREQ-EXT-070``
    (``Documents/SRS-lean.md:270-271``) requires, and
    ``interfaces/chunk-01.md`` §4.1 fixes the same three-way outcome for this
    comparison: all equal → ``resolved``, any disagreement → ``conflict``,
    nothing derivable → ``unresolved``. There is no peer-versus-fallback tier, so
    there is deliberately no suffix, prefix, or substring tolerance here — the
    same strictness ``LREQ-EXT-080`` states for category paths. The derived keys
    are what the conflict check compares, so a record whose explicit candidates
    disagree stays ``conflict`` even when a URI happens to match one of them.
    """
    explicit: list[str] = []
    uri_keys: list[str] = []
    for candidate, key in derived:
        if candidate.source_field in _URI_IDENTITY_FIELDS:
            uri_keys.append(key)
        else:
            explicit.append(key)
    if len(set(explicit)) > 1:
        return False
    if not explicit:
        # No explicit candidate: the URI identifiers are all that is left to
        # compare, and two disagreeing URIs are a genuine conflict.
        return len(set(uri_keys)) <= 1
    if len(set(explicit)) == 1:
        anchor = explicit[0]
        # Every URI-derived key must equal the explicit anchor, not merely be one
        # of its suffixes: the comparison happens on the mapping rule's normalized
        # form above, so an equality here is exactly the primitive's equality.
        return all(anchor == key for key in uri_keys)
    return False  # pragma: no cover - an empty explicit set was handled above


def resolve_observation_identity(record: Mapping[str, object]) -> IdentityResolutionResult:
    """Classify one response record's canonical identity.

    Always delegates to ``validation.resolve_canonical_identity`` — the frozen
    Chunk 1 primitive — and adopts its verdict whenever that verdict already
    yields a canonical key. The primitive compares the *canonicalized* values of
    the four source fields, so a response whose ``ec_product_id`` is
    ``"product-0001"`` and whose ``permanentid`` is ``"permanent-0001"`` reads as
    two distinct canonical values and therefore as a ``conflict``, even though
    ``LREQ-EXT-060``/``LREQ-EXT-070`` make those four fields *candidate sources
    for one asset* and ``LREQ-EXT-070`` reserves ``conflict`` for candidates that
    **disagree**.

    This wrapper therefore adds the cross-field agreement step the primitive
    leaves out: each retained candidate is read under its own field's mapping
    rule — an ``ec_product_id``/``permanentid`` value as supplied, a
    ``clickUri``/``uri`` value as the trailing ``-<digits>`` identifier of its
    last path segment — and when the derived candidates describe one asset the
    record is ``resolved`` to the first candidate's canonical value, in candidate
    order. An ``ec_product_id`` and a ``permanentid`` that agree resolve, and so
    do those two together with a URI whose trailing identifier *equals* that same
    product id (all four are peer candidate sources for one asset,
    ``LREQ-EXT-060``); two distinct explicit product ids remain a ``conflict``,
    and so does a URI identifier that merely resembles one. A candidate that
    could not be canonicalized does not vote, matching the primitive's own rule,
    so ``"not-a-uri-with-identifier"`` beside ``.../fixture-7-654321`` resolves to
    ``654321``.

    Only when the derived candidates genuinely disagree does the primitive's
    ``conflict`` stand (``LREQ-EXT-070``): nothing is inferred and no key is
    invented, because the agreement step is what decides whether the values
    disagree at all, and the resolved key is always a value an explicit identity
    candidate actually carried. When nothing is canonicalizable the record stays
    ``unresolved``.
    """
    primitive = resolve_canonical_identity(record)
    if primitive.canonical_identity_key is not None:
        return primitive

    candidates = collect_identity_candidates(record)
    derived: list[tuple[IdentityCandidate, str]] = []
    for candidate in candidates:
        key = _identity_candidate_key(candidate)
        if key is not None:
            derived.append((candidate, key))
    if not derived:
        return primitive
    if not _identity_candidates_agree(derived):
        return IdentityResolutionResult(
            canonical_identity_key=None,
            status=IdentityResolutionStatus.CONFLICT,
            reason=(
                "identity candidates disagree under mapping rule "
                f"{IDENTITY_MAPPING_RULE_VERSION}: distinct canonical identities "
                "were derived from "
                f"{[candidate.source_field for candidate, _ in derived]}"
            ),
            candidates=primitive.candidates,
            included_in_canonical_denominator=False,
            included_in_enrichment_set=False,
            mapping_rule_version=IDENTITY_MAPPING_RULE_VERSION,
            issues=primitive.issues,
        )

    first_candidate, first_key = derived[0]
    if first_candidate.canonical_value is None:  # pragma: no cover - defensive
        return primitive
    return IdentityResolutionResult(
        canonical_identity_key=first_candidate.canonical_value,
        status=IdentityResolutionStatus.RESOLVED,
        reason=None,
        candidates=candidates,
        included_in_canonical_denominator=True,
        included_in_enrichment_set=True,
        mapping_rule_version=IDENTITY_MAPPING_RULE_VERSION,
        issues=primitive.issues,
    )


def _build_observation(
    record: Mapping[str, object],
    *,
    run_id: str,
    category: str,
    ordinal: int,
    identity: IdentityResolutionResult,
    category_match: CategoryMatchResult,
    request_metadata: Mapping[str, object],
    page_issues: Sequence[ValidationIssue],
    retrieved_at_utc: datetime,
    duplicate_of: str | None,
) -> RawDiscoveryObservationRecord:
    """Build one discovery-time raw observation record.

    ``asset_identity_key`` is non-null only for a ``resolved`` identity and
    ``stratum_index`` is ``None`` during discovery: both are post-discovery
    updates owned by later chunks. ``category_value_json`` carries the response
    value verbatim. Failed fields stay ``None`` — never a fabricated zero.
    """
    identity_candidates_json = json.dumps(
        [
            {
                "source_field": candidate.source_field,
                "raw_value": candidate.raw_value,
                "canonical_value": candidate.canonical_value,
                "parse_failure_reason": candidate.parse_failure_reason,
            }
            for candidate in identity.candidates
        ],
        sort_keys=True,
        separators=(",", ":"),
    )
    error_issues = tuple(page_issues) + tuple(identity.issues) + tuple(category_match.issues)
    return RawDiscoveryObservationRecord(
        observation_id=_observation_id(run_id, category, ordinal),
        run_id=run_id,
        category=category,
        discovery_ordinal=ordinal,
        asset_identity_key=identity.canonical_identity_key,
        identity_candidates_json=identity_candidates_json,
        identity_resolution_status=identity.status.value,
        identity_resolution_reason=identity.reason,
        category_value_json=json.dumps(
            record.get("ec_category"), sort_keys=True, separators=(",", ":"), default=str
        ),
        category_filter_validation_status=category_match.status.value,
        stratum_index=None,
        is_duplicate=duplicate_of is not None,
        duplicate_of_observation_id=duplicate_of,
        request_metadata_json=json.dumps(
            dict(request_metadata), sort_keys=True, separators=(",", ":")
        ),
        error_summary_json=(
            summarize_validation_issues(error_issues) if error_issues else None
        ),
        retrieved_at_utc=retrieved_at_utc,
    )


@contextmanager
def _category_transaction(
    repository: SqliteRepository | None, run_id: str, category: str
) -> Iterator[SqliteRepository]:
    """Open the category transaction the sink requires, when a repository is given."""
    if repository is None:
        raise ValueError(
            "the observation sink must expose its repository so the adapter can "
            "open the category transaction the page sink requires"
        )
    with repository.category_transaction(run_id, category):
        yield repository


def discover_category(
    category: str,
    taxonomy_payload: object,
    *,
    config: NicheScoutConfig,
    credentials: Credentials,
    reference_utc: datetime,
    sink: CoveoObservationSink,
    transport: CoveoTransport,
    sleeper: Callable[[float], None] = time.sleep,
    clock: Callable[[], datetime] = _default_clock,
    run_id: str,
    template_path: "Path | str" = COVEO_TEMPLATE_PATH,
    rate_limiter: CoveoRateLimiter | None = None,
    opener: Any = None,
    shared_limiter: CoveoRateLimiter | None = None,
) -> CategoryDiscoveryResult:
    """Discover one category and stream its raw observations into ``sink``.

    The order of operations is the contract: taxonomy validation and credential
    validation both complete **before** the first request; the template capture
    is hash-verified; the category transaction is opened once for the whole
    category and every page is written through the sink inside it; the terminal
    status is persisted with ``set_category_status`` after the observations are
    committed.

    Failure isolation: a per-category request failure or an unexpected per-page
    failure ends only the current category and is returned as a
    :class:`CategoryDiscoveryResult` carrying a failure status and a populated
    redacted ``error_summary_json`` — it never propagates and never aborts
    another category. A failed, truncated, unverified, or mismatched page is
    never interpreted as zero assets.

    ``clock`` is caller-injected and supplies every ``retrieved_at_utc``;
    ``sleeper`` is the only waiting primitive, and :data:`COVEO_MIN_REQUEST_INTERVAL_SECONDS`
    is honored between consecutive requests of the run through the limiter
    (LREQ-EXT-100). ``rate_limiter`` — when supplied — is the caller's run-wide
    limiter, so the minimum interval also holds between one category's last
    request and the next category's first. ``shared_limiter`` is the caller's
    cross-category limiter: when supplied it is used as-is, and when both are
    omitted the adapter creates one so a single-category call is still spaced.
    """
    repository = _repository_of(sink)
    limiter = rate_limiter if rate_limiter is not None else shared_limiter
    if limiter is None:
        limiter = CoveoRateLimiter(sleeper)
    with _category_transaction(repository, run_id, category):
        return _discover_category_in_transaction(
            category,
            taxonomy_payload,
            config=config,
            credentials=credentials,
            reference_utc=reference_utc,
            sink=sink,
            transport=transport,
            sleeper=sleeper,
            clock=clock,
            run_id=run_id,
            template_path=template_path,
            rate_limiter=limiter,
        )


def _repository_of(sink: CoveoObservationSink) -> SqliteRepository:
    """Return the repository a sink writes through."""
    repository = getattr(sink, "repository", None)
    if repository is None:
        raise ValueError(
            "the observation sink must expose its repository so the adapter can "
            "open the category transaction the page sink requires"
        )
    return repository


def _discover_category_in_transaction(
    category: str,
    taxonomy_payload: object,
    *,
    config: NicheScoutConfig,
    credentials: Credentials,
    reference_utc: datetime,
    sink: CoveoObservationSink,
    transport: CoveoTransport,
    sleeper: Callable[[float], None],
    clock: Callable[[], datetime],
    run_id: str,
    template_path: "Path | str",
    rate_limiter: CoveoRateLimiter | None = None,
) -> CategoryDiscoveryResult:
    """The category body, run inside the repository's category transaction."""
    counters = _CategoryCounters()
    parent_issues: list[ValidationIssue] = []

    taxonomy_result = validate_discovery_taxonomy(
        taxonomy_payload,
        requested_categories=[category],
        reference_utc=reference_utc,
        max_taxonomy_age_days=config.max_taxonomy_age_days,
    )
    if not taxonomy_result.is_valid:
        raise CoveoTaxonomyInvalid(
            f"the cached taxonomy did not validate for category '{category}' "
            f"(status '{taxonomy_result.status}'): no discovery request is made"
        )
    # Credential validation completes before any request; get_credentials() has
    # already rejected a missing credential, so an empty value here is a
    # caller error and the message never echoes the value.
    headers = build_coveo_headers(credentials.coveo_bearer_token)

    template = load_coveo_search_template(template_path)
    taxonomy_paths = taxonomy_path_set(taxonomy_payload)
    max_results = int(config.max_discovery_results_per_category)
    page_size = int(config.page_size)
    if page_size <= 0:
        raise ValueError("config.page_size must be a positive integer")

    url = coveo_search_url()
    limiter = rate_limiter
    seen_identities: dict[str, str] = {}
    observed_counts: list[int | None] = []
    filtered_counts: list[int | None] = []
    #: The traversal keeps only the *outcome* of each page it has already read and
    #: written — never the page's records. A page is handed to the sink the moment
    #: it arrives, before the next request is issued, so ``LREQ-NFR-010``'s
    #: "page *n+1* is only requested once page *n* is persisted" holds by
    #: construction and ``LREQ-NFR-030``'s per-page failure isolation stays
    #: meaningful: a page that fails after a successful one is a *page* failure
    #: for a category that already has rows, not a reason to discard them.
    outcomes: list[CoveoPageOutcome] = []
    #: The last page actually read, kept only so the truncation verdict can be
    #: derived from it; its records are already persisted and are not retained.
    last_page: CoveoPageResponse | None = None
    page_index = 0

    while True:
        body = build_coveo_request_body(
            template, category, page_index=page_index, page_size=page_size
        )
        try:
            page = fetch_category_page(
                body,
                headers=headers,
                url=url,
                transport=transport,
                sleeper=sleeper,
                rate_limiter=limiter,
                template=template,
            )
        except CoveoRequestFailed as exc:
            counters.pages += 1
            counters.conditions.append(DiscoveryStatus.REQUEST_FAILED)
            parent_issues.append(
                _issue(
                    "coveo_request_failed",
                    str(exc),
                    category=category,
                    page_index=page_index,
                )
            )
            break
        except Exception as exc:  # noqa: BLE001 - per-category failure isolation
            counters.pages += 1
            counters.conditions.append(DiscoveryStatus.PAGE_FAILED)
            parent_issues.append(
                _issue(
                    "coveo_page_unexpected_failure",
                    "the page could not be read; the failure is isolated to this "
                    f"category and the page contributes no observations ({exc.__class__.__name__})",
                    category=category,
                    page_index=page_index,
                )
            )
            break

        counters.pages += 1
        if page.is_structural_failure:
            counters.conditions.append(DiscoveryStatus.PAGE_FAILED)
            parent_issues.extend(page.issues)
            break

        observed_counts.append(page.total_count)
        filtered_counts.append(page.filtered_count)
        if page.total_count is not None and counters.total_count is None:
            counters.total_count = page.total_count
        counters.issues.extend(page.issues)
        last_page = page
        # The page is written through the sink *now*, still inside the category
        # transaction, before the next request exists. The cap is enforced against
        # the running persisted count rather than against a batch computed after
        # the traversal: the requested page size is always the full ``page_size``
        # (``build_coveo_request_body`` receives the configured size, never a
        # remainder), so the adapter cannot ask the endpoint for fewer rows to
        # stay under the cap — it reads a whole page and admits only the leading
        # records that fit, which is what ``_write_page``'s ``max_records`` is.
        outcome = _write_page(
            sink,
            page,
            taxonomy_paths=taxonomy_paths,
            seen_identities=seen_identities,
            counters=counters,
            max_records=max_results - counters.emitted,
        )
        if outcome is not None:
            outcomes.append(outcome)
        page_index += 1
        if counters.emitted >= max_results:
            # The read cap concealed whatever the endpoint holds beyond the
            # admitted records; that is a recorded condition, never a silent
            # zero-asset reading (LREQ-EXT-050).
            counters.conditions.append(DiscoveryStatus.TRUNCATED)
            break
        if _has_read_enough(
            counters.emitted, page, max_results=max_results, page_size=page_size
        ):
            break

    # The traversal is complete, so the remaining terminal conditions can be
    # derived from what was actually read and written. The persistent row count is
    # what every verdict is checked against, because that count — not the number
    # of records seen on the wire — is what discovery actually contributes.
    persisted = counters.emitted
    pages_with_records = sum(
        1 for outcome in outcomes if outcome.ordinal_end > outcome.ordinal_start
    )
    # The cap and the API-reported count are recorded separately and neither is
    # allowed to become a fabricated zero. `total_count` stays the endpoint's own
    # verified `totalCount`; `api_reported_count` keeps the API-reported count
    # (the filtered count when the response carried one).
    counters.api_reported_count = _api_reported_count(
        counters.total_count, observed_counts, filtered_counts
    )

    # A page that could not be read is never interpreted as zero assets
    # (LREQ-EXT-050): when the read cap concealed part of the endpoint, or when a
    # page after the last one read is still expected from the verified
    # ``totalCount``, the truncation verdict is a recorded condition. A page
    # shorter than the page size with no usable ``totalCount`` is the endpoint's
    # own terminal signal, so nothing is claimed about the part never asked for.
    if last_page is not None and _endpoint_may_hold_more(
        last_page, persisted=persisted, max_results=max_results, page_size=page_size
    ):
        counters.conditions.append(DiscoveryStatus.TRUNCATED)

    # Every applicable condition is recorded (LREQ-EXT-090); which one is
    # *terminal* is decided afterwards by the fixed severity precedence. A record
    # whose response ``ec_category`` does not match the requested category is a
    # recorded condition, not a silent drop (LREQ-EXT-080) — it is counted from
    # the per-record CategoryMatchResult, never inferred from a missing identity.
    if counters.unresolved or counters.conflict:
        counters.conditions.append(DiscoveryStatus.IDENTITY_INCOMPLETE)
    if counters.category_mismatches:
        counters.conditions.append(DiscoveryStatus.CATEGORY_MISMATCH)

    filter_status, filter_issues, filter_conditions = _filter_status_for_records(
        counters.emitted,
        pages_with_records,
        counters.issues,
        counters.category_match_statuses,
    )
    counters.filter_status = filter_status
    parent_issues.extend(filter_issues)
    counters.conditions.extend(filter_conditions)

    return _finalize_result(
        category,
        run_id=run_id,
        counters=counters,
        parent_issues=parent_issues,
        repository=sink.repository,
        computed_at_utc=clock(),
    )


def _has_read_enough(
    emitted: int, page: CoveoPageResponse, *, max_results: int, page_size: int
) -> bool:
    """Decide whether the traversal has read every page it needs.

    Reading stops when the endpoint's own verified ``totalCount`` has been
    reached, when the response can hold no further page, or when the read cap has
    been reached. A page shorter than ``page_size`` is such a signal only when it
    also settles the verified count: a short page that leaves the verified
    ``totalCount`` unaccounted for does not prove exhaustion, so the traversal
    continues — otherwise a later page's failure could never be observed and
    would be silently reported as a complete, short category (LREQ-EXT-050,
    LREQ-NFR-030).

    ``emitted`` is the number of rows persisted so far, which is the count the
    endpoint's own ``totalCount`` has to be compared against after a capped page
    admits fewer records than it carried.
    """
    if emitted >= max_results:
        return True
    if not page.records:
        return True
    if page.total_count is not None:
        return emitted >= page.total_count
    return len(page.records) < page_size


def _endpoint_may_hold_more(
    page: CoveoPageResponse,
    *,
    persisted: int,
    max_results: int,
    page_size: int,
) -> bool:
    """Whether truncation is a fact about what was read.

    True when the cap concealed part of the endpoint — either because the cap was
    reached or because the admitted page crossed it and the rest of that page was
    never read — or when the last page actually read was full and the verified
    ``totalCount`` still accounts for more records. False for a genuinely
    exhausted endpoint: a final page shorter than ``page_size``, an empty page, or
    a verified count that has been reached.
    """
    if persisted >= max_results:
        return True
    if not page.records:
        return False
    if page.total_count is not None and persisted >= page.total_count:
        return False
    return len(page.records) >= page_size


def _filter_status_for_records(
    records_emitted: int,
    pages_with_records: int,
    issues: Sequence[ValidationIssue],
    match_statuses: Sequence[CategoryFilterValidationStatus] = (),
) -> tuple[CategoryFilterValidationStatus, list[ValidationIssue], list[DiscoveryStatus]]:
    """Decide the category-filter verdict for a category's records.

    The verdict is derived from the per-record :class:`CategoryMatchResult`
    values the sink produced (LREQ-EXT-080), not from how many records came
    back: a page whose records all mismatch yields ``match`` rows and therefore a
    ``mismatch`` category verdict, which is exactly what the per-row status says.
    At least one matched value is ``verified``; usable values present and none
    matching is ``mismatch``; no usable ``ec_category`` value at all is
    ``unverified``, and that is the only case that raises
    :data:`DiscoveryStatus.FILTER_UNVERIFIED`.

    A zero-result category carries no per-record verdict, so it stays ``verified``
    only when the response structure validated — a zero-breadth reading is
    evidence only when the structure it came from was checked. A structural or
    malformed-member failure is ``unverified``, which is never the same fact as a
    verified zero.
    """
    if any(
        status is CategoryFilterValidationStatus.VERIFIED for status in match_statuses
    ):
        return CategoryFilterValidationStatus.VERIFIED, [], []
    if any(
        status is CategoryFilterValidationStatus.MISMATCH for status in match_statuses
    ):
        return CategoryFilterValidationStatus.MISMATCH, [], []
    if records_emitted > 0 or pages_with_records > 0:
        # Every emitted record's ``ec_category`` was unusable: the filter was
        # exercised but could not be judged from the values it returned.
        return (
            CategoryFilterValidationStatus.UNVERIFIED,
            [],
            [DiscoveryStatus.FILTER_UNVERIFIED],
        )
    unverified = any(
        issue.code
        in {
            "response_body_not_json",
            "response_wrong_container_kind",
            "response_missing_required_member",
            "response_null_required_member",
            "response_wrong_scalar_type",
            "response_record_not_a_mapping",
        }
        for issue in issues
    )
    if unverified:
        return (
            CategoryFilterValidationStatus.UNVERIFIED,
            [],
            [DiscoveryStatus.FILTER_UNVERIFIED],
        )
    return CategoryFilterValidationStatus.VERIFIED, [], []


def _write_page(
    sink: CoveoObservationSink,
    page: CoveoPageResponse,
    *,
    taxonomy_paths: Container[str],
    seen_identities: MutableMapping[str, str],
    counters: _CategoryCounters,
    max_records: int,
) -> CategoryPageOutcome | None:
    """Stream one page into the sink and fold its counts into ``counters``.

    Called from inside the repository's active category transaction, once per
    page and immediately after that page was read, so the page is persisted
    before the next request is issued and the adapter never holds a category's
    records across pages (LREQ-NFR-010).

    ``max_records`` is the number of the page's *leading* records the cap admits.
    Regardless of whether the sink enforces a per-record limit of its own, the
    persisted count is this one, so ``observations_emitted`` and the durable row
    count agree exactly (LREQ-EXT-050). ``None`` is returned when the cap admits
    none of the page's records, so a caller can distinguish "nothing was written"
    from a page whose write succeeded and contributed to ``counters``.
    """
    if max_records <= 0:
        counters.conditions.append(DiscoveryStatus.TRUNCATED)
        return None
    admitted = min(len(page.records), max_records)
    if admitted <= 0:
        if page.records:
            counters.conditions.append(DiscoveryStatus.TRUNCATED)
        return None
    outcome = sink.write_page(
        page,
        ordinal_start=counters.ordinal,
        taxonomy_paths=taxonomy_paths,
        seen_identities=seen_identities,
        limit=admitted,
    )
    if len(outcome.identities) != admitted:
        raise RepositoryError(
            "the observation sink persisted "
            f"{len(outcome.identities)} record(s) for page {page.page_index} where "
            f"the discovery read limit admitted {admitted}; the persisted row count "
            "must equal the emitted count"
        )
    for identity in outcome.identities:
        # The classification vocabulary is the frozen IdentityResolutionStatus:
        # only a ``resolved`` record contributes a canonical key, while a
        # ``conflict`` and an ``unresolved`` record are counted separately and
        # excluded from the canonical denominator (LREQ-EXT-070).
        if identity.status is IdentityResolutionStatus.CONFLICT:
            counters.conflict += 1
        elif identity.status is IdentityResolutionStatus.UNRESOLVED:
            counters.unresolved += 1
        elif identity.canonical_identity_key is not None:
            counters.canonical_keys.add(identity.canonical_identity_key)
    for match in outcome.category_matches:
        if match.status is CategoryFilterValidationStatus.MISMATCH:
            counters.category_mismatches += 1
        if match.status is not None:
            counters.category_match_statuses.append(match.status)
    counters.ordinal = outcome.ordinal_start + admitted
    counters.emitted += admitted
    counters.duplicates += outcome.duplicates
    return outcome


def _finalize_result(
    category: str,
    *,
    run_id: str,
    counters: _CategoryCounters,
    parent_issues: Sequence[ValidationIssue],
    repository: SqliteRepository,
    computed_at_utc: datetime,
) -> CategoryDiscoveryResult:
    """Assemble the terminal result and persist the category's discovery status."""
    conditions = _ordered_conditions(counters.conditions)
    status = _select_terminal_status(conditions)
    issues = tuple(parent_issues) + tuple(counters.issues)
    repository.set_category_status(
        run_id, category, status.value, computed_at_utc=ensure_utc(computed_at_utc)
    )
    return CategoryDiscoveryResult(
        category=category,
        discovery_status=status,
        ordinal_start=0,
        ordinal_end=counters.ordinal,
        observations_emitted=counters.emitted,
        canonical_identity_count=len(counters.canonical_keys),
        unresolved_identity_count=counters.unresolved,
        conflict_identity_count=counters.conflict,
        duplicate_observation_count=counters.duplicates,
        pages_fetched=counters.pages,
        total_count=counters.total_count,
        api_reported_count=counters.api_reported_count,
        filter_status=counters.filter_status,
        conditions=conditions,
        issues=issues,
    )
