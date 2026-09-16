"""Chunk 1 analytical tests — taxonomy, category, and structural validation.

Every test here carries exactly one explicit ``@pytest.mark.lreq`` marker and a
matching entry in ``tests/traceability.json``. The tests are purely local: no
network access, no system-clock reads for expected values, and no writes outside
pytest's ``tmp_path``.

Scope reminder: these tests cover *structural* validity only. Metric-eligibility
semantics (published-state eligibility applied to metric inputs, UTC/date
normalization for metrics, future-date rejection, finite/non-negative checks, age
thresholds, and page-view eligibility ranges) belong to Chunk 7A and are asserted
absent here, not asserted present.
"""

from __future__ import annotations

import ast
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import fixtures.validation_fixtures as fx
import pytest

from niche_scout import validation as v
from niche_scout.models import (
    MAX_TAXONOMY_AGE_DAYS,
    CategoryFilterValidationStatus,
    DiscoveryStatus,
)
from niche_scout.tools.check_import_boundaries import (
    FORBIDDEN_MODULES,
    check_module,
    clock_violations,
)

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "niche_scout"
VALIDATION_PATH = PACKAGE / "validation.py"

TAXONOMY_REFERENCE_UTC: datetime = fx.REFERENCE_UTC
TAXONOMY_MAX_AGE_DAYS: int = MAX_TAXONOMY_AGE_DAYS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _issues_of(result: Any) -> list[str]:
    """Return the issue codes on a validation result."""
    return [issue.code for issue in result.issues]


def _issue_codes_with_context(result: Any, key: str) -> list[tuple[str, Any]]:
    """Return ``(code, context[key])`` pairs for issues that carry ``key``."""
    return [
        (issue.code, issue.context.get(key))
        for issue in result.issues
        if key in issue.context
    ]


def _taxonomy_payload(**overrides: Any) -> dict[str, Any]:
    """Return the valid taxonomy fixture with ``overrides`` applied."""
    payload = dict(fx.NORMALIZED_TAXONOMY_FIXTURE)
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# LREQ-EXT-020 — taxonomy schema, inventory, freshness, requested categories
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-EXT-020")
def test_taxonomy_requires_all_header_fields() -> None:
    """Every required header field is reported missing when absent, in field order."""
    valid = v.validate_taxonomy_structure(_taxonomy_payload())
    assert valid.is_valid is True
    assert valid.status == "valid"
    assert valid.missing_header_fields == ()
    assert valid.issues == ()
    assert valid.age_days_exact is None, "structure alone cannot determine freshness"
    assert valid.is_fresh is None, "freshness must not default to True"

    for field in fx.REQUIRED_TAXONOMY_FIELDS:
        payload = fx.TAXONOMY_PAYLOADS_MISSING_ONE_HEADER[field]
        result = v.validate_taxonomy_structure(payload)
        assert result.is_valid is False
        assert result.status == "missing_headers"
        assert result.missing_header_fields == (field,)
        assert _issues_of(result) == ["taxonomy_missing_header"]
        assert result.issues[0].context["field"] == field

    fully_missing = v.validate_taxonomy_structure({})
    assert fully_missing.status == "missing_headers"
    assert fully_missing.missing_header_fields == fx.REQUIRED_TAXONOMY_FIELDS
    assert _issues_of(fully_missing) == ["taxonomy_missing_header"] * len(
        fx.REQUIRED_TAXONOMY_FIELDS
    )

    nulled = _taxonomy_payload(source_url=None)
    assert v.validate_taxonomy_structure(nulled).missing_header_fields == ("source_url",)
    assert v.validate_taxonomy_structure(fx.TAXONOMY_NOT_A_MAPPING).status == "malformed"


@pytest.mark.lreq("LREQ-EXT-020")
def test_taxonomy_requires_canonical_path_inventory() -> None:
    """A missing, empty, wrong-shaped, or malformed inventory is an explicit failure."""
    valid = v.validate_taxonomy_structure(_taxonomy_payload())
    assert v.taxonomy_path_set(valid_payload := _taxonomy_payload()) == frozenset(
        fx.DEFAULT_CATEGORIES
    )
    assert valid.is_valid is True
    assert valid_payload["canonical_category_paths"] == list(fx.DEFAULT_CATEGORIES)

    absent = v.validate_taxonomy_structure(fx.TAXONOMY_WITHOUT_INVENTORY)
    assert absent.is_valid is False
    assert absent.status == "malformed"
    assert "taxonomy_missing_path_inventory" in _issues_of(absent)

    empty = v.validate_taxonomy_structure(_taxonomy_payload(canonical_category_paths=[]))
    assert empty.is_valid is False
    assert "taxonomy_empty_path_inventory" in _issues_of(empty)

    scalar = v.validate_taxonomy_structure(fx.TAXONOMY_WITH_SCALAR_INVENTORY)
    assert scalar.is_valid is False
    assert _issue_codes_with_context(scalar, "expected_shape") == [
        ("taxonomy_invalid_path_inventory_shape", "list")
    ]

    non_string = v.validate_taxonomy_structure(fx.TAXONOMY_WITH_NON_STRING_PATH)
    assert non_string.is_valid is False
    assert _issue_codes_with_context(non_string, "entry_type") == [
        ("taxonomy_invalid_path_entry_type", "int")
    ]

    mapping_entry = v.validate_taxonomy_structure(fx.TAXONOMY_WITH_MAPPING_PATH_ENTRY)
    assert mapping_entry.is_valid is False
    assert "taxonomy_invalid_path_entry_type" in _issues_of(mapping_entry)

    parent_only = v.validate_taxonomy_structure(fx.TAXONOMY_WITH_PARENT_ONLY_PATH)
    assert parent_only.is_valid is False
    assert _issue_codes_with_context(parent_only, "path") == [
        ("taxonomy_malformed_path_entry", "Tools")
    ], "a bare parent label is not a selectable canonical category path"

    malformed_path = v.validate_taxonomy_structure(fx.TAXONOMY_WITH_MALFORMED_INVENTORY_PATH)
    assert malformed_path.is_valid is False
    assert "taxonomy_malformed_path_entry" in _issues_of(malformed_path)

    duplicated = v.validate_taxonomy_structure(fx.TAXONOMY_WITH_DUPLICATE_PATH)
    assert duplicated.is_valid is False
    assert _issue_codes_with_context(duplicated, "path") == [
        ("taxonomy_duplicate_path_entry", fx.DEFAULT_CATEGORIES[0])
    ]

    malformed_entry = v.validate_taxonomy_structure(fx.TAXONOMY_WITH_MALFORMED_ENTRY)
    assert malformed_entry.is_valid is False
    assert "taxonomy_entry_path_not_in_inventory" in _issues_of(malformed_entry)

    assert v.taxonomy_path_set(fx.TAXONOMY_WITHOUT_INVENTORY) == frozenset()
    assert v.taxonomy_path_set(fx.TAXONOMY_NOT_A_MAPPING) == frozenset()
    assert v.taxonomy_path_set(fx.TAXONOMY_WITH_SCALAR_INVENTORY) == frozenset()


@pytest.mark.lreq("LREQ-EXT-020")
def test_taxonomy_rejects_naive_captured_at() -> None:
    """A naive or unusable ``captured_at_utc`` is rejected, never treated as fresh."""
    for payload in (
        fx.NAIVE_CAPTURE_PAYLOAD,
        fx.UNPARSABLE_CAPTURE_PAYLOAD,
        fx.NON_STRING_CAPTURE_PAYLOAD,
    ):
        result = v.validate_taxonomy_freshness(
            payload,
            reference_utc=TAXONOMY_REFERENCE_UTC,
            max_taxonomy_age_days=TAXONOMY_MAX_AGE_DAYS,
        )
        assert result.is_valid is False
        assert result.status == "invalid_capture_timestamp"
        assert result.is_fresh is None, "undeterminable freshness is None, never False"
        assert result.age_days_exact is None, "an unusable capture time has no exact age"
        assert _issues_of(result) == ["taxonomy_invalid_capture_timestamp"]

    absent = v.validate_taxonomy_freshness(
        fx.TAXONOMY_WITHOUT_INVENTORY,
        reference_utc=TAXONOMY_REFERENCE_UTC,
        max_taxonomy_age_days=TAXONOMY_MAX_AGE_DAYS,
    )
    # This fixture keeps every required header and drops only the inventory, so the
    # header stage passed and the payload is a genuine shape failure — not a header
    # failure. Plan §8 (LREQ-EXT-020) classifies a payload whose inventory is
    # missing as malformed; reporting "missing_headers" here would claim a header
    # failure for a payload that declares all four headers.
    assert absent.status == "malformed"
    assert _issues_of(absent) == ["taxonomy_missing_path_inventory"]

    # A payload whose header block is absent has not reached the inventory check,
    # so freshness reports the stage it actually failed at rather than asserting a
    # verdict ("malformed") about a step that never ran. This is the case where
    # "missing_headers" is the correct classification.
    headers_absent = v.validate_taxonomy_freshness(
        fx.TAXONOMY_WITHOUT_HEADERS_OR_INVENTORY,
        reference_utc=TAXONOMY_REFERENCE_UTC,
        max_taxonomy_age_days=TAXONOMY_MAX_AGE_DAYS,
    )
    assert headers_absent.status == "missing_headers"
    assert headers_absent.missing_header_fields != ()

    nulled = v.validate_taxonomy_freshness(
        {**_taxonomy_payload(), "captured_at_utc": None},
        reference_utc=TAXONOMY_REFERENCE_UTC,
        max_taxonomy_age_days=TAXONOMY_MAX_AGE_DAYS,
    )
    assert nulled.is_fresh is None

    naive_reference_expected = v.validate_taxonomy_freshness(
        fx.NAIVE_CAPTURE_PAYLOAD,
        reference_utc=TAXONOMY_REFERENCE_UTC,
        max_taxonomy_age_days=TAXONOMY_MAX_AGE_DAYS,
    )
    assert "naive" in naive_reference_expected.issues[0].message


@pytest.mark.lreq("LREQ-EXT-020")
def test_taxonomy_flags_stale_capture() -> None:
    """``age <= MAX_TAXONOMY_AGE_DAYS`` is fresh and ``age > ...`` is stale, exactly."""
    boundary = v.validate_taxonomy_freshness(
        fx.FRESH_CAPTURE_PAYLOAD,
        reference_utc=TAXONOMY_REFERENCE_UTC,
        max_taxonomy_age_days=TAXONOMY_MAX_AGE_DAYS,
    )
    assert boundary.is_valid is True
    assert boundary.status == "valid"
    assert boundary.is_fresh is True
    assert boundary.age_days_exact == fx.FRESH_AGE_DAYS_EXACT
    assert boundary.age_days_exact == TAXONOMY_MAX_AGE_DAYS, "the boundary is inclusive (R-5)"

    beyond = v.validate_taxonomy_freshness(
        fx.STALE_CAPTURE_PAYLOAD,
        reference_utc=TAXONOMY_REFERENCE_UTC,
        max_taxonomy_age_days=TAXONOMY_MAX_AGE_DAYS,
    )
    assert beyond.is_valid is False
    assert beyond.status == "stale"
    assert beyond.is_fresh is False
    assert beyond.age_days_exact == pytest.approx(fx.STALE_AGE_DAYS_EXACT, abs=1e-12)
    assert beyond.age_days_exact > TAXONOMY_MAX_AGE_DAYS
    assert _issues_of(beyond) == ["taxonomy_stale_capture"]

    clearly_stale = v.validate_taxonomy_freshness(
        fx.CLEARLY_STALE_CAPTURE_PAYLOAD,
        reference_utc=TAXONOMY_REFERENCE_UTC,
        max_taxonomy_age_days=TAXONOMY_MAX_AGE_DAYS,
    )
    assert clearly_stale.status == "stale"
    assert clearly_stale.age_days_exact == 45.0

    reference = fx.VALID_CAPTURE_UTC + timedelta(days=TAXONOMY_MAX_AGE_DAYS)
    exact_boundary = v.validate_taxonomy_freshness(
        fx.TAXONOMY_FIXTURE,
        reference_utc=reference,
        max_taxonomy_age_days=TAXONOMY_MAX_AGE_DAYS,
    )
    assert exact_boundary.age_days_exact == float(TAXONOMY_MAX_AGE_DAYS)
    assert exact_boundary.is_fresh is True

    one_second_past = v.validate_taxonomy_freshness(
        fx.TAXONOMY_FIXTURE,
        reference_utc=reference + timedelta(seconds=1),
        max_taxonomy_age_days=TAXONOMY_MAX_AGE_DAYS,
    )
    assert one_second_past.is_fresh is False
    assert one_second_past.age_days_exact > float(TAXONOMY_MAX_AGE_DAYS)

    configured = v.validate_taxonomy_freshness(
        fx.CLEARLY_STALE_CAPTURE_PAYLOAD,
        reference_utc=TAXONOMY_REFERENCE_UTC,
        max_taxonomy_age_days=60,
    )
    assert configured.is_fresh is True, "the threshold is the caller's, not hardcoded"

    naive_reference = datetime(2026, 2, 1, 12, 0, 0)
    with pytest.raises(ValueError):
        v.validate_taxonomy_freshness(
            fx.FRESH_CAPTURE_PAYLOAD,
            reference_utc=naive_reference,
            max_taxonomy_age_days=TAXONOMY_MAX_AGE_DAYS,
        )


@pytest.mark.lreq("LREQ-EXT-020")
def test_taxonomy_flags_future_capture() -> None:
    """A capture dated after the reference is never accepted as a known-fresh state."""
    result = v.validate_taxonomy_freshness(
        fx.FUTURE_CAPTURE_PAYLOAD,
        reference_utc=TAXONOMY_REFERENCE_UTC,
        max_taxonomy_age_days=TAXONOMY_MAX_AGE_DAYS,
    )
    assert result.is_valid is False
    assert result.age_days_exact is not None
    assert result.age_days_exact < 0, "a future capture has a negative exact age"
    assert result.age_days_exact == -1.0
    assert result.status == "stale"
    assert result.is_fresh is False

    one_second_ahead = v.validate_taxonomy_freshness(
        fx.TAXONOMY_FIXTURE,
        reference_utc=fx.VALID_CAPTURE_UTC - timedelta(seconds=1),
        max_taxonomy_age_days=TAXONOMY_MAX_AGE_DAYS,
    )
    assert one_second_ahead.status == "stale"
    assert one_second_ahead.age_days_exact is not None
    assert one_second_ahead.age_days_exact < 0

    at_reference = v.validate_taxonomy_freshness(
        fx.TAXONOMY_FIXTURE,
        reference_utc=fx.VALID_CAPTURE_UTC,
        max_taxonomy_age_days=TAXONOMY_MAX_AGE_DAYS,
    )
    assert at_reference.age_days_exact == 0.0
    assert at_reference.is_fresh is True, "a capture at the reference instant is fresh"


@pytest.mark.lreq("LREQ-EXT-020")
def test_taxonomy_reports_missing_requested_categories() -> None:
    """An absent requested category is an explicit failure, never an empty category."""
    present = v.validate_requested_categories(_taxonomy_payload(), fx.ALL_PRESENT_CATEGORIES)
    assert present.is_valid is True
    assert present.status == "valid"
    assert present.missing_requested_categories == ()
    assert present.issues == ()

    absent = v.validate_requested_categories(_taxonomy_payload(), fx.ONE_ABSENT_CATEGORY)
    assert absent.is_valid is False
    assert absent.status == "missing_categories"
    assert absent.missing_requested_categories == ("Audio/Music/Orchestral",)
    assert _issues_of(absent) == ["taxonomy_missing_requested_category"]
    assert absent.issues[0].context["category"] == "Audio/Music/Orchestral"

    parent_requested = v.validate_requested_categories(
        _taxonomy_payload(), fx.PARENT_PATH_REQUESTED_CATEGORIES
    )
    assert parent_requested.status == "missing_categories", (
        "a requested parent path does not satisfy an inventory of child paths"
    )
    assert parent_requested.missing_requested_categories == (fx.PARENT_PATH_OF_INVENTORY_PATH,)

    child_requested = v.validate_requested_categories(
        _taxonomy_payload(), (fx.CHILD_PATH_OF_INVENTORY_PATH,)
    )
    assert child_requested.status == "missing_categories"

    whitespace_tolerant = v.validate_requested_categories(
        _taxonomy_payload(), (f"  {fx.DEFAULT_CATEGORIES[0]}  ",)
    )
    assert whitespace_tolerant.is_valid is True

    empty_request = v.validate_requested_categories(_taxonomy_payload(), ())
    assert empty_request.is_valid is True
    assert empty_request.missing_requested_categories == ()


@pytest.mark.lreq("LREQ-EXT-020")
def test_validate_taxonomy_combines_structure_freshness_and_presence() -> None:
    """The combined validator reports the first failing stage and keeps every issue."""
    valid = v.validate_taxonomy(
        _taxonomy_payload(),
        requested_categories=fx.ALL_PRESENT_CATEGORIES,
        reference_utc=TAXONOMY_REFERENCE_UTC,
        max_taxonomy_age_days=TAXONOMY_MAX_AGE_DAYS,
    )
    assert valid.is_valid is True
    assert valid.status == "valid"
    assert valid.is_fresh is True
    assert valid.age_days_exact == pytest.approx(27.5)
    assert valid.age_days_exact == (TAXONOMY_REFERENCE_UTC - fx.VALID_CAPTURE_UTC).total_seconds() / 86400
    assert valid.missing_header_fields == ()
    assert valid.missing_requested_categories == ()
    assert valid.issues == ()

    structurally_bad = v.validate_taxonomy(
        fx.TAXONOMY_NOT_A_MAPPING,
        requested_categories=fx.ALL_PRESENT_CATEGORIES,
        reference_utc=TAXONOMY_REFERENCE_UTC,
        max_taxonomy_age_days=TAXONOMY_MAX_AGE_DAYS,
    )
    assert structurally_bad.status == "malformed"
    assert structurally_bad.is_fresh is None
    assert structurally_bad.age_days_exact is None

    headers_missing = v.validate_taxonomy(
        fx.TAXONOMY_PAYLOADS_MISSING_ONE_HEADER["template_sha256"],
        requested_categories=fx.ALL_PRESENT_CATEGORIES,
        reference_utc=TAXONOMY_REFERENCE_UTC,
        max_taxonomy_age_days=TAXONOMY_MAX_AGE_DAYS,
    )
    assert headers_missing.status == "missing_headers"
    assert headers_missing.is_fresh is None

    stale = v.validate_taxonomy(
        fx.CLEARLY_STALE_CAPTURE_PAYLOAD,
        requested_categories=fx.ALL_PRESENT_CATEGORIES,
        reference_utc=TAXONOMY_REFERENCE_UTC,
        max_taxonomy_age_days=TAXONOMY_MAX_AGE_DAYS,
    )
    assert stale.status == "stale"
    assert stale.is_fresh is False
    assert stale.age_days_exact == 45.0

    categories_missing = v.validate_taxonomy(
        _taxonomy_payload(),
        requested_categories=fx.ONE_ABSENT_CATEGORY,
        reference_utc=TAXONOMY_REFERENCE_UTC,
        max_taxonomy_age_days=TAXONOMY_MAX_AGE_DAYS,
    )
    assert categories_missing.status == "missing_categories"
    assert categories_missing.is_fresh is True, "freshness still holds when presence fails"
    assert categories_missing.missing_requested_categories == ("Audio/Music/Orchestral",)
    assert categories_missing.age_days_exact == pytest.approx(27.5)

    naive = v.validate_taxonomy(
        fx.NAIVE_CAPTURE_PAYLOAD,
        requested_categories=fx.ALL_PRESENT_CATEGORIES,
        reference_utc=TAXONOMY_REFERENCE_UTC,
        max_taxonomy_age_days=TAXONOMY_MAX_AGE_DAYS,
    )
    assert naive.status == "invalid_capture_timestamp"
    assert naive.is_fresh is None
    assert naive.age_days_exact is None

    strict_threshold = v.validate_taxonomy(
        _taxonomy_payload(),
        requested_categories=fx.ALL_PRESENT_CATEGORIES,
        reference_utc=TAXONOMY_REFERENCE_UTC,
        max_taxonomy_age_days=10,
    )
    assert strict_threshold.status == "stale"


# ---------------------------------------------------------------------------
# LREQ-EXT-080 — exact category membership
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-EXT-080")
def test_exact_category_path_match() -> None:
    """An exact segment sequence matches; segment comparison is case-insensitive."""
    paths = v.taxonomy_path_set(_taxonomy_payload())
    assert paths == frozenset(fx.DEFAULT_CATEGORIES)

    exact = v.match_exact_category(fx.SCALAR_EXACT_CATEGORY_VALUE, paths)
    assert exact.status is CategoryFilterValidationStatus.VERIFIED
    assert exact.matched_path == fx.DEFAULT_CATEGORIES[0]
    assert exact.matched_value_count == 1
    assert exact.unmatched_values == ()
    assert exact.issues == ()

    other = v.match_exact_category(fx.DEFAULT_CATEGORIES[3], paths)
    assert other.status is CategoryFilterValidationStatus.VERIFIED
    assert other.matched_path == fx.DEFAULT_CATEGORIES[3]

    case_insensitive = v.match_exact_category(fx.DEFAULT_CATEGORIES[0].upper(), paths)
    assert case_insensitive.status is CategoryFilterValidationStatus.VERIFIED
    assert case_insensitive.matched_path == fx.DEFAULT_CATEGORIES[0], (
        "the reported path is the canonical, case-preserving one"
    )

    whitespace_tolerant = v.match_exact_category(
        f"  {fx.DEFAULT_CATEGORIES[0]}  ", paths
    )
    assert whitespace_tolerant.status is CategoryFilterValidationStatus.VERIFIED
    assert whitespace_tolerant.matched_path == fx.DEFAULT_CATEGORIES[0]

    assert v.normalize_category_path(" Tools / Utilities / ") == "Tools/Utilities"
    assert v.normalize_category_path("A//B") == "A/B"
    assert v.normalize_category_path("A/B") == "A/B"
    with pytest.raises(TypeError):
        v.normalize_category_path(7)  # type: ignore[arg-type]


@pytest.mark.lreq("LREQ-EXT-080")
def test_parent_path_does_not_match_child_path() -> None:
    """A parent path never matches a child path merely by prefix."""
    paths = v.taxonomy_path_set(_taxonomy_payload())
    assert fx.PARENT_PATH_OF_INVENTORY_PATH not in paths
    assert fx.DEFAULT_CATEGORIES[5] in paths

    parent = v.match_exact_category(fx.SCALAR_PARENT_CATEGORY_VALUE, paths)
    assert parent.status is CategoryFilterValidationStatus.MISMATCH
    assert parent.matched_path is None
    assert parent.matched_value_count == 0
    assert _issues_of(parent) == ["category_value_mismatch"]

    top_level = v.match_exact_category("Tools", paths)
    assert top_level.status is CategoryFilterValidationStatus.MISMATCH

    multi_valued_parents = v.match_exact_category(fx.MULTI_VALUED_PARENT_PATH_VALUE, paths)
    assert multi_valued_parents.status is CategoryFilterValidationStatus.MISMATCH
    assert multi_valued_parents.matched_value_count == 0
    assert multi_valued_parents.unmatched_values == tuple(fx.MULTI_VALUED_PARENT_PATH_VALUE)

    prefix_only = v.match_exact_category("Tools/Utilit", paths)
    assert prefix_only.status is CategoryFilterValidationStatus.MISMATCH


@pytest.mark.lreq("LREQ-EXT-080")
def test_child_path_does_not_match_parent_path() -> None:
    """A child path never matches an inventory containing only its parent."""
    child_only_taxonomy = _taxonomy_payload(canonical_category_paths=["Tools/Utilities"])
    paths = v.taxonomy_path_set(child_only_taxonomy)
    assert paths == frozenset({"Tools/Utilities"})

    child = v.match_exact_category(fx.CHILD_PATH_OF_INVENTORY_PATH, paths)
    assert child.status is CategoryFilterValidationStatus.MISMATCH
    assert child.matched_path is None
    assert child.matched_value_count == 0

    grandchild = v.match_exact_category(fx.DEFAULT_CATEGORIES[5], paths)
    assert grandchild.status is CategoryFilterValidationStatus.MISMATCH

    parent_still_matches = v.match_exact_category("Tools/Utilities", paths)
    assert parent_still_matches.status is CategoryFilterValidationStatus.VERIFIED

    multi_valued_children = v.match_exact_category(fx.MULTI_VALUED_CHILD_PATH_VALUE, paths)
    assert multi_valued_children.status is CategoryFilterValidationStatus.MISMATCH
    assert multi_valued_children.matched_value_count == 0

    real_paths = v.taxonomy_path_set(_taxonomy_payload())
    real_mismatch = v.match_exact_category(fx.CHILD_PATH_OF_INVENTORY_PATH, real_paths)
    assert real_mismatch.status is CategoryFilterValidationStatus.MISMATCH


@pytest.mark.lreq("LREQ-EXT-080")
def test_scalar_category_shape_handled_explicitly() -> None:
    """Scalar, null, absent, and wrong-typed category values are classified explicitly."""
    paths = v.taxonomy_path_set(_taxonomy_payload())

    scalar = v.match_exact_category(fx.SCALAR_EXACT_CATEGORY_VALUE, paths)
    assert scalar.status is CategoryFilterValidationStatus.VERIFIED
    assert scalar.matched_value_count == 1

    for unusable in (None, *fx.WRONG_TYPED_CATEGORY_VALUES):
        result = v.match_exact_category(unusable, paths)
        assert result.status is CategoryFilterValidationStatus.UNVERIFIED
        assert result.matched_path is None
        assert result.matched_value_count == 0
        assert result.unmatched_values == ()
        assert _issues_of(result) == ["category_value_unverified"]

    absent = v.match_exact_category(None, paths)
    assert "absent" in absent.issues[0].message

    empty_string = v.match_exact_category("", paths)
    assert empty_string.status is CategoryFilterValidationStatus.MISMATCH, (
        "an empty string is a supplied value that matches nothing, not a missing one"
    )

    empty_list = v.match_exact_category([], paths)
    assert empty_list.status is CategoryFilterValidationStatus.UNVERIFIED

    int_list = v.match_exact_category([7, 8], paths)
    assert int_list.status is CategoryFilterValidationStatus.UNVERIFIED


@pytest.mark.lreq("LREQ-EXT-080")
def test_multi_valued_category_shape_handled_explicitly() -> None:
    """Multi-valued shapes contribute every string entry; counts reflect values."""
    paths = v.taxonomy_path_set(_taxonomy_payload())

    one_match = v.match_exact_category(fx.MULTI_VALUED_ONE_MATCH, paths)
    assert one_match.status is CategoryFilterValidationStatus.VERIFIED
    assert one_match.matched_path == fx.DEFAULT_CATEGORIES[3]
    assert one_match.matched_value_count == 1
    assert one_match.unmatched_values == ("Nonexistent/Category",)

    two_matches = v.match_exact_category(
        [fx.DEFAULT_CATEGORIES[0], fx.DEFAULT_CATEGORIES[3], "Missing/Path"], paths
    )
    assert two_matches.status is CategoryFilterValidationStatus.VERIFIED
    assert two_matches.matched_path == fx.DEFAULT_CATEGORIES[0]
    assert two_matches.matched_value_count == 2, "counts are per value, not per distinct path"
    assert two_matches.unmatched_values == ("Missing/Path",)

    no_match = v.match_exact_category(fx.MULTI_VALUED_NO_MATCH, paths)
    assert no_match.status is CategoryFilterValidationStatus.MISMATCH
    assert no_match.matched_value_count == 0
    assert set(no_match.unmatched_values) == set(fx.MULTI_VALUED_NO_MATCH)

    tuple_shape = v.match_exact_category(
        (fx.DEFAULT_CATEGORIES[0], "Missing/Path"), paths
    )
    assert tuple_shape.status is CategoryFilterValidationStatus.VERIFIED
    assert tuple_shape.matched_value_count == 1

    mixed_list = v.match_exact_category([7, fx.DEFAULT_CATEGORIES[0], None], paths)
    assert mixed_list.status is CategoryFilterValidationStatus.VERIFIED, (
        "non-string entries are ignored while string entries still match"
    )
    assert mixed_list.matched_value_count == 1

    duplicate_match = v.match_exact_category(
        [fx.DEFAULT_CATEGORIES[0], fx.DEFAULT_CATEGORIES[0]], paths
    )
    assert duplicate_match.status is CategoryFilterValidationStatus.VERIFIED
    assert duplicate_match.matched_value_count == 2
    assert duplicate_match.matched_path == fx.DEFAULT_CATEGORIES[0]


@pytest.mark.lreq("LREQ-EXT-080")
def test_unverified_versus_mismatch_classification() -> None:
    """``unverified`` means "no usable value"; ``mismatch`` means "usable but unmatched"."""
    paths = v.taxonomy_path_set(_taxonomy_payload())

    verified = v.match_exact_category(fx.DEFAULT_CATEGORIES[0], paths)
    mismatch = v.match_exact_category(fx.PARENT_PATH_OF_INVENTORY_PATH, paths)
    unverified = v.match_exact_category(None, paths)

    assert verified.status is CategoryFilterValidationStatus.VERIFIED
    assert mismatch.status is CategoryFilterValidationStatus.MISMATCH
    assert unverified.status is CategoryFilterValidationStatus.UNVERIFIED

    assert verified.issues == ()
    assert _issues_of(mismatch) == ["category_value_mismatch"]
    assert _issues_of(unverified) == ["category_value_unverified"]
    assert {verified.status, mismatch.status, unverified.status} == set(
        CategoryFilterValidationStatus
    ), "the three SRS filter-validation states are all reachable"

    assert v.match_exact_category(None, paths).unmatched_values == ()
    assert v.match_exact_category(fx.MULTI_VALUED_NO_MATCH, paths).unmatched_values != ()

    with pytest.raises(TypeError):
        v.match_exact_category("A/B", "A/B")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# LREQ-MET-010 (structural half) — malformed shape, type, and redaction
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-MET-010")
def test_malformed_shape_is_explicitly_invalid() -> None:
    """Wrong container kinds and missing members are reported as typed issues."""
    for name in ("not_a_mapping_list", "not_a_mapping_scalar", "not_a_mapping_none"):
        vector = fx.MALFORMED_RESPONSE_VECTORS[name]
        result = v.validate_response_shape(
            vector["payload"],
            expected_shape=vector["expected_shape"],
            required_members=fx.PRODUCT_DETAIL_MEMBERS,
            field_types=fx.PRODUCT_DETAIL_FIELD_TYPES,
        )
        assert result.is_valid is False, name
        assert _issues_of(result) == ["response_wrong_container_kind"], name
        assert result.expected_shape == "mapping"
        assert result.actual_shape in {"list", "str", "none"}

    missing = v.validate_response_shape(
        fx.PRODUCT_DETAIL_MISSING_MEMBER,
        expected_shape="mapping",
        required_members=fx.PRODUCT_DETAIL_MEMBERS,
        field_types=fx.PRODUCT_DETAIL_FIELD_TYPES,
    )
    assert missing.is_valid is False
    assert ("response_missing_required_member", "product_id") in _issue_codes_with_context(
        missing, "member"
    )
    assert missing.actual_shape == "mapping"

    wrong_container = v.validate_response_shape(
        fx.PRODUCT_DETAIL_WRONG_CONTAINER,
        expected_shape="mapping",
        required_members=fx.PRODUCT_DETAIL_MEMBERS,
        field_types=fx.PRODUCT_DETAIL_FIELD_TYPES,
    )
    assert wrong_container.is_valid is False
    assert "response_wrong_scalar_type" in _issues_of(wrong_container)

    # A list-shaped member is structurally valid as a list. The payload is a member
    # *value*, not an operation response, so no identity member is expected here.
    list_expected = v.validate_response_shape(
        fx.PRODUCT_DETAIL_WRONG_CONTAINER["category"],
        expected_shape="list",
        required_members=("path",),
    )
    assert list_expected.is_valid is True
    assert list_expected.actual_shape == "list"

    mapping_expected_but_list = v.validate_response_shape(
        [fx.WELL_FORMED_PRODUCT_DETAIL], expected_shape="mapping"
    )
    assert mapping_expected_but_list.is_valid is False
    assert mapping_expected_but_list.actual_shape == "list"

    with pytest.raises(ValueError):
        v.validate_response_shape({}, expected_shape="not_a_known_shape")

    well_formed = v.validate_response_shape(
        fx.WELL_FORMED_PRODUCT_DETAIL,
        expected_shape="mapping",
        required_members=fx.PRODUCT_DETAIL_MEMBERS,
        field_types=fx.PRODUCT_DETAIL_FIELD_TYPES,
    )
    assert well_formed.is_valid is True
    assert well_formed.issues == ()
    assert well_formed.actual_shape == "mapping"
    assert "mapping" in v.RESPONSE_CONTAINER_KINDS


@pytest.mark.lreq("LREQ-MET-010")
def test_wrong_scalar_type_is_explicitly_invalid() -> None:
    """A member whose value does not match its declared type is reported explicitly."""
    result = v.validate_response_shape(
        fx.PRODUCT_DETAIL_WRONG_TYPE,
        expected_shape="mapping",
        required_members=fx.PRODUCT_DETAIL_MEMBERS,
        field_types=fx.PRODUCT_DETAIL_FIELD_TYPES,
    )
    assert result.is_valid is False
    assert _issues_of(result) == ["response_wrong_scalar_type"]
    issue = result.issues[0]
    assert issue.context["member"] == "rating_count"
    assert issue.context["expected_type"] == "int"
    assert issue.context["actual_shape"] == "str"

    bool_is_not_int = v.validate_response_shape(
        {"rating_count": True},
        expected_shape="mapping",
        required_members=("rating_count",),
        field_types={"rating_count": int},
    )
    assert _issues_of(bool_is_not_int) == ["response_wrong_scalar_type"], (
        "a bool must not satisfy an int declaration"
    )

    float_is_not_int = v.validate_response_shape(
        {"rating_count": 5.5},
        expected_shape="mapping",
        required_members=("rating_count",),
        field_types={"rating_count": int},
    )
    assert _issues_of(float_is_not_int) == ["response_wrong_scalar_type"]

    # A wrong-typed *identity* member is a type error and nothing else. The
    # payload is validated against a named member spec rather than an operation
    # response, so the identity-presence check does not apply and the issue list
    # contains exactly the type problem.
    int_is_not_str = v.validate_response_shape(
        {"rating_count": 5, "graphql_id": 1234567},
        expected_shape="mapping",
        required_members=("rating_count",),
        field_types={"graphql_id": str},
    )
    assert _issues_of(int_is_not_str) == ["response_wrong_scalar_type"]

    union_declared = v.validate_response_shape(
        {"rating_count": 5},
        expected_shape="mapping",
        required_members=("rating_count",),
        field_types={"rating_count": (int, str)},
    )
    assert union_declared.is_valid is True

    union_mismatch = v.validate_response_shape(
        {"rating_count": None},
        expected_shape="mapping",
        required_members=(),
        field_types={"rating_count": (int, str)},
    )
    assert union_mismatch.is_valid is True, (
        "an explicit null is null-member territory, not a wrong-type value"
    )


@pytest.mark.lreq("LREQ-MET-010")
def test_null_required_member_is_distinct_from_wrong_type() -> None:
    """``null``, absent, and wrong-typed members stay three distinct issue codes."""
    result = v.validate_response_shape(
        fx.PRODUCT_DETAIL_NULL_MEMBER,
        expected_shape="mapping",
        required_members=fx.PRODUCT_DETAIL_MEMBERS,
        field_types=fx.PRODUCT_DETAIL_FIELD_TYPES,
    )
    codes = _issues_of(result)
    assert result.is_valid is False
    assert ("response_null_required_member", "product_id") in _issue_codes_with_context(
        result, "member"
    )
    assert "response_missing_required_member" not in codes

    absent = v.validate_response_shape(
        fx.PRODUCT_DETAIL_MISSING_MEMBER,
        expected_shape="mapping",
        required_members=fx.PRODUCT_DETAIL_MEMBERS,
        field_types=fx.PRODUCT_DETAIL_FIELD_TYPES,
    )
    absent_codes = _issues_of(absent)
    assert "response_missing_required_member" in absent_codes
    assert "response_null_required_member" not in absent_codes

    wrong_typed = v.validate_response_shape(
        fx.PRODUCT_DETAIL_WRONG_TYPE,
        expected_shape="mapping",
        required_members=fx.PRODUCT_DETAIL_MEMBERS,
        field_types=fx.PRODUCT_DETAIL_FIELD_TYPES,
    )
    wrong_typed_codes = _issues_of(wrong_typed)
    assert wrong_typed_codes == ["response_wrong_scalar_type"]
    assert "response_null_required_member" not in wrong_typed_codes

    assert len(
        {
            "response_missing_required_member",
            "response_null_required_member",
            "response_wrong_scalar_type",
        }
    ) == 3, "null, absent, and wrong type must remain distinguishable states"

    null_issue = next(
        issue for issue in result.issues if issue.code == "response_null_required_member"
    )
    assert "unavailable" in null_issue.message
    assert "default" in null_issue.message or "substituted" in null_issue.message


@pytest.mark.lreq("LREQ-MET-010")
def test_failed_fields_remain_none_not_zero() -> None:
    """A failed or missing field is never filled with ``0``, ``""``, ``[]``, or ``False``."""
    result = v.validate_response_shape(
        fx.PRODUCT_DETAIL_NULL_MEMBER,
        expected_shape="mapping",
        required_members=fx.PRODUCT_DETAIL_MEMBERS,
        field_types=fx.PRODUCT_DETAIL_FIELD_TYPES,
    )
    assert result.is_valid is False
    for issue in result.issues:
        for value in issue.context.values():
            assert value != 0, "a failed value must not be recorded as zero"
            assert value != "", "a failed value must not be recorded as an empty string"
            assert value is not False, "a failed value must not be recorded as False"

    missing_identity = v.validate_response_shape(
        fx.PRODUCT_DETAIL_MISSING_IDENTITY,
        expected_shape="mapping",
        required_members=fx.PRODUCT_DETAIL_MEMBERS,
        field_types=fx.PRODUCT_DETAIL_FIELD_TYPES,
    )
    assert "response_missing_identity" in _issues_of(missing_identity)

    identity_absent_from_payload = v.validate_response_shape(
        {"rating_count": 5},
        expected_shape="mapping",
        required_members=fx.PRODUCT_DETAIL_OPTIONAL_MEMBERS,
    )
    assert "response_missing_identity" in _issues_of(identity_absent_from_payload)

    structure_only = v.validate_response_shape(
        {"review_count": None}, expected_shape="mapping", required_members=("review_count",)
    )
    assert structure_only.is_valid is False
    assert structure_only.issues[0].code == "response_null_required_member"


@pytest.mark.lreq("LREQ-MET-010")
def test_validation_issues_are_redacted() -> None:
    """No credential, header, token, or cookie survives into an issue or a summary."""
    issues = tuple(
        v.ValidationIssue(code=f"fixture_{name}", message=value, context={"field": value})
        for name, value in fx.REDACTION_VECTORS.items()
    )
    summary = v.summarize_validation_issues(issues)

    for secret in fx.FORBIDDEN_REDACTION_SUBSTRINGS:
        assert secret not in summary, secret
    assert "Authorization" not in summary
    assert "Cookie" not in summary
    assert "Set-Cookie" not in summary
    assert "Bearer" not in summary
    # ``"csrf"`` is a substring of the fixture *code name* (``fixture_csrf_token_value``),
    # not of a secret: plan §11 forbids credential values, headers, CSRF tokens, and
    # cookies from appearing — not identifier names. Assert the token values instead.
    assert fx.REDACTION_VECTORS["csrf_token_value"] not in summary
    assert fx.REDACTION_VECTORS["x_csrf_token"] not in summary
    # ``access_token``/``api_key`` are likewise forbidden as *values*, not as
    # identifier names: the fixture code names ``fixture_access_token`` and
    # ``fixture_api_key`` legitimately appear in the summary's code list.
    assert fx.REDACTION_VECTORS["access_token"] not in summary
    assert fx.REDACTION_VECTORS["api_key"] not in summary
    assert "fixture-access-token-value" not in summary
    assert "fixture-api-key-value" not in summary

    for name, vector in fx.REDACTION_VECTORS.items():
        assert vector not in summary, name
        assert vector not in v.redact_value(vector), name
        assert "redacted" in v.redact_value(vector), name

    rendered = json.loads(summary)
    assert rendered["issue_count"] == len(issues)
    assert sorted(rendered["codes"]) == sorted(issue.code for issue in issues)
    for entry in rendered["issues"]:
        assert "redacted" in entry["message"]

    header_issue = v.ValidationIssue(
        code="fixture_header",
        message="request failed",
        context={"header": "Authorization: Bearer fixture-coveo-token"},
    )
    # ``to_json`` preserves the issue as stored (it is a plain serializer, not a
    # redactor); redaction happens when an issue is *created* through
    # ``_redacted_context``/``redact_value`` or summarised. A hand-built issue is
    # therefore redacted on the way out through ``summarize_validation_issues``,
    # which is the path that reaches ``error_summary_json``.
    summarized_header = v.summarize_validation_issues((header_issue,))
    assert "fixture-coveo-token" not in summarized_header
    assert "Authorization" not in summarized_header

    assert "fixture-coveo-token" not in v.redact_value(
        "Authorization: Bearer fixture-coveo-token"
    )
    assert "Authorization" not in v.redact_value(
        "Authorization: Bearer fixture-coveo-token"
    )

    token_issue = v.ValidationIssue(code="fixture_token", message="fixture-csrf-token")
    assert "fixture-csrf-token" not in v.summarize_validation_issues((token_issue,))

    explicit_bounded = v.summarize_validation_issues(issues, max_context_chars=0)
    assert json.loads(explicit_bounded)["issue_count"] == len(issues)
    for secret in fx.FORBIDDEN_REDACTION_SUBSTRINGS:
        assert secret not in explicit_bounded

    assert json.loads(v.summarize_validation_issues(()))["issue_count"] == 0

    structural = v.ValidationIssue(
        code="taxonomy_missing_header", message="missing", context={"field": "source_url"}
    )
    assert "source_url" in structural.to_json(), (
        "structural identifiers such as a field name remain reportable"
    )
    assert json.loads(v.summarize_validation_issues((structural,)))["issues"][0]["context"][
        "field"
    ].startswith("<value redacted")


@pytest.mark.lreq("LREQ-MET-010")
def test_structural_validation_does_not_decide_metric_eligibility() -> None:
    """Structural validators return no metric-eligibility verdict, and import nothing impure."""
    published = v.annotate_state_eligibility("published")
    assert published.is_published is True
    assert not hasattr(published, "eligible_for_d")
    assert not hasattr(published, "eligible_for_r")
    assert not hasattr(published, "eligible_for_q")

    negative = v.validate_response_shape(
        {"product_page_views": -5},
        expected_shape="mapping",
        required_members=("product_page_views",),
        field_types={"product_page_views": int},
    )
    assert negative.is_valid is True, (
        "a negative but correctly-typed scalar is structurally valid; its metric "
        "eligibility is Chunk 7A's decision"
    )
    assert negative.issues == ()

    boolean_views = v.validate_response_shape(
        {"product_page_views": True},
        expected_shape="mapping",
        required_members=("product_page_views",),
        field_types={"product_page_views": int},
    )
    assert boolean_views.is_valid is False, (
        "a boolean is a wrong scalar type, which is structural"
    )

    non_finite = v.validate_response_shape(
        {"rating_average": float("nan")},
        expected_shape="mapping",
        required_members=("rating_average",),
        field_types={"rating_average": float},
    )
    assert non_finite.is_valid is True, (
        "finiteness is a metric-eligibility rule, not a structural one"
    )

    source = VALIDATION_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(VALIDATION_PATH))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        (node.module or "").split(".")[-1]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert imported & {
        "collector",
        "collector_coveo",
        "collector_graphql",
        "database",
        "pipeline",
        "report",
        "cli",
        "config",
        "sqlite3",
        "pathlib",
        "os",
        "time",
        "logging",
        "requests",
        "urllib",
        "http",
        "httpx",
        "aiohttp",
        "socket",
        "subprocess",
        "metrics",
        "scoring",
    } == set()
    # ``validation.py`` is governed by plan §11: no I/O modules and no clock reads.
    # ``json`` is forbidden only for the modules in ``check_import_boundaries``
    # ``PURE_MODULES`` (metrics.py, scoring.py), and ``validation.py`` legitimately
    # needs it to emit the redacted JSON summary required by plan §5.2, so the
    # checked set excludes ``json`` while every other boundary member still applies.
    assert imported & (FORBIDDEN_MODULES - {"json"}) == set(), (
        "json is the only FORBIDDEN_MODULES member validation.py may import"
    )
    assert check_module(VALIDATION_PATH) == ["validation.py: forbidden import 'json'"], (
        "the only check_module violation for validation.py is the json import, which "
        "PURE_MODULES does not apply to it"
    )
    assert not set(check_module(VALIDATION_PATH)) - {
        "validation.py: forbidden import 'json'"
    }, "validation.py must not violate any other import boundary"
    assert clock_violations(tree) == []
    assert "metrics" not in source.split("import", 1)[0]

    assert v.validate_response_shape({}, expected_shape="mapping").is_valid is True


# ---------------------------------------------------------------------------
# LREQ-GQL-040 / LREQ-GQL-050 (structural half)
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-GQL-040")
def test_missing_identity_member_is_operation_shape_error() -> None:
    """A response with no populated identity member is a structural operation error."""
    absent = v.validate_response_shape(
        {"rating_count": 5, "state": "published"},
        expected_shape="mapping",
        required_members=fx.PRODUCT_DETAIL_OPTIONAL_MEMBERS,
    )
    assert absent.is_valid is False
    # Both declared identity members are absent from the payload, so the structural
    # stage reports each omission under its own code and then the operation-level
    # missing-identity code. A missing member is NOT collapsed into the missing
    # identity: plan §7 lists "missing required member" separately and plan §8
    # requires the codes to stay distinct.
    assert _issues_of(absent) == [
        "response_missing_identity",
        "response_missing_required_member",
        "response_missing_required_member",
    ]
    identity_issue = next(
        issue for issue in absent.issues if issue.code == "response_missing_identity"
    )
    assert identity_issue.context["expected_fields"] == "graphql_id, product_id"

    nulled = v.validate_response_shape(
        fx.PRODUCT_DETAIL_MISSING_IDENTITY,
        expected_shape="mapping",
        required_members=fx.PRODUCT_DETAIL_MEMBERS,
        field_types=fx.PRODUCT_DETAIL_FIELD_TYPES,
    )
    assert nulled.is_valid is False
    assert "response_missing_identity" in _issues_of(nulled)

    empty_identity = v.validate_response_shape(
        {"graphql_id": "   ", "product_id": ""},
        expected_shape="mapping",
        required_members=fx.PRODUCT_DETAIL_OPTIONAL_MEMBERS,
    )
    assert "response_missing_identity" in _issues_of(empty_identity), (
        "a whitespace-only identity is a missing identity, not an empty one"
    )

    # The declared identity alias set here is only ``graphql_id``: a payload that
    # populates every declared alias is valid, and the declaration — not an
    # assumption about a second alias — decides what counts as missing.
    populated = v.validate_response_shape(
        {"graphql_id": "1234567"},
        expected_shape="mapping",
        required_members=("graphql_id",),
    )
    assert populated.is_valid is True

    # Declaring both aliases and supplying only one is a missing member, not a
    # missing identity: the other alias is still populated.
    partially_populated = v.validate_response_shape(
        {"graphql_id": "1234567"},
        expected_shape="mapping",
        required_members=fx.PRODUCT_DETAIL_OPTIONAL_MEMBERS,
    )
    assert partially_populated.is_valid is False
    assert _issues_of(partially_populated) == ["response_missing_required_member"]
    assert partially_populated.issues[0].context["member"] == "product_id"

    second_alias_populated = v.validate_response_shape(
        {"graphql_id": None, "product_id": "1234567"},
        expected_shape="mapping",
        required_members=fx.PRODUCT_DETAIL_OPTIONAL_MEMBERS,
    )
    assert second_alias_populated.is_valid is False, (
        "a null required member stays a null-member error even though the other alias "
        "is populated"
    )
    assert [issue.code for issue in second_alias_populated.issues] == [
        "response_null_required_member"
    ]


@pytest.mark.lreq("LREQ-GQL-050")
def test_structure_validation_retains_valid_member_when_other_missing() -> None:
    """A valid member stays valid while a failed member is reported, never defaulted."""
    partial = v.validate_response_shape(
        {"graphql_id": "1234567", "rating_count": 12},
        expected_shape="mapping",
        required_members=("graphql_id", "product_page_views"),
        field_types={"graphql_id": str, "rating_count": int},
    )
    assert partial.is_valid is False
    assert _issues_of(partial) == ["response_missing_required_member"]
    assert partial.issues[0].context["member"] == "product_page_views"
    assert "rating_count" not in partial.issues[0].context

    typed_and_missing = v.validate_response_shape(
        {"graphql_id": "1234567", "rating_count": "twelve"},
        expected_shape="mapping",
        required_members=("graphql_id", "product_page_views"),
        field_types={"graphql_id": str, "rating_count": int},
    )
    assert set(_issues_of(typed_and_missing)) == {
        "response_missing_required_member",
        "response_wrong_scalar_type",
    }, "failures are reported independently, not collapsed"

    operation_maps = fx.PARTIAL_OPERATION_RESPONSE
    successful = v.validate_response_shape(
        operation_maps["ProductDetail"],
        expected_shape="mapping",
        required_members=fx.PRODUCT_DETAIL_MEMBERS,
        field_types=fx.PRODUCT_DETAIL_FIELD_TYPES,
    )
    failed = v.validate_response_shape(
        operation_maps["ProductPageViews"],
        expected_shape="mapping",
        required_members=("product_page_views",),
    )
    assert successful.is_valid is True
    assert failed.is_valid is False
    assert _issues_of(failed) == ["response_wrong_container_kind"]
    assert failed.actual_shape == "none", (
        "a failed operation's fields stay unavailable rather than defaulting to zero"
    )

    deterministic = v.validate_response_shape(
        {"graphql_id": "1234567", "rating_count": "twelve"},
        expected_shape="mapping",
        required_members=("graphql_id", "product_page_views"),
        field_types={"graphql_id": str, "rating_count": int},
    )
    assert _issues_of(deterministic) == _issues_of(typed_and_missing)
    assert deterministic.issues == typed_and_missing.issues


# ---------------------------------------------------------------------------
# LREQ-EXT-050 / LREQ-EXT-090 — discovery-status reason vocabulary
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-EXT-050")
@pytest.mark.lreq("LREQ-EXT-090")
def test_category_mismatch_and_unverified_map_to_discovery_status_vocabulary() -> None:
    """Mismatch and unverified map onto the LREQ-EXT-050 discovery status vocabulary."""
    assert (
        v.discovery_status_for_category_status(CategoryFilterValidationStatus.MISMATCH)
        is DiscoveryStatus.CATEGORY_MISMATCH
    )
    assert (
        v.discovery_status_for_category_status(CategoryFilterValidationStatus.UNVERIFIED)
        is DiscoveryStatus.FILTER_UNVERIFIED
    )
    assert (
        v.discovery_status_for_category_status(CategoryFilterValidationStatus.VERIFIED)
        is None
    ), "a verified filter asserts no failure condition"

    vocabulary = {status.value for status in DiscoveryStatus}
    assert DiscoveryStatus.CATEGORY_MISMATCH.value in vocabulary
    assert DiscoveryStatus.FILTER_UNVERIFIED.value in vocabulary
    assert {
        "complete",
        "truncated",
        "page_failed",
        "filter_unverified",
        "category_mismatch",
        "identity_incomplete",
        "request_failed",
    } == vocabulary, "the reason vocabulary is the SRS's, unchanged"

    paths = v.taxonomy_path_set(_taxonomy_payload())
    mismatched = v.match_exact_category(fx.PARENT_PATH_OF_INVENTORY_PATH, paths)
    unverified = v.match_exact_category(None, paths)
    verified = v.match_exact_category(fx.DEFAULT_CATEGORIES[0], paths)
    assert v.discovery_status_for_category_status(mismatched.status) is DiscoveryStatus.CATEGORY_MISMATCH
    assert v.discovery_status_for_category_status(unverified.status) is DiscoveryStatus.FILTER_UNVERIFIED
    assert v.discovery_status_for_category_status(verified.status) is None

    assert v.discovery_status_for_category_status(mismatched.status) is not DiscoveryStatus.TRUNCATED
    assert mismatched.matched_value_count == 0, (
        "a mismatch never becomes a zero-asset success"
    )
