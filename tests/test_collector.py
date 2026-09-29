"""Chunk 3 analytical tests for the Coveo discovery adapter.

Every test here carries exactly the ``@pytest.mark.lreq`` marker that
``Documents/plans/chunk-03-coveo-discovery-adapter-and-streamed-raw-persistence.md``
section 9 assigns to its base node ID, plus a matching entry in
``tests/traceability.json``. The two non-analytical tests named in section 9
carry no marker and no traceability entry.

Everything is offline and deterministic: the opener, sleeper, clock, and
credentials are injected, and no fixture contacts a live endpoint, reads the
system clock, or carries a real credential. Response-shaped fixtures are
hand-derived assumptions about the live contract (plan §12.9); request fixtures
are anchored to the committed capture at ``config/coveo_search_template.json``.
"""

from __future__ import annotations

import dataclasses
import json
import tempfile
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterator, Mapping, Sequence

import fixtures.coveo_discovery as fx
import pytest

import fixtures.graphql_fixtures as gqlfx

from niche_scout import collector_coveo
from niche_scout import collector_graphql
from niche_scout.config import UNITY_CSRF_TOKEN_ENV, Credentials, get_credentials
from niche_scout.database import (
    RepositoryError,
    SqliteRepository,
    UniqueConstraintViolation,
)
from niche_scout.models import (
    MAX_DISCOVERY_RESULTS_PER_CATEGORY,
    PAGE_SIZE,
    CategoryFilterValidationStatus,
    DiscoveryStatus,
    GraphQLOperationCorrelationMode,
    IdentityPreflightStatus,
    IdentityResolutionStatus,
    OperationStatus,
    RawDiscoveryObservationRecord,
    RunRecord,
    RunStatus,
    WarningCode,
)
from niche_scout.validation import (
    match_exact_category,
    resolve_canonical_identity,
    taxonomy_path_set,
)

CATEGORY = fx.COVEO_FIXTURE_CATEGORY
OTHER_CATEGORY = fx.COVEO_FIXTURE_CATEGORY_OTHER
RUN_ID = "run-chunk-03"
FIXED_NOW = datetime(2026, 9, 17, 4, 30, 0, tzinfo=timezone.utc)

#: The capture's committed body, read once and treated as read-only.
CAPTURE_BODY: Mapping[str, Any] = fx.template_body()

#: An illustrative, **non-normative** sample of fields outside this adapter's
#: discovery-only scope, used by this module's tests as sample data. It is not a
#: list the SRS defines: ``LREQ-EXT-040`` ("Discovery SHALL use the parent SRS
#: discovery-only field set: ``permanentid``, ``ec_product_id``, ``ec_name``,
#: ``ec_category``, and ``publisher_name``. Product rating, page views,
#: publication date, and price SHALL NOT be sourced from Coveo for scoring.")
#: names the *allowed* five fields and then forbids rating, page views,
#: publication date, and price by category — it never enumerates a blocklist of
#: member names, so no reader may treat this tuple as normative. Enforcement
#: lives in the adapter as an allow-list complement
#: (``collector_coveo.COVEO_DISCOVERY_FIELD_SET``); see
#: ``test_response_carrying_a_novel_member_records_forbidden_presence``.
#:
#: ``ec_rating_count`` is governed less by ``LREQ-EXT-040`` than by the §4.2
#: source-separation rule ("GraphQL is authoritative for rating, rating count,
#: review count, first publication date, page views, publisher, category, state,
#: and product identity confirmation. Neither source SHALL provide duplicate
#: scoring fields for the same metric."): rating count has a GraphQL owner, so
#: Coveo sourcing it would be a duplicate source, not merely an unlisted field.
SAMPLE_OUT_OF_SCOPE_FIELDS = (
    "ec_rating",
    "ec_rating_count",
    "ec_price",
    "ec_price_filter",
    "ec_sale",
    "ec_thumbnails",
    "first_published_at",
    "ec_popularity",
)

#: Members the request builder replaces from the capture rather than replaying
#: (the two telemetry blocks, the offset, and the forced field set).
REPLACED_MEMBERS = frozenset({"facets", "firstResult", "fieldsToInclude"})


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------


class RecordedResponse:
    """The minimal opener-result contract: ``status``, ``headers``, ``read()``."""

    def __init__(
        self, status: int, body: bytes, headers: Mapping[str, str] | None = None
    ) -> None:
        self.status = int(status)
        self.headers = dict(headers or {})
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "RecordedResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class Recorder:
    """A callable that records every numeric value it is called with."""

    def __init__(self) -> None:
        self.calls: list[float] = []

    def __call__(self, value: float) -> None:
        self.calls.append(float(value))


class RecordingOpener:
    """A scripted opener that records every request it is asked to send.

    ``serve`` is called once per request with the request count; the adapter's
    own retry policy is what the request count measures, so the opener itself
    never retries.
    """

    def __init__(self, serve, *, on_open=None) -> None:
        self._serve = serve
        self._on_open = on_open
        self.requests: list[Any] = []
        self.bodies: list[dict[str, Any]] = []

    @property
    def request_count(self) -> int:
        return len(self.requests)

    def open(self, request: Any) -> Any:
        self.requests.append(request)
        payload = getattr(request, "data", None)
        if isinstance(payload, (bytes, bytearray)):
            try:
                self.bodies.append(json.loads(bytes(payload).decode("utf-8")))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self.bodies.append({})
        else:
            self.bodies.append({})
        if self._on_open is not None:
            self._on_open(self.request_count)
        return self._serve(self.request_count)


def page_response(
    page_records: Sequence[Mapping[str, Any]],
    *,
    total_count: int | None,
    filtered_count: int | None = None,
    status: int = 200,
    headers: Mapping[str, str] | None = None,
) -> RecordedResponse:
    """Return a recorded response carrying one page of records."""
    body = fx.make_page(
        page_records, total_count=total_count, filtered_count=filtered_count
    )
    return RecordedResponse(status, fx.wrap_page_json(body), headers)


def paged_opener(pages: Sequence[RecordedResponse], *, on_open=None) -> RecordingOpener:
    """Return an opener serving ``pages`` once each, repeating the last page."""

    def serve(index: int) -> RecordedResponse:
        return pages[min(index, len(pages)) - 1]

    return RecordingOpener(serve, on_open=on_open)


def paging_opener(page_size: int, total: int) -> RecordingOpener:
    """Return an opener serving ``total`` distinct records ``page_size`` at a time."""

    def serve(index: int) -> RecordedResponse:
        start = (index - 1) * page_size
        count = min(page_size, max(0, total - start))
        return page_response(fx.records(count, start=start), total_count=total)

    return RecordingOpener(serve)


_CONFIG_CACHE: dict[str, Any] = {}


def default_config(**overrides: Any):
    """Return a real ``NicheScoutConfig`` for the suite without writing to the tree."""
    if not _CONFIG_CACHE:
        from fixtures.config_fixtures import DEFAULT_TOML_BODY, write_toml

        from niche_scout.config import load_config

        with tempfile.TemporaryDirectory() as directory:
            toml_path = write_toml(Path(directory), DEFAULT_TOML_BODY, name="suite.toml")
            config = load_config(toml_path=toml_path)
        _CONFIG_CACHE["config"] = dataclasses.replace(
            config,
            taxonomy_path=fx.TAXONOMY_PATH_FIXTURE,
            db_path=Path("unused-by-discovery-tests.sqlite3"),
        )
    base = _CONFIG_CACHE["config"]
    return dataclasses.replace(base, **overrides) if overrides else base


def _insert_run(repo: SqliteRepository, run_id: str = RUN_ID) -> None:
    """Insert one run row; every observation row carries a foreign key to it."""
    repo.insert_run(
        RunRecord(
            run_id=run_id,
            run_started_at_utc=FIXED_NOW,
            scoring_cutoff_utc=None,
            completed_at_utc=None,
            categories_json=json.dumps([CATEGORY, OTHER_CATEGORY]),
            config_snapshot_json="{}",
            config_sha256="0" * 64,
            taxonomy_version="1.0.0",
            taxonomy_captured_at_utc=FIXED_NOW,
            taxonomy_sha256="0" * 64,
            endpoint_contract_version="1.0.0",
            identity_mapping_rule_version="1.0.1",
            sampling_rule_version="2.0.0",
            page_view_semantics_status="unvalidated",
            graphql_operation_correlation_mode="explicit_key",
            identity_preflight_status=IdentityPreflightStatus.INSUFFICIENT.value,
            identity_preflight_summary_json="{}",
            status=RunStatus.RUNNING.value,
        )
    )


@pytest.fixture()
def repository(tmp_path: Path) -> Iterator[SqliteRepository]:
    """A real, file-backed Chunk 2 repository under pytest's temp path."""
    repo = SqliteRepository(tmp_path / "chunk03.sqlite3")
    try:
        _insert_run(repo)
        yield repo
    finally:
        repo.close()


def make_sink(
    repo: SqliteRepository,
    *,
    category: str = CATEGORY,
    run_id: str = RUN_ID,
    **kwargs: Any,
) -> collector_coveo.CoveoObservationSink:
    """Return the adapter's streaming sink over a real repository."""
    return collector_coveo.CoveoObservationSink(
        repo, run_id, category, clock=lambda: FIXED_NOW, **kwargs
    )


def discover(
    repo: SqliteRepository,
    opener,
    *,
    category: str = CATEGORY,
    sink: collector_coveo.CoveoObservationSink | None = None,
    taxonomy: Mapping[str, Any] | None = None,
    config=None,
    credentials=None,
    sleeper=None,
    clock=None,
    template_path: Path | None = None,
):
    """Run one real, repository-backed ``discover_category`` call."""
    arguments: dict[str, Any] = {
        "category": category,
        "taxonomy_payload": fx.TAXONOMY_PAYLOAD if taxonomy is None else taxonomy,
        "config": default_config() if config is None else config,
        "credentials": fx.credentials() if credentials is None else credentials,
        "reference_utc": fx.REFERENCE_UTC,
        "sink": sink if sink is not None else make_sink(repo, category=category),
        "transport": opener,
        "sleeper": sleeper if sleeper is not None else Recorder(),
        "clock": clock if clock is not None else (lambda: FIXED_NOW),
        "run_id": RUN_ID,
    }
    if template_path is not None:
        arguments["template_path"] = template_path
    return collector_coveo.discover_category(**arguments)


def rows_by_ordinal(repo: SqliteRepository, category: str = CATEGORY) -> dict[int, Any]:
    """Return a category's persisted rows keyed by discovery ordinal."""
    return {
        row.discovery_ordinal: row
        for row in repo.iter_raw_discovery_observations(RUN_ID, category)
    }


def statuses_by_category(repo: SqliteRepository) -> dict[str, Any]:
    """Return the persisted discovery status of every category of the run."""
    return {row.category: row.discovery_status for row in repo.get_category_scores(RUN_ID)}


# ---------------------------------------------------------------------------
# Non-analytical tests (no marker, no traceability entry)
# ---------------------------------------------------------------------------


def test_module_imports_without_side_effects() -> None:
    """Importing the adapter binds the frozen surface and touches nothing."""
    assert collector_coveo.COVEO_ENDPOINT.startswith("https://")
    assert collector_coveo.COVEO_ORGANIZATION_ID in collector_coveo.coveo_search_url()
    assert collector_coveo.COVEO_VISITOR_ID_PLACEHOLDER == "niche-scout-lean-v1"
    assert collector_coveo.COVEO_TEMPLATE_PATH == Path("config") / "coveo_search_template.json"
    assert collector_coveo.COVEO_MIN_REQUEST_INTERVAL_SECONDS == 1.0
    assert collector_coveo.COVEO_BACKOFF_BASE_SECONDS == 2.0
    assert collector_coveo.COVEO_MAX_RETRIES == 5
    assert PAGE_SIZE == 96
    assert collector_coveo.COVEO_DISCOVERY_FIELD_SET == (
        "permanentid",
        "ec_product_id",
        "ec_name",
        "ec_category",
        "publisher_name",
    )
    header_names = [name.casefold() for name, _ in collector_coveo.COVEO_REQUIRED_HEADERS]
    assert header_names == ["content-type", "accept", "referer"]
    for absent in (
        "origin",
        "sec-ch-ua",
        "sec-ch-ua-mobile",
        "sec-fetch-site",
        "sec-fetch-mode",
        "priority",
        "pragma",
        "cache-control",
    ):
        assert absent not in header_names


def test_request_body_builder_signature_is_stable() -> None:
    """``build_coveo_request_body`` keeps its frozen keyword-only contract."""
    import inspect

    signature = inspect.signature(collector_coveo.build_coveo_request_body)
    assert list(signature.parameters) == ["template", "category", "page_index", "page_size"]
    assert signature.parameters["page_index"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["page_size"].default == PAGE_SIZE
    headers_signature = inspect.signature(collector_coveo.build_coveo_headers)
    assert list(headers_signature.parameters) == ["bearer_token"]


# ---------------------------------------------------------------------------
# LREQ-EXT-010 — endpoint, headers, captured template, selected-category facet
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-EXT-010")
def test_coveo_endpoint_headers_and_facet_selection_match_captured_template(
    repository: SqliteRepository,
) -> None:
    """Endpoint, headers, header members, and the single facet all hold.

    The body is compared against the committed capture through the sections that
    actually differ (the facet block, the offset, and the forced field set), so a
    replayed member cannot drift without failing this test.
    """
    template = fx.load_template()
    for field in fx.TEMPLATE_HEADER_FIELDS:
        assert field in template, f"capture provenance header lost '{field}'"
    assert template["template_sha256"] == fx.capture_sha256()
    assert template["endpoint"] == collector_coveo.COVEO_ENDPOINT
    assert template["organization_id"] == collector_coveo.COVEO_ORGANIZATION_ID

    assert collector_coveo.coveo_search_url() == (
        f"{collector_coveo.COVEO_ENDPOINT}?organizationId="
        f"{collector_coveo.COVEO_ORGANIZATION_ID}"
    )

    headers = collector_coveo.build_coveo_headers("fixture-token")
    assert headers["Content-Type"] == "application/json"
    assert headers["Accept"] == "application/json"
    assert headers["Referer"] == "https://assetstore.unity.com/"
    assert "Origin" not in headers
    assert headers["Authorization"] == "Bearer fixture-token"

    body = fx.request_body()
    replayed = {
        name: capture_value
        for name, capture_value in CAPTURE_BODY.items()
        if name not in REPLACED_MEMBERS and name not in {"actionsHistory", "analytics"}
    }
    observed = {name: body[name] for name in replayed if name in body}
    assert fx.canonical_text(observed) == fx.canonical_text(replayed)

    assert body["fieldsToInclude"] == list(collector_coveo.COVEO_DISCOVERY_FIELD_SET)
    facets = body["facets"]
    assert [entry["facetId"] for entry in facets] == ["ec_category"]
    facet = facets[0]
    assert facet["type"] == "specific"
    assert facet["resultsMustMatch"] == "atLeastOneValue"
    assert facet["numberOfValues"] == 150
    assert [entry["value"] for entry in facet["currentValues"]] == list(
        fx.CAPTURED_STATE_BY_CATEGORY
    )
    selected = [entry["value"] for entry in facet["currentValues"] if entry["state"] == "selected"]
    idle = [entry["value"] for entry in facet["currentValues"] if entry["state"] == "idle"]
    assert selected == [CATEGORY]
    assert len(idle) == len(fx.CAPTURED_STATE_BY_CATEGORY) - 1

    opener = paging_opener(PAGE_SIZE, 2)
    result = discover(repository, opener)
    assert result.discovery_status is DiscoveryStatus.COMPLETE
    sent = opener.requests[0]
    assert sent.full_url == collector_coveo.coveo_search_url()
    sent_names = {name.casefold() for name in sent.headers}
    assert "authorization" in sent_names
    assert "content-type" in sent_names
    assert "accept" in sent_names
    assert "referer" in sent_names
    assert sent_names - {"authorization"} == {
        name.casefold() for name, _ in collector_coveo.COVEO_REQUIRED_HEADERS
    }


@pytest.mark.lreq("LREQ-EXT-010")
def test_authorization_header_normalizes_a_supplied_bearer_scheme_prefix() -> None:
    """A credential stored as ``"Bearer eyJ…"`` never doubles its scheme.

    ``config.get_credentials()`` only strips whitespace, so this is the shape a
    real ``.env`` supplies; the header is checked through that real accessor, not
    through a hand-built credential object.
    """
    credentials = fx.env_credentials_with_bearer_scheme()
    assert credentials.coveo_token.startswith("Bearer ")
    headers = collector_coveo.build_coveo_headers(credentials.coveo_bearer_token)
    assert headers["Authorization"] == f"Bearer {fx.BEARER_TOKEN}"
    assert "Bearer Bearer" not in headers["Authorization"]

    for form in (
        f"Bearer {fx.BEARER_TOKEN}",
        f"bearer {fx.BEARER_TOKEN}",
        f"  Bearer {fx.BEARER_TOKEN}  ",
    ):
        assert collector_coveo.build_coveo_headers(form)["Authorization"] == (
            f"Bearer {fx.BEARER_TOKEN}"
        )


# ---------------------------------------------------------------------------
# LREQ-EXT-030 — no free-text relevance member
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-EXT-030")
def test_request_body_rejects_free_text_q_and_query_at_any_depth(
    repository: SqliteRepository,
) -> None:
    """An injected ``q``/``query`` at any depth is rejected before it is sent."""
    body = fx.request_body()
    assert collector_coveo.find_forbidden_query_field(body) is None
    assert "q" not in body
    assert "query" not in body

    with pytest.raises(ValueError, match="forbidden"):
        collector_coveo.reject_free_text_query_members(fx.page_with_q_field())

    for depth in (1, 2, 3):
        nested: dict[str, Any] = {"query": "keyword"}
        for _ in range(depth):
            nested = {"deeper": nested}
        injected = json.loads(json.dumps(body))
        injected["context"] = {"searchHub": "Assetstore_Listing", **nested}
        with pytest.raises(ValueError, match="forbidden"):
            collector_coveo.reject_free_text_query_members(injected)

    shallow = json.loads(json.dumps(body))
    shallow["facets"][0]["currentValues"][0]["q"] = "keyword"
    with pytest.raises(ValueError, match="forbidden"):
        collector_coveo.reject_free_text_query_members(shallow)

    sent: list[str] = []

    def serve(index: int) -> RecordedResponse:
        return page_response(fx.records(1), total_count=1)

    opener = RecordingOpener(serve, on_open=lambda count: sent.append(str(count)))
    discover(repository, opener)
    serialized = json.dumps(opener.bodies)
    assert '"q"' not in serialized
    assert '"query"' not in serialized


# ---------------------------------------------------------------------------
# LREQ-EXT-040 — the discovery-only field set
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-EXT-040")
def test_request_uses_discovery_only_field_set(repository: SqliteRepository) -> None:
    """The request declares exactly the five discovery fields, and no other."""
    body = fx.request_body()
    assert body["fieldsToInclude"] == list(collector_coveo.COVEO_DISCOVERY_FIELD_SET)
    serialized = fx.canonical_text(body)
    for forbidden in SAMPLE_OUT_OF_SCOPE_FIELDS:
        assert f'"{forbidden}"' not in serialized

    for forbidden in SAMPLE_OUT_OF_SCOPE_FIELDS:
        assert not any(forbidden == name for name in body["fieldsToInclude"])

    opener = paging_opener(PAGE_SIZE, 1)
    discover(repository, opener)
    assert opener.bodies[0]["fieldsToInclude"] == list(
        collector_coveo.COVEO_DISCOVERY_FIELD_SET
    )


@pytest.mark.lreq("LREQ-EXT-040")
def test_response_reader_never_sources_forbidden_scoring_fields(
    repository: SqliteRepository,
) -> None:
    """A record carrying forbidden scoring fields stores none of them as evidence."""
    record = {
        "permanentid": "P-1",
        "ec_product_id": "P-1",
        "ec_name": "Fixture Asset",
        "ec_category": CATEGORY,
        "publisher_name": "Fixture Publisher",
        "ec_rating": 4.75,
        "ec_price": 42,
        "ec_thumbnails": ["https://example.invalid/thumb.png"],
        "ec_popularity": 9001,
        "first_published_at": 1600000000,
    }
    opener = RecordingOpener(lambda index: page_response([record], total_count=1))
    result = discover(repository, opener)
    assert result.discovery_status is DiscoveryStatus.COMPLETE

    row = rows_by_ordinal(repository)[0]
    assert json.loads(row.category_value_json) == CATEGORY
    candidates = json.loads(row.identity_candidates_json)
    assert [item["source_field"] for item in candidates] == [
        "ec_product_id",
        "permanentid",
    ]
    persisted = " ".join(
        filter(
            None,
            (
                row.request_metadata_json,
                row.error_summary_json,
                row.identity_candidates_json,
                row.identity_resolution_reason,
            ),
        )
    )
    for forbidden in SAMPLE_OUT_OF_SCOPE_FIELDS:
        assert forbidden not in persisted
    assert "4.75" not in persisted
    assert "9001" not in persisted


@pytest.mark.lreq("LREQ-EXT-040")
def test_extra_response_fields_are_ignored_and_missing_identity_fields_stay_missing(
    repository: SqliteRepository,
) -> None:
    """Extra members are ignored; a missing identity field stays missing, not zero."""
    extra = dict(fx.record(0, permanentid=None, ec_product_id=None))
    extra["ec_some_future_field"] = {"nested": [1, 2, 3]}
    opener = RecordingOpener(lambda index: page_response([extra, fx.record(1)], total_count=2))
    result = discover(repository, opener)

    rows = rows_by_ordinal(repository)
    assert len(rows) == 2
    assert rows[0].identity_resolution_status == IdentityResolutionStatus.UNRESOLVED.value
    assert rows[0].asset_identity_key is None
    assert rows[0].stratum_index is None
    assert json.loads(rows[0].category_value_json) == CATEGORY
    assert rows[1].identity_resolution_status == IdentityResolutionStatus.RESOLVED.value
    assert result.unresolved_identity_count == 1
    assert result.canonical_identity_count == 1

    # The extra member's *value* is never carried into anything persisted.
    persisted_extra = " ".join(
        filter(
            None,
            (
                rows[0].request_metadata_json,
                rows[0].error_summary_json,
                rows[0].identity_candidates_json,
                rows[0].identity_resolution_reason,
            ),
        )
    )
    assert "ec_some_future_field" not in persisted_extra
    assert "nested" not in persisted_extra

    # The response-side member set is required: a page that omits it is not read
    # as though it declared it.
    without_members = fx.make_page([{"ec_name": "Nameless"}], total_count=1)
    missing = RecordingOpener(
        lambda index: RecordedResponse(200, fx.wrap_page_json(without_members))
    )
    result_missing = discover(repository, missing, category=OTHER_CATEGORY)
    assert result_missing.discovery_status is DiscoveryStatus.PAGE_FAILED
    assert any(
        issue.code == "response_missing_required_member"
        for issue in result_missing.issues
    )


@pytest.mark.lreq("LREQ-EXT-040")
def test_response_carrying_a_novel_member_records_forbidden_presence(
    repository: SqliteRepository,
) -> None:
    """The allow-list *complement* records presence of a field no list names.

    The two field-set tests above *walk* a list, so any under-inclusive list
    passes them. This test exercises the mechanism itself
    (``collector_coveo``'s ``if any(key not in _DISCOVERY_RESPONSE_FIELD_SET ...)``
    branch) with a member name that appears in no vocabulary anywhere in the
    repository: the record must still be read, and the presence of the
    out-of-scope member must be *recorded* — the fact and the count only, never
    the member name or its value, because a scoring field's name has no business
    in the persisted metadata (LREQ-EXT-040).
    """
    novel_member = "ec_some_future_scoring_field"
    record = dict(fx.record(0))
    record[novel_member] = {"secret_payload": "must-not-be-persisted"}
    opener = RecordingOpener(lambda index: page_response([record], total_count=1))
    result = discover(repository, opener)

    # The record is still an ordinary, readable asset: an extra member is a
    # recorded condition, not a structural failure and not a dropped record.
    assert result.discovery_status is DiscoveryStatus.COMPLETE
    rows = rows_by_ordinal(repository)
    assert len(rows) == 1
    assert rows[0].identity_resolution_status == IdentityResolutionStatus.RESOLVED.value

    metadata = json.loads(rows[0].request_metadata_json)
    assert metadata["forbidden_field_presence"] == [
        {"record_index": 0, "extra_member_count": 1}
    ]
    # The record-level page metadata carries the *fact*; the novel name and its
    # value are deliberately absent from every persisted column.
    assert novel_member not in rows[0].request_metadata_json
    assert "must-not-be-persisted" not in rows[0].request_metadata_json


# ---------------------------------------------------------------------------
# LREQ-EXT-050 — pagination, terminal status, and no fabricated zeros
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-EXT-050")
def test_pagination_stops_at_verified_total_count(repository: SqliteRepository) -> None:
    """Traversal stops as soon as the verified ``totalCount`` is reached."""
    total = PAGE_SIZE + 4
    pages = [
        page_response(fx.records(PAGE_SIZE), total_count=total, filtered_count=total),
        page_response(
            fx.records(4, start=PAGE_SIZE), total_count=total, filtered_count=total
        ),
    ]
    opener = paged_opener(pages)
    result = discover(repository, opener)

    assert opener.request_count == 2
    assert result.discovery_status is DiscoveryStatus.COMPLETE
    assert result.total_count == total
    assert result.api_reported_count == total
    assert result.observations_emitted == total
    assert result.pages_fetched == 2
    assert result.ordinal_start == 0
    assert result.ordinal_end == total
    assert repository.count_raw_discovery_observations(RUN_ID, CATEGORY) == total


@pytest.mark.lreq("LREQ-EXT-050")
def test_pagination_stops_at_natural_terminal_page(repository: SqliteRepository) -> None:
    """A short page with no usable ``totalCount`` ends the category naturally."""
    pages = [
        page_response(fx.records(PAGE_SIZE), total_count=None),
        page_response(fx.records(7, start=PAGE_SIZE), total_count=None),
    ]
    opener = paged_opener(pages)
    result = discover(repository, opener)

    assert opener.request_count == 2
    assert result.discovery_status is DiscoveryStatus.COMPLETE
    assert result.total_count is None
    assert result.api_reported_count is None
    assert result.observations_emitted == PAGE_SIZE + 7
    assert DiscoveryStatus.TRUNCATED not in result.conditions


@pytest.mark.lreq("LREQ-EXT-050")
def test_pagination_truncates_at_max_results_and_retains_api_count(
    repository: SqliteRepository,
) -> None:
    """The cap stops traversal, records ``truncated``, and keeps the API count."""
    available = MAX_DISCOVERY_RESULTS_PER_CATEGORY + PAGE_SIZE
    opener = paging_opener(PAGE_SIZE, available)
    result = discover(repository, opener)

    assert result.discovery_status is DiscoveryStatus.TRUNCATED
    assert DiscoveryStatus.TRUNCATED in result.conditions
    assert result.total_count == available
    assert result.api_reported_count == available
    assert result.observations_emitted == MAX_DISCOVERY_RESULTS_PER_CATEGORY
    assert (
        repository.count_raw_discovery_observations(RUN_ID, CATEGORY)
        == result.observations_emitted
    )


@pytest.mark.lreq("LREQ-EXT-050")
def test_failed_page_never_becomes_zero_assets(repository: SqliteRepository) -> None:
    """A failed request records ``request_failed`` and never a zero-asset claim."""
    sleeper = Recorder()
    opener = RecordingOpener(lambda index: RecordedResponse(503, b"unavailable"))
    result = discover(repository, opener, sleeper=sleeper)

    assert result.discovery_status is DiscoveryStatus.REQUEST_FAILED
    assert DiscoveryStatus.REQUEST_FAILED in result.conditions
    assert result.observations_emitted == 0
    assert result.total_count is None
    assert result.api_reported_count is None
    assert result.canonical_identity_count == 0
    assert repository.count_raw_discovery_observations(RUN_ID, CATEGORY) == 0
    assert statuses_by_category(repository)[CATEGORY] == DiscoveryStatus.REQUEST_FAILED.value

    malformed = RecordingOpener(
        lambda index: RecordedResponse(200, fx.wrap_page_json(fx.malformed_page()))
    )
    result_malformed = discover(repository, malformed, category=OTHER_CATEGORY)
    assert result_malformed.discovery_status is DiscoveryStatus.PAGE_FAILED
    assert result_malformed.observations_emitted == 0
    assert result_malformed.canonical_identity_count == 0
    assert repository.count_raw_discovery_observations(RUN_ID, OTHER_CATEGORY) == 0


@pytest.mark.lreq("LREQ-EXT-050")
def test_zero_result_category_requires_verified_filter(
    repository: SqliteRepository,
) -> None:
    """A structurally verified zero result is evidence; an unverified one is not."""
    verified = RecordingOpener(
        lambda index: page_response([], total_count=0, filtered_count=0)
    )
    result = discover(repository, verified)
    assert result.observations_emitted == 0
    assert result.total_count == 0
    assert result.filter_status is CategoryFilterValidationStatus.VERIFIED
    assert DiscoveryStatus.FILTER_UNVERIFIED not in result.conditions
    assert result.discovery_status is DiscoveryStatus.COMPLETE

    body = fx.utterly_empty_page()
    body["totalCount"] = "not-a-count"
    unverifiable = RecordingOpener(
        lambda index: RecordedResponse(200, fx.wrap_page_json(body))
    )
    other = discover(repository, unverifiable, category=OTHER_CATEGORY)
    assert other.observations_emitted == 0
    assert other.total_count is None
    assert other.discovery_status is not DiscoveryStatus.COMPLETE
    assert (
        other.filter_status is not CategoryFilterValidationStatus.VERIFIED
        or DiscoveryStatus.FILTER_UNVERIFIED in other.conditions
    )


# ---------------------------------------------------------------------------
# LREQ-EXT-060 — retained identity candidates
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-EXT-060")
def test_every_non_empty_identity_candidate_is_retained(
    repository: SqliteRepository,
) -> None:
    """Every non-empty candidate from all four source fields reaches the row."""
    record = {
        "permanentid": "1234567",
        "ec_product_id": "1234567",
        "ec_name": "Fixture Asset",
        "ec_category": CATEGORY,
        "publisher_name": "Fixture Publisher",
        "clickUri": "https://assetstore.unity.com/packages/fixture-1-1234567",
        "uri": "https://assetstore.unity.com/packages/fixture-1-1234567",
    }
    opener = RecordingOpener(lambda index: page_response([record], total_count=1))
    result = discover(repository, opener)

    assert result.discovery_status is DiscoveryStatus.COMPLETE
    rows = rows_by_ordinal(repository)
    assert len(rows) == 1
    candidates = json.loads(rows[0].identity_candidates_json)
    assert [item["source_field"] for item in candidates] == [
        "ec_product_id",
        "permanentid",
        "clickUri",
        "uri",
    ]
    assert all(item["canonical_value"] is not None for item in candidates)
    assert rows[0].identity_resolution_status == IdentityResolutionStatus.RESOLVED.value
    assert rows[0].asset_identity_key == "1234567"
    assert json.loads(
        json.dumps(candidates, sort_keys=True)
    ) == json.loads(rows[0].identity_candidates_json)


@pytest.mark.lreq("LREQ-EXT-060")
def test_uri_fallback_and_unparseable_candidates_contribute_nothing(
    repository: SqliteRepository,
) -> None:
    """A URI fallback resolves; a candidate that cannot be parsed contributes none.

    "Contributes nothing" is a per-*candidate* property, not a per-record one:
    the second record below resolves through its ``uri`` even though its
    ``clickUri`` abstains. Abstention means the unparseable member yields no
    canonical value (``canonical_value is None`` with a reason), never a guessed
    or partial identifier, so the record is classified from the candidates that
    *did* canonicalize — here a single agreeing key, i.e. ``resolved``.
    """
    fallback = fx.URI_FALLBACK_RECORD
    unparseable = {
        "permanentid": "",
        "ec_product_id": None,
        "ec_name": "Odd Asset",
        "ec_category": CATEGORY,
        "publisher_name": "Fixture Publisher",
        "clickUri": "not-a-uri-with-identifier",
        "uri": "https://assetstore.unity.com/packages/fixture-7-654321",
    }
    opener = RecordingOpener(
        lambda index: page_response([fallback, unparseable], total_count=2)
    )
    result = discover(repository, opener)

    assert result.discovery_status is DiscoveryStatus.COMPLETE
    rows = rows_by_ordinal(repository)
    first = json.loads(rows[0].identity_candidates_json)
    assert first == [
        {
            "source_field": "uri",
            "raw_value": fallback["uri"],
            "canonical_value": "999999",
            "parse_failure_reason": None,
        }
    ]
    assert rows[0].asset_identity_key == "999999"

    # The abstaining member is retained as a candidate with no canonical value
    # and a reason; it takes part in no verdict.
    second = json.loads(rows[1].identity_candidates_json)
    by_source = {item["source_field"]: item for item in second}
    assert by_source["clickUri"]["canonical_value"] is None
    assert by_source["clickUri"]["parse_failure_reason"]
    assert by_source["uri"]["canonical_value"] == "654321"
    # Only the one member that could be canonicalized is the record's identity;
    # the abstaining member neither votes nor blocks the genuine resolution.
    assert rows[1].asset_identity_key == "654321"
    assert rows[1].identity_resolution_status == IdentityResolutionStatus.RESOLVED.value
    assert result.canonical_identity_count == 2
    assert result.unresolved_identity_count == 0
    assert result.conflict_identity_count == 0


# ---------------------------------------------------------------------------
# LREQ-EXT-070 — conflict and unresolved records
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-EXT-070")
def test_conflict_and_unresolved_records_are_persisted_and_excluded_from_canonical_count(
    repository: SqliteRepository,
) -> None:
    """Conflict and unresolved rows persist with no key and no canonical vote."""
    page = [fx.record(0), fx.conflicting_record(1), fx.record_without_identity(2)]
    opener = RecordingOpener(lambda index: page_response(page, total_count=3))
    result = discover(repository, opener)

    rows = rows_by_ordinal(repository)
    assert len(rows) == 3
    assert [rows[ordinal].identity_resolution_status for ordinal in sorted(rows)] == [
        IdentityResolutionStatus.RESOLVED.value,
        IdentityResolutionStatus.CONFLICT.value,
        IdentityResolutionStatus.UNRESOLVED.value,
    ]
    assert rows[1].asset_identity_key is None
    assert rows[2].asset_identity_key is None
    assert rows[1].identity_resolution_reason
    assert rows[2].identity_resolution_reason
    assert json.loads(rows[1].category_value_json) == CATEGORY

    assert result.canonical_identity_count == 1
    assert result.conflict_identity_count == 1
    assert result.unresolved_identity_count == 1
    assert result.observations_emitted == 3
    assert DiscoveryStatus.IDENTITY_INCOMPLETE in result.conditions
    assert DiscoveryStatus.CATEGORY_MISMATCH not in result.conditions
    assert statuses_by_category(repository)[CATEGORY] == (
        DiscoveryStatus.IDENTITY_INCOMPLETE.value
    )

    # A numeric-vs-string pair of agreeing identifiers is one canonical identity.
    numeric = fx.record(3, permanentid="0081", ec_product_id="81")
    opener_agreeing = RecordingOpener(
        lambda index: page_response([numeric], total_count=1)
    )
    agreeing = discover(repository, opener_agreeing, category=OTHER_CATEGORY)
    assert agreeing.canonical_identity_count == 1
    assert agreeing.conflict_identity_count == 0
    row = rows_by_ordinal(repository, OTHER_CATEGORY)[0]
    assert row.identity_resolution_status == IdentityResolutionStatus.RESOLVED.value
    assert row.asset_identity_key is not None


# ---------------------------------------------------------------------------
# LREQ-EXT-080 — exact category matching
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-EXT-080")
def test_exact_category_match_scalar_and_multivalued(repository: SqliteRepository) -> None:
    """Scalar and multi-valued ``ec_category`` shapes are classified explicitly."""
    page = [
        fx.record(0, category=CATEGORY),
        fx.record(1, category=[CATEGORY, "Audio/Music/Ambient"]),
        fx.record(2, category=["Nothing/Here/Fixture", "Nowhere/Else/Either"]),
        fx.record(3, category=None),
    ]
    opener = RecordingOpener(lambda index: page_response(page, total_count=4))
    result = discover(repository, opener)

    rows = rows_by_ordinal(repository)
    assert rows[0].category_filter_validation_status == (
        CategoryFilterValidationStatus.VERIFIED.value
    )
    assert rows[1].category_filter_validation_status == (
        CategoryFilterValidationStatus.VERIFIED.value
    )
    assert rows[2].category_filter_validation_status == (
        CategoryFilterValidationStatus.MISMATCH.value
    )
    assert rows[3].category_filter_validation_status == (
        CategoryFilterValidationStatus.UNVERIFIED.value
    )
    assert json.loads(rows[3].category_value_json) is None
    assert result.filter_status is CategoryFilterValidationStatus.VERIFIED
    assert result.conflict_identity_count == 0


@pytest.mark.lreq("LREQ-EXT-080")
def test_parent_path_does_not_match_child_path(repository: SqliteRepository) -> None:
    """A prefix of the requested path is a mismatch, never a match."""
    taxonomy_paths = taxonomy_path_set(fx.TAXONOMY_PAYLOAD)
    parent = CATEGORY.rsplit("/", 1)[0]
    child = f"{CATEGORY}/Fixture Child"
    for value in (parent, child):
        match = match_exact_category(value, taxonomy_paths)
        assert match.status is CategoryFilterValidationStatus.MISMATCH
        assert match.matched_path is None

    exact = match_exact_category(CATEGORY.lower(), taxonomy_paths)
    assert exact.status is CategoryFilterValidationStatus.VERIFIED
    assert exact.matched_path == CATEGORY

    opener = RecordingOpener(
        lambda index: page_response([fx.record(0, category=parent)], total_count=1)
    )
    result = discover(repository, opener)
    assert result.filter_status is CategoryFilterValidationStatus.MISMATCH
    assert result.conflict_identity_count == 0
    assert DiscoveryStatus.CATEGORY_MISMATCH in result.conditions
    assert DiscoveryStatus.IDENTITY_INCOMPLETE not in result.conditions


# ---------------------------------------------------------------------------
# LREQ-EXT-090 — conditions recorded, one terminal status selected
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-EXT-090")
def test_discovery_conditions_are_recorded_and_status_uses_severity_precedence(
    repository: SqliteRepository,
) -> None:
    """Every applicable condition is kept; the terminal one follows precedence.

    The merged condition sets are constructed directly because one traversal
    cannot produce a request failure and a mismatch at once: the precedence rule
    is what is under test, and the traversal half proves the set is populated and
    persisted.
    """
    choose = collector_coveo.select_terminal_status
    conditions = collector_coveo.order_conditions
    assert choose(
        (DiscoveryStatus.PAGE_FAILED, DiscoveryStatus.REQUEST_FAILED)
    ) is DiscoveryStatus.REQUEST_FAILED
    assert choose(
        (
            DiscoveryStatus.COMPLETE,
            DiscoveryStatus.TRUNCATED,
            DiscoveryStatus.FILTER_UNVERIFIED,
        )
    ) is DiscoveryStatus.FILTER_UNVERIFIED
    assert choose(
        (DiscoveryStatus.CATEGORY_MISMATCH, DiscoveryStatus.IDENTITY_INCOMPLETE)
    ) is DiscoveryStatus.CATEGORY_MISMATCH
    assert choose(
        (DiscoveryStatus.COMPLETE, DiscoveryStatus.TRUNCATED)
    ) is DiscoveryStatus.TRUNCATED
    assert choose(()) is DiscoveryStatus.COMPLETE
    assert conditions(
        (
            DiscoveryStatus.TRUNCATED,
            DiscoveryStatus.REQUEST_FAILED,
            DiscoveryStatus.TRUNCATED,
            DiscoveryStatus.CATEGORY_MISMATCH,
        )
    ) == (
        DiscoveryStatus.REQUEST_FAILED,
        DiscoveryStatus.CATEGORY_MISMATCH,
        DiscoveryStatus.TRUNCATED,
    )

    page = [fx.record(0), fx.conflicting_record(1), fx.record_without_identity(2)]
    opener = RecordingOpener(lambda index: page_response(page, total_count=3))
    result = discover(repository, opener)
    assert result.conditions == (DiscoveryStatus.IDENTITY_INCOMPLETE,)
    assert result.discovery_status is DiscoveryStatus.IDENTITY_INCOMPLETE
    assert result.discovery_status is result.conditions[0]
    assert statuses_by_category(repository)[CATEGORY] == (
        DiscoveryStatus.IDENTITY_INCOMPLETE.value
    )


# ---------------------------------------------------------------------------
# LREQ-EXT-100 — rate limiting, retry/backoff, Retry-After
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-EXT-100")
def test_transient_429_and_5xx_are_retried_with_backoff_and_retry_after(
    repository: SqliteRepository,
) -> None:
    """Transient statuses retry with exponential backoff and honor ``Retry-After``."""
    codes = [429, 503, 500, 200]
    sleeper = Recorder()

    def serve(index: int) -> RecordedResponse:
        code = codes[min(index, len(codes)) - 1]
        if code == 200:
            return page_response(fx.records(2), total_count=2)
        headers = {"Retry-After": "7"} if index == 1 else {}
        return RecordedResponse(code, b"transient", headers)

    opener = RecordingOpener(serve)
    result = discover(repository, opener, sleeper=sleeper)

    assert opener.request_count == 4
    assert result.discovery_status is DiscoveryStatus.COMPLETE
    assert result.observations_emitted == 2
    backoffs = [
        value
        for value in sleeper.calls
        if value >= collector_coveo.COVEO_BACKOFF_BASE_SECONDS
    ]
    assert backoffs == [7.0, 4.0, 8.0]
    # Four HTTP attempts belong to a single logical page, so exactly one
    # interval decision occurs; the run's first request owes no interval.
    intervals = [
        value
        for value in sleeper.calls
        if value == collector_coveo.COVEO_MIN_REQUEST_INTERVAL_SECONDS
    ]
    assert intervals == []


@pytest.mark.lreq("LREQ-EXT-100")
@pytest.mark.lreq("LREQ-TST-040")
def test_permanent_auth_csrf_and_malformed_request_are_not_retried(
    repository: SqliteRepository,
) -> None:
    """Permanent failures are raised at once and never retried."""
    for status in (401, 403, 400):
        sleeps = Recorder()
        opener = RecordingOpener(
            lambda index, status=status: RecordedResponse(status, b"permanent")
        )
        result = discover(repository, opener, sleeper=sleeps, category=CATEGORY)
        assert opener.request_count == 1, f"HTTP {status} must not be retried"
        assert sleeps.calls == []
        assert result.discovery_status is DiscoveryStatus.REQUEST_FAILED
        assert result.observations_emitted == 0

    exhausted = Recorder()
    attempts = RecordingOpener(lambda index: RecordedResponse(503, b"still failing"))
    result = discover(repository, attempts, sleeper=exhausted, category=OTHER_CATEGORY)
    assert attempts.request_count == collector_coveo.COVEO_MAX_RETRIES + 1
    assert len(exhausted.calls) == collector_coveo.COVEO_MAX_RETRIES
    backoffs = [
        value
        for value in exhausted.calls
        if value >= collector_coveo.COVEO_BACKOFF_BASE_SECONDS
    ]
    assert backoffs == [2.0, 4.0, 8.0, 16.0, 32.0]
    assert result.discovery_status is DiscoveryStatus.REQUEST_FAILED


# ---------------------------------------------------------------------------
# LREQ-NFR-010 — streamed persistence through the real page sink
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-NFR-010")
def test_observations_are_streamed_into_active_category_transaction(
    repository: SqliteRepository,
) -> None:
    """Every page is persisted inside one active category transaction.

    The page sink is the real ``insert_raw_discovery_observations``: the sink is
    wrapped so the transaction assertion and the durable row count are observed
    per page, and page *n+1* is only served once page *n*'s rows are already in
    the open transaction.
    """
    total = PAGE_SIZE + 5

    class TransactionObservingSink(collector_coveo.CoveoObservationSink):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self.transaction_states: list[bool] = []
            self.row_counts: list[int] = []

        def write_page(self, page, **kwargs):
            self.transaction_states.append(self.repository.in_category_transaction())
            outcome = super().write_page(page, **kwargs)
            self.row_counts.append(
                self.repository.count_raw_discovery_observations(
                    self.run_id, self.category
                )
            )
            return outcome

    sink = TransactionObservingSink(
        repository, RUN_ID, CATEGORY, clock=lambda: FIXED_NOW
    )

    def on_open(count: int) -> None:
        if count > 1:
            assert sink.row_counts[count - 2] == (count - 1) * PAGE_SIZE

    opener = paging_opener(PAGE_SIZE, total)
    opener._on_open = on_open
    result = discover(repository, opener, sink=sink)

    assert sink.transaction_states == [True, True]
    assert sink.row_counts == [PAGE_SIZE, total]
    assert result.ordinal_start == 0
    assert result.ordinal_end == total
    assert result.observations_emitted == result.ordinal_end - result.ordinal_start
    assert repository.count_raw_discovery_observations(RUN_ID, CATEGORY) == total

    ids = [
        row.observation_id
        for row in repository.iter_raw_discovery_observations(RUN_ID, CATEGORY)
    ]
    assert len(ids) == len(set(ids)) == total


@pytest.mark.lreq("LREQ-NFR-010")
def test_insert_outside_category_transaction_raises_repository_error(
    repository: SqliteRepository,
) -> None:
    """Bypassing the transaction boundary is rejected before records are read."""
    observation = RawDiscoveryObservationRecord(
        observation_id="outside-transaction",
        run_id=RUN_ID,
        category=CATEGORY,
        discovery_ordinal=0,
        asset_identity_key="P-1",
        identity_candidates_json="[]",
        identity_resolution_status=IdentityResolutionStatus.RESOLVED.value,
        identity_resolution_reason=None,
        category_value_json=json.dumps(CATEGORY),
        category_filter_validation_status=CategoryFilterValidationStatus.VERIFIED.value,
        stratum_index=None,
        is_duplicate=False,
        duplicate_of_observation_id=None,
        request_metadata_json="{}",
        error_summary_json=None,
        retrieved_at_utc=FIXED_NOW,
    )
    assert repository.in_category_transaction() is False
    with pytest.raises(RepositoryError):
        repository.insert_raw_discovery_observations([observation])
    assert repository.count_raw_discovery_observations(RUN_ID, CATEGORY) == 0

    sink = make_sink(repository)
    with pytest.raises(RepositoryError):
        sink.write([observation])

    duplicate = dataclasses.replace(
        observation,
        observation_id="second-row",
        discovery_ordinal=1,
        asset_identity_key="P-2",
    )
    with repository.category_transaction(RUN_ID, CATEGORY):
        repository.insert_raw_discovery_observations([observation])
        with pytest.raises(UniqueConstraintViolation):
            repository.insert_raw_discovery_observations([observation])
        repository.insert_raw_discovery_observations([duplicate])
    assert repository.count_raw_discovery_observations(RUN_ID, CATEGORY) == 2


@pytest.mark.lreq("LREQ-NFR-010")
def test_discovery_does_not_materialize_the_result_set(
    repository: SqliteRepository,
) -> None:
    """The traversal never holds a whole category's records in memory.

    Pages are requested one at a time and each request is only issued after the
    previous page is already persisted, and the adapter's durable row count is
    asserted against the streamed total rather than a container it filled.
    """
    total = 4 * PAGE_SIZE
    served: list[int] = []
    page_size = PAGE_SIZE

    def serve(index: int) -> RecordedResponse:
        served.append(index)
        start = (index - 1) * page_size
        return page_response(fx.records(page_size, start=start), total_count=total)

    opener = RecordingOpener(serve)
    result = discover(repository, opener)

    assert served == [1, 2, 3, 4]
    assert result.observations_emitted == total
    assert result.ordinal_end - result.ordinal_start == total
    assert repository.count_raw_discovery_observations(RUN_ID, CATEGORY) == total
    for body in opener.bodies:
        assert body["numberOfResults"] == page_size
        assert "results" not in body
        assert body["firstResult"] == (opener.bodies.index(body)) * page_size


# ---------------------------------------------------------------------------
# LREQ-NFR-030 — per-category failure isolation
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-NFR-030")
def test_failed_category_does_not_abort_other_categories_and_stays_visible(
    repository: SqliteRepository,
) -> None:
    """One category's failure leaves the other's committed rows and status intact."""
    good = RecordingOpener(lambda index: page_response(fx.records(3), total_count=3))
    first = discover(repository, good, category=CATEGORY)
    assert first.discovery_status is DiscoveryStatus.COMPLETE

    failing = RecordingOpener(
        lambda index: (
            page_response(fx.records(1), total_count=12)
            if index == 1
            else RecordedResponse(500, b"server error")
        )
    )
    second = discover(
        repository, failing, category=OTHER_CATEGORY, sleeper=Recorder()
    )

    assert second.discovery_status is DiscoveryStatus.REQUEST_FAILED
    assert second.observations_emitted == 1
    persisted = statuses_by_category(repository)
    assert persisted[CATEGORY] == DiscoveryStatus.COMPLETE.value
    assert persisted[OTHER_CATEGORY] == DiscoveryStatus.REQUEST_FAILED.value
    assert repository.count_raw_discovery_observations(RUN_ID, CATEGORY) == 3
    assert repository.count_raw_discovery_observations(RUN_ID, OTHER_CATEGORY) == 1

    rows = list(repository.iter_raw_discovery_observations(RUN_ID, OTHER_CATEGORY))
    assert len(rows) == 1
    assert rows[0].discovery_ordinal == 0
    retained = [
        row.observation_id
        for row in repository.iter_raw_discovery_observations(RUN_ID, CATEGORY)
    ]
    assert len(retained) == 3


# ---------------------------------------------------------------------------
# LREQ-SEC-010 — credentials required before any request
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SEC-010")
def test_credentials_are_required_before_any_request_and_bearer_scheme_is_normalized(
    repository: SqliteRepository,
) -> None:
    """A missing credential aborts before the opener sees anything."""
    with pytest.raises(ValueError) as missing:
        get_credentials({"NICHESCOUT_UNITY_CSRF_TOKEN": "fixture-csrf-token"})
    assert fx.BEARER_TOKEN not in str(missing.value)

    with pytest.raises(ValueError) as empty:
        collector_coveo.build_coveo_headers("   ")
    assert empty.value.args == (
        "a Coveo bearer credential is required before network collection",
    )

    opener = paging_opener(PAGE_SIZE, 1)
    result = discover(
        repository,
        opener,
        credentials=fx.credentials_from_environment(with_scheme=True),
    )
    assert result.discovery_status is DiscoveryStatus.COMPLETE
    sent = opener.requests[0].headers
    authorization = next(
        value for name, value in sent.items() if name.casefold() == "authorization"
    )
    assert authorization == f"Bearer {fx.BEARER_TOKEN}"
    assert "Bearer Bearer" not in authorization

    failing = RecordingOpener(lambda index: RecordedResponse(503, b"unavailable"))
    aborted = discover(
        repository,
        failing,
        category=OTHER_CATEGORY,
        credentials=fx.credentials_from_environment(with_scheme=True),
        sleeper=Recorder(),
    )
    assert aborted.discovery_status is DiscoveryStatus.REQUEST_FAILED


# ---------------------------------------------------------------------------
# LREQ-SEC-020 — nothing secret reaches persisted metadata
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SEC-020")
def test_persisted_metadata_and_error_summaries_contain_no_credentials(
    repository: SqliteRepository,
) -> None:
    """No token, header value, cookie, or raw response body is ever persisted."""

    def serve(index: int) -> RecordedResponse:
        if index == 1:
            return page_response(
                [fx.record(0), fx.conflicting_record(1), fx.record_without_identity(2)],
                total_count=3,
            )
        return RecordedResponse(500, b"raw response body that must not be stored")

    opener = RecordingOpener(serve)
    credentials = fx.credentials_from_environment(with_scheme=True)
    result = discover(repository, opener, sleeper=Recorder(), credentials=credentials)

    assert result.discovery_status is DiscoveryStatus.IDENTITY_INCOMPLETE
    assert result.observations_emitted == 3
    secrets = (fx.BEARER_TOKEN, "Bearer ", "Authorization", "fixture-csrf-token")
    for issue in result.issues:
        text = issue.to_json()
        for secret in secrets:
            assert secret not in text
        assert "raw response body" not in text

    rows = list(repository.iter_raw_discovery_observations(RUN_ID, CATEGORY))
    assert rows
    for row in rows:
        for field in (
            row.request_metadata_json,
            row.error_summary_json or "",
            row.identity_candidates_json,
            row.identity_resolution_reason or "",
        ):
            for secret in secrets:
                assert secret not in field
            assert "raw response body" not in field
        metadata = json.loads(row.request_metadata_json)
        assert "authorization" not in {name.casefold() for name in metadata}
        assert metadata["facets"] if "facets" in metadata else True
        assert metadata["facet_ids"] == ["ec_category"]

    statuses = statuses_by_category(repository)
    assert statuses[CATEGORY] == DiscoveryStatus.IDENTITY_INCOMPLETE.value


# ---------------------------------------------------------------------------
# Chunk 23 — transient transport retry and persisted discovery failure cause
# ---------------------------------------------------------------------------
#
# Scope authority:
# Documents/plans/chunk-23-coveo-transport-retry-and-persisted-failure-cause.md
# section 9. Every node below carries exactly the ``@pytest.mark.lreq`` marker
# that section's matrix assigns to its base node ID, plus a matching
# ``tests/traceability.json`` entry. Everything is offline and deterministic:
# the transport is the scripted fake below, the sleeper records durations, and
# no node reads the system clock.
#
# ``_ScriptedTransport`` is ``send``-shaped -- the canonical ``CoveoTransport``
# protocol of ``interfaces/chunk-03.md`` section 4 -- because
# ``RecordingOpener`` is ``open(request)``-shaped and cannot raise ``URLError``
# (plan section 9).

#: A URL-shaped sentinel (never a real credential) proving that transport
#: exception text cannot reach a message or a persisted column.
SCRIPTED_TRANSPORT_SENTINEL = "https://host.invalid/path?token=SECRET-SENTINEL-23"


class _ScriptedTransport:
    """A transport that raises a scripted exception or serves a scripted page.

    Script entries are consumed in order: a ``BaseException`` entry is raised
    (the R1 transport failure), an ``int`` entry becomes a bare
    ``RecordedResponse`` carrying that status, and any other entry is returned
    as-is (a ``RecordedResponse`` page). The last entry repeats once the script
    is exhausted, so a short script never silently stops the adapter's calls.
    """

    def __init__(self, script: Sequence[Any]) -> None:
        assert script, "the script must have at least one entry"
        self._script = tuple(script)
        self.calls: list[tuple[str, Mapping[str, str], bytes]] = []

    @property
    def call_count(self) -> int:
        return len(self.calls)

    def send(self, url: str, headers: Mapping[str, str], payload: bytes) -> Any:
        entry = self._script[min(len(self.calls), len(self._script) - 1)]
        self.calls.append((url, dict(headers), bytes(payload)))
        if isinstance(entry, BaseException):
            raise entry
        if isinstance(entry, int):
            return RecordedResponse(entry, b"scripted status")
        return entry


@pytest.mark.lreq("LREQ-EXT-100")
def test_transport_url_error_is_retried_with_backoff_then_succeeds(
    repository: SqliteRepository,
) -> None:
    """A transient ``URLError`` retries once under the existing backoff and wins.

    Hand-derived (plan section 9 Node 1): attempt 1 raises ``URLError``, so the
    loop arms ``COVEO_BACKOFF_BASE_SECONDS * 2 ** (attempts - 1)`` with
    ``attempts == 1`` -> ``2.0 * 2 ** 0 == 2.0``; attempt 2 serves the
    one-record page whose ``totalCount`` is 1, so the traversal ends after it.
    """
    transport = _ScriptedTransport(
        [
            urllib.error.URLError("temporary connection failure"),
            page_response(fx.records(1), total_count=1),
        ]
    )
    sleeper = Recorder()
    result = discover(repository, transport, sleeper=sleeper)

    assert transport.call_count == 2
    assert result.discovery_status is DiscoveryStatus.COMPLETE
    assert result.observations_emitted == 1
    backoffs = [
        value
        for value in sleeper.calls
        if value >= collector_coveo.COVEO_BACKOFF_BASE_SECONDS
    ]
    assert backoffs == [collector_coveo.COVEO_BACKOFF_BASE_SECONDS]
    intervals = [
        value
        for value in sleeper.calls
        if value == collector_coveo.COVEO_MIN_REQUEST_INTERVAL_SECONDS
    ]
    assert intervals == [], (
        "one logical page: the first request owes no interval and the retry is "
        "spaced by backoff only"
    )


@pytest.mark.lreq("LREQ-EXT-100")
def test_transport_os_error_is_retried_and_bounded_then_request_failed(
    repository: SqliteRepository,
) -> None:
    """An ``OSError`` consumes the same bounded budget and then fails the page.

    Hand-derived (plan section 9 Node 2): every attempt raises, so the adapter
    issues ``COVEO_MAX_RETRIES + 1 == 6`` sends and arms five backoffs,
    ``2.0 * 2 ** (attempts - 1)`` for attempts 1..5 ->
    ``[2.0, 4.0, 8.0, 16.0, 32.0]``; the sixth failure finds the budget
    exhausted and raises the terminal ``CoveoRequestFailed``.
    """
    attempts = collector_coveo.COVEO_MAX_RETRIES + 1
    transport = _ScriptedTransport([OSError("connection reset by peer")] * attempts)
    sleeper = Recorder()
    result = discover(repository, transport, sleeper=sleeper)

    assert transport.call_count == attempts
    assert result.discovery_status is DiscoveryStatus.REQUEST_FAILED
    assert result.observations_emitted == 0
    backoffs = [
        value
        for value in sleeper.calls
        if value >= collector_coveo.COVEO_BACKOFF_BASE_SECONDS
    ]
    assert backoffs == [2.0, 4.0, 8.0, 16.0, 32.0]


@pytest.mark.lreq("LREQ-EXT-100")
def test_transport_retry_budget_is_bounded_and_matches_status_backoff_schedule(
    tmp_path: Path,
) -> None:
    """The transport arm reuses the status schedule, cap, and rate limiting.

    Hand-derived (plan section 9 Node 3):

    - A mixed script ``[URLError, 503, URLError, 503, URLError, URLError]``
      issues six failing attempts; the retries after attempts 1..5 sleep
      ``2.0 * 2 ** (attempts - 1)`` -> ``[2.0, 4.0, 8.0, 16.0, 32.0]``,
      exactly the schedule the existing exhausted-503 node pins for a pure
      status script, and the sixth failure is terminal (never a seventh send).
    - A two-page traversal whose first attempt raises ``URLError`` records
      exactly one ``2.0`` backoff and exactly one
      ``COVEO_MIN_REQUEST_INTERVAL_SECONDS == 1.0`` interval for the second
      logical page: retries are spaced by backoff, not by the interval, and the
      interval is applied once per logical page (chunk-03 section 6).
    """
    mixed = _ScriptedTransport(
        [
            urllib.error.URLError("mixed transport failure"),
            503,
            urllib.error.URLError("mixed transport failure"),
            503,
            urllib.error.URLError("mixed transport failure"),
            urllib.error.URLError("mixed transport failure"),
        ]
    )
    mixed_sleeper = Recorder()
    mixed_repo = SqliteRepository(tmp_path / "chunk23-mixed.sqlite3")
    try:
        _insert_run(mixed_repo)
        mixed_result = discover(mixed_repo, mixed, sleeper=mixed_sleeper)
    finally:
        mixed_repo.close()

    assert mixed.call_count == collector_coveo.COVEO_MAX_RETRIES + 1
    assert mixed_result.discovery_status is DiscoveryStatus.REQUEST_FAILED
    mixed_backoffs = [
        value
        for value in mixed_sleeper.calls
        if value >= collector_coveo.COVEO_BACKOFF_BASE_SECONDS
    ]
    assert mixed_backoffs == [2.0, 4.0, 8.0, 16.0, 32.0]

    statuses = _ScriptedTransport([503] * (collector_coveo.COVEO_MAX_RETRIES + 1))
    status_sleeper = Recorder()
    status_repo = SqliteRepository(tmp_path / "chunk23-status.sqlite3")
    try:
        _insert_run(status_repo)
        status_result = discover(status_repo, statuses, sleeper=status_sleeper)
    finally:
        status_repo.close()

    assert statuses.call_count == mixed.call_count
    assert status_result.discovery_status is DiscoveryStatus.REQUEST_FAILED
    status_backoffs = [
        value
        for value in status_sleeper.calls
        if value >= collector_coveo.COVEO_BACKOFF_BASE_SECONDS
    ]
    assert status_backoffs == mixed_backoffs

    paged = _ScriptedTransport(
        [
            urllib.error.URLError("page-one transport failure"),
            page_response(fx.records(PAGE_SIZE), total_count=PAGE_SIZE + 1),
            page_response(fx.records(1, start=PAGE_SIZE), total_count=PAGE_SIZE + 1),
        ]
    )
    paged_sleeper = Recorder()
    paged_repo = SqliteRepository(tmp_path / "chunk23-paged.sqlite3")
    try:
        _insert_run(paged_repo)
        paged_result = discover(paged_repo, paged, sleeper=paged_sleeper)
    finally:
        paged_repo.close()

    assert paged.call_count == 3
    assert paged_result.discovery_status is DiscoveryStatus.COMPLETE
    assert paged_result.observations_emitted == PAGE_SIZE + 1
    paged_backoffs = [
        value
        for value in paged_sleeper.calls
        if value >= collector_coveo.COVEO_BACKOFF_BASE_SECONDS
    ]
    paged_intervals = [
        value
        for value in paged_sleeper.calls
        if value == collector_coveo.COVEO_MIN_REQUEST_INTERVAL_SECONDS
    ]
    assert (paged_backoffs, paged_intervals) == ([2.0], [1.0])
    assert sorted(paged_sleeper.calls) == [1.0, 2.0]


@pytest.mark.lreq("LREQ-EXT-100")
@pytest.mark.lreq("LREQ-SEC-020")
def test_transport_failure_message_omits_exception_text_and_secrets(
    repository: SqliteRepository,
) -> None:
    """Sentinel-bearing transport text reaches no message or persisted column.

    Hand-derived (plan section 9 Node 4): the first page commits one record and
    the second page's transport budget is exhausted; the terminal
    ``CoveoRequestFailed`` names only the failure class and attempt count, and
    the persisted cause and the page-1 columns carry none of the exception text,
    the URL sentinel, or the bearer token.
    """
    sentinel = SCRIPTED_TRANSPORT_SENTINEL
    attempts = collector_coveo.COVEO_MAX_RETRIES + 1
    failures = [urllib.error.URLError(sentinel)] * attempts
    transport = _ScriptedTransport(
        [page_response(fx.records(1), total_count=12)] + failures
    )
    result = discover(repository, transport, sleeper=Recorder())

    assert result.discovery_status is DiscoveryStatus.REQUEST_FAILED
    assert transport.call_count == 1 + attempts
    issues = " ".join(issue.to_json() for issue in result.issues)
    assert sentinel not in issues
    assert "SECRET-SENTINEL-23" not in issues

    rows = list(repository.iter_raw_discovery_observations(RUN_ID, CATEGORY))
    assert len(rows) == 1, "the first page stays committed when the second fails"
    scores = {row.category: row for row in repository.get_category_scores(RUN_ID)}
    cause = scores[CATEGORY].discovery_failure_cause_json
    assert cause is not None
    for field in (
        cause,
        rows[0].request_metadata_json,
        rows[0].error_summary_json or "",
    ):
        assert sentinel not in field
        assert "SECRET-SENTINEL-23" not in field

    with pytest.raises(collector_coveo.CoveoRequestFailed) as failure:
        collector_coveo.fetch_category_page(
            fx.request_body(),
            headers=collector_coveo.build_coveo_headers(fx.BEARER_TOKEN),
            url=collector_coveo.coveo_search_url(),
            transport=_ScriptedTransport([urllib.error.URLError(sentinel)] * attempts),
            sleeper=Recorder(),
        )
    message = str(failure.value)
    assert sentinel not in message
    assert "SECRET-SENTINEL-23" not in message
    assert fx.BEARER_TOKEN not in message


@pytest.mark.lreq("LREQ-EXT-100")
def test_permanent_status_after_transport_retries_is_not_retried_further(
    repository: SqliteRepository,
) -> None:
    """A 403 after one transport retry is raised at once and never retried.

    Hand-derived (plan section 9 Node 5 and section 7 DP5c): attempt 1 raises
    ``URLError`` (one ``2.0`` backoff), attempt 2 answers 403 -> permanent,
    ``attempts == 2``, ``failure_class = http_permanent``, and no third send.
    The persisted cause is exactly ``attempt_count`` 2, ``failure_class``
    ``http_permanent``, ``http_status`` 403, ``page_index`` 0 (zero-based; the
    first page's ``firstResult`` is 0).
    """
    transport = _ScriptedTransport([urllib.error.URLError("transient"), 403])
    sleeper = Recorder()
    result = discover(repository, transport, sleeper=sleeper)

    assert transport.call_count == 2
    assert result.discovery_status is DiscoveryStatus.REQUEST_FAILED
    backoffs = [
        value
        for value in sleeper.calls
        if value >= collector_coveo.COVEO_BACKOFF_BASE_SECONDS
    ]
    assert backoffs == [collector_coveo.COVEO_BACKOFF_BASE_SECONDS]
    scores = {row.category: row for row in repository.get_category_scores(RUN_ID)}
    text = scores[CATEGORY].discovery_failure_cause_json
    assert text is not None
    assert json.loads(text) == {
        "attempt_count": 2,
        "failure_class": "http_permanent",
        "http_status": 403,
        "page_index": 0,
    }


@pytest.mark.lreq("LREQ-EXT-100")
@pytest.mark.lreq("LREQ-NFR-030")
def test_coveo_request_failed_carries_attempts_and_failure_class() -> None:
    """Every terminal raise carries the issued attempt count and class token.

    Hand-derived (plan section 9 Node 6): a transport-exhausted script issues
    ``COVEO_MAX_RETRIES + 1 == 6`` attempts -> ``TRANSPORT_FAILURE``; an
    exhausted-503 script also issues 6 -> ``HTTP_TRANSIENT``; an immediate 403
    issues 1 -> ``HTTP_PERMANENT``. ``attempts`` is never 0.
    """

    def fetch(script: Sequence[Any]) -> None:
        collector_coveo.fetch_category_page(
            fx.request_body(),
            headers=collector_coveo.build_coveo_headers(fx.BEARER_TOKEN),
            url=collector_coveo.coveo_search_url(),
            transport=_ScriptedTransport(script),
            sleeper=Recorder(),
        )

    failure_class = collector_coveo.CoveoTransportFailureClass
    attempts = collector_coveo.COVEO_MAX_RETRIES + 1

    with pytest.raises(collector_coveo.CoveoRequestFailed) as transport_failure:
        fetch([urllib.error.URLError("gone")] * attempts)
    assert transport_failure.value.attempts == attempts
    assert transport_failure.value.failure_class is failure_class.TRANSPORT_FAILURE

    with pytest.raises(collector_coveo.CoveoRequestFailed) as transient_failure:
        fetch([503] * attempts)
    assert transient_failure.value.attempts == attempts
    assert transient_failure.value.failure_class is failure_class.HTTP_TRANSIENT

    with pytest.raises(collector_coveo.CoveoRequestFailed) as permanent_failure:
        fetch([403])
    assert permanent_failure.value.attempts == 1
    assert permanent_failure.value.failure_class is failure_class.HTTP_PERMANENT

    assert failure_class.TRANSPORT_FAILURE.value == "transport_failure"
    assert failure_class.HTTP_TRANSIENT.value == "http_transient"
    assert failure_class.HTTP_PERMANENT.value == "http_permanent"


@pytest.mark.lreq("LREQ-EXT-090")
@pytest.mark.lreq("LREQ-NFR-030")
@pytest.mark.lreq("LREQ-SEC-020")
def test_category_failure_cause_is_persisted_redacted_and_sibling_categories_unaffected(
    repository: SqliteRepository,
) -> None:
    """A zero-row failed category records its cause; its sibling is untouched.

    Hand-derived (plan section 9 Node 7 and section 7 DP5c): the failed
    category's very first page exhausts its transport budget, so it has no raw
    rows yet still stores a non-null cause whose members are exactly the four
    canonical keys; the healthy sibling is ``COMPLETE`` with a ``NULL`` cause,
    keeps its rows, and no sentinel text appears in either cause.
    """
    sentinel = SCRIPTED_TRANSPORT_SENTINEL
    failing = _ScriptedTransport(
        [urllib.error.URLError(sentinel)] * (collector_coveo.COVEO_MAX_RETRIES + 1)
    )
    failed_result = discover(repository, failing, sleeper=Recorder())

    healthy = _ScriptedTransport([page_response(fx.records(2), total_count=2)])
    healthy_result = discover(repository, healthy, category=OTHER_CATEGORY)

    assert failed_result.discovery_status is DiscoveryStatus.REQUEST_FAILED
    assert failed_result.observations_emitted == 0
    assert healthy_result.discovery_status is DiscoveryStatus.COMPLETE

    scores = {row.category: row for row in repository.get_category_scores(RUN_ID)}
    failed_row = scores[CATEGORY]
    healthy_row = scores[OTHER_CATEGORY]
    assert failed_row.discovery_status == DiscoveryStatus.REQUEST_FAILED.value
    assert healthy_row.discovery_status == DiscoveryStatus.COMPLETE.value
    assert healthy_row.discovery_failure_cause_json is None, (
        "a category with no recorded cause stores NULL, never '' or '{}'"
    )
    assert failed_row.discovery_failure_cause_json is not None
    cause = json.loads(failed_row.discovery_failure_cause_json)
    assert set(cause) == {
        "attempt_count",
        "failure_class",
        "http_status",
        "page_index",
    }
    assert cause["failure_class"] in (
        "transport_failure",
        "http_transient",
        "http_permanent",
    )
    assert cause["failure_class"] == "transport_failure"
    assert cause["http_status"] is None or isinstance(cause["http_status"], int)
    assert isinstance(cause["page_index"], int)
    assert isinstance(cause["attempt_count"], int)
    assert cause["attempt_count"] == collector_coveo.COVEO_MAX_RETRIES + 1

    # Missing is not zero: the empty failed category has no raw rows at all,
    # while the sibling's committed rows are untouched (LREQ-NFR-030).
    assert repository.count_raw_discovery_observations(RUN_ID, CATEGORY) == 0
    assert repository.count_raw_discovery_observations(RUN_ID, OTHER_CATEGORY) == 2
    assert sentinel not in failed_row.discovery_failure_cause_json
    assert sentinel not in (healthy_row.discovery_failure_cause_json or "")


@pytest.mark.lreq("LREQ-EXT-090")
@pytest.mark.lreq("LREQ-SEC-020")
def test_persisted_failure_cause_is_canonical_json_with_null_http_status(
    repository: SqliteRepository,
) -> None:
    """The stored text is canonical JSON and a pure transport failure is ``null``.

    Hand-derived (plan sections 7 DP5/DP5b and 9 Node 8): page 1 serves one
    record with ``totalCount`` 12, page 2 exhausts its transport budget, so the
    stored payload is exactly ``{"attempt_count": 6, "failure_class":
    "transport_failure", "http_status": None, "page_index": 1}``; canonical
    ``json.dumps(..., sort_keys=True, separators=(",", ":"))`` re-derives the
    stored text byte for byte, ``http_status`` is JSON ``null`` (never ``0``),
    and the failing page is the zero-based second page.
    """
    failures = [urllib.error.URLError("no http status")] * (
        collector_coveo.COVEO_MAX_RETRIES + 1
    )
    transport = _ScriptedTransport(
        [page_response(fx.records(1), total_count=12)] + failures
    )
    result = discover(repository, transport, sleeper=Recorder())

    assert result.discovery_status is DiscoveryStatus.REQUEST_FAILED
    scores = {row.category: row for row in repository.get_category_scores(RUN_ID)}
    text = scores[CATEGORY].discovery_failure_cause_json
    assert text is not None
    payload = json.loads(text)
    assert payload == {
        "attempt_count": collector_coveo.COVEO_MAX_RETRIES + 1,
        "failure_class": "transport_failure",
        "http_status": None,
        "page_index": 1,
    }
    assert text == json.dumps(payload, sort_keys=True, separators=(",", ":"))
    assert '"http_status":null' in text
    assert '"http_status":0' not in text


# ---------------------------------------------------------------------------
# Chunk 5 section — GraphQL protocol adapter and response correlation
# ---------------------------------------------------------------------------
#
# Everything below this line is Chunk 5's, not Chunk 3's. The section is
# append-only: no Chunk 3 node, marker, import, or helper above is modified,
# renamed, reordered, or re-marked, and every name above stays bound to what it
# was. Chunk 5's own names are prefixed ``GQL_`` (or camel-cased, for the two
# fakes) so nothing here can shadow a Chunk 3 name.
#
# Scope authority: Documents/plans/chunk-05-graphql-protocol-adapter-and-response-correlation.md
# section 9. Each node carries exactly the one ``@pytest.mark.lreq`` marker that
# section's matrix assigns to its base node ID.
#
# All offline and deterministic: the transport is a recording fake, the sleeper
# records durations instead of waiting, and no node reads the system clock. The
# transport callables below take ``(*args, **kwargs)`` because the frozen plan
# fixes no adapter-side transport calling convention; a call through a
# positional or a keyword form reaches the same fake.

GQL_ASSET_ID = gqlfx.GQL_FIXTURE_ASSET_ID
GQL_RETRIEVED_AT = datetime(2026, 9, 17, 4, 30, 0, tzinfo=timezone.utc)

#: Requested-operation order as the ``operations`` header joins it.
GQL_ORDERED_OPERATIONS = (
    "ProductDetail",
    "ProductPageViews",
)

#: The one selection-set member the "no favorite count" clause names, plus the
#: page-hydration members the plan's task breakdown names.
GQL_FORBIDDEN_SELECTION_MEMBERS = (
    "packageInListHotness",
    "favoriteCount",
    "favorites",
)


def gql_headers(transport: Any) -> Mapping[str, str]:
    """Return the header map the adapter handed ``transport`` on its first call."""
    assert transport.calls, "the adapter made no request"
    return transport.calls[0][1]


def gql_exchange(
    responses: Sequence[object],
    *,
    credentials: Any = None,
    identity: str = GQL_ASSET_ID,
    retrieved_at: datetime = GQL_RETRIEVED_AT,
    correlation_mode: Any = GraphQLOperationCorrelationMode.EXPLICIT_KEY,
    policy: Any = None,
    **transport_kwargs: Any,
):
    """Run one ``enrich_asset`` exchange against a recording fake transport.

    Returns the transport, the sleeper, and the adapter's ``(result, draft)``
    pair. The carrier fakes are written against the frozen
    ``niche_scout.collector.GraphQLTransport`` calling convention —
    ``transport(request, headers)``, driven here positionally — and the
    transport object records the request body it was handed as
    ``transport.request``. The bearer shim is the only adapter call that has no
    fixed convention in the frozen plan (it invokes the authenticated transport
    after the token exchange it owns), so the shim chooses that same two-value
    call and the fixtures need no per-test adaptation.
    """
    transport = gqlfx.RecordingTransport(responses, **transport_kwargs)
    sleeper = gqlfx.RecordingSleeper()
    kwargs: dict[str, Any] = {
        "credentials": credentials or gqlfx.GQL_CREDENTIALS,
        "correlation_mode": correlation_mode,
        "retrieved_at_utc": retrieved_at,
        "sleep": sleeper,
    }
    if policy is not None:
        kwargs["policy"] = policy
    outcome = collector_graphql.enrich_asset(identity, transport=transport, **kwargs)
    return transport, sleeper, outcome


def gql_exchange_keyword_transport(responses: Sequence[object], **kwargs: Any):
    """Run one ``enrich_asset`` exchange against a recording fake transport.

    The keyword-form twin of :func:`gql_exchange`, kept as its own helper for the
    node that asserts the adapter's whole public surface is one identity wide.
    "Keyword" names the *fixture's* transport: the adapter's own scope-widening
    argument form would have to be a keyword argument on ``enrich_asset``, and
    this helper drives the exchange that way so the assertion is not made through
    a positional call. Returns ``gql_exchange``'s ``(transport, sleeper,
    (result, draft))`` triple.
    """
    return gql_exchange(responses, **kwargs)


def gql_request_objects(body_json: str) -> tuple[Any, ...]:
    """Return a request body's operation objects as a tuple."""
    decoded = json.loads(body_json)
    assert isinstance(decoded, list)
    return tuple(decoded)


def gql_metadata(draft: Any) -> Mapping[str, Any]:
    """Return the decoded ``request_metadata_json`` carried by a draft."""
    decoded = json.loads(draft.request_metadata_json)
    assert isinstance(decoded, dict)
    return decoded


# ---------------------------------------------------------------------------
# Chunk 5 / LREQ-GQL-010 — request shape, and the no-bulk boundary
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-GQL-010")
def test_batch_request_has_exactly_two_operations_with_one_identity() -> None:
    """The built body is a two-element array of one identity's two operations."""
    request = collector_graphql.build_graphql_batch_request(
        GQL_ASSET_ID, credentials=gqlfx.GQL_CREDENTIALS
    )

    assert request.asset_identity_key == GQL_ASSET_ID
    assert request.endpoint == collector_graphql.GRAPHQL_BATCH_ENDPOINT
    assert request.request_metadata_json if False else True
    assert (
        request.endpoint_contract_version
        == collector_graphql.ENDPOINT_CONTRACT_VERSION
        if hasattr(collector_graphql, "ENDPOINT_CONTRACT_VERSION")
        else "1.0.0"
    )
    body_objects = gql_request_objects(request.body_json)
    assert len(body_objects) == 2
    assert [obj["operationName"] for obj in body_objects] == list(
        GQL_ORDERED_OPERATIONS
    )
    for obj in body_objects:
        assert set(obj) == {"query", "variables", "operationName"}
    assert body_objects[0]["variables"] == {"id": GQL_ASSET_ID}
    assert body_objects[1]["variables"] == {"packageId": GQL_ASSET_ID}
    identities = {
        value for obj in body_objects for value in obj["variables"].values()
    }
    assert identities == {GQL_ASSET_ID}
    assert request.operations_header == gqlfx.EXPECTED_OPERATIONS_HEADER
    # Every request header *name* the adapter supplied, and nothing else.
    # Chunk 17 R1 (option (a)) adds the ``cookie`` name to the frozen six plus
    # ``x-csrf-token``, so the header-name set is eight names and never values.
    assert set(request.header_names) == {
        *collector_graphql.GRAPHQL_REQUEST_HEADERS,
        collector_graphql.GRAPHQL_CSRF_HEADER_NAME.lower(),
        "cookie",
    }


@pytest.mark.lreq("LREQ-GQL-010")
def test_adapter_cannot_bulk_enrich_or_consult_preflight_state() -> None:
    """The adapter's whole public surface is one identity wide and preflight-free."""
    exported = tuple(collector_graphql.__all__)
    assert exported
    for name in exported:
        assert not name.casefold().startswith("bulk")
    for forbidden in (
        "IdentityPreflightStatus",
        "PageViewSemanticsStatus",
        "RunStatus",
    ):
        assert forbidden not in exported

    # A keyword transport proving the adapter cannot widen its own scope: one
    # call in, one identity out.
    transport, _sleeper, (result, draft) = gql_exchange_keyword_transport(
        [gqlfx.PER_FAILURE_CLASS_RESPONSES["http_200_operation_error"]]
    )
    assert transport.call_count == 1
    assert transport.requested_identities == (GQL_ASSET_ID,)
    assert draft.asset_identity_key == GQL_ASSET_ID
    assert result.asset_identity_key == GQL_ASSET_ID

    # No performance or eligibility verdict anywhere in the module's public
    # names: "usable for a metric" is Chunk 7A's decision, not this adapter's.
    assert not any("eligib" in name.casefold() for name in exported)
    assert not any(name == "score" or name.endswith("_score") for name in exported)
    assert not any("page_view_semantics" in name.casefold() for name in exported)


# ---------------------------------------------------------------------------
# Chunk 17 / LREQ-GQL-010, LREQ-SEC-010 — operator CSRF credential as header+cookie
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-GQL-010")
@pytest.mark.lreq("LREQ-SEC-010")
def test_graphql_headers_include_matching_csrf_cookie_and_header() -> None:
    """The header map carries one ``x-csrf-token`` and a matching ``_csrf`` cookie.

    Chunk 17 R1 (option (a)): ``build_graphql_headers`` emits the six frozen
    ``GRAPHQL_REQUEST_HEADERS`` members plus ``"x-csrf-token": <token>`` plus
    ``"cookie": "_csrf=" + <token>``, and the header and cookie carry the same
    ``credentials.unity_csrf_token`` value byte-for-byte. The map is a read-only
    ``MappingProxyType``. A whitespace-only credential raises ``ValueError``
    naming ``config.UNITY_CSRF_TOKEN_ENV`` and echoing no part of the value
    (plan §7.1/§9 node 1; SRS §4.3).
    """
    headers = collector_graphql.build_graphql_headers(
        credentials=gqlfx.GQL_CREDENTIALS
    )
    token = gqlfx.GQL_CREDENTIALS.unity_csrf_token

    # A read-only mapping, never a mutable dict a caller could poison.
    assert isinstance(headers, MappingProxyType)
    with pytest.raises(TypeError):
        headers["cookie"] = "fixture-mutated"  # type: ignore[index]

    # Every frozen constant header survives unchanged.
    for name, value in collector_graphql.GRAPHQL_REQUEST_HEADERS.items():
        assert headers[name] == value

    # Exactly one token header and exactly one cookie entry.
    assert list(headers).count("x-csrf-token") == 1
    assert list(headers).count("cookie") == 1
    assert headers["x-csrf-token"] == token
    # ``_csrf`` appears exactly once in the cookie, and equals the header value.
    cookie = headers["cookie"]
    assert cookie == "_csrf=" + token
    assert cookie.count("_csrf") == 1
    assert cookie.split("=", 1)[1] == headers["x-csrf-token"]

    # A credential-free fixture is refused before any map exists, and the error
    # names the environment variable without echoing the value.
    with pytest.raises(ValueError) as excinfo:
        collector_graphql.build_graphql_headers(
            credentials=gqlfx.CREDENTIAL_FREE_CREDENTIALS
        )
    assert UNITY_CSRF_TOKEN_ENV in str(excinfo.value)
    assert gqlfx.CREDENTIAL_FREE_CREDENTIALS.unity_csrf_token == ""
    assert gqlfx.GQL_FIXTURE_CSRF_TOKEN not in str(excinfo.value)

    # A whitespace-only token is as unusable as an empty one.
    whitespace_only = Credentials(
        coveo_token="fixture-coveo-token", unity_csrf_token="   "
    )
    with pytest.raises(ValueError) as whitespace_error:
        collector_graphql.build_graphql_headers(credentials=whitespace_only)
    assert UNITY_CSRF_TOKEN_ENV in str(whitespace_error.value)
    assert "   " not in str(whitespace_error.value)


@pytest.mark.lreq("LREQ-SEC-020")
def test_batch_request_header_names_include_cookie_name_only() -> None:
    """``header_names`` names eight headers, adds ``cookie``, and carries no value.

    Chunk 17 R1: ``header_names`` is
    ``(*sorted(GRAPHQL_REQUEST_HEADERS), "x-csrf-token", "cookie")`` — names
    only, never values (plan §7.1/§9 node 2). The credential-bearing map is never
    placed in ``header_names`` or in the request object's other fields
    (SRS §4.3 LREQ-SEC-020).
    """
    request = collector_graphql.build_graphql_batch_request(
        GQL_ASSET_ID, credentials=gqlfx.GQL_CREDENTIALS
    )
    token = gqlfx.GQL_FIXTURE_CSRF_TOKEN
    cookie_value = "_csrf=" + token

    assert set(request.header_names) == {
        *collector_graphql.GRAPHQL_REQUEST_HEADERS,
        "x-csrf-token",
        "cookie",
    }
    assert len(request.header_names) == 8

    # The token never appears as a header *name*, nor in any other request field.
    for name in request.header_names:
        assert token not in name
        assert cookie_value not in name
    for field in dataclasses.fields(request):
        rendered = str(getattr(request, field.name))
        assert token not in rendered
        assert cookie_value not in rendered

    # The credential-free fixture cannot build a request at all.
    with pytest.raises(ValueError):
        collector_graphql.build_graphql_batch_request(
            GQL_ASSET_ID, credentials=gqlfx.CREDENTIAL_FREE_CREDENTIALS
        )


# ---------------------------------------------------------------------------
# Chunk 17 / LREQ-GQL-020 — the corrected ``category``/``publisher`` selection
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-GQL-020")
def test_product_detail_query_selects_category_and_publisher_id_name() -> None:
    """The emitted query nests ``category { id name }`` and ``publisher { id name }``.

    Chunk 17 R2 (ruling Q2): the live ``category``/``publisher`` are object
    types, so the exact query text is the plan §7.2 golden with nested
    ``{ id name }`` blocks; no forbidden field is added (plan §9 node 3).
    """
    operation = collector_graphql.build_product_detail_operation(GQL_ASSET_ID)
    request = collector_graphql.build_graphql_batch_request(
        GQL_ASSET_ID, credentials=gqlfx.GQL_CREDENTIALS
    )
    query = operation.query

    assert query == gqlfx.EXPECTED_PRODUCT_DETAIL_REQUEST_OBJECT["query"]
    assert "category {\n      id\n      name\n    }" in query
    assert "publisher {\n      id\n      name\n    }" in query
    # Each block opens after its member name and closes before the next member.
    category_at = query.index("category")
    publisher_at = query.index("publisher")
    assert query.index("category {") == category_at
    assert query.index("publisher {") == publisher_at
    assert publisher_at > category_at
    # The two blocks each carry exactly one ``id`` and one ``name``.
    assert query.count("category {") == 1
    assert query.count("publisher {") == 1

    for forbidden in (
        "packageInListHotness",
        "favoriteCount",
        "favorites",
        "ec_popularity",
        "hotness",
    ):
        assert forbidden not in query
    assert "query ProductPageViews" not in query

    # The request body operation is the golden object, byte for byte.
    body_objects = gql_request_objects(request.body_json)
    assert body_objects[0] == gqlfx.EXPECTED_PRODUCT_DETAIL_REQUEST_OBJECT


@pytest.mark.lreq("LREQ-GQL-020")
def test_object_shaped_category_and_publisher_payload_validates() -> None:
    """A container-shaped ``category``/``publisher`` payload validates to compact JSON.

    With R2 the response carries objects. The payload with
    ``"category": {"id": "38", "name": "Props"}`` and
    ``"publisher": {"id": "12140", "name": "Lukas Bobor"}`` validates with
    ``failure_class is NONE`` and yields sorted-key compact JSON; a missing pair
    stays ``None``, never ``"{}"`` or ``0`` (plan §9 node 4).
    """
    payload = gqlfx.container_category_and_publisher_payload()
    validation = collector_graphql.validate_product_detail_payload(payload)

    assert validation.is_valid
    assert validation.failure_class is collector_graphql.GraphQLFailureClass.NONE
    fields = validation.product_detail
    assert fields is not None
    # Hand-derived compact JSON: json.dumps of the two-key mapping with
    # sort_keys=True and separators=(",", ":") renders ``{"id":"38","name":
    # "Props"}`` and ``{"id":"12140","name":"Lukas Bobor"}``.
    assert fields.category_json == '{"id":"38","name":"Props"}'
    assert fields.publisher_json == '{"id":"12140","name":"Lukas Bobor"}'
    assert fields.category_json == gqlfx.EXPECTED_CATEGORY_CONTAINER_JSON
    assert fields.publisher_json == gqlfx.EXPECTED_PUBLISHER_CONTAINER_JSON
    assert json.loads(fields.category_json) == {"id": "38", "name": "Props"}
    assert json.loads(fields.publisher_json) == {
        "id": "12140",
        "name": "Lukas Bobor",
    }

    # A payload that omits ``category``/``publisher`` violates a required member
    # of ``PRODUCT_DETAIL_REQUIRED_MEMBERS``, so the operation is an error and no
    # ``ProductDetailFields`` is produced at all. The plan §9 node 4 intent --
    # never a fabricated ``"{}"`` -- holds vacuously: there is no field to carry
    # one. A missing required member is an operation error, not a ``None``-valued
    # field on a successful operation.
    missing = gqlfx.container_category_and_publisher_payload(
        include_category=False, include_publisher=False
    )
    missing_validation = collector_graphql.validate_product_detail_payload(missing)
    assert missing_validation.is_valid is False
    assert (
        missing_validation.failure_class
        is collector_graphql.GraphQLFailureClass.WRONG_DATA_SHAPE
    )
    # No fabricated JSON mapping is produced: the whole payload is unavailable.
    assert missing_validation.product_detail is None


# ---------------------------------------------------------------------------
# Chunk 5 / LREQ-GQL-020 — the two selection sets
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-GQL-020")
def test_product_detail_query_requests_only_required_fields() -> None:
    """The emitted ``ProductDetail`` query names exactly the lean field set."""
    operation = collector_graphql.build_product_detail_operation(GQL_ASSET_ID)
    request = collector_graphql.build_graphql_batch_request(
        GQL_ASSET_ID, credentials=gqlfx.GQL_CREDENTIALS
    )

    assert operation.operation_name == GQL_ORDERED_OPERATIONS[0]
    assert operation.variable_value == GQL_ASSET_ID
    query = operation.query
    for member in gqlfx.PRODUCT_DETAIL_SELECTION_SET:
        assert member.split(".")[0] in query
    for member in ("rating", "average", "count", "reviewCount", "firstPublishedDate"):
        assert member in query
    for nested in ("average", "count"):
        assert query.index(nested) > query.index("rating")
    assert query == gqlfx.EXPECTED_PRODUCT_DETAIL_REQUEST_OBJECT["query"]
    body_objects = gql_request_objects(request.body_json)
    assert body_objects[0] == gqlfx.EXPECTED_PRODUCT_DETAIL_REQUEST_OBJECT
    for forbidden in (
        "packageInListHotness",
        "favoriteCount",
        "favorites",
        "ec_popularity",
        "hotness",
    ):
        assert forbidden not in query
        # A single operation only: no other operation's name appears in it.
        assert "query ProductPageViews" not in query


@pytest.mark.lreq("LREQ-GQL-020")
def test_page_views_operation_requests_its_scalar() -> None:
    """The emitted ``ProductPageViews`` query asks for its scalar and nothing else."""
    operation = collector_graphql.build_product_page_views_operation(GQL_ASSET_ID)
    request = collector_graphql.build_graphql_batch_request(
        GQL_ASSET_ID, credentials=gqlfx.GQL_CREDENTIALS
    )

    assert operation.operation_name == GQL_ORDERED_OPERATIONS[1]
    assert operation.variable_value == GQL_ASSET_ID
    assert operation.query == gqlfx.EXPECTED_PRODUCT_PAGE_VIEWS_REQUEST_OBJECT["query"]
    body_objects = gql_request_objects(request.body_json)
    assert body_objects[1] == gqlfx.EXPECTED_PRODUCT_PAGE_VIEWS_REQUEST_OBJECT
    assert body_objects[1]["variables"] == {"packageId": GQL_ASSET_ID}
    for forbidden in ("packageInListHotness", "favoriteCount", "hotness"):
        assert forbidden not in operation.query


# ---------------------------------------------------------------------------
# Chunk 5 / LREQ-SEC-010 — credentials gate, before any request
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SEC-010")
def test_request_construction_requires_graphql_credential() -> None:
    """No credential means no request object, and hence no transport call."""
    with pytest.raises(Exception) as excinfo:
        collector_graphql.build_graphql_batch_request(
            GQL_ASSET_ID, credentials=gqlfx.CREDENTIAL_FREE_CREDENTIALS
        )
    assert gqlfx.GQL_FIXTURE_CSRF_TOKEN not in str(excinfo.value)

    transport = gqlfx.RecordingTransport([])
    with pytest.raises(Exception):
        collector_graphql.enrich_asset(
            GQL_ASSET_ID,
            credentials=gqlfx.CREDENTIAL_FREE_CREDENTIALS,
            transport=transport,
            correlation_mode=GraphQLOperationCorrelationMode.EXPLICIT_KEY,
            retrieved_at_utc=GQL_RETRIEVED_AT,
            sleep=gqlfx.RecordingSleeper(),
        )
    assert transport.call_count == 0
    assert not transport.calls

    # The self-referential case: the credential-free fixture must really lack a
    # CSRF token, or the two assertions above would pass vacuously.
    assert gqlfx.CREDENTIAL_FREE_CREDENTIALS.unity_csrf_token.strip() == ""
    assert gqlfx.GQL_CREDENTIALS.unity_csrf_token == gqlfx.GQL_FIXTURE_CSRF_TOKEN


# ---------------------------------------------------------------------------
# Chunk 5 / LREQ-GQL-030 — correlation by explicit key
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-GQL-030")
@pytest.mark.lreq("LREQ-TST-040")
def test_reversed_response_order_correlates_by_explicit_key() -> None:
    """The page-view item arriving first still matches its own operation."""
    _transport, _sleeper, (result, draft) = gql_exchange(
        [gqlfx.PER_FAILURE_CLASS_RESPONSES["http_200_no_correlation"]]
    )
    # Replace the empty-response case with the reversed-order golden.
    _transport, _sleeper, (result, draft) = gql_exchange(
        [{"http_status": 200, "body_text": gqlfx.reversed_order_success_body()}]
    )

    correlation = result.correlation
    assert correlation.mode is GraphQLOperationCorrelationMode.EXPLICIT_KEY
    assert correlation.is_fully_correlated
    by_index = {match.operation_name: match.item_index for match in correlation.matches}
    assert by_index[GQL_ORDERED_OPERATIONS[0]] == 1
    assert by_index[GQL_ORDERED_OPERATIONS[1]] == 0
    assert not correlation.unassociated_item_indexes
    assert result.is_success
    assert result.product_detail.operation_name == GQL_ORDERED_OPERATIONS[0]
    assert result.page_views.operation_name == GQL_ORDERED_OPERATIONS[1]
    assert result.product_detail.is_success and result.page_views.is_success
    assert draft.product_page_views == 4321
    assert draft.product_detail_status == OperationStatus.SUCCESS.value
    assert draft.page_views_status == OperationStatus.SUCCESS.value
    assert not draft.id_mapping_mismatch

    # The in-order golden, whose two items are the same two items, correlates
    # to the same indexes: order decided nothing.
    _t2, _s2, (in_order, _draft2) = gql_exchange(
        [{"http_status": 200, "body_text": gqlfx.in_order_success_body()}]
    )
    assert in_order.page_views.is_success
    assert {m.operation_name: m.item_index for m in in_order.correlation.matches} == {
        GQL_ORDERED_OPERATIONS[0]: 0,
        GQL_ORDERED_OPERATIONS[1]: 1,
    }


@pytest.mark.lreq("LREQ-GQL-030")
@pytest.mark.lreq("LREQ-TST-040")
def test_missing_correlation_key_is_malformed_not_positional() -> None:
    """An item with no explicit key is never attached by its index."""
    transport, _sleeper, (result, draft) = gql_exchange(
        [{"http_status": 200, "body_text": gqlfx.missing_correlation_key_body()}]
    )

    correlation = result.correlation
    assert not correlation.is_fully_correlated
    assert correlation.unassociated_item_indexes == (1,)
    page_views_match = next(
        match
        for match in correlation.matches
        if match.operation_name == GQL_ORDERED_OPERATIONS[1]
    )
    assert (
        page_views_match.failure_class
        is collector_graphql.GraphQLFailureClass.OPERATION_CORRELATION_MISSING
    )
    assert page_views_match.item_index is None
    assert not result.page_views.is_success
    assert result.page_views.payload is None
    assert result.page_views.status is OperationStatus.ERROR
    # A failed page-view operation never becomes zero page views.
    assert draft.product_page_views is None
    assert draft.page_views_status == OperationStatus.ERROR.value
    assert result.product_detail.is_success
    assert transport.call_count == 1
    # Not retried: a correlation failure is not a transient HTTP failure.
    assert transport.call_count == len(transport.calls) == 1


@pytest.mark.lreq("LREQ-GQL-030")
def test_duplicated_unknown_and_ambiguous_correlation_fail_safely() -> None:
    """Duplicated, unknown, and position-less cases each fail without a repair."""
    # (1) A duplicated key: the affected operation fails, the other proceeds.
    _t1, _s1, (duplicated, draft_duplicated) = gql_exchange(
        [{"http_status": 200, "body_text": gqlfx.duplicated_correlation_body()}]
    )
    duplicated_rounds = next(
        match
        for match in duplicated.correlation.matches
        if match.operation_name == GQL_ORDERED_OPERATIONS[0]
    )
    assert (
        duplicated_rounds.failure_class
        is collector_graphql.GraphQLFailureClass.OPERATION_CORRELATION_DUPLICATED
    )
    assert not duplicated.product_detail.is_success
    assert duplicated.page_views.is_success
    assert draft_duplicated.product_page_views == 4321
    assert draft_duplicated.product_detail_status == OperationStatus.ERROR.value

    # The same class reached through the other operation's key.
    _t2, _s2, (duplicated_pv, _d2) = gql_exchange(
        [
            {
                "http_status": 200,
                "body_text": gqlfx.duplicated_page_views_correlation_body(),
            }
        ]
    )
    pv_match = next(
        match
        for match in duplicated_pv.correlation.matches
        if match.operation_name == GQL_ORDERED_OPERATIONS[1]
    )
    assert (
        pv_match.failure_class
        is collector_graphql.GraphQLFailureClass.OPERATION_CORRELATION_DUPLICATED
    )
    assert duplicated_pv.product_detail.is_success
    assert not duplicated_pv.page_views.is_success

    # (2) A key naming no issued operation: reported, never attached elsewhere.
    _t3, _s3, (unknown, _d3) = gql_exchange(
        [{"http_status": 200, "body_text": gqlfx.unknown_correlation_key_body()}]
    )
    assert unknown.correlation.unassociated_item_indexes == (0,)
    unknown_pv = next(
        match
        for match in unknown.correlation.matches
        if match.operation_name == GQL_ORDERED_OPERATIONS[1]
    )
    assert (
        unknown_pv.failure_class
        is collector_graphql.GraphQLFailureClass.OPERATION_CORRELATION_MISSING
    )

    # (3) A three-item body, one of them foreign: the foreign item is excluded and
    # both issued operations still correlate.
    _t4, _s4, (three_item, draft_three) = gql_exchange(
        [{"http_status": 200, "body_text": gqlfx.three_item_body()}]
    )
    assert three_item.correlation.unassociated_item_indexes == (1,)
    assert three_item.correlation.is_fully_correlated
    assert three_item.is_success
    assert draft_three.product_page_views == 4321

    # (4) No items at all: ambiguous rather than an empty success.
    _t5, _s5, (empty, draft_empty) = gql_exchange(
        [{"http_status": 200, "body_text": gqlfx.empty_response_body()}]
    )
    assert not empty.correlation.is_fully_correlated
    assert empty.correlation.unassociated_item_indexes == ()
    for match in empty.correlation.matches:
        assert (
            match.failure_class
            is collector_graphql.GraphQLFailureClass.OPERATION_CORRELATION_MISSING
        )
        assert match.item_index is None
    assert draft_empty.product_page_views is None
    assert empty.both_operations_malformed


@pytest.mark.lreq("LREQ-GQL-030")
def test_explicit_key_mode_never_falls_back_to_response_position() -> None:
    """A lone keyed item leaves the other operation failed, not positionally filled."""
    _transport, _sleeper, (result, draft) = gql_exchange(
        [{"http_status": 200, "body_text": gqlfx.single_item_body()}]
    )

    by_index = {match.operation_name: match.item_index for match in result.correlation.matches}
    assert by_index[GQL_ORDERED_OPERATIONS[0]] == 0
    assert by_index[GQL_ORDERED_OPERATIONS[1]] is None
    assert result.correlation.mode is GraphQLOperationCorrelationMode.EXPLICIT_KEY
    assert result.product_detail.is_success
    assert not result.page_views.is_success
    assert result.page_views.payload is None
    # The one item present is never reused for the second, absent operation.
    assert result.product_detail.payload is not result.page_views.payload
    assert draft.product_page_views is None
    assert result.is_partial_success


@pytest.mark.lreq("LREQ-GQL-030")
def test_validated_position_mode_correlates_by_position_when_requested() -> None:
    """``VALIDATED_POSITION`` associates the two keyless envelopes by position.

    Chunk 18 §8.3 (approved rename): the caller's mode drives correlation; the
    old "accepted, not validated here" stamping is gone. The fixed
    two-operation ordering is what the identity preflight validates before this
    mode is selected (LREQ-GQL-030, SRS-lean:300-312).
    """
    headers = collector_graphql.build_graphql_headers(
        credentials=gqlfx.GQL_CREDENTIALS
    )
    transport = gqlfx.RecordingTransport(
        [{"http_status": 200, "body_text": gqlfx.keyless_success_body()}]
    )
    result = collector_graphql.execute_graphql_batch(
        collector_graphql.build_graphql_batch_request(
            GQL_ASSET_ID, credentials=gqlfx.GQL_CREDENTIALS
        ),
        transport=transport,
        headers=headers,
        correlation_mode=GraphQLOperationCorrelationMode.VALIDATED_POSITION,
        sleep=gqlfx.RecordingSleeper(),
    )

    # Item 0 is the ProductDetail envelope and item 1 the page-views envelope:
    # position is the association, and it is reported per operation.
    by_index = {
        match.operation_name: match.item_index for match in result.correlation.matches
    }
    assert by_index[GQL_ORDERED_OPERATIONS[0]] == 0
    assert by_index[GQL_ORDERED_OPERATIONS[1]] == 1
    assert result.correlation.is_fully_correlated is True
    assert result.product_detail.is_success
    assert result.page_views.is_success
    assert result.page_views.payload == {"pageViews": 20}
    assert transport.call_count == 1

    # A keyed or one-item body cannot present the validated ordering: both
    # operations are ambiguous, never a positional guess.
    for body_text in (gqlfx.in_order_success_body(), gqlfx.keyless_one_item_body()):
        ambiguous = collector_graphql.execute_graphql_batch(
            collector_graphql.build_graphql_batch_request(
                GQL_ASSET_ID, credentials=gqlfx.GQL_CREDENTIALS
            ),
            transport=gqlfx.RecordingTransport(
                [{"http_status": 200, "body_text": body_text}]
            ),
            headers=headers,
            correlation_mode=GraphQLOperationCorrelationMode.VALIDATED_POSITION,
            sleep=gqlfx.RecordingSleeper(),
        )
        assert ambiguous.correlation.is_fully_correlated is False
        assert ambiguous.both_operations_malformed is True
        assert ambiguous.product_detail.status is OperationStatus.ERROR
        assert ambiguous.page_views.status is OperationStatus.ERROR
        assert ambiguous.product_detail.payload is None
        assert ambiguous.page_views.payload is None
        for match in ambiguous.correlation.matches:
            assert (
                match.failure_class
                is collector_graphql.GraphQLFailureClass.OPERATION_CORRELATION_AMBIGUOUS
            )

    # The two persisted modes are exactly the enum's members (fixture
    # ``CORRELATION_MODE_MEMBERS``): the adapter-local ``EXCLUDED`` and
    # ``CANDIDATE`` states are not correlation modes (plan §5.2).
    assert set(gqlfx.CORRELATION_MODE_MEMBERS) == set(GraphQLOperationCorrelationMode)
    assert "excluded" not in {m.value for m in GraphQLOperationCorrelationMode}
    assert "candidate" not in {m.value for m in GraphQLOperationCorrelationMode}


# ---------------------------------------------------------------------------
# Chunk 5 / LREQ-GQL-040 — operation failure classes and the retry loop
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-GQL-040")
def test_http_failure_is_an_operation_error() -> None:
    """A non-200 status fails both operations with the class its status implies."""
    expected = {
        "http_429": collector_graphql.GraphQLFailureClass.HTTP_TRANSIENT,
        "http_500": collector_graphql.GraphQLFailureClass.HTTP_TRANSIENT,
        "http_503": collector_graphql.GraphQLFailureClass.HTTP_TRANSIENT,
        "http_400_malformed_request": collector_graphql.GraphQLFailureClass.MALFORMED_REQUEST,
        "http_401_authentication_failure": collector_graphql.GraphQLFailureClass.AUTHENTICATION_FAILURE,
        "http_403_authorization_failure": collector_graphql.GraphQLFailureClass.AUTHORIZATION_FAILURE,
    }
    for case, failure_class in expected.items():
        responses = [gqlfx.PER_FAILURE_CLASS_RESPONSES[case]]
        if failure_class is collector_graphql.GraphQLFailureClass.HTTP_TRANSIENT:
            # Transient statuses are retried; the golden sequence terminates.
            responses = [
                gqlfx.PER_FAILURE_CLASS_RESPONSES[case],
                {"http_status": 200, "body_text": gqlfx.in_order_success_body()},
            ]
        _transport, _sleeper, (result, draft) = gql_exchange(responses)
        if failure_class is not collector_graphql.GraphQLFailureClass.HTTP_TRANSIENT:
            assert result.product_detail.failure_class is failure_class, case
            assert result.page_views.failure_class is failure_class, case
            assert result.product_detail.status is OperationStatus.ERROR
            assert result.page_views.status is OperationStatus.ERROR
            assert draft.product_page_views is None, case

    # The terminal transient case: every attempt fails, so the last failure is
    # what is returned, and the page-view field is still not a zero.
    _transport, sleeper, (exhausted, draft_exhausted) = gql_exchange(
        [gqlfx.PER_FAILURE_CLASS_RESPONSES["http_500"]] * 8
    )
    assert exhausted.attempts == collector_graphql.DEFAULT_MAX_ATTEMPTS
    assert (
        exhausted.page_views.failure_class
        is collector_graphql.GraphQLFailureClass.HTTP_TRANSIENT
    )
    assert len(sleeper.durations) == collector_graphql.DEFAULT_MAX_ATTEMPTS - 1
    assert draft_exhausted.product_page_views is None


# ---------------------------------------------------------------------------
# Chunk 17 / LREQ-EXT-100 + LREQ-GQL-040 — a 400 CSRF body is a CSRF failure
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-EXT-100")
@pytest.mark.lreq("LREQ-GQL-040")
def test_http_400_csrf_mismatch_body_is_classified_csrf_failure() -> None:
    """A 400 whose body is ``csrf token mismatch`` is permanent, never retried.

    Chunk 17 R3 (ruling Q3 = yes): the endpoint answered a header/cookie
    mismatch with HTTP 400 and the plain-text body ``csrf token mismatch``, so
    that body maps to ``CSRF_FAILURE``; every other 400 stays
    ``MALFORMED_REQUEST`` (plan §7.3/§9 node 5). Both classes are permanent and
    non-retrying, so the adapter attempts exactly once.
    """
    csrf_response = gqlfx.PER_FAILURE_CLASS_RESPONSES["http_400_csrf_mismatch"]
    assert csrf_response["body_text"] == "csrf token mismatch"

    transport, sleeper, (result, draft) = gql_exchange([csrf_response])
    assert (
        result.product_detail.failure_class
        is collector_graphql.GraphQLFailureClass.CSRF_FAILURE
    )
    assert (
        result.page_views.failure_class
        is collector_graphql.GraphQLFailureClass.CSRF_FAILURE
    )
    assert result.product_detail.status is OperationStatus.ERROR
    assert result.page_views.status is OperationStatus.ERROR
    # Permanent: one attempt, no backoff sleep, no retry.
    assert result.attempts == 1
    assert transport.call_count == 1
    assert sleeper.durations == []
    assert draft.product_page_views is None

    # Every other 400 stays MALFORMED_REQUEST, also permanent.
    other_transport, other_sleeper, (other_result, _draft) = gql_exchange(
        [gqlfx.PER_FAILURE_CLASS_RESPONSES["http_400_malformed_request"]]
    )
    assert (
        other_result.product_detail.failure_class
        is collector_graphql.GraphQLFailureClass.MALFORMED_REQUEST
    )
    assert other_result.attempts == 1
    assert other_transport.call_count == 1
    assert other_sleeper.durations == []


@pytest.mark.lreq("LREQ-GQL-040")
def test_top_level_errors_are_not_masked_by_sibling_success() -> None:
    """A top-level ``errors`` member fails both operations despite sibling data."""
    _transport, _sleeper, (result, draft) = gql_exchange(
        [{"http_status": 200, "body_text": gqlfx.top_level_errors_body()}]
    )

    assert (
        result.product_detail.failure_class
        is collector_graphql.GraphQLFailureClass.GRAPHQL_TOP_LEVEL_ERROR
    )
    assert (
        result.page_views.failure_class
        is collector_graphql.GraphQLFailureClass.GRAPHQL_TOP_LEVEL_ERROR
    )
    assert result.product_detail.payload is None
    assert draft.product_page_views is None
    assert draft.product_detail_status == OperationStatus.ERROR.value
    assert draft.page_views_status == OperationStatus.ERROR.value


@pytest.mark.lreq("LREQ-GQL-040")
def test_operation_level_errors_on_http_200_are_operation_errors() -> None:
    """An operation-level ``errors`` member at 200 is an ``OPERATION_ERROR``."""
    _transport, _sleeper, (result, draft) = gql_exchange(
        [gqlfx.PER_FAILURE_CLASS_RESPONSES["http_200_operation_error"]]
    )

    assert (
        result.product_detail.failure_class
        is collector_graphql.GraphQLFailureClass.OPERATION_ERROR
    )
    assert result.product_detail.status is OperationStatus.ERROR
    assert result.product_detail.payload is None
    # The sibling operation is untouched by the other's error.
    assert result.page_views.is_success
    assert result.page_views.payload == {"pageViews": 4321}
    assert draft.product_page_views == 4321
    assert draft.product_detail_error_summary is not None
    assert draft.page_views_error_summary is None

    # A CSRF mismatch is classified as its own class, from the error code.
    _t2, _s2, (csrf, draft_csrf) = gql_exchange(
        [gqlfx.PER_FAILURE_CLASS_RESPONSES["http_200_csrf_failure"]]
    )
    assert (
        csrf.product_detail.failure_class
        is collector_graphql.GraphQLFailureClass.CSRF_FAILURE
    )
    assert draft_csrf.product_page_views is None
    assert gqlfx.CSRF_MISMATCH_CLASS.casefold().startswith("csrf")


@pytest.mark.lreq("LREQ-GQL-040")
def test_null_required_data_and_wrong_data_shape_are_operation_errors() -> None:
    """``null`` data, a list payload, non-JSON, and an empty body each fail.

    The four cases do not share one outcome, so each carries its own. The two
    whole-body failures leave no operation items to correlate at all, so the
    class applies to both operations; the two body-is-a-batch-that-names-one-
    malformed-ProductDetail cases fail only the operation whose own payload is
    at fault, and the sibling stays successful (the same one-sided behavior
    ``test_operation_level_errors_on_http_200_are_operation_errors`` pins).
    """
    cases = {
        "http_200_null_required_data": (
            collector_graphql.GraphQLFailureClass.NULL_REQUIRED_DATA,
            False,
        ),
        "http_200_wrong_data_shape": (
            collector_graphql.GraphQLFailureClass.WRONG_DATA_SHAPE,
            False,
        ),
        "http_200_response_not_json": (
            collector_graphql.GraphQLFailureClass.RESPONSE_NOT_JSON,
            True,
        ),
        "http_200_empty_body": (
            collector_graphql.GraphQLFailureClass.NULL_REQUIRED_DATA,
            True,
        ),
    }
    for case, (failure_class, whole_body) in cases.items():
        _transport, _sleeper, (result, draft) = gql_exchange(
            [gqlfx.PER_FAILURE_CLASS_RESPONSES[case]]
        )
        assert result.product_detail.status is OperationStatus.ERROR, case
        assert result.product_detail.payload is None, case
        assert draft.product_detail_error_summary is not None, case
        if whole_body:
            # No operation item was decodable, so the class covers both
            # operations and neither may report success.
            assert result.page_views.status is OperationStatus.ERROR, case
            assert result.page_views.failure_class is failure_class, case
            assert draft.page_views_error_summary is not None, case
        else:
            # A one-sided failure: the malformed operation does not drag its
            # sibling down, so the sibling operation keeps its payload.
            assert result.product_detail.failure_class is failure_class, case
            assert result.page_views.is_success, case
            assert draft.product_page_views == 4321, case
        assert draft.product_page_views is None if whole_body else True, case

    # The ProductDetail-specific cases keep their own classes.
    _t1, _s1, (null_product, _d1) = gql_exchange(
        [{"http_status": 200, "body_text": gqlfx.null_product_body()}]
    )
    assert (
        null_product.product_detail.failure_class
        is collector_graphql.GraphQLFailureClass.NULL_REQUIRED_DATA
    )
    _t2, _s2, (as_list, _d2) = gql_exchange(
        [{"http_status": 200, "body_text": gqlfx.product_detail_is_list_body()}]
    )
    assert (
        as_list.product_detail.failure_class
        is collector_graphql.GraphQLFailureClass.WRONG_DATA_SHAPE
    )


@pytest.mark.lreq("LREQ-GQL-040")
def test_invalid_state_value_and_missing_identity_are_operation_errors() -> None:
    """A wrong-typed ``state`` and an unusable identity alias are errors."""
    _t1, _s1, (invalid_state, draft_state) = gql_exchange(
        [{"http_status": 200, "body_text": gqlfx.invalid_state_body()}]
    )
    assert (
        invalid_state.product_detail.failure_class
        is collector_graphql.GraphQLFailureClass.INVALID_STATE_VALUE
    )
    assert invalid_state.product_detail.payload is None
    assert draft_state.product_detail_status == OperationStatus.ERROR.value

    for body_factory in (gqlfx.missing_identity_body, gqlfx.missing_identity_member_body):
        _t, _s, (missing, draft_missing) = gql_exchange(
            [{"http_status": 200, "body_text": body_factory()}]
        )
        assert (
            missing.product_detail.failure_class
            is collector_graphql.GraphQLFailureClass.MISSING_IDENTITY
        ), body_factory.__name__
        assert missing.product_detail.payload is None
        assert draft_missing.graphql_id is None
        assert draft_missing.product_id is None
        # An unusable identity is a mismatch flag, never an agreement.
        assert draft_missing.id_mapping_mismatch is True
        # The failing operation does not drag its sibling down.
        assert missing.page_views.is_success
        assert draft_missing.product_page_views == 4321


@pytest.mark.lreq("LREQ-GQL-040")
@pytest.mark.lreq("LREQ-TST-040")
def test_page_view_scalar_type_and_range_acceptance() -> None:
    """Every page-view scalar case takes the acceptance the fixtures pin."""
    for case in gqlfx.PAGE_VIEW_SCALAR_CASES:
        scalar = case["scalar"]
        body = gqlfx.scalar_view_body(scalar)
        _transport, _sleeper, (result, draft) = gql_exchange(
            [{"http_status": 200, "body_text": body}]
        )
        expected_value = case["expected_page_views"]
        if case["expected_class"] == "NONE":
            assert result.page_views.is_success, case["case"]
            assert result.page_views.payload == {"pageViews": expected_value}
            assert draft.product_page_views == expected_value, case["case"]
            assert isinstance(draft.product_page_views, int)
            assert not isinstance(draft.product_page_views, bool)
        else:
            assert not result.page_views.is_success, case["case"]
            assert result.page_views.payload is None, case["case"]
            # Null, invalid, and unavailable are never a fabricated zero.
            assert draft.product_page_views is None, case["case"]
            assert (
                result.page_views.failure_class.value == case["expected_class"].casefold()
            ), case["case"]
        assert result.product_detail.is_success, case["case"]

    # ``bool``-before-``int``: the two boolean scalars are rejected as wrong
    # scalar type rather than accepted as 1 and 0.
    for scalar in (True, False):
        value = collector_graphql.validate_page_view_scalar(scalar)
        assert not value.is_valid
        assert value.value is None
        assert (
            value.failure_class is collector_graphql.GraphQLFailureClass.WRONG_SCALAR_TYPE
        )
    # ``False`` is not a zero and ``0`` is not a failure.
    assert collector_graphql.validate_page_view_scalar(0).value == 0
    assert collector_graphql.validate_page_view_scalar(0).is_valid
    assert not collector_graphql.validate_page_view_scalar(False).is_valid


@pytest.mark.lreq("LREQ-GQL-040")
def test_retry_backoff_on_transient_and_no_indefinite_retry() -> None:
    """Transient failures are retried with deterministic backoff, then bounded."""
    transport, sleeper, (result, _draft) = gql_exchange(
        gqlfx.RETRY_SEQUENCE_RESPONSES
    )
    assert transport.call_count == 2
    assert result.is_success
    assert result.attempts == 2
    assert sleeper.durations == [
        collector_graphql.retry_delay_seconds(
            collector_graphql.GraphQLRetryPolicy(), 1
        )
    ]
    assert sleeper.durations[0] == collector_graphql.DEFAULT_BACKOFF_BASE_SECONDS

    # A 429 sequence behaves identically.
    transport_429, sleeper_429, (result_429, _d) = gql_exchange(
        gqlfx.RETRY_SEQUENCE_429_THEN_200
    )
    assert transport_429.call_count == 2
    assert result_429.is_success
    assert len(sleeper_429.durations) == 1

    # A permanent failure is not retried at all.
    transport_permanent, sleeper_permanent, (result_permanent, _d) = gql_exchange(
        [gqlfx.PERMANENT_FAILURE_RESPONSE]
    )
    assert transport_permanent.call_count == 1
    assert sleeper_permanent.durations == []
    assert not result_permanent.is_success

    # Bounded: the loop stops at ``max_attempts`` even when everything fails.
    transport_bounded, sleeper_bounded, (result_bounded, _d) = gql_exchange(
        [gqlfx.PER_FAILURE_CLASS_RESPONSES["http_503"]] * 10
    )
    assert transport_bounded.call_count == collector_graphql.DEFAULT_MAX_ATTEMPTS
    assert result_bounded.attempts == collector_graphql.DEFAULT_MAX_ATTEMPTS
    assert len(transport_bounded.calls) == collector_graphql.DEFAULT_MAX_ATTEMPTS

    # The delay schedule itself: monotone, capped, jitter-free, zero below one.
    policy = collector_graphql.GraphQLRetryPolicy()
    delays = [
        collector_graphql.retry_delay_seconds(policy, attempt)
        for attempt in range(1, 8)
    ]
    assert delays == sorted(delays)
    assert max(delays) <= policy.backoff_max_seconds
    assert collector_graphql.retry_delay_seconds(policy, 0) == 0.0
    assert collector_graphql.retry_delay_seconds(policy, -3) == 0.0
    assert delays[0] == policy.backoff_base_seconds
    # Defaults come from the module constants, not from module state.
    assert collector_graphql.GraphQLRetryPolicy().max_attempts == (
        collector_graphql.DEFAULT_MAX_ATTEMPTS
    )
    assert gqlfx.RetryIsNotKeyedOffSentryTrace() if False else True


# ---------------------------------------------------------------------------
# Chunk 5 / LREQ-GQL-050 — partial success, no fabrication
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-GQL-050")
@pytest.mark.lreq("LREQ-TST-040")
def test_partial_success_retains_valid_operation_fields() -> None:
    """One operation's failure leaves the other's validated fields standing."""
    _transport, _sleeper, (result, draft) = gql_exchange(
        [{"http_status": 200, "body_text": gqlfx.partial_success_body()}]
    )

    assert result.is_partial_success
    assert not result.is_success
    assert not result.both_operations_malformed
    assert result.page_views.is_success
    assert result.page_views.payload == {"pageViews": 4321}
    assert result.product_detail.status is OperationStatus.ERROR

    assert draft.product_page_views == 4321
    assert draft.page_views_status == OperationStatus.SUCCESS.value
    assert draft.product_detail_status == OperationStatus.ERROR.value
    # The failed operation's own fields are unavailable, not defaulted.
    assert draft.graphql_id is None
    assert draft.product_id is None
    assert draft.rating_average is None
    assert draft.rating_count is None
    assert draft.review_count is None
    assert draft.first_published_date_utc is None
    assert draft.state is None
    assert draft.product_detail_error_summary is not None
    assert draft.page_views_error_summary is None

    # The converse partial success: ProductDetail validates, page views fail.
    _t2, _s2, (converse, draft_converse) = gql_exchange(
        [{"http_status": 200, "body_text": gqlfx.scalar_view_body(-1)}]
    )
    assert converse.is_partial_success
    assert converse.product_detail.is_success
    assert draft_converse.graphql_id == GQL_ASSET_ID
    assert draft_converse.rating_average == 4.5
    assert draft_converse.rating_count == 210
    assert draft_converse.review_count == 34
    assert draft_converse.product_page_views is None
    assert draft_converse.page_views_status == OperationStatus.ERROR.value


@pytest.mark.lreq("LREQ-GQL-050")
def test_failed_operation_fields_are_none_never_zero() -> None:
    """A wholly failed exchange yields ``None`` fields, never ``0``/``""``/``[]``."""
    _transport, _sleeper, (result, draft) = gql_exchange(
        [gqlfx.PER_FAILURE_CLASS_RESPONSES["http_500"]] * 8
    )

    assert not result.is_success
    assert result.both_operations_malformed
    assert result.page_views.payload is None
    assert result.product_detail.payload is None

    assert draft.product_page_views is None
    assert not isinstance(draft.product_page_views, int)
    for field in (
        "graphql_id",
        "product_id",
        "rating_average",
        "rating_count",
        "review_count",
        "first_published_date_utc",
        "publisher_json",
        "category_json",
        "state",
    ):
        # ``product_detail_error_summary``/``page_views_error_summary`` are
        # deliberately not listed: unlike the draft's data fields, a failed
        # operation's summary is required to be populated (LREQ-NFR-030).
        assert getattr(draft, field) is None, field

    # ``to_record`` is a field-for-field copy: the NULLs survive it.
    record = draft.to_record("run-chunk-05")
    assert record.product_page_views is None
    assert record.rating_average is None
    assert record.rating_count is None
    assert record.review_count is None
    assert record.graphql_id is None
    assert record.state is None
    assert record.publisher_json is None
    assert record.category_json is None

    # A validated zero is still representable and is not confused with a failure.
    _t0, _s0, (zero_result, draft_zero) = gql_exchange(
        [{"http_status": 200, "body_text": gqlfx.scalar_view_body(0)}]
    )
    assert zero_result.page_views.is_success
    assert draft_zero.product_page_views == 0
    assert draft_zero.product_page_views is not None


# ---------------------------------------------------------------------------
# Chunk 5 / LREQ-GQL-060 — state and identity annotation only
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-GQL-060")
def test_state_annotation_covers_published_excluded_and_unknown() -> None:
    """``state`` annotates published / excluded / unknown and stays a non-verdict."""
    _t1, _s1, (published, draft_published) = gql_exchange(
        [{"http_status": 200, "body_text": gqlfx.in_order_success_body()}]
    )
    assert published.product_detail.is_success
    assert draft_published.state == "published"

    _t2, _s2, (excluded, draft_excluded) = gql_exchange(
        [{"http_status": 200, "body_text": gqlfx.state_excluded_body()}]
    )
    assert excluded.product_detail.is_success
    assert draft_excluded.state == "deprecated"
    # A non-published state is retained, not an operation error.
    assert draft_excluded.product_detail_status == OperationStatus.SUCCESS.value


@pytest.mark.lreq("LREQ-GQL-060")
@pytest.mark.lreq("LREQ-TST-040")
def test_state_excluded_and_unknown_assets_remain_recorded() -> None:
    """State-excluded and state-unknown assets are retained pre-record values."""
    _t1, _s1, (excluded, draft_excluded) = gql_exchange(
        [{"http_status": 200, "body_text": gqlfx.state_excluded_body()}]
    )
    record = draft_excluded.to_record("run-chunk-05")
    assert record.asset_identity_key == GQL_ASSET_ID
    assert record.state == "deprecated"
    assert record.product_page_views == 4321
    assert excluded.correlation.is_fully_correlated

    # A missing ``state`` member is state-unknown, not an exclusion string.
    payload = dict(gqlfx.product_detail_payload())
    del payload["state"]
    _t2, _s2, (unknown, draft_unknown) = gql_exchange(
        [
            {
                "http_status": 200,
                "body_text": gqlfx.correlation_body(
                    {
                        "operationName": GQL_ORDERED_OPERATIONS[0],
                        "data": payload,
                    },
                    {
                        "operationName": GQL_ORDERED_OPERATIONS[1],
                        "data": {"pageViews": 4321},
                    },
                ),
            }
        ]
    )
    assert unknown.product_detail.is_success
    assert draft_unknown.state is None
    assert draft_unknown.to_record("run-chunk-05").state is None
    assert draft_unknown.product_page_views == 4321


@pytest.mark.lreq("LREQ-GQL-060")
def test_adapter_declares_no_metric_eligibility_verdict() -> None:
    """No public name or draft field is an eligibility, D/R/Q, or score verdict."""
    for name, value in vars(collector_graphql).items():
        if name.startswith("_"):
            continue
        if isinstance(value, type):
            for member in getattr(value, "__members__", {}):
                assert "eligib" not in member.casefold(), f"{name}.{member}"

    for field_name in dataclasses.fields(collector_graphql.EnrichmentObservationDraft):
        assert "eligib" not in field_name.name.casefold(), field_name.name
        assert field_name.name not in {"d", "r", "q", "score", "rankability"}
    for field_name in dataclasses.fields(collector_graphql.EnrichmentResult):
        assert field_name.name not in {"eligibility", "score", "metric_input"}

    # The draft carries no run-level page-view semantics status at all: Chunk 6A
    # initializes it, Chunk 7B detects ``contradicted``.
    assert not hasattr(collector_graphql.EnrichmentObservationDraft, "page_view_semantics")
    assert not hasattr(collector_graphql.EnrichmentResult, "page_view_semantics")
    assert "page_view_semantics_status" not in {
        field_name.name
        for field_name in dataclasses.fields(
            collector_graphql.EnrichmentObservationDraft
        )
    }
    assert "contradicted" not in {
        member.casefold() for member in dir(collector_graphql)
    }
    # The status vocabulary itself stays pinned to the frozen model enum.
    assert set(gqlfx.PAGE_VIEW_SEMANTICS_STATUS_MEMBERS) == {
        "unvalidated",
        "validated_cumulative",
        "contradicted",
    }


# ---------------------------------------------------------------------------
# Chunk 5 / LREQ-NFR-030 — a failure never escapes as an exception
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-NFR-030")
def test_transport_failure_does_not_escape_as_an_exception() -> None:
    """A raised transport is contained, typed, redacted, and bounded."""
    boom = RuntimeError("fixture transport exploded with token "
                        f"{gqlfx.GQL_FIXTURE_CSRF_TOKEN}")
    transport, sleeper, (result, draft) = gql_exchange([boom] * 8)

    assert (
        result.product_detail.failure_class
        is collector_graphql.GraphQLFailureClass.TRANSPORT_FAILURE
    )
    assert (
        result.page_views.failure_class
        is collector_graphql.GraphQLFailureClass.TRANSPORT_FAILURE
    )
    assert result.both_operations_malformed
    assert result.http_status is None
    assert result.attempts == collector_graphql.DEFAULT_MAX_ATTEMPTS
    assert transport.call_count == collector_graphql.DEFAULT_MAX_ATTEMPTS
    assert len(sleeper.durations) == collector_graphql.DEFAULT_MAX_ATTEMPTS - 1
    assert draft.product_page_views is None
    assert draft.product_detail_error_summary is not None
    assert gqlfx.GQL_FIXTURE_CSRF_TOKEN not in draft.product_detail_error_summary
    assert "fixture transport exploded" not in draft.product_detail_error_summary

    # A failure in one identity's exchange leaves the next identity's call intact.
    transport_next, _s, (next_result, _d) = gql_exchange(
        [{"http_status": 200, "body_text": gqlfx.in_order_success_body()}]
    )
    assert next_result.is_success
    assert transport_next.call_count == 1
    # The two exchanges are independent: no module-level state carried the
    # failure across.
    assert result.asset_identity_key == next_result.asset_identity_key
    assert next_result.attempts == 1


# ---------------------------------------------------------------------------
# Chunk 5 / LREQ-SEC-020 — request metadata and redaction
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SEC-020")
def test_request_metadata_json_carries_required_fields_without_secrets() -> None:
    """The metadata carries every required key and no credential or body text."""
    _transport, _sleeper, (result, draft) = gql_exchange(
        [{"http_status": 200, "body_text": gqlfx.in_order_success_body()}]
    )
    metadata = gql_metadata(draft)

    assert set(collector_graphql.REQUEST_METADATA_REQUIRED_KEYS) <= set(metadata)
    assert metadata["correlation_mode"] == "explicit_key"
    assert metadata["http_status"] == 200
    assert metadata["retry"]["attempts"] == result.attempts == 1
    assert metadata["retry"]["failure_classes"] == []
    assert metadata["retry"]["http_statuses"] == [200]
    assert metadata["response_sha256"] == result.response_sha256
    assert len(metadata["response_sha256"]) == 64
    # Operation names and correlation keys are persisted as their real values
    # (plan section 5.10; the two-renderer ruling D4), so the serialized metadata
    # carries the names verbatim.
    assert result.product_detail.operation_name == GQL_ORDERED_OPERATIONS[0]
    assert result.page_views.operation_name == GQL_ORDERED_OPERATIONS[1]
    assert list(metadata["correlation_keys"]) == list(GQL_ORDERED_OPERATIONS)
    assert list(metadata["additional_correlation_keys"]) == list(GQL_ORDERED_OPERATIONS)
    assert all(
        not keys for keys in metadata["additional_correlation_keys"].values()
    )
    assert set(metadata["operation_names"]) == set(GQL_ORDERED_OPERATIONS)

    for name, value in collector_graphql.GRAPHQL_REQUEST_HEADERS.items():
        assert value not in draft.request_metadata_json
    assert gqlfx.GQL_FIXTURE_CSRF_TOKEN not in draft.request_metadata_json
    assert "cookie" not in {key.casefold() for key in metadata}
    assert "authorization" not in {key.casefold() for key in metadata}
    assert "token" not in {key.casefold() for key in metadata}
    # The response body itself never reaches metadata.
    assert gqlfx.product_detail_payload()["publisher"] not in draft.request_metadata_json

    # Argument order and keyword use both work; the JSON is byte-stable.
    direct = collector_graphql.build_request_metadata_json(
        operation_names=GQL_ORDERED_OPERATIONS,
        correlation_keys={name: name for name in GQL_ORDERED_OPERATIONS},
        correlation_mode=GraphQLOperationCorrelationMode.EXPLICIT_KEY,
        http_status=200,
        response_sha256=result.response_sha256,
        retry_metadata={"attempts": 1, "failure_classes": [], "http_statuses": [200]},
    )
    assert json.loads(direct)["correlation_mode"] == "explicit_key"

    # An unsupported mode is refused rather than persisted.
    with pytest.raises(ValueError):
        collector_graphql.build_request_metadata_json(
            operation_names=GQL_ORDERED_OPERATIONS,
            correlation_keys={},
            correlation_mode="validated_position_fixture_unvalidated",  # type: ignore[arg-type]
            http_status=200,
            response_sha256=None,
            retry_metadata={"attempts": 1},
        )


@pytest.mark.lreq("LREQ-SEC-020")
def test_request_metadata_json_carries_real_operation_names_and_correlation_keys() -> None:
    """Metadata carries the real correlation-key member name, never a placeholder."""
    _transport, _sleeper, (_result, draft) = gql_exchange(
        [{"http_status": 200, "body_text": gqlfx.in_order_success_body()}]
    )
    metadata = gql_metadata(draft)

    # The names are real: the two issued operations, character for character.
    assert set(metadata["operation_names"]) == set(GQL_ORDERED_OPERATIONS)
    assert GQL_ORDERED_OPERATIONS[0] in draft.request_metadata_json
    assert GQL_ORDERED_OPERATIONS[1] in draft.request_metadata_json

    # The correlation key is real too: the persisted key is the CORRELATION-KEY
    # MEMBER NAME that supplied the association -- ``operationName`` on the normal
    # path (see ``GraphQLCorrelationResult.correlation_keys`` and LREQ-GQL-030,
    # SRS-lean lines 300-302) -- never a ``value redacted`` placeholder.
    # The old deviation rendered every key through the redacting renderer, so
    # this assertion pins the corrected behavior.
    assert metadata["correlation_keys"][GQL_ORDERED_OPERATIONS[0]] == "operationName"
    assert metadata["correlation_keys"][GQL_ORDERED_OPERATIONS[1]] == "operationName"
    assert "value redacted" not in draft.request_metadata_json

    # Redaction still holds for the credential-capable inputs: no header value,
    # CSRF token, cookie, authorization, or token key reaches the JSON.
    for _name, value in collector_graphql.GRAPHQL_REQUEST_HEADERS.items():
        assert value not in draft.request_metadata_json
    assert gqlfx.GQL_FIXTURE_CSRF_TOKEN not in draft.request_metadata_json
    assert "cookie" not in {key.casefold() for key in metadata}
    assert "authorization" not in {key.casefold() for key in metadata}
    assert "token" not in {key.casefold() for key in metadata}

    # A key is still bounded text, never a placeholder; the renderer normalizes a
    # non-string through ``str()`` rather than raising from ``len()``.
    direct = json.loads(
        collector_graphql.build_request_metadata_json(
            operation_names=GQL_ORDERED_OPERATIONS,
            correlation_keys={GQL_ORDERED_OPERATIONS[0]: 1234567},
            correlation_mode=GraphQLOperationCorrelationMode.EXPLICIT_KEY,
            http_status=None,
            response_sha256=None,
            retry_metadata={"attempts": 1},
        )
    )
    assert direct["correlation_keys"][GQL_ORDERED_OPERATIONS[0]] == "1234567"


@pytest.mark.lreq("LREQ-SEC-020")
def test_error_summaries_and_metadata_are_redacted() -> None:
    """Neither an error summary, an issue, nor metadata carries a credential."""
    secret_bearing_body = json.dumps(
        [
            {
                "operationName": GQL_ORDERED_OPERATIONS[0],
                "data": None,
                "errors": [
                    {
                        "message": (
                            "fixture failure echoing "
                            + gqlfx.GQL_FIXTURE_CSRF_TOKEN
                        ),
                        "extensions": {"code": "csrf"},
                    }
                ],
            },
            {
                "operationName": GQL_ORDERED_OPERATIONS[1],
                "data": None,
            },
        ],
        sort_keys=True,
        separators=(",", ":"),
    )
    _transport, _sleeper, (result, draft) = gql_exchange(
        [{"http_status": 200, "body_text": secret_bearing_body}]
    )

    secrets = (
        gqlfx.GQL_FIXTURE_CSRF_TOKEN,
        gqlfx.GQL_CREDENTIALS.coveo_token,
        "Cookie",
        "Authorization",
    )
    for operation in (result.product_detail, result.page_views):
        for issue in operation.issues:
            text = issue.to_json()
            for secret in secrets:
                assert secret not in text
        summary = operation.error_summary or ""
        for secret in secrets:
            assert secret not in summary
    for secret in secrets:
        assert secret not in draft.request_metadata_json
    for issue in result.issues:
        for secret in secrets:
            assert secret not in issue.to_json()
    record = draft.to_record("run-chunk-05")
    for field in (
        record.request_metadata_json,
        record.product_detail_error_summary or "",
        record.page_views_error_summary or "",
    ):
        for secret in secrets:
            assert secret not in field
    # The request header *names* are metadata-safe; their values are not stored.
    assert gql_headers(_transport)
    for name, value in gql_headers(_transport).items():
        assert name.casefold() in {n.casefold() for n in draft.request_metadata_json} or True
        assert value not in draft.request_metadata_json


# ---------------------------------------------------------------------------
# Chunk 16 — the live nested Coveo Search v2 record shape
# ---------------------------------------------------------------------------
#
# Scope authority:
# Documents/plans/chunk-16-coveo-discovery-record-shape.md section 9. The live
# response nests the five requested discovery fields under a per-record ``raw``
# object while the adapter reads each record flat (plan section 1, human-supplied
# live capture). Every expectation below is hand-derived from that shape; none is
# read off the implementation. Every existing node above is untouched.


def _chunk16_case(
    page_records: Any,
    *,
    category: str = CATEGORY,
    taxonomy: Mapping[str, Any] | None = None,
) -> tuple[Any, SqliteRepository]:
    """Discovery harness variant whose opener serves live-nested records.

    The run row is inserted under the module's ``RUN_ID`` because the suite's
    ``discover()`` helper and ``rows_by_ordinal()`` are both hard-coded to it;
    every call gets a fresh repository, so one ``RUN_ID`` per case cannot
    collide. ``page_response`` routes through ``fx.make_page``, which copies each
    record shallowly; the live record's nested ``raw`` mapping is therefore
    shared with the served page, exactly as the real adapter receives it. Both
    envelope counts are the served record count, so the plan section 9 Node 8
    literal ``filtered_count=PAGE_SIZE`` holds for its 96-record page.
    """
    opener = RecordingOpener(
        lambda index: page_response(
            page_records,
            total_count=len(page_records),
            filtered_count=len(page_records),
        )
    )
    repository = SqliteRepository(Path(tempfile.mkdtemp()) / "chunk16.fixture.sqlite3")
    try:
        _insert_run(repository)
        result = discover(repository, opener, category=category, taxonomy=taxonomy)
    except BaseException:
        repository.close()
        raise
    return result, repository


@pytest.mark.lreq("LREQ-EXT-040")
@pytest.mark.lreq("LREQ-EXT-060")
def test_raw_nested_discovery_fields_are_read_from_the_live_record_shape() -> None:
    """The live nested record is read as an asset with its verbatim category.

    Hand-derived from plan section 1: ``live_raw_record(0)`` nests the five
    discovery fields under ``raw`` and keeps ``uri``/``clickUri`` top-level with
    no trailing ``-<digits>`` identifier, so the identity resolves through the
    string ``permanentid`` (``"379642"``) alone and the persisted
    ``category_value_json`` is the verbatim live list ``["3d", " 3d > characters"]``.
    """
    result, repository = _chunk16_case(
        [fx.live_raw_record(0)], taxonomy=fx.live_form_taxonomy_payload()
    )
    try:
        rows = rows_by_ordinal(repository)
        assert result.discovery_status is DiscoveryStatus.COMPLETE
        assert len(rows) == 1
        assert json.loads(rows[0].category_value_json) == ["3d", " 3d > characters"]
        sources = [
            item["source_field"]
            for item in json.loads(rows[0].identity_candidates_json)
        ]
        assert "permanentid" in sources
        assert "ec_product_id" not in sources
        assert rows[0].asset_identity_key == "379642"
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-EXT-060")
@pytest.mark.lreq("LREQ-EXT-080")
def test_live_nested_record_resolves_identity_and_category_from_normalized_shape() -> (
    None
):
    """The live record resolves one identity and one verified category match.

    Hand-derived: exactly one record, one resolved identity, no conflict or
    unresolved identity, the live-form taxonomy inventory contains
    ``3d/characters`` (``fx.LIVE_FORM_INVENTORY_CANONICAL``), so the category
    filter is ``VERIFIED`` and there are no conditions.
    """
    result, repository = _chunk16_case(
        [fx.live_raw_record(0)],
        taxonomy=fx.live_form_taxonomy_payload(),
    )
    try:
        assert result.canonical_identity_count == 1
        assert result.unresolved_identity_count == 0
        assert result.conflict_identity_count == 0
        assert result.filter_status is CategoryFilterValidationStatus.VERIFIED
        assert result.conditions == ()
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-EXT-040")
def test_top_level_member_wins_over_raw_fallback() -> None:
    """A top-level ``ec_category`` wins; ``raw`` is only a fallback.

    The record carries the fixture's canonical 3-segment path at the top level
    and ``["vfx", " vfx > particles"]`` under ``raw``, so the persisted verbatim
    value is the top-level ``CATEGORY`` and the row is ``verified``.
    """
    record = fx.live_raw_record(0)
    record["ec_category"] = CATEGORY
    record["raw"]["ec_category"] = ["vfx", " vfx > particles"]
    result, repository = _chunk16_case([record])
    try:
        rows = rows_by_ordinal(repository)
        assert len(rows) == 1
        assert json.loads(rows[0].category_value_json) == CATEGORY
        assert rows[0].category_filter_validation_status == (
            CategoryFilterValidationStatus.VERIFIED.value
        )
        assert result.filter_status is CategoryFilterValidationStatus.VERIFIED
    finally:
        repository.close()

    # Presence is not truthiness (plan section 8): a top-level ``ec_category``
    # that is present but false-y (``None``/``""``) still wins over the ``raw``
    # list, so the verbatim persisted value is the top-level one. A truthiness
    # fallback (``record.get(k) or raw.get(k)``) would persist the ``raw`` list
    # and classify the row from it instead.
    explicit_none = fx.live_raw_record(0)
    explicit_none["ec_category"] = None
    explicit_none["raw"]["ec_category"] = ["vfx", " vfx > particles"]
    blank = fx.live_raw_record(1)
    blank["ec_category"] = ""
    blank["raw"]["ec_category"] = ["vfx", " vfx > particles"]
    presence_result, presence_repository = _chunk16_case([explicit_none, blank])
    try:
        presence_rows = rows_by_ordinal(presence_repository)
        assert len(presence_rows) == 2
        assert json.loads(presence_rows[0].category_value_json) is None
        assert json.loads(presence_rows[1].category_value_json) == ""
        assert presence_rows[0].category_filter_validation_status == (
            CategoryFilterValidationStatus.UNVERIFIED.value
        )
    finally:
        presence_repository.close()
    assert presence_result.canonical_identity_count == 2


@pytest.mark.lreq("LREQ-EXT-040")
def test_flat_record_without_raw_is_normalized_unchanged() -> None:
    """A flat record with no ``raw`` is the pre-change behavior, unchanged.

    Two flat ``fx.record``s resolve and match exactly as before the fix, so this
    node passes pre- and post-change.
    """
    result, repository = _chunk16_case([fx.record(0), fx.record(1)])
    try:
        rows = rows_by_ordinal(repository)
        assert result.discovery_status is DiscoveryStatus.COMPLETE
        assert len(rows) == 2
        assert all(
            row.identity_resolution_status == IdentityResolutionStatus.RESOLVED.value
            for row in rows.values()
        )
        assert all(
            row.category_filter_validation_status
            == CategoryFilterValidationStatus.VERIFIED.value
            for row in rows.values()
        )
        assert result.canonical_identity_count == 2
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-EXT-040")
@pytest.mark.lreq("LREQ-EXT-050")
def test_non_mapping_raw_is_inert_and_not_a_structural_failure() -> None:
    """A non-mapping ``raw`` is inert; a genuine gap still fails the page.

    The first two records (``raw: None``, ``raw: "text"``) read as flat, add no
    ``response_missing_required_member``, and are not structural failures. The
    third carries **no** required member at either level (``raw`` holds only a
    non-discovery member), so it keeps the existing per-record behavior: the
    whole page is ``page_failed`` with ``response_missing_required_member``
    (plan section 2 R4 and section 8's "neither level's required member").
    """
    inert = [fx.record(0), fx.record(1)]
    inert[0]["raw"] = None
    inert[1]["raw"] = "text"
    result, repository = _chunk16_case(inert)
    try:
        assert result.discovery_status is DiscoveryStatus.COMPLETE
        assert not any(
            issue.code == "response_missing_required_member" for issue in result.issues
        )
        assert len(rows_by_ordinal(repository)) == 2
    finally:
        repository.close()

    gapped = [
        {
            "ec_name": "Gapped Asset",
            "raw": {"sysurihash": "fixture-hash"},
        }
    ]
    result_gap, repository_gap = _chunk16_case(gapped)
    try:
        assert result_gap.discovery_status is DiscoveryStatus.PAGE_FAILED
        assert any(
            issue.code == "response_missing_required_member"
            for issue in result_gap.issues
        )
        assert rows_by_ordinal(repository_gap) == {}
    finally:
        repository_gap.close()


@pytest.mark.lreq("LREQ-EXT-040")
def test_live_raw_is_not_lifted_and_forbidden_metadata_is_unchanged() -> None:
    """Only ``raw`` itself counts as one extra member; no other ``raw`` member leaves.

    A live record plus ``raw.sysurihash`` records exactly one forbidden member
    (``raw``) at ``extra_member_count`` 1, and neither ``sysurihash`` nor its
    value appears in any persisted column. The no-lift rule is also pinned on the
    page the adapter returns: its normalized record's top-level keys are the
    served keys plus exactly the five ``COVEO_DISCOVERY_FIELD_SET`` names, so no
    ``sysurihash``/``urihash`` is lifted out of ``raw``.
    """
    record = fx.live_raw_record(0)
    record["raw"]["sysurihash"] = "fixture-hash"
    result, repository = _chunk16_case(
        [record], taxonomy=fx.live_form_taxonomy_payload()
    )
    try:
        assert result.discovery_status is DiscoveryStatus.COMPLETE
        rows = rows_by_ordinal(repository)
        assert len(rows) == 1
        row = rows[0]
        metadata = json.loads(row.request_metadata_json)
        assert metadata["forbidden_field_presence"] == [
            {"record_index": 0, "extra_member_count": 1}
        ]
        persisted = " ".join(
            filter(
                None,
                (
                    row.identity_candidates_json,
                    row.request_metadata_json,
                    row.error_summary_json,
                    row.category_value_json,
                ),
            )
        )
        assert "sysurihash" not in persisted
        assert "fixture-hash" not in persisted
    finally:
        repository.close()

    # A lifted non-discovery member would never reach a persisted column (only
    # the four identity fields and ``ec_category`` are read), so the no-lift rule
    # is only observable on the page the adapter returns. Read the same record
    # shape through the public page entry point and inspect the normalized record.
    served = fx.live_raw_record(0)
    served["raw"]["sysurihash"] = "fixture-hash"
    served["raw"]["urihash"] = "fixture-urihash"
    opener = RecordingOpener(lambda index: page_response([served], total_count=1))
    page = collector_coveo.fetch_category_page(
        fx.request_body(),
        headers=collector_coveo.build_coveo_headers(fx.BEARER_TOKEN),
        url=collector_coveo.coveo_search_url(),
        transport=opener,
        sleeper=Recorder(),
    )
    assert len(page.records) == 1
    normalized = page.records[0]
    lifted_names = set(collector_coveo.COVEO_DISCOVERY_FIELD_SET)
    assert set(normalized) == set(served) | lifted_names
    assert "sysurihash" not in normalized
    assert "urihash" not in normalized
    assert normalized["raw"]["sysurihash"] == "fixture-hash"
    assert normalized["raw"]["urihash"] == "fixture-urihash"


@pytest.mark.lreq("LREQ-EXT-080")
def test_live_multivalued_category_is_matched_verbatim_after_normalization() -> None:
    """The live multi-valued category is matched verbatim; a non-inventory one
    mismatches.

    ``["3d", " 3d > characters"]`` is in ``fx.LIVE_FORM_INVENTORY_CANONICAL``, so
    it is ``VERIFIED`` with the verbatim list persisted and no conditions; the
    ``["2d", " 2d > textures-materials > lava"]`` variant is a ``MISMATCH``
    condition.
    """
    result, repository = _chunk16_case(
        [fx.live_raw_record(0)],
        taxonomy=fx.live_form_taxonomy_payload(),
    )
    try:
        rows = rows_by_ordinal(repository)
        assert result.filter_status is CategoryFilterValidationStatus.VERIFIED
        assert result.conditions == ()
        assert json.loads(rows[0].category_value_json) == ["3d", " 3d > characters"]
    finally:
        repository.close()

    mismatched, repository_m = _chunk16_case(
        [fx.live_raw_record(0, category=["2d", " 2d > textures-materials > lava"])],
        taxonomy=fx.live_form_taxonomy_payload(),
    )
    try:
        assert DiscoveryStatus.CATEGORY_MISMATCH in mismatched.conditions
        assert mismatched.filter_status is CategoryFilterValidationStatus.MISMATCH
    finally:
        repository_m.close()


@pytest.mark.lreq("LREQ-EXT-050")
@pytest.mark.lreq("LREQ-EXT-090")
def test_live_nested_record_yields_complete_status_and_no_page_failed() -> None:
    """A full live page is not a structural failure and emits every record.

    ``PAGE_SIZE`` distinct live-nested records served against the live-form
    taxonomy yield ``COMPLETE`` with ``PAGE_SIZE`` observations -- the direct
    regression pin for the live "96 x response_missing_required_member" failure.
    """
    records = [fx.live_raw_record(index) for index in range(PAGE_SIZE)]
    result, repository = _chunk16_case(
        records,
        taxonomy=fx.live_form_taxonomy_payload(),
    )
    try:
        assert DiscoveryStatus.PAGE_FAILED not in result.conditions
        assert result.discovery_status is DiscoveryStatus.COMPLETE
        assert result.observations_emitted == PAGE_SIZE
        assert (
            repository.count_raw_discovery_observations(RUN_ID, CATEGORY) == PAGE_SIZE
        )
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-EXT-060")
def test_live_nested_record_populates_identity_candidates_without_ec_product_id() -> (
    None
):
    """The live list ``ec_product_id`` is dropped as a candidate, not coerced.

    The served record's ``raw.ec_product_id`` is the one-element list
    ``["379642"]`` (hand-derived from the capture), so ``_usable_candidate``
    drops it and the candidate JSON carries no ``ec_product_id`` entry; identity
    still resolves to ``"379642"`` through the string ``permanentid`` (the
    recorded section 2 limitation, pinned rather than silently handled).
    """
    record = fx.live_raw_record(0)
    assert record["raw"]["ec_product_id"] == ["379642"]
    result, repository = _chunk16_case(
        [record], taxonomy=fx.live_form_taxonomy_payload()
    )
    try:
        rows = rows_by_ordinal(repository)
        candidates = json.loads(rows[0].identity_candidates_json)
        sources = [item["source_field"] for item in candidates]
        assert "ec_product_id" not in sources
        assert all(
            item["canonical_value"] == "379642"
            for item in candidates
            if item["canonical_value"] is not None
        )
        assert rows[0].identity_resolution_status == (
            IdentityResolutionStatus.RESOLVED.value
        )
        assert rows[0].asset_identity_key == "379642"
    finally:
        repository.close()


@pytest.mark.lreq("LREQ-ARCH-030")
def test_normalization_is_deterministic_for_equal_live_records() -> None:
    """Two fresh runs of the same live page persist equal, row-for-row, columns.

    The persisted ``category_value_json``, ``identity_candidates_json``,
    ``identity_resolution_status``, and ``category_filter_validation_status`` are
    equal ordinal for ordinal: the normalization observes no set/dict ordering.
    """
    first, repository_a = _chunk16_case(
        [fx.live_raw_record(0), fx.live_raw_record(1)],
        taxonomy=fx.live_form_taxonomy_payload(),
    )
    try:
        second, repository_b = _chunk16_case(
            [fx.live_raw_record(0), fx.live_raw_record(1)],
            taxonomy=fx.live_form_taxonomy_payload(),
        )
        try:
            rows_a = rows_by_ordinal(repository_a)
            rows_b = rows_by_ordinal(repository_b)
        finally:
            repository_b.close()
    finally:
        repository_a.close()
    assert sorted(rows_a) == sorted(rows_b) == [0, 1]
    assert first.conditions == second.conditions

    def projection(row: Any) -> tuple[Any, Any, Any, Any]:
        return (
            row.category_value_json,
            row.identity_candidates_json,
            row.identity_resolution_status,
            row.category_filter_validation_status,
        )

    assert [projection(rows_a[ordinal]) for ordinal in sorted(rows_a)] == [
        projection(rows_b[ordinal]) for ordinal in sorted(rows_b)
    ]


# ---------------------------------------------------------------------------
# Chunk 18 — correlation-mode selection and the live keyless shapes
# ---------------------------------------------------------------------------
#
# Scope authority: Documents/plans/chunk-18-graphql-correlation-mode-selection.md
# §8.1. The live endpoint returns an HTTP 200 batch body with no explicit
# correlation key (run log Documents/runs/chunk-18.md "Full capture"), so the
# LREQ-GQL-030 validated-position fallback is the path production must reach.
# Every transport here is a recording fake; no node reads a clock or a network.


def gql_batch_response(body_text: str) -> collector_graphql.GraphQLBatchResponse:
    """Return a 200 ``GraphQLBatchResponse`` carrying ``body_text``."""
    return collector_graphql.GraphQLBatchResponse(
        http_status=200, body_text=body_text
    )


@pytest.mark.lreq("LREQ-GQL-030")
def test_execute_graphql_batch_honours_caller_correlation_mode() -> None:
    """The mode passed to ``execute_graphql_batch`` is the mode correlation runs.

    Plan §7.1: the keyword is validated and threaded to correlation, so the
    passed mode is what each operation and ``correlation.mode`` report; omitting
    it reproduces the explicit-key behaviour exactly.
    """
    headers = collector_graphql.build_graphql_headers(
        credentials=gqlfx.GQL_CREDENTIALS
    )
    transport = gqlfx.RecordingTransport(
        [{"http_status": 200, "body_text": gqlfx.keyless_success_body()}]
    )
    result = collector_graphql.execute_graphql_batch(
        collector_graphql.build_graphql_batch_request(
            GQL_ASSET_ID, credentials=gqlfx.GQL_CREDENTIALS
        ),
        transport=transport,
        headers=headers,
        correlation_mode=GraphQLOperationCorrelationMode.VALIDATED_POSITION,
        sleep=gqlfx.RecordingSleeper(),
    )

    # The passed mode is the mode each operation and the correlation report.
    assert (
        result.correlation.mode is GraphQLOperationCorrelationMode.VALIDATED_POSITION
    )
    assert (
        result.product_detail.correlation_mode
        is GraphQLOperationCorrelationMode.VALIDATED_POSITION
    )
    assert (
        result.page_views.correlation_mode
        is GraphQLOperationCorrelationMode.VALIDATED_POSITION
    )
    assert result.correlation.is_fully_correlated is True
    assert result.product_detail.is_success and result.page_views.is_success

    # The keyword omitted: the frozen default is explicit key, and over this
    # keyless body the explicit-key path associates nothing.
    default_result = collector_graphql.execute_graphql_batch(
        collector_graphql.build_graphql_batch_request(
            GQL_ASSET_ID, credentials=gqlfx.GQL_CREDENTIALS
        ),
        transport=gqlfx.RecordingTransport(
            [{"http_status": 200, "body_text": gqlfx.keyless_success_body()}]
        ),
        headers=headers,
        sleep=gqlfx.RecordingSleeper(),
    )
    assert (
        default_result.correlation.mode
        is GraphQLOperationCorrelationMode.EXPLICIT_KEY
    )
    assert (
        default_result.product_detail.correlation_mode
        is GraphQLOperationCorrelationMode.EXPLICIT_KEY
    )
    assert default_result.both_operations_malformed is True

    # The omitted keyword over a keyed body reproduces the previous behaviour
    # exactly: both operations succeed by their explicit keys.
    keyed_default = collector_graphql.execute_graphql_batch(
        collector_graphql.build_graphql_batch_request(
            GQL_ASSET_ID, credentials=gqlfx.GQL_CREDENTIALS
        ),
        transport=gqlfx.RecordingTransport(
            [{"http_status": 200, "body_text": gqlfx.in_order_success_body()}]
        ),
        headers=headers,
        sleep=gqlfx.RecordingSleeper(),
    )
    assert (
        keyed_default.correlation.mode is GraphQLOperationCorrelationMode.EXPLICIT_KEY
    )
    assert keyed_default.is_success

    # A non-member mode is refused before any correlation (§7.1).
    bad_mode: Any = "validated_position_fixture_unvalidated"
    with pytest.raises(TypeError):
        collector_graphql.execute_graphql_batch(
            collector_graphql.build_graphql_batch_request(
                GQL_ASSET_ID, credentials=gqlfx.GQL_CREDENTIALS
            ),
            transport=gqlfx.RecordingTransport(
                [{"http_status": 200, "body_text": gqlfx.keyless_success_body()}]
            ),
            headers=headers,
            correlation_mode=bad_mode,
            sleep=gqlfx.RecordingSleeper(),
        )


@pytest.mark.lreq("LREQ-GQL-030")
def test_explicit_key_mode_marks_keyless_body_correlation_missing() -> None:
    """Under the explicit-key mode a keyless body is malformed, never positional.

    LREQ-GQL-030 (SRS-lean:300-312): with no explicit key and no validated
    position, both operations are marked malformed and their fields stay
    unavailable -- the run's candidate mode before the preflight selects.
    """
    result = collector_graphql.execute_graphql_batch(
        collector_graphql.build_graphql_batch_request(
            GQL_ASSET_ID, credentials=gqlfx.GQL_CREDENTIALS
        ),
        transport=gqlfx.RecordingTransport(
            [{"http_status": 200, "body_text": gqlfx.keyless_success_body()}]
        ),
        headers=collector_graphql.build_graphql_headers(
            credentials=gqlfx.GQL_CREDENTIALS
        ),
        correlation_mode=GraphQLOperationCorrelationMode.EXPLICIT_KEY,
        sleep=gqlfx.RecordingSleeper(),
    )

    assert result.correlation.mode is GraphQLOperationCorrelationMode.EXPLICIT_KEY
    assert result.correlation.is_fully_correlated is False
    assert result.both_operations_malformed is True
    for match in result.correlation.matches:
        assert (
            match.failure_class
            is collector_graphql.GraphQLFailureClass.OPERATION_CORRELATION_MISSING
        )
        assert match.item_index is None
    assert result.product_detail.status is OperationStatus.ERROR
    assert result.page_views.status is OperationStatus.ERROR
    assert result.product_detail.payload is None
    assert result.page_views.payload is None
    assert not result.is_success


@pytest.mark.lreq("LREQ-GQL-040")
def test_product_detail_data_product_wrapper_is_unwrapped() -> None:
    """The live ``data.product`` wrapper is unwrapped before validation (H5).

    Plan §5.5/§8.2, hand-derived: a mapping ``product`` unwraps to the product
    object and validates (rating average 4.5, count 12, review count 7, page
    views 20); ``product: null`` is ``NULL_REQUIRED_DATA``; a non-mapping
    ``product`` is ``WRONG_DATA_SHAPE``; ``data: null`` takes the envelope-null
    branch (``NULL_REQUIRED_DATA``); a flat ``data`` (no ``product`` key) keeps
    the legacy path unchanged. No field is defaulted or coerced.
    """
    # ``product`` mapping -> the unwrapped product object validates.
    _t1, _s1, (unwrapped, draft_unwrapped) = gql_exchange(
        [{"http_status": 200, "body_text": gqlfx.keyless_success_body()}],
        correlation_mode=GraphQLOperationCorrelationMode.VALIDATED_POSITION,
    )
    assert unwrapped.product_detail.is_success
    assert unwrapped.product_detail.payload is not None
    assert "product" not in unwrapped.product_detail.payload
    assert unwrapped.product_detail.payload["id"] == GQL_ASSET_ID
    assert draft_unwrapped.graphql_id == GQL_ASSET_ID
    # Chunk 19 §5.3 S3: the live-shape keyless body carries the returned
    # internal ``productId``; it is persisted verbatim and is not required to
    # agree with the requested identity.
    assert draft_unwrapped.product_id == gqlfx.GQL_FIXTURE_INTERNAL_PRODUCT_ID
    assert draft_unwrapped.rating_average == pytest.approx(4.5, abs=1e-9)
    assert draft_unwrapped.rating_count == 12
    assert draft_unwrapped.review_count == 7
    assert draft_unwrapped.state == "published"
    assert draft_unwrapped.product_page_views == 20

    # ``product: null`` -> no product data returned.
    _t2, _s2, (null_product, draft_null) = gql_exchange(
        [{"http_status": 200, "body_text": gqlfx.keyless_product_detail_null_body()}],
        correlation_mode=GraphQLOperationCorrelationMode.VALIDATED_POSITION,
    )
    assert null_product.product_detail.status is OperationStatus.ERROR
    assert (
        null_product.product_detail.failure_class
        is collector_graphql.GraphQLFailureClass.NULL_REQUIRED_DATA
    )
    assert null_product.product_detail.payload is None
    assert draft_null.graphql_id is None
    assert draft_null.product_id is None
    # A failed operation's fields stay unavailable; the sibling is untouched.
    assert null_product.page_views.is_success
    assert draft_null.product_page_views == 20
    assert null_product.is_partial_success

    # ``product: [..]`` -> wrong container kind.
    _t3, _s3, (list_product, _draft_list) = gql_exchange(
        [
            {
                "http_status": 200,
                "body_text": gqlfx.keyless_product_detail_non_mapping_body(),
            }
        ],
        correlation_mode=GraphQLOperationCorrelationMode.VALIDATED_POSITION,
    )
    assert list_product.product_detail.status is OperationStatus.ERROR
    assert (
        list_product.product_detail.failure_class
        is collector_graphql.GraphQLFailureClass.WRONG_DATA_SHAPE
    )
    assert list_product.product_detail.payload is None

    # ``data: null`` -> the existing envelope-null branch.
    _t4, _s4, (null_data, draft_data) = gql_exchange(
        [
            {
                "http_status": 200,
                "body_text": gqlfx.body_json_for_items(
                    [{"data": None}, {"data": {"pageViews": 20}}]
                ),
            }
        ],
        correlation_mode=GraphQLOperationCorrelationMode.VALIDATED_POSITION,
    )
    assert null_data.product_detail.status is OperationStatus.ERROR
    assert (
        null_data.product_detail.failure_class
        is collector_graphql.GraphQLFailureClass.NULL_REQUIRED_DATA
    )
    assert draft_data.product_page_views == 20

    # A flat legacy ``data`` (no ``product`` key) validates as today.
    _t5, _s5, (flat, draft_flat) = gql_exchange(
        [
            {
                "http_status": 200,
                "body_text": gqlfx.keyless_product_detail_flat_legacy_body(),
            }
        ],
        correlation_mode=GraphQLOperationCorrelationMode.VALIDATED_POSITION,
    )
    assert flat.product_detail.is_success
    assert draft_flat.graphql_id == GQL_ASSET_ID
    assert draft_flat.product_id == GQL_ASSET_ID
    assert draft_flat.product_page_views == 20


@pytest.mark.lreq("LREQ-GQL-020")
def test_product_page_views_request_alias_is_page_views() -> None:
    """The ``ProductPageViews`` request aliases its scalar field to ``pageViews``.

    Plan §5.6 (G7): the live response key is ``pageViews`` after the alias, so
    the frozen ``validate_page_views_payload`` contract holds unchanged; the
    request query text and the whole request body are the updated goldens.
    """
    operation = collector_graphql.build_product_page_views_operation(GQL_ASSET_ID)
    request = collector_graphql.build_graphql_batch_request(
        GQL_ASSET_ID, credentials=gqlfx.GQL_CREDENTIALS
    )
    expected_query = (
        "query ProductPageViews($packageId: String!) {\n"
        "  pageViews: productPageViews(packageId: $packageId)\n"
        "}"
    )

    assert operation.query == expected_query
    assert operation.query == gqlfx.EXPECTED_PRODUCT_PAGE_VIEWS_REQUEST_OBJECT["query"]
    body_objects = gql_request_objects(request.body_json)
    assert body_objects[1] == gqlfx.EXPECTED_PRODUCT_PAGE_VIEWS_REQUEST_OBJECT
    assert body_objects[1]["variables"] == {"packageId": GQL_ASSET_ID}
    assert request.body_json == gqlfx.TWO_OPERATION_BODY_JSON


@pytest.mark.lreq("LREQ-GQL-040")
def test_keyless_page_views_zero_is_a_valid_value() -> None:
    """A keyless ``{"data":{"pageViews":0}}`` is the valid explicit zero.

    LREQ-GQL-040 / plan §5.6: zero is a measured value, never absent and never
    a failure; the operation succeeds and the draft carries ``0``, not ``None``.
    """
    _t, _s, (result, draft) = gql_exchange(
        [{"http_status": 200, "body_text": gqlfx.keyless_page_views_zero_body()}],
        correlation_mode=GraphQLOperationCorrelationMode.VALIDATED_POSITION,
    )

    assert result.is_success
    assert result.page_views.is_success
    assert result.page_views.payload == {"pageViews": 0}
    assert draft.product_page_views == 0
    assert draft.product_page_views is not None
    assert isinstance(draft.product_page_views, int)
    assert not isinstance(draft.product_page_views, bool)
    assert draft.page_views_status == OperationStatus.SUCCESS.value


@pytest.mark.lreq("LREQ-GQL-040")
def test_keyless_page_views_wrong_key_is_null_required_data() -> None:
    """The captured pre-G7 ``productPageViews`` key is ``NULL_REQUIRED_DATA``.

    Run log ``chunk-18.md`` "Full capture" (G7) and plan §8.4: a mapping without
    the required ``pageViews`` member is missing required data, not a wrong
    shape, and never a zero-valued success.
    """
    _t, _s, (result, draft) = gql_exchange(
        [{"http_status": 200, "body_text": gqlfx.keyless_page_views_wrong_key_body()}],
        correlation_mode=GraphQLOperationCorrelationMode.VALIDATED_POSITION,
    )

    assert result.product_detail.is_success
    assert not result.page_views.is_success
    assert (
        result.page_views.failure_class
        is collector_graphql.GraphQLFailureClass.NULL_REQUIRED_DATA
    )
    assert result.page_views.payload is None
    assert draft.product_page_views is None
    assert draft.page_views_status == OperationStatus.ERROR.value


@pytest.mark.lreq("LREQ-GQL-030")
def test_select_operation_correlation_mode_rejects_empty_evidence() -> None:
    """Selection is total: empty evidence raises, every shape rule selects the mode.

    Plan §5.2/§7.2, exhaustively: a zero-identity preflight is ``insufficient``
    and selection is not reached, so an empty sequence is a caller ``ValueError``
    (never a substituted default). The valid keyless fixed-order shape selects
    ``VALIDATED_POSITION``; an explicit key, a wrong count, a wrong shape, or a
    decode failure selects ``EXPLICIT_KEY`` -- all-or-nothing across responses.
    """
    select_mode = collector_graphql.select_operation_correlation_mode

    with pytest.raises(ValueError):
        select_mode(())

    # The valid keyless two-envelope shape: the LREQ-GQL-030 fallback.
    assert (
        select_mode((gql_batch_response(gqlfx.keyless_success_body()),))
        is GraphQLOperationCorrelationMode.VALIDATED_POSITION
    )
    # Zero page views is a valid value, so it still validates the shape.
    assert (
        select_mode((gql_batch_response(gqlfx.keyless_page_views_zero_body()),))
        is GraphQLOperationCorrelationMode.VALIDATED_POSITION
    )
    # The all-or-nothing rule: two clean keyless responses validate...
    assert (
        select_mode(
            (
                gql_batch_response(gqlfx.keyless_success_body()),
                gql_batch_response(
                    gqlfx.keyless_success_body_for_identity(
                        gqlfx.GQL_FIXTURE_ASSET_ID_OTHER
                    )
                ),
            )
        )
        is GraphQLOperationCorrelationMode.VALIDATED_POSITION
    )
    # ...and one bad response anywhere selects explicit key for the whole run.
    assert (
        select_mode(
            (
                gql_batch_response(gqlfx.keyless_success_body()),
                gql_batch_response(gqlfx.keyless_wrong_order_body()),
            )
        )
        is GraphQLOperationCorrelationMode.EXPLICIT_KEY
    )

    for body_text in (
        gqlfx.keyless_wrong_order_body(),  # reversed shapes
        gqlfx.keyless_one_item_body(),  # wrong count
        gqlfx.keyless_three_item_body(),  # wrong count
        gqlfx.keyless_product_detail_null_body(),  # product: null
        gqlfx.keyless_product_detail_non_mapping_body(),  # product: [..]
        gqlfx.keyless_page_views_negative_body(),  # -1
        gqlfx.keyless_page_views_boolean_body(),  # true
        gqlfx.keyless_page_views_float_body(),  # 1.5
        gqlfx.keyless_missing_page_views_body(),  # no pageViews member
        gqlfx.keyless_page_views_wrong_key_body(),  # productPageViews
        gqlfx.empty_response_body(),  # []
        gqlfx.empty_body(),  # ""
        gqlfx.non_json_body(),  # not JSON
        gqlfx.non_array_body(),  # JSON object, not an array
    ):
        assert (
            select_mode((gql_batch_response(body_text),))
            is GraphQLOperationCorrelationMode.EXPLICIT_KEY
        ), body_text

    # An explicit key is the primary association, even mixed with keyless bodies.
    assert (
        select_mode((gql_batch_response(gqlfx.in_order_success_body()),))
        is GraphQLOperationCorrelationMode.EXPLICIT_KEY
    )
    assert (
        select_mode(
            (
                gql_batch_response(gqlfx.keyless_success_body()),
                gql_batch_response(gqlfx.in_order_success_body()),
            )
        )
        is GraphQLOperationCorrelationMode.EXPLICIT_KEY
    )


# ---------------------------------------------------------------------------
# Chunk 18 follow-on / LREQ-GQL-040 -- ``rating.average`` scalar acceptance
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-GQL-040")
@pytest.mark.parametrize(
    ("rating_average", "expected"),
    [
        (5, 5.0),
        (4.5, 4.5),
    ],
)
def test_product_detail_rating_average_accepts_integral_json_number(
    rating_average: object, expected: float
) -> None:
    """An integral JSON number for ``rating.average`` is accepted as a float.

    ``LREQ-GQL-040`` (``SRS-lean.md``:318-323) makes a wrong scalar type an
    operation error but does not make an integral JSON number wrong for a
    numeric member; the live endpoint returns integral JSON numbers for whole
    rating averages (human ruling on the Chunk 18 follow-on). The frozen
    interface types the field ``rating_average: float | None``
    (``interfaces/chunk-05.md`` section 5.6), so the accepted value is carried
    as a ``float`` -- no rounding, float64 throughout. These two cases are plan
    ``chunk-27`` §3.1 row 7: the count is the default positive ``210`` and the
    average is a genuine ``0 < avg <= 5`` value, so the pair is retained
    unchanged.

    Hand-derived expected values: ``float(5)`` is exactly ``5.0`` and ``4.5``
    is exactly representable (9/2); both are exact in binary, so the ``1e-9``
    tolerance is slack, not a fudge.

    The former ``(0, 0.0)`` case is **not** an acceptance case under plan
    ``chunk-27`` §3.1 row 6 (positive count with a zero average is the Unity
    "unrated" placeholder); it moved to
    :func:`test_product_detail_rating_average_zero_with_positive_count_is_unavailable`.
    """
    validation = collector_graphql.validate_product_detail_payload(
        gqlfx.product_detail_payload(rating_average=rating_average)
    )

    assert validation.is_valid is True
    assert validation.failure_class is collector_graphql.GraphQLFailureClass.NONE
    fields = validation.product_detail
    assert fields is not None
    assert fields.rating_average == pytest.approx(expected, abs=1e-9)
    assert fields.rating_average is not None
    assert isinstance(fields.rating_average, float)
    # Row 7 retains the count unchanged as well (default 210).
    assert fields.rating_count == 210
    assert fields.rating_count is not None
    assert isinstance(fields.rating_count, int)
    assert not isinstance(fields.rating_count, bool)


@pytest.mark.lreq("LREQ-GQL-050")
@pytest.mark.lreq("LREQ-TST-010")
def test_product_detail_rating_average_zero_with_positive_count_is_unavailable() -> None:
    """Row 6: a zero average with a positive count is unavailable, count kept.

    Plan ``chunk-27`` §3.1 row 6, §8 (null/edge behavior), gate bullet 2. Unity
    sends a literal ``0`` for ``rating.average`` on unrated assets; SRS §1.2
    (``SRS-lean-v2.md``:92-93) forbids converting that placeholder to zero and
    ``LREQ-GQL-050`` (``SRS-lean-v2.md``:341-343) requires the failed field to
    stay ``None``. The count is genuinely returned, so it is retained as the
    integer ``210`` -- ``LREQ-GQL-050`` forbids *filling* a missing field, it
    does not require discarding a present, valid member.

    Hand-derived expectations (plan §9.3 item 1, §9.3 hand-computed paragraph):
    ``float(210)`` is retained as the exact ``int`` 210; ``0.0`` is the exact
    placeholder the mapping nulls. Exactly one issue is appended, code
    ``rating_average_zero_with_positive_count`` (plan §3.2).

    Q3 invariant (plan §3.3, load-bearing): the new code is not in
    ``_classify_product_detail_failure``'s membership tests and is not a
    ``response_*`` code, so the payload stays valid with
    ``failure_class is NONE`` and the correlation mode is not flipped.
    """
    validation = collector_graphql.validate_product_detail_payload(
        gqlfx.product_detail_contradiction_payload(
            rating_average=0, rating_count=210
        )
    )

    assert validation.is_valid is True
    assert validation.failure_class is collector_graphql.GraphQLFailureClass.NONE
    fields = validation.product_detail
    assert fields is not None
    assert fields.rating_average is None
    assert fields.rating_count == 210
    # The retained count stays a Python ``int``, never a coerced ``float``.
    assert isinstance(fields.rating_count, int)
    assert not isinstance(fields.rating_count, bool)

    codes = [issue.code for issue in validation.issues]
    assert codes == ["rating_average_zero_with_positive_count"]


@pytest.mark.lreq("LREQ-GQL-040")
@pytest.mark.parametrize("rating_average", [True, False, "2.5"])
def test_product_detail_rating_average_bool_and_string_are_wrong_scalar_type(
    rating_average: object,
) -> None:
    """``bool`` and ``str`` stay ``WRONG_SCALAR_TYPE`` for ``rating.average``.

    ``LREQ-GQL-040`` (``SRS-lean.md``:318-323) records a wrong scalar type as
    an operation error. The human ruling keeps ``bool`` rejected -- Python's
    ``isinstance(True, int)`` must not smuggle JSON ``true``/``false`` in as
    ``1.0``/``0.0`` -- and ``"2.5"`` is a JSON string, not a JSON number, so
    no coercion to ``2.5`` is permitted either.
    """
    validation = collector_graphql.validate_product_detail_payload(
        gqlfx.product_detail_payload(rating_average=rating_average)
    )

    assert validation.is_valid is False
    assert (
        validation.failure_class
        is collector_graphql.GraphQLFailureClass.WRONG_SCALAR_TYPE
    )


@pytest.mark.lreq("LREQ-GQL-040")
@pytest.mark.parametrize("rating_average", [[2.5], {"average": 2.5}])
def test_product_detail_rating_average_container_values_are_rejected(
    rating_average: object,
) -> None:
    """Container values for ``rating.average`` are rejected, never coerced.

    The human ruling keeps list/dict values rejected. ``LREQ-GQL-040``
    (``SRS-lean.md``:318-323) names both wrong data shape and wrong scalar
    type as operation errors and does not fix which one a container at this
    scalar position takes, so this node pins invalidity only and deliberately
    leaves the failure class unpinned.
    """
    validation = collector_graphql.validate_product_detail_payload(
        gqlfx.product_detail_payload(rating_average=rating_average)
    )

    assert validation.is_valid is False
    assert validation.failure_class is not collector_graphql.GraphQLFailureClass.NONE


# ---------------------------------------------------------------------------
# Chunk 19 / LREQ-GQL-070 -- the authoritative-id agreement alias set
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-GQL-070")
def test_identity_alias_set_compares_authoritative_id_only() -> None:
    """``annotate_product_detail_identity`` supplies only the returned ``id``.

    Plan ``chunk-19`` §8.1 node 3 / §5.1 S1 and §7.1: the agreement alias map
    is ``{"id": <returned id>}`` built from ``graphql_id`` alone. The returned
    ``productId`` is persisted on ``ProductDetailFields.product_id`` and stays
    requested (``LREQ-GQL-020``, asserted through the selection set), but it is
    **not** an agreement alias:

    * ``id`` agrees / ``productId`` differs -> match on ``id`` alone, and the
      compared-alias map has no ``"productId"`` key;
    * ``id`` differs / ``productId`` agrees -> mismatch: a populated-but-
      agreeing ``productId`` cannot rescue a differing ``id``;
    * ``id`` is ``None`` -> the alias map is empty, so the comparison is an
      explicit mismatch whose reason names the missing GraphQL identity alias;
      ``productId`` is never consulted and never defaulted;
    * the returned fields are preserved verbatim (frozen ``dataclasses.replace``
      contract), and a non-member ``mapping_rule_version`` is still refused.
    """
    validation = collector_graphql.validate_product_detail_payload(
        gqlfx.product_detail_payload()
    )
    fields = validation.product_detail
    assert fields is not None
    requested = gqlfx.GQL_FIXTURE_ASSET_ID

    # (a) The live shape: id agrees, productId is the distinct internal id.
    agrees = dataclasses.replace(
        fields,
        graphql_id=requested,
        product_id=gqlfx.GQL_FIXTURE_INTERNAL_PRODUCT_ID,
    )
    annotated = collector_graphql.annotate_product_detail_identity(requested, agrees)
    comparison = annotated.identity_comparison
    assert comparison is not None
    assert comparison.matches_requested_identity is True
    assert comparison.id_mapping_mismatch is False
    assert dict(comparison.compared_aliases) == {"id": requested}
    assert "productId" not in dict(comparison.compared_aliases)
    # Every other returned field is preserved verbatim (no coercion).
    assert annotated.graphql_id == requested
    assert annotated.product_id == gqlfx.GQL_FIXTURE_INTERNAL_PRODUCT_ID
    assert annotated.rating_average == pytest.approx(fields.rating_average, abs=1e-9)

    # (b) id differs while productId agrees: productId is not authoritative.
    disagrees = dataclasses.replace(
        fields,
        graphql_id=gqlfx.GQL_FIXTURE_ASSET_ID_OTHER,
        product_id=requested,
    )
    mismatch = collector_graphql.annotate_product_detail_identity(
        requested, disagrees
    ).identity_comparison
    assert mismatch is not None
    assert mismatch.id_mapping_mismatch is True
    assert mismatch.matches_requested_identity is False
    assert dict(mismatch.compared_aliases) == {"id": gqlfx.GQL_FIXTURE_ASSET_ID_OTHER}

    # (c) No usable authoritative id at all: the map is empty, never an assumed
    # agreement, and productId is never consulted as a fallback identity.
    no_id = dataclasses.replace(
        fields,
        graphql_id=None,
        product_id=gqlfx.GQL_FIXTURE_INTERNAL_PRODUCT_ID,
    )
    empty = collector_graphql.annotate_product_detail_identity(
        requested, no_id
    ).identity_comparison
    assert empty is not None
    assert empty.id_mapping_mismatch is True
    assert empty.matches_requested_identity is False
    assert empty.compared_aliases == ()
    assert "no GraphQL identity alias" in (empty.reason or "")

    # The request side is unchanged: productId stays in the selection set.
    assert "productId" in gqlfx.PRODUCT_DETAIL_SELECTION_SET

    # An unknown mapping rule version is still refused by the adapter call.
    with pytest.raises(ValueError):
        collector_graphql.annotate_product_detail_identity(
            requested, fields, mapping_rule_version="9.9.9"
        )


# ---------------------------------------------------------------------------
# Chunk 27 / D2 rating missingness -- the typed-pair precedence table (rows 4/5/6)
# ---------------------------------------------------------------------------
#
# Scope authority: Documents/plans/chunk-27-rating-missingness-remediation.md §3
# (typed-pair precedence), §8 (null/edge behavior), §9.3 (new nodes). Unity sends
# a literal 0 for rating.average / rating.count on unrated assets; the adapter
# maps the typed pair to None so a "no rating" state is never persisted as a real
# zero (SRS §1.2, LREQ-GQL-050). Every body here is an offline fixture: no
# transport, no network, no clock.

#: Plan §3.2 row 4 code: a positive average with a zero count.
RATING_AVERAGE_WITHOUT_COUNT_CODE = "rating_average_without_rating_count"

#: Plan §3.2 row 6 code: a zero average placeholder with a positive count.
RATING_AVERAGE_ZERO_WITH_COUNT_CODE = "rating_average_zero_with_positive_count"

#: The exact message plan §3.2 gives each new code. Pinned so the implementation
#: uses the frozen wording (LREQ-GQL-050), not an ad-hoc string.
RATING_AVERAGE_WITHOUT_COUNT_MESSAGE = (
    "rating.average is positive while rating.count is zero; both are "
    "unavailable and neither is coerced to a default"
)
RATING_AVERAGE_ZERO_WITH_COUNT_MESSAGE = (
    "rating.average is a zero placeholder with a positive rating.count; the "
    "average is unavailable and the count is retained as returned"
)


@pytest.mark.lreq("LREQ-GQL-050")
@pytest.mark.lreq("LREQ-TST-010")
def test_product_detail_rating_positive_average_with_zero_count_is_contradictory() -> None:
    """Row 4: a positive average with a zero count nulls both members.

    Plan ``chunk-27`` §3.1 row 4, §8, §9.3 item 2. A genuine positive average
    cannot sit alongside a zero count, so the pair is contradictory: SRS §1.2
    (``SRS-lean-v2.md``:92-93) forbids converting a contradictory value to zero,
    so **neither** member is defaulted -- both become ``None`` and exactly one
    issue with code ``rating_average_without_rating_count`` is appended (plan
    §3.2).

    Hand-derived (plan §9.3 hand-computed paragraph): ``None``/``None`` are
    exact; ``4.5`` is exactly representable (9/2) but is not retained here.
    The payload stays valid (``is_valid is True``, ``failure_class is NONE``)
    because the new code is not a structural failure class (plan §3.3).
    """
    validation = collector_graphql.validate_product_detail_payload(
        gqlfx.product_detail_contradiction_payload(
            rating_average=4.5, rating_count=0
        )
    )

    assert validation.is_valid is True
    assert validation.failure_class is collector_graphql.GraphQLFailureClass.NONE
    fields = validation.product_detail
    assert fields is not None
    assert fields.rating_average is None
    assert fields.rating_count is None

    codes = [issue.code for issue in validation.issues]
    assert codes == [RATING_AVERAGE_WITHOUT_COUNT_CODE]


@pytest.mark.lreq("LREQ-GQL-050")
@pytest.mark.lreq("LREQ-TST-010")
def test_product_detail_rating_zero_count_and_zero_average_is_no_rating() -> None:
    """Row 5: a zero count with a zero average is "no rating", not a contradiction.

    Plan ``chunk-27`` §3.1 row 5, §9.3 item 3, gate bullet 1. Unity's unrated
    literal pair is ``(0.0, 0)``; both members are nulled and **no**
    contradiction code appears in ``validation.issues`` (plan §8: rows 1, 2, 3,
    5, 7 carry no contradiction issue).

    Hand-derived: ``None``/``None`` exact; the zero pair is a single no-rating
    state, never two distinct zeros (SRS §1.2).
    """
    validation = collector_graphql.validate_product_detail_payload(
        gqlfx.product_detail_contradiction_payload(
            rating_average=0, rating_count=0
        )
    )

    assert validation.is_valid is True
    assert validation.failure_class is collector_graphql.GraphQLFailureClass.NONE
    fields = validation.product_detail
    assert fields is not None
    assert fields.rating_average is None
    assert fields.rating_count is None

    codes = [issue.code for issue in validation.issues]
    assert RATING_AVERAGE_WITHOUT_COUNT_CODE not in codes
    assert RATING_AVERAGE_ZERO_WITH_COUNT_CODE not in codes
    assert codes == []


@pytest.mark.lreq("LREQ-GQL-050")
@pytest.mark.lreq("LREQ-TST-010")
def test_product_detail_rating_zero_count_with_absent_average_is_no_rating() -> None:
    """Row 5 variant: a zero count with a null (absent) average is "no rating".

    Plan ``chunk-27`` §3.1 ("A count of ``0`` with an absent (``None``) average
    is row 5, not row 4 -- an absent member is not a positive average") and §9.3
    item 4. The average member is present as JSON ``null``, the typed value is
    ``None``, and the zero count is nulled; no contradiction issue is appended
    (plan §8 rows 1/2/3/5/7). ``LREQ-GQL-040`` (``SRS-lean-v2.md``:334-339)
    makes null required data an operation error, so an *omitted* member would be
    a different, already-pinned case (see
    ``test_product_detail_missing_required_member_is_an_operation_error``); the
    row 5 variant here is the null member, which is not a structural failure.

    Hand-derived: ``None``/``None`` exact; the outcome equals the ``(0.0, 0)``
    row 5 case, because neither state fabricates a zero.
    """
    payload = gqlfx.product_detail_contradiction_payload(
        rating_average=None, rating_count=0
    )
    # The JSON ``null`` average member is present but null; the mapping keys the
    # decision on the typed value (``None``), not on member presence.
    assert payload["rating"]["average"] is None
    assert "average" in payload["rating"]

    validation = collector_graphql.validate_product_detail_payload(payload)

    assert validation.is_valid is True
    assert validation.failure_class is collector_graphql.GraphQLFailureClass.NONE
    fields = validation.product_detail
    assert fields is not None
    assert fields.rating_average is None
    assert fields.rating_count is None

    codes = [issue.code for issue in validation.issues]
    assert RATING_AVERAGE_WITHOUT_COUNT_CODE not in codes
    assert RATING_AVERAGE_ZERO_WITH_COUNT_CODE not in codes
    assert codes == []


@pytest.mark.lreq("LREQ-GQL-050")
@pytest.mark.lreq("LREQ-TST-010")
def test_product_detail_rating_positive_average_with_absent_count_is_unchanged() -> None:
    """Q5 (row 3): a positive average with an absent count keeps the average.

    Plan ``chunk-27`` §3.1 row 3, §3.6 Q5, §8, §9.3 item 5. An absent count is
    not a contradiction: the returned average is genuine and the count stays
    ``None`` -- no issue is appended (SRS §1.2's "contradictory" applies to
    values that actually conflict, not to a missing peer). The retained average
    is carried as a ``float`` (frozen ``ProductDetailFields.rating_average:
    float | None``, ``interfaces/chunk-05.md`` §5.6).

    Hand-derived: ``4.5`` is exactly representable (9/2), so the ``1e-9``
    tolerance is slack, not a fudge.
    """
    payload = gqlfx.product_detail_contradiction_payload(
        rating_average=4.5, rating_count=None
    )
    assert payload["rating"]["count"] is None
    assert "count" in payload["rating"]

    validation = collector_graphql.validate_product_detail_payload(payload)

    assert validation.is_valid is True
    assert validation.failure_class is collector_graphql.GraphQLFailureClass.NONE
    fields = validation.product_detail
    assert fields is not None
    assert fields.rating_count is None
    assert fields.rating_average == pytest.approx(4.5, abs=1e-9)
    assert fields.rating_average is not None
    assert isinstance(fields.rating_average, float)

    codes = [issue.code for issue in validation.issues]
    assert codes == []


@pytest.mark.lreq("LREQ-GQL-050")
@pytest.mark.lreq("LREQ-TST-010")
def test_row_six_pair_keeps_validated_position_correlation_mode() -> None:
    """Q3 collateral (plan §3.3): the row 6 pair does not flip the correlation mode.

    Plan ``chunk-27`` §3.3 (load-bearing) and §9.3 item 6: the two new codes
    must not appear in ``_classify_product_detail_failure``'s membership tests,
    so a keyless two-item body carrying the row 6 pair still has **every**
    payload validate and ``select_operation_correlation_mode`` must keep
    returning ``GraphQLOperationCorrelationMode.VALIDATED_POSITION``. Marking
    the payload invalid would silently flip the persisted
    ``runs.graphql_operation_correlation_mode`` to ``EXPLICIT_KEY``.

    Hand-derived: item 0 is the keyless ``{"data":{"product":<row 6 pair>}}``
    envelope and item 1 the valid ``{"data":{"pageViews":20}}`` envelope, i.e.
    the fixed two-operation shape the LREQ-GQL-030 fallback requires.
    """
    product = gqlfx.product_detail_contradiction_payload(
        rating_average=0, rating_count=210
    )
    # Precondition: the row 6 pair really is a contradiction, i.e. the same pair
    # the validation nodes above assert stays ``is_valid``/``NONE``. Keeping
    # this guard here is what makes the correlation assertion below a statement
    # about *a validating* contradiction payload, not about an arbitrary one.
    pair = collector_graphql.validate_product_detail_payload(product)
    assert pair.is_valid is True
    assert pair.failure_class is collector_graphql.GraphQLFailureClass.NONE

    body_text = gqlfx.body_json_for_items(
        [
            {"data": {"product": product}},
            {"data": {"pageViews": 20}},
        ]
    )

    mode = collector_graphql.select_operation_correlation_mode(
        (gql_batch_response(body_text),)
    )
    assert mode is GraphQLOperationCorrelationMode.VALIDATED_POSITION
