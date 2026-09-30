"""Chunk 8 analytical tests — normalization and primary scoring in ``scoring.py``.

Every expected value is a fixture constant from
``tests/fixtures/scoring_fixtures.py``, hand-derived from SRS-lean.md §8 (with the
§7.5/§9.1 below-threshold rule), matching plan
``chunk-08-normalization-and-primary-scoring.md`` §9. No network access, no clock
reads for expected values, and no writes. Float golden assertions use the
project's ``1e-9`` tolerance.

The module imports the Chunk 8 public surface from ``niche_scout.scoring``. Before
the implementation lands that import (and the fixture module's own import of
``NormalizedValues``) raises ``ImportError``, which is the required
missing-implementation shape for a test-author-first chunk.
"""

from __future__ import annotations

import ast
from pathlib import Path

import fixtures.scoring_fixtures as sfx
import pytest

from niche_scout import models, scoring
from niche_scout.models import (
    MIN_REQUIRED_COMPONENT_COVERAGE,
    BreadthCompletenessStatus,
    BreadthSource,
    EvidenceGrade,
    PageViewSemanticsStatus,
    RankabilityStatus,
    ScoreState,
)
from niche_scout.tools.check_import_boundaries import (
    FORBIDDEN_MODULES,
    check_module,
    clock_violations,
)

COMPETITION_VERIFIED: BreadthSource = BreadthSource.VERIFIED_TOTAL_COUNT
COMPETITION_COMPLETE: BreadthCompletenessStatus = BreadthCompletenessStatus.COMPLETE


def _normalized(**fields: float | None) -> object:
    """Build a ``NormalizedValues`` from explicit keyword midranks.

    ``NormalizedValues`` has no field defaults (frozen plan §5), so every one of
    the six fields is passed explicitly: each starts at ``None`` and the caller's
    keywords overlay it. An unknown keyword is a test-author bug, not a silently
    ignored field.
    """
    values: dict[str, float | None] = {
        "demand_per_asset_raw": None,
        "demand_median_raw": None,
        "breadth_raw": None,
        "recent_share_raw": None,
        "median_age_raw": None,
        "quality_raw": None,
    }
    unknown = set(fields) - set(values)
    if unknown:
        raise TypeError(f"unknown NormalizedValues field(s): {sorted(unknown)}")
    values.update(fields)
    return scoring.NormalizedValues(**values)


def _components(
    demand: float | None,
    competition: float | None,
    recent_supply: float | None,
    quality: float | None,
) -> object:
    """Build a literal ``ComponentValues`` for the composite tests."""
    return scoring.ComponentValues(
        demand=demand,
        competition=competition,
        recent_supply=recent_supply,
        quality=quality,
    )


# ---------------------------------------------------------------------------
# Midrank (LREQ-NRM-030)
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-NRM-030")
@pytest.mark.lreq("LREQ-TST-010")
def test_midrank_golden_vectors() -> None:
    """``P_ref(x) = (L + 0.5 * E) / m`` for every hand-derived vector (SRS §8.1).

    ``sfx.MIDRANK_GOLDEN_VECTORS`` states the target, the usable reference, and
    the expected ``(L + 0.5 * E) / m`` written out in the fixture comments:
    ``(2.0, (1,2,3)) -> 0.5``, ``(1.0, (1,1,3)) -> 1/3``, ``(1.0, (2,3,4)) -> 0.0``
    (minimum), ``(4.0, (1,2,3)) -> 1.0`` (maximum), the all-equal cases, and the
    two-cluster case. The null target and the empty reference return ``None``, not
    a fabricated zero (SRS §8.1: "If ``m = 0`` or ``x`` is null, the normalized
    value is null").

    Plan §9 writes ``(5.0, (2.0, 2.0, 2.0)) -> 0.0`` labelled "target above all";
    the SRS formula gives ``L = 3, E = 0, m = 3 -> 1.0``. This test asserts the
    SRS value and the mismatch is reported as a DISPUTE in the run result.
    """
    for label, target, reference, expected in sfx.MIDRANK_GOLDEN_VECTORS:
        result = scoring.midrank(target, reference)
        if expected is None:
            assert result is None, label
        else:
            assert result == pytest.approx(expected, abs=1e-9), label


@pytest.mark.lreq("LREQ-NRM-030")
def test_midrank_ties_receive_same_midrank() -> None:
    """Ties receive the same midrank and duplicates count in ``m`` (SRS §8.1).

    Against ``(1.0, 1.0, 3.0)`` both equal targets give
    ``L = 0, E = 2, m = 3 -> 1/3``. ``sfx.MIDRANK_DUPLICATE_VECTOR`` keeps the
    duplicate reference values repeated: target ``2.0`` against
    ``(1.0, 2.0, 2.0, 2.0)`` gives ``L = 1, E = 3, m = 4 -> (1 + 1.5)/4 = 0.625``.
    Also, an explicit valid zero is a value, never a missing entry: midrank of
    ``0.0`` against ``(0.0, 1.0, 2.0)`` is ``(0 + 0.5) / 3 = 1/6``.
    """
    assert scoring.midrank(1.0, (1.0, 1.0, 3.0)) == pytest.approx(
        scoring.midrank(1.0, (1.0, 1.0, 3.0)), abs=1e-9
    )
    target, reference, expected = sfx.MIDRANK_DUPLICATE_VECTOR
    assert scoring.midrank(target, reference) == pytest.approx(expected, abs=1e-9)
    assert scoring.midrank(0.0, (0.0, 1.0, 2.0)) == pytest.approx(
        sfx.MIDRANK_EXPLICIT_ZERO_EXPECTED, abs=1e-9
    )


@pytest.mark.lreq("LREQ-NRM-030")
def test_midrank_all_equal_reference() -> None:
    """An all-equal reference ranks a target above it at ``1.0`` (SRS §8.1).

    Reference ``(2.0, 2.0, 2.0)``: target ``5.0`` gives ``L = 3, E = 0, m = 3
    -> 1.0`` and target ``2.0`` gives ``L = 0, E = 3, m = 3 -> 0.5``.
    """
    assert scoring.midrank(5.0, (2.0, 2.0, 2.0)) == pytest.approx(1.0, abs=1e-9)
    assert scoring.midrank(2.0, (2.0, 2.0, 2.0)) == pytest.approx(0.5, abs=1e-9)


@pytest.mark.lreq("LREQ-NRM-030")
def test_midrank_null_target_or_empty_reference_returns_none() -> None:
    """A null target or an empty usable reference is null, never zero (SRS §8.1).

    ``m = 0`` and ``x is None`` both yield ``None``; else a "no reference
    available" outcome would be misread as the fabricated value ``0.0``
    (missing is not zero, SRS §1.2).
    """
    assert scoring.midrank(None, (1.0, 2.0, 3.0)) is None
    assert scoring.midrank(1.0, ()) is None
    assert scoring.midrank(None, ()) is None


@pytest.mark.lreq("LREQ-NRM-030")
def test_midrank_rejects_non_finite_values() -> None:
    """A non-finite target or reference element raises ``ValueError`` (plan §5 D4).

    A ``nan``/``inf`` raw or reference value is a caller breach, mirroring
    ``metrics.weighted_median``: it raises rather than fabricating a midrank.
    """
    for label, target, reference in sfx.MIDRANK_INVALID_VECTORS:
        with pytest.raises(ValueError):
            scoring.midrank(target, reference)
        assert label


# ---------------------------------------------------------------------------
# Leave-one-out reference (LREQ-NRM-010, LREQ-NRM-020)
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-NRM-010")
def test_leave_one_out_reference_excludes_target() -> None:
    """A category never appears in its own reference (SRS §8.1; plan §10).

    For the 8-category run, target ``"c-3"`` (demand raw ``3.0``, breadth
    ``40.0``) is absent from every value tuple, which holds the seven peers in
    input order: demand ``(0,1,2,4,5,6,7)`` and breadth
    ``(10,100,20,50,0,90,70)``. Reversing the input keeps the same peer set, so
    the target's midrank is unchanged.
    """
    reference = scoring.leave_one_out_reference(sfx.EIGHT_CATEGORY_RUN, "c-3")
    assert reference.target_category == "c-3"
    assert reference.reference_size == 7
    assert reference.demand_per_asset_raw == tuple(
        float(index) for index in range(8) if index != 3
    )
    assert reference.breadth_raw == tuple(
        sfx.BREADTH_COUNTS_EIGHT_RUN[index] for index in range(8) if index != 3
    )
    reversed_reference = scoring.leave_one_out_reference(
        tuple(reversed(sfx.EIGHT_CATEGORY_RUN)), "c-3"
    )
    assert set(reversed_reference.breadth_raw) == set(reference.breadth_raw)
    assert scoring.midrank(40.0, reversed_reference.breadth_raw) == pytest.approx(
        scoring.midrank(40.0, reference.breadth_raw), abs=1e-9
    )


@pytest.mark.lreq("LREQ-NRM-020")
def test_reference_size_is_category_count_minus_one() -> None:
    """``reference_size = category_count - 1`` for every run size (SRS §8.1).

    The one-category run gives ``0``; the 8- and 21-category runs give ``7`` and
    ``20`` (``sfx.REFERENCE_SIZE_VECTORS``). ``reference_size`` is the category
    count minus one, not the number of usable reference values.
    """
    single = scoring.leave_one_out_reference(sfx.SINGLE_CATEGORY_RUN, "c-0")
    assert single.reference_size == 0
    assert single.reference_size == len(sfx.SINGLE_CATEGORY_RUN) - 1
    for label, run, category, expected in sfx.REFERENCE_SIZE_VECTORS:
        reference = scoring.leave_one_out_reference(run, category)
        assert reference.reference_size == expected, label
        assert reference.reference_size == len(run) - 1, label


@pytest.mark.lreq("LREQ-NRM-020")
@pytest.mark.lreq("LREQ-TST-060")
def test_eight_and_twenty_one_category_run_reference_sizes() -> None:
    """A 21-category run has 20 leave-one-out peers, never 21 (SRS §8.1).

    ``models.STRONG_REFERENCE_CATEGORY_COUNT`` is 21; the strong-reference run's
    target ``"c-10"`` therefore has ``reference_size == 20`` and its demand peer
    tuple is ``(0.0..9.0, 11.0..20.0)`` (``m = 20``). The target's own
    ``10.0`` is excluded, giving ``P_ref(10.0) = 10/20 = 0.5``. An 8-category run
    gives ``reference_size == 7``.
    """
    assert models.STRONG_REFERENCE_CATEGORY_COUNT == 21
    eight = scoring.leave_one_out_reference(sfx.EIGHT_CATEGORY_RUN, "c-3")
    assert eight.reference_size == 7
    assert len(eight.demand_per_asset_raw) == 7
    strong = scoring.leave_one_out_reference(
        sfx.TWENTY_ONE_CATEGORY_RUN, sfx.STRONG_CATEGORY
    )
    assert strong.reference_size == 20
    assert strong.reference_size != 21
    assert strong.demand_per_asset_raw == sfx.STRONG_REFERENCE_EXPECTED_DEMAND
    assert scoring.midrank(10.0, strong.demand_per_asset_raw) == pytest.approx(
        0.5, abs=1e-9
    )


@pytest.mark.lreq("LREQ-NRM-020")
def test_field_specific_usable_reference_counts() -> None:
    """Each field's usable count is its non-null peer count (SRS §8.1).

    ``sfx.FIELD_USABLE_COUNT_VECTORS`` pairs each run with its target category
    and expected ``(reference_size, quality count, other-field count)``: the
    one-category run is all zeros; the ordinary 8- and 21-category runs have
    every field present (``7`` and ``20``); ``sfx.FIELD_USABLE_COUNT_RUN`` has
    two peers with ``quality_raw = None``, so only ``quality_raw`` drops to
    ``5`` while the other five fields keep ``7``. Counts are stored separately
    per field.
    """
    for (
        label,
        run,
        category,
        ref_size,
        quality_count,
        other_count,
    ) in sfx.FIELD_USABLE_COUNT_VECTORS:
        reference = scoring.leave_one_out_reference(run, category)
        counts = reference.field_usable_counts
        assert reference.reference_size == ref_size, label
        assert counts.quality_raw == quality_count, label
        assert counts.demand_per_asset_raw == other_count, label
        assert counts.demand_median_raw == other_count, label
        assert counts.breadth_raw == other_count, label
        assert counts.recent_share_raw == other_count, label
        assert counts.median_age_raw == other_count, label


@pytest.mark.lreq("LREQ-NRM-010")
def test_leave_one_out_reference_rejects_absent_or_duplicate_target() -> None:
    """Caller breaches raise ``ValueError`` (plan §5 D4).

    An empty run, an absent/empty ``target_category``, and two entries sharing a
    ``category`` are caller breaches, never a fabricated reference.
    """
    with pytest.raises(ValueError):
        scoring.leave_one_out_reference((), "c-0")
    with pytest.raises(ValueError):
        scoring.leave_one_out_reference(sfx.EIGHT_CATEGORY_RUN, "absent")
    with pytest.raises(ValueError):
        scoring.leave_one_out_reference(sfx.EIGHT_CATEGORY_RUN, "")
    duplicate_run = (
        sfx.make_category_raw_metrics("dup", sfx.make_raw_bundle(breadth_raw=1.0)),
        sfx.make_category_raw_metrics("dup", sfx.make_raw_bundle(breadth_raw=2.0)),
    )
    with pytest.raises(ValueError):
        scoring.leave_one_out_reference(duplicate_run, "dup")


# ---------------------------------------------------------------------------
# Field-specific normalization (LREQ-NRM-040)
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-NRM-040")
def test_normalize_raw_metrics_independently() -> None:
    """All six fields normalize independently against their own reference.

    SRS §8.1 / LREQ-NRM-040: the six raws are normalized independently and no log
    transform applies (strictly monotone transforms do not change midrank order).
    Each field is matched to its own reference tuple. Against
    ``(1, 2, 3, 4, 5)`` the hand-derived results are ``0.5, 1.0, 0.0, 0.1, 1.0,
    0.7`` (``sfx.NORMALIZE_INDEPENDENT_EXPECTED``). Changing another field's
    reference cannot change a field's result.
    """
    reference = scoring.LeaveOneOutReference(
        target_category="t",
        reference_size=len(sfx.NORMALIZE_REFERENCE_TUPLES),
        demand_per_asset_raw=sfx.NORMALIZE_REFERENCE_TUPLES,
        demand_median_raw=sfx.NORMALIZE_REFERENCE_TUPLES,
        breadth_raw=sfx.NORMALIZE_REFERENCE_TUPLES,
        recent_share_raw=sfx.NORMALIZE_REFERENCE_TUPLES,
        median_age_raw=sfx.NORMALIZE_REFERENCE_TUPLES,
        quality_raw=sfx.NORMALIZE_REFERENCE_TUPLES,
    )
    normalized = scoring.normalize_raw_metrics(sfx.NORMALIZE_INDEPENDENT_RAW, reference)
    actual = (
        normalized.demand_per_asset_raw,
        normalized.demand_median_raw,
        normalized.breadth_raw,
        normalized.recent_share_raw,
        normalized.median_age_raw,
        normalized.quality_raw,
    )
    for result, expected in zip(actual, sfx.NORMALIZE_INDEPENDENT_EXPECTED):
        assert result == pytest.approx(expected, abs=1e-9)


@pytest.mark.lreq("LREQ-NRM-040")
def test_normalize_raw_metrics_null_target_and_null_reference() -> None:
    """A null raw value or an empty field reference is null for that field.

    SRS §8.1 / LREQ-NRM-040. With every other field against ``(1, 2, 3, 4, 5)``
    (raw ``5.0`` -> ``(4 + 0.5)/5 = 0.9``), a ``quality_raw = None`` and an empty
    ``quality_raw`` reference both yield ``None`` for quality. A non-null raw
    ``3.0`` with an empty demand reference yields ``None`` for that field only.
    """
    null_reference = scoring.LeaveOneOutReference(
        target_category="t",
        reference_size=5,
        demand_per_asset_raw=sfx.NORMALIZE_REFERENCE_TUPLES,
        demand_median_raw=sfx.NORMALIZE_REFERENCE_TUPLES,
        breadth_raw=sfx.NORMALIZE_REFERENCE_TUPLES,
        recent_share_raw=sfx.NORMALIZE_REFERENCE_TUPLES,
        median_age_raw=sfx.NORMALIZE_REFERENCE_TUPLES,
        quality_raw=(),
    )
    normalized = scoring.normalize_raw_metrics(sfx.NORMALIZE_NULL_RAW, null_reference)
    quality_expected = sfx.NORMALIZE_NULL_EXPECTED[-1]
    assert quality_expected is None
    assert normalized.quality_raw is None
    assert normalized.demand_per_asset_raw == pytest.approx(0.9, abs=1e-9)
    assert normalized.demand_median_raw == pytest.approx(0.9, abs=1e-9)
    assert normalized.breadth_raw == pytest.approx(0.9, abs=1e-9)
    assert normalized.recent_share_raw == pytest.approx(0.9, abs=1e-9)
    assert normalized.median_age_raw == pytest.approx(0.9, abs=1e-9)

    empty_demand_reference = scoring.LeaveOneOutReference(
        target_category="t",
        reference_size=5,
        demand_per_asset_raw=(),
        demand_median_raw=sfx.NORMALIZE_REFERENCE_TUPLES,
        breadth_raw=sfx.NORMALIZE_REFERENCE_TUPLES,
        recent_share_raw=sfx.NORMALIZE_REFERENCE_TUPLES,
        median_age_raw=sfx.NORMALIZE_REFERENCE_TUPLES,
        quality_raw=sfx.NORMALIZE_REFERENCE_TUPLES,
    )
    mixed = scoring.normalize_raw_metrics(
        sfx.NORMALIZE_INDEPENDENT_RAW, empty_demand_reference
    )
    assert mixed.demand_per_asset_raw is None
    assert mixed.demand_median_raw == pytest.approx(1.0, abs=1e-9)


# ---------------------------------------------------------------------------
# Demand component D (LREQ-SCR-010)
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SCR-010")
def test_demand_component_both_one_or_neither_field() -> None:
    """``D0`` weights both sub-signals, uses the one available, or is null.

    SRS §8.2: ``D0 = 0.60 * a + 0.40 * b`` when both midranks are available;
    the single available value when exactly one is; unavailable when neither is.
    ``a = 1.0, b = 0.0 -> 0.6``; the asymmetric ``a = 0.0, b = 1.0 -> 0.4``
    proves the 0.60/0.40 subweights are not swapped; only ``a = 0.8 -> 0.8``;
    ``a = 0.0, b = 0.0 -> 0.0`` is the explicit valid zero; neither -> ``None``.
    At coverage ``1.0`` no shrinkage changes these values.
    """
    both = _normalized(demand_per_asset_raw=1.0, demand_median_raw=0.0)
    assert scoring.demand_component(
        both, demand_stratum_eligibility_coverage=1.0
    ) == pytest.approx(0.6, abs=1e-9)
    swapped = _normalized(demand_per_asset_raw=0.0, demand_median_raw=1.0)
    assert scoring.demand_component(
        swapped, demand_stratum_eligibility_coverage=1.0
    ) == pytest.approx(0.4, abs=1e-9)
    only = _normalized(demand_per_asset_raw=sfx.D_ONLY_SUBSIGNAL_EXPECTED)
    assert scoring.demand_component(
        only, demand_stratum_eligibility_coverage=1.0
    ) == pytest.approx(0.8, abs=1e-9)
    explicit_zero = _normalized(demand_per_asset_raw=0.0, demand_median_raw=0.0)
    assert scoring.demand_component(
        explicit_zero, demand_stratum_eligibility_coverage=1.0
    ) == pytest.approx(0.0, abs=1e-9)
    neither = _normalized()
    assert (
        scoring.demand_component(neither, demand_stratum_eligibility_coverage=1.0)
        is None
    )


@pytest.mark.lreq("LREQ-SCR-010")
def test_demand_component_coverage_shrinkage_and_clamp() -> None:
    """``D = clamp(0.5 + coverage * (D0 - 0.5), 0, 1)`` (SRS §8.2).

    With ``D0 = 0.6``: coverage ``1.0 -> 0.6`` and ``0.5 -> 0.55``
    (``sfx.D_BOTH_SUBSIGNAL_VECTORS``), where ``0.50`` is the available boundary.
    A coverage strictly below ``MIN_REQUIRED_COMPONENT_COVERAGE`` (``0.50``) is
    unavailable before any shrinkage (SRS §7.5 / §9.1; plan §5 Q1), asserted by
    ``test_below_minimum_component_coverage_is_unavailable``. ``D0 = 1.0`` clamps
    to ``1.0`` and ``D0 = 0.0`` clamps to ``0.0``. A non-finite or out-of-range
    ``min_required_component_coverage`` is a policy breach -> ``ValueError``.
    """
    both = _normalized(demand_per_asset_raw=1.0, demand_median_raw=0.0)
    for label, coverage, expected in sfx.D_BOTH_SUBSIGNAL_VECTORS:
        assert scoring.demand_component(
            both, demand_stratum_eligibility_coverage=coverage
        ) == pytest.approx(expected, abs=1e-9), label
    high = _normalized(demand_per_asset_raw=1.0, demand_median_raw=1.0)
    assert scoring.demand_component(
        high, demand_stratum_eligibility_coverage=1.0
    ) == pytest.approx(1.0, abs=1e-9)
    low = _normalized(demand_per_asset_raw=0.0, demand_median_raw=0.0)
    assert scoring.demand_component(
        low, demand_stratum_eligibility_coverage=1.0
    ) == pytest.approx(0.0, abs=1e-9)
    for bad_threshold in (float("nan"), 1.5, -0.1):
        with pytest.raises(ValueError):
            scoring.demand_component(
                both,
                demand_stratum_eligibility_coverage=1.0,
                min_required_component_coverage=bad_threshold,
            )


# ---------------------------------------------------------------------------
# Competition component C (LREQ-SCR-020)
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SCR-020")
def test_competition_component_requires_verified_complete_breadth() -> None:
    """``C`` is available only with verified and complete breadth (SRS §8.2).

    ``sfx.COMPETITION_VECTORS`` requires
    ``breadth_source is VERIFIED_TOTAL_COUNT`` **and**
    ``breadth_completeness_status is COMPLETE``; a fallback source, an incomplete
    status, and a null ``P_ref(BreadthRaw)`` each yield ``None``. A verified
    ``P_ref = 0.25 -> 0.75``.
    """
    for label, midrank, source, status, expected in sfx.COMPETITION_VECTORS:
        normalized = _normalized(breadth_raw=midrank)
        result = scoring.competition_component(
            normalized,
            breadth_source=source,
            breadth_completeness_status=status,
        )
        if expected is None:
            assert result is None, label
        else:
            assert result == pytest.approx(expected, abs=1e-9), label


@pytest.mark.lreq("LREQ-SCR-020")
def test_competition_component_inverts_midrank_and_clamps() -> None:
    """``C = clamp(1 - P_ref(BreadthRaw), 0, 1)`` with no coverage gate.

    SRS §8.2. Verified + complete breadth with ``P_ref = 0.25 -> 0.75``; a
    verified zero-result breadth (``P_ref = 0.0``) -> ``1.0`` (an explicit valid
    zero is a value); ``P_ref = 1.0 -> 0.0``. ``C`` takes no stratum eligibility
    coverage parameter, so it is never affected by the sample-derived coverage
    threshold (LREQ-SCR-020).
    """
    assert scoring.competition_component(
        _normalized(breadth_raw=0.25),
        breadth_source=COMPETITION_VERIFIED,
        breadth_completeness_status=COMPETITION_COMPLETE,
    ) == pytest.approx(0.75, abs=1e-9)
    assert scoring.competition_component(
        _normalized(breadth_raw=0.0),
        breadth_source=COMPETITION_VERIFIED,
        breadth_completeness_status=COMPETITION_COMPLETE,
    ) == pytest.approx(1.0, abs=1e-9)
    assert scoring.competition_component(
        _normalized(breadth_raw=1.0),
        breadth_source=COMPETITION_VERIFIED,
        breadth_completeness_status=COMPETITION_COMPLETE,
    ) == pytest.approx(0.0, abs=1e-9)


# ---------------------------------------------------------------------------
# Recent supply component R (LREQ-SCR-030)
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SCR-030")
def test_recent_supply_component_both_one_or_neither_field() -> None:
    """``R0 = 1 - Rpressure0`` uses both, one, or neither pressure term.

    SRS §8.2: ``Rpressure0 = 0.70 * s + 0.30 * (1 - a)`` when both midranks are
    available. ``s = 0.9, a = 0.2 -> Rpressure0 = 0.87, R0 = 0.13``. With only
    ``s = 0.9`` the single pressure term is ``0.9`` and ``R0 = 0.1``; with only
    ``a = 0.2`` it is ``1 - 0.2 = 0.8`` and ``R0 = 0.2`` (plan §12 D7: the single
    term and its renormalized subweight coincide). Neither -> ``None``.
    """
    both = _normalized(recent_share_raw=0.9, median_age_raw=0.2)
    assert scoring.recent_supply_component(
        both, recent_supply_stratum_eligibility_coverage=1.0
    ) == pytest.approx(0.13, abs=1e-9)
    for label, share, age, coverage, expected in sfx.R_ONE_SUBSIGNAL_VECTORS:
        normalized = _normalized(recent_share_raw=share, median_age_raw=age)
        result = scoring.recent_supply_component(
            normalized, recent_supply_stratum_eligibility_coverage=coverage
        )
        if expected is None:
            assert result is None, label
        else:
            assert result == pytest.approx(expected, abs=1e-9), label


@pytest.mark.lreq("LREQ-SCR-030")
def test_recent_supply_component_coverage_shrinkage() -> None:
    """``R = clamp(0.5 + coverage * (R0 - 0.5), 0, 1)`` (SRS §8.2).

    With ``R0 = 0.13``: coverage ``1.0 -> 0.13`` and ``0.5 -> 0.315``
    (``sfx.R_BOTH_SUBSIGNAL_VECTORS``), where ``0.50`` is the available boundary.
    A coverage strictly below ``MIN_REQUIRED_COMPONENT_COVERAGE`` (``0.50``) is
    unavailable before any shrinkage (SRS §7.5 / §9.1; plan §5 Q1), asserted by
    ``test_below_minimum_component_coverage_is_unavailable``. A non-finite or
    out-of-range threshold is a policy breach -> ``ValueError``.
    """
    both = _normalized(recent_share_raw=0.9, median_age_raw=0.2)
    for label, coverage, expected in sfx.R_BOTH_SUBSIGNAL_VECTORS:
        assert scoring.recent_supply_component(
            both, recent_supply_stratum_eligibility_coverage=coverage
        ) == pytest.approx(expected, abs=1e-9), label
    for bad_threshold in (float("nan"), 1.5, -0.1):
        with pytest.raises(ValueError):
            scoring.recent_supply_component(
                both,
                recent_supply_stratum_eligibility_coverage=1.0,
                min_required_component_coverage=bad_threshold,
            )


# ---------------------------------------------------------------------------
# Quality component Q (LREQ-SCR-040)
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SCR-040")
def test_quality_component_null_or_shrunk() -> None:
    """``Q0 = 1 - P_ref(QualityRaw)`` with coverage shrinkage (SRS §8.2).

    ``sfx.Q_SHRINKAGE_VECTORS``: ``P_ref = 0.4 -> Q0 = 0.6`` and
    coverage ``1.0 -> 0.6``, ``0.5 -> 0.55``; ``P_ref = 1.0 -> Q0 = 0.0`` and
    ``P_ref = 0.0 -> Q0 = 1.0`` (explicit valid values). A null quality midrank
    yields ``None`` at every coverage (``sfx.Q_NULL_QUALITY_VECTORS``).
    """
    for label, midrank, coverage, expected in sfx.Q_SHRINKAGE_VECTORS:
        normalized = _normalized(quality_raw=midrank)
        result = scoring.quality_component(
            normalized, quality_stratum_eligibility_coverage=coverage
        )
        if expected is None:
            assert result is None, label
        else:
            assert result == pytest.approx(expected, abs=1e-9), label
    for label, midrank, coverage in sfx.Q_NULL_QUALITY_VECTORS:
        assert (
            scoring.quality_component(
                _normalized(quality_raw=midrank),
                quality_stratum_eligibility_coverage=coverage,
            )
            is None
        ), label


@pytest.mark.lreq("LREQ-SCR-010")
@pytest.mark.lreq("LREQ-SCR-030")
@pytest.mark.lreq("LREQ-SCR-040")
def test_below_minimum_component_coverage_is_unavailable() -> None:
    """Coverage below the policy threshold makes ``D``/``R``/``Q`` unavailable.

    SRS §7.5 / §9.1 with ``MIN_REQUIRED_COMPONENT_COVERAGE = 0.50``: strictly
    below the threshold the component is ``None`` and receives no composite
    weight; exactly ``0.50`` is available. For ``D`` the below/at/above cases are
    ``None / 0.55 / 0.575``, for ``R`` ``None / 0.315 / 0.2225``, and for ``Q``
    ``None / 0.55``. ``C`` has no such vector because it is not sample-derived.
    """
    assert MIN_REQUIRED_COMPONENT_COVERAGE == pytest.approx(0.50, abs=1e-9)
    demand = _normalized(demand_per_asset_raw=1.0, demand_median_raw=0.0)
    for label, coverage, expected in sfx.D_THRESHOLD_VECTORS:
        result = scoring.demand_component(
            demand, demand_stratum_eligibility_coverage=coverage
        )
        if expected is None:
            assert result is None, label
        else:
            assert result == pytest.approx(expected, abs=1e-9), label
    recent = _normalized(recent_share_raw=0.9, median_age_raw=0.2)
    for label, coverage, expected in sfx.R_THRESHOLD_VECTORS:
        result = scoring.recent_supply_component(
            recent, recent_supply_stratum_eligibility_coverage=coverage
        )
        if expected is None:
            assert result is None, label
        else:
            assert result == pytest.approx(expected, abs=1e-9), label
    quality = _normalized(quality_raw=0.4)
    for label, coverage, expected in sfx.Q_THRESHOLD_VECTORS:
        result = scoring.quality_component(
            quality, quality_stratum_eligibility_coverage=coverage
        )
        if expected is None:
            assert result is None, label
        else:
            assert result == pytest.approx(expected, abs=1e-9), label


# ---------------------------------------------------------------------------
# Contradicted page-view semantics (LREQ-SCR-050)
# ---------------------------------------------------------------------------

CONTRADICTED_NORMALIZED: object = _normalized(
    demand_per_asset_raw=1.0,
    demand_median_raw=0.0,
    breadth_raw=0.25,
    recent_share_raw=0.9,
    median_age_raw=0.2,
    quality_raw=0.4,
)


def _components_for_status(status: PageViewSemanticsStatus) -> object:
    """``compute_components`` over the full input at full coverage for ``status``."""
    return scoring.compute_components(
        CONTRADICTED_NORMALIZED,
        demand_stratum_eligibility_coverage=1.0,
        recent_supply_stratum_eligibility_coverage=1.0,
        quality_stratum_eligibility_coverage=1.0,
        breadth_source=COMPETITION_VERIFIED,
        breadth_completeness_status=COMPETITION_COMPLETE,
        page_view_semantics_status=status,
    )


@pytest.mark.lreq("LREQ-SCR-050")
def test_contradicted_page_views_disable_demand_and_quality() -> None:
    """``contradicted`` makes ``D`` and ``Q`` unavailable (SRS §8.2).

    Under ``UNVALIDATED`` the full input yields ``D = 0.6`` and ``Q = 0.6``;
    under ``CONTRADICTED`` both become ``None``. The status is consumed from the
    caller, never re-detected (interfaces/chunk-05.md §5.8).
    """
    unvalidated = _components_for_status(PageViewSemanticsStatus.UNVALIDATED)
    assert unvalidated.demand == pytest.approx(0.6, abs=1e-9)
    assert unvalidated.quality == pytest.approx(0.6, abs=1e-9)
    contradicted = _components_for_status(PageViewSemanticsStatus.CONTRADICTED)
    assert contradicted.demand is None
    assert contradicted.quality is None


@pytest.mark.lreq("LREQ-SCR-050")
def test_contradicted_page_views_keep_competition_and_recent_supply() -> None:
    """``C`` and ``R`` are unchanged by contradicted semantics (SRS §8.2).

    ``C = 0.75`` (breadth midrank ``0.25``) and ``R = 0.13`` are identical under
    both statuses, so ``available_component_count`` drops from 4 to 2 rather than
    to 0.
    """
    unvalidated = _components_for_status(PageViewSemanticsStatus.UNVALIDATED)
    contradicted = _components_for_status(PageViewSemanticsStatus.CONTRADICTED)
    assert contradicted.competition == pytest.approx(unvalidated.competition, abs=1e-9)
    assert contradicted.recent_supply == pytest.approx(
        unvalidated.recent_supply, abs=1e-9
    )
    assert contradicted.competition == pytest.approx(0.75, abs=1e-9)
    assert contradicted.recent_supply == pytest.approx(0.13, abs=1e-9)
    assert unvalidated.available_component_count == 4
    assert contradicted.available_component_count == 2


# ---------------------------------------------------------------------------
# Composite and score state (LREQ-SCR-060)
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SCR-060")
def test_fewer_than_two_components_score_unavailable() -> None:
    """Fewer than two available components -> null score, ``unavailable``.

    SRS §8.3 / LREQ-SCR-060: with one component the score is ``null`` and
    ``score_state = unavailable``; the available weight is still reported
    (``0.35`` for ``D``). ``renormalized_composite`` raises ``ValueError`` when a
    weight is missing, negative, or non-finite (plan §5).
    """
    one = scoring.renormalized_composite(
        _components(0.8, None, None, None), sfx.FIXED_PRIMARY_WEIGHTS
    )
    assert one.market_opportunity_score is None
    assert one.score_state is ScoreState.UNAVAILABLE
    assert one.available_component_count == 1
    assert one.available_weight == pytest.approx(0.35, abs=1e-9)
    none_available = scoring.renormalized_composite(
        _components(None, None, None, None), sfx.FIXED_PRIMARY_WEIGHTS
    )
    assert none_available.market_opportunity_score is None
    assert none_available.score_state is ScoreState.UNAVAILABLE
    assert none_available.available_component_count == 0
    assert none_available.available_weight == pytest.approx(0.0, abs=1e-9)
    full = _components(0.8, 0.6, 0.4, 0.2)
    for bad_weights in (
        {"D": 0.35, "C": 0.30, "R": 0.20},
        {"D": 0.35, "C": 0.30, "R": 0.20, "Q": -0.15},
        {"D": 0.35, "C": 0.30, "R": 0.20, "Q": float("nan")},
    ):
        with pytest.raises(ValueError):
            scoring.renormalized_composite(full, bad_weights)


@pytest.mark.lreq("LREQ-SCR-060")
def test_two_or_three_components_score_partial() -> None:
    """``partial`` for 2-3 available components, ``available`` for 4.

    SRS §8.3 / LREQ-SCR-060: ``score_state`` is ``available`` when all four
    components are available, otherwise ``partial`` when at least two are, and
    ``unavailable`` below two. This test walks ``sfx.COMPOSITE_VECTORS`` and
    derives the expected state from the count.
    """
    for label, components, _score, _weight in sfx.COMPOSITE_VECTORS:
        result = scoring.renormalized_composite(
            _components(*components), sfx.FIXED_PRIMARY_WEIGHTS
        )
        count = result.available_component_count
        if count >= 4:
            expected_state = ScoreState.AVAILABLE
        elif count >= 2:
            expected_state = ScoreState.PARTIAL
        else:
            expected_state = ScoreState.UNAVAILABLE
        assert result.score_state is expected_state, label
        assert count == sum(component is not None for component in components), label


@pytest.mark.lreq("LREQ-SCR-060")
def test_available_component_weight_renormalization() -> None:
    """``W_A`` sums available weights and renormalizes ``S_available``.

    SRS §8.3: ``W_A = sum(weights of available components)``,
    ``S_available = sum(w_x * x) / W_A``, and
    ``score = clamp(0.5 + W_A * (S_available - 0.5), 0, 1)``. The hand-derived
    ``sfx.COMPOSITE_VECTORS`` cover four/three/two/one/none available components
    and the low-coverage-``D`` case whose excluded ``W_D`` leaves ``W_A = 0.65``
    and score ``0.465``.
    """
    for label, components, expected_score, expected_weight in sfx.COMPOSITE_VECTORS:
        result = scoring.renormalized_composite(
            _components(*components), sfx.FIXED_PRIMARY_WEIGHTS
        )
        assert result.available_weight == pytest.approx(expected_weight, abs=1e-9), (
            label
        )
        if expected_score is None:
            assert result.market_opportunity_score is None, label
        else:
            assert result.market_opportunity_score == pytest.approx(
                expected_score, abs=1e-9
            ), label
    low_coverage = scoring.renormalized_composite(
        _components(None, 0.6, 0.4, 0.2), sfx.FIXED_PRIMARY_WEIGHTS
    )
    assert low_coverage.available_weight == pytest.approx(0.65, abs=1e-9)
    assert low_coverage.market_opportunity_score == pytest.approx(0.465, abs=1e-9)


@pytest.mark.lreq("LREQ-SCR-060")
@pytest.mark.lreq("LREQ-TST-060")
def test_balanced_primary_matches_balanced_sensitivity_policy() -> None:
    """Balanced primary scoring uses exactly the balanced sensitivity weights.

    SRS §8.3 / plan §10: ``models.W_D/W_C/W_R/W_Q = 0.35/0.30/0.20/0.15`` and
    ``models.SENSITIVITY_POLICIES["balanced"]`` are the same mapping, so
    ``balanced_composite(c)`` equals
    ``renormalized_composite(c, SENSITIVITY_POLICIES["balanced"])`` for every
    vector, including the low-coverage-``D`` case where ``W_A`` excludes
    ``W_D``.
    """
    assert (models.W_D, models.W_C, models.W_R, models.W_Q) == (
        0.35,
        0.30,
        0.20,
        0.15,
    )
    assert sfx.FIXED_PRIMARY_WEIGHTS == models.SENSITIVITY_POLICIES["balanced"]
    balanced = models.SENSITIVITY_POLICIES["balanced"]
    for label, components in sfx.COMPOSITE_COMPONENT_OBJECTS:
        assert scoring.balanced_composite(components) == scoring.renormalized_composite(
            components, balanced
        ), label
    low_coverage = _components(None, 0.6, 0.4, 0.2)
    assert scoring.balanced_composite(low_coverage) == scoring.renormalized_composite(
        low_coverage, balanced
    )
    assert scoring.balanced_composite(low_coverage).available_weight == pytest.approx(
        0.65, abs=1e-9
    )


@pytest.mark.lreq("LREQ-SCR-060")
def test_score_category_integration_and_score_state() -> None:
    """``score_category`` wires reference -> normalized -> components -> composite.

    ``sfx.SCORE_CATEGORY_RUN``'s target ``"c-1"`` (3 categories) yields
    ``D = 0.30, C = 1.0, R = 0.0, Q = 1.0`` and
    ``W_A = 1.0, S = 0.555, score = 0.555``, ``available``, count ``4``
    (``sfx.SCORE_CATEGORY_EXPECTED``). ``rankability_status`` and
    ``evidence_grade`` stay at their Chunk 0 defaults because Chunk 8 assigns
    neither. Under ``CONTRADICTED`` only ``C`` and ``R`` remain, giving
    ``W_A = 0.5, S = 0.6, score = 0.55``, ``partial``, count ``2``.
    """
    target = sfx.SCORE_CATEGORY_RUN[1]
    result = scoring.score_category(
        target,
        sfx.SCORE_CATEGORY_RUN,
        page_view_semantics_status=PageViewSemanticsStatus.UNVALIDATED,
    )
    component_d, component_c, component_r, component_q, score, count = (
        sfx.SCORE_CATEGORY_EXPECTED
    )
    assert result.component_d == pytest.approx(component_d, abs=1e-9)
    assert result.component_c == pytest.approx(component_c, abs=1e-9)
    assert result.component_r == pytest.approx(component_r, abs=1e-9)
    assert result.component_q == pytest.approx(component_q, abs=1e-9)
    assert result.market_opportunity_score == pytest.approx(score, abs=1e-9)
    assert result.score_state is ScoreState.AVAILABLE
    assert result.available_component_count == count
    assert result.rankability_status is RankabilityStatus.NOT_RANKABLE
    assert result.evidence_grade is EvidenceGrade.INSUFFICIENT

    contradicted = scoring.score_category(
        target,
        sfx.SCORE_CATEGORY_RUN,
        page_view_semantics_status=PageViewSemanticsStatus.CONTRADICTED,
    )
    assert contradicted.component_d is None
    assert contradicted.component_q is None
    assert contradicted.component_c == pytest.approx(1.0, abs=1e-9)
    assert contradicted.component_r == pytest.approx(0.0, abs=1e-9)
    assert contradicted.available_component_count == 2
    assert contradicted.score_state is ScoreState.PARTIAL
    assert contradicted.market_opportunity_score == pytest.approx(0.55, abs=1e-9)


@pytest.mark.lreq("LREQ-SCR-060")
def test_score_state_field_is_distinct_from_rankability_status() -> None:
    """``score_state`` and ``rankability_status`` are distinct fields (plan §10).

    ``ScoreState`` is ``available`` / ``partial`` / ``unavailable``;
    ``RankabilityStatus`` is ``not_rankable`` / ``provisional`` / ``rankable``.
    They share no value; ``score_category`` reports the former and leaves the
    latter at its default, so a scored category is not thereby rankable
    (rankability is Chunk 9A's).
    """
    available = scoring.score_category(
        sfx.SCORE_CATEGORY_RUN[1],
        sfx.SCORE_CATEGORY_RUN,
        page_view_semantics_status=PageViewSemanticsStatus.UNVALIDATED,
    )
    assert available.score_state is ScoreState.AVAILABLE
    assert available.rankability_status is RankabilityStatus.NOT_RANKABLE
    score_values = {state.value for state in ScoreState}
    rankability_values = {status.value for status in RankabilityStatus}
    assert score_values == {"available", "partial", "unavailable"}
    assert rankability_values == {"not_rankable", "provisional", "rankable"}
    assert score_values & rankability_values == set()
    assert hasattr(scoring.ScoreResult, "score_state")
    assert hasattr(scoring.ScoreResult, "rankability_status")


# ---------------------------------------------------------------------------
# Public contract: type hints/docstrings, purity, determinism
# ---------------------------------------------------------------------------

SCORING_PATH = (
    Path(__file__).resolve().parents[1] / "src" / "niche_scout" / "scoring.py"
)

PUBLIC_SCORING_FUNCTIONS: tuple[str, ...] = (
    "midrank",
    "leave_one_out_reference",
    "normalize_raw_metrics",
    "demand_component",
    "competition_component",
    "recent_supply_component",
    "quality_component",
    "compute_components",
    "renormalized_composite",
    "balanced_composite",
    "score_category",
)


@pytest.mark.lreq("LREQ-NFR-040")
def test_scoring_public_functions_have_type_hints_and_docstrings() -> None:
    """Every public Chunk 8 function is annotated and documented (SRS §11).

    LREQ-NFR-040: public metric and scoring functions carry type hints plus a
    docstring describing null and edge-case behavior. Each name below is imported
    from ``niche_scout.scoring`` and checked for a docstring, parameter
    annotations, and a return annotation.
    """
    for name in PUBLIC_SCORING_FUNCTIONS:
        function = getattr(scoring, name)
        assert function.__doc__, f"{name} must have a docstring"
        assert function.__annotations__, f"{name} must be annotated"
        assert "return" in function.__annotations__, f"{name} needs a return type"


@pytest.mark.lreq("LREQ-ARCH-010")
@pytest.mark.lreq("LREQ-ARCH-020")
def test_scoring_module_is_import_pure_and_clock_free() -> None:
    """``scoring.py`` stays inside the SRS §3.3 purity/clock boundary.

    LREQ-ARCH-010/-020: no collector, database, report, or CLI import, no
    network or file I/O, and no clock read. The structural checker and a direct
    AST scan both agree, and no randomness module is imported.
    """
    source = SCORING_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(SCORING_PATH))
    assert check_module(SCORING_PATH) == [], (
        "scoring.py must not import an I/O, network, DB, CLI, or clock module "
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
def test_scoring_outputs_are_deterministic() -> None:
    """Identical inputs give equal outputs (SRS §3.3 / LREQ-ARCH-030).

    ``score_category``, ``balanced_composite``, ``renormalized_composite``, and
    ``midrank`` are pure and use a fixed key iteration order with no RNG and no
    clock, so repeated calls return equal values.
    """
    first = scoring.score_category(
        sfx.SCORE_CATEGORY_RUN[1],
        sfx.SCORE_CATEGORY_RUN,
        page_view_semantics_status=PageViewSemanticsStatus.UNVALIDATED,
    )
    second = scoring.score_category(
        sfx.SCORE_CATEGORY_RUN[1],
        sfx.SCORE_CATEGORY_RUN,
        page_view_semantics_status=PageViewSemanticsStatus.UNVALIDATED,
    )
    assert first == second
    components_a = _components(0.8, 0.6, 0.4, 0.2)
    components_b = _components(0.8, 0.6, 0.4, 0.2)
    assert components_a == components_b
    assert scoring.balanced_composite(components_a) == scoring.balanced_composite(
        components_b
    )
    assert scoring.renormalized_composite(
        components_a, sfx.FIXED_PRIMARY_WEIGHTS
    ) == scoring.renormalized_composite(components_b, sfx.FIXED_PRIMARY_WEIGHTS)
    assert scoring.midrank(2.0, (1.0, 2.0, 3.0)) == scoring.midrank(
        2.0, (1.0, 2.0, 3.0)
    )


# ---------------------------------------------------------------------------
# LREQ-SCR-020 / LREQ-MET-070 (Chunk 29) — fallback breadth disables C
# ---------------------------------------------------------------------------


@pytest.mark.lreq("LREQ-SCR-020")
@pytest.mark.lreq("LREQ-MET-070")
def test_incomplete_breadth_fallback_disables_c_and_is_not_rankable() -> None:
    """``incomplete_estimate`` breadth yields no ``C`` and no rankable result.

    SRS §8.2 LREQ-SCR-020 with §7.3 LREQ-MET-070: ``C`` requires
    ``verified_total_count`` breadth with ``complete`` provenance. Golden: with
    ``P_ref(BreadthRaw) = 0.5`` a verified+complete breadth gives
    ``C = clamp(1 - 0.5, 0, 1) = 0.5``, while the fallback triple gives
    ``None``. ``not_rankable_reasons`` then reports
    ``COMPETITION_UNBOUNDED_OR_MATERIAL_FAILURE`` for the fallback score and
    none for the healthy verified score (Chunk 9A reason vocabulary; plan §2
    step 6).
    """
    from fixtures.scoring_evidence_fixtures import (
        make_pre_sensitivity_input,
        make_score_result,
    )
    from niche_scout.models import IdentityPreflightStatus

    fallback_source = BreadthSource.DISTINCT_CANONICAL_DISCOVERED_COUNT
    fallback_status = BreadthCompletenessStatus.INCOMPLETE_ESTIMATE

    fallback_c = scoring.competition_component(
        _normalized(breadth_raw=0.5),
        breadth_source=fallback_source,
        breadth_completeness_status=fallback_status,
    )
    assert fallback_c is None

    fallback_reasons = scoring.not_rankable_reasons(
        make_score_result(component_c=fallback_c),
        make_pre_sensitivity_input(
            "c-0",
            breadth_source=fallback_source,
            breadth_completeness_status=fallback_status,
            discovery_bounded_by_verified_total=False,
        ),
        identity_preflight_status=IdentityPreflightStatus.PASSED,
    )
    assert (
        scoring.NotRankableReason.COMPETITION_UNBOUNDED_OR_MATERIAL_FAILURE
        in fallback_reasons
    )

    healthy_c = scoring.competition_component(
        _normalized(breadth_raw=0.5),
        breadth_source=COMPETITION_VERIFIED,
        breadth_completeness_status=COMPETITION_COMPLETE,
    )
    assert healthy_c == pytest.approx(0.5, abs=1e-9)
    healthy_reasons = scoring.not_rankable_reasons(
        make_score_result(component_c=healthy_c),
        make_pre_sensitivity_input("c-0"),
        identity_preflight_status=IdentityPreflightStatus.PASSED,
    )
    assert (
        scoring.NotRankableReason.COMPETITION_UNBOUNDED_OR_MATERIAL_FAILURE
        not in healthy_reasons
    )
