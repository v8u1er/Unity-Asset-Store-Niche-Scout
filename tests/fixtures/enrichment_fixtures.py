"""Inert fixtures and golden vectors for chunk 6B unique enrichment executor.

Data and construction helpers only: this module contains no assertions and no
logic under test, so a defect in it cannot mask a union, projection, execution,
or redaction defect.

Sources:

- ``Documents/SRS-lean.md`` §4.2 (``LREQ-GQL-080``) and §11 (``LREQ-NFR-020``/
  ``030``).
- ``Documents/plans/chunk-6B-unique-enrichment-executor-and-persistence.md`` §5.1
  (union/reuse), §5.2 (projection), §5.3 (execution), §9 (golden vectors).
- ``Documents/interfaces/chunk-4A.md`` (``RunSamplingResult``,
  ``CategorySamplingResult``, ``SamplingStratum``, ``SampledMember``),
  ``chunk-05.md`` (transport bodies), ``chunk-02.md``
  (``EnrichmentObservationRecord``).

No credential is real and none is stored: the credential literals are
non-secret fixture strings. No network, no clock read, no file I/O, no
``sqlite3``. Datetimes are fixed aware-UTC literals, never ``now()``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
from typing import Any

from fixtures.identity_preflight_vectors import (
    EXPLICIT_KEY,
    GQL_CREDENTIALS,
    REDACTION_CREDENTIALS,
    RETRIEVED_AT_UTC,
    SCORING_CUTOFF_UTC,
    seed_sampling_and_run,
    success_body,
)
from niche_scout import sampling
from niche_scout.database import EnrichmentObservationRecord
from niche_scout.models import DiscoveryStatus, OperationStatus, SamplingBasis

__all__ = [
    "CATEGORY_1",
    "CATEGORY_2",
    "CATEGORY_3",
    "CREDENTIAL_SENTINELS",
    "EnrichmentTransport",
    "EXPLICIT_KEY",
    "FINALIZATION_CATEGORY",
    "FINALIZATION_DATE_UTC",
    "FINALIZATION_ELIGIBILITY_RULE",
    "FINALIZATION_MEMBERS",
    "FINALIZATION_NAIVE_DATE_UTC",
    "FINALIZATION_POPULATION",
    "FINALIZATION_SAMPLE",
    "FINALIZATION_U_DEMAND",
    "FINALIZATION_U_QUALITY",
    "FINALIZATION_U_RECENT",
    "FINALIZATION_USABLE_STATUS",
    "FINALIZATION_ZERO_CATEGORY",
    "GQL_CREDENTIALS",
    "OVERLAP_CATEGORY_REFERENCE_COUNT",
    "OVERLAP_EXECUTED_CALLS",
    "OVERLAP_MEMBERS",
    "PENDING_KEYS",
    "PROJECTION_INTERVAL",
    "PROJECTION_MINIMUM_SECONDS",
    "PROJECTION_PENDING",
    "QUALITY_STRADDLE_CATEGORY",
    "QUALITY_STRADDLE_MEMBERS",
    "QUALITY_STRADDLE_POPULATION",
    "QUALITY_STRADDLE_RATING_COUNTS",
    "REDACTION_CREDENTIALS",
    "RETRIEVED_AT_UTC",
    "REUSE_EXECUTED_CALLS",
    "REUSE_KEYS",
    "RUN_ID",
    "SCORING_CUTOFF_UTC",
    "all_reused_keys",
    "category_result",
    "finalization_category",
    "finalization_observations",
    "finalization_run",
    "finalization_run_with_zero",
    "mixed_transport",
    "observation_record",
    "overlap_run",
    "persisted_finalization_observations",
    "quality_straddle_finalization_category",
    "quality_straddle_finalization_observations",
    "quality_straddle_finalization_run",
    "seed_finalization",
    "seed_quality_straddle_finalization",
    "seed_run",
    "success_bodies",
    "success_transport",
    "zero_population_category",
]

# Fixed aware-UTC timestamp; no clock is ever read (LREQ-ARCH-020).
RUN_ID = "run-6b"

CATEGORY_1 = "Category/One"
CATEGORY_2 = "Category/Two"
CATEGORY_3 = "Category/Three"

# --------------------------------------------------------------------------
# Golden vectors (plan §9; hand-derived, never read off the implementation).
# --------------------------------------------------------------------------

#: Overlap golden: identity A in categories 1 and 2, B in 2 and 3, C in 3.
OVERLAP_MEMBERS: tuple[str, ...] = ("A", "B", "C")
OVERLAP_CATEGORY_REFERENCE_COUNT = 5
OVERLAP_EXECUTED_CALLS = 3

#: Reuse golden: A already persisted by the preflight, so only B and C run.
REUSE_KEYS: tuple[str, ...] = ("A",)
PENDING_KEYS: tuple[str, ...] = ("B", "C")
REUSE_EXECUTED_CALLS = 2

#: Projection golden: two pending identities at a 0.5 s interval give 1.0 s.
PROJECTION_PENDING = 2
PROJECTION_INTERVAL = 0.5
PROJECTION_MINIMUM_SECONDS = 1.0

#: The flat sentinel list the redaction node scans the log line for.
CREDENTIAL_SENTINELS: tuple[str, ...] = (
    REDACTION_CREDENTIALS.coveo_token,
    REDACTION_CREDENTIALS.unity_csrf_token,
    "sessionid=fixture-cookie-value",
    "Bearer fixture-header-value",
    "fixture-response-body-marker",
)


# --------------------------------------------------------------------------
# Hand-built sampling results with overlapping category samples.
#
# Construction is direct so stratum index and sample rank -- the union's
# deterministic order inputs -- are fully caller-controlled and hand-computable.
# --------------------------------------------------------------------------


def category_result(
    category: str,
    members: tuple[tuple[str, int], ...],
) -> sampling.CategorySamplingResult:
    """Build one census ``CategorySamplingResult`` from ``(key, rank)`` pairs.

    ``members`` is the exact sample in ``(stratum_index, sample_rank)`` order;
    the canonical population is the identity set of the members.
    """
    members = tuple(members)
    keys = tuple(key for key, _ in members)
    population = sampling.CanonicalPopulation(
        category=category,
        identity_keys=keys,
        retained_ordinals=tuple(range(1, len(keys) + 1)),
        excluded_unresolved_count=0,
        excluded_duplicate_count=0,
        collapsed_repeat_count=0,
    )
    strata = (
        (
            sampling.SamplingStratum(
                stratum_index=0,
                stratum_offset=0,
                stratum_stride=1,
                population_count=len(keys),
                selected_count=len(members),
                target_count=len(members),
                is_reduced=False,
            ),
        )
        if keys
        else ()
    )
    built_members = tuple(
        sampling.SampledMember(
            category=category,
            asset_identity_key=key,
            stratum_index=0,
            stratum_offset=0,
            stratum_stride=1,
            sample_rank_within_stratum=rank,
            sample_is_census=True,
            selection_digest=f"digest:{category}:{key}",
        )
        for key, rank in members
    )
    return sampling.CategorySamplingResult(
        category=category,
        population=population,
        strata=strata,
        members=built_members,
        sampling_basis=SamplingBasis.CENSUS,
        sample_is_census=True,
        discovered_population_count=len(keys),
        enriched_sample_count=len(built_members),
        sample_fraction=1.0 if keys else None,
        sampling_rule_version="2.0.0",
    )


def overlap_run(run_id: str = RUN_ID) -> sampling.RunSamplingResult:
    """Return the overlap golden run: A -> {1,2}, B -> {2,3}, C -> {3}.

    Category references sum to five; unique identities are three.
    """
    return sampling.RunSamplingResult(
        run_id=run_id,
        sampling_rule_version="2.0.0",
        categories=(
            category_result(CATEGORY_1, (("A", 1),)),
            category_result(CATEGORY_2, (("A", 1), ("B", 2))),
            category_result(CATEGORY_3, (("B", 1), ("C", 2))),
        ),
    )


def all_reused_keys() -> tuple[str, ...]:
    """Return every overlap-run identity, for the zero-pending projection case."""
    return OVERLAP_MEMBERS


# --------------------------------------------------------------------------
# Persisted observation rows (frozen Chunk 2 ``EnrichmentObservationRecord``).
# --------------------------------------------------------------------------


def observation_record(
    run_id: str,
    asset_identity_key: str,
    *,
    product_detail_status: str = OperationStatus.SUCCESS.value,
    page_views_status: str = OperationStatus.SUCCESS.value,
    product_page_views: int | None = 4321,
    first_published_date_utc: datetime | None = None,
    state: str | None = "published",
    rating_average: float | None = 4.5,
    rating_count: int | None = 210,
    id_mapping_mismatch: bool = False,
) -> EnrichmentObservationRecord:
    """Build one inert enrichment observation row for ``(run_id, key)``.

    Every keyword is an explicit field override so the finalization fixtures can
    vary one product-level input at a time; the defaults are the executable-suite
    values and are unchanged. A naive ``first_published_date_utc`` is deliberate
    for the pure ``finalize_stratum_counts`` vectors (no persistence).
    """
    return EnrichmentObservationRecord(
        run_id=run_id,
        asset_identity_key=asset_identity_key,
        product_detail_status=product_detail_status,
        page_views_status=page_views_status,
        graphql_id=asset_identity_key,
        product_id=asset_identity_key,
        rating_average=rating_average,
        rating_count=rating_count,
        review_count=34,
        first_published_date_utc=first_published_date_utc,
        publisher_json=None,
        category_json=None,
        state=state,
        product_page_views=product_page_views,
        id_mapping_mismatch=id_mapping_mismatch,
        product_detail_error_summary=None,
        page_views_error_summary=None,
        request_metadata_json="{}",
        retrieved_at_utc=RETRIEVED_AT_UTC,
    )


def seed_run(repository: Any, run: sampling.RunSamplingResult) -> None:
    """Insert the ``runs`` row and its category rows through the frozen path.

    ``enrichment_observations`` carries a foreign key to ``runs.run_id``, so the
    run row must exist before a pass persists a row; this mirrors the runtime
    order without seeding sample members (the executor never reads them).
    """
    from fixtures.identity_preflight_vectors import run_record

    repository.insert_run(
        run_record(run.run_id, categories=tuple(c.category for c in run.categories))
    )
    for category in run.categories:
        repository.set_category_status(
            run.run_id,
            category.category,
            DiscoveryStatus.COMPLETE.value,
            computed_at_utc=RETRIEVED_AT_UTC,
        )


# --------------------------------------------------------------------------
# 6B §5.4 finalization golden vectors (plan §9; hand-derived, never read off
# the implementation).
#
# One category, one stratum, N_h == 10, n_h == 6. Six sampled observations:
# F1-F3 carry a valid aware date at least MIN_AGE_DAYS_FOR_RATE old and finite
# page views (F2's page views are the explicit valid 0); F4 carries a missing
# date (unavailable, reason ``null``); F5 is state-excluded; F6 has a failed
# page_views_status but a valid date. Hand-computed by Chunk 7A's rules:
# u_demand_h == 4 (F1,F2,F3,F6), u_recent_h == 5 (all but the undated F4),
# u_quality_h == 3 (F1,F2,F3).
#
# Plan §9 calls F4 "a naive date", but a persisted EnrichmentObservationRecord
# validates ``first_published_date_utc`` as timezone-aware UTC (models.py
# ``_UtcRecord``), and SRS hard rule 3 forbids naive datetimes. A naive value
# therefore cannot reach ``finalize_stratum_counts`` through the frozen record;
# the equivalent unavailable observation is a missing date, which also keeps
# ``missing is not zero`` (reason ``null``, never a fabricated zero).
# --------------------------------------------------------------------------

FINALIZATION_CATEGORY = "Category/Final"
FINALIZATION_ZERO_CATEGORY = "Category/Zero"
FINALIZATION_POPULATION = 10
FINALIZATION_SAMPLE = 6
FINALIZATION_U_DEMAND = 4
FINALIZATION_U_RECENT = 5
FINALIZATION_U_QUALITY = 3
FINALIZATION_USABLE_STATUS = "usable"
FINALIZATION_MEMBERS: tuple[str, ...] = ("F1", "F2", "F3", "F4", "F5", "F6")
#: F4's null date is the first unavailable classification in (stratum, rank)
#: order, but at the default minimum 1 the demand count (4) and the quality
#: count (3) still meet the inclusive floor, so every component is usable and
#: the rule emits ``usable:<min>`` with the default minimum.
FINALIZATION_ELIGIBILITY_RULE = "demand=usable:1;recent=usable:1;quality=usable:1"
#: 100 days before the fixed cutoff: finite page views and >= MIN_AGE_DAYS_FOR_RATE.
FINALIZATION_DATE_UTC = SCORING_CUTOFF_UTC - timedelta(days=100)
#: A deliberate naive datetime (never persisted): the cutoff-rejection input.
FINALIZATION_NAIVE_DATE_UTC = FINALIZATION_DATE_UTC.replace(tzinfo=None)


def finalization_category() -> sampling.CategorySamplingResult:
    """Return the golden category: one stratum, ``N_h == 10``, ``n_h == 6``."""
    return _finalization_category_result(
        FINALIZATION_CATEGORY,
        tuple((key, rank) for rank, key in enumerate(FINALIZATION_MEMBERS, start=1)),
        population_count=FINALIZATION_POPULATION,
    )


def _finalization_category_result(
    category: str,
    members: tuple[tuple[str, int], ...],
    *,
    population_count: int,
) -> sampling.CategorySamplingResult:
    """Build one stratified category with a caller-chosen stratum population."""
    keys = tuple(key for key, _ in members)
    population = sampling.CanonicalPopulation(
        category=category,
        identity_keys=keys,
        retained_ordinals=tuple(range(1, len(keys) + 1)),
        excluded_unresolved_count=0,
        excluded_duplicate_count=0,
        collapsed_repeat_count=0,
    )
    strata = (
        (
            sampling.SamplingStratum(
                stratum_index=0,
                stratum_offset=0,
                stratum_stride=1,
                population_count=population_count,
                selected_count=len(members),
                target_count=len(members),
                is_reduced=False,
            ),
        )
        if members
        else ()
    )
    # A hand-built single stratum whose membership covers ordinals 1..N: the
    # full-cover geometry is (offset=0, stride=1), the same encoding census uses
    # (plan chunk-24 §2.3). This fixture drives the metric/finalization paths,
    # which consume stratum_index/N_h/n_h only; it is not produced by
    # build_strata and makes no large-category claim.
    built_members = tuple(
        sampling.SampledMember(
            category=category,
            asset_identity_key=key,
            stratum_index=0,
            stratum_offset=0,
            stratum_stride=1,
            sample_rank_within_stratum=rank,
            sample_is_census=False,
            selection_digest=f"digest:{category}:{key}",
        )
        for key, rank in members
    )
    return sampling.CategorySamplingResult(
        category=category,
        population=population,
        strata=strata,
        members=built_members,
        sampling_basis=SamplingBasis.DETERMINISTIC_STRATIFIED_SAMPLE,
        sample_is_census=False,
        discovered_population_count=population_count,
        enriched_sample_count=len(built_members),
        sample_fraction=(len(built_members) / population_count)
        if population_count
        else None,
        sampling_rule_version="2.0.0",
    )


def zero_population_category() -> sampling.CategorySamplingResult:
    """Return the zero-population category: no strata, no members, ``N == 0``."""
    return category_result(FINALIZATION_ZERO_CATEGORY, ())


def finalization_observations(
    run_id: str = RUN_ID,
) -> dict[str, EnrichmentObservationRecord]:
    """Return the six golden observations keyed by identity, in rank order."""
    return {
        "F1": observation_record(
            run_id,
            "F1",
            product_page_views=4321,
            first_published_date_utc=FINALIZATION_DATE_UTC,
        ),
        "F2": observation_record(
            run_id,
            "F2",
            product_page_views=0,
            first_published_date_utc=FINALIZATION_DATE_UTC,
        ),
        "F3": observation_record(
            run_id,
            "F3",
            product_page_views=999,
            first_published_date_utc=FINALIZATION_DATE_UTC,
        ),
        "F4": observation_record(
            run_id,
            "F4",
            product_page_views=4321,
        ),
        "F5": observation_record(
            run_id,
            "F5",
            product_page_views=4321,
            first_published_date_utc=FINALIZATION_DATE_UTC,
            state="excluded",
        ),
        "F6": observation_record(
            run_id,
            "F6",
            product_page_views=4321,
            first_published_date_utc=FINALIZATION_DATE_UTC,
            page_views_status=OperationStatus.ERROR.value,
        ),
    }


def finalization_run(run_id: str = RUN_ID) -> sampling.RunSamplingResult:
    """Return the single-category golden run whose samples are F1-F6."""
    return sampling.RunSamplingResult(
        run_id=run_id,
        sampling_rule_version="2.0.0",
        categories=(finalization_category(),),
    )


def finalization_run_with_zero(run_id: str = RUN_ID) -> sampling.RunSamplingResult:
    """Return the golden run plus the zero-population category (plan §8 E8)."""
    return sampling.RunSamplingResult(
        run_id=run_id,
        sampling_rule_version="2.0.0",
        categories=(finalization_category(), zero_population_category()),
    )


def persisted_finalization_observations(repository: Any, run_id: str = RUN_ID) -> None:
    """Upsert the six golden observations through the frozen write path."""
    for record in finalization_observations(run_id).values():
        repository.upsert_enrichment_observation(record)


def seed_finalization(repository: Any, run: sampling.RunSamplingResult) -> None:
    """Seed run + 4B sampling rows + the golden observations for ``run``.

    The zero-population category deliberately gets no observation row: its
    empty sample means no member was sampled (plan §8 E8). Every other category
    is assumed to be the golden one (the only one this builder is used for).
    """
    seed_sampling_and_run(repository, run)
    if any(category.category == FINALIZATION_CATEGORY for category in run.categories):
        persisted_finalization_observations(repository, run.run_id)


# --------------------------------------------------------------------------
# Chunk 21 rating-count-straddling finalization fixture (plan §8.3).
#
# One stratum, N_h = 25, n_h = 5. Every member mirrors the golden finalization
# fixture's product-level fields (aware UTC date 100 days before the cutoff,
# 4321 page views, both operations successful, published state) except
# ``rating_count``, which straddles the default QUALITY_MIN_RATING_COUNT (5)
# and the chunk-21 override minimum 3 (SRS §14 marks it Configurable ``Yes``):
#
#   Q1 rating_count = 2 -> below both minimums, ineligible under both
#   Q2 rating_count = 3 -> eligible only at an override of 3
#   Q3 rating_count = 4 -> eligible only at an override of 3
#   Q4 rating_count = 5 -> eligible at the default 5 and at 3
#   Q5 rating_count = 7 -> eligible at the default 5 and at 3
#
# Hand-computed u_quality_h (SRS §7.5, ``rating_count >= minimum``):
#   4 at quality_min_rating_count = 3 (Q2, Q3, Q4, Q5)
#   2 at the default 5 (Q4, Q5)
# The fixture stores inputs only; expectations live in the test (plan §8.3).
# --------------------------------------------------------------------------

QUALITY_STRADDLE_CATEGORY = "Category/QualityStraddle"
QUALITY_STRADDLE_POPULATION = 25
QUALITY_STRADDLE_MEMBERS: tuple[str, ...] = ("Q1", "Q2", "Q3", "Q4", "Q5")
#: ``(member key, rating_count)`` in member/sample-rank order.
QUALITY_STRADDLE_RATING_COUNTS: tuple[tuple[str, int], ...] = (
    ("Q1", 2),
    ("Q2", 3),
    ("Q3", 4),
    ("Q4", 5),
    ("Q5", 7),
)


def quality_straddle_finalization_category() -> sampling.CategorySamplingResult:
    """Return the straddling category: one stratum, ``N_h = 25``, ``n_h = 5``."""
    return _finalization_category_result(
        QUALITY_STRADDLE_CATEGORY,
        tuple(
            (key, rank) for rank, key in enumerate(QUALITY_STRADDLE_MEMBERS, start=1)
        ),
        population_count=QUALITY_STRADDLE_POPULATION,
    )


def quality_straddle_finalization_observations(
    run_id: str = RUN_ID,
) -> dict[str, EnrichmentObservationRecord]:
    """Return the five straddling observations keyed by identity, in rank order."""
    return {
        key: observation_record(
            run_id,
            key,
            rating_count=rating_count,
            first_published_date_utc=FINALIZATION_DATE_UTC,
        )
        for key, rating_count in QUALITY_STRADDLE_RATING_COUNTS
    }


def quality_straddle_finalization_run(
    run_id: str = RUN_ID,
) -> sampling.RunSamplingResult:
    """Return the single-category straddling run whose samples are Q1-Q5."""
    return sampling.RunSamplingResult(
        run_id=run_id,
        sampling_rule_version="2.0.0",
        categories=(quality_straddle_finalization_category(),),
    )


def seed_quality_straddle_finalization(
    repository: Any, run: sampling.RunSamplingResult
) -> None:
    """Seed run + 4B sampling rows + the five straddling observations for ``run``."""
    seed_sampling_and_run(repository, run)
    if any(
        category.category == QUALITY_STRADDLE_CATEGORY for category in run.categories
    ):
        for record in quality_straddle_finalization_observations(run.run_id).values():
            repository.upsert_enrichment_observation(record)


# --------------------------------------------------------------------------
# Caller-injected transports (inert; never the network).
# --------------------------------------------------------------------------


class EnrichmentTransport:
    """A fake ``GraphQLTransport`` that counts calls and fails selected keys.

    ``body_for_identity`` maps an identity to an inert response body; an
    identity in ``failing`` raises before a body is served (the adapter's
    ``TRANSPORT_FAILURE`` path). ``on_call`` is invoked with the requested
    identity before the body is served, so a test can snapshot log state at the
    first request.
    """

    def __init__(
        self,
        body_for_identity: Mapping[str, Any] | None = None,
        *,
        failing: tuple[str, ...] = (),
        on_call: Callable[[str], None] | None = None,
    ) -> None:
        self._bodies = dict(body_for_identity or {})
        self._failing = set(failing)
        self._on_call = on_call
        self.calls: list[Any] = []

    def __call__(self, request: Any, headers: Mapping[str, str]) -> Any:
        from niche_scout.collector_graphql import GraphQLBatchResponse

        self.calls.append(request)
        key = str(getattr(request, "asset_identity_key", ""))
        if self._on_call is not None:
            self._on_call(key)
        if key in self._failing:
            raise ConnectionResetError("injected transport failure")
        body = self._bodies.get(key)
        if body is None:
            raise AssertionError(f"no fixture response queued for identity {key!r}")
        if isinstance(body, (bytes, bytearray)):
            body = body.decode("utf-8")
        return GraphQLBatchResponse(http_status=200, body_text=body)

    @property
    def call_count(self) -> int:
        """Return how many times the transport was called."""
        return len(self.calls)

    @property
    def requested_identities(self) -> tuple[str, ...]:
        """Return each call's ``asset_identity_key``, in call order."""
        return tuple(
            str(getattr(call, "asset_identity_key", "")) for call in self.calls
        )

    @property
    def distinct_requested_identities(self) -> tuple[str, ...]:
        """Return the distinct requested identities, in first-call order."""
        seen: list[str] = []
        for key in self.requested_identities:
            if key not in seen:
                seen.append(key)
        return tuple(seen)


def success_transport(keys: tuple[str, ...]) -> EnrichmentTransport:
    """Return a transport serving a both-operations-success body per identity."""
    return EnrichmentTransport({key: success_body(key) for key in keys})


def success_bodies(keys: tuple[str, ...]) -> dict[str, bytes]:
    """Return ``{key: both-operations-success body}`` for injected transports."""
    return {key: success_body(key) for key in keys}


def mixed_transport(
    succeeding: tuple[str, ...], *, failing: tuple[str, ...] = ()
) -> EnrichmentTransport:
    """Return a transport succeeding on ``succeeding`` and raising on ``failing``."""
    return EnrichmentTransport(
        {key: success_body(key) for key in succeeding}, failing=failing
    )
