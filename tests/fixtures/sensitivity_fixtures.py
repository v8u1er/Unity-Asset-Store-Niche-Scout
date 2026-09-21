"""Golden vectors and builders for Chunk 9B sensitivity and final evidence.

Data only: explicit constants, inert golden-vector tables, and small
keyword-argument builders. There are no assertions here; the expectations live in
``tests/test_scoring_sensitivity.py``.

Every expected value below is hand-derived from ``SRS-lean.md`` §9.1–§9.3 and the
frozen Chunk 9B plan §9
(``Documents/plans/chunk-9B-sensitivity-final-evidence-and-final-rankability.md``),
never copied from the implementation:

* The three sensitivity policies and their fixed weights are the SRS §9.3
  LREQ-SEN-010 block (lines 1060-1066): ``balanced`` D=0.35 C=0.30 R=0.20 Q=0.15,
  ``demand_heavy`` D=0.50 C=0.25 R=0.15 Q=0.10, ``competition_heavy`` D=0.30
  C=0.45 R=0.15 Q=0.10.
* With all four components available the composite is the weighted sum
  ``sum(w_x * x)`` clamped to ``[0, 1]`` (SRS §8.3); the balanced policy equals the
  fixed primary weights, so a base candidate's balanced score is the same number as
  its ``ScoreResult.market_opportunity_score``.
* ``top_k_stability`` is the intersection size of the three policy top-k sets
  divided by ``k``, for k = 3 and k = 5; it is ``None`` when fewer than k rankable
  categories exist (SRS §9.3 LREQ-SEN-020, lines 1082-1087). Ranks are
  descending-score order with ties broken by ascending lexical category path
  (line 1074).
* The warning fires iff ``top_3_stability < 2/3`` (strict) or a category's rank
  displacement exceeds ``max(3, 0.25 * reference_set_size)`` (strict), and is
  ``None`` only for zero base candidates (SRS §9.3 LREQ-SEN-030, lines 1093-1096;
  plan §5.3 and rulings R2/R4).
* Evidence grades follow the SRS §9.2 table (lines 1047-1052) with the plan §5.4
  precedence: ``insufficient`` when ``not_rankable_reasons`` is non-empty; else
  ``strong`` needs ``minimum_component_sample_count >= 80`` or a census of at least
  50, all three coverages at least ``STRONG_COMPONENT_COVERAGE`` (0.80), verified
  discovery, no identity conflict, at least ``STRONG_REFERENCE_CATEGORY_COUNT`` (21)
  categories, no contradicted page views, and ``sensitivity_warning is False`` (a
  ``None`` warning is not acceptable; R6); else ``moderate`` needs ``>= 40`` or a
  census of at least 20, coverages at least ``MIN_REQUIRED_COMPONENT_COVERAGE``
  (0.50), at least ``MIN_CATEGORIES_PER_RUN`` (8) categories, and no critical
  identity failure; else ``weak``.
* Final rankability maps the pre-sensitivity state and lets sensitivity demote only
  to ``provisional`` (SRS §9.1 LREQ-EVD-040, lines 1003-1010; plan §5.5 and R7).

Design notes:

* This module imports before the Chunk 9B implementation lands: every
  ``niche_scout.scoring`` name is imported lazily inside a builder function, so
  importing this module never touches the module under test. The module-level
  tables hold only plain literals, ``models`` enums, and Chunk 7B metric
  structures.
* Enum-typed decision facts in the final-evidence and final-rankability tables are
  stored as their frozen string values (for example ``"rankable"``). The test
  constructs the ``StrEnum`` members from those strings before passing them to the
  implementation, because the implementation distinguishes states by identity; a
  bare string is not the member.
* ``field_usable_counts`` is stored as a six-key mapping of explicit counts; the
  test constructs the Chunk 9A ``FieldUsableCounts`` from it.

No network, no credentials, no clock reads, no randomness: every value below is an
explicit literal and every builder is total over its arguments.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from niche_scout.metrics import CategoryRawMetrics, RawMetricBundle
from niche_scout.models import (
    MIN_CATEGORIES_PER_RUN,
    MIN_REQUIRED_COMPONENT_COVERAGE,
    STRONG_COMPONENT_COVERAGE,
    STRONG_REFERENCE_CATEGORY_COUNT,
    BreadthCompletenessStatus,
    BreadthSource,
    DiscoveryStatus,
    PageViewSemanticsStatus,
    ScoreState,
)

__all__ = [
    "BALANCED_POLICY_WEIGHTS",
    "COMPETITION_HEAVY_POLICY_WEIGHTS",
    "DEMAND_HEAVY_POLICY_WEIGHTS",
    "FINAL_EVIDENCE_BASE_DECISION_KWARGS",
    "FINAL_EVIDENCE_BASE_EVIDENCE_KWARGS",
    "FINAL_EVIDENCE_BASE_SAMPLE_KWARGS",
    "FINAL_EVIDENCE_GRADE_VECTORS",
    "FINAL_RANKABILITY_VECTORS",
    "SENSITIVITY_DISPLACEMENT_VECTOR",
    "SENSITIVITY_ONE_CANDIDATE_VECTOR",
    "SENSITIVITY_POLICY_ORDER_EXPECTED",
    "SENSITIVITY_POLICY_WEIGHTS",
    "SENSITIVITY_STABLE_VECTOR",
    "SENSITIVITY_TOP_K_EXPECTED",
    "SENSITIVITY_TOP_THREE_VECTOR",
    "SENSITIVITY_TWO_CANDIDATE_VECTOR",
    "SENSITIVITY_VECTORS",
    "SENSITIVITY_ZERO_CANDIDATE_VECTOR",
    "make_candidate_set",
    "make_metrics_and_scores",
    "make_score_result",
]

# ---------------------------------------------------------------------------
# Fixed sensitivity policies (SRS-lean.md §9.3 LREQ-SEN-010, lines 1060-1066)
# ---------------------------------------------------------------------------
#
# The keys are the frozen ``models.SENSITIVITY_POLICIES`` key spelling; the
# weights are the SRS literals. The repository policy dict is compared against
# ``SENSITIVITY_POLICY_WEIGHTS`` by the vocabulary test, never re-derived.

BALANCED_POLICY_WEIGHTS: dict[str, float] = {
    "D": 0.35,
    "C": 0.30,
    "R": 0.20,
    "Q": 0.15,
}

DEMAND_HEAVY_POLICY_WEIGHTS: dict[str, float] = {
    "D": 0.50,
    "C": 0.25,
    "R": 0.15,
    "Q": 0.10,
}

COMPETITION_HEAVY_POLICY_WEIGHTS: dict[str, float] = {
    "D": 0.30,
    "C": 0.45,
    "R": 0.15,
    "Q": 0.10,
}

SENSITIVITY_POLICY_WEIGHTS: dict[str, dict[str, float]] = {
    "balanced": BALANCED_POLICY_WEIGHTS,
    "demand_heavy": DEMAND_HEAVY_POLICY_WEIGHTS,
    "competition_heavy": COMPETITION_HEAVY_POLICY_WEIGHTS,
}

#: The plan §5 fixed policy evaluation order (SRS §9.3; LREQ-ARCH-030).
SENSITIVITY_POLICY_ORDER_EXPECTED: tuple[str, ...] = (
    "balanced",
    "demand_heavy",
    "competition_heavy",
)

#: The plan §5 fixed top-k order (SRS §9.3 lines 1086-1087).
SENSITIVITY_TOP_K_EXPECTED: tuple[int, ...] = (3, 5)

# ---------------------------------------------------------------------------
# Builders (plain typed facts; ``niche_scout.scoring`` names imported lazily)
# ---------------------------------------------------------------------------


def _balanced_score(d: float, c: float, r: float, q: float) -> float:
    """The balanced composite for four available components.

    With all four components available ``W_A = 1.0`` and
    ``score = clamp(0.5 + W_A * (S_available - 0.5), 0, 1) = sum(w_x * x)``;
    every component is in ``[0, 1]``, so the clamp is inert (SRS §8.3, §9.3).
    """
    return (
        BALANCED_POLICY_WEIGHTS["D"] * d
        + BALANCED_POLICY_WEIGHTS["C"] * c
        + BALANCED_POLICY_WEIGHTS["R"] * r
        + BALANCED_POLICY_WEIGHTS["Q"] * q
    )


def _metric(category: str) -> CategoryRawMetrics:
    """One inert ``CategoryRawMetrics`` used only as ordering authority.

    Sensitivity reads ``all_metrics`` for its category sequence and alignment,
    never for the raw values; the values here are explicit placeholders and the
    usable counts are the explicit ``0`` of an unread field, not "missing".
    """
    return CategoryRawMetrics(
        category=category,
        raw=RawMetricBundle(
            demand_per_asset_raw=1.0,
            demand_median_raw=1.0,
            breadth_raw=1.0,
            recent_share_raw=1.0,
            median_age_raw=1.0,
            quality_raw=1.0,
        ),
        demand_stratum_eligibility_coverage=1.0,
        recent_supply_stratum_eligibility_coverage=1.0,
        quality_stratum_eligibility_coverage=1.0,
        usable_demand_sample_count=0,
        usable_recent_supply_sample_count=0,
        usable_quality_sample_count=0,
        breadth_source=BreadthSource.VERIFIED_TOTAL_COUNT,
        breadth_completeness_status=BreadthCompletenessStatus.COMPLETE,
    )


def make_score_result(
    score: float | None = None,
    state: ScoreState = ScoreState.AVAILABLE,
    d: float | None = None,
    c: float | None = None,
    r: float | None = None,
    q: float | None = None,
) -> object:
    """Build one ``ScoreResult`` with ``available_component_count`` derived.

    ``score`` is the balanced primary ``market_opportunity_score``; for a base
    candidate it equals ``_balanced_score(d, c, r, q)`` (plan §5.2 step 2). A
    ``None`` component is unavailable and is never counted as available or
    converted to ``0.0`` (SRS §1.2); with all four components present the count is
    the explicit ``4``. ``ScoreResult`` is imported locally so this module imports
    before the Chunk 9B implementation lands.
    """
    from niche_scout.scoring import ScoreResult

    available_component_count = sum(component is not None for component in (d, c, r, q))
    return ScoreResult(
        market_opportunity_score=score,
        score_state=state,
        component_d=d,
        component_c=c,
        component_r=r,
        component_q=q,
        available_component_count=available_component_count,
    )


def make_candidate_set(categories: Sequence[str], run_category_count: int) -> object:
    """Build a ``BaseCandidateSet`` whose decisions are all base-rankable.

    Every supplied category is a frozen base candidate: ``base_rankable=True``, a
    ``rankable`` pre-sensitivity state, ``sufficient`` evidence, and empty reason
    tuples (the Chunk 9A base rule; interfaces/chunk-9A.md §4.6).
    ``base_rankable_candidates`` and ``decisions`` keep the caller's order, and
    ``run_category_count`` is the explicit run size (an empty ``categories`` tuple
    plus ``run_category_count`` in 8–20 is the provisional empty-candidate run).
    ``BaseCandidateSet`` is imported locally so this module imports before the
    Chunk 9B implementation lands.
    """
    from niche_scout.scoring import (
        BaseCandidateSet,
        PreSensitivityDecision,
        PreSensitivityEvidenceState,
        PreSensitivityRankabilityState,
    )

    decisions = tuple(
        PreSensitivityDecision(
            category=category,
            evidence_state=PreSensitivityEvidenceState.SUFFICIENT,
            rankability_state=PreSensitivityRankabilityState.RANKABLE,
            not_rankable_reasons=(),
            provisional_reasons=(),
            base_rankable=True,
        )
        for category in categories
    )
    return BaseCandidateSet(
        base_rankable_candidates=tuple(categories),
        decisions=decisions,
        run_category_count=run_category_count,
    )


def make_metrics_and_scores(
    components_by_category: Mapping[str, tuple[float, float, float, float]],
) -> tuple[tuple[CategoryRawMetrics, ...], tuple[object, ...]]:
    """Build aligned ``(all_metrics, scores)`` in mapping insertion order.

    Each component tuple is ``(D, C, R, Q)`` and all four components are
    available (the Chunk 9A base rule), so every ``ScoreResult`` is ``available``
    with ``available_component_count == 4`` and its ``market_opportunity_score``
    equal to the balanced composite (SRS §8.3, §9.3). The mapping's insertion
    order is the canonical category order; ``all_metrics`` is 1:1 aligned with
    ``scores`` and every base candidate appears in both. ``ScoreResult`` is
    imported locally so this module imports before the Chunk 9B implementation
    lands.
    """
    from niche_scout.scoring import ScoreResult

    metrics: list[CategoryRawMetrics] = []
    scores: list[object] = []
    for category, (d, c, r, q) in components_by_category.items():
        metrics.append(_metric(category))
        scores.append(
            ScoreResult(
                market_opportunity_score=_balanced_score(d, c, r, q),
                score_state=ScoreState.AVAILABLE,
                component_d=d,
                component_c=c,
                component_r=r,
                component_q=q,
                available_component_count=4,
            )
        )
    return tuple(metrics), tuple(scores)


# ---------------------------------------------------------------------------
# Sensitivity vector schema (SRS-lean.md §9.3; plan §9)
# ---------------------------------------------------------------------------
#
# Every sensitivity vector is a dict with exactly these keys:
#
#   "components": dict[str, tuple[float, float, float, float]]
#       ``(D, C, R, Q)`` per base candidate, in canonical order.
#   "run_category_count": int          explicit run size (R3).
#   "reference_set_size": int          explicit leave-one-out peer count (R3).
#   "displacement_threshold": float    max(3, 0.25 * reference_set_size).
#   "expected_scores_by_policy": dict[str, dict[str, float]]
#   "expected_ranks_by_policy": dict[str, dict[str, int]]
#       1-based ranks over the candidate set (SRS §9.3 line 1074).
#   "expected_max_score_delta": dict[str, float]
#   "expected_max_rank_displacement": dict[str, int]
#   "expected_warning": dict[str, bool | None]
#   "expected_top_3_stability": float | None
#   "expected_top_5_stability": float | None
#   "expected_maximum_score_delta": float | None
#   "expected_maximum_rank_displacement": int | None
#   "expected_run_warning": bool | None
#
# ``SENSITIVITY_VECTORS`` pairs each label with its vector for parametrized
# iteration; the individually named constants below are for direct use.

# Derivation of every expected value in the stable vector (SRS §9.3 lines
# 1060-1096; plan §9 stable vector). Policy formulas:
#   B  = 0.35D + 0.30C + 0.20R + 0.15Q
#   DH = 0.50D + 0.25C + 0.15R + 0.10Q
#   CH = 0.30D + 0.45C + 0.15R + 0.10Q
# A (0.9, 0.1, 0.5, 0.5): B  = 0.315 + 0.03 + 0.10 + 0.075 = 0.52
#                          DH = 0.45 + 0.025 + 0.075 + 0.05 = 0.60
#                          CH = 0.27 + 0.045 + 0.075 + 0.05 = 0.44
# B (0.1, 0.9, 0.5, 0.5): B  = 0.035 + 0.27 + 0.10 + 0.075 = 0.48
#                          DH = 0.05 + 0.225 + 0.075 + 0.05 = 0.40
#                          CH = 0.03 + 0.405 + 0.075 + 0.05 = 0.56
# C (0.5, 0.5, 0.9, 0.9): B  = 0.175 + 0.15 + 0.18 + 0.135 = 0.64
#                          DH = 0.25 + 0.125 + 0.135 + 0.09 = 0.60
#                          CH = 0.15 + 0.225 + 0.135 + 0.09 = 0.60
# D (0.5, 0.5, 0.5, 0.5): B = DH = CH = 0.175 + 0.15 + 0.10 + 0.075 = 0.50
# E (0.2, 0.2, 0.2, 0.2): B = DH = CH = 0.07 + 0.06 + 0.04 + 0.03 = 0.20
# Ranks: balanced C 0.64, A 0.52, D 0.50, B 0.48, E 0.20 -> C, A, D, B, E.
#   Demand ties A 0.60 with C 0.60; ascending lexical path breaks it A then C,
#   then D 0.50, B 0.40, E 0.20.
#   Competition C 0.60, B 0.56, D 0.50, A 0.44, E 0.20 -> C, B, D, A, E.
# T3: balanced {C, A, D}, demand {A, C, D}, competition {C, B, D}; intersection
#   {C, D} -> top_3_stability = 2/3 exactly (strict "<" boundary: no warning).
# T5: all five sets contain every candidate -> 5/5 = 1.0.
# Displacements (max rank - min rank): A ranks 2/1/4 -> 3; B 4/4/2 -> 2;
#   C 1/2/1 -> 1; D 3/3/3 -> 0; E 5/5/5 -> 0; run max = 3.
# Score deltas (max |alternate - balanced|): A max(|0.60-0.52|, |0.44-0.52|)
#   = 0.08; B max(0.08, 0.08) = 0.08; C max(0.04, 0.04) = 0.04; D 0.0; E 0.0;
#   run max = 0.08.
# Run 21 categories -> reference_set_size = 20 (R3); threshold
#   max(3, 0.25 * 20) = 5.0. 3 <= 5.0 and 2/3 is not < 2/3 -> every category
#   warning False and the run-level warning False.
SENSITIVITY_STABLE_VECTOR: dict[str, object] = {
    "components": {
        "A": (0.9, 0.1, 0.5, 0.5),
        "B": (0.1, 0.9, 0.5, 0.5),
        "C": (0.5, 0.5, 0.9, 0.9),
        "D": (0.5, 0.5, 0.5, 0.5),
        "E": (0.2, 0.2, 0.2, 0.2),
    },
    "run_category_count": STRONG_REFERENCE_CATEGORY_COUNT,
    "reference_set_size": STRONG_REFERENCE_CATEGORY_COUNT - 1,
    "displacement_threshold": 5.0,
    "expected_scores_by_policy": {
        "balanced": {"A": 0.52, "B": 0.48, "C": 0.64, "D": 0.50, "E": 0.20},
        "demand_heavy": {"A": 0.60, "B": 0.40, "C": 0.60, "D": 0.50, "E": 0.20},
        "competition_heavy": {
            "A": 0.44,
            "B": 0.56,
            "C": 0.60,
            "D": 0.50,
            "E": 0.20,
        },
    },
    "expected_ranks_by_policy": {
        "balanced": {"A": 2, "B": 4, "C": 1, "D": 3, "E": 5},
        "demand_heavy": {"A": 1, "B": 4, "C": 2, "D": 3, "E": 5},
        "competition_heavy": {"A": 4, "B": 2, "C": 1, "D": 3, "E": 5},
    },
    "expected_max_score_delta": {
        "A": 0.08,
        "B": 0.08,
        "C": 0.04,
        "D": 0.0,
        "E": 0.0,
    },
    "expected_max_rank_displacement": {"A": 3, "B": 2, "C": 1, "D": 0, "E": 0},
    "expected_warning": {
        "A": False,
        "B": False,
        "C": False,
        "D": False,
        "E": False,
    },
    "expected_top_3_stability": 2.0 / 3.0,
    "expected_top_5_stability": 1.0,
    "expected_maximum_score_delta": 0.08,
    "expected_maximum_rank_displacement": 3,
    "expected_run_warning": False,
}

# Derivation of every expected value in the top-3 vector (SRS §9.3; plan §9
# top-3-only vector). R = Q = 0.5 for all, so:
#   B  = 0.35D + 0.30C + 0.175
#   DH = 0.50D + 0.25C + 0.125
#   CH = 0.30D + 0.45C + 0.125
# c1 (1.0, 0.0, 0.5, 0.5): B  = 0.35 + 0.175 = 0.525
#                          DH = 0.50 + 0.125 = 0.625
#                          CH = 0.30 + 0.125 = 0.425
# c2 (0.8, 0.2, 0.5, 0.5): B  = 0.28 + 0.06 + 0.175 = 0.515
#                          DH = 0.40 + 0.05 + 0.125 = 0.575
#                          CH = 0.24 + 0.09 + 0.125 = 0.455
# c3 (0.6, 0.4, 0.5, 0.5): B  = 0.21 + 0.12 + 0.175 = 0.505
#                          DH = 0.30 + 0.10 + 0.125 = 0.525
#                          CH = 0.18 + 0.18 + 0.125 = 0.485
# c4 (0.4, 0.6, 0.5, 0.5): B  = 0.14 + 0.18 + 0.175 = 0.495
#                          DH = 0.20 + 0.15 + 0.125 = 0.475
#                          CH = 0.12 + 0.27 + 0.125 = 0.515
# c5 (0.2, 0.8, 0.5, 0.5): B  = 0.07 + 0.24 + 0.175 = 0.485
#                          DH = 0.10 + 0.20 + 0.125 = 0.425
#                          CH = 0.06 + 0.36 + 0.125 = 0.545
# Ranks: balanced and demand keep c1, c2, c3, c4, c5 (strictly descending);
#   competition reverses to c5, c4, c3, c2, c1.
# T3: balanced {c1, c2, c3}, demand {c1, c2, c3}, competition {c5, c4, c3};
#   intersection {c3} -> top_3_stability = 1/3 < 2/3, so the top-3 clause fires
#   for every base-candidate row (R4). T5: all five in every set -> 1.0.
# Displacements: c1 1/1/5 -> 4; c2 2/2/4 -> 2; c3 3/3/3 -> 0; c4 4/4/2 -> 2;
#   c5 5/5/1 -> 4; run max = 4.
# Score deltas: c1 max(0.100, 0.100) = 0.100; c2 max(0.060, 0.060) = 0.060;
#   c3 0.020; c4 0.020; c5 0.060; run max = 0.100.
# reference_set_size = 20 -> threshold 5.0; the displacement clause does not
#   fire (4 <= 5.0), so every True comes from the top-3 clause. (The plan §9
#   parenthetical claiming all five also breach displacement cannot hold with
#   displacement 0 for c3 and threshold 5.0; the numeric table governs.)
SENSITIVITY_TOP_THREE_VECTOR: dict[str, object] = {
    "components": {
        "c1": (1.0, 0.0, 0.5, 0.5),
        "c2": (0.8, 0.2, 0.5, 0.5),
        "c3": (0.6, 0.4, 0.5, 0.5),
        "c4": (0.4, 0.6, 0.5, 0.5),
        "c5": (0.2, 0.8, 0.5, 0.5),
    },
    "run_category_count": STRONG_REFERENCE_CATEGORY_COUNT,
    "reference_set_size": STRONG_REFERENCE_CATEGORY_COUNT - 1,
    "displacement_threshold": 5.0,
    "expected_scores_by_policy": {
        "balanced": {
            "c1": 0.525,
            "c2": 0.515,
            "c3": 0.505,
            "c4": 0.495,
            "c5": 0.485,
        },
        "demand_heavy": {
            "c1": 0.625,
            "c2": 0.575,
            "c3": 0.525,
            "c4": 0.475,
            "c5": 0.425,
        },
        "competition_heavy": {
            "c1": 0.425,
            "c2": 0.455,
            "c3": 0.485,
            "c4": 0.515,
            "c5": 0.545,
        },
    },
    "expected_ranks_by_policy": {
        "balanced": {"c1": 1, "c2": 2, "c3": 3, "c4": 4, "c5": 5},
        "demand_heavy": {"c1": 1, "c2": 2, "c3": 3, "c4": 4, "c5": 5},
        "competition_heavy": {"c1": 5, "c2": 4, "c3": 3, "c4": 2, "c5": 1},
    },
    "expected_max_score_delta": {
        "c1": 0.100,
        "c2": 0.060,
        "c3": 0.020,
        "c4": 0.020,
        "c5": 0.060,
    },
    "expected_max_rank_displacement": {"c1": 4, "c2": 2, "c3": 0, "c4": 2, "c5": 4},
    "expected_warning": {
        "c1": True,
        "c2": True,
        "c3": True,
        "c4": True,
        "c5": True,
    },
    "expected_top_3_stability": 1.0 / 3.0,
    "expected_top_5_stability": 1.0,
    "expected_maximum_score_delta": 0.100,
    "expected_maximum_rank_displacement": 4,
    "expected_run_warning": True,
}

# Derivation of every expected value in the isolated displacement vector
# (SRS §9.3; plan §9 displacement-only vector). The components are hand-chosen
# so {T3,balanced} = {T3,demand_heavy} = {T3,competition_heavy} (stability
# exactly 2/3, so the top-3 clause never fires) while c-8 climbs from rank 7
# balanced to rank 1 competition-heavy: displacement 6 > 5.0.
# c-1 (1.0, 0.2, 1.0, 1.0): B  = 0.35 + 0.06 + 0.20 + 0.15 = 0.76
#                          DH = 0.50 + 0.05 + 0.15 + 0.10 = 0.80
#                          CH = 0.30 + 0.09 + 0.15 + 0.10 = 0.64
# c-2 (0.9, 0.2, 0.9, 0.9): B  = 0.315 + 0.06 + 0.18 + 0.135 = 0.69
#                          DH = 0.45 + 0.05 + 0.135 + 0.09 = 0.725
#                          CH = 0.27 + 0.09 + 0.135 + 0.09 = 0.585
# c-3 (0.8, 0.2, 0.8, 0.8): B  = 0.28 + 0.06 + 0.16 + 0.12 = 0.62
#                          DH = 0.40 + 0.05 + 0.12 + 0.08 = 0.65
#                          CH = 0.24 + 0.09 + 0.12 + 0.08 = 0.53
# c-4 (0.72, 0.2, 0.8, 0.8): B  = 0.252 + 0.06 + 0.16 + 0.12 = 0.592
#                           DH = 0.36 + 0.05 + 0.12 + 0.08 = 0.61
#                           CH = 0.216 + 0.09 + 0.12 + 0.08 = 0.506
# c-5 (0.75, 0.1, 0.75, 0.75): B  = 0.2625 + 0.03 + 0.15 + 0.1125 = 0.555
#                             DH = 0.375 + 0.025 + 0.1125 + 0.075 = 0.5875
#                             CH = 0.225 + 0.045 + 0.1125 + 0.075 = 0.4575
# c-6 (0.78, 0.15, 0.7, 0.7): B  = 0.273 + 0.045 + 0.14 + 0.105 = 0.563
#                            DH = 0.39 + 0.0375 + 0.105 + 0.07 = 0.6025
#                            CH = 0.234 + 0.0675 + 0.105 + 0.07 = 0.4765
# c-7 (0.7, 0.1, 0.7, 0.7): B  = 0.245 + 0.03 + 0.14 + 0.105 = 0.52
#                          DH = 0.35 + 0.025 + 0.105 + 0.07 = 0.55
#                          CH = 0.21 + 0.045 + 0.105 + 0.07 = 0.43
# c-8 (0.7, 1.0, 0.0, 0.0): B  = 0.245 + 0.30 = 0.545
#                          DH = 0.35 + 0.25 = 0.60
#                          CH = 0.21 + 0.45 = 0.66
# Balanced ranks: c-1 0.76, c-2 0.69, c-3 0.62, c-4 0.592, c-6 0.563,
#   c-5 0.555, c-8 0.545, c-7 0.52 -> c-5 and c-6 swap, c-8 is 7, c-7 is 8.
# Demand ranks: c-1 0.80, c-2 0.725, c-3 0.65, c-4 0.61, c-6 0.6025,
#   c-8 0.60, c-5 0.5875, c-7 0.55 -> c-6 5, c-8 6, c-5 7, c-7 8.
# Competition ranks: c-8 0.66, c-1 0.64, c-2 0.585, c-3 0.53, c-4 0.506,
#   c-6 0.4765, c-5 0.4575, c-7 0.43.
# T3: balanced {c-1, c-2, c-3}, demand {c-1, c-2, c-3}, competition
#   {c-8, c-1, c-2}; intersection {c-1, c-2} -> 2/3 exactly (no top-3 warning).
# T5: balanced/demand {c-1, c-2, c-3, c-4, c-6}, competition
#   {c-8, c-1, c-2, c-3, c-4}; intersection {c-1, c-2, c-3, c-4} -> 4/5 = 0.8.
# Displacements: c-1..c-4 -> 1; c-5 ranks 6/7/7 -> 1; c-6 5/5/6 -> 1;
#   c-7 8/8/8 -> 0; c-8 max(|7-6|, |7-1|, |6-1|) = 6 -> run max 6 > 5.0, so
#   only c-8 warns and the run-level warning is True.
# Score deltas: c-1 max(0.04, 0.12) = 0.12; c-2 max(0.035, 0.105) = 0.105;
#   c-3 max(0.03, 0.09) = 0.09; c-4 max(0.018, 0.086) = 0.086;
#   c-5 max(0.0325, 0.0975) = 0.0975; c-6 max(0.0395, 0.0865) = 0.0865;
#   c-7 max(0.03, 0.09) = 0.09; c-8 max(0.055, 0.115) = 0.115; run max = 0.12.
# Run 21 categories -> reference_set_size 20 -> threshold max(3, 5.0) = 5.0.
SENSITIVITY_DISPLACEMENT_VECTOR: dict[str, object] = {
    "components": {
        "c-1": (1.0, 0.2, 1.0, 1.0),
        "c-2": (0.9, 0.2, 0.9, 0.9),
        "c-3": (0.8, 0.2, 0.8, 0.8),
        "c-4": (0.72, 0.2, 0.8, 0.8),
        "c-5": (0.75, 0.1, 0.75, 0.75),
        "c-6": (0.78, 0.15, 0.7, 0.7),
        "c-7": (0.7, 0.1, 0.7, 0.7),
        "c-8": (0.7, 1.0, 0.0, 0.0),
    },
    "run_category_count": STRONG_REFERENCE_CATEGORY_COUNT,
    "reference_set_size": STRONG_REFERENCE_CATEGORY_COUNT - 1,
    "displacement_threshold": 5.0,
    "expected_scores_by_policy": {
        "balanced": {
            "c-1": 0.76,
            "c-2": 0.69,
            "c-3": 0.62,
            "c-4": 0.592,
            "c-5": 0.555,
            "c-6": 0.563,
            "c-7": 0.52,
            "c-8": 0.545,
        },
        "demand_heavy": {
            "c-1": 0.80,
            "c-2": 0.725,
            "c-3": 0.65,
            "c-4": 0.61,
            "c-5": 0.5875,
            "c-6": 0.6025,
            "c-7": 0.55,
            "c-8": 0.60,
        },
        "competition_heavy": {
            "c-1": 0.64,
            "c-2": 0.585,
            "c-3": 0.53,
            "c-4": 0.506,
            "c-5": 0.4575,
            "c-6": 0.4765,
            "c-7": 0.43,
            "c-8": 0.66,
        },
    },
    "expected_ranks_by_policy": {
        "balanced": {
            "c-1": 1,
            "c-2": 2,
            "c-3": 3,
            "c-4": 4,
            "c-5": 6,
            "c-6": 5,
            "c-7": 8,
            "c-8": 7,
        },
        "demand_heavy": {
            "c-1": 1,
            "c-2": 2,
            "c-3": 3,
            "c-4": 4,
            "c-5": 7,
            "c-6": 5,
            "c-7": 8,
            "c-8": 6,
        },
        "competition_heavy": {
            "c-1": 2,
            "c-2": 3,
            "c-3": 4,
            "c-4": 5,
            "c-5": 7,
            "c-6": 6,
            "c-7": 8,
            "c-8": 1,
        },
    },
    "expected_max_score_delta": {
        "c-1": 0.12,
        "c-2": 0.105,
        "c-3": 0.09,
        "c-4": 0.086,
        "c-5": 0.0975,
        "c-6": 0.0865,
        "c-7": 0.09,
        "c-8": 0.115,
    },
    "expected_max_rank_displacement": {
        "c-1": 1,
        "c-2": 1,
        "c-3": 1,
        "c-4": 1,
        "c-5": 1,
        "c-6": 1,
        "c-7": 0,
        "c-8": 6,
    },
    "expected_warning": {
        "c-1": False,
        "c-2": False,
        "c-3": False,
        "c-4": False,
        "c-5": False,
        "c-6": False,
        "c-7": False,
        "c-8": True,
    },
    "expected_top_3_stability": 2.0 / 3.0,
    "expected_top_5_stability": 0.8,
    "expected_maximum_score_delta": 0.12,
    "expected_maximum_rank_displacement": 6,
    "expected_run_warning": True,
}

# Derivation of the top-3-inapplicable vector (SRS §9.3; plan §9 two-candidate
# vector). c-1 leads c-2 under all three policies, so the pair is rank-stable:
# c-1 (0.9, 0.1, 0.9, 0.9): B  = 0.315 + 0.03 + 0.18 + 0.135 = 0.66
#                          DH = 0.45 + 0.025 + 0.135 + 0.09 = 0.70
#                          CH = 0.27 + 0.045 + 0.135 + 0.09 = 0.54
# c-2 (0.1, 0.9, 0.1, 0.1): B  = 0.035 + 0.27 + 0.02 + 0.015 = 0.34
#                          DH = 0.05 + 0.225 + 0.015 + 0.01 = 0.30
#                          CH = 0.03 + 0.405 + 0.015 + 0.01 = 0.46
# Fewer than 3 candidates -> top_3_stability = top_5_stability = None; the
# top-3 clause is inapplicable (not False); displacement is 0 for both, so the
# displacement clause does not fire (0 <= 5.0) -> every warning False (R2).
# Score deltas: c-1 max(0.04, 0.12) = 0.12; c-2 max(0.04, 0.12) = 0.12.
SENSITIVITY_TWO_CANDIDATE_VECTOR: dict[str, object] = {
    "components": {
        "c-1": (0.9, 0.1, 0.9, 0.9),
        "c-2": (0.1, 0.9, 0.1, 0.1),
    },
    "run_category_count": STRONG_REFERENCE_CATEGORY_COUNT,
    "reference_set_size": STRONG_REFERENCE_CATEGORY_COUNT - 1,
    "displacement_threshold": 5.0,
    "expected_scores_by_policy": {
        "balanced": {"c-1": 0.66, "c-2": 0.34},
        "demand_heavy": {"c-1": 0.70, "c-2": 0.30},
        "competition_heavy": {"c-1": 0.54, "c-2": 0.46},
    },
    "expected_ranks_by_policy": {
        "balanced": {"c-1": 1, "c-2": 2},
        "demand_heavy": {"c-1": 1, "c-2": 2},
        "competition_heavy": {"c-1": 1, "c-2": 2},
    },
    "expected_max_score_delta": {"c-1": 0.12, "c-2": 0.12},
    "expected_max_rank_displacement": {"c-1": 0, "c-2": 0},
    "expected_warning": {"c-1": False, "c-2": False},
    "expected_top_3_stability": None,
    "expected_top_5_stability": None,
    "expected_maximum_score_delta": 0.12,
    "expected_maximum_rank_displacement": 0,
    "expected_run_warning": False,
}

# Derivation of the minimum-boundary vector (SRS §9.3; plan §9 one-candidate
# vector). c-1 = (0.5, 0.5, 0.5, 0.5): B = DH = CH =
# 0.175 + 0.15 + 0.10 + 0.075 = 0.50. Rank 1 under every policy, displacement 0,
# score delta 0.0; fewer than 3 candidates -> both stability values None;
# warning False (R2). Run 21 -> threshold 5.0.
SENSITIVITY_ONE_CANDIDATE_VECTOR: dict[str, object] = {
    "components": {"c-1": (0.5, 0.5, 0.5, 0.5)},
    "run_category_count": STRONG_REFERENCE_CATEGORY_COUNT,
    "reference_set_size": STRONG_REFERENCE_CATEGORY_COUNT - 1,
    "displacement_threshold": 5.0,
    "expected_scores_by_policy": {
        "balanced": {"c-1": 0.50},
        "demand_heavy": {"c-1": 0.50},
        "competition_heavy": {"c-1": 0.50},
    },
    "expected_ranks_by_policy": {
        "balanced": {"c-1": 1},
        "demand_heavy": {"c-1": 1},
        "competition_heavy": {"c-1": 1},
    },
    "expected_max_score_delta": {"c-1": 0.0},
    "expected_max_rank_displacement": {"c-1": 0},
    "expected_warning": {"c-1": False},
    "expected_top_3_stability": None,
    "expected_top_5_stability": None,
    "expected_maximum_score_delta": 0.0,
    "expected_maximum_rank_displacement": 0,
    "expected_run_warning": False,
}

# Derivation of the null vector (SRS §9.3; dependency-map §6.2/§6.3; plan §9
# null vector). An 8-category run has an empty candidate set: every
# stability/displacement/warning output is None and ``categories`` is empty,
# while the diagnostics still record reference_set_size = 8 - 1 = 7 and
# displacement_threshold = max(3, 0.25 * 7) = 3.0.
SENSITIVITY_ZERO_CANDIDATE_VECTOR: dict[str, object] = {
    "components": {},
    "run_category_count": MIN_CATEGORIES_PER_RUN,
    "reference_set_size": MIN_CATEGORIES_PER_RUN - 1,
    "displacement_threshold": 3.0,
    "expected_scores_by_policy": {
        "balanced": {},
        "demand_heavy": {},
        "competition_heavy": {},
    },
    "expected_ranks_by_policy": {
        "balanced": {},
        "demand_heavy": {},
        "competition_heavy": {},
    },
    "expected_max_score_delta": {},
    "expected_max_rank_displacement": {},
    "expected_warning": {},
    "expected_top_3_stability": None,
    "expected_top_5_stability": None,
    "expected_maximum_score_delta": None,
    "expected_maximum_rank_displacement": None,
    "expected_run_warning": None,
}

#: ``(label, vector)`` pairs for parametrized iteration (fixed order).
SENSITIVITY_VECTORS: tuple[tuple[str, dict[str, object]], ...] = (
    ("stable", SENSITIVITY_STABLE_VECTOR),
    ("top_three", SENSITIVITY_TOP_THREE_VECTOR),
    ("displacement", SENSITIVITY_DISPLACEMENT_VECTOR),
    ("two_candidate", SENSITIVITY_TWO_CANDIDATE_VECTOR),
    ("one_candidate", SENSITIVITY_ONE_CANDIDATE_VECTOR),
    ("zero_candidate", SENSITIVITY_ZERO_CANDIDATE_VECTOR),
)

# ---------------------------------------------------------------------------
# Final-evidence facts and vectors (SRS-lean.md §9.1-§9.2; plan §9, §5.4)
# ---------------------------------------------------------------------------
#
# Each vector is (label, evidence_overrides, sample_overrides,
# decision_overrides, run_category_count, sensitivity_warning,
# expected_minimum_component_sample_count, expected_grade). Overrides apply
# over the three base kwargs blocks below, so each row states exactly the
# fact(s) it varies. The test builds ``PreSensitivityCategoryInput``,
# ``SampleEvidenceFacts``, and ``PreSensitivityDecision`` from these facts and
# converts the stored state strings to the ``StrEnum`` members.

#: Base evidence facts of a category that can earn ``strong`` (plan §9): discovery
#: ``COMPLETE`` and filter-verified, zero unresolved/conflicting identities, page
#: views not contradicted, verified and complete breadth, all three coverages at
#: the strong boundary ``STRONG_COMPONENT_COVERAGE`` (0.80), a 20-peer leave-one-
#: out reference, and six usable-field counts of 20. The plan §5.4 grade
#: conditions read discovery status/filter, identity counts, page-view semantics,
#: the three coverages, the run size, and the sensitivity warning; the remaining
#: required fields are carried as clean facts. ``field_usable_counts`` is a plain
#: six-key mapping (the test constructs ``FieldUsableCounts`` from it).
FINAL_EVIDENCE_BASE_EVIDENCE_KWARGS: dict[str, object] = {
    "discovery_status": DiscoveryStatus.COMPLETE,
    "discovery_filter_verified": True,
    "discovery_unresolved_identity_count": 0,
    "discovery_conflict_count": 0,
    "discovery_bounded_by_verified_total": True,
    "page_view_semantics_status": PageViewSemanticsStatus.UNVALIDATED,
    "breadth_source": BreadthSource.VERIFIED_TOTAL_COUNT,
    "breadth_completeness_status": BreadthCompletenessStatus.COMPLETE,
    "demand_stratum_eligibility_coverage": STRONG_COMPONENT_COVERAGE,
    "recent_supply_stratum_eligibility_coverage": STRONG_COMPONENT_COVERAGE,
    "quality_stratum_eligibility_coverage": STRONG_COMPONENT_COVERAGE,
    "reference_size": STRONG_REFERENCE_CATEGORY_COUNT - 1,
    "field_usable_counts": {
        "demand_per_asset_raw": STRONG_REFERENCE_CATEGORY_COUNT - 1,
        "demand_median_raw": STRONG_REFERENCE_CATEGORY_COUNT - 1,
        "breadth_raw": STRONG_REFERENCE_CATEGORY_COUNT - 1,
        "recent_share_raw": STRONG_REFERENCE_CATEGORY_COUNT - 1,
        "median_age_raw": STRONG_REFERENCE_CATEGORY_COUNT - 1,
        "quality_raw": STRONG_REFERENCE_CATEGORY_COUNT - 1,
    },
}

#: Base sample facts: the strong-policy sample boundary of 80 usable
#: observations for each sample-derived component, so
#: ``minimum_component_sample_count = 80`` (SRS §9.2 lines 1035-1040, 1049). The
#: category is not a census; ``discovered_population_count`` is then unused, and
#: its 0 is an explicit value, never a missing one (SRS §1.2).
FINAL_EVIDENCE_BASE_SAMPLE_KWARGS: dict[str, object] = {
    "sample_is_census": False,
    "discovered_population_count": 0,
    "usable_demand_sample_count": 80,
    "usable_recent_supply_sample_count": 80,
    "usable_quality_sample_count": 80,
}

#: Base decision facts: a pre-sensitivity ``RANKABLE`` decision with no reasons
#: and ``base_rankable=True`` (Chunk 9A semantics). State names are stored as
#: their frozen string values; the test constructs the ``StrEnum`` members.
FINAL_EVIDENCE_BASE_DECISION_KWARGS: dict[str, object] = {
    "evidence_state": "sufficient",
    "rankability_state": "rankable",
    "not_rankable_reasons": (),
    "provisional_reasons": (),
    "base_rankable": True,
}

#: Final-evidence vectors, keyed by label. The first four are the grade vectors
#: (strong/moderate/weak/insufficient); the remainder are the plan §9 variants
#: (null warning, warning True, census alternative, minimum-component count, the
#: sub-40 count with sub-strong coverage, and the 8-category provisional run).
FINAL_EVIDENCE_GRADE_VECTORS: dict[str, dict[str, object]] = {
    # The four grade vectors (SRS §9.2 lines 1047-1052; plan §9).
    #
    # strong: min(80, 80, 80) = 80 >= 80; every coverage 0.80 >= 0.80; verified
    # discovery (COMPLETE + filter verified); zero identity counts; page views
    # UNVALIDATED (not contradicted); run 21 >= 21; warning False -> STRONG.
    "strong": {
        "evidence_overrides": {},
        "sample_overrides": {},
        "decision_overrides": {},
        "run_category_count": STRONG_REFERENCE_CATEGORY_COUNT,
        "sensitivity_warning": False,
        "expected_minimum_component_sample_count": 80,
        "expected_grade": "strong",
    },
    # moderate: min(40, 40, 40) = 40 >= 40 (strong fails: 40 < 80) and every
    # coverage 0.50 >= 0.50 (strong fails: 0.50 < 0.80); run 21 >= 8; no
    # critical identity failure -> MODERATE.
    "moderate": {
        "evidence_overrides": {
            "demand_stratum_eligibility_coverage": MIN_REQUIRED_COMPONENT_COVERAGE,
            "recent_supply_stratum_eligibility_coverage": (
                MIN_REQUIRED_COMPONENT_COVERAGE
            ),
            "quality_stratum_eligibility_coverage": MIN_REQUIRED_COMPONENT_COVERAGE,
        },
        "sample_overrides": {
            "usable_demand_sample_count": 40,
            "usable_recent_supply_sample_count": 40,
            "usable_quality_sample_count": 40,
        },
        "decision_overrides": {},
        "run_category_count": STRONG_REFERENCE_CATEGORY_COUNT,
        "sensitivity_warning": False,
        "expected_minimum_component_sample_count": 40,
        "expected_grade": "moderate",
    },
    # weak: min(39, 39, 39) = 39 < 40, so strong and moderate both fail on the
    # sample count -> WEAK.
    "weak": {
        "evidence_overrides": {},
        "sample_overrides": {
            "usable_demand_sample_count": 39,
            "usable_recent_supply_sample_count": 39,
            "usable_quality_sample_count": 39,
        },
        "decision_overrides": {},
        "run_category_count": STRONG_REFERENCE_CATEGORY_COUNT,
        "sensitivity_warning": False,
        "expected_minimum_component_sample_count": 39,
        "expected_grade": "weak",
    },
    # insufficient: a non-empty not_rankable_reasons wins over every other
    # condition (SRS §9.2 line 1052), so even the strong sample facts grade
    # INSUFFICIENT.
    "insufficient": {
        "evidence_overrides": {},
        "sample_overrides": {},
        "decision_overrides": {
            "evidence_state": "insufficient",
            "rankability_state": "not_rankable",
            "not_rankable_reasons": ("unrecoverable_data_integrity_error",),
            "base_rankable": False,
        },
        "run_category_count": STRONG_REFERENCE_CATEGORY_COUNT,
        "sensitivity_warning": False,
        "expected_minimum_component_sample_count": 80,
        "expected_grade": "insufficient",
    },
    # The plan §9 variants.
    #
    # strong facts with sensitivity_warning None: strong requires
    # warning False (R6), moderate has no sensitivity condition -> MODERATE.
    "strong_null_warning": {
        "evidence_overrides": {},
        "sample_overrides": {},
        "decision_overrides": {},
        "run_category_count": STRONG_REFERENCE_CATEGORY_COUNT,
        "sensitivity_warning": None,
        "expected_minimum_component_sample_count": 80,
        "expected_grade": "moderate",
    },
    # strong facts with sensitivity_warning True: strong's acceptable-sensitivity
    # condition fails; moderate -> MODERATE.
    "strong_warning_true": {
        "evidence_overrides": {},
        "sample_overrides": {},
        "decision_overrides": {},
        "run_category_count": STRONG_REFERENCE_CATEGORY_COUNT,
        "sensitivity_warning": True,
        "expected_minimum_component_sample_count": 80,
        "expected_grade": "moderate",
    },
    # census alternative: population 50 >= 50 satisfies the strong count
    # condition although min count 0 < 80; coverages 0.80; verified; run 21;
    # warning False -> STRONG.
    "census_strong": {
        "evidence_overrides": {},
        "sample_overrides": {
            "sample_is_census": True,
            "discovered_population_count": 50,
            "usable_demand_sample_count": 0,
            "usable_recent_supply_sample_count": 0,
            "usable_quality_sample_count": 0,
        },
        "decision_overrides": {},
        "run_category_count": STRONG_REFERENCE_CATEGORY_COUNT,
        "sensitivity_warning": False,
        "expected_minimum_component_sample_count": 0,
        "expected_grade": "strong",
    },
    # population 20 >= 20 satisfies the moderate census alternative (strong
    # fails: 20 < 50); coverages 0.80 >= 0.50; run 21 -> MODERATE.
    "census_moderate": {
        "evidence_overrides": {},
        "sample_overrides": {
            "sample_is_census": True,
            "discovered_population_count": 20,
            "usable_demand_sample_count": 0,
            "usable_recent_supply_sample_count": 0,
            "usable_quality_sample_count": 0,
        },
        "decision_overrides": {},
        "run_category_count": STRONG_REFERENCE_CATEGORY_COUNT,
        "sensitivity_warning": False,
        "expected_minimum_component_sample_count": 0,
        "expected_grade": "moderate",
    },
    # min(80, 40, 80) = 40: strong fails (40 < 80), moderate passes (40 >= 40);
    # the two 80s cannot raise the minimum -> MODERATE.
    "min_component_moderate": {
        "evidence_overrides": {},
        "sample_overrides": {
            "usable_demand_sample_count": 80,
            "usable_recent_supply_sample_count": 40,
            "usable_quality_sample_count": 80,
        },
        "decision_overrides": {},
        "run_category_count": STRONG_REFERENCE_CATEGORY_COUNT,
        "sensitivity_warning": False,
        "expected_minimum_component_sample_count": 40,
        "expected_grade": "moderate",
    },
    # min(80, 80, 39) = 39 < 40: one low component count drags the grade down
    # -> WEAK.
    "min_component_weak": {
        "evidence_overrides": {},
        "sample_overrides": {
            "usable_demand_sample_count": 80,
            "usable_recent_supply_sample_count": 80,
            "usable_quality_sample_count": 39,
        },
        "decision_overrides": {},
        "run_category_count": STRONG_REFERENCE_CATEGORY_COUNT,
        "sensitivity_warning": False,
        "expected_minimum_component_sample_count": 39,
        "expected_grade": "weak",
    },
    # min 39 < 40 and coverages 0.60 (above the required 0.50, below the strong
    # 0.80): the count alone already fails moderate -> WEAK. Note: coverage 0.60
    # with a count >= 40 would be MODERATE under SRS §9.2 line 1050, so this row
    # is only weak together with the sub-40 count.
    "weak_low_count_and_coverage": {
        "evidence_overrides": {
            "demand_stratum_eligibility_coverage": 0.60,
            "recent_supply_stratum_eligibility_coverage": 0.60,
            "quality_stratum_eligibility_coverage": 0.60,
        },
        "sample_overrides": {
            "usable_demand_sample_count": 39,
            "usable_recent_supply_sample_count": 39,
            "usable_quality_sample_count": 39,
        },
        "decision_overrides": {},
        "run_category_count": STRONG_REFERENCE_CATEGORY_COUNT,
        "sensitivity_warning": False,
        "expected_minimum_component_sample_count": 39,
        "expected_grade": "weak",
    },
    # 8-category provisional run: run 8 < 21 fails strong; moderate needs
    # min 80 >= 40, coverages 0.80 >= 0.50, run 8 >= 8, and no critical identity
    # failure -> MODERATE (an 8-20 category run is never rankable but may be
    # provisional; SRS §9.1 line 1008). reference_size 7 mirrors the 8-category
    # run (one leave-one-out peer per other category).
    "eight_category": {
        "evidence_overrides": {
            "reference_size": MIN_CATEGORIES_PER_RUN - 1,
        },
        "sample_overrides": {},
        "decision_overrides": {
            "evidence_state": "provisional_only",
            "rankability_state": "provisional",
            "provisional_reasons": ("run_below_strong_reference",),
            "base_rankable": False,
        },
        "run_category_count": MIN_CATEGORIES_PER_RUN,
        "sensitivity_warning": False,
        "expected_minimum_component_sample_count": 80,
        "expected_grade": "moderate",
    },
}

# ---------------------------------------------------------------------------
# Final-rankability vectors (SRS-lean.md §9.1 LREQ-EVD-040; plan §5.5, R7)
# ---------------------------------------------------------------------------
#
# Each row is (label, decision_overrides, sensitivity_warning, expected_status).
# Overrides apply over ``FINAL_EVIDENCE_BASE_DECISION_KWARGS`` (a pre-sensitivity
# RANKABLE decision with no reasons). State names are stored as their frozen
# string values; the test constructs the StrEnum members. Sensitivity demotes
# only to ``provisional``; a null warning on a pre-sensitivity RANKABLE category
# is ``provisional`` (R7), and NOT_RANKABLE is never overridden.

FINAL_RANKABILITY_VECTORS: tuple[
    tuple[str, dict[str, object], bool | None, str], ...
] = (
    ("rankable_warning_false", {}, False, "rankable"),
    ("rankable_warning_true", {}, True, "provisional"),
    ("rankable_warning_none", {}, None, "provisional"),
    # The 8-20 category run: an empty candidate set and a provisional decision
    # (any provisional reason maps the same way) stays provisional.
    (
        "pre_sensitivity_provisional",
        {
            "evidence_state": "provisional_only",
            "rankability_state": "provisional",
            "provisional_reasons": ("run_below_strong_reference",),
            "base_rankable": False,
        },
        False,
        "provisional",
    ),
    # A not-rankable decision is never overridden by sensitivity (even True).
    (
        "pre_sensitivity_not_rankable",
        {
            "evidence_state": "insufficient",
            "rankability_state": "not_rankable",
            "not_rankable_reasons": ("required_demand_data_unavailable",),
            "base_rankable": False,
        },
        True,
        "not_rankable",
    ),
)
