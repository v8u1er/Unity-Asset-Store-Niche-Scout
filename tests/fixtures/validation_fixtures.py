"""Deterministic fixtures and golden vectors for the Chunk 1 validation suite.

Everything here is local, hand-derived, and network-free. The taxonomy payloads,
identity records, malformed-response shapes, and redaction vectors are the inputs
the pure ``niche_scout.validation`` primitives are exercised against by
``tests/test_validation.py`` and ``tests/test_identity.py``.

The valid taxonomy payload reuses Chunk 0's ``TAXONOMY_FIXTURE`` and
``DEFAULT_CATEGORIES`` read-only (``interfaces/chunk-00.md`` §9); this module adds
the permutations Chunk 1 needs (missing headers, stale/future/naive capture
timestamps, malformed inventories) without redefining the Chunk 0 values.

Freshness fixtures follow resolved decision R-5: the boundary is **inclusive**, so
``age_days_exact == MAX_TAXONOMY_AGE_DAYS`` is fresh and anything above it is
stale. ``REFERENCE_UTC`` is an explicit, timezone-aware UTC constant; no test
reads the system clock.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fixtures.config_fixtures import (
    DEFAULT_CATEGORIES,
    MOCK_ENVIRONMENT,
    REQUIRED_TAXONOMY_FIELDS,
    TAXONOMY_FIXTURE,
)

__all__ = [
    "AGREEING_IDENTITY_RECORD",
    "CANONICAL_ASSET_ID",
    "CHILD_PATH_OF_INVENTORY_PATH",
    "DISAGREEING_SUFFIX_URI_RECORD",
    "FRESH_AGE_DAYS_EXACT",
    "FRESH_CAPTURE_PAYLOAD",
    "GQL_ALIAS_MAPS",
    "IDENTITY_RECORDS",
    "MALFORMED_RESPONSE_VECTORS",
    "MULTI_VALUED_CHILD_PATH_VALUE",
    "MULTI_VALUED_PARENT_PATH_VALUE",
    "PARENT_PATH_OF_INVENTORY_PATH",
    "REDACTION_VECTORS",
    "REFERENCE_UTC",
    "STATE_VECTORS",
    "STALE_AGE_DAYS_EXACT",
    "TAXONOMY_FIXTURE",
    "TAXONOMY_PAYLOADS_MISSING_ONE_HEADER",
    "TAXONOMY_WITH_MALFORMED_ENTRY",
    "TAXONOMY_WITHOUT_INVENTORY",
    "TAXONOMY_WITHOUT_HEADERS_OR_INVENTORY",
    "TAXONOMY_WITH_NON_STRING_PATH",
    "TAXONOMY_WITH_PARENT_ONLY_PATH",
    "URI_NO_TRAILING_IDENTIFIER",
    "URI_WITH_FRAGMENT_AND_QUERY",
    "URI_WITH_QUERY_STRING",
    "URI_WITH_SLUG_IDENTIFIER",
    "VALID_CAPTURE_UTC",
    "normalized_naive_capture_payload",
]

# --------------------------------------------------------------------------
# Freshness fixtures (inclusive boundary, R-5)
# --------------------------------------------------------------------------

#: Explicit freshness reference. The stored ``captured_at_utc`` is a UTC instant,
#: so every age below is independent of the host timezone.
REFERENCE_UTC: datetime = datetime(2026, 2, 1, 12, 0, 0, tzinfo=timezone.utc)

#: ``TAXONOMY_FIXTURE`` captures at exactly this instant (Chunk 0 fixture).
VALID_CAPTURE_UTC: datetime = datetime(2026, 1, 5, 0, 0, 0, tzinfo=timezone.utc)

#: Exactly at the inclusive ``MAX_TAXONOMY_AGE_DAYS`` boundary (fresh).
FRESH_AGE_DAYS_EXACT: float = 30.0

#: One microsecond beyond the boundary (stale). Fractions of a day, not whole
#: days, so the comparison cannot succeed through integer rounding.
STALE_AGE_DAYS_EXACT: float = 30.0 + 1e-6 / 86400


def _payload_at(expected_age_days: float, *, suffix_text: str = "Z") -> dict[str, Any]:
    """Return a valid taxonomy payload captured ``expected_age_days`` ago."""
    captured = REFERENCE_UTC - timedelta(days=expected_age_days)
    return _with_capture_utc(
        TAXONOMY_FIXTURE, captured.isoformat().replace("+00:00", suffix_text)
    )


def _with_capture_utc(payload: dict[str, Any], captured_at_utc: Any) -> dict[str, Any]:
    """Return a shallow copy of ``payload`` with a replaced capture timestamp."""
    mutated = dict(payload)
    mutated["captured_at_utc"] = captured_at_utc
    return mutated


#: A payload whose age is exactly ``MAX_TAXONOMY_AGE_DAYS`` (must be fresh).
FRESH_CAPTURE_PAYLOAD: dict[str, Any] = _payload_at(FRESH_AGE_DAYS_EXACT)

#: A payload one microsecond beyond the boundary (must be stale).
STALE_CAPTURE_PAYLOAD: dict[str, Any] = _payload_at(STALE_AGE_DAYS_EXACT)

#: A payload captured 45 days ago (unambiguously stale).
CLEARLY_STALE_CAPTURE_PAYLOAD: dict[str, Any] = _payload_at(45.0)

#: A payload captured after the reference time (future capture).
FUTURE_CAPTURE_PAYLOAD: dict[str, Any] = _with_capture_utc(
    TAXONOMY_FIXTURE, (REFERENCE_UTC + timedelta(days=1)).isoformat().replace("+00:00", "Z")
)

#: A payload whose capture timestamp carries no timezone (naive).
NAIVE_CAPTURE_PAYLOAD: dict[str, Any] = _with_capture_utc(
    TAXONOMY_FIXTURE, VALID_CAPTURE_UTC.replace(tzinfo=None).isoformat()
)

#: A payload whose capture timestamp is a type that cannot be parsed at all.
UNPARSABLE_CAPTURE_PAYLOAD: dict[str, Any] = _with_capture_utc(
    TAXONOMY_FIXTURE, "not-a-timestamp"
)

#: A payload whose capture timestamp is not even a string.
NON_STRING_CAPTURE_PAYLOAD: dict[str, Any] = _with_capture_utc(TAXONOMY_FIXTURE, 20260105)

#: A normalized copy of the valid payload — the canonical fixture for equality.
NORMALIZED_TAXONOMY_FIXTURE: dict[str, Any] = dict(TAXONOMY_FIXTURE)


def normalized_naive_capture_payload() -> dict[str, Any]:
    """Return a fresh, valid payload with a naive capture timestamp."""
    return _with_capture_utc(NORMALIZED_TAXONOMY_FIXTURE, NAIVE_CAPTURE_PAYLOAD["captured_at_utc"])


# --------------------------------------------------------------------------
# Taxonomy payload permutations
# --------------------------------------------------------------------------

#: One payload per required header field, with that field removed.
TAXONOMY_PAYLOADS_MISSING_ONE_HEADER: dict[str, dict[str, Any]] = {
    field: {
        name: value for name, value in TAXONOMY_FIXTURE.items() if name != field
    }
    for field in REQUIRED_TAXONOMY_FIELDS
}

#: A payload carrying no canonical category-path inventory at all.
TAXONOMY_WITHOUT_INVENTORY: dict[str, Any] = {
    name: value
    for name, value in TAXONOMY_FIXTURE.items()
    if name != "canonical_category_paths"
}

#: A payload that is missing a required header *and* carries no inventory — the
#: case where the first failing stage is the header check, so no inventory verdict
#: may be reported. The empty mapping is the smallest such payload; an empty
#: taxonomy cache is a realistic one.
TAXONOMY_WITHOUT_HEADERS_OR_INVENTORY: dict[str, Any] = {}

#: An inventory whose entries are not a usable category-path shape (parent only,
#: never a leaf, so it is not a selectable category).
TAXONOMY_WITH_PARENT_ONLY_PATH: dict[str, Any] = {
    **TAXONOMY_FIXTURE,
    "canonical_category_paths": ["Tools"],
}

#: An inventory containing a non-string entry.
TAXONOMY_WITH_NON_STRING_PATH: dict[str, Any] = {
    **TAXONOMY_FIXTURE,
    "canonical_category_paths": [*DEFAULT_CATEGORIES, 7],
}

#: An inventory with a duplicated path (the duplicate is a shape problem).
TAXONOMY_WITH_DUPLICATE_PATH: dict[str, Any] = {
    **TAXONOMY_FIXTURE,
    "canonical_category_paths": [*DEFAULT_CATEGORIES, DEFAULT_CATEGORIES[0]],
}

#: A per-entry record whose ``path`` disagrees with the inventory (malformed).
TAXONOMY_WITH_MALFORMED_ENTRY: dict[str, Any] = {
    **TAXONOMY_FIXTURE,
    "categories": [
        {**TAXONOMY_FIXTURE["categories"][0], "path": "Not/A/Path"},
        *TAXONOMY_FIXTURE["categories"][1:],
    ],
}

#: An inventory entry that is not itself a well-formed path.
TAXONOMY_WITH_MALFORMED_INVENTORY_PATH: dict[str, Any] = {
    **TAXONOMY_FIXTURE,
    "canonical_category_paths": ["/Leading/Slash"],
}

#: A payload with a wrong-typed container for the header block (not a mapping).
TAXONOMY_NOT_A_MAPPING: list[str] = list(REQUIRED_TAXONOMY_FIELDS)

#: An inventory whose container kind is wrong (a scalar instead of a sequence).
TAXONOMY_WITH_SCALAR_INVENTORY: dict[str, Any] = {
    **TAXONOMY_FIXTURE,
    "canonical_category_paths": DEFAULT_CATEGORIES[0],
}

#: An inventory whose entries are mappings instead of strings.
TAXONOMY_WITH_MAPPING_PATH_ENTRY: dict[str, Any] = {
    **TAXONOMY_FIXTURE,
    "canonical_category_paths": [*DEFAULT_CATEGORIES, {"path": "Tools/Utilities/Editor Extensions"}],
}

# --------------------------------------------------------------------------
# Requested-category fixtures
# --------------------------------------------------------------------------

#: Every default category is present in the fixture inventory.
ALL_PRESENT_CATEGORIES: tuple[str, ...] = DEFAULT_CATEGORIES

#: Exactly one requested category (the last) is absent from the inventory.
ONE_ABSENT_CATEGORY: tuple[str, ...] = (*DEFAULT_CATEGORIES[:-1], "Audio/Music/Orchestral")

#: A requested category that is a real parent path of inventory entries.
PARENT_PATH_OF_INVENTORY_PATH: str = "Tools/Utilities"

#: A requested category that is a real child path of an inventory entry.
CHILD_PATH_OF_INVENTORY_PATH: str = "Tools/Utilities/Editor Extensions/Themes"

#: Requested categories containing a parent path of real inventory entries.
PARENT_PATH_REQUESTED_CATEGORIES: tuple[str, ...] = (PARENT_PATH_OF_INVENTORY_PATH,)

# --------------------------------------------------------------------------
# Category-value shapes (LREQ-EXT-080)
# --------------------------------------------------------------------------

#: A scalar category value that matches an inventory path exactly.
SCALAR_EXACT_CATEGORY_VALUE: str = DEFAULT_CATEGORIES[0]

#: A scalar parent path — must NOT match any child inventory path by prefix.
SCALAR_PARENT_CATEGORY_VALUE: str = PARENT_PATH_OF_INVENTORY_PATH

#: A scalar child path — must NOT match the parent inventory path.
SCALAR_CHILD_CATEGORY_VALUE: str = CHILD_PATH_OF_INVENTORY_PATH

#: A multi-valued list with exactly one exact match.
MULTI_VALUED_ONE_MATCH: list[str] = [
    "Nonexistent/Category",
    DEFAULT_CATEGORIES[3],
]

#: A multi-valued list whose only entries are parents of inventory paths.
MULTI_VALUED_PARENT_PATH_VALUE: list[str] = [
    PARENT_PATH_OF_INVENTORY_PATH,
    "Audio/Music",
]

#: A multi-valued list whose only entries are children of inventory paths.
MULTI_VALUED_CHILD_PATH_VALUE: list[str] = [
    CHILD_PATH_OF_INVENTORY_PATH,
    "Audio/Music/Ambient/Sub",
]

#: Multi-valued lists with no exact match.
MULTI_VALUED_NO_MATCH: list[str] = ["Nonexistent/Category", "Another/Missing/Path"]

#: Wrong-typed category values that must classify as ``unverified``.
WRONG_TYPED_CATEGORY_VALUES: tuple[Any, ...] = (7, [7, 8], {"path": DEFAULT_CATEGORIES[0]}, True)

# --------------------------------------------------------------------------
# Identity fixtures (mapping rule 1.0.1, R-2)
# --------------------------------------------------------------------------

#: The canonical asset identifier every agreeing fixture resolves to.
CANONICAL_ASSET_ID: str = "1234567"

#: A Unity Asset Store package URL whose last segment carries the identifier.
URI_WITH_SLUG_IDENTIFIER: str = (
    "https://assetstore.unity.com/packages/tools/level-design/tilemap-pro-1234567"
)

#: The same URL with a query string; the identifier still comes from the path.
URI_WITH_QUERY_STRING: str = f"{URI_WITH_SLUG_IDENTIFIER}?utm_source=fixture&page=2"

#: The same URL with a fragment as well.
URI_WITH_FRAGMENT_AND_QUERY: str = f"{URI_WITH_SLUG_IDENTIFIER}#reviews"

#: A URL whose last path segment has no trailing ``-<numeric>`` identifier.
URI_NO_TRAILING_IDENTIFIER: str = "https://assetstore.unity.com/packages/tools/level-design/tilemap-pro"

#: A URL where the trailing numeric group is not the final path segment.
URI_NUMERIC_GROUP_BEFORE_FINAL_SEGMENT: str = (
    "https://assetstore.unity.com/packages/tools/level-design/2d-tools"
)

#: A URL with an empty last path segment (trailing slash).
URI_TRAILING_SLASH: str = "https://assetstore.unity.com/packages/tools/level-design/"

#: All four source fields agreeing on the same identity.
AGREEING_IDENTITY_RECORD: dict[str, Any] = {
    "ec_product_id": CANONICAL_ASSET_ID,
    "permanentid": f" {CANONICAL_ASSET_ID} ",
    "clickUri": URI_WITH_SLUG_IDENTIFIER,
    "uri": URI_WITH_QUERY_STRING,
}

#: A record whose candidates all agree but only after canonicalization.
AGREEING_AFTER_CANONICALIZATION_RECORD: dict[str, Any] = {
    "ec_product_id": " 1234567 ",
    "permanentid": "1234567",
    "clickUri": URI_WITH_FRAGMENT_AND_QUERY,
}

#: A record whose ``ec_product_id`` / ``permanentid`` disagree.
DISAGREEING_PRODUCT_IDS_RECORD: dict[str, Any] = {
    "ec_product_id": "1234567",
    "permanentid": "7654321",
}

#: A record whose product ids disagree with the URI-derived value.
DISAGREEING_URI_RECORD: dict[str, Any] = {
    "ec_product_id": "1234567",
    "permanentid": "1234567",
    "clickUri": URI_WITH_SLUG_IDENTIFIER,
    "uri": "https://assetstore.unity.com/packages/tools/level-design/other-9999999",
}

#: A URI whose last path segment itself carries a hyphenated numeric group before
#: the final ``-<digits>`` identifier (``level-design-toolkit-234-1234567``). A
#: multi-hyphen last segment is what makes the equality step observable at all:
#: the extracted identifier is ``1234567``, not a longer tail.
URI_CARRYING_RECORD_SUFFIX_OF_ANCHOR: str = (
    "https://assetstore.unity.com/packages/tools/level-design/"
    "level-design-toolkit-234-1234567"
)

#: An explicit anchor of which the URI-derived identifier is a *proper* suffix:
#: ``product-1234567`` ends with ``1234567`` but is not equal to it. This is the
#: anchored shape ``interfaces/chunk-03.md`` §8 records (``product-0001`` for
#: ``.../fixture-1-0001``). ``DISAGREEING_URI_RECORD`` cannot stand in for it:
#: ``"1234567".endswith("9999999")`` is ``False``, so that fixture yields
#: ``conflict`` under a suffix-tolerant comparison *and* under exact equality.
EXPLICIT_ANCHOR_WITH_SUFFIX_URI_IDENTIFIER: str = "product-1234567"

#: A record whose URI-derived identifier is a proper suffix of the explicit
#: anchor. The derived key really is ``1234567`` (extraction takes the trailing
#: ``-<digits>`` group of the last path segment); the anchor is compared as the
#: already-canonical string it is under §4.1, so ``product-1234567`` and
#: ``1234567`` are distinct canonical values and ``LREQ-EXT-070`` makes this a
#: ``conflict``.
DISAGREEING_SUFFIX_URI_RECORD: dict[str, Any] = {
    "ec_product_id": EXPLICIT_ANCHOR_WITH_SUFFIX_URI_IDENTIFIER,
    "permanentid": EXPLICIT_ANCHOR_WITH_SUFFIX_URI_IDENTIFIER,
    "clickUri": URI_CARRYING_RECORD_SUFFIX_OF_ANCHOR,
}

#: A record whose only candidates are empty, whitespace-only, or unusable.
EMPTY_CANDIDATES_RECORD: dict[str, Any] = {
    "ec_product_id": "",
    "permanentid": "   ",
    "clickUri": "",
    "uri": "\t\n",
}

#: A record whose candidates are present but non-string.
NON_STRING_CANDIDATES_RECORD: dict[str, Any] = {
    "ec_product_id": 1234567,
    "permanentid": None,
    "clickUri": ["https://assetstore.unity.com/packages/x-1234567"],
    "uri": 1234567,
}

#: A record with one field missing entirely and the rest empty.
ABSENT_CANDIDATE_FIELDS_RECORD: dict[str, Any] = {}

#: ``ec_product_id`` only.
EC_PRODUCT_ID_ONLY_RECORD: dict[str, Any] = {"ec_product_id": CANONICAL_ASSET_ID}

#: ``permanentid`` only.
PERMANENTID_ONLY_RECORD: dict[str, Any] = {"permanentid": CANONICAL_ASSET_ID}

#: ``clickUri`` only.
CLICK_URI_ONLY_RECORD: dict[str, Any] = {"clickUri": URI_WITH_SLUG_IDENTIFIER}

#: ``uri`` only.
URI_ONLY_RECORD: dict[str, Any] = {"uri": URI_WITH_QUERY_STRING}

#: A record whose only candidate is a URI with no trailing identifier.
UNPARSEABLE_URI_RECORD: dict[str, Any] = {"uri": URI_NO_TRAILING_IDENTIFIER}

#: Named identity records used across the identity tests.
IDENTITY_RECORDS: dict[str, dict[str, Any]] = {
    "agreeing": AGREEING_IDENTITY_RECORD,
    "agreeing_after_canonicalization": AGREEING_AFTER_CANONICALIZATION_RECORD,
    "ec_product_id_only": EC_PRODUCT_ID_ONLY_RECORD,
    "permanentid_only": PERMANENTID_ONLY_RECORD,
    "click_uri_only": CLICK_URI_ONLY_RECORD,
    "uri_only": URI_ONLY_RECORD,
    "disagreeing_product_ids": DISAGREEING_PRODUCT_IDS_RECORD,
    "disagreeing_uri": DISAGREEING_URI_RECORD,
    "disagreeing_suffix_uri": DISAGREEING_SUFFIX_URI_RECORD,
    "empty_candidates": EMPTY_CANDIDATES_RECORD,
    "non_string_candidates": NON_STRING_CANDIDATES_RECORD,
    "unparseable_uri": UNPARSEABLE_URI_RECORD,
}

#: Numerically equal but textually different raw forms that MUST agree (R-2).
NUMERICALLY_EQUAL_RAW_FORMS: tuple[str, ...] = (
    "123",
    " 123 ",
    "123",
    "0123",
)

# --------------------------------------------------------------------------
# GraphQL identity-alias fixtures (LREQ-GQL-070)
# --------------------------------------------------------------------------

#: Requested canonical identity used by the alias fixtures.
REQUESTED_IDENTITY: str = CANONICAL_ASSET_ID

GQL_ALIAS_MAPS: dict[str, dict[str, Any]] = {
    # Both aliases carry the requested identity verbatim.
    "agreeing": {"graphql_id": CANONICAL_ASSET_ID, "product_id": CANONICAL_ASSET_ID},
    # ``graphql_id`` agrees, ``product_id`` disagrees.
    "disagreeing": {"graphql_id": CANONICAL_ASSET_ID, "product_id": "7654321"},
    # No alias keys at all.
    "missing": {},
    # Alias present but null.
    "null_alias": {"graphql_id": None, "product_id": None},
    # Alias present but not canonicalizable. Only ``clickUri``/``uri`` can fail to
    # canonicalize: under mapping rule 1.0.1 `ec_product_id`/`permanentid`-style
    # aliases are already canonical and pass through unchanged (R-2), so they are
    # merely *non-agreeing*, never unparseable.
    "unparseable": {"clickUri": "not-an-identifier", "product_id": "also-bad"},
    # Agrees only after canonicalization (whitespace + URI form).
    "agreeing_after_canonicalization": {
        "graphql_id": f" {CANONICAL_ASSET_ID} ",
        "product_id": URI_WITH_SLUG_IDENTIFIER,
    },
    # An extra canonicalizable alias value that agrees.
    "extra_alias_source": {
        "graphql_id": CANONICAL_ASSET_ID,
        "packageId": CANONICAL_ASSET_ID,
    },
    # The two required operations use the same canonical key.
    "shared_operation_key": {
        "graphql_id": CANONICAL_ASSET_ID,
        "product_id": CANONICAL_ASSET_ID,
        "packageId": CANONICAL_ASSET_ID,
    },
}

# --------------------------------------------------------------------------
# State fixtures (LREQ-GQL-060)
# --------------------------------------------------------------------------

#: Named state values, including absent and wrong-typed shapes.
STATE_VECTORS: dict[str, Any] = {
    "published": "published",
    "excluded": "draft",
    "excluded_empty": " ",
    "null": None,
    "wrong_type": 7,
    "wrong_type_list": ["published"],
    "wrong_type_bool": True,
}

# --------------------------------------------------------------------------
# Structural response-validation fixtures (LREQ-MET-010 structural half)
# --------------------------------------------------------------------------

#: A well-formed ``ProductDetail`` payload with the members Chunk 1 structurally
#: validates: identity members plus the scalar/container shapes.
WELL_FORMED_PRODUCT_DETAIL: dict[str, Any] = {
    "graphql_id": CANONICAL_ASSET_ID,
    "product_id": CANONICAL_ASSET_ID,
    "rating_count": 12,
    "category": ["Tools/Utilities/Editor Extensions"],
}

#: A payload with one required member removed.
PRODUCT_DETAIL_MISSING_MEMBER: dict[str, Any] = {
    name: value
    for name, value in WELL_FORMED_PRODUCT_DETAIL.items()
    if name != "product_id"
}

#: A payload with a required member present but null.
PRODUCT_DETAIL_NULL_MEMBER: dict[str, Any] = {
    **WELL_FORMED_PRODUCT_DETAIL,
    "product_id": None,
}

#: A payload with the wrong scalar type for an integer member.
PRODUCT_DETAIL_WRONG_TYPE: dict[str, Any] = {
    **WELL_FORMED_PRODUCT_DETAIL,
    "rating_count": "twelve",
}

#: A payload whose container member has the wrong kind (mapping for a list).
PRODUCT_DETAIL_WRONG_CONTAINER: dict[str, Any] = {
    **WELL_FORMED_PRODUCT_DETAIL,
    "category": {"path": DEFAULT_CATEGORIES[0]},
}

#: A payload with no identity alias at all (missing identity).
PRODUCT_DETAIL_MISSING_IDENTITY: dict[str, Any] = {
    **WELL_FORMED_PRODUCT_DETAIL,
    "graphql_id": None,
    "product_id": None,
}

#: Named malformed-response vectors, with the shape each one is validated against.
MALFORMED_RESPONSE_VECTORS: dict[str, dict[str, Any]] = {
    "not_a_mapping_list": {"payload": [WELL_FORMED_PRODUCT_DETAIL], "expected_shape": "mapping"},
    "not_a_mapping_scalar": {"payload": "product", "expected_shape": "mapping"},
    "not_a_mapping_none": {"payload": None, "expected_shape": "mapping"},
    "missing_member": {"payload": PRODUCT_DETAIL_MISSING_MEMBER, "expected_shape": "mapping"},
    "null_member": {"payload": PRODUCT_DETAIL_NULL_MEMBER, "expected_shape": "mapping"},
    "wrong_scalar_type": {"payload": PRODUCT_DETAIL_WRONG_TYPE, "expected_shape": "mapping"},
    "wrong_container_kind": {"payload": PRODUCT_DETAIL_WRONG_CONTAINER, "expected_shape": "mapping"},
    "missing_identity": {"payload": PRODUCT_DETAIL_MISSING_IDENTITY, "expected_shape": "mapping"},
}

#: A ``ProductDetail`` member specification: member name -> required / expected type.
PRODUCT_DETAIL_MEMBERS: tuple[str, ...] = ("graphql_id", "product_id", "rating_count", "category")
PRODUCT_DETAIL_OPTIONAL_MEMBERS: tuple[str, ...] = ("graphql_id", "product_id")

PRODUCT_DETAIL_FIELD_TYPES: dict[str, type | tuple[type, ...]] = {
    "graphql_id": str,
    "product_id": str,
    "rating_count": int,
    "category": list,
}

#: A single-operation response where one operation succeeded and the other did not.
PARTIAL_OPERATION_RESPONSE: dict[str, Any] = {
    "ProductDetail": WELL_FORMED_PRODUCT_DETAIL,
    "ProductPageViews": None,
}

# --------------------------------------------------------------------------
# Redaction vectors (LREQ-SEC-020 as consumed)
# --------------------------------------------------------------------------

#: Strings that must never survive into a redacted issue message, context, or
#: summary. The credential values come from Chunk 0's mock-environment fixture.
REDACTION_VECTORS: dict[str, Any] = {
    "authorization_header": "Authorization: Bearer fixture-coveo-token",
    "bearer_token_value": MOCK_ENVIRONMENT["NICHESCOUT_COVEO_BEARER_TOKEN"],
    "csrf_token_value": MOCK_ENVIRONMENT["NICHESCOUT_UNITY_CSRF_TOKEN"],
    "env_var_shaped": (
        f"{'NICHESCOUT_COVEO_BEARER_TOKEN'}="
        f"{MOCK_ENVIRONMENT['NICHESCOUT_COVEO_BEARER_TOKEN']}"
    ),
    "cookie_header": "Cookie: session=fixture-session; csrf=fixture-csrf-token",
    "set_cookie_header": "Set-Cookie: session=fixture-session; HttpOnly",
    "api_key": "api_key=fixture-api-key-value",
    "access_token": "access_token: fixture-access-token-value",
    "x_csrf_token": "X-CSRF-Token: fixture-csrf-token",
}

#: Secret substrings asserted absent from every redacted output.
FORBIDDEN_REDACTION_SUBSTRINGS: tuple[str, ...] = (
    MOCK_ENVIRONMENT["NICHESCOUT_COVEO_BEARER_TOKEN"],
    MOCK_ENVIRONMENT["NICHESCOUT_UNITY_CSRF_TOKEN"],
    "fixture-session",
    "fixture-api-key-value",
    "fixture-access-token-value",
)
