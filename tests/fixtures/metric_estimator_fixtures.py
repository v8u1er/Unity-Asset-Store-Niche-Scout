"""Golden vectors and builders for the Chunk 7B sample-aware raw estimators.

Data only: explicit constants, inert golden-vector tables, and small
keyword-argument builders. There are no assertions here; the expectations live in
``tests/test_metrics.py``.

Every expected value below is hand-derived from the SRS formulas, never copied
from the implementation:

* stratum expansion weight ``N_h / n_h`` — SRS-lean.md §7.2 / §7.4 / §7.5
  (LREQ-MET-050, LREQ-MET-100).
* ``DemandPerAssetRaw = sum(w_h * mean_h) / sum(w_h)`` with ``w_h = N_h / N``
  — SRS-lean.md §7.2 (LREQ-MET-030).
* ``DemandMedianRaw`` / ``MedianAgeRaw``: stratum-expanded weighted median with
  per-observation weight ``N_h / n_h`` and the exact-half boundary rule
  — SRS-lean.md §7.2 / §7.4 (LREQ-MET-050, LREQ-MET-080).
* ``demand_stratum_eligibility_coverage = sum(N_h / N)`` over usable strata
  — SRS-lean.md §7.2 (LREQ-MET-060).
* ``BreadthRaw``: verified ``totalCount`` else distinct canonical discovered
  count — SRS-lean.md §7.3 (LREQ-MET-070).
* ``RecentShareRaw``: population-weighted mean of usable
  ``count(0 <= age <= 365) / dated_asset_count_h`` — SRS-lean.md §7.4
  (LREQ-MET-080).
* ``QualityRaw = sum(num_h) / sum(den_h)`` with
  ``num_h = (N_h/n_h) * sum((rating_average_i / 5) * index_i)`` and
  ``den_h = (N_h/n_h) * sum(index_i)`` — SRS-lean.md §7.5 (LREQ-MET-090,
  LREQ-MET-100).

``CUTOFF_UTC`` is an explicit, timezone-aware UTC instant (SRS-lean.md §7.1;
LREQ-ARCH-020). Every dated observation below is a constant built by subtracting
a fixed ``timedelta`` from ``CUTOFF_UTC``, so each ``age_days_exact`` is exact
and no clock is ever read. No network, no credentials.

Import note: this module imports the Chunk 7B names from ``niche_scout.metrics``.
Before the implementation landed it raised ``ImportError`` (expected for a
test-author-first chunk); it now imports and collects normally.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from niche_scout.metrics import (
    BreadthMetricInput,
    CategoryMetricInput,
    MetricObservation,
    StratumMetricInput,
)
from niche_scout.models import (
    MIN_REQUIRED_COMPONENT_COVERAGE,
    MIN_USABLE_SAMPLES_PER_STRATUM,
    QUALITY_MIN_ELIGIBLE_ASSETS,
    QUALITY_MIN_RATING_COUNT,
    RECENT_WINDOW_DAYS,
    BreadthCompletenessStatus,
    BreadthSource,
    OperationStatus,
    PageViewSemanticsStatus,
)

__all__ = [
    "BREADTH_FALLBACK_INPUT",
    "BREADTH_INPUT_VECTORS",
    "BREADTH_VERIFIED_INPUT",
    "BREADTH_VERIFIED_ZERO_INPUT",
    "CUTOFF_UTC",
    "DATE_10D",
    "DATE_20D",
    "DATE_29D",
    "DATE_30D",
    "DATE_40D",
    "DATE_50D",
    "DATE_70D",
    "DATE_100D",
    "DATE_200D",
    "DATE_300D",
    "DATE_400D",
    "DATE_500D",
    "DATE_600D",
    "DEMAND_EXPLICIT_ZERO",
    "DEMAND_INELIGIBLE_EXCLUDED",
    "DEMAND_MEDIAN_EXACT_HALF",
    "DEMAND_NO_USABLE_INDEX",
    "DEMAND_NO_USABLE_STRATUM",
    "DEMAND_PARTIAL_COVERAGE",
    "DEMAND_UNEQUAL_STRATA",
    "MIN_REQUIRED_COMPONENT_COVERAGE",
    "MIN_USABLE_SAMPLES_PER_STRATUM",
    "OPERATION_ERROR",
    "OPERATION_SUCCESS",
    "PAGE_VIEW_SEMANTICS_CONTRADICTED",
    "PAGE_VIEW_SEMANTICS_UNVALIDATED",
    "PAGE_VIEW_SEMANTICS_VALIDATED_CUMULATIVE",
    "QUALITY_ELIGIBLE_SET_TOO_SMALL",
    "QUALITY_LOW_COVERAGE",
    "QUALITY_MIN_ELIGIBLE_ASSETS",
    "QUALITY_MIN_RATING_COUNT",
    "QUALITY_UNEQUAL_STRATA",
    "QUALITY_UNEQUAL_STRATUM_INPUTS",
    "QUALITY_ZERO_VISIBILITY",
    "RECENT_MISSING_DATES",
    "RECENT_UNEQUAL_STRATA",
    "RECENT_USABILITY_BOUNDARY",
    "RECENT_WINDOW_DAYS",
    "RATING_AVERAGE_STRATUM_ONE",
    "RATING_AVERAGE_STRATUM_ZERO",
    "RATING_COUNT_AT_MINIMUM",
    "SEMANTICS_CONTRADICTED",
    "STATE_DRAFT",
    "STATE_PUBLISHED",
    "STRATUM_EXPANSION_WEIGHT_INVALID_VECTORS",
    "STRATUM_EXPANSION_WEIGHT_VECTORS",
    "WEIGHTED_MEDIAN_DEMAND_STRATA_VECTOR",
    "WEIGHTED_MEDIAN_EMPTY",
    "WEIGHTED_MEDIAN_INVALID_VECTORS",
    "WEIGHTED_MEDIAN_TIE_VECTOR",
    "WEIGHTED_MEDIAN_VECTORS",
    "WEIGHTED_MEDIAN_ZERO_WEIGHT_VECTORS",
    "ZERO_POPULATION",
    "make_breadth_input",
    "make_category_input",
    "make_observation",
    "make_stratum",
]

# ---------------------------------------------------------------------------
# Cutoff and exact ages (SRS-lean.md §7.1: age is exact fractional days)
# ---------------------------------------------------------------------------

#: The explicit scoring cutoff every age below is measured against (plan §9.2).
CUTOFF_UTC: datetime = datetime(2025, 1, 31, 0, 0, tzinfo=timezone.utc)

# Each date is exactly ``CUTOFF_UTC - timedelta(days=N)``, so the resulting
# ``age_days_exact`` is the integer in the constant's name. All are valid UTC
# dates no later than the cutoff (SRS-lean.md §7.2).

DATE_10D: datetime = CUTOFF_UTC - timedelta(days=10)  # age_days_exact == 10.0
DATE_20D: datetime = CUTOFF_UTC - timedelta(days=20)  # age_days_exact == 20.0
DATE_29D: datetime = CUTOFF_UTC - timedelta(days=29)  # age_days_exact == 29.0
DATE_30D: datetime = CUTOFF_UTC - timedelta(days=30)  # age_days_exact == 30.0
DATE_40D: datetime = CUTOFF_UTC - timedelta(days=40)  # age_days_exact == 40.0
DATE_50D: datetime = CUTOFF_UTC - timedelta(days=50)  # age_days_exact == 50.0
DATE_70D: datetime = CUTOFF_UTC - timedelta(days=70)  # age_days_exact == 70.0
DATE_100D: datetime = CUTOFF_UTC - timedelta(days=100)  # age_days_exact == 100.0
DATE_200D: datetime = CUTOFF_UTC - timedelta(days=200)  # age_days_exact == 200.0
DATE_300D: datetime = CUTOFF_UTC - timedelta(days=300)  # age_days_exact == 300.0
DATE_400D: datetime = CUTOFF_UTC - timedelta(days=400)  # age_days_exact == 400.0
DATE_500D: datetime = CUTOFF_UTC - timedelta(days=500)  # age_days_exact == 500.0
DATE_600D: datetime = CUTOFF_UTC - timedelta(days=600)  # age_days_exact == 600.0

# ---------------------------------------------------------------------------
# Enum and vocabulary fixtures
# ---------------------------------------------------------------------------

OPERATION_SUCCESS: OperationStatus = OperationStatus.SUCCESS
OPERATION_ERROR: OperationStatus = OperationStatus.ERROR

PAGE_VIEW_SEMANTICS_UNVALIDATED: PageViewSemanticsStatus = (
    PageViewSemanticsStatus.UNVALIDATED
)
PAGE_VIEW_SEMANTICS_VALIDATED_CUMULATIVE: PageViewSemanticsStatus = (
    PageViewSemanticsStatus.VALIDATED_CUMULATIVE
)
PAGE_VIEW_SEMANTICS_CONTRADICTED: PageViewSemanticsStatus = (
    PageViewSemanticsStatus.CONTRADICTED
)

#: A published state passes Chunk 7A's index/quality gates; a draft state does not.
STATE_PUBLISHED: str = "published"
STATE_DRAFT: str = "draft"

#: ``QUALITY_UNEQUAL_STRATA`` stratum 0's rating average: 2.5 / 5 = 0.5.
RATING_AVERAGE_STRATUM_ZERO: float = 2.5

#: ``QUALITY_UNEQUAL_STRATA`` stratum 1's rating average: 5.0 / 5 = 1.0.
RATING_AVERAGE_STRATUM_ONE: float = 5.0

#: An exactly-at-minimum rating count (5); the eligible-set size gate, not the
#: rating count, is what ``QUALITY_ELIGIBLE_SET_TOO_SMALL`` exercises.
RATING_COUNT_AT_MINIMUM: int = QUALITY_MIN_RATING_COUNT

# ---------------------------------------------------------------------------
# Builders (inert construction helpers, no behavior under test)
# ---------------------------------------------------------------------------


def make_observation(**overrides: object) -> MetricObservation:
    """Build one ``MetricObservation`` (plan §5.2).

    Defaults describe a fully usable asset: published, matched identity, both
    operations successful, ``product_page_views = 100`` at ``DATE_70D`` (so the
    page-view index is the weekly view count ``100.0``; SRS §7.2 / chunk-28),
    a rating average of 5.0, and a rating count at
    ``QUALITY_MIN_RATING_COUNT``.
    """
    kwargs: dict[str, object] = {
        "product_page_views": 100,
        "first_published_date_utc": DATE_70D,
        "state": STATE_PUBLISHED,
        "id_mapping_mismatch": False,
        "rating_average": 5.0,
        "rating_count": QUALITY_MIN_RATING_COUNT,
        "product_detail_status": OPERATION_SUCCESS,
        "page_views_status": OPERATION_SUCCESS,
    }
    kwargs.update(overrides)
    return MetricObservation(**kwargs)


def make_stratum(
    stratum_index: int,
    discovered_population_count: int,
    observations: tuple[MetricObservation, ...],
    sampled_population_count: int | None = None,
) -> StratumMetricInput:
    """Build one ``StratumMetricInput`` (plan §5.2).

    ``sampled_population_count`` (``n_h``) defaults to ``len(observations)`` so a
    fixture never accidentally violates the ``len(observations) == n_h`` rule.
    Pass it explicitly to construct the deliberate mismatch a caller-breach test
    needs.
    """
    return StratumMetricInput(
        stratum_index=stratum_index,
        discovered_population_count=discovered_population_count,
        sampled_population_count=(
            len(observations)
            if sampled_population_count is None
            else sampled_population_count
        ),
        observations=tuple(observations),
    )


def make_category_input(
    strata: tuple[StratumMetricInput, ...],
    *,
    category: str = "fixture-category",
    scoring_cutoff_utc: datetime = CUTOFF_UTC,
    page_view_semantics_status: PageViewSemanticsStatus = (
        PageViewSemanticsStatus.UNVALIDATED
    ),
) -> CategoryMetricInput:
    """Build one ``CategoryMetricInput`` (plan §5.2).

    Every threshold parameter keeps the frozen ``models`` default (SRS §14 marks
    them configurable; production callers use the defaults).
    """
    return CategoryMetricInput(
        category=category,
        scoring_cutoff_utc=scoring_cutoff_utc,
        page_view_semantics_status=page_view_semantics_status,
        strata=tuple(strata),
    )


def make_breadth_input(
    verified_total_count: int | None,
    distinct_canonical_discovered_count: int,
) -> BreadthMetricInput:
    """Build one ``BreadthMetricInput`` (plan §5.2 / §7.3)."""
    return BreadthMetricInput(
        verified_total_count=verified_total_count,
        distinct_canonical_discovered_count=distinct_canonical_discovered_count,
    )


# ---------------------------------------------------------------------------
# Stratum expansion weight N_h / n_h (SRS-lean.md §7.2, §7.4, §7.5)
# ---------------------------------------------------------------------------

#: ``(N_h, n_h, expected N_h / n_h)``. The first two are the weights used by the
#: DEMAND_UNEQUAL_STRATA median vector; ``(50, 25)`` gives the recent/quality
#: weight 2.0; ``(100, 4)`` gives 25.0.
STRATUM_EXPANSION_WEIGHT_VECTORS: tuple[tuple[int, int, float], ...] = (
    (75, 25, 3.0),
    (25, 25, 1.0),
    (50, 25, 2.0),
    (100, 4, 25.0),
)

#: Caller/policy breaches: a bool (``isinstance(True, int)`` is ``True``), zero,
#: or a negative population/sample count must raise ``ValueError`` (plan §5.0).
STRATUM_EXPANSION_WEIGHT_INVALID_VECTORS: tuple[tuple[str, object, object], ...] = (
    ("bool_population", True, 1),
    ("bool_sampled", 1, True),
    ("zero_population", 0, 1),
    ("zero_sampled", 1, 0),
    ("negative_population", -1, 1),
    ("negative_sampled", 1, -1),
)

# ---------------------------------------------------------------------------
# Weighted-median golden vectors (SRS-lean.md §7.2, LREQ-MET-050)
# ---------------------------------------------------------------------------

#: ``sorted(value, weight)`` ascending; an empty sequence has no usable weight.
WEIGHTED_MEDIAN_EMPTY: tuple[tuple[float, float], ...] = ()

#: Total weight exactly zero: the usable weighted sample is empty -> ``None``.
WEIGHTED_MEDIAN_ZERO_WEIGHT_VECTORS: tuple[tuple[tuple[float, float], ...], ...] = (
    ((1.0, 0.0),),
    ((1.0, 0.0), (2.0, 0.0)),
)

#: Ties retained as separate observations: ``T = 4``, cumulative ``1, 2``; the
#: exact-half cumulative weight lands on the second ``1.0``, whose next sorted
#: value is ``2.0`` -> ``(1.0 + 2.0) / 2 == 1.5``.
WEIGHTED_MEDIAN_TIE_VECTOR: tuple[tuple[float, float], ...] = (
    (1.0, 1.0),
    (1.0, 1.0),
    (2.0, 2.0),
)

#: The 10-element vector of plan §9.2, which is exactly the DEMAND_UNEQUAL_STRATA
#: usable-index population with ``N_h / n_h`` weights: stratum 0 values
#: ``10, 20, 30, 40, 50`` each weighted ``75 / 25 == 3.0`` and stratum 1 values
#: ``100, 200, 300, 400, 500`` each weighted ``25 / 25 == 1.0``.
#: ``T = 20``, cumulative ``3, 6, 9, 12``; the first value whose cumulative
#: weight is ``>= 10`` is ``40.0`` (no exact-half tie) -> ``40.0``.
WEIGHTED_MEDIAN_DEMAND_STRATA_VECTOR: tuple[tuple[float, float], ...] = (
    (10.0, 3.0),
    (20.0, 3.0),
    (30.0, 3.0),
    (40.0, 3.0),
    (50.0, 3.0),
    (100.0, 1.0),
    (200.0, 1.0),
    (300.0, 1.0),
    (400.0, 1.0),
    (500.0, 1.0),
)

#: ``(values_and_weights, expected)``, hand-derived from the SRS boundary rule
#: "first sorted value whose cumulative weight is at least half the total weight;
#: if cumulative weight equals exactly half at a value boundary, use the
#: arithmetic mean of that value and the next sorted value".
WEIGHTED_MEDIAN_VECTORS: tuple[tuple[tuple[tuple[float, float], ...], float], ...] = (
    # T = 1, half = 0.5; cumulative 1 >= 0.5 -> 7.0.
    (((7.0, 1.0),), 7.0),
    # T = 2, half = 1; cumulative 1 == half at value 1.0, next is 2.0 -> 1.5.
    (((1.0, 1.0), (2.0, 1.0)), 1.5),
    # T = 4, half = 2; cumulative 2 == half at value 1.0, next is 2.0 -> 1.5.
    (((1.0, 2.0), (2.0, 2.0)), 1.5),
    # T = 4, half = 2; cumulative 1, 2 == half at the second 1.0, next 2.0 -> 1.5.
    (((1.0, 1.0), (1.0, 1.0), (2.0, 2.0)), 1.5),
    # Plan §9.2's 10-element vector: T = 20, half = 10 -> 40.0.
    (WEIGHTED_MEDIAN_DEMAND_STRATA_VECTOR, 40.0),
)

#: Caller-contract breaches: a non-finite value or weight, or a negative weight,
#: raises ``ValueError`` (plan §5.0) rather than fabricating a product value.
WEIGHTED_MEDIAN_INVALID_VECTORS: tuple[
    tuple[str, tuple[tuple[float, float], ...]], ...
] = (
    ("nan_value", ((float("nan"), 1.0),)),
    ("infinite_value", ((float("inf"), 1.0),)),
    ("nan_weight", ((1.0, float("nan")),)),
    ("negative_weight", ((1.0, -1.0),)),
)

# ---------------------------------------------------------------------------
# DEMAND_UNEQUAL_STRATA — plan §9.2 (LREQ-MET-030, -050, -060)
# ---------------------------------------------------------------------------
#
# Two strata, N_0 = 75, n_0 = 25, N_1 = 25, n_1 = 25, N = 100.
#
# Index arithmetic (D1-S2; the index IS the weekly page-view count): every
# observation sits at DATE_70D (age_days_exact = 70.0), and the index no longer
# depends on age, so index = product_page_views.
#   Stratum 0 usable indices: views 10, 20, 30, 40, 50 -> [10.0, 20.0, 30.0, 40.0, 50.0]
#     mean_0 = (10+20+30+40+50)/5 = 150/5 = 30.0; u_demand_0 = 5; w_0 = N_0/N = 0.75.
#   Stratum 1 usable indices: views 100..500 -> [100, 200, 300, 400, 500]
#     mean_1 = 1500/5 = 300.0; u_demand_1 = 5; w_1 = N_1/N = 0.25.
#   20 unusable observations per stratum (product_page_views = None) contribute
#   no weight and no zero.
#
# DemandPerAssetRaw = (0.75 * 30.0 + 0.25 * 300.0) / (0.75 + 0.25)
#                   = (22.5 + 75.0) / 1.0
#                   = 97.5.
# DemandMedianRaw = weighted median of WEIGHTED_MEDIAN_DEMAND_STRATA_VECTOR = 40.0.
# demand_stratum_eligibility_coverage = 0.75 + 0.25 = 1.0.
# usable_demand_sample_count = 5 + 5 = 10.
DEMAND_UNEQUAL_STRATA: CategoryMetricInput = make_category_input(
    (
        make_stratum(
            0,
            75,
            (
                make_observation(product_page_views=10),
                make_observation(product_page_views=20),
                make_observation(product_page_views=30),
                make_observation(product_page_views=40),
                make_observation(product_page_views=50),
            )
            + (make_observation(product_page_views=None),) * 20,
        ),
        make_stratum(
            1,
            25,
            (
                make_observation(product_page_views=100),
                make_observation(product_page_views=200),
                make_observation(product_page_views=300),
                make_observation(product_page_views=400),
                make_observation(product_page_views=500),
            )
            + (make_observation(product_page_views=None),) * 20,
        ),
    ),
    category="demand-unequal-strata",
)

# ---------------------------------------------------------------------------
# RECENT_UNEQUAL_STRATA — plan §9.2 (LREQ-MET-080)
# ---------------------------------------------------------------------------
#
# N_0 = N_1 = 50, n_0 = n_1 = 25, N = 100, w_0 = w_1 = 0.5.
#
#   Stratum 0 usable ages [100, 200, 300, 400, 500]; u_recent_0 = 5. The inclusive
#   window 0 <= age <= 365 holds for 100, 200, 300 -> share_0 = 3/5 = 0.6.
#   Stratum 1 usable ages [10, 20, 30, 40, 50]; u_recent_1 = 5; all 5 inside ->
#   share_1 = 5/5 = 1.0.
#   20 unusable dates per stratum reduce u_recent (never a zero numerator entry).
#
# RecentShareRaw = (0.5 * 0.6 + 0.5 * 1.0) / (0.5 + 0.5)
#                = (0.3 + 0.5) / 1.0
#                = 0.8.
# MedianAgeRaw: every usable dated observation weighs N_h/n_h = 50/25 = 2.0;
#   sorted ages 10, 20, 30, 40, 50, 100, 200, 300, 400, 500; T = 20, half = 10;
#   cumulative 2, 4, 6, 8, 10 -> exact half at age 50, next sorted age 100 ->
#   (50 + 100) / 2 = 75.0.
# recent_supply_stratum_eligibility_coverage = 0.5 + 0.5 = 1.0.
# usable_recent_supply_sample_count = 5 + 5 = 10.
RECENT_UNEQUAL_STRATA: CategoryMetricInput = make_category_input(
    (
        make_stratum(
            0,
            50,
            (
                make_observation(first_published_date_utc=DATE_100D),
                make_observation(first_published_date_utc=DATE_200D),
                make_observation(first_published_date_utc=DATE_300D),
                make_observation(first_published_date_utc=DATE_400D),
                make_observation(first_published_date_utc=DATE_500D),
            )
            + (make_observation(first_published_date_utc=None),) * 20,
        ),
        make_stratum(
            1,
            50,
            (
                make_observation(first_published_date_utc=DATE_10D),
                make_observation(first_published_date_utc=DATE_20D),
                make_observation(first_published_date_utc=DATE_30D),
                make_observation(first_published_date_utc=DATE_40D),
                make_observation(first_published_date_utc=DATE_50D),
            )
            + (make_observation(first_published_date_utc=None),) * 20,
        ),
    ),
    category="recent-unequal-strata",
)

# ---------------------------------------------------------------------------
# QUALITY_UNEQUAL_STRATA — plan §9.2 (LREQ-MET-090, LREQ-MET-100)
# ---------------------------------------------------------------------------
#
# N_0 = N_1 = 50, n_0 = n_1 = 25, N = 100, quality_weight_h = N_h/n_h = 2.0.
# Every quality-eligible observation sits at DATE_70D with views 100, so its index
# (the weekly view count; chunk-28) is exactly 100.0.
#
#   Stratum 0: 5 quality-eligible, each rating_average = 2.5 ->
#     num_0 = 2.0 * sum((2.5/5) * 100.0) = 2.0 * (5 * 50.0) = 500.0;
#     den_0 = 2.0 * sum(100.0) = 2.0 * 500.0 = 1000.0.
#   Stratum 1: 5 quality-eligible, each rating_average = 5.0 ->
#     num_1 = 2.0 * (5 * (1.0 * 100.0)) = 1000.0; den_1 = 1000.0.
#   20 quality-ineligible observations per stratum (rating_average = None).
#
# QualityRaw = (500.0 + 1000.0) / (1000.0 + 1000.0) = 1500.0 / 2000.0 = 0.75.
# quality_stratum_eligibility_coverage = 50/100 + 50/100 = 1.0.
# usable_quality_sample_count = 5 + 5 = 10.
QUALITY_UNEQUAL_STRATUM_INPUTS: tuple[StratumMetricInput, ...] = (
    make_stratum(
        0,
        50,
        (
            make_observation(rating_average=2.5),
            make_observation(rating_average=2.5),
            make_observation(rating_average=2.5),
            make_observation(rating_average=2.5),
            make_observation(rating_average=2.5),
        )
        + (make_observation(rating_average=None),) * 20,
    ),
    make_stratum(
        1,
        50,
        (
            make_observation(),
            make_observation(),
            make_observation(),
            make_observation(),
            make_observation(),
        )
        + (make_observation(rating_average=None),) * 20,
    ),
)

QUALITY_UNEQUAL_STRATA: CategoryMetricInput = make_category_input(
    QUALITY_UNEQUAL_STRATUM_INPUTS,
    category="quality-unequal-strata",
)

# ---------------------------------------------------------------------------
# ZERO_POPULATION — plan §9.2 (LREQ-MET-030, -060, -080, -100)
# ---------------------------------------------------------------------------
#
# strata = (), N = 0. Every sample-derived raw is null and no estimator evaluates
# N_h / N (SRS-lean.md §7.2). All three coverages are 0.0 (a value, not null).
# The paired breadth input is a verified zero-result category: (0, 0) ->
# BreadthResult(0, VERIFIED_TOTAL_COUNT, COMPLETE).
ZERO_POPULATION: CategoryMetricInput = make_category_input(
    (),
    category="zero-population",
)

# ---------------------------------------------------------------------------
# QUALITY_ZERO_VISIBILITY — plan §9.2 (LREQ-MET-100)
# ---------------------------------------------------------------------------
#
# One usable stratum, N_h = 25, n_h = 5, and 5 quality-eligible observations with
# product_page_views = 0 (an explicit valid zero, SRS-lean.md §7.2) at
# DATE_70D: index_i = 0.0 for each (the index is the weekly view count; chunk-28).
#
#   num_h = (25/5) * sum((5.0/5) * 0.0) = 0.0
#   den_h = (25/5) * sum(0.0) = 0.0
# QualityRaw is None with METRIC_REASON_ZERO_DENOMINATOR (the eligible set is 5
# and the stratum is quality-usable), while quality_stratum_eligibility_coverage
# = 25/25 = 1.0 — low/zero coverage and a zero value stay distinct.
QUALITY_ZERO_VISIBILITY: CategoryMetricInput = make_category_input(
    (
        make_stratum(
            0,
            25,
            (
                make_observation(product_page_views=0),
                make_observation(product_page_views=0),
                make_observation(product_page_views=0),
                make_observation(product_page_views=0),
                make_observation(product_page_views=0),
            ),
        ),
    ),
    category="quality-zero-visibility",
)

# ---------------------------------------------------------------------------
# QUALITY_LOW_COVERAGE — plan §9.2, Q-3 (LREQ-MET-090)
# ---------------------------------------------------------------------------
#
# Two strata: N_0 = 25 with 5 quality-eligible observations (usable at any
# floor <= 5), and N_1 = 75 with only 4 quality-eligible observations. The
# consuming floor-branch tests pin ``min_usable_samples_per_stratum = 5``
# explicitly, so stratum 1 (4 < 5) is not quality-usable. N = 100.
#
#   Total quality-eligible = 5 + 4 = 9 >= QUALITY_MIN_ELIGIBLE_ASSETS (5), so the
#   eligible-set guard does not fire.
#   quality_stratum_eligibility_coverage = N_0/N = 25/100 = 0.25 (a population
#   weight, NOT a count fraction: 5/9 = 0.5555...).
#   0.25 < MIN_REQUIRED_COMPONENT_COVERAGE (0.50) -> QualityRaw is None with
#   METRIC_REASON_INSUFFICIENT_COVERAGE (Q-3, option (a)).
QUALITY_LOW_COVERAGE: CategoryMetricInput = make_category_input(
    (
        make_stratum(
            0,
            25,
            (
                make_observation(),
                make_observation(),
                make_observation(),
                make_observation(),
                make_observation(),
            ),
        ),
        make_stratum(
            1,
            75,
            (
                make_observation(),
                make_observation(),
                make_observation(),
                make_observation(),
            ),
        ),
    ),
    category="quality-low-coverage",
)

# ---------------------------------------------------------------------------
# QUALITY_ELIGIBLE_SET_TOO_SMALL — plan §9.3 (LREQ-MET-090)
# ---------------------------------------------------------------------------
#
# One stratum, N_h = 75, n_h = 4, all 4 observations quality-eligible.
# Total quality-eligible = 4 < QUALITY_MIN_ELIGIBLE_ASSETS (5), so QualityRaw is
# None (METRIC_REASON_ELIGIBLE_SET_TOO_SMALL, which precedes the no-usable-stratum
# reason in the documented §5.3 order). The stratum is below the former default
# floor of 5 as well, but the eligible-set guard fires first.
QUALITY_ELIGIBLE_SET_TOO_SMALL: CategoryMetricInput = make_category_input(
    (
        make_stratum(
            0,
            75,
            (
                make_observation(),
                make_observation(),
                make_observation(),
                make_observation(),
            ),
        ),
    ),
    category="quality-eligible-set-too-small",
)

# ---------------------------------------------------------------------------
# SEMANTICS_CONTRADICTED — plan §9.2, Q-1, C-1 (LREQ-MET-090)
# ---------------------------------------------------------------------------
#
# The same two strata as QUALITY_UNEQUAL_STRATA (all observations would otherwise
# be quality-eligible), but the run-level page-view semantics status is
# CONTRADICTED. Chunk 7B consumes the status; it does not detect it (Q-1). Under
# Chunk 7A, CONTRADICTED makes every observation quality-ineligible.
#
# Expected: QualityRaw is None. Lead correction (2026-09-20, C-1, plan §9.2):
# contradicted makes every observation quality-ineligible, so the
# observation-level quality-eligible count is 0 and the §5.3 precedence order
# yields METRIC_REASON_ELIGIBLE_SET_TOO_SMALL (0 < QUALITY_MIN_ELIGIBLE_ASSETS)
# before METRIC_REASON_PAGE_VIEW_SEMANTICS_CONTRADICTED; coverage is 0.0 and the
# run-level status is consumed, not detected (Q-1).
SEMANTICS_CONTRADICTED: CategoryMetricInput = make_category_input(
    QUALITY_UNEQUAL_STRATUM_INPUTS,
    category="semantics-contradicted",
    page_view_semantics_status=PAGE_VIEW_SEMANTICS_CONTRADICTED,
)

# ---------------------------------------------------------------------------
# DEMAND_NO_USABLE_STRATUM — plan §9.3 (LREQ-MET-030)
# ---------------------------------------------------------------------------
#
# Two strata, N_0 = 75, N_1 = 25, n_0 = n_1 = 4; each has only 4 usable indices.
# The consuming floor-branch test pins ``min_usable_samples_per_stratum = 5``
# explicitly, so ``u_demand_h = 4 < 5`` and NO stratum is usable.
#   Stratum 0 indices [10, 20, 30, 40] (weekly view counts, chunk-28)
#   Stratum 1 indices [100, 200, 300, 400]
# DemandPerAssetRaw is None (METRIC_REASON_NO_USABLE_STRATUM);
# demand_stratum_eligibility_coverage = 0.0.
# Per Q-2, every usable observation still enters DemandMedianRaw regardless of
# the stratum minimum: weights 75/4 = 18.75 (four values) and 25/4 = 6.25 (four
# values), T = 100, half = 50, cumulative 18.75, 37.5, 56.25 -> 30.0.
DEMAND_NO_USABLE_STRATUM: CategoryMetricInput = make_category_input(
    (
        make_stratum(
            0,
            75,
            (
                make_observation(product_page_views=10),
                make_observation(product_page_views=20),
                make_observation(product_page_views=30),
                make_observation(product_page_views=40),
            ),
        ),
        make_stratum(
            1,
            25,
            (
                make_observation(product_page_views=100),
                make_observation(product_page_views=200),
                make_observation(product_page_views=300),
                make_observation(product_page_views=400),
            ),
        ),
    ),
    category="demand-no-usable-stratum",
)

# ---------------------------------------------------------------------------
# DEMAND_NO_USABLE_INDEX — plan §9.3 (LREQ-MET-050)
# ---------------------------------------------------------------------------
#
# One stratum, N_h = 75, n_h = 5, every observation with product_page_views = None.
# u_demand_h = 0, so DemandPerAssetRaw is None and DemandMedianRaw is None with
# METRIC_REASON_EMPTY_USABLE_SAMPLE; coverage = 0.0. Missing is never a zero.
DEMAND_NO_USABLE_INDEX: CategoryMetricInput = make_category_input(
    (
        make_stratum(
            0,
            75,
            (make_observation(product_page_views=None),) * 5,
        ),
    ),
    category="demand-no-usable-index",
)

# ---------------------------------------------------------------------------
# DEMAND_MEDIAN_EXACT_HALF — plan §9.3 (LREQ-MET-050)
# ---------------------------------------------------------------------------
#
# Two strata, N_0 = N_1 = 25, n_0 = n_1 = 5 -> stratum expansion weight
# N_h / n_h = 25 / 5 = 5.0 each.
#   Stratum 0 indices [10, 20, 30, 40, 50]; stratum 1 indices [60, 70, 80, 90, 100].
# T = 10 * 5.0 = 50, half = 25; cumulative 5, 10, 15, 20, 25 -> exactly half at
# value 50.0, next sorted value 60.0 -> DemandMedianRaw = (50.0 + 60.0) / 2 = 55.0.
DEMAND_MEDIAN_EXACT_HALF: CategoryMetricInput = make_category_input(
    (
        make_stratum(
            0,
            25,
            (
                make_observation(product_page_views=10),
                make_observation(product_page_views=20),
                make_observation(product_page_views=30),
                make_observation(product_page_views=40),
                make_observation(product_page_views=50),
            ),
        ),
        make_stratum(
            1,
            25,
            (
                make_observation(product_page_views=60),
                make_observation(product_page_views=70),
                make_observation(product_page_views=80),
                make_observation(product_page_views=90),
                make_observation(product_page_views=100),
            ),
        ),
    ),
    category="demand-median-exact-half",
)

# ---------------------------------------------------------------------------
# DEMAND_PARTIAL_COVERAGE — plan §9.3 (LREQ-MET-060)
# ---------------------------------------------------------------------------
#
# Stratum 0: N_0 = 75, n_0 = 25, 5 usable indices [10, 20, 30, 40, 50] (mean 30.0)
#   and 20 unusable -> usable, w_0 = 0.75.
# Stratum 1: N_1 = 25, n_1 = 25, 4 usable indices [100, 200, 300, 400] and 21
#   unusable -> u_demand_1 = 4, which meets the default minimum 1, so the
#   stratum is usable at the default and w_1 = 0.25 contributes.
# demand_stratum_eligibility_coverage = 0.75 + 0.25 = 1.0 at the default.
# DemandPerAssetRaw at the default = (0.75 * 30.0 + 0.25 * 250.0) / 1.0 = 85.0,
#   the population-weighted mean of the two usable stratum means.
# DemandMedianRaw = weighted median of the 9 usable observations: weights 3.0
#   (stratum 0) and 1.0 (stratum 1); T = 19, half = 9.5; cumulative 3, 6, 9, 12
#   -> first value with cumulative >= 9.5 is 40.0.
DEMAND_PARTIAL_COVERAGE: CategoryMetricInput = make_category_input(
    (
        make_stratum(
            0,
            75,
            (
                make_observation(product_page_views=10),
                make_observation(product_page_views=20),
                make_observation(product_page_views=30),
                make_observation(product_page_views=40),
                make_observation(product_page_views=50),
            )
            + (make_observation(product_page_views=None),) * 20,
        ),
        make_stratum(
            1,
            25,
            (
                make_observation(product_page_views=100),
                make_observation(product_page_views=200),
                make_observation(product_page_views=300),
                make_observation(product_page_views=400),
            )
            + (make_observation(product_page_views=None),) * 21,
        ),
    ),
    category="demand-partial-coverage",
)

# ---------------------------------------------------------------------------
# DEMAND_EXPLICIT_ZERO — SRS-lean.md §7.2 (LREQ-MET-040, LREQ-MET-030)
# ---------------------------------------------------------------------------
#
# One stratum, N_h = 75, n_h = 10. Five observations carry the explicit valid
# product_page_views = 0 at DATE_70D (age_days_exact = 70.0), and five carry
# product_page_views = 10 at the same age. This is the "An explicit valid
# page-view value of zero is usable and yields an index of zero" case of SRS
# §7.2 (LREQ-MET-040): zero views are a usable observation whose index is 0.0,
# never a missing/unusable value.
#
#   index = product_page_views (D1-S2; plan §13):
#     five zero-view observations -> index_i = 0.0, all usable -> u_demand_h = 10,
#     NOT 5 (missing is not zero, SRS §1.2).
#     five ten-view observations -> index_i = 10.0.
#
# DemandPerAssetRaw = mean of the 5 + 5 usable indices (single stratum, so the
#   N_h / N weight renormalizes to itself) = (5 * 10.0 + 5 * 0.0) / 10 = 5.0.
# DemandMedianRaw: every usable observation weighs N_h / n_h = 75 / 10 = 7.5;
#   T = 10 * 7.5 = 75, half = 37.5. Sorted indices are 0.0 five times, then 10.0
#   five times; the cumulative weight AFTER the five zeros is 5 * 7.5 = 37.5,
#   exactly half, and a next sorted value (10.0) exists, so the exact-half branch
#   applies: (0.0 + 10.0) / 2 = 5.0.
# demand_stratum_eligibility_coverage = 75 / 75 = 1.0.
# usable_demand_sample_count = 10.
DEMAND_EXPLICIT_ZERO: CategoryMetricInput = make_category_input(
    (
        make_stratum(
            0,
            75,
            (make_observation(product_page_views=0),) * 5
            + (make_observation(product_page_views=10),) * 5,
        ),
    ),
    category="demand-explicit-zero",
)

# ---------------------------------------------------------------------------
# DEMAND_INELIGIBLE_EXCLUDED — plan §9.3 (LREQ-MET-040, LREQ-MET-030)
# ---------------------------------------------------------------------------
#
# One stratum, N_h = 75, n_h = 10:
#   5 usable observations give indices [10, 20, 30, 40, 50] (the weekly view
#     counts, chunk-28);
#   5 observations are ineligible per Chunk 7A and must not become zeros:
#     - negative page views (-10)
#     - missing page views (None)
#     - state = "draft"
#     - age below MIN_AGE_DAYS_FOR_RATE (DATE_29D, age 29.0 < 30)
#     - id_mapping_mismatch = True
# u_demand_h = 5 -> usable, w_0 = 75/75 = 1.0 (single stratum, N = 75).
# DemandPerAssetRaw = 1.0 * 30.0 / 1.0 = 30.0. Treating the five ineligible
# observations as zero would instead give 150/10 = 15.0, which is the bug this
# fixture guards against.
DEMAND_INELIGIBLE_EXCLUDED: CategoryMetricInput = make_category_input(
    (
        make_stratum(
            0,
            75,
            (
                make_observation(product_page_views=10),
                make_observation(product_page_views=20),
                make_observation(product_page_views=30),
                make_observation(product_page_views=40),
                make_observation(product_page_views=50),
                make_observation(product_page_views=-10),
                make_observation(product_page_views=None),
                make_observation(state=STATE_DRAFT),
                make_observation(
                    first_published_date_utc=DATE_29D,
                    product_page_views=100,
                ),
                make_observation(
                    id_mapping_mismatch=True,
                    product_page_views=100,
                ),
            ),
        ),
    ),
    category="demand-ineligible-excluded",
)

# ---------------------------------------------------------------------------
# RECENT_USABILITY_BOUNDARY — plan §9.3 (LREQ-MET-080)
# ---------------------------------------------------------------------------
#
# N_0 = N_1 = 50, n_0 = n_1 = 25, N = 100.
#   Stratum 0: 4 usable dates (ages 10, 20, 30, 40). The consuming floor-branch
#     test pins ``min_usable_samples_per_stratum = 5`` explicitly, so
#     u_recent_0 = 4 < 5 and the stratum is NOT usable for Recent Supply.
#   Stratum 1: 5 usable dates (ages 10..50), all inside the inclusive 365-day
#     window -> u_recent_1 = 5, usable, share_1 = 5/5 = 1.0.
# RecentShareRaw = (0.5 * 1.0) / 0.5 = 1.0 (renormalized over the one usable
#   stratum).
# recent_supply_stratum_eligibility_coverage = 50/100 = 0.5 (the unusable
#   stratum's population weight is excluded, not zeroed).
# usable_recent_supply_sample_count = 5.
RECENT_USABILITY_BOUNDARY: CategoryMetricInput = make_category_input(
    (
        make_stratum(
            0,
            50,
            (
                make_observation(first_published_date_utc=DATE_10D),
                make_observation(first_published_date_utc=DATE_20D),
                make_observation(first_published_date_utc=DATE_30D),
                make_observation(first_published_date_utc=DATE_40D),
            )
            + (make_observation(first_published_date_utc=None),) * 21,
        ),
        make_stratum(
            1,
            50,
            (
                make_observation(first_published_date_utc=DATE_10D),
                make_observation(first_published_date_utc=DATE_20D),
                make_observation(first_published_date_utc=DATE_30D),
                make_observation(first_published_date_utc=DATE_40D),
                make_observation(first_published_date_utc=DATE_50D),
            )
            + (make_observation(first_published_date_utc=None),) * 20,
        ),
    ),
    category="recent-usability-boundary",
)

# ---------------------------------------------------------------------------
# RECENT_MISSING_DATES — plan §9.3 (LREQ-MET-080)
# ---------------------------------------------------------------------------
#
# One stratum, N_h = 50, n_h = 25: 5 usable dates (ages 10, 20, 400, 500, 600)
# and 20 missing dates. u_recent_h = 5 (usable), so
#   stratum_recent_share_h = count(0 <= age <= 365) / u_recent_h = 2 / 5 = 0.4.
# The two in-window ages are 10 and 20; 400, 500, 600 are outside.
# If missing dates were treated as zero-numerator entries the share would be
# 2/25 = 0.08, which is the bug this fixture guards against.
# RecentShareRaw = 1.0 * 0.4 / 1.0 = 0.4; coverage = 50/50 = 1.0.
# MedianAgeRaw: weights N_h/n_h = 2.0; sorted ages 10, 20, 400, 500, 600, T = 10,
#   half = 5; cumulative 2, 4, 6 -> first value with cumulative >= 5 is 400.0
#   (the cumulative weight reaches exactly 4 after age 20, so age 20 is not at or
#   above half; there is no exact-half tie here).
RECENT_MISSING_DATES: CategoryMetricInput = make_category_input(
    (
        make_stratum(
            0,
            50,
            (
                make_observation(first_published_date_utc=DATE_10D),
                make_observation(first_published_date_utc=DATE_20D),
                make_observation(first_published_date_utc=DATE_400D),
                make_observation(first_published_date_utc=DATE_500D),
                make_observation(first_published_date_utc=DATE_600D),
            )
            + (make_observation(first_published_date_utc=None),) * 20,
        ),
    ),
    category="recent-missing-dates",
)

# ---------------------------------------------------------------------------
# Breadth vectors — plan §9.2 / §7.3 (LREQ-MET-070)
# ---------------------------------------------------------------------------
#
# ``(verified_total_count, distinct_canonical_discovered_count)`` with the
# hand-derived result.
BREADTH_VERIFIED_INPUT: BreadthMetricInput = make_breadth_input(1200, 1180)
# -> BreadthRaw = 1200, breadth_source = verified_total_count,
#    breadth_completeness_status = complete.

BREADTH_FALLBACK_INPUT: BreadthMetricInput = make_breadth_input(None, 250)
# -> BreadthRaw = 250, breadth_source = distinct_canonical_discovered_count,
#    breadth_completeness_status = incomplete_estimate.

BREADTH_VERIFIED_ZERO_INPUT: BreadthMetricInput = make_breadth_input(0, 0)
# -> BreadthRaw = 0, breadth_source = verified_total_count,
#    breadth_completeness_status = complete (a verified zero-result category).

#: ``(input, expected_breadth_raw, expected_source, expected_completeness)``.
BREADTH_INPUT_VECTORS: tuple[
    tuple[
        BreadthMetricInput,
        int,
        BreadthSource,
        BreadthCompletenessStatus,
    ],
    ...,
] = (
    (
        BREADTH_VERIFIED_INPUT,
        1200,
        BreadthSource.VERIFIED_TOTAL_COUNT,
        BreadthCompletenessStatus.COMPLETE,
    ),
    (
        BREADTH_FALLBACK_INPUT,
        250,
        BreadthSource.DISTINCT_CANONICAL_DISCOVERED_COUNT,
        BreadthCompletenessStatus.INCOMPLETE_ESTIMATE,
    ),
    (
        BREADTH_VERIFIED_ZERO_INPUT,
        0,
        BreadthSource.VERIFIED_TOTAL_COUNT,
        BreadthCompletenessStatus.COMPLETE,
    ),
)
