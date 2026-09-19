"""Chunk 1 identity tests: candidate collection, canonicalization, and classification.

Every test here carries an explicit ``@pytest.mark.lreq`` marker and a matching
entry in ``tests/traceability.json``. The suite exercises the pure identity half of
``niche_scout.validation`` under mapping rule 1.0.1 (resolved decision R-2, plus
the 1.0.1 candidate-comparison correction): which
candidates a discovery record retains, how a candidate is canonicalized, how
agreement/disagreement is classified, how a conflict or unresolved identity is kept
out of the canonical denominator and enrichment set, how GraphQL identity aliases
are compared with a requested identity, and how a ``state`` value is annotated
without deciding metric eligibility.

These tests are network-free: the fixtures in ``fixtures.validation_fixtures`` are
local, hand-derived golden vectors, and no test reads the system clock for an
expected value.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

import fixtures.graphql_fixtures as gqlfx
import fixtures.validation_fixtures as fx

import niche_scout.collector_graphql as collector_graphql
import niche_scout.validation as v
from niche_scout.models import (
    GraphQLOperationCorrelationMode,
    IDENTITY_MAPPING_RULE_VERSION,
    IdentityResolutionStatus,
)

#: The one mapping rule version this chunk implements; an unknown version must be
#: rejected rather than silently treated as 1.0.0.
UNKNOWN_MAPPING_RULE_VERSION = "9.9.9"

#: Values that must never be fabricated as a canonical identity. ``"0"`` matters
#: because a missing identifier reduced to an integer would become ``0``.
FABRICATED_IDENTITY_VALUES = ("", "0", "0.0", "None", "none", "null")


def _candidate_source_fields(record: dict[str, object]) -> list[str]:
    """Return the source fields of every retained candidate, in input order."""
    return [candidate.source_field for candidate in v.collect_identity_candidates(record)]


def _candidate_for(record: dict[str, object], source_field: str) -> v.IdentityCandidate:
    """Return the single retained candidate for ``source_field``."""
    matching = [
        candidate
        for candidate in v.collect_identity_candidates(record)
        if candidate.source_field == source_field
    ]
    assert len(matching) == 1, f"expected exactly one candidate from {source_field!r}"
    return matching[0]


# --------------------------------------------------------------------------
# LREQ-EXT-060 — candidate collection and versioned canonicalization
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-EXT-060")
def test_collects_all_non_empty_identity_candidates() -> None:
    """``ec_product_id``, ``permanentid``, ``clickUri``, and ``uri`` are all retained."""
    candidates = v.collect_identity_candidates(fx.AGREEING_IDENTITY_RECORD)

    assert set(_candidate_source_fields(fx.AGREEING_IDENTITY_RECORD)) == {
        "ec_product_id",
        "permanentid",
        "clickUri",
        "uri",
    }
    assert len(candidates) == 4

    by_field = {candidate.source_field: candidate for candidate in candidates}
    assert by_field["ec_product_id"].raw_value == fx.CANONICAL_ASSET_ID
    # The raw value is retained verbatim, padding included (LREQ-EXT-060 "retain").
    assert by_field["permanentid"].raw_value == f" {fx.CANONICAL_ASSET_ID} "
    assert by_field["clickUri"].raw_value == fx.URI_WITH_SLUG_IDENTIFIER
    assert by_field["uri"].raw_value == fx.URI_WITH_QUERY_STRING

    # A single-field record still yields exactly that one candidate.
    assert _candidate_source_fields(fx.EC_PRODUCT_ID_ONLY_RECORD) == ["ec_product_id"]
    assert _candidate_source_fields(fx.PERMANENTID_ONLY_RECORD) == ["permanentid"]
    assert _candidate_source_fields(fx.CLICK_URI_ONLY_RECORD) == ["clickUri"]
    assert _candidate_source_fields(fx.URI_ONLY_RECORD) == ["uri"]

    # Candidate order is deterministic input order, so the result is reproducible.
    assert _candidate_source_fields(fx.AGREEING_IDENTITY_RECORD) == [
        "ec_product_id",
        "permanentid",
        "clickUri",
        "uri",
    ]
    assert v.collect_identity_candidates(fx.AGREEING_IDENTITY_RECORD) == candidates

    for name, record in fx.IDENTITY_RECORDS.items():
        for candidate in v.collect_identity_candidates(record):
            assert candidate.raw_value.strip() != "", name


@pytest.mark.lreq("LREQ-EXT-060")
def test_candidate_source_fields_are_retained() -> None:
    """Every candidate names the exact record field it came from."""
    candidates = v.collect_identity_candidates(fx.AGREEING_IDENTITY_RECORD)

    assert [candidate.source_field for candidate in candidates] == [
        "ec_product_id",
        "permanentid",
        "clickUri",
        "uri",
    ]
    for candidate in candidates:
        assert candidate.source_field in {
            "ec_product_id",
            "permanentid",
            "clickUri",
            "uri",
        }
        assert isinstance(candidate.source_field, str)

    # The source field survives even when the candidate cannot be canonicalized.
    unparseable = _candidate_for(fx.UNPARSEABLE_URI_RECORD, "uri")
    assert unparseable.source_field == "uri"
    assert unparseable.canonical_value is None

    # Duplicate values from different source fields are distinct candidates, each
    # keeping its own source field (LREQ-EXT-060 edge case).
    duplicate_values = {"ec_product_id": "1234567", "permanentid": "1234567"}
    duplicate_candidates = v.collect_identity_candidates(duplicate_values)
    assert [candidate.source_field for candidate in duplicate_candidates] == [
        "ec_product_id",
        "permanentid",
    ]
    assert [candidate.raw_value for candidate in duplicate_candidates] == [
        "1234567",
        "1234567",
    ]


@pytest.mark.lreq("LREQ-EXT-060")
def test_uri_fallback_parsing() -> None:
    """A URI contributes only the trailing numeric identifier of its last path segment."""
    # The identifier after the final ``-`` in the last path segment.
    assert v.canonicalize_identity_candidate(fx.URI_WITH_SLUG_IDENTIFIER) == (
        fx.CANONICAL_ASSET_ID
    )
    assert (
        _candidate_for(fx.CLICK_URI_ONLY_RECORD, "clickUri").canonical_value
        == fx.CANONICAL_ASSET_ID
    )
    assert (
        _candidate_for(fx.URI_ONLY_RECORD, "uri").canonical_value == fx.CANONICAL_ASSET_ID
    )

    # A query string does not change the identifier, which comes from the path. The
    # ``uri`` field is the home of the URI-specific reading, so the assertion goes
    # through candidate collection rather than the field-agnostic helper.
    assert (
        _candidate_for({"uri": fx.URI_WITH_QUERY_STRING}, "uri").canonical_value
        == fx.CANONICAL_ASSET_ID
    )
    assert (
        _candidate_for({"uri": fx.URI_WITH_FRAGMENT_AND_QUERY}, "uri").canonical_value
        == fx.CANONICAL_ASSET_ID
    )
    assert (
        _candidate_for(
            {"uri": f"{fx.URI_WITH_SLUG_IDENTIFIER}#reviews?page=2"}, "uri"
        ).canonical_value
        == fx.CANONICAL_ASSET_ID
    )
    assert (
        _candidate_for(
            {"clickUri": fx.URI_WITH_FRAGMENT_AND_QUERY}, "clickUri"
        ).canonical_value
        == fx.CANONICAL_ASSET_ID
    )

    # The URI-specific reading is what the ``clickUri``/``uri`` source fields get:
    # the same slug-less URL that yields no candidate as a URI is an already-canonical
    # ``ec_product_id``/``permanentid`` value and is passed through unchanged.
    assert v.canonicalize_identity_candidate(fx.URI_NO_TRAILING_IDENTIFIER) == (
        fx.URI_NO_TRAILING_IDENTIFIER
    )
    assert _candidate_for(fx.UNPARSEABLE_URI_RECORD, "uri").canonical_value is None
    assert (
        _candidate_for({"ec_product_id": fx.URI_NO_TRAILING_IDENTIFIER}, "ec_product_id")
        .canonical_value
        == fx.URI_NO_TRAILING_IDENTIFIER
    )

    # A URI last path segment with no trailing ``-<numeric>`` yields no candidate,
    # and specifically not the slug text, the URL, or a fabricated ``""``/``"0"``.
    for unusable_uri in (
        fx.URI_NO_TRAILING_IDENTIFIER,
        fx.URI_TRAILING_SLASH,
        "https://assetstore.unity.com/packages/tools/level-design/-abc",
        "https://assetstore.unity.com/",
    ):
        candidate = _candidate_for({"uri": unusable_uri}, "uri")
        assert candidate.canonical_value is None, unusable_uri
        assert candidate.canonical_value not in FABRICATED_IDENTITY_VALUES, unusable_uri
        assert candidate.parse_failure_reason is not None, unusable_uri

    # The trailing numeric group of the *last* path segment is the identifier; a
    # numeric group appearing earlier in the path is not.
    assert (
        _candidate_for(
            {"uri": "https://assetstore.unity.com/packages/2d/textures-materials/environment-99"},
            "uri",
        ).canonical_value
        == "99"
    )
    assert (
        _candidate_for(
            {"uri": fx.URI_NUMERIC_GROUP_BEFORE_FINAL_SEGMENT}, "uri"
        ).canonical_value
        is None
    )

    # A non-conforming URI is retained as a candidate but contributes no value, so
    # the record's candidate tuple is not empty and carries no placeholder.
    assert _candidate_source_fields(fx.UNPARSEABLE_URI_RECORD) == ["uri"]
    assert _candidate_for(fx.UNPARSEABLE_URI_RECORD, "uri").raw_value == (
        fx.URI_NO_TRAILING_IDENTIFIER
    )


@pytest.mark.lreq("LREQ-EXT-060")
def test_canonicalization_is_versioned() -> None:
    """Canonicalization records its rule version and rejects an unknown one."""
    default_result = v.resolve_canonical_identity(fx.AGREEING_IDENTITY_RECORD)
    assert default_result.mapping_rule_version == IDENTITY_MAPPING_RULE_VERSION
    assert default_result.mapping_rule_version == "1.0.1"

    explicit_result = v.resolve_canonical_identity(
        fx.AGREEING_IDENTITY_RECORD, mapping_rule_version=IDENTITY_MAPPING_RULE_VERSION
    )
    assert explicit_result.mapping_rule_version == IDENTITY_MAPPING_RULE_VERSION

    # An unknown version is refused rather than silently applying 1.0.0 semantics.
    with pytest.raises(ValueError):
        v.resolve_canonical_identity(
            fx.AGREEING_IDENTITY_RECORD,
            mapping_rule_version=UNKNOWN_MAPPING_RULE_VERSION,
        )
    with pytest.raises(ValueError):
        v.canonicalize_identity_candidate(
            fx.CANONICAL_ASSET_ID,
            mapping_rule_version=UNKNOWN_MAPPING_RULE_VERSION,
        )
    with pytest.raises(ValueError):
        v.compare_graphql_identity_aliases(
            fx.REQUESTED_IDENTITY,
            fx.GQL_ALIAS_MAPS["agreeing"],
            mapping_rule_version=UNKNOWN_MAPPING_RULE_VERSION,
        )


@pytest.mark.lreq("LREQ-EXT-060")
def test_unparseable_candidate_retained_with_reason() -> None:
    """A non-conforming candidate is kept, carries no value, and explains itself."""
    candidate = _candidate_for(fx.UNPARSEABLE_URI_RECORD, "uri")

    assert candidate.raw_value == fx.URI_NO_TRAILING_IDENTIFIER
    assert candidate.canonical_value is None
    assert candidate.parse_failure_reason is not None
    assert candidate.parse_failure_reason.strip() != ""

    result = v.resolve_canonical_identity(fx.UNPARSEABLE_URI_RECORD)
    assert result.status is IdentityResolutionStatus.UNRESOLVED
    assert [candidate.raw_value for candidate in result.candidates] == [
        fx.URI_NO_TRAILING_IDENTIFIER
    ]
    assert [issue.code for issue in result.issues] == ["identity_candidate_unparseable"]


@pytest.mark.lreq("LREQ-EXT-060")
def test_empty_candidates_are_dropped_not_fabricated() -> None:
    """Empty, whitespace, absent, and non-string candidates never become candidates."""
    # Every candidate empty or whitespace-only: nothing is retained, and nothing is
    # fabricated in their place.
    assert v.collect_identity_candidates(fx.EMPTY_CANDIDATES_RECORD) == ()
    assert _candidate_source_fields(fx.EMPTY_CANDIDATES_RECORD) == []

    # Absent fields are absent, not empty candidates.
    assert v.collect_identity_candidates(fx.ABSENT_CANDIDATE_FIELDS_RECORD) == ()

    # Non-string values are unusable candidates and are never coerced to text.
    non_string_candidates = v.collect_identity_candidates(fx.NON_STRING_CANDIDATES_RECORD)
    assert non_string_candidates == ()
    # In particular, the integer ``1234567`` must not be stringified into a
    # candidate, and ``None`` must not become "None" or "".
    assert all(candidate.raw_value not in ("1234567", "None", "") for candidate in non_string_candidates)

    # A mixed record keeps only the usable candidate and invents no placeholder for
    # the rest.
    mixed = {
        "ec_product_id": fx.CANONICAL_ASSET_ID,
        "permanentid": "   ",
        "clickUri": None,
        "uri": ["not-a-string"],
    }
    assert _candidate_source_fields(mixed) == ["ec_product_id"]

    # A record with no usable candidate cannot become an ordinary asset: it is
    # explicitly unresolved, and its canonical key is ``None`` rather than ``""``
    # or ``"0"``.
    unresolved = v.resolve_canonical_identity(fx.EMPTY_CANDIDATES_RECORD)
    assert unresolved.status is IdentityResolutionStatus.UNRESOLVED
    assert unresolved.canonical_identity_key is None
    assert unresolved.canonical_identity_key not in FABRICATED_IDENTITY_VALUES


# --------------------------------------------------------------------------
# LREQ-EXT-070 — agreement, conflict, unresolved, and population membership
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-EXT-070")
def test_agreeing_candidates_resolve() -> None:
    """Agreeing candidates resolve to one canonical key and join both populations."""
    for name in ("agreeing", "agreeing_after_canonicalization"):
        result = v.resolve_canonical_identity(fx.IDENTITY_RECORDS[name])

        assert result.status is IdentityResolutionStatus.RESOLVED, name
        assert result.canonical_identity_key == fx.CANONICAL_ASSET_ID, name
        assert result.reason is None, name
        assert result.included_in_canonical_denominator is True, name
        assert result.included_in_enrichment_set is True, name
        assert result.mapping_rule_version == IDENTITY_MAPPING_RULE_VERSION, name
        assert not [issue for issue in result.issues if issue.code == "identity_unresolved"]
        assert result.issues == (), name

    # Single-source records agree with themselves and resolve.
    for name in ("ec_product_id_only", "permanentid_only", "click_uri_only", "uri_only"):
        result = v.resolve_canonical_identity(fx.IDENTITY_RECORDS[name])

        assert result.status is IdentityResolutionStatus.RESOLVED, name
        assert result.canonical_identity_key == fx.CANONICAL_ASSET_ID, name
        assert result.reason is None, name

    # Numerically equal but textually different forms agree (R-2): the values only
    # become one identity after canonicalization.
    for raw_form in fx.NUMERICALLY_EQUAL_RAW_FORMS:
        assert v.resolve_canonical_identity({"ec_product_id": raw_form}).status is (
            IdentityResolutionStatus.RESOLVED
        ), raw_form
    assert (
        v.resolve_canonical_identity({"ec_product_id": "123", "permanentid": " 123 "}).status
        is IdentityResolutionStatus.RESOLVED
    )


@pytest.mark.lreq("LREQ-EXT-070")
def test_disagreeing_candidates_become_conflict() -> None:
    """Any disagreement between derived candidates is an explicit conflict."""
    result = v.resolve_canonical_identity(fx.DISAGREEING_PRODUCT_IDS_RECORD)

    assert result.status is IdentityResolutionStatus.CONFLICT
    assert result.canonical_identity_key is None
    assert result.reason is not None
    assert result.reason.strip() != ""
    assert result.included_in_canonical_denominator is False
    assert result.included_in_enrichment_set is False

    # Both disagreeing candidates are retained verbatim for audit.
    assert [candidate.raw_value for candidate in result.candidates] == ["1234567", "7654321"]

    # The same classification holds when the disagreement is only between a product
    # identifier and a URI-derived one.
    uri_result = v.resolve_canonical_identity(fx.DISAGREEING_URI_RECORD)
    assert uri_result.status is IdentityResolutionStatus.CONFLICT
    assert uri_result.canonical_identity_key is None
    assert uri_result.reason is not None

    # A disagreement is a conflict, never a majority decision or a first-wins pick.
    assert uri_result.status is not IdentityResolutionStatus.RESOLVED


@pytest.mark.lreq("LREQ-EXT-070")
def test_no_canonicalizable_candidate_becomes_unresolved() -> None:
    """Nothing derivable from any candidate is an explicit unresolved record."""
    result = v.resolve_canonical_identity(fx.UNPARSEABLE_URI_RECORD)

    assert result.status is IdentityResolutionStatus.UNRESOLVED
    assert result.canonical_identity_key is None
    assert result.reason is not None
    assert result.reason.strip() != ""
    assert result.included_in_canonical_denominator is False
    assert result.included_in_enrichment_set is False

    # An absent record is unresolved rather than resolved-with-nothing.
    absent = v.resolve_canonical_identity(fx.ABSENT_CANDIDATE_FIELDS_RECORD)
    assert absent.status is IdentityResolutionStatus.UNRESOLVED
    assert absent.candidates == ()
    assert absent.canonical_identity_key is None

    # An unparseable candidate does not silently vote: it is reported, and the
    # record does not become conflict-free by omission or resolve to a guess.
    assert tuple(issue.code for issue in result.issues) == ("identity_candidate_unparseable",)


@pytest.mark.lreq("LREQ-EXT-070")
def test_uri_derived_proper_suffix_of_anchor_is_conflict() -> None:
    """A URI identifier that is only a *suffix* of the explicit anchor is a conflict.

    The comparison is exact equality, so ``product-1234567`` and the URI-derived
    ``1234567`` are two distinct canonical identities and ``LREQ-EXT-070`` makes
    the record ``conflict``. A suffix-tolerant comparison would have accepted
    ``anchor.endswith(key)`` here and wrongly resolved the record, so this node
    is what makes that behavior observable — the pre-existing
    ``DISAGREEING_URI_RECORD`` cannot, because its URI identifier ``9999999`` is
    neither equal to nor a suffix of the ``1234567`` anchor.

    What this proves is narrow, and it is stated rather than implied: it fixes
    the *comparison* policy for a proper-suffix pair. It does **not** verify the
    URI trailing-identifier extraction rule against a real captured Coveo
    response — that rule remains inferred and capture-unverified
    (``interfaces/chunk-01.md`` §4.1 caveat, ``interfaces/chunk-03.md`` §8).
    """
    anchor = fx.EXPLICIT_ANCHOR_WITH_SUFFIX_URI_IDENTIFIER
    derived = v.canonicalize_identity_candidate(fx.URI_CARRYING_RECORD_SUFFIX_OF_ANCHOR)

    # The fixture's whole point is the relationship between the two values; assert
    # the relationship itself rather than trusting the fixture's shape.
    assert derived == fx.CANONICAL_ASSET_ID
    assert anchor == f"product-{fx.CANONICAL_ASSET_ID}"
    assert anchor != derived
    assert anchor.endswith(derived)

    result = v.resolve_canonical_identity(fx.DISAGREEING_SUFFIX_URI_RECORD)

    assert result.status is IdentityResolutionStatus.CONFLICT
    assert result.canonical_identity_key is None
    assert result.reason is not None
    assert result.included_in_canonical_denominator is False
    assert result.included_in_enrichment_set is False

    # Every candidate is retained verbatim: the record is excluded for audit, not
    # discarded, and the suffix relationship survives in the evidence.
    assert [candidate.source_field for candidate in result.candidates] == [
        "ec_product_id",
        "permanentid",
        "clickUri",
    ]
    assert result.candidates[2].canonical_value == fx.CANONICAL_ASSET_ID


@pytest.mark.lreq("LREQ-EXT-070")
def test_conflict_excluded_from_denominator_and_enrichment() -> None:
    """A conflict is explicitly excluded from both populations."""
    for name in ("disagreeing_product_ids", "disagreeing_uri"):
        result = v.resolve_canonical_identity(fx.IDENTITY_RECORDS[name])

        assert result.status is IdentityResolutionStatus.CONFLICT, name
        assert result.included_in_canonical_denominator is False, name
        assert result.included_in_enrichment_set is False, name
        assert result.canonical_identity_key is None, name
        assert result.reason is not None, name


@pytest.mark.lreq("LREQ-EXT-070")
def test_unresolved_excluded_from_denominator_and_enrichment() -> None:
    """An unresolved identity is explicitly excluded from both populations."""
    for name in (
        "unparseable_uri",
        "empty_candidates",
        "non_string_candidates",
    ):
        result = v.resolve_canonical_identity(fx.IDENTITY_RECORDS[name])

        assert result.status is IdentityResolutionStatus.UNRESOLVED, name
        assert result.included_in_canonical_denominator is False, name
        assert result.included_in_enrichment_set is False, name
        assert result.canonical_identity_key is None, name
        assert result.reason is not None, name


@pytest.mark.lreq("LREQ-EXT-070")
def test_conflict_and_unresolved_never_ordinary_asset() -> None:
    """Neither case is ever returned with a key or with a fabricated identifier."""
    for name, record in fx.IDENTITY_RECORDS.items():
        result = v.resolve_canonical_identity(record)

        assert result.status in (
            IdentityResolutionStatus.RESOLVED,
            IdentityResolutionStatus.UNRESOLVED,
            IdentityResolutionStatus.CONFLICT,
        ), name

        if result.status in (
            IdentityResolutionStatus.CONFLICT,
            IdentityResolutionStatus.UNRESOLVED,
        ):
            assert result.canonical_identity_key is None, name
            assert result.canonical_identity_key not in FABRICATED_IDENTITY_VALUES, name
            assert result.reason is not None, name
            assert result.included_in_canonical_denominator is False, name
            assert result.included_in_enrichment_set is False, name
            # An excluded record is never recorded as a resolved ordinary asset.
            assert result.status is not IdentityResolutionStatus.RESOLVED, name

    # An empty-string and an all-whitespace record must not become ``""`` or ``"0"``.
    for record in (
        {"ec_product_id": ""},
        {"permanentid": "   "},
        {"ec_product_id": None},
        {"ec_product_id": 0},
    ):
        result = v.resolve_canonical_identity(record)
        assert result.canonical_identity_key is None
        assert result.status is IdentityResolutionStatus.UNRESOLVED
        assert result.included_in_canonical_denominator is False
        assert result.included_in_enrichment_set is False


# --------------------------------------------------------------------------
# LREQ-GQL-060 — pure state annotation (not a metric-eligibility decision)
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-GQL-060")
def test_published_state_annotated_eligible() -> None:
    """``published`` is annotated as the published state, and nothing else."""
    annotation = v.annotate_state_eligibility(fx.STATE_VECTORS["published"])

    assert annotation.is_published is True
    assert annotation.state_excluded is False
    assert annotation.state_unknown is False
    assert annotation.state_value == "published"

    # The comparison is on the state vocabulary, not on raw case.
    assert v.annotate_state_eligibility("Published").is_published is True
    assert v.annotate_state_eligibility(" published ").is_published is True


@pytest.mark.lreq("LREQ-GQL-060")
def test_state_excluded_annotation() -> None:
    """A present non-published state is annotated as state-excluded."""
    annotation = v.annotate_state_eligibility(fx.STATE_VECTORS["excluded"])

    assert annotation.is_published is False
    assert annotation.state_excluded is True
    assert annotation.state_unknown is False
    assert annotation.state_value == "draft"
    assert annotation.remains_in_discovered_breadth is True

    assert v.annotate_state_eligibility("archived").state_excluded is True
    assert v.annotate_state_eligibility("archived").state_unknown is False

    # The annotation decides on the state vocabulary, not on raw case: a differently
    # cased or padded published state is still published, and anything else present
    # is excluded.
    assert v.annotate_state_eligibility("PUBLISHED").is_published is True
    assert v.annotate_state_eligibility("Draft").state_excluded is True


@pytest.mark.lreq("LREQ-GQL-060")
def test_state_unknown_annotation() -> None:
    """A missing, null, or wrong-typed state is annotated as unknown."""
    for name in ("null", "wrong_type", "wrong_type_list", "wrong_type_bool", "excluded_empty"):
        annotation = v.annotate_state_eligibility(fx.STATE_VECTORS[name])

        assert annotation.is_published is False, name
        assert annotation.state_excluded is False, name
        assert annotation.state_unknown is True, name
        assert annotation.state_value is None, name

    # An absent state is unknown, not excluded and not published.
    absent = v.annotate_state_eligibility(None)
    assert absent == v.annotate_state_eligibility(None)
    assert absent.state_unknown is True
    assert absent.state_value is None

    # A whitespace-only string carries no usable state value either.
    whitespace = v.annotate_state_eligibility("   ")
    assert whitespace.state_unknown is True
    assert whitespace.state_value is None


@pytest.mark.lreq("LREQ-GQL-060")
def test_state_annotation_keeps_asset_in_discovered_breadth() -> None:
    """Every state annotation keeps the asset in discovered breadth."""
    for name, state_value in fx.STATE_VECTORS.items():
        annotation = v.annotate_state_eligibility(state_value)

        assert annotation.remains_in_discovered_breadth is True, name

    for state_value in ("published", "draft", None, 7, ["published"], True, ""):
        assert v.annotate_state_eligibility(state_value).remains_in_discovered_breadth is True


@pytest.mark.lreq("LREQ-GQL-060")
def test_state_annotation_is_not_metric_eligibility() -> None:
    """The annotation is exactly one of three flags and no D/R/Q verdict."""
    for name, state_value in fx.STATE_VECTORS.items():
        annotation = v.annotate_state_eligibility(state_value)

        flags = (annotation.is_published, annotation.state_excluded, annotation.state_unknown)
        assert sum(flag is True for flag in flags) == 1, name
        assert all(isinstance(flag, bool) for flag in flags), name

    # There is no metric-eligibility verdict on the annotation: the only fields are
    # the state value, the three exclusive flags, and the breadth invariant. Whether
    # a published state makes an asset eligible for D, R, and Q is Chunk 7A's.
    field_names = set(type(v.annotate_state_eligibility("published")).__slots__)
    assert field_names == {
        "state_value",
        "is_published",
        "state_excluded",
        "state_unknown",
        "remains_in_discovered_breadth",
    }
    assert not any(
        forbidden in field_name
        for field_name in field_names
        for forbidden in ("metric", "eligible_for", "demand", "rating", "quality", "score")
    )

    # Annotating a state never produces a metric-eligibility attribute, so a caller
    # cannot mistake the annotation for the D/R/Q decision.
    annotation = v.annotate_state_eligibility("published")
    for forbidden in ("is_metric_eligible", "eligible_for_demand", "metric_eligibility"):
        assert not hasattr(annotation, forbidden), forbidden


# --------------------------------------------------------------------------
# LREQ-GQL-070 / LREQ-ID-020 — alias comparison and identity compatibility
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-GQL-070")
def test_matching_alias_after_canonicalization() -> None:
    """Aliases agreeing after canonicalization match the requested identity."""
    for name in ("agreeing", "extra_alias_source", "shared_operation_key"):
        result = v.compare_graphql_identity_aliases(
            fx.REQUESTED_IDENTITY, fx.GQL_ALIAS_MAPS[name]
        )

        assert result.matches_requested_identity is True, name
        assert result.id_mapping_mismatch is False, name
        assert result.reason is None, name
        assert result.issues == (), name

    # When the map reports the canonicalized value, the compared aliases are the
    # canonical ones: a whitespace-padded alias agrees with the bare requested
    # identifier, which raw string equality would have rejected.
    padded = {
        "graphql_id": f" {fx.CANONICAL_ASSET_ID} ",
        "product_id": fx.CANONICAL_ASSET_ID,
    }
    padded_result = v.compare_graphql_identity_aliases(fx.REQUESTED_IDENTITY, padded)
    assert padded_result.matches_requested_identity is True
    assert padded_result.id_mapping_mismatch is False
    assert dict(padded_result.compared_aliases) == {
        "graphql_id": fx.CANONICAL_ASSET_ID,
        "product_id": fx.CANONICAL_ASSET_ID,
    }
    # Comparison is on canonical values, but the padding is not lost: the same raw
    # value canonicalizes to the identifier when it is a product-id candidate.
    assert dict(padded_result.compared_aliases)["graphql_id"] == fx.CANONICAL_ASSET_ID
    raw_candidate = _candidate_for(
        {"ec_product_id": f" {fx.CANONICAL_ASSET_ID} "}, "ec_product_id"
    )
    assert raw_candidate.raw_value == f" {fx.CANONICAL_ASSET_ID} "
    assert raw_candidate.canonical_value == fx.CANONICAL_ASSET_ID

    # The alias named ``uri`` is read with the URI rule, so a URI-shaped alias also
    # agrees after canonicalization.
    uri_alias = v.compare_graphql_identity_aliases(
        fx.REQUESTED_IDENTITY, {"uri": fx.URI_WITH_SLUG_IDENTIFIER}
    )
    assert uri_alias.matches_requested_identity is True
    assert dict(uri_alias.compared_aliases) == {"uri": fx.CANONICAL_ASSET_ID}

    # A requested identity supplied as a URI canonicalizes to the same target.
    uri_request = v.compare_graphql_identity_aliases(
        fx.URI_WITH_SLUG_IDENTIFIER, fx.GQL_ALIAS_MAPS["agreeing"]
    )
    assert uri_request.matches_requested_identity is True
    assert uri_request.id_mapping_mismatch is False


@pytest.mark.lreq("LREQ-GQL-070")
def test_disagreeing_alias_sets_id_mapping_mismatch() -> None:
    """A disagreeing alias sets the mismatch flag and clears agreement."""
    result = v.compare_graphql_identity_aliases(
        fx.REQUESTED_IDENTITY, fx.GQL_ALIAS_MAPS["disagreeing"]
    )

    assert result.id_mapping_mismatch is True
    assert result.matches_requested_identity is False
    assert result.reason is not None
    assert result.reason.strip() != ""

    # The mismatch is typed, so a caller reports it without inspecting the payload.
    assert [issue.code for issue in result.issues] == ["graphql_id_mapping_mismatch"]

    # ``id_mapping_mismatch`` always implies the agreement flag is ``False``.
    for name, aliases in fx.GQL_ALIAS_MAPS.items():
        comparison = v.compare_graphql_identity_aliases(fx.REQUESTED_IDENTITY, aliases)
        assert comparison.id_mapping_mismatch is (not comparison.matches_requested_identity), name


@pytest.mark.lreq("LREQ-GQL-070")
def test_missing_alias_is_mismatch_not_agreement() -> None:
    """An absent alias is a mismatch with a reason, never agreement."""
    for name in ("missing", "null_alias"):
        result = v.compare_graphql_identity_aliases(
            fx.REQUESTED_IDENTITY, fx.GQL_ALIAS_MAPS[name]
        )

        assert result.id_mapping_mismatch is True, name
        assert result.matches_requested_identity is False, name
        assert result.reason is not None, name
        assert "missing" in result.reason or "no GraphQL identity alias" in result.reason, name

    # An empty alias map is missing rather than vacuously agreeing.
    empty = v.compare_graphql_identity_aliases(fx.REQUESTED_IDENTITY, {})
    assert empty.id_mapping_mismatch is True
    assert empty.matches_requested_identity is False

    # A partially absent alias set is still a mismatch, even though one alias
    # agrees: an absent alias is never treated as agreement.
    partial = v.compare_graphql_identity_aliases(
        fx.REQUESTED_IDENTITY, {"graphql_id": fx.CANONICAL_ASSET_ID, "product_id": None}
    )
    assert partial.id_mapping_mismatch is True
    assert partial.matches_requested_identity is False

    # The absent alias is reported by name, so the mismatch is diagnosable without
    # inspecting the returned payload.
    assert "product_id" in (partial.reason or "")

    # An alias that is present but unusable — null, non-string, or empty — is a
    # missing alias, not a disagreement or a silent pass.
    for name in ("null_alias", "missing"):
        unusable = v.compare_graphql_identity_aliases(
            fx.REQUESTED_IDENTITY, fx.GQL_ALIAS_MAPS[name]
        )
        assert unusable.id_mapping_mismatch is True, name
        assert unusable.matches_requested_identity is False, name


@pytest.mark.lreq("LREQ-GQL-070")
def test_unparseable_alias_is_mismatch_with_reason() -> None:
    """An alias that cannot be canonicalized is a mismatch with an explicit reason."""
    result = v.compare_graphql_identity_aliases(
        fx.REQUESTED_IDENTITY, fx.GQL_ALIAS_MAPS["unparseable"]
    )

    assert result.id_mapping_mismatch is True
    assert result.matches_requested_identity is False
    assert result.reason is not None
    assert result.reason.strip() != ""

    # The reason names the alias keys that could not be canonicalized, but not their
    # raw values: an unusable alias value is reported structurally. Only
    # ``clickUri``/``uri`` can fail to canonicalize under mapping rule 1.0.1 —
    # ``product_id`` is canonical as-supplied (see the fixture's own note), so it is
    # non-agreeing rather than unparseable and is correctly absent from the reason.
    unparseable_alias = "clickUri"
    assert unparseable_alias in result.reason
    assert "product_id" not in result.reason, (
        "a canonical-as-supplied alias is non-agreeing, not unparseable"
    )
    # The unparseable alias's raw text never survives into a compared value: an
    # unusable alias is reported structurally (its name, not its content).
    unparsed_raw = fx.GQL_ALIAS_MAPS["unparseable"]["clickUri"]
    assert unparsed_raw not in result.reason
    assert all(
        unparsed_raw not in compared_value for _n, compared_value in result.compared_aliases
    )
    # Plan §11's no-leakage rule covers credential-shaped values, not every
    # business-domain field: a canonical-as-supplied alias is compared verbatim, so
    # its value is legitimately present in ``compared_aliases``.
    assert (
        "product_id",
        fx.GQL_ALIAS_MAPS["unparseable"]["product_id"],
    ) in result.compared_aliases
    for raw_value in fx.GQL_ALIAS_MAPS["unparseable"].values():
        assert raw_value not in result.reason

    # A non-string alias is unusable and therefore a mismatch, not a silent pass.
    non_string_alias = v.compare_graphql_identity_aliases(
        fx.REQUESTED_IDENTITY, {"graphql_id": 1234567}
    )
    assert non_string_alias.id_mapping_mismatch is True
    assert non_string_alias.reason is not None
    # The integer alias is never coerced into the canonical identifier it resembles.
    assert all(
        compared_value != fx.CANONICAL_ASSET_ID
        for _alias_name, compared_value in non_string_alias.compared_aliases
    )


@pytest.mark.lreq("LREQ-ID-020")
def test_requested_identity_compatibility_comparison() -> None:
    """Returned identifiers are compared for compatibility with the requested identity."""
    # Compatible: the returned aliases canonicalize to the requested identifier.
    compatible = v.compare_graphql_identity_aliases(
        fx.REQUESTED_IDENTITY, {"graphql_id": fx.CANONICAL_ASSET_ID}
    )
    assert compatible.matches_requested_identity is True
    assert compatible.id_mapping_mismatch is False

    # Incompatible: a returned identifier differs from the requested identity.
    incompatible = v.compare_graphql_identity_aliases(
        fx.REQUESTED_IDENTITY, {"graphql_id": "9999999"}
    )
    assert incompatible.matches_requested_identity is False
    assert incompatible.id_mapping_mismatch is True

    # The comparison is symmetric in the mapping rule's numeric-or-string
    # convention: textually different but numerically equal identifiers are
    # compatible, and textually identical values with different magnitudes are not.
    assert (
        v.compare_graphql_identity_aliases(
            "123", {"product_id": " 123 "}
        ).matches_requested_identity
        is True
    )
    assert (
        v.compare_graphql_identity_aliases(
            "123", {"product_id": "1234"}
        ).matches_requested_identity
        is False
    )

    # A requested identity that cannot itself be canonicalized yields an explicit
    # incompatibility rather than a vacuous agreement.
    unusable_request = v.compare_graphql_identity_aliases(
        fx.URI_NO_TRAILING_IDENTIFIER, {"graphql_id": fx.CANONICAL_ASSET_ID}
    )
    assert unusable_request.matches_requested_identity is False
    assert unusable_request.id_mapping_mismatch is True
    assert unusable_request.reason is not None

    # Only the pure comparison is produced here: preflight execution, the persisted
    # asset marking, and metric exclusion are Chunks 6A/5/7A.
    assert set(v.GraphQLIdentityComparisonResult.__slots__) == {
        "matches_requested_identity",
        "id_mapping_mismatch",
        "reason",
        "compared_aliases",
        "issues",
    }


# --------------------------------------------------------------------------
# LREQ-GQL-010 — the shared canonical identity unit
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-GQL-010")
def test_canonical_identity_key_type_is_shared_identity_unit() -> None:
    """canonical_identity_key is a string (or None), the shared canonical identity unit."""
    resolved = v.resolve_canonical_identity(fx.AGREEING_IDENTITY_RECORD)
    assert resolved.canonical_identity_key is not None
    assert isinstance(resolved.canonical_identity_key, str)
    assert resolved.canonical_identity_key == fx.CANONICAL_ASSET_ID

    # When unresolved or conflict, canonical_identity_key is None, never a placeholder
    unresolved = v.resolve_canonical_identity(fx.EMPTY_CANDIDATES_RECORD)
    assert unresolved.canonical_identity_key is None


# --------------------------------------------------------------------------
# LREQ-SMP-010 — resolution status supports population exclusion
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SMP-010")
def test_resolution_status_supports_population_exclusion() -> None:
    """Resolution status carries the flags a sampling population filter needs."""
    resolvable = v.resolve_canonical_identity(fx.AGREEING_IDENTITY_RECORD)
    excluded = {
        name: v.resolve_canonical_identity(record)
        for name, record in fx.IDENTITY_RECORDS.items()
        if name in ("disagreeing_product_ids", "disagreeing_uri", "unparseable_uri", "empty_candidates")
    }

    # A resolved record is the only one that may enter the canonical population.
    assert resolvable.status is IdentityResolutionStatus.RESOLVED
    assert resolvable.included_in_canonical_denominator is True

    # Every unresolved or conflicting record is excluded from the population the
    # sampler draws from, and says so on the result rather than leaving the caller
    # to re-derive it from the status.
    for name, result in excluded.items():
        assert result.status in (
            IdentityResolutionStatus.UNRESOLVED,
            IdentityResolutionStatus.CONFLICT,
        ), name
        assert result.included_in_canonical_denominator is False, name
        assert result.included_in_enrichment_set is False, name

    # The exclusion is exactly the complement of resolution across every fixture, so
    # a sampler can filter on the flag without inventing its own rule. Population
    # construction, duplicate marking, and ordinal ordering remain Chunk 4A's.
    for name, record in fx.IDENTITY_RECORDS.items():
        result = v.resolve_canonical_identity(record)
        assert result.included_in_canonical_denominator is (
            result.status is IdentityResolutionStatus.RESOLVED
        ), name
        assert result.included_in_enrichment_set is (
            result.status is IdentityResolutionStatus.RESOLVED
        ), name

    # A record missing its identity entirely is likewise excluded from the
    # post-resolution population rather than silently sampled as an ordinary asset.
    absent = v.resolve_canonical_identity(fx.ABSENT_CANDIDATE_FIELDS_RECORD)
    assert absent.included_in_canonical_denominator is False


# --------------------------------------------------------------------------
# LREQ-TST-030 — suite coverage and cross-category duplicate identities
# --------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-TST-030")
def test_identity_suite_covers_valid_malformed_unresolved_conflict_uri_and_mismatch() -> None:
    """The identity suite covers every case LREQ-TST-030 names, including duplicates."""
    # Each required case is exercised here through the fixtures it depends on, so
    # the coverage claim is checked against live behavior rather than asserted.
    required_cases = {
        "valid_canonical_candidates": v.resolve_canonical_identity(
            fx.AGREEING_IDENTITY_RECORD
        ),
        "malformed_fallback": v.resolve_canonical_identity(fx.UNPARSEABLE_URI_RECORD),
        "unresolved_identity": v.resolve_canonical_identity(fx.EMPTY_CANDIDATES_RECORD),
        "conflicting_candidates": v.resolve_canonical_identity(
            fx.DISAGREEING_PRODUCT_IDS_RECORD
        ),
    }
    assert required_cases["valid_canonical_candidates"].status is IdentityResolutionStatus.RESOLVED
    assert required_cases["malformed_fallback"].status is IdentityResolutionStatus.UNRESOLVED
    assert required_cases["unresolved_identity"].status is IdentityResolutionStatus.UNRESOLVED
    assert required_cases["conflicting_candidates"].status is IdentityResolutionStatus.CONFLICT

    # URI parsing: the identifier comes from the last path segment and nowhere else.
    assert v.canonicalize_identity_candidate(fx.URI_WITH_SLUG_IDENTIFIER) == fx.CANONICAL_ASSET_ID
    assert _candidate_for({"uri": fx.URI_NO_TRAILING_IDENTIFIER}, "uri").canonical_value is None

    # GraphQL mismatch: a disagreeing alias is reported, never silently accepted.
    mismatch = v.compare_graphql_identity_aliases(
        fx.REQUESTED_IDENTITY, fx.GQL_ALIAS_MAPS["disagreeing"]
    )
    assert mismatch.id_mapping_mismatch is True

    # Duplicate cross-category identities (R-6): the same asset discovered under two
    # different categories canonicalizes to one identity, so the duplicate is
    # recognizable as the same identity independent of category. Counting, duplicate
    # marking, and persistence stay in Chunks 3, 4B, and 6B.
    tools_category_record = {
        "category": "Tools/Utilities/Editor Extensions",
        "permanentid": fx.CANONICAL_ASSET_ID,
        "clickUri": fx.URI_WITH_SLUG_IDENTIFIER,
    }
    audio_category_record = {
        "category": "Audio/Music",
        "ec_product_id": f" {fx.CANONICAL_ASSET_ID} ",
        "uri": f"https://assetstore.unity.com/packages/audio/music/ambient-kit-{fx.CANONICAL_ASSET_ID}",
    }
    assert tools_category_record["category"] != audio_category_record["category"]

    tools_identity = v.resolve_canonical_identity(tools_category_record)
    audio_identity = v.resolve_canonical_identity(audio_category_record)
    assert tools_identity.status is IdentityResolutionStatus.RESOLVED
    assert audio_identity.status is IdentityResolutionStatus.RESOLVED
    assert tools_identity.canonical_identity_key == audio_identity.canonical_identity_key

    # The resolution result itself carries no category-derived field: the identity
    # is a property of the asset, not of the category it was discovered under.
    assert not any(
        "categor" in field_name for field_name in type(tools_identity).__slots__
    )
    assert v.collect_identity_candidates(tools_category_record) == v.collect_identity_candidates(
        {name: value for name, value in tools_category_record.items() if name != "category"}
    )


# --------------------------------------------------------------------------
# Chunk 5 / LREQ-GQL-070 - adapter-level identity mismatch marking
# --------------------------------------------------------------------------


#: A caller-supplied UTC instant; the adapter never reads the clock.
_IDENTITY_EXCHANGE_RETRIEVED_AT = datetime(2026, 9, 17, 4, 30, 0, tzinfo=timezone.utc)


def _enrich_identity(
    body_text: str,
) -> tuple[
    collector_graphql.EnrichmentResult,
    collector_graphql.EnrichmentObservationDraft,
]:
    """Run one adapter exchange for the fixture identity against ``body_text``."""
    transport = gqlfx.RecordingTransport([{"http_status": 200, "body_text": body_text}])
    return collector_graphql.enrich_asset(
        gqlfx.GQL_FIXTURE_ASSET_ID,
        credentials=gqlfx.GQL_CREDENTIALS,
        transport=transport,
        correlation_mode=GraphQLOperationCorrelationMode.EXPLICIT_KEY,
        retrieved_at_utc=_IDENTITY_EXCHANGE_RETRIEVED_AT,
        sleep=gqlfx.RecordingSleeper(),
    )


def _mismatch_body() -> str:
    """Return a correlated body whose ProductDetail aliases disagree."""
    return gqlfx.correlation_body(
        {
            "operationName": gqlfx.GQL_OPERATION_NAMES[0],
            "data": gqlfx.IDENTITY_MISMATCH_PRODUCT_DETAIL_PAYLOAD,
        },
        {
            "operationName": gqlfx.GQL_OPERATION_NAMES[1],
            "data": {"pageViews": 4321},
        },
    )


@pytest.mark.lreq("LREQ-GQL-070")
def test_correlated_product_detail_reports_alias_mismatch() -> None:
    """A correlated ProductDetail with disagreeing aliases is marked mismatched."""
    result, draft = _enrich_identity(_mismatch_body())

    # The association is a real correlation, so the mismatch is reported on a
    # correlated payload rather than being confused with a correlation failure.
    assert result.correlation.is_fully_correlated
    assert result.product_detail.is_success
    assert result.page_views.is_success

    # The requested identity is the fixture identity; the returned aliases are a
    # different identifier, so the adapter marks the affected result.
    assert draft.asset_identity_key == gqlfx.GQL_FIXTURE_ASSET_ID
    assert draft.graphql_id == gqlfx.GQL_FIXTURE_ASSET_ID_OTHER
    assert draft.product_id == gqlfx.GQL_FIXTURE_ASSET_ID_OTHER
    assert draft.id_mapping_mismatch is True
    assert "graphql_id_mapping_mismatch" in {
        issue.code for issue in result.product_detail.issues
    }

    # The agreeing case does not raise the flag, so the flag reports the
    # comparison rather than being a constant.
    _agreeing, agreeing_draft = _enrich_identity(gqlfx.in_order_success_body())
    assert agreeing_draft.id_mapping_mismatch is False


@pytest.mark.lreq("LREQ-GQL-070")
def test_missing_returned_identity_is_not_an_implicit_match() -> None:
    """A missing or unusable returned identity is a mismatch, never a match."""
    for body_factory in (
        gqlfx.missing_identity_body,
        gqlfx.missing_identity_member_body,
    ):
        result, draft = _enrich_identity(body_factory())

        # No returned alias is usable, and no alias is fabricated from the
        # request: the draft carries ``None``, never the requested identifier.
        assert draft.graphql_id is None, body_factory.__name__
        assert draft.product_id is None, body_factory.__name__
        assert draft.graphql_id != gqlfx.GQL_FIXTURE_ASSET_ID, body_factory.__name__
        assert draft.product_id != gqlfx.GQL_FIXTURE_ASSET_ID, body_factory.__name__

        # An uncomparable identity is never an implicit match: the flag is set
        # and the operation is an error, not a success with an assumed identity.
        assert draft.id_mapping_mismatch is True, body_factory.__name__
        assert (
            result.product_detail.failure_class
            is collector_graphql.GraphQLFailureClass.MISSING_IDENTITY
        ), body_factory.__name__
        assert not result.product_detail.is_success, body_factory.__name__

        # The failing identity operation does not drag its sibling down.
        assert result.page_views.is_success, body_factory.__name__
        assert draft.product_page_views == 4321, body_factory.__name__


@pytest.mark.lreq("LREQ-GQL-070")
def test_adapter_mismatch_is_a_flag_not_a_metric_exclusion() -> None:
    """The adapter marks ``id_mapping_mismatch`` and emits no D/R/Q verdict."""
    result, draft = _enrich_identity(_mismatch_body())

    # The mark is a flag on an otherwise successful result: the adapter does not
    # turn a mismatch into an operation error or drop the observation.
    assert result.product_detail.is_success
    assert (
        result.product_detail.failure_class
        is collector_graphql.GraphQLFailureClass.NONE
    )
    assert draft.id_mapping_mismatch is True
    record = draft.to_record("run-chunk-05")
    assert record.asset_identity_key == gqlfx.GQL_FIXTURE_ASSET_ID
    assert record.id_mapping_mismatch is True

    # Neither the result nor the draft exposes a D/R/Q, metric-eligibility, or
    # score verdict: exclusion from D, R, and Q is Chunk 7A"s decision.
    for surface in (type(result).__slots__, type(draft).__slots__):
        names = {str(name).casefold() for name in surface}
        for forbidden in (
            "metric",
            "eligib",
            "score",
            "rankab",
            "demand",
            "quality",
        ):
            assert not any(forbidden in name for name in names), forbidden
        assert not ({"d", "r", "q"} & names)

    # The flag is not a metric verdict: the agreeing draft carries the same field
    # set, so no verdict appears only when a mismatch is set.
    _agreeing, agreeing_draft = _enrich_identity(gqlfx.in_order_success_body())
    assert type(agreeing_draft).__slots__ == type(draft).__slots__
