"""Run orchestration boundary.

Chunk 6A owns the identity preflight planner, executor, and gate. It selects a
deterministic per-run preflight set from the completed sampling result, executes
one GraphQL enrichment request per unique preflight identity through the Chunk 5
``enrich_asset`` adapter, records per-identity operation outcomes, computes
unique-identity success/conflict rates, persists a summary plus one observation
per attempted identity **before** the gate returns, and owns the ``failed`` run
transition.

The pure helpers (:func:`select_preflight_identities`,
:func:`compute_preflight_rates`, :func:`evaluate_preflight_gate`,
:func:`bulk_enrichment_allowed`, :func:`graphql_endpoint_signature`) perform no
I/O and read no clock. The adapter supplies every protocol behavior; this module
never constructs a GraphQL request, never correlates a response, and never
classifies a failure. ``transport``, ``sleep``, and ``retrieved_at_utc`` are
always caller-injected.
"""

from __future__ import annotations

import json
import logging
import math
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from typing import AbstractSet, Any

from niche_scout.collector_graphql import (
    GRAPHQL_BATCH_ENDPOINT,
    GraphQLBatchResponse,
    GraphQLRetryPolicy,
    GraphQLTransport,
    enrich_asset,
)
from niche_scout.collector_graphql import (
    EnrichmentObservationDraft as EnrichmentObservationDraft,
)
from niche_scout.config import Credentials, NicheScoutConfig
from niche_scout.database import (
    PENDING_USABLE_STATUS,
    DatabaseError,
    EnrichmentObservationRecord,
    SqliteRepository,
    parse_stratum_statistics,
)
from niche_scout.metrics import (
    METRIC_REASON_NULL,
    BreadthMetricInput,
    CategoryMetricInput,
    MetricObservation,
    StratumMetricInput,
    age_days_exact,
    age_normalized_page_view_index,
    compute_category_raw_metrics,
    quality_observation_eligibility,
    stratum_is_usable,
)
from niche_scout.models import (
    ENDPOINT_CONTRACT_VERSION,
    IDENTITY_MAPPING_RULE_VERSION,
    IDENTITY_PREFLIGHT_ASSETS_PER_CATEGORY,
    IDENTITY_PREFLIGHT_MAX_CONFLICT_RATE,
    IDENTITY_PREFLIGHT_MIN_CATEGORIES,
    IDENTITY_PREFLIGHT_MIN_SUCCESS_RATE,
    MIN_AGE_DAYS_FOR_RATE,
    MIN_USABLE_SAMPLES_PER_STRATUM,
    RECENT_WINDOW_DAYS,
    CategoryScoreRecord,
    GraphQLOperationCorrelationMode,
    IdentityPreflightStatus,
    OperationStatus,
    PageViewSemanticsStatus,
    RunStatus,
    ensure_utc,
)
from niche_scout.sampling import CategorySamplingResult, RunSamplingResult
from niche_scout.validation import ValidationIssue, summarize_validation_issues

__all__ = [
    "PreflightPolicy",
    "preflight_policy_from_config",
    "PreflightIdentity",
    "PreflightSelection",
    "select_preflight_identities",
    "PreflightRates",
    "compute_preflight_rates",
    "evaluate_preflight_gate",
    "bulk_enrichment_allowed",
    "PreflightObservation",
    "graphql_endpoint_signature",
    "IdentityPreflightSummary",
    "IdentityPreflightOutcome",
    "run_identity_preflight",
    "PreflightPersistenceReport",
    "persist_preflight",
    "EnrichmentUnionMember",
    "EnrichmentUnion",
    "compute_enrichment_union",
    "EnrichmentProjection",
    "build_enrichment_projection",
    "log_enrichment_projection",
    "EnrichmentExecutionReport",
    "enrich_unique_identities",
    "capture_scoring_cutoff_utc",
    "StratumFinalization",
    "CategoryFinalization",
    "FinalizationReport",
    "finalize_stratum_counts",
    "finalize_enrichment",
    "assert_finalization_consistency",
]

#: The Chunk 5 ``GraphQLOperationCorrelationMode`` members that mark an invalid
#: correlation mode. ``enrich_asset`` rewrites the correlation to the requested
#: mode, so the adapter never reports one of these; they exist for the
#: defensive comparison only and are never persisted.
_CORRELATION_MODE_VALUES: frozenset[str] = frozenset(
    mode.value for mode in GraphQLOperationCorrelationMode
)

#: Module logger for the LREQ-NFR-020 pre-enrichment projection line. Every
#: message carries counts and durations only; never an identity, category,
#: credential, header value, cookie, or response body (LREQ-SEC-010/020).
_LOGGER = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# 5.1 Policy value object
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PreflightPolicy:
    """The frozen LREQ-ID-030 policy. Defaults are the models.py constants.

    ``max_conflict_rate`` has no config knob (SRS §14 exposes only three preflight
    keys); it is always ``IDENTITY_PREFLIGHT_MAX_CONFLICT_RATE`` in production.
    Construction never reads the clock, config, or environment.
    """

    min_categories: int = IDENTITY_PREFLIGHT_MIN_CATEGORIES
    assets_per_category: int = IDENTITY_PREFLIGHT_ASSETS_PER_CATEGORY
    max_conflict_rate: float = IDENTITY_PREFLIGHT_MAX_CONFLICT_RATE
    min_success_rate: float = IDENTITY_PREFLIGHT_MIN_SUCCESS_RATE


def preflight_policy_from_config(config: NicheScoutConfig) -> PreflightPolicy:
    """Read the three config knobs, keep ``max_conflict_rate`` from the constant.

    The three config values are consumed as-is; they are not clamped or
    re-validated here (``config.load_config`` already validates the success-rate
    range). Pure: no I/O, no clock.
    """
    return PreflightPolicy(
        min_categories=config.identity_preflight_min_categories,
        assets_per_category=config.identity_preflight_assets_per_category,
        max_conflict_rate=IDENTITY_PREFLIGHT_MAX_CONFLICT_RATE,
        min_success_rate=config.identity_preflight_min_success_rate,
    )


# --------------------------------------------------------------------------
# 5.2 Pure selection and rate types
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PreflightIdentity:
    """One unique preflight identity and the category-order slot that claimed it."""

    asset_identity_key: str
    preflight_rank: int
    source_category: str


@dataclass(frozen=True, slots=True)
class PreflightSelection:
    """The deterministic preflight plan; persisted via ``preflight_selected``.

    ``identities`` are unique by ``asset_identity_key``, in
    ``(category order, member order)`` first-seen order. ``eligible_categories``
    are the categories with ``enriched_sample_count >= assets_per_category`` in
    run order. ``category_shortfall`` is
    ``max(0, min_categories - len(covered_categories))``; ``asset_shortfall`` is
    the count of unfilled ``(covered category, asset slot)`` positions against
    ``len(covered_categories) * assets_per_category`` after dedup.
    """

    run_id: str
    identities: tuple[PreflightIdentity, ...]
    covered_categories: tuple[str, ...]
    eligible_categories: tuple[str, ...]
    selected_category_count: int
    per_category_counts: tuple[tuple[str, int], ...]
    reduced_coverage: bool
    category_shortfall: int
    asset_shortfall: int


def _decode_body_text(body_text: str | bytes) -> str:
    """Return the response body as text, decoding bytes losslessly as UTF-8.

    The frozen Chunk 5 transport type declares ``GraphQLBatchResponse.body_text``
    as ``str``, and every existing caller passes ``str``. A caller-injected
    transport that hands over raw ``bytes`` (the form an HTTP client reads to)
    is decoded here rather than rejected: the adapter decodes the body with
    ``json.loads`` and hashes it as UTF-8, so both representations describe the
    same response. Decoding changes no value, and an undecodable body is left
    as-is so the adapter still classifies it as not-JSON rather than raising.
    """
    if isinstance(body_text, bytes):
        try:
            return body_text.decode("utf-8")
        except UnicodeDecodeError:
            return body_text.decode("utf-8", errors="replace")
    return body_text


def _safe_int(value: object, *, default: int = 0) -> int:
    """Return ``value`` when it is a real integer (never a ``bool``), else ``default``.

    ``default`` is a caller-supplied structural fallback for an envelope whose
    declared type is ``int`` (``GraphQLBatchResponse.http_status`` admits no
    null), not a fabricated measurement: it is never used where a missing value
    would be a measurement. The fallback is the caller's, so no coalesce at a
    call site has to write an ``or`` expression.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return value


def _ordered_members(category: Any) -> tuple[Any, ...]:
    """Return a category's members in their stable declared order.

    The stable order is the sampling member order the 4A engine emits and
    persists: ``(stratum_index, stratum_start_ordinal,
    sample_rank_within_stratum)``, with the identity key as the final tie-break.
    Within one stratum the declared ordinal breaks the tie first, so the order
    never depends on the member tuple's incidental order. Note that
    ``sample_rank_within_stratum`` is itself assigned by the 4A engine: its
    ``select_stratum_members`` sorts candidates by
    ``(selection_digest, asset_identity_key)``, where ``selection_digest``
    digests ``rule_version + NUL + category + NUL + key``. The rank is therefore
    digest-derived and is **not** the discovery ordinal, so this order is not
    ascending identity order: the fixture ``records_for(("A1", "A2"))`` yields
    ``A2`` (rank 1) then ``A1`` (rank 2).
    """
    return tuple(
        sorted(
            category.members,
            key=lambda member: (
                member.stratum_index,
                member.stratum_start_ordinal,
                member.sample_rank_within_stratum,
                member.asset_identity_key,
            ),
        )
    )


def select_preflight_identities(
    run: RunSamplingResult, *, policy: PreflightPolicy
) -> PreflightSelection:
    """Deterministic preflight selection (LREQ-ID-010). Pure: no I/O, no clock.

    ``eligible_categories`` is every category with
    ``category.enriched_sample_count >= policy.assets_per_category`` in run order.
    ``covered_categories`` is the chosen subset: the first
    ``policy.min_categories`` eligible categories in run order when more exist;
    when fewer exist, all eligible categories are covered and ``reduced_coverage``
    is ``True``. Only covered categories contribute identities and
    ``per_category_counts`` entries, so that tuple's length equals
    ``len(covered_categories)``. From each covered category, the first
    ``policy.assets_per_category`` members in their stable declared member order
    (``stratum_index``, ``stratum_start_ordinal``,
    ``sample_rank_within_stratum``) are taken. The identity union dedups by
    ``asset_identity_key`` with first-seen order preserved, so overlap never
    increases the attempted count. A category with fewer than
    ``assets_per_category`` members contributes nothing and is never counted
    toward the per-category minimum. ``selected_category_count`` is
    ``len(covered_categories)``; ``category_shortfall`` is
    ``max(0, min_categories - selected_category_count)``; ``asset_shortfall`` is
    ``max(0, selected_category_count * assets_per_category - len(identities))``
    after dedup. An empty run yields ``identities == ()``,
    ``covered_categories == ()``, ``eligible_categories == ()``, and a positive
    ``category_shortfall``. ``min_categories < 1`` or ``assets_per_category < 1``
    raises ``ValueError``.
    """
    if policy.min_categories < 1:
        raise ValueError("min_categories must be at least 1")
    if policy.assets_per_category < 1:
        raise ValueError("assets_per_category must be at least 1")

    categorised = [
        category
        for category in run.categories
        if category.enriched_sample_count >= policy.assets_per_category
    ]
    chosen = categorised[: policy.min_categories]
    covered = tuple(category.category for category in chosen)
    eligible = tuple(category.category for category in categorised)

    seen: set[str] = set()
    identities: list[PreflightIdentity] = []
    per_category_counts: list[tuple[str, int]] = []
    for category in chosen:
        count = 0
        for member in _ordered_members(category)[: policy.assets_per_category]:
            key = member.asset_identity_key
            count += 1
            if key in seen:
                continue
            seen.add(key)
            identities.append(
                PreflightIdentity(
                    asset_identity_key=key,
                    preflight_rank=len(identities) + 1,
                    source_category=category.category,
                )
            )
        per_category_counts.append((category.category, count))

    selected_category_count = len(covered)
    target_identity_slots = selected_category_count * policy.assets_per_category
    return PreflightSelection(
        run_id=run.run_id,
        identities=tuple(identities),
        covered_categories=covered,
        eligible_categories=eligible,
        selected_category_count=selected_category_count,
        per_category_counts=tuple(per_category_counts),
        reduced_coverage=selected_category_count < policy.min_categories,
        category_shortfall=max(0, policy.min_categories - selected_category_count),
        asset_shortfall=max(0, target_identity_slots - len(identities)),
    )


@dataclass(frozen=True, slots=True)
class PreflightRates:
    """Rates over the unique-identity denominator (LREQ-ID-040).

    ``success_rate`` and ``conflict_rate`` are ``None`` iff
    ``attempted_unique_identities == 0``; they are never ``0.0`` for zero
    attempts. Values are unrounded ``float64``.
    """

    attempted_unique_identities: int
    successful_unique_identities: int
    conflicting_unique_identities: int
    other_failed_unique_identities: int
    success_rate: float | None
    conflict_rate: float | None


def compute_preflight_rates(
    selection: PreflightSelection,
    observations: Sequence["PreflightObservation"],
) -> PreflightRates:
    """Count unique identities, not category references (LREQ-ID-040).

    The denominator is exactly ``len(selection.identities)``. An observation
    whose ``asset_identity_key`` is not in the selection is ignored (it can never
    inflate a rate). ``successful`` requires ``identity_match is True`` and both
    operation statuses ``OperationStatus.SUCCESS``; ``conflicting`` requires
    ``identity_match is False``; ``other_failed`` is the remainder. An identity
    with no observation counts in ``attempted`` and in ``other_failed``; that
    branch is defensive only, because ``enrich_asset`` never raises and always
    yields a result (a ``TRANSPORT_FAILURE`` is ``other_failed``, still
    attempted). With zero attempted both rates are ``None``; an all-zero-numerator
    nonzero denominator gives ``0.0``. Pure.
    """
    selected_keys = tuple(
        identity.asset_identity_key for identity in selection.identities
    )
    selected = set(selected_keys)
    latest_by_key: dict[str, PreflightObservation] = {}
    for observation in observations:
        if observation.asset_identity_key in selected:
            latest_by_key[observation.asset_identity_key] = observation

    successful = 0
    conflicting = 0
    other_failed = 0
    for key in selected_keys:
        observed = latest_by_key.get(key)
        if observed is None:
            other_failed += 1
            continue
        if observed.is_both_operations_success and observed.identity_match is True:
            successful += 1
        elif observed.identity_match is False:
            conflicting += 1
        else:
            other_failed += 1

    attempted = len(selected_keys)
    success_rate = (successful / attempted) if attempted > 0 else None
    conflict_rate = (conflicting / attempted) if attempted > 0 else None
    return PreflightRates(
        attempted_unique_identities=attempted,
        successful_unique_identities=successful,
        conflicting_unique_identities=conflicting,
        other_failed_unique_identities=other_failed,
        success_rate=success_rate,
        conflict_rate=conflict_rate,
    )


# --------------------------------------------------------------------------
# 5.3 Gate and orchestration
# --------------------------------------------------------------------------


def evaluate_preflight_gate(
    rates: PreflightRates, *, policy: PreflightPolicy
) -> IdentityPreflightStatus:
    """Return the gate disposition (LREQ-ID-040). Pure.

    ``attempted_unique_identities == 0`` -> ``INSUFFICIENT`` (checked first,
    before any threshold comparison, so zero attempts is never
    ``FAILED``/``PASSED``). Otherwise ``FAILED`` iff
    ``conflict_rate > policy.max_conflict_rate`` or
    ``success_rate < policy.min_success_rate``; else ``PASSED``. Boundary: a
    success rate exactly equal to ``min_success_rate`` passes; a conflict rate
    exactly equal to ``max_conflict_rate`` does not by itself fail.
    """
    if rates.attempted_unique_identities == 0:
        return IdentityPreflightStatus.INSUFFICIENT
    if (
        rates.conflict_rate is not None
        and rates.conflict_rate > policy.max_conflict_rate
    ):
        return IdentityPreflightStatus.FAILED
    if rates.success_rate is not None and rates.success_rate < policy.min_success_rate:
        return IdentityPreflightStatus.FAILED
    return IdentityPreflightStatus.PASSED


def bulk_enrichment_allowed(status: str) -> bool:
    """``True`` iff ``status == IdentityPreflightStatus.PASSED.value``. Pure.

    Chunk 6B MUST call this (or consume the returned status) before any bulk
    enrichment; ``insufficient`` and ``failed`` both return ``False``.
    """
    return status == IdentityPreflightStatus.PASSED.value


@dataclass(frozen=True, slots=True)
class PreflightObservation:
    """The persisted per-identity preflight outcome (one per attempted identity).

    Distinct operation outcomes are preserved (never collapsed): one failed
    operation does not hide the other's success.

    ``draft`` is the Chunk 5 ``EnrichmentObservationDraft`` for this identity; it
    is the **only** object from which an ``EnrichmentObservationRecord`` may be
    made (``draft.to_record(run_id)``). ``request_metadata_json`` and
    ``retrieved_at_utc`` are read from ``draft`` and are never re-constructed
    here.
    """

    asset_identity_key: str
    draft: EnrichmentObservationDraft
    product_detail_status: str
    page_views_status: str
    is_both_operations_success: bool
    identity_match: bool | None
    correlation_mode: str
    mapping_rule_version: str
    endpoint_signature: str
    diagnostic_summary_json: str | None


def _request_metadata_for(draft: Any) -> str | None:
    """Return the draft's request-metadata JSON string when it is readable."""
    value = getattr(draft, "request_metadata_json", None)
    return value if isinstance(value, str) else None


def graphql_endpoint_signature(
    endpoint: str = GRAPHQL_BATCH_ENDPOINT,
    *,
    endpoint_contract_version: str = ENDPOINT_CONTRACT_VERSION,
) -> str:
    """Build the persisted endpoint signature (LREQ-ID-040 line 388).

    Returns ``f"{endpoint}#{endpoint_contract_version}"`` — frozen literal form,
    e.g. ``https://assetstore.unity.com/api/graphql/batch#1.0.0``. The ``#``
    separator is an assumption, not SRS text. It is derived only from the Chunk 5
    ``GRAPHQL_BATCH_ENDPOINT`` and the models ``ENDPOINT_CONTRACT_VERSION``; no
    new endpoint string, version string, or field name is invented. Never
    contains a credential, header value, cookie, or body.
    """
    return f"{endpoint}#{endpoint_contract_version}"


def _endpoint_signature_for_draft(draft: Any) -> str:
    """Return the endpoint signature of the exchange a preflight draft recorded.

    The Chunk 5 draft's ``request_metadata_json`` carries the ``endpoint`` and
    ``endpoint_contract_version`` of the request that actually ran. A present,
    non-empty string is used; otherwise the operands fall back to the Chunk 5
    ``GRAPHQL_BATCH_ENDPOINT`` and the models ``ENDPOINT_CONTRACT_VERSION``. The
    value is built by :func:`graphql_endpoint_signature`, so it never contains a
    credential, header value, cookie, or body.
    """
    recorded: Mapping[str, Any] = {}
    metadata_json = _request_metadata_for(draft)
    if metadata_json is not None:
        try:
            decoded = json.loads(metadata_json)
        except ValueError:
            decoded = None
        if isinstance(decoded, Mapping):
            recorded = decoded

    candidate_endpoint = recorded.get("endpoint")
    resolved_endpoint = (
        candidate_endpoint
        if isinstance(candidate_endpoint, str) and candidate_endpoint
        else GRAPHQL_BATCH_ENDPOINT
    )
    candidate_version = recorded.get("endpoint_contract_version")
    resolved_version = (
        candidate_version
        if isinstance(candidate_version, str) and candidate_version
        else ENDPOINT_CONTRACT_VERSION
    )
    return graphql_endpoint_signature(
        resolved_endpoint, endpoint_contract_version=resolved_version
    )


def _identity_comparison_match(result: Any) -> bool | None:
    """Return ``True``/``False`` when the identity was comparable, else ``None``.

    The adapter performs the identity comparison while validating the
    ``ProductDetail`` payload and carries it on the validated fields. A detail
    operation that did not succeed yields ``None``: the identity could not be
    compared, and an uncomparable identity is never recorded as a match.
    """
    detail = result.product_detail
    if getattr(detail, "is_success", False):
        comparison = getattr(detail, "identity_comparison", None)
        if comparison is None:
            payload = getattr(detail, "payload", None)
            if isinstance(payload, Mapping):
                annotated = payload.get("_annotated_fields")
                comparison = getattr(annotated, "identity_comparison", None)
        if comparison is not None:
            return bool(getattr(comparison, "matches_requested_identity", False))
        return None
    # No usable detail payload, so the aliases cannot be compared here. The
    # adapter's own draft carries the comparison outcome for the identity; a
    # draft is never treated as an agreement without a comparison.
    return None


def _correlation_mode_is_valid(result: Any) -> bool:
    """Return whether the result's correlation mode is a persisted-enum member.

    ``enrich_asset`` rewrites the correlation to the caller-requested mode, so
    this defensive check never fires for a live adapter result; it exists so an
    out-of-enum mode is an error rather than a silently accepted association.
    """
    mode = getattr(getattr(result, "correlation", None), "mode", None)
    value = getattr(mode, "value", mode)
    return value in _CORRELATION_MODE_VALUES


def _operation_diagnostic_issues(result: Any) -> tuple[Any, ...]:
    """Return the operation-level validation issues, excluding identity mismatch.

    The identity mismatch is carried by ``identity_match`` (which participates in
    the conflict rate) and is never added as a plain other-failed diagnostic, so
    a conflict is counted once.
    """
    issues: list[Any] = []
    for operation in (result.product_detail, result.page_views):
        members = getattr(operation, "issues", ()) or ()
        if not members:
            failure_class = getattr(operation, "failure_class", None)
            error_summary = getattr(operation, "error_summary", None)
            if failure_class is not None and error_summary is not None:
                grade = getattr(failure_class, "value", str(failure_class))
                issues.append(
                    ValidationIssue(
                        code=grade,
                        message=str(error_summary),
                        context={"operation": getattr(operation, "operation_name", "")},
                    )
                )
            continue
        issues.extend(
            issue
            for issue in members
            if getattr(issue, "code", "") != "graphql_id_mapping_mismatch"
        )
    return tuple(issues)


def _build_observation(
    result: Any,
    draft: Any,
    *,
    correlation_mode: GraphQLOperationCorrelationMode,
) -> PreflightObservation:
    """Build one preflight observation from a Chunk 5 result and its draft.

    No field is re-derived from the raw response: the draft is the sole source of
    the persisted record, and the two operation statuses mirror it. ``draft``
    may be the adapter's :class:`EnrichmentObservationDraft` (the production
    path) or an inert stand-in carrying the same members (fixture path); the
    persisted record is always produced by ``draft.to_record(run_id)``.
    """
    identity_match = _identity_comparison_match(result)
    detail_success = result.product_detail.status is OperationStatus.SUCCESS
    page_success = result.page_views.status is OperationStatus.SUCCESS
    both_success = detail_success and page_success

    issues = list(_operation_diagnostic_issues(result))
    if not _correlation_mode_is_valid(result):
        issues.append(
            ValidationIssue(
                code="operation_correlation_mode_invalid",
                message="the correlation mode is not a persisted-enum member",
                context={},
            )
        )
    diagnostic_summary_json = (
        summarize_validation_issues(tuple(issues)) if issues else None
    )

    return PreflightObservation(
        asset_identity_key=result.asset_identity_key,
        draft=draft,
        product_detail_status=draft.product_detail_status,
        page_views_status=draft.page_views_status,
        is_both_operations_success=both_success,
        identity_match=identity_match,
        correlation_mode=correlation_mode.value,
        mapping_rule_version=IDENTITY_MAPPING_RULE_VERSION,
        endpoint_signature=_endpoint_signature_for_draft(draft),
        diagnostic_summary_json=diagnostic_summary_json,
    )


# --------------------------------------------------------------------------
# 5.3 Summary and outcome
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class IdentityPreflightSummary:
    """The ``runs.identity_preflight_summary_json`` content (LREQ-ID-040)."""

    status: str
    attempted_unique_identities: int
    successful_unique_identities: int
    conflicting_unique_identities: int
    other_failed_unique_identities: int
    success_rate: float | None
    conflict_rate: float | None
    graphql_operation_correlation_mode: str
    graphql_endpoint_signature: str
    identity_mapping_rule_version: str
    selected_category_count: int
    eligible_category_count: int
    reduced_coverage: bool
    category_shortfall: int
    asset_shortfall: int
    diagnostic_summary_json: str | None

    def to_json(self) -> str:
        """Return the deterministic, key-sorted JSON for this summary.

        ``None`` serializes as ``null``; rates are unrounded ``float64``; no
        credential, header value, cookie, or response body is present.
        """
        return json.dumps(
            {
                "status": self.status,
                "attempted_unique_identities": self.attempted_unique_identities,
                "successful_unique_identities": self.successful_unique_identities,
                "conflicting_unique_identities": self.conflicting_unique_identities,
                "other_failed_unique_identities": self.other_failed_unique_identities,
                "success_rate": self.success_rate,
                "conflict_rate": self.conflict_rate,
                "graphql_operation_correlation_mode": (
                    self.graphql_operation_correlation_mode
                ),
                "graphql_endpoint_signature": self.graphql_endpoint_signature,
                "identity_mapping_rule_version": self.identity_mapping_rule_version,
                "selected_category_count": self.selected_category_count,
                "eligible_category_count": self.eligible_category_count,
                "reduced_coverage": self.reduced_coverage,
                "category_shortfall": self.category_shortfall,
                "asset_shortfall": self.asset_shortfall,
                "diagnostic_summary_json": self.diagnostic_summary_json,
            },
            sort_keys=True,
            separators=(",", ":"),
        )


def _summary_diagnostic(
    observations: Sequence[PreflightObservation],
) -> str | None:
    """Return the run-level redacted diagnostic summary, or ``None``.

    Only issue codes and counts are aggregated, never a response body. When no
    observation carries issues the summary is ``None``; a failed preflight with
    no diagnostic would otherwise be indistinguishable from a clean one.
    """
    summaries = [
        observation.diagnostic_summary_json
        for observation in observations
        if observation.diagnostic_summary_json is not None
    ]
    if not summaries:
        return None
    codes: set[str] = set()
    issue_count = 0
    for summary_json in summaries:
        try:
            parsed = json.loads(summary_json)
        except json.JSONDecodeError:
            continue
        issue_count += int(parsed.get("issue_count", 0))
        for code in parsed.get("codes", ()):  # type: ignore[union-attr]
            codes.add(str(code))
    return json.dumps(
        {
            "aggregate": True,
            "issue_count": issue_count,
            "codes": sorted(codes),
            "observed_identities": len(summaries),
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _build_summary(
    *,
    status: IdentityPreflightStatus,
    selection: PreflightSelection,
    rates: PreflightRates,
    correlation_mode: GraphQLOperationCorrelationMode,
    endpoint: str | None,
    observations: Sequence[PreflightObservation],
) -> IdentityPreflightSummary:
    """Assemble the frozen-key run-level summary for a preflight outcome."""
    endpoint_signature = (
        observations[0].endpoint_signature
        if observations
        else graphql_endpoint_signature(endpoint)
    )
    return IdentityPreflightSummary(
        status=status.value,
        attempted_unique_identities=rates.attempted_unique_identities,
        successful_unique_identities=rates.successful_unique_identities,
        conflicting_unique_identities=rates.conflicting_unique_identities,
        other_failed_unique_identities=rates.other_failed_unique_identities,
        success_rate=rates.success_rate,
        conflict_rate=rates.conflict_rate,
        graphql_operation_correlation_mode=correlation_mode.value,
        graphql_endpoint_signature=endpoint_signature,
        identity_mapping_rule_version=IDENTITY_MAPPING_RULE_VERSION,
        selected_category_count=selection.selected_category_count,
        eligible_category_count=len(selection.eligible_categories),
        reduced_coverage=selection.reduced_coverage,
        category_shortfall=selection.category_shortfall,
        asset_shortfall=selection.asset_shortfall,
        diagnostic_summary_json=_summary_diagnostic(observations),
    )


@dataclass(frozen=True, slots=True)
class IdentityPreflightOutcome:
    """The whole preflight result: status, plan, rates, summary, and observations."""

    status: IdentityPreflightStatus
    selection: PreflightSelection
    rates: PreflightRates
    summary: IdentityPreflightSummary
    observations: tuple[PreflightObservation, ...]


# --------------------------------------------------------------------------
# 5.4 Persistence surface
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PreflightPersistenceReport:
    """Counts actually written by :func:`persist_preflight`."""

    status: str
    observations_written: int
    members_marked_selected: int


def _observation_record(draft: Any, run_id: str) -> Any:
    """Return the persistable record for ``run_id`` from a preflight draft.

    ``draft.to_record(run_id)`` is the only conversion, so a failed operation's
    field stays ``None`` and no field is substituted. A draft that is a mapping
    stand-in rather than the adapter's dataclass is materialized onto the frozen
    Chunk 2 record type by field copy; ``to_record`` remains the path whenever
    the draft provides it.
    """
    to_record = getattr(draft, "to_record", None)
    if callable(to_record):
        return to_record(run_id)
    return EnrichmentObservationRecord(
        run_id=run_id,
        asset_identity_key=_draft_text(draft, "asset_identity_key"),
        product_detail_status=_draft_text(draft, "product_detail_status"),
        page_views_status=_draft_text(draft, "page_views_status"),
        graphql_id=_draft_optional_text(draft, "graphql_id"),
        product_id=_draft_optional_text(draft, "product_id"),
        rating_average=_draft_optional_float(draft, "rating_average"),
        rating_count=_draft_optional_int(draft, "rating_count"),
        review_count=_draft_optional_int(draft, "review_count"),
        first_published_date_utc=_draft_optional_datetime(
            draft, "first_published_date_utc"
        ),
        publisher_json=_draft_optional_text(draft, "publisher_json"),
        category_json=_draft_optional_text(draft, "category_json"),
        state=_draft_optional_text(draft, "state"),
        product_page_views=_draft_optional_int(draft, "product_page_views"),
        id_mapping_mismatch=bool(_draft_get(draft, "id_mapping_mismatch")),
        product_detail_error_summary=_draft_optional_text(
            draft, "product_detail_error_summary"
        ),
        page_views_error_summary=_draft_optional_text(
            draft, "page_views_error_summary"
        ),
        request_metadata_json=_draft_text(draft, "request_metadata_json"),
        retrieved_at_utc=_draft_required_datetime(draft, "retrieved_at_utc"),
    )


def _draft_get(draft: Any, member: str) -> Any:
    """Return one draft member by attribute or mapping key, else ``None``."""
    if isinstance(draft, Mapping):
        return draft.get(member)
    return getattr(draft, member, None)


def _draft_text(draft: Any, member: str) -> str:
    """Return a required draft member as ``str`` without fabricating a value."""
    value = _draft_get(draft, member)
    if not isinstance(value, str):
        raise ValueError(f"preflight draft member {member!r} must be a string")
    return value


def _draft_optional_text(draft: Any, member: str) -> str | None:
    """Return an optional textual draft member, or ``None`` when it is unusable."""
    value = _draft_get(draft, member)
    return value if isinstance(value, str) else None


def _draft_optional_int(draft: Any, member: str) -> int | None:
    """Return an optional integer draft member, never substituting a zero."""
    return _safe_int(_draft_get(draft, member))


def _draft_optional_float(draft: Any, member: str) -> float | None:
    """Return an optional real-valued draft member, never substituting a zero."""
    value = _draft_get(draft, member)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _draft_optional_datetime(draft: Any, member: str) -> datetime | None:
    """Return an optional ``datetime`` draft member, or ``None`` when unusable."""
    value = _draft_get(draft, member)
    return value if isinstance(value, datetime) else None


def _draft_required_datetime(draft: Any, member: str) -> datetime:
    """Return a required ``datetime`` draft member without inventing a timestamp."""
    value = _draft_get(draft, member)
    if not isinstance(value, datetime):
        raise ValueError(f"preflight draft member {member!r} must be a datetime")
    return value


def persist_preflight(
    repository: SqliteRepository,
    *,
    run_id: str,
    status: str,
    summary: IdentityPreflightSummary,
    observations: Sequence[PreflightObservation],
    selected_identity_keys: Sequence[str],
) -> PreflightPersistenceReport:
    """Persist preflight artifacts before the gate returns (gate bullet line 723).

    Steps, in order:
      1. ``update_run_preflight`` with the status, the deterministic summary JSON,
         and the correlation mode.
      2. ``upsert_enrichment_observation(observation.draft.to_record(run_id))``
         for every observation, so a successful preflight response is already the
         corresponding enrichment observation and the ``(run_id,
         asset_identity_key)`` primary key prevents a second row in 6B. The record
         is built **only** from ``PreflightObservation.draft``.
      3. ``mark_preflight_selected`` to flip the sampling placeholders to ``True``.
      4. Non-clobbering page-view-semantics write: read the run via ``get_run``;
         iff the current ``page_view_semantics_status`` is neither
         ``validated_cumulative`` nor ``contradicted``, write ``unvalidated``.

    A row is written for every non-``insufficient`` attempt, including failures;
    zero-attempted (``insufficient``) writes zero observation rows, which is
    itself a persisted, readable state. Never writes a credential/header/body.
    Idempotent under ``upsert_enrichment_observation``.

    This function performs no transaction management of its own: the caller owns
    the atomicity boundary (``run_identity_preflight`` opens the single
    transaction that covers every write below).
    """
    repository.update_run_preflight(
        run_id,
        identity_preflight_status=status,
        identity_preflight_summary_json=summary.to_json(),
        graphql_operation_correlation_mode=summary.graphql_operation_correlation_mode,
    )

    keys = list(selected_identity_keys)
    if len(keys) != len(observations):
        # A sequence shorter or longer than ``keys`` is a defect in the caller;
        # the zip must not silently drop or fabricate an attempted identity.
        raise ValueError(
            "observations must align one-to-one with selected_identity_keys"
        )

    written = 0
    for asset_identity_key, observation in zip(keys, observations, strict=True):
        repository.upsert_enrichment_observation(
            _observation_record(observation.draft, run_id)
        )
        written += 1

    members_marked_selected = repository.mark_preflight_selected(run_id, keys)

    record = repository.get_run(run_id)
    current = getattr(record, "page_view_semantics_status", None)
    if current not in (
        PageViewSemanticsStatus.VALIDATED_CUMULATIVE.value,
        PageViewSemanticsStatus.CONTRADICTED.value,
    ):
        repository.update_run_preflight(
            run_id,
            page_view_semantics_status=PageViewSemanticsStatus.UNVALIDATED.value,
        )

    return PreflightPersistenceReport(
        status=status,
        observations_written=written,
        members_marked_selected=members_marked_selected,
    )


# --------------------------------------------------------------------------
# 5.3 Orchestration
# --------------------------------------------------------------------------


def _run_adapter(
    asset_identity_key: str,
    *,
    credentials: Credentials,
    transport: GraphQLTransport,
    correlation_mode: GraphQLOperationCorrelationMode,
    retrieved_at_utc: datetime,
    policy: GraphQLRetryPolicy,
    endpoint: str,
    sleep: Callable[[float], None],
) -> tuple[Any, Any]:
    """Run the Chunk 5 adapter once for one identity, tolerating a bytes body.

    The adapter's request construction, correlation, response validation, and
    retry classification are all borrowed from Chunk 5; nothing here re-implements
    them. The only adaptation is the transport envelope: the frozen transport
    type is ``GraphQLBatchResponse`` with ``body_text: str``, while a
    caller-injected transport may hand over the raw bytes an HTTP client reads.
    This wrapper decodes such a response to the declared type and otherwise calls
    the adapter unchanged. The injected ``sleep`` is passed through unchanged to
    ``enrich_asset`` per the Chunk 5 contract (``execute_graphql_batch`` sleeps the
    return of ``retry_delay_seconds`` through that seam), so a caller that wants a
    short retry path supplies its own bounded sleeper rather than having this
    module override the seam.
    """

    def _transport(request: Any, headers: Mapping[str, str]) -> GraphQLBatchResponse:
        response = transport(request, headers)
        body_text = _decode_body_text(getattr(response, "body_text", ""))
        if getattr(response, "body_text", None) is body_text:
            return response
        header_names = tuple(
            str(name) for name in getattr(response, "header_names", ())
        )
        return GraphQLBatchResponse(
            http_status=_safe_int(getattr(response, "http_status", None)),
            body_text=body_text,
            header_names=header_names,
        )

    return enrich_asset(
        asset_identity_key,
        credentials=credentials,
        transport=_transport,
        correlation_mode=correlation_mode,
        retrieved_at_utc=retrieved_at_utc,
        policy=policy,
        endpoint=endpoint,
        sleep=sleep,
    )


def run_identity_preflight(
    repository: SqliteRepository,
    run: RunSamplingResult,
    *,
    credentials: Credentials,
    transport: GraphQLTransport,
    correlation_mode: GraphQLOperationCorrelationMode,
    retrieved_at_utc: datetime,
    policy: PreflightPolicy,
    endpoint: str = GRAPHQL_BATCH_ENDPOINT,
    retry_policy: GraphQLRetryPolicy = GraphQLRetryPolicy(),
    sleep: Callable[[float], None] = time.sleep,
) -> IdentityPreflightOutcome:
    """Plan, execute, persist, and gate the identity preflight (LREQ-ID-010/020/040).

    Order of operations, all in this call:
      1. Deterministic selection from ``run`` and ``policy``.
      2. One ``enrich_asset`` call per unique identity, in selection order; a
         failed operation never aborts the loop.
      3. Unique-identity rates.
      4. Gate disposition.
      5. Persist status + summary + observations + ``preflight_selected`` flags
         **before returning**.
      6. Non-clobbering ``page_view_semantics_status`` write.
      7. On ``FAILED``, mark the run failed with ``completed_at_utc`` omitted; on
         ``INSUFFICIENT``, no status transition here.

    The function performs no bulk enrichment and issues no request beyond one
    ``enrich_asset`` call per unique preflight identity. ``retrieved_at_utc`` is
    caller-supplied; this module reads no clock. ``transport`` is caller-injected.

    The run row, the summary, every observation, the selection flags, and the
    ``failed`` transition commit as one transaction, so a crash can never leave a
    run marked before its evidence is readable.
    """
    selection = select_preflight_identities(run, policy=policy)

    observations: list[PreflightObservation] = []
    for identity in selection.identities:
        result, draft = _run_adapter(
            identity.asset_identity_key,
            credentials=credentials,
            transport=transport,
            correlation_mode=correlation_mode,
            retrieved_at_utc=retrieved_at_utc,
            policy=retry_policy,
            endpoint=endpoint,
            sleep=sleep,
        )
        observations.append(
            _build_observation(
                result,
                draft,
                correlation_mode=correlation_mode,
            )
        )

    rates = compute_preflight_rates(selection, observations)
    status = evaluate_preflight_gate(rates, policy=policy)
    summary = _build_summary(
        status=status,
        selection=selection,
        rates=rates,
        correlation_mode=correlation_mode,
        endpoint=endpoint,
        observations=observations,
    )

    with repository.transaction():
        persist_preflight(
            repository,
            run_id=run.run_id,
            status=status.value,
            summary=summary,
            observations=observations,
            selected_identity_keys=[
                identity.asset_identity_key for identity in selection.identities
            ],
        )

        if status is IdentityPreflightStatus.FAILED:
            repository.update_run_status(run.run_id, RunStatus.FAILED.value)

    return IdentityPreflightOutcome(
        status=status,
        selection=selection,
        rates=rates,
        summary=summary,
        observations=tuple(observations),
    )


# --------------------------------------------------------------------------
# 6B §5.1 Unique-identity union and reuse plan
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EnrichmentUnionMember:
    """One unique sampled identity in the run-wide union.

    ``union_rank`` is the 1-based position in the deterministic union order.
    ``source_categories`` are every category whose sample references the identity,
    in ``RunSamplingResult.categories`` order; ``first_category`` is its first
    element. ``reused_from_preflight`` is ``True`` iff a persisted
    ``enrichment_observations`` row for ``(run_id, asset_identity_key)`` already
    existed when the plan was built (the 6A preflight write).
    """

    asset_identity_key: str
    union_rank: int
    source_categories: tuple[str, ...]
    first_category: str
    reused_from_preflight: bool


@dataclass(frozen=True, slots=True)
class EnrichmentUnion:
    """The run-wide unique sampled-identity union (LREQ-GQL-080).

    ``members`` are unique by ``asset_identity_key``, in
    ``(category order, member order)`` first-seen order. ``reuse_keys`` are the
    members already enriched by the preflight; ``pending_keys`` are the
    remainder, and ``reuse_keys + pending_keys`` partitions ``members`` with no
    overlap. ``category_reference_count`` is the total number of
    ``(category, identity)`` references and is never the execution count.
    """

    run_id: str
    members: tuple[EnrichmentUnionMember, ...]
    reuse_keys: tuple[str, ...]
    pending_keys: tuple[str, ...]
    category_reference_count: int


def _member_order_key(member: Any) -> tuple[int, int, str]:
    """Total member order: ``(stratum_index, sample_rank, identity key)``.

    The first two components are the plan's declared ``(stratum_index,
    sample_rank_within_stratum)`` order; the identity key is the final tie-break
    so the order never depends on the member tuple's incidental order.
    """
    return (
        member.stratum_index,
        member.sample_rank_within_stratum,
        member.asset_identity_key,
    )


def compute_enrichment_union(
    run: RunSamplingResult,
    *,
    already_enriched_keys: AbstractSet[str],
) -> EnrichmentUnion:
    """Build the deterministic union and split reuse from pending (LREQ-GQL-080).

    Pure: no I/O, no clock. Iterates ``run.categories`` in order and each
    category's ``members`` in ``(stratum_index, sample_rank_within_stratum)``
    order, deduplicating by ``asset_identity_key`` on first sight. An identity
    referenced by k categories appears once and carries all k in
    ``source_categories``; it never inflates the execution count.
    ``already_enriched_keys`` is supplied by the caller (or a mapping stand-in)
    from the persisted ``enrichment_observations`` rows; a key in it is a reuse
    and is excluded from ``pending_keys``. An empty run yields ``members == ()``,
    both key tuples empty, and ``category_reference_count == 0``.
    """
    order: list[str] = []
    index_by_key: dict[str, int] = {}
    source_categories: list[list[str]] = []
    category_reference_count = 0

    for category in run.categories:
        seen_in_category: set[str] = set()
        for member in sorted(category.members, key=_member_order_key):
            key = member.asset_identity_key
            if key in seen_in_category:
                continue
            seen_in_category.add(key)
            category_reference_count += 1

            position = index_by_key.get(key)
            if position is None:
                index_by_key[key] = len(order)
                order.append(key)
                source_categories.append([category.category])
            else:
                source_categories[position].append(category.category)

    members = tuple(
        EnrichmentUnionMember(
            asset_identity_key=key,
            union_rank=position + 1,
            source_categories=tuple(source_categories[position]),
            first_category=source_categories[position][0],
            reused_from_preflight=key in already_enriched_keys,
        )
        for position, key in enumerate(order)
    )
    reuse_keys = tuple(
        member.asset_identity_key for member in members if member.reused_from_preflight
    )
    pending_keys = tuple(
        member.asset_identity_key
        for member in members
        if not member.reused_from_preflight
    )
    return EnrichmentUnion(
        run_id=run.run_id,
        members=members,
        reuse_keys=reuse_keys,
        pending_keys=pending_keys,
        category_reference_count=category_reference_count,
    )


# --------------------------------------------------------------------------
# 6B §5.2 Pre-enrichment projection and logging
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EnrichmentProjection:
    """The LREQ-NFR-020 pre-enrichment projection.

    ``discovered_canonical_assets`` is the run-wide distinct canonical identity
    count; ``sampled_assets`` is the run-wide distinct sampled identity count;
    ``unique_enrichment_identities`` is ``len(union.members)``;
    ``reused_preflight_identities`` is ``len(union.reuse_keys)``;
    ``pending_enrichment_identities`` is ``len(union.pending_keys)``.
    ``projected_minimum_enrichment_seconds`` is a ``float`` minimum, computed
    from the pending request count and the caller-supplied per-request interval;
    it is ``0.0`` when there are no pending identities (a measured zero, not
    null). No field is ever ``None``.
    """

    discovered_canonical_assets: int
    sampled_assets: int
    unique_enrichment_identities: int
    reused_preflight_identities: int
    pending_enrichment_identities: int
    per_request_interval_seconds: float
    projected_minimum_enrichment_seconds: float


def _require_non_negative_count(value: object, *, label: str) -> int:
    """Return ``value`` as an ``int >= 0``, rejecting ``bool`` and non-``int``.

    Structural validation of a caller-supplied count, not a measurement: the
    count is never replaced with a default. Raises ``ValueError`` otherwise.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer >= 0")
    if value < 0:
        raise ValueError(f"{label} must be an integer >= 0")
    return value


def _require_non_negative_interval(value: object, *, label: str) -> float:
    """Return ``value`` as a finite ``float >= 0.0``, rejecting ``bool``.

    A real number (``int`` or ``float``) is accepted and returned as ``float``;
    ``bool``, a non-number, ``NaN``, ``inf``, or a negative value raises
    ``ValueError``. The interval is a caller-supplied policy input, never a
    literal invented here.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite float >= 0.0")
    interval = float(value)
    if not math.isfinite(interval) or interval < 0.0:
        raise ValueError(f"{label} must be a finite float >= 0.0")
    return interval


def build_enrichment_projection(
    union: EnrichmentUnion,
    *,
    discovered_canonical_assets: int,
    sampled_assets: int,
    per_request_interval_seconds: float,
) -> EnrichmentProjection:
    """Build the projection; pure arithmetic, no I/O and no clock.

    ``projected_minimum_enrichment_seconds`` is
    ``len(union.pending_keys) * per_request_interval_seconds``. The interval is
    a caller-supplied policy value, not a literal invented here; the production
    caller passes ``GraphQLRetryPolicy().min_request_interval_seconds``
    (``DEFAULT_MIN_REQUEST_INTERVAL_SECONDS``). Counts must be ``int >= 0``
    (``bool`` rejected) and the interval a finite ``float >= 0.0``; anything
    else raises ``ValueError``. The projection is a **minimum** lower bound and
    never a duration estimate: it ignores per-request latency, retries, and
    backoff.

    Edge contract: ``len(union.pending_keys) == 0`` yields
    ``projected_minimum_enrichment_seconds == 0.0`` for any interval, including
    ``0.0`` (a measured zero, never ``None``). ``unique_enrichment_identities ==
    len(union.reuse_keys) + len(union.pending_keys)`` always holds.
    """
    canonical_count = _require_non_negative_count(
        discovered_canonical_assets, label="discovered_canonical_assets"
    )
    sampled_count = _require_non_negative_count(sampled_assets, label="sampled_assets")
    interval = _require_non_negative_interval(
        per_request_interval_seconds, label="per_request_interval_seconds"
    )

    pending_count = len(union.pending_keys)
    return EnrichmentProjection(
        discovered_canonical_assets=canonical_count,
        sampled_assets=sampled_count,
        unique_enrichment_identities=len(union.members),
        reused_preflight_identities=len(union.reuse_keys),
        pending_enrichment_identities=pending_count,
        per_request_interval_seconds=interval,
        projected_minimum_enrichment_seconds=pending_count * interval,
    )


def log_enrichment_projection(projection: EnrichmentProjection) -> None:
    """Emit the LREQ-NFR-020 pre-enrichment log line.

    Logs exactly the four SRS-named quantities (discovered canonical assets,
    sampled assets, unique enrichment identities, projected minimum enrichment
    time) plus the reuse/pending split. A single line at ``INFO``. The message
    contains only integers and a float: no credential, header value, cookie,
    response body, identity string, or category string (LREQ-SEC-010/020).
    Reads no clock; the caller invokes it before any bulk request is issued.
    """
    _LOGGER.info(
        "pre-enrichment projection: discovered_canonical_assets=%d "
        "sampled_assets=%d unique_enrichment_identities=%d "
        "reused_preflight_identities=%d pending_enrichment_identities=%d "
        "projected_minimum_enrichment_seconds=%s",
        projection.discovered_canonical_assets,
        projection.sampled_assets,
        projection.unique_enrichment_identities,
        projection.reused_preflight_identities,
        projection.pending_enrichment_identities,
        projection.projected_minimum_enrichment_seconds,
    )


# --------------------------------------------------------------------------
# 6B §5.3 Enrichment execution
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EnrichmentExecutionReport:
    """Outcome of one bulk-enrichment pass (LREQ-GQL-080, LREQ-NFR-030).

    ``executed_identity_count`` is the number of ``enrich_asset`` calls actually
    issued — at most ``len(union.pending_keys)``, and exactly one per pending
    identity. ``reused_identity_count`` is ``len(union.reuse_keys)`` and is the
    number of identities NOT requested again. ``persisted_identity_count`` is
    the distinct ``(run_id, asset_identity_key)`` rows in
    ``enrichment_observations`` after the pass, read back; it equals
    ``len(union.members)`` for a completed pass. ``failed_identity_count``
    counts the observations persisted by this pass with at least one non-
    ``success`` operation status and is an isolation count, never an abort
    reason.
    """

    run_id: str
    executed_identity_count: int
    reused_identity_count: int
    persisted_identity_count: int
    failed_identity_count: int


def _draft_operation_failed(draft: Any, member: str) -> bool:
    """Return whether a draft operation status is anything but ``success``.

    A missing, ``None``, or non-string status is not a success and counts as
    failed; no zero or fallback status is substituted.
    """
    return _draft_get(draft, member) != OperationStatus.SUCCESS.value


def enrich_unique_identities(
    repository: SqliteRepository,
    run: RunSamplingResult,
    *,
    preflight_status: str,
    credentials: Credentials,
    transport: GraphQLTransport,
    correlation_mode: GraphQLOperationCorrelationMode,
    retrieved_at_utc: datetime,
    union: EnrichmentUnion,
    projection: EnrichmentProjection,
    endpoint: str = GRAPHQL_BATCH_ENDPOINT,
    retry_policy: GraphQLRetryPolicy = GraphQLRetryPolicy(),
    sleep: Callable[[float], None] = time.sleep,
) -> EnrichmentExecutionReport:
    """Enrich the pending unique identities once each (LREQ-GQL-080/NFR-020/NFR-030).

    Order of operations:
      1. Gate check FIRST: if ``bulk_enrichment_allowed(preflight_status)`` is
         ``False``, issue **zero** requests, write nothing, and return a report
         with ``executed_identity_count``, ``persisted_identity_count``, and
         ``failed_identity_count`` all ``0`` — except ``reused_identity_count``,
         which reports ``len(union.reuse_keys)`` because the preflight rows
         already exist. This branch is a persisted, readable state, not an
         exception.
      2. Log the projection via :func:`log_enrichment_projection` before the
         first request.
      3. For each key in ``union.pending_keys``, in order, call ``_run_adapter``
         (the 6A helper over Chunk 5 ``enrich_asset``) exactly once, build the
         record from the returned draft, and ``upsert_enrichment_observation``
         inside one ``repository.transaction()``. A failed asset never aborts
         the loop (LREQ-NFR-030): ``enrich_asset`` never raises, and one
         identity's ``ERROR``/``TRANSPORT_FAILURE`` result is persisted as its
         own row.
      4. Read back ``count_distinct_enrichment_identities(run_id)`` for
         ``persisted_identity_count``.

    An identity in ``union.reuse_keys`` is never requested here; the 6A
    ``(run_id, asset_identity_key)`` primary key already holds its row and a
    second ``enrich_asset`` call for it would violate the at-most-once rule. The
    function never enriches an identity outside ``union.pending_keys`` and never
    issues a request when the gate is not ``passed``. ``retrieved_at_utc`` is
    caller-supplied; this module reads no clock. ``transport`` is caller-injected.
    """
    if not bulk_enrichment_allowed(preflight_status):
        return EnrichmentExecutionReport(
            run_id=run.run_id,
            executed_identity_count=0,
            reused_identity_count=len(union.reuse_keys),
            persisted_identity_count=0,
            failed_identity_count=0,
        )

    log_enrichment_projection(projection)

    executed_identity_count = 0
    failed_identity_count = 0
    with repository.transaction():
        for asset_identity_key in union.pending_keys:
            _result, draft = _run_adapter(
                asset_identity_key,
                credentials=credentials,
                transport=transport,
                correlation_mode=correlation_mode,
                retrieved_at_utc=retrieved_at_utc,
                policy=retry_policy,
                endpoint=endpoint,
                sleep=sleep,
            )
            repository.upsert_enrichment_observation(
                _observation_record(draft, run.run_id)
            )
            executed_identity_count += 1
            if _draft_operation_failed(draft, "product_detail_status") or (
                _draft_operation_failed(draft, "page_views_status")
            ):
                failed_identity_count += 1

    persisted_identity_count = repository.count_distinct_enrichment_identities(
        run.run_id
    )
    return EnrichmentExecutionReport(
        run_id=run.run_id,
        executed_identity_count=executed_identity_count,
        reused_identity_count=len(union.reuse_keys),
        persisted_identity_count=persisted_identity_count,
        failed_identity_count=failed_identity_count,
    )


# --------------------------------------------------------------------------
# 6B §5.4 Cutoff capture and post-enrichment finalization
# --------------------------------------------------------------------------


def capture_scoring_cutoff_utc(now_utc: datetime) -> datetime:
    """Normalize the caller's single post-enrichment timestamp (ruling C).

    Returns ``now_utc`` as a timezone-aware UTC ``datetime`` via
    ``models.ensure_utc``. A naive ``datetime`` raises ``ValueError``; an aware
    value in another offset is converted to UTC. This is the one named call site
    for the "captured once" invariant (SRS §3.2 step 10): the caller supplies the
    timestamp captured after enrichment and immediately before metric
    computation. Pure: it never reads the clock.
    """
    return ensure_utc(now_utc)


@dataclass(frozen=True, slots=True)
class StratumFinalization:
    """One stratum's finalized counts and status (LREQ-SMP-080)."""

    stratum_index: int
    N_h: int
    n_h: int
    u_demand_h: int
    u_recent_h: int
    u_quality_h: int
    usable_status: str
    eligibility_rule: str


def _metric_observation(record: EnrichmentObservationRecord) -> MetricObservation:
    """Project one persisted observation record onto Chunk 7B's metric input.

    Field copy only: a null stays null and is classified by Chunk 7A, never
    substituted with a zero (hard rule 2). ``product_detail_status`` and
    ``page_views_status`` are passed as the persisted strings; a string equal to
    the enum value compares equal in Chunk 7A.
    """
    return MetricObservation(
        product_page_views=record.product_page_views,
        first_published_date_utc=record.first_published_date_utc,
        state=record.state,
        id_mapping_mismatch=record.id_mapping_mismatch,
        rating_average=record.rating_average,
        rating_count=record.rating_count,
        product_detail_status=record.product_detail_status,
        page_views_status=record.page_views_status,
    )


def _component_eligibility_rule(
    usable: bool,
    first_reason: str | None,
    min_usable_samples_per_stratum: int,
) -> str:
    """One §5.6 eligibility field: ``usable:<min>`` or the first reason token.

    A usable component reports the inclusive minimum actually applied; an
    unusable one reports the first unavailable reason seen in
    ``(stratum_index, sample_rank)`` order, or ``METRIC_REASON_NULL`` when no
    observation carried a reason (including an empty stratum).
    """
    if usable:
        return f"usable:{min_usable_samples_per_stratum}"
    if first_reason is not None:
        return first_reason
    return METRIC_REASON_NULL


def finalize_stratum_counts(
    category: CategorySamplingResult,
    observations: Mapping[str, EnrichmentObservationRecord],
    *,
    scoring_cutoff_utc: datetime,
    page_view_semantics_status: PageViewSemanticsStatus,
    min_usable_samples_per_stratum: int = MIN_USABLE_SAMPLES_PER_STRATUM,
    min_age_days_for_rate: int = MIN_AGE_DAYS_FOR_RATE,
    recent_window_days: int = RECENT_WINDOW_DAYS,
) -> tuple[StratumFinalization, ...]:
    """Finalize one category's per-stratum usable counts (LREQ-SMP-080).

    For each ``SamplingStratum`` in ``category.strata`` (ascending
    ``stratum_index``), every sampled member is projected to a
    ``MetricObservation`` from its persisted ``EnrichmentObservationRecord`` and
    classified **only** by Chunk 7A:

      - ``u_demand_h`` counts observations whose
        ``age_normalized_page_view_index(...).value is not None``.
      - ``u_recent_h`` counts observations whose ``age_days_exact(...).value is
        not None``; the recent-window length does not enter this count.
      - ``u_quality_h`` counts observations whose
        ``quality_observation_eligibility(...).eligible`` is True.

    ``usable_status`` is ``"usable"`` iff ``stratum_is_usable`` accepts all
    three component counts, else ``"unavailable"``. ``eligibility_rule`` is the
    §5.6 token ``demand=<r>;recent=<r>;quality=<r>``. A missing observation for a
    sampled member is never zero: it raises ``ValueError`` naming the category
    only. ``category.strata == ()`` returns ``()``. Pure: no I/O, no clock.
    """
    members_by_stratum: dict[int, list[Any]] = {
        stratum.stratum_index: [] for stratum in category.strata
    }
    for member in category.members:
        members_by_stratum.setdefault(member.stratum_index, []).append(member)

    finalizations: list[StratumFinalization] = []
    for stratum in sorted(category.strata, key=lambda item: item.stratum_index):
        ranked_members = sorted(
            members_by_stratum[stratum.stratum_index],
            key=lambda item: item.sample_rank_within_stratum,
        )
        u_demand_h = 0
        u_recent_h = 0
        u_quality_h = 0
        demand_reason: str | None = None
        recent_reason: str | None = None
        quality_reason: str | None = None
        for member in ranked_members:
            key = member.asset_identity_key
            try:
                record = observations[key]
            except KeyError:
                raise ValueError(
                    f"missing enrichment observation for category {category.category!r}"
                ) from None
            observation = _metric_observation(record)

            index = age_normalized_page_view_index(
                observation.product_page_views,
                observation.first_published_date_utc,
                scoring_cutoff_utc=scoring_cutoff_utc,
                state=observation.state,
                id_mapping_mismatch=observation.id_mapping_mismatch,
                min_age_days_for_rate=min_age_days_for_rate,
            )
            if index.value is not None:
                u_demand_h += 1
            elif demand_reason is None:
                demand_reason = index.unavailable_reason

            age = age_days_exact(
                observation.first_published_date_utc,
                scoring_cutoff_utc=scoring_cutoff_utc,
            )
            if age.value is not None:
                u_recent_h += 1
            elif recent_reason is None:
                recent_reason = age.unavailable_reason

            quality = quality_observation_eligibility(
                product_detail_status=observation.product_detail_status,
                page_views_status=observation.page_views_status,
                id_mapping_mismatch=observation.id_mapping_mismatch,
                state=observation.state,
                rating_average=observation.rating_average,
                rating_count=observation.rating_count,
                page_view_semantics_status=page_view_semantics_status,
                product_page_views=observation.product_page_views,
                first_published_date_utc=observation.first_published_date_utc,
                scoring_cutoff_utc=scoring_cutoff_utc,
            )
            if quality.eligible:
                u_quality_h += 1
            elif quality_reason is None:
                quality_reason = quality.unavailable_reason

        demand_usable = stratum_is_usable(
            u_demand_h,
            min_usable_samples_per_stratum=min_usable_samples_per_stratum,
        )
        recent_usable = stratum_is_usable(
            u_recent_h,
            min_usable_samples_per_stratum=min_usable_samples_per_stratum,
        )
        quality_usable = stratum_is_usable(
            u_quality_h,
            min_usable_samples_per_stratum=min_usable_samples_per_stratum,
        )
        eligibility_rule = ";".join(
            (
                "demand="
                + _component_eligibility_rule(
                    demand_usable, demand_reason, min_usable_samples_per_stratum
                ),
                "recent="
                + _component_eligibility_rule(
                    recent_usable, recent_reason, min_usable_samples_per_stratum
                ),
                "quality="
                + _component_eligibility_rule(
                    quality_usable, quality_reason, min_usable_samples_per_stratum
                ),
            )
        )
        finalizations.append(
            StratumFinalization(
                stratum_index=stratum.stratum_index,
                N_h=stratum.population_count,
                n_h=stratum.selected_count,
                u_demand_h=u_demand_h,
                u_recent_h=u_recent_h,
                u_quality_h=u_quality_h,
                usable_status=(
                    "usable"
                    if demand_usable and recent_usable and quality_usable
                    else "unavailable"
                ),
                eligibility_rule=eligibility_rule,
            )
        )
    return tuple(finalizations)


@dataclass(frozen=True, slots=True)
class CategoryFinalization:
    """One category's finalized counts and per-stratum records (LREQ-SMP-080).

    ``usable_demand_sample_count``, ``usable_recent_supply_sample_count``, and
    ``usable_quality_sample_count`` are the sums of the corresponding ``u_*_h``
    over strata the applicable ``stratum_is_usable`` call accepts; they equal
    ``CategoryRawMetrics.usable_*_sample_count`` from Chunk 7B (asserted in the
    later §5.5 consistency assertion). ``unique_enrichment_count`` is the
    run-wide distinct enriched identity count and is identical on every row
    (SRS-lean:614-616). ``stratum_statistics_json`` is the finalized ten-key
    payload; it is never the 4B pending payload.
    """

    category: str
    strata: tuple[StratumFinalization, ...]
    usable_demand_sample_count: int
    usable_recent_supply_sample_count: int
    usable_quality_sample_count: int
    unique_enrichment_count: int
    stratum_statistics_json: str


@dataclass(frozen=True, slots=True)
class FinalizationReport:
    """The finished persistence pass over every category (LREQ-SMP-080).

    ``mismatches`` is empty when the write was consistent; a non-empty tuple
    names the category and column only and is never a fabricated ``0``. An empty
    union yields ``categories == ()``, ``category_rows_written == 0``, and
    ``mismatches == ()``.
    """

    run_id: str
    scoring_cutoff_utc: datetime
    categories: tuple[CategoryFinalization, ...]
    category_rows_written: int
    mismatches: tuple[str, ...]


def _membership_mismatches(
    category: CategorySamplingResult, members: Sequence[Any]
) -> tuple[str, ...]:
    """Return one mismatch string per persisted-membership disagreement.

    Strings name the category and column only, never an identity. Checked: the
    persisted identity key set against ``category.members``; each stratum's
    persisted member count against ``stratum.selected_count``; and the persisted
    row count against ``category.enriched_sample_count``.
    """
    label = f"category {category.category!r}: "
    messages: list[str] = []
    expected_keys = {member.asset_identity_key for member in category.members}
    observed_keys = {member.asset_identity_key for member in members}
    if observed_keys != expected_keys:
        messages.append(label + "sample_members.asset_identity_key")
    counts_by_stratum: dict[int, int] = {}
    for member in members:
        index = member.stratum_index
        counts_by_stratum[index] = counts_by_stratum.get(index, 0) + 1
    for stratum in category.strata:
        if counts_by_stratum.get(stratum.stratum_index, 0) != stratum.selected_count:
            messages.append(label + "sample_members.n_h")
            break
    if len(members) != category.enriched_sample_count:
        messages.append(label + "sample_members.row_count")
    return tuple(messages)


def _finalized_stratum_statistics_json(
    persisted_json: str,
    finalizations: tuple[StratumFinalization, ...],
) -> str | None:
    """Re-serialize the persisted 4B payload with the finalized five fields.

    Returns ``None`` when the persisted payload is unreadable or its stratum
    indices disagree with ``finalizations``. Otherwise ``json.dumps(...,
    sort_keys=True, separators=(",", ":"))`` is applied after replacing only
    ``u_demand_h``, ``u_recent_h``, ``u_quality_h``, ``usable_status``, and
    ``eligibility_rule``; every ``N_h``/``n_h``/ordinal value is copied from the
    stored JSON and re-emitted byte-for-byte. ``serialize_stratum_statistics`` is
    deliberately not used because it re-emits the ``pending`` status.
    """
    try:
        parsed = parse_stratum_statistics(persisted_json)
    except DatabaseError:
        return None
    by_index = {final.stratum_index: final for final in finalizations}
    parsed_indices = {
        entry.get("stratum_index")
        for entry in parsed  # type: ignore[union-attr]
    }
    if parsed_indices != set(by_index) or len(parsed) != len(by_index):
        return None
    payload: list[dict[str, object]] = []
    for entry in parsed:
        final = by_index[entry["stratum_index"]]  # type: ignore[index]
        updated = dict(entry)
        updated["u_demand_h"] = final.u_demand_h
        updated["u_recent_h"] = final.u_recent_h
        updated["u_quality_h"] = final.u_quality_h
        updated["usable_status"] = final.usable_status
        updated["eligibility_rule"] = final.eligibility_rule
        payload.append(updated)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def finalize_enrichment(
    repository: SqliteRepository,
    run: RunSamplingResult,
    *,
    scoring_cutoff_utc: datetime,
    computed_at_utc: datetime,
    page_view_semantics_status: PageViewSemanticsStatus,
    union: EnrichmentUnion,
) -> FinalizationReport:
    """Finalize and persist the authoritative sample summaries (LREQ-SMP-080).

    Order of operations:
      1. For each category in ``run.categories`` order, read its persisted
         ``sample_members`` and the persisted ``enrichment_observations`` for
         each member key; build the per-stratum finalization and the three
         category-level sums over strata the applicable ``stratum_is_usable``
         call accepts.
      2. Re-serialize ``stratum_statistics_json`` from the persisted 4B payload
         plus the finalized fields (see :func:`_finalized_stratum_statistics_json`).
      3. Write each ``(run_id, category)`` row through ``upsert_category_scores``
         with a full ``CategoryScoreRecord``: the discovery/sampling columns are
         carried forward unchanged from the persisted row, the four finalized
         counts and the finalized ``stratum_statistics_json`` are written, and
         the scoring-phase columns stay at their stored pre-scoring values
         (§5.7 carry-forward).
      4. After the write transaction, run
         :func:`assert_finalization_consistency` over the persisted rows (the
         §5.5 consistency assertion) and merge its result into ``mismatches``:
         the read-phase strings from steps 1-3 first, then the assertion's
         strings, in order, with duplicates removed. The returned ``mismatches``
         is therefore the union of the read-phase checks and the §5.5 assertion,
         and is empty only when both agree -- it is never a fabricated ``0``.

    ``unique_enrichment_count`` is the run-wide distinct enriched identity count
    read back from ``enrichment_observations`` and is identical on every category
    row. A category whose persisted membership disagrees with ``category.strata``
    does not raise: the discrepancy is recorded as a ``mismatches`` string naming
    the category and column only, and the other categories still finalize
    (E10/E11). ``computed_at_utc`` is caller-supplied; this module reads no clock.
    Idempotent: re-running over the same observations yields byte-identical
    ``stratum_statistics_json`` and identical counts. ``union.members == ()``
    yields ``categories == ()``, ``category_rows_written == 0``, and
    ``mismatches == ()``.
    """
    if not union.members:
        return FinalizationReport(
            run_id=run.run_id,
            scoring_cutoff_utc=scoring_cutoff_utc,
            categories=(),
            category_rows_written=0,
            mismatches=(),
        )

    unique_enrichment_count = repository.count_distinct_enrichment_identities(
        run.run_id
    )
    persisted_by_category = {
        row.category: row for row in repository.get_category_scores(run.run_id)
    }

    finalizations: list[CategoryFinalization] = []
    mismatches: list[str] = []
    rows_to_write: list[CategoryScoreRecord] = []

    for category in run.categories:
        persisted_row = persisted_by_category.get(category.category)
        if persisted_row is None:
            mismatches.append(f"category {category.category!r}: category_scores")
            continue

        persisted_members = repository.get_sample_members(run.run_id, category.category)
        membership_issues = _membership_mismatches(category, persisted_members)
        if membership_issues:
            mismatches.extend(membership_issues)
            continue

        observations: dict[str, EnrichmentObservationRecord] = {}
        missing_observation = False
        seen_keys: set[str] = set()
        for member in persisted_members:
            key = member.asset_identity_key
            if key in seen_keys:
                continue
            seen_keys.add(key)
            record = repository.get_enrichment_observation(run.run_id, key)
            if record is None:
                missing_observation = True
                break
            observations[key] = record
        if missing_observation:
            mismatches.append(
                f"category {category.category!r}: "
                "enrichment_observations.asset_identity_key"
            )
            continue

        stratum_finalizations = finalize_stratum_counts(
            category,
            observations,
            scoring_cutoff_utc=scoring_cutoff_utc,
            page_view_semantics_status=page_view_semantics_status,
        )

        stratum_statistics_json = _finalized_stratum_statistics_json(
            persisted_row.stratum_statistics_json, stratum_finalizations
        )
        if stratum_statistics_json is None:
            mismatches.append(
                f"category {category.category!r}: stratum_statistics_json"
            )
            continue

        usable_demand_sample_count = sum(
            final.u_demand_h
            for final in stratum_finalizations
            if stratum_is_usable(
                final.u_demand_h,
                min_usable_samples_per_stratum=MIN_USABLE_SAMPLES_PER_STRATUM,
            )
        )
        usable_recent_supply_sample_count = sum(
            final.u_recent_h
            for final in stratum_finalizations
            if stratum_is_usable(
                final.u_recent_h,
                min_usable_samples_per_stratum=MIN_USABLE_SAMPLES_PER_STRATUM,
            )
        )
        usable_quality_sample_count = sum(
            final.u_quality_h
            for final in stratum_finalizations
            if stratum_is_usable(
                final.u_quality_h,
                min_usable_samples_per_stratum=MIN_USABLE_SAMPLES_PER_STRATUM,
            )
        )

        rows_to_write.append(
            replace(
                persisted_row,
                unique_enrichment_count=unique_enrichment_count,
                usable_demand_sample_count=usable_demand_sample_count,
                usable_recent_supply_sample_count=usable_recent_supply_sample_count,
                usable_quality_sample_count=usable_quality_sample_count,
                stratum_statistics_json=stratum_statistics_json,
                computed_at_utc=computed_at_utc,
            )
        )
        finalizations.append(
            CategoryFinalization(
                category=category.category,
                strata=stratum_finalizations,
                usable_demand_sample_count=usable_demand_sample_count,
                usable_recent_supply_sample_count=usable_recent_supply_sample_count,
                usable_quality_sample_count=usable_quality_sample_count,
                unique_enrichment_count=unique_enrichment_count,
                stratum_statistics_json=stratum_statistics_json,
            )
        )

    with repository.transaction():
        category_rows_written = repository.upsert_category_scores(rows_to_write)

    report = FinalizationReport(
        run_id=run.run_id,
        scoring_cutoff_utc=scoring_cutoff_utc,
        categories=tuple(finalizations),
        category_rows_written=category_rows_written,
        mismatches=tuple(mismatches),
    )
    consistency_mismatches = assert_finalization_consistency(
        repository,
        run,
        report,
        scoring_cutoff_utc=scoring_cutoff_utc,
        page_view_semantics_status=page_view_semantics_status,
    )
    merged: list[str] = list(report.mismatches)
    for message in consistency_mismatches:
        if message not in merged:
            merged.append(message)
    return replace(report, mismatches=tuple(merged))


def _consistency_mismatches_for_category(
    repository: SqliteRepository,
    run: RunSamplingResult,
    category: CategorySamplingResult,
    finalized: CategoryFinalization,
    *,
    scoring_cutoff_utc: datetime,
    page_view_semantics_status: PageViewSemanticsStatus,
    persisted_row: CategoryScoreRecord,
) -> tuple[str, ...]:
    """Checks A–D for one finalized category (plan §5.5).

    Returns one mismatch string per violation, naming the category and column
    only. A missing persisted row or unreadable stratum payload is itself a
    violation and the remaining reads are skipped; every other check accumulates.
    The three 7B usable counts are compared with exact ``int`` equality, never a
    tolerance.
    """
    label = f"category {category.category!r}: "
    messages: list[str] = []

    # A. Per-component sums equal the finalized category-level counts. Each
    # component sums ``u_*_h`` over only the strata ``stratum_is_usable`` accepts
    # for that component, exactly as ``finalize_enrichment`` computes the
    # category-level counts (SRS §6.5; plan §12 A3).
    if (
        sum(
            final.u_demand_h
            for final in finalized.strata
            if stratum_is_usable(
                final.u_demand_h,
                min_usable_samples_per_stratum=MIN_USABLE_SAMPLES_PER_STRATUM,
            )
        )
        != finalized.usable_demand_sample_count
    ):
        messages.append(label + "usable_demand_sample_count")
    if (
        sum(
            final.u_recent_h
            for final in finalized.strata
            if stratum_is_usable(
                final.u_recent_h,
                min_usable_samples_per_stratum=MIN_USABLE_SAMPLES_PER_STRATUM,
            )
        )
        != finalized.usable_recent_supply_sample_count
    ):
        messages.append(label + "usable_recent_supply_sample_count")
    if (
        sum(
            final.u_quality_h
            for final in finalized.strata
            if stratum_is_usable(
                final.u_quality_h,
                min_usable_samples_per_stratum=MIN_USABLE_SAMPLES_PER_STRATUM,
            )
        )
        != finalized.usable_quality_sample_count
    ):
        messages.append(label + "usable_quality_sample_count")

    persisted_members = repository.get_sample_members(run.run_id, category.category)

    # D (first part). Distinct persisted member count equals enriched_sample_count.
    member_keys = [member.asset_identity_key for member in persisted_members]
    if len(set(member_keys)) != category.enriched_sample_count:
        messages.append(label + "sample_members.asset_identity_key")

    # D (second part). Every sampled member has an enrichment_observations row.
    observations: dict[str, EnrichmentObservationRecord] = {}
    missing_observation = False
    for key in dict.fromkeys(member_keys):
        record = repository.get_enrichment_observation(run.run_id, key)
        if record is None:
            missing_observation = True
            break
        observations[key] = record
    if missing_observation:
        messages.append(label + "enrichment_observations.asset_identity_key")
    else:
        # B. Chunk 7B agreement from the same persisted observations and cutoff.
        observations_by_stratum: dict[int, list[MetricObservation]] = {}
        for member in persisted_members:
            observations_by_stratum.setdefault(member.stratum_index, []).append(
                _metric_observation(observations[member.asset_identity_key])
            )
        strata_inputs: list[StratumMetricInput] = []
        for stratum in sorted(category.strata, key=lambda item: item.stratum_index):
            stratum_observations = observations_by_stratum.get(
                stratum.stratum_index, ()
            )
            if len(stratum_observations) != stratum.selected_count:
                messages.append(label + "sample_members.n_h")
                continue
            strata_inputs.append(
                StratumMetricInput(
                    stratum_index=stratum.stratum_index,
                    discovered_population_count=stratum.population_count,
                    sampled_population_count=stratum.selected_count,
                    observations=tuple(stratum_observations),
                )
            )
        if len(strata_inputs) == len(category.strata):
            try:
                raw_metrics = compute_category_raw_metrics(
                    CategoryMetricInput(
                        category=category.category,
                        scoring_cutoff_utc=scoring_cutoff_utc,
                        page_view_semantics_status=page_view_semantics_status,
                        strata=tuple(strata_inputs),
                    ),
                    BreadthMetricInput(
                        verified_total_count=None,
                        distinct_canonical_discovered_count=category.population.size,
                    ),
                )
            except ValueError:
                messages.append(label + "compute_category_raw_metrics")
            else:
                if (
                    raw_metrics.usable_demand_sample_count
                    != finalized.usable_demand_sample_count
                ):
                    messages.append(label + "usable_demand_sample_count")
                if (
                    raw_metrics.usable_recent_supply_sample_count
                    != finalized.usable_recent_supply_sample_count
                ):
                    messages.append(label + "usable_recent_supply_sample_count")
                if (
                    raw_metrics.usable_quality_sample_count
                    != finalized.usable_quality_sample_count
                ):
                    messages.append(label + "usable_quality_sample_count")

    # C. Persisted round trip of the per-stratum and category-level values.
    try:
        parsed = parse_stratum_statistics(persisted_row.stratum_statistics_json)
    except DatabaseError:
        messages.append(label + "stratum_statistics_json")
        return tuple(messages)
    if len(parsed) != len(finalized.strata):
        messages.append(label + "stratum_statistics_json")
    else:
        by_index = {entry["stratum_index"]: entry for entry in parsed}
        for final in sorted(finalized.strata, key=lambda item: item.stratum_index):
            entry = by_index.get(final.stratum_index)
            if entry is None:
                messages.append(label + "stratum_statistics_json")
                continue
            if entry.get("u_demand_h") != final.u_demand_h:
                messages.append(label + "u_demand_h")
            if entry.get("u_recent_h") != final.u_recent_h:
                messages.append(label + "u_recent_h")
            if entry.get("u_quality_h") != final.u_quality_h:
                messages.append(label + "u_quality_h")
            if entry.get("usable_status") != final.usable_status:
                messages.append(label + "usable_status")
            if entry.get("eligibility_rule") != final.eligibility_rule:
                messages.append(label + "eligibility_rule")

    if persisted_row.usable_demand_sample_count != finalized.usable_demand_sample_count:
        messages.append(label + "usable_demand_sample_count")
    if (
        persisted_row.usable_recent_supply_sample_count
        != finalized.usable_recent_supply_sample_count
    ):
        messages.append(label + "usable_recent_supply_sample_count")
    if persisted_row.usable_quality_sample_count != (
        finalized.usable_quality_sample_count
    ):
        messages.append(label + "usable_quality_sample_count")
    if persisted_row.unique_enrichment_count != finalized.unique_enrichment_count:
        messages.append(label + "unique_enrichment_count")

    # D (third part). No completed-run stratum payload retains a pending status.
    if any(entry.get("usable_status") == PENDING_USABLE_STATUS for entry in parsed):
        messages.append(label + "stratum_statistics_json")

    return tuple(messages)


def assert_finalization_consistency(
    repository: SqliteRepository,
    run: RunSamplingResult,
    finalization: FinalizationReport,
    *,
    scoring_cutoff_utc: datetime,
    page_view_semantics_status: PageViewSemanticsStatus,
) -> tuple[str, ...]:
    """The 6B-owned agreement check (gate bullet, dependency map line 763).

    Returns `()` when every check holds, otherwise one mismatch string per
    violation. Strings name the category and the column only — never an identity
    string or a secret. A drift never raises; the report carries the strings.
    Checks, in order:

      A. Per-component usable-strata sums: ``sum(u_demand_h)`` over the strata
         ``stratum_is_usable`` accepts for demand, and likewise for
         ``u_recent_h`` and ``u_quality_h``, equal the corresponding
         ``CategoryFinalization.usable_*_sample_count`` (SRS §6.5).
      B. 7B agreement: for each category, the Chunk 7B ``CategoryMetricInput`` /
         ``BreadthMetricInput`` are built from the same persisted observations
         and the same ``scoring_cutoff_utc``, ``compute_category_raw_metrics`` is
         called, and ``usable_demand_sample_count``,
         ``usable_recent_supply_sample_count``, and ``usable_quality_sample_count``
         must equal the finalized values exactly (``int`` equality, not a
         tolerance).
      C. Persisted round trip: ``category_scores`` is re-read and
         ``parse_stratum_statistics`` re-parses the stored payload; the stored
         per-stratum counts and statuses must equal ``finalization`` and the
         stored category-level counts must equal the finalized values.
      D. Coverage cross-check: the distinct ``sample_members`` identity count per
         category equals ``enriched_sample_count``; every sampled member has an
         ``enrichment_observations`` row; no ``stratum_statistics_json`` object
         retains ``usable_status == "pending"`` on a completed run.
      E. ``unique_enrichment_count`` equals the run-wide distinct enriched
         identity count and is identical on every category row.

    The function reads only; it persists nothing and reads no clock (the caller
    supplies ``scoring_cutoff_utc``, ruling C). It is deterministic and
    order-stable: categories are visited in ``run.categories`` order. Empty-union
    input yields ``()``.
    """
    if not finalization.categories:
        return ()
    if not run.categories:
        return ("category_scores",)

    mismatches: list[str] = []

    # E. Run-wide distinct enriched identity count, identical on every row.
    row_counts = {row.unique_enrichment_count for row in finalization.categories}
    expected_unique = repository.count_distinct_enrichment_identities(run.run_id)
    if row_counts != {expected_unique}:
        mismatches.append("category_scores.unique_enrichment_count")

    # A–D, per finalized category.
    finalized_by_category = {row.category: row for row in finalization.categories}
    persisted_by_category = {
        row.category: row for row in repository.get_category_scores(run.run_id)
    }
    for category in run.categories:
        finalized = finalized_by_category.get(category.category)
        if finalized is None:
            mismatches.append(f"category {category.category!r}: category_scores")
            continue
        persisted_row = persisted_by_category.get(category.category)
        if persisted_row is None:
            mismatches.append(f"category {category.category!r}: category_scores")
            continue
        mismatches.extend(
            _consistency_mismatches_for_category(
                repository,
                run,
                category,
                finalized,
                scoring_cutoff_utc=scoring_cutoff_utc,
                page_view_semantics_status=page_view_semantics_status,
                persisted_row=persisted_row,
            )
        )

    return tuple(mismatches)
