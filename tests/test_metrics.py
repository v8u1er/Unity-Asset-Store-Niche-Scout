"""Chunk 7B analytical tests — sample-aware raw estimators in ``metrics.py``.

Batch 1 covers the stratum expansion weight ``N_h / n_h`` and the weighted-median
primitive (LREQ-MET-050, LREQ-MET-100). Every expected value is a fixture constant
from ``tests/fixtures/metric_estimator_fixtures.py``, hand-derived from SRS-lean.md
§7.2 (demand / weighted median) and §7.5 (quality expansion weight), matching plan
``chunk-7B-sample-aware-raw-estimators.md`` §9.2. No network access, no clock
reads for expected values, and no writes.
"""

from __future__ import annotations

import ast
import dataclasses
import math
from pathlib import Path

import fixtures.metric_estimator_fixtures as mfx
import pytest

from niche_scout import metrics as m
from niche_scout.models import BreadthCompletenessStatus, BreadthSource
from niche_scout.tools.check_import_boundaries import (
    FORBIDDEN_MODULES,
    check_module,
    clock_violations,
)


@pytest.mark.lreq("LREQ-MET-050")
@pytest.mark.lreq("LREQ-MET-100")
@pytest.mark.lreq("LREQ-TST-050")
def test_stratum_expansion_weight_is_population_over_sample() -> None:
    """``stratum_expansion_weight(N_h, n_h)`` is the expansion weight ``N_h / n_h``.

    SRS §7.2 (LREQ-MET-050) gives each usable demand observation weight
    ``N_h / n_h``; SRS §7.5 (LREQ-MET-100) defines the same
    ``quality_weight_h = N_h / n_h``. Each fixture tuple is
    ``(N_h, n_h, expected)`` with ``expected = N_h / n_h``:
    ``(75, 25) -> 3.0``, ``(25, 25) -> 1.0``, ``(50, 25) -> 2.0``,
    ``(100, 4) -> 25.0``. The two distinct weight kinds (mean weight ``N_h / N``
    versus median/quality weight ``N_h / n_h``) never share a value here: ``3.0``
    and ``2.0`` appear as expansion weights, not as ``N_h / N`` shares.
    """
    for population, sampled, expected in mfx.STRATUM_EXPANSION_WEIGHT_VECTORS:
        # Fixture constants are finite, non-negative rational N_h / n_h values.
        assert math.isfinite(expected)
        assert m.stratum_expansion_weight(population, sampled) == pytest.approx(
            expected, abs=1e-9
        )


@pytest.mark.lreq("LREQ-MET-050")
def test_stratum_expansion_weight_rejects_bool_zero_and_negative() -> None:
    """A caller breach raises ``ValueError``, never a fabricated weight (plan §5.0).

    ``bool`` is an ``int`` subclass (``isinstance(True, int)`` is ``True``), so a
    boolean ``N_h``/``n_h`` must be rejected explicitly. A zero or negative
    population/sample count cannot define a usable ``N_h / n_h`` expansion weight
    (SRS §7.2 and §7.5 need a positive sampled count), so it raises as well.
    """
    for _label, population, sampled in mfx.STRATUM_EXPANSION_WEIGHT_INVALID_VECTORS:
        with pytest.raises(ValueError):
            m.stratum_expansion_weight(population, sampled)


@pytest.mark.lreq("LREQ-MET-050")
def test_weighted_median_empty_and_all_zero_weight_return_none() -> None:
    """An empty usable weighted sample yields ``None``, never ``0``.

    SRS §7.2 / LREQ-MET-050: the weighted median is null when the usable weighted
    sample is empty. ``()`` has no usable weight, and a vector whose total weight
    is exactly zero (every weight ``0.0``) is likewise an empty usable sample, so
    both return ``None``.
    """
    assert m.weighted_median(()) is None
    for vector in mfx.WEIGHTED_MEDIAN_ZERO_WEIGHT_VECTORS:
        assert m.weighted_median(vector) is None


@pytest.mark.lreq("LREQ-MET-050")
def test_weighted_median_single_value_and_first_at_or_above_half() -> None:
    """First sorted value whose cumulative weight is at least half the total.

    SRS §7.2 / LREQ-MET-050. Single value ``((7.0, 1.0),)``: ``T = 1``, half
    ``0.5``, cumulative ``1 >= 0.5`` -> ``7.0``. The demand-strata vector
    ``mfx.WEIGHTED_MEDIAN_DEMAND_STRATA_VECTOR`` (plan §9.2) has weights ``3.0``
    five times and ``1.0`` five times: ``T = 20``, half ``10``, cumulative
    ``3, 6, 9, 12``; the first value at or above half is ``4.0`` (no exact-half
    tie, so no averaging). The loop re-checks every fixture vector against its
    hand-derived constant.
    """
    for vector, expected in mfx.WEIGHTED_MEDIAN_VECTORS:
        assert m.weighted_median(vector) == pytest.approx(expected, abs=1e-9)
    assert m.weighted_median(((7.0, 1.0),)) == pytest.approx(7.0, abs=1e-9)
    assert m.weighted_median(mfx.WEIGHTED_MEDIAN_DEMAND_STRATA_VECTOR) == pytest.approx(
        4.0, abs=1e-9
    )


@pytest.mark.lreq("LREQ-MET-050")
@pytest.mark.lreq("LREQ-TST-050")
def test_weighted_median_exact_half_averages_with_next() -> None:
    """Exact-half cumulative weight averages the boundary and next sorted value.

    SRS §7.2 / LREQ-MET-050. ``((1.0, 1.0), (2.0, 1.0))``: ``T = 2``, half ``1``,
    cumulative ``1`` equals half exactly at value ``1.0``, next sorted value is
    ``2.0`` -> ``(1.0 + 2.0) / 2 = 1.5``. ``((1.0, 2.0), (2.0, 2.0))``: ``T = 4``,
    half ``2``, cumulative ``2`` equals half at ``1.0``, next ``2.0`` -> ``1.5``.
    ``mfx.WEIGHTED_MEDIAN_TIE_VECTOR`` keeps ties as separate observations:
    ``T = 4``, cumulative ``1, 2``; exact half ``2`` lands on the second ``1.0``,
    next ``2.0`` -> ``1.5``.
    """
    assert m.weighted_median(((1.0, 1.0), (2.0, 1.0))) == pytest.approx(1.5, abs=1e-9)
    assert m.weighted_median(((1.0, 2.0), (2.0, 2.0))) == pytest.approx(1.5, abs=1e-9)
    assert m.weighted_median(mfx.WEIGHTED_MEDIAN_TIE_VECTOR) == pytest.approx(
        1.5, abs=1e-9
    )


@pytest.mark.lreq("LREQ-MET-050")
def test_weighted_median_retains_ties_and_rejects_non_finite() -> None:
    """Ties stay separate; non-finite or negative weight raises ``ValueError``.

    SRS §7.2 sorts finite usable values and retains ties as separate observations,
    which is why ``mfx.WEIGHTED_MEDIAN_TIE_VECTOR`` resolves to ``1.5`` rather than
    a duplicated-value midpoint. A ``nan``/``inf`` value or weight, or a negative
    weight, breaches the caller contract: it must raise rather than fabricate a
    median (plan §5.0).
    """
    assert m.weighted_median(mfx.WEIGHTED_MEDIAN_TIE_VECTOR) == pytest.approx(
        1.5, abs=1e-9
    )
    for _label, vector in mfx.WEIGHTED_MEDIAN_INVALID_VECTORS:
        with pytest.raises(ValueError):
            m.weighted_median(vector)


@pytest.mark.lreq("LREQ-MET-030")
def test_demand_per_asset_uses_population_weighted_means() -> None:
    """``DemandPerAssetRaw`` renormalizes the ``N_h / N``-weighted usable strata.

    SRS §7.2 / LREQ-MET-030: ``sum(w_h * mean_h) / sum(w_h)`` over usable strata,
    ``w_h = N_h / N`` (plan §9.2 ``DEMAND_UNEQUAL_STRATA``). Stratum 0 has
    ``N_0 = 75``, ``n_0 = 25`` and usable indices ``[1, 2, 3, 4, 5]``, so
    ``mean_0 = 15 / 5 = 3.0`` and ``w_0 = 75 / 100 = 0.75``. Stratum 1 has
    ``N_1 = 25``, ``n_1 = 25`` and usable indices ``[10, 20, 30, 40, 50]``, so
    ``mean_1 = 150 / 5 = 30.0`` and ``w_1 = 25 / 100 = 0.25``. The result is
    ``(0.75 * 3.0 + 0.25 * 30.0) / (0.75 + 0.25) = (2.25 + 7.5) / 1.0 = 9.75``.
    The 20 missing-view observations per stratum contribute no weight and no zero
    (SRS §7.2).
    """
    result = m.demand_per_asset_raw(mfx.DEMAND_UNEQUAL_STRATA)
    assert result.value == pytest.approx(9.75, abs=1e-9)
    assert result.unavailable_reason is None


@pytest.mark.lreq("LREQ-MET-030")
def test_demand_per_asset_null_when_no_usable_stratum() -> None:
    """``u_demand_h < 5`` in every stratum is null, not a zero (LREQ-MET-030).

    In ``mfx.DEMAND_NO_USABLE_STRATUM`` each stratum has only 4 usable indices
    (``u_demand_h = 4 < MIN_USABLE_SAMPLES_PER_STRATUM = 5``), so no stratum is
    usable. SRS §7.2 / LREQ-MET-030: ``DemandPerAssetRaw`` is null when no stratum
    has at least the usable minimum, and plan §5.1 gives that outcome the reason
    ``METRIC_REASON_NO_USABLE_STRATUM``.
    """
    result = m.demand_per_asset_raw(mfx.DEMAND_NO_USABLE_STRATUM)
    assert result.value is None
    assert result.unavailable_reason == m.METRIC_REASON_NO_USABLE_STRATUM


@pytest.mark.lreq("LREQ-MET-030")
def test_demand_per_asset_zero_population_is_null_and_never_divides() -> None:
    """``N = 0`` is null with ``zero_population``; ``N_h / N`` is never evaluated.

    ``mfx.ZERO_POPULATION`` has no strata, so ``N = 0``. SRS §7.2 / LREQ-MET-030:
    the implementation SHALL never evaluate ``N_h / N`` when ``N = 0`` and the
    demand raw metrics SHALL be null; plan §5.1 assigns
    ``METRIC_REASON_ZERO_POPULATION``. Coverage is the computed value ``0.0``
    (SRS §7.2 / LREQ-MET-060: coverage is ``0`` for a verified ``N = 0``
    category), which stays distinct from the null raw value.
    """
    result = m.demand_per_asset_raw(mfx.ZERO_POPULATION)
    assert result.value is None
    assert result.unavailable_reason == m.METRIC_REASON_ZERO_POPULATION
    assert m.demand_stratum_eligibility_coverage(mfx.ZERO_POPULATION) == pytest.approx(
        0.0, abs=1e-9
    )


@pytest.mark.lreq("LREQ-MET-050")
def test_demand_median_uses_stratum_expansion_weights() -> None:
    """``DemandMedianRaw`` weights each usable index by ``N_h / n_h``.

    SRS §7.2 / LREQ-MET-050: each usable observation in stratum ``h`` receives
    weight ``N_h / n_h`` and the first sorted value whose cumulative weight is at
    least half the total weight is the median. In ``mfx.DEMAND_UNEQUAL_STRATA``
    (plan §9.2) stratum 0 gives weight ``75 / 25 = 3.0`` to each of ``1, 2, 3, 4,
    5`` and stratum 1 gives ``25 / 25 = 1.0`` to each of ``10, 20, 30, 40, 50``.
    Total weight ``T = 15 + 5 = 20``, half ``10``; cumulative weights are ``3, 6,
    9, 12``, so the first value at or above half is ``4.0`` (no exact-half tie).
    """
    result = m.demand_median_raw(mfx.DEMAND_UNEQUAL_STRATA)
    assert result.value == pytest.approx(4.0, abs=1e-9)
    assert result.unavailable_reason is None


@pytest.mark.lreq("LREQ-MET-050")
def test_demand_median_exact_half_boundary() -> None:
    """Exact-half cumulative weight averages the boundary and next value.

    SRS §7.2 / LREQ-MET-050: if the cumulative weight equals exactly half at a
    value boundary, use the arithmetic mean of that value and the next sorted
    value. In ``mfx.DEMAND_MEDIAN_EXACT_HALF`` (plan §9.3) both strata are
    census-like: ``N_0 = N_1 = 25``, ``n_0 = n_1 = 5``, so every usable index
    weighs ``25 / 25 = 1.0``; stratum 0 holds ``[1, 2, 3, 4, 5]`` and stratum 1
    holds ``[6, 7, 8, 9, 10]``. ``T = 10``, half ``5``, cumulative weights
    ``1, 2, 3, 4, 5`` reach exactly ``5`` at value ``5.0``, and the next sorted
    value is ``6.0`` -> ``(5.0 + 6.0) / 2 = 5.5``.
    """
    result = m.demand_median_raw(mfx.DEMAND_MEDIAN_EXACT_HALF)
    assert result.value == pytest.approx(5.5, abs=1e-9)
    assert result.unavailable_reason is None


@pytest.mark.lreq("LREQ-MET-050")
def test_demand_median_null_when_no_usable_index() -> None:
    """An empty usable weighted sample is null, never a fabricated zero.

    In ``mfx.DEMAND_NO_USABLE_INDEX`` (plan §9.3) every observation has
    ``product_page_views = None``, so ``u_demand_h = 0`` and no usable index
    exists. SRS §7.2 / LREQ-MET-050: the weighted median is null when the usable
    weighted sample is empty; plan §5.1 names that outcome
    ``METRIC_REASON_EMPTY_USABLE_SAMPLE``. Missing is not a zero (SRS §1.2).
    """
    result = m.demand_median_raw(mfx.DEMAND_NO_USABLE_INDEX)
    assert result.value is None
    assert result.unavailable_reason == m.METRIC_REASON_EMPTY_USABLE_SAMPLE


@pytest.mark.lreq("LREQ-MET-060")
def test_demand_coverage_sums_usable_stratum_weights() -> None:
    """Coverage is ``sum(N_h / N)`` over the strata meeting the usable minimum.

    SRS §7.2 / LREQ-MET-060. In ``mfx.DEMAND_UNEQUAL_STRATA`` both strata are
    usable, so coverage is ``75 / 100 + 25 / 100 = 0.75 + 0.25 = 1.0``. In
    ``mfx.DEMAND_PARTIAL_COVERAGE`` (plan §9.3) stratum 1 has ``u_demand_1 = 4 <
    5`` and is therefore not usable; its population weight is excluded rather
    than zeroed, leaving ``N_0 / N = 75 / 100 = 0.75``. Only stratum 0
    contributes to the aggregate ``usable_demand_sample_count``, which is
    ``u_demand_0 = 5`` (plan §5.2 / SRS §6.5: observations contributing to
    strata that satisfy the applicable usable minimum).
    """
    assert m.demand_stratum_eligibility_coverage(
        mfx.DEMAND_UNEQUAL_STRATA
    ) == pytest.approx(1.0, abs=1e-9)
    assert m.demand_stratum_eligibility_coverage(
        mfx.DEMAND_PARTIAL_COVERAGE
    ) == pytest.approx(0.75, abs=1e-9)
    aggregate = m.compute_category_raw_metrics(
        mfx.DEMAND_PARTIAL_COVERAGE,
        mfx.make_breadth_input(None, 0),
    )
    assert aggregate.usable_demand_sample_count == 5


@pytest.mark.lreq("LREQ-MET-060")
def test_demand_coverage_is_zero_for_zero_population() -> None:
    """``N = 0`` gives coverage ``0.0``: a value, not a null or an error.

    SRS §7.2 / LREQ-MET-060: "For a verified category with ``N = 0``, demand
    stratum eligibility coverage SHALL be ``0`` and demand raw metrics SHALL be
    null." ``mfx.ZERO_POPULATION`` has no strata, so ``N = 0``; the coverage is
    the explicit valid zero ``0.0`` while the raw value stays null.
    """
    coverage = m.demand_stratum_eligibility_coverage(mfx.ZERO_POPULATION)
    assert coverage == pytest.approx(0.0, abs=1e-9)


@pytest.mark.lreq("LREQ-MET-060")
@pytest.mark.lreq("LREQ-MET-030")
def test_demand_coverage_is_distinct_from_sample_fraction() -> None:
    """Coverage is a population-weight sum, never ``enriched / discovered``.

    SRS §7.2 / LREQ-MET-060: coverage is ``sum(N_h / N)`` over usable strata and
    "SHALL not be confused with ``sample_fraction``" (SRS §5.1:
    ``enriched_sample_count / discovered_population_count``). On
    ``mfx.DEMAND_UNEQUAL_STRATA`` every stratum is usable, so coverage is
    ``75 / 100 + 25 / 100 = 1.0``. The sample fraction is derived here from the
    fixture's own population counts, not from an estimator: sampled
    ``n_0 + n_1 = 25 + 25 = 50`` over discovered ``N_0 + N_1 = 75 + 25 = 100``,
    i.e. ``0.5``. Chunk 7B never computes or returns ``sample_fraction``.
    """
    coverage = m.demand_stratum_eligibility_coverage(mfx.DEMAND_UNEQUAL_STRATA)
    assert coverage == pytest.approx(1.0, abs=1e-9)
    strata = mfx.DEMAND_UNEQUAL_STRATA.strata
    enriched = sum(stratum.sampled_population_count for stratum in strata)
    discovered = sum(stratum.discovered_population_count for stratum in strata)
    assert (enriched, discovered) == (50, 100)
    sample_fraction = enriched / discovered
    assert sample_fraction == pytest.approx(0.5, abs=1e-9)
    assert abs(coverage - sample_fraction) > 1e-9


@pytest.mark.lreq("LREQ-MET-070")
def test_breadth_uses_verified_total_count() -> None:
    """A verified ``totalCount`` is ``BreadthRaw`` with complete provenance.

    SRS §7.3 / LREQ-MET-070: when the endpoint provides a structurally verified,
    category-filter-consistent ``totalCount``, ``breadth_source`` SHALL be
    ``verified_total_count`` and ``BreadthRaw`` SHALL equal that count.
    ``mfx.BREADTH_VERIFIED_INPUT`` is ``(verified_total_count=1200,
    distinct_canonical_discovered_count=1180)``, so ``breadth_raw == 1200`` (the
    verified population count, not the smaller discovered sample count) with
    ``BreadthCompletenessStatus.COMPLETE``.
    """
    result = m.breadth_raw(mfx.BREADTH_VERIFIED_INPUT)
    assert result.breadth_raw == 1200
    assert result.breadth_source is BreadthSource.VERIFIED_TOTAL_COUNT
    assert result.breadth_completeness_status is BreadthCompletenessStatus.COMPLETE


@pytest.mark.lreq("LREQ-MET-070")
def test_breadth_falls_back_to_distinct_canonical_count() -> None:
    """Without a verified total, breadth is the distinct canonical count.

    SRS §7.3 / LREQ-MET-070: otherwise ``breadth_source`` SHALL be
    ``distinct_canonical_discovered_count``, ``BreadthRaw`` SHALL equal that
    count, and ``breadth_completeness_status`` SHALL be
    ``incomplete_estimate``. ``mfx.BREADTH_FALLBACK_INPUT`` is
    ``(verified_total_count=None, distinct_canonical_discovered_count=250)``, so
    ``breadth_raw == 250``.
    """
    result = m.breadth_raw(mfx.BREADTH_FALLBACK_INPUT)
    assert result.breadth_raw == 250
    assert result.breadth_source is BreadthSource.DISTINCT_CANONICAL_DISCOVERED_COUNT
    assert (
        result.breadth_completeness_status
        is BreadthCompletenessStatus.INCOMPLETE_ESTIMATE
    )


@pytest.mark.lreq("LREQ-MET-070")
def test_breadth_verified_zero_result_is_zero() -> None:
    """A verified zero-result category has ``BreadthRaw == 0``, not null.

    SRS §7.3 / LREQ-MET-070: "For a verified zero-result category,
    ``discovered_population_count`` and ``BreadthRaw`` SHALL be ``0``."
    ``mfx.BREADTH_VERIFIED_ZERO_INPUT`` is ``(0, 0)``, so the verified zero is a
    value with ``verified_total_count`` provenance and ``COMPLETE`` completeness —
    a failed or truncated page is never interpreted as zero.
    """
    result = m.breadth_raw(mfx.BREADTH_VERIFIED_ZERO_INPUT)
    assert result.breadth_raw == 0
    assert result.breadth_source is BreadthSource.VERIFIED_TOTAL_COUNT
    assert result.breadth_completeness_status is BreadthCompletenessStatus.COMPLETE


# ---------------------------------------------------------------------------
# Batch 3 — Recent Supply share, coverage, and MedianAgeRaw (LREQ-MET-080)
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-MET-080")
def test_recent_share_uses_inclusive_window_per_stratum() -> None:
    """``RecentShareRaw`` is the population-weighted mean of per-stratum shares.

    SRS §7.4 / LREQ-MET-080: ``RecentShareRaw = sum(w_h * share_h) / sum(w_h)``
    with ``w_h = N_h / N`` and, per usable stratum,
    ``share_h = count(0 <= age_days_exact <= 365) / u_recent_h``. In
    ``mfx.RECENT_UNEQUAL_STRATA`` both strata are usable
    (``u_recent_0 = u_recent_1 = 5``) and ``N_0 = N_1 = 50``, so
    ``w_0 = w_1 = 0.5``. Stratum 0 ages ``[100, 200, 300, 400, 500]``: ``3``
    inside the window -> ``share_0 = 3 / 5 = 0.6``. Stratum 1 ages
    ``[10, 20, 30, 40, 50]``: ``5`` inside -> ``share_1 = 5 / 5 = 1.0``.
    Result ``(0.5 * 0.6 + 0.5 * 1.0) / 1.0 = 0.3 + 0.5 = 0.8``.
    The window is inclusive at both ends: age ``365.0`` is inside while
    ``365.0 + 1e-6`` is outside (SRS §7.4).
    """
    result = m.recent_share_raw(mfx.RECENT_UNEQUAL_STRATA)
    assert result.value == pytest.approx(0.8, abs=1e-9)
    assert result.unavailable_reason is None
    assert (
        m.is_within_recent_window(365.0, recent_window_days=mfx.RECENT_WINDOW_DAYS)
        is True
    )
    assert (
        m.is_within_recent_window(
            365.0 + 1e-6, recent_window_days=mfx.RECENT_WINDOW_DAYS
        )
        is False
    )


@pytest.mark.lreq("LREQ-MET-080")
def test_recent_share_missing_dates_reduce_coverage_not_zero() -> None:
    """Missing dates shrink ``u_recent_h``; they are never zero-numerator rows.

    SRS §7.4 / LREQ-MET-080, with missing is not zero (SRS §1.2). In
    ``mfx.RECENT_MISSING_DATES`` one stratum has ``N_h = 50``, ``n_h = 25``,
    ages ``[10, 20, 400, 500, 600]`` and 20 missing dates. The usable dated
    count is ``u_recent_h = 5``, so ``share_h = 2 / 5 = 0.4`` (ages ``10`` and
    ``20`` are inside the window); the missing dates leave the denominator
    instead of entering it as ``0``-numerator rows. Treating them as zero
    entries would give ``2 / 25 = 0.08``, which this test rejects. ``N = 50``,
    so the single usable stratum carries ``w_h = 50 / 50 = 1.0``:
    ``RecentShareRaw = 1.0 * 0.4 / 1.0 = 0.4`` and coverage ``50 / 50 = 1.0``.
    """
    result = m.recent_share_raw(mfx.RECENT_MISSING_DATES)
    assert result.value == pytest.approx(0.4, abs=1e-9)
    assert abs(result.value - 0.08) > 1e-9
    coverage = m.recent_supply_stratum_eligibility_coverage(mfx.RECENT_MISSING_DATES)
    assert coverage == pytest.approx(1.0, abs=1e-9)


@pytest.mark.lreq("LREQ-MET-080")
@pytest.mark.lreq("LREQ-MET-030")
def test_recent_supply_usability_minimum_boundary() -> None:
    """A stratum needs ``u_recent_h >= 5``; four usable dates is not usable.

    SRS §7.4 / LREQ-MET-080 with the usable minimum of SRS §7.2 /
    LREQ-MET-030 (``MIN_USABLE_SAMPLES_PER_STRATUM = 5``). In
    ``mfx.RECENT_USABILITY_BOUNDARY`` the population is ``N_0 = N_1 = 50``,
    ``N = 100``: stratum 0 has ``u_recent_0 = 4`` (ages ``10, 20, 30, 40``) and
    is excluded; stratum 1 has ``u_recent_1 = 5`` (ages ``10..50``, all inside
    the window) and is usable with ``share_1 = 5 / 5 = 1.0``. The raw value
    renormalizes over the one usable stratum: ``(0.5 * 1.0) / 0.5 = 1.0``,
    while coverage is ``N_1 / N = 50 / 100 = 0.5`` (the excluded stratum's
    population weight is dropped, never zeroed).

    SRS §7.4 also defines ``usable_recent_supply_sample_count`` as the sum of
    usable dated observations in those usable strata, so only stratum 1's
    ``u_recent_1 = 5`` counts (stratum 0's four usable dates do not).
    """
    result = m.recent_share_raw(mfx.RECENT_USABILITY_BOUNDARY)
    assert result.value == pytest.approx(1.0, abs=1e-9)
    coverage = m.recent_supply_stratum_eligibility_coverage(
        mfx.RECENT_USABILITY_BOUNDARY
    )
    assert coverage == pytest.approx(0.5, abs=1e-9)
    aggregate = m.compute_category_raw_metrics(
        mfx.RECENT_USABILITY_BOUNDARY,
        mfx.make_breadth_input(None, 0),
    )
    assert aggregate.usable_recent_supply_sample_count == 5


@pytest.mark.lreq("LREQ-MET-080")
def test_recent_supply_coverage_and_usable_count() -> None:
    """``compute_category_raw_metrics`` reports full coverage and 10 usable dates.

    SRS §7.4 / LREQ-MET-080. ``mfx.RECENT_UNEQUAL_STRATA`` has both strata
    usable with ``N_0 = N_1 = 50`` out of ``N = 100``, so recent supply
    coverage is ``50 / 100 + 50 / 100 = 1.0``. The usable dated count is
    ``u_recent_0 + u_recent_1 = 5 + 5 = 10``; the 20 missing-date observations
    per stratum contribute nothing.
    """
    coverage = m.recent_supply_stratum_eligibility_coverage(mfx.RECENT_UNEQUAL_STRATA)
    assert coverage == pytest.approx(1.0, abs=1e-9)
    aggregate = m.compute_category_raw_metrics(
        mfx.RECENT_UNEQUAL_STRATA,
        mfx.make_breadth_input(None, 0),
    )
    assert aggregate.usable_recent_supply_sample_count == 10


@pytest.mark.lreq("LREQ-MET-080")
def test_median_age_uses_stratum_expansion_weights() -> None:
    """``MedianAgeRaw`` is a stratum-expanded weighted median, not a mean.

    SRS §7.4 / LREQ-MET-080: each usable dated observation in stratum ``h``
    carries weight ``N_h / n_h`` (SRS §7.2). In ``mfx.RECENT_UNEQUAL_STRATA``
    both strata have ``N_h = 50`` and ``n_h = 25``, so every usable age weighs
    ``50 / 25 = 2.0``. The sorted ages ``10, 20, 30, 40, 50, 100, 200, 300,
    400, 500`` give ``T = 10 * 2.0 = 20``, half ``10``; the cumulative weight
    equals exactly ``10`` at age ``50``, so the exact-half boundary rule
    averages that boundary with the next sorted age:
    ``(50 + 100) / 2 = 75.0``. The unweighted arithmetic mean of the same ten
    ages is ``(10 + 20 + 30 + 40 + 50 + 100 + 200 + 300 + 400 + 500) / 10 =
    1650 / 10 = 165.0``, so the result is not the unweighted mean; the plain
    median midpoint coincides numerically at ``75.0``, but the asserted value
    is the weighted exact-half outcome, applied with weight
    ``stratum_expansion_weight(50, 25) = 2.0``.
    """
    result = m.median_age_raw(mfx.RECENT_UNEQUAL_STRATA)
    assert result.value == pytest.approx(75.0, abs=1e-9)
    assert m.stratum_expansion_weight(50, 25) == pytest.approx(2.0, abs=1e-9)
    dates = (
        mfx.DATE_10D,
        mfx.DATE_20D,
        mfx.DATE_30D,
        mfx.DATE_40D,
        mfx.DATE_50D,
        mfx.DATE_100D,
        mfx.DATE_200D,
        mfx.DATE_300D,
        mfx.DATE_400D,
        mfx.DATE_500D,
    )
    ages = tuple((mfx.CUTOFF_UTC - dt).total_seconds() / 86400.0 for dt in dates)
    unweighted_mean = sum(ages) / len(ages)
    assert unweighted_mean == pytest.approx(165.0, abs=1e-9)
    assert abs(result.value - unweighted_mean) > 1e-9


@pytest.mark.lreq("LREQ-MET-080")
@pytest.mark.lreq("LREQ-MET-050")
def test_median_age_exact_half_boundary() -> None:
    """Exact-half cumulative weight averages the boundary with the next age.

    SRS §7.4 / LREQ-MET-080 with the boundary rule of SRS §7.2 /
    LREQ-MET-050. ``mfx.RECENT_UNEQUAL_STRATA``: uniform weight ``2.0``,
    ``T = 20``, half ``10``; cumulative weight equals exactly ``10`` at age
    ``50`` and the next sorted age is ``100`` -> ``(50 + 100) / 2 = 75.0``.
    ``mfx.RECENT_MISSING_DATES``: ages ``10, 20, 400, 500, 600`` each weighing
    ``50 / 25 = 2.0``; ``T = 10``, half ``5``; cumulative ``2, 4, 6`` -> the
    first value at or above half is ``400.0`` (the cumulative stands at ``4``
    after age ``20``, so there is no exact-half tie).
    ``mfx.RECENT_USABILITY_BOUNDARY``: the usable stratum holds ages
    ``10, 20, 30, 40, 50`` each weighing ``2.0``; ``T = 10``, half ``5``;
    cumulative ``2, 4, 6`` -> ``30.0``.
    """
    unequal = m.median_age_raw(mfx.RECENT_UNEQUAL_STRATA)
    assert unequal.value == pytest.approx(75.0, abs=1e-9)
    missing = m.median_age_raw(mfx.RECENT_MISSING_DATES)
    assert missing.value == pytest.approx(400.0, abs=1e-9)
    boundary = m.median_age_raw(mfx.RECENT_USABILITY_BOUNDARY)
    assert boundary.value == pytest.approx(30.0, abs=1e-9)


@pytest.mark.lreq("LREQ-MET-080")
def test_recent_zero_population_is_null_and_coverage_zero() -> None:
    """``N = 0`` gives null recent-supply raws and coverage ``0.0``, not null.

    SRS §7.4 / LREQ-MET-080 with SRS §7.2: for a verified ``N = 0`` category
    the sample-derived raws are null because no ``N_h / N`` is evaluated, while
    coverage stays the explicit valid zero ``0.0`` — a computed value, distinct
    from the null raw (SRS §7.2 / LREQ-MET-060 coverage shape, applied to
    recent supply). ``mfx.ZERO_POPULATION`` has no strata, so ``N = 0`` and
    ``RecentShareRaw`` and ``MedianAgeRaw`` are null while
    ``recent_supply_stratum_eligibility_coverage`` is ``0.0``.
    """
    share = m.recent_share_raw(mfx.ZERO_POPULATION)
    assert share.value is None
    median = m.median_age_raw(mfx.ZERO_POPULATION)
    assert median.value is None
    assert m.recent_supply_stratum_eligibility_coverage(
        mfx.ZERO_POPULATION
    ) == pytest.approx(0.0, abs=1e-9)


# ---------------------------------------------------------------------------
# Batch 4 — QualityRaw and quality coverage (LREQ-MET-090, LREQ-MET-100)
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-MET-100")
@pytest.mark.lreq("LREQ-TST-050")
def test_quality_raw_uses_n_h_over_n_h_weights() -> None:
    """``QualityRaw`` weights each stratum by ``N_h / n_h``, not by sample size.

    SRS §7.5 / LREQ-MET-100: ``num_h = (N_h / n_h) * sum((rating_average_i /
    5) * index_i)`` and ``den_h = (N_h / n_h) * sum(index_i)``, so the stratum
    expansion weight is the weight that must be used. Fixture arithmetic
    (``mfx.QUALITY_UNEQUAL_STRATA``): both strata have ``N_h = 50`` and
    ``n_h = 25``, so ``quality_weight_h = 50 / 25 = 2.0`` — the same weight
    ``m.stratum_expansion_weight(50, 25)`` returns. Stratum 0's five eligible
    observations rate ``2.5 / 5 = 0.5`` at index ``10.0`` each:
    ``num_0 = 2.0 * (5 * 5.0) = 50.0``, ``den_0 = 2.0 * 50.0 = 100.0``.
    Stratum 1's five rate ``5.0 / 5 = 1.0``: ``num_1 = 2.0 * 50.0 = 100.0``,
    ``den_1 = 100.0``. ``QualityRaw = (50.0 + 100.0) / (100.0 + 100.0) =
    150.0 / 200.0 = 0.75``.
    """
    result = m.quality_raw(mfx.QUALITY_UNEQUAL_STRATA)
    assert result.value == pytest.approx(0.75, abs=1e-9)
    assert result.unavailable_reason is None
    assert m.stratum_expansion_weight(50, 25) == pytest.approx(2.0, abs=1e-9)


@pytest.mark.lreq("LREQ-MET-100")
@pytest.mark.lreq("LREQ-TST-050")
def test_quality_raw_zero_visibility_denominator_is_null() -> None:
    """A zero visibility denominator is null, never a zero quality score.

    SRS §7.5 / LREQ-MET-100: when ``den_h`` is zero the ratio is undefined, so
    ``QualityRaw`` is null with ``METRIC_REASON_ZERO_DENOMINATOR`` (plan §5.1);
    missing is not zero (SRS §1.2). In ``mfx.QUALITY_ZERO_VISIBILITY`` all five
    eligible observations carry the explicit valid ``product_page_views = 0``
    (age 70, index ``0 * 7 / 70 = 0.0``), so ``num_h = den_h = 0.0``. The
    eligible set is 5 and the single stratum is quality-usable, so the coverage
    stays the computed value ``25 / 25 = 1.0`` — a zero-value raw is not a
    zero-coverage raw.
    """
    result = m.quality_raw(mfx.QUALITY_ZERO_VISIBILITY)
    assert result.value is None
    assert result.unavailable_reason == m.METRIC_REASON_ZERO_DENOMINATOR
    coverage = m.quality_stratum_eligibility_coverage(mfx.QUALITY_ZERO_VISIBILITY)
    assert coverage == pytest.approx(1.0, abs=1e-9)


@pytest.mark.lreq("LREQ-MET-090")
def test_quality_eligible_set_too_small_is_null() -> None:
    """Fewer than five quality-eligible observations is null, not a zero.

    SRS §7.5 / LREQ-MET-090: the eligible-set guard requires at least
    ``QUALITY_MIN_ELIGIBLE_ASSETS = 5`` quality-eligible observations before a
    ratio is computed. ``mfx.QUALITY_ELIGIBLE_SET_TOO_SMALL`` has one stratum
    with ``N_h = 75``, ``n_h = 4`` and all four observations eligible, so
    ``4 < 5`` and ``QualityRaw`` is null; plan §5.1 names the outcome
    ``METRIC_REASON_ELIGIBLE_SET_TOO_SMALL``.
    """
    result = m.quality_raw(mfx.QUALITY_ELIGIBLE_SET_TOO_SMALL)
    assert result.value is None
    assert result.unavailable_reason == m.METRIC_REASON_ELIGIBLE_SET_TOO_SMALL


@pytest.mark.lreq("LREQ-MET-090")
def test_quality_raw_null_below_required_coverage() -> None:
    """Coverage below ``MIN_REQUIRED_COMPONENT_COVERAGE`` yields a null raw.

    SRS §7.5 / LREQ-MET-090 with plan Q-3 option (a): quality coverage must
    reach ``MIN_REQUIRED_COMPONENT_COVERAGE = 0.50`` or ``QualityRaw`` is null
    with ``METRIC_REASON_INSUFFICIENT_COVERAGE``. In
    ``mfx.QUALITY_LOW_COVERAGE`` stratum 0 (``N_0 = 25``, 5 eligible) is
    quality-usable and stratum 1 (``N_1 = 75``, 4 eligible < 5) is not, so the
    coverage is the population weight ``25 / 100 = 0.25``, below the required
    ``0.50``. The total eligible set is ``5 + 4 = 9 >= 5``, so only the
    coverage guard fires.
    """
    result = m.quality_raw(mfx.QUALITY_LOW_COVERAGE)
    assert m.quality_stratum_eligibility_coverage(
        mfx.QUALITY_LOW_COVERAGE
    ) == pytest.approx(0.25, abs=1e-9)
    assert result.value is None
    assert result.unavailable_reason == m.METRIC_REASON_INSUFFICIENT_COVERAGE


@pytest.mark.lreq("LREQ-MET-090")
def test_quality_raw_contradicted_semantics_is_null() -> None:
    """Contradicted semantics make every observation ineligible (plan §9.2).

    SRS §7.5 / LREQ-MET-090. Plan §9.2 lead correction C-1: a run-level
    ``CONTRADICTED`` page-view semantics status (a Chunk 7A classification,
    consumed here rather than detected, plan Q-1) makes every observation
    quality-ineligible, so the eligible count is 0. The plan §5.3 precedence
    order then yields ``METRIC_REASON_ELIGIBLE_SET_TOO_SMALL`` (``0 < 5``)
    ahead of the contradicted-semantics reason, and the coverage is ``0.0``:
    ``mfx.SEMANTICS_CONTRADICTED`` reuses the ``QUALITY_UNEQUAL_STRATA``
    strata with that status set.
    """
    result = m.quality_raw(mfx.SEMANTICS_CONTRADICTED)
    assert result.value is None
    assert result.unavailable_reason == m.METRIC_REASON_ELIGIBLE_SET_TOO_SMALL
    coverage = m.quality_stratum_eligibility_coverage(mfx.SEMANTICS_CONTRADICTED)
    assert coverage == pytest.approx(0.0, abs=1e-9)


@pytest.mark.lreq("LREQ-MET-090")
def test_quality_coverage_not_renormalized() -> None:
    """Coverage is a usable-stratum population-weight sum, never a count ratio.

    SRS §7.5 / LREQ-MET-090: ``quality_stratum_eligibility_coverage`` is
    ``sum(N_h / N)`` over the quality-usable strata — it is neither
    ``eligible / total_eligible`` nor renormalized to the usable subset. In
    ``mfx.QUALITY_LOW_COVERAGE`` only stratum 0 is usable, so coverage is
    ``N_0 / N = 25 / 100 = 0.25`` while the naive count fraction would be
    ``5 / 9 = 0.5555...`` (the 5 eligible observations of stratum 0 over the
    9 eligible observations in total). ``mfx.QUALITY_UNEQUAL_STRATA`` has both
    strata usable, so coverage is ``50 / 100 + 50 / 100 = 1.0``.
    """
    low_coverage = m.quality_stratum_eligibility_coverage(mfx.QUALITY_LOW_COVERAGE)
    assert low_coverage == pytest.approx(0.25, abs=1e-9)
    assert abs(low_coverage - 5 / 9) > 1e-9
    full_coverage = m.quality_stratum_eligibility_coverage(mfx.QUALITY_UNEQUAL_STRATA)
    assert full_coverage == pytest.approx(1.0, abs=1e-9)


@pytest.mark.lreq("LREQ-MET-100")
def test_quality_zero_population_is_null_and_coverage_zero() -> None:
    """``N = 0`` gives a null ``QualityRaw`` and coverage ``0.0``, not null.

    SRS §7.5 / LREQ-MET-100 with the verified-zero shape of SRS §7.2 /
    LREQ-MET-060: for ``mfx.ZERO_POPULATION`` (no strata, ``N = 0``) no
    ``N_h / N`` is evaluated, so ``QualityRaw`` is null while the coverage
    stays the explicit valid zero ``0.0`` — a computed value distinct from the
    null raw.
    """
    assert m.quality_raw(mfx.ZERO_POPULATION).value is None
    coverage = m.quality_stratum_eligibility_coverage(mfx.ZERO_POPULATION)
    assert coverage == pytest.approx(0.0, abs=1e-9)


@pytest.mark.lreq("LREQ-MET-090")
def test_quality_raw_ineligible_observations_are_excluded() -> None:
    """Chunk-7A-ineligible observations leave both the ratio and the coverage.

    SRS §7.5 / LREQ-MET-090 with missing is not zero (SRS §1.2). This local
    input copies ``mfx.QUALITY_UNEQUAL_STRATA`` but replaces stratum 1's five
    eligible observations with 25 observations whose ``rating_average`` is
    ``None`` — Chunk-7A quality-ineligible, never zero-rated. Stratum 1 is
    then not quality-usable and its ``N_h / N`` weight is excluded, so coverage
    is only ``N_0 / N = 50 / 100 = 0.5`` and the usable quality sample count,
    read through ``compute_category_raw_metrics``, is the five eligible
    observations of stratum 0.
    """
    local_input = mfx.make_category_input(
        (
            mfx.QUALITY_UNEQUAL_STRATUM_INPUTS[0],
            mfx.make_stratum(
                1,
                50,
                (mfx.make_observation(rating_average=None),) * 25,
            ),
        ),
        category="quality-ineligible-excluded",
    )
    coverage = m.quality_stratum_eligibility_coverage(local_input)
    assert coverage == pytest.approx(0.5, abs=1e-9)
    aggregate = m.compute_category_raw_metrics(
        local_input,
        mfx.make_breadth_input(None, 0),
    )
    assert aggregate.usable_quality_sample_count == 5


# ---------------------------------------------------------------------------
# Batch 5 — aggregate bundles, coverage/count reporting, caller contract,
# purity, and determinism (LREQ-MET-030/060/070/080/090/100, LREQ-ARCH-*)
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-MET-030")
@pytest.mark.lreq("LREQ-MET-050")
@pytest.mark.lreq("LREQ-MET-060")
@pytest.mark.lreq("LREQ-MET-070")
@pytest.mark.lreq("LREQ-MET-080")
@pytest.mark.lreq("LREQ-MET-100")
def test_compute_raw_metric_bundle_maps_all_six_values() -> None:
    """``compute_raw_metric_bundle`` maps the six SRS §8.1 raw fields.

    SRS §8.1 / plan §5.3: ``demand_per_asset_raw``, ``demand_median_raw``,
    ``breadth_raw``, ``recent_share_raw``, ``median_age_raw``, and
    ``quality_raw``. On ``mfx.DEMAND_UNEQUAL_STRATA`` (plan §9.2 arithmetic):

    * ``demand_per_asset_raw``: usable strata means ``3.0`` and ``30.0`` with
      population weights ``0.75`` and ``0.25`` ->
      ``(0.75 * 3.0 + 0.25 * 30.0) / 1.0 = 9.75`` (SRS §7.2).
    * ``demand_median_raw``: expansion weights ``75/25 = 3.0`` and
      ``25/25 = 1.0``; ``T = 20``, half ``10``, cumulative ``3, 6, 9, 12`` ->
      ``4.0`` (SRS §7.2).
    * ``breadth_raw`` is ``None``: breadth is not derivable from
      ``CategoryMetricInput``; ``compute_category_raw_metrics`` fills it.
    * ``recent_share_raw``: every observation sits at ``DATE_70D`` (age
      ``70.0``, inside the inclusive window), so every stratum is usable with
      share ``25 / 25 = 1.0``; ``(0.75 + 0.25) / 1.0 = 1.0`` (SRS §7.4).
    * ``median_age_raw``: all 50 usable ages are exactly ``70.0`` with weights
      ``3.0`` and ``1.0``; the weighted median of a constant vector is that
      constant -> ``70.0`` (SRS §7.4).
    * ``quality_raw``: the five index-usable observations per stratum have
      ``rating_average = 5.0``, so ``rating_average / 5 = 1.0`` and numerator
      equals denominator: ``(3.0 * 15 + 1.0 * 150) / (3.0 * 15 + 1.0 * 150)
      = 195 / 195 = 1.0`` (SRS §7.5). The ``None``-view rows are not
      quality-eligible (missing is not zero, SRS §1.2).
    """
    bundle = m.compute_raw_metric_bundle(mfx.DEMAND_UNEQUAL_STRATA)
    assert bundle.demand_per_asset_raw == pytest.approx(9.75, abs=1e-9)
    assert bundle.demand_median_raw == pytest.approx(4.0, abs=1e-9)
    assert bundle.breadth_raw is None
    assert bundle.recent_share_raw == pytest.approx(1.0, abs=1e-9)
    assert bundle.median_age_raw == pytest.approx(70.0, abs=1e-9)
    assert bundle.quality_raw == pytest.approx(1.0, abs=1e-9)


@pytest.mark.lreq("LREQ-MET-060")
@pytest.mark.lreq("LREQ-MET-080")
@pytest.mark.lreq("LREQ-MET-090")
@pytest.mark.lreq("LREQ-MET-070")
def test_compute_category_raw_metrics_reports_coverages_and_counts() -> None:
    """``compute_category_raw_metrics`` reports all coverages, counts, breadth.

    SRS §6.5 field set. On ``mfx.QUALITY_UNEQUAL_STRATA`` with
    ``mfx.make_breadth_input(1200, 1180)``:

    * breadth: verified ``totalCount`` -> ``verified_total_count`` /
      ``complete`` (SRS §7.3).
    * demand: rating is irrelevant to the page-view index, so all 25
      observations per stratum are demand-usable;
      ``demand_stratum_eligibility_coverage = 50/100 + 50/100 = 1.0``
      (SRS §7.2).
    * recent supply: every observation sits at ``DATE_70D`` (age ``70.0``), so
      every stratum has 25 usable dates;
      ``recent_supply_stratum_eligibility_coverage = 1.0`` and
      ``usable_recent_supply_sample_count = 25 + 25 = 50`` (SRS §7.4).
    * quality: five quality-eligible observations per stratum (the 20
      ``rating_average = None`` rows are ineligible), so
      ``quality_stratum_eligibility_coverage = 50/100 + 50/100 = 1.0`` and
      ``usable_quality_sample_count = 5 + 5 = 10`` (SRS §7.5).
    * ``raw.quality_raw = (50.0 + 100.0) / (100.0 + 100.0) = 0.75``
      (fixture arithmetic for ``mfx.QUALITY_UNEQUAL_STRATA``).
    """
    aggregate = m.compute_category_raw_metrics(
        mfx.QUALITY_UNEQUAL_STRATA,
        mfx.make_breadth_input(1200, 1180),
    )
    assert aggregate.breadth_source is BreadthSource.VERIFIED_TOTAL_COUNT
    assert aggregate.breadth_completeness_status is BreadthCompletenessStatus.COMPLETE
    assert aggregate.demand_stratum_eligibility_coverage == pytest.approx(1.0, abs=1e-9)
    assert aggregate.recent_supply_stratum_eligibility_coverage == pytest.approx(
        1.0, abs=1e-9
    )
    assert aggregate.usable_recent_supply_sample_count == 50
    assert aggregate.quality_stratum_eligibility_coverage == pytest.approx(
        1.0, abs=1e-9
    )
    assert aggregate.usable_quality_sample_count == 10
    assert aggregate.raw.quality_raw == pytest.approx(0.75, abs=1e-9)


@pytest.mark.lreq("LREQ-MET-030")
@pytest.mark.lreq("LREQ-MET-060")
@pytest.mark.lreq("LREQ-MET-080")
@pytest.mark.lreq("LREQ-MET-100")
def test_zero_population_bundle_has_null_raws_and_zero_coverages() -> None:
    """``N = 0`` makes every sample-derived raw null and every coverage ``0.0``.

    SRS §7.2/§7.4/§7.5 with ``mfx.ZERO_POPULATION`` (no strata, ``N = 0``):
    the five sample-derived raw fields are null because no ``N_h / N`` or
    ``N_h / n_h`` is ever evaluated, while the three coverages are the explicit
    computed value ``0.0`` — a value, not a null (SRS §7.2 / LREQ-MET-060).
    The paired breadth input ``(0, 0)`` is the verified zero-result category.
    """
    aggregate = m.compute_category_raw_metrics(
        mfx.ZERO_POPULATION,
        mfx.make_breadth_input(0, 0),
    )
    assert aggregate.raw.demand_per_asset_raw is None
    assert aggregate.raw.demand_median_raw is None
    assert aggregate.raw.recent_share_raw is None
    assert aggregate.raw.median_age_raw is None
    assert aggregate.raw.quality_raw is None
    assert aggregate.demand_stratum_eligibility_coverage == pytest.approx(0.0, abs=1e-9)
    assert aggregate.recent_supply_stratum_eligibility_coverage == pytest.approx(
        0.0, abs=1e-9
    )
    assert aggregate.quality_stratum_eligibility_coverage == pytest.approx(
        0.0, abs=1e-9
    )


@pytest.mark.lreq("LREQ-MET-040")
@pytest.mark.lreq("LREQ-MET-030")
@pytest.mark.lreq("LREQ-MET-080")
@pytest.mark.lreq("LREQ-MET-100")
def test_estimators_consume_chunk_7a_index_eligibility() -> None:
    """Chunk-7A-ineligible observations are excluded, never counted as zero.

    SRS §7.2 / LREQ-MET-040: the page-view index is usable only for a finite
    non-negative page-view value, a valid UTC date no later than cutoff,
    ``age_days_exact >= MIN_AGE_DAYS_FOR_RATE``, and a matched, published
    identity. ``mfx.DEMAND_INELIGIBLE_EXCLUDED`` holds one stratum with
    ``N_h = 75, n_h = 10``: five usable indices ``[1, 2, 3, 4, 5]`` and five
    Chunk-7A-ineligible observations (negative views, missing views, draft
    state, age ``29 < 30``, identity mismatch). ``u_demand_h = 5``, so
    ``DemandPerAssetRaw = (1.0 * 3.0) / 1.0 = 3.0``. Treating the ineligible
    observations as zero-views would give ``15 / 10 = 1.5``, which this test
    rejects (missing is not zero, SRS §1.2).
    """
    result = m.demand_per_asset_raw(mfx.DEMAND_INELIGIBLE_EXCLUDED)
    assert result.value == pytest.approx(3.0, abs=1e-9)
    assert abs(result.value - 1.5) > 1e-9


@pytest.mark.lreq("LREQ-MET-030")
def test_estimators_raise_valueerror_only_for_caller_contract() -> None:
    """Only caller/policy breaches raise ``ValueError`` (plan §5.0).

    A product-level value is classified, never raised (SRS §1.2 /
    LREQ-MET-010). These are caller-contract breaches, so ``ValueError`` is
    expected: a ``len(observations) != sampled_population_count`` stratum, a
    duplicate ``stratum_index``, a negative ``stratum_index``, and a
    ``min_usable_samples_per_stratum`` that is not an ``int >= 0``. A normal
    fixture call still returns its value without raising.
    """
    observations = (mfx.make_observation(),) * 5

    with pytest.raises(ValueError):
        m.demand_per_asset_raw(
            mfx.make_category_input(
                (
                    mfx.make_stratum(
                        0,
                        50,
                        observations,
                        sampled_population_count=len(observations) + 1,
                    ),
                ),
            )
        )

    with pytest.raises(ValueError):
        m.demand_per_asset_raw(
            mfx.make_category_input(
                (
                    mfx.make_stratum(0, 50, observations),
                    mfx.make_stratum(0, 50, observations),
                ),
            )
        )

    with pytest.raises(ValueError):
        m.demand_per_asset_raw(
            mfx.make_category_input((mfx.make_stratum(-1, 50, observations),))
        )

    for bad_minimum in (-1, 1.5):
        with pytest.raises(ValueError):
            m.demand_per_asset_raw(
                dataclasses.replace(
                    mfx.DEMAND_UNEQUAL_STRATA,
                    min_usable_samples_per_stratum=bad_minimum,
                )
            )

    assert m.demand_per_asset_raw(mfx.DEMAND_UNEQUAL_STRATA).value == pytest.approx(
        9.75, abs=1e-9
    )


METRICS_PATH = (
    Path(__file__).resolve().parents[1] / "src" / "niche_scout" / "metrics.py"
)


@pytest.mark.lreq("LREQ-ARCH-010")
@pytest.mark.lreq("LREQ-ARCH-020")
def test_estimators_are_pure_no_forbidden_imports_or_clock() -> None:
    """``metrics.py`` stays inside the SRS §3.3 purity boundary."""
    source = METRICS_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(METRICS_PATH))

    assert check_module(METRICS_PATH) == [], (
        "metrics.py must not import an I/O, network, DB, CLI, or clock module "
        "and must not read the clock"
    )
    assert clock_violations(tree) == []

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
    assert imported & FORBIDDEN_MODULES == set(), imported & FORBIDDEN_MODULES
    assert imported & {"random", "secrets", "uuid"} == set(), (
        "no randomness or platform-dependent identifiers (plan §11)"
    )


@pytest.mark.lreq("LREQ-ARCH-030")
def test_estimators_repeat_deterministically() -> None:
    """Identical inputs and constants give equal results (LREQ-ARCH-030).

    SRS §3.3: the same normalized input data, policy versions, and
    configuration produce the same outputs. Two identical
    ``compute_category_raw_metrics`` calls return equal dataclass values and
    equal ``raw`` bundles: the estimators use no RNG, no clock, and no
    set/dict iteration order (plan §5.0).
    """
    first = m.compute_category_raw_metrics(
        mfx.QUALITY_UNEQUAL_STRATA,
        mfx.make_breadth_input(1200, 1180),
    )
    second = m.compute_category_raw_metrics(
        mfx.QUALITY_UNEQUAL_STRATA,
        mfx.make_breadth_input(1200, 1180),
    )
    assert first == second
    assert first.raw == second.raw


@pytest.mark.lreq("LREQ-MET-040")
@pytest.mark.lreq("LREQ-MET-030")
def test_demand_explicit_zero_page_views_are_usable() -> None:
    """Explicit valid zero page views are usable and enter demand as index ``0.0``.

    SRS §7.2 / LREQ-MET-040: "An explicit valid page-view value of zero is
    usable and yields an index of zero." In ``mfx.DEMAND_EXPLICIT_ZERO`` one
    stratum has ``N_h = 75``, ``n_h = 10``: five observations carry the explicit
    valid ``product_page_views = 0`` and five carry ``product_page_views = 10``,
    all at ``DATE_70D`` (age ``70.0``). The index is ``views * 7 / 70 =
    views / 10``, so the zero-view observations contribute index ``0.0`` and the
    ten-view observations index ``1.0``. Both groups are usable, so
    ``u_demand_h = 10`` — the five zeros are values, not missing entries (missing
    is not zero, SRS §1.2).

    ``DemandPerAssetRaw = (5 * 1.0 + 5 * 0.0) / 10 = 0.5`` (single stratum, so
    the ``N_h / N`` weight renormalizes to itself; SRS §7.2 / LREQ-MET-030).
    ``DemandMedianRaw`` weights every usable observation by ``N_h / n_h =
    75 / 10 = 7.5``: ``T = 75``, half ``37.5``; the cumulative weight after the
    five sorted ``0.0`` values is exactly ``37.5`` with a next sorted value
    ``1.0``, so the exact-half branch returns ``(0.0 + 1.0) / 2 = 0.5`` (SRS
    §7.2 / LREQ-MET-050 rule, reached by this fixture). Coverage is
    ``75 / 75 = 1.0`` and the usable demand sample count is ``10``.
    """
    mean = m.demand_per_asset_raw(mfx.DEMAND_EXPLICIT_ZERO)
    assert mean.value == pytest.approx(0.5, abs=1e-9)
    assert mean.unavailable_reason is None

    median = m.demand_median_raw(mfx.DEMAND_EXPLICIT_ZERO)
    assert median.value == pytest.approx(0.5, abs=1e-9)
    assert median.unavailable_reason is None
    assert m.stratum_expansion_weight(75, 10) == pytest.approx(7.5, abs=1e-9)

    assert m.demand_stratum_eligibility_coverage(
        mfx.DEMAND_EXPLICIT_ZERO
    ) == pytest.approx(1.0, abs=1e-9)

    aggregate = m.compute_category_raw_metrics(
        mfx.DEMAND_EXPLICIT_ZERO,
        mfx.make_breadth_input(None, 0),
    )
    assert aggregate.usable_demand_sample_count == 10
