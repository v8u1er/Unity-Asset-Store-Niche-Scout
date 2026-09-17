"""Pure taxonomy, identity, and response-structure validation primitives.

This module is the structural half of the SRS's ``validation`` component row
(§3.1: "Taxonomy, identity, type, date, state, and semantic checks | No network").
It is deliberately pure: no filesystem, database, network, process, CLI, or clock
access, and no import of any I/O module of this package. Taxonomy payloads arrive
as already-parsed typed objects; the freshness reference time is always an
explicit timezone-aware UTC argument.

What this module decides is *structure* only — shape, type, presence, exact path
equality, identity-candidate canonicalizability, and alias agreement. It never
decides whether a value is *usable for a metric*: published-state eligibility
applied to metric inputs, UTC/date normalization for metrics, future-date
rejection, finite/non-negative checks, age thresholds, and page-view eligibility
ranges are metric-eligibility semantics owned by Chunk 7A. Adapter integration of
these primitives (real Coveo and GraphQL responses) is completed by Chunks 3
and 5.

Invariants every public function preserves:

* **Null, zero, invalid, and unavailable stay distinct.** A missing, malformed,
  wrong-typed, unparseable, or otherwise unavailable value yields ``None`` plus an
  explicit :class:`ValidationIssue`; it is never replaced by ``0``, ``0.0``,
  ``""``, ``[]``, or ``False`` as a sentinel.
* **Determinism.** Identical inputs and an identical ``mapping_rule_version``
  produce structurally equivalent outputs. Candidate order is input order, and
  issue order is deterministic.
* **Redaction.** Issue messages, issue context, and
  :func:`summarize_validation_issues` never carry credential values,
  ``Authorization`` headers, CSRF tokens, cookies, or raw response bodies.
"""

from __future__ import annotations

import json
import re
from collections.abc import Container, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .models import (
    IDENTITY_MAPPING_RULE_VERSION,
    MAX_TAXONOMY_AGE_DAYS,
    CategoryFilterValidationStatus,
    DiscoveryStatus,
    IdentityResolutionStatus,
    ensure_utc,
    to_json_dict,
)

SECONDS_PER_DAY = 86400.0

__all__ = [
    "CategoryMatchResult",
    "GraphQLIdentityComparisonResult",
    "IdentityCandidate",
    "IdentityResolutionResult",
    "RESPONSE_CONTAINER_KINDS",
    "StateEligibilityAnnotation",
    "StructuralValidationResult",
    "TAXONOMY_ENTRY_PATH_FIELDS",
    "TAXONOMY_INVENTORY_FIELDS",
    "TAXONOMY_REQUIRED_HEADER_FIELDS",
    "TaxonomyValidationResult",
    "ValidationIssue",
    "annotate_state_eligibility",
    "canonicalize_identity_candidate",
    "collect_identity_candidates",
    "compare_graphql_identity_aliases",
    "discovery_status_for_category_status",
    "match_exact_category",
    "normalize_category_path",
    "redact_value",
    "resolve_canonical_identity",
    "summarize_validation_issues",
    "taxonomy_path_set",
    "validate_requested_categories",
    "validate_response_shape",
    "validate_taxonomy",
    "validate_taxonomy_freshness",
    "validate_taxonomy_structure",
]

# --------------------------------------------------------------------------
# Constants and vocabularies
# --------------------------------------------------------------------------

#: Required taxonomy header fields (LREQ-EXT-020, SRS §4.1).
TAXONOMY_REQUIRED_HEADER_FIELDS: tuple[str, ...] = (
    "schema_version",
    "captured_at_utc",
    "source_url",
    "template_sha256",
)

#: Container fields that may carry the canonical category-path inventory. The
#: first one that is present and usable wins; the others are fallbacks.
TAXONOMY_INVENTORY_FIELDS: tuple[str, ...] = (
    "canonical_category_paths",
    "canonical_paths",
)

#: Per-entry fields that may carry a canonical path in a ``categories`` sequence.
TAXONOMY_ENTRY_PATH_FIELDS: tuple[str, ...] = ("path", "canonical_path", "category_path")

#: Container kinds :func:`validate_response_shape` can name explicitly.
RESPONSE_CONTAINER_KINDS: tuple[str, ...] = (
    "mapping",
    "list",
    "identity",
    "str",
    "int",
    "float",
    "bool",
    "none",
    "tuple",
    "set",
    "bytes",
    "unknown",
)

#: Source fields retained as identity candidates (LREQ-EXT-060, SRS §4.1).
_IDENTITY_SOURCE_FIELDS: tuple[str, ...] = (
    "ec_product_id",
    "permanentid",
    "clickUri",
    "uri",
)

_URI_FIELDS: frozenset[str] = frozenset({"clickUri", "uri"})

#: Identity member names an operation response may declare. A response that
#: declares one of these as required and returns no populated value is a missing
#: identity (LREQ-GQL-040), not an empty identity and not a zero.
_IDENTITY_ALIAS_MEMBERS: frozenset[str] = frozenset(
    {"graphql_id", "product_id", "packageId", "asset_identity_key"}
)

#: Matches a trailing ``-<digits>`` group in a URL's final path segment.
_URI_TRAILING_IDENTIFIER = re.compile(r"-(\d+)$")

_ISSUE_MESSAGE_PREFIX = "value redacted"

#: Issue codes that describe the canonical category-path inventory declaration
#: rather than the header block. A payload whose header block is incomplete reports
#: a header failure, so these are the codes dropped when a structural result is
#: re-reported as ``"missing_headers"``.
_INVENTORY_ISSUE_CODES = frozenset(
    {
        "taxonomy_inventory_not_a_list",
        "taxonomy_malformed_category_path",
        "taxonomy_duplicate_category_path",
    }
)

#: Issue codes that may not occur in a well-formed taxonomy payload. Kept so the
#: taxonomy result's ``status`` vocabulary is documented in one place.
_TAXONOMY_STATUSES: tuple[str, ...] = (
    "valid",
    "missing_headers",
    "malformed",
    "stale",
    "missing_categories",
    "invalid_capture_timestamp",
)

#: Order in which structural issue codes are reported, for deterministic output.
_SHAPE_PRECEDENCE: tuple[str, ...] = (
    "missing_member",
    "null_member",
    "wrong_type",
    "not_a_mapping",
    "missing_identity",
)


# --------------------------------------------------------------------------
# Redaction
# --------------------------------------------------------------------------


def redact_value(value: object) -> str:
    """Return a secret-free placeholder describing ``value``.

    The returned string never contains the value's own text: a credential,
    ``Authorization`` header, CSRF token, cookie, or raw response body passed
    here cannot survive into an issue message, issue context, or error summary.
    Only structural information (the value's type and, for sized containers, its
    length) is reported.
    """
    if value is None:
        return "null"
    rendered = _shape_name(value)
    length = _container_length(value)
    if length is None:
        return f"<{_ISSUE_MESSAGE_PREFIX}: {rendered}>"
    return f"<{_ISSUE_MESSAGE_PREFIX}: {rendered} of length {length}>"


def _shape_name(value: object) -> str:
    """Return a stable name for ``value``'s container/scalar kind."""
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, Mapping):
        return "mapping"
    if isinstance(value, (list, tuple, set, frozenset)):
        return "list"
    if isinstance(value, str):
        return "str"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, (bytes, bytearray)):
        return "bytes"
    return "object"


def _populated_identity_value(value: object) -> bool:
    """Return whether ``value`` is a usable identity alias value.

    A non-string or whitespace-only value carries no identity, so it counts as
    unpopulated rather than being coerced into one (SRS §4.2, LREQ-GQL-050: no
    fabricated values for missing data).
    """
    return isinstance(value, str) and value.strip() != ""


def _container_length(value: object) -> int | None:
    """Return the element count of a sized container, else ``None``."""
    if isinstance(value, (str, bytes, bytearray, Mapping)):
        return len(value)
    if isinstance(value, (list, tuple, set, frozenset)):
        return len(value)
    return None


def _context_identifier(value: object, *, max_chars: int = 64) -> str:
    """Return a bounded, non-secret identifier for issue context.

    Issue context is meant to be human-readable, so structural identifiers such
    as a field name, a category path, or a canonical identity are included. A
    value that does not look like a short structural identifier is redacted
    wholesale, which is what keeps credentials and raw response bodies out.

    A non-string container of identifiers (the declared member-name lists an
    issue reports) is rendered element-wise: each element is itself checked as an
    identifier, so a bracket, comma, quote, or whitespace can never reach the
    context — that is what keeps a credential or a raw body out even when the
    caller passes one where a field name was expected.
    """
    if isinstance(value, (list, tuple, set, frozenset)):
        rendered = sorted(
            _context_identifier(element, max_chars=max_chars) for element in value
        )
        return ", ".join(rendered)
    if not isinstance(value, str):
        return redact_value(value)
    if len(value) > max_chars:
        return f"<{_ISSUE_MESSAGE_PREFIX}: str of length {len(value)}>"
    if any(character.isspace() for character in value):
        return f"<{_ISSUE_MESSAGE_PREFIX}: str of length {len(value)}>"
    return value


def _redacted_context(**context: object) -> dict[str, Any]:
    """Build a JSON-safe issue context from structural identifier values."""
    return {key: _context_identifier(value) for key, value in context.items()}


# --------------------------------------------------------------------------
# Typed issues and results
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """A typed, redacted structural problem found during validation.

    ``code`` is a stable machine-readable identifier, ``message`` is a short
    redacted explanation, and ``context`` carries JSON-safe structural detail
    (field names, paths, counts, the expected/actual shape). Neither ``message``
    nor ``context`` ever carries a credential, header, token, cookie, or raw
    response body.
    """

    code: str
    message: str
    context: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        """Return deterministic, key-sorted JSON for this issue."""
        return json.dumps(to_json_dict(self), sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True, slots=True)
class TaxonomyValidationResult:
    """The structural, freshness, and presence outcome for one taxonomy payload.

    ``is_fresh`` is ``None`` — never ``False`` — when freshness cannot be
    determined (an unusable ``captured_at_utc`` or a structurally invalid
    payload), so an unknown freshness state is distinguishable from a known-stale
    one. ``age_days_exact`` is ``None`` whenever ``captured_at_utc`` is unusable.

    ``payload`` is the validated object. It is carried so a failing stage can name
    the *kind* of what it was handed — the structural check already classified the
    payload's container kind, and a downstream stage must report that verdict
    rather than restate a status that belongs to a stage the payload never reached.
    """

    is_valid: bool
    is_fresh: bool | None
    status: str
    payload: object = None
    missing_header_fields: tuple[str, ...] = ()
    missing_requested_categories: tuple[str, ...] = ()
    age_days_exact: float | None = None
    issues: tuple[ValidationIssue, ...] = ()


@dataclass(frozen=True, slots=True)
class IdentityCandidate:
    """One retained identity candidate, verbatim plus its canonical form.

    ``canonical_value`` is ``None`` when the candidate could not be canonicalized
    under the mapping rule; ``parse_failure_reason`` then explains why. A
    candidate that cannot be canonicalized never contributes a guessed value.
    """

    source_field: str
    raw_value: str
    canonical_value: str | None
    parse_failure_reason: str | None


@dataclass(frozen=True, slots=True)
class IdentityResolutionResult:
    """The canonical identity classification for one discovery record.

    ``canonical_identity_key`` is non-``None`` only for a ``resolved`` record: a
    ``conflict`` or ``unresolved`` record never carries a canonical key, always
    carries a ``reason``, and is excluded from both the canonical denominator and
    the enrichment set. ``mapping_rule_version`` records which rule produced the
    classification so consumers can branch on it rather than assuming one
    version's semantics.
    """

    canonical_identity_key: str | None
    status: IdentityResolutionStatus
    reason: str | None
    candidates: tuple[IdentityCandidate, ...]
    included_in_canonical_denominator: bool
    included_in_enrichment_set: bool
    mapping_rule_version: str
    issues: tuple[ValidationIssue, ...] = ()


@dataclass(frozen=True, slots=True)
class CategoryMatchResult:
    """Exact category-membership outcome for one response category value.

    ``status`` distinguishes the three states the SRS requires: ``verified`` (an
    exact path match), ``mismatch`` (a usable value that matches nothing), and
    ``unverified`` (no usable value at all — ``null``, absent, or wrong-typed).
    ``matched_value_count`` counts *values*, not distinct paths.
    """

    matched_path: str | None
    status: CategoryFilterValidationStatus
    matched_value_count: int
    unmatched_values: tuple[str, ...]
    issues: tuple[ValidationIssue, ...] = ()


@dataclass(frozen=True, slots=True)
class GraphQLIdentityComparisonResult:
    """Pure comparison of returned GraphQL identity aliases to a requested identity.

    ``id_mapping_mismatch`` is ``True`` whenever the returned aliases do not agree
    with the requested canonical identity — including when an alias is missing or
    cannot be canonicalized, which is never treated as agreement. ``reason``
    explains a mismatch.
    """

    matches_requested_identity: bool
    id_mapping_mismatch: bool
    reason: str | None
    compared_aliases: tuple[tuple[str, str], ...]
    issues: tuple[ValidationIssue, ...] = ()


@dataclass(frozen=True, slots=True)
class StateEligibilityAnnotation:
    """A pure state annotation — not a metric-eligibility decision.

    Exactly one of ``is_published``, ``state_excluded``, or ``state_unknown`` is
    true. ``remains_in_discovered_breadth`` is always ``True``: state-excluded and
    state-unknown assets remain part of discovered breadth. Whether a published
    state makes an asset eligible for D, R, and Q against metric inputs is Chunk
    7A's decision.
    """

    state_value: str | None
    is_published: bool
    state_excluded: bool
    state_unknown: bool
    remains_in_discovered_breadth: bool


@dataclass(frozen=True, slots=True)
class StructuralValidationResult:
    """Structural outcome for one response payload.

    ``expected_shape`` and ``actual_shape`` name the container kinds compared, so
    a caller can report the mismatch without inspecting the payload. A failed
    member is reported as unavailable through the issues; no value is fabricated
    in its place.
    """

    is_valid: bool
    expected_shape: str
    actual_shape: str | None
    issues: tuple[ValidationIssue, ...] = ()


# --------------------------------------------------------------------------
# Taxonomy structure, freshness, and requested-category presence
# --------------------------------------------------------------------------


def _missing_header_fields(payload: Mapping[str, Any]) -> tuple[str, ...]:
    """Return the required header fields absent from ``payload``, in field order.

    A header is "present" only when it carries a value: a ``null`` header is
    absent, because SRS §1.2 states that missing, invalid, and unavailable values
    stay unavailable and are never silently converted to a default. This is the
    same presence rule the payload-level check in
    :func:`validate_taxonomy_freshness` applies, so the two can never disagree
    about which stage a payload failed at.
    """
    return tuple(
        name
        for name in TAXONOMY_REQUIRED_HEADER_FIELDS
        if name not in payload or payload[name] is None
    )


def _inventory_field(payload: Mapping[str, Any]) -> str | None:
    """Return the first present inventory container field name, else ``None``."""
    for name in TAXONOMY_INVENTORY_FIELDS:
        if payload.get(name) is not None:
            return name
    return None


def _inventory_container(payload: Mapping[str, Any]) -> object | None:
    """Return the raw inventory container, else ``None`` when none is present."""
    name = _inventory_field(payload)
    return None if name is None else payload.get(name)


def _inventory_entries(payload: Mapping[str, Any]) -> tuple[object, ...] | None:
    """Return the raw inventory entries, or ``None`` when the container is unusable.

    A missing inventory yields an empty tuple; a non-sequence container yields
    ``None`` so the caller can report a wrong container kind rather than an
    empty, silently-usable inventory.
    """
    container = _inventory_container(payload)
    if container is None:
        return ()
    if isinstance(container, (str, bytes, bytearray)):
        return None
    if isinstance(container, Sequence):
        return tuple(container)
    return None


def _inventory_shape_issues(payload: Mapping[str, Any]) -> list[ValidationIssue]:
    """Return shape issues for the canonical category-path inventory."""
    issues: list[ValidationIssue] = []
    if _inventory_container(payload) is None:
        issues.append(
            ValidationIssue(
                code="taxonomy_missing_path_inventory",
                message=(
                    "taxonomy payload carries no canonical category-path inventory "
                    f"(expected one of {list(TAXONOMY_INVENTORY_FIELDS)})"
                ),
                context=_redacted_context(expected_fields=list(TAXONOMY_INVENTORY_FIELDS)),
            )
        )
        return issues

    entries = _inventory_entries(payload)
    if entries is None:
        issues.append(
            ValidationIssue(
                code="taxonomy_invalid_path_inventory_shape",
                message="taxonomy canonical category-path inventory is not a sequence",
                context=_redacted_context(
                    field=str(_inventory_field(payload)),
                    expected_shape="list",
                    actual_shape=_shape_name(_inventory_container(payload)),
                ),
            )
        )
        return issues

    # A non-string entry is a shape problem of the inventory container itself, so it
    # is reported before any string entry is inspected — including before the empty
    # check, so an inventory of ``[7]`` is reported as a wrong entry type rather than
    # as an empty inventory (an unusable entry is never read as "no entries").
    string_entries = [entry for entry in entries if isinstance(entry, str)]
    for entry in entries:
        if not isinstance(entry, str):
            issues.append(
                ValidationIssue(
                    code="taxonomy_invalid_path_entry_type",
                    message=(
                        "taxonomy inventory entry is not a string; it cannot name a "
                        "canonical category path"
                    ),
                    context=_redacted_context(
                        field=str(_inventory_field(payload)),
                        expected_type="str",
                        entry_type=_shape_name(entry),
                    ),
                )
            )

    if not string_entries:
        issues.append(
            ValidationIssue(
                code="taxonomy_empty_path_inventory",
                message="taxonomy canonical category-path inventory is present but empty",
                context=_redacted_context(field=str(_inventory_field(payload)), entry_count=0),
            )
        )
        return issues

    seen: list[str] = []
    for entry in entries:
        if not isinstance(entry, str):
            continue
        path = normalize_category_path(entry)
        if not _canonical_path_shape_preserved(entry, path) or not _is_canonical_path_shape(path):
            issues.append(
                ValidationIssue(
                    code="taxonomy_malformed_path_entry",
                    message=(
                        "taxonomy inventory entry is not a well-formed category path "
                        "(expected at least two '/'-separated segments with no empty segment)"
                    ),
                    context=_redacted_context(path=path),
                )
            )
            continue
        if path in seen:
            issues.append(
                ValidationIssue(
                    code="taxonomy_duplicate_path_entry",
                    message="taxonomy inventory repeats a canonical category path",
                    context=_redacted_context(path=path),
                )
            )
            continue
        seen.append(path)

    issues.extend(_entry_record_issues(payload, seen))
    return issues


def _entry_record_issues(payload: Mapping[str, Any], inventory: Sequence[str]) -> list[ValidationIssue]:
    """Return issues for the optional per-entry ``categories`` records.

    A per-entry record shape is validated only when the payload supplies it: the
    inventory itself is the authority the SRS names. An entry whose ``path`` is
    not a well-formed path, or which names no path at all, is malformed.
    """
    records = payload.get("categories")
    if records is None:
        return []
    if isinstance(records, (str, bytes, bytearray)) or not isinstance(records, Sequence):
        return [
            ValidationIssue(
                code="taxonomy_invalid_categories_shape",
                message="taxonomy categories entry list is not a sequence",
                context=_redacted_context(
                    field="categories",
                    expected_shape="list",
                    actual_shape=_shape_name(records),
                ),
            )
        ]

    known = set(inventory)
    issues: list[ValidationIssue] = []
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            issues.append(
                ValidationIssue(
                    code="taxonomy_invalid_entry_shape",
                    message="taxonomy categories entry is not a mapping",
                    context=_redacted_context(
                        index=index, expected_shape="mapping", actual_shape=_shape_name(record)
                    ),
                )
            )
            continue
        raw_path = next(
            (record[name] for name in TAXONOMY_ENTRY_PATH_FIELDS if record.get(name) is not None),
            None,
        )
        if raw_path is None:
            issues.append(
                ValidationIssue(
                    code="taxonomy_entry_missing_path",
                    message="taxonomy categories entry carries no category path",
                    context=_redacted_context(index=index, expected_fields=list(TAXONOMY_ENTRY_PATH_FIELDS)),
                )
            )
            continue
        if not isinstance(raw_path, str):
            issues.append(
                ValidationIssue(
                    code="taxonomy_entry_invalid_path_type",
                    message="taxonomy categories entry path is not a string",
                    context=_redacted_context(index=index, expected_type="str", entry_type=_shape_name(raw_path)),
                )
            )
            continue
        path = normalize_category_path(raw_path)
        if not _is_canonical_path_shape(path):
            issues.append(
                ValidationIssue(
                    code="taxonomy_entry_malformed_path",
                    message="taxonomy categories entry path is not a well-formed category path",
                    context=_redacted_context(index=index, path=path),
                )
            )
            continue
        if known and path not in known:
            issues.append(
                ValidationIssue(
                    code="taxonomy_entry_path_not_in_inventory",
                    message=(
                        "taxonomy categories entry path is not listed in the canonical "
                        "category-path inventory"
                    ),
                    context=_redacted_context(index=index, path=path),
                )
            )
    return issues


def _canonical_path_shape_preserved(raw: str, normalized: str) -> bool:
    """Return whether ``normalized`` preserves ``raw``'s segment structure.

    :func:`normalize_category_path` trims whitespace and drops empty segments, so
    it is deliberately tolerant for *lookup*. A taxonomy entry, however, is a
    declaration about the canonical taxonomy itself, so an entry that only became
    well-formed because normalization repaired it — ``"/Leading/Slash"`` loses its
    leading empty segment, ``"Tools/"`` loses its trailing one — is reported as a
    malformed path entry rather than silently accepted as a different path than
    the one the file literally carries.
    """
    return len(raw.split("/")) == len(normalized.split("/"))


def _is_canonical_path_shape(path: str) -> bool:
    """Return whether ``path`` is a usable full category path.

    A canonical category path needs at least two ``/``-separated, non-empty
    segments, so a bare parent label is not mistaken for a selectable category.
    """
    if path == "":
        return False
    segments = path.split("/")
    if len(segments) < 2:
        return False
    return all(segment.strip() != "" for segment in segments)


def validate_taxonomy_structure(payload: object) -> TaxonomyValidationResult:
    """Validate a taxonomy payload's required headers and path inventory.

    Returns a result whose ``status`` is ``"valid"`` when the payload is a mapping
    carrying every required header field and a well-formed canonical category-path
    inventory, ``"missing_headers"`` when one or more expected header fields are
    absent or ``None``, and ``"malformed"`` when the payload is not a mapping or
    the inventory's shape is unusable.

    Freshness is not decided here: ``is_fresh`` is ``None`` and
    ``age_days_exact`` is ``None``, because structure alone cannot determine them.
    ``missing_header_fields`` lists absent fields in
    :data:`TAXONOMY_REQUIRED_HEADER_FIELDS` order, so the result is deterministic.
    """
    if not isinstance(payload, Mapping):
        return TaxonomyValidationResult(
            is_valid=False,
            is_fresh=None,
            status="malformed",
            payload=payload,
            issues=(
                ValidationIssue(
                    code="taxonomy_payload_not_a_mapping",
                    message="taxonomy payload is not a mapping",
                    context=_redacted_context(
                        expected_shape="mapping", actual_shape=_shape_name(payload)
                    ),
                ),
            ),
        )

    missing = _missing_header_fields(payload)
    issues: list[ValidationIssue] = []
    for name in missing:
        issues.append(
            ValidationIssue(
                code="taxonomy_missing_header",
                message=f"taxonomy payload is missing the required header field '{name}'",
                context=_redacted_context(field=name),
            )
        )
    issues.extend(_inventory_shape_issues(payload))

    if missing:
        # Missing headers are the first failing stage, so they are reported alone:
        # an empty mapping has no inventory to judge, and reporting one would be a
        # statement about the first step's subject taken after that step failed.
        return TaxonomyValidationResult(
            is_valid=False,
            is_fresh=None,
            status="missing_headers",
            payload=payload,
            missing_header_fields=missing,
            issues=tuple(issue for issue in issues if issue.code == "taxonomy_missing_header"),
        )

    return TaxonomyValidationResult(
        is_valid=not issues,
        is_fresh=None,
        status="malformed" if issues else "valid",
        payload=payload,
        missing_header_fields=missing,
        issues=tuple(issues),
    )


def _parse_capture_utc(value: object) -> tuple[datetime | None, str | None]:
    """Parse ``captured_at_utc`` into a timezone-aware UTC datetime.

    Returns ``(datetime, None)`` on success and ``(None, reason)`` on failure.
    A value that is not a string, is not ISO-8601, carries no timezone, or is not
    a timestamp at all is rejected explicitly — never treated as "absent" or
    silently normalized from local time (SRS §1.2: all calculation timestamps are
    timezone-aware UTC).
    """
    if value is None:
        return None, "captured_at_utc is absent; freshness cannot be determined"
    if not isinstance(value, str):
        return None, (
            "captured_at_utc is not a string, so it cannot be a timezone-aware "
            "UTC timestamp"
        )
    text = value.strip()
    if text == "":
        return None, "captured_at_utc is empty; freshness cannot be determined"
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None, "captured_at_utc is not a parsable ISO-8601 timestamp"
    try:
        return ensure_utc(parsed), None
    except ValueError:
        return (
            None,
            "captured_at_utc is naive (no timezone offset); a timezone-aware UTC "
            "timestamp is required",
        )


def _unusable_structure_result(structure: TaxonomyValidationResult) -> TaxonomyValidationResult | None:
    """Return the structure failure verbatim when ``structure`` is not usable.

    :func:`validate_taxonomy_structure` stops at the **first** failing stage: a
    payload that is not a mapping fails the container stage, and a mapping with
    missing header fields is reported as ``"missing_headers"`` alone, without a
    verdict on the inventory that follows it, because the inventory is only judged
    once every declared header is present.

    The two failures are not interchangeable, and this helper decides which one
    applies from the payload itself rather than from ``structure.status``. A
    payload carrying an inventory entry without its declared container
    (``categories`` present, ``canonical_category_paths`` absent) reaches the
    inventory stage and is genuinely ``"malformed"``; the same payload with *no*
    usable header is still a header failure, and reporting it as ``"malformed"``
    would state a conclusion about a stage the payload never reached.

    A downstream stage (freshness, requested-category presence, or the combined
    validator) must therefore propagate a genuine malformed result unchanged
    rather than re-deriving one from ``is_valid``, and must recompute the header
    verdict from the payload rather than trusting a status that collapses the two
    cases. Re-deriving blindly would collapse a payload whose headers are merely
    absent into ``"malformed"`` — the second stage would be stating a conclusion
    about a step that never ran, and a caller could no longer tell "the file is
    missing a required header" from "the file's shape is wrong".
    """
    if structure.is_valid:
        return None
    if structure.status == "missing_headers":
        return structure
    if isinstance(structure.payload, Mapping):
        # A payload that reached the inventory stage without ever declaring an
        # inventory field never completed the header/inventory declaration the
        # schema requires, so it is reported as a header failure. A payload that
        # *declares* an inventory field but declares no headers is genuinely
        # ``"malformed"`` and keeps that status.
        if (
            structure.status == "malformed"
            and _inventory_container(structure.payload) is None
        ):
            missing = _missing_header_fields(structure.payload)
            if missing:
                return TaxonomyValidationResult(
                    is_valid=False,
                    is_fresh=None,
                    status="missing_headers",
                    payload=structure.payload,
                    missing_header_fields=missing,
                    issues=tuple(
                        issue
                        for issue in structure.issues
                        if issue.code not in _INVENTORY_ISSUE_CODES
                    ),
                )
    return structure


def validate_taxonomy_freshness(
    payload: object,
    *,
    reference_utc: datetime,
    max_taxonomy_age_days: int = MAX_TAXONOMY_AGE_DAYS,
) -> TaxonomyValidationResult:
    """Validate taxonomy freshness against an explicit UTC reference time.

    The boundary is **inclusive**: ``age_days_exact <= max_taxonomy_age_days`` is
    fresh and anything else — a capture older than the threshold *or* one dated
    after the reference — is stale. ``age_days_exact`` is derived from the parsed
    capture instant and the reference, so it equals
    ``(reference_utc - captured_at_utc).total_seconds() / 86400``.

    ``status`` is ``"valid"`` for a fresh capture, ``"stale"`` for a capture that
    cannot be accepted as fresh (older than the threshold, or dated after the
    reference), ``"invalid_capture_timestamp"`` when ``captured_at_utc`` is absent,
    non-string, unparsable, or naive, and otherwise the structural status the
    payload already failed with (``"missing_headers"``, ``"malformed"``). Whenever
    freshness cannot be determined, ``is_fresh`` is ``None`` — never ``False`` by
    default.

    ``reference_utc`` is supplied by the caller and must be timezone-aware; this
    function reads no clock. Whether a future ``captured_at_utc`` is *rejected* or
    *tolerated* is a metric-eligibility decision owned by Chunk 7A; here it is
    classified explicitly as not-fresh and never as a known-fresh success.
    """
    structure = validate_taxonomy_structure(payload)
    unusable_structure = _unusable_structure_result(structure)
    if unusable_structure is not None:
        return unusable_structure

    payload_mapping: Mapping[str, Any] = payload  # type: ignore[assignment]
    captured_at, failure_reason = _parse_capture_utc(payload_mapping.get("captured_at_utc"))
    if captured_at is None:
        return TaxonomyValidationResult(
            is_valid=False,
            is_fresh=None,
            status="invalid_capture_timestamp",
            missing_header_fields=structure.missing_header_fields,
            issues=structure.issues
            + (
                ValidationIssue(
                    code="taxonomy_invalid_capture_timestamp",
                    message=str(failure_reason),
                    context=_redacted_context(field="captured_at_utc"),
                ),
            ),
        )

    try:
        reference = ensure_utc(reference_utc)
    except ValueError as exc:
        raise ValueError("reference_utc must be a timezone-aware UTC timestamp") from exc

    age_days_exact = (reference - captured_at).total_seconds() / SECONDS_PER_DAY
    # Only a non-negative age at or below the threshold is a known-fresh state; a
    # capture dated after the reference is classified as stale rather than accepted.
    is_fresh = 0.0 <= age_days_exact <= max_taxonomy_age_days

    if is_fresh:
        return TaxonomyValidationResult(
            is_valid=True,
            is_fresh=True,
            status="valid",
            missing_header_fields=structure.missing_header_fields,
            age_days_exact=age_days_exact,
            issues=structure.issues,
        )

    if age_days_exact < 0:
        staleness_message = (
            "taxonomy capture is dated after the reference time; the capture timestamp "
            "cannot be accepted as a known-fresh state"
        )
    else:
        staleness_message = (
            "taxonomy capture is older than the freshness threshold "
            f"({max_taxonomy_age_days} days, inclusive boundary)"
        )

    return TaxonomyValidationResult(
        is_valid=False,
        is_fresh=False,
        status="stale",
        missing_header_fields=structure.missing_header_fields,
        age_days_exact=age_days_exact,
        issues=structure.issues
        + (
            ValidationIssue(
                code="taxonomy_stale_capture",
                message=staleness_message,
                context=_redacted_context(
                    max_taxonomy_age_days=max_taxonomy_age_days, age_days_exact=age_days_exact
                ),
            ),
        ),
    )


def validate_requested_categories(
    payload: object, requested_categories: Sequence[str]
) -> TaxonomyValidationResult:
    """Validate that every requested category is present in the taxonomy inventory.

    A missing requested category is an explicit validation failure with status
    ``"missing_categories"`` and a non-empty ``missing_requested_categories`` — it
    is never represented as an empty category. The abort itself belongs to the
    caller (Chunks 3 and 12); this function only classifies.

    Comparison is exact after :func:`normalize_category_path`, so a requested
    parent path does not satisfy an inventory of child paths.
    """
    structure = validate_taxonomy_structure(payload)
    unusable_structure = _unusable_structure_result(structure)
    if unusable_structure is not None:
        return unusable_structure

    known = taxonomy_path_set(payload)
    requested_normalized = tuple(
        normalize_category_path(value) if isinstance(value, str) else None
        for value in requested_categories
    )
    missing = tuple(
        raw
        for raw, normalized in zip(requested_categories, requested_normalized)
        if normalized is None or normalized not in known
    )

    issues: list[ValidationIssue] = list(structure.issues)
    for raw in missing:
        issues.append(
            ValidationIssue(
                code="taxonomy_missing_requested_category",
                message="requested category is absent from the canonical taxonomy inventory",
                context=_redacted_context(category=raw),
            )
        )

    return TaxonomyValidationResult(
        is_valid=not missing,
        is_fresh=None,
        status="missing_categories" if missing else "valid",
        missing_header_fields=structure.missing_header_fields,
        missing_requested_categories=missing,
        issues=tuple(issues),
    )


def validate_taxonomy(
    payload: object,
    *,
    requested_categories: Sequence[str],
    reference_utc: datetime,
    max_taxonomy_age_days: int = MAX_TAXONOMY_AGE_DAYS,
) -> TaxonomyValidationResult:
    """Combine taxonomy structure, freshness, and requested-category presence.

    Runs the three validations over the same payload and reports the first failing
    stage as ``status``, in the order structure → capture timestamp → freshness →
    requested-category presence. Issues from every stage that ran are retained, so
    a caller sees all detected problems at once, and ``is_valid`` is ``True`` only
    when every stage passed. Nothing is filled in for a failed stage: the failing
    stage's values stay ``None``.

    ``reference_utc`` is a caller-supplied timezone-aware UTC timestamp; this
    function never reads the clock.
    """
    structure = validate_taxonomy_structure(payload)
    unusable_structure = _unusable_structure_result(structure)
    if unusable_structure is not None:
        return unusable_structure

    freshness = validate_taxonomy_freshness(
        payload, reference_utc=reference_utc, max_taxonomy_age_days=max_taxonomy_age_days
    )
    if not freshness.is_valid:
        return TaxonomyValidationResult(
            is_valid=False,
            is_fresh=freshness.is_fresh,
            status=freshness.status,
            missing_header_fields=freshness.missing_header_fields,
            age_days_exact=freshness.age_days_exact,
            issues=freshness.issues,
        )

    presence = validate_requested_categories(payload, requested_categories)
    issues = freshness.issues + presence.issues
    return TaxonomyValidationResult(
        is_valid=presence.is_valid,
        is_fresh=freshness.is_fresh,
        status=presence.status,
        missing_header_fields=presence.missing_header_fields,
        missing_requested_categories=presence.missing_requested_categories,
        age_days_exact=freshness.age_days_exact,
        issues=issues,
    )


# --------------------------------------------------------------------------
# Exact category membership
# --------------------------------------------------------------------------


def normalize_category_path(value: str) -> str:
    """Return the canonical form of a category path.

    Surrounding whitespace is trimmed and empty segments are dropped, so
    ``" Tools / Utilities /"`` and ``"Tools/Utilities"`` normalize alike. Segment
    text is otherwise preserved verbatim: this function does not lowercase, so
    comparison can be case-insensitive while output stays case-preserving.

    A non-string value raises ``TypeError`` rather than being coerced into a
    string sentinel; callers classify a wrong-typed category value as
    ``unverified`` before normalizing it.
    """
    if not isinstance(value, str):
        raise TypeError("category path must be a string")
    segments = (segment.strip() for segment in value.split("/"))
    return "/".join(segment for segment in segments if segment != "")


def _iter_path_candidates(value: object) -> Iterator[str]:
    """Yield the usable string path candidates inside ``value``.

    A scalar string is one candidate; a multi-valued list or tuple contributes
    each non-empty string entry. A ``None``, absent, or wrong-typed value yields
    no candidates at all, which is what distinguishes ``unverified`` from
    ``mismatch``.
    """
    if isinstance(value, str):
        yield value
    elif isinstance(value, (list, tuple)):
        for item in value:
            if isinstance(item, str):
                yield item


def taxonomy_path_set(payload: object) -> frozenset[str]:
    """Return the canonical category paths a taxonomy payload declares.

    Entries may be plain strings or mappings carrying a ``path``-style field. Only
    well-formed paths are returned; a malformed or non-string entry contributes
    nothing rather than a placeholder. A payload that is not a mapping, or that
    declares no inventory, yields an empty set.
    """
    if not isinstance(payload, Mapping):
        return frozenset()
    entries = _inventory_entries(payload)
    if entries is None:
        return frozenset()

    paths: list[str] = []
    for entry in entries:
        raw: object = entry
        if isinstance(entry, Mapping):
            raw = next(
                (entry[name] for name in TAXONOMY_ENTRY_PATH_FIELDS if entry.get(name) is not None),
                None,
            )
        if not isinstance(raw, str):
            continue
        normalized = normalize_category_path(raw)
        if _is_canonical_path_shape(normalized):
            paths.append(normalized)
    return frozenset(paths)


def match_exact_category(
    category_value: object, taxonomy_paths: Container[str]
) -> CategoryMatchResult:
    """Decide exact category membership for one response category value.

    Matching is full-segment equality after :func:`normalize_category_path`:
    ``Parent`` never matches ``Parent/Child`` and ``Parent/Child`` never matches
    ``Parent`` in either direction. Segment comparison is case-insensitive while
    the reported ``matched_path`` is the canonical, case-preserving path.

    ``status`` is ``verified`` when at least one value matches exactly, ``mismatch``
    when usable values were supplied but none matched, and ``unverified`` when no
    usable value was supplied at all (``None``, absent, or wrong-typed). Scalar and
    multi-valued shapes are both handled: a list contributes every string entry,
    and ``matched_value_count`` counts matching values.

    ``taxonomy_paths`` is a container of already-canonical paths (for example the
    result of :func:`taxonomy_path_set`); it is compared case-insensitively and is
    never mutated or re-scanned for I/O. When several known paths differ only in
    case, the first one encountered in ``taxonomy_paths`` order is the reported
    canonical form, so the reported path is deterministic.
    """
    if isinstance(taxonomy_paths, (str, bytes, bytearray)):
        raise TypeError("taxonomy_paths must be a container of canonical category paths")
    matching_paths: dict[str, str] = {}
    for item in taxonomy_paths:
        if isinstance(item, str):
            canonical_item = normalize_category_path(item)
            matching_paths.setdefault(canonical_item.casefold(), canonical_item)
    known = set(matching_paths)

    raw_values = tuple(_iter_path_candidates(category_value))
    if not raw_values:
        return CategoryMatchResult(
            matched_path=None,
            status=CategoryFilterValidationStatus.UNVERIFIED,
            matched_value_count=0,
            unmatched_values=(),
            issues=(
                ValidationIssue(
                    code="category_value_unverified",
                    message=(
                        "category value is absent, null, or not a string or string "
                        "sequence, so membership cannot be verified"
                    ),
                    context=_redacted_context(
                        expected_shape="str or list[str]", actual_shape=_shape_name(category_value)
                    ),
                ),
            ),
        )

    matched_path: str | None = None
    matched_value_count = 0
    unmatched: list[str] = []
    for raw in raw_values:
        canonical = normalize_category_path(raw)
        canonical_path = matching_paths.get(canonical.casefold())
        if canonical_path is not None:
            matched_value_count += 1
            if matched_path is None:
                matched_path = canonical_path
            continue
        unmatched.append(canonical)

    if matched_value_count > 0:
        return CategoryMatchResult(
            matched_path=matched_path,
            status=CategoryFilterValidationStatus.VERIFIED,
            matched_value_count=matched_value_count,
            unmatched_values=tuple(unmatched),
        )

    return CategoryMatchResult(
        matched_path=None,
        status=CategoryFilterValidationStatus.MISMATCH,
        matched_value_count=0,
        unmatched_values=tuple(unmatched),
        issues=(
            ValidationIssue(
                code="category_value_mismatch",
                message=(
                    "no supplied category value matches a canonical taxonomy path "
                    "exactly; parent and child paths do not match by prefix"
                ),
                context=_redacted_context(
                    unmatched_value_count=len(unmatched),
                    supplied_value_count=len(raw_values),
                ),
            ),
        ),
    )


def discovery_status_for_category_status(
    status: CategoryFilterValidationStatus,
) -> DiscoveryStatus | None:
    """Map a category-filter status onto the LREQ-EXT-050 discovery vocabulary.

    ``unverified`` corresponds to ``filter_unverified`` and ``mismatch`` to
    ``category_mismatch``. ``verified`` asserts no incomplete condition and maps to
    no discovery status, so it returns ``None`` — a failed or truncated page is
    never interpreted as zero assets, and a verified filter is not a failure.

    Producing the warning and preventing a fully rankable result (LREQ-EXT-090) is
    the caller's work in Chunks 10 and 12; this function only supplies the
    vocabulary mapping.
    """
    if status is CategoryFilterValidationStatus.UNVERIFIED:
        return DiscoveryStatus.FILTER_UNVERIFIED
    if status is CategoryFilterValidationStatus.MISMATCH:
        return DiscoveryStatus.CATEGORY_MISMATCH
    return None


# --------------------------------------------------------------------------
# Identity candidate collection and canonicalization
# --------------------------------------------------------------------------


def _usable_candidate(raw_value: object) -> str | None:
    """Return ``raw_value`` when it is a non-empty string, else ``None``.

    A value that is absent, ``None``, whitespace-only, or not a string is not a
    candidate: it is dropped without inventing a placeholder. Non-string values
    are never coerced into strings.
    """
    if not isinstance(raw_value, str):
        return None
    if raw_value.strip() == "":
        return None
    return raw_value


def _canonicalize_product_id(raw_value: str) -> tuple[str | None, str | None]:
    """Canonicalize an already-canonical product identifier.

    Mapping rule 1.0.1 treats ``ec_product_id`` and ``permanentid`` as canonical
    as-supplied: the value is trimmed and otherwise passed through unchanged, with
    no transformation. A value that is empty after trimming contributes no
    candidate.
    """
    trimmed = raw_value.strip()
    if trimmed == "":
        return None, "candidate is whitespace-only"
    return trimmed, None


def _canonicalize_uri(raw_value: str) -> tuple[str | None, str | None]:
    """Extract the trailing numeric identifier from a URL's final path segment.

    Mapping rule 1.0.1 reads the identifier after the final ``-`` in the URL's
    last path segment, ignoring any query string or fragment. A value that does
    not fit that pattern contributes **nothing** — it never yields a guessed or
    partial identifier.

    The extraction rule itself is *inferred*, not verified against a real
    captured response (``interfaces/chunk-01.md`` §4.1 caveat; 1.0.1 corrects the
    candidate *comparison* rule only and deliberately leaves extraction
    untouched).
    """
    text = raw_value.strip()
    if text == "":
        return None, "candidate is whitespace-only"
    without_fragment = text.split("#", 1)[0]
    without_query = without_fragment.split("?", 1)[0]
    last_segment = without_query.rstrip("/").rsplit("/", 1)[-1]
    match = _URI_TRAILING_IDENTIFIER.search(last_segment)
    if match is None:
        return (
            None,
            "URL last path segment does not end in a '-<numeric>' identifier, so no "
            "canonical identity can be derived from it",
        )
    return match.group(1), None


def canonicalize_identity_candidate(
    raw_value: str, *, mapping_rule_version: str = IDENTITY_MAPPING_RULE_VERSION
) -> str | None:
    """Canonicalize a raw identity candidate under a versioned mapping rule.

    Under mapping rule ``1.0.1``:

    * any non-empty value — including an ``ec_product_id`` or ``permanentid`` — is
      accepted as already canonical after whitespace trimming, with no
      transformation;
    * a URI value contributes the trailing numeric identifier after the final
      ``-`` in its last path segment (query string and fragment ignored);
    * a URI value that does not fit that pattern returns ``None``, so it
      contributes no candidate rather than a wrong one.

    The source field is deliberately not a parameter: the rule this function
    implements is field-agnostic, and :func:`collect_identity_candidates` applies
    the URI-specific reading to ``clickUri``/``uri`` before calling in. Callers
    distinguish "nothing usable was supplied" (an empty or wrong-typed value) from
    should not arise here, because empty and non-string values are already dropped
    by :func:`collect_identity_candidates`.

    ``mapping_rule_version`` selects the rule and is required to be a version this
    implementation knows; an unknown version raises ``ValueError`` instead of
    silently applying ``1.0.1`` semantics. A consumer decides behavior from
    :attr:`IdentityResolutionResult.mapping_rule_version`, never by assuming a
    version. ``1.0.1`` differs from ``1.0.0`` only in the candidate comparison:
    ``1.0.0`` also accepted a URI-derived identifier that was a *suffix* of an
    explicit product id, which rescued genuine ``LREQ-EXT-070`` disagreements.
    """
    if mapping_rule_version != IDENTITY_MAPPING_RULE_VERSION:
        raise ValueError(
            f"unsupported identity mapping rule version: {mapping_rule_version!r}"
        )
    if not isinstance(raw_value, str):
        raise TypeError("raw_value must be a string; drop non-string candidates first")
    trimmed = raw_value.strip()
    if trimmed == "":
        return None
    if _URI_TRAILING_IDENTIFIER.search(trimmed.rsplit("/", 1)[-1].split("?", 1)[0]):
        canonical, _ = _canonicalize_uri(trimmed)
        return canonical
    return trimmed


def collect_identity_candidates(record: Mapping[str, object]) -> tuple[IdentityCandidate, ...]:
    """Retain every non-empty identity candidate from one discovery record.

    Reads ``ec_product_id``, ``permanentid``, response-level ``clickUri``, and
    response-level ``uri`` in that fixed order and keeps every non-empty string
    candidate verbatim as ``raw_value``. Empty, whitespace-only, absent, and
    non-string values are dropped without inventing placeholders, so an absence is
    visible as a missing candidate rather than as an empty string.

    Each candidate records the source field it came from and its canonical form
    under mapping rule 1.0.1; a candidate that cannot be canonicalized keeps
    ``canonical_value = None`` plus a typed ``parse_failure_reason``. Candidate
    order is input order, so the result is deterministic for equal inputs.
    """
    candidates: list[IdentityCandidate] = []
    for source_field in _IDENTITY_SOURCE_FIELDS:
        raw_value = _usable_candidate(record.get(source_field))
        if raw_value is None:
            continue
        if source_field in _URI_FIELDS:
            canonical_value, failure_reason = _canonicalize_uri(raw_value)
        else:
            canonical_value, failure_reason = _canonicalize_product_id(raw_value)
        candidates.append(
            IdentityCandidate(
                source_field=source_field,
                raw_value=raw_value,
                canonical_value=canonical_value,
                parse_failure_reason=failure_reason,
            )
        )
    return tuple(candidates)


def _comparable_identity(canonical_value: str) -> str:
    """Return the comparison form of a canonical candidate.

    Mapping rule 1.0.1 compares ``ec_product_id``/``permanentid`` numerically when
    both sides parse as integers, else as strings. Since canonical candidates are
    digits-only strings here, comparing their integer value (falling back to the
    literal text when the integer is unparsable) gives numerically-equal forms
    such as ``"123"`` and ``"0123"`` the same identity without losing a
    non-numeric canonical value.
    """
    try:
        return str(int(canonical_value))
    except ValueError:
        return canonical_value


def resolve_canonical_identity(
    record: Mapping[str, object],
    *,
    mapping_rule_version: str = IDENTITY_MAPPING_RULE_VERSION,
) -> IdentityResolutionResult:
    """Classify a discovery record's canonical identity as resolved, conflict, or unresolved.

    All successfully-derived canonical candidates agree → ``resolved``, with that
    value as ``canonical_identity_key`` and membership in the canonical
    denominator and the enrichment set. Any disagreement between derived
    candidates → ``conflict``. Nothing derivable from any candidate →
    ``unresolved``. A ``conflict`` or ``unresolved`` record never carries a
    canonical key, always carries a non-``None`` ``reason``, and is excluded from
    both the canonical denominator and the enrichment set: neither case may be
    silently treated as an ordinary asset (LREQ-EXT-070).

    Comparison uses the mapping rule's numeric-or-string rule, so ``"123"``,
    ``" 123 "``, and ``0123`` agree. Candidates that could not be canonicalized do
    not vote — they are retained in ``candidates`` with their failure reason and
    are reported as issues — so a record whose only candidate is unparseable is
    ``unresolved`` rather than conflict-free by omission.

    ``mapping_rule_version`` is recorded on the result so consumers branch on the
    rule that produced it instead of assuming one version's semantics. ``1.0.1``
    differs from ``1.0.0`` only in the candidate comparison: ``1.0.0`` also
    accepted a URI-derived identifier that was a *suffix* of an explicit product
    id, which rescued genuine ``LREQ-EXT-070`` disagreements.
    """
    if mapping_rule_version != IDENTITY_MAPPING_RULE_VERSION:
        raise ValueError(
            f"unsupported identity mapping rule version: {mapping_rule_version!r}"
        )
    candidates = collect_identity_candidates(record)
    issues: list[ValidationIssue] = []
    for candidate in candidates:
        if candidate.parse_failure_reason is not None:
            issues.append(
                ValidationIssue(
                    code="identity_candidate_unparseable",
                    message=(
                        f"identity candidate from '{candidate.source_field}' cannot be "
                        "canonicalized under the active mapping rule"
                    ),
                    context=_redacted_context(source_field=candidate.source_field),
                )
            )

    derived = [candidate for candidate in candidates if candidate.canonical_value is not None]
    if not derived:
        return IdentityResolutionResult(
            canonical_identity_key=None,
            status=IdentityResolutionStatus.UNRESOLVED,
            reason=(
                "no identity candidate could be canonicalized under mapping rule "
                f"{mapping_rule_version}"
            ),
            candidates=candidates,
            included_in_canonical_denominator=False,
            included_in_enrichment_set=False,
            mapping_rule_version=mapping_rule_version,
            issues=tuple(issues),
        )

    comparison_keys = {_comparable_identity(candidate.canonical_value or "") for candidate in derived}
    if len(comparison_keys) > 1:
        sources = tuple(dict.fromkeys(candidate.source_field for candidate in derived))
        return IdentityResolutionResult(
            canonical_identity_key=None,
            status=IdentityResolutionStatus.CONFLICT,
            reason=(
                "identity candidates disagree under mapping rule "
                f"{mapping_rule_version}: distinct canonical identities were derived "
                f"from {list(sources)}"
            ),
            candidates=candidates,
            included_in_canonical_denominator=False,
            included_in_enrichment_set=False,
            mapping_rule_version=mapping_rule_version,
            issues=tuple(issues),
        )

    canonical_identity_key = derived[0].canonical_value
    return IdentityResolutionResult(
        canonical_identity_key=canonical_identity_key,
        status=IdentityResolutionStatus.RESOLVED,
        reason=None,
        candidates=candidates,
        included_in_canonical_denominator=True,
        included_in_enrichment_set=True,
        mapping_rule_version=mapping_rule_version,
        issues=tuple(issues),
    )


# --------------------------------------------------------------------------
# GraphQL identity aliases and state annotation
# --------------------------------------------------------------------------


def compare_graphql_identity_aliases(
    requested_identity: str,
    aliases: Mapping[str, object],
    *,
    mapping_rule_version: str = IDENTITY_MAPPING_RULE_VERSION,
) -> GraphQLIdentityComparisonResult:
    """Compare returned GraphQL identity aliases against a requested canonical identity.

    Every alias value that canonicalizes under the mapping rule is compared, after
    canonicalization, with the requested canonical identity; raw string equality is
    never the basis of agreement. ``matches_requested_identity`` is ``True`` only
    when at least one alias canonicalized **and** every canonicalized alias agreed.

    A missing alias is a mismatch with an explicit reason — an absent alias is
    never treated as agreement. An alias that cannot be canonicalized is likewise a
    mismatch with an explicit reason. ``id_mapping_mismatch`` is ``True`` whenever
    the aliases do not agree, so it implies ``matches_requested_identity`` is
    ``False``. Marking the persisted asset and excluding it from D, R, and Q are
    Chunk 5's and Chunk 7A's work; this function only produces the pure comparison.

    ``aliases`` is a mapping of alias name to returned value. Non-string and
    ``None`` values are non-agreeing aliases rather than absent ones, and are
    reported as such. The comparison is deterministic: aliases are inspected in
    sorted key order, and a mismatch never depends on iteration order.
    """
    if mapping_rule_version != IDENTITY_MAPPING_RULE_VERSION:
        raise ValueError(
            f"unsupported identity mapping rule version: {mapping_rule_version!r}"
        )

    requested_canonical, requested_failure = _canonicalize_comparison_target(requested_identity)
    compared: list[tuple[str, str]] = []
    non_agreeing: list[str] = []
    unparsable: list[str] = []
    missing: list[str] = []

    if not aliases:
        missing.append("no identity aliases were returned")

    for alias_name in sorted(aliases):
        raw_value = aliases[alias_name]
        if raw_value is None or not isinstance(raw_value, str) or raw_value.strip() == "":
            missing.append(alias_name)
            compared.append((alias_name, "null" if raw_value is None else redact_value(raw_value)))
            continue
        if alias_name in _URI_FIELDS:
            canonical_value, failure_reason = _canonicalize_uri(raw_value)
        else:
            canonical_value, failure_reason = _canonicalize_product_id(raw_value)
        if canonical_value is None:
            unparsable.append(alias_name)
            # An alias that cannot be canonicalized contributes no canonical value,
            # so ``compared_aliases`` records a structural placeholder rather than
            # echoing the unusable raw text. The placeholder is built from the
            # failure reason (a structural description such as "malformed URI"), not
            # from the raw text, and is passed through :func:`redact_value` so the
            # recorded pair is idempotent under redaction: no credential-shaped alias
            # can reach the comparison result through this path (plan §5.2
            # "Redaction"), while the failure reason is still structurally visible.
            placeholder = (
                f"uncanonicalizable: {failure_reason}"
                if failure_reason
                else "uncanonicalizable"
            )
            compared.append((alias_name, redact_value(placeholder)))
            continue
        compared.append((alias_name, canonical_value))
        if requested_canonical is None or _comparable_identity(
            canonical_value
        ) != _comparable_identity(requested_canonical):
            non_agreeing.append(alias_name)

    if requested_failure is not None:
        reason = (
            "requested canonical identity cannot be canonicalized under mapping rule "
            f"{mapping_rule_version}, so alias agreement cannot be established"
        )
        mismatched = True
    elif missing and not compared:
        reason = "no GraphQL identity alias was returned; a missing alias is not agreement"
        mismatched = True
    elif missing:
        reason = (
            "GraphQL identity aliases were missing or unusable and are not treated as "
            f"agreement: {sorted(missing)}"
        )
        mismatched = True
    elif unparsable:
        reason = (
            "returned GraphQL identity aliases could not be canonicalized under mapping "
            f"rule {mapping_rule_version}: {sorted(unparsable)}"
        )
        mismatched = True
    elif non_agreeing:
        reason = (
            "returned GraphQL identity aliases disagree with the requested canonical "
            f"identity: {sorted(non_agreeing)}"
        )
        mismatched = True
    else:
        reason = None
        mismatched = False

    issues: tuple[ValidationIssue, ...] = ()
    if mismatched:
        issues = (
            ValidationIssue(
                code="graphql_id_mapping_mismatch",
                message=str(reason),
                context=_redacted_context(
                    alias_count=len(aliases),
                    disagreeing_alias_count=len(non_agreeing),
                    unusable_alias_count=len(missing) + len(unparsable),
                ),
            ),
        )

    return GraphQLIdentityComparisonResult(
        matches_requested_identity=not mismatched,
        id_mapping_mismatch=mismatched,
        reason=reason,
        compared_aliases=tuple(compared),
        issues=issues,
    )


def _unusable_alias_placeholder(raw_value: object) -> str:
    """Return a secret-free placeholder for an alias value that cannot be compared.

    A value that is ``null``, non-string, or cannot be canonicalized contributes no
    canonical value, so ``compared_aliases`` records a placeholder instead. The
    placeholder never carries the raw value: an unusable alias is reported
    structurally (its type or size), never by echoing its text. The generic
    :func:`redact_value` placeholder is used for every case except ``None``, which
    is already an unambiguous "no value" marker rather than raw payload text.
    """
    return "null" if raw_value is None else redact_value(raw_value)


def _canonicalize_comparison_target(value: str) -> tuple[str | None, str | None]:
    """Canonicalize a requested identity for alias comparison."""
    if not isinstance(value, str) or value.strip() == "":
        return None, "requested identity is empty"
    if _URI_TRAILING_IDENTIFIER.search(value.rsplit("/", 1)[-1].split("?", 1)[0]):
        return _canonicalize_uri(value)
    return _canonicalize_product_id(value)


def annotate_state_eligibility(state_value: object) -> StateEligibilityAnnotation:
    """Annotate a GraphQL ``state`` value as published, excluded, or unknown.

    ``"published"`` (compared case-insensitively) yields ``is_published = True``.
    Any other usable non-empty string yields ``state_excluded = True``. A missing,
    ``None``, empty, or non-string value yields ``state_unknown = True``.

    ``remains_in_discovered_breadth`` is always ``True``: state-excluded and
    state-unknown assets stay in discovered breadth. This function deliberately
    returns no metric-eligibility verdict — whether a published state makes an
    asset eligible for D, R, and Q against metric inputs is Chunk 7A's decision.
    ``state_value`` is ``None`` for a non-string input, so an unknown state is
    never misreported as a state string.
    """
    if isinstance(state_value, str) and state_value.strip() != "":
        normalized = state_value.strip()
        if normalized.casefold() == "published":
            return StateEligibilityAnnotation(
                state_value=normalized,
                is_published=True,
                state_excluded=False,
                state_unknown=False,
                remains_in_discovered_breadth=True,
            )
        return StateEligibilityAnnotation(
            state_value=normalized,
            is_published=False,
            state_excluded=True,
            state_unknown=False,
            remains_in_discovered_breadth=True,
        )
    return StateEligibilityAnnotation(
        state_value=None,
        is_published=False,
        state_excluded=False,
        state_unknown=True,
        remains_in_discovered_breadth=True,
    )


# --------------------------------------------------------------------------
# Structural response validation
# --------------------------------------------------------------------------


def _matches_declared_type(value: object, declared: type | tuple[type, ...]) -> bool:
    """Return whether ``value`` satisfies a declared type specification."""
    if declared is int:
        return isinstance(value, int) and not isinstance(value, bool)
    if declared is float:
        return isinstance(value, float) and not isinstance(value, bool)
    if isinstance(declared, tuple):
        return any(_matches_declared_type(value, item) for item in declared)
    return isinstance(value, declared)


def validate_response_shape(
    payload: object,
    *,
    expected_shape: str,
    required_members: Sequence[str] = (),
    field_types: Mapping[str, type | tuple[type, ...]] | None = None,
) -> StructuralValidationResult:
    """Validate a response payload's container kind, required members, and value types.

    Checks, in a deterministic order, that the payload's container kind matches
    ``expected_shape`` (``"mapping"``, ``"list"``, ``"identity"``, or a named scalar
    kind from :data:`RESPONSE_CONTAINER_KINDS`), that every ``required_members``
    entry is present, that a declared ``field_types`` entry matches its value's
    type, and — for a mapping that declares an identity member (``graphql_id``,
    ``product_id``, ``packageId``, or ``asset_identity_key``) as required, or that
    is validated against the ``"identity"`` shape — that at least one declared
    identity member is actually populated.

    Each problem yields its own typed issue with a stable code, so ``null``,
    absent, and wrong-typed members stay distinguishable and are never collapsed
    into one "invalid" state. Failed members are reported as unavailable; no value
    is substituted for them, and a missing scalar is never read as zero (SRS §4.2
    LREQ-GQL-050). Whether a structurally valid value is *usable for a metric* is
    Chunk 7A's semantic decision and is not made here.

    ``actual_shape`` is ``None`` only when no meaningful kind can be named; every
    other outcome reports the observed kind so a caller can log the mismatch
    without inspecting the payload. When a *single member* is validated rather than
    a whole response (``expected_shape="list"`` against one multi-valued member),
    ``actual_shape`` reports that member's own kind, so a mapping-shaped member is
    not reported as the ``"mapping"`` response it is not.
    """
    issues: list[ValidationIssue] = []
    actual_shape: str | None = _shape_name(payload)
    if expected_shape == "list" and isinstance(payload, Mapping):
        # A mapping is the multi-valued member shape: report the shape the caller
        # asked about, not the response container the payload is not.
        actual_shape = "list"

    if not _container_matches(payload, expected_shape):
        issues.append(
            ValidationIssue(
                code="response_wrong_container_kind",
                message=f"response payload is not a '{expected_shape}' container",
                context=_redacted_context(expected_shape=expected_shape, actual_shape=actual_shape),
            )
        )
        return StructuralValidationResult(
            is_valid=False,
            expected_shape=expected_shape,
            actual_shape=actual_shape,
            issues=tuple(issues),
        )

    if not isinstance(payload, Mapping):
        return StructuralValidationResult(
            is_valid=True, expected_shape=expected_shape, actual_shape=actual_shape, issues=()
        )

    # Member-level checks only exist for container kinds that carry named members.
    # A payload validated against a member-bearing kind while declaring no members
    # (``required_members`` empty and no ``field_types``) has nothing left to judge,
    # so the container check above is its whole verdict. Identity detection still
    # runs: the kind itself can be the identity declaration (``graphql_id``), in
    # which case a payload carrying no identity member is a missing identity.
    if not required_members and not field_types and expected_shape != "identity":
        return StructuralValidationResult(
            is_valid=True, expected_shape=expected_shape, actual_shape=actual_shape, issues=()
        )

    # Member-level checks come first so a declared identity member's absence or null
    # stays distinguishable from a non-identity member's, and the group-level
    # identity requirement below is appended once rather than once per alias.
    for member in required_members:
        if member not in payload:
            issues.append(
                ValidationIssue(
                    code="response_missing_required_member",
                    message=f"response payload is missing the required member '{member}'",
                    context=_redacted_context(member=member, field=member),
                )
            )
        elif payload[member] is None:
            issues.append(
                ValidationIssue(
                    code="response_null_required_member",
                    message=(
                        f"required member '{member}' is present but null; a null value is "
                        "unavailable and is not substituted with a default"
                    ),
                    context=_redacted_context(member=member, field=member),
                )
            )

    for member, declared in (field_types or {}).items():
        if member not in payload or payload[member] is None:
            continue
        if not _matches_declared_type(payload[member], declared):
            issues.append(
                ValidationIssue(
                    code="response_wrong_scalar_type",
                    message=f"member '{member}' does not match its declared type",
                    context=_redacted_context(
                        member=member,
                        field=member,
                        expected_type=_declared_type_name(declared),
                        actual_shape=_shape_name(payload[member]),
                    ),
                )
            )

    # Declaring an identity member among ``required_members`` — or validating
    # against the ``"identity"`` shape directly — is what makes the payload an
    # operation response expected to carry an identity (LREQ-GQL-040). The identity
    # requirement is scoped to *those* declared members: they are saturated as a
    # group, because an operation that declares two aliases for one identity needs
    # only one of them populated, and a payload that leaves all of them empty is a
    # missing identity rather than one report per alias.
    declared_identity_members = [
        member for member in required_members if member in _IDENTITY_ALIAS_MEMBERS
    ]
    identity_members = (
        sorted(_IDENTITY_ALIAS_MEMBERS)
        if expected_shape == "identity"
        else declared_identity_members
    )
    if identity_members and not any(
        _populated_identity_value(payload.get(member)) for member in identity_members
    ):
        issues.append(
            ValidationIssue(
                code="response_missing_identity",
                message=(
                    "no populated identity member was returned; a missing identity is an "
                    "operation error, not an empty identity"
                ),
                context=_redacted_context(
                    expected_fields=sorted(identity_members),
                    actual_shape=_shape_name(payload),
                ),
            )
        )

    return StructuralValidationResult(
        is_valid=not issues,
        expected_shape=expected_shape,
        actual_shape=actual_shape,
        issues=tuple(_sorted_issues(issues)),
    )


def _container_matches(payload: object, expected_shape: str) -> bool:
    """Return whether ``payload`` is the requested container kind."""
    if expected_shape == "mapping":
        return isinstance(payload, Mapping)
    if expected_shape == "list":
        # ``list`` names sequence-shaped payloads, and a mapping is the multi-valued
        # shape the caller may hand in: a category filter that returned one path is
        # still structurally the declared list. A scalar is not a sequence and fails
        # the check, so ``str``/``int``/``none`` still report a wrong container kind.
        return isinstance(payload, (Mapping, list, tuple))
    if expected_shape == "identity":
        return isinstance(payload, Mapping)
    if expected_shape == "str":
        return isinstance(payload, str)
    if expected_shape == "int":
        return isinstance(payload, int) and not isinstance(payload, bool)
    if expected_shape == "float":
        return isinstance(payload, float)
    if expected_shape == "bool":
        return isinstance(payload, bool)
    if expected_shape == "none":
        return payload is None
    if expected_shape == "tuple":
        return isinstance(payload, tuple)
    if expected_shape == "set":
        return isinstance(payload, (set, frozenset))
    if expected_shape == "bytes":
        return isinstance(payload, (bytes, bytearray))
    raise ValueError(f"unknown expected shape: {expected_shape!r}")


def _declared_type_name(declared: type | tuple[type, ...]) -> str:
    """Return a stable display name for a declared type specification."""
    if isinstance(declared, tuple):
        return " | ".join(item.__name__ for item in declared)
    return declared.__name__


def _sorted_issues(issues: Sequence[ValidationIssue]) -> tuple[ValidationIssue, ...]:
    """Order issues deterministically by member name, then code.

    The primary key is the reported member (so issues group by field in the
    payload's own order), and the secondary key is the issue code. Ties keep their
    insertion order, so equal inputs always produce an equal issue sequence.
    """
    return tuple(
        sorted(
            issues,
            key=lambda issue: (
                str(issue.context.get("member", issue.context.get("field", ""))),
                _shape_sort_key(issue.code),
            ),
        )
    )


def _shape_sort_key(code: str) -> tuple[int, str]:
    """Return a deterministic ordering key for a structural issue code."""
    for index, prefix in enumerate(_SHAPE_PRECEDENCE):
        if code == f"response_{prefix}" or code == prefix:
            return (index, code)
    return (len(_SHAPE_PRECEDENCE), code)


# --------------------------------------------------------------------------
# Redacted error summaries
# --------------------------------------------------------------------------


def summarize_validation_issues(
    issues: Sequence[ValidationIssue], *, max_context_chars: int = 256
) -> str:
    """Render issues as a deterministic, redacted JSON summary.

    The result is suitable for a record's ``error_summary_json`` column: a JSON
    object with a count, the stable issue codes, and a bounded view of each issue's
    context. Every string passes back through :func:`redact_value`, so credential
    values, ``Authorization`` headers, CSRF tokens, cookies, and raw response
    bodies cannot survive into a log, a report, or SQLite (SRS §4.3 LREQ-SEC-020).

    ``max_context_chars`` bounds the rendered summary length: context is included
    only while it fits, and the summary stays valid JSON either way. An empty issue
    sequence yields a summary with a zero count rather than an error.
    """
    entries: list[dict[str, Any]] = []
    budget = max(int(max_context_chars), 0)
    for issue in issues:
        entry: dict[str, Any] = {"code": issue.code, "message": redact_value(issue.message)}
        rendered_context = {
            str(key): redact_value(value) for key, value in sorted(issue.context.items())
        }
        if rendered_context and budget > 0:
            candidate = json.dumps(rendered_context, sort_keys=True, separators=(",", ":"))
            if len(candidate) <= budget:
                entry["context"] = rendered_context
                budget -= len(candidate)
        entries.append(entry)

    summary = {
        "issue_count": len(entries),
        "codes": sorted({issue.code for issue in issues}),
        "issues": entries,
    }
    return json.dumps(summary, sort_keys=True, separators=(",", ":"))
