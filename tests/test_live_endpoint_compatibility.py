"""Chunk 14 analytical tests — live Unity/Coveo endpoint compatibility.

Every test carries exactly the explicit ``@pytest.mark.lreq`` marker (or marker
pair) that ``Documents/plans/chunk-14-live-endpoint-compatibility.md`` §9 assigns
to its base node ID, plus a matching ``tests/traceability.json`` entry. The module
is offline and deterministic: the live vocabulary is encoded as explicit literals
in ``fixtures/coveo_discovery.py``, the committed files are read read-only the way
``tests/test_contracts.py::test_taxonomy_contract`` reads them, and no test
contacts the endpoint, reads the clock, or carries a credential.

Where a value is not stated by the SRS prose — the ``" > "`` separator, segment
trimming, leading-space record values, and the canonical ``/`` round-trip — the
source is the plan's §8 edge-case list plus the frozen remediation decisions;
plan §2 records that the SRS defines neither a separator nor a casing rule.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any

import fixtures.coveo_discovery as discovery
import pytest

from niche_scout import collector_coveo
from niche_scout import validation as v
from niche_scout.config import read_categories
from niche_scout.models import (
    MIN_CATEGORIES_PER_RUN,
    PAGE_SIZE,
    CategoryFilterValidationStatus,
    DiscoveryStatus,
    IdentityResolutionStatus,
)

ROOT = Path(__file__).resolve().parents[1]
COMMITTED_CATEGORIES_PATH = ROOT / "config" / "categories.json"
COMMITTED_TAXONOMY_PATH = ROOT / "config" / "category_taxonomy.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _issue_codes(result: Any) -> list[str]:
    """Return the issue codes reported by a validation result."""
    return [issue.code for issue in result.issues]


def _taxonomy_payload(*, canonical: bool = False) -> dict[str, Any]:
    """Return a valid payload whose inventory is live-form or canonical.

    ``canonical=True`` swaps the live-form inventory for the canonical paths it
    round-trips to, which is the shape the committed taxonomy carries. Both come
    from explicit ``fixtures.coveo_discovery`` literals; neither reads
    ``config/``.
    """
    payload = discovery.live_form_taxonomy_payload()
    if canonical:
        payload["canonical_category_paths"] = sorted(
            discovery.LIVE_FORM_INVENTORY_CANONICAL
        )
    return payload


def _committed_taxonomy() -> dict[str, Any]:
    """Return the committed taxonomy file parsed from disk."""
    return json.loads(COMMITTED_TAXONOMY_PATH.read_text(encoding="utf-8"))


def _committed_template_facet_values() -> list[str]:
    """Return the committed capture's ``ec_category`` facet values, in order."""
    body = discovery.template_body()
    facets = [
        facet
        for facet in body["facets"]
        if facet["facetId"] == collector_coveo.COVEO_FACET_ID
    ]
    assert len(facets) == 1, "the capture carries exactly one ec_category facet"
    return [entry["value"] for entry in facets[0]["currentValues"]]


# ---------------------------------------------------------------------------
# LREQ-EXT-080 — live separator normalization and exact membership
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-EXT-080")
def test_normalize_category_path_accepts_live_double_gt_separator() -> None:
    """The exact ``" > "`` sequence normalizes to the canonical ``/`` form.

    Hand-derived from plan §8: only the exact three-character sequence splits;
    segments are trimmed, empties dropped, and case preserved.
    """
    # "2d > textures-materials > stone" -> "2d/textures-materials/stone"
    assert (
        v.normalize_category_path(discovery.LIVE_FORM_FACET_VALUE)
        == discovery.LIVE_FORM_FACET_VALUE_CANONICAL
    )
    # " 3d > characters" -> "3d/characters" (per-segment trim of the leading space)
    assert (
        v.normalize_category_path(discovery.LIVE_FORM_PARENT_VALUE)
        == discovery.LIVE_FORM_PARENT_VALUE_CANONICAL
    )
    assert (
        v.normalize_category_path(discovery.LIVE_FORM_CHILD_VALUE)
        == discovery.LIVE_FORM_CHILD_VALUE_CANONICAL
    )
    # "A>B" carries no " > " sequence and stays one segment.
    assert v.normalize_category_path("A>B") == "A>B"
    assert v.normalize_category_path("A>B > C") == "A>B/C"
    # Empty segments are dropped and surrounding whitespace is trimmed.
    assert v.normalize_category_path(" 3d >  > characters > ") == "3d/characters"
    # Case is preserved in the canonical output.
    assert (
        v.normalize_category_path("3D > Characters > Humanoids")
        == "3D/Characters/Humanoids"
    )
    # A whitespace-only value normalizes to the empty string, not to a path.
    assert v.normalize_category_path("  ") == ""


@pytest.mark.lreq("LREQ-EXT-080")
def test_normalize_category_path_leaves_slash_form_unchanged() -> None:
    """``/``-only raw input normalizes exactly as before; non-strings still raise."""
    # Plan §8: "A/B", " Tools / Utilities / ", and "A//B" keep their prior outputs.
    assert v.normalize_category_path("A/B") == "A/B"
    assert v.normalize_category_path(" Tools / Utilities / ") == "Tools/Utilities"
    assert v.normalize_category_path("A//B") == "A/B"
    assert v.normalize_category_path("") == ""
    assert v.normalize_category_path("   ") == ""
    assert (
        v.normalize_category_path("2d/textures-materials/stone")
        == "2d/textures-materials/stone"
    )
    with pytest.raises(TypeError):
        v.normalize_category_path(7)  # type: ignore[arg-type]


@pytest.mark.lreq("LREQ-EXT-020")
def test_live_form_taxonomy_inventory_entry_is_well_formed() -> None:
    """A ``" > "``-joined inventory entry survives taxonomy structure validation.

    The shape check tokenizes the raw entry on both ``" > "`` and ``/`` without
    dropping empties, so a live-form entry is not misreported as a normalization
    "repair", while ``/Leading/Slash`` and ``Tools/`` stay malformed (plan §8).
    """
    payload = _taxonomy_payload()
    result = v.validate_taxonomy_structure(payload)
    assert result.is_valid is True
    assert result.status == "valid"
    assert result.missing_header_fields == ()
    assert result.issues == ()

    for malformed in ("/Leading/Slash", "Tools/"):
        repairable = {**payload, "canonical_category_paths": [malformed]}
        rejected = v.validate_taxonomy_structure(repairable)
        assert rejected.is_valid is False, malformed
        assert "taxonomy_malformed_path_entry" in _issue_codes(rejected), malformed


@pytest.mark.lreq("LREQ-EXT-080")
def test_live_form_multi_valued_record_values_match_canonical_inventory() -> None:
    """Every live-form record value normalizes into the canonical inventory.

    The canonical payload is the committed taxonomy's shape (canonical ``/``
    entries); the record values carry the live shape.
    """
    paths = v.taxonomy_path_set(_taxonomy_payload(canonical=True))
    assert paths == discovery.LIVE_FORM_INVENTORY_CANONICAL

    assert v.normalize_category_path(discovery.LIVE_FORM_FACET_VALUE) in paths
    assert v.normalize_category_path(discovery.LIVE_FORM_PARENT_VALUE) in paths
    assert v.normalize_category_path(discovery.LIVE_FORM_CHILD_VALUE) in paths
    # The top-level record value stays a non-selectable single segment.
    assert v.normalize_category_path("3d") not in paths


@pytest.mark.lreq("LREQ-EXT-090")
def test_live_form_record_category_match_is_verified_not_mismatch() -> None:
    """A live multi-valued record verifies against the canonical inventory."""
    paths = v.taxonomy_path_set(_taxonomy_payload(canonical=True))
    record = discovery.live_form_record(0)

    result = v.match_exact_category(record["ec_category"], paths)
    assert result.status is CategoryFilterValidationStatus.VERIFIED
    assert result.matched_path == discovery.LIVE_FORM_PARENT_VALUE_CANONICAL
    assert result.matched_value_count == 2
    assert result.unmatched_values == ("3d",)
    assert result.issues == ()
    assert v.discovery_status_for_category_status(result.status) is None, (
        "a verified filter is not a discovery failure"
    )

    scalar = v.match_exact_category(discovery.LIVE_FORM_FACET_VALUE, paths)
    assert scalar.status is CategoryFilterValidationStatus.VERIFIED
    assert scalar.matched_path == discovery.LIVE_FORM_FACET_VALUE_CANONICAL
    assert scalar.matched_value_count == 1


@pytest.mark.lreq("LREQ-EXT-090")
def test_absent_category_value_still_maps_to_category_mismatch() -> None:
    """A live-form value absent from the inventory is still a mismatch."""
    paths = v.taxonomy_path_set(_taxonomy_payload(canonical=True))
    absent = (
        discovery.LIVE_FORM_ABSENT_FACET_VALUE,
        "3d > characters > dragons",
    )

    result = v.match_exact_category(list(absent), paths)
    assert result.status is CategoryFilterValidationStatus.MISMATCH
    assert result.matched_path is None
    assert result.matched_value_count == 0
    assert _issue_codes(result) == ["category_value_mismatch"]
    assert len(result.unmatched_values) == 2, (
        "both supplied values are usable strings with no exact match"
    )
    assert (
        v.normalize_category_path(result.unmatched_values[0])
        == "2d/textures-materials/lava"
    )
    assert (
        v.discovery_status_for_category_status(result.status)
        is DiscoveryStatus.CATEGORY_MISMATCH
    )


# ---------------------------------------------------------------------------
# LREQ-EXT-010 — captured template and the request-body facet guard
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-EXT-010")
def test_request_body_guard_rejects_category_absent_from_template() -> None:
    """A category no template ``currentValue`` equals raises ``ValueError``."""
    template = discovery.load_template()
    current_values = _committed_template_facet_values()
    absent = "3d/characters/dragons"
    assert absent not in current_values, "fixture precondition: the value is absent"

    with pytest.raises(ValueError):
        collector_coveo.build_coveo_request_body(template, absent, page_index=0)


@pytest.mark.lreq("LREQ-EXT-010")
def test_request_body_guard_selects_exactly_one_committed_category() -> None:
    """Each committed fixture category builds a body selecting exactly itself.

    The guard is behavior-only: the public keyword-only signature is unchanged.
    """
    template = discovery.load_template()
    committed = _committed_template_facet_values()

    for category in (
        discovery.COVEO_FIXTURE_CATEGORY,
        discovery.COVEO_FIXTURE_CATEGORY_OTHER,
    ):
        assert category in committed, "fixture category must be a currentValue"
        body = collector_coveo.build_coveo_request_body(
            template, category, page_index=0
        )
        facets = [
            facet
            for facet in body["facets"]
            if facet["facetId"] == collector_coveo.COVEO_FACET_ID
        ]
        assert len(facets) == 1
        entries = facets[0]["currentValues"]
        assert [entry["value"] for entry in entries] == committed
        selected = [entry["value"] for entry in entries if entry["state"] == "selected"]
        idle = [entry["value"] for entry in entries if entry["state"] == "idle"]
        assert selected == [category]
        assert len(idle) == len(entries) - 1

    signature = inspect.signature(collector_coveo.build_coveo_request_body)
    assert list(signature.parameters) == [
        "template",
        "category",
        "page_index",
        "page_size",
    ]
    assert signature.parameters["page_index"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["page_size"].default == PAGE_SIZE


# ---------------------------------------------------------------------------
# LREQ-EXT-020 / LREQ-EXT-010 — committed config consistency
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-EXT-020")
@pytest.mark.lreq("LREQ-EXT-010")
def test_committed_categories_match_template_facet_byte_for_byte() -> None:
    """``config/categories.json`` and the capture facet carry identical strings.

    ``read_categories`` and ``coveo_discovery``'s hash-verified loader are the
    reads ``tests/test_contracts.py::test_taxonomy_contract`` and
    ``tests/test_collector.py`` use. String equality of the ordered ASCII slugs
    is byte equality, and order matters: the file and the facet must agree
    position by position.
    """
    requested = list(read_categories(COMMITTED_CATEGORIES_PATH))
    facet_values = _committed_template_facet_values()

    assert requested == facet_values
    assert len(requested) >= MIN_CATEGORIES_PER_RUN


@pytest.mark.lreq("LREQ-EXT-020")
def test_committed_taxonomy_covers_requested_categories_and_parents() -> None:
    """Every committed requested category and its immediate parent is inventoried."""
    taxonomy = _committed_taxonomy()
    inventory = set(taxonomy["canonical_category_paths"])
    requested = read_categories(COMMITTED_CATEGORIES_PATH)

    assert len(requested) >= MIN_CATEGORIES_PER_RUN
    for path in requested:
        assert path == v.normalize_category_path(path), (
            "committed requested categories are canonical '/'-form paths"
        )
        assert path in inventory, f"taxonomy is missing requested category {path}"
        parent = path.rsplit("/", 1)[0]
        assert parent in inventory, f"taxonomy is missing the parent of {path}"


@pytest.mark.lreq("LREQ-EXT-020")
def test_committed_taxonomy_excludes_single_segment_entries() -> None:
    """The committed inventory is the 121-entry multi-segment live list."""
    taxonomy = _committed_taxonomy()
    paths = taxonomy["canonical_category_paths"]

    assert isinstance(paths, list)
    assert paths, "the committed inventory must not be empty"
    assert len(paths) == len(set(paths)), "inventory entries are unique"
    assert [path for path in paths if "/" not in path] == [], (
        "the seven single-segment tops (2d, 3d, add-ons, audio, templates, "
        "tools, vfx) are excluded"
    )
    assert len(paths) == 121, "plan appendix A: 121 multi-segment entries"
    for path in paths:
        assert path == v.normalize_category_path(path), (
            f"inventory entry is not canonical '/'-form: {path!r}"
        )


# ---------------------------------------------------------------------------
# LREQ-EXT-050 — sortCriteria removal
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-EXT-050")
def test_committed_template_omits_sort_criteria() -> None:
    """The committed capture carries no ``sortCriteria``; neither does the builder.

    Removing the rejected explicit sort leaves the engine default as the one
    shared sort order. Pagination stability is not asserted here: it is a
    documented, unverified limitation (plan §12.2).
    """
    body = discovery.template_body()
    assert "sortCriteria" not in body

    built = discovery.request_body(discovery.COVEO_FIXTURE_CATEGORY)
    assert "sortCriteria" not in built


# ---------------------------------------------------------------------------
# LREQ-ARCH-030 / LREQ-EXT-060 — determinism and identity isolation
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-ARCH-030")
def test_live_form_normalization_is_deterministic() -> None:
    """Normalization and matching are pure functions of their inputs.

    Repeated calls are equivalent and no result depends on container ordering.
    """
    values = (
        discovery.LIVE_FORM_FACET_VALUE,
        discovery.LIVE_FORM_PARENT_VALUE,
        discovery.LIVE_FORM_CHILD_VALUE,
        "A>B",
        "A//B",
        " Tools / Utilities / ",
    )
    first = [v.normalize_category_path(value) for value in values]
    for _ in range(2):
        assert [v.normalize_category_path(value) for value in values] == first
    assert frozenset(first) == frozenset(
        v.normalize_category_path(value) for value in reversed(values)
    )

    payload = _taxonomy_payload()
    assert v.taxonomy_path_set(payload) == v.taxonomy_path_set(payload)

    paths = v.taxonomy_path_set(_taxonomy_payload(canonical=True))
    record = discovery.live_form_record(0)
    assert v.match_exact_category(
        record["ec_category"], paths
    ) == v.match_exact_category(record["ec_category"], paths)


@pytest.mark.lreq("LREQ-EXT-060")
def test_live_form_record_identity_candidates_unchanged() -> None:
    """The live multi-valued ``ec_category`` never becomes an identity candidate."""
    live = discovery.live_form_record(7)
    canonical = {**live, "ec_category": ["3d/characters/humanoids"]}

    assert v.collect_identity_candidates(live) == v.collect_identity_candidates(
        canonical
    )
    live_result = v.resolve_canonical_identity(live)
    assert live_result == v.resolve_canonical_identity(canonical)
    assert live_result.status is IdentityResolutionStatus.RESOLVED
    assert live_result.canonical_identity_key == "product-0007"
