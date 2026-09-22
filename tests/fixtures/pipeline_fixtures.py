"""Inert fixtures for the Chunk 10 pipeline-orchestration suite.

Data and small construction helpers only: this module contains no assertions and
no logic under test, so a defect in it cannot mask an orchestration, isolation,
cutoff, logging, determinism, or provenance defect.

Sources (read, not paraphrased from memory):

- ``Documents/SRS-lean.md`` §3.2 (one-run data flow), §3.3 (``LREQ-ARCH-030``),
  §4.1 (``LREQ-EXT-090``), §4.4 (``LREQ-ID-040``), §8.1 (``LREQ-NRM-020``),
  §9.1 (``LREQ-EVD-020``), §9.3 (``LREQ-SEN-020``), §10 (``LREQ-CLI-040``), and
  §11 (``LREQ-NFR-020``/``LREQ-NFR-030``).
- ``Documents/plans/chunk-10-pipeline-orchestration.md`` §5 (produced interface),
  §5.4/§5.5 (``taxonomy_sha256`` derivation and enforcement), §5.6 (frozen JSON
  shapes), §5.7 (``CategoryStatus`` roll-up), §8 (edge cases), §9 (test plan and
  golden vectors), §12 (resolved rulings).
- Frozen interfaces consumed by the plan: ``chunk-00``, ``chunk-01``,
  ``chunk-02``, ``chunk-03``, ``chunk-4A``, ``chunk-4B``, ``chunk-05``,
  ``chunk-6A``, ``chunk-6B``, ``chunk-7A``, ``chunk-7B``, ``chunk-08``,
  ``chunk-9A``, ``chunk-9B``.

No live network, no real credentials, no ``.env``, no clock read: the clock is a
caller-advanced fixed instant, the transports are in-memory, and every datetime
is a fixed aware-UTC literal. The credential literals are deliberately
non-secret fixture strings.

Pinned expected facts for the eight-category end-to-end scenario
(:func:`end_to_end_scenario`), each hand-derived and each asserted by
``tests/test_pipeline.py``. The scenario's default run config covers the first
two preflight-eligible categories (``identity_preflight_min_categories=2``,
``identity_preflight_assets_per_category=2``), which are ``Truncated Textures``
and ``Verified Tilemap`` in the declared order:

- distinct sampled identities (the union the run enriches once) = **13**
  (``900``, ``901``, ``902``, ``A1``, ``A2``, ``B1``, ``B2``, ``C1``, ``C2``,
  ``D1``, ``D2``, ``E1``, ``E2``);
- raw discovery rows persisted = **15** (2 verified + 3 truncated + 0
  filter-unverified + 2 + 2 + 2 + 2 + 2 complete): the truncated category's
  endpoint reports a verified ``totalCount`` of 2000 while its pages carry two
  records, and the run's read cap (:data:`SCENARIO_DISCOVERY_CAP` = 3, below that
  total) admits both records of the first page plus the leading record of the
  terminal page, so the cap branch records ``truncated`` instead of reading the
  concealed remainder as zero; the third row is the cap-admitted duplicate of
  ``900``;
- sample member rows = **14**: the duplicate is flagged ``is_duplicate`` and is
  excluded by ``sampling.build_canonical_population``, so every category stays a
  two-member census;
- preflight attempted unique identities = **3**: the covered categories are
  ``Truncated Textures`` (members ``900``, ``902``) and ``Verified Tilemap``
  (members ``900``, ``901``), and identity ``900`` dedups, so the union is
  ``{900, 901, 902}``;
- reused preflight identities = 3, so pending identities = 13 - 3 = **10**;
- projected minimum enrichment time = ``pending_count *
  DEFAULT_MIN_REQUEST_INTERVAL_SECONDS`` = ``10 * 0.5`` = **5.0 s**;
- the injected enrichment failure is identity ``C1`` (``Charlie``'s first
  member): ``Charlie`` is not covered by the two-category preflight, so ``C1``
  reaches bulk enrichment while every covered identity is already reused.
- the run has exactly the eight categories required by ``MIN_CATEGORIES_PER_RUN``
  (SRS §14, non-configurable), so it is accepted and scored provisionally.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fixtures import config_fixtures, coveo_discovery, identity_preflight_vectors
from niche_scout import collector_coveo, collector_graphql
from niche_scout.config import Credentials, NicheScoutConfig

__all__ = [
    "CATEGORY_COUNT_21",
    "CATEGORY_COUNT_8",
    "CATEGORY_COUNT_BELOW_MIN",
    "CLOCK_SLOTS",
    "COMPONENT_WEIGHT_KEYS",
    "END_TO_END_EXTRA_VIEWS",
    "END_TO_END_RUN_ID",
    "END_TO_END_SHARED_KEY",
    "END_TO_END_SHARED_VIEWS",
    "ENRICHMENT_INTERVAL_SECONDS",
    "EXPECTED_PREFLIGHT_ATTEMPTS",
    "EXPECTED_PROJECTED_MINIMUM_SECONDS",
    "EXPECTED_RAW_DISCOVERY_ROWS",
    "EXPECTED_SAMPLE_MEMBER_ROWS",
    "EXPECTED_TAXONOMY_SHA256",
    "EXPECTED_UNION_IDENTITY_COUNT",
    "FIRST_RUN_ID",
    "FIXED_CLOCK_START",
    "GOLDEN_MISSING_COMPONENTS_ALL",
    "GOLDEN_MISSING_COMPONENTS_NONE",
    "GOLDEN_WARNINGS_EMPTY",
    "MIN_CATEGORIES",
    "MISSING_COMPONENTS_SCORING_PHASE_DEFAULTS",
    "PREFLIGHT_COMPLIANT_COUNT",
    "PREFLIGHT_VIOLATING_COUNT",
    "RECORDED_SENTINELS",
    "SCENARIO_DISCOVERY_CAP",
    "SECOND_RUN_ID",
    "STRONG_REFERENCE",
    "SUMMARY_JSON_KEY_SET",
    "SYNTHETIC_COMPLETE_CATEGORIES",
    "TRANSPORT_FAILED_CATEGORY",
    "TRANSPORT_TRUNCATED_CATEGORY",
    "TRANSPORT_VERIFIED_TOTAL_CATEGORY",
    "EndToEndScenario",
    "ErrorCoveoTransport",
    "FailingGraphQLTransport",
    "FixedClock",
    "LogCapture",
    "RecordingCoveoTransport",
    "RecordingGraphQLTransport",
    "category_from_request",
    "category_set",
    "compliant_category_paths",
    "coveo_page",
    "coveo_record",
    "end_to_end_scenario",
    "failed_enrichment_identity",
    "fixture_config",
    "fixture_credentials",
    "graphql_body_for_category",
    "identity_rejecting_body",
    "identity_success_body",
    "install_projection_observer",
    "population_records",
    "request_body_for_category",
    "request_body_fingerprint",
    "taxonomy_payload",
    "taxonomy_sha256_for",
    "write_categories",
    "write_run_local_template",
    "write_taxonomy",
]

# ---------------------------------------------------------------------------
# Constants and golden vectors derived from the frozen SRS constants.
# ---------------------------------------------------------------------------

#: ``MIN_CATEGORIES_PER_RUN`` (SRS §9.1 line 1013; ``models``).
MIN_CATEGORIES = 8
#: ``STRONG_REFERENCE_CATEGORY_COUNT`` (SRS §9.1 line 1014; ``models``).
STRONG_REFERENCE = 21

CATEGORY_COUNT_BELOW_MIN = 2
CATEGORY_COUNT_8 = 8
CATEGORY_COUNT_21 = 21

#: The Chunk 8 fixed component-key order (``interfaces/chunk-08.md`` §2), which
#: plan §5.6 re-exports and never re-declares.
COMPONENT_WEIGHT_KEYS: tuple[str, ...] = ("D", "C", "R", "Q")

#: Plan §5.6 golden JSON shapes: sorted + set-deduplicated codes; missing
#: components in the fixed key order.
GOLDEN_WARNINGS_EMPTY = "[]"
GOLDEN_MISSING_COMPONENTS_NONE = "[]"
GOLDEN_MISSING_COMPONENTS_ALL = '["D","C","R","Q"]'

#: A ``CategoryScoreRecord`` default for the scoring phase. After a preflight
#: failure the limitation rows carry no component values, so the four-component
#: missing vector is the only self-consistent shape (plan §5.6).
MISSING_COMPONENTS_SCORING_PHASE_DEFAULTS = GOLDEN_MISSING_COMPONENTS_ALL

#: The frozen ``identity_preflight_summary_json`` key set
#: (interfaces/chunk-6A.md §5.5), consumed read-only.
SUMMARY_JSON_KEY_SET: tuple[str, ...] = (
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

#: LREQ-NFR-020 projection interval. The plan §9 golden vector is
#: ``projected_minimum_enrichment_seconds == pending_count *
#: DEFAULT_MIN_REQUEST_INTERVAL_SECONDS``; the caller supplies the interval and
#: the production default is ``DEFAULT_MIN_REQUEST_INTERVAL_SECONDS``.
ENRICHMENT_INTERVAL_SECONDS = collector_graphql.DEFAULT_MIN_REQUEST_INTERVAL_SECONDS

END_TO_END_RUN_ID = "run-10-e2e"
FIRST_RUN_ID = "run-10-determinism-a"
SECOND_RUN_ID = "run-10-determinism-b"
END_TO_END_SHARED_KEY = "900"
END_TO_END_SHARED_VIEWS = 4321
END_TO_END_EXTRA_VIEWS = 250

#: The fixed clock starts here and advances one second per call, so every
#: timestamp is aware-UTC, deterministic, and strictly increasing without a wall
#: clock.
FIXED_CLOCK_START = datetime(2026, 3, 1, 0, 0, 0, tzinfo=timezone.utc)
CLOCK_SLOTS = 64

#: Credential-shaped sentinel strings that must never reach a log line, a
#: persisted column, or an exception message (LREQ-SEC-010/020).
RECORDED_SENTINELS: tuple[str, ...] = (
    "fixture-pipeline-bearer-token",
    "fixture-pipeline-csrf-token",
    "sessionid=fixture-pipeline-cookie",
    "Bearer fixture-pipeline-header",
    "fixture-pipeline-response-body",
)

#: The e2e scenario's three transport-fed categories: a verified-total category,
#: a genuinely ``truncated`` category (the run read cap ends its traversal), and
#: a category whose filter verdict is not ``verified``.
TRANSPORT_VERIFIED_TOTAL_CATEGORY = "Category/Verified Tilemap"
TRANSPORT_TRUNCATED_CATEGORY = "Category/Truncated Textures"
TRANSPORT_FAILED_CATEGORY = "Category/FilterUnverified Audio"

#: Three synthetic complete categories whose samples feed the metrics. Together
#: with the transport-fed populations they give the pinned 10 raw rows / 9
#: distinct sampled identities documented in the module docstring.
SYNTHETIC_COMPLETE_CATEGORIES: tuple[str, ...] = (
    "Category/Complete Alpha",
    "Category/Complete Bravo",
    "Category/Complete Charlie",
    "Category/Complete Delta",
    "Category/Complete Echo",
)

#: The declared category order handed to ``run_pipeline``. It is deliberately
#: not lexical: the SRS §4.4 preflight covers the first
#: ``identity_preflight_min_categories`` eligible categories in declared order, so
#: placing the transport-fed ``Truncated``/``Verified`` categories first makes the
#: preflight cover their three unique identities (``900``, ``902``, ``901``).
END_TO_END_CATEGORIES: tuple[str, ...] = (
    TRANSPORT_TRUNCATED_CATEGORY,
    TRANSPORT_VERIFIED_TOTAL_CATEGORY,
    TRANSPORT_FAILED_CATEGORY,
    *SYNTHETIC_COMPLETE_CATEGORIES,
)

#: The run-local discovery read cap every scenario run config sets. It sits
#: below the truncated category's verified ``totalCount`` (2000) and above the
#: two records every other category serves, so exactly the truncated category's
#: cap branch records ``truncated``: 2 admitted records on the first page plus 1
#: admitted record of the terminal page = 3. Without a cap the truncated
#: category would re-request its scripted pages until the endpoint count was
#: reached, which the fixture does not serve; the cap is the SRS-conformant
#: exhaustion signal (LREQ-EXT-050) and keeps the traversal finite.
SCENARIO_DISCOVERY_CAP = 3

EXPECTED_UNION_IDENTITY_COUNT = 13
EXPECTED_RAW_DISCOVERY_ROWS = 15
EXPECTED_SAMPLE_MEMBER_ROWS = 14
EXPECTED_PREFLIGHT_ATTEMPTS = 3
EXPECTED_PENDING_ENRICHMENT_IDENTITIES = 10
EXPECTED_PROJECTED_MINIMUM_SECONDS = (
    EXPECTED_PENDING_ENRICHMENT_IDENTITIES * ENRICHMENT_INTERVAL_SECONDS
)

PREFLIGHT_COMPLIANT_COUNT = 5
PREFLIGHT_VIOLATING_COUNT = 2

# ---------------------------------------------------------------------------
# Taxonomy payloads and the golden hash derivation (plan §5.4).
# ---------------------------------------------------------------------------

TAXONOMY_HEADERS: Mapping[str, Any] = {
    "schema_version": "1.0.0",
    "captured_at_utc": "2026-02-15T00:00:00Z",
    "source_url": "https://assetstore.unity.com/categories",
    "template_sha256": "0" * 64,
}


def taxonomy_payload(paths: Sequence[str]) -> dict[str, Any]:
    """Return a valid taxonomy payload whose inventory is exactly ``paths``.

    The shape is the Chunk 1 fixture shape (canonical-path inventory plus a
    ``categories`` tree), never a value read from the implementation.
    ``captured_at_utc`` is 14 days before ``FIXED_CLOCK_START`` (the caller's
    ``reference_utc``), inside the default ``MAX_TAXONOMY_AGE_DAYS = 30`` window,
    so the payload is fresh by hand derivation.
    """
    ordered = tuple(paths)
    return {
        **TAXONOMY_HEADERS,
        "canonical_category_paths": list(ordered),
        "categories": [
            {
                "path": path,
                "label": path.rsplit("/", 1)[-1],
                "parent": path.rsplit("/", 1)[0] if "/" in path else "",
            }
            for path in ordered
        ],
    }


def taxonomy_sha256_for(payload: object) -> str:
    """Return the lowercase-hex SHA-256 over the canonical JSON payload.

    The plan §5.4 golden derivation, hand-derived here and never read off the
    implementation: ``json.dumps(payload, sort_keys=True, separators=(",", ":"),
    ensure_ascii=False).encode("utf-8")``.
    """
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def write_taxonomy(
    directory: Path, payload: object, *, name: str = "taxonomy.json"
) -> Path:
    """Write ``payload`` as a taxonomy file under ``directory`` (pytest temp)."""
    path = Path(directory) / name
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def write_categories(
    directory: Path, categories: Sequence[str], *, name: str = "categories.json"
) -> Path:
    """Write a bare JSON array of category paths (``config.read_categories``)."""
    path = Path(directory) / name
    path.write_text(json.dumps(list(categories)), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Run-local Coveo template.
#
# The committed capture's ``ec_category`` facet lists real storefront
# categories; none of the synthetic scenario categories is among them, and
# ``build_coveo_request_body`` marks a value ``selected`` only when it literally
# equals the requested category. Replaying the capture would therefore leave
# every value ``idle`` and the Coveo transport could not resolve a request to
# its category. The writer below extends the captured facet inventory with the
# scenario categories and writes the result through the frozen
# ``coveo_discovery.write_template`` writer, so the provenance header and the
# body it hashes stay self-consistent and the committed capture is never
# modified.
# ---------------------------------------------------------------------------


def write_run_local_template(directory: Path, categories: Sequence[str]) -> Path:
    """Write a run-local Coveo template selecting exactly ``categories``.

    The captured request body is copied with its ``ec_category`` facet's
    ``currentValues`` replaced by ``categories`` (the values the pipeline may
    request) and written through :func:`fixtures.coveo_discovery.write_template`,
    which recomputes the header's ``template_sha256`` over the body it writes.
    """
    captured = coveo_discovery.template_body()
    facets: list[Any] = []
    replaced = False
    for facet in captured.get("facets", ()):
        if (
            isinstance(facet, Mapping)
            and facet.get("facetId") == collector_coveo.COVEO_FACET_ID
        ):
            updated = dict(facet)
            updated["currentValues"] = [
                {"value": str(category), "state": "idle"} for category in categories
            ]
            updated["numberOfValues"] = len(updated["currentValues"])
            facet = updated
            replaced = True
        facets.append(facet)
    if not replaced:
        raise AssertionError(
            f"the committed capture carries no '{collector_coveo.COVEO_FACET_ID}' "
            "facet to extend"
        )
    body = dict(captured)
    body["facets"] = facets
    return coveo_discovery.write_template(directory, body)


def request_body_for_category(
    category: str, *, template_path: Path | None = None
) -> dict[str, Any]:
    """Return the discovery request body the pipeline builds for ``category``.

    Without ``template_path`` this is the frozen Chunk 3 builder against the
    committed capture (``coveo_discovery.request_body``). With a run-local
    template the same ``collector_coveo.build_coveo_request_body`` builder is
    applied to that template, so the fixture's request fingerprints stay equal
    to the bodies the pipeline actually sends.
    """
    if template_path is None:
        return coveo_discovery.request_body(category)
    template = collector_coveo.load_coveo_search_template(template_path)
    return collector_coveo.build_coveo_request_body(template, category, page_index=0)


# ---------------------------------------------------------------------------
# Category sets for the size boundaries (plan §9: 2 / 8 / 21).
# ---------------------------------------------------------------------------


def category_set(count: int) -> tuple[str, ...]:
    """Return ``count`` distinct canonical-looking category paths in order.

    The paths are lexically ordered, so the declared order, the caller's
    canonical order, and the lexical tie-break order agree.
    """
    return tuple(f"Category/{index:04d}" for index in range(1, int(count) + 1))


def compliant_category_paths() -> tuple[str, ...]:
    """Return the config fixture's default eight canonical category paths."""
    return tuple(config_fixtures.DEFAULT_CATEGORIES)


EXPECTED_TAXONOMY_SHA256 = taxonomy_sha256_for(
    taxonomy_payload(compliant_category_paths())
)

# ---------------------------------------------------------------------------
# The fixed injected clock.
# ---------------------------------------------------------------------------


class FixedClock:
    """A caller-advanced, timezone-aware UTC clock that counts its calls.

    Every call returns the current instant and then advances by ``step``
    seconds, so the pipeline's "captured once" cutoff can be asserted both by
    call count and by value identity. No wall clock is ever read.
    """

    def __init__(
        self,
        start: datetime = FIXED_CLOCK_START,
        *,
        step: timedelta = timedelta(seconds=1),
    ) -> None:
        if start.tzinfo is None:
            raise ValueError("the fixture clock must start aware-UTC")
        self._now = start
        self._step = step
        self.calls: list[datetime] = []

    def __call__(self) -> datetime:
        value = self._now
        self.calls.append(value)
        self._now = value + self._step
        return value

    @property
    def call_count(self) -> int:
        return len(self.calls)

    @property
    def timestamps(self) -> tuple[datetime, ...]:
        return tuple(self.calls)


# ---------------------------------------------------------------------------
# Request helpers shared by both transports.
# ---------------------------------------------------------------------------


def _decode_json(payload: bytes) -> Mapping[str, Any]:
    try:
        value = json.loads(bytes(payload).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, Mapping) else {}


def category_from_request(body: Mapping[str, Any]) -> str | None:
    """Read the selected ``ec_category`` value out of a Coveo request body.

    The adapter marks exactly one facet value ``selected`` (Chunk 3 §6); this
    helper recovers it so the transport can serve the right page.
    """
    facets = body.get("facets", ())
    if not isinstance(facets, (list, tuple)):
        return None
    for facet in facets:
        if not isinstance(facet, Mapping):
            continue
        values = facet.get("currentValues", ())
        if not isinstance(values, (list, tuple)):
            continue
        for value in values:
            if isinstance(value, Mapping) and value.get("state") == "selected":
                return str(value.get("value"))
    return None


def _fingerprint_members(value: Any) -> list[str]:
    """Return every string and member name inside ``value``."""
    found: list[str] = []
    if isinstance(value, Mapping):
        for name, item in value.items():
            found.append(str(name))
            found.extend(_fingerprint_members(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            found.extend(_fingerprint_members(item))
    elif isinstance(value, str):
        found.append(value)
    return found


def request_body_fingerprint(payload: bytes) -> str:
    """Return a canonical fingerprint of a Coveo request body.

    The fingerprint is the sorted, set-deduplicated list of every string value
    and member name in the body, joined by ``|``. It exists so the GraphQL
    fixture can resolve a request to the category whose Coveo request produced
    it without the fixture knowing the pipeline's sampling order; it is a
    fixture-side join key, never a pipeline signal.
    """
    decoded = _decode_json(payload)
    if not decoded:
        return hashlib.sha256(bytes(payload)).hexdigest()
    return "|".join(sorted(set(_fingerprint_members(decoded))))


# ---------------------------------------------------------------------------
# The in-memory Coveo transport.
# ---------------------------------------------------------------------------


class _CoveoResponse:
    """The minimal opener-result contract the Coveo adapter reads."""

    def __init__(self, status: int, body: bytes) -> None:
        self.status = int(status)
        self.headers: dict[str, str] = {}
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_CoveoResponse":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return False


class RecordingCoveoTransport:
    """A Coveo transport serving scripted in-memory pages and recording calls.

    ``category_body`` maps a category path to the ordered page bodies it serves.
    A category absent from the mapping has no fixture response and raises, which
    is a fixture-defect signal, never a live request. Every call appends
    ``(url, payload)`` to :attr:`calls`.
    """

    def __init__(self, category_body: Mapping[str, Sequence[bytes]]) -> None:
        self._pages: dict[str, list[bytes]] = {
            category: [bytes(body) for body in bodies]
            for category, bodies in category_body.items()
        }
        self.calls: list[tuple[str, bytes]] = []

    def send(
        self, url: str, headers: Mapping[str, str], payload: bytes
    ) -> _CoveoResponse:
        self.calls.append((url, payload))
        category = category_from_request(_decode_json(payload))
        queued = self._pages.get(category)
        if not queued:
            raise AssertionError(
                f"no Coveo fixture pages queued for category {category!r}"
            )
        page = queued[0] if len(queued) == 1 else queued.pop(0)
        return _CoveoResponse(200, page)

    @property
    def call_count(self) -> int:
        return len(self.calls)


class ErrorCoveoTransport:
    """A Coveo transport returning an HTTP error for every request.

    The adapter classifies the response as a per-category request failure and
    returns it as a ``CategoryDiscoveryResult``; it never propagates and never
    records a zero-breadth category (SRS §4.1 ``LREQ-EXT-050``).
    """

    def __init__(self, status: int = 500) -> None:
        self._status = int(status)
        self.calls: list[tuple[str, bytes]] = []

    def send(
        self, url: str, headers: Mapping[str, str], payload: bytes
    ) -> _CoveoResponse:
        self.calls.append((url, payload))
        return _CoveoResponse(self._status, b'{"error":"fixture upstream failure"}')


# ---------------------------------------------------------------------------
# Coveo page builders for the e2e scenario.
# ---------------------------------------------------------------------------


def coveo_record(index: int, identity: str, category: str) -> dict[str, Any]:
    """Return one agreeing-identity discovery record.

    ``permanentid`` and ``ec_product_id`` carry the *same* identifier so the
    identity resolves under the frozen mapping rule (Chunk 3 §8); a single side
    is never allowed to disagree.
    """
    return {
        "permanentid": identity,
        "ec_product_id": identity,
        "ec_name": f"Fixture Asset {index:04d}",
        "ec_category": category,
        "publisher_name": "Fixture Publisher",
    }


def coveo_page(
    records: Sequence[Mapping[str, Any]],
    *,
    total_count: int | None = None,
    filtered_count: int | None = None,
) -> bytes:
    """Return one recorded-shape Coveo page body as bytes."""
    page: dict[str, Any] = {"results": [dict(record) for record in records]}
    page["totalCount"] = len(records) if total_count is None else total_count
    if filtered_count is not None:
        page["totalCountFiltered"] = filtered_count
    return json.dumps(page).encode("utf-8")


# ---------------------------------------------------------------------------
# The in-memory GraphQL transport.
# ---------------------------------------------------------------------------


def identity_success_body(
    identity: str, *, page_views: int = END_TO_END_SHARED_VIEWS
) -> bytes:
    """Return a both-operations-success GraphQL body for ``identity``.

    The ProductDetail payload echoes ``identity`` back as both aliases so the
    requested-vs-returned comparison passes (SRS §4.4). ``page_views`` of ``0``
    is an explicit valid zero distinct from a failed operation.
    """
    return identity_preflight_vectors.success_body(identity, page_views=page_views)


def identity_rejecting_body() -> bytes:
    """Return a body whose ProductDetail operation carries no usable payload."""
    return json.dumps(
        [
            {
                "operationName": "ProductDetail",
                "data": {"errors": [{"message": "fixture operation failure"}]},
            },
            {
                "operationName": "ProductPageViews",
                "data": {"pageViews": END_TO_END_SHARED_VIEWS},
            },
        ],
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


class _GraphQLBatchResponse:
    """The Chunk 5 response record shape (status + verbatim body text)."""

    def __init__(self, http_status: int, body_text: str) -> None:
        self.http_status = int(http_status)
        self.body_text = body_text
        self.header_names: tuple[str, ...] = ()


#: The identity directories the scenario builder installs, keyed by category.
_IDENTITIES_BY_CATEGORY: dict[str, tuple[str, ...]] = {}


def scenario_identities(category: str) -> tuple[str, ...]:
    """Return the identities the scenario plants in ``category``."""
    return _IDENTITIES_BY_CATEGORY.get(category, ())


def graphql_body_for_category(category: str) -> bytes:
    """Return a GraphQL *directory* body for every scenario identity of ``category``.

    The directory body is a JSON object keyed by identity whose values are the
    per-identity two-operation response bodies. The GraphQL transport resolves a
    request to its directory through the Coveo request fingerprint; the
    directory is a lookup table, not an oracle for the pipeline.
    """
    bodies = {
        identity: identity_success_body(identity).decode("utf-8")
        for identity in scenario_identities(category)
    }
    return json.dumps(bodies, sort_keys=True, separators=(",", ":")).encode("utf-8")


class RecordingGraphQLTransport:
    """An in-memory ``GraphQLTransport`` that records every call.

    ``body_for_identity`` is the primary lookup. ``body_for_fingerprint`` maps a
    Coveo-request fingerprint to a *directory* body (a JSON object keyed by
    identity); it is consulted when the identity is not in
    ``body_for_identity``, which lets one directory serve every identity of a
    category. ``failing_identities`` raises a transport failure for named
    identities, which the adapter classifies rather than propagating
    (LREQ-NFR-030).
    """

    def __init__(
        self,
        body_for_identity: Mapping[str, bytes] | None = None,
        *,
        body_for_fingerprint: Mapping[str, bytes] | None = None,
        failing_identities: Sequence[str] = (),
        on_call: Callable[[str], None] | None = None,
    ) -> None:
        self._by_identity = {
            str(key): bytes(value) for key, value in (body_for_identity or {}).items()
        }
        self._by_fingerprint = {
            str(key): bytes(value)
            for key, value in (body_for_fingerprint or {}).items()
        }
        self._failing = {str(key) for key in failing_identities}
        self._on_call = on_call
        self.calls: list[Any] = []

    def __call__(
        self, request: Any, headers: Mapping[str, str]
    ) -> _GraphQLBatchResponse:
        self.calls.append(request)
        identity = str(getattr(request, "asset_identity_key", ""))
        if self._on_call is not None:
            self._on_call(identity)
        if identity in self._failing:
            raise ConnectionResetError("injected GraphQL transport failure")
        body = self._by_identity.get(identity)
        if body is None:
            body = self._resolve_directory(identity)
        if body is None:
            raise AssertionError(
                f"no GraphQL fixture body queued for identity {identity!r}"
            )
        return _GraphQLBatchResponse(200, bytes(body).decode("utf-8"))

    def _resolve_directory(self, identity: str) -> bytes | None:
        for directory in self._by_fingerprint.values():
            mapping = _decode_json(directory)
            if identity in mapping:
                return str(mapping[identity]).encode("utf-8")
        return None

    @property
    def call_count(self) -> int:
        return len(self.calls)

    @property
    def requested_identities(self) -> tuple[str, ...]:
        return tuple(
            str(getattr(call, "asset_identity_key", "")) for call in self.calls
        )

    @property
    def distinct_requested_identities(self) -> tuple[str, ...]:
        seen: list[str] = []
        for key in self.requested_identities:
            if key not in seen:
                seen.append(key)
        return tuple(seen)


class FailingGraphQLTransport(RecordingGraphQLTransport):
    """A GraphQL transport that raises for every call (the adapter errors it)."""

    def __call__(
        self, request: Any, headers: Mapping[str, str]
    ) -> _GraphQLBatchResponse:
        self.calls.append(request)
        raise ConnectionResetError("injected GraphQL transport failure")


def graphql_seeded_transport(
    category_bodies: Mapping[str, bytes],
    *,
    template_path: Path | None = None,
    failing_identities: Sequence[str] = (),
    on_call: Callable[[str], None] | None = None,
) -> RecordingGraphQLTransport:
    """Return a transport seeded by identity -> per-identity response body.

    Each category's directory body (a JSON object keyed by identity) is merged
    into a single identity lookup, because the GraphQL request carries only the
    identity and not the originating category. The request-body fingerprint is
    retained as a secondary key, but it is *not* the join key: every category's
    Coveo request body contains the same facet-value string set (only the
    ``selected`` state differs), so the fingerprint cannot distinguish
    categories and must not be relied on to select a directory.
    """
    by_fingerprint: dict[str, bytes] = {}
    by_identity: dict[str, bytes] = {}
    for category, directory in category_bodies.items():
        body = request_body_for_category(category, template_path=template_path)
        request = json.dumps(body).encode("utf-8")
        by_fingerprint[request_body_fingerprint(request)] = directory
        for identity, per_identity in _decode_json(directory).items():
            by_identity.setdefault(str(identity), str(per_identity).encode("utf-8"))
    return RecordingGraphQLTransport(
        body_for_identity=by_identity,
        body_for_fingerprint=by_fingerprint,
        failing_identities=failing_identities,
        on_call=on_call,
    )


def graphql_rejecting_transport(
    identity_keys: Sequence[str] = (),
) -> RecordingGraphQLTransport:
    """Return a transport serving a shape-invalid body for every named identity.

    Every ``ProductDetail`` operation carries no usable payload, so the identity
    comparison fails for each attempted preflight identity and the gate computes
    a zero success rate (SRS §4.4). The failure is a persisted observation, not
    an exception.
    """
    body = identity_rejecting_body()
    return RecordingGraphQLTransport(
        body_for_identity={key: body for key in identity_keys}
    )


# ---------------------------------------------------------------------------
# Test-only log capture (hand-built, not the pipeline's implementation).
# ---------------------------------------------------------------------------


class LogCapture(logging.Handler):
    """A real ``logging.Handler`` recording every emitted message in order.

    :func:`install_projection_observer` attaches it to the pipeline module
    logger, so :meth:`messages` is populated whenever the pipeline emits its
    LREQ-NFR-020 projection line. The e2e transport's ``on_call`` hook consults
    :meth:`assert_projection_logged` before any *bulk-enrichment* call (preflight
    calls legitimately precede the projection log), so the projection must
    already be present at the first bulk-enrichment call.
    """

    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.messages: list[str] = []

    def emit(self, record: Any) -> None:
        self.messages.append(str(record.getMessage()))

    def assert_projection_logged(self, label: str) -> None:
        for message in self.messages:
            if "enrichment" in message.lower():
                return
        raise AssertionError(
            f"no enrichment projection log was emitted before {label}"
        )


#: The pipeline module logger the projection line is emitted on
#: (``pipeline._LOGGER = logging.getLogger("niche_scout.pipeline")``).
_PIPELINE_LOGGER_NAME = "niche_scout.pipeline"

_PROJECTION_LOG_OBSERVER: LogCapture | None = None
_INSTALLED_LOG_HANDLER: LogCapture | None = None
_PREVIOUS_LOGGER_LEVEL: int | None = None

#: Identities the default scenario preflight attempts. The observer hook skips
#: these: preflight runs before the projection log, so only bulk-enrichment
#: calls may be required to observe it.
_PREFLIGHT_OBSERVER_IDENTITIES: frozenset[str] = frozenset()


def install_projection_observer(capture: LogCapture | None) -> None:
    """Install (or clear) the pipeline-logger capture consulted by the hook."""
    global _PROJECTION_LOG_OBSERVER, _INSTALLED_LOG_HANDLER, _PREVIOUS_LOGGER_LEVEL
    logger = logging.getLogger(_PIPELINE_LOGGER_NAME)
    if _INSTALLED_LOG_HANDLER is not None:
        logger.removeHandler(_INSTALLED_LOG_HANDLER)
        _INSTALLED_LOG_HANDLER = None
    if _PREVIOUS_LOGGER_LEVEL is not None:
        logger.setLevel(_PREVIOUS_LOGGER_LEVEL)
        _PREVIOUS_LOGGER_LEVEL = None
    _PROJECTION_LOG_OBSERVER = capture
    if capture is not None:
        _PREVIOUS_LOGGER_LEVEL = logger.level
        logger.setLevel(logging.INFO)
        logger.addHandler(capture)
        _INSTALLED_LOG_HANDLER = capture


def _on_call_hook(identity: str) -> None:
    capture = _PROJECTION_LOG_OBSERVER
    if capture is None or identity in _PREFLIGHT_OBSERVER_IDENTITIES:
        return
    capture.assert_projection_logged(
        f"the enrichment request for identity {identity!r}"
    )



# ---------------------------------------------------------------------------
# The end-to-end scenario.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EndToEndScenario:
    """The Chunk 10 end-to-end fixture, with every expected value hand-derived."""

    run_id: str
    categories: tuple[str, ...]
    taxonomy_payload: Mapping[str, Any]
    taxonomy_sha256: str
    clock: FixedClock
    coveo_transport: RecordingCoveoTransport
    graphql_transport: RecordingGraphQLTransport
    summary_key_set: tuple[str, ...]
    preflight_attempted_unique_identities: int
    union_identity_count: int
    raw_discovery_rows: int
    removed_category: str
    observed_sentinels: tuple[str, ...]

    def records(self) -> dict[str, tuple[dict[str, Any], ...]]:
        """Return the designed category -> population-record mapping."""
        return _scenario_category_records()

    def run(self):
        """Return the designed canonical ``RunSamplingResult`` for this scenario."""
        from niche_scout import sampling

        return sampling.select_run_sample(self.records(), run_id=self.run_id)


def population_records(keys: Sequence[str]) -> tuple[dict[str, Any], ...]:
    """Return ``keys`` as ascending-ordinal 4A population records."""
    return tuple(
        {"discovery_ordinal": index, "asset_identity_key": key, "is_duplicate": False}
        for index, key in enumerate(keys)
    )


def _scenario_category_records() -> dict[str, tuple[dict[str, Any], ...]]:
    by_category = {
        TRANSPORT_VERIFIED_TOTAL_CATEGORY: population_records(
            (END_TO_END_SHARED_KEY, "901")
        ),
        TRANSPORT_TRUNCATED_CATEGORY: population_records(
            (END_TO_END_SHARED_KEY, "902")
        ),
        TRANSPORT_FAILED_CATEGORY: population_records(()),
        SYNTHETIC_COMPLETE_CATEGORIES[0]: population_records(("A1", "A2")),
        SYNTHETIC_COMPLETE_CATEGORIES[1]: population_records(("B1", "B2")),
        SYNTHETIC_COMPLETE_CATEGORIES[2]: population_records(("C1", "C2")),
        SYNTHETIC_COMPLETE_CATEGORIES[3]: population_records(("D1", "D2")),
        SYNTHETIC_COMPLETE_CATEGORIES[4]: population_records(("E1", "E2")),
    }
    # Declared order is the canonical order (``END_TO_END_CATEGORIES``); the
    # pipeline sees categories in that order, so the fixture's sampling and
    # preflight derivations must use it too.
    return {category: by_category[category] for category in END_TO_END_CATEGORIES}


def _scenario_preflight_identities() -> frozenset[str]:
    """Return the identities the scenario's default preflight attempts.

    Uses the frozen pure surfaces (``sampling.select_run_sample`` and
    ``pipeline.select_preflight_identities``) with the scenario's documented
    default knobs (``identity_preflight_min_categories=2``,
    ``identity_preflight_assets_per_category=2``). The observer hook skips these
    identities because preflight legitimately runs before the projection log.
    """
    from niche_scout import pipeline as pipeline_module
    from niche_scout import sampling as sampling_module

    run = sampling_module.select_run_sample(
        _scenario_category_records(), run_id=END_TO_END_RUN_ID
    )
    selection = pipeline_module.select_preflight_identities(
        run,
        policy=pipeline_module.PreflightPolicy(
            min_categories=2, assets_per_category=2
        ),
    )
    return frozenset(
        identity.asset_identity_key for identity in selection.identities
    )


def failed_enrichment_identity() -> str:
    """Return the identity whose enrichment request raises (adapter error).

    ``C1`` is ``Charlie``'s first member. ``Charlie`` is the last eligible
    category and the scenario's default preflight covers only the first two
    eligible categories, so ``C1`` is never attempted by the preflight and its
    transport failure is isolated to the bulk phase (LREQ-NFR-030).
    """
    return "C1"


def end_to_end_scenario(*, template_path: Path | None = None) -> EndToEndScenario:
    """Return the eight-category scenario: verified, truncated, unverified + 5.

    ``template_path`` is the run-local discovery template the caller wrote with
    :func:`write_run_local_template`; it is threaded into the GraphQL fixture's
    request fingerprints so both transport sides join on the same request body.

    Hand-derived shape (plan §12 Q5):

    - ``Category/Verified Tilemap``: a verified ``totalCount`` of 2 with two
      identities (``900``, ``901``); it shares ``900`` with the truncated
      category so the union dedups three references to two identities.
    - ``Category/Truncated Textures``: the verified ``totalCount`` of 2000 far
      exceeds the records served, and the run's read cap
      (:data:`SCENARIO_DISCOVERY_CAP` = 3) admits both records of the first page
      plus the leading record of the terminal page; the cap branch records
      ``truncated`` (LREQ-EXT-050) rather than reading the concealed remainder
      as zero. The identity inventory is ``900`` and ``902``; the third,
      cap-admitted row is a duplicate of ``900``.
    - ``Category/FilterUnverified Audio``: the response's ``totalCount`` is not
      usable, so the filter verdict is not ``verified``; no sampled member.
    - ``Category/Complete Alpha|Bravo|Charlie|Delta|Echo``: two identities each
      (``A1``, ``A2``, … ``E1``, ``E2``). Five synthetic categories keep the run
      at ``MIN_CATEGORIES_PER_RUN`` (8) with the three transport-fed categories.

    Pinned expected facts (also documented in the module docstring): union = 13
    distinct identities; raw discovery rows = 15; projection minimum =
    ``10 * 0.5`` = 5.0 s; preflight attempts = 3.
    """
    global _IDENTITIES_BY_CATEGORY
    global _PREFLIGHT_OBSERVER_IDENTITIES
    _IDENTITIES_BY_CATEGORY = {
        TRANSPORT_VERIFIED_TOTAL_CATEGORY: (END_TO_END_SHARED_KEY, "901"),
        TRANSPORT_TRUNCATED_CATEGORY: (END_TO_END_SHARED_KEY, "902"),
        TRANSPORT_FAILED_CATEGORY: (),
        SYNTHETIC_COMPLETE_CATEGORIES[0]: ("A1", "A2"),
        SYNTHETIC_COMPLETE_CATEGORIES[1]: ("B1", "B2"),
        SYNTHETIC_COMPLETE_CATEGORIES[2]: ("C1", "C2"),
        SYNTHETIC_COMPLETE_CATEGORIES[3]: ("D1", "D2"),
        SYNTHETIC_COMPLETE_CATEGORIES[4]: ("E1", "E2"),
    }
    categories = END_TO_END_CATEGORIES
    payload = taxonomy_payload(categories)
    verified_page = coveo_page(
        [
            coveo_record(0, END_TO_END_SHARED_KEY, TRANSPORT_VERIFIED_TOTAL_CATEGORY),
            coveo_record(1, "901", TRANSPORT_VERIFIED_TOTAL_CATEGORY),
        ],
        total_count=2,
        filtered_count=2,
    )
    truncated_page = coveo_page(
        [
            coveo_record(0, END_TO_END_SHARED_KEY, TRANSPORT_TRUNCATED_CATEGORY),
            coveo_record(1, "902", TRANSPORT_TRUNCATED_CATEGORY),
        ],
        total_count=2000,
    )
    # The endpoint's terminal page for the truncated category: the read cap
    # (SCENARIO_DISCOVERY_CAP) admits only its leading record, which repeats
    # ``900`` and is therefore persisted as a duplicate of the first page's row.
    truncated_terminal_page = coveo_page(
        [
            coveo_record(0, END_TO_END_SHARED_KEY, TRANSPORT_TRUNCATED_CATEGORY),
            coveo_record(1, "902", TRANSPORT_TRUNCATED_CATEGORY),
        ],
        total_count=2000,
    )
    unverified_page = coveo_page([], total_count=None)
    coveo = RecordingCoveoTransport(
        {
            TRANSPORT_VERIFIED_TOTAL_CATEGORY: (verified_page,),
            TRANSPORT_TRUNCATED_CATEGORY: (truncated_page, truncated_terminal_page),
            TRANSPORT_FAILED_CATEGORY: (unverified_page,),
            SYNTHETIC_COMPLETE_CATEGORIES[0]: (
                coveo_page(
                    [
                        coveo_record(0, "A1", SYNTHETIC_COMPLETE_CATEGORIES[0]),
                        coveo_record(1, "A2", SYNTHETIC_COMPLETE_CATEGORIES[0]),
                    ],
                    total_count=2,
                    filtered_count=2,
                ),
            ),
            SYNTHETIC_COMPLETE_CATEGORIES[1]: (
                coveo_page(
                    [
                        coveo_record(0, "B1", SYNTHETIC_COMPLETE_CATEGORIES[1]),
                        coveo_record(1, "B2", SYNTHETIC_COMPLETE_CATEGORIES[1]),
                    ],
                    total_count=2,
                    filtered_count=2,
                ),
            ),
            SYNTHETIC_COMPLETE_CATEGORIES[2]: (
                coveo_page(
                    [
                        coveo_record(0, "C1", SYNTHETIC_COMPLETE_CATEGORIES[2]),
                        coveo_record(1, "C2", SYNTHETIC_COMPLETE_CATEGORIES[2]),
                    ],
                    total_count=2,
                    filtered_count=2,
                ),
            ),
            SYNTHETIC_COMPLETE_CATEGORIES[3]: (
                coveo_page(
                    [
                        coveo_record(0, "D1", SYNTHETIC_COMPLETE_CATEGORIES[3]),
                        coveo_record(1, "D2", SYNTHETIC_COMPLETE_CATEGORIES[3]),
                    ],
                    total_count=2,
                    filtered_count=2,
                ),
            ),
            SYNTHETIC_COMPLETE_CATEGORIES[4]: (
                coveo_page(
                    [
                        coveo_record(0, "E1", SYNTHETIC_COMPLETE_CATEGORIES[4]),
                        coveo_record(1, "E2", SYNTHETIC_COMPLETE_CATEGORIES[4]),
                    ],
                    total_count=2,
                    filtered_count=2,
                ),
            ),
        }
    )
    graphql = graphql_seeded_transport(
        {category: graphql_body_for_category(category) for category in categories},
        template_path=template_path,
        failing_identities=(failed_enrichment_identity(),),
        on_call=_on_call_hook,
    )
    _PREFLIGHT_OBSERVER_IDENTITIES = _scenario_preflight_identities()
    return EndToEndScenario(
        run_id=END_TO_END_RUN_ID,
        categories=categories,
        taxonomy_payload=payload,
        taxonomy_sha256=taxonomy_sha256_for(payload),
        clock=FixedClock(),
        coveo_transport=coveo,
        graphql_transport=graphql,
        summary_key_set=SUMMARY_JSON_KEY_SET,
        preflight_attempted_unique_identities=EXPECTED_PREFLIGHT_ATTEMPTS,
        union_identity_count=EXPECTED_UNION_IDENTITY_COUNT,
        raw_discovery_rows=EXPECTED_RAW_DISCOVERY_ROWS,
        removed_category=TRANSPORT_TRUNCATED_CATEGORY,
        observed_sentinels=RECORDED_SENTINELS,
    )


# ---------------------------------------------------------------------------
# Configuration and credentials.
# ---------------------------------------------------------------------------


def fixture_credentials() -> Credentials:
    """Return non-secret offline credentials for the injected transports."""
    return Credentials(
        coveo_token="fixture-pipeline-bearer-token",
        unity_csrf_token="fixture-pipeline-csrf-token",
    )


def fixture_config(directory: Path, **overrides: Any) -> NicheScoutConfig:
    """Return a real ``NicheScoutConfig`` whose paths live under ``directory``.

    The base config is the Chunk 0 fixture TOML; the three paths are replaced
    with pytest-temp locations so no pipeline test can touch the repository
    tree. ``overrides`` replaces any further field.
    """
    from niche_scout.config import load_config

    toml_path = config_fixtures.write_toml(
        Path(directory), config_fixtures.DEFAULT_TOML_BODY, name="chunk10.toml"
    )
    base = load_config(toml_path=toml_path)
    values: dict[str, Any] = {
        "categories_path": Path(directory) / "categories.json",
        "taxonomy_path": Path(directory) / "taxonomy.json",
        "db_path": Path(directory) / "niche_scout.sqlite3",
    }
    values.update(overrides)
    return replace(base, **values)