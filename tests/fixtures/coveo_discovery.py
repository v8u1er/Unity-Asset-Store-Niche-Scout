"""Deterministic, offline fixtures for the Chunk 3 Coveo discovery suite.

Everything here is local and hand-derived. No fixture contacts the network, reads
the system clock, or carries a real credential.

**Request side — anchored to the capture.** ``config/coveo_search_template.json``
is the operator's captured discovery request plus its provenance header; the
request fixtures load it read-only through ``load_coveo_search_template`` and
apply the four mechanical edits of the plan's §12.6, so a fixture can never drift
from the committed capture. The violating variants (missing file, hash mismatch,
an injected ``q``, a foreign facet) exist so the adapter's rejections are
exercised rather than assumed.

**Response side — hand-derived assumptions.** The SRS forbids live calls in
tests and the capture covers the request only, so the page and record shapes
below are hand-derived assumptions about the live contract (plan §12.9), not
capture-derived facts.

**Live-form vocabulary (Chunk 14).** The ``LIVE_FORM_*`` literals encode the
live facet/record shape the human probe observed: lowercase slugs joined by the
exact ``" > "`` sequence, leading-space child entries in a multi-valued
``ec_category``, and a canonical slash-form round-trip. They are hand-derived
offline literals (plan §8), so the compatibility tests ground on them rather
than on the committed regeneration.

Nothing here writes into ``config/``: the only path under it that is read is the
committed capture, and ``configured_config`` uses the committed taxonomy path
solely as a harmless ``NicheScoutConfig`` option value.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence

from fixtures.config_fixtures import (
    DEFAULT_CATEGORIES,
    DEFAULT_TOML_BODY,
    MOCK_ENVIRONMENT,
    TAXONOMY_FIXTURE,
    write_toml,
)

from niche_scout import collector_coveo
from niche_scout.config import Credentials, get_credentials, load_config

__all__ = [
    "BEARER_TOKEN",
    "CAPTURE_PATH",
    "CAPTURED_STATE_BY_CATEGORY",
    "COVEO_FIXTURE_CATEGORY",
    "COVEO_FIXTURE_CATEGORY_OTHER",
    "CREDENTIALS",
    "CREDENTIALS_WITH_BEARER_SCHEME",
    "DROPPED_CAPTURE_FACET_IDS",
    "EXHAUSTED_CAPTURE_FACET_IDS",
    "LIVE_FORM_ABSENT_FACET_VALUE",
    "LIVE_FORM_CHILD_VALUE",
    "LIVE_FORM_CHILD_VALUE_CANONICAL",
    "LIVE_FORM_FACET_VALUE",
    "LIVE_FORM_FACET_VALUE_CANONICAL",
    "LIVE_FORM_INVENTORY",
    "LIVE_FORM_INVENTORY_CANONICAL",
    "LIVE_FORM_MULTI_VALUED_CATEGORY",
    "LIVE_FORM_PARENT_VALUE",
    "LIVE_FORM_PARENT_VALUE_CANONICAL",
    "LIVE_FORM_SEPARATOR",
    "LIVE_RAW_RECORD_FIELDS",
    "live_raw_page",
    "live_raw_record",
    "live_raw_summary_record",
    "MALFORMED_PAGE_JSON",
    "NON_ADVANCING_PAGE_COUNT",
    "REFERENCE_UTC",
    "TAXONOMY_PATH_FIXTURE",
    "TAXONOMY_PAYLOAD",
    "TEMPLATE_HEADER_FIELDS",
    "URI_FALLBACK_RECORD",
    "URL_FALLBACK_RECORD",
    "canonical_sections",
    "canonical_text",
    "capture_sha256",
    "conflicting_record",
    "configured_config",
    "count_containers",
    "credentials",
    "credentials_from_environment",
    "env_credentials_with_bearer_scheme",
    "live_form_record",
    "live_form_taxonomy_payload",
    "load_template",
    "make_page",
    "malformed_page",
    "page_with_foreign_facet",
    "page_with_q_field",
    "record",
    "record_without_identity",
    "records",
    "request_body",
    "template_body",
    "template_body_text",
    "uri_fallback_record",
    "utterly_empty_page",
    "write_mismatched_template",
    "write_missing_template_path",
    "write_template",
]

ROOT = Path(__file__).resolve().parents[2]

#: The capture this chunk replays. Read-only: no fixture writes to it.
CAPTURE_PATH = ROOT / "config" / "coveo_search_template.json"

#: The committed taxonomy file, used only as a ``NicheScoutConfig`` option value
#: that keeps every config path pointing outside the pytest temp tree. The file
#: itself is never opened, read, or written by this suite.
TAXONOMY_PATH_FIXTURE = ROOT / "config" / "category_taxonomy.json"

#: An explicit, timezone-aware freshness reference; no test reads the clock. It is
#: derived from the committed taxonomy's own capture instant (30-day window,
#: ``MAX_TAXONOMY_AGE_DAYS``) and advanced by the captured request's clock offset
#: to the discovery capture (2026-09-17T04:28:28.915Z), so every discovery test
#: validates against a fresh taxonomy without editing ``config/``.
TAXONOMY_CAPTURED_AT_UTC = datetime(2026, 1, 5, 0, 0, 0, tzinfo=timezone.utc)
CAPTURE_CLOCK_OFFSET = timedelta(
    days=1, hours=4, minutes=28, seconds=28, milliseconds=915
)
REFERENCE_UTC = TAXONOMY_CAPTURED_AT_UTC + CAPTURE_CLOCK_OFFSET

#: Facet ids the capture carried that this adapter deliberately drops (§12.1).
DROPPED_CAPTURE_FACET_IDS: tuple[str, ...] = ("publisher_name",)

#: The capture's other four facets: dropped as well, because a facet returns a
#: separate aggregation no requirement consumes (plan §12.1, R-D).
EXHAUSTED_CAPTURE_FACET_IDS: tuple[str, ...] = (
    "ec_sale_filters",
    "ec_price_filter",
    "ec_rating",
    "first_published_at",
)

#: Provenance-header members the capture must carry.
TEMPLATE_HEADER_FIELDS: tuple[str, ...] = (
    "schema_version",
    "captured_at_utc",
    "source_url",
    "template_sha256",
    "organization_id",
    "endpoint",
)

#: The category under discovery in most tests: the chunk-22 committed default
#: selection's ``3d/characters/humanoids``, so the regenerated template facet
#: carries it and the builder marks exactly it ``selected``.
COVEO_FIXTURE_CATEGORY = "3d/characters/humanoids"

#: A second committed chunk-22 category, used for the multi-category isolation test.
COVEO_FIXTURE_CATEGORY_OTHER = "vfx/particles/fire-explosions"

#: The taxonomy payload every discovery test validates against.
TAXONOMY_PAYLOAD: dict[str, Any] = dict(TAXONOMY_FIXTURE)

#: How many identical consecutive pages a non-advancing endpoint serves before
#: the adapter gives up on the traversal.
NON_ADVANCING_PAGE_COUNT = 3

#: A page body that cannot be decoded as a JSON object.
MALFORMED_PAGE_JSON = b'{"results": ['

#: Offline credential material. The ``.env`` form stores the value with its
#: scheme already applied while ``config.get_credentials()`` only strips
#: whitespace (plan §12.8).
BEARER_TOKEN = "fixture-coveo-token"
CREDENTIALS = Credentials(
    coveo_token=BEARER_TOKEN, unity_csrf_token="fixture-csrf-token"
)
CREDENTIALS_WITH_BEARER_SCHEME = Credentials(
    coveo_token=f"Bearer {BEARER_TOKEN}", unity_csrf_token="fixture-csrf-token"
)


def credentials(*, with_scheme: bool = False) -> Credentials:
    """Return offline credentials; ``with_scheme`` reproduces the ``.env`` form."""
    return CREDENTIALS_WITH_BEARER_SCHEME if with_scheme else CREDENTIALS


def credentials_from_environment(*, with_scheme: bool = True) -> Credentials:
    """Return credentials built by ``config.get_credentials`` from a mock env.

    ``with_scheme`` stores the Coveo value as ``"Bearer eyJ…"`` in the
    environment, which is exactly the shape ``.env`` supplies, so the wire header
    is checked against the real credential path instead of a hand-built object.
    """
    raw = f"Bearer {BEARER_TOKEN}" if with_scheme else BEARER_TOKEN
    environment = {**MOCK_ENVIRONMENT, "NICHESCOUT_COVEO_BEARER_TOKEN": raw}
    return get_credentials(environment)


def env_credentials_with_bearer_scheme() -> Credentials:
    """Return ``.env``-shaped credentials through the real accessor."""
    return credentials_from_environment(with_scheme=True)


# ---------------------------------------------------------------------------
# Request side — anchored to the committed capture
# ---------------------------------------------------------------------------


def load_template() -> Mapping[str, Any]:
    """Return the hash-verified capture header for the committed template."""
    return collector_coveo.load_coveo_search_template(CAPTURE_PATH)


def template_body() -> Mapping[str, Any]:
    """Return the capture's committed request body."""
    body = load_template()["request_body"]
    assert isinstance(body, Mapping)
    return body


def template_body_text() -> str:
    """Return the capture's request body as canonical text."""
    return canonical_text(template_body())


def capture_sha256() -> str:
    """Return the provenance hash declared by the committed capture's header."""
    declared = load_template()["template_sha256"]
    assert isinstance(declared, str)
    return declared


def captured_state_by_category() -> dict[str, str]:
    """Return the ``state`` the capture stores for each captured facet value."""
    body = template_body()
    facets = body["facets"]
    return {
        str(entry["value"]): str(entry["state"])
        for entry in facets[0]["currentValues"]
    }


#: Captured facet values and the state the capture stores for each of them.
CAPTURED_STATE_BY_CATEGORY: dict[str, str] = captured_state_by_category()


def request_body(
    category: str = COVEO_FIXTURE_CATEGORY, *, page_index: int = 0
) -> dict[str, Any]:
    """Return the adapter's request body for ``category`` at ``page_index``."""
    return collector_coveo.build_coveo_request_body(
        load_template(), category, page_index=page_index
    )


def canonical_text(value: object) -> str:
    """Return the canonical text of a request body or any JSON-shaped value."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_sections(body: Mapping[str, Any]) -> dict[str, str]:
    """Split a body into canonicalized ``facets`` and every other member."""
    facets = list(body.get("facets", ()))
    rest = {name: value for name, value in body.items() if name != "facets"}
    return {"facets": canonical_text(facets), "rest": canonical_text(rest)}


def write_template(
    directory: Path,
    body: Mapping[str, Any],
    *,
    template_sha256: str | None = None,
    extra_header: Mapping[str, Any] | None = None,
    name: str = "coveo_search_template.json",
) -> Path:
    """Write a template file for the rejecting-path tests; never into ``config/``.

    ``template_sha256`` defaults to the body's own canonical hash, so a caller
    that passes a different value is deliberately writing a drifted capture.
    """
    canonical = canonical_text(body)
    header: dict[str, Any] = {
        "schema_version": "1.0.0",
        "captured_at_utc": "2026-09-17T04:28:28.915Z",
        "source_url": "https://assetstore.unity.com/",
        "organization_id": collector_coveo.COVEO_ORGANIZATION_ID,
        "endpoint": collector_coveo.COVEO_ENDPOINT,
        "template_sha256": (
            template_sha256
            if template_sha256 is not None
            else hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        ),
        "request_body": body,
    }
    header.update(dict(extra_header or {}))
    path = Path(directory) / name
    path.write_text(json.dumps(header, indent=2), encoding="utf-8")
    return path


def write_mismatched_template(directory: Path) -> Path:
    """Write a capture whose committed body does not match its declared hash."""
    return write_template(
        directory, template_body(), template_sha256="0" * 64, name="drifted.json"
    )


def write_missing_template_path(directory: Path) -> Path:
    """Return a path inside ``directory`` where no capture exists."""
    return Path(directory) / "absent" / "coveo_search_template.json"


def page_with_q_field() -> dict[str, Any]:
    """Return a body carrying a ``q`` member nested two levels deep."""
    body = request_body()
    body["context"] = {"searchHub": "Assetstore_Listing", "q": "contaminating keyword"}
    return body


def page_with_foreign_facet() -> dict[str, Any]:
    """Return a body whose facet block carries a second, forbidden facet."""
    body = request_body()
    facets = list(body["facets"])
    facets.append(
        {"facetId": "ec_rating", "field": "ec_rating", "type": "numericalRange"}
    )
    body["facets"] = facets
    return body


def count_containers(value: object) -> int:
    """Count every container (list/tuple) nested anywhere inside ``value``."""
    if isinstance(value, Mapping):
        return sum(count_containers(item) for item in value.values()) + sum(
            1 for item in value.values() if isinstance(item, (list, tuple))
        )
    if isinstance(value, (list, tuple)):
        return 1 + sum(count_containers(item) for item in value)
    return 0


# ---------------------------------------------------------------------------
# Response side — hand-derived page and record shapes
# ---------------------------------------------------------------------------


def record(
    index: int,
    *,
    category: object = COVEO_FIXTURE_CATEGORY,
    permanentid: object = ...,
    ec_product_id: object = ...,
    name: object = ...,
    publisher: object = "Fixture Publisher",
) -> dict[str, Any]:
    """Return one response record with agreeing ``permanentid``/``ec_product_id``.

    Both identity members carry the *same* identifier, which is what the SRS
    describes for an ordinary listing record and what the plan §9 response
    fixtures call for ("recorded-shape page of 96 records with ``permanentid`` +
    ``ec_product_id`` agreeing"). Agreeing means the same canonical string under
    the frozen mapping rule 1.0.1, so the two members must not be derivable into
    two distinct canonical values: an opaque per-field value such as
    ``"permanent-0000"`` beside ``"product-0000"`` is a genuine ``conflict``,
    which is :func:`conflicting_record`'s job. Pass
    ``permanentid``/``ec_product_id`` explicitly to vary one side.
    """
    identity = f"{index:04d}"
    product_id = f"product-{identity}"
    return {
        "permanentid": product_id if permanentid is ... else permanentid,
        "ec_product_id": (product_id if ec_product_id is ... else ec_product_id),
        "ec_name": f"Fixture Asset {identity}" if name is ... else name,
        "ec_category": category,
        "publisher_name": publisher,
    }


def records(
    count: int, *, start: int = 0, category: object = COVEO_FIXTURE_CATEGORY
) -> list[dict[str, Any]]:
    """Return ``count`` agreeing-identity records with distinct identities."""
    return [record(index, category=category) for index in range(start, start + count)]


def record_without_identity(
    index: int = 0, *, category: object = COVEO_FIXTURE_CATEGORY
) -> dict[str, Any]:
    """Return a record with no canonicalizable identity candidate at all."""
    return {
        "permanentid": "",
        "ec_product_id": None,
        "ec_name": f"Unidentifiable Asset {index:04d}",
        "ec_category": category,
        "publisher_name": "Fixture Publisher",
    }


def conflicting_record(
    index: int = 0, *, category: object = COVEO_FIXTURE_CATEGORY
) -> dict[str, Any]:
    """Return a record whose two identity candidates disagree (``conflict``)."""
    return {
        "permanentid": "permanent-0001",
        "ec_product_id": "product-9999",
        "ec_name": f"Conflicting Asset {index:04d}",
        "ec_category": category,
        "publisher_name": "Fixture Publisher",
    }


def uri_fallback_record(
    index: int = 0, *, category: object = COVEO_FIXTURE_CATEGORY
) -> dict[str, Any]:
    """Return a record identified only through a trailing-identifier ``uri``."""
    return {
        "ec_name": f"URI-only Asset {index:04d}",
        "ec_category": category,
        "publisher_name": "Fixture Publisher",
        "uri": f"https://assetstore.unity.com/packages/fixture-asset-{index}-999999",
    }


#: A record resolved through the response-level ``uri`` fallback only.
URI_FALLBACK_RECORD: dict[str, Any] = uri_fallback_record(0)

#: Backwards-compatible alias kept for readers of the earlier fixture name.
URL_FALLBACK_RECORD: dict[str, Any] = URI_FALLBACK_RECORD


def make_page(
    page_records: Iterable[Mapping[str, Any]],
    *,
    total_count: int | None,
    filtered_count: int | None = None,
) -> dict[str, Any]:
    """Return one recorded-shape Coveo page body."""
    page: dict[str, Any] = {
        "results": [dict(item) for item in page_records],
        "totalCount": total_count,
        "duration": 7,
        "indexDuration": 3,
        "requestDuration": 4,
    }
    if filtered_count is not None:
        page["totalCountFiltered"] = filtered_count
    return page


def malformed_page() -> dict[str, Any]:
    """Return a page whose ``results`` member is not a usable list."""
    return {"totalCount": 12, "results": {"unexpected": "shape"}}


def utterly_empty_page() -> dict[str, Any]:
    """Return a structurally valid page with no results and no usable count."""
    return {"results": [], "totalCount": None}


def wrap_page_json(page: Mapping[str, Any]) -> bytes:
    """Encode a page mapping as the response body bytes an opener would return."""
    return json.dumps(page).encode("utf-8")


# ---------------------------------------------------------------------------
# Live-form vocabulary (Chunk 14) — hand-derived, offline
# ---------------------------------------------------------------------------
# The live facet/record vocabulary: lowercase slugs joined by the exact
# ``" > "`` sequence, with the child entries of a multi-valued ``ec_category``
# carrying a leading space (plan §1 and §8). Everything below is an explicit
# literal; nothing is derived from ``config/``, so the compatibility tests can
# exercise the live shape without depending on the committed regeneration.

#: The live separator. Only this exact sequence splits a path; ``"A>B"`` is one
#: segment and normalizes unchanged.
LIVE_FORM_SEPARATOR = " > "

#: A live-form facet value and its canonical slash-form round-trip (plan §8).
LIVE_FORM_FACET_VALUE = "2d > textures-materials > stone"
LIVE_FORM_FACET_VALUE_CANONICAL = "2d/textures-materials/stone"

#: Live-form parent and child record values, each with the leading space the
#: endpoint writes on child entries of a multi-valued ``ec_category``.
LIVE_FORM_PARENT_VALUE = " 3d > characters"
LIVE_FORM_PARENT_VALUE_CANONICAL = "3d/characters"
LIVE_FORM_CHILD_VALUE = " 3d > characters > humanoids"
LIVE_FORM_CHILD_VALUE_CANONICAL = "3d/characters/humanoids"

#: The live multi-valued ``ec_category`` shape of one record: a bare top-level
#: value followed by leading-space child entries (plan §8 edge case).
LIVE_FORM_MULTI_VALUED_CATEGORY: tuple[str, ...] = (
    "3d",
    LIVE_FORM_PARENT_VALUE,
    LIVE_FORM_CHILD_VALUE,
)

#: A live-form facet value absent from the live inventory, so it can only be a
#: mismatch. There is no ``2d/textures-materials/lava`` entry.
LIVE_FORM_ABSENT_FACET_VALUE = "2d > textures-materials > lava"

#: Explicit live-form inventory and the canonical paths it round-trips to.
LIVE_FORM_INVENTORY: tuple[str, ...] = (
    "2d > textures-materials > stone",
    "3d > characters",
    "3d > characters > humanoids",
    "3d > vehicles > land",
)
LIVE_FORM_INVENTORY_CANONICAL: frozenset[str] = frozenset(
    {
        "2d/textures-materials/stone",
        "3d/characters",
        "3d/characters/humanoids",
        "3d/vehicles/land",
    }
)


def live_form_record(index: int = 0) -> dict[str, Any]:
    """Return a record whose ``ec_category`` carries the live multi-valued shape."""
    return record(index, category=list(LIVE_FORM_MULTI_VALUED_CATEGORY))


def live_form_taxonomy_payload() -> dict[str, Any]:
    """Return a valid taxonomy payload whose inventory is in live form.

    Only the four required headers and the live-form inventory are carried: the
    committed taxonomy has no ``categories`` records (plan §6) and the headers
    are the Chunk 0 fixture's, so nothing here is read from ``config/``.
    """
    return {
        "schema_version": TAXONOMY_FIXTURE["schema_version"],
        "captured_at_utc": TAXONOMY_FIXTURE["captured_at_utc"],
        "source_url": TAXONOMY_FIXTURE["source_url"],
        "template_sha256": TAXONOMY_FIXTURE["template_sha256"],
        "canonical_category_paths": list(LIVE_FORM_INVENTORY),
    }


# ---------------------------------------------------------------------------
# Live raw-nested record shape (Chunk 16) — hand-derived, offline
# ---------------------------------------------------------------------------
# The Chunk 16 plan §1 records the live Coveo Search v2 shape: the five
# requested discovery fields arrive nested under a per-record ``raw`` object,
# while ``uri``/``clickUri`` stay top-level. ``ec_product_id`` and
# ``ec_category`` are one-element / multi-element lists and ``permanentid`` is
# a string. These helpers are hand-derived from that human-supplied live
# capture; they are not a committed captured response.

#: The five live ``raw`` members, verbatim from the capture in plan §1.
LIVE_RAW_RECORD_FIELDS: dict[str, object] = {
    "permanentid": "379642",
    "ec_product_id": ["379642"],
    "ec_name": "Fixture Live Asset",
    "ec_category": ["3d", " 3d > characters"],
    "publisher_name": "Fixture Publisher",
}


def live_raw_record(index: int = 0, *, category: object = None) -> dict[str, Any]:
    """Return one record in the live nested shape (discovery fields under ``raw``).

    The top level carries the response fields the capture shows there
    (``uri``, ``clickUri``, ``uniqueId``, ``title``, ``excerpt``, ``score``) and
    the requested discovery fields live under ``raw``. ``uri``/``clickUri`` have
    no trailing ``-<digits>`` identifier, so the URI fallback contributes no
    candidate and the identity resolves through the string ``permanentid``.
    """
    identity = f"{379642 + index}"
    raw = dict(LIVE_RAW_RECORD_FIELDS)
    raw["permanentid"] = identity
    raw["ec_product_id"] = [identity]
    if category is not None:
        raw["ec_category"] = category
    return {
        "title": f"Fixture Live Asset {identity}",
        "uri": f"assetstore://product/{identity}",
        "clickUri": f"https://assetstore.unity.com/packages/package/{identity}",
        "uniqueId": f"42.20568$assetstore://product/{identity}",
        "excerpt": "Fixture live excerpt",
        "score": 2711,
        "raw": raw,
    }


def live_raw_page(
    page_records: Iterable[Mapping[str, Any]],
    *,
    total_count: int | None,
    filtered_count: int | None = None,
) -> dict[str, Any]:
    """Return one live-nested Coveo page body (same envelope as ``make_page``)."""
    return make_page(
        page_records, total_count=total_count, filtered_count=filtered_count
    )


def live_raw_summary_record(*, identity: str, category: str) -> dict[str, Any]:
    """Return one live-nested record for a synthetic e2e category.

    ``permanentid`` is the scenario identity and ``ec_product_id`` its
    one-element list; ``ec_category`` is the requested category; ``uri`` and
    ``clickUri`` carry no usable trailing identifier, so identity resolves
    through ``permanentid`` alone.
    """
    return {
        "title": f"Fixture Live Asset {identity}",
        "uri": f"assetstore://product/{identity}",
        "clickUri": f"https://assetstore.unity.com/packages/package/{identity}",
        "uniqueId": f"42.20568$assetstore://product/{identity}",
        "excerpt": "Fixture live excerpt",
        "score": 2711,
        "raw": {
            "permanentid": identity,
            "ec_product_id": [identity],
            "ec_name": f"Fixture Live Asset {identity}",
            "ec_category": [category],
            "publisher_name": "Fixture Publisher",
        },
    }


# ---------------------------------------------------------------------------
# SQLite and configuration helpers
# ---------------------------------------------------------------------------


def configured_config(tmp_path: Path, **overrides: Any):
    """Return a real ``NicheScoutConfig`` whose paths live under ``tmp_path``."""
    toml_path = write_toml(Path(tmp_path), DEFAULT_TOML_BODY, name="chunk03.toml")
    config = load_config(toml_path=toml_path)
    values: dict[str, Any] = {
        "categories_path": Path(tmp_path) / "categories.json",
        "taxonomy_path": TAXONOMY_PATH_FIXTURE,
        "db_path": Path(tmp_path) / "niche_scout.sqlite3",
    }
    values.update(overrides)
    Path(values["categories_path"]).write_text(
        json.dumps(list(DEFAULT_CATEGORIES)), encoding="utf-8"
    )
    return replace(config, **values)


def count_consumed(values: Sequence[Any]) -> Iterator[Any]:
    """Yield ``values`` lazily while recording how many items were consumed."""
    for value in values:
        yield value
