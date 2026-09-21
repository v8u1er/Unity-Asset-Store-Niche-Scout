"""Golden vectors and builders for Chunk 8 normalization and primary scoring.

Data only: explicit constants, inert golden-vector tables, and small
keyword-argument builders. There are no assertions here; the expectations live in
``tests/test_scoring.py``.

Every expected value below is hand-derived from the SRS formulas (never copied
from the implementation). The derivation of each vector is written next to it:

* Leave-one-out reference: ``reference_size = category_count - 1``; the target is
  excluded from every field tuple; each field tuple holds the non-null peer values
  in input order — SRS-lean.md §8.1 (LREQ-NRM-010, LREQ-NRM-020).
* Midrank ``P_ref(x) = (L + 0.5 * E) / m`` with ``L = count(r < x)`` and
  ``E = count(r == x)`` — SRS-lean.md §8.1 (LREQ-NRM-030).
* ``D0 = 0.60 * P_ref(DemandPerAssetRaw) + 0.40 * P_ref(DemandMedianRaw)`` and
  ``D = clamp(0.5 + demand_coverage * (D0 - 0.5), 0, 1)`` — SRS-lean.md §8.2
  (LREQ-SCR-010).
* ``C = clamp(1 - P_ref(BreadthRaw), 0, 1)``, available only with verified and
  complete breadth — SRS-lean.md §8.2 (LREQ-SCR-020).
* ``Rpressure0 = 0.70 * P_ref(RecentShareRaw) + 0.30 * (1 - P_ref(MedianAgeRaw))``,
  ``R0 = 1 - Rpressure0``, ``R = clamp(0.5 + recent_coverage * (R0 - 0.5), 0, 1)``
  — SRS-lean.md §8.2 (LREQ-SCR-030).
* ``Q0 = 1 - P_ref(QualityRaw)``,
  ``Q = clamp(0.5 + quality_coverage * (Q0 - 0.5), 0, 1)`` — SRS-lean.md §8.2
  (LREQ-SCR-040).
* ``W_A = sum(weights of available components)``,
  ``market_opportunity_score = clamp(0.5 + W_A * (S_available - 0.5), 0, 1)`` when
  at least two components are available, else ``None`` — SRS-lean.md §8.3
  (LREQ-SCR-060).
* A sample-derived ``D``/``R``/``Q`` whose stratum eligibility coverage is
  strictly below ``MIN_REQUIRED_COMPONENT_COVERAGE`` is unavailable and receives no
  composite weight — SRS-lean.md §7.5 / §9.1 (plan §5).

``CategoryRawMetrics`` and ``RawMetricBundle`` come from the frozen Chunk 7B
interface (``interfaces/chunk-7B.md``). They are constructed directly here, so
this module depends only on the Chunk 0/7B types that already exist; the Chunk 8
names under test are imported by ``tests/test_scoring.py`` alone. No network, no
credentials, and no clock reads: every value below is an explicit literal.
"""

from __future__ import annotations

from niche_scout.metrics import CategoryRawMetrics, RawMetricBundle
from niche_scout.models import (
    STRONG_REFERENCE_CATEGORY_COUNT,
    BreadthCompletenessStatus,
    BreadthSource,
    PageViewSemanticsStatus,
)

__all__ = [
    "BALANCED_POLICY_WEIGHTS",
    "BREADTH_COUNTS_EIGHT_RUN",
    "COMPETITION_VECTORS",
    "COMPOSITE_COMPONENT_OBJECTS",
    "COMPOSITE_VECTORS",
    "D_BOTH_SUBSIGNAL_VECTORS",
    "D_CONTRADICTED_VECTORS",
    "D_ONLY_SUBSIGNAL_EXPECTED",
    "D_THRESHOLD_VECTORS",
    "DEMAND_BOTH_NORMALIZED",
    "DEMAND_ONLY_NORMALIZED",
    "EIGHT_CATEGORY_RUN",
    "FIELD_USABLE_COUNT_CATEGORY",
    "FIELD_USABLE_COUNT_RUN",
    "FIELD_USABLE_COUNT_VECTORS",
    "FIXED_PRIMARY_WEIGHTS",
    "FULL_COMPONENT_NORMALIZED",
    "MIDRANK_DUPLICATE_VECTOR",
    "MIDRANK_GOLDEN_VECTORS",
    "MIDRANK_INVALID_VECTORS",
    "MIDRANK_EXPLICIT_ZERO_EXPECTED",
    "NORMALIZE_INDEPENDENT_EXPECTED",
    "NORMALIZE_INDEPENDENT_RAW",
    "NORMALIZE_MIXED_EXPECTED",
    "NORMALIZE_MIXED_RAW",
    "NORMALIZE_NULL_EXPECTED",
    "NORMALIZE_NULL_RAW",
    "NORMALIZE_REFERENCE_TUPLES",
    "PAGE_VIEW_SEMANTICS_CONTRADICTED",
    "PAGE_VIEW_SEMANTICS_UNVALIDATED",
    "Q_NULL_QUALITY_VECTORS",
    "Q_SHRINKAGE_VECTORS",
    "Q_THRESHOLD_VECTORS",
    "R_BOTH_SUBSIGNAL_VECTORS",
    "R_ONE_SUBSIGNAL_VECTORS",
    "R_THRESHOLD_VECTORS",
    "RECENT_BOTH_NORMALIZED",
    "REFERENCE_SIZE_VECTORS",
    "SCORE_CATEGORY_EXPECTED",
    "SCORE_CATEGORY_RUN",
    "SCORE_CATEGORY_TARGET",
    "SINGLE_CATEGORY_RUN",
    "STRONG_CATEGORY",
    "STRONG_REFERENCE_EXPECTED_DEMAND",
    "TWENTY_ONE_CATEGORY_RUN",
    "make_category_raw_metrics",
    "make_raw_bundle",
    "near",
]


def make_raw_bundle(
    *,
    demand_per_asset_raw: float | None = None,
    demand_median_raw: float | None = None,
    breadth_raw: float | None = None,
    recent_share_raw: float | None = None,
    median_age_raw: float | None = None,
    quality_raw: float | None = None,
) -> RawMetricBundle:
    """Build one ``RawMetricBundle`` with explicit keyword fields.

    ``None`` (the default) means unavailable and is never a zero; ``0.0`` is an
    explicit valid value (SRS-lean.md §1.2 / interfaces/chunk-7A.md §4.2).
    """
    return RawMetricBundle(
        demand_per_asset_raw=demand_per_asset_raw,
        demand_median_raw=demand_median_raw,
        breadth_raw=breadth_raw,
        recent_share_raw=recent_share_raw,
        median_age_raw=median_age_raw,
        quality_raw=quality_raw,
    )


def make_category_raw_metrics(
    category: str,
    raw: RawMetricBundle,
    *,
    demand_stratum_eligibility_coverage: float = 1.0,
    recent_supply_stratum_eligibility_coverage: float = 1.0,
    quality_stratum_eligibility_coverage: float = 1.0,
    usable_demand_sample_count: int = 0,
    usable_recent_supply_sample_count: int = 0,
    usable_quality_sample_count: int = 0,
    breadth_source: BreadthSource = BreadthSource.VERIFIED_TOTAL_COUNT,
    breadth_completeness_status: BreadthCompletenessStatus = (
        BreadthCompletenessStatus.COMPLETE
    ),
) -> CategoryRawMetrics:
    """Build one ``CategoryRawMetrics`` (frozen Chunk 7B interface).

    The coverage and provenance defaults describe the ordinary "everything
    verified and fully covered" category so a fixture only states what it means to
    vary. Usable counts default to ``0`` because Chunk 8 never reads them
    (LREQ-NRM-020's counts are computed per reference, not per category).
    """
    return CategoryRawMetrics(
        category=category,
        raw=raw,
        demand_stratum_eligibility_coverage=demand_stratum_eligibility_coverage,
        recent_supply_stratum_eligibility_coverage=(
            recent_supply_stratum_eligibility_coverage
        ),
        quality_stratum_eligibility_coverage=quality_stratum_eligibility_coverage,
        usable_demand_sample_count=usable_demand_sample_count,
        usable_recent_supply_sample_count=usable_recent_supply_sample_count,
        usable_quality_sample_count=usable_quality_sample_count,
        breadth_source=breadth_source,
        breadth_completeness_status=breadth_completeness_status,
    )


def near(
    actual: float | None, expected: float | None, *, abs_tol: float = 1e-9
) -> bool:
    """Return whether ``actual`` equals ``expected`` within the 1e-9 tolerance.

    Fixtures are inert data and import no ``pytest``. The scoring tests use
    ``pytest.approx``; this helper exists only for the few fixture-table loops that
    compare two ``None``-able floats without a per-case expected/value pairing.
    """
    if actual is None or expected is None:
        return actual is None and expected is None
    return abs(actual - expected) <= abs_tol


# ---------------------------------------------------------------------------
# Vocabulary fixtures
# ---------------------------------------------------------------------------

PAGE_VIEW_SEMANTICS_UNVALIDATED: PageViewSemanticsStatus = (
    PageViewSemanticsStatus.UNVALIDATED
)
PAGE_VIEW_SEMANTICS_CONTRADICTED: PageViewSemanticsStatus = (
    PageViewSemanticsStatus.CONTRADICTED
)

#: The fixed Lean v1 primary weights, in the frozen key spelling of
#: ``models.SENSITIVITY_POLICIES`` (SRS-lean.md §8.3; plan §4.5).
FIXED_PRIMARY_WEIGHTS: dict[str, float] = {
    "D": 0.35,
    "C": 0.30,
    "R": 0.20,
    "Q": 0.15,
}

#: ``models.SENSITIVITY_POLICIES["balanced"]`` (SRS-lean.md §8.3/§14).
BALANCED_POLICY_WEIGHTS: dict[str, float] = {
    "D": 0.35,
    "C": 0.30,
    "R": 0.20,
    "Q": 0.15,
}

# ---------------------------------------------------------------------------
# Midrank golden vectors (SRS-lean.md §8.1, LREQ-NRM-030)
# ---------------------------------------------------------------------------
#
# ``P_ref(x) = (L + 0.5 * E) / m`` with ``L = count(r_k < x)``,
# ``E = count(r_k == x)``, ``m = len(reference)``. Each derivation below shows the
# counts and the quotient written as a comment.

MIDRANK_GOLDEN_VECTORS: tuple[
    tuple[str, float | None, tuple[float, ...], float | None], ...
] = (
    # target 2.0; reference 1, 2, 3: L = 1 (1.0), E = 1 (2.0), m = 3
    # -> (1 + 0.5) / 3 = 1.5 / 3 = 0.5.
    ("middle_of_three", 2.0, (1.0, 2.0, 3.0), 0.5),
    # target 1.0; reference 1, 1, 3: L = 0, E = 2, m = 3
    # -> (0 + 1.0) / 3 = 1/3.
    ("tie_pair_at_minimum", 1.0, (1.0, 1.0, 3.0), 1.0 / 3.0),
    # target 1.0; reference 2, 3, 4: L = 0, E = 0, m = 3 -> 0/3 = 0.0 (minimum).
    ("below_every_reference_value", 1.0, (2.0, 3.0, 4.0), 0.0),
    # target 4.0; reference 1, 2, 3: L = 3, E = 0, m = 3 -> 3/3 = 1.0 (maximum).
    ("above_every_reference_value", 4.0, (1.0, 2.0, 3.0), 1.0),
    # target 5.0; all-equal reference 2, 2, 2: L = 3, E = 0, m = 3 -> 1.0.
    ("all_equal_reference_target_above", 5.0, (2.0, 2.0, 2.0), 1.0),
    # target 2.0; all-equal reference 2, 2, 2: L = 0, E = 3, m = 3
    # -> (0 + 1.5) / 3 = 0.5.
    ("all_equal_reference_target_equal", 2.0, (2.0, 2.0, 2.0), 0.5),
    # target 2.0; reference 1, 1, 1, 3, 3, 3: L = 3, E = 0, m = 6 -> 3/6 = 0.5.
    ("two_clusters_target_between", 2.0, (1.0, 1.0, 1.0, 3.0, 3.0, 3.0), 0.5),
    # null target -> None regardless of the reference.
    ("null_target_with_reference", None, (1.0,), None),
    # empty usable reference (m = 0) -> None regardless of the target.
    ("value_with_empty_reference", 1.0, (), None),
)

#: Non-finite ``target`` or ``reference_values`` element -> ``ValueError``
#: (caller breach; plan §5 D4, mirroring ``metrics.weighted_median``).
MIDRANK_INVALID_VECTORS: tuple[tuple[str, float | None, tuple[float, ...]], ...] = (
    ("nan_target", float("nan"), (1.0, 2.0, 3.0)),
    ("infinite_target", float("inf"), (1.0, 2.0, 3.0)),
    ("negative_infinite_target", float("-inf"), (1.0, 2.0, 3.0)),
    ("nan_reference_element", 1.0, (float("nan"), 2.0)),
    ("infinite_reference_element", 1.0, (1.0, float("inf"))),
)

#: Duplicate reference values stay repeated and count in ``m`` (plan §5):
#: target 2.0; reference 1, 2, 2, 2: L = 1, E = 3, m = 4
#: -> (1 + 1.5) / 4 = 2.5 / 4 = 0.625.
MIDRANK_DUPLICATE_VECTOR: tuple[float, tuple[float, ...], float] = (
    2.0,
    (1.0, 2.0, 2.0, 2.0),
    0.625,
)

# ---------------------------------------------------------------------------
# Single-category and multi-category runs (LREQ-NRM-010, LREQ-NRM-020)
# ---------------------------------------------------------------------------

#: Plan §9: a one-category run leaves an empty LOO reference: ``reference_size``
#: is ``1 - 1 = 0`` and every field usable count is ``0``.
SINGLE_CATEGORY_RUN: tuple[CategoryRawMetrics, ...] = (
    make_category_raw_metrics(
        "c-0",
        make_raw_bundle(
            demand_per_asset_raw=1.0,
            demand_median_raw=1.0,
            breadth_raw=1.0,
            recent_share_raw=1.0,
            median_age_raw=1.0,
            quality_raw=1.0,
        ),
    ),
)

#: Plan §9: 21 categories qualifies for the strong-reference policy, so each
#: target has ``21 - 1 = 20`` leave-one-out peers, never 21. Target ``"c-10"``
#: has ``demand_per_asset_raw = 10.0`` and the reference tuple is
#: ``(0.0..9.0, 11.0..20.0)``: ``P_ref(10.0) = (L + 0.5 * E) / m`` with L = 10,
#: E = 0, m = 20 -> 10/20 = 0.5. Every other field is a constant so the other
#: normalizations stay trivially predictable.
STRONG_CATEGORY = "c-10"

NUMERIC_REFERENCE_ROWS: int = STRONG_REFERENCE_CATEGORY_COUNT

TWENTY_ONE_CATEGORY_RUN: tuple[CategoryRawMetrics, ...] = tuple(
    make_category_raw_metrics(
        f"c-{index}",
        make_raw_bundle(
            demand_per_asset_raw=float(index),
            demand_median_raw=5.0,
            breadth_raw=5.0,
            recent_share_raw=5.0,
            median_age_raw=5.0,
            quality_raw=5.0,
        ),
    )
    for index in range(STRONG_REFERENCE_CATEGORY_COUNT)
)

#: The 20 peers of ``"c-10"``: ``(0.0..9.0, 11.0..20.0)`` (the target 10.0 is
#: excluded). Used as the expected reference tuple and as the direct ``midrank``
#: reference for the same expected ``0.5``.
STRONG_REFERENCE_EXPECTED_DEMAND: tuple[float, ...] = tuple(
    float(index) for index in range(STRONG_REFERENCE_CATEGORY_COUNT) if index != 10
)

#: Breadth values for the 8-category run; target ``COMPONENT_COUNT_CATEGORY``
#: ("c-3", breadth 40.0) is against peers ``(0.0, 10.0, 20.0, 50.0, 70.0, 90.0,
#: 100.0)``: L = 3 (< 40), E = 0, m = 7 -> ``P_ref = 3/7``; the remaining three
#: normalizations equal ``P_ref`` itself because the raw field is constant 5.0
#: (``L = 0, E = 7, m = 7 -> 3.5/7 = 0.5``).
BREADTH_COUNTS_EIGHT_RUN: tuple[float, ...] = (
    10.0,
    100.0,
    20.0,
    40.0,
    50.0,
    0.0,
    90.0,
    70.0,
)

#: Plan §9: 8 categories -> every target has ``8 - 1 = 7`` peers.
EIGHT_CATEGORY_RUN: tuple[CategoryRawMetrics, ...] = tuple(
    make_category_raw_metrics(
        f"c-{index}",
        make_raw_bundle(
            demand_per_asset_raw=float(index),
            demand_median_raw=5.0,
            breadth_raw=BREADTH_COUNTS_EIGHT_RUN[index],
            recent_share_raw=5.0,
            median_age_raw=5.0,
            quality_raw=5.0,
        ),
    )
    for index in range(8)
)

#: Plan §9 field-usable-count fixture: an 8-category run where two peers of
#: target ``"c-3"`` carry ``quality_raw = None``. The reference size is 7, the
#: quality usable count is 7 - 2 = 5, and every other field keeps 7.
FIELD_USABLE_COUNT_CATEGORY: str = "c-3"
FIELD_USABLE_COUNT_QUALITY_NULL_INDICES: tuple[int, ...] = (0, 6)

FIELD_USABLE_COUNT_RUN: tuple[CategoryRawMetrics, ...] = tuple(
    make_category_raw_metrics(
        f"c-{index}",
        make_raw_bundle(
            demand_per_asset_raw=float(index),
            demand_median_raw=float(index),
            breadth_raw=float(index),
            recent_share_raw=float(index),
            median_age_raw=float(index),
            quality_raw=(
                None
                if index in FIELD_USABLE_COUNT_QUALITY_NULL_INDICES
                else float(index)
            ),
        ),
    )
    for index in range(8)
)

#: ``(description, run, target category, expected reference size, expected
#: quality count, expected other-field count)`` for the four cases. The run is
#: the second element so the test can call ``leave_one_out_reference(run,
#: category)`` without any name-to-run lookup table.
FIELD_USABLE_COUNT_VECTORS: tuple[
    tuple[str, tuple[CategoryRawMetrics, ...], str, int, int, int], ...
] = (
    ("single_category_run", SINGLE_CATEGORY_RUN, "c-0", 0, 0, 0),
    ("eight_category_run", EIGHT_CATEGORY_RUN, "c-3", 7, 7, 7),
    ("eight_category_run_quality_nulls", FIELD_USABLE_COUNT_RUN, "c-3", 7, 5, 7),
    ("twenty_one_category_run", TWENTY_ONE_CATEGORY_RUN, "c-10", 20, 20, 20),
)

#: ``(run, category, expected reference size)`` pairs the reference-size test
#: iterates: the 8-category run gives 7 peers, the 21-category run gives 20
#: (never 21), and the one-category run gives 0.
REFERENCE_SIZE_VECTORS: tuple[
    tuple[str, tuple[CategoryRawMetrics, ...], str, int], ...
] = (
    ("eight_category_run", EIGHT_CATEGORY_RUN, "c-3", 7),
    ("twenty_one_category_run", TWENTY_ONE_CATEGORY_RUN, STRONG_CATEGORY, 20),
)

# ---------------------------------------------------------------------------
# Field-specific normalization (SRS-lean.md §8.1, LREQ-NRM-040)
# ---------------------------------------------------------------------------
#
# Each case below states the raw bundle, the (reference_size, per-field peer value
# tuples, per-field usable counts), and the six expected normalized values. All
# six fields are normalized independently: there is no log transform and no
# cross-field influence (strictly monotone transforms do not change midrank
# ordering).

#: ``raw`` with all six fields populated distinctly; reference (m = 5) values are
#: ``(1.0, 2.0, 3.0, 4.0, 5.0)`` for every field, as built below.
NORMALIZE_INDEPENDENT_RAW: RawMetricBundle = make_raw_bundle(
    demand_per_asset_raw=3.0,
    demand_median_raw=6.0,
    breadth_raw=-1.0,
    recent_share_raw=1.0,
    median_age_raw=9.0,
    quality_raw=4.0,
)

#: Reference field tuples ``(1.0, 2.0, 3.0, 4.0, 5.0)`` (m = 5) for all six
#: fields.
NORMALIZE_REFERENCE_TUPLES: tuple[float, ...] = (1.0, 2.0, 3.0, 4.0, 5.0)

#: Derivation of each field against ``(1, 2, 3, 4, 5)`` (m = 5):
#: * demand_per_asset_raw = 3.0: L = 2, E = 1 -> (2 + 0.5) / 5 = 0.5.
#: * demand_median_raw = 6.0: L = 5, E = 0 -> 5/5 = 1.0.
#: * breadth_raw = -1.0: L = 0, E = 0 -> 0/5 = 0.0.
#: * recent_share_raw = 1.0: L = 0, E = 1 -> 0.5/5 = 0.1.
#: * median_age_raw = 9.0: L = 5, E = 0 -> 1.0.
#: * quality_raw = 4.0: L = 3, E = 1 -> 3.5/5 = 0.7.
NORMALIZE_INDEPENDENT_EXPECTED: tuple[float, ...] = (0.5, 1.0, 0.0, 0.1, 1.0, 0.7)

#: Midrank of the explicit valid zero against ``(0.0, 1.0, 2.0)``: L = 0, E = 1,
#: m = 3 -> 0.5/3 = 1/6 (missing is not zero: a zero here is a value).
MIDRANK_EXPLICIT_ZERO_EXPECTED: float = 1.0 / 6.0

#: Null-target case: ``raw`` has ``quality_raw = None`` and every other field set;
#: the reference has an empty ``quality_raw`` tuple (m = 0). Both the null raw and
#: the empty reference yield ``None`` for that field. The other five fields use the
#: same reference ``(1, 2, 3, 4, 5)`` with the raw 5.0, so each gives
#: L = 4, E = 1 -> 4.5/5 = 0.9.
NORMALIZE_NULL_RAW: RawMetricBundle = make_raw_bundle(
    demand_per_asset_raw=5.0,
    demand_median_raw=5.0,
    breadth_raw=5.0,
    recent_share_raw=5.0,
    median_age_raw=5.0,
    quality_raw=None,
)

NORMALIZE_NULL_EXPECTED: tuple[float | None, ...] = (0.9, 0.9, 0.9, 0.9, 0.9, None)

#: Mixed availability: ``demand_median_raw = 6.0`` is above all five peers
#: (L = 5 -> 1.0) and ``breadth_raw = None`` stays null; the rest are 0.9 (raw 5.0
#: -> (4 + 0.5)/5).
NORMALIZE_MIXED_RAW: RawMetricBundle = make_raw_bundle(
    demand_per_asset_raw=5.0,
    demand_median_raw=6.0,
    breadth_raw=None,
    recent_share_raw=5.0,
    median_age_raw=5.0,
    quality_raw=5.0,
)

NORMALIZE_MIXED_EXPECTED: tuple[float | None, ...] = (0.9, 1.0, None, 0.9, 0.9, 0.9)

# ---------------------------------------------------------------------------
# Component vectors (SRS-lean.md §8.2; threshold SRS-lean.md §7.5/§9.1)
# ---------------------------------------------------------------------------
#
# ``ComponentValues`` instances built literally — a fixture may construct the
# dataclass directly, and it keeps the expected component values in the test body
# independent of the component functions under test.

#: ``D = 0.8, C = 0.6, R = 0.4, Q = 0.2`` (plan §9 composite vector).
COMPONENT_D: float = 0.8
COMPONENT_C: float = 0.6
COMPONENT_R: float = 0.4
COMPONENT_Q: float = 0.2

# ---------------------------------------------------------------------------
# Midrank inputs for the component vectors, and the component vectors themselves
# ---------------------------------------------------------------------------
#
# The component functions consume ``NormalizedValues`` (six null-able midranks),
# never raw values. Each ``NormalizedValues`` instance below states, in a comment,
# the field midrank it encodes. ``normalized_with`` is the builder; the module
# keeps the dataclass import local so the fixture module still imports cleanly
# before the Chunk 8 implementation lands.

# -- D: LREQ-SCR-010 --------------------------------------------------------

#: ``D`` both-sub-signal midrank inputs (``a = 1.0``, ``b = 0.0``) and the
#: ``(coverage, expected D)`` pairs the shrinkage test iterates:
#: ``D0 = 0.60 * 1.0 + 0.40 * 0.0 = 0.6``.
#: * coverage 1.0: ``D = 0.5 + 1.0 * (0.6 - 0.5) = 0.6``.
#: * coverage 0.5 (the available boundary): ``D = 0.5 + 0.5 * 0.1 = 0.55``.
#: Coverage strictly below ``MIN_REQUIRED_COMPONENT_COVERAGE`` (0.50) is
#: unavailable before shrinkage (SRS §7.5 / §9.1; plan §5 Q1); the ``0.49 ->
#: None`` case lives in ``D_THRESHOLD_VECTORS``.
D_BOTH_SUBSIGNAL_VECTORS: tuple[tuple[str, float, float], ...] = (
    ("coverage_one", 1.0, 0.6),
    ("coverage_half", 0.5, 0.55),
)

#: ``D`` one-sub-signal input: only ``a = 0.8`` is available; ``D0`` is that value
#: directly (plan §5: weighting the single term by its renormalized subweight gives
#: the same value, plan §12 D7). coverage 1.0 -> ``D = 0.5 + 1.0 * 0.3 = 0.8``.
D_ONLY_SUBSIGNAL_EXPECTED: float = 0.8

# -- C: LREQ-SCR-020 --------------------------------------------------------

#: ``C`` vectors: ``(description, P_ref(BreadthRaw), breadth_source,
#: breadth_completeness_status, expected)``.
#: * P_ref = 0.25, verified + complete -> ``1 - 0.25 = 0.75``.
#: * P_ref = 0.25 with the fallback source -> ``None`` (unverified breadth).
#: * P_ref = 0.25, complete status but fallback source -> ``None``.
#: * explicit zero breadth P_ref = 0.0, verified + complete -> ``1 - 0.0 = 1.0``.
#: * P_ref = None -> ``None`` (empty usable reference).
COMPETITION_SOURCE_VERIFIED: BreadthSource = BreadthSource.VERIFIED_TOTAL_COUNT
COMPETITION_SOURCE_FALLBACK: BreadthSource = (
    BreadthSource.DISTINCT_CANONICAL_DISCOVERED_COUNT
)

COMPETITION_VECTORS: tuple[
    tuple[str, float | None, BreadthSource, BreadthCompletenessStatus, float | None],
    ...,
] = (
    (
        "verified_complete_quarter",
        0.25,
        COMPETITION_SOURCE_VERIFIED,
        BreadthCompletenessStatus.COMPLETE,
        0.75,
    ),
    (
        "fallback_source_incomplete",
        0.25,
        COMPETITION_SOURCE_FALLBACK,
        BreadthCompletenessStatus.INCOMPLETE_ESTIMATE,
        None,
    ),
    (
        "fallback_source_complete_status",
        0.25,
        COMPETITION_SOURCE_FALLBACK,
        BreadthCompletenessStatus.COMPLETE,
        None,
    ),
    (
        "verified_but_incomplete_status",
        0.25,
        COMPETITION_SOURCE_VERIFIED,
        BreadthCompletenessStatus.INCOMPLETE_ESTIMATE,
        None,
    ),
    (
        "verified_complete_explicit_zero_breadth",
        0.0,
        COMPETITION_SOURCE_VERIFIED,
        BreadthCompletenessStatus.COMPLETE,
        1.0,
    ),
    (
        "verified_complete_null_midrank",
        None,
        COMPETITION_SOURCE_VERIFIED,
        BreadthCompletenessStatus.COMPLETE,
        None,
    ),
)

# -- R: LREQ-SCR-030 --------------------------------------------------------

#: ``R`` both-sub-signal midrank inputs (``s = 0.9``, ``a = 0.2``) and the
#: ``(coverage, expected R)`` pairs:
#: ``Rpressure0 = 0.70 * 0.9 + 0.30 * (1 - 0.2) = 0.63 + 0.24 = 0.87``;
#: ``R0 = 1 - 0.87 = 0.13``.
#: * coverage 1.0: ``R = 0.5 + 1.0 * (0.13 - 0.5) = 0.13``.
#: * coverage 0.5 (the available boundary): ``R = 0.5 + 0.5 * (-0.37) = 0.315``.
#: Coverage strictly below ``MIN_REQUIRED_COMPONENT_COVERAGE`` (0.50) is
#: unavailable before shrinkage (SRS §7.5 / §9.1; plan §5 Q1); the ``0.49 ->
#: None`` case lives in ``R_THRESHOLD_VECTORS``.
R_BOTH_SUBSIGNAL_VECTORS: tuple[tuple[str, float, float], ...] = (
    ("coverage_one", 1.0, 0.13),
    ("coverage_half", 0.5, 0.315),
)

#: ``R`` one-sub-signal vectors: ``(description, s_or_None, age_or_None, coverage,
#: expected)``.
#: * only share ``s = 0.9``: ``Rpressure0 = 0.9`` -> ``R0 = 0.1``; at coverage
#:   1.0 -> ``R = 0.1``.
#: * only age ``a = 0.2``: ``Rpressure0 = 1 - 0.2 = 0.8`` -> ``R0 = 0.2``; at
#:   coverage 1.0 -> ``R = 0.2``.
#: * neither -> ``None``.
R_ONE_SUBSIGNAL_VECTORS: tuple[
    tuple[str, float | None, float | None, float, float | None], ...
] = (
    ("only_recent_share", 0.9, None, 1.0, 0.1),
    ("only_median_age", None, 0.2, 1.0, 0.2),
    ("neither_sub_signal", None, None, 1.0, None),
)

# -- Q: LREQ-SCR-040 --------------------------------------------------------

#: ``Q`` vectors: ``(description, P_ref(QualityRaw), coverage, expected)``.
#: * P_ref = 0.4 -> ``Q0 = 1 - 0.4 = 0.6``; coverage 1.0 -> ``0.6``; coverage 0.5
#:   -> ``0.55``; coverage 0.49 -> ``None``.
#: * P_ref = 1.0 -> ``Q0 = 0.0``; coverage 1.0 -> ``0.0`` (explicit valid zero).
#: * P_ref = 0.0 -> ``Q0 = 1.0``; coverage 1.0 -> ``1.0``.
#: * P_ref = None -> ``None`` (independent of coverage).
Q_SHRINKAGE_VECTORS: tuple[tuple[str, float | None, float, float | None], ...] = (
    ("coverage_one", 0.4, 1.0, 0.6),
    ("coverage_boundary", 0.4, 0.5, 0.55),
    ("coverage_below_threshold", 0.4, 0.49, None),
    ("zero_quality_component", 1.0, 1.0, 0.0),
    ("one_quality_component", 0.0, 1.0, 1.0),
)

Q_NULL_QUALITY_VECTORS: tuple[tuple[str, float | None, float], ...] = (
    ("null_midrank_coverage_one", None, 1.0),
    ("null_midrank_coverage_half", None, 0.5),
)

# ---------------------------------------------------------------------------
# Below-threshold unavailability vectors (SRS-lean.md §7.5 / §9.1; plan §5)
# ---------------------------------------------------------------------------

#: ``(description, coverage, expected available)`` for ``D`` at fixed
#: ``a = 1.0, b = 0.0`` (``D0 = 0.6``): 0.49 -> unavailable, 0.50 -> available
#: boundary, 0.75 -> available.
D_THRESHOLD_VECTORS: tuple[tuple[str, float, float | None], ...] = (
    ("below_threshold_demand", 0.49, None),
    ("boundary_threshold_demand", 0.50, 0.55),
    ("above_threshold_demand", 0.75, 0.575),
)

#: ``(description, coverage, expected available)`` for ``R`` at fixed
#: ``s = 0.9, a = 0.2`` (``R0 = 0.13``): 0.49 -> unavailable, 0.50 -> available
#: boundary (``0.5 + 0.5 * (-0.37) = 0.315``), 0.75 -> ``0.2225``.
R_THRESHOLD_VECTORS: tuple[tuple[str, float, float | None], ...] = (
    ("below_threshold_recent", 0.49, None),
    ("boundary_threshold_recent", 0.50, 0.315),
    ("above_threshold_recent", 0.75, 0.2225),
)

#: ``(description, coverage, expected available)`` for ``Q`` at fixed
#: ``P_ref(QualityRaw) = 0.4`` (``Q0 = 0.6``): 0.49 -> unavailable, 0.50 ->
#: available boundary (``0.55``).
Q_THRESHOLD_VECTORS: tuple[tuple[str, float, float | None], ...] = (
    ("below_threshold_quality", 0.49, None),
    ("boundary_threshold_quality", 0.50, 0.55),
)

# ---------------------------------------------------------------------------
# Contradicted page-view semantics (SRS-lean.md §8.2, LREQ-SCR-050)
# ---------------------------------------------------------------------------
#
# Full four-component input: a = 1.0, b = 0.0 (D0 = 0.6); breadth midrank 0.25
# (C = 0.75); s = 0.9, a = 0.2 (R0 = 0.13); quality midrank 0.4 (Q0 = 0.6).
# At coverage 1.0 that gives D = 0.6, C = 0.75, R = 0.13, Q = 0.6 whether the
# page-view status is UNVALIDATED or CONTRADICTED — except that CONTRADICTED
# replaces D and Q with ``None`` and leaves C and R untouched.

D_CONTRADICTED_VECTORS: tuple[tuple[str, PageViewSemanticsStatus], ...] = (
    ("unvalidated_keeps_all_four", PAGE_VIEW_SEMANTICS_UNVALIDATED),
    ("contradicted_drops_d_and_q", PAGE_VIEW_SEMANTICS_CONTRADICTED),
)

# ---------------------------------------------------------------------------
# Composite vectors (SRS-lean.md §8.3, LREQ-SCR-060)
# ---------------------------------------------------------------------------
#
# All arithmetic is done from ``models.W_D/W_C/W_R/W_Q = 0.35/0.30/0.20/0.15``:
#   W_A = sum of available weights
#   S_available = sum(w_x * x) / W_A
#   score = clamp(0.5 + W_A * (S_available - 0.5), 0, 1)
#   state = available (4 components) / partial (2-3) / unavailable (< 2)
#
# ``(description, components, expected score, expected available weight)``. The
# component tuples are ``(D, C, R, Q)``.

#: All four: W_A = 0.35 + 0.30 + 0.20 + 0.15 = 1.0.
#: S = (0.35*0.8 + 0.30*0.6 + 0.20*0.4 + 0.15*0.2) / 1.0
#:   = (0.28 + 0.18 + 0.08 + 0.03) / 1.0 = 0.57; score = 0.5 + 1.0*(0.57-0.5) = 0.57.
COMPOSITE_FOUR_AVAILABLE: tuple[float, float, float, float] = (0.8, 0.6, 0.4, 0.2)

#: Drop Q: W_A = 0.35 + 0.30 + 0.20 = 0.85.
#: S = (0.28 + 0.18 + 0.08) / 0.85 = 0.54 / 0.85 = 0.6352941176470588...
#: score = 0.5 + 0.85 * (0.6352941176470588 - 0.5) = 0.5 + 0.85 * 0.1352941176470588
#:       = 0.5 + 0.115 = 0.615.
COMPOSITE_THREE_AVAILABLE: tuple[float, float, float, None] = (0.8, 0.6, 0.4, None)

#: Drop R and Q: W_A = 0.35 + 0.30 = 0.65.
#: S = (0.28 + 0.18) / 0.65 = 0.46 / 0.65 = 0.7076923076923077...
#: score = 0.5 + 0.65 * (0.7076923076923077 - 0.5) = 0.5 + 0.65 * 0.2076923076923077
#:       = 0.5 + 0.135 = 0.635.
COMPOSITE_TWO_AVAILABLE: tuple[float, float, None, None] = (0.8, 0.6, None, None)

#: The D + Q pair: W_A = 0.35 + 0.15 = 0.50.
#: S = (0.35*1.0 + 0.15*0.0) / 0.50 = 0.35 / 0.50 = 0.7.
#: score = 0.5 + 0.50 * (0.7 - 0.5) = 0.5 + 0.10 = 0.6.
COMPOSITE_D_Q_PAIR: tuple[float, None, None, float] = (1.0, None, None, 0.0)

#: Only D: one component -> ``None`` score and ``unavailable`` state.
COMPOSITE_ONE_AVAILABLE: tuple[float, None, None, None] = (0.8, None, None, None)

#: No components at all.
COMPOSITE_NONE_AVAILABLE: tuple[None, None, None, None] = (None, None, None, None)

#: Low-coverage D excluded from W_A (SRS-lean.md §7.5/§9.1): demand coverage 0.49
#: makes D unavailable, leaving C = 0.6, R = 0.4, Q = 0.2.
#: W_A = 0.30 + 0.20 + 0.15 = 0.65.
#: S = (0.30*0.6 + 0.20*0.4 + 0.15*0.2) / 0.65 = (0.18 + 0.08 + 0.03) / 0.65
#:   = 0.29 / 0.65 = 0.44615384615384617...
#: score = 0.5 + 0.65 * (0.4461538461538462 - 0.5) = 0.5 + 0.65 * (-0.0538461538461538)
#:       = 0.465.
COMPOSITE_LOW_COVERAGE_D_WEIGHTS: tuple[float, None, float, float, float] = (
    0.49,
    None,  # D after the threshold gate
    0.6,
    0.4,
    0.2,
)

#: ``(description, components, expected score, expected available weight)`` —
#: the single table both the composite and the balanced-composite tests iterate.
#: Expected states are derived in the test body from the component count
#: (4 -> available, 2-3 -> partial, < 2 -> unavailable).
COMPOSITE_VECTORS: tuple[
    tuple[
        str,
        tuple[float | None, float | None, float | None, float | None],
        float | None,
        float,
    ],
    ...,
] = (
    (
        "four_available",
        COMPOSITE_FOUR_AVAILABLE,
        0.57,
        1.0,
    ),
    (
        "three_available_partial",
        COMPOSITE_THREE_AVAILABLE,
        0.615,
        0.85,
    ),
    (
        "two_available_partial",
        COMPOSITE_TWO_AVAILABLE,
        0.635,
        0.65,
    ),
    (
        "demand_quality_pair",
        COMPOSITE_D_Q_PAIR,
        0.6,
        0.50,
    ),
    (
        "one_available_unavailable",
        COMPOSITE_ONE_AVAILABLE,
        None,
        0.35,
    ),
    (
        "none_available_unavailable",
        COMPOSITE_NONE_AVAILABLE,
        None,
        0.0,
    ),
    (
        "low_coverage_d_excluded",
        (None, 0.6, 0.4, 0.2),
        0.465,
        0.65,
    ),
)

#: The repository-balanced policy must agree exactly with the fixed primary
#: weights (plan §9 "Fixed-weight vectors").
COMPOSITE_BALANCED_POLICY_VECTORS: tuple[
    tuple[str, tuple[float | None, float | None, float | None, float | None]], ...
] = tuple((name, components) for name, components, _score, _weight in COMPOSITE_VECTORS)

# ---------------------------------------------------------------------------
# ``score_category`` integration vector (LREQ-SCR-060)
# ---------------------------------------------------------------------------
#
# A 3-category run whose target has a demand and quality raw but a null recent
# supply raw. Target ``"c-1"``: demand_per_asset_raw = 5.0 against peers
# ``(0.0, 10.0)`` (L = 1, E = 0, m = 2 -> 0.5); demand_median_raw = 5.0 vs
# ``(10.0, 20.0)`` (L = 0, E = 0 -> 0.0); breadth_raw = 5.0 vs ``(10.0, 20.0)``
# (L = 0 -> 0.0); recent_share_raw = None (null normalized); median_age_raw = 5.0
# vs ``(10.0, 20.0)`` (L = 0 -> 0.0); quality_raw = 5.0 vs ``(10.0, 20.0)``
# (L = 0 -> 0.0). At full coverage:
#   D0 = 0.60 * 0.5 + 0.40 * 0.0 = 0.30      -> D = 0.30
#   C  = 1 - 0.0 = 1.0                        -> C = 1.0
#   Rpressure0 = single share term (s = None, a = 0.0) = 1 - 0.0 = 1.0 -> R0 = 0.0
#                                              -> R = 0.0
#   Q0 = 1 - 0.0 = 1.0                        -> Q = 1.0
#   W_A = 1.0, S = 0.35*0.30 + 0.30*1.0 + 0.20*0.0 + 0.15*1.0
#               = 0.105 + 0.30 + 0 + 0.15 = 0.555
#   score = 0.5 + 1.0 * (0.555 - 0.5) = 0.555, state = available, count = 4.

SCORE_CATEGORY_TARGET: str = "c-1"

SCORE_CATEGORY_RUN: tuple[CategoryRawMetrics, ...] = (
    make_category_raw_metrics(
        "c-0",
        make_raw_bundle(
            demand_per_asset_raw=0.0,
            demand_median_raw=10.0,
            breadth_raw=10.0,
            recent_share_raw=1.0,
            median_age_raw=10.0,
            quality_raw=10.0,
        ),
    ),
    make_category_raw_metrics(
        SCORE_CATEGORY_TARGET,
        make_raw_bundle(
            demand_per_asset_raw=5.0,
            demand_median_raw=5.0,
            breadth_raw=5.0,
            recent_share_raw=None,
            median_age_raw=5.0,
            quality_raw=5.0,
        ),
    ),
    make_category_raw_metrics(
        "c-2",
        make_raw_bundle(
            demand_per_asset_raw=10.0,
            demand_median_raw=20.0,
            breadth_raw=20.0,
            recent_share_raw=1.0,
            median_age_raw=20.0,
            quality_raw=20.0,
        ),
    ),
)

#: ``(D, C, R, Q, score, available count)`` for the run above.
SCORE_CATEGORY_EXPECTED: tuple[float, float, float, float, float, int] = (
    0.30,
    1.0,
    0.0,
    1.0,
    0.555,
    4,
)


def _build_demand_both_normalized() -> object:
    """``NormalizedValues`` for the ``D`` both-sub-signal vectors.

    ``demand_per_asset_raw = 1.0``, ``demand_median_raw = 0.0`` and every other
    field ``None``. Kept in a function so the ``NormalizedValues`` import stays
    local to it.
    """
    from niche_scout.scoring import NormalizedValues

    return NormalizedValues(
        demand_per_asset_raw=1.0,
        demand_median_raw=0.0,
        breadth_raw=None,
        recent_share_raw=None,
        median_age_raw=None,
        quality_raw=None,
    )


def _build_demand_only_normalized() -> object:
    """``NormalizedValues`` with only ``demand_per_asset_raw = 0.8`` available."""
    from niche_scout.scoring import NormalizedValues

    return NormalizedValues(
        demand_per_asset_raw=0.8,
        demand_median_raw=None,
        breadth_raw=None,
        recent_share_raw=None,
        median_age_raw=None,
        quality_raw=None,
    )


def _build_recent_both_normalized() -> object:
    """``NormalizedValues`` for the ``R`` both-sub-signal vectors (s = 0.9, a = 0.2)."""
    from niche_scout.scoring import NormalizedValues

    return NormalizedValues(
        demand_per_asset_raw=None,
        demand_median_raw=None,
        breadth_raw=None,
        recent_share_raw=0.9,
        median_age_raw=0.2,
        quality_raw=None,
    )


def _build_quality_normalized(quality_midrank: float | None) -> object:
    """``NormalizedValues`` with only ``quality_raw`` set (or null)."""
    from niche_scout.scoring import NormalizedValues

    return NormalizedValues(
        demand_per_asset_raw=None,
        demand_median_raw=None,
        breadth_raw=None,
        recent_share_raw=None,
        median_age_raw=None,
        quality_raw=quality_midrank,
    )


def _build_breadth_normalized(breadth_midrank: float | None) -> object:
    """``NormalizedValues`` with only ``breadth_raw`` set (or null)."""
    from niche_scout.scoring import NormalizedValues

    return NormalizedValues(
        demand_per_asset_raw=None,
        demand_median_raw=None,
        breadth_raw=breadth_midrank,
        recent_share_raw=None,
        median_age_raw=None,
        quality_raw=None,
    )


def _build_full_component_normalized() -> object:
    """``NormalizedValues`` for the contradicted and composite-input vectors.

    ``demand_per_asset_raw = 1.0``, ``demand_median_raw = 0.0``,
    ``breadth_raw = 0.25``, ``recent_share_raw = 0.9``, ``median_age_raw = 0.2``,
    ``quality_raw = 0.4``. At coverage 1.0 that yields
    ``D = 0.6, C = 0.75, R = 0.13, Q = 0.6``.
    """
    from niche_scout.scoring import NormalizedValues

    return NormalizedValues(
        demand_per_asset_raw=1.0,
        demand_median_raw=0.0,
        breadth_raw=0.25,
        recent_share_raw=0.9,
        median_age_raw=0.2,
        quality_raw=0.4,
    )


def _build_normalized_with(
    *,
    demand_per_asset_raw: float | None = None,
    demand_median_raw: float | None = None,
    breadth_raw: float | None = None,
    recent_share_raw: float | None = None,
    median_age_raw: float | None = None,
    quality_raw: float | None = None,
) -> object:
    """Build an arbitrary ``NormalizedValues`` from explicit keyword fields."""
    from niche_scout.scoring import NormalizedValues

    return NormalizedValues(
        demand_per_asset_raw=demand_per_asset_raw,
        demand_median_raw=demand_median_raw,
        breadth_raw=breadth_raw,
        recent_share_raw=recent_share_raw,
        median_age_raw=median_age_raw,
        quality_raw=quality_raw,
    )


def _build_component_values(
    demand: float | None,
    competition: float | None,
    recent_supply: float | None,
    quality: float | None,
) -> object:
    """Build a literal ``ComponentValues`` (fixture-side expected inputs)."""
    from niche_scout.scoring import ComponentValues

    return ComponentValues(
        demand=demand,
        competition=competition,
        recent_supply=recent_supply,
        quality=quality,
    )


#: ``NormalizedValues`` fixtures for the composite/contradicted tests, built once
#: at import time from the local-import builders above.
FULL_COMPONENT_NORMALIZED: object = _build_full_component_normalized()
DEMAND_BOTH_NORMALIZED: object = _build_demand_both_normalized()
DEMAND_ONLY_NORMALIZED: object = _build_demand_only_normalized()
RECENT_BOTH_NORMALIZED: object = _build_recent_both_normalized()
NORMALIZED_ALL_ONE: object = _build_normalized_with(
    demand_per_asset_raw=1.0,
    demand_median_raw=1.0,
    breadth_raw=1.0,
    recent_share_raw=1.0,
    median_age_raw=1.0,
    quality_raw=1.0,
)
NORMALIZED_ALL_ZERO: object = _build_normalized_with(
    demand_per_asset_raw=0.0,
    demand_median_raw=0.0,
    breadth_raw=0.0,
    recent_share_raw=0.0,
    median_age_raw=0.0,
    quality_raw=0.0,
)
NORMALIZED_ONE_ONLY: object = _build_normalized_with(
    demand_per_asset_raw=1.0,
)
NORMALIZED_ZERO: object = _build_normalized_with(
    demand_per_asset_raw=0.0,
)
NORMALIZED_TWO: object = _build_normalized_with(
    demand_per_asset_raw=0.0,
    demand_median_raw=1.0,
)
NORMALIZED_D_ONLY: object = _build_normalized_with(demand_per_asset_raw=1.0)
NORMALIZED_Q_ONLY: object = _build_normalized_with(quality_raw=0.4)
NORMALIZED_Q_ONLY_ONE: object = _build_normalized_with(quality_raw=0.0)
NORMALIZED_D_MISSING_ALL_ELSE_ZERO: object = _build_quality_normalized(None)
NORMALIZED_QUALITY_ZERO: object = _build_quality_normalized(1.0)
NORMALIZED_QUALITY_ONE: object = _build_quality_normalized(0.0)
NORMALIZED_BREADTH_QUARTER: object = _build_breadth_normalized(0.25)
NORMALIZED_BREADTH_ZERO: object = _build_breadth_normalized(0.0)
NORMALIZED_BREADTH_NULL: object = _build_breadth_normalized(None)
NORMALIZED_RECENT_SHARE_ONLY: object = _build_normalized_with(recent_share_raw=0.9)
NORMALIZED_MEDIAN_AGE_ONLY: object = _build_normalized_with(median_age_raw=0.2)
NORMALIZED_RECENT_NEITHER: object = _build_normalized_with()

#: Composite-input component tuples as ``ComponentValues`` for the balanced test.
COMPOSITE_COMPONENT_OBJECTS: tuple[tuple[str, object], ...] = tuple(
    (
        name,
        _build_component_values(
            components[0], components[1], components[2], components[3]
        ),
    )
    for name, components, _score, _weight in COMPOSITE_VECTORS
)

#: Fixed-weight vector: ``FIXED_PRIMARY_WEIGHTS`` is the balanced policy, and
#: ``models.W_D/W_C/W_R/W_Q`` are ``0.35/0.30/0.20/0.15`` (SRS-lean.md §8.3/§14).
FIXED_WEIGHT_VECTORS: tuple[tuple[str, float, float], ...] = tuple(
    (key, FIXED_PRIMARY_WEIGHTS[key], BALANCED_POLICY_WEIGHTS[key])
    for key in ("D", "C", "R", "Q")
)
